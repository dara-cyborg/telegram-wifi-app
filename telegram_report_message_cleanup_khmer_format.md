# Fix Specification: Clean & Minimal Telegram Daily Report (Khmer Format)

> **Instructions for AI Coding Assistant (GitHub Copilot / Cursor):**
> Refactor the daily Telegram report formatting in `app/services/telegram_service.py` so the message is clean, concise, and easy to scan at a glance.
>
> **Core Rule:** *"Change one thing does not break the app."*
> Do **not** alter the database schema, frontend UI, or API contracts. Only update the message formatter in `app/services/telegram_service.py` (and add unit tests in `tests/test_telegram_service.py` to verify the exact output).

---

## 1. What to Remove (De-Clutter)

Remove all noisy technical metadata from the Telegram group message:
- **DO NOT** include `SSID`
- **DO NOT** include `MACs`
- **DO NOT** include `Due day: X`
- **DO NOT** include `Next Due: YYYY-MM-DD`
- **DO NOT** show clutter lines for empty categories if a section has 0 items (or keep it minimal).

---

## 2. Exact Alert Lifecycle & Khmer Line Templates

For every active tenant evaluated against `today` (in `Asia/Phnom_Penh`), let:
- `days_until_due = (next_due_date - today).days`
- `paid_date_str = last_payment_date.strftime("%d/%m/%y")` (strictly `DD/MM/YY`, e.g., `14/11/26`)

The daily 6:00 AM report must alert continuously every day from **3 days before due** all the way through **due today** and **overdue** until the Admin marks the tenant as paid (which advances `next_due_date` to the following month):

| `days_until_due` | Category | Exact Line Format (Khmer) | Example |
| :--- | :--- | :--- | :--- |
| `< 0` (e.g., `-1`, `-2`, `-4`) | **មិនទាន់បង់** (Overdue) | `• Room {room_number} លើស {abs(days_until_due)} ថ្ងៃ` | `• Room 100 លើស 4 ថ្ងៃ` |
| `== 0` | **មិនទាន់បង់** (Due Today) | `• Room {room_number} ត្រូវបង់ថ្ងៃនេះ` | `• Room 100 ត្រូវបង់ថ្ងៃនេះ` |
| `1`, `2`, or `3` | **ជិតដល់ថ្ងៃបង់** (Due Soon) | `• Room {room_number} សល់ {days_until_due} ថ្ងៃទៀតដល់ថ្ងៃបង់` | `• Room 100 សល់ 3 ថ្ងៃទៀតដល់ថ្ងៃបង់` |
| `> 3` (Paid for current cycle) | **បង់ហើយ** (Paid) | `• Room {room_number} បង់ហើយថ្ងៃទី {DD/MM/YY}` | `• Room 100 បង់ហើយថ្ងៃទី 14/11/26` |

### Important Edge Case Rules:
1. **Continuous Countdown Until Paid:**
   - 3 days before due (`days_until_due == 3`) → `Room 100 សល់ 3 ថ្ងៃទៀតដល់ថ្ងៃបង់`
   - 2 days before due (`days_until_due == 2`) → `Room 100 សល់ 2 ថ្ងៃទៀតដល់ថ្ងៃបង់`
   - 1 day before due (`days_until_due == 1`) → `Room 100 សល់ 1 ថ្ងៃទៀតដល់ថ្ងៃបង់`
   - On due date (`days_until_due == 0`) → `Room 100 ត្រូវបង់ថ្ងៃនេះ`
   - 1 day past due (`days_until_due == -1`) → `Room 100 លើស 1 ថ្ងៃ`
   - 2 days past due (`days_until_due == -2`) → `Room 100 លើស 2 ថ្ងៃ`
   - ...continues every morning at 6:00 AM until marked paid.
2. **No Duplicate Entries in the Same Message:**
   - Once a tenant enters the 3-day countdown (`days_until_due <= 3`), they appear under the alert section (**ជិតដល់ថ្ងៃបង់** or **មិនទាន់បង់**) so they are not duplicated in **បង់ហើយ** for the same message.
   - As soon as the Admin marks them as paid, `next_due_date` moves to next month (`days_until_due > 3`), and the next morning they automatically move cleanly into **បង់ហើយ** with `Room {room_number} បង់ហើយថ្ងៃទី {DD/MM/YY}`.
3. **Sorting Within Each Section:**
   - **មិនទាន់បង់:** Sort by `days_until_due` ascending (most overdue at the top, then due today).
   - **ជិតដល់ថ្ងៃបង់:** Sort by `days_until_due` ascending (`1` day left, then `2`, then `3`).
   - **បង់ហើយ:** Sort by `room_number` ascending.

---

## 3. Exact Telegram Message Layout (HTML Parse Mode)

Use clean blank lines between sections for mobile readability:

```html
📅 <b>របាយការណ៍បង់ថ្លៃអ៊ីនធឺណិត</b>
🕒 14/11/26

🔴 <b>មិនទាន់បង់ (2)</b>
• Room 100 លើស 4 ថ្ងៃ
• Room 102 ត្រូវបង់ថ្ងៃនេះ

🟡 <b>ជិតដល់ថ្ងៃបង់ (2)</b>
• Room 105 សល់ 1 ថ្ងៃទៀតដល់ថ្ងៃបង់
• Room 108 សល់ 3 ថ្ងៃទៀតដល់ថ្ងៃបង់

🟢 <b>បង់ហើយ (2)</b>
• Room 101 បង់ហើយថ្ងៃទី 10/11/26
• Room 103 បង់ហើយថ្ងៃទី 14/11/26
```

### Section Visibility Rules:
- Always show **មិនទាន់បង់** and **បង់ហើយ**. If a section has 0 rooms, display `• គ្មាន` under it (or omit **ជិតដល់ថ្ងៃបង់** completely when it has 0 rooms to keep the message short and clean).
- Use `html.escape(str(room_number))` for safe Telegram HTML formatting.

---

## 4. Implementation & Unit Test Checklist for Copilot

1. **Update `app/services/telegram_service.py`:**
   - Create a pure helper function `format_daily_report(tenants: list[...], today: date) -> str` that builds the exact message above.
   - Ensure `send_daily_report()` uses `parse_mode="HTML"` and `today = datetime.now(ZoneInfo("Asia/Phnom_Penh")).date()`.
2. **Add Unit Tests (`tests/test_telegram_service.py`):**
   - Test `days_until_due = 3` → outputs `Room 100 សល់ 3 ថ្ងៃទៀតដល់ថ្ងៃបង់`
   - Test `days_until_due = 2` → outputs `Room 100 សល់ 2 ថ្ងៃទៀតដល់ថ្ងៃបង់`
   - Test `days_until_due = 1` → outputs `Room 100 សល់ 1 ថ្ងៃទៀតដល់ថ្ងៃបង់`
   - Test `days_until_due = 0` → outputs `Room 100 ត្រូវបង់ថ្ងៃនេះ`
   - Test `days_until_due = -1` → outputs `Room 100 លើស 1 ថ្ងៃ`
   - Test `days_until_due = -5` → outputs `Room 100 លើស 5 ថ្ងៃ`
   - Test paid tenant (`days_until_due = 20`, `last_payment_date = date(2026, 11, 14)`) → outputs `Room 100 បង់ហើយថ្ងៃទី 14/11/26`
   - Verify no `SSID`, `MAC`, or `Next Due` strings appear anywhere in the formatted message.