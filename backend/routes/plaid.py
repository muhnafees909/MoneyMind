import json
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.plaid_client import get_plaid_client
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.transactions_sync_request import TransactionsSyncRequest 
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from models.transaction import Transaction
from datetime import datetime, date
from models.user import db, User

plaid_bp = Blueprint('plaid', __name__)

@plaid_bp.route('/create-link-token', methods=['POST'])
@jwt_required()
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
            language='en'
        )

        response = client.link_token_create(request_data).to_dict()

        return jsonify({'link_token': response['link_token']}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/exchange-public-token', methods=['POST'])
@jwt_required()
def exchange_public_token():
    """Exchange Plaid public token for access token"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        public_token = data.get('public_token')

        if not public_token:
            return jsonify({'error': 'public_token required'}), 500

        client = get_plaid_client()

        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = client.item_public_token_exchange(exchange_request)

        access_token = exchange_response['access_token']  # Now this will work
        item_id = exchange_response['item_id']
        
        # TODO: Store access_token and item_id in database
        # For now, just return them

        return jsonify({
            'access_token': access_token,
            'item_id': item_id, 
            'message': 'Bank Connected Successfully'
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@plaid_bp.route('/sync-transactions', methods=["POST"])
@jwt_required()
def sync_transactions():
    """Fetch transactions from Plaid and save to database"""

    try: 
        user_id = get_jwt_identity()
        data = request.get_json()
        access_token = data.get('access_token')

        if not access_token: 
            return jsonify({'error': 'access_token required'}), 400

        client = get_plaid_client()

        request_data = TransactionsSyncRequest(access_token=access_token)
        response = client.transactions_sync(request_data).to_dict()

        transactions = response.get('added', [])
        saved_count = 0

        for txn in transactions:

            # Check if transaction already exists
            existing = Transaction.query.filter_by(plaid_transaction_id=txn['transaction_id']).first()

            if not existing: 
                # Create new transaction
                transaction = Transaction(
                    user_id=int(user_id),
                    amount=abs(txn['amount']),
                    description=txn['name'],
                    category=txn['personal_finance_category']['primary'] if txn.get('personal_finance_category') else 'other',
                    transaction_date=txn['date'],
                    transaction_type='expense' if txn['amount'] > 0 else 'income',
                    source='plaid',
                    plaid_transaction_id=txn['transaction_id'],
                    transaction_notes=f"Merchant: {txn.get('merchant_name', 'N/A')}"
                )

                db.session.add(transaction)
                saved_count += 1
            
        db.session.commit()

        return jsonify({
            'message': f'Successfully synced {saved_count} transactions',
            'total_transactions': len(transactions),
            'saved_transactions': saved_count
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500