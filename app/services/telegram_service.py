from datetime import date
from html import escape

import httpx

from app.config import get_settings


def _room_name(tenant: dict) -> str:
    return escape(str(tenant["room_number"]))


def format_daily_report(tenants: list[dict], today: date) -> str:
    overdue: list[dict] = []
    due_soon: list[dict] = []
    paid: list[dict] = []

    for tenant in tenants:
        days_until_due = (
            date.fromisoformat(tenant["next_due_date"]) - today
        ).days
        tenant_with_days = {**tenant, "days_until_due": days_until_due}
        if days_until_due <= 0:
            overdue.append(tenant_with_days)
        elif days_until_due <= 3:
            due_soon.append(tenant_with_days)
        else:
            paid.append(tenant_with_days)

    overdue.sort(key=lambda tenant: tenant["days_until_due"])
    due_soon.sort(key=lambda tenant: tenant["days_until_due"])
    paid.sort(key=lambda tenant: _room_name(tenant))

    lines = [
        f"🕒 {today:%d/%m/%y}",
        "",
        f"🔴 <b>មិនទាន់បង់ ({len(overdue)})</b>",
    ]
    lines.extend(_format_alert_line(tenant) for tenant in overdue)
    if not overdue:
        lines.append("• គ្មាន")

    if due_soon:
        lines.extend(
            [
                "",
                f"🟡 <b>ជិតដល់ថ្ងៃបង់ ({len(due_soon)})</b>",
            ]
        )
        lines.extend(_format_alert_line(tenant) for tenant in due_soon)

    lines.extend(
        [
            "",
            f"🟢 <b>បង់ហើយ ({len(paid)})</b>",
        ]
    )
    lines.extend(
        f"• Room {_room_name(tenant)} បង់ហើយថ្ងៃទី "
        f"{date.fromisoformat(tenant['last_payment_date']):%d/%m/%y}"
        for tenant in paid
    )
    if not paid:
        lines.append("• គ្មាន")
    return "\n".join(lines)


def _format_alert_line(tenant: dict) -> str:
    room = _room_name(tenant)
    days_until_due = tenant["days_until_due"]
    if days_until_due < 0:
        return f"• Room {room} លើស {abs(days_until_due)} ថ្ងៃ"
    if days_until_due == 0:
        return f"• Room {room} ត្រូវបង់ថ្ងៃនេះ"
    return f"• Room {room} សល់ {days_until_due} ថ្ងៃទៀតដល់ថ្ងៃបង់"


def format_report(tenants: list[dict], today: date) -> str:
    return format_daily_report(tenants, today)


async def send_report(message: str) -> None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            url,
            json={
                "chat_id": settings.telegram_group_chat_id,
                "text": message,
                "parse_mode": "HTML",
            },
        )
        response.raise_for_status()
