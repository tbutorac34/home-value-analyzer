"""Compute estimated property values from comparable sold data."""

import click
from rich.console import Console

from .db import get_connection, init_db

console = Console()


def estimate_value_from_comps(
    conn,
    zip_code: str,
    sqft: int | None,
    bedrooms: int | None,
    property_type: str | None,
    max_age_days: int = 365,
) -> float | None:
    """Estimate a property's value using recent sold comps in the same ZIP.

    Strategy:
    1. Find sold properties in same ZIP with similar characteristics
    2. Compute weighted median $/sqft from those comps
    3. Multiply by subject sqft

    Returns estimated value or None if insufficient data.
    """
    if not sqft or sqft <= 0 or not zip_code:
        return None

    # Build query for comparable sold properties
    query = """
        SELECT price_per_sqft, sqft, bedrooms, property_type, sold_price
        FROM properties
        WHERE status = 'SOLD'
          AND zip_code = ?
          AND price_per_sqft IS NOT NULL
          AND price_per_sqft > 10
          AND sqft IS NOT NULL
          AND sqft > 0
    """
    params: list = [zip_code]

    # Filter to similar sqft range (within 40%)
    min_sqft = int(sqft * 0.6)
    max_sqft = int(sqft * 1.4)
    query += " AND sqft BETWEEN ? AND ?"
    params.extend([min_sqft, max_sqft])

    # Filter to similar bedroom count if available
    if bedrooms and bedrooms > 0:
        query += " AND bedrooms BETWEEN ? AND ?"
        params.extend([max(1, bedrooms - 1), bedrooms + 1])

    # Filter to same property type if available
    if property_type:
        query += " AND property_type = ?"
        params.append(property_type)

    query += " ORDER BY sold_price DESC"
    rows = conn.execute(query, params).fetchall()

    # If too few comps with type filter, try without it
    if len(rows) < 3 and property_type:
        query2 = """
            SELECT price_per_sqft, sqft, bedrooms, property_type, sold_price
            FROM properties
            WHERE status = 'SOLD'
              AND zip_code = ?
              AND price_per_sqft IS NOT NULL
              AND price_per_sqft > 10
              AND sqft IS NOT NULL
              AND sqft BETWEEN ? AND ?
            ORDER BY sold_price DESC
        """
        rows = conn.execute(query2, [zip_code, min_sqft, max_sqft]).fetchall()

    if len(rows) < 3:
        return None

    # Compute weighted median $/sqft
    # Weight by how similar the comp's sqft is to the subject
    ppsf_values = []
    weights = []
    for row in rows:
        comp_sqft = row["sqft"]
        ppsf = row["price_per_sqft"]

        # Weight: closer sqft = higher weight
        sqft_diff_pct = abs(comp_sqft - sqft) / sqft
        weight = max(0.1, 1.0 - sqft_diff_pct)

        # Bonus weight for matching bedroom count
        if bedrooms and row["bedrooms"] and row["bedrooms"] == bedrooms:
            weight *= 1.3

        ppsf_values.append(ppsf)
        weights.append(weight)

    # Weighted average (more robust than weighted median for small samples)
    total_weight = sum(weights)
    if total_weight <= 0:
        return None

    weighted_ppsf = sum(p * w for p, w in zip(ppsf_values, weights)) / total_weight

    return round(weighted_ppsf * sqft, -2)  # Round to nearest $100


def backfill_estimates(zip_codes: list[str] | None = None, overwrite: bool = False) -> int:
    """Compute and store estimated values for properties missing them.

    Returns number of properties updated.
    """
    conn = get_connection()

    query = "SELECT id, zip_code, sqft, bedrooms, property_type, estimated_value FROM properties WHERE sqft IS NOT NULL AND sqft > 0"
    params: list = []

    if not overwrite:
        query += " AND estimated_value IS NULL"

    if zip_codes:
        placeholders = ",".join("?" for _ in zip_codes)
        query += f" AND zip_code IN ({placeholders})"
        params.extend(zip_codes)

    rows = conn.execute(query, params).fetchall()

    if not rows:
        console.print("[yellow]No properties need estimates[/yellow]")
        return 0

    console.print(f"Computing estimates for {len(rows)} properties...")

    updated = 0
    by_zip: dict[str, int] = {}

    for row in rows:
        estimate = estimate_value_from_comps(
            conn,
            zip_code=row["zip_code"],
            sqft=row["sqft"],
            bedrooms=row["bedrooms"],
            property_type=row["property_type"],
        )

        if estimate:
            conn.execute(
                "UPDATE properties SET estimated_value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (estimate, row["id"]),
            )
            updated += 1
            z = row["zip_code"] or "unknown"
            by_zip[z] = by_zip.get(z, 0) + 1

    conn.commit()
    conn.close()

    console.print(f"[bold green]Updated {updated} properties with comp-based estimates[/bold green]")
    for z in sorted(by_zip):
        console.print(f"  {z}: {by_zip[z]} properties")

    return updated


@click.command()
@click.option("--zips", "-z", default=None, help="Comma-separated ZIP codes (default: all)")
@click.option("--overwrite", is_flag=True, help="Overwrite existing estimated values")
def main(zips: str | None, overwrite: bool):
    """Compute estimated values from comparable sold data."""
    init_db()
    zip_list = [z.strip() for z in zips.split(",")] if zips else None
    backfill_estimates(zip_list, overwrite)


if __name__ == "__main__":
    main()
