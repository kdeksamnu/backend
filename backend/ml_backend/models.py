from ml_backend.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Standard safe serialization excluding sensitive credentials."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role
        }
        
    def to_evidence_dict(self):
        """Evidence-only serialization to prove one-way password hashing for Maestro audits."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "password_hash": self.password_hash
        }
