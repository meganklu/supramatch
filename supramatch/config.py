"""
Configuration management for supramatch.

Configuration can be overridden with environment variables.
"""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{PROJECT_ROOT}/data/supramatch.db"
)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", f"{PROJECT_ROOT}/logs/supramatch.log")

# Create logs directory if it doesn't exist
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

# Create data directory if it doesn't exist
Path(f"{PROJECT_ROOT}/data").mkdir(parents=True, exist_ok=True)

# Calculation parameters
CAGE_CALC_CONFIG = {
    "grid_spacing": 0.5,
    "distance_threshold_multiplier": 2.0,
    "min_distance_threshold": 5.0,
}

GUEST_CALC_CONFIG = {
    "random_seed": 0xf00d,
    "optimize_geometry": True,
}

MATCHER_CONFIG = {
    "pc_min_default": 0.3,
    "pc_max_default": 0.7,
    "viable_threshold": True,
}

# Feature flags
ENABLE_SCRAPER = os.getenv("ENABLE_SCRAPER", "false").lower() == "true"
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"