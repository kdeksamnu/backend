import pytest

from ml_backend import create_app
from ml_backend.config import config_by_name
from ml_backend.extensions import db
from ml_backend.views.entries import VALID_SPECTRAL_BANDS


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Isolated Flask test client backed by a fresh temporary SQLite database."""
    db_file = tmp_path / "entries_pagination_test.db"
    monkeypatch.setattr(
        config_by_name["testing"],
        "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{db_file}",
    )

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        with app.test_client() as test_client:
            yield test_client
        db.session.remove()
        db.engine.dispose()


def _get_bands():
    bands = list(VALID_SPECTRAL_BANDS)
    assert len(bands) >= 1, "VALID_SPECTRAL_BANDS must contain at least one band"
    primary = bands[0]
    secondary = bands[1] if len(bands) > 1 else bands[0]
    return primary, secondary


def _register_and_login(client, username, password="TestPassword123!"):
    reg = client.post(
        "/register",
        json={"username": username, "password": password},
    )
    assert reg.status_code in (200, 201), f"Register failed: {reg.status_code} {reg.get_json()}"

    login = client.post(
        "/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, f"Login failed: {login.status_code} {login.get_json()}"
    body = login.get_json()
    token = body.get("access_token") or body.get("token") or body.get("data", {}).get("access_token")
    assert token, f"JWT token missing from login response: {body}"
    return {"Authorization": f"Bearer {token}"}


def _seed_entries(client, headers, count, band, prefix="Codex Entry"):
    created = []
    for i in range(1, count + 1):
        resp = client.post(
            "/entries",
            headers=headers,
            json={
                "title": f"{prefix} {i:02d}",
                "spectral_band": band,
                "content": f"Content payload {i:02d}",
            },
        )
        assert resp.status_code in (200, 201), f"Seed #{i} failed: {resp.status_code} {resp.get_json()}"
        created.append(resp.get_json())
    return created


def test_pagination_pages_and_past_the_end_empty_slice(client):
    """Covers page 1 (5 items), page 3 (4 items), and past-the-end page 4 (200 with [])."""
    band, _ = _get_bands()
    headers = _register_and_login(client, "page_user")
    _seed_entries(client, headers, count=14, band=band)

    # Page 1: 5 items
    r1 = client.get("/entries?page=1&per_page=5", headers=headers)
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert len(d1["entries"]) == 5
    assert d1["page"] == 1
    assert d1["per_page"] == 5
    assert d1["total"] == 14
    assert d1["pages"] == 3

    # Page 3 (last non-empty page): 4 items
    r3 = client.get("/entries?page=3&per_page=5", headers=headers)
    assert r3.status_code == 200
    d3 = r3.get_json()
    assert len(d3["entries"]) == 4
    assert d3["page"] == 3
    assert d3["per_page"] == 5
    assert d3["total"] == 14
    assert d3["pages"] == 3

    # Page 4 (past-the-end): 200 OK with empty entries list
    r4 = client.get("/entries?page=4&per_page=5", headers=headers)
    assert r4.status_code == 200
    d4 = r4.get_json()
    assert d4["entries"] == []
    assert d4["page"] == 4
    assert d4["per_page"] == 5
    assert d4["total"] == 14
    assert d4["pages"] == 3


@pytest.mark.parametrize(
    "query",
    [
        "per_page=0",
        "per_page=-5",
        "per_page=101",
        "per_page=abc",
        "page=0",
        "page=-1",
        "page=xyz",
    ],
)
def test_pagination_bounds_validation_returns_400(client, query):
    """Invalid page or per_page bounds are rejected with 400 before querying."""
    headers = _register_and_login(client, "bounds_user")
    resp = client.get(f"/entries?{query}", headers=headers)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body is not None


def test_page_2_is_deterministic_across_repeated_calls(client):
    """Calling page=2&per_page=5 ten times in a row yields identical ordered IDs."""
    band, _ = _get_bands()
    headers = _register_and_login(client, "determinism_user")
    _seed_entries(client, headers, count=14, band=band)

    snapshots = []
    for _ in range(10):
        resp = client.get("/entries?page=2&per_page=5", headers=headers)
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.get_json()["entries"]]
        assert len(ids) == 5
        snapshots.append(ids)

    assert all(s == snapshots[0] for s in snapshots)


def test_allowlisted_sorting_asc_desc_and_tiebreaker(client):
    """Sorting by title asc/desc orders entries accurately and rejects invalid fields/orders."""
    band, _ = _get_bands()
    headers = _register_and_login(client, "sort_user")

    for title in ("Zeta", "Alpha", "Mu", "Beta", "Delta"):
        resp = client.post(
            "/entries",
            headers=headers,
            json={"title": title, "spectral_band": band, "content": f"Body {title}"},
        )
        assert resp.status_code in (200, 201)

    r_asc = client.get("/entries?sort_by=title&order=asc&per_page=10", headers=headers)
    assert r_asc.status_code == 200
    asc_titles = [e["title"] for e in r_asc.get_json()["entries"]]
    assert asc_titles == ["Alpha", "Beta", "Delta", "Mu", "Zeta"]
    assert r_asc.get_json()["sort_by"] == "title"
    assert r_asc.get_json()["order"] == "asc"

    r_desc = client.get("/entries?sort_by=title&order=DESC&per_page=10", headers=headers)
    assert r_desc.status_code == 200
    desc_titles = [e["title"] for e in r_desc.get_json()["entries"]]
    assert desc_titles == ["Zeta", "Mu", "Delta", "Beta", "Alpha"]
    assert r_desc.get_json()["order"] == "desc"

    # Invalid sort_by and invalid order must return 400
    bad_field = client.get("/entries?sort_by=password_hash", headers=headers)
    assert bad_field.status_code == 400

    bad_order = client.get("/entries?sort_by=title&order=sideways", headers=headers)
    assert bad_order.status_code == 400


def test_tenant_isolation_and_spectral_band_filter_with_pagination(client):
    """Users only see their own entries and totals; spectral_band filtering scopes totals too."""
    band_a, band_b = _get_bands()
    headers_alice = _register_and_login(client, "alice_tenant")
    headers_bob = _register_and_login(client, "bob_tenant")

    _seed_entries(client, headers_alice, count=7, band=band_a, prefix="Alice")
    _seed_entries(client, headers_bob, count=3, band=band_a, prefix="BobA")
    if band_b != band_a:
        _seed_entries(client, headers_bob, count=2, band=band_b, prefix="BobB")

    # Alice sees only her 7 entries
    r_alice = client.get("/entries?page=1&per_page=5", headers=headers_alice)
    assert r_alice.status_code == 200
    d_alice = r_alice.get_json()
    assert d_alice["total"] == 7
    assert d_alice["pages"] == 2
    assert len(d_alice["entries"]) == 5
    assert all(e["title"].startswith("Alice") for e in d_alice["entries"])

    # Bob sees only his own entries (never Alice's)
    r_bob = client.get(f"/entries?spectral_band={band_a}&page=1&per_page=5", headers=headers_bob)
    assert r_bob.status_code == 200
    d_bob = r_bob.get_json()
    assert d_bob["total"] == 3
    assert d_bob["pages"] == 1
    assert len(d_bob["entries"]) == 3
    assert all(e["title"].startswith("BobA") for e in d_bob["entries"])
