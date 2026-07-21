# Connect Happy Valley — Data Sync Pipelines

Two scheduled data pipelines (Python + GitHub Actions + Supabase/PostgreSQL) powering [Connect Happy Valley](https://connecthappyvalley.com), a native iOS visitor guide for State College / Centre County, PA. Built as contract work; published with the client's permission.

```
WordPress GeoDirectory ──┐                        ┌──▶ places table ──┐
      (hourly, :00)      ├──▶ GitHub Actions ──▶ Supabase             ├──▶ iOS app (Swift)
Yodel events feed ───────┘        (Python)        └──▶ events table ──┘
      (hourly, :30)
```

## The two jobs

**`sync.py` — GeoDirectory places sync** (hourly at :00)
Pulls ~3,900 business listings from a WordPress GeoDirectory REST API, filters to ~1,650 visitor-facing listings by parent-category whitelist, and upserts them into the `places` table the iOS app reads.

**`events_sync.py` — Yodel events sync** (hourly at :30, offset to avoid contending for the same write window)
Pulls the local events feed, filters test/cancelled entries, deduplicates, and upserts into the `events` table — then reconciles staleness, since the feed is a rolling window and upserts never delete.

## Engineering decisions worth reading

- **Parent-bucket whitelist filtering** (`config/categories.py`) — filtering by subcategory *name* proved fragile (plural drift, HTML entities, new subcategories); filtering by stable top-level bucket ID fixed a bug that had capped the first run at 25 of 3,873 listings.
- **Two-tier type resolution** — every synced row is guaranteed a valid iOS enum type (bucket default, refined by normalized subcategory name), because the app's Discover tab decodes all-or-nothing: one null type would blank the entire tab.
- **Coordinate-based dedup via union-find** (`sync.py`) — near-duplicate listings (same name within ~50m) are clustered pairwise with transitive union rather than a rounded grid, which was verified to miss ~half the real pairs at cell boundaries.
- **Mojibake repair** — double-encoded UTF-8 from WordPress is round-tripped through latin-1 then cp1252, with each attempt guarded so already-clean strings pass through.
- **Content integrity** — the source's auto-generated listing descriptions are formulaic and occasionally factually wrong, so synced descriptions are deliberately nulled rather than surfaced; the app shows only verifiable fields.
- **Guarded staleness prune** (`events_sync.py`) — past events are always deactivated, but rows missing from the current feed are only pruned when the feed is ≥50% of the prior active count, so a partial or failed fetch can never mass-blank the Events tab.
- **Defensive iOS contract** — both transforms document and enforce the app's decode requirements (required non-null columns, valid enum values) so a bad row can't take down a tab.

## Layout

| Path | What it is |
|---|---|
| `sync.py` | GeoDirectory → `places` sync job |
| `events_sync.py` | Yodel → `events` sync job |
| `config/categories.py` | Category whitelist + GeoDirectory→iOS type mapping (with reasoning) |
| `config/event_categories.py` | Yodel category → iOS event-category mapping (with reasoning) |
| `.github/workflows/` | The two hourly scheduled jobs |
| `supabase/migrations/` | Schema changes the sync relies on |
| `SETUP.md` | Ops runbook: secrets, first run, verification, troubleshooting |
| `.env.example` | Local development environment template |

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in values
python sync.py --dry-run          # fetch + filter + dedup, no DB writes
python events_sync.py --dry-run
```

Both jobs support `--dry-run`, which runs the full pipeline and logs per-stage counts without constructing a database client.

---

*Built by [Josh Kraus](https://github.com/joshkraus27) under contract for Connect Happy Valley. Secrets and client-internal hosts are redacted in this public copy.*
