"""
Route guards layered on top of JWT auth.

require_verified_email: gates sensitive actions (bank linking) behind a
confirmed email. Unverified users keep basic access everywhere else.
"""

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from models.user import User


def require_verified_email(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = User.query.get(get_jwt_identity())
        if not user:
            return jsonify({'message': 'User not found'}), 404
        if not user.email_verified:
            return jsonify({
                'message': 'Please verify your email before connecting a bank account.',
                'code': 'email_unverified',
            }), 403
        return fn(*args, **kwargs)
    return wrapper
