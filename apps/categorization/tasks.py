from celery import shared_task
from django.contrib.auth import get_user_model

from apps.imports.models import ImportBatch
from apps.ledger.models import Transaction

from . import services


@shared_task
def categorize_transactions(user_id: int, transaction_ids: list[int], batch_id: int | None = None):
    user = get_user_model().objects.get(pk=user_id)
    transactions = list(Transaction.objects.filter(user=user, pk__in=transaction_ids))
    count = services.categorize(user, transactions)
    if batch_id:
        ImportBatch.objects.filter(pk=batch_id, user=user).update(auto_categorized=count)
    return count


@shared_task
def retrain_user_model(user_id: int) -> bool:
    user = get_user_model().objects.get(pk=user_id)
    return services.train_user_model(user) is not None
