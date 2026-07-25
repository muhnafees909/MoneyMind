import json
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.auth_guards import require_verified_email
from utils.plaid_client import get_plaid_client
from utils.plaid_errors import PlaidItemActionRequired, item_action_from_exception
from plaid.exceptions import ApiException
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_get_request import ItemGetRequest
from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from models.transaction import Transaction
from models.plaid_item import PlaidItem
from models.plaid_account import PlaidAccount
from utils.income import record_income_event
from utils.recurring import detect_recurring
from datetime import datetime, date
from models.user import db, User

plaid_bp = Blueprint('plaid', __name__)


def _delete_removed_transaction(transaction):
    """Remove a transaction Plaid retracted, cleaning up rows that point at it."""
    from models.envelope import EnvelopeAllocation
    from models.income_event import IncomeEvent
    from models.recurring import RecurringExpenseOccurrence

    EnvelopeAllocation.query.filter_by(source_transaction_id=transaction.id) \
        .update({'source_transaction_id': None})
    IncomeEvent.query.filter_by(transaction_id=transaction.id).delete()
    RecurringExpenseOccurrence.query.filter_by(transaction_id=transaction.id).delete()
    db.session.delete(transaction)


def perform_transaction_sync(user_id: int, access_token: str, plaid_item: PlaidItem = None) -> dict:
    """
    Incrementally syncs transactions from Plaid using the stored cursor, so
    each run only fetches what changed. Handles added, modified, and removed
    transactions, flags likely income deposits, and re-runs recurring
    detection. Returns {'saved': int, 'modified': int, 'removed': int, 'total': int}.
    Raises exceptions on failure.
    """
    client = get_plaid_client()

    if plaid_item is None:
        # Tokens are encrypted at rest, so match by decrypting each item's token
        plaid_item = next(
            (item for item in PlaidItem.query.filter_by(user_id=int(user_id)).all()
             if item.get_access_token() == access_token),
            None
        )

    cursor = plaid_item.sync_cursor if plaid_item else None

    added, modified, removed = [], [], []
    try:
        while True:
            kwargs = {'access_token': access_token}
            if cursor:
                kwargs['cursor'] = cursor
            response = client.transactions_sync(TransactionsSyncRequest(**kwargs)).to_dict()
            added.extend(response.get('added', []))
            modified.extend(response.get('modified', []))
            removed.extend(response.get('removed', []))
            cursor = response.get('next_cursor') or cursor
            if not response.get('has_more'):
                break
    except ApiException as e:
        # If Plaid says the item needs the user to act (re-auth, etc.), record
        # it on the item and raise a structured signal the route turns into a
        # calm reconnect prompt instead of a raw 400.
        action = item_action_from_exception(e, plaid_item)
        if action and plaid_item:
            plaid_item.needs_reauth = action.reconnect
            plaid_item.last_error_code = action.error_code
            db.session.commit()
        if action:
            raise action
        raise

    # Map Plaid's string account ids to our PlaidAccount rows
    account_map = {
        a.plaid_account_id: a.id
        for a in PlaidAccount.query.filter_by(user_id=int(user_id)).all()
    }

    saved_count = 0
    new_transactions = []
    for txn in added:
        # Check for duplicate
        existing = Transaction.query.filter_by(
            plaid_transaction_id=txn['transaction_id']
        ).first()

        if not existing:
            transaction = Transaction(
                user_id=int(user_id),
                amount=abs(txn['amount']),
                description=txn['name'],
                category=txn['personal_finance_category']['primary']
                    if txn.get('personal_finance_category') else 'other',
                transaction_date=txn['date'],
                transaction_type='expense' if txn['amount'] > 0 else 'income',
                source='plaid',
                plaid_transaction_id=txn['transaction_id'],
                plaid_account_id=account_map.get(txn.get('account_id')),
                merchant_name=txn.get('merchant_name'),
                merchant_entity_id=txn.get('merchant_entity_id'),
                # transaction_notes is the user's note field — leave it empty on
                # sync (the merchant is already stored in merchant_name). Writing
                # filler here would make every synced row look like it has a note.
                transaction_notes=''
            )
            db.session.add(transaction)
            new_transactions.append(transaction)
            saved_count += 1
        elif existing.plaid_account_id is None:
            # Backfill account linkage on rows synced before accounts existed
            existing.plaid_account_id = account_map.get(txn.get('account_id'))
            # Backfill merchant identifiers on older rows too
            if existing.merchant_entity_id is None:
                existing.merchant_name = txn.get('merchant_name')
                existing.merchant_entity_id = txn.get('merchant_entity_id')

    modified_count = 0
    for txn in modified:
        existing = Transaction.query.filter_by(
            plaid_transaction_id=txn['transaction_id']).first()
        if existing:
            existing.amount = abs(txn['amount'])
            existing.description = txn['name']
            # A category the user set by hand survives re-sync — Plaid's
            # auto-category only applies while the row is still 'auto'
            if existing.category_source != 'manual':
                existing.category = txn['personal_finance_category']['primary'] \
                    if txn.get('personal_finance_category') else existing.category
            existing.transaction_date = txn['date']
            existing.transaction_type = 'expense' if txn['amount'] > 0 else 'income'
            existing.merchant_name = txn.get('merchant_name')
            existing.merchant_entity_id = txn.get('merchant_entity_id')
            modified_count += 1

    removed_count = 0
    for txn in removed:
        existing = Transaction.query.filter_by(
            plaid_transaction_id=txn.get('transaction_id')).first()
        if existing:
            _delete_removed_transaction(existing)
            removed_count += 1

    db.session.flush()  # assign ids so income events can reference them

    # Flag likely paycheck deposits for the allocation prompt
    for transaction in new_transactions:
        record_income_event(transaction)

    if plaid_item:
        plaid_item.sync_cursor = cursor
        plaid_item.last_sync_timestamp = datetime.utcnow()
        # A successful sync means the connection is healthy again — clear any
        # stale reauth flag so the reconnect prompt disappears.
        plaid_item.needs_reauth = False
        plaid_item.last_error_code = None

    db.session.commit()

    # Keep recurring series up to date (new occurrences, price creep, candidates)
    if saved_count or modified_count or removed_count:
        try:
            detect_recurring(int(user_id))
        except Exception as e:
            print(f"[RECURRING] detection after sync failed: {e}")

    return {
        'saved': saved_count,
        'modified': modified_count,
        'removed': removed_count,
        'total': len(added)
    }


def sync_accounts_for_item(plaid_item: PlaidItem) -> int:
    """Fetch real-time balances for all accounts under a PlaidItem and upsert
    PlaidAccount rows. Returns number of accounts synced.

    Raises PlaidItemActionRequired if Plaid reports an item-level error (the
    caller turns that into a reconnect prompt); other exceptions propagate."""
    client = get_plaid_client()
    request_data = AccountsBalanceGetRequest(access_token=plaid_item.get_access_token())
    try:
        response = client.accounts_balance_get(request_data).to_dict()
    except ApiException as e:
        action = item_action_from_exception(e, plaid_item)
        if action:
            plaid_item.needs_reauth = action.reconnect
            plaid_item.last_error_code = action.error_code
            db.session.commit()
            raise action
        raise

    synced = 0
    for acct in response.get('accounts', []):
        account = PlaidAccount.query.filter_by(plaid_account_id=acct['account_id']).first()
        if not account:
            account = PlaidAccount(
                user_id=plaid_item.user_id,
                plaid_item_id=plaid_item.id,
                plaid_account_id=acct['account_id']
            )
            db.session.add(account)

        account.name = acct.get('name') or 'Account'
        account.official_name = acct.get('official_name')
        account.account_type = str(acct.get('type')) if acct.get('type') else None
        account.account_subtype = str(acct.get('subtype')) if acct.get('subtype') else None
        account.mask = acct.get('mask')
        balances = acct.get('balances') or {}
        account.current_balance = balances.get('current')
        account.available_balance = balances.get('available')
        account.iso_currency_code = balances.get('iso_currency_code')
        account.balance_updated_at = datetime.utcnow()
        synced += 1

    # Balances came back cleanly — the connection is healthy again.
    plaid_item.needs_reauth = False
    plaid_item.last_error_code = None
    db.session.commit()
    return synced


@plaid_bp.route('/sync-accounts', methods=['POST'])
@jwt_required()
def sync_accounts():
    """Refresh account list + balances for all of the user's connected banks.

    One bank needing re-auth shouldn't block the others: each item is synced
    independently. If any item reports an item-level error (e.g.
    ITEM_LOGIN_REQUIRED), the still-current accounts are returned alongside a
    list of items that need the user to reconnect."""
    try:
        user_id = get_jwt_identity()
        plaid_items = PlaidItem.query.filter_by(user_id=int(user_id)).all()

        if not plaid_items:
            return jsonify({'error': 'No bank account connected. Please connect a bank account first.'}), 404

        total = 0
        items_need_action = []
        for item in plaid_items:
            try:
                total += sync_accounts_for_item(item)
            except PlaidItemActionRequired as action:
                items_need_action.append(action.to_payload())

        accounts = PlaidAccount.query.filter_by(user_id=int(user_id)).order_by(PlaidAccount.name).all()
        accounts_payload = [a.to_dict() for a in accounts]

        # At least one bank needs the user to act — surface a calm prompt (409)
        # while still handing back whatever balances are current.
        if items_need_action:
            return jsonify({
                'error_code': 'ITEM_ACTION_REQUIRED',
                'message': 'One or more of your banks need to be reconnected.',
                'items': items_need_action,
                'accounts': accounts_payload,
                'synced': total
            }), 409

        return jsonify({
            'message': f'Synced {total} accounts',
            'accounts': accounts_payload
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/create-link-token', methods=['POST'])
@require_verified_email   # bank linking is gated behind a confirmed email
def create_link_token():
    """Create a Plaid Link token for the user"""

    try:
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        
        client = get_plaid_client()

        request_data = LinkTokenCreateRequest(
            user = LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            client_name="MoneyMind",
            products=[Products('transactions')],
            country_codes=[CountryCode('US')],
            language='en',
            webhook='https://moneymind-dy31.onrender.com/api/plaid/webhook'
        )

        response = client.link_token_create(request_data).to_dict()

        return jsonify({'link_token': response['link_token']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/create-update-link-token', methods=['POST'])
@require_verified_email
def create_update_link_token():
    """Create a Plaid Link token in UPDATE MODE for a specific existing item.

    Update mode re-authenticates an already-linked bank (fixing
    ITEM_LOGIN_REQUIRED etc.) without creating a new item: the token is built
    with the item's existing access_token and no `products`. On success the
    frontend does NOT exchange a public token — the original access_token is
    simply valid again — it just retries the sync."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json(silent=True) or {}
        item_id = data.get('item_id')
        if not item_id:
            return jsonify({'error': 'item_id required'}), 400

        # Scope to the authenticated user — never issue an update token for an
        # item that isn't theirs.
        plaid_item = PlaidItem.query.filter_by(
            user_id=int(user_id), item_id=item_id).first()
        if not plaid_item:
            return jsonify({'error': 'Connected bank not found.'}), 404

        client = get_plaid_client()
        request_data = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=str(user_id)),
            client_name="MoneyMind",
            country_codes=[CountryCode('US')],
            language='en',
            access_token=plaid_item.get_access_token(),  # update mode: no products
            webhook='https://moneymind-dy31.onrender.com/api/plaid/webhook'
        )
        response = client.link_token_create(request_data).to_dict()
        return jsonify({'link_token': response['link_token']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/exchange-public-token', methods=['POST'])
@require_verified_email   # completing a bank link is gated behind a confirmed email
def exchange_public_token():
    """Exchange Plaid public token for access token and store in database"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        public_token = data.get('public_token')

        if not public_token:
            return jsonify({'error': 'public_token required'}), 400

        client = get_plaid_client()

        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = client.item_public_token_exchange(exchange_request)

        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']

        # Get institution name (optional but helpful)
        institution_name = None
        try:
            item_request = ItemGetRequest(access_token=access_token)
            item_response = client.item_get(item_request)
            institution_id = item_response['item']['institution_id']

            # Get institution details
            inst_request = InstitutionsGetByIdRequest(
                institution_id=institution_id,
                country_codes=[CountryCode('US')]
            )
            inst_response = client.institutions_get_by_id(inst_request)
            institution_name = inst_response['institution']['name']
        except Exception as e:
            print(f"Failed to fetch institution name: {e}")

        # Check if item already exists (in case of re-linking)
        existing_item = PlaidItem.query.filter_by(item_id=item_id).first()

        if existing_item:
            # Update existing item (token re-encrypted; cursor reset for the new grant)
            existing_item.set_access_token(access_token)
            existing_item.institution_name = institution_name
            existing_item.sync_cursor = None
            existing_item.updated_at = datetime.utcnow()
        else:
            # Create new PlaidItem record
            plaid_item = PlaidItem(
                user_id=int(user_id),
                item_id=item_id,
                institution_name=institution_name
            )
            plaid_item.set_access_token(access_token)
            db.session.add(plaid_item)

        db.session.commit()

        # Pull the item's accounts + balances right away so envelopes can link to them
        try:
            item_record = PlaidItem.query.filter_by(item_id=item_id).first()
            if item_record:
                sync_accounts_for_item(item_record)
        except Exception as e:
            print(f"Failed to sync accounts after link: {e}")

        return jsonify({
            'item_id': item_id,
            'institution_name': institution_name,
            'message': 'Bank Connected Successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@plaid_bp.route('/sync-transactions', methods=["POST"])
@jwt_required()
def sync_transactions():
    """Fetch transactions from Plaid and save to database"""

    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}

        # Support both old and new API: access_token in body OR fetch from database
        access_token = data.get('access_token')
        plaid_item = None

        if not access_token:
            # New behavior: Fetch access token from PlaidItem table
            # Use the most recent PlaidItem (in case user connected same bank multiple times)
            plaid_item = PlaidItem.query.filter_by(user_id=int(user_id)).order_by(PlaidItem.created_at.desc()).first()

            if not plaid_item:
                return jsonify({
                    'error': 'No bank account connected. Please connect a bank account first.'
                }), 404

            access_token = plaid_item.get_access_token()

        result = perform_transaction_sync(int(user_id), access_token, plaid_item)

        return jsonify({
            'message': f'Successfully synced {result["saved"]} transactions',
            'total_transactions': result['total'],
            'saved_transactions': result['saved'],
            'modified_transactions': result['modified'],
            'removed_transactions': result['removed']
        }), 200

    except PlaidItemActionRequired as action:
        # The bank needs the user to reconnect — a calm, actionable prompt
        # rather than a raw error.
        return jsonify({
            'error_code': 'ITEM_ACTION_REQUIRED',
            'message': action.message,
            'items': [action.to_payload()]
        }), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/webhook', methods=['POST'])
def plaid_webhook():
    """
    Plaid webhook endpoint for automatic transaction updates.
    Plaid calls this directly (no user session), so it's verified with a
    shared secret in the URL: set PLAID_WEBHOOK_SECRET and register the
    webhook as .../api/plaid/webhook?secret=<value> in the Plaid dashboard.
    """
    expected_secret = os.getenv('PLAID_WEBHOOK_SECRET')
    if expected_secret and request.args.get('secret') != expected_secret:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        webhook_data = request.get_json()

        # Log webhook for debugging
        webhook_type = webhook_data.get('webhook_type')
        webhook_code = webhook_data.get('webhook_code')
        item_id = webhook_data.get('item_id')

        print(f"[PLAID WEBHOOK] Type: {webhook_type}, Code: {webhook_code}, Item: {item_id}")

        # Only process TRANSACTIONS webhooks
        if webhook_type == 'TRANSACTIONS':
            # Webhook codes to trigger sync:
            # - INITIAL_UPDATE: Initial transactions are ready
            # - HISTORICAL_UPDATE: Historical transactions are ready
            # - DEFAULT_UPDATE: New/modified transactions (legacy)
            # - SYNC_UPDATES_AVAILABLE: Recommended for transactions sync

            sync_codes = [
                'INITIAL_UPDATE',
                'HISTORICAL_UPDATE',
                'DEFAULT_UPDATE',
                'SYNC_UPDATES_AVAILABLE'
            ]

            if webhook_code in sync_codes:
                # Find PlaidItem by item_id
                plaid_item = PlaidItem.query.filter_by(item_id=item_id).first()

                if not plaid_item:
                    print(f"[PLAID WEBHOOK ERROR] PlaidItem not found for item_id: {item_id}")
                    # Return 200 anyway to acknowledge receipt
                    return jsonify({'status': 'received', 'note': 'item not found'}), 200

                # Perform sync using helper function
                result = perform_transaction_sync(
                    user_id=plaid_item.user_id,
                    access_token=plaid_item.get_access_token(),
                    plaid_item=plaid_item
                )

                print(f"[PLAID WEBHOOK SUCCESS] Synced {result['saved']} transactions for user {plaid_item.user_id}")

                return jsonify({
                    'status': 'success',
                    'saved_transactions': result['saved'],
                    'total_transactions': result['total']
                }), 200
            else:
                # Other transaction webhook codes we don't handle yet
                print(f"[PLAID WEBHOOK] Ignoring code: {webhook_code}")
                return jsonify({'status': 'received', 'note': 'code not handled'}), 200
        else:
            # Non-TRANSACTIONS webhook (e.g., ITEM, AUTH, etc.)
            print(f"[PLAID WEBHOOK] Ignoring type: {webhook_type}")
            return jsonify({'status': 'received', 'note': 'type not handled'}), 200

    except Exception as e:
        # Log error but return 200 to prevent Plaid retries
        print(f"[PLAID WEBHOOK ERROR] {str(e)}")
        return jsonify({'status': 'error', 'message': 'internal error'}), 200