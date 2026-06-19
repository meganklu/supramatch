"""
CLI commands for guest operations.

Usage:
    supramatch guest calculate <smiles>
    supramatch guest load <smiles> --name NAME [OPTIONS]
    supramatch guest import <file>
    supramatch guest list [--supplier SUPPLIER] [--limit LIMIT]
    supramatch guest search <query>
    supramatch guest delete <guest_id>

Examples:
    supramatch guest calculate c1ccccc1
    supramatch guest load c1ccccc1 --name Benzene --cas 71-43-2 --price 0.59
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
from supramatch.utils.helpers import format_volume, format_price

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
    Properties calculated: volume and molecular weight.
    
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
@click.option('--mass', '-m', type=float, default=None, help='Molar mass in g/mol')
@click.option('--cas', default=None, help='CAS registry number')
@click.option('--supplier', '-s', default=None, help='Supplier name (e.g., Sigma-Aldrich)')
@click.option('--price', '-p', type=float, default=None, help='Price in USD per gram ($/g)')
@click.option('--state', type=click.Choice(['solid', 'liquid', 'gas']), default=None, help='Physical state')
@click.option('--url', default=None, help='Supplier product URL')
def load(
    smiles: str,
    name: str,
    mass: Optional[float],
    cas: Optional[str],
    supplier: Optional[str],
    price: Optional[float],
    state: Optional[str],
    url: Optional[str]
):
    """
    Load a single guest molecule into the database.
    
    Creates a new guest molecule with calculated properties and
    optional supplier/pricing information.
    
    Examples:
        supramatch guest load c1ccccc1 --name Benzene
        supramatch guest load c1ccccc1 --name Benzene --cas 71-43-2
        supramatch guest load c1ccccc1 --name Benzene --price 0.59 --supplier "Sigma-Aldrich"
        supramatch guest load Cc1ccccc1 --name Toluene --cas 108-88-3 --price 0.45 --state liquid
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
                molar_mass=mass,
                cas_number=cas,
                supplier=supplier,
                price_per_gram=price,
                physical_state=state,
                url=url
            )
        
        click.secho(f"✓ Loaded guest '{guest.name}'", fg="green")
        click.echo(f"  SMILES: {guest.smiles}")
        click.echo(f"  Volume: {format_volume(guest.molecular_volume)}")
        
        if guest.molar_mass:
            click.echo(f"  Molar mass: {guest.molar_mass} g/mol")

        if guest.cas_number:
            click.echo(f"  CAS: {guest.cas_number}")
        
        if guest.supplier:
            click.echo(f"  Supplier: {guest.supplier}")
        
        if guest.price_per_gram:
            click.echo(f"  Price: {format_price(guest.price_per_gram)}")
        
        if guest.physical_state:
            click.echo(f"  State: {guest.physical_state}")
        
        if guest.url:
            click.echo(f"  URL: {guest.url}")
        
        click.echo()
        logger.info(f"Successfully loaded guest: {guest.name}")
    
    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Failed to load guest: {e}")
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
        name, smiles, molar_mass, cas_number, supplier, price_per_gram, physical_state, url
    
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
        
        click.secho(f"✓ Imported {len(guests)} guests", fg="green")
        
        if guests:
            click.echo("\nImported guests:")
            click.echo(f"{'Name':<30} {'Volume':<15} {'Price':<15}")
            click.echo("-" * 60)
            
            for guest in guests[:10]:  # Show first 10
                volume_str = format_volume(guest.molecular_volume)
                price_str = format_price(guest.price_per_gram)
                click.echo(f"{guest.name:<30} {volume_str:<15} {price_str:<15}")
            
            if len(guests) > 10:
                click.echo(f"... and {len(guests) - 10} more")
        
        logger.info(f"Successfully imported {len(guests)} guests")
    
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
@click.option('--supplier', default=None, help='Filter by supplier name')
@click.option('--limit', default=20, type=int, help='Maximum number of guests to display')
def list(supplier: Optional[str], limit: int):
    """
    List guests in database.
    
    Example:
        supramatch guest list
        supramatch guest list --supplier "Sigma-Aldrich"
        supramatch guest list --limit 50
    """
    logger.info(f"Listing guests: supplier={supplier}, limit={limit}")
    init_db()
    
    calc = GuestCalculator()
    
    try:
        if supplier:
            guests = calc.search_guests(supplier=supplier)
        else:
            guests = calc.list_guests(limit=limit)
        
        if not guests:
            click.echo("No guests found")
            logger.info("No guests found")
            return
        
        click.echo(f"\nFound {len(guests)} guests:\n")
        click.echo(f"{'ID':<5} {'Name':<25} {'Volume':<15} {'Price':<12} {'Supplier'}")
        click.echo("-" * 80)
        
        for guest in guests[:limit]:
            volume_str = format_volume(guest.molecular_volume)
            price_str = format_price(guest.price_per_gram)
            supplier_name = guest.supplier if guest.supplier else "N/A"
            
            click.echo(
                f"{guest.id:<5} "
                f"{guest.name:<25} "
                f"{volume_str:<15} "
                f"{price_str:<12} "
                f"{supplier_name}"
            )
        
        if len(guests) > limit:
            click.echo(f"\n... and {len(guests) - limit} more (use --limit to see more)")
        
        logger.info(f"Listed {min(len(guests), limit)} guests")
    
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
        click.echo(f"{'ID':<5} {'Name':<30} {'Volume':<15} {'Price':<12}")
        click.echo("-" * 65)
        
        for guest in guests:
            volume_str = format_volume(guest.molecular_volume)
            price_str = format_price(guest.price_per_gram)
            
            click.echo(
                f"{guest.id:<5} "
                f"{guest.name:<30} "
                f"{volume_str:<15} "
                f"{price_str:<12}"
            )
        
        logger.info(f"Found {len(guests)} matches")
    
    finally:
        calc.close()


@guest_group.command()
@click.argument('guest_id', type=int)
@click.confirmation_option(prompt='Are you sure you want to delete this guest? This will also delete all associated pairings.')
def delete(guest_id: int):
    """
    Delete a guest from the database.
    
    WARNING: This will also delete all host-guest pairings for this guest.

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