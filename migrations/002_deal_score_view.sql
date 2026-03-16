-- Deal Finder: Supabase SQL view
-- Run in: https://supabase.com/dashboard/project/btwntyfjcendzmqwdoic/sql/new

CREATE OR REPLACE VIEW deal_scores AS
WITH zip_benchmarks AS (
    SELECT
        zip_code,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_sqft) AS median_ppsf,
        COUNT(*) AS zip_listing_count
    FROM properties
    WHERE status = 'FOR_SALE'
      AND price_per_sqft IS NOT NULL
    GROUP BY zip_code
),
market_benchmarks AS (
    SELECT DISTINCT ON (region_name)
        region_name,
        median_dom,
        avg_sale_to_list
    FROM market_stats
    WHERE region_type = 'zip'
    ORDER BY region_name, period DESC
),
price_drop_agg AS (
    SELECT
        property_id,
        COUNT(*) FILTER (WHERE event = 'Price Changed') AS num_drops,
        -- Get earliest Listed price
        (ARRAY_AGG(price ORDER BY date ASC) FILTER (WHERE event = 'Listed' AND price IS NOT NULL))[1] AS first_list_price,
        -- Detect relists
        COUNT(*) FILTER (WHERE event = 'Listed') AS num_listings
    FROM price_history
    GROUP BY property_id
),
scored AS (
    SELECT
        p.id,
        p.address,
        p.city,
        p.zip_code,
        p.status,
        p.list_price,
        p.sold_price,
        p.estimated_value,
        p.price_per_sqft,
        p.sqft,
        p.bedrooms,
        p.bathrooms_total,
        p.days_on_mls,
        p.property_url,
        p.last_sold_price,
        p.last_sold_date,
        p.property_type,
        p.year_built,

        -- Signal 1: Value discount (0-25)
        CASE
            WHEN p.estimated_value IS NULL OR p.list_price IS NULL OR p.list_price = 0 THEN 0
            WHEN (p.estimated_value - p.list_price) / p.list_price >= 0.15 THEN 25
            WHEN (p.estimated_value - p.list_price) / p.list_price >= 0.10 THEN 20
            WHEN (p.estimated_value - p.list_price) / p.list_price >= 0.05 THEN 14
            WHEN (p.estimated_value - p.list_price) / p.list_price >= 0.02 THEN 8
            WHEN (p.estimated_value - p.list_price) / p.list_price >= 0.0 THEN 3
            ELSE 0
        END AS value_discount_score,

        -- Signal 2a: Drop count (0-10)
        CASE
            WHEN COALESCE(pd.num_drops, 0) >= 4 THEN 10
            WHEN COALESCE(pd.num_drops, 0) >= 3 THEN 8
            WHEN COALESCE(pd.num_drops, 0) >= 2 THEN 5
            WHEN COALESCE(pd.num_drops, 0) >= 1 THEN 2
            ELSE 0
        END AS drop_count_score,

        -- Signal 2b: Drop magnitude (0-10)
        CASE
            WHEN pd.first_list_price IS NOT NULL AND p.list_price IS NOT NULL
                 AND pd.first_list_price > 0
                 AND (pd.first_list_price - p.list_price) / pd.first_list_price >= 0.15 THEN 10
            WHEN pd.first_list_price IS NOT NULL AND p.list_price IS NOT NULL
                 AND pd.first_list_price > 0
                 AND (pd.first_list_price - p.list_price) / pd.first_list_price >= 0.10 THEN 8
            WHEN pd.first_list_price IS NOT NULL AND p.list_price IS NOT NULL
                 AND pd.first_list_price > 0
                 AND (pd.first_list_price - p.list_price) / pd.first_list_price >= 0.05 THEN 5
            WHEN pd.first_list_price IS NOT NULL AND p.list_price IS NOT NULL
                 AND pd.first_list_price > 0
                 AND (pd.first_list_price - p.list_price) / pd.first_list_price >= 0.02 THEN 2
            ELSE 0
        END AS drop_magnitude_score,

        -- Signal 3: PPSF vs ZIP (0-15)
        CASE
            WHEN p.price_per_sqft IS NULL OR zb.median_ppsf IS NULL OR zb.median_ppsf = 0 THEN 0
            WHEN (zb.median_ppsf - p.price_per_sqft) / zb.median_ppsf >= 0.20 THEN 15
            WHEN (zb.median_ppsf - p.price_per_sqft) / zb.median_ppsf >= 0.15 THEN 12
            WHEN (zb.median_ppsf - p.price_per_sqft) / zb.median_ppsf >= 0.10 THEN 8
            WHEN (zb.median_ppsf - p.price_per_sqft) / zb.median_ppsf >= 0.05 THEN 4
            ELSE 0
        END AS ppsf_vs_zip_score,

        -- Signal 4: DOM vs market (0-12)
        CASE
            WHEN p.days_on_mls IS NULL OR mb.median_dom IS NULL OR mb.median_dom = 0 THEN 0
            WHEN p.days_on_mls::float / mb.median_dom >= 3.0 THEN 12
            WHEN p.days_on_mls::float / mb.median_dom >= 2.0 THEN 9
            WHEN p.days_on_mls::float / mb.median_dom >= 1.5 THEN 6
            WHEN p.days_on_mls::float / mb.median_dom >= 1.0 THEN 3
            ELSE 0
        END AS dom_score,

        -- Signal 5: Flip markup (0-10)
        CASE
            WHEN p.last_sold_price IS NULL OR p.list_price IS NULL OR p.last_sold_price = 0 THEN 0
            WHEN (p.list_price - p.last_sold_price) / p.last_sold_price >= 0.50 THEN 10
            WHEN (p.list_price - p.last_sold_price) / p.last_sold_price >= 0.30 THEN 6
            WHEN (p.list_price - p.last_sold_price) / p.last_sold_price <= 0.05 THEN 4
            ELSE 0
        END AS flip_markup_score,

        -- Signal 6: Sale-to-list ratio (0-8)
        CASE
            WHEN mb.avg_sale_to_list IS NULL THEN 0
            WHEN mb.avg_sale_to_list < 0.95 THEN 8
            WHEN mb.avg_sale_to_list < 0.97 THEN 5
            WHEN mb.avg_sale_to_list < 0.99 THEN 3
            ELSE 0
        END AS sale_to_list_score,

        -- Signal 7: Relist (0-5)
        CASE
            WHEN COALESCE(pd.num_listings, 0) > 1 AND pd.first_list_price > p.list_price THEN 5
            WHEN COALESCE(pd.num_listings, 0) > 1 THEN 2
            ELSE 0
        END AS relist_score,

        -- Signal 8: Description (0-5) — simplified SQL version
        CASE
            WHEN p.description ILIKE '%motivated seller%' THEN 3
            WHEN p.description ILIKE '%must sell%' THEN 3
            WHEN p.description ILIKE '%estate sale%' THEN 3
            WHEN p.description ILIKE '%probate%' THEN 3
            WHEN p.description ILIKE '%priced to sell%' THEN 3
            WHEN p.description ILIKE '%cash only%' THEN 3
            WHEN p.description ILIKE '%as-is%' OR p.description ILIKE '%as is%' THEN 3
            WHEN p.description ILIKE '%reo%' THEN 3
            WHEN p.description ILIKE '%investor%' THEN 2
            WHEN p.description ILIKE '%bring%offers%' THEN 2
            WHEN p.description ILIKE '%make it your own%' THEN 2
            WHEN p.description ILIKE '%vacant%' THEN 2
            WHEN p.description ILIKE '%cosmetic%' THEN 2
            WHEN p.description ILIKE '%price reduced%' THEN 1
            WHEN p.description ILIKE '%relocating%' THEN 1
            WHEN p.description ILIKE '%won''t last%' THEN 1
            ELSE 0
        END AS description_score,

        -- Context fields
        ROUND(((p.estimated_value - p.list_price) / NULLIF(p.list_price, 0) * 100)::numeric, 1) AS value_discount_pct,
        COALESCE(pd.num_drops, 0) AS num_price_drops,
        pd.first_list_price AS original_list_price,
        ROUND(((pd.first_list_price - p.list_price) / NULLIF(pd.first_list_price, 0) * 100)::numeric, 1) AS total_drop_pct,
        zb.median_ppsf AS zip_median_ppsf,
        mb.median_dom AS market_median_dom,
        mb.avg_sale_to_list AS market_sale_to_list

    FROM properties p
    LEFT JOIN zip_benchmarks zb ON zb.zip_code = p.zip_code
    LEFT JOIN market_benchmarks mb ON mb.region_name LIKE '%' || p.zip_code || '%'
    LEFT JOIN price_drop_agg pd ON pd.property_id = p.id
    WHERE p.list_price IS NOT NULL
      AND p.list_price > 0
)
SELECT
    *,
    (value_discount_score + drop_count_score + drop_magnitude_score
     + ppsf_vs_zip_score + dom_score + flip_markup_score
     + sale_to_list_score + relist_score + description_score) AS total_score,
    CASE
        WHEN (value_discount_score + drop_count_score + drop_magnitude_score
              + ppsf_vs_zip_score + dom_score + flip_markup_score
              + sale_to_list_score + relist_score + description_score) >= 75 THEN 'A'
        WHEN (value_discount_score + drop_count_score + drop_magnitude_score
              + ppsf_vs_zip_score + dom_score + flip_markup_score
              + sale_to_list_score + relist_score + description_score) >= 60 THEN 'B'
        WHEN (value_discount_score + drop_count_score + drop_magnitude_score
              + ppsf_vs_zip_score + dom_score + flip_markup_score
              + sale_to_list_score + relist_score + description_score) >= 45 THEN 'C'
        WHEN (value_discount_score + drop_count_score + drop_magnitude_score
              + ppsf_vs_zip_score + dom_score + flip_markup_score
              + sale_to_list_score + relist_score + description_score) >= 30 THEN 'D'
        ELSE 'F'
    END AS grade
FROM scored
ORDER BY (value_discount_score + drop_count_score + drop_magnitude_score
          + ppsf_vs_zip_score + dom_score + flip_markup_score
          + sale_to_list_score + relist_score + description_score) DESC;
