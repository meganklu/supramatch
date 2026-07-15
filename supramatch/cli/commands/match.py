"""
CLI commands for host-guest matching.

Usage:
    supramatch match create <cage_id> [--guest-ids LIST]
    supramatch match info <cage_id>
    supramatch match find <cage_id> [OPTIONS]
    supramatch match show <match_id>

Options:
    --pc-ideal IDEAL     Ideal packing coefficient (default: 0.55)
    --pc-tolerance TOL   Packing coefficient range tolerance (default: 0.09)
    --max-price PRICE    Maximum guest price in $/g
    --min-price PRICE    Minimum guest price in $/g
    --sort METRIC        Sort by: quality_score, packing_coefficient, price
    --limit N            Maximum number of results to display (default: 20)
    --in-inventory       Only show guests currently in our inventory

Examples:
    supramatch match create 1
    supramatch match info 1
    supramatch match find 1
    supramatch match find 1 --pc-ideal 0.5 --pc-tolerance 0.1 --limit 10
    supramatch match find 1 --sort price --max-price 5.0
    supramatch match find 1 --sort price
    supramatch match find 1 --in-inventory
    supramatch match show 1
"""

import click
import click_spinner
import logging
from typing import Optional
from supramatch.db.database import init_db
from supramatch.modules.matcher import MatchingEngine
from supramatch.config import HG_MATCH_CONFIG
from supramatch.utils.helpers import format_volume, format_price, format_packing_coefficient, truncate

logger = logging.getLogger(__name__)


@click.group()
def match_group():
    """
    Commands for finding host-guest matches.

    Find optimal guest molecules for a cage based on structural properties
    and pricing.
    """
    pass


@match_group.command()
@click.argument('cage_id', type=int)
@click.option('--guest-ids', '-g', default=None, help='Comma-separated list of guest IDs (if not provided, uses all guests)')
def create(cage_id: int, guest_ids: Optional[str]):
    """
    Create matches between a cage and guests.

    This calculates packing coefficients for all possible cage-guest
    combinations. Must be done before finding matches.

    Examples:
        supramatch match create 1
        supramatch match create 1 --guest-ids 1,2,3,4,5
    """
    logger.info(f"Creating matches for cage {cage_id}")
    init_db()

    engine = MatchingEngine()

    try:
        # Parse guest IDs if provided
        guest_id_list = None
        if guest_ids:
            try:
                guest_id_list = [int(gid.strip()) for gid in guest_ids.split(',')]
                logger.debug(f"Using specific guest IDs: {guest_id_list}")
            except ValueError:
                click.secho("✗ Error: Guest IDs must be comma-separated integers", fg="red", err=True)
                logger.error("Invalid guest IDs format")
                raise click.Abort()

        # Verify cage exists
        cage = engine.get_cage(cage_id)
        if not cage:
            click.secho(f"✗ Cage {cage_id} not found", fg="red", err=True)
            logger.error(f"Cage {cage_id} not found")
            raise click.Abort()

        click.echo(f"Creating matches for cage '{cage.name}'...\n")

        with click_spinner.spinner():
            click.echo("Calculating matches...")
            results = engine.batch_create_matches(cage_id, guest_id_list)

        # Display results
        click.secho(f"✓ Matches created:", fg="green")
        click.echo(f"  Created:  {results['created']}")
        click.echo(f"  Skipped:  {results['skipped']} (already existed)")
        click.echo(f"  Failed:   {results['failed']}")

        total = results['created'] + results['skipped']
        click.echo(f"\nTotal matches for '{cage.name}': {total}")
        click.echo()

        if results['created'] > 0:
            click.secho(
                f"Next step: supramatch match find {cage_id}",
                fg="blue"
            )
            click.echo()

        logger.info(
            f"Successfully created {results['created']} matches "
            f"({results['skipped']} skipped, {results['failed']} failed)"
        )

    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Failed to create matches: {e}", exc_info=True)
        raise click.Abort()

    finally:
        engine.close()


@match_group.command()
@click.argument('cage_id', type=int)
def info(cage_id: int):
    """
    Show matching information for a cage.

    Displays the number of matches and summary statistics.

    Examples:
        supramatch match info 1
    """
    logger.info(f"Getting match info for cage {cage_id}")
    init_db()

    engine = MatchingEngine()

    try:
        cage = engine.get_cage(cage_id)

        if not cage:
            click.secho(f"✗ Cage {cage_id} not found", fg="red", err=True)
            logger.error(f"Cage {cage_id} not found")
            raise click.Abort()

        # Get match statistics
        matches = engine.list_matches_for_cage(cage_id)

        if not matches:
            click.echo(f"Cage '{cage.name}' has no matches yet.")
            click.echo()
            click.secho(f"Create matches with: supramatch match create {cage_id}", fg="blue")
            click.echo()
            return

        # Calculate statistics
        pcs = [m.packing_coefficient for m in matches]
        prices = [m.guest_price_per_gram for m in matches if m.guest_price_per_gram]
        scores = [m.quality_score for m in matches]

        pc_ideal_default = HG_MATCH_CONFIG["pc_ideal_default"]
        pc_tolerance_default = HG_MATCH_CONFIG["pc_tolerance_default"]

        viable_count = sum(1 for m in matches if m.is_viable)

        click.echo(f"\nMatch Information for Cage '{cage.name}':\n")
        click.echo(f"  Total Matches: {len(matches)}")
        click.echo(f"  Viable ({pc_ideal_default} ± {pc_tolerance_default}): {viable_count}")

        if pcs:
            click.echo(f"\nPacking Coefficient:")
            click.echo(f"  Min: {min(pcs):.3f}")
            click.echo(f"  Max: {max(pcs):.3f}")
            click.echo(f"  Avg: {sum(pcs)/len(pcs):.3f}")

        if prices:
            click.echo(f"\nGuest Prices ($/g):")
            click.echo(f"  Min: {format_price(min(prices))}")
            click.echo(f"  Max: {format_price(max(prices))}")
            click.echo(f"  Avg: {format_price(sum(prices)/len(prices))}")

        if scores:
            click.echo(f"\nQuality Scores:")
            click.echo(f"  Min: {min(scores):.1f}")
            click.echo(f"  Max: {max(scores):.1f}")
            click.echo(f"  Avg: {sum(scores)/len(scores):.1f}")

        click.echo()

        logger.info(f"Displayed match info for cage {cage_id}")

    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Failed to get match info: {e}", exc_info=True)
        raise click.Abort()

    finally:
        engine.close()


@match_group.command()
@click.argument('match_id', type=int)
def show(match_id: int):
    """
    Show details for a specific match.

    Example:
        supramatch match show 1
    """
    logger.info(f"Showing match details: {match_id}")
    init_db()

    engine = MatchingEngine()

    try:
        match = engine.get_match(match_id)

        if not match:
            click.secho(f"✗ Match {match_id} not found", fg="red", err=True)
            logger.warning(f"Match {match_id} not found")
            raise click.Abort()

        click.echo(f"\nMatch {match.id}: '{match.cage_name}' + '{match.guest_name}'")
        click.echo(f"  Cage ID: {match.cage_id}")
        click.echo(f"  Guest ID: {match.guest_id}")

        if match.cage_cavity_volume is not None:
            click.echo(f"  Cage cavity volume: {format_volume(match.cage_cavity_volume)}")

        click.echo(f"  Packing coefficient: {format_packing_coefficient(match.packing_coefficient)}")
        click.echo(f"  Guest price: {format_price(match.guest_price_per_gram)}")
        click.echo(f"  Guest rotatable bonds: {match.guest_rotatable_bonds if match.guest_rotatable_bonds is not None else 'N/A'}")
        click.echo(f"  Guest in inventory: {'✓' if match.guest_in_inventory else '✗'}")
        click.echo(f"  Quality score: {match.quality_score:.1f}")
        click.echo(f"  Viable: {'✓' if match.is_viable else '✗'}")

        if match.notes:
            click.echo(f"  Notes: {match.notes}")

        if match.created_at:
            click.echo(f"  Created: {match.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        click.echo()
        logger.info(f"Displayed match {match_id}")

    finally:
        engine.close()


@match_group.command()
@click.argument('cage_id', type=int)
@click.option('--pc-ideal', '-i', default=HG_MATCH_CONFIG["pc_ideal_default"], type=float, help='Ideal packing coefficient')
@click.option('--pc-tolerance', '-t', default=HG_MATCH_CONFIG["pc_tolerance_default"], type=float, help='Packing coefficient tolerance range')
@click.option('--max-price', default=None, type=float, help='Maximum guest price ($/g)')
@click.option('--min-price', default=None, type=float, help='Minimum guest price ($/g)')
@click.option(
    '--sort', '-s',
    default='quality_score',
    type=click.Choice(['quality_score', 'packing_coefficient', 'price']),
    help='Sort results by metric'
)
@click.option('--limit', '-l', default=20, type=int, help='Maximum number of results')
@click.option('--in-inventory', is_flag=True, default=False, help='Only show guests currently in our inventory')
def find(cage_id: int, pc_ideal: float, pc_tolerance: float, max_price: Optional[float], min_price: Optional[float], sort: str, limit: int, in_inventory: bool):
    """
    Find best guest matches for a cage.

    Results are evaluated based on structural properties (packing
    coefficient, guest flexibility) and pricing. --pc-ideal/--pc-tolerance
    set the search window itself (defaulting to the app's standard PC target).

    Default packing coefficient ranges:
        0.0-0.3: Loose fit
        0.3-0.7: Optimal fit (recommended)
        0.7-0.9: Snug fit
        0.9-1.0: Very tight fit

    Example:
        supramatch match 1
        supramatch match 1 --pc-ideal 0.3 --pc-tolerance 0.7 --limit 10
        supramatch match 1 --sort price --max-price 5.0
        supramatch match 1 --sort price
        supramatch match 1 --in-inventory
    """
    logger.info(
        f"Finding matches for cage {cage_id}: pc={pc_ideal} ± {pc_tolerance}, "
        f"price=${min_price}–${max_price}, sort={sort}, limit={limit}, in_inventory={in_inventory}"
    )
    init_db()

    engine = MatchingEngine()

    try:
        with click_spinner.spinner():
            click.echo("Finding matches...")
            matches = engine.match_guests_to_cage(
                cage_id=cage_id,
                pc_ideal=pc_ideal,
                pc_tolerance=pc_tolerance,
                max_price=max_price,
                min_price=min_price,
                sort_by=sort,
                limit=limit,
                in_inventory_only=in_inventory,
            )

        if not matches:
            click.echo(f"No matches found for cage {cage_id}")
            logger.info(f"No matches found for cage {cage_id}")
            return

        cage = engine.get_cage(cage_id)

        click.echo(f"\nMatch(es) for cage '{cage.name}' ({format_volume(cage.cavity_volume)}):\n")
        click.echo(f"{'#':<4} {'Guest ID':<9} {'Guest Name':<25} {'PC':>8} {'$/g':>10} {'NRB':>5} {'Score':>8} {'Viable':>8} {'Inv':>5}")
        click.echo("-" * 106)

        for idx, match in enumerate(matches, 1):
            pc_str = format_packing_coefficient(match.packing_coefficient)
            price_str = format_price(match.guest_price_per_gram)
            nrb_str = str(match.guest_rotatable_bonds) if match.guest_rotatable_bonds is not None else "N/A"
            viable_str = "✓" if match.is_viable else "✗"
            inv_str = "✓" if match.guest_in_inventory else "✗"

            click.echo(
                f"{idx:<4} "
                f"{match.guest_id:<9} "
                f"{truncate(match.guest_name, 25):<25} "
                f"{pc_str:>8} "
                f"{price_str:>10} "
                f"{nrb_str:>5} "
                f"{match.quality_score:>8.1f} "
                f"{viable_str:>8} "
                f"{inv_str:>5}"
            )

        click.echo()
        logger.info(f"Found {len(matches)} match(es) for cage {cage_id}")

    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Matching failed: {e}")
        raise click.Abort()

    finally:
        engine.close()
