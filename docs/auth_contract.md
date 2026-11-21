# MLAOS-Prime Identity & Auth Error Contract (`ml_backend`)

All authentication failures return HTTP `401 Unauthorized` using the standard error envelope:

```json
{
  "error": {
    "code": "<ERROR_CODE>",
    "message": "<Human-readable message>",
    "details": {}
  }
}
Bearer Token & Identity Cases (ml_backend/views/auth.py)CaseStatuserror.codeerror.messageLayer & ConditionMissing or malformed header401UNAUTHORIZEDMissing or malformed Authorization header.@require_auth: header absent, not Bearer <token>, or blank token.Tampered or structurally invalid JWT401INVALID_TOKENInvalid authentication token.@require_auth: invalid HS256 signature, corrupt JWT payload, or invalid sub claim.Expired JWT401TOKEN_EXPIREDToken has expired.@require_auth: valid signature, but UTC exp timestamp has elapsed.Deleted or missing user record401USER_NOT_FOUNDAuthenticated user no longer exists.GET /me: valid unexpired JWT, but g.current_user_id no longer exists in users.EOFgit add docs/auth_contract.md
git diff --cached --quiet || git commit -m "Document 401 USER_NOT_FOUND in auth contract"cat << 'EOF' | tee /tmp/maestro_summary.txt | pbcopy
Project Summary — MLAOS-Prime Backend & Identity Service (Branch: unit-2-auth):Core Resource & Models: Modular Flask backend API (ml_backend, SQLite sqlite:///dev.db) serving as the backend and operator identity service for MLAOS-Prime. Currently has a single User model in ml_backend/models.py (id PK, username String(80) unique non-null, password_hash String(255) non-null, created_at DateTime UTC non-null, with set_password(), check_password(), and to_dict()). No child resource models are linked yet; user-owned MLAOS resources will attach via foreign key in this next unit.   How Auth Currently Works:   POST /register (ml_backend/views/auth.py) creates users with User.set_password() (201 Created, 400 VALIDATION_ERROR, 409 USERNAME_TAKEN).   POST /login (ml_backend/views/auth.py) verifies credentials via User.check_password() and signs an HS256 JWT (sub=str(user.id), role="operator", exp) using JWT_SECRET_KEY and JWT_ACCESS_LIFETIME_SECONDS (900s default) from ml_backend/config.py / .env.   @require_auth (ml_backend/views/auth.py) validates Authorization: Bearer <token>, sets g.current_user_id = int(payload["sub"]), and returns distinct 401 JSON errors (UNAUTHORIZED, INVALID_TOKEN, TOKEN_EXPIRED).   GET /me (ml_backend/views/auth.py) uses @require_auth, hydrates User via db.session.get(User, g.current_user_id), returns 200 {"user": ...} or 401 USER_NOT_FOUND if deleted, and is covered by pytest in tests/test_auth_me.py.Where Files & Routes Live: create_app() in ml_backend/__init__.py registers main_bp (GET /health) and auth_bp (POST /register, POST /login, GET /me in ml_backend/views/auth.py) at /.Next Planned Step: Define a user-owned MLAOS resource model with a foreign key to users.id (and Alembic migration), then build CRUD endpoints protected by @require_auth with strict g.current_user_id ownership enforcement.
