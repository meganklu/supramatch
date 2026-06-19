"""
CLI commands for cage operations.

Usage:
    supramatch cage load <pdb_file> [--name NAME] [--cas CAS]
    supramatch cage list [--limit LIMIT]
    supramatch cage show <cage_id> [--recalculate]
    supramatch cage delete <cage_id>

Examples:
    supramatch cage load data/cage.pdb --name MyCage
    supramatch cage list
    supramatch cage show 1
    supramatch cage delete 1
"""

import click
import click_spinner
import logging
from typing import Optional
from supramatch.db.database import init_db
from supramatch.modules.cage_calc import CageCalculator
from supramatch.utils.helpers import format_volume

logger = logging.getLogger(__name__)


@click.group()
def cage_group():
    """
    Commands for managing cages.
    
    Cages are metal-organic cage host structures. Use these commands
    to load, view, and manage cage data.
    """
    pass


@cage_group.command()
@click.argument('pdb_file', type=click.Path(exists=True))
@click.option('--name', '-n', default=None, help='Cage name (extracted from PDB if not provided)')
@click.option('--cas', default=None, help='CAS registry number')
def load(pdb_file: str, name: Optional[str], cas: Optional[str]):
    """
    Load a cage from a PDB file.

    The PDB file should contain the 3D structure of the cage.
    The cavity volume will be automatically calculated.

    Example:
        supramatch cage load data/cage.pdb --name MyCage
        supramatch cage load data/cage.pdb --name MyCage --cas 123-45-6
    """
    logger.info(f"Loading cage from: {pdb_file}")
    init_db()
    
    calculator = CageCalculator()
    
    try:
        with click_spinner.spinner():
            click.echo("Calculating cavity volume...")
            cage = calculator.create_cage(pdb_file, name, cas)
        
        volume_str = format_volume(cage.cavity_volume)
        click.secho(f"✓ Loaded cage '{cage.name}'", fg="green")
        click.echo(f"  Volume: {volume_str}")
        if cage.cas_number:
            click.echo(f"  CAS: {cage.cas_number}")
        click.echo(f"  PDB: {cage.pdb_file}")
        
        logger.info(f"Successfully loaded cage: {cage.name}")
    
    except FileNotFoundError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"File not found: {e}")
        raise click.Abort()
    
    except ValueError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Validation error: {e}")
        raise click.Abort()
    
    finally:
        calculator.close()


@cage_group.command()
@click.option('--limit', default=None, type=int, help='Maximum number of cages to display')
def list(limit: Optional[int]):
    """
    List all cages in database.
    
    Example:
        supramatch cage list
        supramatch cage list --limit 10
    """
    logger.info("Listing cages from database")
    init_db()
    
    calculator = CageCalculator()
    
    try:
        cages = calculator.list_cages()
        
        if not cages:
            click.echo("No cages found in database")
            logger.info("No cages found")
            return
        
        if limit:
            cages = cages[:limit]
        
        click.echo(f"\nFound {len(cages)} cages:\n")
        click.echo(f"{'ID':<5} {'Name':<25} {'Volume':<15} {'PDB File'}")
        click.echo("-" * 80)
        
        for cage in cages:
            volume_str = format_volume(cage.cavity_volume)
            pdb_file = cage.pdb_file if cage.pdb_file else "N/A"
            
            # Truncate long paths
            if len(pdb_file) > 35:
                pdb_file = "..." + pdb_file[-32:]
            
            click.echo(
                f"{cage.id:<5} "
                f"{cage.name:<25} "
                f"{volume_str:<15} "
                f"{pdb_file}"
            )
        
        logger.info(f"Listed {len(cages)} cages")
    
    finally:
        calculator.close()


@cage_group.command()
@click.argument('cage_id', type=int)
@click.option('--recalculate', is_flag=True, help='Recalculate volume from PDB file')
def show(cage_id: int, recalculate: bool):
    """
    Show details for a specific cage.
    
    Example:
        supramatch cage show 1
        supramatch cage show 1 --recalculate
    """
    logger.info(f"Showing cage details: {cage_id}")
    init_db()
    
    calculator = CageCalculator()
    
    try:
        cage = calculator.get_cage(cage_id=cage_id)
        
        if not cage:
            click.secho(f"✗ Cage {cage_id} not found", fg="red", err=True)
            logger.warning(f"Cage {cage_id} not found")
            raise click.Abort()
        
        click.echo(f"\nCage: {cage.name}")
        click.echo(f"  ID: {cage.id}")
        click.echo(f"  Volume: {format_volume(cage.cavity_volume)}")
        if cage.cas_number:
            click.echo(f"  CAS: {cage.cas_number}")
        click.echo(f"  PDB: {cage.pdb_file}")
        click.echo(f"  Created: {cage.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"  Pairings: {cage.pairing_count}")
        
        if recalculate and cage.pdb_file:
            try:
                with click_spinner.spinner():
                    click.echo("Recalculating volume...")
                    new_vol = calculator.update_cage_volume(cage_id, recalculate=True)
                
                click.secho(f"✓ Updated volume: {format_volume(new_vol)}", fg="green")
                logger.info(f"Recalculated cage volume: {new_vol}")
            
            except ValueError as e:
                click.secho(f"✗ Recalculation failed: {e}", fg="red", err=True)
                logger.error(f"Recalculation failed: {e}")
        
        click.echo()
        logger.info(f"Displayed cage {cage_id}")
    
    finally:
        calculator.close()


@cage_group.command()
@click.argument('cage_id', type=int)
@click.confirmation_option(prompt='Are you sure you want to delete this cage? This will also delete all associated pairings.')
def delete(cage_id: int):
    """
    Delete a cage from the database.
    
    WARNING: This will also delete all host-guest pairings for this cage.

    Example:
        supramatch cage delete 1
    """
    logger.info(f"Deleting cage: {cage_id}")
    init_db()
    
    calculator = CageCalculator()
    
    try:
        if calculator.delete_cage(cage_id):
            click.secho(f"✓ Deleted cage {cage_id}", fg="green")
            logger.info(f"Deleted cage {cage_id}")
        else:
            click.secho(f"✗ Cage {cage_id} not found", fg="red", err=True)
            logger.warning(f"Cage {cage_id} not found")
            raise click.Abort()
    
    finally:
        calculator.close()