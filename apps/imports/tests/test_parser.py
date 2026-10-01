from datetime import date
from decimal import Decimal

import pytest

from apps.imports.parser import (
    DAY_FIRST,
    MONTH_FIRST,
    CSVFormatError,
    detect_date_order,
    parse_amount,
    parse_csv,
    parse_date,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12.50", Decimal("12.50")),
        ("-12.50", Decimal("-12.50")),
        ("(12.50)", Decimal("-12.50")),
        ("1,234.56", Decimal("1234.56")),
        ("1.234,56", Decimal("1234.56")),
        ("$ 1 234,56", Decimal("1234.56")),
        ("12,5", Decimal("12.5")),
        ("1,000", Decimal("1000")),
        ("€-7.10", Decimal("-7.10")),
        ("", Decimal("0")),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_parse_amount_rejects_garbage():
    with pytest.raises(ValueError):
        parse_amount("abc")


def test_date_order_detection():
    assert detect_date_order(["03/04/2026", "25/04/2026"], MONTH_FIRST) == DAY_FIRST
    assert detect_date_order(["04/25/2026"], DAY_FIRST) == MONTH_FIRST
    assert detect_date_order(["03/04/2026"], MONTH_FIRST) == MONTH_FIRST  # ambiguous -> preference


@pytest.mark.parametrize(
    ("text", "order", "expected"),
    [
        ("03/04/2026", DAY_FIRST, date(2026, 4, 3)),
        ("03/04/2026", MONTH_FIRST, date(2026, 3, 4)),
        ("3.4.26", DAY_FIRST, date(2026, 4, 3)),
        ("2026-04-03", DAY_FIRST, date(2026, 4, 3)),
        ("03 Apr 2026", DAY_FIRST, date(2026, 4, 3)),
    ],
)
def test_parse_date(text, order, expected):
    assert parse_date(text, order) == expected


def test_parse_csv_with_signed_amount_column():
    raw = b"\n".join(
        [
            b"Date,Description,Amount",
            b"2026-04-01,TESCO STORES 3021,-23.10",
            b"2026-04-02,SALARY ACME,2500.00",
        ]
    )

    result = parse_csv(raw)

    assert [(r.description, r.amount) for r in result.rows] == [
        ("TESCO STORES 3021", Decimal("-23.10")),
        ("SALARY ACME", Decimal("2500.00")),
    ]
    assert result.errors == []


def test_parse_csv_with_debit_credit_semicolons_and_bom():
    lines = [
        "Booking date;Payee;Debit;Credit",
        "25/04/2026;Coffee;3,20;",
        "26/04/2026;Refund;;10,00",
    ]
    raw = "\n".join(lines).encode("utf-8-sig")  # Excel-style UTF-8 with BOM

    result = parse_csv(raw, preferred_date_order=MONTH_FIRST)

    assert result.date_order == DAY_FIRST  # 25 can only be a day
    assert [(r.date, r.amount) for r in result.rows] == [
        (date(2026, 4, 25), Decimal("-3.20")),
        (date(2026, 4, 26), Decimal("10.00")),
    ]


def test_bad_rows_are_reported_not_fatal():
    raw = b"Date,Description,Amount\n2026-04-01,OK,-1\nnot-a-date,BAD,-2\n2026-04-03,,-3\n"

    result = parse_csv(raw)

    assert len(result.rows) == 1
    assert result.errors[0].startswith("Line 3:")
    assert "Line 4: empty description" in result.errors


@pytest.mark.parametrize(
    "raw",
    [b"Foo,Bar\n1,2\n", b"Date,Description\n2026-01-01,x\n", b"Date,Description,Amount\n"],
)
def test_unusable_files(raw):
    with pytest.raises(CSVFormatError):
        parse_csv(raw)
