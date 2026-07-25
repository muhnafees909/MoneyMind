"""
Category management: list categories (system defaults + the user's custom
ones), create a custom category, and delete a custom one (reassigning any
transactions/budgets/recurring that used it to Uncategorized).

System categories (user_id NULL) are shared and cannot be edited or deleted.
"""

import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import db
from models.category import Category, UNCATEGORIZED_VALUE
from models.transaction import Transaction
from models.budget import Budget
from models.recurring import RecurringExpense
from utils.categories import get_user_categories

categories_bp = Blueprint('categories', __name__)

MAX_NAME_LEN = 40
# Colors offered in the UI (the design system's category palette). Custom
# categories must pick one of these so they stay on-brand.
ALLOWED_COLORS = {
    '#6c9de6', '#dba43e', '#27b9de', '#e27c4e',
    '#b189e0', '#a9bf49', '#e07b9f', '#8f93ea', '#86817a',
}
# Curated lucide icon set for custom categories (kebab-case names the frontend
# knows how to render).
ALLOWED_ICONS = {
    'tag', 'utensils', 'coffee', 'shopping-bag', 'shopping-cart', 'car',
    'house', 'plane', 'heart-pulse', 'dumbbell', 'gift', 'graduation-cap',
    'baby', 'dog', 'gamepad-2', 'music', 'shirt', 'wrench', 'plug', 'wifi',
    'phone', 'book', 'briefcase', 'piggy-bank', 'credit-card', 'banknote',
    'sparkles', 'clapperboard', 'hammer', 'building-2', 'landmark', 'receipt',
    'circle-dashed',
}


def _slugify_value(name):
    """'Dining Out' -> 'DINING_OUT'. Used as the stable stored key."""
    slug = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_').upper()
    return slug or 'CATEGORY'


def _unique_value(user_id, base):
    """Ensure the value doesn't collide with a system default or one of the
    user's existing categories; append a counter if needed."""
    taken = {
        c.value for c in Category.query.filter(
            (Category.user_id.is_(None)) | (Category.user_id == int(user_id))
        ).all()
    }
    if base not in taken:
        return base
    n = 2
    while f'{base}_{n}' in taken:
        n += 1
    return f'{base}_{n}'


@categories_bp.route('', methods=['GET'])
@jwt_required()
def list_categories():
    """All categories the user can see and use: system defaults + their own."""
    user_id = get_jwt_identity()
    return jsonify([c.to_dict() for c in get_user_categories(user_id)]), 200


@categories_bp.route('', methods=['POST'])
@jwt_required()
def create_category():
    """Create a custom category. Body: {name, color, icon?}"""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Category name is required.'}), 400
    if len(name) > MAX_NAME_LEN:
        return jsonify({'error': f'Name must be {MAX_NAME_LEN} characters or fewer.'}), 400

    color = (data.get('color') or '').lower()
    if color not in ALLOWED_COLORS:
        return jsonify({'error': 'Pick a color from the palette.'}), 400

    icon = data.get('icon') or 'tag'
    if icon not in ALLOWED_ICONS:
        icon = 'tag'

    # Reject a duplicate display name within the user's visible set (case-insensitive)
    existing_names = {c.name.lower() for c in get_user_categories(user_id, include_archived=True)}
    if name.lower() in existing_names:
        return jsonify({'error': 'A category with that name already exists.'}), 400

    value = _unique_value(user_id, _slugify_value(name))
    category = Category(user_id=user_id, value=value, name=name, color=color, icon=icon)
    db.session.add(category)
    db.session.commit()
    return jsonify(category.to_dict()), 201


@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@jwt_required()
def delete_category(category_id):
    """Delete a custom category. Any transactions/budgets/recurring using it are
    reassigned to Uncategorized. System categories cannot be deleted."""
    user_id = int(get_jwt_identity())
    category = Category.query.filter_by(id=category_id).first()
    if not category:
        return jsonify({'error': 'Category not found.'}), 404
    if category.is_system:
        return jsonify({'error': 'Default categories cannot be deleted.'}), 400
    if category.user_id != user_id:
        return jsonify({'error': 'Category not found.'}), 404

    # Transactions and recurring series keep their history under Uncategorized.
    txn_count = Transaction.query.filter_by(
        user_id=user_id, category=category.value).update(
            {'category': UNCATEGORIZED_VALUE}, synchronize_session=False)
    rec_count = RecurringExpense.query.filter_by(
        user_id=user_id, category=category.value).update(
            {'category': UNCATEGORIZED_VALUE}, synchronize_session=False)
    # A budget is a limit for one category; once that category is gone the
    # limit is meaningless, so remove it (reassigning could also collide with
    # an existing Uncategorized budget — one budget per category is enforced).
    budget_count = Budget.query.filter_by(
        user_id=user_id, category=category.value).delete(synchronize_session=False)

    db.session.delete(category)
    db.session.commit()
    return jsonify({
        'deleted': category_id,
        'reassigned_transactions': txn_count,
        'reassigned_recurring': rec_count,
        'removed_budgets': budget_count,
    }), 200
