"""
Category mapping utility for Plaid transaction categories.
Maps Plaid's primary categories to user-friendly names and colors.
"""

# Plaid category to user-friendly display name
CATEGORY_DISPLAY_NAMES = {
    'INCOME': 'Income',
    'TRANSFER_IN': 'Transfer In',
    'TRANSFER_OUT': 'Transfer Out',
    'LOAN_PAYMENTS': 'Loan Payments',
    'BANK_FEES': 'Bank Fees',
    'ENTERTAINMENT': 'Entertainment',
    'FOOD_AND_DRINK': 'Food & Drink',
    'GENERAL_MERCHANDISE': 'Shopping',
    'HOME_IMPROVEMENT': 'Home Improvement',
    'MEDICAL': 'Healthcare',
    'PERSONAL_CARE': 'Personal Care',
    'GENERAL_SERVICES': 'Services',
    'GOVERNMENT_AND_NON_PROFIT': 'Government & Non-Profit',
    'TRANSPORTATION': 'Transportation',
    'TRAVEL': 'Travel',
    'RENT_AND_UTILITIES': 'Rent & Utilities'
}

# Plaid category -> chart color. Mirrors the frontend's shared palette
# (frontend/src/app/shared/category-colors.ts) — the vivid "gallery" tuning
# of the heritage family. Keep the two in sync.
CATEGORY_COLORS = {
    'INCOME': '#27b9de',                    # petrol
    'TRANSFER_IN': '#6c9de6',               # cornflower
    'TRANSFER_OUT': '#b189e0',              # mauve
    'LOAN_PAYMENTS': '#8f93ea',             # indigo
    'BANK_FEES': '#8f93ea',                 # indigo
    'ENTERTAINMENT': '#b189e0',             # mauve
    'FOOD_AND_DRINK': '#e27c4e',            # terracotta
    'GENERAL_MERCHANDISE': '#e07b9f',       # rose
    'HOME_IMPROVEMENT': '#a9bf49',          # olive
    'MEDICAL': '#a9bf49',                   # olive
    'PERSONAL_CARE': '#e07b9f',             # rose
    'GENERAL_SERVICES': '#e27c4e',          # terracotta
    'GOVERNMENT_AND_NON_PROFIT': '#dba43e', # ochre
    'TRANSPORTATION': '#dba43e',            # ochre
    'TRAVEL': '#27b9de',                    # petrol
    'RENT_AND_UTILITIES': '#6c9de6'         # cornflower
}

# Legacy lowercase to Plaid uppercase mapping
LEGACY_CATEGORY_MAPPING = {
    'groceries': 'FOOD_AND_DRINK',
    'dining': 'FOOD_AND_DRINK',
    'transportation': 'TRANSPORTATION',
    'utilities': 'RENT_AND_UTILITIES',
    'entertainment': 'ENTERTAINMENT',
    'shopping': 'GENERAL_MERCHANDISE',
    'healthcare': 'MEDICAL',
    'travel': 'TRAVEL',
    'education': 'GENERAL_SERVICES',
    'other': 'GENERAL_SERVICES'
}


def get_category_display_name(plaid_category):
    """
    Get user-friendly display name from Plaid category.

    Args:
        plaid_category (str): Plaid category string (e.g., 'FOOD_AND_DRINK')

    Returns:
        str: User-friendly display name (e.g., 'Food & Drink')
             Returns formatted category if not found in mapping
    """
    if not plaid_category:
        return 'Other'

    category_upper = plaid_category.upper()
    return CATEGORY_DISPLAY_NAMES.get(category_upper, plaid_category.replace('_', ' ').title())


def get_category_color(plaid_category):
    """
    Get color hex code from Plaid category.

    Args:
        plaid_category (str): Plaid category string (e.g., 'FOOD_AND_DRINK')

    Returns:
        str: Hex color code (e.g., '#fb923c')
             Returns gray default if not found in mapping
    """
    if not plaid_category:
        return '#6b7280'  # Gray default

    category_upper = plaid_category.upper()
    return CATEGORY_COLORS.get(category_upper, '#6b7280')


def normalize_legacy_category(legacy_category):
    """
    Convert old lowercase categories to Plaid format.

    Args:
        legacy_category (str): Old category format (e.g., 'groceries', 'dining')

    Returns:
        str: Plaid category format (e.g., 'FOOD_AND_DRINK')
    """
    if not legacy_category:
        return 'GENERAL_SERVICES'

    lower = legacy_category.lower()
    return LEGACY_CATEGORY_MAPPING.get(lower, legacy_category.upper())


def get_all_categories():
    """
    Get list of all supported categories with metadata.

    Returns:
        list: List of dictionaries containing value, display_name, and color
    """
    return [
        {
            'value': cat,
            'display_name': CATEGORY_DISPLAY_NAMES[cat],
            'color': CATEGORY_COLORS[cat]
        }
        for cat in CATEGORY_DISPLAY_NAMES.keys()
    ]


