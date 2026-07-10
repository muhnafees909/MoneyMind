"""Recurring-expense detection: merchant + amount clustering over the
transaction history, cadence inference from occurrence intervals, and
attachment of new charges to known series."""
import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from statistics import median
from models.user import db
from models.transaction import Transaction
from models.recurring import RecurringExpense, RecurringExpenseOccurrence

# A charge joins an amount cluster if it's within this fraction of the cluster mean
AMOUNT_TOLERANCE = Decimal('0.15')

# Minimum charges before something is considered recurring
MIN_OCCURRENCES = 3

# (cadence, nominal gap in days, tolerance in days)
CADENCE_SPECS = (
    ('weekly', 7, 2),
    ('biweekly', 14, 3),
    ('monthly', 30, 6),
    ('annual', 365, 20),
)


def normalize_merchant(description: str) -> str:
    """Collapse variations like 'NETFLIX.COM *123' / 'Netflix' into one key."""
    key = re.sub(r'[^a-z]+', ' ', (description or '').lower())
    return re.sub(r'\s+', ' ', key).strip()


def infer_cadence(dates):
    """Given sorted occurrence dates, return a cadence name if the gaps are
    consistent with one of the known cadences, else None."""
    intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    if not intervals:
        return None
    mid = median(intervals)
    for cadence, nominal, tolerance in CADENCE_SPECS:
        if abs(mid - nominal) <= tolerance and \
                all(abs(gap - nominal) <= tolerance for gap in intervals):
            return cadence
    return None


def cadence_nominal_days(cadence: str) -> int:
    return {name: nominal for name, nominal, _ in CADENCE_SPECS}[cadence]


def _cluster_by_amount(transactions):
    """Split one merchant's charges into clusters of similar amounts, so a $15.49
    subscription isn't polluted by a $200 one-off at the same merchant."""
    clusters = []
    for txn in transactions:
        amount = Decimal(txn.amount)
        placed = False
        for cluster in clusters:
            mean = cluster['total'] / len(cluster['txns'])
            if mean > 0 and abs(amount - mean) / mean <= AMOUNT_TOLERANCE:
                cluster['txns'].append(txn)
                cluster['total'] += amount
                placed = True
                break
        if not placed:
            clusters.append({'txns': [txn], 'total': amount})
    return clusters


def _matching_series(user_id, merchant_key, mean_amount):
    """Existing series for this merchant with a similar amount, any status."""
    candidates = RecurringExpense.query.filter_by(
        user_id=user_id, merchant_key=merchant_key).all()
    for series in candidates:
        expected = Decimal(series.expected_amount)
        if expected > 0 and abs(mean_amount - expected) / expected <= AMOUNT_TOLERANCE:
            return series
    return None


def _attach_occurrences(series, transactions):
    """Add transactions (not yet linked anywhere) as occurrences of a series,
    then refresh expected_amount and next_expected_date."""
    added = 0
    for txn in sorted(transactions, key=lambda t: t.transaction_date):
        db.session.add(RecurringExpenseOccurrence(
            recurring_expense_id=series.id,
            transaction_id=txn.id,
            amount=Decimal(txn.amount),
            occurred_at=txn.transaction_date.date()
        ))
        added += 1
    db.session.flush()

    occurrences = sorted(series.occurrences, key=lambda o: o.occurred_at)
    amounts = [Decimal(o.amount) for o in occurrences]
    series.expected_amount = (sum(amounts) / len(amounts)).quantize(Decimal('0.01'))
    series.next_expected_date = occurrences[-1].occurred_at + \
        timedelta(days=cadence_nominal_days(series.cadence))
    return added


def detect_recurring(user_id: int) -> dict:
    """Scan the user's expense history for recurring charges.

    New candidates are created unconfirmed (review queue). Charges matching an
    existing active series are attached as new occurrences. Dismissed/cancelled
    series swallow their matches so they aren't re-flagged. Commits at the end.
    """
    linked_ids = {
        row.transaction_id
        for row in RecurringExpenseOccurrence.query.join(RecurringExpense)
        .filter(RecurringExpense.user_id == user_id).all()
    }

    expenses = Transaction.query.filter_by(
        user_id=user_id, transaction_type='expense'
    ).order_by(Transaction.transaction_date.asc()).all()

    groups = {}
    for txn in expenses:
        key = normalize_merchant(txn.description)
        if key:
            groups.setdefault(key, []).append(txn)

    new_candidates = 0
    new_occurrences = 0

    for merchant_key, txns in groups.items():
        for cluster in _cluster_by_amount(txns):
            cluster_txns = cluster['txns']
            mean_amount = cluster['total'] / len(cluster_txns)
            unlinked = [t for t in cluster_txns if t.id not in linked_ids]

            series = _matching_series(user_id, merchant_key, mean_amount)
            if series is not None:
                # Dismissed/cancelled series absorb matches silently
                if series.status == 'active' and unlinked:
                    new_occurrences += _attach_occurrences(series, unlinked)
                continue

            if len(cluster_txns) < MIN_OCCURRENCES or len(unlinked) != len(cluster_txns):
                continue

            dates = sorted(t.transaction_date.date() for t in cluster_txns)
            cadence = infer_cadence(dates)
            if cadence is None:
                continue

            category_counts = Counter(t.category for t in cluster_txns if t.category)
            latest = max(cluster_txns, key=lambda t: t.transaction_date)

            series = RecurringExpense(
                user_id=user_id,
                merchant_name=latest.description,
                merchant_key=merchant_key,
                category=category_counts.most_common(1)[0][0] if category_counts else None,
                expected_amount=mean_amount.quantize(Decimal('0.01')),
                cadence=cadence,
                status='active',
                confirmed_by_user=False
            )
            db.session.add(series)
            db.session.flush()
            _attach_occurrences(series, cluster_txns)
            new_candidates += 1

    db.session.commit()
    return {'new_candidates': new_candidates, 'new_occurrences': new_occurrences}
