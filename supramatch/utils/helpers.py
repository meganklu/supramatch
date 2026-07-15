"""Helper utility functions.

Simple formatting and classification helpers used throughout the project.
"""

import re
from typing import Optional

from supramatch.config import VOLUME_DECIMALS, PRICE_DECIMALS, PC_DECIMALS

# CAS registry numbers are 2-7 digits, then exactly 2 digits, then 1 check
# digit. This shape is what distinguishes them from other identifiers (e.g.
# EC/EINECS numbers, which are always NNN-NNN-N) -- see pubchem_client's
# module docstring for why this matters for CAS number provenance.
_CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")


def is_cas_shaped(identifier: str) -> bool:
    """Whether `identifier` has the shape of a CAS registry number."""
    return bool(_CAS_PATTERN.match(identifier.strip()))

def format_volume(volume: Optional[float]) -> str:
    """
    Format volume value with unit.
    
    Uses VOLUME_DECIMALS from config for consistent display.
    
    Args:
        volume: Volume in cubic angstroms (Å³)
    
    Returns:
        str: Formatted volume with unit, or 'N/A' if None
    
    Example:
        >>> format_volume(234.567)
        '234.57 Å³'
        >>> format_volume(None)
        'N/A'
    """
    if volume is None:
        return "N/A"
    return f"{volume:.{VOLUME_DECIMALS}f} Å³"


def format_price(price: Optional[float]) -> str:
    """
    Format price value with unit.
    
    Uses PRICE_DECIMALS from config for consistent display.
    
    Args:
        price: Price in USD
    
    Returns:
        str: Formatted price with unit, or 'N/A' if None
    
    Example:
        >>> format_price(0.5925)
        '$0.59'
        >>> format_price(None)
        'N/A'
    """
    if price is None:
        return "N/A"
    return f"${price:.{PRICE_DECIMALS}f}"


def truncate(text: str, width: int) -> str:
    """
    Truncate text to fit within width, marking cut-off text with '...'.

    Args:
        text: Text to truncate
        width: Maximum length of the returned string

    Returns:
        str: Text unchanged if it already fits, otherwise cut short with a
            trailing '...'

    Example:
        >>> truncate("benzene", 10)
        'benzene'
        >>> truncate("2,3,4,5-tetraphenylcyclopenta-2,4-dien-1-one", 10)
        '2,3,4,...'
    """
    if len(text) <= width:
        return text
    return text[:width - 3] + "..."


def format_packing_coefficient(pc: Optional[float]) -> str:
    """
    Format packing coefficient value.
    
    Uses PC_DECIMALS from config for consistent display.
    
    Args:
        pc: Packing coefficient (0-1)
    
    Returns:
        str: Formatted packing coefficient, or 'N/A' if None
    
    Example:
        >>> format_packing_coefficient(0.456)
        '0.456'
        >>> format_packing_coefficient(None)
        'N/A'
    """
    if pc is None:
        return "N/A"
    return f"{pc:.{PC_DECIMALS}f}"