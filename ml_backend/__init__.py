from ml_backend.views.entries import entries_bp
from ml_backend.cli import register_cli
import os
from flask import Flask
from ml_backend.extensions import db, migrate
from ml_backend.config import config_by_name


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Diagnostic output
    print(f"\n--- RUNTIME CONFIG DIAGNOSTIC ---")
    print(f"Active Environment Name: {config_name}")
    print(f"Loaded Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    print(f"---------------------------------\n")

    # Register SQLite PRAGMA foreign_keys=ON BEFORE db.init_app(app)
    if app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite"):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so SQLAlchemy registers tables on db.metadata
    from ml_backend import models  # noqa: F401

    # Register Blueprints
    from ml_backend.views import main_bp
    from ml_backend.views.auth import auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(entries_bp, url_prefix="/api/codex")
    register_cli(app)


    return app
