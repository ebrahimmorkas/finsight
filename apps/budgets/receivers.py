from django.dispatch import receiver

from apps.imports.signals import transactions_imported

from .tasks import check_budgets_for_user


@receiver(transactions_imported, dispatch_uid="budgets.on_import")
def on_import(sender, user, transaction_ids, **kwargs) -> None:
    # Runs after categorization (registered later in INSTALLED_APPS), so new
    # spending is already assigned to categories.
    if transaction_ids:
        check_budgets_for_user.delay(user.pk)
