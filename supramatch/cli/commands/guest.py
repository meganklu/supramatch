"""
CLI commands for guest operations.

Usage:
    supramatch guest calculate <smiles>
    supramatch guest load <smiles> --name NAME [OPTIONS]
    supramatch guest fetch <query>
    supramatch guest import <file>
    supramatch guest list [--limit LIMIT]
    supramatch guest search <query>
    supramatch guest batch-create [IDENTIFIERS]... [--file FILE] [--in-inventory]
    supramatch guest set-inventory <guest_id> <in|out>
    supramatch guest show <guest_id>
    supramatch guest delete <guest_id>

Examples:
    supramatch guest calculate c1ccccc1
    supramatch guest load c1ccccc1 --name Benzene --cas 71-43-2
    supramatch guest fetch aspirin
    supramatch guest fetch 50-78-2
    supramatch guest import guests.csv
    supramatch guest list
    supramatch guest search benzene
    supramatch guest batch-create 50-78-2 58-08-2 --in-inventory
    supramatch guest batch-create --file cas_list.txt --in-inventory
    supramatch guest set-inventory 1 in
    supramatch guest show 1
    supramatch guest delete 1
"""

import click
import click_spinner
import logging
from typing import Optional
from supramatch.db.database import init_db
from supramatch.modules.guest_calc import GuestCalculator
from supramatch.utils.helpers import format_volume, truncate

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
        click.echo(f"  Rotatable bonds: {guest.rotatable_bonds}")

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
        click.echo(f"  Rotatable bonds: {guest.rotatable_bonds}")

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
            click.echo(f"{'Name':<30} {'Formula':<12} {'Volume':<15} {'NRB':<5} {'CAS'}")
            click.echo("-" * 75)

            for guest in guests[:10]:  # Show first 10
                volume_str = format_volume(guest.molecular_volume)
                formula_str = guest.molecular_formula or "N/A"
                nrb_str = str(guest.rotatable_bonds) if guest.rotatable_bonds is not None else "N/A"
                cas_str = guest.cas_number or "N/A"
                click.echo(f"{truncate(guest.name, 30):<30} {formula_str:<12} {volume_str:<15} {nrb_str:<5} {cas_str}")

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
        click.echo(f"{'ID':<5} {'Name':<25} {'Formula':<10} {'MW (g/mol)':<12} {'Volume':<15} {'NRB':<5} {'State':<8} {'Inv':<4} {'CAS'}")
        click.echo("-" * 110)

        for guest in guests[:limit]:
            volume_str = format_volume(guest.molecular_volume)
            formula_str = guest.molecular_formula or "N/A"
            mw_str = f"{guest.molecular_weight:.2f}" if guest.molecular_weight else "N/A"
            nrb_str = str(guest.rotatable_bonds) if guest.rotatable_bonds is not None else "N/A"
            state_str = guest.physical_state or "N/A"
            inv_str = "✓" if guest.in_inventory else "✗"
            cas_str = guest.cas_number or "N/A"

            click.echo(
                f"{guest.id:<5} "
                f"{truncate(guest.name, 25):<25} "
                f"{formula_str:<10} "
                f"{mw_str:<12} "
                f"{volume_str:<15} "
                f"{nrb_str:<5} "
                f"{state_str:<8} "
                f"{inv_str:<4} "
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
        click.echo(f"{'ID':<5} {'Name':<30} {'Formula':<10} {'MW (g/mol)':<12} {'Volume':<15} {'NRB':<5} {'State':<8} {'Inv':<4} {'CAS'}")
        click.echo("-" * 110)

        for guest in guests:
            volume_str = format_volume(guest.molecular_volume)
            formula_str = guest.molecular_formula or "N/A"
            mw_str = f"{guest.molecular_weight:.2f}" if guest.molecular_weight else "N/A"
            nrb_str = str(guest.rotatable_bonds) if guest.rotatable_bonds is not None else "N/A"
            state_str = guest.physical_state or "N/A"
            inv_str = "✓" if guest.in_inventory else "✗"
            cas_str = guest.cas_number or "N/A"

            click.echo(
                f"{guest.id:<5} "
                f"{truncate(guest.name, 30):<30} "
                f"{formula_str:<10} "
                f"{mw_str:<12} "
                f"{volume_str:<15} "
                f"{nrb_str:<5} "
                f"{state_str:<8} "
                f"{inv_str:<4} "
                f"{cas_str}"
            )

        logger.info(f"Found {len(guests)} match(es)")

    finally:
        calc.close()


@guest_group.command(name='batch-create')
@click.argument('identifiers', nargs=-1)
@click.option('--file', '-f', type=click.Path(exists=True), default=None, help='File with one name or CAS number per line')
@click.option('--in-inventory', is_flag=True, default=False, help='Mark every guest touched (created or already existing) as in inventory')
def batch_create(identifiers: tuple, file: Optional[str], in_inventory: bool):
    """
    Create guests in bulk from a list of names or CAS numbers, resolving
    each via PubChem.

    Identifiers that already exist in the database (matched by CAS number
    or SMILES) are reused rather than duplicated. If a matched guest doesn't
    have a CAS number on file yet and the identifier that matched it was
    itself a CAS number, that CAS number is backfilled onto the guest.
    Combine identifiers given directly with --file; each is looked up
    individually on PubChem, so large lists take a while.

    Examples:
        supramatch guest batch-create 50-78-2 58-08-2
        supramatch guest batch-create aspirin caffeine --in-inventory
        supramatch guest batch-create --file cas_list.txt --in-inventory
    """
    all_identifiers = [*identifiers]

    if file:
        with open(file, 'r', encoding='utf-8') as f:
            all_identifiers += [line.strip() for line in f if line.strip()]

    if not all_identifiers:
        click.secho("✗ Error: No identifiers given (pass them as arguments or via --file)", fg="red", err=True)
        raise click.Abort()

    logger.info(f"Batch creating {len(all_identifiers)} guest(s), in_inventory={in_inventory}")
    init_db()

    calc = GuestCalculator()

    try:
        with click_spinner.spinner():
            click.echo(f"Resolving {len(all_identifiers)} identifier(s) via PubChem...")
            results = calc.batch_create_from_identifiers(
                all_identifiers,
                mark_in_inventory=in_inventory,
            )

        click.secho(f"✓ Batch create complete:", fg="green")
        click.echo(f"  Created:         {len(results['created'])}")
        click.echo(f"  Already existed: {len(results['matched'])}")
        click.echo(f"  CAS backfilled:  {len(results['cas_filled'])}")
        click.echo(f"  Failed:          {len(results['failed'])}")

        if results['cas_filled']:
            click.echo("\nCAS number backfilled for:")
            for guest in results['cas_filled']:
                click.echo(f"  {guest.name}: {guest.cas_number}")

        if results['failed']:
            click.echo("\nFailed identifiers:")
            for item in results['failed']:
                click.echo(f"  {item['identifier']}: {item['error']}")

        click.echo()
        logger.info(
            f"Batch create complete: {len(results['created'])} created, "
            f"{len(results['matched'])} matched ({len(results['cas_filled'])} CAS-backfilled), "
            f"{len(results['failed'])} failed"
        )

    finally:
        calc.close()


@guest_group.command(name='set-inventory')
@click.argument('guest_id', type=int)
@click.argument('status', type=click.Choice(['in', 'out']))
def set_inventory(guest_id: int, status: str):
    """
    Mark whether a guest is currently in our physical inventory.

    This is separate from vendor pricing/availability -- a guest can be
    purchasable without us actually having it on hand.

    Example:
        supramatch guest set-inventory 1 in
        supramatch guest set-inventory 1 out
    """
    logger.info(f"Setting inventory status for guest {guest_id}: {status}")
    init_db()

    calc = GuestCalculator()

    try:
        guest = calc.set_inventory(guest_id, in_inventory=(status == 'in'))

        if not guest:
            click.secho(f"✗ Guest {guest_id} not found", fg="red", err=True)
            logger.warning(f"Guest {guest_id} not found")
            raise click.Abort()

        if guest.in_inventory:
            click.secho(f"✓ '{guest.name}' marked as in inventory", fg="green")
        else:
            click.secho(f"✓ '{guest.name}' marked as not in inventory", fg="green")

        logger.info(f"Set inventory status for '{guest.name}' to {guest.in_inventory}")

    finally:
        calc.close()


@guest_group.command()
@click.argument('guest_id', type=int)
def show(guest_id: int):
    """
    Show details for a specific guest.

    Example:
        supramatch guest show 1
    """
    logger.info(f"Showing guest details: {guest_id}")
    init_db()

    calc = GuestCalculator()

    try:
        guest = calc.get_guest(guest_id=guest_id)

        if not guest:
            click.secho(f"✗ Guest {guest_id} not found", fg="red", err=True)
            logger.warning(f"Guest {guest_id} not found")
            raise click.Abort()

        click.echo(f"\nGuest: {guest.name}")
        click.echo(f"  ID: {guest.id}")
        click.echo(f"  SMILES: {guest.smiles}")
        click.echo(f"  Volume: {format_volume(guest.molecular_volume)}")
        click.echo(f"  Rotatable bonds: {guest.rotatable_bonds if guest.rotatable_bonds is not None else 'N/A'}")

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

        if guest.pubchem_cid:
            click.echo(f"  PubChem CID: {guest.pubchem_cid}")

        click.echo(f"  In inventory: {'✓' if guest.in_inventory else '✗'}")

        if guest.created_at:
            click.echo(f"  Created: {guest.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        click.echo()
        logger.info(f"Displayed guest {guest_id}")

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
