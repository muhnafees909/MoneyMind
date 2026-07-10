"""One-time script: encrypt any plaintext Plaid access tokens already in the
database. Safe to run repeatedly — already-encrypted rows are skipped.

Usage: venv\\Scripts\\python.exe encrypt_existing_tokens.py
Run once locally and once on production after deploying token encryption.
"""
from app import app
from models.user import db
from models.plaid_item import PlaidItem
from utils.token_crypto import encrypt_token, is_encrypted


def main():
    with app.app_context():
        items = PlaidItem.query.all()
        encrypted = 0
        for item in items:
            if not is_encrypted(item.access_token):
                item.access_token = encrypt_token(item.access_token)
                encrypted += 1
        db.session.commit()
        print(f"Checked {len(items)} Plaid item(s); encrypted {encrypted} plaintext token(s).")


if __name__ == '__main__':
    main()
