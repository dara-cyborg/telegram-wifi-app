# Critical Fix Specification: MAC Address Auto-Formatting, Copyable Badges & Multiple Entries Per Room

> **Instructions for AI Coding Assistant (GitHub Copilot / Cursor):**
> Read this entire specification carefully and apply these targeted updates without breaking existing billing calculations (`app/services/billing_logic.py`) or other working features.
>
> **Core Rule:** *"Change one thing does not break the app."* Keep code modular, human-readable, and cleanly separated between database, backend validation, and frontend UI.

---

## 1. Logic Fix: Allow Adding the Same Room Number Multiple Times

### Why
A single physical room (e.g., `Room 101`) can have multiple users/devices registered at different times with **different `due_day` and `last_payment_date` schedules**. Therefore, `room_number` MUST NOT have a `UNIQUE` constraint in the database.

### Backend & Database Changes (`app/database.py` & `app/repositories/tenant_repo.py`)

1. **Remove `UNIQUE` Constraint on `tenants.room_number`:**
   * Update the `CREATE TABLE IF NOT EXISTS tenants` statement in `app/database.py`:
     ```sql
     CREATE TABLE IF NOT EXISTS tenants (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         room_number TEXT NOT NULL,                -- REMOVED UNIQUE CONSTRAINT
         ssid TEXT NOT NULL,
         due_day INTEGER NOT NULL CHECK (due_day >= 1 AND due_day <= 31),
         last_payment_date TEXT NOT NULL,
         last_paid_for_due_date TEXT NOT NULL,
         late_days_remark INTEGER NOT NULL DEFAULT 0,
         is_active INTEGER NOT NULL DEFAULT 1,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL
     );
     ```
   * **Automatic SQLite Migration on Startup:**
     Because SQLite does not support `ALTER TABLE DROP CONSTRAINT` directly, add a safe, idempotent migration check inside `init_db()` in `app/database.py`:
     * Query `SELECT sql FROM sqlite_master WHERE type='table' AND name='tenants';`
     * If `"room_number TEXT NOT NULL UNIQUE"` (or `UNIQUE` on `room_number`) is present in the table definition:
       1. `PRAGMA foreign_keys = OFF;`
       2. Begin transaction.
       3. Create `tenants_new` without the `UNIQUE` constraint on `room_number`.
       4. `INSERT INTO tenants_new SELECT * FROM tenants;`
       5. `DROP TABLE tenants;`
       6. `ALTER TABLE tenants_new RENAME TO tenants;`
       7. Commit transaction and re-enable `PRAGMA foreign_keys = ON;`.
     * Create a non-unique index for fast room lookups:
       `CREATE INDEX IF NOT EXISTS idx_tenants_room_number ON tenants(room_number);`

2. **Keep `devices.mac_address` Unique:**
   * A specific MAC address (`AA:BB:CC:DD:EE:FF`) still uniquely identifies a physical device, so `mac_address TEXT NOT NULL UNIQUE` on `devices` remains enforced (with clear error messaging if a duplicate MAC is submitted).

3. **Telegram Report & UI Disambiguation:**
   * Since `Room 101` can appear more than once in the list or daily 6:00 AM report, always display the room's associated MAC address(es) and Due Day right alongside `Room {room_number}` in both the UI cards and the Telegram report so the Admin immediately knows which registration in `Room 101` is due.

---

## 2. UX & Input Fix: Plain 12-Character MAC Input with Live Auto-Formatting

### Why
Typing colons (`:`) manually on mobile or desktop is slow and error-prone. The Admin wants to type or paste plain hex characters like `AABBCCDDEEFF` (or `aabbccddeeff` or `AA:BB:CC:DD:EE:FF`), have the input strictly cap at **12 valid hex characters**, and automatically format it into `AA:BB:CC:DD:EE:FF`.

### Frontend Implementation (`app/static/app.js` & `app/static/index.html`)

1. **Pure Helper Function for MAC Formatting (`app/static/app.js`):**
   Create a dedicated, reusable function:
   ```javascript
   /**
    * Strips all non-hex characters, limits to 12 hex chars, converts to uppercase,
    * and inserts colons every 2 characters -> "AA:BB:CC:DD:EE:FF"
    */
   function formatMacInput(rawValue) {
       const hexOnly = String(rawValue || "")
           .replace(/[^0-9a-fA-F]/g, "")
           .toUpperCase()
           .slice(0, 12);

       const pairs = hexOnly.match(/.{1,2}/g) || [];
       return pairs.join(":");
   }

   function isValidMac(macValue) {
       return /^([0-9A-F]{2}:){5}[0-9A-F]{2}$/.test(macValue);
   }
   ```

2. **Live Input Event Binding on MAC Fields:**
   * In `addMacInputRow(value = "")`:
     * Set `maxlength="17"` on the `<input>` element (`12` hex characters + `5` colons = `17` characters max).
     * Set `placeholder="AABBCCDDEEFF or AA:BB:CC:DD:EE:FF"`.
     * Set `autocomplete="off"`, `autocapitalize="characters"`, `spellcheck="false"`.
     * Attach an `input` event listener to every `.mac-input` field:
       ```javascript
       inputEl.addEventListener("input", (e) => {
           const formatted = formatMacInput(e.target.value);
           if (e.target.value !== formatted) {
               e.target.value = formatted;
           }
       });
       ```
     * Also handle `paste` cleanly so pasting `aabb-ccdd-eeff` or `aabbccddeeff` immediately turns into `AA:BB:CC:DD:EE:FF`.

3. **Frontend Form Validation Before Submit:**
   * When saving the room form, run `formatMacInput()` on each non-empty MAC input.
   * If any MAC input has fewer than 12 hex characters (i.e. `!isValidMac(mac)`), prevent form submission, highlight the input border in red (`border-red-500`), and show a clear message: `"MAC address must be exactly 12 hex characters (0-9, A-F)."`

### Backend Normalization (`app/schemas.py`)

* In `app/schemas.py`, add a Pydantic validator on `mac_addresses` so the backend also accepts either raw 12-char hex (`AABBCCDDEEFF`) or colon/hyphen-separated strings:
  ```python
  import re
  from pydantic import field_validator

  def normalize_mac_address(raw_mac: str) -> str:
      hex_only = re.sub(r"[^0-9A-Fa-f]", "", raw_mac).upper()
      if len(hex_only) != 12:
          raise ValueError(f"Invalid MAC address '{raw_mac}': must contain exactly 12 hex characters.")
      return ":".join(hex_only[i:i+2] for i in range(0, 12, 2))
  ```
* Apply `normalize_mac_address` to every MAC address in `TenantCreate` and `TenantUpdate`.

---

## 3. Display Fix: One-Tap Copyable MAC Addresses in the UI

### Requirement
Every MAC address displayed on a tenant card must be one-tap copyable to the clipboard with instant visual confirmation.

### Frontend Implementation (`app/static/app.js`)

1. **Render Copyable MAC Pills:**
   In `renderTenants()`, render each MAC address inside a `<button>` element with a `data-copy-mac` attribute:
   ```html
   <button
       type="button"
       data-copy-mac="AA:BB:CC:DD:EE:FF"
       title="Click to copy MAC address"
       class="mac-copy-btn inline-flex items-center gap-1 font-mono text-xs bg-neutral-100 border border-neutral-300 px-2 py-1 rounded text-neutral-900 hover:bg-neutral-200 active:bg-neutral-300 transition-none cursor-pointer"
   >
       <span class="mac-text">AA:BB:CC:DD:EE:FF</span>
   </button>
   ```

2. **Clipboard Copy Handler with Fallback:**
   Implement `copyMacToClipboard(macAddress, buttonEl)` in `app/static/app.js`:
   * Primary method: `await navigator.clipboard.writeText(macAddress)`
   * Fallback method (for older WebViews / Telegram WebApp environments where `navigator.clipboard` may be restricted): create a temporary off-screen `<textarea>`, `.select()`, and `document.execCommand("copy")`.
   * **Visual Feedback:**
     * Temporarily change the button text from `AA:BB:CC:DD:EE:FF` to `Copied!` and switch classes to `bg-neutral-900 text-white border-neutral-900`.
     * After `1000ms`, restore the original `AA:BB:CC:DD:EE:FF` text and neutral styling.

---

## 4. Verification Checklist for Copilot

After implementing these changes, verify:
1. [ ] Typing `aabbccddeeff1234` into the MAC input stops at 12 hex characters and displays `AA:BB:CC:DD:EE:FF` automatically.
2. [ ] Pasting `aa-bb-cc-dd-ee-ff` or `AABB.CCDD.EEFF` into the MAC input formats immediately to `AA:BB:CC:DD:EE:FF`.
3. [ ] Clicking any displayed MAC badge on a room card copies `AA:BB:CC:DD:EE:FF` to the clipboard and briefly displays `Copied!`.
4. [ ] Creating two separate entries for `Room 101` (e.g., Entry 1 with MAC `AA:BB:CC:11:22:33` and `due_day = 10`, Entry 2 with MAC `AA:BB:CC:44:55:66` and `due_day = 25`) succeeds without any database `UNIQUE` constraint error.