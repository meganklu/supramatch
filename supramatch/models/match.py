"""Match dataclass."""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from supramatch.config import HG_MATCH_CONFIG, VOLUME_DECIMALS, PRICE_DECIMALS, PC_DECIMALS
from supramatch.utils.helpers import format_price, format_packing_coefficient

@dataclass
class Match:
    """
    Host-guest match with calculated metrics.

    quality_score and is_viable are computed properties rather than stored
    columns: quality_score depends on price data in the `prices` table that
    can change independently after a match is created, and is_viable is a
    pure function of packing_coefficient plus the app's current default PC
    target -- persisting either would just let them drift stale.

    Attributes:
        cage_id: Foreign key to Cage
        guest_id: Foreign key to Guest
        packing_coefficient: Calculated PC (dimensionless, 0-1)
        notes: Optional user notes
        id: Primary key (set by database)
        created_at: Creation timestamp
        cage_name: Denormalized cage name (populated by queries that join cages)
        cage_cavity_volume: Denormalized cage cavity volume in Å³ (populated by queries that join cages)
        guest_name: Denormalized guest name (populated by queries that join guests)
        guest_rotatable_bonds: Denormalized guest rotatable bond count (populated by queries
            that join guests). None if the guest's rotatable_bonds hasn't been computed/
            backfilled yet, in which case quality_score treats it neutrally (see quality_score).
        guest_price_per_gram: Denormalized best known guest price in $/g (populated by queries
            that join prices, falling back to a usd_per_mol/molecular_weight conversion when no
            gram-based quote exists. Known limitation: volume-based quotes (usd_per_liter),
            e.g. for liquids priced by the mL, can't be converted to $/g without density data,
            so a guest priced only in those terms is treated as having no known price.)
    """
    cage_id: int
    guest_id: int
    packing_coefficient: float
    notes: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    cage_name: Optional[str] = None
    cage_cavity_volume: Optional[float] = None
    guest_name: Optional[str] = None
    guest_rotatable_bonds: Optional[int] = None
    guest_price_per_gram: Optional[float] = None

    @property
    def is_viable(self) -> bool:
        """Whether packing_coefficient falls within the app's default ideal range."""
        pc_ideal = HG_MATCH_CONFIG["pc_ideal_default"]
        pc_tolerance = HG_MATCH_CONFIG["pc_tolerance_default"]
        return abs(self.packing_coefficient - pc_ideal) <= pc_tolerance

    @property
    def quality_score(self) -> float:
        """
        Combined quality metric (0-100) from packing coefficient, price, and
        guest flexibility.

        - Geometric fit: 0-quality_pc_weight points (default 40), on a
          quadratic curve centered on the ideal PC so nearby deviations cost
          little and the penalty accelerates further out, bottoming out at 0
          at quality_pc_window_multiplier * pc_tolerance_default away from
          ideal (no cliff at the pc_tolerance_default boundary itself,
          which is_viable still uses as its pass/fail cutoff)
        - Cost efficiency: 0-quality_price_weight points (default 40), lower
          price per gram scores higher, on a log scale so a given price
          change matters more near the low end (e.g. $1 -> $2) than the same
          change near the high end (e.g. $90 -> $100) (neutral half credit
          if no price data has been looked up yet)
        - Flexibility: 0-quality_flexibility_weight points (default 20),
          full marks for a fully rigid guest (0 rotatable bonds), decaying
          on a saturating curve -- half_saturation / (rotatable_bonds +
          half_saturation) -- so each additional rotatable bond costs less
          than the last, matching the diminishing entropic penalty of an
          already-flexible guest picking up one more degree of freedom
          (neutral half credit if rotatable_bonds hasn't been computed for
          this guest yet, mirroring the price handling above)
        """
        pc_ideal = HG_MATCH_CONFIG["pc_ideal_default"]
        pc_tolerance = HG_MATCH_CONFIG["pc_tolerance_default"]
        pc_window = pc_tolerance * HG_MATCH_CONFIG["quality_pc_window_multiplier"]
        pc_weight = HG_MATCH_CONFIG["quality_pc_weight"]
        price_weight = HG_MATCH_CONFIG["quality_price_weight"]
        flexibility_weight = HG_MATCH_CONFIG["quality_flexibility_weight"]

        pc_score = max(0, pc_weight * (1 - ((self.packing_coefficient - pc_ideal) / pc_window) ** 2))

        if self.guest_price_per_gram:
            price_ceiling = HG_MATCH_CONFIG["quality_price_ceiling"]
            decay_rate = price_weight / math.log(1 + price_ceiling)
            price_score = max(0, price_weight - decay_rate * math.log(1 + self.guest_price_per_gram))
        else:
            price_score = price_weight / 2

        if self.guest_rotatable_bonds is not None:
            half_saturation = HG_MATCH_CONFIG["quality_flexibility_half_saturation"]
            flexibility_score = flexibility_weight * half_saturation / (self.guest_rotatable_bonds + half_saturation)
        else:
            flexibility_score = flexibility_weight / 2

        return pc_score + price_score + flexibility_score

    def __repr__(self) -> str:
        price_str = format_price(self.guest_price_per_gram)
        return (
            f"<Match(cage='{self.cage_name}', guest='{self.guest_name}', "
            f"PC={format_packing_coefficient(self.packing_coefficient)}, {price_str}, quality={self.quality_score:.1f})>"
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
            "guest_rotatable_bonds": self.guest_rotatable_bonds,
            "packing_coefficient": round(self.packing_coefficient, PC_DECIMALS),
            "guest_price_per_gram": round(self.guest_price_per_gram, PRICE_DECIMALS) if self.guest_price_per_gram is not None else None,
            "is_viable": self.is_viable,
            "quality_score": round(self.quality_score, 2),
            "notes": self.notes,
        }
