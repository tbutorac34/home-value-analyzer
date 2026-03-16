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
    source TEXT NOT NULL,              -- 'zillow', 'redfin', 'realtor'
    source_id TEXT,                    -- listing ID from source
    address TEXT NOT NULL,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    county TEXT,
    latitude REAL,
    longitude REAL,
    property_type TEXT,                -- 'single_family', 'condo', 'townhouse', etc.
    year_built INTEGER,
    sqft INTEGER,
    lot_sqft INTEGER,
    bedrooms INTEGER,
    bathrooms REAL,
    stories INTEGER,
    garage_spaces INTEGER,
    has_pool INTEGER,                  -- 0/1
    hoa_fee REAL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    listing_type TEXT NOT NULL,        -- 'for_sale', 'sold', 'pending'
    list_price REAL,
    sold_price REAL,
    list_date TEXT,
    sold_date TEXT,
    days_on_market INTEGER,
    price_per_sqft REAL,
    list_to_sale_ratio REAL,
    agent_name TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, listing_type, list_date)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    date TEXT NOT NULL,
    event TEXT,                        -- 'listed', 'price_change', 'pending', 'sold'
    price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    tax_year INTEGER,
    assessed_value REAL,
    land_value REAL,
    improvement_value REAL,
    tax_amount REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, tax_year)
);

CREATE INDEX IF NOT EXISTS idx_properties_zip ON properties(zip_code);
CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city, state);
CREATE INDEX IF NOT EXISTS idx_properties_location ON properties(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_sales_sold_date ON sales(sold_date);
CREATE INDEX IF NOT EXISTS idx_sales_listing_type ON sales(listing_type);
CREATE INDEX IF NOT EXISTS idx_market_stats_region ON market_stats(region_type, region_name);
"""
