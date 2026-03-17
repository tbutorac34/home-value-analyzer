# Product Requirements Document: HomeValue Analyzer

**Document Status:** Draft
**Author:** Product Team
**Date:** 2026-03-16
**Version:** 1.0

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Target Users](#2-target-users)
3. [User Stories](#3-user-stories)
4. [Feature Requirements](#4-feature-requirements)
5. [Technical Architecture](#5-technical-architecture)
6. [Data Model](#6-data-model)
7. [Success Metrics](#7-success-metrics)
8. [Risks & Mitigations](#8-risks--mitigations)
9. [Phased Rollout Plan](#9-phased-rollout-plan)

---

## 1. Problem Statement

Home buyers today face a massive information asymmetry. They rely on listing agents' curated photos, optimistic descriptions, and opaque pricing to make the largest financial decision of their lives. Existing platforms (Zillow, Redfin, Realtor.com) display data but do not help buyers interpret it. Buyers lack:

- **Objective deal quality assessment.** No tool scores how good a deal actually is relative to the local market. Buyers must manually compare price per square foot, days on market, and price history across dozens of listings.
- **Honest property condition evaluation.** Listing photos are professionally staged and angled to hide flaws. Buyers cannot distinguish a recently remodeled kitchen from one with cosmetic staging until they visit in person, wasting time on properties that don't meet their standards.
- **Feature-adjusted comparable analysis.** Automated valuations (Zestimates, Redfin Estimates) treat all homes in a price range as equivalent. They do not account for a finished basement, a new roof, or a home that backs to a busy road. Buyers have no way to compute what a specific home is actually worth given its unique features.
- **Community-sourced local knowledge.** Neighborhood-level information (traffic patterns, school quality perception, construction defects common to a subdivision) is trapped in individual buyers' heads. There is no structured way for buyers to share and access touring notes and local insights on specific properties.
- **Proactive opportunity detection.** Price drops, new listings matching criteria, and emerging deals require constant manual monitoring across multiple platforms.

We have built an internal tool that solves these problems for our own home search. It ingests data from Redfin and Realtor.com, tracks full price history, scores deals on a 0-100 scale, analyzes listing photos with AI, and computes feature-adjusted property valuations. This PRD defines the product that brings these capabilities to all home buyers.

---

## 2. Target Users

### Primary: Active Home Buyers

- Currently searching for a home to purchase (next 0-12 months)
- Frustrated by the volume of listings and difficulty assessing true value
- Willing to invest time researching properties before touring
- Comfortable with web applications; some are data-oriented, others want simple grades and recommendations
- Geographic starting point: Southeast Michigan (Macomb, Oakland, Wayne counties), expanding to additional metros

### Secondary: Real Estate Investors

- Evaluating properties for investment potential (rental, flip, buy-and-hold)
- More analytically sophisticated; want raw data, comp breakdowns, and adjustment details
- Higher willingness to pay for tooling that saves time on deal sourcing

### Tertiary: Curious Homeowners

- Want to understand their own home's value relative to neighborhood sales
- Interested in market trends in their ZIP code
- Lower engagement frequency but high volume; good for top-of-funnel growth

### User Personas

**Sarah, First-Time Buyer (Age 29)**
Sarah is pre-approved for $300K and searching in Macomb County. She browses 50+ listings per week on Zillow and Redfin but struggles to assess which are genuinely good deals vs. overpriced. She has toured 8 homes and been disappointed by condition gaps between photos and reality. She wants a tool that filters out the noise and tells her where to focus.

**Mike, Move-Up Buyer (Age 42)**
Mike owns a home and is looking to upgrade. He understands the market better than Sarah but still finds comp analysis tedious. He wants to know what specific features (finished basement, new windows) are actually worth in dollar terms so he can make informed offers. He is willing to pay for a tool that replaces hours of manual spreadsheet work.

**Raj, Small-Scale Investor (Age 35)**
Raj owns two rental properties and is looking for his third. He wants to find undervalued properties quickly, assess renovation potential from photos without visiting, and understand market trends at the ZIP level. He values speed and data density. He would pay a premium for AI photo analysis and deal scoring.

---

## 3. User Stories

### Deal Finder

| ID | Story | Priority |
|----|-------|----------|
| US-1.1 | As a buyer, I want to see a ranked list of the best deals in my target ZIP codes so I can focus my time on the most promising properties. | P0 |
| US-1.2 | As a buyer, I want to understand why a property scored the way it did (score breakdown with individual signals) so I can trust the rating. | P0 |
| US-1.3 | As a buyer, I want to filter deals by grade (A/B/C/D/F), price range, beds/baths, and ZIP code so I can narrow results to my criteria. | P0 |
| US-1.4 | As an investor, I want to see flip detection signals (recent purchase at lower price, quick relist) so I can avoid overpaying for cosmetic flips. | P1 |
| US-1.5 | As a buyer, I want to sort by different scoring signals (biggest price drop, best $/sqft, longest DOM) to explore deals from different angles. | P1 |

### Price History Tracking

| ID | Story | Priority |
|----|-------|----------|
| US-2.1 | As a buyer, I want to see the full sale and listing history for any property so I can understand its pricing trajectory. | P0 |
| US-2.2 | As a buyer, I want to see price changes visualized on a timeline so I can quickly spot trends. | P1 |
| US-2.3 | As a buyer, I want to know if a property was previously pending and relisted, which may indicate inspection issues or a flaky seller. | P0 |

### AI Photo Analysis

| ID | Story | Priority |
|----|-------|----------|
| US-3.1 | As a buyer, I want an AI-generated condition score for each property so I can screen out homes in poor condition without visiting. | P0 |
| US-3.2 | As a buyer, I want AI to identify kitchen quality, bathroom condition, and flooring type from listing photos so I know what to expect before touring. | P0 |
| US-3.3 | As a buyer, I want a detailed room-by-room AI analysis for properties I have favorited so I can prepare for tours with specific things to inspect. | P1 |
| US-3.4 | As a buyer, I want to see a "photo vs. reality" flag when AI detects that photos are heavily staged or misleading relative to the property's age and price. | P2 |

### Property Adjustments & Comp Analysis

| ID | Story | Priority |
|----|-------|----------|
| US-4.1 | As a buyer, I want to see comparable sales with dollar adjustments for feature differences (basement, remodel, garage, lot) so I can compute what a home is truly worth. | P0 |
| US-4.2 | As a buyer, I want to manually add features I observed during a tour (e.g., "basement is finished, kitchen is original") and see the valuation update. | P1 |
| US-4.3 | As a buyer, I want to see which features are auto-detected from the listing description vs. AI photos vs. manually entered, with confidence levels. | P1 |

### Market Dashboard

| ID | Story | Priority |
|----|-------|----------|
| US-5.1 | As a buyer, I want to see ZIP-level market trends (median price, days on market, inventory, sale-to-list ratio) so I can understand whether the market favors buyers or sellers. | P0 |
| US-5.2 | As a buyer, I want to compare market conditions across multiple ZIP codes side-by-side so I can decide where to focus my search. | P1 |
| US-5.3 | As a buyer, I want to see months-of-supply trends to understand how competitive my target market is. | P1 |

### Community Forum / Comments

| ID | Story | Priority |
|----|-------|----------|
| US-6.1 | As a buyer, I want to read comments other buyers have left about a specific property so I can learn things not visible in the listing. | P0 |
| US-6.2 | As a buyer, I want to leave a comment on a property after touring it (e.g., "kitchen was dated, photos are misleading") so I can help other buyers. | P0 |
| US-6.3 | As a buyer, I want to share neighborhood insights on a property thread (e.g., "street gets a lot of traffic", "great neighbors") so location-specific information is captured. | P0 |
| US-6.4 | As a buyer, I want to upvote or downvote comments so the most useful information rises to the top. | P1 |
| US-6.5 | As a buyer, I want to see a "Verified Buyer" badge on comments from users who have purchased a home through the platform so I can assess credibility. | P2 |
| US-6.6 | As a moderator, I want to flag and remove comments that contain personal attacks, agent names, or discriminatory content so the community remains useful and legally compliant. | P0 |
| US-6.7 | As a user, I want to be notified when someone replies to my comment or comments on a property I have commented on so I can follow the conversation. | P2 |

### Saved Searches & Favorites

| ID | Story | Priority |
|----|-------|----------|
| US-7.1 | As a buyer, I want to save a search with my criteria (ZIP codes, price range, beds/baths, min deal score) so I can quickly re-run it. | P0 |
| US-7.2 | As a buyer, I want to favorite/bookmark individual properties so I can build a shortlist. | P0 |
| US-7.3 | As a buyer, I want to add private notes to favorited properties so I can track my own observations. | P1 |
| US-7.4 | As a buyer, I want to organize favorites into lists (e.g., "Top Picks", "Need to Tour", "Toured - Liked") so I can manage my search process. | P2 |

### Price Drop Alerts

| ID | Story | Priority |
|----|-------|----------|
| US-8.1 | As a buyer, I want to receive an email or push notification when a favorited property drops in price so I can act quickly. | P0 |
| US-8.2 | As a buyer, I want to receive alerts when a new property matching my saved search criteria is listed so I can see it before other buyers. | P0 |
| US-8.3 | As a buyer, I want to set alert preferences (email vs. push, frequency: instant/daily digest) so I control notification volume. | P1 |
| US-8.4 | As a buyer, I want to receive alerts when a property matching my criteria gets a deal score upgrade (e.g., C to B after price drop) so I catch emerging deals. | P2 |

### Offer Assistant

| ID | Story | Priority |
|----|-------|----------|
| US-9.1 | As a buyer, I want to see a suggested offer price range for any property based on the deal score, adjusted comps, and current market conditions so I know where to start negotiations. | P0 |
| US-9.2 | As a buyer, I want to see the reasoning behind the suggested offer (e.g., "3 comparable sales adjusted to $285K-$295K, property is 15% overpriced, market has 4 months supply suggesting buyer leverage") so I can evaluate the recommendation. | P0 |
| US-9.3 | As a buyer, I want to adjust offer parameters (e.g., "I want to be aggressive" vs. "I want to be competitive") and see the range update accordingly. | P1 |
| US-9.4 | As a buyer, I want to generate a shareable offer analysis summary I can show my agent to support my offer price. | P2 |

---

## 4. Feature Requirements

### 4.1 Deal Finder

**Description:** Automatically scores every for-sale property on a 0-100 scale based on multiple signals indicating whether it represents a good value. Displays a letter grade (A through F) and a human-readable summary of why the score is what it is.

**Scoring Signals:**

| Signal | Max Points | Source |
|--------|-----------|--------|
| Price vs. estimated value (comp-based) | 25 | Adjusted comp analysis output vs. list price |
| Price drop history (count + magnitude) | 20 | Price history table |
| Price per sqft vs. ZIP median | 15 | Property data vs. market stats |
| Days on market vs. area average | 12 | Property DOM vs. market stats median |
| List price vs. last sold price (flip detection) | 10 | Property sale history |
| Area sale-to-list ratio | 8 | Market stats |
| Relist detection (listed after pending/removed) | 5 | Price history pattern matching |
| Description keyword signals (motivation indicators) | 5 | NLP scan of listing description |

**Grade Scale:**

| Score | Grade | Label |
|-------|-------|-------|
| 75-100 | A | Strong Deal |
| 60-74 | B | Good Deal |
| 45-59 | C | Fair Value |
| 30-44 | D | Market Price |
| 0-29 | F | Overpriced |

**Requirements:**
- F-DF-1: Each property page displays the deal score prominently with the letter grade and a color indicator (green through red).
- F-DF-2: Score breakdown section shows each signal's contribution with a bar visualization.
- F-DF-3: Deal notes provide plain-English explanation (e.g., "Price dropped 8% over 45 days. Priced 12% below comp-adjusted value. Listed as 'motivated seller.'").
- F-DF-4: Search results are sortable by deal score (default), price, DOM, and $/sqft.
- F-DF-5: Scores recompute daily as new market data is ingested.
- F-DF-6: Deal score history is persisted so users can see if a property's score has improved or declined over time.

### 4.2 Price History Tracking

**Description:** Displays the complete listing and sale history for every property, including all price changes, status changes (listed, pending, removed, sold), and historical sale prices.

**Requirements:**
- F-PH-1: Interactive timeline visualization showing all price events (list, price change, pending, sold, removed, relisted).
- F-PH-2: Price change summary card: total drop from original list, number of reductions, average days between reductions.
- F-PH-3: Relist flag with explanation when a property was pending and returned to market.
- F-PH-4: Historical sale data (prior sales with dates and prices) when available.
- F-PH-5: Price history data refreshed at least daily for active listings.

### 4.3 AI Photo Analysis

**Description:** Uses Claude Vision to analyze listing photos and produce structured assessments of property condition, kitchen quality, bathroom quality, flooring type, and overall renovation level. Operates in two tiers to balance cost and depth.

**Tier 1 - Quick Screen (all properties):**
- F-PA-1: Analyze primary listing photo for every property.
- F-PA-2: Produce an overall condition score (1-10), quality tier (luxury / mid-grade / builder-grade / needs-work), and key observations.
- F-PA-3: Process via Claude Batch API using Haiku for cost efficiency (target < $0.002/property).
- F-PA-4: Display condition score on search result cards alongside deal score.

**Tier 2 - Deep Dive (favorited / high-score properties):**
- F-PA-5: Analyze all available listing photos (typically 15-40 per property).
- F-PA-6: Produce room-by-room analysis: room type, condition score, materials detected, quality assessment.
- F-PA-7: Aggregate into property-level scores with room-type weighting (kitchen 2.5x, bathrooms 2x, living areas 1.5x, bedrooms 1x, exterior 1x, other 0.5x).
- F-PA-8: Auto-populate property adjustments (detected features like hardwood floors, granite counters, finished basement) with source tagged as `photo_ai`.
- F-PA-9: Trigger automatically when a user favorites a property or manually via "Analyze Photos" button.
- F-PA-10: Display results in a photo gallery with AI annotations overlaid or shown alongside each photo.

### 4.4 Property Adjustments & Comp Analysis

**Description:** Tracks property features not captured in standard listing data and applies dollar-value adjustments to comparable sales analysis. Features can be detected from listing descriptions (NLP), listing photos (AI), or entered manually by users after touring.

**Tracked Adjustments:**

| Feature | Dollar Impact Range | Depreciation |
|---------|-------------------|--------------|
| Finished basement (full) | +$20K to +$35K | None |
| Kitchen remodel (major, < 5yr) | +$15K to +$30K | None |
| Bathroom remodel (major) | +$4K to +$8K per bath | None |
| New roof (< 5yr) | +$3K to +$8K | ~10%/yr |
| New HVAC (< 5yr) | +$3K to +$6K | ~8%/yr |
| New windows | +$5K to +$10K | None |
| 3-car vs. 2-car garage | +$15K to +$25K | None |
| In-ground pool | +$5K to +$15K | None |
| Backs to woods/park | +$5K to +$15K | None |
| Backs to busy road | -$10K to -$20K | None |
| Hardwood floors vs. carpet | +$3K to +$8K | None |
| Open floor plan | +$3K to +$7K | None |

**Requirements:**
- F-CA-1: Comp analysis displays both raw and adjusted sale prices for each comparable.
- F-CA-2: Adjustment breakdown shows each feature difference between subject and comp with the dollar amount applied.
- F-CA-3: Users can manually add/edit property features via the property detail page.
- F-CA-4: Each feature entry shows its source (NLP, photo AI, manual) and confidence level.
- F-CA-5: Comp selection uses similarity scoring based on distance, square footage, beds/baths, year built, and lot size.
- F-CA-6: Adjusted valuation range displayed prominently on property page (e.g., "Estimated value: $285K-$305K based on 6 adjusted comps").
- F-CA-7: Dollar adjustment values are configurable per market area and will expand as coverage grows.

### 4.5 Market Dashboard

**Description:** ZIP-code-level market statistics and trends, giving buyers a macro view of conditions in their target areas.

**Requirements:**
- F-MD-1: Dashboard displays for each ZIP: median list price, median sale price, median $/sqft, median days on market, active inventory count, sale-to-list ratio, months of supply.
- F-MD-2: Trend charts showing 6-12 month history for each metric.
- F-MD-3: Multi-ZIP comparison view (up to 5 ZIPs side-by-side).
- F-MD-4: Market condition indicator per ZIP: Strong Seller's Market / Seller's Market / Balanced / Buyer's Market / Strong Buyer's Market, derived from months of supply and sale-to-list ratio.
- F-MD-5: Data refreshed monthly from market data sources.

### 4.6 Community Forum / Comments

**Description:** A per-property discussion thread where users share touring notes, neighborhood insights, pricing opinions, and renovation observations. Community-generated content creates a data moat that competitors cannot replicate.

**Requirements:**

*Core Commenting:*
- F-CF-1: Every property page has a comments section where authenticated users can post text comments.
- F-CF-2: Comments are tied to a `property_id` and displayed in reverse chronological order (newest first) with an option to sort by most upvoted.
- F-CF-3: Comments support categorization tags selected by the author: "Touring Notes", "Neighborhood", "Pricing Opinion", "Renovation/Construction", "General".
- F-CF-4: Comments appear in real-time for all users viewing the same property page (via Supabase Realtime).
- F-CF-5: Users can edit their own comments within 15 minutes of posting. After 15 minutes, comments are locked.
- F-CF-6: Users can delete their own comments at any time. Deleted comments show "[deleted]" if they have replies.

*Voting:*
- F-CF-7: Authenticated users can upvote or downvote each comment once.
- F-CF-8: Net vote count is displayed on each comment.
- F-CF-9: Comments with a net score below -5 are collapsed by default with a "Show hidden comment" toggle.

*User Profiles:*
- F-CF-10: Each user has a public profile showing: display name, join date, comment count, average vote score.
- F-CF-11: Optional "Verified Buyer" badge awarded when a user provides proof of a completed home purchase (manual verification by admin for v1).
- F-CF-12: Users can set their target search area on their profile, displayed as a badge (e.g., "Searching in Macomb County").

*Moderation:*
- F-CF-13: Users can report comments via a "Report" button with reason categories: spam, harassment, discrimination, personal information, off-topic.
- F-CF-14: Reported comments are queued for admin review. Comments with 3+ reports are auto-hidden pending review.
- F-CF-15: Admin moderation dashboard for reviewing reported comments with approve/remove/ban actions.
- F-CF-16: Community guidelines page outlining prohibited content: personal attacks, agent/seller names, discriminatory language (Fair Housing compliance), spam, and off-topic content.
- F-CF-17: Automated keyword filter blocks comments containing known slurs, personal phone numbers, or email addresses before posting.

### 4.7 Saved Searches & Favorites

**Description:** Users save search criteria for quick re-use and bookmark individual properties into organized lists.

**Requirements:**
- F-SS-1: "Save This Search" button on search results page captures all active filters (ZIP codes, price range, beds/baths, min deal score, property type).
- F-SS-2: Saved searches accessible from user dashboard with one-click re-run.
- F-SS-3: "Favorite" heart icon on property cards and detail pages adds property to default favorites list.
- F-SS-4: Users can create custom lists (e.g., "Top Picks", "Need to Tour", "Toured - Liked", "Rejected") and move favorites between them.
- F-SS-5: Each favorited property supports a private notes field visible only to the user.
- F-SS-6: Favorites dashboard shows current status (active, pending, sold, removed) and any price changes since favoriting.
- F-SS-7: Maximum 3 saved searches and 25 favorites on free tier. Unlimited on paid tiers.

### 4.8 Price Drop Alerts

**Description:** Push and email notifications when properties of interest change price or new properties match saved search criteria.

**Requirements:**
- F-AL-1: Price drop alert triggered when any favorited property reduces its list price. Notification includes: old price, new price, drop percentage, updated deal score.
- F-AL-2: New listing alert triggered when a property matching a saved search's criteria is newly listed. Notification includes: address, price, deal score, primary photo, key stats.
- F-AL-3: Deal score upgrade alert triggered when a property matching saved criteria moves up a grade (e.g., C to B).
- F-AL-4: Users configure notification channel per alert type: email, push notification, or both.
- F-AL-5: Users configure frequency per alert type: instant, daily digest (morning), or weekly digest.
- F-AL-6: Alert history page shows all past alerts with links to the relevant property.
- F-AL-7: Free tier receives daily digest only. Paid tiers receive instant alerts.

### 4.9 Offer Assistant

**Description:** Recommends an offer price range based on deal score, adjusted comp analysis, and current market conditions. Provides reasoning the buyer can share with their agent.

**Requirements:**
- F-OA-1: "Get Offer Guidance" button on any property detail page generates a suggested offer range (low / target / high).
- F-OA-2: Offer range computed from: adjusted comp median, deal score, days on market, number of price drops, months of supply, sale-to-list ratio.
- F-OA-3: Reasoning narrative explains the recommendation in plain English, referencing specific comps and market data points.
- F-OA-4: User can select offer posture: "Aggressive" (10th-25th percentile of comp range), "Competitive" (25th-50th), "Conservative" (50th-75th).
- F-OA-5: Shareable offer analysis PDF/link that the buyer can send to their agent, containing: suggested range, comp details, adjustment breakdown, market conditions summary.
- F-OA-6: Disclaimer displayed: "This is not an appraisal or financial advice. Consult with your real estate agent and lender before making an offer."
- F-OA-7: Offer Assistant is a paid-tier feature only.

---

## 5. Technical Architecture

### 5.1 System Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Client Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Next.js Web  │  │  Mobile Web  │  │  PWA (push)  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         └─────────────────┼─────────────────┘           │
└───────────────────────────┼─────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────┐
│                     API Layer                           │
│  ┌────────────────────────┴────────────────────────┐    │
│  │          Next.js API Routes / Edge Functions     │    │
│  └────────────────────────┬────────────────────────┘    │
│                           │                             │
│  ┌────────────┐  ┌────────┴───────┐  ┌──────────────┐  │
│  │ Supabase   │  │  Supabase      │  │  Supabase    │  │
│  │ Auth       │  │  Database (PG) │  │  Realtime    │  │
│  └────────────┘  └────────────────┘  └──────────────┘  │
│                           │                             │
│  ┌────────────┐  ┌────────┴───────┐  ┌──────────────┐  │
│  │ Supabase   │  │  Supabase      │  │  Claude API  │  │
│  │ Storage    │  │  Edge Functions │  │  (Vision)    │  │
│  └────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────┐
│                  Background Jobs                        │
│  ┌──────────────┐  ┌─────┴────────┐  ┌──────────────┐  │
│  │ Data Ingest  │  │ Deal Score   │  │ Photo        │  │
│  │ Pipeline     │  │ Recompute    │  │ Analysis     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │ Alert        │  │ Market Data  │                     │
│  │ Dispatcher   │  │ Refresh      │                     │
│  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 14+ (App Router) | SSR for SEO-friendly property pages, React Server Components for performance, strong ecosystem |
| Styling | Tailwind CSS + shadcn/ui | Rapid development, mobile-responsive by default |
| Auth | Supabase Auth | Built-in email/password, Google/Apple OAuth, session management, RLS integration |
| Database | Supabase (PostgreSQL 15+) | Already in use for internal tool; RLS for multi-tenant security, JSONB for flexible data |
| Realtime | Supabase Realtime | Native integration for live comments; subscription-based with channel support |
| Storage | Supabase Storage | Cached listing photos, user avatars, generated PDF reports |
| AI/Vision | Claude API (Haiku for batch, Sonnet for deep analysis) | Already integrated; excellent structured output for photo analysis |
| Background Jobs | Supabase Edge Functions + pg_cron | Serverless execution for ingest, scoring, alerts; pg_cron for scheduling |
| Email | Resend or Supabase Edge Functions + SMTP | Transactional emails for alerts and digests |
| Push Notifications | Web Push API (service worker) | No app store dependency; works via PWA |
| Hosting | Vercel | Native Next.js hosting, edge functions, preview deployments |
| Analytics | PostHog or Plausible | Privacy-friendly, self-hostable option |

### 5.3 Key Technical Decisions

**SEO-Friendly Property Pages:**
- Each property gets a canonical URL: `/properties/{slug}` where slug is `{address-city-state-zip}`.
- Server-side rendered with full Open Graph tags for social sharing.
- Structured data (JSON-LD) for Google real estate rich results.
- Sitemap auto-generated from active listings.

**Real-Time Comments:**
- Supabase Realtime subscriptions on the `comments` table filtered by `property_id`.
- Optimistic UI updates on comment submission; reconcile on server confirmation.
- Presence tracking to show "X users viewing this property" (optional, Phase 3).

**Mobile-Responsive Design:**
- Mobile-first responsive design; all features functional on 375px+ viewport.
- Bottom navigation bar on mobile for core actions (Search, Favorites, Alerts, Profile).
- Property cards designed for thumb-scrollable vertical feed.
- Map view with gesture support on mobile.

**Data Pipeline:**
- Ingest pipeline runs as scheduled Supabase Edge Functions (or external cron hitting an API endpoint).
- Ingestion frequency: active listings refreshed daily, market stats monthly.
- Deal scores recomputed after each ingestion cycle.
- Price drop detection runs as a diff between current and previous ingestion; triggers alert dispatch.

---

## 6. Data Model

### 6.1 Existing Tables (from internal tool)

These tables are already in production and will be retained with minor schema additions.

**`properties`** — Core property listing data
- `id` (UUID, PK)
- `mls_id`, `source`, `address`, `city`, `state`, `zip_code`
- `price`, `beds`, `baths`, `sqft`, `lot_sqft`, `year_built`
- `property_type`, `status`, `days_on_mls`
- `price_per_sqft`, `description`, `primary_photo`, `alt_photos`
- `estimated_value`, `last_sold_price`, `last_sold_date`
- `latitude`, `longitude`
- `created_at`, `updated_at`

**`price_history`** — All listing/sale events
- `id` (UUID, PK)
- `property_id` (FK -> properties)
- `event_type` (Listed, Price Changed, Pending, Sold, Removed)
- `price`, `date`, `source`

**`market_stats`** — ZIP-level monthly metrics
- `id` (UUID, PK)
- `zip_code`, `period_start`, `period_end`
- `median_list_price`, `median_sale_price`, `median_dom`
- `active_listings`, `avg_sale_to_list`, `months_of_supply`

**`property_adjustments`** — Feature tracking per property
- `id` (UUID, PK)
- `property_id` (FK -> properties, UNIQUE)
- `basement_finished`, `kitchen_remodel_year`, `bathroom_remodel_year`
- `roof_year`, `hvac_year`, `windows_new`
- `garage_cars`, `pool`, `backs_to`, `flooring_type`, `floor_plan`
- `features_json` (JSONB overflow)
- `source` (nlp_extracted, photo_ai, manual)
- `confidence`

**`photo_analysis`** — Per-photo AI results
- `id` (UUID, PK)
- `property_id` (FK -> properties)
- `photo_url`, `room_type`, `condition_score`, `quality_tier`
- `features_json`, `model_used`, `analyzed_at`

**`deal_scores`** — Computed deal scores (materialized view or table)
- `property_id` (FK -> properties)
- `total_score`, `grade`
- `signal_breakdown` (JSONB: each signal's contribution)
- `deal_notes` (text summary)
- `computed_at`

### 6.2 New Tables (consumer product)

**`users`** (extends Supabase Auth `auth.users`)

```sql
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    avatar_url TEXT,
    bio TEXT,
    target_area TEXT,                    -- e.g., "Macomb County, MI"
    is_verified_buyer BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    subscription_tier TEXT DEFAULT 'free',  -- free, pro, premium
    subscription_expires_at TIMESTAMPTZ,
    comment_count INTEGER DEFAULT 0,
    avg_vote_score NUMERIC(3,1) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**`comments`**

```sql
CREATE TABLE public.comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    parent_comment_id UUID REFERENCES comments(id) ON DELETE CASCADE,  -- for threading
    body TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    category TEXT NOT NULL CHECK (category IN (
        'touring_notes', 'neighborhood', 'pricing_opinion',
        'renovation', 'general'
    )),
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    net_score INTEGER GENERATED ALWAYS AS (upvotes - downvotes) STORED,
    is_edited BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,       -- hidden by moderation
    report_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_comments_property ON comments(property_id, created_at DESC);
CREATE INDEX idx_comments_user ON comments(user_id);
CREATE INDEX idx_comments_reported ON comments(report_count) WHERE report_count > 0;
```

**`comment_votes`**

```sql
CREATE TABLE public.comment_votes (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    vote_type SMALLINT NOT NULL CHECK (vote_type IN (-1, 1)),  -- -1 = downvote, 1 = upvote
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, comment_id)
);
```

**`comment_reports`**

```sql
CREATE TABLE public.comment_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    reporter_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL CHECK (reason IN (
        'spam', 'harassment', 'discrimination',
        'personal_info', 'off_topic'
    )),
    details TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'actioned')),
    reviewed_by UUID REFERENCES auth.users(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (comment_id, reporter_id)
);
```

**`saved_searches`**

```sql
CREATE TABLE public.saved_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    criteria JSONB NOT NULL,
    -- criteria schema: {
    --   zip_codes: ["48044", "48042"],
    --   price_min: 200000, price_max: 350000,
    --   beds_min: 3, baths_min: 2,
    --   min_deal_score: 45,
    --   property_types: ["single_family"],
    --   sqft_min: 1500
    -- }
    alerts_enabled BOOLEAN DEFAULT TRUE,
    alert_frequency TEXT DEFAULT 'daily' CHECK (alert_frequency IN ('instant', 'daily', 'weekly')),
    last_alerted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_saved_searches_user ON saved_searches(user_id);
```

**`favorites`**

```sql
CREATE TABLE public.favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    list_name TEXT DEFAULT 'default',      -- user-defined list name
    private_notes TEXT,
    price_at_favorite NUMERIC,             -- snapshot price when favorited
    alert_on_price_drop BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, property_id)
);

CREATE INDEX idx_favorites_user ON favorites(user_id, list_name);
CREATE INDEX idx_favorites_property ON favorites(property_id);
```

**`alerts`**

```sql
CREATE TABLE public.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL CHECK (alert_type IN (
        'price_drop', 'new_listing', 'score_upgrade', 'new_comment'
    )),
    property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
    saved_search_id UUID REFERENCES saved_searches(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    -- payload schema varies by type:
    -- price_drop: { old_price, new_price, drop_pct, new_score }
    -- new_listing: { address, price, score, grade, photo_url }
    -- score_upgrade: { old_grade, new_grade, old_score, new_score }
    channel TEXT NOT NULL CHECK (channel IN ('email', 'push', 'both')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_user_status ON alerts(user_id, status, created_at DESC);
```

**`alert_preferences`**

```sql
CREATE TABLE public.alert_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    price_drop_channel TEXT DEFAULT 'email',
    price_drop_frequency TEXT DEFAULT 'instant',
    new_listing_channel TEXT DEFAULT 'email',
    new_listing_frequency TEXT DEFAULT 'daily',
    score_upgrade_channel TEXT DEFAULT 'email',
    score_upgrade_frequency TEXT DEFAULT 'daily',
    comment_reply_channel TEXT DEFAULT 'email',
    comment_reply_frequency TEXT DEFAULT 'daily',
    digest_time TIME DEFAULT '08:00',        -- preferred digest delivery time
    timezone TEXT DEFAULT 'America/Detroit',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 6.3 Row-Level Security (RLS)

All tables will have RLS enabled. Key policies:

| Table | SELECT | INSERT | UPDATE | DELETE |
|-------|--------|--------|--------|--------|
| profiles | Public (display_name, avatar, badges) | Own profile only | Own profile only | N/A |
| comments | Public (non-hidden) | Authenticated users | Own comments, within 15 min | Own comments |
| comment_votes | Own votes only | Authenticated users | Own votes | Own votes |
| comment_reports | Own reports only | Authenticated users | N/A | N/A |
| saved_searches | Own searches only | Authenticated users | Own searches | Own searches |
| favorites | Own favorites only | Authenticated users | Own favorites | Own favorites |
| alerts | Own alerts only | System only | System only | Own alerts |
| properties | Public | System only | System only | System only |
| deal_scores | Public (free: score + grade only; paid: full breakdown) | System only | System only | System only |

---

## 7. Success Metrics

### 7.1 North Star Metric

**Monthly Active Users (MAU) who view 5+ property detail pages.** This indicates genuine engagement with the core value proposition rather than casual visits.

### 7.2 Acquisition Metrics

| Metric | Phase 1 Target (Month 3) | Phase 2 Target (Month 6) | Phase 3 Target (Month 12) |
|--------|--------------------------|--------------------------|---------------------------|
| Registered users | 500 | 3,000 | 15,000 |
| MAU (5+ property views) | 200 | 1,200 | 6,000 |
| Organic search traffic (monthly) | 1,000 | 10,000 | 50,000 |
| User referral rate | -- | 10% | 15% |

### 7.3 Engagement Metrics

| Metric | Target |
|--------|--------|
| Avg. properties viewed per session | 8+ |
| Favorites per active user (monthly) | 5+ |
| Saved searches per active user | 2+ |
| Comments per active user (monthly) | 1+ |
| Alert click-through rate | 25%+ |
| Time on property detail page | 90+ seconds |
| Return visit rate (7-day) | 40%+ |

### 7.4 Revenue Metrics

| Metric | Phase 2 Target (Month 6) | Phase 3 Target (Month 12) |
|--------|--------------------------|---------------------------|
| Paid subscribers | 100 | 750 |
| Monthly Recurring Revenue (MRR) | $1,500 | $11,000 |
| Free-to-paid conversion rate | 5% | 7% |
| Paid user churn (monthly) | < 8% | < 5% |

### 7.5 Content / Data Moat Metrics

| Metric | Target |
|--------|--------|
| Comments per property (active listings in covered ZIPs) | 2+ avg by Month 12 |
| Properties with community comments (in covered ZIPs) | 30%+ by Month 12 |
| AI photo analyses completed | 50,000+ by Month 12 |
| User-reported "photo vs. reality" mismatches | Track; no specific target |

---

## 8. Risks & Mitigations

### 8.1 Data & Legal Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Data source ToS violations.** Scraping Redfin/Realtor.com may violate terms of service, leading to IP blocks or legal action. | High | Medium | (1) Consult with an attorney before launch. (2) Investigate MLS IDX data feeds as a legitimate data source. (3) Attribute data sources clearly. (4) Rate-limit scraping and respect robots.txt. (5) Build the product to be data-source-agnostic so we can swap to licensed feeds. |
| **Fair Housing Act compliance.** Community comments could contain discriminatory language about neighborhoods or residents. | High | Medium | (1) Automated keyword filter on comment submission. (2) Clear community guidelines with Fair Housing language. (3) Moderation queue with rapid response. (4) Legal review of comment policies before launch. |
| **Accuracy liability.** Users may make financial decisions based on deal scores or offer suggestions that prove inaccurate. | High | Low | (1) Prominent disclaimers on all analysis ("not an appraisal"). (2) Show confidence ranges, not single-point estimates. (3) Terms of Service with limitation of liability. (4) Encourage users to consult licensed professionals. |

### 8.2 Product Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Cold-start problem for comments.** No comments exist at launch; empty comment sections feel dead. | Medium | High | (1) Seed initial markets with our own touring notes from personal home search. (2) Incentivize early comments (badge, free month of Pro). (3) Show comment sections only when at least 1 comment exists until critical mass is reached, using "Be the first to share insights" CTA otherwise. |
| **Low comment quality.** Comments devolve into noise, speculation, or agent marketing. | Medium | Medium | (1) Category tags structure content. (2) Voting surfaces quality. (3) Active moderation in early months. (4) Character minimum (50 chars) to discourage low-effort posts. |
| **Deal score gaming.** Listing agents learn the scoring signals and optimize listings to score higher without genuine value. | Low | Low | (1) Do not publicly document exact scoring weights. (2) Signal weights are tunable and can be adjusted. (3) Community comments serve as a check on misleading listings. |

### 8.3 Technical Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **AI photo analysis cost at scale.** Analyzing all photos for all properties in expanded markets could become expensive. | Medium | Medium | (1) Tiered approach limits expensive analysis to high-value actions (favoriting). (2) Batch API pricing is 50% cheaper than real-time. (3) Cache results; only re-analyze if photos change. (4) Cost is offset by paid subscriptions. |
| **Data freshness.** Stale listings or prices erode trust. | High | Medium | (1) Daily ingestion pipeline for active listings. (2) Show "last updated" timestamp on all data. (3) Allow users to report stale data. (4) Status change detection (sold, pending) prioritized in pipeline. |
| **Supabase scalability.** Real-time subscriptions, RLS policies, and growing data volume may strain Supabase. | Medium | Low | (1) Start on Supabase Pro plan. (2) Use database indexes per schema above. (3) Materialized views for deal scores rather than computed views. (4) Connection pooling via Supabase's built-in PgBouncer. (5) Migration path to dedicated Postgres if needed. |

### 8.4 Business Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Low willingness to pay.** Home buyers may not pay for analysis tools when Zillow/Redfin are free. | High | Medium | (1) Generous free tier to build habit and demonstrate value. (2) Paid features target highest-value actions (offer guidance, instant alerts, AI deep-dive). (3) Community comments are free to maximize data moat. (4) Validate pricing with early user interviews before committing. |
| **Geographic expansion difficulty.** Adjustment values, market knowledge, and data sources vary by market. | Medium | High | (1) Start in a single metro (SE Michigan) and go deep. (2) Build adjustment value framework that supports per-market configuration. (3) Community comments provide local knowledge even in new markets. (4) Expand only after proving unit economics in home market. |

---

## 9. Phased Rollout Plan

### Phase 1: Foundation (Months 1-3)

**Goal:** Launch a publicly accessible web app with core analysis features for SE Michigan. Establish the product's value proposition and begin building user base.

**Scope:**
- Next.js web app deployed on Vercel with Supabase backend
- Supabase Auth (email + Google OAuth)
- Property search and browse with deal scores (F-DF-1 through F-DF-6)
- Property detail pages with price history (F-PH-1 through F-PH-5)
- AI photo analysis Tier 1: quick screen on all properties (F-PA-1 through F-PA-4)
- Market dashboard with ZIP-level trends (F-MD-1 through F-MD-5)
- Basic saved searches and favorites (F-SS-1 through F-SS-3)
- SEO-optimized property pages with structured data
- Mobile-responsive design
- Coverage: Macomb County + adjacent ZIP codes (~30 ZIPs)

**Key Deliverables:**
- [ ] Production database with RLS policies
- [ ] Data ingestion pipeline running on daily schedule
- [ ] Deal scoring engine computing nightly
- [ ] Photo analysis batch pipeline (Tier 1)
- [ ] Deployed web app with property search, detail, and market pages
- [ ] User registration and authentication
- [ ] Basic analytics tracking

**Not Included:** Comments, alerts, offer assistant, paid tiers, Tier 2 photo analysis.

---

### Phase 2: Community & Engagement (Months 4-6)

**Goal:** Launch community features and alerts to drive engagement, retention, and word-of-mouth growth. Introduce freemium model.

**Scope:**
- Community comments with categories, voting, and moderation (F-CF-1 through F-CF-17)
- Price drop alerts via email (F-AL-1 through F-AL-3)
- New listing alerts for saved searches (F-AL-2)
- Favorites lists and private notes (F-SS-4 through F-SS-6)
- Property adjustments from NLP extraction (F-CA-1 through F-CA-4)
- Comp analysis with adjustments displayed (F-CA-5 through F-CA-6)
- AI photo analysis Tier 2 for favorited properties (F-PA-5 through F-PA-10)
- Freemium tier gate introduced

**Pricing Tiers (v1):**

| Feature | Free | Pro ($15/mo) | Premium ($29/mo) |
|---------|------|-------------|-------------------|
| Deal scores (grade only) | Yes | Yes | Yes |
| Deal score breakdown | -- | Yes | Yes |
| Price history | Last 3 events | Full | Full |
| AI photo screen (Tier 1) | Score only | Full details | Full details |
| AI photo deep dive (Tier 2) | -- | 10/month | Unlimited |
| Saved searches | 3 | 10 | Unlimited |
| Favorites | 25 | 100 | Unlimited |
| Alerts | Daily digest | Instant | Instant |
| Comp analysis | Basic (3 comps) | Full (10 comps) | Full + adjustments |
| Offer assistant | -- | -- | Yes |
| Community comments | Read + write | Read + write | Read + write |

**Key Deliverables:**
- [ ] Comments system with real-time updates
- [ ] Moderation dashboard
- [ ] Alert pipeline (email)
- [ ] Stripe integration for subscriptions
- [ ] Tier-based feature gating
- [ ] NLP adjustment extraction running on all properties
- [ ] Tier 2 photo analysis pipeline

---

### Phase 3: Monetization & Scale (Months 7-12)

**Goal:** Optimize conversion, launch Offer Assistant, expand geographic coverage, and build toward sustainable revenue.

**Scope:**
- Offer Assistant (F-OA-1 through F-OA-7)
- Push notifications via PWA (F-AL-4, F-AL-5)
- Alert preference configuration (F-AL-4 through F-AL-6)
- Verified Buyer badges (F-CF-11)
- Manual property adjustment entry on web (F-CA-3)
- Geographic expansion: Oakland County, Wayne County, Washtenaw County (metro Detroit)
- Alert frequency and channel preferences (F-AL-4, F-AL-5)
- Shareable offer analysis reports (F-OA-5)
- User profile enhancements (F-CF-10, F-CF-12)
- Performance optimization and caching layer
- A/B testing on pricing and paywall placement

**Key Deliverables:**
- [ ] Offer Assistant with reasoning engine
- [ ] PDF/shareable report generation
- [ ] Push notification infrastructure
- [ ] Expanded coverage (100+ ZIP codes)
- [ ] Conversion funnel optimization
- [ ] User onboarding flow improvements
- [ ] Admin tools for market expansion (adjustment value configuration per market)

---

### Future Considerations (Month 12+)

- **Native mobile app** if PWA engagement data supports the investment.
- **Agent partnerships:** Referral revenue from connecting buyers with agents. Agents could pay for promoted presence on properties they list.
- **Appraisal/inspection integration:** Partner with appraisers to validate AI condition scores; build confidence in the product.
- **Rental analysis:** Extend deal scoring and comp analysis to rental properties for investor users.
- **National expansion:** Requires licensed MLS data feeds (IDX/RETS); plan for this as the business scales.
- **API access:** Offer data and scores via API for real estate professionals and tools.
- **Machine learning deal scoring:** Replace rule-based scoring with ML model trained on actual sale outcomes (did the property sell above or below our predicted value?).

---

## Appendix A: Competitive Landscape

| Competitor | Deal Scoring | AI Photo Analysis | Community Comments | Comp Adjustments | Offer Guidance |
|-----------|-------------|-------------------|-------------------|-----------------|----------------|
| Zillow | No (Zestimate only) | No | No | No | No |
| Redfin | No (Redfin Estimate only) | No | No | No | No |
| Realtor.com | No | No | No | No | No |
| Haus (defunct) | Partial | No | No | No | Yes (was core feature) |
| **HomeValue Analyzer** | **Yes (8-signal, 0-100)** | **Yes (Claude Vision)** | **Yes (per-property threads)** | **Yes (dollar-value)** | **Yes** |

**Differentiation summary:** No existing consumer platform combines quantitative deal scoring, AI-powered photo condition analysis, feature-adjusted comp analysis, and community-sourced property insights. Each of these alone is a feature; together they represent a fundamentally different approach to home buying research. The community comments layer is the long-term moat: every comment makes the platform more valuable and harder to replicate.

---

## Appendix B: Open Questions

1. **MLS data licensing.** Can we obtain IDX/RETS feeds for SE Michigan to replace scraping? What is the cost and timeline? This is a prerequisite for scaling beyond a small user base.
2. **Fair Housing legal review.** What specific moderation policies and automated filters are required to ensure comment features comply with the Fair Housing Act?
3. **Pricing validation.** Are the proposed tier prices ($15/$29) aligned with buyer willingness to pay? Conduct user interviews before finalizing.
4. **Agent reaction.** Will listing agents view this product as adversarial (exposing overpricing) or beneficial (connecting them with serious buyers)? This affects partnership strategy.
5. **Photo analysis accuracy validation.** What is the measured accuracy of Claude Vision condition scoring against human assessments? Conduct a formal accuracy study before marketing AI scores as a core feature.
6. **Comp adjustment calibration.** Are the Macomb County dollar adjustment values accurate? Validate against appraiser data or actual sale price deltas for homes with known features.
