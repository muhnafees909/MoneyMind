from app import app
from models.user import db

with app.app_context():
    db.create_all()
    print('[SUCCESS] Database tables created successfully')
    print('[SUCCESS] PlaidItem table ready for webhooks')
