# SimpleFIN Connection and Sync

Source: [modules/Finance/simplefin_client.py](../../modules/Finance/simplefin_client.py)

---

## 1. Connecting

1. Create a SimpleFIN Bridge app token (the "claim token") at the bridge.
2. Paste it into the dashboard settings, which calls `POST /api/finance/claim` with `{"claim_token": "..."}`.
3. `decode_claim_token()` accepts a claim URL, a base64-encoded claim URL, or a bare token (turned into `https://beta-bridge.simplefin.org/simplefin/claim/<token>`).
4. `claim_access_url()` POSTs to that URL. A `200` response body is the permanent **access URL**, which is stored (see [architecture.md](architecture.md#5-secrets)). The route then runs a first sync.

If you already have an access URL, send `{"access_url": "..."}` instead and it is saved directly. `POST /api/finance/disconnect` clears both copies.

---

## 2. Sync flow (`sync_simplefin_accounts`)

`POST /api/finance/sync` runs these steps:

1. Run `deduplicate_database_accounts()` so the starting state is clean.
2. **No access URL configured**: record a baseline snapshot, store the sync time, and return `success: true, is_simulated: true`.
3. Otherwise `GET <access_url>/accounts` with HTTP Basic auth taken from the URL (25 second timeout). A non-200 response returns `success: false` with the status. Network errors return `Connection error syncing SimpleFIN`.
4. For each incoming account, find the local row with `match_existing_account()`:
   * **Primary**: `simplefin_id` or `id` equals the bridge ID (or `sf_<id>`).
   * **Fallback**: for rows with no `simplefin_id` yet, `calculate_match_score()` compares institution, name, mask digits and balance. A score of 450 or more links the row. A row can only be matched once per sync.
5. Unmatched accounts become new rows with ID `sf_<bridge id>`. Their type comes from `infer_account_type()` (keyword heuristics on the institution and name, with a balance below -1000 treated as a loan).
6. Matched accounts keep user edits (name, institution, type, APY, rewards, limit, holdings). Only the balance and sync time are refreshed.
7. A positive balance on a `mortgage` account is flipped to negative.
8. **Balance change tracking**:
   * If at least one balance changed, changed accounts store `balance_change = new - old` and every other account is set to `0.0`.
   * If nothing changed, existing `balance_change` values are left alone, so the dashboard does not show `+$0.00` everywhere after a no-op sync.
9. **Net worth change** (the number next to Net Worth on the dashboard): when at least one balance changed, it is the net worth after this sync minus the net worth just before it. A sync where nothing changed keeps the previous value, so the figure always reflects the last two syncs where something moved. It is stored on the snapshot, and edits to manual accounts carry it forward unchanged.
10. Record a snapshot and store `simplefin_last_sync`.

The per-account `last_synced` value is the bridge's `balance-date` when present.

---

## 3. Response shape

```json
{
  "success": true,
  "is_simulated": false,
  "total_checked": 12,
  "refreshed_count": 0,
  "snapshot_id": 41,
  "message": "All 12 accounts verified. ...",
  "synced_at": "2026-10-12T09:00:00-07:00",
  "accounts": [ { "account_id": "sf_ACT-1", "balance": 1200.5, "has_balance_change": true, "bal_diff": 75.25 } ]
}
```

Failures return `{"success": false, "error": "..."}` with HTTP 400 (or 500 for unexpected exceptions).
