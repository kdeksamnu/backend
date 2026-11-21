from flask import Blueprint, jsonify
from ml_backend.models import User

main_bp = Blueprint('main', __name__)

@main_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "engine": "MLAOS-Prime"}), 200

@main_bp.route('/user-count', methods=['GET'])
def user_count():
    # Query executed safely inside the request and application context
    count = User.query.count()
    return jsonify({"count": count}), 200
