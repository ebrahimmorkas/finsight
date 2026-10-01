from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.ledger.models import MONEY, Category


class Budget(models.Model):
    """A monthly spending limit for one category."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets"
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="budgets")
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("1"))])
    warn_at_percent = models.PositiveSmallIntegerField(
        default=80, validators=[MinValueValidator(10), MaxValueValidator(99)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "category"], name="one_budget_per_category")
        ]

    def __str__(self) -> str:
        return f"{self.category}: {self.amount}/month"


class BudgetAlert(models.Model):
    """Records alerts already sent so each threshold is emailed at most once per month."""

    class Level(models.TextChoices):
        WARNING = "warning", "Approaching limit"
        EXCEEDED = "exceeded", "Over budget"

    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="alerts")
    month = models.DateField(help_text="First day of the month.")
    level = models.CharField(max_length=10, choices=Level.choices)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["budget", "month", "level"], name="one_alert_per_level"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.budget} {self.month:%Y-%m} {self.level}"
