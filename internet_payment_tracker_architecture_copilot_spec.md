# Project Specification: Telegram Mini App - Internet Payment Tracker

> **Instructions for AI Coding Assistant (GitHub Copilot / Cursor):**
> Read this entire document before generating any code. You must strictly follow the directory structure, coding rules, database schema, and exact date calculation algorithms defined below. Do not over-engineer or introduce heavy frameworks outside of this specification.

---

## 1. Core Coding Philosophy & Rules

1. **"Change One Thing Does Not Break the App" (Strict Decoupling):**
   - **Pure Business Logic:** All date, billing cycle, and status calculations MUST live in a standalone module (`app/services/billing_logic.py`) with **zero** dependencies on FastAPI, SQLite, or Telegram. It takes plain Python data types/dataclasses and returns plain data types.
   - **Database Isolation:** SQL queries and database interactions live strictly in `app/repositories/`. Route handlers must never write raw SQL.
   - **External Services Isolation:** Telegram Bot API calls live strictly in `app/services/telegram_service.py`.
2. **Human-Readable & Maintainable:**
   - Use explicit variable names (`next_due_date`, `days_paid_late`, `tenant_room_number`) instead of abbreviations (`ndd`, `dpl`, `trn`).
   - Add Python type hints (`typing`) to every function signature.
   - Keep functions under 40 lines of code where possible; each function must do one thing well.
3. **Lightweight & Scalable:**
   - No heavy frontend build steps (no Webpack/Vite/React required). Use a single clean HTML file with Tailwind CSS (via CDN) and modular Vanilla JavaScript (`app/static/app.js`).
   - Use **SQLite** in `WAL` (Write-Ahead Logging) mode for fast, concurrency-safe local storage on a basic DigitalOcean Droplet (e.g., $4–$6/mo tier).

---

## 2. Tech Stack & Architecture

- **OS / Hosting:** Ubuntu 24.04 LTS on DigitalOcean Droplet
- **Timezone:** Strictly `Asia/Phnom_Penh` (`UTC+7`) across OS, Python runtime, and scheduler.
- **Backend Framework:** Python 3.11+ with **FastAPI**
- **Database:** **SQLite3** (using standard library `sqlite3` with `Row` factory or `SQLModel`—prefer lightweight standard `sqlite3` with Pydantic schemas for zero-ORM magic).
- **Task Scheduler:** **APScheduler** (`AsyncIOScheduler`) running inside the FastAPI lifespan context, triggered daily at `06:00:00` (`Asia/Phnom_Penh`).
- **Telegram Integration:**
  - **Mini App Auth:** HMAC-SHA256 validation of `window.Telegram.WebApp.initData` coupled with an `ADMIN_TELEGRAM_ID` whitelist.
  - **Group Notifications:** Direct async HTTP requests via `httpx` to `https://api.telegram.org/bot<TOKEN>/sendMessage`.
- **Reverse Proxy:** **Caddy** (for automatic HTTPS, required by Telegram Mini Apps).

---

## 3. Project Directory Structure

```text
internet-payment-tracker/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── Caddyfile
├── systemd/
│   └── payment-tracker.service
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI entry point, lifespan scheduler setup, static mounts
│   ├── config.py                # Env vars validation (Pydantic BaseSettings)
│   ├── database.py              # SQLite connection helper & schema initialization
│   ├── auth.py                  # Telegram initData HMAC validation & Admin ID check
│   ├── schemas.py               # Pydantic models for API request/response validation
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── tenant_repo.py       # CRUD operations for rooms, tenants, devices, payments
│   ├── services/
│   │   ├── __init__.py
│   │   ├── billing_logic.py     # PURE PYTHON: Date anchoring, status, & late remark calculations
│   │   ├── telegram_service.py  # Formats & sends the 6:00 AM Telegram group report
│   │   └── scheduler.py         # APScheduler job definitions
│   ├── routers/
│   │   ├── __init__.py
│   │   └── api.py               # REST API endpoints for the Mini App
│   └── static/
│       ├── index.html           # Admin Mini App UI (Tailwind CSS + Telegram WebApp SDK)
│       └── app.js               # Frontend state, API fetch wrapper, UI rendering
└── tests/
    ├── __init__.py
    └── test_billing_logic.py    # Unit tests for edge cases (leap years, Feb 28/30/31, late remarks)
```

---

## 4. Database Schema (SQLite)

Because a single room can have multiple registered MAC addresses, we normalize `tenants` (rooms) and `devices` (MAC addresses), plus a `payment_logs` table for auditability.

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- 1. Tenants / Rooms Table
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_number TEXT NOT NULL UNIQUE,         -- e.g., "101", "204A"
    ssid TEXT NOT NULL,                       -- e.g., "TP-Link_Room101"
    due_day INTEGER NOT NULL CHECK (due_day >= 1 AND due_day <= 31),
    last_payment_date TEXT NOT NULL,          -- ISO-8601 Date: "YYYY-MM-DD" (e.g., "2026-11-10")
    last_paid_for_due_date TEXT NOT NULL,     -- ISO-8601 Date: The cycle due date that last_payment_date settled (e.g., "2026-11-10")
    late_days_remark INTEGER NOT NULL DEFAULT 0, -- Stores X days if the last payment was paid late (0 if on time/early)
    is_active INTEGER NOT NULL DEFAULT 1,     -- 1 = active, 0 = archived/moved out
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 2. Devices Table (1-to-Many with Tenants)
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    mac_address TEXT NOT NULL UNIQUE,         -- Standardized uppercase format: "AA:BB:CC:DD:EE:FF"
    device_label TEXT DEFAULT '',             -- Optional: e.g., "iPhone", "Laptop"
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

-- 3. Payment History Log (Audit Trail)
CREATE TABLE IF NOT EXISTS payment_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    payment_date TEXT NOT NULL,               -- Actual date paid ("YYYY-MM-DD")
    covered_due_date TEXT NOT NULL,           -- The anchored due date this payment covered ("YYYY-MM-DD")
    days_late INTEGER NOT NULL DEFAULT 0,     -- >0 if payment_date > covered_due_date
    recorded_at TEXT NOT NULL,                -- Full ISO timestamp in Asia/Phnom_Penh
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
```

---

## 5. Exact Business Logic & Date Rules (`billing_logic.py`)

All date operations MUST use `zoneinfo.ZoneInfo("Asia/Phnom_Penh")`.

### Rule 5.1: Clamping Due Day to Valid Calendar Date
If a user's `due_day` is `31`, and the target month only has `28`, `29`, or `30` days, the due date snaps to the last day of that month using `calendar.monthrange(year, month)[1]`.

```python
import calendar
from datetime import date

def get_anchored_date(year: int, month: int, due_day: int) -> date:
    """Returns a valid date in the given year/month anchored to due_day."""
    max_day = calendar.monthrange(year, month)[1]
    actual_day = min(due_day, max_day)
    return date(year, month, actual_day)
```

### Rule 5.2: Anchored Next Due Date & Late Payment Remark
- Every tenant has an anchored `due_day` (e.g., `10`).
- We track `last_paid_for_due_date` (the cycle date their last payment settled) and `last_payment_date` (the actual calendar date they handed over the money).
- **Example Scenario (Anchored to the 10th):**
  - Tenant owes for `2026-11-10`.
  - Tenant pays late on `2026-11-14`.
  - When Admin marks as paid for the `2026-11-10` cycle on `2026-11-14`:
    1. `last_payment_date` = `"2026-11-14"`
    2. `last_paid_for_due_date` = `"2026-11-10"`
    3. `late_days_remark` = `(2026-11-14 - 2026-11-10).days` = `4` (Remark: *"Paid late by 4 days on 14 Nov 2026"*).
    4. **`next_due_date`** is strictly calculated as `last_paid_for_due_date + 1 month` anchored to `due_day` -> **`2026-12-10`**.
- **Initial Tenant Creation:**
  - When Admin creates a new tenant and inputs `due_day = 10` and `last_payment_date = 2026-11-14`:
  - The system determines the cycle due date that payment belonged to (the most recent occurrence of `due_day` on or before `last_payment_date`, or the current month's `due_day` if paid a few days early).
  - Specifically:
    - Let `candidate_due = get_anchored_date(last_payment_date.year, last_payment_date.month, due_day)`.
    - If `last_payment_date >= candidate_due`:
      - `covered_due_date = candidate_due`
      - `late_days_remark = (last_payment_date - covered_due_date).days`
    - Else (if paid early in the same month, e.g., paid on Nov 8 for Nov 10 due date, OR paid late in the next month):
      - If `(candidate_due - last_payment_date).days <= 7`: (Paid up to 7 days early for this month's cycle)
        - `covered_due_date = candidate_due`
        - `late_days_remark = 0`
      - Else: (Paid in a new month for the *previous* month's cycle, e.g., due day is 28th, paid on Dec 2nd for Nov 28th)
        - `prev_month_due = subtract_one_month(candidate_due, due_day)`
        - `covered_due_date = prev_month_due`
        - `late_days_remark = (last_payment_date - covered_due_date).days`
  - Then, `next_due_date = add_one_month(covered_due_date, due_day)`.

### Rule 5.3: Classification Categories (Evaluated Daily at 6:00 AM)
Given `today` (in `Asia/Phnom_Penh`) and a tenant's `next_due_date`, `last_payment_date`, and `late_days_remark`:

Let `days_until_due = (next_due_date - today).days`.

1. **UNPAID / OVERDUE (`OVERDUE`):**
   - Condition: `days_until_due < 0` (or `days_until_due == 0`, i.e., due today and not yet paid for today's cycle).
   - Overdue by: `abs(days_until_due)` days.
2. **DUE SOON (`DUE_SOON`):**
   - Condition: `1 <= days_until_due <= 3` (Strictly within 3 days before due date).
   - Note: You can also include `days_until_due == 0` under "Due Today / Action Needed" inside the Unpaid or Due Soon section so it's never missed. Let's group:
     - `days_until_due < 0`: **Overdue (Not Paid)**
     - `0 <= days_until_due <= 3`: **Due Soon (3 Days Warning / Due Today)**
3. **PAID WITHIN THE MONTH (`PAID`):**
   - Condition: Tenant is currently up-to-date (`days_until_due > 0`) AND their `last_payment_date` falls within the current billing window (within the last ~31 days / current calendar month cycle).
   - Note: A tenant who paid on `20 Nov 2026` (next due `20 Dec 2026`) will appear in the **Paid** list, and during `17 Dec – 19 Dec` will *also* be highlighted in **Due Soon**.
   - Display Remark: If `late_days_remark > 0`, append `(Paid X days late on DD Mon)` next to their entry.

---

## 6. Daily 6:00 AM Telegram Group Message Format

Every day at `06:00` (`Asia/Phnom_Penh`), the bot sends an HTML-formatted message to `TELEGRAM_GROUP_CHAT_ID`:

```html
📅 <b>DAILY INTERNET PAYMENT REPORT</b>
🕒 Date: 14 Nov 2026 (06:00 AM ICT)
━━━━━━━━━━━━━━━━━━━━

🚨 <b>NOT PAID / OVERDUE (1)</b>
• <b>Room 102</b> (SSID: <code>Net_102</code>)
  └ Due: 10 Nov 2026 (<b>4 days overdue</b>)
  └ MACs: <code>AA:BB:CC:11:22:33</code>

⏳ <b>DUE SOON - WITHIN 3 DAYS (1)</b>
• <b>Room 105</b> (SSID: <code>Net_105</code>)
  └ Next Due: 17 Nov 2026 (<b>in 3 days</b>)

✅ <b>PAID THIS MONTH (2)</b>
• <b>Room 101</b> — Paid: 10 Nov 2026 (On time)
  └ Next Due: 10 Dec 2026
• <b>Room 103</b> — Paid: 14 Nov 2026 (<i>Late by 4 days</i>)
  └ Next Due: 10 Dec 2026
```

---

## 7. Security: Admin-Only Telegram Mini App Authentication

Since **only the Admin** uses this Mini App:
1. The Frontend loads `https://telegram.org/js/telegram-web-app.js` and sends `window.Telegram.WebApp.initData` in the `Authorization: tma <initData>` HTTP header on every API request.
2. In `app/auth.py`:
   - Verify the cryptographic signature of `initData` using `TELEGRAM_BOT_TOKEN` per Telegram's official WebApp validation algorithm.
   - Extract the `user.id` from the validated payload.
   - Compare `user.id == settings.ADMIN_TELEGRAM_ID`.
   - If the signature is invalid or `user.id` does not match `ADMIN_TELEGRAM_ID`, immediately raise `HTTPException(status_code=403, detail="Unauthorized: Admin access only")`.
   - Include a `DEV_MODE=false` toggle in `.env` solely for local browser testing during development.

---

## 8. REST API Endpoints (`app/routers/api.py`)

All endpoints require the Admin Auth dependency (`Depends(verify_admin)`):

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/tenants` | Lists all active tenants with their devices, calculated `next_due_date`, `status` (`OVERDUE`, `DUE_SOON`, `PAID`), and `late_days_remark`. |
| `POST` | `/api/tenants` | Creates a new tenant room + list of MAC addresses + `due_day` + `last_payment_date`. |
| `PUT` | `/api/tenants/{tenant_id}` | Updates room number, SSID, `due_day`, `last_payment_date`, or replaces/updates the list of MAC addresses. |
| `POST` | `/api/tenants/{tenant_id}/pay` | Quick action: Marks the current due cycle as paid on a given `payment_date` (defaults to today in Phnom Penh), calculates if late, logs to `payment_logs`, and advances `last_paid_for_due_date`. |
| `DELETE` | `/api/tenants/{tenant_id}` | Deletes (or soft-deletes) a tenant room and its MAC addresses. |
| `POST` | `/api/report/trigger` | Manually triggers the 6:00 AM Telegram group report immediately (useful for testing from the Mini App UI). |

---

## 9. Frontend UI Specification (`app/static/index.html` & `app.js`)

Build a clean, mobile-first single-page interface tailored for Telegram Mini Apps:
1. **Top Summary Bar:**
   - Displays Current Phnom Penh Date.
   - 3 Filter/Stat Pills: `All`, `Overdue (Red)`, `Due Soon (Amber)`, `Paid (Green)`.
   - Button: **"Send Group Report Now"** (calls `POST /api/report/trigger`).
2. **Tenant Cards List:**
   - Each card shows:
     - **Header:** `Room {room_number}` + Status Badge (`OVERDUE`, `DUE IN X DAYS`, or `PAID`).
     - **Details:**
       - `SSID`: `{ssid}`
       - `MAC Addresses`: Expandable or pill list of all MACs for that room (with one-tap copy).
       - `Due Day`: Every `{due_day}` of the month.
       - `Last Payment`: `{last_payment_date}` (with a yellow badge `"Paid X days late"` if `late_days_remark > 0`).
       - `Next Expected Payment`: **`{next_due_date}`**
     - **Actions:**
       - **"Mark Paid"** button (opens a small modal pre-filled with today's date `YYYY-MM-DD`, allowing Admin to confirm or pick an exact date).
       - **"Edit"** button (allows editing Room, SSID, Due Day, Last Payment Date, and adding/removing MAC inputs dynamically).
3. **Add/Edit Modal:**
   - Inputs:
     - `Room Number` (Text, required)
     - `SSID` (Text, required)
     - `Due Day` (Number `1-31`, required)
     - `Last Payment Date` (Date picker `YYYY-MM-DD`, required)
     - `MAC Addresses` (Dynamic list of inputs with `+ Add Another MAC` button and regex validation for `^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$`).

---

## 10. Environment Variables (`.env.example`)

```ini
# Telegram Configuration
TELEGRAM_BOT_TOKEN=123456789:ABCDEF_your_bot_token_here
TELEGRAM_GROUP_CHAT_ID=-1001234567890
ADMIN_TELEGRAM_ID=987654321

# App & Database Configuration
TIMEZONE=Asia/Phnom_Penh
DATABASE_PATH=./data/tracker.db
DEV_MODE=false
PORT=8000
```

---

## 11. Step-by-Step Implementation Plan for Copilot

Follow these exact steps in order when generating the codebase:

1. **Step 1: Configuration & Pure Billing Logic**
   - Create `requirements.txt` (`fastapi`, `uvicorn[standard]`, `pydantic-settings`, `apscheduler`, `httpx`, `pytest`).
   - Create `app/config.py` and `app/services/billing_logic.py`.
   - Create `tests/test_billing_logic.py` and verify:
     - Payment on `2026-11-10` with `due_day=10` -> `next_due_date = 2026-12-10`, `late_days = 0`.
     - Payment on `2026-11-14` for `2026-11-10` cycle (`due_day=10`) -> `next_due_date = 2026-12-10`, `late_days = 4`.
     - Due date within 3 days (`today = 2026-12-07`, `next_due = 2026-12-10`) -> status is `DUE_SOON`.
     - End-of-month clamping (`due_day=31` in Feb 2026 -> `2026-02-28`).
2. **Step 2: SQLite Database & Repository Layer**
   - Create `app/database.py` and `app/schemas.py`.
   - Create `app/repositories/tenant_repo.py` handling multi-MAC insertions/updates inside atomic SQLite transactions.
3. **Step 3: Telegram Service & Daily 6:00 AM Scheduler**
   - Create `app/services/telegram_service.py` to format the daily summary and send via `httpx`.
   - Create `app/services/scheduler.py` with `CronTrigger(hour=6, minute=0, timezone="Asia/Phnom_Penh")`.
4. **Step 4: Security & FastAPI Routes**
   - Create `app/auth.py` for Telegram WebApp HMAC validation + `ADMIN_TELEGRAM_ID` check.
   - Create `app/routers/api.py` and wire everything in `app/main.py`.
5. **Step 5: Lightweight Frontend (Mini App)**
   - Create `app/static/index.html` and `app/static/app.js`.
6. **Step 6: DigitalOcean Deployment Files**
   - Create `systemd/payment-tracker.service` and `Caddyfile`.

---

## 12. DigitalOcean Droplet Deployment Guide

1. **Provision Droplet:**
   - Ubuntu 24.04 LTS ($4 or $6/month Basic Droplet).
   - Point a domain or subdomain (e.g., `tracker.yourdomain.com`) to the Droplet's IP via an `A` record (Telegram Mini Apps require HTTPS).
2. **Set Server Timezone:**
   ```bash
   sudo timedatectl set-timezone Asia/Phnom_Penh
   ```
3. **Install Dependencies & Caddy:**
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv caddy sqlite3
   ```
4. **Setup Application:**
   ```bash
   git clone <your-repo> /opt/internet-payment-tracker
   cd /opt/internet-payment-tracker
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   mkdir -p data
   cp .env.example .env && nano .env
   ```
5. **Configure Systemd Service (`/etc/systemd/system/payment-tracker.service`):**
   ```ini
   [Unit]
   Description=Telegram Mini App Internet Payment Tracker
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/opt/internet-payment-tracker
   EnvironmentFile=/opt/internet-payment-tracker/.env
   ExecStart=/opt/internet-payment-tracker/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   *(Note: Keep `--workers 1` so the embedded `APScheduler` runs exactly one instance and sends only one message at 6:00 AM).*
6. **Configure Caddy (`/etc/caddy/Caddyfile`):**
   ```caddyfile
   tracker.yourdomain.com {
       reverse_proxy 127.0.0.1:8000
   }
   ```
7. **Register Mini App with `@BotFather`:**
   - Message `@BotFather` -> `/newapp` or `/mybots` -> Select Bot -> **Bot Settings** -> **Menu Button** -> Paste `https://tracker.yourdomain.com`.