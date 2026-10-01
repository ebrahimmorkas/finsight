"""Domain events emitted by the ledger."""

from django.dispatch import Signal

# A user manually set (or changed) a transaction's category. kwargs: user, transaction
category_corrected = Signal()
