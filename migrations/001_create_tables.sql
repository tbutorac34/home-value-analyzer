-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/btwntyfjcendzmqwdoic/sql/new

CREATE TABLE IF NOT EXISTS properties (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    property_id TEXT,
    listing_id TEXT,
    property_url TEXT,
    permalink TEXT,
    address TEXT NOT NULL,
    street TEXT,
    unit TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    county TEXT,
    fips_code TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    property_type TEXT,
    year_built INTEGER,
    sqft INTEGER,
    lot_sqft INTEGER,
    bedrooms INTEGER,
    full_baths INTEGER,
    half_baths INTEGER,
    bathrooms_total DOUBLE PRECISION,
    stories INTEGER,
    garage_spaces INTEGER,
    hoa_fee DOUBLE PRECISION,
    new_construction BOOLEAN DEFAULT FALSE,
    estimated_value DOUBLE PRECISION,
    assessed_value DOUBLE PRECISION,
    annual_tax DOUBLE PRECISION,
    status TEXT,
    mls_status TEXT,
    list_price DOUBLE PRECISION,
    list_price_min DOUBLE PRECISION,
    list_price_max DOUBLE PRECISION,
    sold_price DOUBLE PRECISION,
    list_date TEXT,
    sold_date TEXT,
    pending_date TEXT,
    days_on_mls INTEGER,
    price_per_sqft DOUBLE PRECISION,
    list_to_sale_ratio DOUBLE PRECISION,
    last_sold_date TEXT,
    last_sold_price DOUBLE PRECISION,
    last_status_change_date TEXT,
    last_update_date TEXT,
    agent_name TEXT,
    agent_email TEXT,
    agent_phones TEXT,
    broker_name TEXT,
    office_name TEXT,
    primary_photo TEXT,
    alt_photos TEXT,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    property_id BIGINT NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    event TEXT,
    price DOUBLE PRECISION,
    price_change DOUBLE PRECISION,
    price_change_pct DOUBLE PRECISION,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(property_id, date, event)
);

CREATE TABLE IF NOT EXISTS tax_history (
    id BIGSERIAL PRIMARY KEY,
    property_id BIGINT NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    tax_paid DOUBLE PRECISION,
    assessed_value DOUBLE PRECISION,
    land_value DOUBLE PRECISION,
    improvement_value DOUBLE PRECISION,
    tax_increase_rate DOUBLE PRECISION,
    value_increase_rate DOUBLE PRECISION,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(property_id, year)
);

CREATE TABLE IF NOT EXISTS market_stats (
    id BIGSERIAL PRIMARY KEY,
    region_type TEXT NOT NULL,
    region_name TEXT NOT NULL,
    period TEXT NOT NULL,
    median_sale_price DOUBLE PRECISION,
    median_list_price DOUBLE PRECISION,
    median_ppsf DOUBLE PRECISION,
    homes_sold INTEGER,
    new_listings INTEGER,
    active_listings INTEGER,
    months_of_supply DOUBLE PRECISION,
    median_dom INTEGER,
    avg_sale_to_list DOUBLE PRECISION,
    pct_price_drops DOUBLE PRECISION,
    source TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(region_type, region_name, period, source)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_properties_zip ON properties(zip_code);
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city, state);
CREATE INDEX IF NOT EXISTS idx_price_history_property ON price_history(property_id);
CREATE INDEX IF NOT EXISTS idx_tax_history_property ON tax_history(property_id);
CREATE INDEX IF NOT EXISTS idx_market_stats_region ON market_stats(region_type, region_name);

-- Enable Row Level Security (required by Supabase, but allow all for service_role)
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_stats ENABLE ROW LEVEL SECURITY;

-- Policies to allow service_role full access
CREATE POLICY "service_role_all" ON properties FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON price_history FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON tax_history FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON market_stats FOR ALL USING (true) WITH CHECK (true);
