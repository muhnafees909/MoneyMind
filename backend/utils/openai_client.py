"""
OpenAI client wrapper for the financial advisor chatbot.
Handles API calls to GPT-4o-mini with proper error handling and prompt engineering.
"""

import os
from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError
from utils.financial_context import format_context_for_llm, build_context_string


# Initialize OpenAI client
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

client = OpenAI(api_key=api_key)

# Configuration
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
API_TIMEOUT = int(os.getenv('OPENAI_API_TIMEOUT', '30'))


def get_system_prompt(context_string):
    """
    Build the system prompt for the financial advisor AI.

    Args:
        context_string: Formatted user financial context

    Returns:
        System prompt string for GPT
    """
    system_prompt = f"""You are MoneyMind's personal financial advisor AI. Your role is to provide helpful,
specific, and actionable financial advice based on the user's actual financial data.

IMPORTANT CONSTRAINTS:
1. You ONLY answer finance-related questions. If a user asks about non-financial topics,
   politely redirect them: "I'm specifically designed to help with financial advice. Would you like
   to discuss your budgets, spending, goals, or other financial matters instead?"

2. Your advice must be:
   - SPECIFIC: Reference their actual budgets, spending, and goals
   - ACTIONABLE: Give concrete steps they can take
   - ENCOURAGING: Be supportive while remaining honest about financial realities
   - DATA-DRIVEN: Base recommendations on their financial data below

3. When users ask about changes to budgets/goals, validate against their actual spending:
   - Check if their suggested budget is realistic based on recent spending
   - Point out if they're on track or overspending in relevant categories
   - Suggest specific categories where they might find savings

4. Format your response:
   - Start with a direct answer to their question
   - Reference specific numbers from their financial data
   - Provide 1-3 actionable next steps
   - If relevant, warn about potential overspending or budget concerns

Here is the user's current financial data to inform your advice:

{context_string}

Now, provide thoughtful, personalized financial advice based on this context and the user's question."""

    return system_prompt


def send_message(user_id, user_message):
    """
    Send a user message to the AI financial advisor and get a response.

    Args:
        user_id: ID of the user asking the question
        user_message: The user's message/question

    Returns:
        dict with:
        - response: AI's response text
        - context_used: Metadata about context gathered
        - error: Error message if something went wrong

    Raises:
        ValueError: If OpenAI API key is not configured
    """
    try:
        # Gather user's financial context
        try:
            context = format_context_for_llm(user_id)
            context_string = build_context_string(context)
            print(f"[CHAT DEBUG] Context built successfully for user {user_id}")
        except Exception as e:
            print(f"Error gathering financial context: {e}")
            # Return error response
            return {
                'response': None,
                'error': 'Unable to gather your financial data. Please try again.',
                'error_code': 'CONTEXT_ERROR'
            }

        # Build system prompt with context
        system_prompt = get_system_prompt(context_string)
        print(f"[CHAT DEBUG] System prompt length: {len(system_prompt)} characters")
        if not context_string or len(context_string.strip()) < 50:
            print(f"[CHAT DEBUG] WARNING: Context string may be too short or empty")
            print(f"[CHAT DEBUG] Context preview: {context_string[:300]}")

        # Call OpenAI API
        print(f"[CHAT DEBUG] Sending message to OpenAI - User: {user_id}, Model: {MODEL}")
        print(f"[CHAT DEBUG] User message: {user_message[:100]}...")
        print(f"[CHAT DEBUG] System prompt preview: {system_prompt[:200]}...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        print(f"[CHAT DEBUG] Full message list: {len(messages)} messages")
        for i, msg in enumerate(messages):
            print(f"[CHAT DEBUG] Message {i}: role={msg['role']}, content_length={len(msg['content'])}")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
            timeout=API_TIMEOUT
        )

        print(f"[CHAT DEBUG] Response object received, type: {type(response)}")

        # Extract response text
        print(f"[CHAT DEBUG] response.choices[0]: {response.choices[0]}")
        print(f"[CHAT DEBUG] response.choices[0].message: {response.choices[0].message}")

        ai_response = response.choices[0].message.content
        print(f"[CHAT DEBUG] ai_response type: {type(ai_response)}")
        print(f"[CHAT DEBUG] ai_response value: '{ai_response}'")
        print(f"[CHAT DEBUG] ai_response length: {len(ai_response) if ai_response else 0}")
        print(f"[CHAT DEBUG] OpenAI response received: {ai_response[:min(200, len(ai_response) if ai_response else 0)]}...")

        # Validate response is not empty
        if not ai_response or not ai_response.strip():
            print(f"[CHAT DEBUG] ERROR: OpenAI returned empty response")
            return {
                'response': None,
                'error': 'Received empty response from AI service. Please try again.',
                'error_code': 'EMPTY_RESPONSE'
            }

        # Prepare context metadata for response
        context_used = {
            'budgets_count': len(context['budgets']),
            'active_goals': len([g for g in context['goals'] if g['status'] == 'active']),
            'completed_goals': len([g for g in context['goals'] if g['status'] == 'completed']),
            'monthly_spending': context['spending_summary']['month_spending'],
            'categories_analyzed': len(context['spending_by_category']),
            'recent_transactions_analyzed': len(context['recent_transactions']),
            'model_used': MODEL
        }

        return {
            'response': ai_response,
            'context_used': context_used,
            'error': None
        }

    except RateLimitError:
        return {
            'response': None,
            'error': 'API rate limit exceeded. Please try again in a moment.',
            'error_code': 'RATE_LIMIT'
        }

    except APITimeoutError:
        return {
            'response': None,
            'error': 'AI advisor is thinking... please try again in a moment.',
            'error_code': 'TIMEOUT'
        }

    except APIConnectionError as e:
        return {
            'response': None,
            'error': 'Unable to connect to AI service. Please check your connection and try again.',
            'error_code': 'CONNECTION_ERROR'
        }

    except ValueError as e:
        if 'API key' in str(e):
            return {
                'response': None,
                'error': 'AI service not properly configured. Please contact support.',
                'error_code': 'INVALID_API_KEY'
            }
        raise

    except Exception as e:
        # Log the error in production
        print(f"Unexpected error in OpenAI client: {str(e)}")
        return {
            'response': None,
            'error': 'An error occurred while getting financial advice. Please try again later.',
            'error_code': 'INTERNAL_ERROR'
        }
