"""Generate a realistic demo user with six months of transactions.

Includes salary, rent, subscriptions (detected as recurring), groceries, dining
and transport; a slice of transactions labelled "by the user" so the personal
model can be trained; and a few budgets.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.budgets.models import Budget
from apps.categorization import services as categorization
from apps.ledger.models import Account, Category, Transaction

DEMO_EMAIL = "demo@finsight.dev"
DEMO_PASSWORD = "demo-pass-123"

RANDOM_SPEND = [
    # description templates, amount range, category, probability per day
    (["TESCO STORES {n} LONDON", "SAINSBURYS S/MKT {n}", "ALDI {n}"], (8, 95), "Groceries", 0.35),
    (
        ["PRET A MANGER {n}", "STARBUCKS #{n}", "DELIVEROO *ORDER {n}", "NANDOS {n}"],
        (4, 45),
        "Dining",
        0.3,
    ),
    (["TFL TRAVEL CH {n}", "UBER *TRIP {n}", "SHELL OIL {n}"], (3, 60), "Transport", 0.25),
    (["AMZN MKTP UK*{n}", "ZARA {n} LONDON", "ARGOS {n}"], (12, 140), "Shopping", 0.08),
    (["CINEWORLD {n}", "STEAM GAMES {n}"], (10, 40), "Entertainment", 0.04),
]
MONTHLY = [
    # day of month, description, amount, category
    (1, "ACME LTD PAYROLL", "3850.00", "Salary"),
    (2, "RENT - FLAT 4B STANDING ORDER", "-1450.00", "Rent & Housing"),
    (5, "NETFLIX.COM 866-579-7172", "-15.99", "Subscriptions"),
    (8, "SPOTIFY P2C8F0A1", "-11.99", "Subscriptions"),
    (12, "OCTOPUS ENERGY DD", "-96.40", "Utilities"),
    (15, "PUREGYM MONTHLY", "-24.99", "Health"),
    (20, "TRANSFER TO SAVINGS", "-500.00", "Transfers"),
]


class Command(BaseCommand):
    help = "Create a demo user with six months of categorized transactions."

    @transaction.atomic
    def handle(self, *args, **options):
        if User.objects.filter(email=DEMO_EMAIL).exists():
            self.stdout.write("Demo user already exists.")
            return
        rng = random.Random(42)
        user = User.objects.create_user(DEMO_EMAIL, DEMO_PASSWORD, full_name="Demo User")
        categories = {c.name: c for c in Category.objects.filter(user=user)}
        current = Account.objects.create(
            user=user, name="Current account", opening_balance=Decimal("2400")
        )
        Account.objects.create(
            user=user, name="Savings", kind=Account.Kind.SAVINGS, opening_balance=Decimal("8000")
        )

        today = timezone.localdate()
        start = today - timedelta(days=182)
        rows = []
        day = start
        while day <= today:
            for dom, description, amount, category in MONTHLY:
                if day.day == dom:
                    rows.append((day, description, Decimal(amount), category))
            for templates, (low, high), category, chance in RANDOM_SPEND:
                if rng.random() < chance:
                    description = rng.choice(templates).format(n=rng.randint(100, 9999))
                    amount = -Decimal(str(round(rng.uniform(low, high), 2)))
                    rows.append((day, description, amount, category))
            day += timedelta(days=1)

        transactions = []
        for i, (day, description, amount, category) in enumerate(rows):
            labelled = i % 3 == 0  # the user categorized roughly a third by hand
            transactions.append(
                Transaction(
                    user=user,
                    account=current,
                    date=day,
                    description=description,
                    amount=amount,
                    category=categories[category] if labelled else None,
                    categorized_by=Transaction.Source.USER if labelled else "",
                )
            )
        for txn in transactions:
            txn.merchant = ""
            txn.save()

        categorization.train_user_model(user)
        auto = categorization.categorize_uncategorized(user)

        for name, amount in [("Groceries", "450"), ("Dining", "220"), ("Shopping", "150")]:
            Budget.objects.create(user=user, category=categories[name], amount=Decimal(amount))

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(transactions)} transactions ({auto} auto-categorized).\n"
                f"  login: {DEMO_EMAIL} / {DEMO_PASSWORD}"
            )
        )
