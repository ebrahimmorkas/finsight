from django.conf import settings
from django.db import models

from apps.ledger.models import Category


class CategorizationRule(models.Model):
    """User-defined rule: "if the merchant/description contains X, use category Y"."""

    class Field(models.TextChoices):
        MERCHANT = "merchant", "Merchant"
        DESCRIPTION = "description", "Description"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categorization_rules"
    )
    field = models.CharField(max_length=12, choices=Field.choices, default=Field.MERCHANT)
    pattern = models.CharField(max_length=80, help_text="Case-insensitive 'contains' match.")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="rules")
    priority = models.PositiveSmallIntegerField(default=100, help_text="Lower runs first.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self) -> str:
        return f"{self.get_field_display()} contains '{self.pattern}' → {self.category}"

    def matches(self, transaction) -> bool:
        value = getattr(transaction, self.field) or ""
        return self.pattern.lower() in value.lower()


class UserModel(models.Model):
    """A user's trained categorization model (serialized with joblib)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="category_model"
    )
    blob = models.BinaryField()
    trained_at = models.DateTimeField()
    samples = models.PositiveIntegerField()
    classes = models.PositiveSmallIntegerField()
    accuracy = models.FloatField(null=True, blank=True, help_text="Cross-validated accuracy.")
    corrections_since_training = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"Model for {self.user} ({self.samples} samples)"
