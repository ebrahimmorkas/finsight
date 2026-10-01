from datetime import date, timedelta
from decimal import Decimal

from apps.insights.recurring import detect_recurring

D = Decimal


def monthly(merchant, amount, months=4, start=date(2026, 5, 3), jitter=(0, 1, -1, 2)):
    return [
        (merchant, start + timedelta(days=30 * i + jitter[i % len(jitter)]), D(amount))
        for i in range(months)
    ]


def test_detects_monthly_subscription():
    [netflix] = detect_recurring(monthly("NETFLIX", "-15.99"))

    assert netflix.cadence == "monthly"
    assert netflix.occurrences == 4
    assert netflix.average_amount == D("15.99")
    assert netflix.monthly_cost == D("15.99")
    assert 28 <= (netflix.next_date - netflix.last_date).days <= 33  # median observed gap


def test_detects_weekly_and_yearly():
    weekly = [("GYM CLASS", date(2026, 8, 3) + timedelta(weeks=i), D("-12")) for i in range(5)]
    yearly = [("DOMAIN RENEWAL", date(2023 + i, 3, 1), D("-20")) for i in range(3)]

    found = {r.merchant: r for r in detect_recurring(weekly + yearly)}

    assert found["GYM CLASS"].cadence == "weekly"
    assert found["GYM CLASS"].monthly_cost == D("52.00")
    assert found["DOMAIN RENEWAL"].cadence == "yearly"


def test_small_price_change_is_still_recurring():
    rows = monthly("SPOTIFY", "-9.99", months=3) + [("SPOTIFY", date(2026, 8, 3), D("-10.99"))]

    assert [r.merchant for r in detect_recurring(rows)] == ["SPOTIFY"]


def test_irregular_amounts_are_not_recurring():
    rows = [
        ("TESCO", date(2026, 5, 1), D("-12.00")),
        ("TESCO", date(2026, 6, 1), D("-95.40")),
        ("TESCO", date(2026, 7, 1), D("-31.15")),
        ("TESCO", date(2026, 8, 1), D("-64.00")),
    ]

    assert detect_recurring(rows) == []


def test_irregular_timing_is_not_recurring():
    days = [date(2026, 5, 1), date(2026, 5, 9), date(2026, 6, 30), date(2026, 7, 4)]

    assert detect_recurring([("CINEMA", d, D("-10")) for d in days]) == []


def test_too_few_occurrences_and_income_are_ignored():
    rows = monthly("NEW SUB", "-5", months=2) + monthly("PAYROLL", "3000")

    assert detect_recurring(rows) == []


def test_cancelled_subscriptions_are_dropped():
    rows = monthly("OLD GYM", "-30", start=date(2025, 1, 1))

    assert detect_recurring(rows, today=date(2026, 10, 1)) == []
