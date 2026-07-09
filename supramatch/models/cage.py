"""Cage dataclass."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from supramatch.utils.helpers import format_volume

@dataclass
class Cage:
    """
    Metal-organic cage host structure.
    
    Attributes:
        name: Unique cage identifier
        cavity_volume: Calculated cavity volume in cubic angstroms (Å³)
        pdb_file: Path to PDB structure file
        cas_number: CAS registry number (optional)
        id: Primary key (set by database)
        created_at: Creation timestamp
    """
    name: str
    cavity_volume: float
    pdb_file: str
    cas_number: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def __repr__(self) -> str:
        return f"<Cage(name='{self.name}', volume={format_volume(self.cavity_volume)})>"
    
    def __str__(self) -> str:
        return self.name