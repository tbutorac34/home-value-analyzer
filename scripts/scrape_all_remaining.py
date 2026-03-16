"""Scrape price history for ALL Redfin properties that don't have history yet."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from home_value_analyzer.db import get_connection, init_db
from home_value_analyzer.scrape_history import scrape_and_store_history
from rich.console import Console

console = Console()
DELAY = 2.5  # Slightly faster since we're doing a big batch


def main():
    init_db()
    conn = get_connection()

    # Find all Redfin properties without price history
    rows = conn.execute("""
        SELECT p.id, p.address, p.city, p.zip_code, p.status
        FROM properties p
        WHERE p.property_url LIKE '%redfin.com%'
          AND p.id NOT IN (SELECT DISTINCT property_id FROM price_history)
        ORDER BY p.zip_code, p.status, COALESCE(p.list_price, p.sold_price) DESC
    """).fetchall()
    conn.close()

    console.print(f"[bold]Scraping history for {len(rows)} remaining Redfin properties[/bold]")

    success = 0
    failed = 0
    current_zip = None

    for i, row in enumerate(rows):
        if row["zip_code"] != current_zip:
            if current_zip:
                console.print(f"  [green]{current_zip} done[/green]")
            current_zip = row["zip_code"]
            console.print(f"\n[bold]ZIP {current_zip}[/bold]")

        if scrape_and_store_history(row["id"], delay=DELAY):
            success += 1
        else:
            failed += 1

        if (i + 1) % 50 == 0:
            console.print(f"  Progress: {i+1}/{len(rows)} ({success} success, {failed} failed)")

    console.print(f"\n[bold green]Done: {success}/{len(rows)} scraped ({failed} failed)[/bold green]")


if __name__ == "__main__":
    main()
