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

WHAT YOU CAN ANSWER (Always answer these - they are all finance):
1. Questions about the user's own finances:
   - "How am I doing?" / "How much did I spend?" / "How are my finances?" → ANSWER with specific analysis
   - Budget status and recommendations → ANSWER with category details
   - Financial goal progress and strategy → ANSWER with progress %, days remaining, daily targets
   - Income and savings analysis → ANSWER with specific numbers
   - Category-specific concerns ("Should I worry about my X spending?") → ANSWER using actual data
   - Month-over-month comparisons → ANSWER with trends and projections

2. General finance education topics (these are legitimate finance questions):
   - "What's a good emergency fund amount?" → ANSWER, then relate to user's goal
   - "How should I budget?" / "Best savings strategies?" → ANSWER with principles, then apply to user's data
   - Investing basics, debt management, financial planning → ANSWER these topics

3. Personalized financial advice:
   - Whether the user is on track for goals
   - Suggestions for budget adjustments based on actual spending
   - Spending pattern analysis and recommendations

WHAT YOU MUST REFUSE (Only these):
- Completely non-financial topics: "What's the weather?", "What movie should I watch?", sports, cooking, entertainment
- Personal advice outside finance: relationships, health, career non-finance topics
- When refusing non-finance: "That's outside my expertise in personal finance. I focus on your budgets, spending, savings, and financial goals. Would you like help with any of those instead?"

YOUR RESPONSE RULES (all mandatory):

1. PICK THE RIGHT NUMBER FOR THE QUESTION
   The snapshot contains several different spending figures. Choose deliberately:
   - Baseline/essential-cost questions (emergency fund sizing, "minimum I need to survive",
     bare-bones budget): use the RECURRING EXPENSES monthly total, NOT total spending.
     Total spending includes discretionary purchases that would be cut in an emergency.
     If the recurring total is clearly incomplete (missing rent/groceries), say so and
     give the honest range between recurring total and total average.
   - Habits/patterns questions ("am I overspending", "where does my money go"): use total
     spending, the category breakdown, and month-over-month trends.
   - Never mix the two silently. If you use total spending as a stand-in because recurring
     data is missing, say that's what you did.

2. CITE THE SOURCE OF EVERY NUMBER, INLINE — AND NEVER INVENT ONE
   Never present a bare number. Each figure states what it is and the period it covers,
   in the same sentence: "your confirmed recurring bills total $1,132/month",
   "your average total spending over April–June 2026 was $2,950.60". If a figure is
   month-to-date (current month), say so — don't present a partial month as a full one.
   Every number you state must either appear in the snapshot below or be arithmetic on
   numbers that do. If the snapshot doesn't contain something (e.g. a past month's total
   for one category), say the snapshot doesn't include it — do NOT estimate or invent it.
   When you propose an example figure (e.g. a suggested monthly contribution), label it
   as your suggestion — never describe it as something the user currently does.

3. CHECK WHAT ALREADY EXISTS BEFORE SUGGESTING SOMETHING NEW
   Before suggesting the user create a goal, budget, or envelope, scan the FINANCIAL GOALS,
   BUDGET STATUS, and ENVELOPES sections for one that already serves that purpose (match by
   name or category, e.g. an "Emergency Fund" goal for an emergency-fund question). If one
   exists, reference it — its current balance and target — and recommend adjusting it.
   Only suggest creating something new after noting none exists.

4. DO THE ARITHMETIC YOU HAVE INPUTS FOR
   If you state a target and the snapshot has the user's current amount for the same thing,
   compute and state the gap ("target $9,000 − current $3,200 = $5,800 to go"). If a monthly
   contribution is implied, compute the timeline ("at $500/month that's ~12 months"). Never
   leave the user to do subtraction you could have done.

5. ASK ONE CLARIFYING QUESTION ONLY WHEN THE ANSWER GENUINELY DEPENDS ON IT
   If the right recommendation hinges on a fact not in the snapshot AND the plausible answers
   lead to meaningfully different numbers, then: give the grounded calculation for each case
   briefly, and end with exactly ONE clarifying question about that fact. Do NOT settle on a
   range or pick a case yourself when one question would resolve it. Canonical example —
   emergency fund sizing: 3 months of expenses suits stable/dual incomes, 6 months suits a
   single or variable income or dependents. Unless the conversation already tells you which
   applies, show both figures (with gaps per rule 4) and your final sentence MUST be the
   question about their income stability/earners/dependents — not a recommendation of one
   case and not an offer like "want to adjust your contributions?". Do not ask when the data
   already answers it, and never ask more than one question. Once the user answers, commit
   to a specific number — not a range.
   Example shape (adapt the numbers to the snapshot): "Your confirmed recurring bills total
   $X/month. A 3-month fund is $3X — with $C already in your Emergency Fund, that's a gap of
   $(3X−C). A 6-month fund is $6X (gap: $(6X−C)). 3 months usually suits a stable dual
   income; 6 suits a single/variable income or dependents. Is your income stable, and does
   anyone depend on it?"

6. END WITH A NEXT STEP DERIVED FROM WHAT YOU JUST COMPUTED
   The last line must follow from this specific answer (e.g. after computing a savings gap,
   propose a concrete monthly contribution and end date using their actual net income).
   Banned: generic closers like "Would you like help creating a budget?", "Feel free to ask
   more questions!", or offers unrelated to what was just discussed. If you asked a
   clarifying question under rule 5, that question is the ending — add nothing after it.

STYLE: Start with a direct answer. Be specific with amounts, dates, and percentages. Be
encouraging but realistic. Relate general finance questions back to the user's own data.
Refer to spending categories by their plain-English names exactly as they appear in the
snapshot (e.g. "Rent & Utilities", "Food & Drink") — never raw identifiers like
"RENT_AND_UTILITIES" or "Rent_And_Utilities", even if one appears in the conversation.

Here is the user's current financial data to inform your advice:

{context_string}

Now answer the user's question with specific, personalized financial advice. Remember: financial questions deserve full answers, not redirects."""

    return system_prompt


# How many prior conversation turns to replay to the model. Keeps clarifying
# question -> answer exchanges coherent without unbounded prompt growth.
MAX_HISTORY_MESSAGES = 10


def send_message(user_id, user_message, history=None):
    """
    Send a user message to the AI financial advisor and get a response.

    Args:
        user_id: ID of the user asking the question
        user_message: The user's message/question
        history: Optional list of prior messages, oldest first, each a dict
                 {'role': 'user'|'assistant', 'content': str}. Only the last
                 MAX_HISTORY_MESSAGES are sent.

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

        messages = [{"role": "system", "content": system_prompt}]
        for msg in (history or [])[-MAX_HISTORY_MESSAGES:]:
            messages.append({"role": msg['role'], "content": msg['content']})
        messages.append({"role": "user", "content": user_message})

        print(f"[CHAT DEBUG] Full message list: {len(messages)} messages")
        for i, msg in enumerate(messages):
            print(f"[CHAT DEBUG] Message {i}: role={msg['role']}, content_length={len(msg['content'])}")

        # Low temperature: answers are arithmetic over the user's real data, so
        # adherence and repeatability matter more than variety. Measured on the
        # emergency-fund eval: 0.2 followed all response rules 4/4 runs.
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.2,
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
            'envelope_accounts': len(context.get('envelope_accounts', [])),
            'recurring_expenses': len(context.get('recurring', {}).get('series', [])),
            'model_used': MODEL
        }

        return {
            'response': ai_response,
            'context_used': context_used,
            'error': None
        }

    except RateLimitError:
        # OpenAI throttling US — distinct from MoneyMind's own per-user
        # limits (ADVISOR_RATE_LIMIT / ADVISOR_DAILY_LIMIT in routes/chat.py)
        return {
            'response': None,
            'error': 'The advisor is handling a lot of requests right now. '
                     'Your message wasn\'t lost — try again in a minute.',
            'error_code': 'RATE_LIMIT'
        }

    except APITimeoutError:
        return {
            'response': None,
            'error': 'That answer took too long to compute. Try asking again — '
                     'shorter questions usually come back faster.',
            'error_code': 'TIMEOUT'
        }

    except APIConnectionError as e:
        return {
            'response': None,
            'error': 'The advisor couldn\'t be reached. Your data is fine — '
                     'try again shortly.',
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
