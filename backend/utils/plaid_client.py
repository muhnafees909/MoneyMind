import os
from plaid.api import plaid_api
from plaid.api_client import ApiClient
from plaid.configuration import Configuration

def get_plaid_client():
    """Initialize and return Plaid client"""
    
    # Map environment names to URLs
    env_map = {
        'sandbox': 'https://sandbox.plaid.com',
        'development': 'https://development.plaid.com',
        'production': 'https://production.plaid.com'
    }
    
    plaid_env = os.getenv('PLAID_ENV', 'sandbox')
    
    configuration = Configuration(
        host=env_map.get(plaid_env, env_map['sandbox']),
        api_key={
            'clientId': os.getenv('PLAID_CLIENT_ID'),
            'secret': os.getenv('PLAID_SECRET'),
        }
    )
    
    api_client = ApiClient(configuration)
    client = plaid_api.PlaidApi(api_client)
    
    return client