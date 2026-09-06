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


# ---------------------------------------------------------------------------
# DB-backed category resolution (system defaults + a user's custom categories).
# These are the source of truth once the categories table exists; the dicts
# above remain as a safe fallback for any value not found in the table.
# ---------------------------------------------------------------------------

def get_user_categories(user_id, include_archived=False):
    """All categories visible to a user: system defaults + their own custom
    ones. Returns a list of Category models."""
    from models.category import Category
    query = Category.query.filter(
        (Category.user_id.is_(None)) | (Category.user_id == int(user_id))
    )
    if not include_archived:
        query = query.filter(Category.archived.is_(False))
    # System first, then custom; alphabetical-ish by name within each
    return query.order_by(Category.user_id.isnot(None), Category.name.asc()).all()


def category_lookup(user_id):
    """value -> {'display_name', 'color', 'icon'} for a user (defaults + custom).
    Used to resolve names/colors for analytics and the advisor in one query."""
    lookup = {}
    for cat in get_user_categories(user_id, include_archived=True):
        lookup[cat.value] = {
            'display_name': cat.name,
            'color': cat.color,
            'icon': cat.icon,
        }
    return lookup


def display_name_from(value, lookup):
    """Resolve a category value to its display name using a prebuilt lookup,
    falling back to the static dict / title-cased value for unknowns."""
    if not value:
        return 'Uncategorized'
    if lookup and value in lookup:
        return lookup[value]['display_name']
    return get_category_display_name(value)


def color_from(value, lookup):
    if lookup and value in lookup:
        return lookup[value]['color']
    return get_category_color(value)


def resolve_category(user_id, raw):
    """Resolve a category value submitted by a client to the value to store.

    A value the user can actually assign — a system default or one of their own
    custom categories — is authoritative and taken as-is. Only values that are
    NOT assignable fall through to the legacy lowercase mapping.

    That ordering matters: `normalize_legacy_category` maps a handful of old
    lowercase names onto Plaid primaries ('groceries' -> FOOD_AND_DRINK), and a
    custom category whose slug collides with one of those keys (a category named
    "Groceries" slugifies to GROCERIES) used to be silently rewritten to the
    mapped system category. The write then looked like a no-op: the API answered
    200 and flipped category_source to 'manual', but the category never changed.

    Returns (value, None) when assignable, else (None, error message).
    """
    value = raw.strip() if isinstance(raw, str) else raw
    if value and is_valid_category(user_id, value):
        return value, None
    # Unrecognised (or empty) — fall back to the legacy migration mapping.
    normalized = normalize_legacy_category(value)
    if is_valid_category(user_id, normalized):
        return normalized, None
    return None, 'Unknown category.'


def is_valid_category(user_id, value):
    """True if `value` is a category the user may assign (system or their own,
    not archived)."""
    if not value:
        return False
    from models.category import Category
    return Category.query.filter(
        Category.value == value,
        Category.archived.is_(False),
        (Category.user_id.is_(None)) | (Category.user_id == int(user_id))
    ).first() is not None


