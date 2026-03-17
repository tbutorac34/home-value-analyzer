# Deal Score Methodology

## Overview

Every for-sale property is scored 0-100 based on 8 signals that indicate whether it's likely a good deal. Higher score = better deal. Signals are weighted by predictive importance.

**Total: 100 points across 8 signals**

| # | Signal | Max Points | What It Measures |
|---|--------|-----------|-----------------|
| 1 | Price vs Estimated Value | 25 | Is it priced below what it's worth? |
| 2 | Price Drop History | 20 | Is the seller cutting price? How much? |
| 3 | $/sqft vs ZIP Average | 15 | Is it cheap relative to the neighborhood? |
| 4 | Days on Market | 12 | Has it been sitting? (leverage for buyer) |
| 5 | Flip Detection | 10 | Was it bought cheap and relisted high? |
| 6 | Sale-to-List Ratio | 8 | Are homes in this area selling below asking? |
| 7 | Relist Detection | 5 | Did a previous deal fall through? |
| 8 | Description Keywords | 5 | Does the listing language signal motivation? |

### Grade Scale

| Score | Grade | Interpretation |
|-------|-------|---------------|
| 75-100 | A | Strong deal — significant undervaluation or seller urgency |
| 60-74 | B | Good deal — multiple positive signals |
| 45-59 | C | Fair value — some deal indicators present |
| 30-44 | D | Market price — nothing stands out |
| 0-29 | F | Overpriced or no data to evaluate |

---

## Signal 1: Price vs Estimated Value (0-25 points)

**Data source:** `properties.estimated_value` (computed from comparable sold properties using weighted $/sqft)

**Logic:** Compare the list price to our comp-based estimated value. If estimated value is higher than list price, the property may be underpriced.

```
discount = (estimated_value - list_price) / list_price
```

| Discount | Points | Example |
|----------|--------|---------|
| >= 15% | 25 | Listed $340K, estimate $391K |
| >= 10% | 20 | Listed $340K, estimate $374K |
| >= 5% | 14 | Listed $340K, estimate $357K |
| >= 2% | 8 | Listed $340K, estimate $347K |
| >= 0% | 3 | Listed at or just below estimate |
| < 0% (overpriced) | 0 | Listed above estimate |

**Why 25 points (highest weight):** This is the most direct measure of undervaluation. If comparable homes sold for more per sqft, this property is objectively cheap relative to the market.

**Limitations:**
- Estimate quality depends on having enough sold comps in the same ZIP
- Doesn't account for condition (a trashed home in a nice ZIP will look undervalued)
- Our comp-based estimate uses weighted $/sqft — not as sophisticated as Zillow/Redfin AVMs

**Future enhancement:** Blend our comp estimate with the Redfin Estimate (now being captured) for a more robust signal.

---

## Signal 2: Price Drop History (0-20 points)

**Data source:** `price_history` table — events of type "Price Changed"

**Logic:** Two sub-signals scored independently:

### Sub-signal 2a: Number of Price Drops (0-10 points)
How many times has the seller cut the price?

| Drops | Points | Interpretation |
|-------|--------|---------------|
| >= 4 | 10 | Seller is desperate, property isn't moving |
| 3 | 8 | Strong motivation signal |
| 2 | 5 | Moderate motivation |
| 1 | 2 | Single adjustment, could be strategic |
| 0 | 0 | No drops |

### Sub-signal 2b: Total Drop Magnitude (0-10 points)
What's the total percentage reduction from original list price?

```
total_drop_pct = (original_list_price - current_list_price) / original_list_price
```

| Total Drop | Points | Example |
|-----------|--------|---------|
| >= 15% | 10 | Listed $500K → now $425K |
| >= 10% | 8 | Listed $500K → now $450K |
| >= 5% | 5 | Listed $500K → now $475K |
| >= 2% | 2 | Listed $500K → now $490K |
| < 2% | 0 | Minimal reduction |

**Why 20 points total:** Price drops are the strongest real-world signal of seller motivation. Multiple drops with significant magnitude almost always mean the seller is struggling to find a buyer at their price.

**How we calculate it:**
1. Find the first "Listed" event in price_history
2. Count all "Price Changed" events
3. Compare first listed price to current list price for total drop percentage

**Limitations:**
- We only have price history for properties where we scraped the Redfin page
- "Price Changed" events don't always mean a decrease (though they almost always do in practice)
- A strategic re-price (e.g., list high to test the market, then drop to realistic price) scores the same as a desperate seller

---

## Signal 3: $/sqft vs ZIP Average (0-15 points)

**Data source:** `properties.price_per_sqft` compared to median $/sqft of FOR_SALE listings in the same ZIP code

**Logic:** If a property's $/sqft is significantly below the ZIP median, it may be underpriced.

```
ppsf_discount = (zip_median_ppsf - property_ppsf) / zip_median_ppsf
```

| Discount | Points | Example |
|----------|--------|---------|
| >= 20% | 15 | ZIP median $200/sqft, property $160/sqft |
| >= 15% | 12 | ZIP median $200/sqft, property $170/sqft |
| >= 10% | 8 | ZIP median $200/sqft, property $180/sqft |
| >= 5% | 4 | ZIP median $200/sqft, property $190/sqft |
| < 5% | 0 | At or above ZIP average |

**ZIP benchmark calculation:**
- Median $/sqft of all FOR_SALE properties in the same ZIP code
- Requires at least 5 listings in the ZIP to be reliable
- Falls back to Redfin Data Center median_ppsf if insufficient local data

**Why 15 points:** Strong indicator of relative value, but can be misleading — a low $/sqft might mean a larger home (natural discount for scale) or poor condition.

**Limitations:**
- Doesn't account for property type (condos vs single-family have very different $/sqft)
- ZIP codes are broad — micro-neighborhoods within a ZIP can vary significantly
- Larger homes naturally have lower $/sqft

---

## Signal 4: Days on Market (0-12 points)

**Data source:** `properties.days_on_mls` compared to `market_stats.median_dom` for the ZIP

**Logic:** Properties sitting longer than the market average suggest the seller may be motivated to negotiate.

```
dom_ratio = property_days_on_mls / zip_median_dom
```

| DOM Ratio | Points | Interpretation |
|----------|--------|---------------|
| >= 3.0x | 12 | Extreme — 3x market average, seller likely frustrated |
| >= 2.0x | 9 | High — well above normal |
| >= 1.5x | 6 | Moderate — starting to sit |
| >= 1.0x | 3 | At market average |
| < 1.0x | 0 | Below average, moving normally |

**Why 12 points:** DOM is a reliable negotiation leverage signal. However, it can be misleading — a property might sit because it's overpriced (which we already capture in Signal 3) or because it has genuine issues.

**Limitations:**
- DOM resets if the listing is removed and relisted (agents do this to look "fresh")
- Seasonal effects — winter DOM is naturally higher than summer
- Requires market_stats data for the ZIP (from Redfin Data Center)

---

## Signal 5: Flip Detection (0-10 points)

**Data source:** `properties.last_sold_price` and `properties.list_price`

**Logic:** If a property was recently purchased at a much lower price and is now listed with a large markup, it's likely a flip. Flips with high markups are often overpriced — the flipper is trying to maximize profit, creating negotiation room.

```
markup = (list_price - last_sold_price) / last_sold_price
```

| Condition | Points | Interpretation |
|----------|--------|---------------|
| Markup >= 50% | 10 | Aggressive flip — significant negotiation room |
| Markup >= 30% | 6 | Moderate flip markup |
| Markup <= 5% | 4 | Barely marked up — seller may be motivated (not a profitable flip) |
| Everything else | 0 | Normal appreciation |

**Why 10 points:** Flips with high markups are one of the best negotiation opportunities. The flipper has a cost basis well below list price and room to negotiate. Conversely, barely-marked-up properties suggest the seller needs to sell quickly.

**Limitations:**
- `last_sold_price` isn't always available
- Doesn't distinguish between flips (renovated) and wholesale (no work done)
- A 50% markup after a full renovation might be fair; the same markup with no work is overpriced
- The adjustment system (Epic 2) will help distinguish these once integrated

---

## Signal 6: Area Sale-to-List Ratio (0-8 points)

**Data source:** `market_stats.avg_sale_to_list` for the ZIP code

**Logic:** If homes in this area are consistently selling below asking price, there's more room to negotiate.

| Sale-to-List | Points | Interpretation |
|-------------|--------|---------------|
| < 95% | 8 | Strong buyer's market — 5%+ off asking is normal |
| < 97% | 5 | Buyers getting 3-5% off asking |
| < 99% | 3 | Slight buyer advantage |
| >= 99% | 0 | Homes selling at or above asking |

**Why 8 points:** This is a market-level signal, not property-specific. It tells you about negotiation leverage in the area rather than about this specific home.

**Data source:** Redfin Data Center, most recent monthly period for the ZIP.

**Limitations:**
- Market-level average may not apply to every property
- Lags by 1-2 months
- A hot micro-neighborhood within a cold ZIP would be misleading

---

## Signal 7: Relist Detection (0-5 points)

**Data source:** `price_history` — pattern of "Listed" event following "Pending" or "Listing Removed"

**Logic:** If a property went under contract (Pending) and then was relisted, the previous deal fell through. This often means the seller is more motivated — they thought they had a buyer and lost them.

| Condition | Points | Interpretation |
|----------|--------|---------------|
| Relisted at a lower price | 5 | Deal fell through AND seller lowered expectations |
| Relisted at same/higher price | 2 | Deal fell through but seller hasn't adjusted |
| No relist | 0 | Normal listing |

**How we detect it:**
1. Scan price_history chronologically
2. Track if we see a "Pending" or "Listing Removed" event
3. If a "Listed" event follows, it's a relist
4. Compare the relist price to the original list price

**Why 5 points:** Useful but relatively rare signal. Most impactful when combined with other signals (relist + price drop + high DOM = very motivated seller).

---

## Signal 8: Description Keywords (0-5 points, can go negative)

**Data source:** `properties.description` — NLP keyword scan

**Logic:** Listing descriptions contain language that signals seller motivation (or lack thereof). We scan for specific keywords in three tiers.

### Positive Keywords (seller motivation)

| Tier | Points | Keywords |
|------|--------|----------|
| High motivation | +3 | "motivated seller", "seller motivated", "must sell", "priced to sell", "estate sale", "probate", "cash only", "as-is", "as is", "sold as-is", "reo" |
| Investor-targeted | +2 | "investor special", "investor opportunity", "investment opportunity", "sweat equity", "instant equity", "bring all offers", "all offers considered", "make it your own", "bring your vision", "cosmetic", "vacant", "unoccupied" |
| Urgency signals | +1 | "won't last", "wont last", "price reduced", "price improvement", "new price", "just reduced", "relocating", "relocation" |

### Negative Keywords (overpriced signal)

| Tier | Points | Keywords |
|------|--------|----------|
| Premium pricing | -1 | "move-in ready", "move in ready", "turnkey" |

**Scoring:** Points accumulate across matches, capped at 5 (floor at 0 for the total score, but negative points reduce the total after all signals are summed).

**Why 5 points:** Description analysis is supplementary — the words agents choose are informative but not as reliable as hard data (price drops, DOM, comps). The negative signal for "move-in ready" / "turnkey" reflects that these sellers are pricing for condition and less likely to negotiate.

**Limitations:**
- Keywords were selected based on frequency analysis of our actual data (1,327 descriptions)
- Many keywords like "handyman special" and "fixer upper" had zero occurrences — agents avoid negative language
- "Opportunity" (23% of listings) is too generic to score
- "Estate" (7%) sometimes means "estate sale" (motivated) and sometimes means "estate-style home" (marketing)

**Future enhancement:** Proper NLP/LLM analysis of description tone and intent rather than keyword matching.

---

## Planned Future Signals

These signals will be added as the enhanced data backfill completes:

| Signal | Max Points | Data Source | Status |
|--------|-----------|-------------|--------|
| Redfin Estimate vs list price | TBD | `properties.redfin_estimate` | Data being collected |
| Walk Score value gap | TBD | `properties.walk_score` | Data being collected |
| School rating value gap | TBD | `properties.school_rating` | Data being collected |
| Photo count / quality | TBD | `property_photos` | Data being collected |
| Feature-adjusted undervaluation | TBD | `property_adjustments` | NLP extraction done |

When these are added, the total will be re-normalized to 100 points. Existing signals may have their weights reduced proportionally.

---

## How Scores Are Used

### CLI
```bash
python -m home_value_analyzer deals --zips 48044 --min-beds 3 --min-price 300000
python -m home_value_analyzer deals --detail <property_id>  # full breakdown
```

### Supabase Dashboard
Query the `deal_scores` view:
```sql
SELECT grade, total_score, address, zip_code, list_price, sqft, bedrooms
FROM deal_scores
WHERE status = 'FOR_SALE' AND list_price BETWEEN 300000 AND 700000
ORDER BY total_score DESC;
```

### Interpretation Guide
- **Grade A (75+):** Actively investigate. Multiple strong signals. Likely worth touring.
- **Grade B (60-74):** Worth a closer look. Run comps and check photos.
- **Grade C (45-59):** Fair value with some deal potential. Dig deeper before pursuing.
- **Grade D (30-44):** Market price. No strong deal signals. May still be a good home, just not a bargain.
- **Grade F (<30):** Overpriced or insufficient data. Proceed with caution.
