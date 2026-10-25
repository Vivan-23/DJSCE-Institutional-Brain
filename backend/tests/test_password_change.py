"""First login: administrator-issued temporary passwords must be replaced by the person."""
from tests.helpers import register


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _new_faculty(client, admin: str, email: str, **extra) -> dict:
    res = client.post("/api/v1/admin/users", headers=_auth(admin),
                      json={"email": email, "full_name": "New Faculty", "role": "employee", **extra})
    assert res.status_code == 201
    return res.json()


def test_temporary_password_requires_a_change(client):
    admin = register(client, "pw.admin@test.com", role="admin")
    created = _new_faculty(client, admin, "pw.fac1@test.com")
    assert created["must_change_password"] is True
    token = _login(client, "pw.fac1@test.com", created["temporary_password"]).json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=_auth(token)).json()["must_change_password"] is True

    res = client.post("/api/v1/auth/change-password", headers=_auth(token),
                      json={"current_password": created["temporary_password"], "new_password": "my-own-pass"})
    assert res.status_code == 200
    assert client.get("/api/v1/auth/me", headers=_auth(token)).json()["must_change_password"] is False
    assert _login(client, "pw.fac1@test.com", "my-own-pass").status_code == 200
    assert _login(client, "pw.fac1@test.com", created["temporary_password"]).status_code == 401


def test_change_password_rejects_bad_input(client):
    admin = register(client, "pw.admin2@test.com", role="admin")
    created = _new_faculty(client, admin, "pw.fac2@test.com")
    temp = created["temporary_password"]
    token = _login(client, "pw.fac2@test.com", temp).json()["access_token"]
    for body in ({"current_password": "wrong", "new_password": "long-enough-1"},
                 {"current_password": temp, "new_password": "short"},
                 {"current_password": temp, "new_password": temp}):
        assert client.post("/api/v1/auth/change-password", headers=_auth(token), json=body).status_code == 400
    assert client.post("/api/v1/auth/change-password",
                       json={"current_password": temp, "new_password": "long-enough-1"}).status_code == 401


def test_chosen_password_and_reset_set_the_flag_correctly(client):
    admin = register(client, "pw.admin3@test.com", role="admin")
    chosen = _new_faculty(client, admin, "pw.fac3@test.com", password="admin-chosen")
    assert chosen["must_change_password"] is False
    res = client.post(f"/api/v1/admin/users/{chosen['id']}/reset-password", headers=_auth(admin), json={})
    assert res.status_code == 200 and res.json()["temporary_password"]
    users = client.get("/api/v1/admin/users?q=pw.fac3", headers=_auth(admin)).json()
    assert users[0]["must_change_password"] is True


def test_csv_import_marks_generated_passwords(client):
    admin = register(client, "pw.admin4@test.com", role="admin")
    csv = "email,full_name,role\npw.csv1@test.com,A,employee\npw.csv2@test.com,B,employee\n"
    res = client.post("/api/v1/admin/users/import", headers=_auth(admin), files={"file": ("u.csv", csv, "text/csv")})
    assert res.status_code == 200
    users = client.get("/api/v1/admin/users?q=pw.csv", headers=_auth(admin)).json()
    assert len(users) == 2 and all(u["must_change_password"] for u in users)
