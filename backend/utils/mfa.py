"""
TOTP MFA helpers: secret generation, provisioning URI + QR (SVG, no PIL),
code verification with a small clock-skew window, and one-time backup codes.

The TOTP secret is Fernet-encrypted at rest (same scheme as Plaid tokens).
Backup codes are shown once and stored bcrypt-hashed.
"""

import base64
import io
import secrets

import bcrypt
import pyotp
import qrcode
import qrcode.image.svg

from models.user import db, MfaBackupCode
from utils.token_crypto import encrypt_token, decrypt_token

ISSUER = 'MoneyMind'
BACKUP_CODE_COUNT = 10
# TOTP validity window: accept the current step ±1 (~30s either side) for clock skew
VALID_WINDOW = 1


def generate_secret():
    """A new base32 TOTP secret (raw — encrypt before storing)."""
    return pyotp.random_base32()


def store_secret(user, secret):
    user.mfa_secret = encrypt_token(secret)


def load_secret(user):
    return decrypt_token(user.mfa_secret) if user.mfa_secret else None


def provisioning_uri(user, secret):
    """otpauth:// URI for the authenticator app."""
    return pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)


def qr_svg_data_uri(uri):
    """Render the provisioning URI as an SVG QR code, returned as a data: URI the
    frontend can drop straight into an <img>. SVG avoids the PIL dependency."""
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue()
    b64 = base64.b64encode(svg).decode('ascii')
    return f'data:image/svg+xml;base64,{b64}'


def verify_code(secret, code):
    """True if `code` is a valid TOTP for `secret` (with skew window)."""
    if not secret or not code:
        return False
    code = str(code).strip().replace(' ', '')
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=VALID_WINDOW)
    except Exception:
        return False


# ----- backup codes -----

def _format_code(raw):
    # 10 hex chars grouped for readability, e.g. "3f9a2-7c1b8"
    return f'{raw[:5]}-{raw[5:10]}'


def generate_backup_codes(user):
    """Replace any existing backup codes with a fresh set. Returns the raw codes
    (shown to the user exactly once); only bcrypt hashes are stored."""
    MfaBackupCode.query.filter_by(user_id=user.id).delete()
    raw_codes = []
    for _ in range(BACKUP_CODE_COUNT):
        code = _format_code(secrets.token_hex(5))  # 10 hex chars
        raw_codes.append(code)
        code_hash = bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        db.session.add(MfaBackupCode(user_id=user.id, code_hash=code_hash, used=False))
    return raw_codes


def consume_backup_code(user, code):
    """If `code` matches an unused backup code, mark it used and return True."""
    if not code:
        return False
    candidate = code.strip().replace(' ', '')
    for bc in MfaBackupCode.query.filter_by(user_id=user.id, used=False).all():
        try:
            if bcrypt.checkpw(candidate.encode('utf-8'), bc.code_hash.encode('utf-8')):
                bc.used = True
                db.session.commit()
                return True
        except ValueError:
            continue
    return False


def unused_backup_code_count(user):
    return MfaBackupCode.query.filter_by(user_id=user.id, used=False).count()
