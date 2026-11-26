## Running with Docker Compose

This project includes a fully containerized development stack using Docker Compose, pairing our Flask backend (`web`) with a PostgreSQL database (`db`) and persistent volume storage.

### 1. Environment Configuration (Dev Only)

Before starting the stack, create a local `.env` file in the project root based on `.env.example`. 

The following environment variables must be provided in your `.env` file (do **not** commit `.env` to version control):

* `POSTGRES_USER`
* `POSTGRES_PASSWORD`
* `POSTGRES_DB`
* `JWT_SECRET`
* `JWT_SECRET_KEY` (Flask app secret)
* `JWT_ACCESS_LIFETIME_SECONDS` (e.g., 900 for 15 minutes)
* `FLASK_CONFIG` (typically `development`)

### 2. Starting the Stack

Build and start the containers in the foreground or background:

```bash
docker compose up --build
```

Once running, the Flask API will be accessible at [http://localhost:8000](http://localhost:8000/).

The database will be accessible on port 5432 internally (not exposed to host by default).

### 3. Running Database Migrations

With the services up and healthy, apply the database migrations inside the running container:

```bash
docker compose exec web flask db upgrade
```

This ensures all tables and schema changes are applied to PostgreSQL before accepting requests.

### 4. Verifying the Application

You can verify the API is working correctly by walking through the following core endpoints:

#### 4a. Register a User

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "compose_tester_01",
    "password": "SecurePassword123!"
  }'
```

**Expected Response (201 Created):**
```json
{
  "user": {
    "id": 1,
    "username": "compose_tester_01",
    "role": "user",
    "created_at": "2026-11-23T16:33:21.403055Z"
  }
}
```

#### 4b. Log In to Retrieve JWT

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "compose_tester_01",
    "password": "SecurePassword123!"
  }'
```

**Expected Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "user": {
    "id": 1,
    "username": "compose_tester_01",
    "role": "user",
    "created_at": "2026-11-23T16:33:21.403055Z"
  }
}
```

**Save the `access_token` value for the next step.**

#### 4c. Create a Codex Entry

Pass the JWT returned from the login step in the `Authorization` header:

```bash
curl -X POST http://localhost:8000/api/codex/entries \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "title": "Docker Compose Persistence Record",
    "content": "Verifying database survival across container restarts."
  }'
```

**Expected Response (201 Created):**
```json
{
  "entry": {
    "id": 1,
    "user_id": 1,
    "title": "Docker Compose Persistence Record",
    "spectral_band": "teal",
    "content": "Verifying database survival across container restarts.",
    "created_at": "2026-11-23T16:33:31.575240Z"
  }
}
```

### 5. Data Persistence Across Restarts

All database records and user data will safely survive `docker compose down` and subsequent `docker compose up` cycles thanks to the configured Docker named volume (`postgres_data`).

**Test persistence:**

```bash
# Stop and remove all containers (volume persists)
docker compose down

# Start the stack again
docker compose up -d

# Verify your data is still there
docker compose exec web flask shell
```

Inside the Flask shell:
```python
from ml_backend.models import User, CodexEntry
user = User.query.filter_by(username="compose_tester_01").first()
print(user.codex_entries)  # Should show your entry
```

### 6. Stopping the Stack

Stop containers but preserve volumes:

```bash
docker compose stop
```

Remove containers but preserve volumes (use this before `docker compose down`):

```bash
docker compose down
```

Completely remove containers **and** volumes (destructive):

```bash
docker compose down -v
```

### 7. Viewing Logs

Stream logs from all services:

```bash
docker compose logs -f
```

Tail logs from a specific service:

```bash
docker compose logs -f web
docker compose logs -f db
```

### 8. Accessing the Database Directly

If you need to inspect or debug the PostgreSQL database directly:

```bash
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB
```

Then query tables:

```sql
\dt                          # List all tables
SELECT * FROM "user";        # View users
SELECT * FROM codex_entry;   # View entries
```

### 9. Troubleshooting

**Issue: `port is already in use`**
- Another process is using port 8000 or 5432
- Kill existing containers: `docker compose down`
- Or use a different port in `docker-compose.yml` temporarily

**Issue: `database "ml_backend_db" does not exist`**
- Run `docker compose exec web flask db upgrade` after starting the stack
- Or manually create the database: `docker compose exec db createdb -U $POSTGRES_USER $POSTGRES_DB`

**Issue: `column user.password_hash does not exist`**
- Migrations are out of sync with the database
- Regenerate and apply: `docker compose exec web flask db migrate -m "sync schema"` then `flask db upgrade`

**Issue: `JWT_SECRET not found`**
- Ensure your `.env` file contains `JWT_SECRET` and `JWT_SECRET_KEY`
- Reload with `docker compose down && docker compose up --build`

