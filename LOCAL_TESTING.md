# Local testing guide

This guide runs the application on a development machine without Telegram
credentials, Caddy, or a public HTTPS endpoint.

## 1. Requirements

- Python 3.11 or newer
- Git
- PowerShell on Windows or a POSIX-compatible shell

Run all commands from the repository root.

## 2. Create the virtual environment

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Linux or macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Use the virtual-environment interpreter for every command. Do not install the
project dependencies with global `pip`.

## 3. Configure local settings

Copy the example environment file:

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### Linux or macOS

```bash
cp .env.example .env
```

For browser testing, update `.env`:

```ini
TELEGRAM_BOT_TOKEN=local-test-token
TELEGRAM_GROUP_CHAT_ID=local-test-group
ADMIN_TELEGRAM_ID=1
TIMEZONE=Asia/Phnom_Penh
DATABASE_PATH=./data/test-tracker.db
DEV_MODE=true
PORT=8001
```

`DEV_MODE=true` bypasses Telegram authentication only when the request has no
authorization header. Never use it on a public or production server.

## 4. Run automated tests

### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app tests
```

### Linux or macOS

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app tests
```

The billing tests cover:

- On-time payment
- Late payment and late-day calculation
- Due-soon classification
- February end-of-month clamping

## 5. Start the local server

Initialize the local database:

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe -c "from app.database import initialize_database; initialize_database('./data/test-tracker.db')"
```

Start FastAPI:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

### Linux or macOS

```bash
mkdir -p data
.venv/bin/python -c "from app.database import initialize_database; initialize_database('./data/test-tracker.db')"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

Keep the server terminal open. Stop it with `Ctrl+C`.

Open <http://127.0.0.1:8001/> in a browser. In local development, the frontend
will load without a Telegram authorization header because `DEV_MODE=true`.

## 6. Test the API

Use a second terminal.

### List tenants

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/tenants
```

### Create a tenant

PowerShell:

```powershell
$body = @{
  room_number = "101"
  ssid = "Net_101"
  due_day = 10
  last_payment_date = "2026-11-10"
  mac_addresses = @("AA:BB:CC:11:22:33")
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8001/api/tenants `
  -Method Post -ContentType "application/json" -Body $body
```

### Mark the tenant paid

```powershell
$body = @{ payment_date = "2026-11-14" } | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8001/api/tenants/1/pay `
  -Method Post -ContentType "application/json" -Body $body
```

### Delete the tenant

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/tenants/1 `
  -Method Delete
```

The API uses the local database configured by `DATABASE_PATH`.

## 7. Test frontend behavior

From the browser:

1. Confirm the tenant list loads.
2. Confirm filter pills update the visible list.
3. Confirm **Mark Paid** advances the payment data.
4. Confirm the next due date is displayed.
5. Confirm invalid requests return an error instead of being silently accepted.

The current frontend does not provide the full add/edit modal workflow. Create
and edit tenant records through the API commands above.

## 8. Test Telegram authentication

Set `DEV_MODE=false` in `.env`, restart the server, and call:

```powershell
Invoke-WebRequest http://127.0.0.1:8001/api/tenants -UseBasicParsing
```

The request should return HTTP `403` without a valid Telegram `initData`
header. Restore `DEV_MODE=true` for ordinary local browser testing.

Do not use a fabricated Telegram signature to test authorization. Use a real
Telegram Mini App launch only when testing against a configured bot and HTTPS
environment.

## 9. Test report formatting without sending Telegram messages

Run the formatter directly:

```powershell
.\.venv\Scripts\python.exe -c "from datetime import date; from app.services.telegram_service import format_report; print(format_report([], date(2026, 11, 14)))"
```

The manual report endpoint sends a real Telegram message. Do not call
`POST /api/report/trigger` unless the configured bot token and group chat ID
are intended for testing.

## 10. Reset local test data

Stop the server first, then remove only the local test database:

### Windows PowerShell

```powershell
Remove-Item .\data\test-tracker.db -Force -ErrorAction SilentlyContinue
```

### Linux or macOS

```bash
rm -f data/test-tracker.db
```

Re-run database initialization before starting the server again.

## 11. Troubleshooting

Check that the venv is being used:

### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
```

### Linux or macOS

```bash
.venv/bin/python -c "import sys; print(sys.executable)"
```

If dependencies are missing, install them inside `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If port `8001` is occupied, use another port and update `PORT`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1
```
