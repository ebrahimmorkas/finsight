"""Transaction categorization model.

Features
    * TF-IDF over **character n-grams** (2-5, word-boundary aware) of the
      normalized merchant + description. Robust to truncation and typos such as
      ``AMZN MKTP`` vs ``AMAZON MARKETPLACE``.
    * TF-IDF over **word unigrams/bigrams**.
    * Two numeric features: direction (money in/out) and log-scaled magnitude,
      which separate e.g. a refund from a purchase at the same merchant.

Model
    Multinomial logistic regression with balanced class weights. It is fast to
    train per user, gives calibrated-enough probabilities for a confidence
    threshold, and its coefficients are explainable.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer

from apps.ledger.merchants import normalize_merchant


@dataclass(frozen=True)
class Example:
    description: str
    amount: float


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float


def _text(examples) -> list[str]:
    return [f"{normalize_merchant(e.description)} {e.description}".lower() for e in examples]


def _numeric(examples) -> np.ndarray:
    return np.array(
        [[1.0 if e.amount > 0 else 0.0, math.log1p(abs(e.amount)) / 10] for e in examples]
    )


def build_pipeline() -> Pipeline:
    text = FunctionTransformer(_text)
    features = FeatureUnion(
        [
            (
                "chars",
                Pipeline(
                    [
                        ("text", text),
                        (
                            "tfidf",
                            TfidfVectorizer(
                                analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True
                            ),
                        ),
                    ]
                ),
            ),
            (
                "words",
                Pipeline(
                    [
                        ("text", text),
                        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                    ]
                ),
            ),
            ("numeric", FunctionTransformer(_numeric)),
        ]
    )
    return Pipeline(
        [
            ("features", features),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced", C=5.0)),
        ]
    )


class CategoryClassifier:
    def __init__(self, pipeline: Pipeline | None = None):
        self.pipeline = pipeline or build_pipeline()

    @property
    def classes(self) -> list[str]:
        return list(self.pipeline.classes_)

    def fit(self, examples: list[Example], labels: list[str]) -> CategoryClassifier:
        self.pipeline.fit(examples, labels)
        return self

    def predict(self, examples: list[Example]) -> list[Prediction]:
        if not examples:
            return []
        probabilities = self.pipeline.predict_proba(examples)
        classes = self.pipeline.classes_
        best = probabilities.argmax(axis=1)
        return [
            Prediction(label=str(classes[i]), confidence=float(row[i]))
            for i, row in zip(best, probabilities, strict=True)
        ]

    def dumps(self) -> bytes:
        buffer = io.BytesIO()
        joblib.dump(self.pipeline, buffer, compress=3)
        return buffer.getvalue()

    @classmethod
    def loads(cls, blob: bytes) -> CategoryClassifier:
        # Only ever loads blobs this application produced and stored itself.
        return cls(joblib.load(io.BytesIO(blob)))


def cross_validated_accuracy(examples: list[Example], labels: list[str]) -> float | None:
    """Mean accuracy over stratified folds, or ``None`` if there is too little data.

    Categories with a single example can't be split across folds, so they are
    left out of the evaluation (they are still used for training).
    """
    counts = {label: labels.count(label) for label in set(labels)}
    keep = [i for i, label in enumerate(labels) if counts[label] >= 2]
    kept_counts = [count for count in counts.values() if count >= 2]
    if len(kept_counts) < 2:
        return None
    folds = min(5, min(kept_counts))
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=0)
    scores = cross_val_score(
        build_pipeline(), [examples[i] for i in keep], [labels[i] for i in keep], cv=splitter
    )
    return float(scores.mean())
