from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta
import os
# Load environment variables
load_dotenv()

print("SECRET_KEY:", os.getenv('SECRET_KEY'))
print("DATABASE_URL:", os.getenv('DATABASE_URL'))
print("Current directory:", os.getcwd())

# Initialize Flask app
app = Flask(__name__)

# Configure CORS - allow both local development and production frontend
allowed_origins = [
    "http://localhost:4200",  # Local development
    "https://moneymindus.onrender.com"  # Production frontend
]

CORS(app, resources={
    r"/api/*": {
        "origins": allowed_origins,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Configure SQLAlchemy
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7) 

from models.user import db
db.init_app(app)
from models.budget import Budget
from models.goal import FinancialGoal


jwt = JWTManager(app)

from routes.auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/api/auth')

from routes.transactions import transactions_bp
app.register_blueprint(transactions_bp, url_prefix='/api/transactions')

from routes.analytics import analytics_bp
app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

from routes.plaid import plaid_bp
app.register_blueprint(plaid_bp, url_prefix='/api/plaid')

from routes.budgets import budgets_bp
app.register_blueprint(budgets_bp, url_prefix='/api/budgets')

from routes.goals import goals_bp
app.register_blueprint(goals_bp, url_prefix='/api/goals')

from routes.chat import chat_bp
app.register_blueprint(chat_bp, url_prefix='/api/chat')

@app.route('/')
def moneyMindWorks(): 
    return {'message': 'MoneyMind is working'}

# Create tables
with app.app_context(): 
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
    

#cd C:\Users\ahsan\MoneyMind\backend
#venv\Scripts\activate
#python app.py