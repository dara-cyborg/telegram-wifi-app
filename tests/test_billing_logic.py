from datetime import date

from app.services.billing_logic import calculate_billing, classify_status, get_anchored_date


def test_on_time_payment():
    result = calculate_billing(date(2026, 11, 10), 10)
    assert result.next_due_date == date(2026, 12, 10)
    assert result.late_days == 0


def test_late_payment():
    result = calculate_billing(date(2026, 11, 14), 10)
    assert result.next_due_date == date(2026, 12, 10)
    assert result.late_days == 4


def test_due_soon():
    assert classify_status(date(2026, 12, 7), date(2026, 12, 10)) == "DUE_SOON"


def test_february_clamping():
    assert get_anchored_date(2026, 2, 31) == date(2026, 2, 28)
