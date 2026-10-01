"""Turning a parsed statement into transactions, without duplicates.

Each row gets a deterministic ``import_hash`` built from the account, date,
amount, normalized description and the row's *occurrence number* among
identical rows in the same file. Two genuine 4.50 coffees on the same day stay
two transactions, while re-importing the same (or an overlapping) statement
skips everything that is already there.
"""

import hashlib
from collections import Counter

from django.db import transaction

from apps.ledger.merchants import normalize_merchant
from apps.ledger.models import Transaction

from .models import ImportBatch
from .parser import ParseResult
from .signals import transactions_imported

MAX_REPORTED_ERRORS = 20


def row_hash(account_id: int, row, occurrence: int) -> str:
    key = "|".join(
        [
            str(account_id),
            row.date.isoformat(),
            f"{row.amount:.2f}",
            " ".join(row.description.upper().split()),
            str(occurrence),
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()


@transaction.atomic
def import_statement(*, user, account, filename: str, parsed: ParseResult) -> ImportBatch:
    seen: Counter = Counter()
    candidates = {}
    for row in parsed.rows:
        identity = (row.date, row.amount, " ".join(row.description.upper().split()))
        seen[identity] += 1
        candidates[row_hash(account.pk, row, seen[identity])] = row

    existing = set(
        Transaction.objects.filter(user=user, import_hash__in=candidates).values_list(
            "import_hash", flat=True
        )
    )
    new = [
        Transaction(
            user=user,
            account=account,
            date=row.date,
            description=row.description,
            merchant=normalize_merchant(row.description),
            amount=row.amount,
            import_hash=digest,
        )
        for digest, row in candidates.items()
        if digest not in existing
    ]
    created = Transaction.objects.bulk_create(new, ignore_conflicts=True)

    batch = ImportBatch.objects.create(
        user=user,
        account=account,
        filename=filename[:255],
        total_rows=len(parsed.rows) + len(parsed.errors),
        imported=len(created),
        duplicates=len(candidates) - len(new),
        errors=parsed.errors[:MAX_REPORTED_ERRORS],
        date_order=parsed.date_order,
    )
    ids = list(
        Transaction.objects.filter(
            user=user, import_hash__in=[t.import_hash for t in new]
        ).values_list("pk", flat=True)
    )
    transaction.on_commit(
        lambda: transactions_imported.send(
            sender=ImportBatch, user=user, transaction_ids=ids, batch=batch
        )
    )
    return batch
