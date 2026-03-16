"""CLI entry point for home_value_analyzer."""

import click

from .ingest import main as ingest_cmd
from .ingest_market import main as ingest_market_cmd
from .analyze import main as analyze_cmd
from .market import main as market_cmd


@click.group()
def cli():
    """Home Value Analyzer - Find fair value for homes."""
    pass


cli.add_command(ingest_cmd, name="ingest")
cli.add_command(ingest_market_cmd, name="ingest-market")
cli.add_command(analyze_cmd, name="analyze")
cli.add_command(market_cmd, name="market")


if __name__ == "__main__":
    cli()
