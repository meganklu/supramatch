"""
Configuration management for supramatch.

Configuration can be overridden with environment variables.

Example environment variables:
    export DATABASE_PATH="/path/to/supramatch.db"
    export LOG_LEVEL="DEBUG"
    export CAGE_GRID_SPACING="0.3"
    export GUEST_RANDOM_SEED="12345"
    export PC_IDEAL_DEFAULT="0.45"
    export MCULE_API_KEY="..."
    export MOLPORT_API_KEY="..."
    export CHEMSPACE_API_KEY="..."
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

    # How many multiples of pc_tolerance_default away from pc_ideal_default
    # the geometric-fit component of quality_score bottoms out at 0. Scored
    # on a smooth quadratic curve inside that window (instead of a flat
    # plateau within tolerance followed by a linear falloff), so there's no
    # scoring cliff right at the tolerance boundary.
    "quality_pc_window_multiplier": float(os.getenv("QUALITY_PC_WINDOW_MULTIPLIER", "3")),

    # Guest price per gram ($/g) at which the price component of
    # quality_score bottoms out at 0. Scored on a log scale between $0 and
    # this ceiling, so a price change matters more near the low end (e.g.
    # $1 -> $2) than the same dollar change near the high end (e.g. $90 -> $100).
    "quality_price_ceiling": float(os.getenv("QUALITY_PRICE_CEILING", "100")),

    # Minimum vendor-reported purity (%) a price quote must meet to be
    # considered a guest's "best price" -- a cheaper quote below this bar is
    # excluded rather than allowed to win on price alone. Quotes with no
    # purity reported at all are excluded too, since there's nothing to
    # confirm they clear the bar.
    "min_purity_pct": float(os.getenv("MIN_PURITY_PCT", "95")),

    # Point budgets for quality_score's three components (should sum to 100,
    # though nothing enforces that if you retune them).
    "quality_pc_weight": float(os.getenv("QUALITY_PC_WEIGHT", "40")),
    "quality_price_weight": float(os.getenv("QUALITY_PRICE_WEIGHT", "40")),
    "quality_flexibility_weight": float(os.getenv("QUALITY_FLEXIBILITY_WEIGHT", "20")),

    # Rotatable bond count at which the flexibility component of
    # quality_score has decayed to half its max. Full marks at 0 rotatable
    # bonds (a rigid guest), decaying on a saturating curve --
    # half_saturation / (rotatable_bonds + half_saturation) -- rather than
    # linearly per bond, since each additional rotor beyond the first few
    # contributes less independent conformational freedom (correlated/
    # constrained motions), matching the diminishing entropic cost per bond.
    "quality_flexibility_half_saturation": float(os.getenv("QUALITY_FLEXIBILITY_HALF_SATURATION", "4")),
}

# ==================== PUBCHEM ====================

PUBCHEM_CONFIG = {
    # Delay between individual name/CAS -> CID resolution requests (PubChem
    # allows ~5 req/s; name-based lookups can't be batched, so this paces them)
    "request_delay_seconds": float(os.getenv("PUBCHEM_REQUEST_DELAY", "0.2")),

    # Number of CIDs to request properties for in a single batched call
    "cid_batch_size": int(os.getenv("PUBCHEM_CID_BATCH_SIZE", "100")),
}

# ==================== PRICING (ChemPrice) ====================

PRICE_CONFIG = {
    "mcule_api_key": os.getenv("MCULE_API_KEY"),
    "molport_api_key": os.getenv("MOLPORT_API_KEY"),
    "chemspace_api_key": os.getenv("CHEMSPACE_API_KEY"),

    # Skip re-querying a guest if it already has a price quote newer than this
    "ttl_days": int(os.getenv("PRICE_TTL_DAYS", "30")),
}

# ==================== FEATURE FLAGS ====================

# Enable result caching
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"

# ==================== DISPLAY ====================

# Number of decimal places for volume display
VOLUME_DECIMALS = int(os.getenv("VOLUME_DECIMALS", "2"))

# Number of decimal places for price display
PRICE_DECIMALS = int(os.getenv("PRICE_DECIMALS", "2"))

# Number of decimal places for packing coefficient display
PC_DECIMALS = int(os.getenv("PC_DECIMALS", "3"))