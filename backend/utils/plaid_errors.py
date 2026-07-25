"""
Plaid error handling: turn a raw plaid.ApiException into a structured,
user-facing signal instead of leaking a 400 with a stack-trace string.

The important class of errors here are ITEM errors — the linked bank needs the
user to do something (most commonly re-authenticate) before Plaid will serve
data again. Those are surfaced to the frontend as an "action required" prompt
(reconnect via Plaid Link update mode), not a generic failure.
"""

import json


class PlaidItemActionRequired(Exception):
    """Raised when a Plaid call fails with an item-level error that the user
    must resolve (re-auth, etc.). Carries enough context for the frontend to
    render a calm reconnect prompt for the specific institution."""

    def __init__(self, item, error_code, message, reconnect):
        super().__init__(message)
        self.item_id = item.item_id if item else None
        self.institution_name = item.institution_name if item else None
        self.error_code = error_code
        self.message = message
        self.reconnect = reconnect  # True → Plaid Link update mode fixes it

    def to_payload(self):
        return {
            'item_id': self.item_id,
            'institution_name': self.institution_name,
            'error_code': self.error_code,
            'message': self.message,
            'reconnect': self.reconnect,
        }


# Item errors the user fixes by re-authenticating through Link update mode.
# (Plaid funnels bad credentials / changed MFA / expired consent through these.)
RECONNECT_ERROR_CODES = {
    'ITEM_LOGIN_REQUIRED',
    'PENDING_EXPIRATION',
    'PENDING_DISCONNECT',
    'ITEM_LOCKED',
}

# Item/institution errors that are transient or informational — no reconnect
# button helps; we just say something calm and let the user retry later.
TRANSIENT_ERROR_CODES = {
    'INSTITUTION_DOWN',
    'INSTITUTION_NOT_RESPONDING',
    'INSTITUTION_NO_LONGER_SUPPORTED',
    'ITEM_NOT_SUPPORTED',
    'NO_ACCOUNTS',
    'RATE_LIMIT_EXCEEDED',
}

# All item-level codes we translate into a friendly prompt rather than a raw error.
ITEM_ERROR_CODES = RECONNECT_ERROR_CODES | TRANSIENT_ERROR_CODES


def _friendly_message(error_code, institution_name):
    """A calm, plain-language line for a given item error. `institution_name`
    may be None (fall back to a generic 'your bank')."""
    bank = institution_name or 'your bank'
    messages = {
        'ITEM_LOGIN_REQUIRED':
            f'Your connection to {bank} needs to be reconnected. '
            'This usually happens after a password, security question, or app change.',
        'PENDING_EXPIRATION':
            f'Your connection to {bank} is about to expire. '
            'Reconnect now to keep balances and transactions in sync.',
        'PENDING_DISCONNECT':
            f'Your connection to {bank} is scheduled to disconnect. '
            'Reconnect to keep it active.',
        'ITEM_LOCKED':
            f'{bank} has temporarily locked this connection. '
            'Reconnect to unlock it.',
        'INSTITUTION_DOWN':
            f'{bank} is temporarily unavailable. Please try again in a little while.',
        'INSTITUTION_NOT_RESPONDING':
            f'{bank} isn’t responding right now. Please try again shortly.',
        'INSTITUTION_NO_LONGER_SUPPORTED':
            f'{bank} is no longer supported for syncing.',
        'ITEM_NOT_SUPPORTED':
            f'This {bank} account type isn’t supported for syncing.',
        'NO_ACCOUNTS':
            f'No supported accounts were found at {bank}.',
        'RATE_LIMIT_EXCEEDED':
            'Too many refreshes in a short time. Please wait a moment and try again.',
    }
    return messages.get(
        error_code,
        f'There’s a problem with your connection to {bank}. Please reconnect it.'
    )


def parse_plaid_exception(exc):
    """Extract Plaid's structured error from an exception, if present.

    Plaid's SDK raises plaid.ApiException with a JSON `body` carrying
    error_type / error_code / error_message. Returns a dict with those fields,
    or None if `exc` isn't a parseable Plaid API error."""
    body = getattr(exc, 'body', None)
    if not body:
        return None
    try:
        data = json.loads(body) if isinstance(body, (str, bytes)) else body
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or 'error_code' not in data:
        return None
    return {
        'error_type': data.get('error_type'),
        'error_code': data.get('error_code'),
        'error_message': data.get('error_message'),
        'display_message': data.get('display_message'),
    }


def item_action_from_exception(exc, item):
    """If `exc` is a Plaid item-level error, return a PlaidItemActionRequired
    describing it (without raising); otherwise return None so the caller can
    treat it as a generic failure."""
    parsed = parse_plaid_exception(exc)
    if not parsed:
        return None
    code = parsed['error_code']
    if code not in ITEM_ERROR_CODES:
        return None
    return PlaidItemActionRequired(
        item=item,
        error_code=code,
        message=_friendly_message(code, item.institution_name if item else None),
        reconnect=code in RECONNECT_ERROR_CODES,
    )
