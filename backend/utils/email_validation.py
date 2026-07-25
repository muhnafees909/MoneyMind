"""
Signup email checks: RFC-ish format validation (server-side, never trusting the
client) and disposable/temporary-domain rejection via a maintained open-source
blocklist. Both run before an account is created.
"""

from email_validator import validate_email, EmailNotValidError
from disposable_email_domains import blocklist as _disposable_blocklist


def normalize_and_validate_email(raw):
    """
    Returns (normalized_email, None) when valid, or (None, error_message).
    Rejects malformed addresses and known disposable domains.
    """
    if not raw or not raw.strip():
        return None, 'Email is required.'

    try:
        # check_deliverability=False → no DNS/network lookups; pure format + normalization
        info = validate_email(raw.strip(), check_deliverability=False)
    except EmailNotValidError:
        return None, 'Please enter a valid email address.'

    email = info.normalized.lower()
    domain = email.rsplit('@', 1)[-1]
    if domain in _disposable_blocklist:
        return None, 'Please use a permanent email address — temporary/disposable addresses aren’t allowed.'

    return email, None
