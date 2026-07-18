from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.user_profile import UserProfile

profile_bp = Blueprint('profile', __name__)

# Allowed values for the categorical fields — everything is optional,
# but what is present must be one of these.
EMPLOYMENT_VALUES = {'employed', 'self_employed', 'student', 'unemployed'}
MARITAL_VALUES = {'single', 'married'}
HOUSING_VALUES = {'rent', 'own', 'family'}


def _validation_error(field):
    # Generic message on purpose: no field values in responses or logs
    return jsonify({'error': f'Invalid value for {field}'}), 400


@profile_bp.route('', methods=['GET'])
@jwt_required()
def get_profile():
    """Return the user's advisor profile (empty object if none saved yet)."""
    user_id = int(get_jwt_identity())
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({
            'employment_status': None,
            'annual_income': None,
            'marital_status': None,
            'dependents': None,
            'housing_status': None,
            'birth_year': None,
            'updated_at': None
        }), 200
    return jsonify(profile.to_dict()), 200


@profile_bp.route('', methods=['PUT'])
@jwt_required()
def upsert_profile():
    """
    Create or update the advisor profile. All fields optional; explicit
    null clears a field. Values are validated but never logged.
    """
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    employment = data.get('employment_status')
    if employment is not None and employment not in EMPLOYMENT_VALUES:
        return _validation_error('employment_status')

    marital = data.get('marital_status')
    if marital is not None and marital not in MARITAL_VALUES:
        return _validation_error('marital_status')

    housing = data.get('housing_status')
    if housing is not None and housing not in HOUSING_VALUES:
        return _validation_error('housing_status')

    income = data.get('annual_income')
    if income is not None:
        try:
            income = float(income)
        except (TypeError, ValueError):
            return _validation_error('annual_income')
        if income < 0 or income > 100_000_000:
            return _validation_error('annual_income')

    dependents = data.get('dependents')
    if dependents is not None:
        try:
            dependents = int(dependents)
        except (TypeError, ValueError):
            return _validation_error('dependents')
        if dependents < 0 or dependents > 20:
            return _validation_error('dependents')

    birth_year = data.get('birth_year')
    if birth_year is not None:
        try:
            birth_year = int(birth_year)
        except (TypeError, ValueError):
            return _validation_error('birth_year')
        current_year = datetime.utcnow().year
        if birth_year < 1900 or birth_year > current_year - 13:
            return _validation_error('birth_year')

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)

    profile.employment_status = employment
    profile.annual_income = income
    profile.marital_status = marital
    profile.dependents = dependents
    profile.housing_status = housing
    profile.birth_year = birth_year

    db.session.commit()
    return jsonify(profile.to_dict()), 200
