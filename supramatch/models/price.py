"""Price dataclass."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Price:
    """
    A vendor price quote for a guest molecule, collected via ChemPrice (Mcule, Molport, Chemspace).

    Mirrors what the vendor reported as-is; usd_per_gram/usd_per_mol/usd_per_liter
    are ChemPrice's own standardized ratios (at most one is populated per row,
    depending on what unit the vendor quoted in).

    Attributes:
        guest_id: Foreign key to Guest
        source: Vendor integrator, e.g. 'Molport', 'MCule', or 'Chemspace'
        supplier_name: The vendor's own supplier/catalog name
        purity: Purity as reported by the vendor (e.g. "95%")
        amount: Pack size
        measure: Unit for amount (e.g. 'g', 'mg', 'mmol')
        price_usd: Raw quoted price in USD
        usd_per_gram: Standardized price per gram, if measure was mass-based
        usd_per_mol: Standardized price per mole, if measure was molar
        usd_per_liter: Standardized price per liter, if measure was volume-based
        id: Primary key (set by database)
        created_at: When this quote was collected
        guest_name: Denormalized guest name (populated by queries that join guests)
    """
    guest_id: int
    source: str
    supplier_name: Optional[str] = None
    purity: Optional[str] = None
    amount: Optional[float] = None
    measure: Optional[str] = None
    price_usd: Optional[float] = None
    usd_per_gram: Optional[float] = None
    usd_per_mol: Optional[float] = None
    usd_per_liter: Optional[float] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    guest_name: Optional[str] = None

    def __repr__(self) -> str:
        # ChemPrice only ever populates the ratio matching the vendor's
        # reported unit (mass/molar/volume), so pick whichever is present
        # rather than assuming usd_per_gram exists.
        if self.usd_per_gram is not None:
            rate_str = f"${self.usd_per_gram:.2f}/g"
        elif self.usd_per_mol is not None:
            rate_str = f"${self.usd_per_mol:.2f}/mol"
        elif self.usd_per_liter is not None:
            rate_str = f"${self.usd_per_liter:.2f}/L"
        elif self.price_usd is not None:
            rate_str = f"${self.price_usd:.2f} ({self.amount}{self.measure})"
        else:
            rate_str = "N/A"
        return f"<Price(guest='{self.guest_name}', source='{self.source}', {rate_str})>"
