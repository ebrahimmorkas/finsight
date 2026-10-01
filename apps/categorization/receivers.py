from django.dispatch import receiver

from apps.imports.signals import transactions_imported
from apps.ledger.events import category_corrected

from . import services
from .tasks import categorize_transactions, retrain_user_model


@receiver(transactions_imported, dispatch_uid="categorization.on_import")
def on_import(sender, user, transaction_ids, batch, **kwargs) -> None:
    if transaction_ids:
        categorize_transactions.delay(user.pk, transaction_ids, batch.pk)


@receiver(category_corrected, dispatch_uid="categorization.on_correction")
def on_correction(sender, user, transaction, **kwargs) -> None:
    if services.note_correction(user):
        retrain_user_model.delay(user.pk)
