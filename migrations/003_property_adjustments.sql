-- Property Adjustments System
-- Run in: https://supabase.com/dashboard/project/btwntyfjcendzmqwdoic/sql/new

-- Features and conditions not captured in standard listing data
CREATE TABLE IF NOT EXISTS property_adjustments (
    id BIGSERIAL PRIMARY KEY,
    property_id BIGINT NOT NULL REFERENCES properties(id) ON DELETE CASCADE,

    -- Source tracking
    source TEXT NOT NULL DEFAULT 'manual',  -- 'manual', 'nlp_extracted', 'photo_ai'
    confidence DOUBLE PRECISION DEFAULT 1.0,  -- 1.0 for manual, 0.0-1.0 for auto
    notes TEXT,

    -- Basement
    basement_finished BOOLEAN,
    basement_finished_sqft INTEGER,
    basement_type TEXT,  -- 'full_finished', 'partial_finished', 'unfinished', 'none', 'crawl'

    -- Kitchen
    kitchen_updated BOOLEAN,
    kitchen_remodel_year INTEGER,
    kitchen_quality TEXT,  -- 'luxury', 'major', 'minor', 'original'
    countertop_material TEXT,  -- 'granite', 'quartz', 'marble', 'laminate', 'butcher_block'

    -- Bathrooms
    bathroom_updated BOOLEAN,
    bathroom_remodel_year INTEGER,
    bathroom_quality TEXT,  -- 'luxury', 'major', 'minor', 'original'
    bathroom_remodel_count INTEGER,

    -- Major systems
    roof_year INTEGER,
    hvac_year INTEGER,
    windows_year INTEGER,
    water_heater_year INTEGER,
    electrical_updated BOOLEAN,
    plumbing_updated BOOLEAN,

    -- Interior features
    flooring_type TEXT,  -- 'hardwood', 'lvp', 'carpet', 'tile', 'mixed'
    open_floor_plan BOOLEAN,
    fireplace BOOLEAN,
    fireplace_type TEXT,  -- 'gas', 'wood', 'electric'

    -- Garage (supplements existing garage_spaces)
    garage_type TEXT,  -- 'attached', 'detached', 'none'
    garage_heated BOOLEAN,

    -- Exterior / lot
    pool BOOLEAN,
    pool_type TEXT,  -- 'inground', 'above_ground'
    fence BOOLEAN,
    fence_type TEXT,  -- 'privacy', 'chain_link', 'vinyl', 'wrought_iron'
    deck_patio BOOLEAN,
    sprinkler_system BOOLEAN,

    -- Lot characteristics
    lot_type TEXT,  -- 'standard', 'corner', 'cul_de_sac'
    lot_backs_to TEXT,  -- 'woods', 'open_space', 'busy_road', 'commercial', 'neighbors', 'water'

    -- Condition
    overall_condition TEXT,  -- 'excellent', 'good', 'average', 'fair', 'poor'
    move_in_ready BOOLEAN,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(property_id)
);

-- Configurable dollar values per market area
CREATE TABLE IF NOT EXISTS adjustment_values (
    id BIGSERIAL PRIMARY KEY,
    market_area TEXT NOT NULL DEFAULT 'macomb_county',
    adjustment_key TEXT NOT NULL,
    adjustment_dollars DOUBLE PRECISION NOT NULL,
    min_dollars DOUBLE PRECISION,
    max_dollars DOUBLE PRECISION,
    depreciation_rate DOUBLE PRECISION DEFAULT 0.0,  -- annual rate for time-sensitive items
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(market_area, adjustment_key)
);

-- Seed Macomb County adjustment values
INSERT INTO adjustment_values (market_area, adjustment_key, adjustment_dollars, min_dollars, max_dollars, depreciation_rate, notes) VALUES
    ('macomb_county', 'basement_full_finished',    25000, 20000, 35000, 0.0,  'Fully finished basement'),
    ('macomb_county', 'basement_partial_finished', 15000, 10000, 20000, 0.0,  'Partially finished basement'),
    ('macomb_county', 'kitchen_luxury',            25000, 20000, 35000, 0.03, 'Full luxury kitchen remodel'),
    ('macomb_county', 'kitchen_major',             18000, 12000, 25000, 0.03, 'Major kitchen remodel'),
    ('macomb_county', 'kitchen_minor',              8000,  5000, 12000, 0.05, 'Minor kitchen update'),
    ('macomb_county', 'bathroom_major',             6000,  4000,  8000, 0.03, 'Per bathroom - major remodel'),
    ('macomb_county', 'bathroom_minor',             3000,  2000,  5000, 0.05, 'Per bathroom - minor update'),
    ('macomb_county', 'roof_new',                   6000,  3000,  8000, 0.10, 'New roof - depreciates ~10%/yr'),
    ('macomb_county', 'hvac_new',                   5000,  3000,  6000, 0.08, 'New furnace + AC'),
    ('macomb_county', 'windows_new',                7000,  5000, 10000, 0.05, 'All windows replaced'),
    ('macomb_county', 'hardwood_floors',            5000,  3000,  8000, 0.0,  'Hardwood vs carpet'),
    ('macomb_county', 'lvp_flooring',               3000,  2000,  5000, 0.0,  'LVP vs carpet'),
    ('macomb_county', 'garage_3car',               20000, 15000, 25000, 0.0,  '3-car vs 2-car garage'),
    ('macomb_county', 'garage_attached',           10000,  8000, 12000, 0.0,  'Attached vs detached'),
    ('macomb_county', 'garage_none',              -25000,-30000,-20000, 0.0,  'No garage penalty'),
    ('macomb_county', 'pool_inground',             10000,  5000, 15000, 0.0,  'In-ground pool'),
    ('macomb_county', 'fence_privacy',              3500,  2000,  5000, 0.0,  'Privacy fence'),
    ('macomb_county', 'lot_backs_woods',           10000,  5000, 15000, 0.0,  'Backs to wooded area'),
    ('macomb_county', 'lot_backs_busy_road',      -15000,-20000,-10000, 0.0,  'Backs to busy road'),
    ('macomb_county', 'lot_cul_de_sac',             5000,  3000,  8000, 0.0,  'Cul-de-sac premium'),
    ('macomb_county', 'open_floor_plan',            5000,  3000,  7000, 0.0,  'Open vs closed layout'),
    ('macomb_county', 'fireplace_gas',              2000,  1500,  3000, 0.0,  'Gas fireplace'),
    ('macomb_county', 'electrical_updated',         3000,  2000,  4000, 0.0,  'Updated panel/wiring'),
    ('macomb_county', 'plumbing_updated',           3000,  2000,  4000, 0.0,  'Updated plumbing'),
    ('macomb_county', 'sprinkler_system',           2000,  1000,  3000, 0.0,  'Lawn sprinkler system'),
    ('macomb_county', 'countertop_granite',         4000,  3000,  6000, 0.0,  'Granite countertops'),
    ('macomb_county', 'countertop_quartz',          5000,  3000,  7000, 0.0,  'Quartz countertops'),
    ('macomb_county', 'water_heater_new',           1500,  1000,  2000, 0.10, 'New water heater')
ON CONFLICT (market_area, adjustment_key) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_adjustments_property ON property_adjustments(property_id);

ALTER TABLE property_adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE adjustment_values ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON property_adjustments FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON adjustment_values FOR ALL USING (true) WITH CHECK (true);
