"""Helper utility functions.

Simple formatting and classification helpers used throughout the project.
"""

from typing import Optional

from supramatch.config import VOLUME_DECIMALS, PRICE_DECIMALS, PC_DECIMALS

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