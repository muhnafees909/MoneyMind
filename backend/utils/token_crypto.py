"""Encryption-at-rest for Plaid access tokens.

Key comes from PLAID_TOKEN_ENCRYPTION_KEY (any string; hashed to a Fernet key).
Falls back to deriving from JWT_SECRET_KEY so local dev works without new
config — set a dedicated key in production so rotating JWT secrets doesn't
orphan stored tokens.
"""
import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    material = os.getenv('PLAID_TOKEN_ENCRYPTION_KEY') or os.getenv('JWT_SECRET_KEY') or 'moneymind-dev'
    digest = hashlib.sha256(material.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(stored: str) -> str:
    """Decrypt a stored token. Legacy plaintext rows (pre-encryption) are
    returned as-is so nothing breaks before the one-time re-encrypt runs."""
    try:
        return _fernet().decrypt(stored.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return stored


def is_encrypted(stored: str) -> bool:
    try:
        _fernet().decrypt(stored.encode())
        return True
    except (InvalidToken, ValueError, TypeError):
        return False
