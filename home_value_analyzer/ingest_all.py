"""Run the full ingestion pipeline for one or more ZIP codes."""

import os
import sqlite3
import time
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console

from .db import get_connection, init_db
from .ingest_redfin import ingest_redfin_listings
from .scrape_redfin import scrape_and_store

console = Console()


def _migrate_new_data_to_supabase(conn: sqlite3.Connection):
    """Push any un-migrated data to Supabase."""
    load_dotenv(Path(__file__).parent.parent / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        console.print("[yellow]  No Supabase configured, skipping sync[/yellow]")
        return

    try:
        from supabase import create_client
    except ImportError:
        return

    sb = create_client(url, key)

    # Get all local properties
    cursor = conn.execute("SELECT * FROM properties ORDER BY id")
    columns = [desc[0] for desc in cursor.description]
    all_rows = cursor.fetchall()

    if not all_rows:
        return

    # Build batch, track old IDs
    batch = []
    old_ids = []
    for row in all_rows:
        d = {}
        old_id = None
        for col, val in zip(columns, row):
            if col == "id":
                old_id = val
                continue
            if col == "new_construction":
                d[col] = bool(val) if val is not None else False
            elif val is not None:
                d[col] = val
        batch.append(d)
        old_ids.append(old_id)

    # Upsert properties in batches
    id_map = {}
    for i in range(0, len(batch), 50):
        chunk = batch[i : i + 50]
        chunk_ids = old_ids[i : i + 50]
        result = sb.table("properties").upsert(
            chunk, on_conflict="source,source_id"
        ).execute()
        for old_id, new_row in zip(chunk_ids, result.data):
            id_map[old_id] = new_row["id"]

    console.print(f"  [green]Synced {len(id_map)} properties to Supabase[/green]")

    # Sync price history
    ph_rows = conn.execute("SELECT * FROM price_history ORDER BY id").fetchall()
    ph_columns = [desc[0] for desc in conn.execute("SELECT * FROM price_history LIMIT 1").description]

    if ph_rows:
        ph_batch = []
        for row in ph_rows:
            d = {}
            for col, val in zip(ph_columns, row):
                if col == "id":
                    continue
                if col == "property_id":
                    if val not in id_map:
                        continue
                    d[col] = id_map[val]
                elif val is not None:
                    d[col] = val
            if "property_id" in d:
                ph_batch.append(d)

        for i in range(0, len(ph_batch), 100):
            chunk = ph_batch[i : i + 100]
            try:
                sb.table("price_history").upsert(
                    chunk, on_conflict="property_id,date,event"
                ).execute()
            except Exception as e:
                console.print(f"  [yellow]Price history sync error: {e}[/yellow]")

        console.print(f"  [green]Synced {len(ph_batch)} price history events to Supabase[/green]")

    # Sync market stats
    ms_rows = conn.execute("SELECT * FROM market_stats ORDER BY id").fetchall()
    ms_columns = [desc[0] for desc in conn.execute("SELECT * FROM market_stats LIMIT 1").description] if ms_rows else []

    if ms_rows:
        ms_batch = []
        for row in ms_rows:
            d = {}
            for col, val in zip(ms_columns, row):
                if col == "id":
                    continue
                if val is not None:
                    d[col] = val
            ms_batch.append(d)

        for i in range(0, len(ms_batch), 200):
            chunk = ms_batch[i : i + 200]
            try:
                sb.table("market_stats").upsert(
                    chunk, on_conflict="region_type,region_name,period,source"
                ).execute()
            except Exception as e:
                console.print(f"  [yellow]Market stats sync error: {e}[/yellow]")

        console.print(f"  [green]Synced {len(ms_batch)} market stats to Supabase[/green]")


def ingest_zip(zip_code: str, scrape_limit: int = 50, scrape_delay: float = 3.0):
    """Run the full ingestion pipeline for a single ZIP code."""
    console.print(f"\n[bold]{'='*60}[/bold]")
    console.print(f"[bold]Processing ZIP: {zip_code}[/bold]")
    console.print(f"[bold]{'='*60}[/bold]")

    # Step 1: Redfin CSV download - discover properties + get URLs
    console.print(f"\n[bold cyan]Step 1: Redfin CSV listings[/bold cyan]")
    try:
        ingest_redfin_listings(zip_code, status="sold", days=180)
    except Exception as e:
        console.print(f"  [red]Redfin sold error: {e}[/red]")

    try:
        ingest_redfin_listings(zip_code, status="for_sale")
    except Exception as e:
        console.print(f"  [red]Redfin for_sale error: {e}[/red]")

    # Step 2: Enhanced Redfin page scrape (history + description + photos + details)
    console.print(f"\n[bold cyan]Step 2: Enhanced Redfin page scrape[/bold cyan]")
    for scrape_status in ["FOR_SALE", "SOLD"]:
        conn = get_connection()
        rows = conn.execute(
            """SELECT id, address, city FROM properties
               WHERE zip_code = ? AND status = ?
                 AND property_url LIKE '%redfin.com%'
               ORDER BY COALESCE(list_price, sold_price) DESC
               LIMIT ?""",
            (zip_code, scrape_status, scrape_limit),
        ).fetchall()
        conn.close()

        if rows:
            console.print(f"  Scraping {len(rows)} {scrape_status} properties...")
            success = 0
            for row in rows:
                if scrape_and_store(row["id"], delay=scrape_delay):
                    success += 1
            console.print(f"  [green]{scrape_status}: {success}/{len(rows)} scraped[/green]")
        else:
            console.print(f"  No Redfin {scrape_status} properties to scrape")

    # Step 3: Sync to Supabase
    console.print(f"\n[bold cyan]Step 3: Syncing to Supabase[/bold cyan]")
    conn = get_connection()
    _migrate_new_data_to_supabase(conn)
    conn.close()

    console.print(f"\n[bold green]Done with ZIP {zip_code}[/bold green]")


@click.command()
@click.option(
    "--zips", "-z", required=True,
    help="Comma-separated ZIP codes to ingest",
)
@click.option("--scrape-limit", "-n", default=50, help="Max properties to scrape history per ZIP")
@click.option("--scrape-delay", "-d", default=3.0, help="Delay between scrape requests (seconds)")
@click.option("--skip-history", is_flag=True, help="Skip price history scraping (faster)")
def main(zips: str, scrape_limit: int, scrape_delay: float, skip_history: bool):
    """Run the full ingestion pipeline for multiple ZIP codes."""
    init_db()

    zip_list = [z.strip() for z in zips.split(",") if z.strip()]
    console.print(f"[bold]Ingesting {len(zip_list)} ZIP codes: {', '.join(zip_list)}[/bold]")

    if skip_history:
        scrape_limit = 0

    start = time.time()
    for i, zip_code in enumerate(zip_list):
        console.print(f"\n[bold]>>> ZIP {i+1}/{len(zip_list)}: {zip_code} <<<[/bold]")
        ingest_zip(zip_code, scrape_limit, scrape_delay)

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    console.print(f"\n[bold green]All done! {len(zip_list)} ZIPs processed in {minutes}m {seconds}s[/bold green]")
    console.print(f"  Dashboard: https://supabase.com/dashboard/project/btwntyfjcendzmqwdoic/editor")


if __name__ == "__main__":
    main()
