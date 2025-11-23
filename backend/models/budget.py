from datetime import datetime
from models.user import db

class Budget(db.Model):
    __tablename__ = 'budgets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Budget details
    category = db.Column(db.String(50), nullable=False, unique=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Remove month/year - now it's recurring!
    is_active = db.Column(db.Boolean, default=True)  # Can pause/deactivate budgets
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Add unique constraint: one budget per user per category
    __table_args__ = (
        db.UniqueConstraint('user_id', 'category', name='unique_user_category'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'category': self.category,
            'amount': float(self.amount),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Budget {self.category}: ${self.amount}/month>'