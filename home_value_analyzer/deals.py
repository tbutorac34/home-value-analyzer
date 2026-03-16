"""Deal finder: score properties on likelihood of being a good deal."""

import re
from dataclasses import dataclass, field

import click
from rich.console import Console
from rich.table import Table

from .db import get_connection, init_db

console = Console()


@dataclass
class DealScore:
    property_id: int
    address: str
    city: str
    zip_code: str
    list_price: float
    sqft: int | None
    bedrooms: int | None
    bathrooms_total: float | None
    days_on_mls: int | None
    property_url: str | None
    estimated_value: float | None

    # Individual signal scores
    value_discount_score: int = 0       # 0-25
    price_drop_score: int = 0           # 0-20
    ppsf_vs_zip_score: int = 0          # 0-15
    dom_score: int = 0                  # 0-12
    flip_markup_score: int = 0          # 0-10
    sale_to_list_score: int = 0         # 0-8
    relist_score: int = 0               # 0-5
    description_score: int = 0          # 0-5

    total_score: int = 0
    grade: str = "F"

    # Context
    value_discount_pct: float | None = None
    num_price_drops: int = 0
    total_drop_pct: float | None = None
    original_list_price: float | None = None
    ppsf_vs_zip_pct: float | None = None
    dom_vs_market_ratio: float | None = None
    deal_notes: list[str] = field(default_factory=list)


# --- Keyword tiers for description scanning ---

KEYWORD_TIERS = {
    3: [
        "motivated seller", "seller motivated", "must sell", "priced to sell",
        "estate sale", "probate", "cash only",
        "as-is", "as is", "sold as-is", "sold as is", "reo",
    ],
    2: [
        "investor special", "investor opportunity", "investment opportunity",
        "sweat equity", "instant equity",
        "bring all offers", "all offers considered", "all offers",
        "make it your own", "bring your vision", "cosmetic",
        "vacant", "unoccupied",
    ],
    1: [
        "won't last", "wont last",
        "price reduced", "price improvement", "new price", "just reduced",
        "relocating", "relocation",
    ],
    -1: [
        "move-in ready", "move in ready", "turnkey",
    ],
}


def _check_description_signals(description: str | None) -> tuple[int, list[str]]:
    """Scan description for motivation keywords. Returns (score, matched_keywords)."""
    if not description:
        return 0, []

    text = description.lower()
    total = 0
    matched = []

    for points, keywords in KEYWORD_TIERS.items():
        for kw in keywords:
            if kw in text:
                total += points
                matched.append(f"{kw} ({'+' if points > 0 else ''}{points})")

    # Cap between -2 and 5
    return max(-2, min(5, total)), matched


def _get_zip_benchmarks(conn, zip_code: str) -> dict:
    """Compute benchmark stats for a ZIP code."""
    # Median price per sqft from active for-sale listings
    ppsf_rows = conn.execute(
        """SELECT price_per_sqft FROM properties
           WHERE zip_code = ? AND status = 'FOR_SALE'
             AND price_per_sqft IS NOT NULL
           ORDER BY price_per_sqft""",
        (zip_code,),
    ).fetchall()

    median_ppsf = None
    if len(ppsf_rows) >= 5:
        mid = len(ppsf_rows) // 2
        median_ppsf = ppsf_rows[mid]["price_per_sqft"]

    # Market stats from Redfin data
    market = conn.execute(
        """SELECT median_dom, avg_sale_to_list, median_ppsf
           FROM market_stats
           WHERE region_name LIKE ? AND region_type = 'zip'
           ORDER BY period DESC LIMIT 1""",
        (f"%{zip_code}%",),
    ).fetchone()

    median_dom = market["median_dom"] if market else None
    avg_stl = market["avg_sale_to_list"] if market else None

    # Use market median ppsf as fallback
    if median_ppsf is None and market and market["median_ppsf"]:
        median_ppsf = market["median_ppsf"]

    return {
        "median_ppsf": median_ppsf,
        "median_dom": median_dom,
        "avg_sale_to_list": avg_stl,
        "listing_count": len(ppsf_rows),
    }


def _get_price_drop_signals(conn, property_id: int, cutoff_date: str | None = None) -> dict:
    """Analyze price history for drop signals."""
    query = "SELECT * FROM price_history WHERE property_id = ? ORDER BY date ASC"
    rows = conn.execute(query, (property_id,)).fetchall()

    if not rows:
        return {
            "num_drops": 0,
            "total_drop_pct": None,
            "original_list_price": None,
            "has_relist": False,
        }

    # Find first Listed event (optionally after cutoff)
    first_list_price = None
    first_list_date = None
    num_drops = 0
    has_relist = False
    saw_pending_or_removed = False

    for row in rows:
        date = row["date"] or ""
        event = row["event"] or ""
        price = row["price"]

        if cutoff_date and date < cutoff_date:
            continue

        if event == "Listed" and price:
            if first_list_price is None:
                first_list_price = price
                first_list_date = date
            if saw_pending_or_removed:
                has_relist = True

        if event == "Price Changed":
            num_drops += 1

        if event in ("Pending", "Listing Removed", "Removed"):
            saw_pending_or_removed = True

    total_drop_pct = None
    if first_list_price and first_list_price > 0:
        # Get the current/latest price
        current_price = None
        for row in reversed(rows):
            if row["price"] and (not cutoff_date or (row["date"] or "") >= cutoff_date):
                current_price = row["price"]
                break
        if current_price:
            total_drop_pct = (first_list_price - current_price) / first_list_price

    return {
        "num_drops": num_drops,
        "total_drop_pct": total_drop_pct,
        "original_list_price": first_list_price,
        "has_relist": has_relist,
    }


def compute_deal_score(conn, property_id: int, benchmarks_cache: dict | None = None) -> DealScore | None:
    """Compute the full deal score for a single property."""
    prop = conn.execute("SELECT * FROM properties WHERE id = ?", (property_id,)).fetchone()
    if not prop or not prop["list_price"] or prop["list_price"] <= 0:
        return None

    score = DealScore(
        property_id=property_id,
        address=prop["address"],
        city=prop["city"] or "",
        zip_code=prop["zip_code"] or "",
        list_price=prop["list_price"],
        sqft=prop["sqft"],
        bedrooms=prop["bedrooms"],
        bathrooms_total=prop["bathrooms_total"],
        days_on_mls=prop["days_on_mls"],
        property_url=prop["property_url"],
        estimated_value=prop["estimated_value"],
    )

    # Get ZIP benchmarks (cached)
    if benchmarks_cache is None:
        benchmarks_cache = {}
    zip_code = prop["zip_code"] or ""
    if zip_code not in benchmarks_cache:
        benchmarks_cache[zip_code] = _get_zip_benchmarks(conn, zip_code)
    bench = benchmarks_cache[zip_code]

    # --- Signal 1: Price vs Estimated Value (0-25) ---
    if prop["estimated_value"] and prop["list_price"]:
        discount = (prop["estimated_value"] - prop["list_price"]) / prop["list_price"]
        score.value_discount_pct = round(discount * 100, 1)
        if discount >= 0.15:
            score.value_discount_score = 25
        elif discount >= 0.10:
            score.value_discount_score = 20
        elif discount >= 0.05:
            score.value_discount_score = 14
        elif discount >= 0.02:
            score.value_discount_score = 8
        elif discount >= 0.0:
            score.value_discount_score = 3

        if discount >= 0.05:
            score.deal_notes.append(f"{score.value_discount_pct:+.1f}% below estimate")

    # --- Signal 2: Price Drop History (0-20) ---
    drops = _get_price_drop_signals(conn, property_id)
    score.num_price_drops = drops["num_drops"]
    score.total_drop_pct = drops["total_drop_pct"]
    score.original_list_price = drops["original_list_price"]

    # Points for number of drops (0-10)
    if drops["num_drops"] >= 4:
        score.price_drop_score += 10
    elif drops["num_drops"] >= 3:
        score.price_drop_score += 8
    elif drops["num_drops"] >= 2:
        score.price_drop_score += 5
    elif drops["num_drops"] >= 1:
        score.price_drop_score += 2

    # Points for magnitude (0-10)
    if drops["total_drop_pct"] is not None:
        pct = drops["total_drop_pct"]
        if pct >= 0.15:
            score.price_drop_score += 10
        elif pct >= 0.10:
            score.price_drop_score += 8
        elif pct >= 0.05:
            score.price_drop_score += 5
        elif pct >= 0.02:
            score.price_drop_score += 2

    if drops["num_drops"] > 0:
        drop_note = f"{drops['num_drops']} price drop{'s' if drops['num_drops'] > 1 else ''}"
        if drops["total_drop_pct"]:
            drop_note += f" ({drops['total_drop_pct']*100:.0f}% total)"
        score.deal_notes.append(drop_note)

    # --- Signal 3: $/sqft vs ZIP Average (0-15) ---
    if prop["price_per_sqft"] and bench["median_ppsf"]:
        ppsf_discount = (bench["median_ppsf"] - prop["price_per_sqft"]) / bench["median_ppsf"]
        score.ppsf_vs_zip_pct = round(ppsf_discount * 100, 1)

        if ppsf_discount >= 0.20:
            score.ppsf_vs_zip_score = 15
        elif ppsf_discount >= 0.15:
            score.ppsf_vs_zip_score = 12
        elif ppsf_discount >= 0.10:
            score.ppsf_vs_zip_score = 8
        elif ppsf_discount >= 0.05:
            score.ppsf_vs_zip_score = 4

        if ppsf_discount >= 0.10:
            score.deal_notes.append(f"{score.ppsf_vs_zip_pct:.0f}% below ZIP $/sqft")

    # --- Signal 4: Days on Market (0-12) ---
    if prop["days_on_mls"] and bench["median_dom"] and bench["median_dom"] > 0:
        dom_ratio = prop["days_on_mls"] / bench["median_dom"]
        score.dom_vs_market_ratio = round(dom_ratio, 1)

        if dom_ratio >= 3.0:
            score.dom_score = 12
        elif dom_ratio >= 2.0:
            score.dom_score = 9
        elif dom_ratio >= 1.5:
            score.dom_score = 6
        elif dom_ratio >= 1.0:
            score.dom_score = 3

        if dom_ratio >= 1.5:
            score.deal_notes.append(f"{score.dom_vs_market_ratio}x market DOM")

    # --- Signal 5: List vs Last Sold Price (0-10) ---
    if prop["last_sold_price"] and prop["list_price"] and prop["last_sold_price"] > 0:
        markup = (prop["list_price"] - prop["last_sold_price"]) / prop["last_sold_price"]

        if markup >= 0.50:
            score.flip_markup_score = 10
            score.deal_notes.append(f"Flip: {markup*100:.0f}% markup from last sale")
        elif markup >= 0.30:
            score.flip_markup_score = 6
        elif markup <= 0.05:
            score.flip_markup_score = 4
            score.deal_notes.append("Barely marked up from last sale")

    # --- Signal 6: Area Sale-to-List Ratio (0-8) ---
    if bench["avg_sale_to_list"]:
        stl = bench["avg_sale_to_list"]
        if stl < 0.95:
            score.sale_to_list_score = 8
        elif stl < 0.97:
            score.sale_to_list_score = 5
        elif stl < 0.99:
            score.sale_to_list_score = 3

    # --- Signal 7: Relist Detection (0-5) ---
    if drops["has_relist"]:
        if drops["original_list_price"] and prop["list_price"] < drops["original_list_price"]:
            score.relist_score = 5
            score.deal_notes.append("Relisted at lower price")
        else:
            score.relist_score = 2
            score.deal_notes.append("Relisted")

    # --- Signal 8: Description Keywords (0-5) ---
    desc_pts, desc_matches = _check_description_signals(prop["description"])
    score.description_score = max(0, desc_pts)  # floor at 0 for total, but note negatives
    if desc_matches:
        score.deal_notes.append(f"Keywords: {', '.join(desc_matches[:3])}")

    # --- Total and Grade ---
    score.total_score = (
        score.value_discount_score
        + score.price_drop_score
        + score.ppsf_vs_zip_score
        + score.dom_score
        + score.flip_markup_score
        + score.sale_to_list_score
        + score.relist_score
        + score.description_score
    )

    # Apply negative description modifier after total
    if desc_pts < 0:
        score.total_score = max(0, score.total_score + desc_pts)

    if score.total_score >= 75:
        score.grade = "A"
    elif score.total_score >= 60:
        score.grade = "B"
    elif score.total_score >= 45:
        score.grade = "C"
    elif score.total_score >= 30:
        score.grade = "D"
    else:
        score.grade = "F"

    return score


def find_deals(
    zip_codes: list[str] | None = None,
    min_score: int = 0,
    limit: int = 50,
    min_price: float | None = None,
    max_price: float | None = None,
    min_beds: int | None = None,
    status: str = "FOR_SALE",
) -> list[DealScore]:
    """Score all properties matching filters, return sorted by score descending."""
    conn = get_connection()

    query = """SELECT id FROM properties
               WHERE status = ? AND list_price IS NOT NULL AND list_price > 0"""
    params: list = [status]

    if zip_codes:
        placeholders = ",".join("?" for _ in zip_codes)
        query += f" AND zip_code IN ({placeholders})"
        params.extend(zip_codes)
    if min_price:
        query += " AND list_price >= ?"
        params.append(min_price)
    if max_price:
        query += " AND list_price <= ?"
        params.append(max_price)
    if min_beds:
        query += " AND bedrooms >= ?"
        params.append(min_beds)

    rows = conn.execute(query, params).fetchall()

    benchmarks_cache = {}
    deals = []

    for row in rows:
        score = compute_deal_score(conn, row["id"], benchmarks_cache)
        if score and score.total_score >= min_score:
            deals.append(score)

    conn.close()

    deals.sort(key=lambda d: d.total_score, reverse=True)
    return deals[:limit]


def display_deals(deals: list[DealScore], title: str = "Deal Finder") -> None:
    """Display ranked deals in a Rich table."""
    if not deals:
        console.print("[yellow]No deals found matching criteria.[/yellow]")
        return

    table = Table(title=title)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Grade", justify="center")
    table.add_column("Score", justify="right")
    table.add_column("Address", max_width=35)
    table.add_column("ZIP")
    table.add_column("Price", justify="right")
    table.add_column("$/sqft", justify="right")
    table.add_column("Bed/Bath")
    table.add_column("DOM", justify="right")
    table.add_column("Key Signals", max_width=45)

    grade_colors = {"A": "bold green", "B": "green", "C": "yellow", "D": "dim", "F": "red"}

    for i, deal in enumerate(deals, 1):
        grade_style = grade_colors.get(deal.grade, "")
        baths = deal.bathrooms_total or "?"
        notes = "; ".join(deal.deal_notes[:3]) if deal.deal_notes else "-"

        table.add_row(
            str(i),
            f"[{grade_style}]{deal.grade}[/{grade_style}]",
            f"[{grade_style}]{deal.total_score}[/{grade_style}]",
            deal.address[:35],
            deal.zip_code,
            f"${deal.list_price:,.0f}",
            f"${deal.list_price / deal.sqft:,.0f}" if deal.sqft else "N/A",
            f"{deal.bedrooms or '?'}/{baths}",
            str(deal.days_on_mls) if deal.days_on_mls is not None else "N/A",
            notes,
        )

    console.print(table)
    console.print(f"\n  {len(deals)} properties scored")


def display_deal_detail(deal: DealScore) -> None:
    """Display detailed breakdown for a single property."""
    console.print()
    console.print(f"[bold]Deal Analysis: {deal.address}[/bold]")
    console.print("=" * 60)

    console.print(f"  List Price:       ${deal.list_price:>12,.0f}")
    if deal.estimated_value:
        console.print(f"  Estimated Value:  ${deal.estimated_value:>12,.0f}  ({deal.value_discount_pct:+.1f}%)")
    if deal.sqft:
        console.print(f"  $/sqft:           ${deal.list_price / deal.sqft:>12,.0f}")
    console.print(f"  Beds/Baths:       {deal.bedrooms or '?'}/{deal.bathrooms_total or '?'}")
    if deal.days_on_mls is not None:
        console.print(f"  Days on Market:   {deal.days_on_mls}")

    console.print()
    console.print(f"  [bold]Score: {deal.total_score}/100  (Grade {deal.grade})[/bold]")
    console.print()

    # Signal breakdown with bars
    signals = [
        ("Value Discount", deal.value_discount_score, 25),
        ("Price Drops", deal.price_drop_score, 20),
        ("$/sqft vs ZIP", deal.ppsf_vs_zip_score, 15),
        ("Days on Market", deal.dom_score, 12),
        ("Flip Detection", deal.flip_markup_score, 10),
        ("Sale-to-List", deal.sale_to_list_score, 8),
        ("Relist", deal.relist_score, 5),
        ("Description", deal.description_score, 5),
    ]

    for name, pts, max_pts in signals:
        bar_width = 25
        filled = int((pts / max_pts) * bar_width) if max_pts > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)
        color = "green" if pts >= max_pts * 0.6 else "yellow" if pts > 0 else "dim"
        console.print(f"  {name:20s} {pts:2d}/{max_pts:2d}  [{color}]{bar}[/{color}]")

    if deal.deal_notes:
        console.print()
        console.print("  [bold]Notes:[/bold]")
        for note in deal.deal_notes:
            console.print(f"    - {note}")

    if deal.property_url:
        console.print(f"\n  URL: {deal.property_url}")


@click.command()
@click.option("--zips", "-z", default=None, help="Comma-separated ZIP codes (default: all)")
@click.option("--min-score", "-m", default=0, type=int, help="Minimum deal score to show")
@click.option("--grade", "-g", default=None, type=click.Choice(["A", "B", "C", "D", "F"]), help="Filter by grade")
@click.option("--limit", "-n", default=30, type=int, help="Max results")
@click.option("--min-price", default=None, type=float, help="Minimum list price")
@click.option("--max-price", default=None, type=float, help="Maximum list price")
@click.option("--min-beds", default=None, type=int, help="Minimum bedrooms")
@click.option("--detail", "-d", default=None, type=int, help="Show detailed breakdown for property ID")
@click.option("--status", "-s", default="FOR_SALE", help="Property status filter")
def main(zips, min_score, grade, limit, min_price, max_price, min_beds, detail, status):
    """Find the best deals among listed properties."""
    init_db()

    if detail:
        conn = get_connection()
        deal = compute_deal_score(conn, detail)
        conn.close()
        if deal:
            display_deal_detail(deal)
        else:
            console.print(f"[red]Property {detail} not found or has no list price[/red]")
        return

    grade_min = {"A": 75, "B": 60, "C": 45, "D": 30, "F": 0}
    if grade:
        min_score = max(min_score, grade_min[grade])

    zip_list = [z.strip() for z in zips.split(",")] if zips else None

    deals = find_deals(
        zip_codes=zip_list,
        min_score=min_score,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        min_beds=min_beds,
        status=status,
    )

    zip_label = ", ".join(zip_list) if zip_list else "all ZIPs"
    display_deals(deals, title=f"Deal Finder: {zip_label}")


if __name__ == "__main__":
    main()
