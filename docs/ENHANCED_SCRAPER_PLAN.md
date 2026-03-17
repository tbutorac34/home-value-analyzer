# Enhanced Redfin Scraper — Implementation Plan

## Goal
Replace the history-only scraper with a comprehensive Redfin page scraper that extracts ALL available data in a single page load. Remove HomeHarvest dependency.

## Pipeline After This Change
```
ingest-redfin (CSV) → scrape-redfin (page) → estimate → adjustments → sync
```

---

## Epic: Enhanced Redfin Page Scraper

### Story 1: Database schema updates
**File:** `migrations/004_enhanced_property_data.sql`
- Add to `properties` table: `redfin_estimate`, `walk_score`, `bike_score`, `flood_risk`, `heating`, `cooling`, `construction_type`, `roof_type`, `foundation_type`, `sewer`, `water_source`, `appliances`, `laundry`
- Create `property_photos` table: `id`, `property_id` (FK), `url`, `position`, `caption`, `created_at`
- Add SQLite schema to `db.py`

### Story 2: Rename and rewrite scraper module
**File:** `home_value_analyzer/scrape_redfin.py` (rename from `scrape_history.py`)
- Extract from JSON blobs in HTML: `lotSize`, `garageSpaces`, `parkingSpaces`, `daysOnMarket`, `listingAgentName`, `listingAgentNumber`, `photoUrls`, `walkScore`, `bikeScore`, `redfinEstimate`
- Extract from HTML property details tables: basement, flooring, heating/cooling, foundation, roof, construction, sewer, water, appliances, fireplace, pool
- Extract from HTML: school ratings, flood risk
- Keep existing: price history, tax history, description extraction
- Store structured property details directly in `property_adjustments` with `source='redfin_structured'`, `confidence=1.0`
- Store photos in `property_photos` table
- Update `properties` table with new fields

### Story 3: Update CLI and pipeline references
**Files:** `__main__.py`, `ingest_all.py`
- Rename command from `scrape-history` to `scrape-redfin`
- Keep `scrape-history` as alias for backwards compatibility
- Update `ingest_all.py` to use new module
- Remove HomeHarvest from default `ingest-all` pipeline

### Story 4: Backfill script
**File:** `scripts/backfill_enhanced_scrape.py`
- Re-scrape all properties that have Redfin URLs to get the new fields
- Skip properties already scraped with enhanced version (check for redfin_estimate or photos)
- Run NLP extraction after for any remaining properties without structured data
