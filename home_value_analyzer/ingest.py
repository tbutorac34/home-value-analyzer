"""Ingest property listings using HomeHarvest."""

import click
import pandas as pd
from homeharvest import scrape_property
from rich.console import Console
from rich.table import Table

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

    for i in range(len(df)):
        source = _safe_str(_col(df, i, "mls")) or "homeharvest"
        source_id = _safe_str(_col(df, i, "mls_id"))

        # Build full address
        street = _safe_str(_col(df, i, "street"))
        unit = _safe_str(_col(df, i, "unit"))
        city = _safe_str(_col(df, i, "city"))
        state = _safe_str(_col(df, i, "state"))
        zip_code = _safe_str(_col(df, i, "zip_code"))

        address_parts = [p for p in [street, unit] if p]
        address = ", ".join(address_parts) if address_parts else "Unknown"

        sqft = _safe_int(_col(df, i, "sqft"))
        sold_price = _safe_float(_col(df, i, "sold_price"))
        list_price = _safe_float(_col(df, i, "list_price"))

        # Compute price per sqft
        price = sold_price or list_price
        price_per_sqft = round(price / sqft, 2) if price and sqft else None

        # Compute list-to-sale ratio
        list_to_sale = None
        if sold_price and list_price and list_price > 0:
            list_to_sale = round(sold_price / list_price, 4)

        try:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO properties
                   (source, source_id, address, city, state, zip_code,
                    latitude, longitude, property_type, year_built,
                    sqft, lot_sqft, bedrooms, bathrooms, stories,
                    garage_spaces, hoa_fee, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source,
                    source_id,
                    address,
                    city,
                    state,
                    zip_code,
                    _safe_float(_col(df, i, "latitude")),
                    _safe_float(_col(df, i, "longitude")),
                    _normalize_property_type(_safe_str(_col(df, i, "style"))),
                    _safe_int(_col(df, i, "year_built")),
                    sqft,
                    _safe_int(_col(df, i, "lot_sqft")),
                    _safe_int(_col(df, i, "beds")),
                    _safe_float(_col(df, i, "full_baths")),
                    _safe_int(_col(df, i, "stories")),
                    _safe_int(_col(df, i, "garage")),
                    _safe_float(_col(df, i, "hoa_fee")),
                    _safe_str(_col(df, i, "description")),
                ),
            )

            if cursor.lastrowid and cursor.rowcount > 0:
                property_id = cursor.lastrowid
                inserted += 1
            else:
                # Property already exists, get its ID
                row = conn.execute(
                    "SELECT id FROM properties WHERE source=? AND source_id=?",
                    (source, source_id),
                ).fetchone()
                property_id = row["id"] if row else None

            if property_id:
                conn.execute(
                    """INSERT OR IGNORE INTO sales
                       (property_id, listing_type, list_price, sold_price,
                        list_date, sold_date, days_on_market,
                        price_per_sqft, list_to_sale_ratio, source_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        property_id,
                        listing_type,
                        list_price,
                        sold_price,
                        _safe_str(_col(df, i, "list_date")),
                        _safe_str(_col(df, i, "sold_date")),
                        _safe_int(_col(df, i, "days_on_mls")),
                        price_per_sqft,
                        list_to_sale,
                        _safe_str(_col(df, i, "property_url")),
                    ),
                )

        except Exception as e:
            console.print(f"[red]Error inserting row {i}: {e}[/red]")
            continue

    conn.commit()
    conn.close()

    console.print(f"[bold green]Inserted {inserted} new properties[/bold green]")
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
