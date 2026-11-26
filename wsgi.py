"""
WSGI entrypoint for Flask application.

Imports create_app from ml_backend and instantiates the Flask app
for production use with Gunicorn or other WSGI servers.
"""

from ml_backend import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
