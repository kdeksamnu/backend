from pathlib import Path

import pytest
from flask_migrate import downgrade, upgrade

from ml_backend import create_app
from ml_backend.config import config_by_name
from ml_backend.extensions import db
from ml_backend.models import User

MIGRATIONS_DIR = str(Path(__file__).resolve().parents[1] / "migrations")


@pytest.fixture
def blank_db_app(tmp_path, monkeypatch):
    """Create a Flask app bound to a brand-new, empty SQLite file."""
    db_file = tmp_path / "blank_migration_test.db"
    uri = f"sqlite:///{db_file}"

    monkeypatch.setattr(
        config_by_name["testing"],
        "SQLALCHEMY_DATABASE_URI",
        uri,
    )

    app = create_app("testing")
    with app.app_context():
        assert str(db_file) in str(db.engine.url), (
            f"Safety guard tripped: unexpected engine URL {db.engine.url}"
        )
        yield app
        db.session.remove()
        db.engine.dispose()


def test_upgrade_from_blank_sqlite_creates_all_model_tables_and_columns(blank_db_app):
    """Running flask db upgrade on an empty DB creates every table and column in models.py."""
    upgrade(directory=MIGRATIONS_DIR)

    inspector = db.inspect(db.engine)
    migrated_tables = set(inspector.get_table_names())
    assert "alembic_version" in migrated_tables

    expected_tables = set(db.metadata.tables.keys())
    missing_tables = expected_tables - migrated_tables
    assert not missing_tables, f"Tables missing after upgrade(): {sorted(missing_tables)}"

    for table_name, table in sorted(db.metadata.tables.items()):
        migrated_cols = {col["name"] for col in inspector.get_columns(table_name)}
        expected_cols = {col.name for col in table.columns}
        missing_cols = expected_cols - migrated_cols
        assert not missing_cols, (
            f"Table '{table_name}' missing columns after upgrade(): {sorted(missing_cols)} "
            f"(migrated={sorted(migrated_cols)}, expected={sorted(expected_cols)})"
        )


def test_user_table_columns_exact_match_and_writable(blank_db_app):
    """The migrated user table matches ml_backend.models.User exactly and accepts inserts."""
    upgrade(directory=MIGRATIONS_DIR)

    inspector = db.inspect(db.engine)
    migrated_user_cols = {col["name"] for col in inspector.get_columns("user")}
    expected_user_cols = {col.name for col in User.__table__.columns}

    assert migrated_user_cols == expected_user_cols, (
        f"User column mismatch: migrated={sorted(migrated_user_cols)} "
        f"vs expected={sorted(expected_user_cols)}"
    )

    # Confirm the migrated schema actually supports persisting a User model row
    test_user = User(username="migration_smoke_user", password_hash="scrypt:dummyhash")
    db.session.add(test_user)
    db.session.commit()

    fetched = db.session.execute(
        db.select(User).where(User.username == "migration_smoke_user")
    ).scalar_one()
    assert fetched.id is not None
    assert fetched.role is not None
    assert fetched.created_at is not None


def test_latest_migration_downgrade_and_reupgrade_roundtrip(blank_db_app):
    """Latest revision cleanly downgrades one step and upgrades back to head on SQLite."""
    upgrade(directory=MIGRATIONS_DIR)
    downgrade(directory=MIGRATIONS_DIR, revision="-1")
    upgrade(directory=MIGRATIONS_DIR)

    inspector = db.inspect(db.engine)
    migrated_user_cols = {col["name"] for col in inspector.get_columns("user")}
    expected_user_cols = {col.name for col in User.__table__.columns}

    assert migrated_user_cols == expected_user_cols
