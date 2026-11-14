from datetime import date, timedelta

from app.services.telegram_service import format_daily_report


TODAY = date(2026, 11, 14)


def tenant(days_until_due: int, room_number: str = "100") -> dict:
    return {
        "room_number": room_number,
        "next_due_date": (TODAY + timedelta(days=days_until_due)).isoformat(),
        "last_payment_date": "2026-11-14",
    }


def test_countdown_and_overdue_lines():
    message = format_daily_report(
        [tenant(3), tenant(2), tenant(1), tenant(0), tenant(-1), tenant(-5)],
        TODAY,
    )
    assert "Room 100 សល់ 3 ថ្ងៃទៀតដល់ថ្ងៃបង់" in message
    assert "Room 100 សល់ 2 ថ្ងៃទៀតដល់ថ្ងៃបង់" in message
    assert "Room 100 សល់ 1 ថ្ងៃទៀតដល់ថ្ងៃបង់" in message
    assert "Room 100 ត្រូវបង់ថ្ងៃនេះ" in message
    assert "Room 100 លើស 1 ថ្ងៃ" in message
    assert "Room 100 លើស 5 ថ្ងៃ" in message


def test_paid_line_and_removed_metadata():
    message = format_daily_report([tenant(20)], TODAY)
    assert "Room 100 បង់ហើយថ្ងៃទី 14/11/26" in message
    assert "SSID" not in message
    assert "MAC" not in message
    assert "Next Due" not in message


def test_sections_are_sorted_and_empty_sections_are_minimal():
    message = format_daily_report([tenant(-1, "102"), tenant(-5, "101"), tenant(20, "103")], TODAY)
    assert message.index("Room 101 លើស 5 ថ្ងៃ") < message.index("Room 102 លើស 1 ថ្ងៃ")
    assert "🟡" not in message
    assert "🔴 <b>មិនទាន់បង់ (2)</b>" in message
    assert "🟢 <b>បង់ហើយ (1)</b>" in message
