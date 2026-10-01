from datetime import date
from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse

from apps.budgets.models import Budget, BudgetAlert
from apps.budgets.services import send_due_alerts, statuses
from apps.ledger.tests.factories import AccountFactory, TransactionFactory, category

pytestmark = pytest.mark.django_db

SEPT = date(2026, 9, 15)


@pytest.fixture
def account():
    return AccountFactory()


@pytest.fixture
def user(account):
    return account.user


def spend(account, name, amount, day=SEPT):
    TransactionFactory(
        account=account,
        amount=Decimal(amount),
        date=day,
        category=category(account.user, name),
        categorized_by="user",
    )


def test_status_counts_only_this_months_outflows_in_category(user, account):
    Budget.objects.create(user=user, category=category(user, "Dining"), amount=Decimal("200"))
    spend(account, "Dining", "-50")
    spend(account, "Dining", "-30.50")
    spend(account, "Dining", "20")  # a refund is not spending
    spend(account, "Dining", "-99", day=date(2026, 8, 31))  # previous month
    spend(account, "Groceries", "-500")  # other category

    [status] = statuses(user, SEPT)

    assert status.spent == Decimal("80.50")
    assert status.percent == 40
    assert status.state == "ok"
    assert status.remaining == Decimal("119.50")


@pytest.mark.parametrize(
    ("spent", "state"), [("-79", "ok"), ("-80", "warning"), ("-120", "exceeded")]
)
def test_states(user, account, spent, state):
    Budget.objects.create(user=user, category=category(user, "Dining"), amount=Decimal("100"))
    spend(account, "Dining", spent)

    assert statuses(user, SEPT)[0].state == state


def test_alerts_are_sent_once_per_level_per_month(user, account):
    Budget.objects.create(user=user, category=category(user, "Dining"), amount=Decimal("100"))
    spend(account, "Dining", "-85")

    assert send_due_alerts(user, SEPT) == 1
    assert send_due_alerts(user, SEPT) == 0  # same level, same month

    spend(account, "Dining", "-30")
    assert send_due_alerts(user, SEPT) == 1  # escalated to exceeded

    assert [m.subject for m in mail.outbox] == [
        "85% of your Dining budget used",
        "You're over your Dining budget",
    ]
    assert BudgetAlert.objects.count() == 2


def test_overview_page(client, user, account):
    Budget.objects.create(user=user, category=category(user, "Dining"), amount=Decimal("100"))
    spend(account, "Dining", "-150", day=date.today())  # the page shows the current month
    client.force_login(user)

    content = client.get(reverse("budgets:overview")).content.decode()

    assert "progress__bar--over" in content
    assert "Over by" in content


def test_create_budget_only_for_own_expense_categories(client, user):
    client.force_login(user)

    salary = client.post(
        reverse("budgets:create"),
        {"category": category(user, "Salary").pk, "amount": "100", "warn_at_percent": 80},
    )
    ok = client.post(
        reverse("budgets:create"),
        {"category": category(user, "Travel").pk, "amount": "300", "warn_at_percent": 75},
    )

    assert "category" in salary.context["form"].errors
    assert ok.status_code == 302
    assert Budget.objects.get().category.name == "Travel"


def test_one_budget_per_category(client, user):
    Budget.objects.create(user=user, category=category(user, "Dining"), amount=Decimal("100"))
    client.force_login(user)

    response = client.post(
        reverse("budgets:create"),
        {"category": category(user, "Dining").pk, "amount": "50", "warn_at_percent": 80},
    )

    assert "category" in response.context["form"].errors


def test_budgets_are_private(client, user):
    other = AccountFactory().user
    budget = Budget.objects.create(user=other, category=category(other, "Dining"), amount=1)
    client.force_login(user)

    assert client.get(reverse("budgets:edit", args=[budget.pk])).status_code == 404
