from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.repositories.tenant_repo import list_tenants
from app.services.telegram_service import format_report, send_report


async def daily_report(database_path: str) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    tenants = build_tenant_views(list_tenants(database_path), today)
    await send_report(format_report(tenants, today))


def build_tenant_views(tenants: list[dict], today):
    from datetime import date
    from app.services.billing_logic import add_one_month, classify_status
    for tenant in tenants:
        due = date.fromisoformat(tenant["last_paid_for_due_date"])
        next_due = add_one_month(due, tenant["due_day"])
        tenant["next_due_date"] = next_due.isoformat()
        tenant["status"] = classify_status(today, next_due)
        tenant["days_until_due"] = (next_due - today).days
    priority = {"OVERDUE": 0, "DUE_SOON": 1, "PAID": 2}
    return sorted(
        tenants,
        key=lambda tenant: (
            priority[tenant["status"]],
            tenant["days_until_due"] if tenant["status"] != "PAID" else 0,
            tenant["room_number"].casefold(),
        ),
    )


def configure_scheduler(scheduler, database_path: str) -> None:
    scheduler.add_job(daily_report, CronTrigger(hour=6, minute=0, timezone=get_settings().timezone), args=[database_path], id="daily-report", replace_existing=True)
