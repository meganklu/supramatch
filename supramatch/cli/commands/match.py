"""
CLI commands for host-guest matching.

Usage:
    supramatch match create <cage_id> [--guest-ids LIST]
    supramatch match info <cage_id>
    supramatch match find <cage_id> [OPTIONS]

Options:
    --pc-min MIN         Minimum packing coefficient (default: 0.3)
    --pc-max MAX         Maximum packing coefficient (default: 0.7)
    --max-price PRICE    Maximum guest price in $/g
    --min-price PRICE    Minimum guest price in $/g
    --sort METRIC        Sort by: quality_score, packing_coefficient, price, value_ratio
    --limit N            Maximum number of results to display (default: 20)

Examples:
    supramatch match create 1
    supramatch match info 1
    supramatch match find 1
    supramatch match find 1 --pc-min 0.3 --pc-max 0.7 --limit 10
    supramatch match find 1 --sort price --max-price 5.0
    supramatch match find 1 --sort value_ratio
"""

import click
import click_spinner
import logging
from typing import Optional
from supramatch.db.database import init_db
from supramatch.modules.hg_match import MatchingEngine
from supramatch.db.models import Cage
from supramatch.utils.helpers import format_volume, format_price, format_packing_coefficient

logger = logging.getLogger(__name__)


@click.group()
def match_group():
    """
    Commands for finding host-guest matches.
    
    Find optimal guest molecules for a cage based on packing coefficient,
    price, and other metrics.
    """
    pass


@match_group.command()
@click.argument('cage_id', type=int)
@click.option('--guest-ids', default=None, help='Comma-separated list of guest IDs (if not provided, uses all guests)')
def create(cage_id: int, guest_ids: Optional[str]):
    """
    Create pairings between a cage and guests.
    
    This calculates packing coefficients for all possible cage-guest
    combinations. Must be done before finding matches.
    
    Examples:
        supramatch match create 1
        supramatch match create 1 --guest-ids 1,2,3,4,5
    """
    logger.info(f"Creating pairings for cage {cage_id}")
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
        cage = engine.session.query(Cage).get(cage_id)
        if not cage:
            click.secho(f"✗ Cage {cage_id} not found", fg="red", err=True)
            logger.error(f"Cage {cage_id} not found")
            raise click.Abort()
        
        click.echo(f"Creating pairings for cage '{cage.name}'...\n")
        
        with click_spinner.spinner():
            click.echo("Calculating pairings...")
            results = engine.batch_create_pairings(cage_id, guest_id_list)
        
        # Display results
        click.secho(f"✓ Pairings created:", fg="green")
        click.echo(f"  Created:  {results['created']}")
        click.echo(f"  Skipped:  {results['skipped']} (already existed)")
        click.echo(f"  Failed:   {results['failed']}")
        
        total = results['created'] + results['skipped']
        click.echo(f"\nTotal pairings for '{cage.name}': {total}")
        click.echo()
        
        if results['created'] > 0:
            click.secho(
                f"Next step: supramatch match find {cage_id}",
                fg="blue"
            )
            click.echo()
        
        logger.info(
            f"Successfully created {results['created']} pairings "
            f"({results['skipped']} skipped, {results['failed']} failed)"
        )
    
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Failed to create pairings: {e}", exc_info=True)
        raise click.Abort()
    
    finally:
        engine.close()


@match_group.command()
@click.argument('cage_id', type=int)
def info(cage_id: int):
    """
    Show matching information for a cage.
    
    Displays the number of pairings and summary statistics.
    
    Examples:
        supramatch match info 1
    """
    logger.info(f"Getting match info for cage {cage_id}")
    init_db()
    
    engine = MatchingEngine()
    
    try:
        cage = engine.session.query(Cage).get(cage_id)
        
        if not cage:
            click.secho(f"✗ Cage {cage_id} not found", fg="red", err=True)
            logger.error(f"Cage {cage_id} not found")
            raise click.Abort()
        
        # Get pairing statistics
        pairings = [p for p in cage.pairings]
        
        if not pairings:
            click.echo(f"Cage '{cage.name}' has no pairings yet.")
            click.echo()
            click.secho(f"Create pairings with: supramatch match create {cage_id}", fg="blue")
            click.echo()
            return
        
        # Calculate statistics
        pcs = [p.packing_coefficient for p in pairings]
        prices = [p.guest.price_per_gram for p in pairings if p.guest.price_per_gram]
        scores = [p.quality_score for p in pairings]
        
        optimal_count = sum(1 for pc in pcs if 0.3 <= pc <= 0.7)
        
        click.echo(f"\nMatch Information for Cage '{cage.name}':\n")
        click.echo(f"  Total Pairings: {len(pairings)}")
        click.echo(f"  Optimal Fit (0.3-0.7): {optimal_count}")
        
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
@click.argument('cage_id', type=int)
@click.option('--pc-min', default=0.3, type=float, help='Minimum packing coefficient')
@click.option('--pc-max', default=0.7, type=float, help='Maximum packing coefficient')
@click.option('--max-price', default=None, type=float, help='Maximum guest price ($/g)')
@click.option('--min-price', default=None, type=float, help='Minimum guest price ($/g)')
@click.option(
    '--sort',
    default='quality_score',
    type=click.Choice(['quality_score', 'packing_coefficient', 'price']),
    help='Sort results by metric'
)
@click.option('--limit', default=20, type=int, help='Maximum number of results')
def find(cage_id: int, pc_min: float, pc_max: float, max_price: Optional[float], min_price: Optional[float], sort: str, limit: int):
    """
    Find best guest matches for a cage.
    
    Results are evaluated based on packing coefficient (geometric fit),
    price, and other metrics.

    Default packing coefficient ranges:
        0.0-0.3: Loose fit
        0.3-0.7: Optimal fit (recommended)
        0.7-0.9: Snug fit
        0.9-1.0: Very tight fit
    
    Example:
        supramatch match 1
        supramatch match 1 --pc-min 0.3 --pc-max 0.7 --limit 10
        supramatch match 1 --sort price --max-price 5.0
        supramatch match 1 --sort price
    """
    logger.info(
        f"Finding matches for cage {cage_id}: pc={pc_min}-{pc_max}, "
        f"price=${min_price}-${max_price}, sort={sort}, limit={limit}"
    )
    init_db()
    
    engine = MatchingEngine()
    
    try:
        with click_spinner.spinner():
            click.echo("Finding matches...")
            matches = engine.match_guests_to_cage(
                cage_id=cage_id,
                pc_min=pc_min,
                pc_max=pc_max,
                max_price=max_price,
                min_price=min_price,
                sort_by=sort,
                limit=limit
            )
        
        if not matches:
            click.echo(f"No matches found for cage {cage_id}")
            logger.info(f"No matches found for cage {cage_id}")
            return
        
        cage = engine.session.get(Cage, cage_id)

        click.echo(f"\nMatches for cage '{cage.name}' ({format_volume(cage.cavity_volume)}):\n")
        click.echo(f"{'#':<4} {'Guest Name':<25} {'PC':>8} {'$/g':>10} {'Score':>8}")
        click.echo("-" * 95)
        
        for idx, pairing in enumerate(matches, 1):
            guest = pairing.guest
            
            pc_str = format_packing_coefficient(pairing.packing_coefficient)
            price_str = format_price(guest.price_per_gram)

            # Color code by fit
            if pairing.packing_coefficient < 0.3:
                fit_color = 'yellow'
            elif pairing.packing_coefficient <= 0.7:
                fit_color = 'green'
            else:
                fit_color = 'red'
            
            click.echo(
                f"{idx:<4} "
                f"{guest.name:<25} "
                f"{pc_str:>8} "
                f"{price_str:>10} "
                f"{pairing.quality_score:>8.1f} "
            )
        
        click.echo()
        logger.info(f"Found {len(matches)} matches for cage {cage_id}")
    
    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Matching failed: {e}")
        raise click.Abort()
    
    finally:
        engine.close()