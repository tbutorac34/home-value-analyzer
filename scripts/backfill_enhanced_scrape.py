"""Re-scrape Redfin properties to get enhanced data (photos, scores, details)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from home_value_analyzer.db import get_connection, init_db
from home_value_analyzer.scrape_redfin import scrape_and_store
from rich.console import Console

console = Console()
DELAY = 2.5


def main():
    init_db()
    conn = get_connection()

    # Find properties with Redfin URLs that don't have enhanced data yet
    rows = conn.execute("""
        SELECT p.id, p.address, p.city, p.zip_code
        FROM properties p
        WHERE p.property_url LIKE '%redfin.com%'
          AND p.redfin_estimate IS NULL
        ORDER BY p.zip_code, p.status DESC, COALESCE(p.list_price, p.sold_price) DESC
    """).fetchall()
    conn.close()

    console.print(f"[bold]Enhanced scraping for {len(rows)} properties[/bold]")

    success = 0
    current_zip = None

    for i, row in enumerate(rows):
        if row["zip_code"] != current_zip:
            if current_zip:
                console.print(f"  [green]{current_zip} done[/green]")
            current_zip = row["zip_code"]
            console.print(f"\n[bold]ZIP {current_zip}[/bold]")

        if scrape_and_store(row["id"], delay=DELAY):
            success += 1

        if (i + 1) % 50 == 0:
            console.print(f"  Progress: {i+1}/{len(rows)} ({success} success)")

    console.print(f"\n[bold green]Done: {success}/{len(rows)} enhanced[/bold green]")


if __name__ == "__main__":
    main()
