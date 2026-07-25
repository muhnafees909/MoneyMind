"""
Email transport: turns a (to, subject, text, html) message into an actual send.

Provider is chosen by the EMAIL_PROVIDER env var:
  - 'resend'          -> Resend API (production)
  - unset / anything  -> dev mode: log the message + link to the console

Every path returns (success: bool, error: str | None) so callers can log a
failure without ever having it raise into the request flow.
"""

import logging
import os

logger = logging.getLogger('moneymind.email')


def send(to_email, subject, text_body, html_body=None, link=None):
    """Dispatch to the configured provider. Never raises — returns (ok, error)."""
    provider = os.getenv('EMAIL_PROVIDER', '').lower()
    if provider == 'resend':
        return _send_via_resend(to_email, subject, text_body, html_body)
    return _send_via_dev(to_email, subject, link)


def _send_via_dev(to_email, subject, link):
    """No provider configured: log the message so the flow works end-to-end
    in local dev without any external dependency or API key."""
    logger.info(
        '[EMAIL:DEV] would send to=%s subject=%r link=%s',
        to_email, subject, link or '(none)'
    )
    # Also print so it's visible in the dev server console.
    print(f'[EMAIL:DEV] to={to_email} subject={subject!r}\n  link={link}')
    return True, None


def _send_via_resend(to_email, subject, text_body, html_body):
    """Send through the Resend API. Requires RESEND_API_KEY and EMAIL_FROM."""
    api_key = os.getenv('RESEND_API_KEY')
    from_addr = os.getenv('EMAIL_FROM', 'MoneyMind <onboarding@resend.dev>')
    if not api_key:
        logger.error('EMAIL_PROVIDER=resend but RESEND_API_KEY is not set.')
        return False, 'Email is not configured.'

    try:
        import resend
    except ImportError:
        logger.error('EMAIL_PROVIDER=resend but the resend package is not installed.')
        return False, 'Email provider unavailable.'

    resend.api_key = api_key
    params = {
        'from': from_addr,
        'to': [to_email],
        'subject': subject,
        'text': text_body,
    }
    if html_body:
        params['html'] = html_body

    try:
        result = resend.Emails.send(params)
        message_id = (result or {}).get('id') if isinstance(result, dict) else None
        logger.info('[EMAIL:RESEND] sent to=%s id=%s', to_email, message_id or '(none)')
        return True, None
    except Exception as e:
        # Never leak provider internals or the recipient into an exception that
        # bubbles up; log server-side and hand back a generic failure.
        logger.error('[EMAIL:RESEND] send failed to=%s: %s', to_email, e)
        return False, 'Email send failed.'
