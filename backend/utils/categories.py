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

# Plaid category to muted dark-theme color (no bright colors)
CATEGORY_COLORS = {
    'INCOME': '#4ade80',          # Muted green
    'TRANSFER_IN': '#60a5fa',     # Muted blue
    'TRANSFER_OUT': '#818cf8',    # Muted indigo
    'LOAN_PAYMENTS': '#f87171',   # Muted red
    'BANK_FEES': '#ef4444',       # Darker red
    'ENTERTAINMENT': '#c084fc',   # Muted purple
    'FOOD_AND_DRINK': '#fb923c',  # Muted orange
    'GENERAL_MERCHANDISE': '#f472b6', # Muted pink
    'HOME_IMPROVEMENT': '#a78bfa', # Muted violet
    'MEDICAL': '#2dd4bf',         # Muted teal
    'PERSONAL_CARE': '#fca5a5',   # Muted coral
    'GENERAL_SERVICES': '#22d3ee', # Muted cyan
    'GOVERNMENT_AND_NON_PROFIT': '#94a3b8', # Muted slate
    'TRANSPORTATION': '#fbbf24',  # Muted amber
    'TRAVEL': '#34d399',          # Muted emerald
    'RENT_AND_UTILITIES': '#38bdf8' # Muted sky blue
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
