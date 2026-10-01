import pytest
from django.core.management import call_command

from apps.categorization.models import UserModel
from apps.insights.analytics import dashboard
from apps.ledger.models import Transaction


@pytest.mark.django_db
def test_seed_demo_builds_a_useful_dataset():
    call_command("seed_demo")
    call_command("seed_demo")  # idempotent

    user = Transaction.objects.first().user
    model = UserModel.objects.get(user=user)
    data = dashboard(user)

    assert model.samples > 30 and model.accuracy > 0.8
    assert Transaction.objects.filter(categorized_by="ml").count() > 50
    assert {r.merchant for r in data["recurring"]} >= {"NETFLIX", "SPOTIFY"}


@pytest.mark.django_db
def test_train_models_command(capsys):
    call_command("seed_demo")

    call_command("train_models")

    assert "Trained 1 model(s)." in capsys.readouterr().out
