from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies
)
from models.user import db, User

auth_bp = Blueprint('auth', __name__)


def _session_response(user, status=200, message=None):
    """
    Issue the session as secure httpOnly cookies (access + refresh).
    Tokens are deliberately NOT included in the response body — the browser
    must never be tempted to persist them in localStorage.
    """
    payload = {
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name
        }
    }
    if message:
        payload['message'] = message
    response = jsonify(payload)
    set_access_cookies(response, create_access_token(identity=str(user.id)))
    set_refresh_cookies(response, create_refresh_token(identity=str(user.id)))
    return response, status


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'User already exists'}), 400

    user = User(
        email=data['email'],
        first_name=data.get('first_name', '')
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    return _session_response(user, 201, 'User created successfully')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400

    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid email or password'}), 401

    # Transparently upgrade legacy pbkdf2 hashes to bcrypt
    if user.password_needs_rehash:
        user.set_password(data['password'])
        db.session.commit()

    return _session_response(user)


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Sliding-session refresh: a fresh access cookie AND a fresh refresh
    cookie are issued, so active users stay signed in indefinitely while
    genuinely idle sessions expire after the refresh-token lifetime.
    """
    identity = get_jwt_identity()
    response = jsonify({'message': 'Session refreshed'})
    set_access_cookies(response, create_access_token(identity=identity))
    set_refresh_cookies(response, create_refresh_token(identity=identity))
    return response, 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear the session cookies. Intentionally unauthenticated — logging
    out with an already-expired session must still succeed."""
    response = jsonify({'message': 'Signed out'})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({'message': 'User not found'}), 404

    return jsonify({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name
    }), 200
