"""CLI entry point for home_value_analyzer."""

import click

from .ingest import main as ingest_cmd
from .ingest_market import main as ingest_market_cmd
from .analyze import main as analyze_cmd
from .market import main as market_cmd
from .export import main as export_cmd
from .scrape_history import main as scrape_history_cmd
from .ingest_redfin import main as ingest_redfin_cmd


@click.group()
def cli():
    """Home Value Analyzer - Find fair value for homes."""
    pass


cli.add_command(ingest_cmd, name="ingest")
cli.add_command(ingest_market_cmd, name="ingest-market")
cli.add_command(analyze_cmd, name="analyze")
cli.add_command(market_cmd, name="market")
cli.add_command(export_cmd, name="export")
cli.add_command(scrape_history_cmd, name="scrape-history")
cli.add_command(ingest_redfin_cmd, name="ingest-redfin")


if __name__ == "__main__":
    cli()
