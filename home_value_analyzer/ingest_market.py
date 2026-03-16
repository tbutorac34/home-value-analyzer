"""Ingest market-level statistics from Redfin Data Center TSV downloads."""

import io
from pathlib import Path

import click
import pandas as pd
import requests
from rich.console import Console

from .db import get_connection, init_db

console = Console()

# Redfin Data Center TSV URLs by region type
# These are the direct download links for housing market data
REDFIN_BASE = "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker"
REDFIN_URLS = {
    "zip": f"{REDFIN_BASE}/zip_code_market_tracker.tsv000.gz",
    "city": f"{REDFIN_BASE}/city_market_tracker.tsv000.gz",
    "county": f"{REDFIN_BASE}/county_market_tracker.tsv000.gz",
    "state": f"{REDFIN_BASE}/state_market_tracker.tsv000.gz",
    "national": f"{REDFIN_BASE}/us_national_market_tracker.tsv000.gz",
}

# Column mappings from Redfin TSV to our schema
REDFIN_COL_MAP = {
    "median_sale_price": "median_sale_price",
    "median_list_price": "median_list_price",
    "median_ppsf": "median_ppsf",
    "homes_sold": "homes_sold",
    "new_listings": "new_listings",
    "inventory": "active_listings",
    "months_of_supply": "months_of_supply",
    "median_dom": "median_dom",
    "avg_sale_to_list": "avg_sale_to_list",
    "off_market_in_two_weeks": None,  # skip
}


def download_redfin_data(region_type: str) -> pd.DataFrame:
    """Download Redfin market tracker TSV for a given region type."""
    url = REDFIN_URLS.get(region_type)
    if not url:
        raise ValueError(f"Unknown region type: {region_type}. Use: {list(REDFIN_URLS.keys())}")

    console.print(f"[bold]Downloading Redfin {region_type} data...[/bold]")
    console.print(f"  URL: {url}")
    console.print("  (This may take a minute for large files)")

    response = requests.get(url, timeout=300)
    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        sep="\t",
        compression="gzip",
    )

    console.print(f"[green]Downloaded {len(df)} rows[/green]")
    return df


def ingest_redfin_market(
    region_type: str,
    region_filter: str | None = None,
    property_type_filter: str = "All Residential",
) -> int:
    """Download and ingest Redfin market data, optionally filtered to a specific region.

    Returns the number of rows inserted.
    """
    init_db()
    df = download_redfin_data(region_type)

    # Filter to residential properties
    if "property_type" in df.columns:
        df = df[df["property_type"] == property_type_filter]

    # Determine region name column
    region_col = None
    for candidate in ["region", "region_name"]:
        if candidate in df.columns:
            region_col = candidate
            break

    if region_col is None:
        console.print("[red]Could not find region column in data[/red]")
        return 0

    # Apply region filter if specified
    if region_filter:
        mask = df[region_col].astype(str).str.contains(region_filter, case=False, na=False)
        df = df[mask]
        if df.empty:
            console.print(f"[yellow]No data found matching '{region_filter}'[/yellow]")
            return 0
        console.print(f"[green]Filtered to {len(df)} rows matching '{region_filter}'[/green]")

    conn = get_connection()
    inserted = 0

    for _, row in df.iterrows():
        region_name = str(row[region_col])
        period = str(row.get("period_end", row.get("month_date_yyyymm", "")))

        # Normalize period to YYYY-MM
        if len(period) >= 10:
            period = period[:7]  # "2024-01-31" -> "2024-01"
        elif len(period) == 6:
            period = f"{period[:4]}-{period[4:]}"  # "202401" -> "2024-01"

        def safe(col):
            val = row.get(col)
            if pd.isna(val):
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        def safe_int(col):
            val = row.get(col)
            if pd.isna(val):
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        try:
            conn.execute(
                """INSERT OR REPLACE INTO market_stats
                   (region_type, region_name, period, median_sale_price,
                    median_list_price, median_ppsf, homes_sold,
                    new_listings, active_listings, months_of_supply,
                    median_dom, avg_sale_to_list, pct_price_drops, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'redfin')""",
                (
                    region_type,
                    region_name,
                    period,
                    safe("median_sale_price"),
                    safe("median_list_price"),
                    safe("median_ppsf"),
                    safe_int("homes_sold"),
                    safe_int("new_listings"),
                    safe_int("inventory"),
                    safe("months_of_supply"),
                    safe_int("median_dom"),
                    safe("avg_sale_to_list"),
                    safe("price_drops"),
                ),
            )
            inserted += 1
        except Exception as e:
            console.print(f"[red]Error inserting row: {e}[/red]")
            continue

    conn.commit()
    conn.close()

    console.print(f"[bold green]Inserted {inserted} market stat rows[/bold green]")
    return inserted


@click.command()
@click.option(
    "--region-type",
    "-t",
    type=click.Choice(["zip", "city", "county", "state", "national"]),
    default="zip",
    help="Geographic level of data",
)
@click.option("--region", "-r", default=None, help="Filter to a specific region (e.g., ZIP code, city name)")
@click.option("--property-type", "-p", default="All Residential", help="Property type filter")
def main(region_type: str, region: str | None, property_type: str):
    """Download and ingest Redfin market-level statistics."""
    ingest_redfin_market(region_type, region, property_type)


if __name__ == "__main__":
    main()
