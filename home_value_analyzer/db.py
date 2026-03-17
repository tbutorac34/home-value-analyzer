"""Database access layer. Supports both local SQLite and Supabase."""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "home_values.db"


def _load_env():
    """Load .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass


def get_supabase():
    """Get a Supabase client, or None if not configured."""
    _load_env()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if url and key:
        try:
            from supabase import create_client
            return create_client(url, key)
        except ImportError:
            pass
    return None


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create SQLite tables if they don't exist (for local fallback)."""
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    latitude REAL,
    longitude REAL,
    property_type TEXT,
    year_built INTEGER,
    sqft INTEGER,
    lot_sqft INTEGER,
    bedrooms INTEGER,
    full_baths INTEGER,
    half_baths INTEGER,
    bathrooms_total REAL,
    stories INTEGER,
    garage_spaces INTEGER,
    hoa_fee REAL,
    new_construction INTEGER,
    estimated_value REAL,
    assessed_value REAL,
    annual_tax REAL,
    status TEXT,
    mls_status TEXT,
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
    last_sold_date TEXT,
    last_sold_price REAL,
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
    redfin_estimate REAL,
    walk_score INTEGER,
    bike_score INTEGER,
    flood_risk TEXT,
    heating TEXT,
    cooling TEXT,
    construction_type TEXT,
    roof_type TEXT,
    foundation_type TEXT,
    sewer TEXT,
    water_source TEXT,
    appliances TEXT,
    laundry TEXT,
    school_rating REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS property_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    url TEXT NOT NULL,
    position INTEGER,
    caption TEXT,
    room_type TEXT,
    condition_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, url)
);

CREATE INDEX IF NOT EXISTS idx_photos_property ON property_photos(property_id);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL REFERENCES properties(id),
    date TEXT NOT NULL,
    event TEXT,
    price REAL,
    price_change REAL,
    price_change_pct REAL,
    source TEXT,
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
    region_type TEXT NOT NULL,
    region_name TEXT NOT NULL,
    period TEXT NOT NULL,
    median_sale_price REAL,
    median_list_price REAL,
    median_ppsf REAL,
    homes_sold INTEGER,
    new_listings INTEGER,
    active_listings INTEGER,
    months_of_supply REAL,
    median_dom INTEGER,
    avg_sale_to_list REAL,
    pct_price_drops REAL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(region_type, region_name, period, source)
);

CREATE INDEX IF NOT EXISTS idx_properties_zip ON properties(zip_code);
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city, state);
CREATE INDEX IF NOT EXISTS idx_price_history_property ON price_history(property_id);
CREATE INDEX IF NOT EXISTS idx_tax_history_property ON tax_history(property_id);
CREATE INDEX IF NOT EXISTS idx_market_stats_region ON market_stats(region_type, region_name);
"""
