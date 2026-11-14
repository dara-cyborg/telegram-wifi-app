from datetime import date
from html import escape

import httpx

from app.config import get_settings
from app.services.billing_logic import classify_status


def format_report(tenants: list[dict], today: date) -> str:
    sections = {"OVERDUE": [], "DUE_SOON": [], "PAID": []}
    for tenant in tenants:
        sections[classify_status(today, date.fromisoformat(tenant["next_due_date"]))].append(tenant)
    lines = [f"📅 <b>DAILY INTERNET PAYMENT REPORT</b>", f"🕒 Date: {today:%d %b %Y} (06:00 AM ICT)", "━━━━━━━━━━━━━━━━━━━━"]
    titles = {"OVERDUE": "🚨 <b>NOT PAID / OVERDUE", "DUE_SOON": "⏳ <b>DUE SOON - WITHIN 3 DAYS", "PAID": "✅ <b>PAID THIS MONTH"}
    for status, items in sections.items():
        lines.append(f"{titles[status]} ({len(items)})</b>")
        for item in items:
            lines.append(f"• <b>Room {escape(item['room_number'])}</b> (SSID: <code>{escape(item['ssid'])}</code>)")
            lines.append(f"  └ Next Due: {item['next_due_date']}")
    return "\n".join(lines)


async def send_report(message: str) -> None:
    settings = get_settings()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json={"chat_id": settings.telegram_group_chat_id, "text": message, "parse_mode": "HTML"})
        response.raise_for_status()
