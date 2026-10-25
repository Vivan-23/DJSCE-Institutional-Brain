"""System Administrator: user management and the (fixed) role permission table."""
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.auth import require_role
from app.core.db import get_session
from app.models.structured import User
from app.services.user_service import UserError, serialize, user_service

router = APIRouter()
require_admin = require_role("admin")

# What each role may do. Permissions are fixed in code (enforced by require_staff /
# require_role on each router); this table only describes them for the admin page.
ROLE_PERMISSIONS = [
    {"capability": "Help Desk: ask questions, raise and track own tickets", "roles": ["student", "employee", "manager", "admin"]},
    {"capability": "Assistant answers from public knowledge (own department + institution-wide)", "roles": ["student"]},
    {"capability": "Assistant answers from internal knowledge (own department + institution-wide)", "roles": ["employee"]},
    {"capability": "Assistant answers from every department", "roles": ["manager", "admin"]},
    {"capability": "Calendar and deadline reminders", "roles": ["student", "employee", "manager", "admin"]},
    {"capability": "Notices: read notices addressed to me", "roles": ["student", "employee", "manager", "admin"]},
    {"capability": "Notices: send to students of own department", "roles": ["employee"]},
    {"capability": "Notices: send to any department", "roles": ["manager", "admin"]},
    {"capability": "Help Desk Queue: triage, AI draft, reply", "roles": ["employee", "manager", "admin"]},
    {"capability": "Meetings, commitments, Faculty Desk, documents, knowledge graph", "roles": ["employee", "manager", "admin"]},
    {"capability": "Approve procedures, export minutes, analytics, audit log", "roles": ["manager", "admin"]},
    {"capability": "Manage users", "roles": ["admin"]},
]


class UserCreate(BaseModel):
    email: str
    full_name: Optional[str] = None
    role: str = "student"
    department: Optional[str] = None
    year: Optional[int] = None
    semester: Optional[int] = None
    division: Optional[str] = None
    password: Optional[str] = None  # omitted → a temporary password is generated and returned once


class UserUpdate(BaseModel):
    email: Optional[str] = None  # the login; changing it ends the person's current session
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    year: Optional[int] = None
    semester: Optional[int] = None
    division: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    password: Optional[str] = None


def _get(db: Session, user_id: str) -> User:
    user = user_service.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/roles")
def roles(current_user: User = Depends(require_admin)):
    return {"roles": ["student", "employee", "manager", "admin"], "permissions": ROLE_PERMISSIONS}


@router.get("/users")
def list_users(
    q: Optional[str] = None,
    role: Optional[str] = None,
    department: Optional[str] = None,
    active: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_session),
):
    return [serialize(u) for u in user_service.list(db, q=q, role=role, department=department, active=active)]


@router.post("/users", status_code=201)
def create_user(req: UserCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_session)):
    try:
        user, password = user_service.create(db, current_user, req.model_dump())
    except UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**serialize(user), "temporary_password": None if req.password else password}


@router.patch("/users/{user_id}")
def update_user(
    user_id: str, req: UserUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    data = req.model_dump(exclude_unset=True)
    email = data.pop("email", None)
    try:
        user = _get(db, user_id)
        if email is not None:
            user = user_service.change_email(db, current_user, user, email)
        if data:
            user = user_service.update(db, current_user, user, data)
    except UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return serialize(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: str, req: PasswordReset, current_user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    try:
        password = user_service.reset_password(db, current_user, _get(db, user_id), req.password)
    except UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"temporary_password": None if req.password else password}


@router.post("/users/import")
async def import_users(
    file: UploadFile = File(...), current_user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV exceeds 2 MB")
    try:
        return user_service.import_csv(db, current_user, raw.decode("utf-8"))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="The CSV must be UTF-8 text")
    except UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
