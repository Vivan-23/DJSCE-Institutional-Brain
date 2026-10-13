"""Shared test helpers."""
from sqlmodel import Session, create_engine, select

from app.models.structured import User
from tests.conftest import TEST_DB_URL

_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})


def set_role(email: str, role: str) -> None:
    with Session(_engine) as db:
        user = db.exec(select(User).where(User.email == email)).first()
        user.role = role
        db.add(user)
        db.commit()


def register(client, email: str, full_name: str = "Test User", role: str = "employee") -> str:
    """Register (or log in) ``email`` and return a JWT for a user holding ``role``.

    Self-registration always creates a student; the role is then set directly in
    the DB, which ``get_current_user`` reads on every request.
    """
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": full_name, "password": "pass1234"},
    )
    if res.status_code == 400:
        res = client.post("/api/v1/auth/login", json={"email": email, "password": "pass1234"})
    set_role(email, role)
    return res.json()["access_token"]
