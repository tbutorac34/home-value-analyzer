"""Property adjustments: NLP extraction, manual entry, and value calculation."""

import re
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from .db import get_connection, init_db

console = Console()

CURRENT_YEAR = datetime.now().year

# --- NLP Extraction Patterns ---
# Each tuple: (field_name, regex_pattern, transform_function)
# Patterns are tested against lowercased description text

EXTRACTION_PATTERNS = [
    # Basement
    ("basement_finished", r"(?:fully\s+)?finished\s+(?:basement|lower\s+level|bsmt)", lambda m: True),
    ("basement_finished", r"finished\s+(?:walk[\s-]?out|w/o)\s+(?:basement|lower)", lambda m: True),
    ("basement_type", r"unfinished\s+(?:basement|lower|bsmt)", lambda m: "unfinished"),
    ("basement_type", r"(?:full|fully)\s+finished\s+(?:basement|lower)", lambda m: "full_finished"),
    ("basement_type", r"partially\s+finished\s+(?:basement|lower)", lambda m: "partial_finished"),
    ("basement_type", r"walk[\s-]?out\s+(?:basement|lower)", lambda m: "full_finished"),
    ("basement_type", r"crawl\s*space", lambda m: "crawl"),

    # Kitchen
    ("kitchen_updated", r"(?:updated|remodeled|renovated|new|gorgeous|stunning|beautiful)\s+kitchen", lambda m: True),
    ("kitchen_updated", r"kitchen\s+(?:has been|was|recently)\s+(?:updated|remodeled|renovated)", lambda m: True),
    ("countertop_material", r"granite\s+(?:counter|countertop)", lambda m: "granite"),
    ("countertop_material", r"quartz\s+(?:counter|countertop)", lambda m: "quartz"),
    ("countertop_material", r"marble\s+(?:counter|countertop)", lambda m: "marble"),
    ("countertop_material", r"butcher\s+block\s+(?:counter|countertop)", lambda m: "butcher_block"),
    ("countertop_material", r"(?:counter|countertop)s?\s+(?:are\s+)?(?:granite)", lambda m: "granite"),
    ("countertop_material", r"(?:counter|countertop)s?\s+(?:are\s+)?(?:quartz)", lambda m: "quartz"),

    # Bathrooms
    ("bathroom_updated", r"(?:updated|remodeled|renovated|new)\s+(?:bath|bathroom)", lambda m: True),
    ("bathroom_updated", r"(?:bath|bathroom)s?\s+(?:have been|were|recently)\s+(?:updated|remodeled)", lambda m: True),

    # Roof
    ("roof_year", r"(?:new\s+)?roof\s*[\(\-:,]?\s*(?:in\s+)?(\d{4})", lambda m: int(m.group(1))),
    ("roof_year", r"(?:new\s+)?roof\s*[\(\-:,]?\s*(?:in\s+)?['\"]?(\d{2})['\"]?\b", lambda m: 2000 + int(m.group(1)) if int(m.group(1)) < 50 else 1900 + int(m.group(1))),
    ("roof_year", r"roof\s+(?:is\s+)?(?:from\s+)?(\d{4})", lambda m: int(m.group(1))),
    ("roof_year", r"(\d{4})\s+roof", lambda m: int(m.group(1))),

    # HVAC
    ("hvac_year", r"(?:furnace|hvac)\s*[\(\-:,]?\s*(?:in\s+)?(\d{4})", lambda m: int(m.group(1))),
    ("hvac_year", r"(?:furnace|hvac)\s*[\(\-:,]?\s*(?:in\s+)?['\"]?(\d{2})['\"]?\b", lambda m: 2000 + int(m.group(1)) if int(m.group(1)) < 50 else 1900 + int(m.group(1))),
    ("hvac_year", r"(?:new|newer)\s+(?:furnace|hvac)", lambda m: CURRENT_YEAR - 2),
    ("hvac_year", r"(?:a/?c|air\s+condition)\s*[\(\-:,]?\s*(\d{4})", lambda m: int(m.group(1))),

    # Windows
    ("windows_year", r"(?:new|newer)\s+windows\s*[\(\-:,]?\s*(?:in\s+)?(\d{4})", lambda m: int(m.group(1))),
    ("windows_year", r"windows\s*[\(\-:,]?\s*(?:in\s+)?(\d{4})", lambda m: int(m.group(1))),
    ("windows_year", r"(?:new|newer)\s+windows", lambda m: CURRENT_YEAR - 2),

    # Water heater
    ("water_heater_year", r"(?:new\s+)?(?:hot\s+)?water\s+(?:heater|tank)\s*[\(\-:,]?\s*(\d{4})", lambda m: int(m.group(1))),
    ("water_heater_year", r"(?:hwh|h\.w\.h)\s*[\(\-:,]?\s*(\d{4})", lambda m: int(m.group(1))),
    ("water_heater_year", r"(?:new|newer)\s+(?:hot\s+)?water\s+(?:heater|tank)", lambda m: CURRENT_YEAR - 2),

    # Flooring
    ("flooring_type", r"hardwood\s+floor", lambda m: "hardwood"),
    ("flooring_type", r"(?:lvp|luxury\s+vinyl)\s+(?:plank\s+)?floor", lambda m: "lvp"),
    ("flooring_type", r"(?:lvp|luxury\s+vinyl)", lambda m: "lvp"),
    ("flooring_type", r"carpet(?:ed)?\s+(?:throughout|floor)", lambda m: "carpet"),
    ("flooring_type", r"tile\s+floor", lambda m: "tile"),

    # Fireplace
    ("fireplace", r"(?:gas|wood|electric)\s+(?:burning\s+)?fireplace", lambda m: True),
    ("fireplace", r"fireplace", lambda m: True),
    ("fireplace_type", r"gas\s+(?:burning\s+)?fireplace", lambda m: "gas"),
    ("fireplace_type", r"wood\s+(?:burning\s+)?fireplace", lambda m: "wood"),
    ("fireplace_type", r"electric\s+fireplace", lambda m: "electric"),

    # Open floor plan
    ("open_floor_plan", r"open[\s\-](?:concept|floor\s*plan|layout)", lambda m: True),
    ("open_floor_plan", r"open\s+and\s+airy", lambda m: True),

    # Pool
    ("pool", r"(?:in[\s\-]?ground|inground)\s+pool", lambda m: True),
    ("pool_type", r"(?:in[\s\-]?ground|inground)\s+pool", lambda m: "inground"),
    ("pool", r"(?:above[\s\-]?ground)\s+pool", lambda m: True),
    ("pool_type", r"(?:above[\s\-]?ground)\s+pool", lambda m: "above_ground"),

    # Fence
    ("fence", r"(?:fully\s+)?fenced\s+(?:yard|backyard|back\s+yard|in)", lambda m: True),
    ("fence", r"privacy\s+fence", lambda m: True),
    ("fence_type", r"privacy\s+(?:wood\s+)?fence", lambda m: "privacy"),
    ("fence_type", r"chain[\s\-]?link\s+fence", lambda m: "chain_link"),
    ("fence_type", r"vinyl\s+fence", lambda m: "vinyl"),
    ("fence_type", r"wrought\s+iron\s+fence", lambda m: "wrought_iron"),

    # Garage
    ("garage_type", r"attached\s+(?:\d[\s\-]?car\s+)?garage", lambda m: "attached"),
    ("garage_type", r"detached\s+(?:\d[\s\-]?car\s+)?garage", lambda m: "detached"),
    ("garage_heated", r"heated\s+garage", lambda m: True),

    # Deck/patio
    ("deck_patio", r"(?:large\s+)?(?:deck|patio|concrete\s+patio)", lambda m: True),

    # Sprinkler
    ("sprinkler_system", r"sprinkler\s+system", lambda m: True),

    # Lot
    ("lot_type", r"cul[\s\-]?de[\s\-]?sac", lambda m: "cul_de_sac"),
    ("lot_type", r"corner\s+lot", lambda m: "corner"),
    ("lot_backs_to", r"backs?\s+to\s+(?:the\s+)?(?:woods|trees|wooded)", lambda m: "woods"),
    ("lot_backs_to", r"(?:wooded|treed)\s+(?:lot|backyard|views?)", lambda m: "woods"),
    ("lot_backs_to", r"no\s+(?:rear\s+)?neighbors", lambda m: "open_space"),

    # Electrical/plumbing
    ("electrical_updated", r"(?:updated|new|newer)\s+(?:electrical|electric)\s+(?:panel|wiring|service)", lambda m: True),
    ("electrical_updated", r"(?:200|150)\s*amp\s+(?:electrical\s+)?(?:panel|service)", lambda m: True),
    ("plumbing_updated", r"(?:updated|new|newer)\s+plumbing", lambda m: True),

    # Overall condition
    ("move_in_ready", r"move[\s\-]?in\s+ready", lambda m: True),
]


def extract_adjustments_from_description(description: str) -> dict:
    """Parse listing description and extract property adjustments."""
    if not description:
        return {}

    text = description.lower()
    extracted = {}

    for field_name, pattern, transform in EXTRACTION_PATTERNS:
        if field_name in extracted:
            continue  # First match wins for each field
        match = re.search(pattern, text)
        if match:
            extracted[field_name] = transform(match)

    # Infer kitchen quality from countertop material
    if "countertop_material" in extracted and "kitchen_quality" not in extracted:
        material = extracted["countertop_material"]
        if material in ("granite", "quartz", "marble"):
            extracted["kitchen_quality"] = "major"
            extracted["kitchen_updated"] = True
        elif material == "butcher_block":
            extracted["kitchen_quality"] = "minor"

    # Infer basement_finished from basement_type
    if "basement_type" in extracted and "basement_finished" not in extracted:
        bt = extracted["basement_type"]
        extracted["basement_finished"] = bt in ("full_finished", "partial_finished")

    return extracted


def save_adjustments(conn, property_id: int, adjustments: dict, source: str = "nlp_extracted", confidence: float = 0.8) -> None:
    """Insert or update adjustments for a property."""
    # Build column list from adjustments dict
    valid_columns = {
        "basement_finished", "basement_finished_sqft", "basement_type",
        "kitchen_updated", "kitchen_remodel_year", "kitchen_quality", "countertop_material",
        "bathroom_updated", "bathroom_remodel_year", "bathroom_quality", "bathroom_remodel_count",
        "roof_year", "hvac_year", "windows_year", "water_heater_year",
        "electrical_updated", "plumbing_updated",
        "flooring_type", "open_floor_plan", "fireplace", "fireplace_type",
        "garage_type", "garage_heated",
        "pool", "pool_type", "fence", "fence_type", "deck_patio", "sprinkler_system",
        "lot_type", "lot_backs_to",
        "overall_condition", "move_in_ready", "notes",
    }

    filtered = {k: v for k, v in adjustments.items() if k in valid_columns}
    if not filtered:
        return

    # Convert booleans to int for SQLite
    for k, v in filtered.items():
        if isinstance(v, bool):
            filtered[k] = 1 if v else 0

    columns = ["property_id", "source", "confidence"] + list(filtered.keys())
    values = [property_id, source, confidence] + list(filtered.values())
    placeholders = ",".join("?" for _ in columns)
    col_str = ",".join(columns)

    # Upsert
    update_parts = ", ".join(f"{k}=excluded.{k}" for k in filtered.keys())
    update_parts += ", source=excluded.source, confidence=excluded.confidence, updated_at=CURRENT_TIMESTAMP"

    conn.execute(
        f"""INSERT INTO property_adjustments ({col_str})
            VALUES ({placeholders})
            ON CONFLICT(property_id) DO UPDATE SET {update_parts}""",
        values,
    )


def calculate_adjustment_total(conn, property_id: int, market_area: str = "macomb_county") -> dict:
    """Calculate the net dollar adjustment for a property.

    Returns dict with 'total', 'breakdown' list, and 'feature_count'.
    """
    adj = conn.execute(
        "SELECT * FROM property_adjustments WHERE property_id = ?",
        (property_id,),
    ).fetchone()

    if not adj:
        return {"total": 0, "breakdown": [], "feature_count": 0}

    # Load adjustment values
    values = {}
    for row in conn.execute(
        "SELECT adjustment_key, adjustment_dollars, depreciation_rate FROM adjustment_values WHERE market_area = ?",
        (market_area,),
    ).fetchall():
        values[row["adjustment_key"]] = {
            "dollars": row["adjustment_dollars"],
            "depreciation": row["depreciation_rate"],
        }

    breakdown = []
    total = 0

    def add(key: str, label: str, year: int | None = None):
        nonlocal total
        if key not in values:
            return
        base = values[key]["dollars"]
        dep = values[key]["depreciation"]

        # Apply depreciation for time-sensitive items
        if year and dep > 0:
            years_old = max(0, CURRENT_YEAR - year)
            effective = base * (1 - dep) ** years_old
        else:
            effective = base

        effective = round(effective, -2)  # Round to nearest $100
        total += effective
        breakdown.append({"feature": label, "key": key, "dollars": effective})

    # Basement
    if adj["basement_finished"]:
        bt = adj["basement_type"] or "full_finished"
        if bt == "full_finished":
            add("basement_full_finished", "Finished basement (full)")
        elif bt == "partial_finished":
            add("basement_partial_finished", "Finished basement (partial)")

    # Kitchen
    if adj["kitchen_updated"]:
        quality = adj["kitchen_quality"] or "major"
        add(f"kitchen_{quality}", f"Kitchen remodel ({quality})", adj["kitchen_remodel_year"])

    # Countertops (only if kitchen not already counted)
    if adj["countertop_material"] and not adj["kitchen_updated"]:
        material = adj["countertop_material"]
        if material in ("granite", "quartz"):
            add(f"countertop_{material}", f"{material.title()} countertops")

    # Bathrooms
    if adj["bathroom_updated"]:
        quality = adj["bathroom_quality"] or "major"
        count = adj["bathroom_remodel_count"] or 1
        for i in range(count):
            add(f"bathroom_{quality}", f"Bathroom remodel ({quality})", adj["bathroom_remodel_year"])

    # Roof
    if adj["roof_year"]:
        add("roof_new", f"Roof ({adj['roof_year']})", adj["roof_year"])

    # HVAC
    if adj["hvac_year"]:
        add("hvac_new", f"HVAC ({adj['hvac_year']})", adj["hvac_year"])

    # Windows
    if adj["windows_year"]:
        add("windows_new", f"Windows ({adj['windows_year']})", adj["windows_year"])

    # Water heater
    if adj["water_heater_year"]:
        add("water_heater_new", f"Water heater ({adj['water_heater_year']})", adj["water_heater_year"])

    # Flooring
    if adj["flooring_type"] == "hardwood":
        add("hardwood_floors", "Hardwood floors")
    elif adj["flooring_type"] == "lvp":
        add("lvp_flooring", "LVP flooring")

    # Garage
    if adj["garage_type"] == "attached":
        add("garage_attached", "Attached garage")
    elif adj["garage_type"] == "detached":
        pass  # baseline, no adjustment

    # Pool
    if adj["pool"]:
        pool_type = adj["pool_type"] or "inground"
        if pool_type == "inground":
            add("pool_inground", "In-ground pool")

    # Fence
    if adj["fence"]:
        fence_type = adj["fence_type"] or "privacy"
        add(f"fence_{fence_type}", f"Fence ({fence_type})")

    # Open floor plan
    if adj["open_floor_plan"]:
        add("open_floor_plan", "Open floor plan")

    # Fireplace
    if adj["fireplace"]:
        ft = adj["fireplace_type"] or "gas"
        add(f"fireplace_{ft}", f"Fireplace ({ft})")

    # Lot
    if adj["lot_type"] == "cul_de_sac":
        add("lot_cul_de_sac", "Cul-de-sac lot")
    if adj["lot_backs_to"] == "woods":
        add("lot_backs_woods", "Backs to woods")
    elif adj["lot_backs_to"] == "busy_road":
        add("lot_backs_busy_road", "Backs to busy road")

    # Electrical/plumbing
    if adj["electrical_updated"]:
        add("electrical_updated", "Updated electrical")
    if adj["plumbing_updated"]:
        add("plumbing_updated", "Updated plumbing")

    # Sprinkler
    if adj["sprinkler_system"]:
        add("sprinkler_system", "Sprinkler system")

    return {
        "total": round(total, -2),
        "breakdown": breakdown,
        "feature_count": len(breakdown),
    }


def extract_all(zip_codes: list[str] | None = None) -> int:
    """Run NLP extraction on all properties with descriptions. Returns count processed."""
    conn = get_connection()

    # Add tables if they don't exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS property_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL REFERENCES properties(id),
            source TEXT NOT NULL DEFAULT 'manual',
            confidence REAL DEFAULT 1.0,
            notes TEXT,
            basement_finished INTEGER,
            basement_finished_sqft INTEGER,
            basement_type TEXT,
            kitchen_updated INTEGER,
            kitchen_remodel_year INTEGER,
            kitchen_quality TEXT,
            countertop_material TEXT,
            bathroom_updated INTEGER,
            bathroom_remodel_year INTEGER,
            bathroom_quality TEXT,
            bathroom_remodel_count INTEGER,
            roof_year INTEGER,
            hvac_year INTEGER,
            windows_year INTEGER,
            water_heater_year INTEGER,
            electrical_updated INTEGER,
            plumbing_updated INTEGER,
            flooring_type TEXT,
            open_floor_plan INTEGER,
            fireplace INTEGER,
            fireplace_type TEXT,
            garage_type TEXT,
            garage_heated INTEGER,
            pool INTEGER,
            pool_type TEXT,
            fence INTEGER,
            fence_type TEXT,
            deck_patio INTEGER,
            sprinkler_system INTEGER,
            lot_type TEXT,
            lot_backs_to TEXT,
            overall_condition TEXT,
            move_in_ready INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(property_id)
        );

        CREATE TABLE IF NOT EXISTS adjustment_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_area TEXT NOT NULL DEFAULT 'macomb_county',
            adjustment_key TEXT NOT NULL,
            adjustment_dollars REAL NOT NULL,
            min_dollars REAL,
            max_dollars REAL,
            depreciation_rate REAL DEFAULT 0.0,
            notes TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(market_area, adjustment_key)
        );
    """)

    # Seed adjustment values if empty
    existing = conn.execute("SELECT COUNT(*) FROM adjustment_values").fetchone()[0]
    if existing == 0:
        _seed_adjustment_values(conn)

    query = "SELECT id, description FROM properties WHERE description IS NOT NULL AND description != ''"
    params: list = []

    if zip_codes:
        placeholders = ",".join("?" for _ in zip_codes)
        query += f" AND zip_code IN ({placeholders})"
        params.extend(zip_codes)

    rows = conn.execute(query, params).fetchall()

    if not rows:
        console.print("[yellow]No properties with descriptions found[/yellow]")
        return 0

    console.print(f"Extracting features from {len(rows)} descriptions...")

    processed = 0
    features_found = 0
    feature_counts: dict[str, int] = {}

    for row in rows:
        adjustments = extract_adjustments_from_description(row["description"])
        if adjustments:
            save_adjustments(conn, row["id"], adjustments)
            processed += 1
            features_found += len(adjustments)
            for key in adjustments:
                feature_counts[key] = feature_counts.get(key, 0) + 1

    conn.commit()
    conn.close()

    console.print(f"[bold green]Processed {processed}/{len(rows)} properties, {features_found} features extracted[/bold green]")

    # Show top features
    console.print("\nFeature extraction summary:")
    table = Table()
    table.add_column("Feature")
    table.add_column("Count", justify="right")
    table.add_column("% of Properties", justify="right")

    for key, count in sorted(feature_counts.items(), key=lambda x: -x[1])[:20]:
        pct = count / len(rows) * 100
        table.add_row(key, str(count), f"{pct:.1f}%")

    console.print(table)

    return processed


def _seed_adjustment_values(conn):
    """Insert default Macomb County adjustment values."""
    defaults = [
        ("macomb_county", "basement_full_finished", 25000, 20000, 35000, 0.0),
        ("macomb_county", "basement_partial_finished", 15000, 10000, 20000, 0.0),
        ("macomb_county", "kitchen_luxury", 25000, 20000, 35000, 0.03),
        ("macomb_county", "kitchen_major", 18000, 12000, 25000, 0.03),
        ("macomb_county", "kitchen_minor", 8000, 5000, 12000, 0.05),
        ("macomb_county", "bathroom_major", 6000, 4000, 8000, 0.03),
        ("macomb_county", "bathroom_minor", 3000, 2000, 5000, 0.05),
        ("macomb_county", "roof_new", 6000, 3000, 8000, 0.10),
        ("macomb_county", "hvac_new", 5000, 3000, 6000, 0.08),
        ("macomb_county", "windows_new", 7000, 5000, 10000, 0.05),
        ("macomb_county", "hardwood_floors", 5000, 3000, 8000, 0.0),
        ("macomb_county", "lvp_flooring", 3000, 2000, 5000, 0.0),
        ("macomb_county", "garage_3car", 20000, 15000, 25000, 0.0),
        ("macomb_county", "garage_attached", 10000, 8000, 12000, 0.0),
        ("macomb_county", "garage_none", -25000, -30000, -20000, 0.0),
        ("macomb_county", "pool_inground", 10000, 5000, 15000, 0.0),
        ("macomb_county", "fence_privacy", 3500, 2000, 5000, 0.0),
        ("macomb_county", "lot_backs_woods", 10000, 5000, 15000, 0.0),
        ("macomb_county", "lot_backs_busy_road", -15000, -20000, -10000, 0.0),
        ("macomb_county", "lot_cul_de_sac", 5000, 3000, 8000, 0.0),
        ("macomb_county", "open_floor_plan", 5000, 3000, 7000, 0.0),
        ("macomb_county", "fireplace_gas", 2000, 1500, 3000, 0.0),
        ("macomb_county", "electrical_updated", 3000, 2000, 4000, 0.0),
        ("macomb_county", "plumbing_updated", 3000, 2000, 4000, 0.0),
        ("macomb_county", "sprinkler_system", 2000, 1000, 3000, 0.0),
        ("macomb_county", "countertop_granite", 4000, 3000, 6000, 0.0),
        ("macomb_county", "countertop_quartz", 5000, 3000, 7000, 0.0),
        ("macomb_county", "water_heater_new", 1500, 1000, 2000, 0.10),
    ]
    for row in defaults:
        conn.execute(
            """INSERT OR IGNORE INTO adjustment_values
               (market_area, adjustment_key, adjustment_dollars, min_dollars, max_dollars, depreciation_rate)
               VALUES (?, ?, ?, ?, ?, ?)""",
            row,
        )
    conn.commit()


def display_adjustments(property_id: int) -> None:
    """Show adjustments and calculated value for a property."""
    conn = get_connection()

    prop = conn.execute("SELECT address, list_price, estimated_value FROM properties WHERE id = ?", (property_id,)).fetchone()
    if not prop:
        console.print(f"[red]Property {property_id} not found[/red]")
        return

    adj = conn.execute("SELECT * FROM property_adjustments WHERE property_id = ?", (property_id,)).fetchone()
    if not adj:
        console.print(f"[yellow]No adjustments recorded for {prop['address']}[/yellow]")
        return

    calc = calculate_adjustment_total(conn, property_id)
    conn.close()

    console.print(f"\n[bold]Adjustments: {prop['address']}[/bold]")
    console.print(f"  Source: {adj['source']} (confidence: {adj['confidence']})")
    console.print(f"  List Price:      ${prop['list_price']:>12,.0f}" if prop["list_price"] else "")
    console.print(f"  Base Estimate:   ${prop['estimated_value']:>12,.0f}" if prop["estimated_value"] else "")

    if calc["breakdown"]:
        console.print(f"\n  [bold]Feature Adjustments ({calc['feature_count']} features):[/bold]")
        table = Table()
        table.add_column("Feature")
        table.add_column("Value", justify="right")

        for item in calc["breakdown"]:
            color = "green" if item["dollars"] > 0 else "red"
            table.add_row(item["feature"], f"[{color}]${item['dollars']:+,.0f}[/{color}]")

        table.add_row("[bold]Total Adjustment[/bold]", f"[bold]${calc['total']:+,.0f}[/bold]")
        console.print(table)

        if prop["estimated_value"]:
            adjusted_value = prop["estimated_value"] + calc["total"]
            console.print(f"\n  Adjusted Estimate: ${adjusted_value:>12,.0f}")


@click.command()
@click.option("--extract", "do_extract", is_flag=True, help="Run NLP extraction on descriptions")
@click.option("--zips", "-z", default=None, help="Comma-separated ZIP codes")
@click.option("--show", "-s", default=None, type=int, help="Show adjustments for a property ID")
@click.option("--values", "show_values", is_flag=True, help="Show adjustment dollar values")
def main(do_extract: bool, zips: str | None, show: int | None, show_values: bool):
    """Manage property adjustments and feature extraction."""
    init_db()

    if show:
        display_adjustments(show)
        return

    if show_values:
        conn = get_connection()
        # Ensure tables exist
        extract_all.__wrapped__ if hasattr(extract_all, '__wrapped__') else None
        rows = conn.execute(
            "SELECT * FROM adjustment_values WHERE market_area = 'macomb_county' ORDER BY adjustment_dollars DESC"
        ).fetchall()
        conn.close()

        table = Table(title="Macomb County Adjustment Values")
        table.add_column("Feature")
        table.add_column("Value", justify="right")
        table.add_column("Range", justify="right")
        table.add_column("Depreciation", justify="right")

        for row in rows:
            dep = f"{row['depreciation_rate']*100:.0f}%/yr" if row["depreciation_rate"] else "-"
            table.add_row(
                row["adjustment_key"],
                f"${row['adjustment_dollars']:+,.0f}",
                f"${row['min_dollars']:,.0f} - ${row['max_dollars']:,.0f}",
                dep,
            )
        console.print(table)
        return

    if do_extract:
        zip_list = [z.strip() for z in zips.split(",")] if zips else None
        extract_all(zip_list)
        return

    console.print("Use --extract to run NLP extraction, --show <id> to view, or --values to see dollar amounts")


if __name__ == "__main__":
    main()
