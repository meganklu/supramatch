"""Guest dataclass."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from supramatch.utils.helpers import format_volume

@dataclass
class Guest:
    """
    Guest molecule with structural properties.

    Pricing lives in the separate `prices` table (a guest can have quotes
    from multiple vendors) -- see supramatch.models.price.Price and
    supramatch.db.queries for price lookups.

    Attributes:
        name: Friendly/common name (PubChem's "Title" when fetched via
            PubChem, or user-supplied otherwise)
        smiles: SMILES string
        molecular_weight: Molecular weight in g/mol
        molecular_volume: Molecular volume in Å³
        iupac_name: Formal IUPAC name (optional; populated when available,
            e.g. from PubChem)
        molecular_formula: Molecular formula, e.g. "C9H8O4" (optional)
        pubchem_cid: PubChem CID this guest was fetched from, for provenance
            (optional; only set when created via `guest fetch`/`create_guest_from_pubchem`)
        cas_number: CAS registry number (optional)
        physical_state: solid/liquid/gas
        id: Primary key (set by database)
        created_at: Creation timestamp
    """
    name: str
    smiles: str
    molecular_weight: float
    molecular_volume: float
    iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    pubchem_cid: Optional[int] = None
    cas_number: Optional[str] = None
    physical_state: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"<Guest(name='{self.name}', volume={format_volume(self.molecular_volume)})>"

    def __str__(self) -> str:
        return self.name
