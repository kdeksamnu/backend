import pytest
from ml_backend import create_app
from ml_backend.extensions import db as _db

@pytest.fixture(scope="session")
def app():
    app = create_app("development")
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture(scope="function")
def db(app):
    with app.app_context():
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()
