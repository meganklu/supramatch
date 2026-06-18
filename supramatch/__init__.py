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

__version__ = "0.1.0"
__author__ = "Megan K. Lu"
__email__ = "megan.k.lu.28@dartmouth.edu"

from supramatch.db.database import init_db, get_session, close_session
from supramatch.db.models import Cage, Guest, HostGuestPairing
from supramatch.modules.cage_calc import CageCalculator
from supramatch.modules.guest_calc import GuestCalculator
from supramatch.modules.matcher import MatchingEngine

__all__ = [
    "__version__",
    "__author__",
    "init_db",
    "get_session",
    "close_session",
    "Cage",
    "Guest",
    "HostGuestPairing",
    "CageCalculator",
    "GuestCalculator",
    "MatchingEngine",
]