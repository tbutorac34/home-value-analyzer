# Home Value Analyzer

A tool for home buyers to collect real estate data, build a local database of comparable properties, and analyze whether homes are fairly valued.

## Features

- **Data Ingestion**: Scrape listings from Zillow, Redfin, and Realtor.com via HomeHarvest; download market-level data from Redfin Data Center; pull historical trends from FRED/FHFA
- **Local Database**: SQLite database of properties, sales, and market statistics
- **Comp Analysis**: Find comparable recently-sold homes and compute fair value estimates
- **Market Indicators**: Track months of inventory, list-to-sale ratios, days on market, and price trends
- **Valuation Scoring**: Flag properties as potentially over- or undervalued relative to comps and market conditions

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add any API keys (FRED, Walk Score, etc.).

## Usage

```bash
# Ingest listings for a target area
python -m home_value_analyzer.ingest --location "San Jose, CA" --listing-type sold --past-days 90

# Ingest Redfin market data for a region
python -m home_value_analyzer.ingest_market --region-type zip --region "95124"

# Analyze a specific property
python -m home_value_analyzer.analyze --address "123 Main St, San Jose, CA"

# View market conditions
python -m home_value_analyzer.market --zip 95124
```

## Architecture

```
Data Sources → Ingestion Pipeline → SQLite DB → Analysis Engine → Reports
```

See `docs/` for detailed documentation on data sources, analysis methods, and methodology.
