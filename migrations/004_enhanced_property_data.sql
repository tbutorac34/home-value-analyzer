-- Enhanced property data: new fields and photos table
-- Run in: https://supabase.com/dashboard/project/btwntyfjcendzmqwdoic/sql/new

ALTER TABLE properties ADD COLUMN IF NOT EXISTS redfin_estimate DOUBLE PRECISION;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS walk_score INTEGER;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS bike_score INTEGER;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS flood_risk TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS heating TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS cooling TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS construction_type TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS roof_type TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS foundation_type TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS sewer TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS water_source TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS appliances TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS laundry TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS school_rating DOUBLE PRECISION;

CREATE TABLE IF NOT EXISTS property_photos (
    id BIGSERIAL PRIMARY KEY,
    property_id BIGINT NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    position INTEGER,
    caption TEXT,
    room_type TEXT,
    condition_score DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(property_id, url)
);

CREATE INDEX IF NOT EXISTS idx_photos_property ON property_photos(property_id);
ALTER TABLE property_photos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON property_photos FOR ALL USING (true) WITH CHECK (true);
