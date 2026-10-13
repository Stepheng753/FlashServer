import base64
import re
from urllib.parse import urlparse
import requests
from datetime import datetime
from .config import (
    APP_TIMEZONE,
    SIMPLEFIN_AUTH_KEY,
    SIMPLEFIN_CLAIM_KEY,
    SIMPLEFIN_LAST_SYNC_KEY,
    get_secret,
    save_secret
)
from .db import (
    get_setting,
    set_setting,
    get_accounts,
    upsert_account,
    record_snapshot,
    deduplicate_database_accounts,
    get_summary
)


def decode_claim_token(raw_token: str) -> str:
    """
    Decodes the user's claim token.
    SimpleFIN claim tokens are base64-encoded claim URLs, or directly a claim URL.
    """
    token = raw_token.strip()
    if token.startswith("http://") or token.startswith("https://"):
        return token

    # Attempt base64 decoding
    try:
        decoded = base64.b64decode(token).decode("utf-8").strip()
        if decoded.startswith("http://") or decoded.startswith("https://"):
            return decoded
    except Exception:
        pass

    # If it's just the token suffix, build the full URL
    return f"https://beta-bridge.simplefin.org/simplefin/claim/{token}"


def claim_access_url(claim_token_input: str) -> dict:
    """
    Exchanges a one-time SimpleFIN claim token for a permanent access URL.
    """
    claim_url = decode_claim_token(claim_token_input)
    try:
        res = requests.post(claim_url, timeout=15)
        if res.status_code == 200:
            access_url = res.text.strip()
            if not access_url.startswith("http"):
                return {"success": False, "error": f"Unexpected response from SimpleFIN: {access_url}"}

            save_secret("SIMPLEFIN_ACCESS_URL", access_url)
            set_setting(SIMPLEFIN_AUTH_KEY, access_url)
            set_setting(SIMPLEFIN_CLAIM_KEY, claim_token_input[:10] + "...")
            return {
                "success": True,
                "message": "Successfully claimed SimpleFIN Access URL!",
                "access_url": access_url
            }
        else:
            return {
                "success": False,
                "error": f"SimpleFIN server returned status {res.status_code}: {res.text}"
            }
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Failed to reach SimpleFIN Bridge: {str(e)}"}


def get_stored_access_url() -> str:
    """Returns stored SimpleFIN Access URL or empty string, checking secrets.json first."""
    url = get_secret("SIMPLEFIN_ACCESS_URL")
    if url:
        return url
    return get_setting(SIMPLEFIN_AUTH_KEY, "")


def normalize_institution_name(name: str) -> str:
    """Normalizes financial institution name for fuzzy/token comparison."""
    if not name:
        return ""
    s = name.lower()
    stopwords = [
        "national association", "credit union", "netbenefits", "investments",
        "investment", "financial", "services", "corporation", "bank",
        "corp", "inc", "llc", "usa", "us", "n.a.", "na", "online", "co", "by quicken loans"
    ]
    for w in stopwords:
        s = re.sub(r'\b' + re.escape(w) + r'\b', ' ', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s.strip()


def extract_masks_and_digits(text: str) -> list[str]:
    """Extracts potential account number mask digits (3 to 8 digits)."""
    if not text:
        return []
    results = []
    for m in re.finditer(r'(?:\.\.\.|\*|x|-|\bending in\s*|\()(\d{3,8})\)?', text, re.IGNORECASE):
        results.append(m.group(1))
    for m in re.finditer(r'\b(\d{3,6})\b', text):
        val = m.group(1)
        if val not in results:
            results.append(val)
    return results


def calculate_match_score(acc, sf_acc) -> float:
    """
    Computes a deterministic match confidence score between an existing DB account
    and an incoming SimpleFIN account object.
    """
    sf_id = str(sf_acc.get("id") or "").strip()
    sf_name = str(sf_acc.get("name") or "").strip()
    sf_org = str(sf_acc.get("org", {}).get("name") if isinstance(sf_acc.get("org"), dict) else sf_acc.get("institution") or "").strip()
    try:
        sf_balance = float(sf_acc.get("balance", 0.0))
    except (ValueError, TypeError):
        sf_balance = 0.0

    acc_id = str(acc.get("id") or "").strip()
    acc_sfin_id = str(acc.get("simplefin_id") or "").strip()
    acc_name = str(acc.get("name") or "").strip()
    acc_inst = str(acc.get("institution") or "").strip()
    acc_mask = str(acc.get("account_number_mask") or "").strip()
    try:
        acc_balance = float(acc.get("balance", 0.0))
    except (ValueError, TypeError):
        acc_balance = 0.0

    # 1. Exact SimpleFIN ID Match -> Tier 1 (10,000 pts)
    if sf_id:
        if acc_sfin_id and (acc_sfin_id == sf_id or acc_sfin_id == f"sf_{sf_id}"):
            return 10000.0
        if acc_id == sf_id or acc_id == f"sf_{sf_id}":
            return 10000.0
        clean_sf_id = sf_id.replace("ACT-", "").replace("sf_", "")
        if clean_sf_id and (clean_sf_id in acc_id or clean_sf_id in acc_sfin_id):
            return 9500.0

    score = 0.0

    # 2. Institution Match
    norm_sf_org = normalize_institution_name(sf_org)
    norm_acc_inst = normalize_institution_name(acc_inst)
    
    inst_matched = False
    if norm_sf_org and norm_acc_inst:
        if norm_sf_org == norm_acc_inst or norm_sf_org in norm_acc_inst or norm_acc_inst in norm_sf_org:
            inst_matched = True
            score += 400.0
        elif any(k in norm_sf_org and k in norm_acc_inst for k in ["schwab", "wells", "chase", "fidelity", "wealthfront", "rocket"]):
            inst_matched = True
            score += 400.0

    # If institutions are completely different and both exist, do not match
    if not inst_matched and norm_sf_org and norm_acc_inst:
        return 0.0

    # 3. Account Mask / Number Matching (Tier 2 - 500-600 pts)
    sf_masks = extract_masks_and_digits(sf_name)
    acc_masks = extract_masks_and_digits(acc_mask) + extract_masks_and_digits(acc_id)
    
    mask_matched = False
    for sm in sf_masks:
        for am in acc_masks:
            if sm == am:
                score += 600.0
                mask_matched = True
                break
            elif len(sm) >= 3 and len(am) >= 3 and (sm.endswith(am) or am.endswith(sm)):
                score += 500.0
                mask_matched = True
                break
        if mask_matched:
            break

    # 4. Product Name Keyword Overlap (Tier 3 - 200-350 pts)
    lower_sf_name = sf_name.lower()
    lower_acc_name = acc_name.lower()
    
    keywords = [
        ("freedom unlimited", 350.0),
        ("sapphire preferred", 350.0),
        ("active cash", 350.0),
        ("everyday checking", 350.0),
        ("high-yield savings", 300.0),
        ("high yield savings", 300.0),
        ("roth ira", 350.0),
        ("traditional ira", 350.0),
        ("traditonal ira", 350.0),
        ("taxable brokerage", 300.0),
        ("brokerage", 250.0),
        ("401k", 250.0),
        ("401(k)", 250.0),
        ("savings", 100.0),
        ("checking", 100.0),
        ("mortgage", 200.0)
    ]
    for kw, pts in keywords:
        if kw in lower_sf_name and kw in lower_acc_name:
            score += pts
        elif kw in lower_sf_name and kw in acc_id.lower():
            score += pts

    # Acronym matching: E.g., ASH in local name vs American Specialty Health in SF name
    if "ash" in lower_acc_name and "american specialty health" in lower_sf_name:
        score += 400.0

    # Rate/APY text matching: E.g. "3.55%" in SF name matches "3.55%" in acc APY
    acc_apy = str(acc.get("apy_interest") or "")
    if "3.55" in lower_sf_name and "3.55" in acc_apy:
        score += 200.0

    # 5. Balance Match / Proximity (Tiebreaker)
    if sf_balance != 0.0 and acc_balance != 0.0:
        if abs(sf_balance - acc_balance) < 0.01 or abs(abs(sf_balance) - abs(acc_balance)) < 0.01:
            score += 150.0

    # Prevent matching manual-only assets (property, promissory notes)
    if acc.get("is_manual") and ("property" in acc_id or "promissory" in acc_id or "real_estate" in acc.get("account_type", "") or "note" in acc_id):
        if not inst_matched:
            return 0.0

    return score


def infer_account_type(name: str, org_name: str, balance: float) -> str:
    """Heuristic helper to classify accounts based on standard financial terms."""
    combined = f"{org_name} {name}".lower()
    if any(k in combined for k in ["mortgage", "home loan"]):
        return "mortgage"
    if any(k in combined for k in ["401k", "401(k)", "ira", "roth", "retirement", "pension", "superannuation"]):
        return "retirement"
    if any(k in combined for k in ["brokerage", "stock", "trading", "securities"]) or ("schwab" in combined and "individual" in combined):
        return "investment"
    if any(k in combined for k in ["card", "credit", "visa", "mastercard", "amex", "freedom", "sapphire", "active cash"]):
        return "credit"
    if any(k in combined for k in ["savings", "hysa", "money market", "wealthfront"]):
        return "savings"
    if any(k in combined for k in ["checking", "share draft", "deposit"]):
        return "checking"
    if balance < -1000:
        return "loan"
    return "checking"


def match_existing_account(existing_accounts, sf_account, used_ids=None):
    """
    Matches an incoming SimpleFIN account to an existing account in SQLite.
    Primary rule: Direct SimpleFIN ID match (simplefin_id or account id).
    Secondary fallback: Matches newly created unlinked accounts by institution & mask.
    """
    if used_ids is None:
        used_ids = set()

    sf_id = str(sf_account.get("id") or "").strip()
    if not sf_id:
        return None

    # 1. Primary: Direct SimpleFIN ID match
    for acc in existing_accounts:
        if acc["id"] in used_ids:
            continue
        acc_sfin = str(acc.get("simplefin_id") or "").strip()
        acc_id = str(acc.get("id") or "").strip()
        if acc_sfin and (acc_sfin == sf_id or acc_sfin == f"sf_{sf_id}"):
            return acc
        if acc_id == sf_id or acc_id == f"sf_{sf_id}":
            return acc

    # 2. Secondary fallback for unlinked base accounts (where simplefin_id is not yet set)
    best_score = 0.0
    best_match = None
    for acc in existing_accounts:
        if acc["id"] in used_ids or acc.get("simplefin_id"):
            continue
        score = calculate_match_score(acc, sf_account)
        if score > best_score:
            best_score = score
            best_match = acc

    if best_match and best_score >= 450.0:
        return best_match

    return None


def sync_simplefin_accounts() -> dict:
    """
    Connects to SimpleFIN Bridge, fetches live account data,
    deterministically updates local accounts (avoiding duplicate creation),
    and records a new historical snapshot.
    """
    access_url = get_stored_access_url()
    now_iso = datetime.now(APP_TIMEZONE).isoformat()

    # Pre-sync deduplication pass to ensure DB state is clean
    try:
        deduplicate_database_accounts()
    except Exception as e:
        print(f"[SimpleFIN Sync] Deduplication pass error: {e}")

    if not access_url:
        # If no access URL is configured yet, record current baseline snapshot
        record_snapshot(note="Manual sync (Pre-SimpleFIN baseline)")
        set_setting(SIMPLEFIN_LAST_SYNC_KEY, now_iso)
        return {
            "success": True,
            "is_simulated": True,
            "message": "Synced current accounts & recorded snapshot. To pull live institutional balances, paste your SimpleFIN Claim Token in Settings!",
            "synced_at": now_iso
        }

    # Fetch from SimpleFIN Bridge
    try:
        parsed = urlparse(access_url)
        auth = None
        clean_url = access_url
        if parsed.username and parsed.password:
            auth = (parsed.username, parsed.password)
            clean_url = f"{parsed.scheme}://{parsed.hostname}{':' + str(parsed.port) if parsed.port else ''}{parsed.path}"

        endpoint = f"{clean_url.rstrip('/')}/accounts"
        res = requests.get(endpoint, auth=auth, timeout=25)

        if res.status_code != 200:
            return {
                "success": False,
                "error": f"SimpleFIN Bridge responded with status {res.status_code}: {res.text[:200]}"
            }

        data = res.json()
        sf_accounts = data.get("accounts", [])
        existing_accounts = get_accounts()

        refreshed_count = 0
        matched_ids = set()
        sync_details = []

        for sf_acc in sf_accounts:
            sf_id = str(sf_acc.get("id") or "").strip()
            org = sf_acc.get("org", {})
            org_name = org.get("name") or "Financial Institution"
            name = sf_acc.get("name") or "Account"
            currency = sf_acc.get("currency") or "USD"

            try:
                balance = float(sf_acc.get("balance", 0.0))
            except (ValueError, TypeError):
                balance = 0.0

            matched = match_existing_account(existing_accounts, sf_acc, used_ids=matched_ids)

            sf_masks = extract_masks_and_digits(name)

            if matched:
                matched_ids.add(matched["id"])
                target_id = matched["id"]
                account_type = matched["account_type"]
                is_asset = matched["is_asset"]
                apy = matched.get("apy_interest")
                rewards = matched.get("rewards_status")
                limit = float(matched.get("credit_limit") or 0.0)
                vested = float(matched.get("vested_balance") or balance)
                holdings = matched.get("holdings_summary")
                mask = matched.get("account_number_mask")
                if (not mask or mask.lower() in ("manual", "none", "")) and sf_masks:
                    mask = f"...{sf_masks[0]}"
            else:
                target_id = f"sf_{sf_id}" if sf_id else f"sf_{re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())}"
                account_type = infer_account_type(name, org_name, balance)
                is_asset = 0 if account_type in ("mortgage", "credit", "loan") else 1
                apy = None
                rewards = None
                limit = 0.0
                vested = balance if is_asset else 0.0
                holdings = None
                mask = f"...{sf_masks[0]}" if sf_masks else None

            # Extract institutional sync timestamp from SimpleFIN (balance-date)
            # This is the exact time MX/SimpleFIN connected to the bank's API
            bdate_epoch = sf_acc.get("balance-date")
            if bdate_epoch:
                try:
                    acct_synced_at = datetime.fromtimestamp(float(bdate_epoch), tz=APP_TIMEZONE).isoformat()
                except Exception:
                    acct_synced_at = now_iso
            else:
                acct_synced_at = now_iso

            # Normalization for liability convention
            if account_type == "mortgage" and balance > 0:
                balance = -abs(balance)

            final_inst = org_name if not matched else matched["institution"]
            final_name = name if not matched else matched["name"]

            # Compare incoming bank_api_polled_at and balance against DB state
            prev_synced_at = matched.get("last_synced") if matched else None
            try:
                prev_balance = float(matched.get("balance", 0.0)) if matched else None
            except (ValueError, TypeError):
                prev_balance = None

            is_fresh = False
            if matched is None:
                is_fresh = True  # New account discovered
            elif not prev_synced_at:
                is_fresh = True  # First time getting bank_api_polled_at
            # Check if balance changed
            has_balance_change = False
            bal_diff = 0.0
            if prev_balance is not None and abs(balance - prev_balance) > 0.001:
                has_balance_change = True
                bal_diff = round(balance - prev_balance, 2)

            sync_details.append({
                "account_id": target_id,
                "institution": final_inst,
                "name": final_name,
                "account_number_mask": mask,
                "account_type": account_type,
                "balance": balance,
                "currency": currency,
                "apy_interest": apy,
                "rewards_status": rewards,
                "credit_limit": limit,
                "vested_balance": vested,
                "holdings_summary": holdings,
                "is_asset": is_asset,
                "is_manual": 0 if matched is None else matched.get("is_manual", 0),
                "last_synced": acct_synced_at,
                "simplefin_id": sf_id,
                "bank_api_polled_at": acct_synced_at,
                "prev_polled_at": prev_synced_at,
                "prev_balance": prev_balance,
                "is_fresh": is_fresh,
                "has_balance_change": has_balance_change,
                "bal_diff": bal_diff,
                "bridge_pull_time": now_iso,
                "matched": matched is not None
            })

        total_checked = len(sf_accounts)
        any_account_changed = any(d["has_balance_change"] for d in sync_details)

        # Upsert accounts to DB
        # Rule: If 0 accounts changed upstream, preserve existing balance_change (do not set +$0.00 on everything)
        # If at least 1 account changed, update changed accounts with their difference and unchanged accounts with 0.0
        for item in sync_details:
            acct_payload = {
                "id": item["account_id"],
                "institution": item["institution"],
                "name": item["name"],
                "account_number_mask": item["account_number_mask"],
                "account_type": item["account_type"],
                "balance": item["balance"],
                "currency": item["currency"],
                "apy_interest": item["apy_interest"],
                "rewards_status": item["rewards_status"],
                "credit_limit": item["credit_limit"],
                "vested_balance": item["vested_balance"],
                "holdings_summary": item["holdings_summary"],
                "is_asset": item["is_asset"],
                "is_manual": item["is_manual"],
                "last_synced": item["last_synced"],
                "simplefin_id": item["simplefin_id"]
            }

            if any_account_changed:
                if item["has_balance_change"]:
                    acct_payload["balance_change"] = item["bal_diff"]
                    acct_payload["prev_balance"] = item["prev_balance"]
                    acct_payload["balance_change_at"] = now_iso
                else:
                    acct_payload["balance_change"] = 0.0
                    acct_payload["prev_balance"] = item["balance"]
                    acct_payload["balance_change_at"] = now_iso
            else:
                # 0 accounts changed: preserve existing values via NULL in upsert
                acct_payload["balance_change"] = None
                acct_payload["prev_balance"] = None
                acct_payload["balance_change_at"] = None

            upsert_account(acct_payload)

        # Record a fresh historical snapshot
        # Compute net worth change if accounts changed; otherwise preserve previous
        net_worth_change = None
        if any_account_changed:
            old_summary = get_summary()
            old_nw = float(old_summary.get("net_worth") or 0.0)
            # Re-fetch fresh summary after upsert
            fresh_summary = get_summary()
            new_nw = float(fresh_summary.get("net_worth") or 0.0)
            net_worth_change = round(new_nw - old_nw, 2)

        snapshot_id = record_snapshot(
            note=f"SimpleFIN sync ({refreshed_count} refreshed, {total_checked} checked)",
            net_worth_change=net_worth_change
        )
        set_setting(SIMPLEFIN_LAST_SYNC_KEY, now_iso)

        if refreshed_count > 0:
            summary_message = f"Synced {refreshed_count} refreshed account{'s' if refreshed_count != 1 else ''} from bank API ({total_checked} accounts verified)."
        else:
            summary_message = f"All {total_checked} accounts verified. Bank data is up to date (0 accounts refreshed since last poll)."

        return {
            "success": True,
            "is_simulated": False,
            "updated_count": refreshed_count,
            "refreshed_count": refreshed_count,
            "total_checked": total_checked,
            "snapshot_id": snapshot_id,
            "message": summary_message,
            "synced_at": now_iso,
            "accounts": sync_details
        }

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection error syncing SimpleFIN: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Error parsing SimpleFIN payload: {str(e)}"}
