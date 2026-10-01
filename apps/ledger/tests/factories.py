from datetime import date
from decimal import Decimal

import factory

from apps.accounts.tests.factories import UserFactory
from apps.ledger.models import Account, Category, Transaction


class AccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Account

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Checking {n}")
    opening_balance = Decimal("1000.00")


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Transaction

    account = factory.SubFactory(AccountFactory)
    user = factory.SelfAttribute("account.user")
    date = factory.LazyFunction(date.today)
    description = factory.Sequence(lambda n: f"COFFEE SHOP #{n}")
    amount = Decimal("-4.50")


def category(user, name: str) -> Category:
    return Category.objects.get(user=user, name=name)
