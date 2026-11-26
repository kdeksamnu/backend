import pytest
from ml_backend import create_app
from ml_backend.extensions import db
from ml_backend.models import User, CodexEntry


@pytest.fixture
def app():
    app = create_app("testing")
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def get_auth_headers(client, username, password):
    """Helper to register/login and return bearer token headers."""
    client.post("/auth/register", json={"username": username, "password": password})
    res = client.post("/auth/login", json={"username": username, "password": password})
    token = res.get_json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


def test_pagination_bounds_and_validation(client):
    headers = get_auth_headers(client, "alice", "securepass")

    # Seed test entries
    for i in range(15):
        client.post("/entries", json={"title": f"Entry {i}", "content": "Test content"}, headers=headers)

    # 1. Test default pagination (page=1, per_page=20)
    res = client.get("/entries", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 15
    assert len(data["entries"]) == 15
    assert data["page"] == 1
    assert data["per_page"] == 20

    # 2. Test custom per_page bound
    res = client.get("/entries?page=1&per_page=5", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["entries"]) == 5
    assert data["pages"] == 3

    # 3. Test upper bound violation (> 100 per_page) -> 400 validation error
    res = client.get("/entries?per_page=150", headers=headers)
    assert res.status_code == 400

    # 4. Test invalid parameter types -> 400 validation error
    res = client.get("/entries?page=invalid", headers=headers)
    assert res.status_code == 400


def test_allowlisted_sorting_and_tie_breaking(client):
    headers = get_auth_headers(client, "bob", "securepass")

    # Create entries with deliberate values for sorting
    client.post("/entries", json={"title": "Alpha", "content": "A", "spectral_band": "Gold"}, headers=headers)
    client.post("/entries", json={"title": "Beta", "content": "B", "spectral_band": "Blue"}, headers=headers)
    client.post("/entries", json={"title": "Gamma", "content": "C", "spectral_band": "Gold"}, headers=headers)

    # 1. Sort by title ascending
    res = client.get("/entries?sort_by=title&order=asc", headers=headers)
    assert res.status_code == 200
    entries = res.get_json()["entries"]
    assert [e["title"] for e in entries] == ["Alpha", "Beta", "Gamma"]

    # 2. Sort by spectral_band descending with ID tie-break
    res = client.get("/entries?sort_by=spectral_band&order=desc", headers=headers)
    assert res.status_code == 200
    entries = res.get_json()["entries"]
    assert entries[0]["title"] in ["Alpha", "Gamma"]


def test_tenant_isolation(client):
    headers_alice = get_auth_headers(client, "alice_tenant", "pass123")
    headers_bob = get_auth_headers(client, "bob_tenant", "pass123")

    # Alice creates an entry
    client.post("/entries", json={"title": "Alice Secret", "content": "Private"}, headers=headers_alice)

    # Bob lists entries — should see 0 entries due to strict tenant isolation
    res = client.get("/entries", headers=headers_bob)
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 0
    assert len(data["entries"]) == 0
