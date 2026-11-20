from datetime import datetime, timezone
from ml_backend.extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        created_at = (
            self.created_at.replace(tzinfo=timezone.utc)
            if self.created_at.tzinfo is None
            else self.created_at.astimezone(timezone.utc)
        )
        return {
            "id": self.id,
            "username": self.username,
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
        }
