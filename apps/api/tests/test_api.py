from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.ledger.models import Transaction
from apps.ledger.tests.factories import AccountFactory, TransactionFactory, category

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def api(user):
    client = APIClient()
    token = client.post(
        reverse("api:token"), {"username": user.email, "password": DEFAULT_PASSWORD}
    ).json()["token"]
    client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    return client


def test_requires_authentication():
    assert APIClient().get(reverse("api:transaction-list")).status_code == 401


def test_account_crud_with_balance(api, user):
    created = api.post(
        reverse("api:account-list"),
        {"name": "Joint", "kind": "checking", "currency": "EUR", "opening_balance": "100.00"},
        format="json",
    ).json()
    TransactionFactory(account_id=created["id"], user=user, amount=Decimal("-30"))

    detail = api.get(reverse("api:account-detail", args=[created["id"]])).json()

    assert detail["balance"] == "70.00"


def test_new_transaction_is_auto_categorized(api, user):
    account = AccountFactory(user=user)

    response = api.post(
        reverse("api:transaction-list"),
        {
            "account": account.pk,
            "date": "2026-09-01",
            "description": "NETFLIX.COM",
            "amount": "-15.99",
        },
        format="json",
    )

    body = response.json()
    assert response.status_code == 201
    assert body["merchant"] == "NETFLIX"
    assert (body["category_name"], body["categorized_by"]) == ("Subscriptions", "ml")


def test_transaction_with_explicit_category_is_user_labelled(api, user):
    account = AccountFactory(user=user)

    body = api.post(
        reverse("api:transaction-list"),
        {
            "account": account.pk,
            "date": "2026-09-01",
            "description": "Gift",
            "amount": "-40",
            "category": category(user, "Shopping").pk,
        },
        format="json",
    ).json()

    assert body["categorized_by"] == "user"


def test_cannot_reference_another_users_account_or_category(api, user):
    response = api.post(
        reverse("api:transaction-list"),
        {
            "account": AccountFactory().pk,
            "date": "2026-09-01",
            "description": "x",
            "amount": "-1",
            "category": category(UserFactory(), "Dining").pk,
        },
        format="json",
    )

    assert response.status_code == 400
    assert {"account", "category"} <= set(response.json())


def test_filters_and_isolation(api, user):
    account = AccountFactory(user=user)
    TransactionFactory(account=account, description="SALARY", amount=Decimal("3000"))
    TransactionFactory(account=account, description="COFFEE", amount=Decimal("-3"))
    TransactionFactory(description="NOT MINE")

    results = api.get(reverse("api:transaction-list"), {"direction": "out"}).json()["results"]

    assert [t["description"] for t in results] == ["COFFEE"]


def test_categorize_action(api, user):
    txn = TransactionFactory(account=AccountFactory(user=user))

    response = api.post(
        reverse("api:transaction-categorize", args=[txn.pk]),
        {"category": category(user, "Dining").pk},
        format="json",
    )

    txn.refresh_from_db()
    assert response.status_code == 200
    assert (txn.category.name, txn.categorized_by) == ("Dining", Transaction.Source.USER)


def test_summary(api, user):
    TransactionFactory(account=AccountFactory(user=user), amount=Decimal("-12.50"))

    body = api.get(reverse("api:summary")).json()

    assert body["expenses"] == "12.50"
    assert len(body["cashflow"]) == 12


def test_categories_list_is_scoped(api, user):
    names = [c["name"] for c in api.get(reverse("api:category-list")).json()]

    assert "Groceries" in names and len(names) == user.categories.count()


def test_openapi_schema(api):
    assert api.get(reverse("api:schema")).status_code == 200
