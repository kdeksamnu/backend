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

---

## Running with Docker Compose

This project includes a fully containerized development stack using Docker Compose, pairing our Flask backend (`web`) with a PostgreSQL database (`db`) and persistent volume storage.

### 1. Environment Configuration (Dev Only)

Before starting the stack, create your local `.env` file by copying `.env.example`:

```bash
cp .env.example .env
```

Fill in the required environment variables in your `.env` file (do **not** commit `.env` to version control):

```
FLASK_CONFIG=development
JWT_SECRET=your_super_secret_jwt_key_here
JWT_SECRET_KEY=your_flask_secret_key_here
JWT_ACCESS_LIFETIME_SECONDS=900
POSTGRES_USER=ml_user
POSTGRES_PASSWORD=ml_pass
POSTGRES_DB=ml_backend_db
```

### 2. Starting the Stack

Build and start the containers in the foreground or background:

```bash
docker compose up --build
```

Once running, the Flask API will be accessible at [http://localhost:8000](http://localhost:8000).

### 3. Running Database Migrations

With the services up and healthy, apply the database migrations inside the running container:

```bash
docker compose exec web flask db upgrade
```

### 4. Verifying the Application & Persistence

You can verify the API is working correctly and test data persistence across container restarts by walking through the following steps:

#### Register a User

```bash
curl -i -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"compose_tester_01","password":"SecurePassword123!"}'
```

#### Log In to Retrieve JWT

```bash
curl -i -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"compose_tester_01","password":"SecurePassword123!"}'
```

*(Copy the `access_token` from the JSON response.)*

#### Create a Codex Entry

```bash
curl -i -X POST http://localhost:8000/api/codex/entries \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"title":"Docker Compose Persistence Record","content":"Verifying database survival."}'
```

#### Verify Persistence Across Restarts

1. Stop the stack:
   ```bash
   docker compose down
   ```

2. Restart the stack:
   ```bash
   docker compose up
   ```

3. Re-fetch your entries using your token to confirm the record survived via the PostgreSQL named volume (`postgres_data`).

---

> **Note:** All database records and user data will safely survive `docker compose down` and subsequent `docker compose up` cycles thanks to the configured Docker named volume (`postgres_data`).
