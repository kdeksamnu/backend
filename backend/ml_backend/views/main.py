from flask import Blueprint, request, jsonify
from ml_backend.extensions import db
from ml_backend.models import User

main_bp = Blueprint('main', __name__)

@main_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "engine": "MLAOS-Prime"}), 200

@main_bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "User already exists"}), 409
        
    user = User(username=username)
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        "message": "User registered successfully",
        "user": user.to_dict()
    }), 201

@main_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
        
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401
        
    return jsonify({
        "message": "Login successful",
        "user": user.to_dict()
    }), 200

@main_bp.route('/audit/users', methods=['GET'])
def audit_users():
    """Evidence-only route exposing password hashes for the Maestro challenge audit."""
    users = User.query.all()
    return jsonify({
        "audit_target": "users_table_credential_storage",
        "total_records": len(users),
        "records": [u.to_evidence_dict() for u in users]
    }), 200
