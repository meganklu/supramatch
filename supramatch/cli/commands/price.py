"""
CLI commands for vendor price lookups.

Usage:
    supramatch price lookup --cage <cage_id> [--all-matches] [--refresh]
    supramatch price lookup --guest <guest_id> [--refresh]
    supramatch price list <guest_id>

Examples:
    supramatch price lookup --cage 1
    supramatch price lookup --cage 1 --all-matches --refresh
    supramatch price lookup --guest 5
    supramatch price list 5
"""

import re
import click
import logging
from typing import List, Optional
from supramatch.db.database import init_db, get_connection
from supramatch.db import queries
from supramatch.models.guest import Guest
from supramatch.modules.matcher import MatchingEngine
from supramatch.discovery.price_lookup import PriceLookup
from supramatch.utils.helpers import format_price, truncate

logger = logging.getLogger(__name__)

# Matches SMILES isotope labels like [2H], [13C], [15N] -- a leading mass
# number inside the brackets, distinct from other bracket atoms ([C@H],
# [NH4+], [Fe]) which start with a letter. See discovery/price_lookup.py's
# module docstring for why this matters: vendor searches are exact-structure
# matches, so an isotope-labeled guest can find zero hits even when its
# unlabeled parent compound is widely available.
_ISOTOPE_PATTERN = re.compile(r'\[\d+[A-Za-z]')


def _isotope_labeled_guests(guests: List[Guest]) -> List[Guest]:
    return [g for g in guests if _ISOTOPE_PATTERN.search(g.smiles)]


@click.group()
def price_group():
    """
    Commands for vendor price lookups (Mcule, Molport, and Chemspace via ChemPrice).
    """
    pass


@price_group.command()
@click.option('--cage', 'cage_id', type=int, default=None, help="Look up prices for guests in this cage's matches")
@click.option('--guest', 'guest_id', type=int, default=None, help='Look up price for a single guest')
@click.option('--all-matches', is_flag=True, help="With --cage, price every matched guest instead of only viable ones")
@click.option('--refresh', is_flag=True, help='Re-query even if a recent price already exists')
def lookup(cage_id: Optional[int], guest_id: Optional[int], all_matches: bool, refresh: bool):
    """
    Look up vendor prices via ChemPrice (Mcule, Molport, Chemspace).

    With --cage, only guests in matches that are viable by the app's
    default packing-coefficient target are priced by default (saves API
    calls on poor geometric fits) -- pass --all-matches to price every
    matched guest regardless of fit.

    Example:
        supramatch price lookup --cage 1
        supramatch price lookup --cage 1 --all-matches --refresh
        supramatch price lookup --guest 5
    """
    if not cage_id and not guest_id:
        click.secho("✗ Error: specify --cage or --guest", fg="red", err=True)
        raise click.Abort()

    if cage_id and guest_id:
        click.secho("✗ Error: specify only one of --cage or --guest", fg="red", err=True)
        raise click.Abort()

    logger.info(f"Looking up prices: cage_id={cage_id}, guest_id={guest_id}, all_matches={all_matches}, refresh={refresh}")
    init_db()

    engine = MatchingEngine()

    try:
        queried_guests: List[Guest] = []

        if guest_id:
            guest = engine.get_guest(guest_id)
            if not guest:
                click.secho(f"✗ Guest {guest_id} not found", fg="red", err=True)
                raise click.Abort()

            click.echo(f"Looking up prices for guest '{guest.name}'...")
            price_lookup = PriceLookup()
            results = price_lookup.lookup_and_store(engine.conn, [guest], refresh=refresh)
            queried_guests = [guest]

        else:
            cage = engine.get_cage(cage_id)
            if not cage:
                click.secho(f"✗ Cage {cage_id} not found", fg="red", err=True)
                raise click.Abort()

            click.echo(f"Looking up prices for cage '{cage.name}' matches...")
            results = engine.price_viable_matches(cage_id, only_viable=not all_matches, refresh=refresh)

            matches = engine.list_matches_for_cage(cage_id)
            if not all_matches:
                matches = [m for m in matches if m.is_viable]
            queried_guests = queries.get_guests_by_ids(engine.conn, [m.guest_id for m in matches])

        click.secho("✓ Price lookup complete:", fg="green")
        click.echo(f"  Queried: {results['queried']}")
        click.echo(f"  Skipped (recently priced): {results['skipped']}")
        click.echo(f"  Priced:  {results['priced']}")
        click.echo()

        if results['priced'] == 0 and results['queried'] > 0:
            isotope_guests = _isotope_labeled_guests(queried_guests)
            if isotope_guests:
                names = ", ".join(g.name for g in isotope_guests)
                click.secho(
                    f"Tip: {names} ha{'s' if len(isotope_guests) == 1 else 've'} an isotope-labeled "
                    f"SMILES (e.g. [2H]). Vendor searches require an exact structure match, so the "
                    f"unlabeled parent compound may be available even though this exact isotopologue "
                    f"wasn't found.",
                    fg="yellow",
                )
                click.echo()

        logger.info(f"Price lookup complete: {results}")

    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Price lookup failed: {e}", exc_info=True)
        raise click.Abort()

    finally:
        engine.close()


@price_group.command(name='list')
@click.argument('guest_id', type=int)
def list_prices(guest_id: int):
    """
    Show stored vendor price quotes for a guest.

    Example:
        supramatch price list 5
    """
    logger.info(f"Listing prices for guest {guest_id}")
    init_db()
    conn = get_connection()

    prices = queries.list_prices_for_guest(conn, guest_id)

    if not prices:
        click.echo(f"No price quotes stored for guest {guest_id}")
        logger.info(f"No prices found for guest {guest_id}")
        return

    click.echo(f"\nPrice quotes for '{prices[0].guest_name}':\n")
    click.echo(f"{'Source':<12} {'Supplier':<20} {'Purity':<10} {'Quoted':<16} {'$/g':>10} {'$/mol':>12} {'$/L':>10}")
    click.echo("-" * 96)

    for p in prices:
        if p.price_usd is not None and p.amount and p.measure:
            quoted_str = f"{format_price(p.price_usd)}/{p.amount:g}{p.measure}"
        else:
            quoted_str = format_price(p.price_usd)

        usd_per_mol_str = format_price(p.usd_per_mol)
        usd_per_liter_str = format_price(p.usd_per_liter)
        purity_str = f"{p.purity:g}%" if p.purity is not None else "N/A"

        click.echo(
            f"{p.source or '':<12} "
            f"{truncate(p.supplier_name or 'N/A', 20):<20} "
            f"{purity_str[:10]:<10} "
            f"{quoted_str:<16} "
            f"{format_price(p.usd_per_gram):>10} "
            f"{usd_per_mol_str:>12} "
            f"{usd_per_liter_str:>10}"
        )

    click.echo()
    logger.info(f"Listed {len(prices)} price quote(s) for guest {guest_id}")
