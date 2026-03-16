"""Export database contents to CSV files."""

from pathlib import Path

import click
import pandas as pd
from rich.console import Console

from .db import get_connection, init_db

console = Console()

DEFAULT_EXPORT_DIR = Path(__file__).parent.parent / "data" / "exports"


def export_properties(
    output_dir: Path = DEFAULT_EXPORT_DIR,
    zip_code: str | None = None,
    listing_type: str | None = None,
) -> Path:
    """Export properties data to CSV."""
    init_db()
    conn = get_connection()

    query = "SELECT * FROM properties WHERE 1=1"
    params: list = []

    if zip_code:
        query += " AND zip_code = ?"
        params.append(zip_code)
    if listing_type:
        status_map = {"for_sale": "FOR_SALE", "sold": "SOLD", "pending": "PENDING"}
        query += " AND status = ?"
        params.append(status_map.get(listing_type, listing_type.upper()))

    query += " ORDER BY zip_code, COALESCE(sold_price, list_price) DESC"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        console.print("[yellow]No data to export.[/yellow]")
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    parts = ["properties"]
    if zip_code:
        parts.append(zip_code)
    if listing_type:
        parts.append(listing_type)
    filename = "_".join(parts) + ".csv"
    filepath = output_dir / filename

    df.to_csv(filepath, index=False)
    console.print(f"[bold green]Exported {len(df)} rows to {filepath}[/bold green]")
    return filepath


def export_market_stats(
    output_dir: Path = DEFAULT_EXPORT_DIR,
    region_type: str | None = None,
    region_filter: str | None = None,
) -> Path:
    """Export market statistics to CSV."""
    init_db()
    conn = get_connection()

    query = "SELECT * FROM market_stats WHERE 1=1"
    params: list = []

    if region_type:
        query += " AND region_type = ?"
        params.append(region_type)
    if region_filter:
        query += " AND region_name LIKE ?"
        params.append(f"%{region_filter}%")

    query += " ORDER BY region_name, period DESC"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        console.print("[yellow]No market data to export.[/yellow]")
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    parts = ["market_stats"]
    if region_filter:
        parts.append(region_filter)
    filename = "_".join(parts) + ".csv"
    filepath = output_dir / filename

    df.to_csv(filepath, index=False)
    console.print(f"[bold green]Exported {len(df)} rows to {filepath}[/bold green]")
    return filepath


def export_price_history(
    output_dir: Path = DEFAULT_EXPORT_DIR,
    zip_code: str | None = None,
) -> Path:
    """Export price history to CSV."""
    init_db()
    conn = get_connection()

    query = """
        SELECT ph.*, p.address, p.city, p.zip_code
        FROM price_history ph
        JOIN properties p ON p.id = ph.property_id
        WHERE 1=1
    """
    params: list = []

    if zip_code:
        query += " AND p.zip_code = ?"
        params.append(zip_code)

    query += " ORDER BY p.address, ph.date"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        console.print("[yellow]No price history to export.[/yellow]")
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    parts = ["price_history"]
    if zip_code:
        parts.append(zip_code)
    filename = "_".join(parts) + ".csv"
    filepath = output_dir / filename

    df.to_csv(filepath, index=False)
    console.print(f"[bold green]Exported {len(df)} rows to {filepath}[/bold green]")
    return filepath


@click.command()
@click.option("--type", "export_type", type=click.Choice(["properties", "market", "history", "all"]), default="all")
@click.option("--zip", "zip_code", default=None, help="Filter to ZIP code")
@click.option("--listing-type", "-t", default=None, help="Filter to listing type")
@click.option("--output-dir", "-o", default=None, type=click.Path(), help="Output directory")
def main(export_type: str, zip_code: str | None, listing_type: str | None, output_dir: str | None):
    """Export data to CSV files."""
    out = Path(output_dir) if output_dir else DEFAULT_EXPORT_DIR

    if export_type in ("properties", "all"):
        export_properties(out, zip_code, listing_type)
    if export_type in ("market", "all"):
        export_market_stats(out, region_filter=zip_code)
    if export_type in ("history", "all"):
        export_price_history(out, zip_code)


if __name__ == "__main__":
    main()
