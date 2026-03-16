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
    bathrooms: float
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
    num_comps: int
    comps: list[CompResult]
    market_assessment: str  # 'hot', 'balanced', 'cold'
    value_assessment: str   # 'undervalued', 'fair', 'overvalued'
    confidence: str         # 'low', 'medium', 'high'


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles."""
    R = 3959  # Earth radius in miles
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def find_comps(
    property_id: int,
    max_distance_miles: float = 0.5,
    max_age_days: int = 180,
    max_results: int = 10,
    sqft_tolerance: float = 0.2,
) -> list[CompResult]:
    """Find comparable sold properties for a given property."""
    conn = get_connection()

    subject = conn.execute(
        """SELECT p.*, s.list_price, s.sold_price
           FROM properties p
           LEFT JOIN sales s ON s.property_id = p.id
           WHERE p.id = ?""",
        (property_id,),
    ).fetchone()

    if not subject:
        console.print(f"[red]Property {property_id} not found[/red]")
        return []

    if not subject["latitude"] or not subject["longitude"]:
        console.print("[yellow]Subject property has no coordinates, using ZIP-based comps[/yellow]")
        comps_query = """
            SELECT p.*, s.sold_price, s.sold_date, s.price_per_sqft
            FROM properties p
            JOIN sales s ON s.property_id = p.id
            WHERE s.listing_type = 'sold'
              AND s.sold_price IS NOT NULL
              AND p.zip_code = ?
              AND p.id != ?
              AND p.sqft BETWEEN ? AND ?
            ORDER BY s.sold_date DESC
            LIMIT ?
        """
        sqft = subject["sqft"] or 1500
        min_sqft = int(sqft * (1 - sqft_tolerance))
        max_sqft = int(sqft * (1 + sqft_tolerance))

        rows = conn.execute(
            comps_query, (subject["zip_code"], property_id, min_sqft, max_sqft, max_results)
        ).fetchall()
    else:
        # Get all sold properties in the same general area
        rows = conn.execute(
            """SELECT p.*, s.sold_price, s.sold_date, s.price_per_sqft
               FROM properties p
               JOIN sales s ON s.property_id = p.id
               WHERE s.listing_type = 'sold'
                 AND s.sold_price IS NOT NULL
                 AND p.id != ?
                 AND p.latitude IS NOT NULL
               ORDER BY s.sold_date DESC""",
            (property_id,),
        ).fetchall()

    comps = []
    for row in rows:
        # Calculate distance
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

        # Distance penalty (closer is better)
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
        if subject["bathrooms"] and row["bathrooms"]:
            bath_diff = abs(subject["bathrooms"] - row["bathrooms"])
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
            bathrooms=row["bathrooms"] or 0,
            year_built=row["year_built"] or 0,
            sold_date=row["sold_date"] or "",
            distance_miles=round(dist, 2),
            similarity_score=round(max(score, 0), 1),
        ))

    # Sort by similarity score descending
    comps.sort(key=lambda c: c.similarity_score, reverse=True)
    conn.close()
    return comps[:max_results]


def estimate_value(property_id: int) -> ValuationResult | None:
    """Estimate the fair market value of a property using comps and market data."""
    conn = get_connection()

    subject = conn.execute(
        """SELECT p.*, s.list_price, s.sold_price, s.listing_type
           FROM properties p
           LEFT JOIN sales s ON s.property_id = p.id
           WHERE p.id = ?""",
        (property_id,),
    ).fetchone()

    if not subject:
        console.print(f"[red]Property {property_id} not found[/red]")
        return None

    comps = find_comps(property_id)

    if not comps:
        console.print("[yellow]No comparable sales found[/yellow]")
        return None

    # Method 1: Weighted average of comp prices (weighted by similarity)
    total_weight = sum(c.similarity_score for c in comps)
    if total_weight > 0:
        comp_based_value = sum(
            c.sold_price * c.similarity_score for c in comps
        ) / total_weight
    else:
        comp_based_value = sum(c.sold_price for c in comps) / len(comps)

    # Method 2: Price-per-sqft from comps applied to subject
    ppsf_values = [c.price_per_sqft for c in comps if c.price_per_sqft > 0]
    if ppsf_values and subject["sqft"]:
        # Weighted median ppsf
        median_ppsf = sorted(ppsf_values)[len(ppsf_values) // 2]
        ppsf_based_value = median_ppsf * subject["sqft"]
    else:
        ppsf_based_value = comp_based_value

    # Blend the two methods
    estimated_value = round((comp_based_value * 0.6 + ppsf_based_value * 0.4), -2)

    # Get market conditions
    market_stats = conn.execute(
        """SELECT * FROM market_stats
           WHERE region_name LIKE ? AND region_type = 'zip'
           ORDER BY period DESC LIMIT 1""",
        (f"%{subject['zip_code']}%",) if subject["zip_code"] else ("%",),
    ).fetchone()

    if market_stats:
        mos = market_stats["months_of_supply"]
        dom = market_stats["median_dom"]
        stl = market_stats["avg_sale_to_list"]

        if mos and mos < 3:
            market_assessment = "hot"
        elif mos and mos > 6:
            market_assessment = "cold"
        else:
            market_assessment = "balanced"
    else:
        market_assessment = "unknown"

    # Assess value
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

    # Confidence based on number and quality of comps
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
        console.print(f"  List Price:       ${result.list_price:>12,.0f}")
    console.print(f"  Estimated Value:  ${result.estimated_value:>12,.0f}")
    console.print(f"    Comp-based:     ${result.comp_based_value:>12,.0f}")
    console.print(f"    PPSF-based:     ${result.ppsf_based_value:>12,.0f}")

    if result.list_price and result.list_price > 0:
        diff = result.estimated_value - result.list_price
        pct = (diff / result.list_price) * 100
        color = "green" if diff > 0 else "red"
        console.print(f"  Difference:       [{color}]${diff:>+12,.0f} ({pct:+.1f}%)[/{color}]")

    console.print(f"  Market:           {result.market_assessment}")
    console.print(f"  Assessment:       [bold]{result.value_assessment}[/bold]")
    console.print(f"  Confidence:       {result.confidence} ({result.num_comps} comps)")

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
            f"{comp.bedrooms}/{comp.bathrooms}",
            f"{comp.distance_miles:.2f}",
            f"{comp.similarity_score:.0f}",
            comp.sold_date[:10] if comp.sold_date else "N/A",
        )

    console.print(table)


@click.command()
@click.option("--address", "-a", default=None, help="Address to look up in the database")
@click.option("--property-id", "-id", default=None, type=int, help="Property ID in the database")
@click.option("--radius", "-r", default=0.5, type=float, help="Max comp distance in miles")
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
            console.print("Try ingesting listings first with: python -m home_value_analyzer.ingest")
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
