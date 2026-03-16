"""Migrate data from local SQLite to Supabase."""

import os
import sqlite3
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from supabase import create_client

console = Console()

SQLITE_PATH = Path(__file__).parent.parent / "data" / "home_values.db"


def _load_supabase():
    load_dotenv(Path(__file__).parent.parent / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        console.print("[red]Set SUPABASE_URL and SUPABASE_KEY in .env[/red]")
        raise SystemExit(1)
    return create_client(url, key)


def _sqlite_rows_as_dicts(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Read all rows from a SQLite table as list of dicts."""
    cursor = conn.execute(f"SELECT * FROM {table}")
    columns = [desc[0] for desc in cursor.description]
    rows = []
    for row in cursor.fetchall():
        d = {}
        for col, val in zip(columns, row):
            if col == "id":
                continue  # Let Supabase generate IDs
            if val is not None:
                d[col] = val
        rows.append(d)
    return rows


def migrate_properties(sb, conn: sqlite3.Connection) -> dict[int, int]:
    """Migrate properties table. Returns mapping of old_id -> new_id."""
    console.print("[bold]Migrating properties...[/bold]")

    cursor = conn.execute("SELECT * FROM properties ORDER BY id")
    columns = [desc[0] for desc in cursor.description]
    all_rows = cursor.fetchall()

    id_map = {}
    batch_size = 50
    total = len(all_rows)

    for i in range(0, total, batch_size):
        batch_raw = all_rows[i : i + batch_size]
        batch = []
        old_ids = []

        for row in batch_raw:
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

        result = sb.table("properties").insert(batch).execute()

        for old_id, new_row in zip(old_ids, result.data):
            id_map[old_id] = new_row["id"]

        console.print(f"  Properties: {min(i + batch_size, total)}/{total}")

    console.print(f"[green]  Migrated {total} properties[/green]")
    return id_map


def migrate_price_history(sb, conn: sqlite3.Connection, id_map: dict[int, int]):
    """Migrate price_history table with remapped property IDs."""
    console.print("[bold]Migrating price history...[/bold]")

    rows = _sqlite_rows_as_dicts(conn, "price_history")
    if not rows:
        console.print("  No price history to migrate")
        return

    # Remap property_id
    mapped = []
    for row in rows:
        old_pid = row.get("property_id")
        if old_pid not in id_map:
            continue
        row["property_id"] = id_map[old_pid]
        mapped.append(row)

    batch_size = 100
    total = len(mapped)
    for i in range(0, total, batch_size):
        batch = mapped[i : i + batch_size]
        sb.table("price_history").insert(batch).execute()
        console.print(f"  Price history: {min(i + batch_size, total)}/{total}")

    console.print(f"[green]  Migrated {total} price history events[/green]")


def migrate_tax_history(sb, conn: sqlite3.Connection, id_map: dict[int, int]):
    """Migrate tax_history table with remapped property IDs."""
    console.print("[bold]Migrating tax history...[/bold]")

    rows = _sqlite_rows_as_dicts(conn, "tax_history")
    if not rows:
        console.print("  No tax history to migrate")
        return

    mapped = []
    for row in rows:
        old_pid = row.get("property_id")
        if old_pid not in id_map:
            continue
        row["property_id"] = id_map[old_pid]
        mapped.append(row)

    if mapped:
        sb.table("tax_history").insert(mapped).execute()

    console.print(f"[green]  Migrated {len(mapped)} tax history records[/green]")


def migrate_market_stats(sb, conn: sqlite3.Connection):
    """Migrate market_stats table."""
    console.print("[bold]Migrating market stats...[/bold]")

    rows = _sqlite_rows_as_dicts(conn, "market_stats")
    if not rows:
        console.print("  No market stats to migrate")
        return

    batch_size = 200
    total = len(rows)
    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        sb.table("market_stats").insert(batch).execute()
        console.print(f"  Market stats: {min(i + batch_size, total)}/{total}")

    console.print(f"[green]  Migrated {total} market stat rows[/green]")


@click.command()
@click.option("--sqlite-path", default=str(SQLITE_PATH), help="Path to SQLite database")
def main(sqlite_path: str):
    """Migrate all data from SQLite to Supabase."""
    sb = _load_supabase()

    conn = sqlite3.connect(sqlite_path)

    # Check if Supabase tables are empty
    existing = sb.table("properties").select("id", count="exact").limit(1).execute()
    if existing.count and existing.count > 0:
        console.print(f"[yellow]Supabase already has {existing.count} properties.[/yellow]")
        if not click.confirm("Clear and re-migrate?"):
            return
        console.print("Clearing existing data...")
        sb.table("price_history").delete().neq("id", 0).execute()
        sb.table("tax_history").delete().neq("id", 0).execute()
        sb.table("market_stats").delete().neq("id", 0).execute()
        sb.table("properties").delete().neq("id", 0).execute()

    id_map = migrate_properties(sb, conn)
    migrate_price_history(sb, conn, id_map)
    migrate_tax_history(sb, conn, id_map)
    migrate_market_stats(sb, conn)

    conn.close()

    console.print("\n[bold green]Migration complete![/bold green]")
    console.print(f"  Dashboard: https://supabase.com/dashboard/project/btwntyfjcendzmqwdoic/editor")


if __name__ == "__main__":
    main()
