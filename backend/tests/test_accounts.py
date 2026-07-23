"""
Linked-accounts screen: list, rename (nickname), display_name fallback, and
envelope-eligibility flags. The nickname must surface app-wide via
display_name (envelope selector, reconciliation, advisor context).
"""

from models.user import db
from models.plaid_item import PlaidItem
from models.plaid_account import PlaidAccount


def make_account(user, name='Chase Checking', acct_type='depository',
                 subtype='checking', mask='4471', balance=2500.00,
                 plaid_account_id='acct-x'):
    item = PlaidItem(user_id=user.id, item_id=f'item-{plaid_account_id}',
                     access_token='tok', institution_name='Chase')
    db.session.add(item)
    db.session.commit()
    acct = PlaidAccount(user_id=user.id, plaid_item_id=item.id,
                        plaid_account_id=plaid_account_id, name=name,
                        account_type=acct_type, account_subtype=subtype,
                        mask=mask, current_balance=balance)
    db.session.add(acct)
    db.session.commit()
    return acct


class TestListAccounts:
    def test_lists_with_display_and_eligibility(self, client, auth_headers, user):
        make_account(user, name='Chase Checking', acct_type='depository',
                     plaid_account_id='a1')
        make_account(user, name='Sapphire Card', acct_type='credit',
                     subtype='credit card', mask='9902', balance=430.12,
                     plaid_account_id='a2')

        res = client.get('/api/accounts', headers=auth_headers)
        assert res.status_code == 200
        accounts = {a['name']: a for a in res.get_json()}

        checking = accounts['Chase Checking']
        assert checking['display_name'] == 'Chase Checking'   # no nickname → raw name
        assert checking['nickname'] is None
        assert checking['is_envelope_eligible'] is True
        assert checking['is_liability'] is False
        assert checking['mask'] == '4471'

        card = accounts['Sapphire Card']
        assert card['is_envelope_eligible'] is False           # credit card excluded
        assert card['is_liability'] is True

    def test_only_own_accounts(self, client, auth_headers, user):
        from models.user import User
        other = User(email='other@x.com', first_name='Other')
        other.set_password('password123')
        db.session.add(other)
        db.session.commit()
        make_account(other, name='Their Account', plaid_account_id='other-1')

        res = client.get('/api/accounts', headers=auth_headers)
        assert res.get_json() == []


class TestRenameAccount:
    def test_set_nickname_drives_display_name(self, client, auth_headers, user):
        acct = make_account(user, name='Chase Checking', plaid_account_id='a1')

        res = client.patch(f'/api/accounts/{acct.id}', headers=auth_headers,
                           json={'nickname': 'Main Checking'})
        assert res.status_code == 200
        body = res.get_json()
        assert body['nickname'] == 'Main Checking'
        assert body['display_name'] == 'Main Checking'
        assert body['name'] == 'Chase Checking'  # raw Plaid name untouched

    def test_clear_nickname_reverts_to_plaid_name(self, client, auth_headers, user):
        acct = make_account(user, name='Chase Checking', plaid_account_id='a1')
        client.patch(f'/api/accounts/{acct.id}', headers=auth_headers,
                     json={'nickname': 'Main Checking'})

        # Empty string clears it
        res = client.patch(f'/api/accounts/{acct.id}', headers=auth_headers,
                           json={'nickname': '   '})
        assert res.status_code == 200
        body = res.get_json()
        assert body['nickname'] is None
        assert body['display_name'] == 'Chase Checking'

    def test_whitespace_is_trimmed(self, client, auth_headers, user):
        acct = make_account(user, plaid_account_id='a1')
        res = client.patch(f'/api/accounts/{acct.id}', headers=auth_headers,
                           json={'nickname': '  Emergency Savings  '})
        assert res.get_json()['nickname'] == 'Emergency Savings'

    def test_too_long_rejected(self, client, auth_headers, user):
        acct = make_account(user, plaid_account_id='a1')
        res = client.patch(f'/api/accounts/{acct.id}', headers=auth_headers,
                           json={'nickname': 'x' * 61})
        assert res.status_code == 400

    def test_missing_field_rejected(self, client, auth_headers, user):
        acct = make_account(user, plaid_account_id='a1')
        res = client.patch(f'/api/accounts/{acct.id}', headers=auth_headers, json={})
        assert res.status_code == 400

    def test_cannot_rename_others_account(self, client, auth_headers, user):
        from models.user import User
        other = User(email='other@x.com', first_name='Other')
        other.set_password('password123')
        db.session.add(other)
        db.session.commit()
        acct = make_account(other, plaid_account_id='other-1')

        res = client.patch(f'/api/accounts/{acct.id}', headers=auth_headers,
                           json={'nickname': 'Hijack'})
        assert res.status_code == 404


class TestNicknamePropagation:
    def test_nickname_flows_to_envelope_selector_and_context(self, client, auth_headers, user):
        acct = make_account(user, name='Chase Checking', plaid_account_id='a1')
        client.patch(f'/api/accounts/{acct.id}', headers=auth_headers,
                     json={'nickname': 'Main Checking'})

        # Envelope account selector endpoint reflects the nickname
        res = client.get('/api/envelopes/accounts', headers=auth_headers)
        selector = res.get_json()
        assert selector[0]['display_name'] == 'Main Checking'

        # Advisor context builder uses display_name too
        from utils.financial_context import get_envelope_context
        ctx = get_envelope_context(user.id)
        assert ctx[0]['account_name'] == 'Main Checking'
