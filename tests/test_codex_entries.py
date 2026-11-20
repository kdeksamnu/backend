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


def _register_and_login(client, username: str, password: str = "Password123!") -> tuple[int, str]:
    reg = client.post("/register", json={"username": username, "password": password})
    assert reg.status_code == 201
    user_id = reg.get_json()["user"]["id"]
    login = client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return user_id, login.get_json()["access_token"]


def _create_admin_and_login(client, username: str = "prime_admin", password: str = "Secret123!") -> str:
    admin = User(username=username, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    login = client.post("/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return login.get_json()["access_token"]


def test_entries_require_authentication_401(client):
    assert client.get("/entries").status_code == 401
    assert client.post("/entries", json={"title": "Unauth", "content": "Blocked"}).status_code == 401
    assert client.get("/entries/1").status_code == 401
    assert client.patch("/entries/1", json={"title": "New"}).status_code == 401
    assert client.delete("/entries/1").status_code == 401


def test_owner_crud_and_cross_user_403_isolation(client):
    user1_id, tok1 = _register_and_login(client, "vaultwalker_1")
    _, tok2 = _register_and_login(client, "vaultwalker_2")

    # Owner creates entry (user_id set from token, not body)
    create_res = client.post(
        "/entries",
        headers={"Authorization": f"Bearer {tok1}"},
        json={
            "title": "Rupes Nigra Bearing",
            "spectral_band": "teal",
            "content": "Magnetic declination stabilizes near the inner ring.",
        },
    )
    assert create_res.status_code == 201
    entry = create_res.get_json()["entry"]
    assert entry["user_id"] == user1_id
    entry_id = entry["id"]

    # Spoofing user_id in body is rejected with 400
    spoof_res = client.post(
        "/entries",
        headers={"Authorization": f"Bearer {tok1}"},
        json={"user_id": 999, "title": "Spoof", "content": "Attempt"},
    )
    assert spoof_res.status_code == 400

    # List isolation: user2 sees empty list; user1 sees own entry
    list_u2 = client.get("/entries", headers={"Authorization": f"Bearer {tok2}"})
    assert list_u2.status_code == 200
    assert list_u2.get_json()["entries"] == []

    list_u1 = client.get("/entries", headers={"Authorization": f"Bearer {tok1}"})
    assert len(list_u1.get_json()["entries"]) == 1

    # Cross-user GET, PATCH, DELETE -> 403 FORBIDDEN
    assert client.get(f"/entries/{entry_id}", headers={"Authorization": f"Bearer {tok2}"}).status_code == 403
    assert (
        client.patch(
            f"/entries/{entry_id}",
            headers={"Authorization": f"Bearer {tok2}"},
            json={"title": "Hijacked"},
        ).status_code
        == 403
    )
    assert client.delete(f"/entries/{entry_id}", headers={"Authorization": f"Bearer {tok2}"}).status_code == 403

    # Owner PATCH succeeds -> 200
    patch_u1 = client.patch(
        f"/entries/{entry_id}",
        headers={"Authorization": f"Bearer {tok1}"},
        json={"title": "Rupes Nigra Bearing (Calibrated)", "spectral_band": "gold"},
    )
    assert patch_u1.status_code == 200
    assert patch_u1.get_json()["entry"]["spectral_band"] == "gold"


def test_admin_override_on_user_owned_entries(client):
    _, tok1 = _register_and_login(client, "citizen_alpha")
    admin_tok = _create_admin_and_login(client)

    create_res = client.post(
        "/entries",
        headers={"Authorization": f"Bearer {tok1}"},
        json={"title": "Harmonic Scar Note", "content": "Shear line stabilized."},
    )
    entry_id = create_res.get_json()["entry"]["id"]

    # Admin can list, read, patch, and delete another user's entry
    admin_list = client.get("/entries", headers={"Authorization": f"Bearer {admin_tok}"})
    assert admin_list.status_code == 200
    assert len(admin_list.get_json()["entries"]) == 1

    admin_get = client.get(f"/entries/{entry_id}", headers={"Authorization": f"Bearer {admin_tok}"})
    assert admin_get.status_code == 200

    admin_patch = client.patch(
        f"/entries/{entry_id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"spectral_band": "null"},
    )
    assert admin_patch.status_code == 200
    assert admin_patch.get_json()["entry"]["spectral_band"] == "null"

    admin_del = client.delete(f"/entries/{entry_id}", headers={"Authorization": f"Bearer {admin_tok}"})
    assert admin_del.status_code == 200

    assert client.get(f"/entries/{entry_id}", headers={"Authorization": f"Bearer {admin_tok}"}).status_code == 404
