from models.user import db
from datetime import datetime

class Category(db.Model):
    """Category for organizing transactions and budgets"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50))  # emoji or icon name

    # Relationships
    transactions = db.relationship('Transaction', backref='category', lazy=True)
    budgets = db.relationship('Budget', backref='category', lazy=True)

    def __repr__(self):
        return f"Category('{self.name}')"


class Transaction(db.Model):
    """Individual financial transaction"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)

    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'income' or 'expense'
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Transaction('{self.description}', ${self.amount}, {self.date})"

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'date': self.date.strftime('%m/%d/%Y'),
            'category': self.category.name if self.category else 'Uncategorized',
            'notes': self.notes
        }


class Budget(db.Model):
    """Monthly budget for a specific category"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Budget('{self.category.name}', ${self.amount}, {self.month}/{self.year})"

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category.name,
            'amount': self.amount,
            'month': self.month,
            'year': self.year
        }


class Goal(db.Model):
    """Financial goal for saving"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    deadline = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"Goal('{self.name}', ${self.current_amount}/${self.target_amount})"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'target_amount': self.target_amount,
            'current_amount': self.current_amount,
            'deadline': self.deadline.strftime('%m/%d/%Y') if self.deadline else None,
            'progress_percent': round((self.current_amount / self.target_amount) * 100, 1) if self.target_amount > 0 else 0,
            'completed': self.completed
        }


class Income(db.Model):
    """User's income sources"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    source = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), nullable=False)  # 'monthly', 'biweekly', 'weekly'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"Income('{self.source}', ${self.amount}, {self.frequency})"

    def to_dict(self):
        return {
            'id': self.id,
            'source': self.source,
            'amount': self.amount,
            'frequency': self.frequency
        }
