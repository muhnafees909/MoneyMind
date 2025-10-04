from flask import Flask
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import os
# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure SQLAlchemy
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models.user import db
db.init_app(app)

jwt = JWTManager(app)

from routes.auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/api/auth')

@app.route('/')
def moneyMindWorks(): 
    return {'message': 'MoneyMind is working'}

# Create tables
with app.app_context(): 
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)