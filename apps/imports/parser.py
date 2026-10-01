"""Bank-statement CSV parsing.

Banks export CSVs in many shapes. The parser:

* sniffs the delimiter (``,`` ``;`` ``\\t`` ``|``),
* finds the date / description / amount columns from common header names, and
  supports either one signed ``amount`` column or separate ``debit`` / ``credit``,
* resolves ambiguous dates (``03/04/2026``) per file: if any value has a first
  part > 12 the file is day-first, otherwise the user's preference is used,
* parses amounts like ``1,234.56``, ``-12.00``, ``(12.00)``, ``$1 234,56``.

Rows that cannot be parsed are reported with their line number instead of
aborting the whole import.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MAX_ROWS = 10_000

HEADER_ALIASES = {
    "date": {
        "date",
        "transaction date",
        "posted date",
        "posting date",
        "booking date",
        "value date",
    },
    "description": {
        "description",
        "details",
        "memo",
        "payee",
        "narrative",
        "merchant",
        "name",
        "transaction description",
    },
    "amount": {"amount", "value", "transaction amount", "amount (usd)", "amount (eur)"},
    "debit": {"debit", "withdrawal", "withdrawals", "money out", "paid out", "debit amount"},
    "credit": {"credit", "deposit", "deposits", "money in", "paid in", "credit amount"},
}

DAY_FIRST = "dmy"
MONTH_FIRST = "mdy"
ISO_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%Y%m%d"]


class CSVFormatError(ValueError):
    """The file as a whole cannot be imported (e.g. missing required columns)."""


@dataclass
class ParsedRow:
    line: int
    date: date
    description: str
    amount: Decimal


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    date_order: str = ""


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CSVFormatError("Could not decode the file. Please export it as UTF-8 CSV.")


def _map_columns(header: list[str]) -> dict[str, int]:
    normalized = [h.strip().lower() for h in header]
    mapping = {}
    for role, aliases in HEADER_ALIASES.items():
        for index, name in enumerate(normalized):
            if name in aliases:
                mapping[role] = index
                break
    if "date" not in mapping or "description" not in mapping:
        raise CSVFormatError("Could not find the date and description columns.")
    if "amount" not in mapping and not ({"debit", "credit"} <= mapping.keys()):
        raise CSVFormatError("Could not find an amount column (or debit and credit columns).")
    return mapping


_AMOUNT_JUNK = re.compile(r"[^\d,.\-()]")


def parse_amount(text: str) -> Decimal:
    raw = text.strip()
    if not raw:
        return Decimal("0")
    kept = _AMOUNT_JUNK.sub("", raw)  # drop currency symbols, spaces, letters
    if not kept:
        raise ValueError(f"invalid amount '{text}'")
    negative = (kept.startswith("(") and kept.endswith(")")) or "-" in (kept[0], kept[-1])
    cleaned = kept.strip("()-")
    if "," in cleaned and "." in cleaned:
        # Whichever separator comes last is the decimal separator.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        head, _, tail = cleaned.rpartition(",")
        cleaned = (
            f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else cleaned.replace(",", "")
        )
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount '{text}'") from exc
    return -value if negative else value


_SLASHED = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\s*$")


def detect_date_order(values: list[str], preferred: str) -> str:
    for value in values:
        match = _SLASHED.match(value)
        if match:
            first, second = int(match.group(1)), int(match.group(2))
            if first > 12:
                return DAY_FIRST
            if second > 12:
                return MONTH_FIRST
    return preferred


def parse_date(text: str, order: str) -> date:
    match = _SLASHED.match(text)
    if match:
        a, b, year = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        day, month = (a, b) if order == DAY_FIRST else (b, a)
        return date(year, month, day)
    for fmt in ISO_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date '{text}'")


def parse_csv(raw: bytes, *, preferred_date_order: str = DAY_FIRST) -> ParseResult:
    text = _decode(raw)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(rows) < 2:
        raise CSVFormatError("The file has no transactions.")
    if len(rows) - 1 > MAX_ROWS:
        raise CSVFormatError(f"Files are limited to {MAX_ROWS:,} rows.")

    header, body = rows[0], rows[1:]
    columns = _map_columns(header)
    result = ParseResult()
    result.date_order = detect_date_order(
        [row[columns["date"]] for row in body if len(row) > columns["date"]], preferred_date_order
    )

    for line, row in enumerate(body, start=2):
        try:
            description = row[columns["description"]].strip()
            if not description:
                raise ValueError("empty description")
            if "amount" in columns:
                amount = parse_amount(row[columns["amount"]])
            else:
                amount = parse_amount(row[columns["credit"]]) - abs(
                    parse_amount(row[columns["debit"]])
                )
            result.rows.append(
                ParsedRow(
                    line=line,
                    date=parse_date(row[columns["date"]], result.date_order),
                    description=description[:255],
                    amount=amount,
                )
            )
        except (IndexError, ValueError) as exc:
            result.errors.append(f"Line {line}: {exc}")
    return result
