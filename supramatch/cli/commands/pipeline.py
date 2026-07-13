"""
CLI command for the full discovery-to-scoring pipeline.

Usage:
    supramatch pipeline run --cage-pdb <path> --guest <query> [--guest <query> ...] [OPTIONS]
    supramatch pipeline run --cage-id <id> --guest-id <id> [--guest-id <id> ...] [OPTIONS]

Examples:
    supramatch pipeline run --cage-pdb data/cages/my_cage.pdb --guest aspirin --guest ibuprofen --guest caffeine
    supramatch pipeline run --cage-id 1 --guest-id 2 --guest-id 3 --all-matches --limit 10
"""

import click
import click_spinner
import logging
from typing import Optional, Tuple
from supramatch.pipeline import run_pipeline
from supramatch.config import HG_MATCH_CONFIG
from supramatch.utils.helpers import format_volume, format_price, format_packing_coefficient

logger = logging.getLogger(__name__)


@click.group()
def pipeline_group():
    """
    Run the full pipeline: resolve a cage and guests, create matches,
    look up prices for the viable ones, and show ranked results.
    """
    pass


@pipeline_group.command()
@click.option('--cage-pdb', default=None, type=click.Path(exists=True), help='Path to a cage PDB file to load (mutually exclusive with --cage-id)')
@click.option('--cage-id', type=int, default=None, help='An already-loaded cage\'s ID (mutually exclusive with --cage-pdb)')
@click.option('--cage-name', default=None, help='Optional name for a newly-loaded cage (ignored with --cage-id)')
@click.option('--guest', 'guest_queries', multiple=True, help='PubChem name/CAS number to fetch as a guest (repeatable)')
@click.option('--guest-id', 'guest_ids', multiple=True, type=int, help="An already-loaded guest's ID (repeatable)")
@click.option('--all-matches', is_flag=True, help='Price every matched guest instead of only viable ones')
@click.option('--refresh-prices', is_flag=True, help='Re-query prices even for guests with a recent quote already stored')
@click.option('--pc-ideal', '-i', default=HG_MATCH_CONFIG["pc_ideal_default"], type=float, help='Ideal packing coefficient for the results window. Independent of --all-matches -- widen this too if you want poor-fit guests you priced to actually show up.')
@click.option('--pc-tolerance', '-t', default=HG_MATCH_CONFIG["pc_tolerance_default"], type=float, help='Packing coefficient tolerance for the results window')
@click.option(
    '--sort', '-s',
    default='quality_score',
    type=click.Choice(['quality_score', 'packing_coefficient', 'price']),
    help='Sort results by metric'
)
@click.option('--limit', '-l', default=20, type=int, help='Maximum number of results')
def run(
    cage_pdb: Optional[str],
    cage_id: Optional[int],
    cage_name: Optional[str],
    guest_queries: Tuple[str, ...],
    guest_ids: Tuple[int, ...],
    all_matches: bool,
    refresh_prices: bool,
    pc_ideal: float,
    pc_tolerance: float,
    sort: str,
    limit: int,
):
    """
    Run the full pipeline in one command.

    Resolves a cage (loading a new PDB or reusing an existing one) and
    guests (fetching new ones from PubChem and/or reusing existing ones),
    creates matches between them, looks up vendor prices for the viable
    ones, and prints ranked results -- equivalent to running `cage load`
    (or nothing, for --cage-id), `guest fetch` for each query, `match
    create`, `price lookup`, and `match find` in sequence.

    --all-matches and --pc-ideal/--pc-tolerance are independent: the former
    controls which guests get *priced*, the latter controls which matches
    get *shown*. A guest priced despite a poor fit (--all-matches) still
    won't appear in the results unless the window is widened to cover it too.

    Example:
        supramatch pipeline run --cage-pdb data/cages/my_cage.pdb --guest aspirin --guest ibuprofen
        supramatch pipeline run --cage-id 1 --guest-id 2 --guest-id 3 --all-matches --pc-ideal 0.4 --pc-tolerance 0.3 --limit 10
    """
    if bool(cage_pdb) == bool(cage_id):
        click.secho("✗ Error: specify exactly one of --cage-pdb or --cage-id", fg="red", err=True)
        raise click.Abort()

    if not guest_queries and not guest_ids:
        click.secho("✗ Error: specify at least one --guest or --guest-id", fg="red", err=True)
        raise click.Abort()

    logger.info(
        f"Running pipeline: cage_pdb={cage_pdb}, cage_id={cage_id}, "
        f"guest_queries={guest_queries}, guest_ids={guest_ids}, "
        f"all_matches={all_matches}, refresh_prices={refresh_prices}, "
        f"pc_ideal={pc_ideal}, pc_tolerance={pc_tolerance}, sort={sort}, limit={limit}"
    )

    try:
        with click_spinner.spinner():
            click.echo("Running pipeline (this may take a while -- PubChem/vendor lookups are rate-limited)...")
            matches = run_pipeline(
                cage_pdb_file=cage_pdb,
                cage_id=cage_id,
                cage_name=cage_name,
                guest_queries=list(guest_queries) or None,
                guest_ids=list(guest_ids) or None,
                price_only_viable=not all_matches,
                refresh_prices=refresh_prices,
                pc_ideal=pc_ideal,
                pc_tolerance=pc_tolerance,
                sort_by=sort,
                limit=limit,
            )

        if not matches:
            click.echo("No matches found")
            logger.info("Pipeline produced no matches")
            return

        cage_name_display = matches[0].cage_name
        cage_volume_display = format_volume(matches[0].cage_cavity_volume)

        click.secho(f"✓ Pipeline complete", fg="green")
        click.echo(f"\nMatch(es) for cage '{cage_name_display}' ({cage_volume_display}):\n")
        click.echo(f"{'#':<4} {'Guest Name':<25} {'PC':>8} {'$/g':>10} {'Score':>8}")
        click.echo("-" * 95)

        for idx, match in enumerate(matches, 1):
            pc_str = format_packing_coefficient(match.packing_coefficient)
            price_str = format_price(match.guest_price_per_gram)

            click.echo(
                f"{idx:<4} "
                f"{match.guest_name:<25} "
                f"{pc_str:>8} "
                f"{price_str:>10} "
                f"{match.quality_score:>8.1f} "
            )

        click.echo()
        logger.info(f"Pipeline complete: {len(matches)} match(es)")

    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Pipeline failed: {e}")
        raise click.Abort()
