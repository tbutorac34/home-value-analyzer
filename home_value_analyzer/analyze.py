"""Analyze properties: find comps, estimate fair value, score listings."""

import math
from dataclasses import dataclass

import click
from rich.console import Console
from rich.table import Table

from .db import get_connection, init_db

console = Console()


@dataclass
class CompResult:
    property_id: int
    address: str
    sold_price: float
    sqft: int
    price_per_sqft: float
    bedrooms: int
    bathrooms_total: float
    year_built: int
    sold_date: str
    distance_miles: float
    similarity_score: float


@dataclass
class ValuationResult:
    subject_address: str
    list_price: float | None
    estimated_value: float
    comp_based_value: float
    ppsf_based_value: float
    source_estimate: float | None
    num_comps: int
    comps: list[CompResult]
    market_assessment: str
    value_assessment: str
    confidence: str


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles."""
    R = 3959
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def find_comps(
    property_id: int,
    max_distance_miles: float = 1.0,
    max_results: int = 10,
    sqft_tolerance: float = 0.25,
) -> list[CompResult]:
    """Find comparable sold properties for a given property."""
    conn = get_connection()

    subject = conn.execute(
        "SELECT * FROM properties WHERE id = ?", (property_id,)
    ).fetchone()

    if not subject:
        console.print(f"[red]Property {property_id} not found[/red]")
        return []

    # Get all sold properties
    if subject["latitude"] and subject["longitude"]:
        rows = conn.execute(
            """SELECT * FROM properties
               WHERE status = 'SOLD'
                 AND sold_price IS NOT NULL
                 AND id != ?
                 AND latitude IS NOT NULL
               ORDER BY sold_date DESC""",
            (property_id,),
        ).fetchall()
    else:
        sqft = subject["sqft"] or 1500
        min_sqft = int(sqft * (1 - sqft_tolerance))
        max_sqft = int(sqft * (1 + sqft_tolerance))
        rows = conn.execute(
            """SELECT * FROM properties
               WHERE status = 'SOLD'
                 AND sold_price IS NOT NULL
                 AND zip_code = ?
                 AND id != ?
                 AND sqft BETWEEN ? AND ?
               ORDER BY sold_date DESC
               LIMIT ?""",
            (subject["zip_code"], property_id, min_sqft, max_sqft, max_results * 3),
        ).fetchall()

    comps = []
    for row in rows:
        if subject["latitude"] and row["latitude"]:
            dist = _haversine_miles(
                subject["latitude"], subject["longitude"],
                row["latitude"], row["longitude"],
            )
        else:
            dist = 0.0

        if dist > max_distance_miles:
            continue

        # Similarity scoring
        score = 100.0

        # Distance penalty
        score -= (dist / max_distance_miles) * 20

        # Sqft similarity
        if subject["sqft"] and row["sqft"]:
            sqft_diff = abs(subject["sqft"] - row["sqft"]) / subject["sqft"]
            if sqft_diff > sqft_tolerance:
                continue
            score -= sqft_diff * 30

        # Bedroom match
        if subject["bedrooms"] and row["bedrooms"]:
            bed_diff = abs(subject["bedrooms"] - row["bedrooms"])
            score -= bed_diff * 10

        # Bathroom match
        if subject["bathrooms_total"] and row["bathrooms_total"]:
            bath_diff = abs(subject["bathrooms_total"] - row["bathrooms_total"])
            score -= bath_diff * 5

        # Year built similarity
        if subject["year_built"] and row["year_built"]:
            age_diff = abs(subject["year_built"] - row["year_built"])
            score -= min(age_diff * 0.5, 15)

        # Property type match
        if subject["property_type"] and row["property_type"]:
            if subject["property_type"] != row["property_type"]:
                score -= 25

        comps.append(CompResult(
            property_id=row["id"],
            address=row["address"],
            sold_price=row["sold_price"],
            sqft=row["sqft"] or 0,
            price_per_sqft=row["price_per_sqft"] or 0,
            bedrooms=row["bedrooms"] or 0,
            bathrooms_total=row["bathrooms_total"] or 0,
            year_built=row["year_built"] or 0,
            sold_date=row["sold_date"] or "",
            distance_miles=round(dist, 2),
            similarity_score=round(max(score, 0), 1),
        ))

    comps.sort(key=lambda c: c.similarity_score, reverse=True)
    conn.close()
    return comps[:max_results]


def estimate_value(property_id: int) -> ValuationResult | None:
    """Estimate the fair market value of a property using comps and market data."""
    conn = get_connection()

    subject = conn.execute(
        "SELECT * FROM properties WHERE id = ?", (property_id,)
    ).fetchone()

    if not subject:
        console.print(f"[red]Property {property_id} not found[/red]")
        return None

    comps = find_comps(property_id)

    if not comps:
        console.print("[yellow]No comparable sales found[/yellow]")
        return None

    # Method 1: Weighted average of comp prices
    total_weight = sum(c.similarity_score for c in comps)
    if total_weight > 0:
        comp_based_value = sum(
            c.sold_price * c.similarity_score for c in comps
        ) / total_weight
    else:
        comp_based_value = sum(c.sold_price for c in comps) / len(comps)

    # Method 2: Price-per-sqft from comps
    ppsf_values = [c.price_per_sqft for c in comps if c.price_per_sqft > 0]
    if ppsf_values and subject["sqft"]:
        median_ppsf = sorted(ppsf_values)[len(ppsf_values) // 2]
        ppsf_based_value = median_ppsf * subject["sqft"]
    else:
        ppsf_based_value = comp_based_value

    # Blend
    estimated_value = round((comp_based_value * 0.6 + ppsf_based_value * 0.4), -2)

    # Source estimate (Zestimate-like)
    source_estimate = subject["estimated_value"]

    # Market conditions
    market_stats = conn.execute(
        """SELECT * FROM market_stats
           WHERE region_name LIKE ? AND region_type = 'zip'
           ORDER BY period DESC LIMIT 1""",
        (f"%{subject['zip_code']}%",) if subject["zip_code"] else ("%",),
    ).fetchone()

    if market_stats and market_stats["months_of_supply"]:
        mos = market_stats["months_of_supply"]
        market_assessment = "hot" if mos < 3 else "cold" if mos > 6 else "balanced"
    elif market_stats and market_stats["avg_sale_to_list"]:
        stl = market_stats["avg_sale_to_list"]
        market_assessment = "hot" if stl > 1.0 else "cold" if stl < 0.95 else "balanced"
    else:
        market_assessment = "unknown"

    # Value assessment
    list_price = subject["list_price"]
    if list_price and list_price > 0:
        ratio = estimated_value / list_price
        if ratio > 1.05:
            value_assessment = "undervalued"
        elif ratio < 0.95:
            value_assessment = "overvalued"
        else:
            value_assessment = "fair"
    else:
        value_assessment = "unknown"

    # Confidence
    avg_similarity = sum(c.similarity_score for c in comps) / len(comps) if comps else 0
    if len(comps) >= 5 and avg_similarity > 70:
        confidence = "high"
    elif len(comps) >= 3 and avg_similarity > 50:
        confidence = "medium"
    else:
        confidence = "low"

    conn.close()

    return ValuationResult(
        subject_address=subject["address"],
        list_price=list_price,
        estimated_value=estimated_value,
        comp_based_value=round(comp_based_value, -2),
        ppsf_based_value=round(ppsf_based_value, -2),
        source_estimate=source_estimate,
        num_comps=len(comps),
        comps=comps,
        market_assessment=market_assessment,
        value_assessment=value_assessment,
        confidence=confidence,
    )


def display_valuation(result: ValuationResult) -> None:
    """Pretty-print a valuation result."""
    console.print()
    console.print(f"[bold]Valuation: {result.subject_address}[/bold]")
    console.print("=" * 60)

    if result.list_price:
        console.print(f"  List Price:         ${result.list_price:>12,.0f}")
    console.print(f"  Estimated Value:    ${result.estimated_value:>12,.0f}")
    console.print(f"    Comp-based:       ${result.comp_based_value:>12,.0f}")
    console.print(f"    PPSF-based:       ${result.ppsf_based_value:>12,.0f}")
    if result.source_estimate:
        console.print(f"    Source estimate:  ${result.source_estimate:>12,.0f}")

    if result.list_price and result.list_price > 0:
        diff = result.estimated_value - result.list_price
        pct = (diff / result.list_price) * 100
        color = "green" if diff > 0 else "red"
        console.print(f"  Difference:         [{color}]${diff:>+12,.0f} ({pct:+.1f}%)[/{color}]")

    console.print(f"  Market:             {result.market_assessment}")
    console.print(f"  Assessment:         [bold]{result.value_assessment}[/bold]")
    console.print(f"  Confidence:         {result.confidence} ({result.num_comps} comps)")

    # Comps table
    console.print()
    table = Table(title="Comparable Sales")
    table.add_column("Address", max_width=30)
    table.add_column("Sold Price", justify="right")
    table.add_column("$/sqft", justify="right")
    table.add_column("Sqft", justify="right")
    table.add_column("Bed/Bath")
    table.add_column("Dist (mi)", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Sold Date")

    for comp in result.comps[:10]:
        table.add_row(
            comp.address[:30],
            f"${comp.sold_price:,.0f}",
            f"${comp.price_per_sqft:,.0f}" if comp.price_per_sqft else "N/A",
            f"{comp.sqft:,}" if comp.sqft else "N/A",
            f"{comp.bedrooms}/{comp.bathrooms_total}",
            f"{comp.distance_miles:.2f}",
            f"{comp.similarity_score:.0f}",
            comp.sold_date[:10] if comp.sold_date else "N/A",
        )

    console.print(table)


@click.command()
@click.option("--address", "-a", default=None, help="Address to look up in the database")
@click.option("--property-id", "-id", default=None, type=int, help="Property ID in the database")
@click.option("--radius", "-r", default=1.0, type=float, help="Max comp distance in miles")
@click.option("--max-comps", "-n", default=10, type=int, help="Max number of comps")
def main(address: str | None, property_id: int | None, radius: float, max_comps: int):
    """Analyze a property's fair market value."""
    init_db()
    conn = get_connection()

    if property_id:
        pass
    elif address:
        row = conn.execute(
            "SELECT id FROM properties WHERE address LIKE ?",
            (f"%{address}%",),
        ).fetchone()
        if not row:
            console.print(f"[red]No property found matching '{address}'[/red]")
            console.print("Try ingesting listings first with: python -m home_value_analyzer ingest")
            return
        property_id = row["id"]
    else:
        console.print("[red]Provide --address or --property-id[/red]")
        return

    conn.close()
    result = estimate_value(property_id)
    if result:
        display_valuation(result)


if __name__ == "__main__":
    main()
