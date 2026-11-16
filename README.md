# MLAOS-Prime Backend Engine

Modular Flask application factory, SQLAlchemy ORM persistence layer, and paraconsistent logic simulation API.

---

## Prerequisites

* Python 3.12+ (or Miniconda environment)
* Git

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/kdeksamnu/backend.git](https://github.com/kdeksamnu/backend.git)
   cd backend
Create and activate a virtual environment:

Bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
Install dependencies:

Bash
pip install -r requirements.txt
Environment Configuration
Copy the example environment file to create your local .env:

Bash
cp .env.example .env
Open .env and fill in your local configurations:

FLASK_CONFIG: Set to development, testing, or production.

JWT_SECRET: Secure secret key for signing JSON Web Tokens.

SECRET_KEY: Flask session secret key.

DATABASE_URL: Connection string (defaults to sqlite:///dev.db if omitted in development).

Database Migrations
This project uses Flask-Migrate for database schema management.

Set the Flask application environment variable:

Bash
export FLASK_APP=ml_backend
Initialize or apply migrations:

If the migrations/ directory does not exist yet (first-time repository setup):

Bash
flask db init
Generate a migration revision (after modifying models):

Bash
flask db migrate -m "Description of changes"
Apply migrations to your database:

Bash
flask db upgrade
Running the Application
Start the Flask development server:

Bash
flask run
