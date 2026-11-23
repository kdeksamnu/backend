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


def test_user_codex_entries_relationship_and_cascade_delete():
    """Verify User.codex_entries, CodexEntry.owner, and ON DELETE CASCADE."""
    from sqlalchemy import event
    from ml_backend import create_app
    from ml_backend.extensions import db
    from ml_backend.models import User, CodexEntry

    app = create_app("testing")

    with app.app_context():
        def _enable_sqlite_fks(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        if db.engine.url.get_backend_name() == "sqlite":
            event.listen(db.engine, "connect", _enable_sqlite_fks)

        db.create_all()

        user = User(username="cascade_test_architect", role="user")
        user.set_password("CascadePass123!")
        db.session.add(user)
        db.session.flush()

        entry_one = CodexEntry(
            user_id=user.id,
            title="Chamber I: Rupes Nigra",
            spectral_band="teal",
            content="Exploratory mechanics anchored along the Teal axis.",
        )
        entry_two = CodexEntry(
            user_id=user.id,
            title="Chamber II: The Seventh Chair",
            spectral_band="blue",
            content="Excavation of inheritance anchored along the Blue axis.",
        )
        db.session.add_all([entry_one, entry_two])
        db.session.commit()

        user_id = user.id
        entry_ids = [entry_one.id, entry_two.id]

        # 1. Forward traversal: User -> codex_entries (One -> Many)
        persisted_user = db.session.get(User, user_id)
        assert len(persisted_user.codex_entries) == 2
        assert {e.title for e in persisted_user.codex_entries} == {
            "Chamber I: Rupes Nigra",
            "Chamber II: The Seventh Chair",
        }

        # 2. Reverse traversal: CodexEntry -> owner (Many -> One)
        for entry in persisted_user.codex_entries:
            assert entry.owner is not None
            assert entry.owner.id == user_id
            assert entry.owner.username == "cascade_test_architect"

        # 3. Cascade delete: deleting User removes owned CodexEntry rows
        db.session.delete(persisted_user)
        db.session.commit()

        assert db.session.get(User, user_id) is None
        remaining = CodexEntry.query.filter(CodexEntry.id.in_(entry_ids)).all()
        assert remaining == []

        db.session.remove()
        db.drop_all()


def test_entry_detail_update_delete_edge_cases():
    """Verify 404 Not Found, PATCH field validation, cross-user 403 isolation, and DELETE persistence."""
    from ml_backend import create_app
    from ml_backend.extensions import db

    app = create_app("testing")
    client = app.test_client()

    with app.app_context():
        db.create_all()

    # Register & authenticate Owner (User A) and Intruder (User B)
    assert client.post("/register", json={"username": "detail_owner", "password": "Password123!"}).status_code == 201
    token_a = client.post("/login", json={"username": "detail_owner", "password": "Password123!"}).get_json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    assert client.post("/register", json={"username": "detail_intruder", "password": "Password123!"}).status_code == 201
    token_b = client.post("/login", json={"username": "detail_intruder", "password": "Password123!"}).get_json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. 404 Not Found on non-existent entry ID across GET, PATCH, and DELETE
    for method in ("get", "patch", "delete"):
        req_kwargs = {"headers": headers_a}
        if method == "patch":
            req_kwargs["json"] = {"title": "Ghost Update"}
        res = getattr(client, method)("/entries/999999", **req_kwargs)
        assert res.status_code == 404
        assert res.get_json()["error"]["code"] == "NOT_FOUND"

    # Create an owned entry as User A
    create_res = client.post(
        "/entries",
        json={
            "title": "Chamber IV: The Anchor of the Abyss",
            "spectral_band": "gold",
            "content": "Initial sovereign inscription.",
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    entry_id = create_res.get_json()["entry"]["id"]

    # 2. Cross-user 403 Forbidden isolation on GET, PATCH, and DELETE
    for method in ("get", "patch", "delete"):
        req_kwargs = {"headers": headers_b}
        if method == "patch":
            req_kwargs["json"] = {"title": "Hijacked Title"}
        res = getattr(client, method)(f"/entries/{entry_id}", **req_kwargs)
        assert res.status_code == 403
        assert res.get_json()["error"]["code"] == "FORBIDDEN"

    # 3. PATCH validation errors on owner's entry (empty object, protected user_id, blank title/content, bad spectral_band)
    empty_patch = client.patch(f"/entries/{entry_id}", json={}, headers=headers_a)
    assert empty_patch.status_code == 400
    assert empty_patch.get_json()["error"]["code"] == "VALIDATION_ERROR"

    spoof_patch = client.patch(f"/entries/{entry_id}", json={"user_id": 2}, headers=headers_a)
    assert spoof_patch.status_code == 400
    assert "user_id" in spoof_patch.get_json()["error"]["details"]

    invalid_fields_patch = client.patch(
        f"/entries/{entry_id}",
        json={"title": "   ", "content": "", "spectral_band": "infrared"},
        headers=headers_a,
    )
    assert invalid_fields_patch.status_code == 400
    details = invalid_fields_patch.get_json()["error"]["details"]
    assert "title" in details
    assert "content" in details
    assert "spectral_band" in details

    # 4. Valid partial PATCH updates only supplied fields and persists
    valid_patch = client.patch(
        f"/entries/{entry_id}",
        json={"title": "  Chamber IV: Revised Anchor  ", "spectral_band": "EMERALD"},
        headers=headers_a,
    )
    assert valid_patch.status_code == 200
    updated_entry = valid_patch.get_json()["entry"]
    assert updated_entry["title"] == "Chamber IV: Revised Anchor"
    assert updated_entry["spectral_band"] == "emerald"
    assert updated_entry["content"] == "Initial sovereign inscription."

    # 5. DELETE removes entry and subsequent GET/PATCH/DELETE return 404 Not Found
    del_res = client.delete(f"/entries/{entry_id}", headers=headers_a)
    assert del_res.status_code == 200
    assert del_res.get_json() == {"deleted": True, "id": entry_id}

    post_del_get = client.get(f"/entries/{entry_id}", headers=headers_a)
    assert post_del_get.status_code == 404
    assert post_del_get.get_json()["error"]["code"] == "NOT_FOUND"

    list_after_del = client.get("/entries", headers=headers_a)
    assert list_after_del.status_code == 200
    assert list_after_del.get_json() == {"entries": []}

    with app.app_context():
        db.session.remove()
        db.drop_all()
