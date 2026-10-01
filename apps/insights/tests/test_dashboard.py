from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.categorization import services as categorization
from apps.insights.analytics import dashboard
from apps.ledger.tests.factories import AccountFactory, TransactionFactory, category

pytestmark = pytest.mark.django_db

TODAY = date(2026, 9, 20)


@pytest.fixture
def account():
    return AccountFactory()


@pytest.fixture
def user(account):
    return account.user


def add(account, description, amount, day=TODAY, category_name=None):
    return TransactionFactory(
        account=account,
        description=description,
        amount=Decimal(amount),
        date=day,
        category=category(account.user, category_name) if category_name else None,
    )


def test_totals_exclude_transfers_and_compute_savings_rate(user, account):
    add(account, "PAYROLL", "4000", category_name="Salary")
    add(account, "RENT", "-1500", category_name="Rent & Housing")
    add(account, "TESCO", "-500", category_name="Groceries")
    add(account, "TO SAVINGS", "-1000", category_name="Transfers")

    data = dashboard(user, TODAY)

    assert (data["income"], data["expenses"], data["net"]) == (
        Decimal("4000"),
        Decimal("2000"),
        Decimal("2000"),
    )
    assert data["savings_rate"] == 50.0


def test_cashflow_has_12_months_and_category_breakdown(user, account):
    add(account, "TESCO", "-80", category_name="Groceries")
    add(account, "TESCO", "-20", category_name="Groceries")
    add(account, "SHELL", "-50", day=date(2026, 7, 2), category_name="Transport")

    data = dashboard(user, TODAY)

    assert len(data["cashflow"]) == 12
    assert data["cashflow"][-1] == {"month": "Sep 2026", "income": 0.0, "expenses": 100.0}
    assert data["cashflow"][-3]["expenses"] == 50.0
    assert data["categories"] == [{"name": "Groceries", "color": "#16a34a", "total": 100.0}]


def test_recurring_payments_are_detected(user, account):
    for i in range(4):
        add(account, "NETFLIX.COM", "-15.99", day=TODAY - timedelta(days=30 * i))

    data = dashboard(user, TODAY)

    assert [r.merchant for r in data["recurring"]] == ["NETFLIX"]
    assert data["recurring_monthly_total"] == Decimal("15.99")


def test_cache_is_invalidated_by_new_transactions(user, account):
    add(account, "TESCO", "-10")
    assert dashboard(user, TODAY)["expenses"] == Decimal("10")

    add(account, "TESCO", "-5")

    assert dashboard(user, TODAY)["expenses"] == Decimal("15")


def test_cache_is_invalidated_by_bulk_categorization(user, account):
    add(account, "NETFLIX.COM 866-579-7172", "-15.99")
    assert dashboard(user, TODAY)["uncategorized"] == 1

    categorization.categorize_uncategorized(user)

    assert dashboard(user, TODAY)["uncategorized"] == 0


def test_dashboard_page_and_home_redirect(client, user, account):
    add(account, "TESCO", "-10", day=date.today(), category_name="Groceries")
    client.force_login(user)

    assert client.get(reverse("home")).url == reverse("insights:dashboard")
    response = client.get(reverse("insights:dashboard"))
    assert response.status_code == 200
    assert b'id="chart-data"' in response.content


def test_dashboard_requires_login(client):
    assert client.get(reverse("insights:dashboard")).status_code == 302
