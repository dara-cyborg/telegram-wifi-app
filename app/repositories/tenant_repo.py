from datetime import datetime

from app.database import get_connection
from app.schemas import TenantInput
from app.services.billing_logic import calculate_billing


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _row(connection, tenant_id: int):
    row = connection.execute(
        "SELECT * FROM tenants WHERE id = ? AND is_active = 1", (tenant_id,)
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["mac_addresses"] = [
        item["mac_address"] for item in connection.execute(
            "SELECT mac_address FROM devices WHERE tenant_id = ? ORDER BY id", (tenant_id,)
        ).fetchall()
    ]
    return result


def list_tenants(path: str) -> list[dict]:
    with get_connection(path) as connection:
        ids = connection.execute("SELECT id FROM tenants WHERE is_active = 1 ORDER BY room_number").fetchall()
        return [_row(connection, item["id"]) for item in ids]


def create_tenant(path: str, data: TenantInput) -> dict:
    billing = calculate_billing(data.last_payment_date, data.due_day)
    now = _now()
    with get_connection(path) as connection:
        cursor = connection.execute(
            """INSERT INTO tenants
            (room_number, ssid, due_day, last_payment_date, last_paid_for_due_date,
             late_days_remark, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data.room_number, data.ssid, data.due_day, data.last_payment_date.isoformat(),
             billing.covered_due_date.isoformat(), billing.late_days, now, now),
        )
        tenant_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO devices (tenant_id, mac_address, created_at) VALUES (?, ?, ?)",
            [(tenant_id, mac, now) for mac in data.mac_addresses],
        )
        return _row(connection, tenant_id)


def update_tenant(path: str, tenant_id: int, data: TenantInput) -> dict | None:
    billing = calculate_billing(data.last_payment_date, data.due_day)
    with get_connection(path) as connection:
        if _row(connection, tenant_id) is None:
            return None
        connection.execute(
            """UPDATE tenants SET room_number=?, ssid=?, due_day=?, last_payment_date=?,
            last_paid_for_due_date=?, late_days_remark=?, updated_at=? WHERE id=?""",
            (data.room_number, data.ssid, data.due_day, data.last_payment_date.isoformat(),
             billing.covered_due_date.isoformat(), billing.late_days, _now(), tenant_id),
        )
        connection.execute("DELETE FROM devices WHERE tenant_id=?", (tenant_id,))
        connection.executemany(
            "INSERT INTO devices (tenant_id, mac_address, created_at) VALUES (?, ?, ?)",
            [(tenant_id, mac, _now()) for mac in data.mac_addresses],
        )
        return _row(connection, tenant_id)


def record_payment(path: str, tenant_id: int, payment_date) -> dict | None:
    with get_connection(path) as connection:
        current = _row(connection, tenant_id)
        if current is None:
            return None
        billing = calculate_billing(payment_date, current["due_day"])
        now = _now()
        connection.execute(
            """UPDATE tenants SET last_payment_date=?, last_paid_for_due_date=?,
            late_days_remark=?, updated_at=? WHERE id=?""",
            (payment_date.isoformat(), billing.covered_due_date.isoformat(),
             billing.late_days, now, tenant_id),
        )
        connection.execute(
            """INSERT INTO payment_logs
            (tenant_id, payment_date, covered_due_date, days_late, recorded_at)
            VALUES (?, ?, ?, ?, ?)""",
            (tenant_id, payment_date.isoformat(), billing.covered_due_date.isoformat(),
             billing.late_days, now),
        )
        return _row(connection, tenant_id)


def delete_tenant(path: str, tenant_id: int) -> bool:
    with get_connection(path) as connection:
        result = connection.execute("UPDATE tenants SET is_active=0, updated_at=? WHERE id=? AND is_active=1",
                                    (_now(), tenant_id))
        return result.rowcount == 1
