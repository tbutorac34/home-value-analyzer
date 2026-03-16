"""Scrape price and tax history from Zillow using Playwright + autocomplete API."""

import json
import random
import time

import click
import requests
from rich.console import Console

from .db import get_connection, init_db

console = Console()

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def _find_zillow_zpid(address: str, city: str, state: str, zip_code: str) -> tuple[str | None, int | None]:
    """Use Zillow's autocomplete API to find a property's zpid and URL."""
    query = f"{address}, {city}, {state} {zip_code}".strip(", ")

    try:
        resp = requests.get(
            "https://www.zillowstatic.com/autocomplete/v3/suggestions",
            params={"q": query, "resultTypes": "allAddress"},
            headers={
                "User-Agent": random.choice(USER_AGENTS),
                "Referer": "https://www.zillow.com/",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                meta = results[0].get("metaData", {})
                zpid = meta.get("zpid")
                if zpid:
                    url = f"https://www.zillow.com/homedetails/{zpid}_zpid/"
                    return url, zpid
    except Exception:
        pass

    return None, None


def _scrape_with_playwright(url: str) -> dict | None:
    """Use Playwright to load a Zillow page and extract embedded JSON data."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        console.print("[red]Playwright not installed. Run: pip install playwright && playwright install chromium[/red]")
        return None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Wait for content to render
            page.wait_for_timeout(3000)

            html = page.content()
        except Exception as e:
            console.print(f"  [yellow]Page load error: {e}[/yellow]")
            browser.close()
            return None

        browser.close()

    # Extract data from embedded JSON
    return _extract_data_from_html(html)


def _extract_data_from_html(html: str) -> dict | None:
    """Extract price and tax history from Zillow's embedded page data."""
    result = {"price_history": [], "tax_history": []}

    # Try __NEXT_DATA__ first
    marker = 'id="__NEXT_DATA__"'
    if marker in html:
        try:
            start = html.index(marker)
            start = html.index(">", start) + 1
            end = html.index("</script>", start)
            data = json.loads(html[start:end])

            # Navigate Next.js structure to find property data
            props = data.get("props", {}).get("pageProps", {})
            _extract_from_nextdata(props, result)
            if result["price_history"] or result["tax_history"]:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Try hdpApolloPreloadedData
    marker2 = 'id="hdpApolloPreloadedData"'
    if marker2 in html:
        try:
            start = html.index(marker2)
            start = html.index(">", start) + 1
            end = html.index("</script>", start)
            raw = json.loads(html[start:end])
            api_cache = json.loads(raw.get("apiCache", "{}"))

            for key, value in api_cache.items():
                if isinstance(value, dict) and "property" in value:
                    prop_data = value["property"]
                    _extract_history(prop_data, result)
                    break
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: search for priceHistory in raw HTML JSON blobs
    if not result["price_history"]:
        _extract_from_raw_json(html, result)

    return result if (result["price_history"] or result["tax_history"]) else None


def _extract_from_nextdata(props: dict, result: dict) -> None:
    """Recursively search Next.js data for price/tax history."""
    if isinstance(props, dict):
        if "priceHistory" in props:
            _extract_history(props, result)
            return
        for value in props.values():
            _extract_from_nextdata(value, result)
    elif isinstance(props, list):
        for item in props:
            _extract_from_nextdata(item, result)


def _extract_history(prop_data: dict, result: dict) -> None:
    """Extract price and tax history from a property data dict."""
    for entry in prop_data.get("priceHistory", []):
        if entry.get("price"):
            result["price_history"].append({
                "date": entry.get("date", ""),
                "event": entry.get("event", ""),
                "price": entry.get("price"),
                "price_change_rate": entry.get("priceChangeRate"),
            })

    for entry in prop_data.get("taxHistory", []):
        year = None
        if entry.get("time"):
            year = str(entry["time"])[:4]
        elif entry.get("year"):
            year = str(entry["year"])
        if year:
            result["tax_history"].append({
                "year": year,
                "tax_paid": entry.get("taxPaid"),
                "assessed_value": entry.get("value"),
                "tax_increase_rate": entry.get("taxIncreaseRate"),
                "value_increase_rate": entry.get("valueIncreaseRate"),
            })


def _extract_from_raw_json(html: str, result: dict) -> None:
    """Last resort: scan HTML for JSON containing priceHistory."""
    import re
    # Find JSON objects containing priceHistory
    for match in re.finditer(r'"priceHistory"\s*:\s*\[', html):
        start = match.start()
        # Walk back to find the enclosing {
        brace_start = html.rfind("{", max(0, start - 500), start)
        if brace_start == -1:
            continue
        # Find matching closing brace
        depth = 0
        for i in range(brace_start, min(len(html), brace_start + 50000)):
            if html[i] == "{":
                depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(html[brace_start : i + 1])
                        _extract_history(obj, result)
                        return
                    except json.JSONDecodeError:
                        break


def scrape_and_store_history(
    db_property_id: int,
    zillow_url: str | None = None,
    delay: float = 3.0,
) -> bool:
    """Scrape Zillow history for a property and store in the database."""
    conn = get_connection()

    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?", (db_property_id,)
    ).fetchone()

    if not prop:
        console.print(f"[red]Property {db_property_id} not found[/red]")
        return False

    if not zillow_url:
        zillow_url, zpid = _find_zillow_zpid(
            prop["street"] or prop["address"],
            prop["city"] or "",
            prop["state"] or "",
            prop["zip_code"] or "",
        )
        if not zillow_url:
            console.print("  [yellow]Could not find property on Zillow[/yellow]")
            conn.close()
            return False

    console.print(f"  Scraping: {zillow_url}")
    time.sleep(delay + random.uniform(0, 2))

    data = _scrape_with_playwright(zillow_url)
    if not data:
        console.print("  [yellow]Could not extract data (bot detection or no history)[/yellow]")
        conn.close()
        return False

    # Store price history
    ph_count = 0
    for entry in data["price_history"]:
        if not entry["date"] or not entry["price"]:
            continue
        try:
            conn.execute(
                """INSERT OR IGNORE INTO price_history
                   (property_id, date, event, price, price_change_pct, source)
                   VALUES (?, ?, ?, ?, ?, 'zillow')""",
                (
                    db_property_id,
                    entry["date"],
                    entry["event"],
                    entry["price"],
                    entry.get("price_change_rate"),
                ),
            )
            ph_count += 1
        except Exception as e:
            console.print(f"  [red]Error storing price history: {e}[/red]")

    # Store tax history
    th_count = 0
    for entry in data["tax_history"]:
        year = entry.get("year")
        if not year:
            continue
        try:
            conn.execute(
                """INSERT OR IGNORE INTO tax_history
                   (property_id, year, tax_paid, assessed_value,
                    tax_increase_rate, value_increase_rate, source)
                   VALUES (?, ?, ?, ?, ?, ?, 'zillow')""",
                (
                    db_property_id,
                    int(year),
                    entry.get("tax_paid"),
                    entry.get("assessed_value"),
                    entry.get("tax_increase_rate"),
                    entry.get("value_increase_rate"),
                ),
            )
            th_count += 1
        except Exception as e:
            console.print(f"  [red]Error storing tax history: {e}[/red]")

    conn.commit()
    conn.close()

    console.print(f"  [green]Stored {ph_count} price events, {th_count} tax records[/green]")
    return ph_count > 0 or th_count > 0


@click.command()
@click.option("--property-id", "-id", type=int, default=None, help="Scrape history for a specific property")
@click.option("--zip", "zip_code", default=None, help="Scrape history for all properties in ZIP")
@click.option("--url", default=None, help="Direct Zillow URL to scrape")
@click.option("--limit", "-n", default=10, type=int, help="Max properties to scrape")
@click.option("--delay", "-d", default=5.0, type=float, help="Delay between requests (seconds)")
@click.option("--status", "-s", default="FOR_SALE", help="Filter by status (FOR_SALE, SOLD, etc.)")
def main(
    property_id: int | None,
    zip_code: str | None,
    url: str | None,
    limit: int,
    delay: float,
    status: str,
):
    """Scrape price/tax history from Zillow for properties in the database."""
    init_db()

    if property_id:
        console.print(f"[bold]Scraping history for property {property_id}[/bold]")
        scrape_and_store_history(property_id, zillow_url=url, delay=0)
        return

    if not zip_code:
        console.print("[red]Provide --property-id or --zip[/red]")
        return

    conn = get_connection()
    rows = conn.execute(
        """SELECT id, address, city FROM properties
           WHERE zip_code = ? AND status = ?
           ORDER BY COALESCE(list_price, sold_price) DESC
           LIMIT ?""",
        (zip_code, status, limit),
    ).fetchall()
    conn.close()

    if not rows:
        console.print(f"[yellow]No {status} properties found in {zip_code}[/yellow]")
        return

    console.print(f"[bold]Scraping Zillow history for {len(rows)} properties in {zip_code}[/bold]")
    success = 0
    for row in rows:
        console.print(f"\n[bold]{row['address']}[/bold] ({row['city']})")
        if scrape_and_store_history(row["id"], delay=delay):
            success += 1

    console.print(f"\n[bold green]Done: {success}/{len(rows)} properties scraped successfully[/bold green]")


if __name__ == "__main__":
    main()
