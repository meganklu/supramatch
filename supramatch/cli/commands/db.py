"""
CLI commands for database management.

Usage:
    supramatch db init
    supramatch db reset
    supramatch db drop
    supramatch db status
"""

import click
import logging
from sqlalchemy import select, func
from supramatch.db.database import init_db, reset_db, drop_all_tables, get_session
from supramatch.db.models import Cage, Guest, HostGuestPairing

logger = logging.getLogger(__name__)


@click.group()
def db_group():
    """
    Commands for database management.

    Initialize, reset, or manage the database.
    """
    pass


@db_group.command()
def init():
    """
    Initialize the database.

    Creates all necessary tables for cages, guests, and pairings.
    Safe to run multiple times.
    
    Example:
        supramatch db init
    """
    logger.info("Initializing database")
    click.echo("Initializing database...")
    
    try:
        init_db()
        click.secho("✓ Database initialized successfully", fg="green")
        click.echo()
        logger.info("Database initialized successfully")
    
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Database initialization failed: {e}")
        raise click.Abort()


@db_group.command()
@click.confirmation_option(prompt='WARNING: This will erase ALL data! Continue?')
def reset():
    """
    Reset the database.

    Drops all tables and recreates them. All data will be lost.
    
    WARNING: This is destructive and cannot be undone!
    
    Example:
        supramatch db reset
    """
    logger.warning("Resetting database - destructive operation")
    click.echo("Resetting database...")
    
    try:
        reset_db()
        click.secho("✓ Database reset successfully", fg="green")
        click.echo()       
        logger.info("Database reset successfully")
    
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Database reset failed: {e}")
        raise click.Abort()


@db_group.command()
@click.confirmation_option(prompt='WARNING: This will erase ALL data! Continue?')
def drop():
    """
    Drop all tables from database.
    
    WARNING: This is destructive and cannot be undone!
    
    Example:
        supramatch db drop
    """
    logger.warning("Dropping all tables - destructive operation")
    click.echo("Dropping all tables...")
    
    try:
        drop_all_tables()
        click.secho("✓ All tables dropped", fg="green")
        click.echo()
        logger.info("All tables dropped successfully")
    
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Drop failed: {e}")
        raise click.Abort()


@db_group.command()
def status():
    """
    Show database status.

    Display counts of cages, guests, and pairings in the database.
    
    Example:
        supramatch db status
    """
    logger.info("Checking database status")
    
    try:
        init_db()

        with get_session() as session:
            cage_count = session.scalar(select(func.count()).select_from(Cage))
            guest_count = session.scalar(select(func.count()).select_from(Guest))
            pairing_count = session.scalar(select(func.count()).select_from(HostGuestPairing))
        
        click.echo("\nDatabase Status:")
        click.echo(f"  Cage(s): {cage_count}")
        click.echo(f"  Guest(s): {guest_count}")
        click.echo(f"  Pairing(s): {pairing_count}")
        click.echo()
        
        logger.info(f"Database status: {cage_count} cage(s), {guest_count} guest(s), {pairing_count} pairing(s)")
    
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        logger.error(f"Status check failed: {e}")
        raise click.Abort()