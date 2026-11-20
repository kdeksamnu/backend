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

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so SQLAlchemy registers tables on db.metadata
    from ml_backend import models  # noqa: F401

    # Register Blueprints
    from ml_backend.views import main_bp
    from ml_backend.views.auth import auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    return app
