import json
import os
import re
import sqlite3
import calendar
from datetime import datetime, date, timedelta
from .config import DB_PATH, APP_TIMEZONE, DEFAULT_SENDER, DEFAULT_DUE_DAYS


def format_phone(phone):
    """Formats phone number to +1 (XXX) XXX-XXXX if 10 or 11 digits."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"+1 ({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return str(phone).strip()


def get_connection():
    """Returns a SQLite connection with Row factory and WAL mode."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initializes SQLite schema for sender profiles, clients, presets, and invoices."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        # 1. Sender Profiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sender_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                website TEXT,
                payment_instructions TEXT,
                default_notes TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 2. Clients
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 3. Client Presets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                preset_name TEXT NOT NULL,
                default_due_days INTEGER DEFAULT 14,
                items_json TEXT NOT NULL,
                notes TEXT,
                discount_amount REAL DEFAULT 0.0,
                tax_rate REAL DEFAULT 0.0,
                payment_instructions TEXT DEFAULT '',
                is_recurring INTEGER DEFAULT 0,
                recurrence_type TEXT DEFAULT 'monthly',
                recurrence_day INTEGER DEFAULT 1,
                recurrence_start_date TEXT DEFAULT '',
                sender_id INTEGER REFERENCES sender_profiles(id) ON DELETE SET NULL,
                auto_status TEXT DEFAULT 'draft',
                last_generated_date TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
        """)

        # Ensure client_presets columns exist
        cursor.execute("PRAGMA table_info(client_presets);")
        preset_cols = [r["name"] for r in cursor.fetchall()]
        if "discount_amount" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN discount_amount REAL DEFAULT 0.0;")
        if "tax_rate" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN tax_rate REAL DEFAULT 0.0;")
        if "payment_instructions" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN payment_instructions TEXT DEFAULT '';")
        if "is_recurring" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN is_recurring INTEGER DEFAULT 0;")
        if "recurrence_type" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN recurrence_type TEXT DEFAULT 'monthly';")
        if "recurrence_day" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN recurrence_day INTEGER DEFAULT 1;")
        if "recurrence_start_date" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN recurrence_start_date TEXT DEFAULT '';")
        if "sender_id" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN sender_id INTEGER REFERENCES sender_profiles(id) ON DELETE SET NULL;")
        if "auto_status" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN auto_status TEXT DEFAULT 'draft';")
        if "last_generated_date" not in preset_cols:
            cursor.execute("ALTER TABLE client_presets ADD COLUMN last_generated_date TEXT DEFAULT '';")

        # 4. Invoices
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                sender_id INTEGER REFERENCES sender_profiles(id) ON DELETE SET NULL,
                sender_name_snapshot TEXT NOT NULL,
                sender_info_snapshot TEXT,
                client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                client_name_snapshot TEXT NOT NULL,
                client_info_snapshot TEXT,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                subtotal REAL NOT NULL DEFAULT 0.0,
                discount_amount REAL NOT NULL DEFAULT 0.0,
                tax_rate REAL NOT NULL DEFAULT 0.0,
                total_amount REAL NOT NULL DEFAULT 0.0,
                payment_instructions TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 5. Invoice Items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                description TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 1.0,
                unit_price REAL NOT NULL DEFAULT 0.0,
                amount REAL NOT NULL DEFAULT 0.0,
                sort_order INTEGER DEFAULT 0
            );
        """)

        # Indexes for fast querying & filtering
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_sender ON invoices(sender_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_issue ON invoices(issue_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due_date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_client_presets_client ON client_presets(client_id);")

        conn.commit()

        # Seed default sender if table is empty
        cursor.execute("SELECT COUNT(*) AS cnt FROM sender_profiles;")
        if cursor.fetchone()["cnt"] == 0:
            now_iso = datetime.now(APP_TIMEZONE).isoformat()
            cursor.execute("""
                INSERT INTO sender_profiles (
                    name, email, phone, address, website,
                    payment_instructions, default_notes, is_default,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                DEFAULT_SENDER.get("name", "Stephen Giang"),
                DEFAULT_SENDER.get("email", "stepheng753@gmail.com"),
                DEFAULT_SENDER.get("phone", ""),
                DEFAULT_SENDER.get("address", ""),
                DEFAULT_SENDER.get("website", ""),
                DEFAULT_SENDER.get("payment_instructions", ""),
                DEFAULT_SENDER.get("default_notes", ""),
                1,
                now_iso,
                now_iso
            ))
            conn.commit()


# ---------------------------------------------------------------------------
# SENDER PROFILES CRUD
# ---------------------------------------------------------------------------

def get_senders():
    """Returns all sender profiles ordered with default first, then by name."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sender_profiles
            ORDER BY is_default DESC, name ASC;
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_sender_by_id(sender_id):
    """Returns a single sender profile by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sender_profiles WHERE id = ?;", (sender_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def add_sender(name, email="", phone="", address="", website="",
               payment_instructions="", default_notes="", is_default=0):
    """Adds a new sender profile."""
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_default:
            cursor.execute("UPDATE sender_profiles SET is_default = 0;")
        cursor.execute("""
            INSERT INTO sender_profiles (
                name, email, phone, address, website,
                payment_instructions, default_notes, is_default,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            name.strip(),
            email.strip(),
            format_phone(phone),
            address.strip(),
            website.strip(),
            payment_instructions.strip(),
            default_notes.strip(),
            1 if is_default else 0,
            now_iso,
            now_iso
        ))
        conn.commit()
        return cursor.lastrowid


def update_sender(sender_id, name, email="", phone="", address="", website="",
                  payment_instructions="", default_notes="", is_default=0):
    """Updates an existing sender profile."""
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_default:
            cursor.execute("UPDATE sender_profiles SET is_default = 0 WHERE id != ?;", (sender_id,))
        cursor.execute("""
            UPDATE sender_profiles SET
                name = ?,
                email = ?,
                phone = ?,
                address = ?,
                website = ?,
                payment_instructions = ?,
                default_notes = ?,
                is_default = ?,
                updated_at = ?
            WHERE id = ?;
        """, (
            name.strip(),
            email.strip(),
            format_phone(phone),
            address.strip(),
            website.strip(),
            payment_instructions.strip(),
            default_notes.strip(),
            1 if is_default else 0,
            now_iso,
            sender_id
        ))
        conn.commit()
        return cursor.rowcount > 0


def set_default_sender(sender_id):
    """Sets the designated sender profile as default."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sender_profiles WHERE id = ?;", (sender_id,))
        if cursor.fetchone() is None:
            return False
        cursor.execute("UPDATE sender_profiles SET is_default = 0;")
        cursor.execute("UPDATE sender_profiles SET is_default = 1 WHERE id = ?;", (sender_id,))
        conn.commit()
        return True


def delete_sender(sender_id):
    """Deletes a sender profile."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sender_profiles WHERE id = ?;", (sender_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# CLIENTS CRUD
# ---------------------------------------------------------------------------

def get_clients():
    """Returns all clients ordered by name."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE ASC;")
        return [dict(row) for row in cursor.fetchall()]


def get_client_by_id(client_id):
    """Returns a client by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients WHERE id = ?;", (client_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def add_client(name, email="", phone="", address="", notes=""):
    """Adds a new client."""
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clients (name, email, phone, address, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            name.strip(),
            email.strip(),
            format_phone(phone),
            address.strip(),
            notes.strip(),
            now_iso,
            now_iso
        ))
        conn.commit()
        return cursor.lastrowid


def update_client(client_id, name, email="", phone="", address="", notes=""):
    """Updates a client's details."""
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE clients SET
                name = ?,
                email = ?,
                phone = ?,
                address = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?;
        """, (
            name.strip(),
            email.strip(),
            format_phone(phone),
            address.strip(),
            notes.strip(),
            now_iso,
            client_id
        ))
        conn.commit()
        return cursor.rowcount > 0


def delete_client(client_id):
    """Deletes a client and cascades to their presets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE id = ?;", (client_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# CLIENT PRESETS CRUD
# ---------------------------------------------------------------------------

def get_presets_by_client(client_id):
    """Returns presets for a given client."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM client_presets
            WHERE client_id = ?
            ORDER BY preset_name COLLATE NOCASE ASC;
        """, (client_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                items_val = json.loads(d.get("items_json") or "[]")
                if isinstance(items_val, str):
                    items_val = json.loads(items_val)
                d["items"] = items_val if isinstance(items_val, list) else []
            except Exception:
                d["items"] = []
            result.append(d)
        return result


def get_all_presets():
    """Returns all client presets with client and sender profile details."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cp.*, c.name AS client_name, c.email AS client_email,
                   sp.name AS sender_name
            FROM client_presets cp
            JOIN clients c ON cp.client_id = c.id
            LEFT JOIN sender_profiles sp ON cp.sender_id = sp.id
            ORDER BY cp.preset_name COLLATE NOCASE ASC;
        """)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                items_val = json.loads(d.get("items_json") or "[]")
                if isinstance(items_val, str):
                    items_val = json.loads(items_val)
                d["items"] = items_val if isinstance(items_val, list) else []
            except Exception:
                d["items"] = []
            result.append(d)
        return result


def get_preset_by_id(preset_id):
    """Returns a single preset by ID with parsed line items."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cp.*, c.name AS client_name, sp.name AS sender_name
            FROM client_presets cp
            JOIN clients c ON cp.client_id = c.id
            LEFT JOIN sender_profiles sp ON cp.sender_id = sp.id
            WHERE cp.id = ?;
        """, (preset_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            items_val = json.loads(d.get("items_json") or "[]")
            if isinstance(items_val, str):
                items_val = json.loads(items_val)
            d["items"] = items_val if isinstance(items_val, list) else []
        except Exception:
            d["items"] = []
        return d


def add_preset(client_id, preset_name, default_due_days=14, items=None, notes="",
               discount_amount=0.0, tax_rate=0.0, payment_instructions="",
               is_recurring=0, recurrence_type="monthly", recurrence_day=1,
               recurrence_start_date="", sender_id=None, auto_status="draft"):
    """Saves a line-item preset for a client with optional automated recurring schedule."""
    if items is None:
        items = []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    items_json = json.dumps(items)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO client_presets (
                client_id, preset_name, default_due_days, items_json, notes,
                discount_amount, tax_rate, payment_instructions, created_at,
                is_recurring, recurrence_type, recurrence_day, recurrence_start_date,
                sender_id, auto_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            client_id,
            preset_name.strip(),
            int(default_due_days),
            items_json,
            notes.strip(),
            float(discount_amount or 0.0),
            float(tax_rate or 0.0),
            (payment_instructions or "").strip(),
            now_iso,
            1 if is_recurring else 0,
            (recurrence_type or "monthly").strip(),
            int(recurrence_day or 1),
            (recurrence_start_date or "").strip(),
            sender_id,
            (auto_status or "draft").strip()
        ))
        conn.commit()
        return cursor.lastrowid


def update_preset(preset_id, preset_name, default_due_days=14, items=None, notes="",
                  discount_amount=0.0, tax_rate=0.0, payment_instructions="",
                  is_recurring=0, recurrence_type="monthly", recurrence_day=1,
                  recurrence_start_date="", sender_id=None, auto_status="draft"):
    """Updates an existing preset record including its line items and recurring rules."""
    if items is None:
        items = []
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []
    if not isinstance(items, list):
        items = []
    items_json = json.dumps(items)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE client_presets SET
                preset_name = ?,
                default_due_days = ?,
                items_json = ?,
                notes = ?,
                discount_amount = ?,
                tax_rate = ?,
                payment_instructions = ?,
                is_recurring = ?,
                recurrence_type = ?,
                recurrence_day = ?,
                recurrence_start_date = ?,
                sender_id = ?,
                auto_status = ?
            WHERE id = ?;
        """, (
            preset_name.strip(),
            int(default_due_days),
            items_json,
            notes.strip(),
            float(discount_amount or 0.0),
            float(tax_rate or 0.0),
            (payment_instructions or "").strip(),
            1 if is_recurring else 0,
            (recurrence_type or "monthly").strip(),
            int(recurrence_day or 1),
            (recurrence_start_date or "").strip(),
            sender_id,
            (auto_status or "draft").strip(),
            preset_id
        ))
        conn.commit()
        return cursor.rowcount > 0


def get_recurring_presets():
    """Returns all presets marked as active recurring templates."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cp.*, c.name AS client_name, c.email AS client_email,
                   sp.name AS sender_name
            FROM client_presets cp
            JOIN clients c ON cp.client_id = c.id
            LEFT JOIN sender_profiles sp ON cp.sender_id = sp.id
            WHERE cp.is_recurring = 1
            ORDER BY cp.preset_name COLLATE NOCASE ASC;
        """)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                items_val = json.loads(d.get("items_json") or "[]")
                if isinstance(items_val, str):
                    items_val = json.loads(items_val)
                d["items"] = items_val if isinstance(items_val, list) else []
            except Exception:
                d["items"] = []
            result.append(d)
        return result


def process_recurring_invoices(target_date=None):
    """
    Evaluates all active recurring presets (is_recurring = 1) and generates
    invoices for presets scheduled on the specified target_date (defaulting to today in APP_TIMEZONE).
    Prevents duplicate creation if already run on target_date.
    Returns a dictionary summarizing execution and newly created invoices.
    """
    if target_date is None:
        eval_date = datetime.now(APP_TIMEZONE).date()
    elif isinstance(target_date, str):
        try:
            eval_date = datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            eval_date = datetime.now(APP_TIMEZONE).date()
    elif isinstance(target_date, datetime):
        eval_date = target_date.date()
    elif isinstance(target_date, date):
        eval_date = target_date
    else:
        eval_date = datetime.now(APP_TIMEZONE).date()

    date_str = eval_date.strftime("%Y-%m-%d")
    created_invoices = []

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM client_presets WHERE is_recurring = 1;")
        presets = [dict(r) for r in cursor.fetchall()]

        for p in presets:
            # Skip if already generated on this target date
            if p.get("last_generated_date") == date_str:
                continue

            rec_type = (p.get("recurrence_type") or "monthly").lower()
            rec_day = int(p.get("recurrence_day") or 1)
            start_date_str = (p.get("recurrence_start_date") or "").strip()

            start_date = None
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                except ValueError:
                    start_date = None

            is_due = False

            if rec_type == "monthly":
                # Matches day of the month (e.g. 1 for 1st of month)
                _, max_days = calendar.monthrange(eval_date.year, eval_date.month)
                effective_day = min(rec_day, max_days)
                if eval_date.day == effective_day:
                    if not start_date or eval_date >= start_date:
                        is_due = True

            elif rec_type == "weekly":
                # rec_day is 0=Monday..6=Sunday
                if eval_date.weekday() == rec_day:
                    if not start_date or eval_date >= start_date:
                        is_due = True

            elif rec_type == "biweekly":
                # Every other week on rec_day weekday starting from start_date
                if eval_date.weekday() == rec_day:
                    if start_date:
                        days_ahead = (rec_day - start_date.weekday()) % 7
                        first_due = start_date + timedelta(days=days_ahead)
                        if eval_date >= first_due and (eval_date - first_due).days % 14 == 0:
                            is_due = True
                    else:
                        is_due = True

            if not is_due:
                continue

            # Load client
            client = get_client_by_id(p["client_id"])
            if not client:
                continue

            sender_id = p.get("sender_id")
            sender = get_sender_by_id(sender_id) if sender_id else None
            if not sender:
                senders = get_senders()
                if senders:
                    sender = senders[0]
                    sender_id = sender["id"]

            sender_name = sender["name"] if sender else "Stephen Giang"
            due_days = int(p.get("default_due_days") or 14)
            due_date = eval_date + timedelta(days=due_days)

            try:
                items = json.loads(p.get("items_json") or "[]")
            except Exception:
                items = []

            inv_data = {
                "invoice_number": generate_next_invoice_number(),
                "sender_id": sender_id,
                "sender_name": sender_name,
                "client_id": client["id"],
                "client_name": client["name"],
                "issue_date": date_str,
                "due_date": due_date.strftime("%Y-%m-%d"),
                "status": p.get("auto_status") or "draft",
                "discount_amount": float(p.get("discount_amount") or 0.0),
                "tax_rate": float(p.get("tax_rate") or 0.0),
                "payment_instructions": p.get("payment_instructions") or (sender.get("payment_instructions") if sender else ""),
                "notes": p.get("notes") or (sender.get("default_notes") if sender else ""),
                "items": items
            }

            inv_id = create_invoice(inv_data)
            if inv_id:
                cursor.execute("UPDATE client_presets SET last_generated_date = ? WHERE id = ?;", (date_str, p["id"]))
                conn.commit()
                created_invoices.append({
                    "id": inv_id,
                    "invoice_number": inv_data["invoice_number"],
                    "client_name": client["name"],
                    "preset_name": p["preset_name"],
                    "status": inv_data["status"],
                    "issue_date": date_str,
                    "due_date": inv_data["due_date"]
                })

    return {
        "success": True,
        "date": date_str,
        "active_recurring_presets": len(presets),
        "created_count": len(created_invoices),
        "invoices": created_invoices
    }


def delete_preset(preset_id):
    """Deletes a preset."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM client_presets WHERE id = ?;", (preset_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# INVOICE NUMBER GENERATION
# ---------------------------------------------------------------------------

def generate_next_invoice_number():
    """Generates the next sequential invoice number for current year: INV-YYYY-001."""
    now = datetime.now(APP_TIMEZONE)
    year = now.year
    prefix = f"INV-{year}-"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT invoice_number FROM invoices
            WHERE invoice_number LIKE ?
            ORDER BY id DESC;
        """, (f"{prefix}%",))
        rows = cursor.fetchall()

        max_seq = 0
        for r in rows:
            num_str = r["invoice_number"]
            try:
                parts = num_str.split("-")
                seq = int(parts[-1])
                if seq > max_seq:
                    max_seq = seq
            except (ValueError, IndexError):
                continue

        return f"{prefix}{max_seq + 1:03d}"


# ---------------------------------------------------------------------------
# INVOICES & ITEMS CRUD
# ---------------------------------------------------------------------------

def get_invoices(status=None, client_id=None, sender_id=None, search=None,
                 start_date=None, end_date=None, sort_by="issue_date", sort_order="desc"):
    """
    Returns invoices matching filters.
    Updates overdue status on the fly for sent/draft invoices whose due_date < today.
    """
    today_str = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d")

    # Auto-flag overdue invoices (sent or draft invoices past due date)
    with get_connection() as conn:
        conn.execute("""
            UPDATE invoices
            SET status = 'overdue', updated_at = ?
            WHERE status IN ('draft', 'sent') AND due_date < ?;
        """, (datetime.now(APP_TIMEZONE).isoformat(), today_str))
        conn.commit()

    query = "SELECT * FROM invoices WHERE 1=1"
    params = []

    if status and status.lower() != "all":
        query += " AND status = ?"
        params.append(status.lower())

    if client_id:
        query += " AND client_id = ?"
        params.append(int(client_id))

    if sender_id:
        query += " AND sender_id = ?"
        params.append(int(sender_id))

    if start_date:
        query += " AND issue_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND issue_date <= ?"
        params.append(end_date)

    if search:
        search_term = f"%{search.strip()}%"
        query += """ AND (
            invoice_number LIKE ? OR
            client_name_snapshot LIKE ? OR
            sender_name_snapshot LIKE ? OR
            notes LIKE ?
        )"""
        params.extend([search_term, search_term, search_term, search_term])

    # Sorting
    allowed_sort_fields = {
        "issue_date": "issue_date",
        "due_date": "due_date",
        "total_amount": "total_amount",
        "invoice_number": "invoice_number",
        "status": "status",
        "created_at": "created_at"
    }
    col = allowed_sort_fields.get(sort_by, "issue_date")
    direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"
    query += f" ORDER BY {col} {direction}, id {direction};"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            result.append(item)
        return result


def get_invoice_by_id(invoice_id):
    """
    Returns full invoice details including snapshots and list of line items.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE id = ?;", (invoice_id,))
        row = cursor.fetchone()
        if not row:
            return None

        invoice = dict(row)

        # Parse JSON snapshots if present
        try:
            invoice["sender_info"] = json.loads(invoice.get("sender_info_snapshot") or "{}")
        except Exception:
            invoice["sender_info"] = {}

        try:
            invoice["client_info"] = json.loads(invoice.get("client_info_snapshot") or "{}")
        except Exception:
            invoice["client_info"] = {}

        # Fetch items
        cursor.execute("""
            SELECT * FROM invoice_items
            WHERE invoice_id = ?
            ORDER BY sort_order ASC, id ASC;
        """, (invoice_id,))
        invoice["items"] = [dict(r) for r in cursor.fetchall()]

        return invoice


def create_invoice(data):
    """
    Creates an invoice along with its line items and historical snapshots.
    `data` expects:
      - invoice_number (optional, generated if omitted)
      - sender_id (optional, takes default sender if omitted)
      - client_id (optional)
      - client_name (required if client_id not present or client snapshot)
      - client_email, client_phone, client_address
      - issue_date, due_date
      - status ('draft', 'sent', 'paid', 'overdue', 'void')
      - discount_amount, tax_rate
      - payment_instructions, notes
      - items: list of {description, quantity, unit_price}
    """
    now = datetime.now(APP_TIMEZONE)
    now_iso = now.isoformat()

    invoice_number = data.get("invoice_number")
    if not invoice_number or not invoice_number.strip():
        invoice_number = generate_next_invoice_number()
    else:
        invoice_number = invoice_number.strip()

    # Resolve sender
    sender_id = data.get("sender_id")
    sender_row = None
    if sender_id:
        sender_row = get_sender_by_id(sender_id)
    if not sender_row:
        # Fall back to default sender
        senders = get_senders()
        if senders:
            sender_row = senders[0]
            sender_id = sender_row["id"]
        else:
            sender_row = DEFAULT_SENDER
            sender_id = None

    sender_name_snapshot = sender_row.get("name", "Stephen Giang")
    sender_info_snapshot = json.dumps({
        "name": sender_row.get("name", ""),
        "email": sender_row.get("email", ""),
        "phone": format_phone(sender_row.get("phone", "")),
        "address": sender_row.get("address", ""),
        "website": sender_row.get("website", ""),
        "payment_instructions": sender_row.get("payment_instructions", "")
    })

    # Resolve client
    client_id = data.get("client_id")
    client_row = None
    if client_id:
        client_row = get_client_by_id(client_id)

    client_name = data.get("client_name") or (client_row.get("name") if client_row else "") or "Valued Client"
    client_email = data.get("client_email") or (client_row.get("email") if client_row else "")
    client_phone = format_phone(data.get("client_phone") or (client_row.get("phone") if client_row else ""))
    client_address = data.get("client_address") or (client_row.get("address") if client_row else "")

    client_info_snapshot = json.dumps({
        "name": client_name,
        "email": client_email,
        "phone": client_phone,
        "address": client_address
    })

    issue_date = data.get("issue_date") or now.strftime("%Y-%m-%d")
    due_date = data.get("due_date")
    if not due_date:
        from datetime import timedelta
        due_date = (now + timedelta(days=DEFAULT_DUE_DAYS)).strftime("%Y-%m-%d")

    status = (data.get("status") or "draft").lower()

    # Calculate item amounts and totals
    raw_items = data.get("items") or []
    subtotal = 0.0
    processed_items = []
    for idx, it in enumerate(raw_items):
        desc = (it.get("description") or "").strip()
        if not desc:
            continue
        try:
            qty = float(it.get("quantity", 1.0))
        except (ValueError, TypeError):
            qty = 1.0
        try:
            unit_price = float(it.get("unit_price", 0.0))
        except (ValueError, TypeError):
            unit_price = 0.0

        line_amount = round(qty * unit_price, 2)
        subtotal += line_amount
        processed_items.append({
            "description": desc,
            "quantity": qty,
            "unit_price": unit_price,
            "amount": line_amount,
            "sort_order": idx
        })

    subtotal = round(subtotal, 2)
    try:
        discount_amount = max(0.0, float(data.get("discount_amount", 0.0)))
    except (ValueError, TypeError):
        discount_amount = 0.0

    try:
        tax_rate = max(0.0, float(data.get("tax_rate", 0.0)))
    except (ValueError, TypeError):
        tax_rate = 0.0

    discounted_subtotal = max(0.0, subtotal - discount_amount)
    tax_amount = round(discounted_subtotal * (tax_rate / 100.0), 2)
    total_amount = round(discounted_subtotal + tax_amount, 2)

    payment_instructions = data.get("payment_instructions") or sender_row.get("payment_instructions", "")
    notes = data.get("notes") or sender_row.get("default_notes", "")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO invoices (
                invoice_number, sender_id, sender_name_snapshot, sender_info_snapshot,
                client_id, client_name_snapshot, client_info_snapshot,
                issue_date, due_date, status,
                subtotal, discount_amount, tax_rate, total_amount,
                payment_instructions, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            invoice_number,
            sender_id,
            sender_name_snapshot,
            sender_info_snapshot,
            client_id,
            client_name,
            client_info_snapshot,
            issue_date,
            due_date,
            status,
            subtotal,
            discount_amount,
            tax_rate,
            total_amount,
            payment_instructions,
            notes,
            now_iso,
            now_iso
        ))
        invoice_id = cursor.lastrowid

        for it in processed_items:
            cursor.execute("""
                INSERT INTO invoice_items (
                    invoice_id, description, quantity, unit_price, amount, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (
                invoice_id,
                it["description"],
                it["quantity"],
                it["unit_price"],
                it["amount"],
                it["sort_order"]
            ))

        conn.commit()
        return invoice_id


def update_invoice(invoice_id, data):
    """
    Updates an invoice and its line items.
    """
    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    existing = get_invoice_by_id(invoice_id)
    if not existing:
        return False

    sender_id = data.get("sender_id", existing.get("sender_id"))
    sender_row = get_sender_by_id(sender_id) if sender_id else None
    sender_name_snapshot = sender_row["name"] if sender_row else existing["sender_name_snapshot"]
    sender_info_snapshot = json.dumps({
        "name": sender_row.get("name", ""),
        "email": sender_row.get("email", ""),
        "phone": format_phone(sender_row.get("phone", "")),
        "address": sender_row.get("address", ""),
        "website": sender_row.get("website", ""),
        "payment_instructions": sender_row.get("payment_instructions", "")
    }) if sender_row else existing.get("sender_info_snapshot")

    client_id = data.get("client_id", existing.get("client_id"))
    client_row = get_client_by_id(client_id) if client_id else None
    client_name = data.get("client_name") or (client_row["name"] if client_row else existing["client_name_snapshot"])
    client_info_snapshot = json.dumps({
        "name": client_name,
        "email": data.get("client_email") or (client_row["email"] if client_row else ""),
        "phone": format_phone(data.get("client_phone") or (client_row["phone"] if client_row else "")),
        "address": data.get("client_address") or (client_row["address"] if client_row else "")
    })

    issue_date = data.get("issue_date", existing["issue_date"])
    due_date = data.get("due_date", existing["due_date"])
    status = (data.get("status", existing["status"])).lower()

    # Recalculate line items
    raw_items = data.get("items")
    if raw_items is None:
        raw_items = existing.get("items", [])

    subtotal = 0.0
    processed_items = []
    for idx, it in enumerate(raw_items):
        desc = (it.get("description") or "").strip()
        if not desc:
            continue
        try:
            qty = float(it.get("quantity", 1.0))
        except (ValueError, TypeError):
            qty = 1.0
        try:
            unit_price = float(it.get("unit_price", 0.0))
        except (ValueError, TypeError):
            unit_price = 0.0
        line_amount = round(qty * unit_price, 2)
        subtotal += line_amount
        processed_items.append({
            "description": desc,
            "quantity": qty,
            "unit_price": unit_price,
            "amount": line_amount,
            "sort_order": idx
        })

    subtotal = round(subtotal, 2)
    try:
        discount_amount = max(0.0, float(data.get("discount_amount", existing["discount_amount"])))
    except (ValueError, TypeError):
        discount_amount = existing["discount_amount"]

    try:
        tax_rate = max(0.0, float(data.get("tax_rate", existing["tax_rate"])))
    except (ValueError, TypeError):
        tax_rate = existing["tax_rate"]

    discounted_subtotal = max(0.0, subtotal - discount_amount)
    tax_amount = round(discounted_subtotal * (tax_rate / 100.0), 2)
    total_amount = round(discounted_subtotal + tax_amount, 2)

    payment_instructions = data.get("payment_instructions", existing["payment_instructions"])
    notes = data.get("notes", existing["notes"])

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE invoices SET
                sender_id = ?,
                sender_name_snapshot = ?,
                sender_info_snapshot = ?,
                client_id = ?,
                client_name_snapshot = ?,
                client_info_snapshot = ?,
                issue_date = ?,
                due_date = ?,
                status = ?,
                subtotal = ?,
                discount_amount = ?,
                tax_rate = ?,
                total_amount = ?,
                payment_instructions = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?;
        """, (
            sender_id,
            sender_name_snapshot,
            sender_info_snapshot,
            client_id,
            client_name,
            client_info_snapshot,
            issue_date,
            due_date,
            status,
            subtotal,
            discount_amount,
            tax_rate,
            total_amount,
            payment_instructions,
            notes,
            now_iso,
            invoice_id
        ))

        # Replace items
        cursor.execute("DELETE FROM invoice_items WHERE invoice_id = ?;", (invoice_id,))
        for it in processed_items:
            cursor.execute("""
                INSERT INTO invoice_items (
                    invoice_id, description, quantity, unit_price, amount, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (
                invoice_id,
                it["description"],
                it["quantity"],
                it["unit_price"],
                it["amount"],
                it["sort_order"]
            ))

        conn.commit()
        return True


def update_invoice_status(invoice_id, status):
    """Updates invoice status (e.g. 'draft', 'sent', 'paid', 'overdue', 'void')."""
    valid_statuses = {"draft", "sent", "paid", "overdue", "void"}
    status = status.lower().strip()
    if status not in valid_statuses:
        return False

    now_iso = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE invoices SET status = ?, updated_at = ?
            WHERE id = ?;
        """, (status, now_iso, invoice_id))
        conn.commit()
        return cursor.rowcount > 0


def duplicate_invoice(invoice_id):
    """
    Duplicates an invoice into a new draft with a new invoice number and today's date.
    """
    orig = get_invoice_by_id(invoice_id)
    if not orig:
        return None

    now = datetime.now(APP_TIMEZONE)
    from datetime import timedelta
    new_due = (now + timedelta(days=DEFAULT_DUE_DAYS)).strftime("%Y-%m-%d")

    data = {
        "invoice_number": generate_next_invoice_number(),
        "sender_id": orig.get("sender_id"),
        "client_id": orig.get("client_id"),
        "client_name": orig.get("client_name_snapshot"),
        "client_email": orig.get("client_info", {}).get("email", ""),
        "client_phone": orig.get("client_info", {}).get("phone", ""),
        "client_address": orig.get("client_info", {}).get("address", ""),
        "issue_date": now.strftime("%Y-%m-%d"),
        "due_date": new_due,
        "status": "draft",
        "discount_amount": orig.get("discount_amount", 0.0),
        "tax_rate": orig.get("tax_rate", 0.0),
        "payment_instructions": orig.get("payment_instructions", ""),
        "notes": orig.get("notes", ""),
        "items": [
            {
                "description": it["description"],
                "quantity": it["quantity"],
                "unit_price": it["unit_price"]
            }
            for it in orig.get("items", [])
        ]
    }

    return create_invoice(data)


def delete_invoice(invoice_id):
    """Hard-deletes an invoice and its items (via CASCADE)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices WHERE id = ?;", (invoice_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_invoices_summary(status=None, client_id=None, sender_id=None, search=None,
                         start_date=None, end_date=None):
    """
    Computes dashboard summary statistics matching optional filter criteria:
    - Total Invoiced (non-void, or void sum if status='void')
    - Outstanding (sent + overdue)
    - Paid (paid)
    - Total Clients (count of distinct client records among filtered invoices)
    """
    today_str = datetime.now(APP_TIMEZONE).strftime("%Y-%m-%d")

    # Auto-flag overdue invoices first
    with get_connection() as conn:
        conn.execute("""
            UPDATE invoices
            SET status = 'overdue', updated_at = ?
            WHERE status IN ('draft', 'sent') AND due_date < ?;
        """, (datetime.now(APP_TIMEZONE).isoformat(), today_str))
        conn.commit()

    query = "SELECT * FROM invoices WHERE 1=1"
    params = []

    if status and status.lower() != "all":
        query += " AND status = ?"
        params.append(status.lower())

    if client_id:
        query += " AND client_id = ?"
        params.append(int(client_id))

    if sender_id:
        query += " AND sender_id = ?"
        params.append(int(sender_id))

    if start_date:
        query += " AND issue_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND issue_date <= ?"
        params.append(end_date)

    if search:
        search_term = f"%{search.strip()}%"
        query += """ AND (
            invoice_number LIKE ? OR
            client_name_snapshot LIKE ? OR
            sender_name_snapshot LIKE ? OR
            notes LIKE ?
        )"""
        params.extend([search_term, search_term, search_term, search_term])

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]

        total_invoiced = 0.0
        outstanding = 0.0
        paid = 0.0
        drafts_count = 0
        void_count = 0
        clients_set = set()

        for inv in rows:
            st = (inv.get("status") or "").lower()
            amt = float(inv.get("total_amount") or 0.0)

            if st != "void":
                total_invoiced += amt
            else:
                void_count += 1

            if st in ("sent", "overdue"):
                outstanding += amt
            elif st == "paid":
                paid += amt
            elif st == "draft":
                drafts_count += 1

            c_key = inv.get("client_id") or (inv.get("client_name_snapshot") or "").strip().lower()
            if c_key:
                clients_set.add(c_key)

        if status and status.lower() == "void":
            total_invoiced = sum(float(inv.get("total_amount") or 0.0) for inv in rows)

        return {
            "total_invoiced": round(total_invoiced, 2),
            "outstanding": round(outstanding, 2),
            "paid": round(paid, 2),
            "total_clients": len(clients_set),
            "total_invoices": len(rows),
            "drafts_count": drafts_count,
            "void_count": void_count
        }
