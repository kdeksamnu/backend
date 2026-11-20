from flask import Blueprint, g, jsonify, request
from ml_backend.extensions import db
from ml_backend.models import VALID_SPECTRAL_BANDS, CodexEntry, User
from ml_backend.views.auth import _error_response, require_auth

entries_bp = Blueprint("entries", __name__)

ALLOWED_ENTRY_FIELDS = {"title", "spectral_band", "content"}


def _get_authenticated_user() -> tuple[User | None, tuple | None]:
    user = db.session.get(User, g.current_user_id)
    if user is None:
        return None, _error_response(
            code="USER_NOT_FOUND",
            message="Authenticated user no longer exists.",
            status_code=401,
        )
    return user, None


def _can_access_entry(entry: CodexEntry, user: User) -> bool:
    return entry.user_id == user.id or user.role == "admin"


@entries_bp.post("/entries")
@require_auth
def create_entry():
    user, auth_err = _get_authenticated_user()
    if auth_err is not None:
        return auth_err

    if not request.is_json:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Request Content-Type must be application/json.",
            status_code=400,
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response(
            code="VALIDATION_ERROR",
            message="Request body must be a JSON object.",
            status_code=400,
        )

    disallowed = sorted(set(data.keys()) - ALLOWED_ENTRY_FIELDS)
    if disallowed:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Request contains protected or unknown fields.",
            status_code=400,
            details={field: "Field cannot be set by client." for field in disallowed},
        )

    details = {}
    raw_title = data.get("title")
    title = raw_title.strip() if isinstance(raw_title, str) else ""
    if not title:
        details["title"] = "Title is required and must be a non-empty string."
    elif len(title) > 120:
        details["title"] = "Title must be 120 characters or fewer."

    raw_content = data.get("content")
    content = raw_content.strip() if isinstance(raw_content, str) else ""
    if not content:
        details["content"] = "Content is required and must be a non-empty string."

    raw_band = data.get("spectral_band", "teal")
    if not isinstance(raw_band, str) or raw_band.strip().lower() not in VALID_SPECTRAL_BANDS:
        details["spectral_band"] = f"Must be one of: {', '.join(VALID_SPECTRAL_BANDS)}."
        spectral_band = "teal"
    else:
        spectral_band = raw_band.strip().lower()

    if details:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid codex entry input.",
            status_code=400,
            details=details,
        )

    entry = CodexEntry(
        user_id=user.id,
        title=title,
        spectral_band=spectral_band,
        content=content,
    )
    db.session.add(entry)
    db.session.commit()

    return jsonify({"entry": entry.to_dict()}), 201


@entries_bp.get("/entries")
@require_auth
def list_entries():
    user, auth_err = _get_authenticated_user()
    if auth_err is not None:
        return auth_err

    stmt = db.select(CodexEntry).order_by(CodexEntry.id.asc())
    if user.role != "admin":
        stmt = stmt.where(CodexEntry.user_id == user.id)

    entries = db.session.execute(stmt).scalars().all()
    return jsonify({"entries": [entry.to_dict() for entry in entries]}), 200


@entries_bp.get("/entries/<int:entry_id>")
@require_auth
def get_entry(entry_id: int):
    user, auth_err = _get_authenticated_user()
    if auth_err is not None:
        return auth_err

    entry = db.session.get(CodexEntry, entry_id)
    if entry is None:
        return _error_response(
            code="NOT_FOUND",
            message="Codex entry not found.",
            status_code=404,
        )

    if not _can_access_entry(entry, user):
        return _error_response(
            code="FORBIDDEN",
            message="You do not have permission to access this codex entry.",
            status_code=403,
        )

    return jsonify({"entry": entry.to_dict()}), 200


@entries_bp.patch("/entries/<int:entry_id>")
@require_auth
def update_entry(entry_id: int):
    user, auth_err = _get_authenticated_user()
    if auth_err is not None:
        return auth_err

    entry = db.session.get(CodexEntry, entry_id)
    if entry is None:
        return _error_response(
            code="NOT_FOUND",
            message="Codex entry not found.",
            status_code=404,
        )

    if not _can_access_entry(entry, user):
        return _error_response(
            code="FORBIDDEN",
            message="You do not have permission to modify this codex entry.",
            status_code=403,
        )

    if not request.is_json:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Request Content-Type must be application/json.",
            status_code=400,
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Request body must be a non-empty JSON object.",
            status_code=400,
        )

    disallowed = sorted(set(data.keys()) - ALLOWED_ENTRY_FIELDS)
    if disallowed:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Request contains protected or unknown fields.",
            status_code=400,
            details={field: "Field is not editable." for field in disallowed},
        )

    details = {}
    if "title" in data:
        raw_title = data["title"]
        title = raw_title.strip() if isinstance(raw_title, str) else ""
        if not title:
            details["title"] = "Title cannot be blank."
        elif len(title) > 120:
            details["title"] = "Title must be 120 characters or fewer."
        else:
            entry.title = title

    if "content" in data:
        raw_content = data["content"]
        content = raw_content.strip() if isinstance(raw_content, str) else ""
        if not content:
            details["content"] = "Content cannot be blank."
        else:
            entry.content = content

    if "spectral_band" in data:
        raw_band = data["spectral_band"]
        if not isinstance(raw_band, str) or raw_band.strip().lower() not in VALID_SPECTRAL_BANDS:
            details["spectral_band"] = f"Must be one of: {', '.join(VALID_SPECTRAL_BANDS)}."
        else:
            entry.spectral_band = raw_band.strip().lower()

    if details:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid codex entry update input.",
            status_code=400,
            details=details,
        )

    db.session.commit()
    return jsonify({"entry": entry.to_dict()}), 200


@entries_bp.delete("/entries/<int:entry_id>")
@require_auth
def delete_entry(entry_id: int):
    user, auth_err = _get_authenticated_user()
    if auth_err is not None:
        return auth_err

    entry = db.session.get(CodexEntry, entry_id)
    if entry is None:
        return _error_response(
            code="NOT_FOUND",
            message="Codex entry not found.",
            status_code=404,
        )

    if not _can_access_entry(entry, user):
        return _error_response(
            code="FORBIDDEN",
            message="You do not have permission to delete this codex entry.",
            status_code=403,
        )

    db.session.delete(entry)
    db.session.commit()
    return jsonify({"deleted": True, "id": entry_id}), 200
