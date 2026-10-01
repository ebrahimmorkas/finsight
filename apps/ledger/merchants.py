"""Merchant normalization.

Bank descriptions are noisy: ``"AMZN Mktp US*2K4L19XR3 Amzn.com/bill WA"`` and
``"AMZN MKTP US*7H21K Amzn.com/bill WA"`` are the same merchant. Normalizing them
gives stable keys for rules, recurring-payment detection and ML features.
"""

import re

_NOISE = [
    re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"),  # phone numbers
    re.compile(r"\bHELP\.\S+"),  # support links: HELP.UBER.COM
    re.compile(r"\.(?:COM|NET|ORG|IO|CO)\b"),  # domain suffixes: NETFLIX.COM
    re.compile(r"\*[A-Z0-9]+"),  # reference after an asterisk: AMZN*2K4L19
    re.compile(r"#\s*\d+"),  # store numbers: #1234
    re.compile(r"\b\d{4,}\b"),  # long numbers: card / reference / dates
    re.compile(r"\b(?:POS|DEBIT|CREDIT|CARD|PURCHASE|PAYMENT|ONLINE|VISA|MC)\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),  # dates
    re.compile(r"\b[A-Z]{2}\s*$"),  # trailing state/country code
    re.compile(r"[^A-Z0-9& ]"),  # punctuation
]
_SPACES = re.compile(r"\s+")


def normalize_merchant(description: str) -> str:
    text = description.upper()
    for pattern in _NOISE:
        text = pattern.sub(" ", text)
    words = _SPACES.sub(" ", text).strip().split(" ")
    return " ".join(words[:4]).strip() or description.strip().upper()[:60]
