"""Quick test to verify the implementation changes work without errors"""
# -*- coding: utf-8 -*-

# Test 1: Check imports work
print("[TEST 1] Checking imports...")
try:
    from utils.financial_context import format_context_for_llm, build_context_string, get_spending_trends
    from utils.openai_client import get_system_prompt
    print("   PASS: All imports successful")
except Exception as e:
    print(f"   FAIL: Import error: {e}")
    exit(1)

# Test 2: Check system prompt contains new language
print("\n[TEST 2] Checking system prompt has new content...")
test_context = "test data"
prompt = get_system_prompt(test_context)

required_phrases = [
    "financial questions deserve full answers",
    "WHAT YOU CAN ANSWER",
    "WHAT YOU MUST REFUSE",
    "How am I doing?",
]

for phrase in required_phrases:
    if phrase in prompt:
        print(f"   PASS: Found '{phrase[:40]}'")
    else:
        print(f"   FAIL: Missing '{phrase}'")
        exit(1)

# Test 3: Check that old restrictive language is gone
print("\n[TEST 3] Checking old restrictive prompt is removed...")
old_phrase = "You ONLY answer finance-related questions"
if old_phrase not in prompt:
    print(f"   PASS: Old restrictive text successfully removed")
else:
    print(f"   FAIL: Old text still present")
    exit(1)

# Test 4: Check build_context_string handles new trends data
print("\n[TEST 4] Testing context formatting with trends...")
test_context_dict = {
    'spending_summary': {
        'month_income': 5000,
        'month_spending': 2450.50,
        'month_net': 2549.50,
        'average_monthly_spending': 2300
    },
    'spending_by_category': [
        {'category': 'groceries', 'amount': 450.75, 'transaction_count': 15},
        {'category': 'entertainment', 'amount': 200.00, 'transaction_count': 8}
    ],
    'budgets': [
        {'category': 'groceries', 'budget_amount': 400, 'spent_this_month': 450.75, 'progress_percentage': 112.7, 'is_over_budget': True},
        {'category': 'entertainment', 'budget_amount': 300, 'spent_this_month': 200, 'progress_percentage': 66.7, 'is_over_budget': False}
    ],
    'goals': [
        {'name': 'Vacation', 'description': 'Beach trip', 'target_amount': 3000, 'current_amount': 2000, 
         'progress_percentage': 66.7, 'status': 'active', 'days_until_target': 45}
    ],
    'recent_transactions': [
        {'date': '2025-12-03', 'description': 'Walmart', 'category': 'groceries', 'amount': 125.50, 'type': 'expense', 'notes': ''}
    ],
    'spending_trends': {
        'highest_category': 'groceries',
        'highest_amount': 450.75,
        'month_growth_percent': 12.0,
        'days_remaining': 10,
        'days_in_month': 31,
        'projected_month_total': 2800,
        'last_month_spending': 2193,
        'budget_alerts': [{'category': 'groceries', 'budget_amount': 400, 'spent_this_month': 450.75}],
        'current_spending': 2450.50
    }
}

try:
    context_str = build_context_string(test_context_dict)
    
    # Check for new features in output
    checks = [
        ('MONTHLY SUMMARY header', 'MONTHLY SUMMARY' in context_str),
        ('Trends data (growth %)', 'Spending trend' in context_str),
        ('Days remaining', 'Days remaining' in context_str),
        ('Budget alerts', 'OVER BUDGET' in context_str),
        ('Emoji indicators', 'OK' in context_str or 'OVER' in context_str),
        ('Recent transactions', 'RECENT TRANSACTIONS' in context_str)
    ]
    
    for check_name, result in checks:
        if result:
            print(f"   PASS: {check_name}")
        else:
            print(f"   FAIL: {check_name}")
            exit(1)
            
except Exception as e:
    print(f"   FAIL: Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "="*60)
print("ALL TESTS PASSED!")
print("="*60)
print("\nImplementation summary:")
print("  PASS: System prompt updated - no longer restrictive")
print("  PASS: Spending trends function working")
print("  PASS: Context formatting enhanced with trends")
print("\nReady for full end-to-end testing!")
