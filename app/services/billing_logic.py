import calendar
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BillingResult:
    covered_due_date: date
    next_due_date: date
    late_days: int


def get_anchored_date(year: int, month: int, due_day: int) -> date:
    return date(year, month, min(due_day, calendar.monthrange(year, month)[1]))


def add_one_month(value: date, due_day: int) -> date:
    month = value.month + 1
    year = value.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return get_anchored_date(year, month, due_day)


def subtract_one_month(value: date, due_day: int) -> date:
    month = value.month - 1
    year = value.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return get_anchored_date(year, month, due_day)


def determine_covered_due_date(payment_date: date, due_day: int) -> tuple[date, int]:
    candidate = get_anchored_date(payment_date.year, payment_date.month, due_day)
    if payment_date >= candidate:
        covered = candidate
    elif (candidate - payment_date).days <= 7:
        covered = candidate
    else:
        covered = subtract_one_month(candidate, due_day)
    return covered, max(0, (payment_date - covered).days)


def calculate_billing(payment_date: date, due_day: int) -> BillingResult:
    covered, late_days = determine_covered_due_date(payment_date, due_day)
    return BillingResult(covered, add_one_month(covered, due_day), late_days)


def classify_status(today: date, next_due_date: date) -> str:
    days_until_due = (next_due_date - today).days
    if days_until_due < 0:
        return "OVERDUE"
    if days_until_due <= 3:
        return "DUE_SOON"
    return "PAID"
