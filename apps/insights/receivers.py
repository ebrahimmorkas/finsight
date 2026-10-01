from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.ledger.events import transactions_changed
from apps.ledger.models import Transaction

from .analytics import bump_version


@receiver([post_save, post_delete], sender=Transaction, dispatch_uid="insights.invalidate")
def invalidate_dashboard(sender, instance, **kwargs) -> None:
    bump_version(instance.user_id)


@receiver(transactions_changed, dispatch_uid="insights.invalidate_bulk")
def invalidate_dashboard_bulk(sender, user_id, **kwargs) -> None:
    bump_version(user_id)
