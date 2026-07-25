"""
Plaid item re-auth flow: an ITEM_LOGIN_REQUIRED (and friends) surfaces as a
calm, structured "reconnect" signal instead of a raw 500, the item is flagged,
update-mode link tokens are scoped to the user, and a later clean sync clears
the flag.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from plaid.exceptions import ApiException

from models.user import db
from models.plaid_item import PlaidItem
from models.plaid_account import PlaidAccount
from utils.plaid_errors import (
    parse_plaid_exception, item_action_from_exception, PlaidItemActionRequired,
)


def _api_exception(error_code, message='Item login required.'):
    e = ApiException(status=400)
    e.body = json.dumps({
        'error_type': 'ITEM_ERROR',
        'error_code': error_code,
        'error_message': message,
        'display_message': None,
    })
    return e


@pytest.fixture
def plaid_item(user):
    item = PlaidItem(user_id=user.id, item_id='item-reauth-1',
                     institution_name='Chase')
    item.set_access_token('access-secret-1')
    db.session.add(item)
    db.session.commit()
    return item


# ------------------------------------------------------------- unit: parsing --

def test_parse_plaid_exception_extracts_code():
    parsed = parse_plaid_exception(_api_exception('ITEM_LOGIN_REQUIRED'))
    assert parsed['error_code'] == 'ITEM_LOGIN_REQUIRED'
    assert parsed['error_type'] == 'ITEM_ERROR'


def test_parse_plaid_exception_ignores_non_plaid():
    assert parse_plaid_exception(ValueError('nope')) is None


def test_item_action_marks_reconnect_for_login_required(plaid_item):
    action = item_action_from_exception(_api_exception('ITEM_LOGIN_REQUIRED'), plaid_item)
    assert isinstance(action, PlaidItemActionRequired)
    assert action.reconnect is True
    assert action.error_code == 'ITEM_LOGIN_REQUIRED'
    assert 'Chase' in action.message


def test_item_action_transient_not_reconnect(plaid_item):
    action = item_action_from_exception(_api_exception('INSTITUTION_DOWN'), plaid_item)
    assert action is not None
    assert action.reconnect is False


def test_item_action_none_for_unrelated_code(plaid_item):
    # A non-item error (e.g. a generic API error) is not turned into a prompt.
    assert item_action_from_exception(_api_exception('INTERNAL_SERVER_ERROR'), plaid_item) is None


# ----------------------------------------------------- endpoint: sync-accounts --

def test_sync_accounts_surfaces_reauth(client, auth_headers, plaid_item):
    fake_client = MagicMock()
    fake_client.accounts_balance_get.side_effect = _api_exception('ITEM_LOGIN_REQUIRED')

    with patch('routes.plaid.get_plaid_client', return_value=fake_client):
        resp = client.post('/api/plaid/sync-accounts', headers=auth_headers)

    assert resp.status_code == 409
    body = resp.get_json()
    assert body['error_code'] == 'ITEM_ACTION_REQUIRED'
    assert len(body['items']) == 1
    assert body['items'][0]['item_id'] == 'item-reauth-1'
    assert body['items'][0]['institution_name'] == 'Chase'
    assert body['items'][0]['reconnect'] is True

    # The item is flagged so the prompt persists across reloads.
    db.session.refresh(plaid_item)
    assert plaid_item.needs_reauth is True
    assert plaid_item.last_error_code == 'ITEM_LOGIN_REQUIRED'


def test_sync_transactions_surfaces_reauth(client, auth_headers, plaid_item):
    fake_client = MagicMock()
    fake_client.transactions_sync.side_effect = _api_exception('ITEM_LOGIN_REQUIRED')

    with patch('routes.plaid.get_plaid_client', return_value=fake_client):
        resp = client.post('/api/plaid/sync-transactions', headers=auth_headers, json={})

    assert resp.status_code == 409
    body = resp.get_json()
    assert body['error_code'] == 'ITEM_ACTION_REQUIRED'
    assert body['items'][0]['error_code'] == 'ITEM_LOGIN_REQUIRED'


def test_sync_accounts_success_clears_flag(client, auth_headers, plaid_item):
    # Start in the flagged state (as if a prior sync failed).
    plaid_item.needs_reauth = True
    plaid_item.last_error_code = 'ITEM_LOGIN_REQUIRED'
    db.session.commit()

    fake_client = MagicMock()
    fake_client.accounts_balance_get.return_value.to_dict.return_value = {
        'accounts': [{
            'account_id': 'acct-xyz', 'name': 'Checking', 'type': 'depository',
            'subtype': 'checking', 'mask': '1234',
            'balances': {'current': 500.0, 'available': 480.0, 'iso_currency_code': 'USD'},
        }]
    }

    with patch('routes.plaid.get_plaid_client', return_value=fake_client):
        resp = client.post('/api/plaid/sync-accounts', headers=auth_headers)

    assert resp.status_code == 200
    db.session.refresh(plaid_item)
    assert plaid_item.needs_reauth is False
    assert plaid_item.last_error_code is None


# ------------------------------------------------ endpoint: update-link-token --

def test_create_update_link_token_scoped_and_ok(client, auth_headers, user, plaid_item):
    # Email must be verified — the endpoint is behind require_verified_email.
    user.email_verified = True
    db.session.commit()

    fake_client = MagicMock()
    fake_client.link_token_create.return_value.to_dict.return_value = {
        'link_token': 'link-update-abc'
    }

    with patch('routes.plaid.get_plaid_client', return_value=fake_client):
        resp = client.post('/api/plaid/create-update-link-token',
                           headers=auth_headers, json={'item_id': 'item-reauth-1'})

    assert resp.status_code == 200
    assert resp.get_json()['link_token'] == 'link-update-abc'
    # Update mode: token built with the item's access_token, no products.
    _, kwargs = fake_client.link_token_create.call_args
    sent = kwargs.get('link_token_create_request') or fake_client.link_token_create.call_args[0][0]
    assert sent.access_token == 'access-secret-1'
    assert 'products' not in sent.to_dict() or not sent.to_dict().get('products')


def test_create_update_link_token_rejects_other_users_item(client, auth_headers, user):
    user.email_verified = True
    db.session.commit()

    resp = client.post('/api/plaid/create-update-link-token',
                       headers=auth_headers, json={'item_id': 'not-mine'})
    assert resp.status_code == 404
