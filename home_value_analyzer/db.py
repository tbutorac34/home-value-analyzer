"""Database setup and access layer using SQLite."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "home_values.db"


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create all tables if they don't exist."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identifiers
    source TEXT NOT NULL,              -- MLS name (e.g., 'DEMI') or 'homeharvest'
    source_id TEXT,                    -- mls_id from source
    property_id TEXT,                  -- realtor.com property_id
    listing_id TEXT,                   -- realtor.com listing_id
    property_url TEXT,                 -- full URL to listing
    permalink TEXT,                    -- realtor.com permalink slug

    -- Address
    address TEXT NOT NULL,             -- formatted_address or constructed
    street TEXT,                       -- street line only
    unit TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    county TEXT,
    fips_code TEXT,
    latitude REAL,
    longitude REAL,

    -- Property details
    property_type TEXT,                -- 'single_family', 'condo', 'townhouse', etc.
    year_built INTEGER,
    sqft INTEGER,
    lot_sqft INTEGER,
    bedrooms INTEGER,
    full_baths INTEGER,
    half_baths INTEGER,
    bathrooms_total REAL,              -- computed: full_baths + 0.5 * half_baths
    stories INTEGER,
    garage_spaces INTEGER,
    hoa_fee REAL,
    new_construction INTEGER,          -- 0/1

    -- Estimated / assessed values
    estimated_value REAL,              -- AVM estimate from source
    assessed_value REAL,
    annual_tax REAL,

    -- Listing status
    status TEXT,                       -- 'FOR_SALE', 'SOLD', 'PENDING', etc.
    mls_status TEXT,                   -- human-readable status

    -- Listing details
    list_price REAL,
    list_price_min REAL,
    list_price_max REAL,
    sold_price REAL,
    list_date TEXT,
    sold_date TEXT,
    pending_date TEXT,
    days_on_mls INTEGER,
    price_per_sqft REAL,
    list_to_sale_ratio REAL,

    -- Previous sale
    last_sold_date TEXT,
    last_sold_price REAL,

    -- Dates
    last_status_change_date TEXT,
    last_update_date TEXT,

    -- Agent / broker info
    agent_name TEXT,
    agent_email TEXT,
    agent_phones TEXT,                 -- JSON string
    broker_name TEXT,
    office_name TEXT,

    -- Media
    primary_photo TEXT,                -- URL
    alt_photos TEXT,                   -- URL(s)

    -- Full text
    description TEXT,                  -- full listing description

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    date TEXT NOT NULL,
    event TEXT,                        -- 'listed', 'price_change', 'pending', 'sold', 'relisted'
    price REAL,
    price_change REAL,                 -- dollar change from previous
    price_change_pct REAL,             -- percent change from previous
    source TEXT,                       -- 'zillow', 'redfin', 'realtor'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, date, event)
);

CREATE TABLE IF NOT EXISTS tax_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    year INTEGER NOT NULL,
    tax_paid REAL,
    assessed_value REAL,
    land_value REAL,
    improvement_value REAL,
    tax_increase_rate REAL,
    value_increase_rate REAL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, year)
);

CREATE TABLE IF NOT EXISTS market_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_type TEXT NOT NULL,         -- 'zip', 'city', 'county', 'metro'
    region_name TEXT NOT NULL,
    period TEXT NOT NULL,              -- 'YYYY-MM' or 'YYYY-WW'
    median_sale_price REAL,
    median_list_price REAL,
    median_ppsf REAL,                 -- price per sqft
    homes_sold INTEGER,
    new_listings INTEGER,
    active_listings INTEGER,
    months_of_supply REAL,
    median_dom INTEGER,               -- days on market
    avg_sale_to_list REAL,            -- ratio
    pct_price_drops REAL,
    source TEXT,                       -- 'redfin', 'fred', 'fhfa'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(region_type, region_name, period, source)
);

CREATE INDEX IF NOT EXISTS idx_properties_zip ON properties(zip_code);
CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city, state);
CREATE INDEX IF NOT EXISTS idx_properties_location ON properties(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
CREATE INDEX IF NOT EXISTS idx_price_history_property ON price_history(property_id);
CREATE INDEX IF NOT EXISTS idx_tax_history_property ON tax_history(property_id);
CREATE INDEX IF NOT EXISTS idx_market_stats_region ON market_stats(region_type, region_name);
"""
