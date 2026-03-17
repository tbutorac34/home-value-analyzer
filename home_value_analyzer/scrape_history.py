"""Scrape price and tax history from Redfin property pages."""

import re
import random
import time

import click
import requests
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
    """Extract dollar amount from a price string like '$415,000 $145/sq ft'."""
    raw = re.sub(r"<[^>]+>", " ", raw).strip()
    match = re.search(r"\$[\d,]+", raw)
    if match:
        return float(match.group().replace("$", "").replace(",", ""))
    return None


def _parse_date(raw: str) -> str:
    """Normalize date like 'Dec 19, 2025' to '2025-12-19'."""
    import datetime
    raw = raw.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def scrape_redfin_history(redfin_url: str) -> dict:
    """Scrape price and tax history from a Redfin property page.

    Returns dict with 'price_history' and 'tax_history' lists.
    """
    result = {"price_history": [], "tax_history": [], "description": None, "error": None}

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

        # Extract sale history rows
        # Pattern: <div class="BasicTable__col date">DATE</div>
        #          <div class="BasicTable__col event">EVENT</div>
        #          <div class="BasicTable__col price">PRICE</div>
        rows = re.findall(
            r'<div class="BasicTable__col date">(.*?)</div>'
            r'.*?<div class="BasicTable__col event">(.*?)</div>'
            r'.*?<div class="BasicTable__col price">(.*?)</div>',
            html,
            re.DOTALL,
        )

        # Dedup (the table appears twice - preview and expanded)
        seen = set()
        for date_raw, event_raw, price_raw in rows:
            date = _parse_date(date_raw)
            event = event_raw.strip()
            price = _parse_price(price_raw)

            key = (date, event)
            if key in seen:
                continue
            seen.add(key)

            result["price_history"].append({
                "date": date,
                "event": event,
                "price": price,
            })

        # Extract tax history rows
        # Pattern: <div class="BasicTable__col year">YEAR</div>
        #          <div class="BasicTable__col tax">TAX</div>
        #          <div class="BasicTable__col assessment">VALUE</div>
        tax_rows = re.findall(
            r'<div class="BasicTable__col year">(.*?)</div>'
            r'.*?<div class="BasicTable__col tax">(.*?)</div>'
            r'.*?<div class="BasicTable__col assessment">(.*?)</div>',
            html,
            re.DOTALL,
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

        # Extract listing description
        desc_match = re.search(
            r'<div[^>]*class="[^"]*remarks[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )
        if desc_match:
            desc_text = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()
            # Decode HTML entities
            desc_text = desc_text.replace("&rsquo;", "'").replace("&lsquo;", "'")
            desc_text = desc_text.replace("&rdquo;", '"').replace("&ldquo;", '"')
            desc_text = desc_text.replace("&amp;", "&").replace("&nbsp;", " ")
            if len(desc_text) > 20:
                result["description"] = desc_text

    except requests.RequestException as e:
        result["error"] = str(e)

    return result


def scrape_and_store_history(
    db_property_id: int,
    property_url: str | None = None,
    delay: float = 3.0,
) -> bool:
    """Scrape Redfin history for a property and store in the database."""
    conn = get_connection()

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
        # Try to find a Redfin entry for the same address
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
        console.print("  [yellow]No Redfin URL found for this property[/yellow]")
        conn.close()
        return False

    console.print(f"  Scraping: {url}")
    time.sleep(delay + random.uniform(0, 1.5))

    result = scrape_redfin_history(url)

    if result["error"]:
        console.print(f"  [yellow]{result['error']}[/yellow]")
        conn.close()
        return False

    # Store price history
    ph_count = 0
    prev_price = None
    # Sort by date ascending for computing changes
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
                (
                    db_property_id,
                    entry["date"],
                    entry["event"],
                    entry["price"],
                    price_change,
                    price_change_pct,
                ),
            )
            ph_count += 1
        except Exception as e:
            console.print(f"  [red]Error storing price history: {e}[/red]")

        if entry["price"]:
            prev_price = entry["price"]

    # Store tax history
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
                (
                    db_property_id,
                    int(year),
                    entry.get("tax_paid"),
                    entry.get("assessed_value"),
                ),
            )
            th_count += 1
        except Exception as e:
            console.print(f"  [red]Error storing tax history: {e}[/red]")

    # Store description if we got one and property doesn't have one
    if result["description"] and not prop["description"]:
        conn.execute(
            "UPDATE properties SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (result["description"], db_property_id),
        )

    conn.commit()
    conn.close()

    desc_note = ", +description" if result["description"] and not prop["description"] else ""
    console.print(f"  [green]Stored {ph_count} price events, {th_count} tax records{desc_note}[/green]")
    return ph_count > 0 or th_count > 0 or bool(result["description"])


def display_history(db_property_id: int) -> None:
    """Display stored price and tax history for a property."""
    conn = get_connection()

    prop = conn.execute(
        "SELECT address, city FROM properties WHERE id = ?", (db_property_id,)
    ).fetchone()
    if not prop:
        console.print(f"[red]Property {db_property_id} not found[/red]")
        return

    console.print(f"\n[bold]History: {prop['address']}[/bold]")

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

    if not ph_rows and not th_rows:
        console.print("[yellow]No history stored yet. Run scrape-history first.[/yellow]")

    conn.close()


@click.command()
@click.option("--property-id", "-id", type=int, default=None, help="Scrape history for a specific property")
@click.option("--zip", "zip_code", default=None, help="Scrape history for all Redfin properties in ZIP")
@click.option("--url", default=None, help="Direct Redfin URL to scrape")
@click.option("--limit", "-n", default=20, type=int, help="Max properties to scrape")
@click.option("--delay", "-d", default=3.0, type=float, help="Delay between requests (seconds)")
@click.option("--status", "-s", default="FOR_SALE", help="Filter by status (FOR_SALE, SOLD, etc.)")
@click.option("--show", is_flag=True, help="Show stored history instead of scraping")
def main(
    property_id: int | None,
    zip_code: str | None,
    url: str | None,
    limit: int,
    delay: float,
    status: str,
    show: bool,
):
    """Scrape price/tax history from Redfin for properties in the database."""
    init_db()

    if show and property_id:
        display_history(property_id)
        return

    if property_id:
        console.print(f"[bold]Scraping history for property {property_id}[/bold]")
        scrape_and_store_history(property_id, property_url=url, delay=0)
        return

    if not zip_code:
        console.print("[red]Provide --property-id or --zip[/red]")
        return

    conn = get_connection()
    # Only select properties that have a Redfin URL
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
        console.print("Try ingesting from Redfin first: python -m home_value_analyzer ingest-redfin --zip <zip>")
        return

    console.print(f"[bold]Scraping Redfin history for {len(rows)} properties in {zip_code}[/bold]")
    success = 0
    for row in rows:
        console.print(f"\n[bold]{row['address']}[/bold] ({row['city']})")
        if scrape_and_store_history(row["id"], delay=delay):
            success += 1

    console.print(f"\n[bold green]Done: {success}/{len(rows)} properties scraped[/bold green]")


if __name__ == "__main__":
    main()
