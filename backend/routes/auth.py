from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from models.user import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # Validate input
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400
    
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'User already exists'}), 400

    # Create new user
    user = User(
        email=data['email'],
        first_name=data.get('first_name', '')
    )

    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User created successfully', 'user_id': user.id}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400

    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid email or password'}), 401

    access_token = create_access_token(identity=user.id)

    return jsonify({
        'access_token': access_token,
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name
        }
    }), 200

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

    