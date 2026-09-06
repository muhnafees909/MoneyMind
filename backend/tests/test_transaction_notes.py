"""
Transaction notes must work on ANY transaction — manual or Plaid-synced.
Notes are a user field, independent of the bank record, so the Plaid
amount/date/description lock does not apply to them.
"""

from datetime import datetime

from models.user import db
from models.transaction import Transaction


def make_txn(user, source='plaid', notes='', plaid_id='ptx-note-1'):
    txn = Transaction(
        user_id=user.id, amount=42.00, description='NETFLIX.COM',
        category='ENTERTAINMENT', transaction_type='expense',
        transaction_date=datetime.utcnow(), transaction_notes=notes,
        source=source,
        plaid_transaction_id=plaid_id if source == 'plaid' else None
    )
    db.session.add(txn)
    db.session.commit()
    return txn


class TestNotesOnAnyTransaction:
    def test_add_note_to_plaid_transaction(self, client, auth_headers, user):
        """The core fix: a synced transaction can receive a user note."""
        txn = make_txn(user, source='plaid')
        res = client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers,
                           json={'transaction_notes': 'Split with roommate'})
        assert res.status_code == 200
        assert res.get_json()['transaction_notes'] == 'Split with roommate'
        assert Transaction.query.get(txn.id).transaction_notes == 'Split with roommate'

    def test_add_note_to_manual_transaction(self, client, auth_headers, user):
        txn = make_txn(user, source='manual', plaid_id=None)
        res = client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers,
                           json={'transaction_notes': 'Birthday gift'})
        assert res.status_code == 200
        assert res.get_json()['transaction_notes'] == 'Birthday gift'

    def test_edit_and_clear_note(self, client, auth_headers, user):
        txn = make_txn(user, source='plaid', notes='first')
        client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers,
                     json={'transaction_notes': 'edited'})
        assert Transaction.query.get(txn.id).transaction_notes == 'edited'

        # Empty string clears the note
        res = client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers,
                           json={'transaction_notes': '   '})
        assert res.status_code == 200
        assert Transaction.query.get(txn.id).transaction_notes == ''

    def test_note_survives_plaid_resync(self, client, auth_headers, user, account, monkeypatch):
        """A user note on a synced row must not be clobbered when Plaid re-sends
        that transaction as 'modified'."""
        import routes.plaid as plaid_routes
        from types import SimpleNamespace
        from models.plaid_item import PlaidItem

        txn = make_txn(user, source='plaid', plaid_id='ptx-1')
        client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers,
                     json={'transaction_notes': 'keep me'})

        response = {'added': [], 'removed': [], 'has_more': False, 'next_cursor': 'c1',
                    'modified': [{
                        'transaction_id': 'ptx-1', 'amount': 42.00, 'name': 'NETFLIX.COM',
                        'personal_finance_category': {'primary': 'ENTERTAINMENT'},
                        'date': datetime.utcnow().date(), 'merchant_name': 'Netflix',
                        'merchant_entity_id': 'ent-nflx', 'account_id': 'acct-1'
                    }]}
        fake = SimpleNamespace(transactions_sync=lambda req, **kwargs: SimpleNamespace(to_dict=lambda: response))
        monkeypatch.setattr(plaid_routes, 'get_plaid_client', lambda: fake)
        plaid_routes.perform_transaction_sync(user.id, 'access-1', plaid_item=PlaidItem.query.one())

        assert Transaction.query.get(txn.id).transaction_notes == 'keep me'

    def test_too_long_rejected(self, client, auth_headers, user):
        txn = make_txn(user)
        res = client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers,
                           json={'transaction_notes': 'x' * 256})
        assert res.status_code == 400

    def test_missing_field_rejected(self, client, auth_headers, user):
        txn = make_txn(user)
        res = client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers, json={})
        assert res.status_code == 400

    def test_cannot_note_others_transaction(self, client, auth_headers, user):
        from models.user import User
        other = User(email='other@x.com', first_name='Other')
        other.set_password('password123')
        db.session.add(other)
        db.session.commit()
        txn = make_txn(other, plaid_id='ptx-other')

        res = client.patch(f'/api/transactions/{txn.id}/notes', headers=auth_headers,
                           json={'transaction_notes': 'hijack'})
        assert res.status_code == 404

    def test_new_plaid_sync_leaves_notes_empty(self, client, auth_headers, user, account, monkeypatch):
        """New synced rows no longer get 'Merchant: X' filler in notes."""
        import routes.plaid as plaid_routes
        from types import SimpleNamespace
        from models.plaid_item import PlaidItem

        response = {'modified': [], 'removed': [], 'has_more': False, 'next_cursor': 'c1',
                    'added': [{
                        'transaction_id': 'ptx-new', 'amount': 12.50, 'name': 'Coffee',
                        'personal_finance_category': {'primary': 'FOOD_AND_DRINK'},
                        'date': datetime.utcnow().date(), 'merchant_name': 'Blue Bottle',
                        'merchant_entity_id': 'ent-bb', 'account_id': 'acct-1'
                    }]}
        fake = SimpleNamespace(transactions_sync=lambda req, **kwargs: SimpleNamespace(to_dict=lambda: response))
        monkeypatch.setattr(plaid_routes, 'get_plaid_client', lambda: fake)
        plaid_routes.perform_transaction_sync(user.id, 'access-1', plaid_item=PlaidItem.query.one())

        new = Transaction.query.filter_by(plaid_transaction_id='ptx-new').one()
        assert new.transaction_notes == ''
        assert new.merchant_name == 'Blue Bottle'  # merchant still captured structurally
