from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlmodel import Session, select
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
import jwt

from app.core.config import settings
from app.core.db import get_session
from app.core.institution_config import ALL_DEPARTMENTS, get_institution_config
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
    department: Optional[str] = None  # code or name from institution.yaml
    year: Optional[int] = None  # 1-4
    semester: Optional[int] = None  # 1-8
    division: Optional[str] = None


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
    if not user or not user.is_active:  # deactivation takes effect on the next request
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


def require_exact_roles(*roles: str):
    """Dependency factory: only the listed roles, with no inheritance by higher ranks.
    For features that belong to a responsibility rather than a privilege level
    (e.g. the Help Desk is for students and faculty, not coordinators)."""
    allowed = set(roles)

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=403, detail=f"Available to: {', '.join(roles)}")
        return current_user

    return _checker


# Help Desk: students raise tickets, faculty answer them (V2 product rule).
require_helpdesk_user = require_exact_roles("student", "employee")
# Ticket queue: faculty handle it; administrators may read it for oversight.
require_ticket_reader = require_exact_roles("employee", "admin")
require_ticket_handler = require_exact_roles("employee")


def is_staff(user: User) -> bool:
    return _ROLE_RANK.get(user.role, -1) >= _ROLE_RANK["employee"]


def department_scope(user: User) -> Optional[list[str]]:
    """Departments whose material ``user`` may retrieve; None = unrestricted.

    Coordinators and administrators work across departments. Students and faculty see
    their own department's material plus institution-wide ("all") material; with no
    department on record they see institution-wide material only (fail closed).
    """
    if _ROLE_RANK.get(user.role, -1) >= _ROLE_RANK["manager"]:
        return None
    return [user.department, ALL_DEPARTMENTS] if user.department else [ALL_DEPARTMENTS]


def parse_department(value: Optional[str]) -> str:
    """An ingestion request's department: a known code/name, or "all" when omitted. 400 otherwise."""
    if not value or value.strip().lower() == ALL_DEPARTMENTS:
        return ALL_DEPARTMENTS
    code = get_institution_config().department_code(value)
    if not code:
        raise HTTPException(status_code=400, detail=f"Unknown department '{value}'")
    return code


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_session)):
    if db.exec(select(User).where(User.email == req.email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    department = get_institution_config().department_code(req.department)
    if req.department and not department:
        raise HTTPException(status_code=400, detail=f"Unknown department '{req.department}'")
    if req.year is not None and not 1 <= req.year <= 4:
        raise HTTPException(status_code=400, detail="year must be between 1 and 4")
    if req.semester is not None and not 1 <= req.semester <= 8:
        raise HTTPException(status_code=400, detail="semester must be between 1 and 8")
    user = User(
        email=req.email,
        full_name=req.full_name,
        hashed_password=hash_password(req.password),
        # Least privilege: self-registration creates a student account. Staff roles
        # come from institution.yaml or an administrator.
        role="student",
        department=department,
        year=req.year,
        semester=req.semester,
        division=(req.division or "").strip().upper() or None,
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
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    token = create_access_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "department": current_user.department,
        "year": current_user.year,
        "semester": current_user.semester,
        "division": current_user.division,
    }
