from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.categorization import services
from apps.categorization.classifier import CategoryClassifier, Example
from apps.categorization.models import CategorizationRule, UserModel
from apps.imports.models import ImportBatch
from apps.ledger.models import Transaction
from apps.ledger.tests.factories import AccountFactory, TransactionFactory, category

pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return AccountFactory()


@pytest.fixture
def user(account):
    return account.user


def txn(account, description, amount="-10.00", **kwargs):
    return TransactionFactory(
        account=account, description=description, amount=Decimal(amount), **kwargs
    )


# --- classifier -------------------------------------------------------------------------


def test_classifier_roundtrips_through_bytes():
    clf = CategoryClassifier().fit(
        [
            Example("NETFLIX", -10),
            Example("TESCO", -30),
            Example("NETFLIX.COM", -12),
            Example("TESCO 12", -5),
        ],
        ["subs", "food", "subs", "food"],
    )

    restored = CategoryClassifier.loads(clf.dumps())

    assert restored.predict([Example("NETFLIX 866", -11)])[0].label == "subs"


def test_starter_model_categorizes_common_merchants(user, account):
    netflix = txn(account, "NETFLIX.COM 866-579-7172 CA", "-15.99")
    tesco = txn(account, "TESCO STORES 3021 LONDON", "-42.10")
    salary = txn(account, "ACME CORP PAYROLL", "3200.00")

    assert services.categorize(user, [netflix, tesco, salary]) == 3

    netflix.refresh_from_db()
    assert netflix.category == category(user, "Subscriptions")
    assert netflix.categorized_by == Transaction.Source.ML
    assert 0.6 <= netflix.confidence <= 1
    tesco.refresh_from_db()
    salary.refresh_from_db()
    assert (tesco.category.name, salary.category.name) == ("Groceries", "Salary")


def test_low_confidence_predictions_are_not_applied(user, account, settings):
    settings.FINSIGHT_ML_CONFIDENCE = 0.99
    mystery = txn(account, "XQZ HOLDINGS 4411")

    assert services.categorize(user, [mystery]) == 0
    mystery.refresh_from_db()
    assert mystery.category is None


def test_rules_win_over_the_model(user, account):
    CategorizationRule.objects.create(
        user=user, field="merchant", pattern="netflix", category=category(user, "Entertainment")
    )
    netflix = txn(account, "NETFLIX.COM")

    services.categorize(user, [netflix])

    netflix.refresh_from_db()
    assert (netflix.category.name, netflix.categorized_by) == ("Entertainment", "rule")


def test_already_categorized_transactions_are_left_alone(user, account):
    mine = txn(account, "NETFLIX.COM", category=category(user, "Travel"), categorized_by="user")

    assert services.categorize(user, [mine]) == 0
    mine.refresh_from_db()
    assert mine.category.name == "Travel"


def test_personal_model_learns_user_specific_labels(user, account, settings):
    settings.FINSIGHT_ML_MIN_SAMPLES = 10
    gym = category(user, "Health")
    pets = category(user, "Shopping")
    for n in range(8):
        txn(account, f"IRON PARADISE GYM {n}", category=gym, categorized_by="user")
        txn(account, f"PAWS & CLAWS PET STORE {n}", category=pets, categorized_by="user")

    model = services.train_user_model(user)
    new = txn(account, "IRON PARADISE GYM MONTHLY")
    services.categorize(user, [new])

    assert model.samples == 16 and model.classes == 2
    assert model.accuracy is not None
    new.refresh_from_db()
    assert new.category == gym


def test_model_never_trains_on_its_own_guesses(user, account, settings):
    settings.FINSIGHT_ML_MIN_SAMPLES = 2
    for _ in range(5):
        txn(account, "NETFLIX", category=category(user, "Subscriptions"), categorized_by="ml")

    assert services.train_user_model(user) is None


def test_corrections_trigger_retraining(client, user, account, settings):
    settings.FINSIGHT_ML_MIN_SAMPLES = 4
    settings.FINSIGHT_ML_RETRAIN_AFTER = 2
    client.force_login(user)
    labels = ["Dining", "Groceries", "Dining", "Groceries", "Dining", "Groceries"]
    transactions = [txn(account, f"PLACE {i}") for i in range(len(labels))]

    for transaction, name in zip(transactions[:4], labels[:4], strict=True):
        client.post(
            reverse("ledger:set-category", args=[transaction.pk]),
            {"category": category(user, name).pk},
        )
    first = UserModel.objects.get(user=user)  # trained once 4 labels existed

    for transaction, name in zip(transactions[4:], labels[4:], strict=True):
        client.post(
            reverse("ledger:set-category", args=[transaction.pk]),
            {"category": category(user, name).pk},
        )

    assert first.samples == 4
    assert UserModel.objects.get(user=user).samples == 6  # retrained after 2 corrections


def test_imported_transactions_are_auto_categorized(
    client, account, django_capture_on_commit_callbacks
):
    client.force_login(account.user)
    csv = b"\n".join(
        [
            b"Date,Description,Amount",
            b"2026-09-01,SPOTIFY P1A2B3,-9.99",
            b"2026-09-02,SHELL OIL 5744,-60.00",
        ]
    )

    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("imports:upload"),
            {
                "account": account.pk,
                "date_order": "dmy",
                "file": SimpleUploadedFile("s.csv", csv, content_type="text/csv"),
            },
        )

    assert ImportBatch.objects.get().auto_categorized == 2
    assert set(Transaction.objects.values_list("category__name", flat=True)) == {
        "Subscriptions",
        "Transport",
    }


# --- views ---------------------------------------------------------------------------------


def test_overview_and_rule_creation_applies_rule(client, user, account):
    client.force_login(user)
    pending = txn(account, "ZZZ UNKNOWN THING")
    response = client.get(reverse("categorization:overview"))
    assert response.status_code == 200

    client.post(
        reverse("categorization:overview"),
        {
            "field": "description",
            "pattern": "zzz",
            "category": category(user, "Shopping").pk,
            "priority": 1,
        },
    )

    pending.refresh_from_db()
    assert pending.category.name == "Shopping"


def test_retrain_without_enough_data_shows_warning(client, user):
    client.force_login(user)

    response = client.post(reverse("categorization:retrain"), follow=True)

    assert "Categorize at least" in str(list(response.context["messages"])[0])


def test_rules_are_private(client, user):
    other_rule = CategorizationRule.objects.create(
        user=AccountFactory().user, pattern="x", category=category(user, "Dining")
    )
    client.force_login(user)

    assert (
        client.post(reverse("categorization:rule-delete", args=[other_rule.pk])).status_code == 404
    )
