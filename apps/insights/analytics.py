"""Dashboard analytics, computed with aggregate queries and cached per user.

The cache key contains a per-user *version* that is bumped whenever one of the
user's transactions changes, so the dashboard is never stale and no key
scanning is needed. Uses Redis when configured, otherwise local memory.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.ledger.models import Category, Transaction

from .recurring import detect_recurring

CACHE_SECONDS = 60 * 10
MONTHS = 12


def _version_key(user_id: int) -> str:
    return f"insights:version:{user_id}"


def bump_version(user_id: int) -> None:
    try:
        cache.incr(_version_key(user_id))
    except ValueError:
        cache.set(_version_key(user_id), 2, timeout=None)


def dashboard(user, today: date | None = None) -> dict:
    today = today or timezone.localdate()
    version = cache.get_or_set(_version_key(user.pk), 1, timeout=None)
    key = f"insights:dashboard:{user.pk}:v{version}:{today.isoformat()}"
    return cache.get_or_set(key, lambda: _compute(user, today), CACHE_SECONDS)


def _spending(qs):
    """Exclude transfers: moving money between accounts is neither income nor spending."""
    return qs.exclude(category__kind=Category.Kind.TRANSFER)


def _compute(user, today: date) -> dict:
    transactions = _spending(Transaction.objects.filter(user=user))
    month_start = today.replace(day=1)
    window_start = month_start - relativedelta(months=MONTHS - 1)

    monthly = {
        row["month"]: row
        for row in transactions.filter(date__gte=window_start)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            income=Sum("amount", filter=Q(amount__gt=0)),
            expenses=Sum("amount", filter=Q(amount__lt=0)),
        )
    }
    cashflow = []
    for offset in range(MONTHS):
        month = window_start + relativedelta(months=offset)
        row = monthly.get(month, {})
        income = row.get("income") or Decimal("0")
        expenses = -(row.get("expenses") or Decimal("0"))
        cashflow.append(
            {"month": month.strftime("%b %Y"), "income": float(income), "expenses": float(expenses)}
        )

    this_month = transactions.filter(date__gte=month_start, date__lte=today)
    by_category = list(
        this_month.filter(amount__lt=0)
        .values("category__name", "category__color")
        .annotate(total=Sum("amount"))
        .order_by("total")
    )
    top_merchants = list(
        transactions.filter(date__gte=today - relativedelta(days=90), amount__lt=0)
        .values("merchant")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("total")[:5]
    )
    totals = this_month.aggregate(
        income=Sum("amount", filter=Q(amount__gt=0)),
        expenses=Sum("amount", filter=Q(amount__lt=0)),
    )
    income = totals["income"] or Decimal("0")
    expenses = -(totals["expenses"] or Decimal("0"))

    recurring = detect_recurring(
        transactions.filter(date__gte=today - relativedelta(months=13)).values_list(
            "merchant", "date", "amount"
        ),
        today=today,
    )

    return {
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
        "savings_rate": round(float((income - expenses) / income * 100), 1) if income else None,
        "uncategorized": Transaction.objects.filter(user=user, category__isnull=True).count(),
        "cashflow": cashflow,
        "categories": [
            {
                "name": row["category__name"] or "Uncategorized",
                "color": row["category__color"] or "#cbd5e1",
                "total": float(-row["total"]),
            }
            for row in by_category
        ],
        "top_merchants": [
            {"merchant": row["merchant"], "total": -row["total"], "count": row["count"]}
            for row in top_merchants
        ],
        "recurring": recurring,
        "recurring_monthly_total": sum((r.monthly_cost for r in recurring), Decimal("0")),
    }
