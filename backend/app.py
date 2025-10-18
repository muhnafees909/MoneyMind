from flask import Flask
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import os
# Load environment variables
load_dotenv()

print("SECRET_KEY:", os.getenv('SECRET_KEY'))
print("DATABASE_URL:", os.getenv('DATABASE_URL'))
print("Current directory:", os.getcwd())

# Initialize Flask app
app = Flask(__name__)

# Configure SQLAlchemy
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models.user import db
db.init_app(app)

jwt = JWTManager(app)

from routes.auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/api/auth')

from routes.transactions import transactions_bp
app.register_blueprint(transactions_bp, url_prefix='/api/transactions')

from routes.analytics import analytics_bp
app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

@app.route('/')
def moneyMindWorks(): 
    return {'message': 'MoneyMind is working'}

# Create tables
with app.app_context(): 
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)