# Data Pipeline Improvements

## Current Problem: 29% duplicate properties, redundant scraping

We run 4 ingestion steps that overlap significantly:

| Step | What It Gets | Overlap |
|------|-------------|---------|
| `ingest` (HomeHarvest/Realtor.com) | Listings + descriptions + photos + agent info | Listings overlap with Redfin CSV |
| `ingest-redfin` (Redfin CSV) | Listings + Redfin URL | Listings overlap with HomeHarvest |
| `scrape-history` (Redfin pages) | Price history + descriptions | Descriptions overlap with HomeHarvest |
| `ingest-market` (Redfin Data Center) | Market stats by ZIP/month | No overlap |

Result: ~1,875 duplicate property records (29% of DB), wasted scraping time, confused dedup.

---

## Data Source Matrix

| Data Field | Redfin CSV | Redfin Page Scrape | HomeHarvest | Redfin Market |
|-----------|:---:|:---:|:---:|:---:|
| address, beds, baths, sqft, year_built, lot, price, lat/lng | Yes | No | Yes | No |
| days on market, $/sqft, HOA, property type | Yes | No | Yes | No |
| Redfin URL (needed for scraping) | **Yes** | N/A | No | No |
| Description | No | **Yes** | Yes | No |
| Photos (URLs) | No | No | **Yes** | No |
| Agent name/email/phone | No | No | **Yes** | No |
| Estimated value (Realtor.com AVM) | No | No | Yes* | No |
| Price history (all events) | No | **Yes** | No | No |
| Tax history | No | **Yes** | No | No |
| Market stats (median price, DOM, inventory) | No | No | No | **Yes** |

*We now compute our own estimated values from comps, so this is less critical.

---

## Proposed Streamlined Pipeline

### Option A: Redfin-Primary (Recommended)

**Step 1: `ingest-redfin` (Redfin CSV)** — Primary listing data source
- Gets: all structured listing data + Redfin URL
- This is our single source of truth for property records
- No 100-result limit (up to 350 per search)

**Step 2: `scrape-history` (Redfin page scrape)** — Enrichment
- Gets: price history, tax history, AND description (already added)
- Runs against Redfin URLs from Step 1
- Could also extract photos from Redfin pages (future improvement)

**Step 3: `ingest-market` (Redfin Data Center)** — Market context
- Gets: ZIP-level trends
- No change needed

**Step 4: `estimate`** — Compute values
- Runs comp-based estimated values from sold data

**Step 5: `adjustments --extract`** — Feature extraction
- NLP on descriptions from Step 2

**Drop or demote:** `ingest` (HomeHarvest) — only run if we specifically need photos or agent info for a subset of properties. Not part of the standard pipeline.

### What We Lose by Dropping HomeHarvest
- **Photo URLs** — Redfin pages have photos but we'd need to extract them (not hard, same page we already scrape)
- **Agent contact info** — nice to have, not critical for valuation
- **~14% of properties** that HomeHarvest found via address formatting differences — actually exist on Redfin, just matched differently

### What We Gain
- No more duplicates
- Single property record per home
- Faster pipeline (no redundant listing ingestion)
- Cleaner data

---

## Improvement Items

### IMP-1: Extract photos from Redfin pages
**Priority:** P1
**Status:** Not started
**Description:** Update `scrape_history.py` to also extract photo URLs from Redfin pages while it's already loading them. This removes the last dependency on HomeHarvest.
**Approach:** Redfin pages have photo URLs in the HTML — extract them with regex like we do for descriptions.

### IMP-2: Address normalization and dedup
**Priority:** P0
**Status:** Not started
**Description:** Normalize addresses (strip trailing directionals E/N/S/W, normalize Unit/#/Apt, standardize abbreviations) and merge duplicate records.
**Approach:**
1. Normalize: "123 N Main St E" → "123 N Main St", "Unit 5" → "#5"
2. Match on normalized street + zip
3. Merge: keep Redfin record, copy over photos/agent/estimated_value from HH record
4. Delete the HH duplicate

### IMP-3: Increase Redfin CSV coverage beyond 350 cap
**Priority:** P1
**Status:** Not started
**Description:** Some ZIPs have >350 sold properties. We're capped. Options:
- Split queries by time window (e.g., sold in last 90 days, then 90-180 days)
- Split by property type
- Split by price range

### IMP-4: Unified `ingest-all` pipeline
**Priority:** P0
**Status:** Partially done
**Description:** Rewrite `ingest-all` to use the streamlined Redfin-primary flow:
1. `ingest-redfin` (CSV) for listings
2. `scrape-history` for price history + descriptions
3. `estimate` for comp-based values
4. `adjustments --extract` for NLP features
5. Sync to Supabase

Drop the HomeHarvest step from the default pipeline.

### IMP-5: Redfin page scrape already has the listing data
**Priority:** P2
**Status:** Not started
**Description:** When we scrape a Redfin page for history, the page also has beds, baths, sqft, year built, etc. We could extract all of it from one page load instead of needing the CSV at all. This would make the pipeline:
1. Get Redfin URLs (from CSV or search)
2. Scrape each page → get everything (listing data + history + description + photos)

This is the cleanest approach but slower (one HTTP request per property vs bulk CSV).

### IMP-6: Scheduled re-ingestion
**Priority:** P2
**Status:** Not started
**Description:** Cron job to re-run the pipeline daily/weekly. Detects new listings, price changes, status changes (sold/pending).

### IMP-7: Sync strategy for Supabase
**Priority:** P1
**Status:** Ad-hoc
**Description:** Currently we manually sync to Supabase after scraping. Should be automatic at the end of every pipeline run. Already partially implemented in `ingest-all` but not all scripts use it.

### IMP-8: Extract climate risk scores from Redfin pages
**Priority:** P1
**Status:** Not started — waiting for current backfill to complete
**Description:** Redfin pages contain First Street Foundation climate risk scores (1-10 scale) for flood, fire, heat, and wind. These directly affect property value and insurance costs. Add extraction patterns:
- Flood factor: `[Ff]lood.*?(\d+)/10`
- Fire factor: `[Ff]ire.*?(\d+)/10`
- Heat factor: `[Hh]eat.*?(\d+)/10`
- Wind factor: `[Ww]ind.*?(\d+)/10`
- New columns on properties: `flood_factor`, `fire_factor`, `heat_factor`, `wind_factor` (all INTEGER 1-10)

### IMP-9: Extract Redfin's comparable homes
**Priority:** P2
**Status:** Not started — waiting for current backfill to complete
**Description:** Redfin pages show their own comparable home suggestions. Extracting these lets us compare our comp selection to Redfin's. Could also populate comps for properties where we don't have enough local sold data.

### IMP-10: Extract annual tax amount
**Priority:** P2
**Status:** Not started
**Description:** Tax amount is on the page (e.g., "$3,223"). Useful for buyer cost estimation. Pattern: `[Tt]ax.*?\$(\d[\d,]+)`. Store in `properties.annual_tax`.

### IMP-11: Extract transit score
**Priority:** P2
**Status:** Not started
**Description:** Some pages have transit score in addition to walk/bike. Pattern TBD — may need unescaped JSON matching like walk score.

---

## Decision: Keep or Drop HomeHarvest?

**Recommendation: Keep as optional, remove from default pipeline.**

HomeHarvest stays installed and available for:
- One-time photo URL collection (until IMP-1 is done)
- Agent contact info lookup when making offers
- Cross-referencing Realtor.com estimates vs our comp-based estimates

But the standard `ingest-all` flow becomes Redfin-only:
```
ingest-redfin → scrape-history → estimate → adjustments --extract → sync
```
