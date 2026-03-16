"""Market condition analysis and reporting."""

import click
from rich.console import Console
from rich.table import Table

from .db import get_connection, init_db

console = Console()


def get_market_summary(zip_code: str | None = None, city: str | None = None) -> None:
    """Display market condition summary for a region."""
    init_db()
    conn = get_connection()

    if zip_code:
        rows = conn.execute(
            """SELECT * FROM market_stats
               WHERE region_name LIKE ? AND region_type = 'zip'
               ORDER BY period DESC LIMIT 12""",
            (f"%{zip_code}%",),
        ).fetchall()
        region_label = f"ZIP {zip_code}"
    elif city:
        rows = conn.execute(
            """SELECT * FROM market_stats
               WHERE region_name LIKE ? AND region_type = 'city'
               ORDER BY period DESC LIMIT 12""",
            (f"%{city}%",),
        ).fetchall()
        region_label = city
    else:
        console.print("[red]Provide --zip or --city[/red]")
        return

    if not rows:
        console.print(f"[yellow]No market data found for {region_label}[/yellow]")
        console.print("Try ingesting market data first:")
        console.print("  python -m home_value_analyzer ingest-market --region-type zip --region <zip>")
        return

    console.print()
    console.print(f"[bold]Market Summary: {region_label}[/bold]")
    console.print("=" * 80)

    latest = rows[0]

    console.print()
    console.print("[bold]Current Conditions[/bold]")

    if latest["median_sale_price"]:
        console.print(f"  Median Sale Price:     ${latest['median_sale_price']:>12,.0f}")
    if latest["median_list_price"]:
        console.print(f"  Median List Price:     ${latest['median_list_price']:>12,.0f}")
    if latest["median_ppsf"]:
        console.print(f"  Median $/sqft:         ${latest['median_ppsf']:>12,.0f}")
    if latest["median_dom"] is not None:
        dom = latest["median_dom"]
        speed = "fast" if dom < 20 else "moderate" if dom < 45 else "slow"
        console.print(f"  Median Days on Market: {dom:>12} ({speed})")
    if latest["months_of_supply"]:
        mos = latest["months_of_supply"]
        if mos < 3:
            market_type = "strong seller's market"
        elif mos < 5:
            market_type = "seller's market"
        elif mos <= 7:
            market_type = "balanced"
        else:
            market_type = "buyer's market"
        console.print(f"  Months of Supply:      {mos:>12.1f} ({market_type})")
    if latest["avg_sale_to_list"]:
        stl = latest["avg_sale_to_list"]
        console.print(f"  Sale-to-List Ratio:    {stl:>12.1%}")
    if latest["active_listings"] is not None:
        console.print(f"  Active Listings:       {latest['active_listings']:>12,}")
    if latest["pct_price_drops"] is not None:
        console.print(f"  % with Price Drops:    {latest['pct_price_drops']:>11.1f}%")

    if len(rows) > 1:
        console.print()
        table = Table(title="Recent Trends")
        table.add_column("Period")
        table.add_column("Med. Sale Price", justify="right")
        table.add_column("Med. $/sqft", justify="right")
        table.add_column("DOM", justify="right")
        table.add_column("Supply (mo)", justify="right")
        table.add_column("Sale/List", justify="right")
        table.add_column("Listings", justify="right")

        for row in rows:
            table.add_row(
                row["period"],
                f"${row['median_sale_price']:,.0f}" if row["median_sale_price"] else "N/A",
                f"${row['median_ppsf']:,.0f}" if row["median_ppsf"] else "N/A",
                str(row["median_dom"]) if row["median_dom"] is not None else "N/A",
                f"{row['months_of_supply']:.1f}" if row["months_of_supply"] else "N/A",
                f"{row['avg_sale_to_list']:.1%}" if row["avg_sale_to_list"] else "N/A",
                f"{row['active_listings']:,}" if row["active_listings"] is not None else "N/A",
            )

        console.print(table)

        if len(rows) >= 12:
            current_price = rows[0]["median_sale_price"]
            year_ago_price = rows[11]["median_sale_price"]
            if current_price and year_ago_price:
                yoy = ((current_price - year_ago_price) / year_ago_price) * 100
                color = "green" if yoy > 0 else "red"
                console.print(f"\n  YoY Price Change: [{color}]{yoy:+.1f}%[/{color}]")

    conn.close()


def list_properties(
    zip_code: str | None = None,
    listing_type: str = "for_sale",
    sort_by: str = "price_per_sqft",
    limit: int = 25,
) -> None:
    """List properties in the database with key metrics."""
    init_db()
    conn = get_connection()

    status_map = {
        "for_sale": "FOR_SALE",
        "sold": "SOLD",
        "pending": "PENDING",
    }
    status = status_map.get(listing_type, listing_type.upper())

    query = "SELECT * FROM properties WHERE status = ?"
    params: list = [status]

    if zip_code:
        query += " AND zip_code = ?"
        params.append(zip_code)

    order_col = {
        "price_per_sqft": "price_per_sqft",
        "price": "COALESCE(sold_price, list_price)",
        "dom": "days_on_mls",
        "sqft": "sqft",
    }.get(sort_by, "price_per_sqft")

    query += f" ORDER BY {order_col} ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    if not rows:
        console.print("[yellow]No properties found. Try ingesting listings first.[/yellow]")
        return

    table = Table(title=f"{listing_type.replace('_', ' ').title()} Properties")
    table.add_column("ID", justify="right")
    table.add_column("Address", max_width=40)
    table.add_column("City")
    table.add_column("Price", justify="right")
    table.add_column("$/sqft", justify="right")
    table.add_column("Sqft", justify="right")
    table.add_column("Bed/Bath")
    table.add_column("Year")
    table.add_column("DOM", justify="right")
    table.add_column("Est. Value", justify="right")

    for row in rows:
        price = row["sold_price"] or row["list_price"]
        baths = row["bathrooms_total"] or row["full_baths"] or "?"
        table.add_row(
            str(row["id"]),
            row["address"][:40] if row["address"] else "N/A",
            row["city"] or "N/A",
            f"${price:,.0f}" if price else "N/A",
            f"${row['price_per_sqft']:,.0f}" if row["price_per_sqft"] else "N/A",
            f"{row['sqft']:,}" if row["sqft"] else "N/A",
            f"{row['bedrooms'] or '?'}/{baths}",
            str(row["year_built"]) if row["year_built"] else "N/A",
            str(row["days_on_mls"]) if row["days_on_mls"] is not None else "N/A",
            f"${row['estimated_value']:,.0f}" if row["estimated_value"] else "N/A",
        )

    console.print(table)
    conn.close()


@click.command()
@click.option("--zip", "zip_code", default=None, help="ZIP code to analyze")
@click.option("--city", default=None, help="City name to analyze")
@click.option("--list", "list_props", is_flag=True, help="List properties instead of market summary")
@click.option(
    "--listing-type",
    "-t",
    type=click.Choice(["for_sale", "sold", "pending"]),
    default="for_sale",
)
@click.option("--sort", default="price_per_sqft", help="Sort by: price_per_sqft, price, dom, sqft")
@click.option("--limit", "-n", default=25, type=int)
def main(zip_code, city, list_props, listing_type, sort, limit):
    """View market conditions and property listings."""
    if list_props:
        list_properties(zip_code, listing_type, sort, limit)
    else:
        get_market_summary(zip_code, city)


if __name__ == "__main__":
    main()
