"""
Logging configuration for supramatch.

Sets up logging with both file and console handlers.
"""

import logging
import logging.handlers
from pathlib import Path

from supramatch.config import LOG_LEVEL, LOG_FILE


def setup_logging():
    """
    Configure logging for the application.
    
    Creates:
    - Console handler: INFO and above
    - File handler: DEBUG and above
    - Rotating file handler: Max 10MB, keep 5 backups
    
    Example:
        >>> from supramatch.logging_config import setup_logging
        >>> setup_logging()
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Application started")
    """
    
    # Create logs directory if it doesn't exist
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # ==================== CONSOLE HANDLER ====================
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    console_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # ==================== FILE HANDLER ====================
    
    # Use rotating file handler (prevents huge log files)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,  # Keep 5 backups
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    file_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    # ==================== ADD HANDLERS ====================
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - Level: {LOG_LEVEL}, File: {LOG_FILE}")


# Initialize logging when module is imported
setup_logging()