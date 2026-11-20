from datetime import datetime, timedelta, timezone
from functools import wraps
import jwt
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from ml_backend.extensions import db
from ml_backend.models import User

auth_bp = Blueprint("auth", __name__)


def _error_response(code: str, message: str, status_code: int, details: dict | None = None):
    return jsonify({
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        }
    }), status_code


def _validate_credentials(data: dict, *, min_password_length: int = 8) -> tuple[str, str, dict]:
    raw_username = data.get("username")
    raw_password = data.get("password")
    details = {}

    username = raw_username.strip() if isinstance(raw_username, str) else ""
    if not username:
        details["username"] = "Username is required and must be a string."
    elif len(username) > 80:
        details["username"] = "Username must be 80 characters or fewer."

    if not isinstance(raw_password, str) or not raw_password.strip() or len(raw_password) < min_password_length:
        if min_password_length > 1:
            details["password"] = f"Password must be at least {min_password_length} characters."
        else:
            details["password"] = "Password is required and must be a string."
    elif len(raw_password) > 128:
        details["password"] = "Password must be 128 characters or fewer."

    password = raw_password if isinstance(raw_password, str) else ""
    return username, password, details


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
            return _error_response(
                code="UNAUTHORIZED",
                message="Missing or malformed Authorization header.",
                status_code=401,
            )

        token = parts[1]
        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
                options={"require": ["sub", "exp"]},
            )
            g.current_user_id = int(payload["sub"])
        except jwt.ExpiredSignatureError:
            return _error_response(
                code="TOKEN_EXPIRED",
                message="Token has expired.",
                status_code=401,
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return _error_response(
                code="INVALID_TOKEN",
                message="Invalid authentication token.",
                status_code=401,
            )

        return fn(*args, **kwargs)

    return wrapper


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid registration input.",
            status_code=400,
        )

    username, password, details = _validate_credentials(data, min_password_length=8)
    if details:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid registration input.",
            status_code=400,
            details=details,
        )

    existing_user = db.session.execute(
        db.select(User).where(db.func.lower(User.username) == username.lower())
    ).scalar_one_or_none()
    if existing_user is not None:
        return _error_response(
            code="USERNAME_TAKEN",
            message="A user with that username already exists.",
            status_code=409,
            details={"username": "Username is already taken."},
        )

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error_response(
            code="USERNAME_TAKEN",
            message="A user with that username already exists.",
            status_code=409,
            details={"username": "Username is already taken."},
        )

    return jsonify({"user": user.to_dict()}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid login input.",
            status_code=400,
        )

    username, password, details = _validate_credentials(data, min_password_length=1)
    if details:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid login input.",
            status_code=400,
            details=details,
        )

    user = db.session.execute(
        db.select(User).where(db.func.lower(User.username) == username.lower())
    ).scalar_one_or_none()

    if user is None or not user.check_password(password):
        return _error_response(
            code="INVALID_CREDENTIALS",
            message="Invalid username or password.",
            status_code=401,
        )

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": "operator",
        "exp": now + timedelta(seconds=current_app.config["JWT_ACCESS_LIFETIME_SECONDS"]),
    }
    access_token = jwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )

    return jsonify({
        "access_token": access_token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    }), 200


@auth_bp.get("/me")
@require_auth
def me():
    user = db.session.get(User, g.current_user_id)
    if user is None:
        return _error_response(
            code="USER_NOT_FOUND",
            message="Authenticated user no longer exists.",
            status_code=401,
        )

    return jsonify({"user": user.to_dict()}), 200
