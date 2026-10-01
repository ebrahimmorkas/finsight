from django.conf import settings
from django.db import models

from apps.ledger.models import Account


class ImportBatch(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="imports"
    )
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="imports")
    filename = models.CharField(max_length=255)
    total_rows = models.PositiveIntegerField(default=0)
    imported = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
    auto_categorized = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list)
    date_order = models.CharField(max_length=3, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "import batches"

    def __str__(self) -> str:
        return f"{self.filename} ({self.imported} imported)"
