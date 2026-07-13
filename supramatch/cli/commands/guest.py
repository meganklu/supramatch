"""
CLI commands for guest operations.

Usage:
    supramatch guest calculate <smiles>
    supramatch guest load <smiles> --name NAME [OPTIONS]
    supramatch guest fetch <query>
    supramatch guest import <file>
    supramatch guest list [--limit LIMIT]
    supramatch guest search <query>
    supramatch guest delete <guest_id>

Examples:
    supramatch guest calculate c1ccccc1
    supramatch guest load c1ccccc1 --name Benzene --cas 71-43-2
    supramatch guest fetch aspirin
    supramatch guest fetch 50-78-2
    supramatch guest import guests.csv
    supramatch guest list
    supramatch guest search benzene
    supramatch guest delete 1
"""

import click
import click_spinner
import logging
from typing import Optional
from supramatch.db.database import init_db
from supramatch.modules.guest_calc import GuestCalculator
from supramatch.utils.helpers import format_volume

logger = logging.getLogger(__name__)


@click.group()
def guest_group():
    """
    Commands for managing guest molecules.

    Guests are molecules that can fit inside cage cavities.
    Use these commands to add, view, and manage guest data.
    """
    pass


@guest_group.command()
@click.argument('smiles')
def calculate(smiles: str):
    """Calculate properties for a molecule from SMILES.

    SMILES is a notation for representing chemical structures.
    Properties calculated: volume.

    Example:
        supramatch guest calculate c1ccccc1
        supramatch guest calculate Cc1ccccc1
    """
    logger.info(f"Calculating properties for SMILES: {smiles}")

    calc = GuestCalculator()

    try:
        with click_spinner.spinner():
            click.echo("Calculating molecular properties...")
            volume = calc.calculate_volume(smiles)

        click.secho(f"✓ Molecular Properties:", fg="green")
        click.echo(f"  SMILES: {smiles}")
        click.echo(f"  Volume: {format_volume(volume)}")

        logger.info(f"Calculated: volume={format_volume(volume)}")

    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Calculation failed: {e}")
        raise click.Abort()

    finally:
        calc.close()

@guest_group.command()
@click.argument('smiles')
@click.option('--name', '-n', required=True, help='Guest molecule name')
@click.option('--molecular-weight', '-w', type=float, default=None, help='Molecular weight in g/mol')
@click.option('--iupac-name', default=None, help='Formal IUPAC name')
@click.option('--formula', default=None, help='Molecular formula, e.g. C9H8O4')
@click.option('--cas', default=None, help='CAS registry number')
@click.option('--state', type=click.Choice(['solid', 'liquid', 'gas']), default=None, help='Physical state')
def load(
    smiles: str,
    name: str,
    molecular_weight: Optional[float],
    iupac_name: Optional[str],
    formula: Optional[str],
    cas: Optional[str],
    state: Optional[str],
):
    """
    Load a single guest molecule into the database.

    Creates a new guest molecule with calculated properties. For pricing,
    use `supramatch price lookup` once matches exist for it.

    Examples:
        supramatch guest load c1ccccc1 --name Benzene
        supramatch guest load c1ccccc1 --name Benzene --cas 71-43-2
        supramatch guest load Cc1ccccc1 --name Toluene --cas 108-88-3 --state liquid
    """
    logger.info(f"Loading guest: {name} (SMILES: {smiles})")
    init_db()

    calc = GuestCalculator()

    try:
        with click_spinner.spinner():
            click.echo(f"Creating guest molecule {name}...")
            guest = calc.create_guest(
                name=name,
                smiles=smiles,
                molecular_weight=molecular_weight,
                iupac_name=iupac_name,
                molecular_formula=formula,
                cas_number=cas,
                physical_state=state,
            )

        click.secho(f"✓ Loaded guest '{guest.name}'", fg="green")
        click.echo(f"  SMILES: {guest.smiles}")
        click.echo(f"  Volume: {format_volume(guest.molecular_volume)}")

        if guest.molecular_weight:
            click.echo(f"  Molecular weight: {guest.molecular_weight} g/mol")

        if guest.molecular_formula:
            click.echo(f"  Formula: {guest.molecular_formula}")

        if guest.iupac_name:
            click.echo(f"  IUPAC name: {guest.iupac_name}")

        if guest.cas_number:
            click.echo(f"  CAS: {guest.cas_number}")

        if guest.physical_state:
            click.echo(f"  State: {guest.physical_state}")

        click.echo()
        logger.info(f"Successfully loaded guest: {guest.name}")

    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Failed to load guest: {e}")
        raise click.Abort()

    finally:
        calc.close()


@guest_group.command()
@click.argument('query')
@click.option('--name', '-n', default=None, help="Override the guest name (defaults to PubChem's Title, falling back to IUPAC name, falling back to the query)")
@click.option('--state', type=click.Choice(['solid', 'liquid', 'gas']), default=None, help='Physical state (not available from PubChem -- see `guest load` docs)')
def fetch(query: str, name: Optional[str], state: Optional[str]):
    """
    Fetch a compound from PubChem and add it as a guest.

    Looks up the compound by name or CAS number, retrieves its SMILES,
    molecular weight, IUPAC name, molecular formula, and CAS number, then
    calculates its volume and creates a guest. For pricing, use `supramatch
    price lookup` once matches exist for it.

    Example:
        supramatch guest fetch aspirin
        supramatch guest fetch 50-78-2
        supramatch guest fetch aspirin --name "My Aspirin"
    """
    logger.info(f"Fetching guest from PubChem: {query}")
    init_db()

    calc = GuestCalculator()

    try:
        with click_spinner.spinner():
            click.echo(f"Looking up '{query}' on PubChem...")
            guest = calc.create_guest_from_pubchem(query, name=name, physical_state=state)

        click.secho(f"✓ Fetched guest '{guest.name}' (PubChem CID {guest.pubchem_cid})", fg="green")
        click.echo(f"  SMILES: {guest.smiles}")
        click.echo(f"  Volume: {format_volume(guest.molecular_volume)}")

        if guest.molecular_weight:
            click.echo(f"  Molecular weight: {guest.molecular_weight} g/mol")

        if guest.molecular_formula:
            click.echo(f"  Formula: {guest.molecular_formula}")

        if guest.iupac_name:
            click.echo(f"  IUPAC name: {guest.iupac_name}")

        if guest.cas_number:
            click.echo(f"  CAS: {guest.cas_number}")

        click.echo()
        logger.info(f"Successfully fetched guest: {guest.name}")

    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Failed to fetch guest from PubChem: {e}")
        raise click.Abort()

    finally:
        calc.close()


@guest_group.command(name='import')
@click.argument('file', type=click.Path(exists=True))
def import_guests(file: str):
    """
    Import guests from a file.

    Supports CSV, XML, and JSON formats.

    CSV format should have columns:
        name, smiles, molecular_weight, iupac_name, molecular_formula, cas_number, physical_state

    Example:
        supramatch guest import guests.csv
        supramatch guest import guests.xml
        supramatch guest import guests.json
    """
    logger.info(f"Importing guests from file: {file}")
    init_db()

    calc = GuestCalculator()

    try:
        with click_spinner.spinner():
            click.echo("Importing guests...")
            guests = calc.import_from_file(file)

        click.secho(f"✓ Imported {len(guests)} guest(s)", fg="green")

        if guests:
            click.echo("\nImported guest(s):")
            click.echo(f"{'Name':<30} {'Volume':<15} {'Formula':<15}")
            click.echo("-" * 60)

            for guest in guests[:10]:  # Show first 10
                volume_str = format_volume(guest.molecular_volume)
                formula_str = guest.molecular_formula or "N/A"
                click.echo(f"{guest.name:<30} {volume_str:<15} {formula_str:<15}")

            if len(guests) > 10:
                click.echo(f"... and {len(guests) - 10} more")

        logger.info(f"Successfully imported {len(guests)} guest(s)")

    except FileNotFoundError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"File not found: {e}")
        raise click.Abort()

    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Import failed: {e}")
        raise click.Abort()

    finally:
        calc.close()


@guest_group.command()
@click.option('--limit', '-l', default=20, type=int, help='Maximum number of guests to display')
def list(limit: int):
    """
    List guests in database.

    Example:
        supramatch guest list
        supramatch guest list --limit 50
    """
    logger.info(f"Listing guest(s): limit={limit}")
    init_db()

    calc = GuestCalculator()

    try:
        guests = calc.list_guests(limit=limit)

        if not guests:
            click.echo("No guests found")
            logger.info("No guests found")
            return

        click.echo(f"\nFound {len(guests)} guest(s):\n")
        click.echo(f"{'ID':<5} {'Name':<25} {'Volume':<15} {'Formula':<12} {'CAS'}")
        click.echo("-" * 80)

        for guest in guests[:limit]:
            volume_str = format_volume(guest.molecular_volume)
            formula_str = guest.molecular_formula or "N/A"
            cas_str = guest.cas_number or "N/A"

            click.echo(
                f"{guest.id:<5} "
                f"{guest.name:<25} "
                f"{volume_str:<15} "
                f"{formula_str:<12} "
                f"{cas_str}"
            )

        if len(guests) > limit:
            click.echo(f"\n... and {len(guests) - limit} more (use --limit to see more)")

        logger.info(f"Listed {min(len(guests), limit)} guest(s)")

    finally:
        calc.close()


@guest_group.command()
@click.argument('query')
def search(query: str):
    """
    Search for guests by name.

    Example:
        supramatch guest search benzene
        supramatch guest search toluene
    """
    logger.info(f"Searching for guests: {query}")
    init_db()

    calc = GuestCalculator()

    try:
        guests = calc.search_guests(name_pattern=query)

        if not guests:
            click.echo(f"No guests found matching '{query}'")
            logger.info(f"No matches for: {query}")
            return

        click.echo(f"\nFound {len(guests)} guest(s) matching '{query}':\n")
        click.echo(f"{'ID':<5} {'Name':<30} {'Volume':<15} {'Formula'}")
        click.echo("-" * 65)

        for guest in guests:
            volume_str = format_volume(guest.molecular_volume)
            formula_str = guest.molecular_formula or "N/A"

            click.echo(
                f"{guest.id:<5} "
                f"{guest.name:<30} "
                f"{volume_str:<15} "
                f"{formula_str}"
            )

        logger.info(f"Found {len(guests)} match(es)")

    finally:
        calc.close()


@guest_group.command()
@click.argument('guest_id', type=int)
@click.confirmation_option(prompt='Are you sure you want to delete this guest? This will also delete all associated matches and prices.')
def delete(guest_id: int):
    """
    Delete a guest from the database.

    WARNING: This will also delete all host-guest matches and stored
    price quotes for this guest.

    Example:
        supramatch guest delete 1
    """
    logger.info(f"Deleting guest: {guest_id}")
    init_db()

    calc = GuestCalculator()

    try:
        if calc.delete_guest(guest_id):
            click.secho(f"✓ Deleted guest {guest_id}", fg="green")
            logger.info(f"Deleted guest {guest_id}")
        else:
            click.secho(f"✗ Guest {guest_id} not found", fg="red", err=True)
            logger.warning(f"Guest {guest_id} not found")
            raise click.Abort()

    finally:
        calc.close()
