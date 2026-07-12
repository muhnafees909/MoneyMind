"""
Chat routes for the AI financial advisor chatbot.
Handles user messages and returns AI financial advice with context.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
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
        "context_used": {
            "budgets_count": 3,
            "active_goals": 2,
            "completed_goals": 0,
            "monthly_spending": 2450.50,
            "categories_analyzed": 5,
            "recent_transactions_analyzed": 20,
            "model_used": "gpt-4o-mini"
        }
    }

    Error Response (400, 401, 500):
    {
        "error": "Error description"
    }
    """
    try:
        # Extract user ID from JWT
        user_id = get_jwt_identity()

        # Parse request JSON
        data = request.get_json()

        # Validate request
        if not data or not data.get('message'):
            return jsonify({
                'error': 'Invalid request. "message" field is required.'
            }), 400

        user_message = data.get('message', '').strip()

        # Validate message is not empty
        if not user_message:
            return jsonify({
                'error': 'Message cannot be empty.'
            }), 400

        # Validate message length (prevent abuse)
        if len(user_message) > 5000:
            return jsonify({
                'error': 'Message is too long. Please keep it under 5000 characters.'
            }), 400

        # Validate optional conversation history
        history = data.get('history') or []
        if not isinstance(history, list):
            return jsonify({
                'error': 'Invalid request. "history" must be a list of messages.'
            }), 400
        for msg in history:
            if (not isinstance(msg, dict)
                    or msg.get('role') not in ('user', 'assistant')
                    or not isinstance(msg.get('content'), str)
                    or len(msg['content']) > 5000):
                return jsonify({
                    'error': 'Invalid request. Each history entry needs a role of '
                             '"user" or "assistant" and content under 5000 characters.'
                }), 400

        # Get AI response
        result = send_message(int(user_id), user_message, history=history)

        # Check if there was an error
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
                'error': result['error']
            }), status_code

        # Success response
        return jsonify({
            'response': result['response'],
            'context_used': result['context_used']
        }), 200

    except ValueError as e:
        # Handle validation errors
        return jsonify({
            'error': str(e)
        }), 400

    except Exception as e:
        # Log unexpected errors
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred. Please try again later.'
        }), 500
