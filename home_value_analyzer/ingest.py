"""Ingest property listings using HomeHarvest."""

import click
import pandas as pd
from homeharvest import scrape_property
from rich.console import Console

from .db import get_connection, init_db

console = Console()


def _normalize_property_type(raw: str | None) -> str | None:
    if raw is None:
        return None
    mapping = {
        "SINGLE_FAMILY": "single_family",
        "CONDO": "condo",
        "TOWNHOUSE": "townhouse",
        "MULTI_FAMILY": "multi_family",
        "LAND": "land",
        "MOBILE": "mobile",
        "OTHER": "other",
    }
    return mapping.get(str(raw).upper(), str(raw).lower())


def _safe_int(val) -> int | None:
    if pd.isna(val):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_str(val) -> str | None:
    if pd.isna(val):
        return None
    return str(val)


def _col(df: pd.DataFrame, row_idx: int, col_name: str):
    """Safely get a column value, returning None if column doesn't exist."""
    if col_name in df.columns:
        return df.iloc[row_idx][col_name]
    return None


def ingest_listings(
    location: str,
    listing_type: str = "sold",
    past_days: int = 90,
    radius: float | None = None,
) -> int:
    """Scrape listings and store them in the database.

    Returns the number of new properties inserted.
    """
    init_db()

    console.print(
        f"[bold]Scraping {listing_type} listings for: {location}[/bold]"
    )
    console.print(f"  Past {past_days} days, radius={radius}")

    kwargs = {
        "location": location,
        "listing_type": listing_type,
        "past_days": past_days,
    }
    if radius is not None:
        kwargs["radius"] = radius

    df = scrape_property(**kwargs)

    if df.empty:
        console.print("[yellow]No listings found.[/yellow]")
        return 0

    console.print(f"[green]Found {len(df)} listings[/green]")

    conn = get_connection()
    inserted = 0
    updated = 0

    for i in range(len(df)):
        source = _safe_str(_col(df, i, "mls")) or "homeharvest"
        source_id = _safe_str(_col(df, i, "mls_id"))

        # Address - prefer formatted_address, fall back to constructed
        address = _safe_str(_col(df, i, "formatted_address"))
        if not address:
            street = _safe_str(_col(df, i, "street"))
            unit = _safe_str(_col(df, i, "unit"))
            parts = [p for p in [street, unit] if p]
            address = ", ".join(parts) if parts else "Unknown"

        city = _safe_str(_col(df, i, "city"))
        state = _safe_str(_col(df, i, "state"))
        zip_code = _safe_str(_col(df, i, "zip_code"))

        # Numeric fields
        sqft = _safe_int(_col(df, i, "sqft"))
        full_baths = _safe_int(_col(df, i, "full_baths"))
        half_baths = _safe_int(_col(df, i, "half_baths"))
        bathrooms_total = None
        if full_baths is not None:
            bathrooms_total = full_baths + (0.5 * (half_baths or 0))

        sold_price = _safe_float(_col(df, i, "sold_price"))
        list_price = _safe_float(_col(df, i, "list_price"))

        # Compute price per sqft
        price = sold_price or list_price
        price_per_sqft = round(price / sqft, 2) if price and sqft else None

        # Compute list-to-sale ratio
        list_to_sale = None
        if sold_price and list_price and list_price > 0:
            list_to_sale = round(sold_price / list_price, 4)

        # Photos - convert list/complex types to strings
        alt_photos = _col(df, i, "alt_photos")
        if alt_photos is not None and not isinstance(alt_photos, str):
            alt_photos = str(alt_photos)

        agent_phones = _col(df, i, "agent_phones")
        if agent_phones is not None and not isinstance(agent_phones, str):
            agent_phones = str(agent_phones)

        try:
            # Try insert first
            cursor = conn.execute(
                """INSERT OR IGNORE INTO properties
                   (source, source_id, property_id, listing_id, property_url, permalink,
                    address, street, unit, city, state, zip_code, county, fips_code,
                    latitude, longitude,
                    property_type, year_built, sqft, lot_sqft,
                    bedrooms, full_baths, half_baths, bathrooms_total,
                    stories, garage_spaces, hoa_fee, new_construction,
                    estimated_value, assessed_value, annual_tax,
                    status, mls_status,
                    list_price, list_price_min, list_price_max, sold_price,
                    list_date, sold_date, pending_date, days_on_mls,
                    price_per_sqft, list_to_sale_ratio,
                    last_sold_date, last_sold_price,
                    last_status_change_date, last_update_date,
                    agent_name, agent_email, agent_phones, broker_name, office_name,
                    primary_photo, alt_photos,
                    description)
                   VALUES (?,?,?,?,?,?, ?,?,?,?,?,?,?,?, ?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?,?, ?,?, ?,?,?,?, ?,?,?,?, ?,?, ?,?, ?,?, ?,?,?,?,?, ?,?, ?)""",
                (
                    source,
                    source_id,
                    _safe_str(_col(df, i, "property_id")),
                    _safe_str(_col(df, i, "listing_id")),
                    _safe_str(_col(df, i, "property_url")),
                    _safe_str(_col(df, i, "permalink")),
                    address,
                    _safe_str(_col(df, i, "street")),
                    _safe_str(_col(df, i, "unit")),
                    city,
                    state,
                    zip_code,
                    _safe_str(_col(df, i, "county")),
                    _safe_str(_col(df, i, "fips_code")),
                    _safe_float(_col(df, i, "latitude")),
                    _safe_float(_col(df, i, "longitude")),
                    _normalize_property_type(_safe_str(_col(df, i, "style"))),
                    _safe_int(_col(df, i, "year_built")),
                    sqft,
                    _safe_int(_col(df, i, "lot_sqft")),
                    _safe_int(_col(df, i, "beds")),
                    full_baths,
                    half_baths,
                    bathrooms_total,
                    _safe_int(_col(df, i, "stories")),
                    _safe_int(_col(df, i, "parking_garage")),
                    _safe_float(_col(df, i, "hoa_fee")),
                    1 if _col(df, i, "new_construction") is True else 0,
                    _safe_float(_col(df, i, "estimated_value")),
                    _safe_float(_col(df, i, "assessed_value")),
                    _safe_float(_col(df, i, "tax")),
                    _safe_str(_col(df, i, "status")),
                    _safe_str(_col(df, i, "mls_status")),
                    list_price,
                    _safe_float(_col(df, i, "list_price_min")),
                    _safe_float(_col(df, i, "list_price_max")),
                    sold_price,
                    _safe_str(_col(df, i, "list_date")),
                    _safe_str(_col(df, i, "sold_date")),
                    _safe_str(_col(df, i, "pending_date")),
                    _safe_int(_col(df, i, "days_on_mls")),
                    price_per_sqft,
                    list_to_sale,
                    _safe_str(_col(df, i, "last_sold_date")),
                    _safe_float(_col(df, i, "last_sold_price")),
                    _safe_str(_col(df, i, "last_status_change_date")),
                    _safe_str(_col(df, i, "last_update_date")),
                    _safe_str(_col(df, i, "agent_name")),
                    _safe_str(_col(df, i, "agent_email")),
                    agent_phones,
                    _safe_str(_col(df, i, "broker_name")),
                    _safe_str(_col(df, i, "office_name")),
                    _safe_str(_col(df, i, "primary_photo")),
                    alt_photos,
                    _safe_str(_col(df, i, "text")),
                ),
            )

            if cursor.rowcount > 0:
                inserted += 1
            else:
                # Property already exists - update with latest data
                conn.execute(
                    """UPDATE properties SET
                        status=?, mls_status=?, list_price=?, sold_price=?,
                        sold_date=?, pending_date=?, days_on_mls=?,
                        price_per_sqft=?, list_to_sale_ratio=?,
                        estimated_value=COALESCE(?, estimated_value),
                        last_status_change_date=?, last_update_date=?,
                        updated_at=CURRENT_TIMESTAMP
                       WHERE source=? AND source_id=?""",
                    (
                        _safe_str(_col(df, i, "status")),
                        _safe_str(_col(df, i, "mls_status")),
                        list_price,
                        sold_price,
                        _safe_str(_col(df, i, "sold_date")),
                        _safe_str(_col(df, i, "pending_date")),
                        _safe_int(_col(df, i, "days_on_mls")),
                        price_per_sqft,
                        list_to_sale,
                        _safe_float(_col(df, i, "estimated_value")),
                        _safe_str(_col(df, i, "last_status_change_date")),
                        _safe_str(_col(df, i, "last_update_date")),
                        source,
                        source_id,
                    ),
                )
                updated += 1

        except Exception as e:
            console.print(f"[red]Error inserting row {i}: {e}[/red]")
            continue

    conn.commit()
    conn.close()

    console.print(f"[bold green]Inserted {inserted} new, updated {updated} existing properties[/bold green]")
    return inserted


@click.command()
@click.option("--location", "-l", required=True, help="City, ZIP, or address to search")
@click.option(
    "--listing-type",
    "-t",
    type=click.Choice(["sold", "for_sale", "for_rent", "pending"]),
    default="sold",
    help="Type of listings to fetch",
)
@click.option("--past-days", "-d", default=90, help="Number of days to look back")
@click.option("--radius", "-r", default=None, type=float, help="Search radius in miles")
def main(location: str, listing_type: str, past_days: int, radius: float | None):
    """Ingest property listings from Zillow, Redfin, and Realtor.com."""
    ingest_listings(location, listing_type, past_days, radius)


if __name__ == "__main__":
    main()
