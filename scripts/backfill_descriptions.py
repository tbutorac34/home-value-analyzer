"""Backfill descriptions for properties that have Redfin URLs but no description."""

import sys
import os
import re
import time
import random

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from home_value_analyzer.db import get_connection, init_db
from rich.console import Console

console = Console()

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

DELAY = 2.5


def scrape_description(url: str) -> str | None:
    """Fetch a Redfin page and extract the listing description."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html",
        "DNT": "1",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return None

        match = re.search(
            r'<div[^>]*class="[^"]*remarks[^"]*"[^>]*>(.*?)</div>',
            resp.text,
            re.DOTALL,
        )
        if match:
            text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            text = text.replace("&rsquo;", "'").replace("&lsquo;", "'")
            text = text.replace("&rdquo;", '"').replace("&ldquo;", '"')
            text = text.replace("&amp;", "&").replace("&nbsp;", " ")
            if len(text) > 20:
                return text
    except requests.RequestException:
        pass

    return None


def main():
    init_db()
    conn = get_connection()

    rows = conn.execute("""
        SELECT id, address, city, zip_code, property_url
        FROM properties
        WHERE (description IS NULL OR description = '')
          AND property_url LIKE '%redfin.com%'
        ORDER BY zip_code, COALESCE(list_price, sold_price) DESC
    """).fetchall()
    conn.close()

    console.print(f"[bold]Backfilling descriptions for {len(rows)} properties[/bold]")

    success = 0
    failed = 0
    current_zip = None

    for i, row in enumerate(rows):
        if row["zip_code"] != current_zip:
            if current_zip:
                console.print(f"  [green]{current_zip}: {success} descriptions so far[/green]")
            current_zip = row["zip_code"]
            console.print(f"\n[bold]ZIP {current_zip}[/bold]")

        time.sleep(DELAY + random.uniform(0, 1))

        desc = scrape_description(row["property_url"])

        if desc:
            conn2 = get_connection()
            conn2.execute(
                "UPDATE properties SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (desc, row["id"]),
            )
            conn2.commit()
            conn2.close()
            success += 1
        else:
            failed += 1

        if (i + 1) % 50 == 0:
            console.print(f"  Progress: {i+1}/{len(rows)} ({success} success, {failed} failed)")

    console.print(f"\n[bold green]Done: {success}/{len(rows)} descriptions backfilled ({failed} failed)[/bold green]")


if __name__ == "__main__":
    main()
