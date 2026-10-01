"""Recurring-payment detection (subscriptions, rent, bills).

A merchant is considered recurring when, among its outflows:

* there are at least ``MIN_OCCURRENCES`` payments,
* the gaps between consecutive payments are regular: their median falls in a
  known cadence window (weekly, monthly, yearly) and most gaps are close to it,
* the amounts are stable: coefficient of variation below ``MAX_AMOUNT_CV``
  (allows small price changes, rejects random shopping at the same store).

The detector is a pure function over plain tuples, which keeps it fast and easy
to unit-test.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, median, pstdev

MIN_OCCURRENCES = 3
MAX_AMOUNT_CV = 0.15
GAP_TOLERANCE_DAYS = 4

CADENCES = {
    "weekly": (6, 8),
    "monthly": (26, 35),
    "yearly": (355, 375),
}
MONTHLY_FACTOR = {"weekly": 52 / 12, "monthly": 1, "yearly": 1 / 12}


@dataclass(frozen=True)
class RecurringPayment:
    merchant: str
    cadence: str
    average_amount: Decimal
    occurrences: int
    last_date: date
    next_date: date

    @property
    def interval_label(self) -> str:
        return {"weekly": "Week", "monthly": "Month", "yearly": "Year"}[self.cadence]

    @property
    def monthly_cost(self) -> Decimal:
        return (self.average_amount * Decimal(str(MONTHLY_FACTOR[self.cadence]))).quantize(
            Decimal("0.01")
        )


def _cadence(gap_days: float) -> str | None:
    for name, (low, high) in CADENCES.items():
        if low <= gap_days <= high:
            return name
    return None


def detect_recurring(rows, today: date | None = None) -> list[RecurringPayment]:
    """Detect recurring outflows in ``(merchant, date, amount)`` rows (outflows are negative)."""
    by_merchant: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for merchant, day, amount in rows:
        if merchant and amount < 0:
            by_merchant[merchant].append((day, -amount))

    found = []
    for merchant, payments in by_merchant.items():
        if len(payments) < MIN_OCCURRENCES:
            continue
        payments.sort()
        dates = [d for d, _ in payments]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False) if (b - a).days > 0]
        if len(gaps) < MIN_OCCURRENCES - 1:
            continue
        typical_gap = median(gaps)
        cadence = _cadence(typical_gap)
        if cadence is None:
            continue
        regular = sum(abs(gap - typical_gap) <= GAP_TOLERANCE_DAYS for gap in gaps)
        if regular / len(gaps) < 0.75:
            continue

        amounts = [float(a) for _, a in payments]
        average = mean(amounts)
        if average == 0 or pstdev(amounts) / average > MAX_AMOUNT_CV:
            continue

        next_date = dates[-1] + timedelta(days=round(typical_gap))
        if today and next_date < today - timedelta(days=typical_gap):
            continue  # stopped a while ago (e.g. cancelled subscription)
        found.append(
            RecurringPayment(
                merchant=merchant,
                cadence=cadence,
                average_amount=Decimal(str(round(average, 2))),
                occurrences=len(payments),
                last_date=dates[-1],
                next_date=next_date,
            )
        )
    return sorted(found, key=lambda r: r.monthly_cost, reverse=True)
