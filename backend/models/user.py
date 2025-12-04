from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id =  db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy=True, foreign_keys='Transaction.user_id')
    budgets = db.relationship('Budget', backref='user', lazy=True, foreign_keys='Budget.user_id')
    goals = db.relationship('Goal', backref='user', lazy=True, foreign_keys='Goal.user_id')
    categories = db.relationship('Category', backref='user', lazy=True, foreign_keys='Category.user_id')
    income_sources = db.relationship('Income', backref='user', lazy=True, foreign_keys='Income.user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.email}', '{self.first_name}')"
