import os
from flask import Flask
from ml_backend.extensions import db, migrate
from ml_backend.config import config_by_name, DevelopmentConfig
from ml_backend.views import main_bp

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Determine configuration name from argument, environment variable, or default
    env_name = config_name or os.getenv("FLASK_CONFIG", "development")
    config_class = config_by_name.get(env_name, DevelopmentConfig)
    
    # Load configuration from the selected config class
    app.config.from_object(config_class)

    # Runtime diagnostic to prove .env integration
    print(f"--- RUNTIME CONFIG DIAGNOSTIC ---")
    print(f"Active Environment Name: {env_name}")
    print(f"Loaded Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"---------------------------------")

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints safely inside the factory
    app.register_blueprint(main_bp)

    return app
