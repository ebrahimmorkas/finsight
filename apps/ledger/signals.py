from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DEFAULT_CATEGORIES, Category


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="ledger.default_categories")
def create_default_categories(sender, instance, created, **kwargs) -> None:
    if created:
        Category.objects.bulk_create(
            [
                Category(user=instance, name=name, kind=kind, color=color)
                for name, kind, color in DEFAULT_CATEGORIES
            ]
        )
