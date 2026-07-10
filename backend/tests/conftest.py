import os

# Must be set before importing app — load_dotenv() won't override existing env vars
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key'

import pytest
from flask_jwt_extended import create_access_token

from app import app as flask_app
from models.user import db, User
from models.goal import FinancialGoal
from models.plaid_item import PlaidItem
from models.plaid_account import PlaidAccount


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    u = User(email='test@example.com', first_name='Test')
    u.set_password('password123')
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def auth_headers(user):
    token = create_access_token(identity=str(user.id))
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def account(user):
    """A Plaid-linked account with a known balance"""
    item = PlaidItem(user_id=user.id, item_id='item-1', access_token='access-1',
                     institution_name='Test Bank')
    db.session.add(item)
    db.session.commit()
    acct = PlaidAccount(user_id=user.id, plaid_item_id=item.id,
                        plaid_account_id='acct-1', name='HYSA',
                        account_type='depository', account_subtype='savings',
                        current_balance=1000.00)
    db.session.add(acct)
    db.session.commit()
    return acct


def make_goal(user, name='Hajj', target=2000, current=0, linked_account_id=None):
    goal = FinancialGoal(user_id=user.id, name=name, target_amount=target,
                         current_amount=current, linked_account_id=linked_account_id)
    db.session.add(goal)
    db.session.commit()
    return goal


@pytest.fixture
def linked_goal(user, account):
    return make_goal(user, linked_account_id=account.id)
