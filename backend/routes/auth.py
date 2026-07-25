from datetime import timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from models.user import db, User
from utils.email_validation import normalize_and_validate_email
from utils.email_verification import (
    issue_verification_token, send_verification_email, verify_token,
)
from utils import login_security as ls
from utils import mfa as mfa_util

auth_bp = Blueprint('auth', __name__)

# How long the intermediate "password ok, awaiting TOTP" token is valid.
MFA_PENDING_TTL = timedelta(minutes=5)
# Minimum gap between verification-email sends (anti-spam).
RESEND_COOLDOWN = timedelta(seconds=60)


def _user_payload(user):
    return {
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'email_verified': user.email_verified,
        'mfa_enabled': user.mfa_enabled,
    }


def _session_response(user, status=200, message=None):
    """
    Issue the session as secure httpOnly cookies (access + refresh).
    Tokens are deliberately NOT included in the response body — the browser
    must never be tempted to persist them in localStorage.
    """
    payload = {'user': _user_payload(user)}
    if message:
        payload['message'] = message
    response = jsonify(payload)
    set_access_cookies(response, create_access_token(identity=str(user.id)))
    set_refresh_cookies(response, create_refresh_token(identity=str(user.id)))
    return response, status


# ============================================================
# Register / Login / Session
# ============================================================

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}

    if not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400

    # Server-side email validation: format + disposable-domain block (never
    # trust the client's own check).
    email, email_error = normalize_and_validate_email(data.get('email'))
    if email_error:
        return jsonify({'message': email_error}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'An account with this email already exists'}), 400

    user = User(email=email, first_name=data.get('first_name', ''), email_verified=False)
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()

    # Send the verification link (dev: logged; prod: real transport). Never let
    # an email hiccup block signup.
    try:
        raw = issue_verification_token(user)
        send_verification_email(user, raw)
    except Exception as e:
        print(f'[REGISTER] verification email failed (non-fatal): {e}')

    # Basic access is allowed while unverified — a session is issued now.
    return _session_response(user, 201, 'User created successfully')


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    if not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400

    email = data['email'].strip().lower()
    ip = ls.client_ip()

    # 1) Brute-force gate — checked before touching credentials.
    locked, lock_msg, retry = ls.check_locked(email, ip)
    if locked:
        resp = jsonify({'message': lock_msg, 'code': 'account_locked',
                        'retry_after_seconds': retry})
        resp.headers['Retry-After'] = str(retry)
        return resp, 429

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(data['password']):
        ls.record_failure(email, ip)
        # Non-revealing: never confirm whether the email exists.
        return jsonify({'message': 'Incorrect email or password'}), 401

    # Transparently upgrade legacy pbkdf2 hashes to bcrypt
    if user.password_needs_rehash:
        user.set_password(data['password'])
        db.session.commit()

    # 2) Second factor, if enabled — don't issue a session yet.
    if user.mfa_enabled:
        pending = create_access_token(
            identity=str(user.id),
            additional_claims={'mfa_pending': True},
            expires_delta=MFA_PENDING_TTL,
        )
        return jsonify({'mfa_required': True, 'mfa_token': pending}), 200

    ls.record_success(email, ip)
    return _session_response(user)


@auth_bp.route('/login/mfa', methods=['POST'])
def login_mfa():
    """Second step of login: verify the TOTP (or a backup) code against the
    short-lived pending token, then issue the real session."""
    data = request.get_json() or {}
    token = data.get('mfa_token')
    code = data.get('code')
    ip = ls.client_ip()

    # Decode the intermediate token
    try:
        decoded = decode_token(token)
    except Exception:
        return jsonify({'message': 'Your verification step expired. Please sign in again.',
                        'code': 'mfa_expired'}), 401
    if not decoded.get('mfa_pending'):
        return jsonify({'message': 'Invalid verification token.'}), 401

    user = User.query.get(decoded.get('sub'))
    if not user or not user.mfa_enabled:
        return jsonify({'message': 'Invalid verification token.'}), 401

    email = user.email
    locked, lock_msg, retry = ls.check_locked(email, ip)
    if locked:
        resp = jsonify({'message': lock_msg, 'code': 'account_locked',
                        'retry_after_seconds': retry})
        resp.headers['Retry-After'] = str(retry)
        return resp, 429

    secret = mfa_util.load_secret(user)
    ok = mfa_util.verify_code(secret, code) or mfa_util.consume_backup_code(user, code)
    if not ok:
        ls.record_failure(email, ip)
        return jsonify({'message': 'That code isn’t right. Try again.',
                        'code': 'mfa_invalid'}), 401

    ls.record_success(email, ip)
    return _session_response(user)


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Sliding-session refresh: fresh access AND refresh cookies."""
    identity = get_jwt_identity()
    response = jsonify({'message': 'Session refreshed'})
    set_access_cookies(response, create_access_token(identity=identity))
    set_refresh_cookies(response, create_refresh_token(identity=identity))
    return response, 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear session cookies. Unauthenticated so an already-expired session can
    still sign out."""
    response = jsonify({'message': 'Signed out'})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify(_user_payload(user)), 200


# ============================================================
# Email verification
# ============================================================

@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Consume a verification token (public — the link works before login)."""
    data = request.get_json(silent=True) or {}
    token = data.get('token') or request.args.get('token')
    user, error = verify_token(token)
    if error:
        return jsonify({'message': error}), 400
    return jsonify({'message': 'Email verified', 'user': _user_payload(user)}), 200


@auth_bp.route('/verify-email/resend', methods=['POST'])
@jwt_required()
def resend_verification():
    user = User.query.get(get_jwt_identity())
    if not user:
        return jsonify({'message': 'User not found'}), 404
    if user.email_verified:
        return jsonify({'message': 'Your email is already verified.'}), 400
    # light anti-spam cooldown
    from datetime import datetime
    if user.verification_sent_at and \
            datetime.utcnow() - user.verification_sent_at < RESEND_COOLDOWN:
        return jsonify({'message': 'A verification email was just sent — check your inbox.'}), 429
    try:
        raw = issue_verification_token(user)
        send_verification_email(user, raw)
    except Exception as e:
        print(f'[RESEND] verification email failed: {e}')
        return jsonify({'message': 'Could not send the email right now. Try again shortly.'}), 500
    return jsonify({'message': 'Verification email sent.'}), 200


# ============================================================
# MFA management (all require an active session)
# ============================================================

@auth_bp.route('/mfa/status', methods=['GET'])
@jwt_required()
def mfa_status():
    user = User.query.get(get_jwt_identity())
    return jsonify({
        'mfa_enabled': user.mfa_enabled,
        'backup_codes_remaining': mfa_util.unused_backup_code_count(user) if user.mfa_enabled else 0,
    }), 200


@auth_bp.route('/mfa/setup', methods=['POST'])
@jwt_required()
def mfa_setup():
    """Begin enrollment: generate a secret and return the QR + manual key. Not
    active until confirmed with a valid code."""
    user = User.query.get(get_jwt_identity())
    if user.mfa_enabled:
        return jsonify({'message': 'MFA is already enabled.'}), 400

    secret = mfa_util.generate_secret()
    mfa_util.store_secret(user, secret)   # stored (encrypted) but mfa_enabled stays False
    db.session.commit()

    uri = mfa_util.provisioning_uri(user, secret)
    return jsonify({
        'secret': secret,                 # manual-entry fallback
        'otpauth_uri': uri,
        'qr_data_uri': mfa_util.qr_svg_data_uri(uri),
    }), 200


@auth_bp.route('/mfa/confirm', methods=['POST'])
@jwt_required()
def mfa_confirm():
    """Finish enrollment: verify a code, enable MFA, return one-time backup codes."""
    user = User.query.get(get_jwt_identity())
    if user.mfa_enabled:
        return jsonify({'message': 'MFA is already enabled.'}), 400

    secret = mfa_util.load_secret(user)
    if not secret:
        return jsonify({'message': 'Start MFA setup first.'}), 400

    code = (request.get_json() or {}).get('code')
    if not mfa_util.verify_code(secret, code):
        return jsonify({'message': 'That code isn’t right. Check your authenticator app and try again.'}), 400

    user.mfa_enabled = True
    backup_codes = mfa_util.generate_backup_codes(user)
    db.session.commit()
    return jsonify({
        'message': 'MFA enabled',
        'backup_codes': backup_codes,   # shown exactly once
    }), 200


@auth_bp.route('/mfa/disable', methods=['POST'])
@jwt_required()
def mfa_disable():
    """Turn MFA off. Requires re-auth (password + a current TOTP/backup code) so
    a hijacked session alone can't remove the second factor."""
    user = User.query.get(get_jwt_identity())
    if not user.mfa_enabled:
        return jsonify({'message': 'MFA is not enabled.'}), 400

    data = request.get_json() or {}
    if not user.check_password(data.get('password', '')):
        return jsonify({'message': 'Password is incorrect.'}), 401

    secret = mfa_util.load_secret(user)
    code = data.get('code')
    if not (mfa_util.verify_code(secret, code) or mfa_util.consume_backup_code(user, code)):
        return jsonify({'message': 'That authentication code isn’t right.'}), 401

    user.mfa_enabled = False
    user.mfa_secret = None
    from models.user import MfaBackupCode
    MfaBackupCode.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    return jsonify({'message': 'MFA disabled'}), 200
