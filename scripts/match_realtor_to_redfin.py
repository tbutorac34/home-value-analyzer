"""Match Realtor.com properties to Redfin URLs and scrape their history.

Strategy:
1. DB match: find Redfin properties with same street + zip (fast, no network)
2. URL construction: build Redfin URL and check if it resolves (for unmatched)
3. Scrape history from matched Redfin URLs
"""

import re
import sys
import os
import time
import random

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from home_value_analyzer.db import get_connection, init_db
from home_value_analyzer.scrape_history import scrape_and_store_history
from rich.console import Console

console = Console()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

DELAY = 2.5

# Redfin uses simplified city names
CITY_MAP = {
    "Macomb Township": "Macomb",
    "Macomb Twp": "Macomb",
    "Shelby Township": "Shelby-Township",
    "Shelby Twp": "Shelby-Township",
    "Clinton Township": "Clinton-Township",
    "Clinton Twp": "Clinton-Township",
    "Washington Township": "Washington-Township",
    "Washington Twp": "Washington-Township",
    "Bruce Township": "Bruce-Township",
    "Bruce Twp": "Bruce-Township",
    "Rochester Hills": "Rochester-Hills",
    "Romeo Vlg": "Romeo",
    "Romeo Village": "Romeo",
}


def _try_redfin_url(street: str, city: str, state: str, zip_code: str) -> str | None:
    """Construct a Redfin URL and check if it resolves to a property page."""
    state_upper = (state or "MI").upper()

    # Normalize city
    city_clean = CITY_MAP.get(city, city) if city else ""
    city_slug = re.sub(r"[^\w\s-]", "", city_clean).strip()
    city_slug = re.sub(r"\s+", "-", city_slug)

    # Normalize street - remove directional suffixes and unit numbers
    street_clean = re.sub(r"\s*(Unit|#|Apt|Ste)\s*\S*$", "", street, flags=re.IGNORECASE).strip()
    # Remove trailing directional (E, N, S, W) that Realtor adds
    street_clean = re.sub(r"\s+[ENSW]$", "", street_clean)
    street_slug = re.sub(r"[^\w\s]", "", street_clean).strip()
    street_slug = re.sub(r"\s+", "-", street_slug)

    url = f"https://www.redfin.com/{state_upper}/{city_slug}/{street_slug}-{zip_code}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code == 200 and "/home/" in resp.url:
            return resp.url
    except requests.RequestException:
        pass

    return None


def main():
    init_db()
    conn = get_connection()

    # Phase 1: DB-based matching (fast, no network)
    console.print("[bold]Phase 1: DB-based matching (street + zip)[/bold]")

    realtor_props = conn.execute("""
        SELECT r.id, r.street, r.zip_code, r.city, r.state
        FROM properties r
        WHERE (r.property_url LIKE '%realtor.com%' OR r.property_url IS NULL)
          AND r.id NOT IN (SELECT DISTINCT property_id FROM price_history)
          AND r.street IS NOT NULL
          AND r.zip_code IS NOT NULL
        ORDER BY r.zip_code
    """).fetchall()

    console.print(f"  {len(realtor_props)} Realtor.com properties need history")

    db_matched = 0
    db_scraped = 0
    unmatched = []

    for row in realtor_props:
        # Try to find a Redfin URL from existing properties
        match = conn.execute(
            """SELECT property_url FROM properties
               WHERE property_url LIKE '%redfin.com%'
                 AND street = ? AND zip_code = ?
               LIMIT 1""",
            (row["street"], row["zip_code"]),
        ).fetchone()

        if match:
            db_matched += 1
            if scrape_and_store_history(row["id"], property_url=match["property_url"], delay=DELAY):
                db_scraped += 1

            if db_matched % 50 == 0:
                console.print(f"  Progress: {db_matched} matched, {db_scraped} scraped")
        else:
            unmatched.append(row)

    console.print(f"[green]Phase 1 done: {db_matched} matched, {db_scraped} scraped[/green]")

    # Phase 2: URL construction for unmatched (slower, hits Redfin)
    console.print(f"\n[bold]Phase 2: URL construction for {len(unmatched)} unmatched[/bold]")

    url_matched = 0
    url_scraped = 0

    for i, row in enumerate(unmatched):
        time.sleep(DELAY + random.uniform(0, 1))

        redfin_url = _try_redfin_url(
            row["street"],
            row["city"] or "",
            row["state"] or "MI",
            row["zip_code"],
        )

        if redfin_url:
            url_matched += 1
            # Store the Redfin URL
            conn.execute(
                "UPDATE properties SET property_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (redfin_url, row["id"]),
            )
            conn.commit()

            if scrape_and_store_history(row["id"], property_url=redfin_url, delay=0):
                url_scraped += 1

        if (i + 1) % 25 == 0:
            console.print(f"  Progress: {i+1}/{len(unmatched)} ({url_matched} matched, {url_scraped} scraped)")

    conn.close()

    console.print(f"\n[bold green]Phase 2 done: {url_matched}/{len(unmatched)} matched, {url_scraped} scraped[/bold green]")
    console.print(f"\n[bold]Total: {db_matched + url_matched} matched, {db_scraped + url_scraped} scraped[/bold]")


if __name__ == "__main__":
    main()
