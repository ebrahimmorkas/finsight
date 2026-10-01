from django.dispatch import Signal

# Sent after new transactions were created by an import.
# kwargs: user, transaction_ids, batch
transactions_imported = Signal()
