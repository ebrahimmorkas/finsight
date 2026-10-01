from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Sum

from apps.core.models import TimeStampedModel

from .merchants import normalize_merchant

MONEY = {"max_digits": 14, "decimal_places": 2}


class Account(TimeStampedModel):
    class Kind(models.TextChoices):
        CHECKING = "checking", "Checking"
        SAVINGS = "savings", "Savings"
        CREDIT_CARD = "credit_card", "Credit card"
        CASH = "cash", "Cash"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts"
    )
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.CHECKING)
    currency = models.CharField(max_length=3, default="USD")
    opening_balance = models.DecimalField(**MONEY, default=Decimal("0"))

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="unique_account_name")]

    def __str__(self) -> str:
        return self.name

    @property
    def balance(self) -> Decimal:
        total = self.transactions.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        return self.opening_balance + total


class Category(models.Model):
    class Kind(models.TextChoices):
        EXPENSE = "expense", "Expense"
        INCOME = "income", "Income"
        TRANSFER = "transfer", "Transfer"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.EXPENSE)
    color = models.CharField(
        max_length=7,
        default="#64748b",
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use a hex color like #2563eb.")],
    )

    class Meta:
        ordering = ["kind", "name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_category_name")
        ]

    def __str__(self) -> str:
        return self.name


DEFAULT_CATEGORIES = [
    ("Groceries", "expense", "#16a34a"),
    ("Dining", "expense", "#f97316"),
    ("Transport", "expense", "#0ea5e9"),
    ("Rent & Housing", "expense", "#7c3aed"),
    ("Utilities", "expense", "#64748b"),
    ("Shopping", "expense", "#db2777"),
    ("Entertainment", "expense", "#eab308"),
    ("Health", "expense", "#ef4444"),
    ("Subscriptions", "expense", "#8b5cf6"),
    ("Travel", "expense", "#14b8a6"),
    ("Salary", "income", "#22c55e"),
    ("Other income", "income", "#84cc16"),
    ("Transfers", "transfer", "#94a3b8"),
]


class Transaction(TimeStampedModel):
    class Source(models.TextChoices):
        NONE = "", "Uncategorized"
        USER = "user", "You"
        RULE = "rule", "Rule"
        ML = "ml", "Auto (ML)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    date = models.DateField(db_index=True)
    description = models.CharField(max_length=255)
    merchant = models.CharField(max_length=80, blank=True, db_index=True)
    amount = models.DecimalField(
        **MONEY, help_text="Negative for money out, positive for money in."
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions"
    )
    categorized_by = models.CharField(max_length=4, choices=Source.choices, blank=True, default="")
    confidence = models.FloatField(null=True, blank=True)
    import_hash = models.CharField(max_length=64, blank=True, default="")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["user", "date"]), models.Index(fields=["user", "category"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "import_hash"],
                condition=~models.Q(import_hash=""),
                name="unique_import_hash",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.description} {self.amount}"

    def save(self, *args, **kwargs):
        if not self.merchant:
            self.merchant = normalize_merchant(self.description)
        super().save(*args, **kwargs)

    @property
    def is_outflow(self) -> bool:
        return self.amount < 0
