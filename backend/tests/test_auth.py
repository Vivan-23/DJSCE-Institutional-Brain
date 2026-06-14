"""Tests for authentication: password hashing, JWT creation, register, and login."""
import pytest
from app.api.v1.auth import hash_password, verify_password, create_access_token
import jwt


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        assert hash_password("secret") != "secret"

    def test_correct_password_verifies(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_same_password_produces_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses a random salt


class TestJWT:
    def test_token_contains_sub(self):
        from app.core.config import settings
        token = create_access_token({"sub": "user@example.com", "role": "admin"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "user@example.com"

    def test_token_has_expiry(self):
        from app.core.config import settings
        token = create_access_token({"sub": "user@example.com"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload


class TestAuthEndpoints:
    def test_register_new_user(self, client):
        res = client.post(
            "/api/v1/auth/register",
            json={"email": "new@test.com", "full_name": "Test User", "password": "pass1234"},
        )
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email_returns_400(self, client):
        payload = {"email": "dup@test.com", "full_name": "Dup", "password": "pass1234"}
        client.post("/api/v1/auth/register", json=payload)
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 400

    def test_login_with_valid_credentials(self, client):
        # Register first
        client.post(
            "/api/v1/auth/register",
            json={"email": "login@test.com", "full_name": "Login User", "password": "pass1234"},
        )
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "pass1234"},
        )
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_login_with_wrong_password_returns_401(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "bad@test.com", "full_name": "Bad", "password": "correct"},
        )
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "bad@test.com", "password": "wrong"},
        )
        assert res.status_code == 401

    def test_protected_endpoint_requires_token(self, client):
        res = client.get("/api/v1/graph/data")
        assert res.status_code == 401

    def test_me_endpoint_returns_user_info(self, client):
        reg = client.post(
            "/api/v1/auth/register",
            json={"email": "me@test.com", "full_name": "Me User", "password": "pass1234"},
        )
        token = reg.json()["access_token"]
        res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["email"] == "me@test.com"
