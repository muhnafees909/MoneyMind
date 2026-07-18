"""
Chat routes for the AI financial advisor chatbot.
Handles user messages and returns AI financial advice with context.

Every request here ultimately costs money (OpenAI API), so rate limits and
input caps are enforced server-side in utils.advisor_limits — the frontend's
indicator is a courtesy, not the enforcement.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils import advisor_limits
from utils.openai_client import send_message

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/message', methods=['POST'], endpoint='send_message')
@jwt_required()
def send_chat_message():
    """
    Send a message to the AI financial advisor and get a response.

    Request JSON:
    {
        "message": "user's question or message",
        "history": [                       // optional: prior turns, oldest first
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }

    Response JSON (200):
    {
        "response": "AI's response text",
        "context_used": { ... },
        "usage": {                          // rate-limit accounting for the UI
            "minute": {"limit": 10, "used": 2, "remaining": 8},
            "daily": {"limit": 50, "used": 12, "remaining": 38,
                      "resets_in_seconds": 21600}
        }
    }

    Error Response (400, 401, 429, 5xx):
    {
        "error": "Human-readable description",
        "error_code": "MACHINE_READABLE_CODE",
        "retry_after_seconds": 42,          // 429s only
        "usage": { ... }                    // 429s only
    }
    """
    try:
        # Extract user ID from JWT
        user_id = int(get_jwt_identity())

        # Parse request JSON
        data = request.get_json()

        # Validate request
        if not data or not data.get('message'):
            return jsonify({
                'error': 'Invalid request. "message" field is required.',
                'error_code': 'INVALID_REQUEST'
            }), 400

        user_message = data.get('message', '').strip()

        # Validate message is not empty
        if not user_message:
            return jsonify({
                'error': 'Message cannot be empty.',
                'error_code': 'INVALID_REQUEST'
            }), 400

        # Cap message size — oversized prompts drive up token costs
        max_chars = advisor_limits.MAX_MESSAGE_CHARS
        if len(user_message) > max_chars:
            return jsonify({
                'error': (
                    f'That message is too long for the advisor — please keep it '
                    f'under {max_chars:,} characters.'
                ),
                'error_code': 'MESSAGE_TOO_LONG'
            }), 400

        # Validate optional conversation history (same caps: history is
        # replayed into the prompt, so it's the same cost surface)
        history = data.get('history') or []
        if not isinstance(history, list):
            return jsonify({
                'error': 'Invalid request. "history" must be a list of messages.',
                'error_code': 'INVALID_REQUEST'
            }), 400
        if len(history) > advisor_limits.MAX_HISTORY_ENTRIES:
            return jsonify({
                'error': (
                    f'Conversation history is too long — send at most '
                    f'{advisor_limits.MAX_HISTORY_ENTRIES} prior messages.'
                ),
                'error_code': 'HISTORY_TOO_LONG'
            }), 400
        for msg in history:
            if (not isinstance(msg, dict)
                    or msg.get('role') not in ('user', 'assistant')
                    or not isinstance(msg.get('content'), str)
                    or len(msg['content']) > max_chars):
                return jsonify({
                    'error': 'Invalid request. Each history entry needs a role of '
                             '"user" or "assistant" and content under '
                             f'{max_chars:,} characters.',
                    'error_code': 'INVALID_REQUEST'
                }), 400

        # Our own rate limits (per-minute burst + daily cost cap) — checked
        # before anything reaches OpenAI
        limited = advisor_limits.check_limits(user_id, user_message)
        if limited:
            response = jsonify({
                'error': limited['message'],
                'error_code': limited['error_code'],
                'retry_after_seconds': limited['retry_after_seconds'],
                'usage': advisor_limits.usage_snapshot(user_id)
            })
            response.headers['Retry-After'] = str(limited['retry_after_seconds'])
            return response, 429

        # Count the attempt before calling out, so a mid-call crash still
        # consumes quota; also runs abuse-pattern checks
        advisor_limits.record_usage(user_id, user_message)

        # Get AI response
        result = send_message(user_id, user_message, history=history)

        # Check if there was an error (OpenAI-side failures — distinct from
        # our own rate limiting above, with their own codes/messages)
        if result.get('error'):
            # Determine appropriate status code
            error_code = result.get('error_code', 'INTERNAL_ERROR')
            status_code = 500

            if error_code == 'RATE_LIMIT':
                status_code = 429
            elif error_code == 'TIMEOUT':
                status_code = 504
            elif error_code == 'INVALID_API_KEY':
                status_code = 500
            elif error_code == 'CONNECTION_ERROR':
                status_code = 503

            return jsonify({
                'error': result['error'],
                'error_code': error_code
            }), status_code

        # Success response
        return jsonify({
            'response': result['response'],
            'context_used': result['context_used'],
            'usage': advisor_limits.usage_snapshot(user_id)
        }), 200

    except ValueError as e:
        # Handle validation errors
        return jsonify({
            'error': str(e),
            'error_code': 'INVALID_REQUEST'
        }), 400

    except Exception as e:
        # Log unexpected errors
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred. Please try again later.',
            'error_code': 'INTERNAL_ERROR'
        }), 500


@chat_bp.route('/usage', methods=['GET'])
@jwt_required()
def advisor_usage():
    """Current advisor usage vs. limits — powers the in-UI indicator."""
    user_id = int(get_jwt_identity())
    return jsonify(advisor_limits.usage_snapshot(user_id)), 200
