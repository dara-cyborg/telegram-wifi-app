import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS tenants (
 id INTEGER PRIMARY KEY AUTOINCREMENT, room_number TEXT NOT NULL UNIQUE,
 ssid TEXT NOT NULL, due_day INTEGER NOT NULL CHECK(due_day BETWEEN 1 AND 31),
 last_payment_date TEXT NOT NULL, last_paid_for_due_date TEXT NOT NULL,
 late_days_remark INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 mac_address TEXT NOT NULL UNIQUE, device_label TEXT DEFAULT '', created_at TEXT NOT NULL,
 FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS payment_logs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 payment_date TEXT NOT NULL, covered_due_date TEXT NOT NULL, days_late INTEGER NOT NULL DEFAULT 0,
 recorded_at TEXT NOT NULL, FOREIGN KEY(tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
"""


def initialize_database(path: str) -> None:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA)


@contextmanager
def get_connection(path: str) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
