# Task Specification: CRUD Audit & Minimalist Frontend Redesign

> **Instructions for AI Coding Assistant (GitHub Copilot / Cursor):**
> Read this entire specification carefully. Your goal is two-fold:
> 1. **Audit & Fix Full CRUD:** Ensure Create (Add), Read (List/Filter), Update (Edit Room/MACs & Mark Paid), and Delete work end-to-end from the UI to the SQLite database. Currently, the **Add Room** action is missing or inaccessible in the frontend.
> 2. **Minimalist UI Redesign ("Experience > Interface"):** Completely strip out gradients, shadows, decorative animations, and noisy colors. Rebuild `app/static/index.html` and `app/static/app.js` into a high-contrast, utilitarian, fast-action tool.
> 
> **Core Rule:** *"Change one thing does not break the app."* Do not break `app/services/billing_logic.py` while updating the frontend or API routes.

---

## Part 1: Full CRUD Audit & Fix Checklist

Verify and fix both the Backend (`app/routers/api.py`, `app/repositories/tenant_repo.py`) and Frontend (`app/static/index.html`, `app/static/app.js`) against this checklist:

### 1. CREATE (`POST /api/tenants`) — **CRITICAL FIX**
* **The Bug:** The user cannot see or trigger the "Add Room" option in the frontend.
* **Frontend Requirement:**
  * Place a permanent, high-contrast **`+ Add Room`** button in the sticky top header so it is always visible regardless of scroll position or empty state.
  * When the tenant list is empty (`tenants.length === 0`), display a centered empty state with a secondary **`+ Add First Room`** button.
  * Clicking `+ Add Room` opens the Room Form Drawer/Modal in **Create Mode** (`id = null`), resetting all fields:
    * `Room Number` (text, required, e.g., `101`)
    * `SSID` (text, required, e.g., `Room_101_WiFi`)
    * `Due Day` (number `1–31`, required, defaults to today's day of month)
    * `Last Payment Date` (date input `YYYY-MM-DD`, required, defaults to today in `Asia/Phnom_Penh`)
    * `MAC Addresses` (starts with 1 empty text input + a `+ Add MAC` button to append more rows).
* **Backend Verification:**
  * Ensure `POST /api/tenants` accepts `{ room_number, ssid, due_day, last_payment_date, mac_addresses: ["AA:BB:..."] }` (or objects with optional labels).
  * Allow empty MAC list `[]` or multiple MACs without crashing. Normalize MAC addresses to uppercase and trim whitespace.

### 2. READ (`GET /api/tenants`)
* Ensure `GET /api/tenants` returns all active rooms sorted logically:
  1. `OVERDUE` first (most overdue at the top)
  2. `DUE_SOON` second (soonest due at the top)
  3. `PAID` last (sorted by room number)
* Ensure every tenant object in the JSON response includes:
  * `id`, `room_number`, `ssid`, `due_day`, `last_payment_date`, `last_paid_for_due_date`, `next_due_date`, `late_days_remark`, `status`, `days_until_due`, and `devices` (array of `{ id, mac_address, device_label }`).

### 3. UPDATE (`PUT /api/tenants/{tenant_id}` & `POST /api/tenants/{tenant_id}/pay`)
* **Edit Room (`PUT /api/tenants/{tenant_id}`):**
  * Every room row/card must have an explicit **`Edit`** button.
  * Clicking `Edit` opens the same Room Form Modal in **Edit Mode**, pre-populated with the room's existing data and all existing MAC addresses.
  * Submitting in Edit Mode replaces the room's details and synchronizes the `devices` table inside an atomic SQLite transaction (`DELETE FROM devices WHERE tenant_id = ?` then re-insert updated list) and recalculates `last_paid_for_due_date` / `late_days_remark` if `due_day` or `last_payment_date` changed.
* **Mark Paid (`POST /api/tenants/{tenant_id}/pay`):**
  * Every room row/card must have a 1-tap **`Mark Paid`** button.
  * Clicking `Mark Paid` opens a minimal confirmation prompt with a Date Picker pre-filled to today (`Asia/Phnom_Penh` `YYYY-MM-DD`) and a single **`Confirm Payment`** button.

### 4. DELETE (`DELETE /api/tenants/{tenant_id}`)
* Inside the Edit Modal (or directly on the row via a `Delete` action), provide a **`Delete Room`** button.
* Require a simple confirmation (`window.confirm("Delete Room 101?")` or inline two-step click) before calling `DELETE /api/tenants/{tenant_id}`.
* Verify SQLite `ON DELETE CASCADE` removes associated rows in `devices` and `payment_logs`.

---

## Part 2: Minimalist Frontend Redesign ("Experience > Interface")

### Strict Visual & UX Rules
1. **NO Gradients:** Never use `bg-gradient-*` anywhere.
2. **NO Fancy Colors or Heavy Shadows:**
   * Background: Pure off-white `bg-neutral-50` (`#FAFAFA`), surfaces/cards in solid white `bg-white` (`#FFFFFF`).
   * Borders: Crisp 1px borders `border border-neutral-200` (`#E5E5E5`). No `shadow-lg` or `shadow-xl`.
   * Typography: System UI stack (`font-sans`) for text; monospace (`font-mono`) for MAC addresses, dates, and room numbers.
   * Primary Interactive Color: Solid black/near-black (`bg-neutral-900 text-white hover:bg-neutral-800`).
   * Secondary Interactive Color: White with neutral border (`bg-white text-neutral-900 border border-neutral-300 hover:bg-neutral-100`).
3. **Semantic Status Indicators Only (Flat & Restrained):**
   * **Overdue:** `bg-red-50 text-red-700 border border-red-200`
   * **Due Soon (≤ 3 days):** `bg-amber-50 text-amber-800 border border-amber-200`
   * **Paid:** `bg-emerald-50 text-emerald-700 border border-emerald-200`
4. **Experience > Interface (Speed & Ergonomics):**
   * Everything important must be visible at a glance without expanding accordions.
   * Tap any MAC address to copy it immediately to the clipboard with a subtle `"Copied"` text swap for 1 second.
   * Search/Filter happens instantaneously in memory without page reloads.

---

## Part 3: Exact Layout & Wireframe for `app/static/index.html`

Structure the single-page frontend into 4 clean sections:

```text
+-------------------------------------------------------------------+
| INTERNET TRACKER (Phnom Penh)       [Send Report]  [+ Add Room]   | <- Sticky Header
+-------------------------------------------------------------------+
| [ Search room, SSID, or MAC...               ]                    | <- Instant Search
| [All (12)]  [Overdue (2)]  [Due Soon (1)]  [Paid (9)]             | <- Flat Filter Tabs
+-------------------------------------------------------------------+
| ROOM 102                              [OVERDUE: 4d]               |
| SSID: Net_102  •  Due Day: 10th                                   |
| Last Paid: 2026-10-10                 Next Due: 2026-11-10        |
| MACs: [AA:BB:CC:11:22:33] [DD:EE:FF:44:55:66]                     |
| ----------------------------------------------------------------- |
| [ Mark Paid ]                                   [ Edit ] [Delete] |
+-------------------------------------------------------------------+
| ROOM 103                              [PAID] (Late 4d)            |
| SSID: Net_103  •  Due Day: 10th                                   |
| Last Paid: 2026-11-14                 Next Due: 2026-12-10        |
| MACs: [11:22:33:44:55:66]                                         |
| ----------------------------------------------------------------- |
| [ Mark Paid ]                                   [ Edit ] [Delete] |
+-------------------------------------------------------------------+
```

### Component Details to Implement in `index.html` & `app.js`:

1. **Sticky Top Bar (`header`):**
   * Left: App Title (`Internet Tracker`) + current Phnom Penh date in small muted monospace text.
   * Right: Two buttons side by side:
     * `Report` (`POST /api/report/trigger`) — secondary button (`border border-neutral-300 bg-white text-neutral-800 text-xs px-2.5 py-1.5 rounded`).
     * `+ Add Room` — primary high-contrast button (`bg-neutral-900 text-white text-xs font-medium px-3 py-1.5 rounded`).

2. **Search & Filter Bar:**
   * A clean text input: `placeholder="Search room, SSID, or MAC..."` (`w-full border border-neutral-300 rounded px-3 py-2 text-sm focus:outline-none focus:border-neutral-900`).
   * 4 flat segmented buttons below it: `All`, `Overdue`, `Due Soon`, `Paid` with live counts. Active tab uses `bg-neutral-900 text-white`, inactive uses `bg-white text-neutral-700 border border-neutral-200`.

3. **Compact Room Card:**
   * White box with `border border-neutral-200 rounded p-3.5 mb-2.5`.
   * **Row 1:** `Room {room_number}` in `font-mono font-semibold text-base` on the left; flat status badge on the right. If `late_days_remark > 0`, show a quiet inline tag next to status: `Paid {late_days_remark}d late`.
   * **Row 2 (Metadata Grid):** A clean 2-column compact grid (`text-xs text-neutral-600 mt-2`):
     * `SSID:` `<span class="font-mono text-neutral-900">{ssid}</span>`
     * `Due Day:` `<span class="font-mono text-neutral-900">Every {due_day}</span>`
     * `Last Paid:` `<span class="font-mono text-neutral-900">{last_payment_date}</span>`
     * `Next Due:` `<span class="font-mono font-semibold text-neutral-900">{next_due_date}</span>`
   * **Row 3 (MAC List):**
     * Render each MAC as a small monospace button: `class="font-mono text-xs bg-neutral-100 border border-neutral-200 px-1.5 py-0.5 rounded text-neutral-800 hover:bg-neutral-200"`. Clicking copies the MAC address.
   * **Row 4 (Action Footer):**
     * Top border `border-t border-neutral-100 mt-3 pt-2.5 flex items-center justify-between`.
     * Left: **`Mark Paid`** button (`bg-neutral-900 text-white text-xs font-medium px-3 py-1.5 rounded`).
     * Right: **`Edit`** (`text-xs text-neutral-700 border border-neutral-300 px-2.5 py-1 rounded`) and **`Delete`** (`text-xs text-red-600 border border-red-200 px-2.5 py-1 rounded`).

4. **Unified Add / Edit Modal (`#room-modal`):**
   * Fixed overlay `bg-black/40` (no blur needed) with a clean white panel `bg-white border border-neutral-300 rounded max-w-md w-full p-4`.
   * Dynamic Title: `"Add Room"` when creating, `"Edit Room {room_number}"` when editing.
   * Form inputs with clear `<label class="block text-xs font-medium text-neutral-700 mb-1">`.
   * **MAC Address List Manager inside Modal:**
     * Container `#mac-inputs-container`.
     * Function `addMacInputRow(value = "")` appends a flex row with `<input type="text" placeholder="AA:BB:CC:DD:EE:FF" class="mac-input font-mono uppercase ...">` and a `Remove` (`×`) button.
     * Button `+ Add MAC Address` (`type="button"`) below the container.
   * Footer buttons: `Cancel` and `Save Room`.

5. **Minimal Mark Paid Modal (`#pay-modal`):**
   * Shows `"Record payment for Room {room_number}"`.
   * Single `<input type="date" id="pay-date-input">` defaulted to today's date in `Asia/Phnom_Penh`.
   * Shows a live note below the date picker: *"Next due date will remain anchored to day {due_day} of next month."*
   * Buttons: `Cancel` and `Confirm Paid`.

---

## Part 4: Step-by-Step Execution Instructions for Copilot

1. **Inspect `app/routers/api.py` and `app/repositories/tenant_repo.py`:**
   * Verify `GET /api/tenants`, `POST /api/tenants`, `PUT /api/tenants/{id}`, `POST /api/tenants/{id}/pay`, and `DELETE /api/tenants/{id}` all exist, use consistent Pydantic schemas in `app/schemas.py`, and return proper HTTP status codes.
   * Ensure MAC address updates in `PUT /api/tenants/{id}` properly replace the room's MAC list without throwing `UNIQUE constraint failed` errors on unchanged MACs for the same tenant.
2. **Rewrite `app/static/index.html`:**
   * Remove all gradients, decorative icons, and complex CSS.
   * Implement the sticky header with the visible **`+ Add Room`** button, search/filter bar, room list container, Add/Edit Modal, and Mark Paid Modal using clean neutral Tailwind utility classes.
3. **Rewrite `app/static/app.js`:**
   * Implement clean, modular functions:
     * `fetchTenants()`
     * `renderTenants()` (applies search query + status filter)
     * `openCreateModal()` (bound to `#btn-add-room`)
     * `openEditModal(tenantId)`
     * `saveTenant(event)` (handles both `POST` and `PUT`)
     * `openPayModal(tenantId)` & `confirmMarkPaid(event)`
     * `deleteTenant(tenantId)`
     * `triggerGroupReport()`
   * Ensure any API error displays a clear, readable message banner or alert so failures are never silent.
4. **Verify End-to-End:**
   * Test adding a room with 2 MAC addresses, editing the room to add a 3rd MAC address, marking the room as paid (both on-time and late), filtering by status, and deleting a room.