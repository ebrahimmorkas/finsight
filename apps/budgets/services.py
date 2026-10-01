from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone

from apps.ledger.models import Transaction

from .models import Budget, BudgetAlert


def month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    return start, start + relativedelta(months=1)


@dataclass(frozen=True)
class BudgetStatus:
    budget: Budget
    spent: Decimal
    percent: int
    state: str  # "ok" | "warning" | "exceeded"

    @property
    def remaining(self) -> Decimal:
        return max(self.budget.amount - self.spent, Decimal("0"))

    @property
    def overspend(self) -> Decimal:
        return max(self.spent - self.budget.amount, Decimal("0"))


def statuses(user, day: date | None = None) -> list[BudgetStatus]:
    """Spending against every budget for the month containing ``day`` (one query)."""
    start, end = month_bounds(day or timezone.localdate())
    budgets = list(Budget.objects.filter(user=user).select_related("category"))
    spent_by_category = dict(
        Transaction.objects.filter(
            user=user,
            category__in=[b.category_id for b in budgets],
            date__gte=start,
            date__lt=end,
            amount__lt=0,
        )
        .values_list("category")
        .annotate(total=Sum("amount"))
    )
    result = []
    for budget in budgets:
        spent = -(spent_by_category.get(budget.category_id) or Decimal("0"))
        percent = int(spent * 100 / budget.amount)
        if percent >= 100:
            state = "exceeded"
        elif percent >= budget.warn_at_percent:
            state = "warning"
        else:
            state = "ok"
        result.append(BudgetStatus(budget, spent, percent, state))
    return result


def send_due_alerts(user, day: date | None = None) -> int:
    """Email the user about budgets that crossed a threshold, once per level per month."""
    day = day or timezone.localdate()
    month_start, _ = month_bounds(day)
    sent = 0
    for status in statuses(user, day):
        if status.state == "ok":
            continue
        try:
            with transaction.atomic():
                BudgetAlert.objects.create(
                    budget=status.budget, month=month_start, level=status.state
                )
        except IntegrityError:
            continue  # this level was already reported this month
        body = render_to_string("budgets/alert_email.txt", {"status": status, "user": user})
        subject = (
            f"You're over your {status.budget.category.name} budget"
            if status.state == "exceeded"
            else f"{status.percent}% of your {status.budget.category.name} budget used"
        )
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
        sent += 1
    return sent
