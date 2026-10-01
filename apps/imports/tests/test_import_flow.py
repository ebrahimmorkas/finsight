import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.imports.models import ImportBatch
from apps.imports.parser import parse_csv
from apps.imports.services import import_statement
from apps.ledger.models import Transaction
from apps.ledger.tests.factories import AccountFactory

pytestmark = pytest.mark.django_db

STATEMENT = (
    b"Date,Description,Amount\n"
    b"2026-04-01,STARBUCKS #123,-4.50\n"
    b"2026-04-01,STARBUCKS #123,-4.50\n"  # a genuine second coffee
    b"2026-04-02,NETFLIX.COM,-15.99\n"
)


def run_import(account, raw=STATEMENT):
    return import_statement(
        user=account.user, account=account, filename="april.csv", parsed=parse_csv(raw)
    )


def test_identical_rows_in_one_file_are_both_imported():
    account = AccountFactory()

    batch = run_import(account)

    assert batch.imported == 3
    assert Transaction.objects.filter(merchant="STARBUCKS").count() == 2


def test_reimporting_same_statement_skips_everything():
    account = AccountFactory()
    run_import(account)

    second = run_import(account)

    assert (second.imported, second.duplicates) == (0, 3)
    assert Transaction.objects.count() == 3


def test_overlapping_statement_only_adds_new_rows():
    account = AccountFactory()
    run_import(account)
    overlap = STATEMENT + b"2026-04-05,UBER *TRIP,-12.00\n"

    batch = run_import(account, overlap)

    assert (batch.imported, batch.duplicates) == (1, 3)


def test_same_rows_in_different_accounts_are_independent():
    user = UserFactory()
    run_import(AccountFactory(user=user, name="A"))
    batch = run_import(AccountFactory(user=user, name="B"))

    assert batch.imported == 3


def test_upload_view(client):
    account = AccountFactory()
    client.force_login(account.user)

    response = client.post(
        reverse("imports:upload"),
        {
            "account": account.pk,
            "date_order": "dmy",
            "file": SimpleUploadedFile("april.csv", STATEMENT, content_type="text/csv"),
        },
    )

    batch = ImportBatch.objects.get()
    assert response.url == reverse("imports:detail", args=[batch.pk])
    assert b"New transactions" in client.get(response.url).content


def test_upload_view_reports_unusable_file(client):
    account = AccountFactory()
    client.force_login(account.user)

    response = client.post(
        reverse("imports:upload"),
        {
            "account": account.pk,
            "date_order": "dmy",
            "file": SimpleUploadedFile("bad.csv", b"a,b\n1,2\n", content_type="text/csv"),
        },
    )

    assert "file" in response.context["form"].errors


def test_cannot_import_into_someone_elses_account(client):
    client.force_login(UserFactory())
    foreign = AccountFactory()

    response = client.post(
        reverse("imports:upload"),
        {
            "account": foreign.pk,
            "date_order": "dmy",
            "file": SimpleUploadedFile("x.csv", STATEMENT, content_type="text/csv"),
        },
    )

    assert "account" in response.context["form"].errors
    assert not Transaction.objects.exists()


def test_import_details_are_private(client):
    batch = run_import(AccountFactory())
    client.force_login(UserFactory())

    assert client.get(reverse("imports:detail", args=[batch.pk])).status_code == 404
