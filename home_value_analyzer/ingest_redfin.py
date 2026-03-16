"""Ingest property-level data from Redfin's CSV download API.

Redfin allows downloading up to 350 listings per search as CSV.
This supplements HomeHarvest with Redfin-specific data.
"""

import csv
import io
import re

import click
import requests
from rich.console import Console

from .db import get_connection, init_db

console = Console()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def _find_redfin_region_id(zip_code: str) -> int | None:
    """Find Redfin's internal region ID for a ZIP code."""
    url = f"https://www.redfin.com/zipcode/{zip_code}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        # Find region_id in the page (look for the non-zip one)
        matches = re.findall(r'region_id[=:](\d+)', resp.text)
        for m in matches:
            if m != zip_code:
                return int(m)
        # If all matches are the zip code itself, try JSON format
        json_matches = re.findall(r'"regionId":(\d+)', resp.text)
        for m in json_matches:
            if m != zip_code:
                return int(m)
    except Exception:
        pass
    return None


def download_redfin_csv(
    region_id: int,
    status: str = "sold",
    days: int = 180,
    num_homes: int = 350,
) -> list[dict]:
    """Download property data from Redfin's CSV API."""
    status_map = {"sold": 9, "for_sale": 1, "pending": 2}
    status_code = status_map.get(status, 9)

    params = {
        "al": 1,
        "region_id": region_id,
        "region_type": 2,
        "sold_within_days": days if status == "sold" else "",
        "status": status_code,
        "uipt": "1,2,3,4,5,6,7,8",
        "v": 8,
        "num_homes": num_homes,
    }

    resp = requests.get(
        "https://www.redfin.com/stingray/api/gis-csv",
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()

    # Filter out disclaimer lines
    lines = [
        l for l in resp.text.split("\n")
        if l and not l.startswith('"In accordance')
    ]

    if len(lines) < 2:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    return list(reader)


def _safe_int(val: str | None) -> int | None:
    if not val:
        return None
    try:
        return int(float(val.replace(",", "")))
    except (ValueError, TypeError):
        return None


def _safe_float(val: str | None) -> float | None:
    if not val:
        return None
    try:
        return float(val.replace(",", "").replace("$", ""))
    except (ValueError, TypeError):
        return None


def ingest_redfin_listings(
    zip_code: str,
    status: str = "sold",
    days: int = 180,
) -> int:
    """Download and ingest Redfin listings for a ZIP code."""
    init_db()

    console.print(f"[bold]Finding Redfin region ID for {zip_code}...[/bold]")
    region_id = _find_redfin_region_id(zip_code)
    if not region_id:
        console.print(f"[red]Could not find Redfin region ID for {zip_code}[/red]")
        return 0

    console.print(f"  Region ID: {region_id}")
    console.print(f"[bold]Downloading {status} listings from Redfin...[/bold]")

    rows = download_redfin_csv(region_id, status, days)
    if not rows:
        console.print("[yellow]No listings found[/yellow]")
        return 0

    console.print(f"[green]Downloaded {len(rows)} listings[/green]")

    conn = get_connection()
    inserted = 0
    updated = 0

    for row in rows:
        address = row.get("ADDRESS", "").strip()
        if not address:
            continue

        city = row.get("CITY", "").strip()
        state = row.get("STATE OR PROVINCE", "").strip()
        zip_code_val = row.get("ZIP OR POSTAL CODE", "").strip()
        redfin_url = ""
        for key in row:
            if "URL" in key:
                redfin_url = row[key].strip()
                break

        # Extract Redfin home ID from URL for dedup
        source_id = None
        if "/home/" in redfin_url:
            source_id = redfin_url.split("/home/")[-1].strip("/")

        price = _safe_float(row.get("PRICE"))
        sqft = _safe_int(row.get("SQUARE FEET"))
        price_per_sqft = _safe_float(row.get("$/SQUARE FEET"))

        sold_date = row.get("SOLD DATE", "").strip() or None
        status_val = "SOLD" if status == "sold" else "FOR_SALE" if status == "for_sale" else "PENDING"

        property_type_map = {
            "Single Family Residential": "single_family",
            "Condo/Co-op": "condo",
            "Townhouse": "townhouse",
            "Multi-Family (2-4 Unit)": "multi_family",
            "Mobile/Manufactured Home": "mobile",
        }
        raw_type = row.get("PROPERTY TYPE", "").strip()
        property_type = property_type_map.get(raw_type, raw_type.lower() if raw_type else None)

        formatted_address = f"{address}, {city}, {state}, {zip_code_val}".strip(", ")

        try:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO properties
                   (source, source_id, property_url,
                    address, street, city, state, zip_code,
                    latitude, longitude,
                    property_type, year_built, sqft, lot_sqft,
                    bedrooms, full_baths, bathrooms_total,
                    hoa_fee,
                    status, mls_status,
                    list_price, sold_price, sold_date,
                    days_on_mls, price_per_sqft)
                   VALUES (?,?,?, ?,?,?,?,?, ?,?, ?,?,?,?, ?,?,?, ?, ?,?, ?,?,?, ?,?)""",
                (
                    "redfin",
                    source_id,
                    redfin_url,
                    formatted_address,
                    address,
                    city,
                    state,
                    zip_code_val,
                    _safe_float(row.get("LATITUDE")),
                    _safe_float(row.get("LONGITUDE")),
                    property_type,
                    _safe_int(row.get("YEAR BUILT")),
                    sqft,
                    _safe_int(row.get("LOT SIZE")),
                    _safe_int(row.get("BEDS")),
                    _safe_int(row.get("BATHS")),
                    _safe_float(row.get("BATHS")),
                    _safe_float(row.get("HOA/MONTH")),
                    status_val,
                    row.get("STATUS", "").strip() or None,
                    price if status != "sold" else None,
                    price if status == "sold" else None,
                    sold_date,
                    _safe_int(row.get("DAYS ON MARKET")),
                    price_per_sqft,
                ),
            )

            if cursor.rowcount > 0:
                inserted += 1
            else:
                updated += 1

        except Exception as e:
            console.print(f"[red]Error inserting {address}: {e}[/red]")

    conn.commit()
    conn.close()

    console.print(f"[bold green]Inserted {inserted} new, {updated} already existed[/bold green]")
    return inserted


@click.command()
@click.option("--zip", "zip_code", required=True, help="ZIP code to download")
@click.option(
    "--status", "-s",
    type=click.Choice(["sold", "for_sale", "pending"]),
    default="sold",
)
@click.option("--days", "-d", default=180, type=int, help="Days to look back (for sold)")
def main(zip_code: str, status: str, days: int):
    """Download property listings directly from Redfin's CSV export."""
    ingest_redfin_listings(zip_code, status, days)


if __name__ == "__main__":
    main()
