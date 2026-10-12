import sqlite3
import os
import json
from datetime import datetime, timedelta
import pytz
from .config import DB_PATH, APP_TIMEZONE

def get_connection():
    """Returns a SQLite connection with Row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database schema."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        # Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                institution TEXT NOT NULL,
                name TEXT NOT NULL,
                account_number_mask TEXT,
                account_type TEXT NOT NULL,
                balance REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                apy_interest TEXT,
                rewards_status TEXT,
                credit_limit REAL DEFAULT 0.0,
                vested_balance REAL DEFAULT 0.0,
                holdings_summary TEXT,
                is_asset INTEGER NOT NULL,
                is_manual INTEGER DEFAULT 0,
                last_synced TEXT NOT NULL,
                created_at TEXT NOT NULL,
                simplefin_id TEXT
            );
        """)

        # Migration: ensure simplefin_id column exists
        try:
            cursor.execute("ALTER TABLE accounts ADD COLUMN simplefin_id TEXT;")
        except sqlite3.OperationalError:
            pass

        # Snapshots table for overall Net Worth history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL UNIQUE,
                net_worth REAL NOT NULL,
                total_assets REAL NOT NULL,
                total_liabilities REAL NOT NULL,
                liquid_cash REAL NOT NULL,
                investments REAL NOT NULL,
                mortgage_debt REAL NOT NULL,
                credit_debt REAL NOT NULL,
                note TEXT
            );
        """)

        # Account snapshots for granular per-account history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER,
                account_id TEXT NOT NULL,
                balance REAL NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
            );
        """)

        # Settings key-value store
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Budget items table for income and monthly recurring expenses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budget_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                frequency TEXT DEFAULT 'monthly',
                raw_amount REAL,
                tax_status TEXT DEFAULT 'post-tax',
                due_date TEXT,
                portal_url TEXT,
                notes TEXT,
                details_json TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON snapshots(timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_acct_snap_time ON account_snapshots(account_id, timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(account_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_sfin ON accounts(simplefin_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_budget_category ON budget_items(category, is_active);")
        conn.commit()

        # Schema evolution: ensure balance_change, prev_balance, balance_change_at exist on accounts
        cursor.execute("PRAGMA table_info(accounts);")
        acct_cols = [r["name"] for r in cursor.fetchall()]
        if "balance_change" not in acct_cols:
            cursor.execute("ALTER TABLE accounts ADD COLUMN balance_change REAL DEFAULT 0.0;")
        if "prev_balance" not in acct_cols:
            cursor.execute("ALTER TABLE accounts ADD COLUMN prev_balance REAL DEFAULT NULL;")
        if "balance_change_at" not in acct_cols:
            cursor.execute("ALTER TABLE accounts ADD COLUMN balance_change_at TEXT DEFAULT '';")
        conn.commit()

        # Schema evolution: ensure net_worth_change exists on snapshots
        cursor.execute("PRAGMA table_info(snapshots);")
        snap_cols = [r["name"] for r in cursor.fetchall()]
        if "net_worth_change" not in snap_cols:
            cursor.execute("ALTER TABLE snapshots ADD COLUMN net_worth_change REAL DEFAULT 0.0;")
        conn.commit()

        # Populate initial baseline balance changes from snapshots if prev_balance is not set
        try:
            cursor.execute("SELECT id, balance FROM accounts WHERE prev_balance IS NULL;")
            uninit_accounts = cursor.fetchall()
            for u in uninit_accounts:
                acct_id = u["id"]
                curr_bal = float(u["balance"])
                cursor.execute("""
                    SELECT balance FROM account_snapshots
                    WHERE account_id = ?
                    ORDER BY id DESC LIMIT 2;
                """, (acct_id,))
                snaps = cursor.fetchall()
                if len(snaps) >= 2:
                    p_bal = float(snaps[1]["balance"])
                    chg = round(curr_bal - p_bal, 2)
                    cursor.execute("""
                        UPDATE accounts
                        SET prev_balance = ?, balance_change = ?
                        WHERE id = ?;
                    """, (p_bal, chg, acct_id))
                else:
                    cursor.execute("""
                        UPDATE accounts
                        SET prev_balance = ?, balance_change = 0.0
                        WHERE id = ?;
                    """, (curr_bal, acct_id))
            conn.commit()
        except Exception as e:
            print(f"[Finance DB] Baseline balance initialization error: {e}")

        # Run automatic deduplication in case duplicate accounts were pulled
        try:
            deduplicate_database_accounts(conn)
        except Exception as e:
            print(f"[Finance DB] Auto-deduplication check error: {e}")


def get_accounts():
    """Returns all accounts sorted by category and balance."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts
            ORDER BY
                CASE account_type
                    WHEN 'checking' THEN 1
                    WHEN 'savings' THEN 2
                    WHEN 'credit' THEN 3
                    WHEN 'investment' THEN 4
                    WHEN 'retirement' THEN 5
                    WHEN 'mortgage' THEN 6
                    WHEN 'loan' THEN 7
                    ELSE 8
                END,
                balance DESC;
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_account_by_id(account_id):
    """Retrieves an individual account by id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?;", (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def upsert_account(acc):
    """Inserts or updates an account."""
    now = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO accounts (
                id, institution, name, account_number_mask, account_type,
                balance, currency, apy_interest, rewards_status,
                credit_limit, vested_balance, holdings_summary,
                is_asset, is_manual, last_synced, created_at, simplefin_id,
                balance_change, prev_balance, balance_change_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                institution = excluded.institution,
                name = excluded.name,
                account_number_mask = COALESCE(excluded.account_number_mask, accounts.account_number_mask),
                account_type = excluded.account_type,
                balance = excluded.balance,
                currency = excluded.currency,
                apy_interest = COALESCE(excluded.apy_interest, accounts.apy_interest),
                rewards_status = COALESCE(excluded.rewards_status, accounts.rewards_status),
                credit_limit = COALESCE(excluded.credit_limit, accounts.credit_limit),
                vested_balance = COALESCE(excluded.vested_balance, accounts.vested_balance),
                holdings_summary = COALESCE(excluded.holdings_summary, accounts.holdings_summary),
                is_asset = excluded.is_asset,
                last_synced = excluded.last_synced,
                simplefin_id = COALESCE(excluded.simplefin_id, accounts.simplefin_id),
                balance_change = COALESCE(excluded.balance_change, accounts.balance_change),
                prev_balance = COALESCE(excluded.prev_balance, accounts.prev_balance),
                balance_change_at = COALESCE(excluded.balance_change_at, accounts.balance_change_at);
        """, (
            acc["id"], acc["institution"], acc["name"], acc.get("account_number_mask"),
            acc["account_type"], float(acc["balance"]), acc.get("currency", "USD"),
            acc.get("apy_interest"), acc.get("rewards_status"), float(acc.get("credit_limit", 0.0)),
            float(acc.get("vested_balance", 0.0)), acc.get("holdings_summary"),
            int(acc.get("is_asset", 1)), int(acc.get("is_manual", 0)),
            acc.get("last_synced", now), acc.get("created_at", now),
            acc.get("simplefin_id"),
            acc.get("balance_change"), acc.get("prev_balance"), acc.get("balance_change_at")
        ))
        conn.commit()


def update_account_metadata(
    account_id,
    name=None,
    institution=None,
    account_type=None,
    account_number_mask=None,
    balance=None,
    apy_interest=None,
    rewards_status=None,
    holdings_summary=None,
    credit_limit=None,
    is_asset=None,
    vested_balance=None,
    simplefin_id=None
):
    """Updates editable fields and metadata on an account."""
    with get_connection() as conn:
        cursor = conn.cursor()
        fields = []
        params = []
        if name is not None:
            fields.append("name = ?")
            params.append(str(name).strip())
        if institution is not None:
            fields.append("institution = ?")
            params.append(str(institution).strip())
        if account_type is not None:
            fields.append("account_type = ?")
            params.append(str(account_type).strip().lower())
        if account_number_mask is not None:
            fields.append("account_number_mask = ?")
            params.append(str(account_number_mask).strip())
        if balance is not None:
            fields.append("balance = ?")
            params.append(float(balance))
        if apy_interest is not None:
            fields.append("apy_interest = ?")
            params.append(apy_interest)
        if rewards_status is not None:
            fields.append("rewards_status = ?")
            params.append(rewards_status)
        if holdings_summary is not None:
            fields.append("holdings_summary = ?")
            params.append(holdings_summary)
        if credit_limit is not None:
            fields.append("credit_limit = ?")
            params.append(float(credit_limit))
        if is_asset is not None:
            fields.append("is_asset = ?")
            params.append(int(is_asset))
        if vested_balance is not None:
            fields.append("vested_balance = ?")
            params.append(float(vested_balance))
        if simplefin_id is not None:
            fields.append("simplefin_id = ?")
            clean_sfin = str(simplefin_id).strip() if simplefin_id else None
            params.append(clean_sfin)

        if not fields:
            return False

        params.append(account_id)
        query = f"UPDATE accounts SET {', '.join(fields)} WHERE id = ?;"
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount > 0


def delete_account(account_id):
    """Deletes an account (e.g. manual asset/liability, duplicate or obsolete account)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM account_snapshots WHERE account_id = ?;", (account_id,))
        cursor.execute("DELETE FROM accounts WHERE id = ?;", (account_id,))
        
        # Clean from order settings
        cursor.execute("SELECT key, value FROM settings WHERE key LIKE 'account_order_%';")
        for r in cursor.fetchall():
            try:
                orders = json.loads(r["value"])
                if account_id in orders:
                    orders = [x for x in orders if x != account_id]
                    cursor.execute("UPDATE settings SET value = ?, updated_at = ? WHERE key = ?;",
                                   (json.dumps(orders), datetime.now(APP_TIMEZONE).isoformat(), r["key"]))
            except Exception:
                pass

        conn.commit()
        return cursor.rowcount > 0


def deduplicate_database_accounts(conn=None):
    """
    Scans the accounts table for duplicated accounts (e.g. SimpleFIN synthetic 'sf_ACT-...'
    entries that correspond to base accounts) and cleanly merges them.
    Preserves all user customizations (APY, custom names, notes, limits) and sets
    the deterministic 'simplefin_id' link on the base accounts.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        from .simplefin_client import calculate_match_score, extract_masks_and_digits
    except (ImportError, ValueError):
        from simplefin_client import calculate_match_score, extract_masks_and_digits

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts;")
    all_accs = [dict(row) for row in cursor.fetchall()]

    base_accounts = [a for a in all_accs if not a["id"].startswith("sf_")]
    sf_accounts = [a for a in all_accs if a["id"].startswith("sf_")]

    if not sf_accounts or not base_accounts:
        if should_close:
            conn.close()
        return {"merged_count": 0, "merged_pairs": []}

    merged_pairs = []
    used_base_ids = set()

    for sf in sf_accounts:
        best_score = 0.0
        best_base = None
        for base in base_accounts:
            if base["id"] in used_base_ids:
                continue
            score = calculate_match_score(base, sf)
            if score > best_score:
                best_score = score
                best_base = base

        if best_base and best_score >= 450.0:
            used_base_ids.add(best_base["id"])
            real_sf_id = sf["id"].replace("sf_", "")
            
            # Mask update if local was empty/generic
            sf_masks = extract_masks_and_digits(sf.get("name") or "")
            best_mask = best_base.get("account_number_mask")
            if (not best_mask or best_mask.lower() in ("manual", "none", "")) and sf_masks:
                best_mask = f"...{sf_masks[0]}"

            # 1. Update base account with SimpleFIN link, new balance, last_synced
            cursor.execute("""
                UPDATE accounts
                SET simplefin_id = ?,
                    balance = ?,
                    last_synced = ?,
                    account_number_mask = COALESCE(?, account_number_mask)
                WHERE id = ?;
            """, (real_sf_id, float(sf["balance"]), sf["last_synced"], best_mask, best_base["id"]))

            # 2. Update snapshots pointing to the duplicate sf_ id
            cursor.execute("""
                UPDATE account_snapshots
                SET account_id = ?
                WHERE account_id = ?;
            """, (best_base["id"], sf["id"]))

            # 3. Delete the duplicate sf_ account from accounts table
            cursor.execute("DELETE FROM accounts WHERE id = ?;", (sf["id"],))

            merged_pairs.append({
                "simplefin_id": real_sf_id,
                "deleted_sf_id": sf["id"],
                "base_id": best_base["id"],
                "base_name": best_base["name"],
                "score": best_score
            })

    # Clean up account_order_* in settings
    if merged_pairs:
        deleted_ids = {p["deleted_sf_id"] for p in merged_pairs}
        cursor.execute("SELECT key, value FROM settings WHERE key LIKE 'account_order_%';")
        order_rows = cursor.fetchall()
        for r in order_rows:
            key = r["key"]
            try:
                order_list = json.loads(r["value"])
                cleaned_order = [x for x in order_list if x not in deleted_ids]
                if len(cleaned_order) != len(order_list):
                    cursor.execute("UPDATE settings SET value = ?, updated_at = ? WHERE key = ?;",
                                   (json.dumps(cleaned_order), datetime.now(APP_TIMEZONE).isoformat(), key))
            except Exception:
                pass

        # Recalculate any snapshots created during duplicated state
        cursor.execute("SELECT id, timestamp FROM snapshots WHERE note LIKE '%SimpleFIN live sync%' ORDER BY id DESC LIMIT 5;")
        sync_snaps = cursor.fetchall()
        for snap in sync_snaps:
            snap_id = snap["id"]
            cursor.execute("""
                SELECT 
                    a.account_type,
                    a.is_asset,
                    s.balance
                FROM account_snapshots s
                JOIN accounts a ON a.id = s.account_id
                WHERE s.snapshot_id = ?
                GROUP BY s.account_id;
            """, (snap_id,))
            acct_rows = cursor.fetchall()
            if acct_rows:
                liquid_cash = sum(r["balance"] for r in acct_rows if r["account_type"] in ("checking", "savings"))
                investments = sum(r["balance"] for r in acct_rows if r["account_type"] in ("investment", "retirement"))
                property_val = sum(r["balance"] for r in acct_rows if r["account_type"] in ("property", "real_estate"))
                mortgage_debt = sum(abs(r["balance"]) for r in acct_rows if r["account_type"] in ("mortgage", "loan"))
                credit_debt = sum(r["balance"] for r in acct_rows if r["account_type"] == "credit")
                
                total_assets = liquid_cash + investments + property_val
                total_liabilities = mortgage_debt + abs(credit_debt)
                net_worth = total_assets - total_liabilities
                
                cursor.execute("""
                    UPDATE snapshots SET
                        net_worth = ?,
                        total_assets = ?,
                        total_liabilities = ?,
                        liquid_cash = ?,
                        investments = ?,
                        mortgage_debt = ?,
                        credit_debt = ?
                    WHERE id = ?;
                """, (
                    round(net_worth, 2), round(total_assets, 2), round(total_liabilities, 2),
                    round(liquid_cash, 2), round(investments, 2), round(mortgage_debt, 2),
                    round(credit_debt, 2), snap_id
                ))

        conn.commit()

    if should_close:
        conn.close()

    return {
        "merged_count": len(merged_pairs),
        "merged_pairs": merged_pairs
    }


def record_snapshot(note="", net_worth_change=None):
    """
    Computes current snapshot metrics across all accounts and stores in `snapshots`.
    Also records per-account snapshot records.
    """
    accounts = get_accounts()
    if not accounts:
        return None

    now = datetime.now(APP_TIMEZONE).isoformat()

    liquid_cash = 0.0
    investments = 0.0
    property_value = 0.0
    mortgage_debt = 0.0
    credit_debt = 0.0

    for a in accounts:
        bal = float(a["balance"])
        atype = a["account_type"]

        if atype in ("checking", "savings"):
            liquid_cash += bal
        elif atype in ("investment", "retirement"):
            investments += bal
        elif atype in ("property", "real_estate"):
            property_value += bal
        elif atype == "mortgage":
            mortgage_debt += abs(bal)
        elif atype == "credit":
            credit_debt += bal
        elif atype == "loan":
            mortgage_debt += abs(bal)

    total_assets = liquid_cash + investments + property_value
    total_liabilities = mortgage_debt + abs(credit_debt)
    net_worth = total_assets - total_liabilities

    with get_connection() as conn:
        cursor = conn.cursor()

        # If net_worth_change not explicitly provided, preserve previous or compute
        if net_worth_change is None:
            cursor.execute("SELECT net_worth_change FROM snapshots WHERE net_worth_change IS NOT NULL ORDER BY id DESC LIMIT 1;")
            prev_row = cursor.fetchone()
            if prev_row and prev_row["net_worth_change"] is not None:
                net_worth_change = float(prev_row["net_worth_change"])
            else:
                net_worth_change = 0.0

        cursor.execute("""
            INSERT INTO snapshots (
                timestamp, net_worth, total_assets, total_liabilities,
                liquid_cash, investments, mortgage_debt, credit_debt, note,
                net_worth_change
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            now, round(net_worth, 2), round(total_assets, 2), round(total_liabilities, 2),
            round(liquid_cash, 2), round(investments, 2), round(mortgage_debt, 2),
            round(credit_debt, 2), note or "Live sync snapshot", round(float(net_worth_change), 2)
        ))
        snapshot_id = cursor.lastrowid

        for a in accounts:
            cursor.execute("""
                INSERT INTO account_snapshots (snapshot_id, account_id, balance, timestamp)
                VALUES (?, ?, ?, ?);
            """, (snapshot_id, a["id"], float(a["balance"]), now))

        conn.commit()
        return snapshot_id


def get_historical_snapshots(timeframe="all"):
    """
    Returns time series snapshots formatted for Chart.js.
    Supports timeframes: '1m', '3m', '6m', '1y', 'all'.
    """
    now = datetime.now(APP_TIMEZONE)
    cutoff = None

    timeframe_lower = (timeframe or "all").lower()
    if timeframe_lower == "1m":
        cutoff = (now - timedelta(days=31)).isoformat()
    elif timeframe_lower == "3m":
        cutoff = (now - timedelta(days=92)).isoformat()
    elif timeframe_lower == "6m":
        cutoff = (now - timedelta(days=183)).isoformat()
    elif timeframe_lower == "1y":
        cutoff = (now - timedelta(days=366)).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        if cutoff:
            cursor.execute("""
                SELECT * FROM snapshots
                WHERE timestamp >= ?
                ORDER BY timestamp ASC;
            """, (cutoff,))
        else:
            cursor.execute("""
                SELECT * FROM snapshots
                ORDER BY timestamp ASC;
            """)
        rows = [dict(r) for r in cursor.fetchall()]

    # Check if all snapshots share the same calendar day
    dates_set = set()
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["timestamp"])
            dates_set.add(dt.strftime("%Y-%m-%d"))
        except Exception:
            dates_set.add(r["timestamp"][:10])

    is_single_day = len(dates_set) <= 1

    if not is_single_day:
        # Group by calendar date: pick the latest snapshot of each day for clean multi-day trajectory
        daily_latest = {}
        for r in rows:
            ts = r["timestamp"]
            try:
                dt = datetime.fromisoformat(ts)
                day_key = dt.strftime("%Y-%m-%d")
            except Exception:
                day_key = ts[:10]
            daily_latest[day_key] = r  # later snapshots on same day overwrite earlier ones
        filtered_rows = list(daily_latest.values())
    else:
        filtered_rows = rows

    labels = []
    net_worth = []
    assets = []
    liabilities = []
    liquid_cash = []
    investments = []
    mortgage = []
    credit = []

    for r in filtered_rows:
        ts = r["timestamp"]
        try:
            dt = datetime.fromisoformat(ts)
            if is_single_day:
                formatted_date = dt.strftime("%b %d, %I:%M %p")
            else:
                formatted_date = dt.strftime("%b %d, %Y")
        except Exception:
            formatted_date = ts[:10]

        labels.append(formatted_date)
        net_worth.append(round(r["net_worth"], 2))
        assets.append(round(r["total_assets"], 2))
        liabilities.append(round(r["total_liabilities"], 2))
        liquid_cash.append(round(r["liquid_cash"], 2))
        investments.append(round(r["investments"], 2))
        mortgage.append(round(r["mortgage_debt"], 2))
        credit.append(round(r["credit_debt"], 2))

    return {
        "timeframe": timeframe_lower,
        "labels": labels,
        "net_worth": net_worth,
        "assets": assets,
        "liabilities": liabilities,
        "liquid_cash": liquid_cash,
        "investments": investments,
        "mortgage": mortgage,
        "credit": credit,
        "count": len(labels)
    }


def get_summary():
    """Computes high-level KPI metrics for the header cards."""
    accounts = get_accounts()
    liquid_cash = 0.0
    investments = 0.0
    property_value = 0.0
    mortgage_debt = 0.0
    credit_debt = 0.0
    total_credit_limit = 0.0
    vested_investments = 0.0

    categorized = {
        "cash": [],
        "credit": [],
        "investments": [],
        "mortgage": [],
        "property": []
    }

    last_sync_timestamp = None

    for a in accounts:
        bal = float(a["balance"])
        atype = a["account_type"]
        last_sync = a.get("last_synced")
        if last_sync and (not last_sync_timestamp or last_sync > last_sync_timestamp):
            last_sync_timestamp = last_sync

        if atype in ("checking", "savings"):
            liquid_cash += bal
            categorized["cash"].append(a)
        elif atype == "credit":
            limit = float(a.get("credit_limit") or 0.0)
            total_credit_limit += limit
            credit_debt += bal
            categorized["credit"].append(a)
        elif atype in ("investment", "retirement"):
            investments += bal
            vested_investments += float(a.get("vested_balance") or bal)
            categorized["investments"].append(a)
        elif atype in ("property", "real_estate"):
            property_value += bal
            categorized["property"].append(a)
        elif atype in ("mortgage", "loan"):
            mortgage_debt += abs(bal)
            categorized["mortgage"].append(a)

    total_assets = liquid_cash + investments + property_value
    total_liabilities = mortgage_debt + abs(credit_debt)
    net_worth = total_assets - total_liabilities
    home_equity = property_value - mortgage_debt

    credit_utilization = 0.0
    if total_credit_limit > 0:
        credit_utilization = (abs(credit_debt) / total_credit_limit) * 100.0

    # Get latest recorded net worth change
    net_worth_change = 0.0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT net_worth_change FROM snapshots WHERE net_worth_change IS NOT NULL ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        if row and row["net_worth_change"] is not None:
            net_worth_change = float(row["net_worth_change"])

    return {
        "net_worth": round(net_worth, 2),
        "net_worth_change": round(net_worth_change, 2),
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "liquid_cash": round(liquid_cash, 2),
        "investments": round(investments, 2),
        "vested_investments": round(vested_investments, 2),
        "property_value": round(property_value, 2),
        "home_equity": round(home_equity, 2),
        "mortgage_debt": round(mortgage_debt, 2),
        "credit_debt": round(credit_debt, 2),
        "total_credit_limit": round(total_credit_limit, 2),
        "credit_utilization": round(credit_utilization, 2),
        "last_sync": last_sync_timestamp,
        "accounts_count": len(accounts),
        "categories": categorized
    }


def get_setting(key, default=None):
    """Retrieves a setting value."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    """Sets a setting value."""
    now = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at;
        """, (key, str(value), now))
        conn.commit()


# ===========================================================================
# BUDGET & RECURRING EXPENSES / INCOMES
# ===========================================================================



def get_budget_items(category=None):
    """Returns all budget items optionally filtered by category ('income' or 'expense')."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("""
                SELECT * FROM budget_items
                WHERE category = ?
                ORDER BY sort_order ASC, id ASC;
            """, (category,))
        else:
            cursor.execute("""
                SELECT * FROM budget_items
                ORDER BY category DESC, sort_order ASC, id ASC;
            """)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("details_json"):
                try:
                    d["details"] = json.loads(d["details_json"])
                except Exception:
                    d["details"] = None
            else:
                d["details"] = None
            result.append(d)
        return result


def get_budget_item_by_id(item_id):
    """Retrieves a single budget item by id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM budget_items WHERE id = ?;", (item_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("details_json"):
            try:
                d["details"] = json.loads(d["details_json"])
            except Exception:
                d["details"] = None
        else:
            d["details"] = None
        return d


def upsert_budget_item(item):
    """Creates or updates a budget item."""
    now = datetime.now(APP_TIMEZONE).isoformat()
    item_id = item.get("id")
    category = item.get("category", "expense")
    name = item.get("name", "").strip()
    amount = float(item.get("amount", 0.0))
    frequency = item.get("frequency", "monthly")
    raw_amount = float(item.get("raw_amount", amount))
    tax_status = item.get("tax_status", "post-tax")
    due_date = item.get("due_date", "")
    portal_url = item.get("portal_url", "")
    notes = item.get("notes", "")
    details_json = item.get("details_json")
    if isinstance(details_json, dict):
        details_json = json.dumps(details_json)
    is_active = int(item.get("is_active", 1))
    sort_order = int(item.get("sort_order", 0))

    with get_connection() as conn:
        cursor = conn.cursor()
        if item_id:
            cursor.execute("""
                UPDATE budget_items SET
                    category = ?,
                    name = ?,
                    amount = ?,
                    frequency = ?,
                    raw_amount = ?,
                    tax_status = ?,
                    due_date = ?,
                    portal_url = ?,
                    notes = ?,
                    details_json = COALESCE(?, details_json),
                    is_active = ?,
                    sort_order = ?,
                    updated_at = ?
                WHERE id = ?;
            """, (
                category, name, amount, frequency, raw_amount,
                tax_status, due_date, portal_url, notes, details_json,
                is_active, sort_order, now, item_id
            ))
            conn.commit()
            return item_id
        else:
            cursor.execute("""
                INSERT INTO budget_items (
                    category, name, amount, frequency, raw_amount,
                    tax_status, due_date, portal_url, notes, details_json,
                    is_active, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                category, name, amount, frequency, raw_amount,
                tax_status, due_date, portal_url, notes, details_json,
                is_active, sort_order, now, now
            ))
            conn.commit()
            return cursor.lastrowid


def delete_budget_item(item_id):
    """Deletes a budget item by id."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM budget_items WHERE id = ?;", (item_id,))
        conn.commit()
        return cursor.rowcount > 0


def toggle_budget_item_active(item_id):
    """Toggles active/inactive state of a budget item."""
    now = datetime.now(APP_TIMEZONE).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE budget_items
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
                updated_at = ?
            WHERE id = ?;
        """, (now, item_id))
        conn.commit()
        return cursor.rowcount > 0


def get_budget_summary():
    """Computes budget totals (monthly incomes, expenses, net monthly cashflow)."""
    items = get_budget_items()
    incomes = [i for i in items if i["category"] == "income"]
    expenses = [i for i in items if i["category"] == "expense"]

    total_monthly_income_posttax = 0.0
    total_monthly_income_pretax = 0.0
    total_monthly_expenses = 0.0

    for inc in incomes:
        if inc.get("is_active", 1):
            amt = float(inc.get("amount") or 0.0)
            if inc.get("tax_status") == "pre-tax":
                total_monthly_income_pretax += amt
            else:
                total_monthly_income_posttax += amt

    for exp in expenses:
        if exp.get("is_active", 1):
            total_monthly_expenses += float(exp.get("amount") or 0.0)

    # Combined gross & take-home cashflow
    total_income_combined = total_monthly_income_posttax + total_monthly_income_pretax
    net_monthly_cash_flow = total_monthly_income_posttax - total_monthly_expenses

    return {
        "total_monthly_income_posttax": round(total_monthly_income_posttax, 2),
        "total_monthly_income_pretax": round(total_monthly_income_pretax, 2),
        "total_income_combined": round(total_income_combined, 2),
        "total_monthly_expenses": round(total_monthly_expenses, 2),
        "net_monthly_cash_flow": round(net_monthly_cash_flow, 2),
        "incomes": incomes,
        "expenses": expenses
    }

