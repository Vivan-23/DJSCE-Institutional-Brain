from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlmodel import Session, select
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt

from app.core.config import settings
from app.core.db import get_session
from app.models.structured import User

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    full_name: str
    password: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_session),
) -> User:
    credentials_exc = HTTPException(
        status_code=401,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str | None = payload.get("sub")
        if not email:
            raise credentials_exc
    except jwt.PyJWTError:
        raise credentials_exc

    user = db.exec(select(User).where(User.email == email)).first()
    if not user:
        raise credentials_exc
    return user


# Role-based access control (security/NFR: role-based access).
# Roles, least → most privileged:
#   student < employee (Faculty) < manager (Committee Coordinator) < admin (System Administrator)
_ROLE_RANK = {"student": 0, "employee": 1, "manager": 2, "admin": 3}


def require_role(*allowed_roles: str):
    """Dependency factory: ensure the current user holds one of ``allowed_roles``
    (or a higher-privileged role). Use on endpoints that need elevation, e.g.
    ``Depends(require_role("manager"))`` for skill approval."""
    min_rank = min((_ROLE_RANK.get(r, 99) for r in allowed_roles), default=99)

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if _ROLE_RANK.get(current_user.role, -1) < min_rank:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role: {' or '.join(allowed_roles)}",
            )
        return current_user

    return _checker


# Any staff member (faculty and above). Gate internal institutional data with this —
# students must never reach meetings, commitments, procedures under review, or the graph.
require_staff = require_role("employee")


def is_staff(user: User) -> bool:
    return _ROLE_RANK.get(user.role, -1) >= _ROLE_RANK["employee"]


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_session)):
    if db.exec(select(User).where(User.email == req.email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(req.password),
        # Least privilege: self-registration creates a student account. Staff roles
        # come from institution.yaml or an administrator.
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.email == req.email)).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }
