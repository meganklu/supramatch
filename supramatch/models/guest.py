"""Guest dataclass."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from supramatch.utils.helpers import format_volume, format_price

@dataclass
class Guest:
    """
    Guest molecule with properties and pricing.
    
    Attributes:
        name: Molecule name
        smiles: SMILES string
        molar_mass: Molecular weight in g/mol
        molecular_volume: Molecular volume in Å³
        cas_number: CAS registry number (optional)
        price_per_gram: Price in USD per gram ($/g)
        supplier: Supplier name
        physical_state: solid/liquid/gas
        url: Supplier product link
        id: Primary key (set by database)
        created_at: Creation timestamp
    """
    name: str
    smiles: str
    molar_mass: float
    molecular_volume: float
    cas_number: Optional[str] = None
    price_per_gram: Optional[float] = None
    supplier: Optional[str] = None
    physical_state: Optional[str] = None
    url: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def __repr__(self) -> str:
        price_str = f"${self.price_per_gram:.2f}/g" if self.price_per_gram else "N/A"
        return f"<Guest(name='{self.name}', {price_str})>"
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def price_per_mole(self) -> Optional[float]:
        """Calculate cost per mole in $/mol."""
        if self.price_per_gram and self.molar_mass:
            return self.price_per_gram * self.molar_mass
        return None
    
    @property
    def is_available(self) -> bool:
        """Check if guest has valid price information."""
        return self.price_per_gram is not None and self.price_per_gram > 0
    
    def calculate_cost_for_mass(self, mass_grams: float) -> Optional[float]:
        """Calculate total cost for a given mass in grams."""
        if self.price_per_gram is None:
            return None
        return self.price_per_gram * mass_grams