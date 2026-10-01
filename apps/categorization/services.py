"""Categorization pipeline: rules first, then the ML model, then leave it to the user.

* Explicit user rules always win (they are what the user asked for).
* Each user gets a **personal model** once they have labelled enough
  transactions; until then a **starter model** trained on built-in examples
  (mapped onto the user's default categories) is used.
* Predictions below ``FINSIGHT_ML_CONFIDENCE`` are not applied: an empty
  category is better than a confidently wrong one.
* Only labels set by the user (or their rules) are used for training, never the
  model's own guesses, to avoid a feedback loop.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings
from django.db import transaction as db_transaction
from django.db.models import F
from django.utils import timezone

from apps.ledger.events import transactions_changed
from apps.ledger.models import Category, Transaction

from .classifier import CategoryClassifier, Example, cross_validated_accuracy
from .models import CategorizationRule, UserModel
from .seed_data import generate

logger = logging.getLogger(__name__)

TRUSTED_SOURCES = [Transaction.Source.USER, Transaction.Source.RULE]


@lru_cache(maxsize=1)
def starter_classifier() -> CategoryClassifier:
    rows = generate()
    return CategoryClassifier().fit(
        [Example(description, amount) for description, amount, _ in rows],
        [label for *_, label in rows],
    )


def _example(txn: Transaction) -> Example:
    return Example(txn.description, float(txn.amount))


def labelled_transactions(user):
    return Transaction.objects.filter(
        user=user, category__isnull=False, categorized_by__in=TRUSTED_SOURCES
    )


def train_user_model(user) -> UserModel | None:
    """(Re)train the user's personal model. Returns ``None`` if there isn't enough data."""
    rows = list(labelled_transactions(user).values_list("description", "amount", "category_id"))
    labels = [str(category_id) for *_, category_id in rows]
    if len(rows) < settings.FINSIGHT_ML_MIN_SAMPLES or len(set(labels)) < 2:
        return None

    examples = [Example(description, float(amount)) for description, amount, _ in rows]
    classifier = CategoryClassifier().fit(examples, labels)
    model, _ = UserModel.objects.update_or_create(
        user=user,
        defaults={
            "blob": classifier.dumps(),
            "trained_at": timezone.now(),
            "samples": len(rows),
            "classes": len(set(labels)),
            "accuracy": cross_validated_accuracy(examples, labels),
            "corrections_since_training": 0,
        },
    )
    logger.info("Trained model for user %s on %s samples", user.pk, len(rows))
    return model


def _classifier_for(user) -> tuple[CategoryClassifier, dict[str, Category]]:
    """Return the best available classifier and a label -> Category mapping."""
    categories = {c.pk: c for c in Category.objects.filter(user=user)}
    personal = UserModel.objects.filter(user=user).first()
    if personal is not None:
        classifier = CategoryClassifier.loads(bytes(personal.blob))
        return classifier, {
            label: categories[int(label)]
            for label in classifier.classes
            if int(label) in categories
        }
    by_name = {c.name: c for c in categories.values()}
    classifier = starter_classifier()
    return classifier, {label: by_name[label] for label in classifier.classes if label in by_name}


def apply_rules(user, transactions: list[Transaction]) -> list[Transaction]:
    """Categorize by rules; return the transactions no rule matched."""
    rules = list(CategorizationRule.objects.filter(user=user).select_related("category"))
    remaining = []
    for txn in transactions:
        rule = next((r for r in rules if r.matches(txn)), None)
        if rule:
            txn.category = rule.category
            txn.categorized_by = Transaction.Source.RULE
            txn.confidence = None
        else:
            remaining.append(txn)
    return remaining


@db_transaction.atomic
def categorize(user, transactions) -> int:
    """Categorize uncategorized transactions in place. Returns how many were categorized."""
    pending = [t for t in transactions if t.category_id is None]
    if not pending:
        return 0

    remaining = apply_rules(user, pending)
    if remaining:
        classifier, label_map = _classifier_for(user)
        threshold = settings.FINSIGHT_ML_CONFIDENCE
        for txn, prediction in zip(
            remaining, classifier.predict([_example(t) for t in remaining]), strict=True
        ):
            category = label_map.get(prediction.label)
            if category is not None and prediction.confidence >= threshold:
                txn.category = category
                txn.categorized_by = Transaction.Source.ML
                txn.confidence = round(prediction.confidence, 4)

    done = [t for t in pending if t.category_id is not None]
    Transaction.objects.bulk_update(done, ["category", "categorized_by", "confidence"])
    if done:
        transactions_changed.send(sender=Transaction, user_id=user.pk)
    return len(done)


def categorize_uncategorized(user) -> int:
    return categorize(user, list(Transaction.objects.filter(user=user, category__isnull=True)))


def note_correction(user) -> bool:
    """Count a manual correction; return True when a retrain is due."""
    updated = UserModel.objects.filter(user=user).update(
        corrections_since_training=F("corrections_since_training") + 1
    )
    if updated:
        corrections = UserModel.objects.get(user=user).corrections_since_training
        return corrections >= settings.FINSIGHT_ML_RETRAIN_AFTER
    # No personal model yet: train as soon as there is enough labelled data.
    return labelled_transactions(user).count() >= settings.FINSIGHT_ML_MIN_SAMPLES
