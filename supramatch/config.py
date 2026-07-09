"""
Configuration management for supramatch.

Configuration can be overridden with environment variables.

Example environment variables:
    export DATABASE_PATH="/path/to/supramatch.db"
    export LOG_LEVEL="DEBUG"
    export CAGE_GRID_SPACING="0.3"
    export GUEST_RANDOM_SEED="12345"
    export PC_IDEAL_DEFAULT="0.45"
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Find and load the .env file
load_dotenv()

# ==================== DATABASE ====================

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    str(PROJECT_ROOT / "data" / "supramatch.db")
)

# ==================== LOGGING ====================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", f"{PROJECT_ROOT}/logs/supramatch.log")

# Create logs directory if it doesn't exist
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

# Create data directory if it doesn't exist
Path(f"{PROJECT_ROOT}/data").mkdir(parents=True, exist_ok=True)

# ==================== CAGE CALCULATIONS ====================

CAGE_CALC_CONFIG = {
    # Grid spacing in angstroms for cavity volume calculation
    "grid_spacing": float(os.getenv("CAGE_GRID_SPACING", "0.5")),
    
    # Multiplier for distance threshold (relative to window radius)
    "distance_threshold_multiplier": float(os.getenv("CAGE_DISTANCE_THRESHOLD_MULT", "2.0")),
    
    # Minimum distance threshold in angstroms
    "min_distance_threshold": float(os.getenv("CAGE_MIN_DISTANCE_THRESHOLD", "5.0")),
}

# ==================== GUEST CALCULATIONS ====================

GUEST_CALC_CONFIG = {
    # Random seed for RDKit 3D embedding (reproducibility)
    # Set to specific value for reproducible results, or None for random
    "random_seed": int(os.getenv("GUEST_RANDOM_SEED", "0xf00d"), 0),
    
    # Whether to optimize molecular geometry after 3D embedding
    "optimize_geometry": os.getenv("GUEST_OPTIMIZE_GEOMETRY", "true").lower() == "true",
}

# ==================== HOST-GUEST MATCHING ====================

HG_MATCH_CONFIG = {
    # Default ideal packing coefficient for viable matches
    "pc_ideal_default": float(os.getenv("PC_IDEAL_DEFAULT", "0.55")),
    
    # Default packing coefficient tolerance for viable matches
    "pc_tolerance_default": float(os.getenv("PC_TOLERANCE_DEFAULT", "0.09")),
    
    # Whether to apply viability threshold when creating pairings
    "viable_threshold": os.getenv("VIABLE_THRESHOLD", "true").lower() == "true",
}

# ==================== FEATURE FLAGS ====================

# Enable web scraping functionality
ENABLE_SCRAPER = os.getenv("ENABLE_SCRAPER", "false").lower() == "true"

# Enable result caching
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"

# ==================== DISPLAY ====================

# Number of decimal places for volume display
VOLUME_DECIMALS = int(os.getenv("VOLUME_DECIMALS", "2"))

# Number of decimal places for price display
PRICE_DECIMALS = int(os.getenv("PRICE_DECIMALS", "2"))

# Number of decimal places for packing coefficient display
PC_DECIMALS = int(os.getenv("PC_DECIMALS", "3"))