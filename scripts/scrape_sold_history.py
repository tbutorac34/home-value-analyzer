"""One-time script: scrape price history for SOLD properties across all ZIPs."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from home_value_analyzer.db import get_connection, init_db
from home_value_analyzer.scrape_history import scrape_and_store_history
from rich.console import Console

console = Console()

ZIPS = [
    "48044", "48042", "48096", "48005", "48317", "48316", "48315",
    "48095", "48065", "48309", "48307", "48085", "48098", "48363",
    "48038", "48094",
]

LIMIT_PER_ZIP = 50
DELAY = 3.0


def main():
    init_db()

    total_success = 0
    total_attempted = 0

    for zip_code in ZIPS:
        conn = get_connection()
        rows = conn.execute(
            """SELECT id, address, city FROM properties
               WHERE zip_code = ? AND status = 'SOLD'
                 AND property_url LIKE '%redfin.com%'
                 AND id NOT IN (SELECT DISTINCT property_id FROM price_history)
               ORDER BY sold_price DESC
               LIMIT ?""",
            (zip_code, LIMIT_PER_ZIP),
        ).fetchall()
        conn.close()

        if not rows:
            console.print(f"[dim]{zip_code}: no sold properties to scrape[/dim]")
            continue

        console.print(f"\n[bold]{zip_code}: scraping {len(rows)} sold properties[/bold]")
        success = 0
        for row in rows:
            if scrape_and_store_history(row["id"], delay=DELAY):
                success += 1
            total_attempted += 1

        total_success += success
        console.print(f"  [green]{zip_code}: {success}/{len(rows)} scraped[/green]")

    console.print(f"\n[bold green]Done: {total_success}/{total_attempted} total[/bold green]")

    # Sync to Supabase
    console.print("\n[bold]Syncing to Supabase...[/bold]")
    from home_value_analyzer.ingest_all import _migrate_new_data_to_supabase
    conn = get_connection()
    _migrate_new_data_to_supabase(conn)
    conn.close()
    console.print("[bold green]Sync complete[/bold green]")


if __name__ == "__main__":
    main()
