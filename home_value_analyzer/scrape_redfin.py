"""Comprehensive Redfin property page scraper.

Extracts from a single page load:
- Price history (all listing/sale/price change events)
- Tax history
- Listing description
- Redfin Estimate
- Walk/Bike scores
- School ratings
- Photo URLs
- Structured property details (basement, flooring, heating, etc.)
- Agent info
"""

import json
import re
import random
import time

import click
from rich.console import Console
from rich.table import Table

from .db import get_connection, init_db

console = Console()

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


def _get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1",
        "Connection": "keep-alive",
    }


def _parse_price(raw: str) -> float | None:
    raw = re.sub(r"<[^>]+>", " ", raw).strip()
    match = re.search(r"\$[\d,]+", raw)
    if match:
        return float(match.group().replace("$", "").replace(",", ""))
    return None


def _parse_date(raw: str) -> str:
    import datetime
    raw = raw.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


def scrape_redfin_page(redfin_url: str) -> dict:
    """Scrape everything from a Redfin property page.

    Returns comprehensive dict with all available data.
    """
    import requests

    result = {
        "price_history": [],
        "tax_history": [],
        "description": None,
        "redfin_estimate": None,
        "walk_score": None,
        "bike_score": None,
        "school_ratings": [],
        "photos": [],
        "property_details": {},
        "agent": {},
        "error": None,
    }

    try:
        resp = requests.get(redfin_url, headers=_get_headers(), timeout=20)

        if resp.status_code == 403:
            result["error"] = "Blocked by Redfin (403). Try again later."
            return result
        if resp.status_code == 404:
            result["error"] = "Property not found (404)."
            return result

        resp.raise_for_status()
        html = resp.text

        # === PRICE HISTORY ===
        rows = re.findall(
            r'<div class="BasicTable__col date">(.*?)</div>'
            r'.*?<div class="BasicTable__col event">(.*?)</div>'
            r'.*?<div class="BasicTable__col price">(.*?)</div>',
            html, re.DOTALL,
        )
        seen = set()
        for date_raw, event_raw, price_raw in rows:
            date = _parse_date(date_raw)
            event = event_raw.strip()
            price = _parse_price(price_raw)
            key = (date, event)
            if key in seen:
                continue
            seen.add(key)
            result["price_history"].append({"date": date, "event": event, "price": price})

        # === TAX HISTORY ===
        tax_rows = re.findall(
            r'<div class="BasicTable__col year">(.*?)</div>'
            r'.*?<div class="BasicTable__col tax">(.*?)</div>'
            r'.*?<div class="BasicTable__col assessment">(.*?)</div>',
            html, re.DOTALL,
        )
        tax_seen = set()
        for year_raw, tax_raw, assessment_raw in tax_rows:
            year = year_raw.strip()
            if year in tax_seen:
                continue
            tax_seen.add(year)
            result["tax_history"].append({
                "year": year,
                "tax_paid": _parse_price(tax_raw),
                "assessed_value": _parse_price(assessment_raw),
            })

        # === DESCRIPTION ===
        desc_match = re.search(
            r'<div[^>]*class="[^"]*remarks[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL,
        )
        if desc_match:
            desc_text = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()
            desc_text = desc_text.replace("&rsquo;", "'").replace("&lsquo;", "'")
            desc_text = desc_text.replace("&rdquo;", '"').replace("&ldquo;", '"')
            desc_text = desc_text.replace("&amp;", "&").replace("&nbsp;", " ")
            desc_text = desc_text.replace("&mdash;", "—").replace("&ndash;", "–")
            if len(desc_text) > 20:
                result["description"] = desc_text

        # === JSON DATA EXTRACTION ===
        # Redfin embeds structured data in JSON throughout the page

        # Redfin Estimate
        for pattern in [
            r'"predictedValue"\s*:\s*([\d.]+)',
            r'"redfinEstimateValue"\s*:\s*([\d.]+)',
            r'"estimatedValue"\s*:\s*([\d.]+)',
            r'"avm"\s*:\s*\{[^}]*"value"\s*:\s*([\d.]+)',
        ]:
            m = re.search(pattern, html)
            if m:
                val = _safe_float(m.group(1))
                if val and val > 10000:  # sanity check
                    result["redfin_estimate"] = val
                    break

        # Walk Score / Bike Score
        m = re.search(r'"walkScore"\s*:\s*\{[^}]*"value"\s*:\s*([\d.]+)', html)
        if m:
            result["walk_score"] = _safe_int(m.group(1))

        m = re.search(r'"bikeScore"\s*:\s*\{[^}]*"value"\s*:\s*([\d.]+)', html)
        if m:
            result["bike_score"] = _safe_int(m.group(1))

        # Lot size, garage, parking from JSON
        details = result["property_details"]

        m = re.search(r'"lotSize"\s*:\s*(\d+)', html)
        if m:
            details["lot_sqft"] = _safe_int(m.group(1))

        m = re.search(r'"skGarageSpaces"\s*:\s*(\d+)', html)
        if m:
            details["garage_spaces"] = _safe_int(m.group(1))

        m = re.search(r'"skParkingSpaces"\s*:\s*(\d+)', html)
        if m:
            details["parking_spaces"] = _safe_int(m.group(1))

        # Agent info
        m = re.search(r'"listingAgentName"\s*:\s*"([^"]+)"', html)
        if m:
            result["agent"]["name"] = m.group(1)

        m = re.search(r'"listingAgentNumber"\s*:\s*"([^"]+)"', html)
        if m:
            result["agent"]["phone"] = m.group(1)

        # Days on market
        m = re.search(r'"daysOnMarket"\s*:\s*"?(\d+)"?', html)
        if m:
            details["days_on_market"] = _safe_int(m.group(1))

        # === SCHOOL RATINGS ===
        school_matches = re.findall(
            r'SchoolsListItem__schoolRating[^>]*>(\d+)/10',
            html,
        )
        if school_matches:
            result["school_ratings"] = [int(s) for s in school_matches]

        # === PHOTOS ===
        photo_urls = set()
        # Pattern 1: photoUrls JSON
        for m in re.finditer(r'"nonFullScreenPhotoUrlCompressed"\s*:\s*"([^"]+)"', html):
            url = m.group(1).replace("\\u002F", "/")
            if url.startswith("http"):
                photo_urls.add(url)

        # Pattern 2: photo URLs in other formats
        for m in re.finditer(r'"fullScreenPhotoUrl"\s*:\s*"([^"]+)"', html):
            url = m.group(1).replace("\\u002F", "/")
            if url.startswith("http"):
                photo_urls.add(url)

        # Pattern 3: cdn-redfin URLs
        for m in re.finditer(r'(https?://ssl\.cdn-redfin\.com/photo/[^"\\]+)', html):
            photo_urls.add(m.group(1))

        result["photos"] = sorted(photo_urls)

        # === PROPERTY DETAILS FROM HTML TABLES ===
        # Pattern: <span class="table-label">KEY</span><div class="table-value">VALUE</div>
        table_pairs = re.findall(
            r'<span class="table-label">(.*?)</span>\s*<div class="table-value">(.*?)</div>',
            html, re.DOTALL,
        )
        for label_raw, value_raw in table_pairs:
            label = re.sub(r"<[^>]+>", "", label_raw).strip().lower()
            value = re.sub(r"<[^>]+>", "", value_raw).strip()
            if not value or value == "—" or value == "N/A":
                continue

            if "basement" in label:
                details["basement"] = value
            elif "flooring" in label:
                details["flooring"] = value
            elif "heating" in label:
                details["heating"] = value
            elif "cooling" in label:
                details["cooling"] = value
            elif "foundation" in label:
                details["foundation"] = value
            elif "roof" in label:
                details["roof"] = value
            elif "construction" in label:
                details["construction"] = value
            elif "sewer" in label:
                details["sewer"] = value
            elif "water" in label and "source" in label:
                details["water_source"] = value
            elif "appliance" in label:
                details["appliances"] = value
            elif "laundry" in label:
                details["laundry"] = value
            elif "fireplace" in label:
                details["fireplace"] = value
            elif "pool" in label:
                details["pool"] = value
            elif "hoa" in label:
                details["hoa"] = value

        # Pattern: <li class="entryItem ">KEY: VALUE</li>
        entry_items = re.findall(
            r'<li class="entryItem\s*">(.*?)</li>',
            html, re.DOTALL,
        )
        for item_raw in entry_items:
            item = re.sub(r"<[^>]+>", "", item_raw).strip()
            if ":" not in item:
                continue
            label, _, value = item.partition(":")
            label = label.strip().lower()
            value = value.strip()
            if not value:
                continue

            if "foundation" in label and "foundation" not in details:
                details["foundation"] = value
            elif "roof" in label and "roof" not in details:
                details["roof"] = value
            elif "construction" in label and "construction" not in details:
                details["construction"] = value
            elif "sewer" in label and "sewer" not in details:
                details["sewer"] = value
            elif "water" in label and "water_source" not in details:
                details["water_source"] = value
            elif "flooring" in label and "flooring" not in details:
                details["flooring"] = value
            elif "basement" in label and "basement" not in details:
                details["basement"] = value
            elif "heating" in label and "heating" not in details:
                details["heating"] = value
            elif "cooling" in label and "cooling" not in details:
                details["cooling"] = value

        # Feature specifications from JSON
        feature_specs = re.findall(
            r'"name"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*(true|false|"[^"]*")',
            html,
        )
        for name, value in feature_specs:
            name_lower = name.lower()
            if "has a/c" in name_lower or "central air" in name_lower:
                if value == "true" and "cooling" not in details:
                    details["cooling"] = "Central Air"
            elif "heating" in name_lower and "heating" not in details:
                details["heating"] = name.split(":")[-1].strip() if ":" in name else value.strip('"')
            elif "laundry" in name_lower and "laundry" not in details:
                details["laundry"] = name.split(":")[-1].strip() if ":" in name else value.strip('"')

        # === FLOOD RISK ===
        flood_match = re.search(r'"floodFactor"\s*:\s*(\d+)', html)
        if flood_match:
            result["flood_risk"] = f"factor_{flood_match.group(1)}"

    except Exception as e:
        result["error"] = str(e)

    return result


def _ensure_tables(conn):
    """Create enhanced tables if they don't exist."""
    conn.executescript("""
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
    """)


def _map_details_to_adjustments(details: dict) -> dict:
    """Map Redfin structured property details to adjustment fields."""
    adj = {}

    basement = details.get("basement", "").lower()
    if basement:
        if any(w in basement for w in ["finished", "full", "walkout", "walk out", "daylight"]):
            adj["basement_finished"] = True
            if "partial" in basement:
                adj["basement_type"] = "partial_finished"
            else:
                adj["basement_type"] = "full_finished"
        elif "unfinished" in basement or "none" in basement:
            adj["basement_finished"] = False
            adj["basement_type"] = "unfinished"

    flooring = details.get("flooring", "").lower()
    if flooring:
        if "hardwood" in flooring:
            adj["flooring_type"] = "hardwood"
        elif "lvp" in flooring or "luxury vinyl" in flooring or "vinyl plank" in flooring:
            adj["flooring_type"] = "lvp"
        elif "carpet" in flooring:
            adj["flooring_type"] = "carpet"
        elif "tile" in flooring:
            adj["flooring_type"] = "tile"

    fireplace = details.get("fireplace", "").lower()
    if fireplace and fireplace not in ("none", "no", "n/a"):
        adj["fireplace"] = True
        if "gas" in fireplace:
            adj["fireplace_type"] = "gas"
        elif "wood" in fireplace:
            adj["fireplace_type"] = "wood"
        elif "electric" in fireplace:
            adj["fireplace_type"] = "electric"

    pool = details.get("pool", "").lower()
    if pool and pool not in ("none", "no", "n/a"):
        adj["pool"] = True
        if "in ground" in pool or "inground" in pool:
            adj["pool_type"] = "inground"
        elif "above" in pool:
            adj["pool_type"] = "above_ground"

    garage = details.get("garage_spaces")
    if garage:
        adj["garage_type"] = "attached"  # default assumption

    return adj


def scrape_and_store(
    db_property_id: int,
    property_url: str | None = None,
    delay: float = 3.0,
) -> bool:
    """Scrape a Redfin page and store all data in the database."""
    conn = get_connection()
    _ensure_tables(conn)

    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?", (db_property_id,)
    ).fetchone()

    if not prop:
        console.print(f"[red]Property {db_property_id} not found[/red]")
        return False

    # Find a Redfin URL
    url = property_url
    if not url:
        url = prop["property_url"]
    if not url or "redfin.com" not in (url or ""):
        row = conn.execute(
            """SELECT property_url FROM properties
               WHERE property_url LIKE '%redfin.com%'
                 AND street = ? AND zip_code = ?
               LIMIT 1""",
            (prop["street"], prop["zip_code"]),
        ).fetchone()
        if row:
            url = row["property_url"]

    if not url or "redfin.com" not in url:
        console.print("  [yellow]No Redfin URL found[/yellow]")
        conn.close()
        return False

    console.print(f"  Scraping: {url}")
    time.sleep(delay + random.uniform(0, 1.5))

    result = scrape_redfin_page(url)

    if result["error"]:
        console.print(f"  [yellow]{result['error']}[/yellow]")
        conn.close()
        return False

    success = False

    # --- Store price history ---
    ph_count = 0
    prev_price = None
    sorted_history = sorted(result["price_history"], key=lambda x: x["date"])
    for entry in sorted_history:
        price_change = None
        price_change_pct = None
        if entry["price"] and prev_price and prev_price > 0:
            price_change = entry["price"] - prev_price
            price_change_pct = price_change / prev_price
        try:
            conn.execute(
                """INSERT OR IGNORE INTO price_history
                   (property_id, date, event, price, price_change, price_change_pct, source)
                   VALUES (?, ?, ?, ?, ?, ?, 'redfin')""",
                (db_property_id, entry["date"], entry["event"], entry["price"],
                 price_change, price_change_pct),
            )
            ph_count += 1
        except Exception:
            pass
        if entry["price"]:
            prev_price = entry["price"]

    if ph_count > 0:
        success = True

    # --- Store tax history ---
    th_count = 0
    for entry in result["tax_history"]:
        year = entry.get("year")
        if not year:
            continue
        try:
            conn.execute(
                """INSERT OR IGNORE INTO tax_history
                   (property_id, year, tax_paid, assessed_value, source)
                   VALUES (?, ?, ?, ?, 'redfin')""",
                (db_property_id, int(year), entry.get("tax_paid"), entry.get("assessed_value")),
            )
            th_count += 1
        except Exception:
            pass

    # --- Update properties with new fields ---
    updates = []
    params = []

    if result["description"] and not prop["description"]:
        updates.append("description=?")
        params.append(result["description"])

    if result["redfin_estimate"]:
        updates.append("redfin_estimate=?")
        params.append(result["redfin_estimate"])

    if result["walk_score"]:
        updates.append("walk_score=?")
        params.append(result["walk_score"])

    if result["bike_score"]:
        updates.append("bike_score=?")
        params.append(result["bike_score"])

    if result.get("flood_risk"):
        updates.append("flood_risk=?")
        params.append(result["flood_risk"])

    details = result["property_details"]
    if details.get("lot_sqft") and not prop["lot_sqft"]:
        updates.append("lot_sqft=?")
        params.append(details["lot_sqft"])

    if details.get("garage_spaces") and not prop["garage_spaces"]:
        updates.append("garage_spaces=?")
        params.append(details["garage_spaces"])

    if details.get("days_on_market") and not prop["days_on_mls"]:
        updates.append("days_on_mls=?")
        params.append(details["days_on_market"])

    if result["agent"].get("name") and not prop["agent_name"]:
        updates.append("agent_name=?")
        params.append(result["agent"]["name"])

    for field in ["heating", "cooling", "construction_type", "roof_type",
                   "foundation_type", "sewer", "water_source", "appliances", "laundry"]:
        detail_key = field.replace("_type", "").replace("water_source", "water_source")
        val = details.get(detail_key) or details.get(field)
        if val:
            updates.append(f"{field}=?")
            params.append(val)

    # School rating (average of all schools)
    if result["school_ratings"]:
        avg_rating = sum(result["school_ratings"]) / len(result["school_ratings"])
        updates.append("school_rating=?")
        params.append(round(avg_rating, 1))

    if updates:
        updates.append("updated_at=CURRENT_TIMESTAMP")
        params.append(db_property_id)
        conn.execute(
            f"UPDATE properties SET {', '.join(updates)} WHERE id=?",
            params,
        )
        success = True

    # --- Store photos ---
    photo_count = 0
    for i, photo_url in enumerate(result["photos"]):
        try:
            conn.execute(
                """INSERT OR IGNORE INTO property_photos
                   (property_id, url, position)
                   VALUES (?, ?, ?)""",
                (db_property_id, photo_url, i),
            )
            photo_count += 1
        except Exception:
            pass

    if photo_count > 0:
        success = True

    # --- Store structured adjustments ---
    adj_data = _map_details_to_adjustments(details)
    if adj_data:
        from .adjustments import save_adjustments
        try:
            save_adjustments(conn, db_property_id, adj_data,
                           source="redfin_structured", confidence=1.0)
        except Exception:
            pass  # Table might not exist yet

    conn.commit()
    conn.close()

    parts = []
    if ph_count > 0:
        parts.append(f"{ph_count} history")
    if th_count > 0:
        parts.append(f"{th_count} tax")
    if photo_count > 0:
        parts.append(f"{photo_count} photos")
    if result["description"] and not prop["description"]:
        parts.append("description")
    if result["redfin_estimate"]:
        parts.append(f"est=${result['redfin_estimate']:,.0f}")
    if result["walk_score"]:
        parts.append(f"walk={result['walk_score']}")
    if details:
        parts.append(f"{len(details)} details")

    console.print(f"  [green]{', '.join(parts) if parts else 'no new data'}[/green]")
    return success


# Keep backwards compatibility
scrape_and_store_history = scrape_and_store


def display_history(db_property_id: int) -> None:
    """Display stored history and enhanced data for a property."""
    conn = get_connection()

    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?", (db_property_id,)
    ).fetchone()
    if not prop:
        console.print(f"[red]Property {db_property_id} not found[/red]")
        return

    console.print(f"\n[bold]{prop['address']}[/bold]")

    # Enhanced fields
    enhanced = []
    if prop["redfin_estimate"]:
        enhanced.append(f"Redfin Estimate: ${prop['redfin_estimate']:,.0f}")
    if prop["walk_score"]:
        enhanced.append(f"Walk Score: {prop['walk_score']}")
    if prop["bike_score"]:
        enhanced.append(f"Bike Score: {prop['bike_score']}")
    if prop["school_rating"]:
        enhanced.append(f"School Rating: {prop['school_rating']}/10")
    if prop["heating"]:
        enhanced.append(f"Heating: {prop['heating']}")
    if prop["cooling"]:
        enhanced.append(f"Cooling: {prop['cooling']}")
    if prop["foundation_type"]:
        enhanced.append(f"Foundation: {prop['foundation_type']}")
    if prop["roof_type"]:
        enhanced.append(f"Roof: {prop['roof_type']}")

    if enhanced:
        console.print("  " + " | ".join(enhanced))

    # Photo count
    _ensure_tables(conn)
    photo_count = conn.execute(
        "SELECT COUNT(*) FROM property_photos WHERE property_id = ?",
        (db_property_id,),
    ).fetchone()[0]
    if photo_count:
        console.print(f"  Photos: {photo_count}")

    # Price history
    ph_rows = conn.execute(
        "SELECT * FROM price_history WHERE property_id = ? ORDER BY date DESC",
        (db_property_id,),
    ).fetchall()

    if ph_rows:
        table = Table(title="Price History")
        table.add_column("Date")
        table.add_column("Event")
        table.add_column("Price", justify="right")
        table.add_column("Change", justify="right")

        for row in ph_rows:
            change_str = ""
            if row["price_change"] and row["price_change_pct"]:
                color = "green" if row["price_change"] > 0 else "red"
                change_str = f"[{color}]${row['price_change']:+,.0f} ({row['price_change_pct']:+.1%})[/{color}]"
            table.add_row(
                row["date"],
                row["event"],
                f"${row['price']:,.0f}" if row["price"] else "-",
                change_str,
            )
        console.print(table)

    # Tax history
    th_rows = conn.execute(
        "SELECT * FROM tax_history WHERE property_id = ? ORDER BY year DESC",
        (db_property_id,),
    ).fetchall()
    if th_rows:
        table = Table(title="Tax History")
        table.add_column("Year")
        table.add_column("Tax Paid", justify="right")
        table.add_column("Assessed Value", justify="right")
        for row in th_rows:
            table.add_row(
                str(row["year"]),
                f"${row['tax_paid']:,.0f}" if row["tax_paid"] else "N/A",
                f"${row['assessed_value']:,.0f}" if row["assessed_value"] else "N/A",
            )
        console.print(table)

    if not ph_rows and not th_rows and not enhanced:
        console.print("[yellow]No data stored yet. Run scrape-redfin first.[/yellow]")

    conn.close()


@click.command()
@click.option("--property-id", "-id", type=int, default=None, help="Scrape a specific property")
@click.option("--zip", "zip_code", default=None, help="Scrape all properties in ZIP")
@click.option("--url", default=None, help="Direct Redfin URL to scrape")
@click.option("--limit", "-n", default=50, type=int, help="Max properties to scrape")
@click.option("--delay", "-d", default=3.0, type=float, help="Delay between requests (seconds)")
@click.option("--status", "-s", default="FOR_SALE", help="Filter by status")
@click.option("--show", is_flag=True, help="Show stored data instead of scraping")
def main(
    property_id: int | None,
    zip_code: str | None,
    url: str | None,
    limit: int,
    delay: float,
    status: str,
    show: bool,
):
    """Scrape comprehensive property data from Redfin pages."""
    init_db()

    if show and property_id:
        display_history(property_id)
        return

    if property_id:
        console.print(f"[bold]Scraping property {property_id}[/bold]")
        scrape_and_store(property_id, property_url=url, delay=0)
        return

    if not zip_code:
        console.print("[red]Provide --property-id or --zip[/red]")
        return

    conn = get_connection()
    rows = conn.execute(
        """SELECT id, address, city, property_url FROM properties
           WHERE zip_code = ? AND status = ?
             AND property_url LIKE '%redfin.com%'
           ORDER BY COALESCE(list_price, sold_price) DESC
           LIMIT ?""",
        (zip_code, status, limit),
    ).fetchall()
    conn.close()

    if not rows:
        console.print(f"[yellow]No {status} properties with Redfin URLs in {zip_code}[/yellow]")
        return

    console.print(f"[bold]Scraping {len(rows)} properties in {zip_code}[/bold]")
    success = 0
    for row in rows:
        console.print(f"\n[bold]{row['address']}[/bold]")
        if scrape_and_store(row["id"], delay=delay):
            success += 1

    console.print(f"\n[bold green]Done: {success}/{len(rows)} scraped[/bold green]")


if __name__ == "__main__":
    main()
