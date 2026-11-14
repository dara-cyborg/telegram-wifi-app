from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlite3 import IntegrityError

from app.auth import verify_admin
from app.config import get_settings
from app.repositories.tenant_repo import create_tenant, delete_tenant, list_tenants, record_payment, update_tenant
from app.schemas import PaymentInput, TenantInput
from app.services.scheduler import build_tenant_views
from app.services.telegram_service import format_report, send_report

router = APIRouter(prefix="/api")


def database_path() -> str:
    return get_settings().database_path


@router.get("/tenants")
async def get_tenants(_: dict = Depends(verify_admin)):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    return build_tenant_views(list_tenants(database_path()), today)


@router.post("/tenants")
async def add_tenant(data: TenantInput, _: dict = Depends(verify_admin)):
    try:
        return create_tenant(database_path(), data)
    except IntegrityError as error:
        raise HTTPException(409, "Room number or MAC address already exists") from error


@router.put("/tenants/{tenant_id}")
async def edit_tenant(tenant_id: int, data: TenantInput, _: dict = Depends(verify_admin)):
    try:
        result = update_tenant(database_path(), tenant_id, data)
    except IntegrityError as error:
        raise HTTPException(409, "Room number or MAC address already exists") from error
    if result is None:
        raise HTTPException(404, "Tenant not found")
    return result


@router.post("/tenants/{tenant_id}/pay")
async def pay_tenant(tenant_id: int, data: PaymentInput, _: dict = Depends(verify_admin)):
    payment_date = data.payment_date or datetime.now(ZoneInfo(get_settings().timezone)).date()
    result = record_payment(database_path(), tenant_id, payment_date)
    if result is None:
        raise HTTPException(404, "Tenant not found")
    return result


@router.delete("/tenants/{tenant_id}")
async def remove_tenant(tenant_id: int, _: dict = Depends(verify_admin)):
    if not delete_tenant(database_path(), tenant_id):
        raise HTTPException(404, "Tenant not found")
    return {"deleted": True}


@router.post("/report/trigger")
async def trigger_report(_: dict = Depends(verify_admin)):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    tenants = build_tenant_views(list_tenants(database_path()), today)
    await send_report(format_report(tenants, today))
    return {"sent": True}
