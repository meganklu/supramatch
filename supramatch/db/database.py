"""
Database connection and session management.

Handles SQLite and PostgreSQL connections with proper session management.
"""

import sys
import os
import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.pool import StaticPool
from supramatch.config import DATABASE_URL
from supramatch.db.base import Base

logger = logging.getLogger(__name__)

# Create engine
def _create_engine() -> Engine:
    """
    Create database engine based on DATABASE_URL.
    
    Returns:
        Engine: SQLAlchemy engine instance.
    
    Notes:
        - SQLite uses StaticPool for better testing support
        - Foreign keys enforced for SQLite
    """
    # Check if using SQLite (in-memory or file)
    is_sqlite = "sqlite" in DATABASE_URL
    
    engine_kwargs = {}
    
    if is_sqlite:
        # Use StaticPool for SQLite (required for in-memory DB in tests)
        if "memory" in DATABASE_URL:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            engine_kwargs["poolclass"] = StaticPool
        
        # Enable foreign keys for SQLite
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    
    engine = create_engine(DATABASE_URL, **engine_kwargs)
    
    return engine


engine = _create_engine()

# Create session factory
SessionLocal = scoped_session(sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
))


def init_db() -> None:
    """
    Initialize database by creating all tables.
    
    Notes:
        - Safe to call multiple times
        - Creates tables if they don't exist
        - Respects existing tables
    
    Raises:
        Exception: If database creation fails
    
    Example:
        >>> from supramatch.db import init_db
        >>> init_db()
        >>> print("Database initialized")
    """
    try:
        logger.info(f"Initializing database: {DATABASE_URL}")
        Base.metadata.create_all(bind=engine)
        logger.info(f"Database initialized: {DATABASE_URL}")
    
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def get_session() -> Session:
    """
    Get a database session.
    
    Returns:
        Session: SQLAlchemy session instance.
    
    Notes:
        - Returns scoped session (thread-local)
        - Safe for multi-threaded applications
        - Must be closed with close_session() or session.close()
    
    Example:
        >>> from supramatch.db import get_session
        >>> session = get_session()
        >>> cage = session.query(Cage).first()
        >>> session.close()
    
    See Also:
        close_session(): Close database session
    """
    return SessionLocal()


def close_session() -> None:
    """
    Close the thread-local database session.
    
    Notes:
        - Removes session from registry
        - Safe to call even if no session is active
        - Recommended at end of application lifecycle
    
    Example:
        >>> from supramatch.db import close_session
        >>> close_session()
    """
    SessionLocal.remove()
    logger.debug("Database session closed")

def get_session_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Yields:
        Session: SQLAlchemy session instance.
    
    Notes:
        - Automatically handles session closing
        - Rolls back on exception
        - Recommended for use with 'with' statement
    
    Example:
        >>> from supramatch.db import get_session_context
        >>> with get_session_context() as session:
        ...     cage = session.query(Cage).first()
        ...     print(cage.name)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()

def drop_all_tables() -> None:
    """
    Drop all tables from database.
    
    WARNING: This is destructive and unrecoverable!
    
    Notes:
        - Only use for testing or development
        - Requires confirmation in production
    
    Example:
        >>> from supramatch.db import drop_all_tables
        >>> drop_all_tables()
    """
    confirm = input(
        "Are you sure you want to drop all tables? "
        "This is irreversible. Type 'yes' to confirm: "
    )
    
    if confirm.lower() == "yes":
        Base.metadata.drop_all(bind=engine)
        logger.warning("All tables dropped from database")
    else:
        logger.info("Drop operation cancelled")


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
    Optimize database (SQLite: VACUUM, PostgreSQL: VACUUM ANALYZE).
    
    Notes:
        - Reclaims space from deleted rows
        - Rebuilds indexes
        - Can take time for large databases
    
    Example:
        >>> from supramatch.db import vacuum_db
        >>> vacuum_db()
    """
    try:
        if "sqlite" in DATABASE_URL:
            engine.execute("VACUUM")
            logger.info("SQLite database vacuumed")
        elif "postgresql" in DATABASE_URL:
            # PostgreSQL: requires explicit transaction handling
            with engine.connect() as conn:
                conn.connection.set_isolation_level(0)
                conn.execute("VACUUM ANALYZE")
                logger.info("PostgreSQL database vacuumed")
    
    except Exception as e:
        logger.error(f"Vacuum failed: {e}")


def main(args):
    """
    CLI entry point for database initialization.
    
    Usage:
        python -m supramatch.db.database [command]
    
    Command Options:
        - init: Initialize database (create tables)
        - reset: Reset database (drop and recreate)
        - drop: Drop all tables
        - help: Show help message
    
    Example:
        python -m supramatch.db.database init
    """
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "init":
            init_db()
            print("✓ Database initialized successfully")
        elif command == "reset":
            reset_db()
            print("✓ Database reset successfully")
        elif command == "drop":
            drop_all_tables()
            print("✓ All tables dropped")
        elif command == "help":
            print("Usage: python -m supramatch.db.database [command]")
            print("\nCommands:")
            print("    - init: Initialize database (create tables)")
            print("    - reset: Reset database (drop and recreate)")
            print("    - drop: Drop all tables")
            print("    - help: Show this help message")
        else:
            print(f"Unknown command: {command}")
            print("Use 'help' for available commands")
            return 1
    else:
        # Default: initialize database
        init_db()
        print("✓ Database initialized successfully")
    return 0

# Cleanup on exit
import atexit
atexit.register(close_session)

if __name__ == "__main__":
    sys.exit(main(sys.argv))