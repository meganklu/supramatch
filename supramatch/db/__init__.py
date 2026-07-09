"""
Database module for supramatch.

Handles SQLite connection management and schema initialization.
Raw SQL query functions live in supramatch.db.queries.
"""

from supramatch.db.database import (
    init_db,
    get_connection,
    close_connection,
    reset_db,
    drop_all_tables,
    vacuum_db,
)

__all__ = [
    "init_db",
    "get_connection",
    "close_connection",
    "reset_db",
    "drop_all_tables",
    "vacuum_db",
]
