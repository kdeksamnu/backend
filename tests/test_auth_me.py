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


def test_get_me_returns_authenticated_user(client):
    reg = client.post("/register", json={"username": "active_op", "password": "Password123!"})
    assert reg.status_code == 201

    login = client.post("/login", json={"username": "active_op", "password": "Password123!"})
    token = login.get_json()["access_token"]

    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["user"]["username"] == "active_op"
    assert "password_hash" not in body["user"]


def test_get_me_rejects_valid_jwt_for_deleted_user(client):
    reg = client.post("/register", json={"username": "ephemeral_op", "password": "Password123!"})
    user_id = reg.get_json()["user"]["id"]

    login = client.post("/login", json={"username": "ephemeral_op", "password": "Password123!"})
    token = login.get_json()["access_token"]

    # Delete the user while their JWT is still unexpired
    user = db.session.get(User, user_id)
    db.session.delete(user)
    db.session.commit()

    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.get_json() == {
        "error": {
            "code": "USER_NOT_FOUND",
            "message": "Authenticated user no longer exists.",
            "details": {},
        }
    }
