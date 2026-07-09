"""Match dataclass."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from supramatch.config import VOLUME_DECIMALS, PRICE_DECIMALS, PC_DECIMALS
from supramatch.utils.helpers import format_price, format_packing_coefficient

@dataclass
class Match:
    """
    Host-guest match with calculated metrics.

    Attributes:
        cage_id: Foreign key to Cage
        guest_id: Foreign key to Guest
        packing_coefficient: Calculated PC (dimensionless, 0-1)
        quality_score: Combined metric of price and packing coefficient (0-100)
        is_viable: Whether the match falls within the viable packing coefficient range
        notes: Optional user notes
        id: Primary key (set by database)
        created_at: Creation timestamp
        cage_name: Denormalized cage name (populated by queries that join cages)
        cage_cavity_volume: Denormalized cage cavity volume in Å³ (populated by queries that join cages)
        guest_name: Denormalized guest name (populated by queries that join guests)
        guest_price_per_gram: Denormalized guest price in $/g (populated by queries that join guests)
    """
    cage_id: int
    guest_id: int
    packing_coefficient: float
    quality_score: float
    is_viable: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    cage_name: Optional[str] = None
    cage_cavity_volume: Optional[float] = None
    guest_name: Optional[str] = None
    guest_price_per_gram: Optional[float] = None

    def __repr__(self) -> str:
        price_str = format_price(self.guest_price_per_gram)
        return (
            f"<Match(cage='{self.cage_name}', guest='{self.guest_name}', "
            f"PC={format_packing_coefficient(self.packing_coefficient)}, {price_str}, quality={self.quality_score})>"
        )

    def to_dict(self) -> dict:
        """Convert match to dictionary."""
        return {
            "id": self.id,
            "cage_id": self.cage_id,
            "cage_name": self.cage_name,
            "cage_volume": round(self.cage_cavity_volume, VOLUME_DECIMALS) if self.cage_cavity_volume is not None else None,
            "guest_id": self.guest_id,
            "guest_name": self.guest_name,
            "packing_coefficient": round(self.packing_coefficient, PC_DECIMALS),
            "guest_price_per_gram": round(self.guest_price_per_gram, PRICE_DECIMALS) if self.guest_price_per_gram is not None else None,
            "is_viable": self.is_viable,
            "quality_score": round(self.quality_score, 2),
            "notes": self.notes,
        }
