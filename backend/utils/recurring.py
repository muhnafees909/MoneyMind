"""Recurring-expense detection: merchant + amount clustering over the
transaction history, cadence inference from occurrence intervals, and
attachment of new charges to known series."""
import re
import difflib
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

# --- Matching new transactions to an existing series (priority ladder) ---
# Used when attaching future charges to a known series (esp. user-created ones
# seeded from history). Tuned separately from the looser clustering tolerance.
#   1. merchant_entity_id  (Plaid's stable id — most reliable)
#   2. exact normalized merchant name
#   3. amount + date-window   (for bills whose description text changes)
#   4. fuzzy name + amount + date-window   (last resort)
MATCH_DATE_WINDOW_DAYS = 5              # +/- window around a projected due date
MATCH_AMOUNT_TOLERANCE = Decimal('0.02')  # near-exact amount for the fallback checks
FUZZY_NAME_THRESHOLD = 0.82            # normalized-name similarity for last resort

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


def _amount_within(amount, expected, tolerance) -> bool:
    """True if amount is within `tolerance` (fraction) of expected."""
    expected = Decimal(expected)
    if expected <= 0:
        return False
    return abs(Decimal(amount) - expected) / expected <= tolerance


def _schedule_anchor(series):
    """A date to project the recurring schedule from: the next expected date,
    else the last occurrence rolled forward one cadence."""
    if series.next_expected_date:
        return series.next_expected_date
    if series.occurrences:
        last = max(o.occurred_at for o in series.occurrences)
        return last + timedelta(days=cadence_nominal_days(series.cadence))
    return None


def _within_schedule(series, txn_date) -> bool:
    """True if txn_date lands within MATCH_DATE_WINDOW_DAYS of any projected
    occurrence (anchor + k*cadence), so a bill that skipped a month still matches."""
    anchor = _schedule_anchor(series)
    if anchor is None:
        return False
    step = cadence_nominal_days(series.cadence)
    k = round((txn_date - anchor).days / step)
    projected = anchor + timedelta(days=k * step)
    return abs((txn_date - projected).days) <= MATCH_DATE_WINDOW_DAYS


def _match_priority(series, txn) -> int:
    """How strongly a transaction matches an existing series. Higher wins;
    0 = no match. See the priority ladder documented at the top of the module."""
    amount = Decimal(txn.amount)
    key = normalize_merchant(txn.description)
    txn_date = txn.transaction_date.date()

    # 1. Plaid merchant entity id — most reliable
    if series.merchant_entity_id and txn.merchant_entity_id \
            and series.merchant_entity_id == txn.merchant_entity_id \
            and _amount_within(amount, series.expected_amount, AMOUNT_TOLERANCE):
        return 4
    # 2. Exact normalized merchant name (digits/punctuation already stripped)
    if key and key == series.merchant_key \
            and _amount_within(amount, series.expected_amount, AMOUNT_TOLERANCE):
        return 3
    # 3. Amount + date-window (bills whose description text varies month to month)
    if _amount_within(amount, series.expected_amount, MATCH_AMOUNT_TOLERANCE) \
            and _within_schedule(series, txn_date):
        return 2
    # 4. Fuzzy name + amount + date-window (last resort)
    if series.merchant_key and key \
            and difflib.SequenceMatcher(None, key, series.merchant_key).ratio() >= FUZZY_NAME_THRESHOLD \
            and _amount_within(amount, series.expected_amount, MATCH_AMOUNT_TOLERANCE) \
            and _within_schedule(series, txn_date):
        return 1
    return 0


def _attach_by_priority(user_id, expenses, linked_ids) -> int:
    """Pass A: attach still-unlinked charges to an existing *active* series using
    the priority ladder (entity id > exact name > amount+date-window > fuzzy).
    Runs before clustering so a manual/seeded series claims its charges instead
    of a duplicate candidate being created. Returns count attached."""
    active_series = RecurringExpense.query.filter_by(
        user_id=user_id, status='active').all()
    if not active_series:
        return 0

    attached = 0
    unlinked = sorted((t for t in expenses if t.id not in linked_ids),
                      key=lambda t: t.transaction_date)
    for txn in unlinked:
        best, best_priority = None, 0
        for series in active_series:
            priority = _match_priority(series, txn)
            if priority > best_priority:
                best, best_priority = series, priority
        if best is not None:
            _attach_occurrences(best, [txn])  # rolls next_expected_date forward
            linked_ids.add(txn.id)
            attached += 1
    return attached


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

    # Pass A: attach charges to existing active series via the priority ladder.
    new_occurrences = _attach_by_priority(user_id, expenses, linked_ids)

    # Pass B: cluster the remainder to auto-detect brand-new series.
    groups = {}
    for txn in expenses:
        key = normalize_merchant(txn.description)
        if key:
            groups.setdefault(key, []).append(txn)

    new_candidates = 0

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
