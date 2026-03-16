# Home Value Analyzer — Product Roadmap

## Vision

A tool that gives home buyers an unfair advantage by combining public listing data, price history, AI-driven photo analysis, and comp adjustments into a single system that identifies undervalued properties and flags overpriced ones.

**Phase 1:** Internal tool for personal home search (current)
**Phase 2:** Productize for other home buyers if it delivers value

---

## Current State (v0.1)

### What's Built
- **Data ingestion pipeline**: HomeHarvest (Realtor.com), Redfin CSV download, Redfin page scraper for price history
- **Database**: Supabase (PostgreSQL) + local SQLite fallback
- **Market stats**: Redfin Data Center monthly trends by ZIP
- **Comp analysis**: Similarity-scored comparable sales with distance, sqft, bed/bath matching
- **CLI**: click-based commands for ingest, analyze, market view, export
- **Coverage**: 16 ZIP codes in Macomb County, MI area (~600+ properties, 747+ price history events, growing)

### What's Missing
- No deal scoring/ranking
- No property feature adjustments (basement, remodel quality, etc.)
- No photo analysis
- No alerting for new listings or price drops
- Ingestion doesn't auto-sync to Supabase from all commands
- Comp analysis doesn't account for feature differences

---

## Epic 1: Deal Finder

**Goal:** Automatically score every for-sale property on a 0-100 scale based on how likely it is to be a good deal, so the user can focus on the best opportunities first.

### Scoring Signals

| Signal | Max Points | Data Source |
|--------|-----------|-------------|
| Price vs estimated value | 25 | properties.estimated_value vs list_price |
| Price drop history | 20 | price_history (count + magnitude) |
| $/sqft vs ZIP average | 15 | properties.price_per_sqft vs ZIP median |
| Days on market vs area avg | 12 | properties.days_on_mls vs market_stats.median_dom |
| List price vs last sold (flip detection) | 10 | properties.last_sold_price |
| Area sale-to-list ratio | 8 | market_stats.avg_sale_to_list |
| Relist detection | 5 | price_history (Listed after Pending/Removed) |
| Description keyword signals | 5 | properties.description NLP scan |

### Grade Scale

| Score | Grade | Label |
|-------|-------|-------|
| 75-100 | A | Strong Deal |
| 60-74 | B | Good Deal |
| 45-59 | C | Fair Value |
| 30-44 | D | Market Price |
| 0-29 | F | Overpriced |

### Stories

#### E1-S1: Core scoring engine (`deals.py`)
**Priority:** P0
**Description:** Create `deals.py` module with `DealScore` dataclass and `compute_deal_score()` function implementing all 8 scoring signals. Each signal reads from existing tables (properties, price_history, market_stats).
**Acceptance criteria:**
- [ ] DealScore dataclass with individual signal scores, total score, grade, and human-readable deal_notes
- [ ] compute_deal_score(property_id) returns a fully populated DealScore
- [ ] find_deals(zip_codes, min_score, limit) batch-scores and returns sorted results
- [ ] Handles missing data gracefully (0 points for unavailable signals, not errors)
- [ ] Unit tested with sample properties

#### E1-S2: ZIP benchmark calculations
**Priority:** P0
**Description:** Implement `_get_zip_benchmarks()` that computes median $/sqft, median DOM, and sale-to-list ratio per ZIP from existing data. Cache results to avoid repeated queries.
**Acceptance criteria:**
- [ ] Returns None/skips scoring if ZIP has < 5 active listings
- [ ] Uses market_stats for DOM and sale-to-list when available
- [ ] Falls back to computing from properties table when market_stats missing

#### E1-S3: Price drop signal calculation
**Priority:** P0
**Description:** Implement `_get_price_drop_signals()` that queries price_history for a property and computes: number of drops, total drop percentage, relist detection, original list price vs current.
**Acceptance criteria:**
- [ ] Supports date cutoff parameter (e.g., only drops in last 12 months)
- [ ] Correctly identifies relists (Listed event after Pending/Removed)
- [ ] Computes total drop as (first_list_price - current_list_price) / first_list_price

#### E1-S4: Description keyword scanner
**Priority:** P1
**Description:** Implement `_check_description_signals()` that regex-scans listing descriptions for motivation keywords. Three tiers: high motivation (3pts), medium (2pts), low (1pt), capped at 5.
**Acceptance criteria:**
- [ ] High: "motivated seller", "must sell", "bring all offers", "estate sale", "foreclosure", "priced to sell"
- [ ] Medium: "as-is", "investor special", "handyman special", "needs work", "fixer"
- [ ] Low: "relocating", "price reduced", "just reduced", "new price"
- [ ] Case-insensitive, accumulates points up to 5

#### E1-S5: CLI command
**Priority:** P0
**Description:** Add `deals` command to CLI with options for ZIP filter, min score, limit, grade filter, and detail view.
**Acceptance criteria:**
- [ ] `deals --zips 48044,48042` shows ranked summary table
- [ ] `deals --detail 123` shows full score breakdown with bar chart visualization
- [ ] `deals --grade A` filters to only A-grade deals
- [ ] `deals --export` writes results to CSV

#### E1-S6: Supabase SQL view
**Priority:** P1
**Description:** Create `deal_scores` PostgreSQL view in Supabase that replicates scoring logic in pure SQL for dashboard browsing.
**Acceptance criteria:**
- [ ] View computes all 8 signals, total score, and grade
- [ ] Browsable and sortable in Supabase dashboard
- [ ] Includes ZIP, address, price, sqft, beds/baths, DOM, score, grade columns
- [ ] Migration SQL in `migrations/002_deal_score_view.sql`

#### E1-S7: Deal alerts (future)
**Priority:** P2
**Description:** Periodic re-ingestion that detects new A/B-grade deals and sends a notification (email, Slack, or push).
**Acceptance criteria:**
- [ ] Cron-able command that re-ingests and diffs against previous scores
- [ ] Alerts on: new A/B listings, properties that jumped to A/B after price drop
- [ ] Configurable notification channel

---

## Epic 2: Property Adjustments

**Goal:** Track property features not captured in listing data (finished basement, remodel quality, roof age, etc.) and factor them into valuations so comp analysis reflects real differences between homes.

### Data Sources
1. **Automated NLP extraction** from listing descriptions (~80% of features detectable)
2. **Manual entry** after viewing/touring a property
3. **AI photo analysis** (Epic 3)

### Key Adjustments (Macomb County Dollar Values)

| Feature | Dollar Impact | Notes |
|---------|-------------|-------|
| Finished basement (full) | +$20K to +$35K | Biggest hidden value driver in MI |
| Kitchen remodel (major, <5yr) | +$15K to +$30K | Granite/quartz, new cabinets |
| Bathroom remodel (major) | +$4K to +$8K per bath | |
| New roof (<5yr) | +$3K to +$8K | Depreciates ~10%/yr |
| New HVAC (<5yr) | +$3K to +$6K | Depreciates ~8%/yr |
| New windows | +$5K to +$10K | |
| 3-car vs 2-car garage | +$15K to +$25K | |
| In-ground pool | +$5K to +$15K | |
| Backs to woods | +$5K to +$15K | |
| Backs to busy road | -$10K to -$20K | |
| Hardwood floors vs carpet | +$3K to +$8K | |
| Open floor plan | +$3K to +$7K | |

### Stories

#### E2-S1: Database schema — `property_adjustments` and `adjustment_values` tables
**Priority:** P0
**Description:** Create two new tables. `property_adjustments` has typed columns for each major feature (basement_finished, kitchen_remodel_year, roof_year, etc.) plus a JSONB overflow field. `adjustment_values` stores configurable dollar amounts per market area with depreciation rates.
**Acceptance criteria:**
- [ ] Supabase migration SQL in `migrations/003_property_adjustments.sql`
- [ ] SQLite schema added to `db.py`
- [ ] `adjustment_values` seeded with Macomb County defaults
- [ ] One row per property (UNIQUE on property_id)

#### E2-S2: NLP extraction engine
**Priority:** P0
**Description:** Implement `extract_adjustments_from_description()` using regex patterns to detect features from listing text. Organized as a list of (field, pattern, transform) tuples.
**Acceptance criteria:**
- [ ] Detects: finished basement, roof/HVAC/window years, flooring type, fireplace, pool, fence, open floor plan, garage type, deck/patio, sprinkler system
- [ ] Batch command: `extract-features --zip 48044` processes all properties with descriptions
- [ ] NLP-extracted records tagged with `source='nlp_extracted'` and `confidence=0.8`
- [ ] Tested against 20+ real descriptions from the database

#### E2-S3: Manual entry CLI
**Priority:** P1
**Description:** Interactive CLI command for entering/updating property adjustments after touring a home.
**Acceptance criteria:**
- [ ] `adjust --address "123 Main St"` opens interactive prompts
- [ ] Pre-populates with NLP-extracted values where available
- [ ] Manual entries override NLP with `source='manual'` and `confidence=1.0`
- [ ] Syncs to Supabase

#### E2-S4: Adjustment dollar calculation
**Priority:** P1
**Description:** Implement `calculate_adjustment_total()` that looks up a property's adjustments, maps them to dollar values from `adjustment_values`, applies depreciation for time-sensitive items, and returns a net adjustment figure.
**Acceptance criteria:**
- [ ] Depreciation formula: `value * (1 - rate)^years` for roof, HVAC, etc.
- [ ] Returns breakdown: [{feature, dollars, confidence}]
- [ ] Handles missing/null fields gracefully

#### E2-S5: Comp analysis integration
**Priority:** P1
**Description:** Modify `analyze.py` to apply adjustment differentials between subject property and each comp. If subject has a finished basement (+$25K) and comp doesn't, comp's price is adjusted up by $25K.
**Acceptance criteria:**
- [ ] CompResult gains `adjusted_sold_price` field
- [ ] ValuationResult includes adjustment breakdown
- [ ] Display shows raw vs adjusted valuation
- [ ] Only applies adjustments where both subject and comp have data

#### E2-S6: Adjustment values management
**Priority:** P2
**Description:** CLI command to view and edit the dollar value configuration table.
**Acceptance criteria:**
- [ ] `adjustments --show-values` displays current dollar values
- [ ] `adjustments --set basement_full_finished 30000` updates a value
- [ ] Supports per-ZIP overrides (future: different values for different neighborhoods)

---

## Epic 3: AI Photo Analysis

**Goal:** Use computer vision to analyze listing photos and extract property condition, renovation quality, and specific features that aren't in the structured listing data.

### What AI Can Detect

**High confidence:**
- Kitchen cabinet quality/age (new vs dated)
- Countertop material (granite, quartz, laminate, butcher block)
- Appliance quality (stainless steel, black, white, dated)
- Bathroom renovation level
- Flooring type (hardwood, carpet, tile, LVP)
- General condition score (1-10)
- Basement finished vs unfinished

**Medium confidence:**
- Renovation quality tier (luxury, mid-grade, builder-grade, needs-work)
- Natural light quality
- Room proportions / layout openness
- Landscaping quality
- Staging quality (indicator of seller motivation/investment)

**Lower confidence (supplementary):**
- Specific fixture brands
- Age of renovations
- Structural issues
- Exact material identification in ambiguous photos

### Recommended Approach: Claude Vision API

**Why Claude:**
- Already have API access (no new vendor)
- Haiku 4.5 batch pricing: ~$0.001/image
- Supports photo URLs directly (no download needed)
- Structured JSON output
- Quality is excellent for this use case

**Cost estimate for full pipeline:**
| Phase | Images | Model | Cost |
|-------|--------|-------|------|
| Screen all properties (primary photo) | ~1,000 | Haiku batch | ~$1.17 |
| Deep analysis on candidates (all photos) | ~4,000 | Haiku batch | ~$5-15 |
| Final analysis on top picks | ~150 | Sonnet | ~$5-10 |
| **Total** | | | **$7-27** |

### Stories

#### E3-S1: Photo download and management
**Priority:** P0
**Description:** Build photo download/caching system. Download listing photos from URLs stored in `primary_photo` and `alt_photos`, cache locally to avoid re-downloading.
**Acceptance criteria:**
- [ ] Downloads primary_photo for all properties with URLs
- [ ] Caches in `data/photos/{property_id}/` directory
- [ ] Handles broken URLs, timeouts, 404s gracefully
- [ ] Tracks download status in DB to avoid re-fetching
- [ ] CLI: `download-photos --zip 48044 --limit 100`

#### E3-S2: Single-photo analysis prompt engineering
**Priority:** P0
**Description:** Design and test the Claude Vision prompt that analyzes a single listing photo and returns structured JSON with detected features and scores.
**Acceptance criteria:**
- [ ] Prompt returns consistent JSON schema with: room_type, condition_score (1-10), features detected, quality_tier, materials identified
- [ ] Tested on 50+ real listing photos with validation
- [ ] Handles exterior, interior, kitchen, bathroom, basement, yard photos
- [ ] Prompt tuned for Haiku (concise, structured)

#### E3-S3: Batch processing pipeline
**Priority:** P0
**Description:** Build the batch processing system using Claude Batch API for cost efficiency.
**Acceptance criteria:**
- [ ] Submits up to 10,000 requests per batch
- [ ] Polls for completion, retrieves results
- [ ] Maps results back to property_id
- [ ] Handles partial failures (some images fail, others succeed)
- [ ] CLI: `analyze-photos --zip 48044 --model haiku --batch`

#### E3-S4: Photo analysis database schema
**Priority:** P0
**Description:** Create `photo_analysis` table to store per-photo AI results and `property_photo_scores` view that aggregates to property-level scores.
**Acceptance criteria:**
- [ ] `photo_analysis` table: property_id, photo_url, room_type, condition_score, quality_tier, features_json, model_used, analyzed_at
- [ ] Aggregation view: property-level avg condition score, worst room, best room, feature summary
- [ ] Supabase migration + SQLite schema

#### E3-S5: Property-level score aggregation
**Priority:** P1
**Description:** Aggregate per-photo scores into a single property condition assessment with room-weighted scoring (kitchen and bathrooms weighted higher than hallways).
**Acceptance criteria:**
- [ ] Weighting: kitchen (2.5x), bathrooms (2x), living areas (1.5x), bedrooms (1x), exterior (1x), other (0.5x)
- [ ] Property gets: overall_condition_score, kitchen_score, bathroom_score, exterior_score
- [ ] Feeds into deal finder (bonus points for underpriced + good condition)
- [ ] Feeds into adjustments (auto-detect kitchen/bath remodel quality)

#### E3-S6: Integration with deal finder and adjustments
**Priority:** P1
**Description:** Wire photo analysis scores into the deal finder scoring and property adjustments system.
**Acceptance criteria:**
- [ ] Deal finder gets bonus signal: "good condition but priced low" = extra points
- [ ] Photo-detected features (hardwood, granite, etc.) auto-populate property_adjustments with `source='photo_ai'`
- [ ] Confidence scores pass through from photo analysis

#### E3-S7: Tiered analysis pipeline
**Priority:** P2
**Description:** Implement the three-tier pipeline: Haiku screen all → Haiku deep-dive candidates → Sonnet final analysis on serious picks.
**Acceptance criteria:**
- [ ] Tier 1: Primary photo only, all properties, flags condition outliers
- [ ] Tier 2: All photos, properties scoring B+ on deal finder
- [ ] Tier 3: Sonnet analysis with detailed narrative on properties user bookmarks
- [ ] Cost tracking and reporting

---

## Epic 4: Infrastructure & Quality of Life

### Stories

#### E4-S1: Supabase-native ingestion
**Priority:** P1
**Description:** Update all ingest commands to write directly to Supabase instead of SQLite-then-migrate.
**Acceptance criteria:**
- [ ] All ingest commands detect Supabase config and write directly
- [ ] SQLite remains as offline fallback
- [ ] No more manual `migrate` step needed

#### E4-S2: Scheduled re-ingestion
**Priority:** P2
**Description:** Cron job or scheduled task that re-ingests all configured ZIPs on a daily/weekly basis.
**Acceptance criteria:**
- [ ] `ingest-all --zips <from config>` runs unattended
- [ ] Detects new listings, price changes, status changes
- [ ] Triggers deal score recalculation
- [ ] Optional: sends alert digest

#### E4-S3: Deduplication
**Priority:** P1
**Description:** Properties appear from both HomeHarvest and Redfin with slightly different addresses. Implement fuzzy matching to merge duplicates.
**Acceptance criteria:**
- [ ] Match on normalized street address + ZIP
- [ ] Merge: keep the record with more data, link the URLs from both
- [ ] CLI: `dedup --zip 48044 --dry-run`

#### E4-S4: Web dashboard (future)
**Priority:** P3
**Description:** If productizing, build a Streamlit or Next.js frontend on top of Supabase.
**Acceptance criteria:**
- [ ] Map view with deal scores color-coded
- [ ] Property detail pages with photos, history, adjustments, comp analysis
- [ ] Saved searches and favorites
- [ ] Shareable reports for offers

---

## Implementation Priority Order

### Now (Personal Use)
1. **E1: Deal Finder** — immediate value, uses existing data
2. **E2-S1 + E2-S2: Adjustment schema + NLP extraction** — auto-populates from descriptions we already have
3. **E1-S6: Supabase deal_scores view** — browsable in dashboard

### Next (Enhanced Analysis)
4. **E3-S1 through E3-S4: Photo analysis MVP** — screen all properties with Haiku
5. **E2-S4 + E2-S5: Dollar adjustments + comp integration** — improved valuations
6. **E4-S3: Deduplication** — cleaner data

### Later (Productization Prep)
7. **E4-S1: Supabase-native ingestion**
8. **E3-S5 + E3-S6: Photo integration with deal finder**
9. **E4-S2: Scheduled re-ingestion + alerts**
10. **E4-S4: Web dashboard**
