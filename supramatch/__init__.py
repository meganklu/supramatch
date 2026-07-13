"""
Supramatch: Match metal-organic cages to guest molecules.

A Python program for matching host metal–organic cages to guest molecules
based on packing coefficient and guest molecule price.

Units:
    - Volumes: Cubic angstroms (Å³)
    - Molecular weight: g/mol
    - Price: USD per gram ($/g)
    - Packing coefficient: Dimensionless (0-1)
"""

import logging
from importlib.metadata import PackageNotFoundError, version

from supramatch import logging_config  # noqa: F401

try:
    __version__ = version("Supramatch")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"

__author__ = "Megan K. Lu"
__email__ = "megan.k.lu.28@dartmouth.edu"

logger = logging.getLogger(__name__)

from supramatch.db.database import init_db, get_connection, close_connection
from supramatch.models import Cage, Guest, Match, Price
from supramatch.modules.cage_calc import CageCalculator
from supramatch.modules.guest_calc import GuestCalculator
from supramatch.modules.matcher import MatchingEngine
from supramatch.discovery import pubchem_client
from supramatch.discovery.price_lookup import PriceLookup
from supramatch.pipeline import run_pipeline
from supramatch.utils.helpers import format_volume, format_price, format_packing_coefficient

__all__ = [
    "__version__",
    "__author__",
    "init_db",
    "get_connection",
    "close_connection",
    "Cage",
    "Guest",
    "Match",
    "Price",
    "CageCalculator",
    "GuestCalculator",
    "MatchingEngine",
    "pubchem_client",
    "PriceLookup",
    "run_pipeline",
    "format_volume",
    "format_price",
    "format_packing_coefficient",
]

logger.debug(f"Supramatch {__version__} initialized")
