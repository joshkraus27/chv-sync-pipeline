# Setup & First-Run Guide

Everything needed to take this repo from "just pushed" to "syncing hourly into
Supabase." Do the steps in order.

---

## 1. Apply the database migrations (one time)

Before the first sync, the target tables need the sync columns and unique
constraints the upserts rely on.

1. Open **Supabase → SQL Editor**.
2. Run the migrations in `supabase/migrations/` (they're idempotent — safe to
   run more than once). The `places` table needs the GeoDirectory columns and
   the `place_id` unique constraint; the `events` table needs `source_id`
   (unique) + `source`.
3. Sanity check:
   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_name = 'places' AND column_name = 'place_id';
   ```
   You should get one row back.

---

## 2. Gather the secret values

| Secret | Where to find it |
| --- | --- |
| **`GEODIR_BASE_URL`** | The GeoDirectory source site, no trailing slash (it's stripped anyway). Point at a staging host pre-launch, the production site after. |
| **`GEODIR_BASIC_AUTH`** | Only needed while the source site sits behind `.htpasswd` (staging). Format `username:password` (single colon separator). Delete once the site is public. |
| **`YODEL_FEED_URL`** | The Yodel widget JSON export URL. The feed is unauthenticated — the access token is baked into the URL path — so treat the whole URL as a secret. |
| **`SUPABASE_URL`** | Supabase Dashboard → **Project Settings → API → Project URL**. |
| **`SUPABASE_SERVICE_ROLE_KEY`** | Supabase Dashboard → **Project Settings → API → Project API keys → `service_role`** (click *Reveal*). **This is a secret admin key — never commit it, never put it in the app.** The sync needs it to write; the anon key won't work. |

---

## 3. Add the secrets in GitHub

For **each** secret:

1. Go to the repo → **Settings** → **Secrets and variables** → **Actions**.
2. Click **New repository secret**.
3. Enter the **Name** exactly as in the table above (case-sensitive) and paste
   the **Secret** value.
4. Click **Add secret**.

---

## 4. Trigger the first runs manually

1. Repo → **Actions** tab.
2. Select **GeoDirectory Sync** in the left sidebar.
3. Click **Run workflow** (top right) → keep branch `main` → **Run workflow**.
4. Click into the running job to **watch the logs in real time**.
5. Repeat for **Yodel Events Sync**.

Things to look for in the GeoDirectory sync logs:
- `HTTP Basic Auth configured (staging mode)` — auth is wired (staging only).
- `Page N: … listings` lines — pagination is working.
- `After whitelist filter: … listings (… excluded)` — the whitelist is matching.
- `Pipeline summary:` — the per-stage counts (filters, dedup, exclusions).
- `Sync complete: N inserted/updated, 0 errors` — success.

---

## 5. Verify it worked

**In Supabase SQL Editor:**
```sql
SELECT COUNT(*) FROM places WHERE source = 'geodirectory';
```
Expected: roughly **800–1500** rows, depending on how many listings match the
whitelist.

Useful follow-ups:
```sql
-- Distribution across the iOS PlaceType buckets
SELECT type, COUNT(*) FROM places WHERE source = 'geodirectory'
GROUP BY type ORDER BY 2 DESC;

-- Spot-check that required iOS columns are populated (should be 0)
SELECT COUNT(*) FROM places
WHERE source = 'geodirectory' AND (type IS NULL OR is_active IS NOT TRUE);

-- Events landed and are active
SELECT COUNT(*) FROM events WHERE source = 'yodel' AND is_active = true;
```

**In the iOS app:** confirm new places appear in Discover with correct names,
types, and (where available) photos. The app caches places, so relaunch or wait
out the cache TTL to see fresh rows.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| **401 Unauthorized** | `GEODIR_BASIC_AUTH` wrong or missing while the source site still has `.htpasswd`. Must be `username:password`. |
| **403 Forbidden** | Credentials present but blocked by the host/WP. Confirm the REST route is permitted. |
| **404 Not Found** | `GEODIR_BASE_URL` wrong, or the GeoDirectory REST API is disabled on the site. |
| **Supabase `permission denied` / RLS error** | `SUPABASE_SERVICE_ROLE_KEY` wrong (using the anon key by mistake?). |
| **`no unique or exclusion constraint matching the ON CONFLICT`** | Migrations (Step 1) not applied — the unique constraint is missing. |
| **`After whitelist filter: 0 listings`** | API categories don't resolve to `ALLOWED_PARENT_IDS`. Read the logged "Parent bucket breakdown" and adjust `config/categories.py`. |
| **Rows in DB but not in the app** | Confirm `is_active = true` and a valid `type`; relaunch the app to clear cached places. |
| **Events tab suddenly sparse** | Check the events run log for `PRUNE SKIPPED` — the fetch-size guard refuses to prune on a suspiciously small feed. |

---

## 7. Staging → production cutover

No code changes — just update secrets:

1. Set **`GEODIR_BASE_URL`** to the production site URL.
2. **Delete** the **`GEODIR_BASIC_AUTH`** secret (or set it empty). The job then
   runs in "production mode" and sends no auth header.

The next scheduled or manual run uses the new host.
