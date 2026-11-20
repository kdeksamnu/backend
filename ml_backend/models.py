from sqlalchemy.orm import validates
from datetime import datetime, timezone
from werkzeug.security import check_password_hash, generate_password_hash
from ml_backend.extensions import db


VALID_ROLES = ("user", "admin")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="user", server_default="user")

    @validates("role")
    def validate_role(self, key: str, value: str) -> str:
        if value not in VALID_ROLES:
            raise ValueError(f"Invalid role {value!r}; expected one of {VALID_ROLES}.")
        return value

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, candidate: str) -> bool:
        return check_password_hash(self.password_hash, candidate)

    def to_dict(self) -> dict:
        created_at = (
            self.created_at.replace(tzinfo=timezone.utc)
            if self.created_at.tzinfo is None
            else self.created_at.astimezone(timezone.utc)
        )
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
        }


VALID_SPECTRAL_BANDS = ("gold", "teal", "blue", "red", "violet", "emerald", "null")


class CodexEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(120), nullable=False)
    spectral_band = db.Column(
        db.String(32),
        nullable=False,
        default="teal",
        server_default="teal",
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    owner = db.relationship("User", backref=db.backref("codex_entries", lazy=True))

    @validates("spectral_band")
    def validate_spectral_band(self, key: str, value: str) -> str:
        if value not in VALID_SPECTRAL_BANDS:
            raise ValueError(
                f"Invalid spectral_band {value!r}; expected one of {VALID_SPECTRAL_BANDS}."
            )
        return value

    def to_dict(self) -> dict:
        created_at = (
            self.created_at.replace(tzinfo=timezone.utc)
            if self.created_at.tzinfo is None
            else self.created_at.astimezone(timezone.utc)
        )
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "spectral_band": self.spectral_band,
            "content": self.content,
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
        }
