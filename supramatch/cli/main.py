"""
Main CLI entry point for supramatch.

This module provides the main CLI interface using Click.

Usage:
    supramatch --help
    supramatch --version
    supramatch cage --help
    supramatch guest --help
    supramatch match --help
    supramatch price --help
    supramatch pipeline --help
    supramatch db --help

Examples:
    supramatch cage load data/cage.pdb --name MyCage
    supramatch guest fetch aspirin
    supramatch guest import guests.csv
    supramatch match find 1 --pc-ideal 0.55 --pc-tolerance 0.15 --limit 10
    supramatch price lookup --cage 1
    supramatch pipeline run --cage-pdb data/cage.pdb --guest aspirin --guest ibuprofen
    supramatch db init
"""

import click
import logging
from pathlib import Path
from supramatch import __version__
from supramatch.cli import commands

logger = logging.getLogger(__name__)

@click.group(invoke_without_command=True)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    """
    Supramatch: Match metal-organic cages to guest molecules.
    
    Command-line tool for analyzing host-guest interactions based on
    packing coefficient and pricing.
    
    For help on a specific command:
        supramatch <command> --help

    Examples:
        supramatch cage load data/cage.pdb --name MyCage
        supramatch guest fetch aspirin
        supramatch guest import guests.csv
        supramatch match find 1 --pc-ideal 0.55 --pc-tolerance 0.15
        supramatch price lookup --cage 1
        supramatch pipeline run --cage-pdb data/cage.pdb --guest aspirin
    """
    ctx.ensure_object(dict)

    # Show help if no subcommand provided
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

    logger.debug(f"Supramatch CLI {__version__} started")

# Register command groups
cli.add_command(commands.cage.cage_group, name="cage")
cli.add_command(commands.guest.guest_group, name="guest")
cli.add_command(commands.match.match_group, name="match")
cli.add_command(commands.price.price_group, name="price")
cli.add_command(commands.pipeline.pipeline_group, name="pipeline")
cli.add_command(commands.db.db_group, name="db")

def main():
    """
    Entry point for the CLI application.
    
    This function is called when the package is invoked as a command-line tool.
    It initializes logging and runs the CLI.
    """
    try:
        cli(obj={})
    except click.Abort:
        # Click's way of handling errors - exit gracefully
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        click.secho(f"✗ Unexpected error: {e}", fg="red", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()