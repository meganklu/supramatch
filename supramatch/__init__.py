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

from supramatch import logging_config  # noqa: F401

__version__ = "0.1.0"
__author__ = "Megan K. Lu"
__email__ = "megan.k.lu.28@dartmouth.edu"

logger = logging.getLogger(__name__)

from supramatch.db.database import init_db, get_connection, close_connection
from supramatch.models import Cage, Guest, Match
from supramatch.modules.cage_calc import CageCalculator
from supramatch.modules.guest_calc import GuestCalculator
from supramatch.modules.matcher import MatchingEngine
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
    "CageCalculator",
    "GuestCalculator",
    "MatchingEngine",
    "format_volume",
    "format_price",
    "format_packing_coefficient",
]

logger.debug(f"Supramatch {__version__} initialized")