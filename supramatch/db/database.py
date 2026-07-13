"""
Database connection and schema management.

Uses Python's built-in sqlite3 module directly (no ORM).
"""

import sqlite3
import logging
from typing import Optional
from supramatch.config import DATABASE_PATH
from supramatch.db.schema import ALL_TABLES, CREATE_INDEXES

logger = logging.getLogger(__name__)

_connection: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    """
    Get the shared SQLite connection, opening it on first use.

    Returns:
        sqlite3.Connection: Connection with row_factory set to sqlite3.Row
        (dict-like access by column name) and foreign key enforcement enabled.

    Example:
        >>> from supramatch.db import get_connection
        >>> conn = get_connection()
        >>> row = conn.execute("SELECT * FROM cages WHERE id = ?", (1,)).fetchone()
    """
    global _connection
    if _connection is None:
        logger.debug(f"Opening database connection: {DATABASE_PATH}")
        _connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
    return _connection


def close_connection() -> None:
    """
    Close the shared database connection.

    Notes:
        - Safe to call even if no connection is open
        - The next get_connection() call reopens a fresh connection

    Example:
        >>> from supramatch.db import close_connection
        >>> close_connection()
    """
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.debug("Database connection closed")


def init_db() -> None:
    """
    Initialize database by creating all tables and indexes.

    Notes:
        - Safe to call multiple times
        - Uses CREATE TABLE/INDEX IF NOT EXISTS

    Example:
        >>> from supramatch.db import init_db
        >>> init_db()
        >>> print("Database initialized")
    """
    conn = get_connection()
    try:
        logger.info(f"Initializing database: {DATABASE_PATH}")
        for statement in ALL_TABLES:
            conn.execute(statement)
        for statement in CREATE_INDEXES:
            conn.execute(statement)
        conn.commit()
        logger.info(f"Database initialized: {DATABASE_PATH}")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def drop_all_tables() -> None:
    """
    Drop all tables from database.

    WARNING: This is destructive and unrecoverable!

    Example:
        >>> from supramatch.db import drop_all_tables
        >>> drop_all_tables()
    """
    conn = get_connection()
    logger.warning("Dropping all tables from database")
    # Drop child tables before parents to respect foreign keys
    conn.execute("DROP TABLE IF EXISTS matches")
    conn.execute("DROP TABLE IF EXISTS prices")
    conn.execute("DROP TABLE IF EXISTS guests")
    conn.execute("DROP TABLE IF EXISTS cages")
    conn.commit()
    logger.warning("All tables dropped from database")


def reset_db() -> None:
    """
    Reset database by dropping and recreating all tables.

    WARNING: This is destructive!

    Example:
        >>> from supramatch.db import reset_db
        >>> reset_db()
        >>> print("Database reset")
    """
    logger.warning("Resetting database...")
    drop_all_tables()
    init_db()
    logger.info("Database reset complete")


def vacuum_db() -> None:
    """
    Reclaim space and rebuild indexes.

    Notes:
        - Reclaims space from deleted rows
        - Can take time for large databases

    Example:
        >>> from supramatch.db import vacuum_db
        >>> vacuum_db()
    """
    try:
        conn = get_connection()
        conn.execute("VACUUM")
        logger.info("Database vacuumed")

    except Exception as e:
        logger.error(f"Vacuum failed: {e}")
        raise
