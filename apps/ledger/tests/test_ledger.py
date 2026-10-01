from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.ledger.merchants import normalize_merchant
from apps.ledger.models import DEFAULT_CATEGORIES, Category, Transaction
from apps.ledger.tests.factories import AccountFactory, TransactionFactory, category

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AMZN Mktp US*2K4L19XR3 Amzn.com/bill WA", "AMZN MKTP US AMZN"),
        ("STARBUCKS STORE #12345 SEATTLE WA", "STARBUCKS STORE SEATTLE"),
        ("POS DEBIT 0412 NETFLIX.COM 866-579-7172 CA", "NETFLIX"),
        ("UBER *TRIP HELP.UBER.COM", "UBER"),
    ],
)
def test_normalize_merchant(raw, expected):
    assert normalize_merchant(raw) == expected


def test_new_users_get_default_categories(user):
    assert Category.objects.filter(user=user).count() == len(DEFAULT_CATEGORIES)


def test_merchant_is_set_on_save():
    txn = TransactionFactory(description="SPOTIFY P1A2B3C4D5 STOCKHOLM SE")

    assert txn.merchant == "SPOTIFY P1A2B3C4D5 STOCKHOLM"


def test_account_balance():
    account = AccountFactory(opening_balance=Decimal("100"))
    TransactionFactory(account=account, amount=Decimal("-30.25"))
    TransactionFactory(account=account, amount=Decimal("50"))

    assert account.balance == Decimal("119.75")


def test_account_list_shows_balances(auth_client, user):
    account = AccountFactory(user=user, name="Main", opening_balance=Decimal("10"))
    TransactionFactory(account=account, amount=Decimal("-2.5"))

    content = auth_client.get(reverse("ledger:accounts")).content.decode()

    assert "7.50 USD" in content


def test_transactions_are_private(auth_client, user):
    TransactionFactory(account=AccountFactory(user=user), description="MINE")
    TransactionFactory(description="SOMEONE ELSES")

    content = auth_client.get(reverse("ledger:transactions")).content.decode()

    assert "MINE" in content and "SOMEONE ELSES" not in content


def test_filter_by_search_direction_and_uncategorized(auth_client, user):
    account = AccountFactory(user=user)
    TransactionFactory(account=account, description="PAYROLL ACME", amount=Decimal("3000"))
    TransactionFactory(account=account, description="ACME CAFE", amount=Decimal("-5"))
    TransactionFactory(
        account=account,
        description="ACME STORE",
        amount=Decimal("-9"),
        category=category(user, "Shopping"),
    )

    response = auth_client.get(
        reverse("ledger:transactions"), {"q": "acme", "direction": "out", "uncategorized": "true"}
    )

    assert [t.description for t in response.context["transactions"]] == ["ACME CAFE"]


def test_create_transaction_with_category_marks_user_source(auth_client, user):
    account = AccountFactory(user=user)

    auth_client.post(
        reverse("ledger:transaction-create"),
        {
            "account": account.pk,
            "date": "2026-09-15",
            "description": "Farmers market",
            "amount": "-23.40",
            "category": category(user, "Groceries").pk,
        },
    )

    txn = Transaction.objects.get()
    assert txn.categorized_by == Transaction.Source.USER


def test_cannot_use_another_users_account(auth_client):
    foreign = AccountFactory()

    response = auth_client.post(
        reverse("ledger:transaction-create"),
        {"account": foreign.pk, "date": "2026-09-15", "description": "x", "amount": "-1"},
    )

    assert "account" in response.context["form"].errors
    assert not Transaction.objects.exists()


def test_inline_category_change_via_htmx(auth_client, user):
    txn = TransactionFactory(account=AccountFactory(user=user))
    dining = category(user, "Dining")

    response = auth_client.post(
        reverse("ledger:set-category", args=[txn.pk]),
        {"category": dining.pk},
        headers={"HX-Request": "true"},
    )

    txn.refresh_from_db()
    assert response.status_code == 200
    assert f'id="txn-{txn.pk}"' in response.content.decode()
    assert (txn.category, txn.categorized_by) == (dining, "user")


def test_cannot_categorize_with_foreign_category(auth_client, user):
    txn = TransactionFactory(account=AccountFactory(user=user))
    foreign = category(UserFactory(), "Dining")

    response = auth_client.post(
        reverse("ledger:set-category", args=[txn.pk]), {"category": foreign.pk}
    )

    assert response.status_code == 404


def test_duplicate_account_name_rejected(auth_client, user):
    AccountFactory(user=user, name="Main")

    response = auth_client.post(
        reverse("ledger:account-create"),
        {"name": "main", "kind": "checking", "currency": "USD", "opening_balance": "0"},
    )

    assert "name" in response.context["form"].errors


def test_unticked_uncategorized_filter_keeps_uncategorized_rows(auth_client, user):
    account = AccountFactory(user=user)
    TransactionFactory(account=account, description="NO CATEGORY", amount=Decimal("-5"))

    response = auth_client.get(reverse("ledger:transactions"), {"direction": "out"})

    assert [t.description for t in response.context["transactions"]] == ["NO CATEGORY"]
