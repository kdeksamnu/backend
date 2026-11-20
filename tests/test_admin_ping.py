import pytest
from ml_backend import create_app
from ml_backend.extensions import db
from ml_backend.models import User


@pytest.fixture
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_admin_ping_without_token_returns_401(client):
    res = client.get("/admin/ping")

    assert res.status_code == 401
    assert res.get_json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Missing or malformed Authorization header.",
            "details": {},
        }
    }


def test_admin_ping_with_user_token_returns_403(client):
    reg = client.post("/register", json={"username": "standard_user", "password": "Password123!"})
    assert reg.status_code == 201

    login = client.post("/login", json={"username": "standard_user", "password": "Password123!"})
    assert login.status_code == 200
    assert login.get_json()["user"]["role"] == "user"
    token = login.get_json()["access_token"]

    res = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 403
    assert res.get_json() == {
        "error": {
            "code": "FORBIDDEN",
            "message": "Administrator privileges are required.",
            "details": {},
        }
    }


def test_admin_ping_with_admin_token_returns_200(client):
    admin = User(username="prime_admin", role="admin")
    admin.set_password("Secret123!")
    db.session.add(admin)
    db.session.commit()

    login = client.post("/login", json={"username": "prime_admin", "password": "Secret123!"})
    assert login.status_code == 200
    assert login.get_json()["user"]["role"] == "admin"
    token = login.get_json()["access_token"]

    res = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert body["message"] == "Admin access verified."
    assert body["user"]["username"] == "prime_admin"
    assert body["user"]["role"] == "admin"
    assert "password_hash" not in body["user"]
