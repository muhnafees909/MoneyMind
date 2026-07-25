from flask import Flask, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from datetime import timedelta
import os
# Load environment variables
load_dotenv()

# Never print secrets (JWT key, DB URL with password) — they end up in logs.

app = Flask(__name__)

allowed_origins = [
    "http://localhost:4200",  # Local development
    "https://moneymindus.onrender.com",  # Production frontend
    "https://moneymind.us",
    "https://www.moneymind.us"
]

CORS(app,
     origins=allowed_origins,
     methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-CSRF-TOKEN"],
     supports_credentials=True,
     expose_headers=["Content-Type", "Authorization"]
)

# ============================================
# Auth configuration
# Browser sessions live in secure httpOnly cookies (localStorage is
# readable by any injected script — unacceptable for bank data).
# Header tokens remain accepted for API clients and tests; CSRF
# double-submit protection applies to the cookie path.
# ============================================
_is_prod = bool(os.getenv('RENDER') or os.getenv('FLASK_ENV') == 'production')

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
app.config['JWT_COOKIE_SECURE'] = _is_prod          # HTTPS-only cookies in prod
# Lax everywhere. Production serves the API through the frontend host's
# /api/* rewrite (same-origin), so Lax cookies are always sent. The previous
# 'None' setting assumed direct cross-site calls to the backend domain —
# but cross-site session cookies are third-party cookies, which browsers
# now block outright (this is what broke prod login), and 'None' would
# needlessly re-enable CSRF exposure once same-origin.
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
app.config['JWT_COOKIE_CSRF_PROTECT'] = True        # double-submit CSRF for cookie auth
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(hours=12)   # idle window; rotated on use
app.config['JWT_REFRESH_COOKIE_PATH'] = '/api/auth/refresh'

from models.user import db
db.init_app(app)
from models.budget import Budget
from models.goal import FinancialGoal
from models.plaid_item import PlaidItem
from models.transaction import Transaction
from models.plaid_account import PlaidAccount
from models.envelope import EnvelopeAllocation, AllocationRule
from models.income_event import IncomeEvent
from models.recurring import RecurringExpense, RecurringExpenseOccurrence
from models.user_profile import UserProfile
from models.advisor_usage import AdvisorUsage, AdvisorAbuseFlag
from models.category import Category
from models.user import MfaBackupCode
from models.login_security import LoginAttempt, LoginLockout

migrate = Migrate(app, db)

jwt = JWTManager(app)


# Clean, machine-readable 401s so the frontend can tell "expired" from
# "missing/invalid" and react (refresh vs. redirect to login).
@jwt.expired_token_loader
def _expired_token(jwt_header, jwt_payload):
    return jsonify({'error': 'Session expired', 'code': 'token_expired'}), 401


@jwt.invalid_token_loader
def _invalid_token(reason):
    return jsonify({'error': 'Invalid session', 'code': 'token_invalid'}), 401


@jwt.unauthorized_loader
def _missing_token(reason):
    return jsonify({'error': 'Authentication required', 'code': 'token_missing'}), 401

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

from routes.envelopes import envelopes_bp
app.register_blueprint(envelopes_bp, url_prefix='/api/envelopes')

from routes.recurring import recurring_bp
app.register_blueprint(recurring_bp, url_prefix='/api/recurring')

from routes.profile import profile_bp
app.register_blueprint(profile_bp, url_prefix='/api/profile')

from routes.accounts import accounts_bp
app.register_blueprint(accounts_bp, url_prefix='/api/accounts')

from routes.categories import categories_bp
app.register_blueprint(categories_bp, url_prefix='/api/categories')

@app.route('/')
def moneyMindWorks(): 
    return {'message': 'MoneyMind is working'}

# Schema is managed by Flask-Migrate now (run: flask db upgrade).
# db.create_all() removed — it cannot alter existing tables.

if __name__ == '__main__':
    app.run(debug=True)
    

#cd C:\Users\ahsan\MoneyMind\backend
#venv\Scripts\activate
#python app.py