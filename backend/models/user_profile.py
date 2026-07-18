from datetime import datetime
from models.user import db


class UserProfile(db.Model):
    """
    Personal/financial context the AI advisor uses for personalization.

    Deliberately separate from the auth `user` table: this is sensitive
    context, every field is optional, and it should be treated like Plaid
    credentials — never logged, never exposed beyond the profile endpoints
    and the advisor's server-side context builder.
    """
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)

    # Employment & income
    employment_status = db.Column(db.String(20), nullable=True)   # employed | self_employed | student | unemployed
    annual_income = db.Column(db.Numeric(12, 2), nullable=True)   # stated income; may differ from inferred deposits

    # Household
    marital_status = db.Column(db.String(10), nullable=True)      # single | married
    dependents = db.Column(db.SmallInteger, nullable=True)
    housing_status = db.Column(db.String(10), nullable=True)      # rent | own | family
    birth_year = db.Column(db.SmallInteger, nullable=True)        # year only — enough for horizon advice

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'employment_status': self.employment_status,
            'annual_income': float(self.annual_income) if self.annual_income is not None else None,
            'marital_status': self.marital_status,
            'dependents': self.dependents,
            'housing_status': self.housing_status,
            'birth_year': self.birth_year,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        # Intentionally value-free: profile contents must not leak into logs
        return f'<UserProfile user_id={self.user_id}>'
