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


DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100

DEFAULT_SORT_BY = "id"
DEFAULT_ORDER = "asc"
VALID_SORT_ORDERS = ("asc", "desc")
SORTABLE_FIELDS = {
    name: getattr(CodexEntry, name)
    for name in ("id", "title", "spectral_band", "created_at")
    if hasattr(CodexEntry, name)
}


@entries_bp.get("/entries")
@require_auth
def list_entries():
    user, auth_err = _get_authenticated_user()
    if auth_err is not None:
        return auth_err

    # 1. Validate optional spectral_band filter
    raw_band = request.args.get("spectral_band")
    band_filter = None
    if raw_band is not None:
        normalized_band = raw_band.strip().lower()
        if not normalized_band or normalized_band not in VALID_SPECTRAL_BANDS:
            return _error_response(
                code="VALIDATION_ERROR",
                message="Invalid spectral_band query parameter.",
                status_code=400,
                details={
                    "spectral_band": f"Must be one of: {', '.join(VALID_SPECTRAL_BANDS)}."
                },
            )
        band_filter = normalized_band

    # 2. Parse and validate pagination parameters
    pagination_errors = {}

    raw_page = request.args.get("page")
    if raw_page is None:
        page = DEFAULT_PAGE
    else:
        try:
            page = int(raw_page.strip())
            if page < 1:
                pagination_errors["page"] = "Must be an integer greater than or equal to 1."
        except ValueError:
            pagination_errors["page"] = "Must be a valid integer."

    raw_per_page = request.args.get("per_page")
    if raw_per_page is None:
        per_page = DEFAULT_PER_PAGE
    else:
        try:
            per_page = int(raw_per_page.strip())
            if per_page < 1 or per_page > MAX_PER_PAGE:
                pagination_errors["per_page"] = (
                    f"Must be an integer between 1 and {MAX_PER_PAGE}."
                )
        except ValueError:
            pagination_errors["per_page"] = "Must be a valid integer."

    if pagination_errors:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid pagination query parameters.",
            status_code=400,
            details=pagination_errors,
        )

    # 3. Parse and validate allowlisted sorting parameters
    sort_errors = {}

    raw_sort_by = request.args.get("sort_by")
    if raw_sort_by is None:
        sort_by = DEFAULT_SORT_BY
    else:
        sort_by = raw_sort_by.strip().lower()
        if not sort_by or sort_by not in SORTABLE_FIELDS:
            sort_errors["sort_by"] = (
                f"Must be one of: {', '.join(SORTABLE_FIELDS.keys())}."
            )

    raw_order = request.args.get("order")
    if raw_order is None:
        sort_order = DEFAULT_ORDER
    else:
        sort_order = raw_order.strip().lower()
        if not sort_order or sort_order not in VALID_SORT_ORDERS:
            sort_errors["order"] = (
                f"Must be one of: {', '.join(VALID_SORT_ORDERS)}."
            )

    if sort_errors:
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid sorting query parameters.",
            status_code=400,
            details=sort_errors,
        )

    # 4. Build ownership-scoped, filtered, deterministically sorted statement
    sort_column = SORTABLE_FIELDS[sort_by]
    primary_order = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    order_clauses = [primary_order]
    if sort_by != "id":
        order_clauses.append(CodexEntry.id.asc())

    stmt = db.select(CodexEntry).order_by(*order_clauses)
    if user.role != "admin":
        stmt = stmt.where(CodexEntry.user_id == user.id)
    if band_filter is not None:
        stmt = stmt.where(CodexEntry.spectral_band == band_filter)

    # 5. Paginate with error_out=False so past-the-end pages return 200 with []
    pagination = db.paginate(
        stmt,
        page=page,
        per_page=per_page,
        max_per_page=MAX_PER_PAGE,
        error_out=False,
    )

    return jsonify(
        {
            "entries": [entry.to_dict() for entry in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "sort_by": sort_by,
            "order": sort_order,
        }
    ), 200


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
