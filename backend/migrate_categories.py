"""
One-time migration script to normalize categories in database.
This script converts all legacy lowercase categories (groceries, dining, etc.)
to Plaid's uppercase format (FOOD_AND_DRINK, TRANSPORTATION, etc.)
"""
from models.user import db
from models.transaction import Transaction
from models.budget import Budget
from utils.categories import normalize_legacy_category


def migrate_categories():
    """Migrate all transactions and budgets to Plaid category format."""

    print("Starting category migration...")
    print("=" * 60)

    # Migrate transactions
    print("\nMigrating transactions...")
    transactions = Transaction.query.all()
    transaction_count = 0
    transaction_changes = {}

    for txn in transactions:
        if txn.category:
            old_category = txn.category
            new_category = normalize_legacy_category(txn.category)
            if old_category != new_category:
                txn.category = new_category
                transaction_count += 1
                # Track changes for reporting
                key = f"{old_category} -> {new_category}"
                transaction_changes[key] = transaction_changes.get(key, 0) + 1

    print(f"Updated {transaction_count} transactions")
    if transaction_changes:
        print("\nTransaction category changes:")
        for change, count in transaction_changes.items():
            print(f"  {change}: {count} records")

    # Migrate budgets (with duplicate handling)
    print("\nMigrating budgets...")
    budgets = Budget.query.all()
    budget_count = 0
    budget_changes = {}
    budgets_to_delete = []

    # Group budgets by user and new category
    budget_groups = {}
    for budget in budgets:
        if budget.category:
            old_category = budget.category
            new_category = normalize_legacy_category(budget.category)
            key = (budget.user_id, new_category)

            if key not in budget_groups:
                budget_groups[key] = []
            budget_groups[key].append((budget, old_category, new_category))

    # Process each group - keep the one with highest amount, delete others
    for (user_id, new_category), group in budget_groups.items():
        if len(group) > 1:
            # Multiple budgets mapping to same category - merge them
            print(f"\n  Merging {len(group)} budgets for user {user_id} category {new_category}:")
            # Sort by amount descending, keep the first (largest)
            group.sort(key=lambda x: x[0].amount, reverse=True)
            keep_budget, keep_old, _ = group[0]
            keep_budget.category = new_category
            print(f"    Keeping: {keep_old} (${keep_budget.amount}) -> {new_category}")

            # Mark others for deletion
            for budget, old_cat, new_cat in group[1:]:
                print(f"    Deleting: {old_cat} (${budget.amount})")
                budgets_to_delete.append(budget)
                key = f"{old_cat} -> MERGED_INTO_{new_category}"
                budget_changes[key] = budget_changes.get(key, 0) + 1

            budget_count += 1
            key = f"{keep_old} -> {new_category}"
            budget_changes[key] = budget_changes.get(key, 0) + 1
        else:
            # Single budget - just update category if needed
            budget, old_category, new_category = group[0]
            if old_category != new_category:
                budget.category = new_category
                budget_count += 1
                key = f"{old_category} -> {new_category}"
                budget_changes[key] = budget_changes.get(key, 0) + 1

    # Delete duplicate budgets
    for budget in budgets_to_delete:
        db.session.delete(budget)

    print(f"\nUpdated {budget_count} budgets")
    print(f"Deleted {len(budgets_to_delete)} duplicate budgets")
    if budget_changes:
        print("\nBudget category changes:")
        for change, count in budget_changes.items():
            print(f"  {change}: {count} records")

    # Commit all changes
    print("\n" + "=" * 60)
    print("Committing changes to database...")
    db.session.commit()
    print("Migration complete!")
    print(f"\nTotal records updated:")
    print(f"  Transactions: {transaction_count}")
    print(f"  Budgets: {budget_count}")
    print(f"  Total: {transaction_count + budget_count}")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        migrate_categories()
