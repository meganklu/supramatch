"""SQLAlchemy ORM models for supramatch."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

from supramatch.db.base import Base, TimestampMixin


class Cage(Base, TimestampMixin):
    """
    Metal-organic cage host structure.
    
    Attributes:
        id: Primary key
        name: Unique cage identifier
        cas_number: CAS registry number (optional)
        pdb_file: Path to PDB structure file
        cavity_volume: Calculated cavity volume in cubic angstroms (Å³)
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        pairings: Relationship to HostGuestPairing
    
    Volume Units:
        All volumes are in cubic angstroms (Ų or Å³)
        1 Å³ = 10⁻²⁴ cm³
    
    Example:
        >>> from supramatch.db import Cage
        >>> cage = Cage(name="MyCage", cavity_volume=234.5)  # 234.5 Å³
    """
    
    __tablename__ = "cages"
    
    # Columns
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    cas_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True, index=True)
    pdb_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cavity_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True, doc="Cavity volume in Å³")
    
    # Relationships
    pairings: Mapped[List["HostGuestPairing"]] = relationship(
        "HostGuestPairing",
        back_populates="cage",
        cascade="all, delete-orphan",
        foreign_keys="HostGuestPairing.cage_id"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_cage_name", "name"),
        Index("idx_cage_cas", "cas_number"),
    )
    
    def __repr__(self) -> str:
        return f"<Cage(id={self.id}, name='{self.name}', volume={self.cavity_volume:.2f}Å³)>"
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def pairing_count(self) -> int:
        """Get number of pairings for this cage."""
        return len(self.pairings)
    
    @property
    def best_matching_guest(self) -> Optional["HostGuestPairing"]:
        """Get pairing with packing coefficient closest to 0.55."""
        if not self.pairings:
            return None
        # Find pairing closest to ideal PC of 0.55
        return min(self.pairings, key=lambda p: abs(p.packing_coefficient - 0.55))
    
    @property
    def cheapest_guest(self) -> Optional["HostGuestPairing"]:
        """Get pairing with lowest guest price per gram."""
        if not self.pairings:
            return None
        viable_pairings = [p for p in self.pairings if p.price_per_gram is not None]
        if not viable_pairings:
            return None
        return min(viable_pairings, key=lambda p: p.price_per_gram)


class Guest(Base, TimestampMixin):
    """
    Guest molecule with pricing in $/gram.
    
    Attributes:
        id: Primary key
        name: Molecule name
        cas_number: CAS registry number
        smiles: SMILES string for molecule structure
        molar_mass: Molar mass in g/mol
        molecular_volume: Molecular volume in Å³
        price_per_gram: Cost in USD per gram ($/g)
        supplier: Supplier name (e.g., Sigma-Aldrich)
        physical_state: Physical state (solid/liquid/gas)
        url: Supplier product link
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        pairings: Relationship to HostGuestPairing
    
    Volume Units:
        molecular_volume: Å³
        Calculated from SMILES using RDKit's ComputeMolVolume()
        Represents volume of a particular conformer of a molecule
    
    Pricing:
        price_per_gram: USD per gram ($/g)
        Standardized across suppliers for fair comparison
    
    Example:
        >>> from supramatch.db import Guest
        >>> guest = Guest(
        ...     name="Benzene",
        ...     smiles="c1ccccc1",
        ...     molar_mass=78.11,            # g/mol
        ...     molecular_volume=89.2,       # Å³
        ...     price_per_gram=0.59          # $/g
        ... )
    """
    
    __tablename__ = "guests"
    
    # Columns
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cas_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True, index=True)
    smiles: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    molar_mass: Mapped[Optional[float]] = mapped_column(Float, nullable=True, doc="Molar mass in g/mol")
    molecular_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True, doc="Molecular volume in Å³")
    price_per_gram: Mapped[Optional[float]] = mapped_column(Float, nullable=True, doc="Price in USD per gram ($/g)")
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    physical_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relationships
    pairings: Mapped[List["HostGuestPairing"]] = relationship(
        "HostGuestPairing",
        back_populates="guest",
        cascade="all, delete-orphan",
        foreign_keys="HostGuestPairing.guest_id"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_guest_name", "name"),
        Index("idx_guest_cas", "cas_number"),
        Index("idx_guest_supplier", "supplier"),
        Index("idx_guest_price_per_gram", "price_per_gram"),
    )
    
    def __repr__(self) -> str:
        price_str = f"${self.price_per_gram:.2f}/g" if self.price_per_gram else "N/A"
        return f"<Guest(id={self.id}, name='{self.name}', {price_str})>"
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def is_available(self) -> bool:
        """Check if guest has price information."""
        return self.price_per_gram is not None and self.price_per_gram > 0
    

class HostGuestPairing(Base, TimestampMixin):
    """
    Host-guest pairing with calculated metrics.
    
    Attributes:
        id: Primary key
        cage_id: Foreign key to Cage
        guest_id: Foreign key to Guest
        packing_coefficient: Calculated PC (dimensionless, 0-1)
        is_viable: User-defined viability flag
        notes: Optional user notes
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        cage: Relationship to Cage
        guest: Relationship to Guest
    
    Units:
        packing_coefficient: Dimensionless (0-1)
            PC = V_guest / V_cage
    
    Evaluation Metrics:
        - Packing Coefficient: Geometric fit (0-1)
        - Guest Price: Cost per gram ($/g)
        - Quality Score: Combined metric (0-100)

    Typical PC Ranges:
        - 0.1-0.3: Loose fit (small guest, large cage)
        - 0.3-0.7: Optimal fit (good for most applications)
        - 0.7-0.9: Snug fit (tight encapsulation)
        - 0.9-1.0: Very tight (potential steric issues)
    
    Example:
        >>> from supramatch.db import HostGuestPairing
        >>> pairing = HostGuestPairing(
        ...     cage_id=1,
        ...     guest_id=1,
        ...     packing_coefficient=0.45,
        ...     is_viable=True
        ... )
    """
    
    __tablename__ = "pairings"
    
    # Columns
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cage_id: Mapped[int] = mapped_column(ForeignKey("cages.id", ondelete="CASCADE"), nullable=False, index=True)
    guest_id: Mapped[int] = mapped_column(ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True)
    packing_coefficient: Mapped[float] = mapped_column(Float, nullable=False, index=True, doc="Packing coefficient (dimensionless, 0-1)")
    is_viable: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Relationships
    cage: Mapped[Cage] = relationship(
        "Cage",
        back_populates="pairings",
        foreign_keys=[cage_id]
    )
    guest: Mapped[Guest] = relationship(
        "Guest",
        back_populates="pairings",
        foreign_keys=[guest_id]
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_pairing_cage", "cage_id"),
        Index("idx_pairing_guest", "guest_id"),
        Index("idx_pairing_pc", "packing_coefficient"),
        Index("idx_pairing_viable", "is_viable"),
        Index("idx_pairing_unique", "cage_id", "guest_id", unique=True),
    )
    
    def __repr__(self) -> str:
        price_str = f"${self.guest.price_per_gram:.2f}/g" if self.guest.price_per_gram else "N/A"
        return (
            f"<Pairing(cage={self.cage.name}, guest={self.guest.name}, "
            f"PC={self.packing_coefficient:.3f}, {price_str})>"
        )
    
    @property
    def quality_score(self) -> float:
        """
        Calculate a quality score for the pairing (0-100).
        
        Balances two factors:
        1. Geometric fit (packing coefficient): 0-50 points
           - Optimal range 0.3-0.7 gets full points
           - Outside this range score decreases
        
        2. Cost efficiency (price per gram): 0-50 points
           - Lower price = higher score
           - Assumes typical range $0.10-$100.00/g
        
        Returns:
            float: Quality score (0-100), higher is better
        
        Example:
            >>> pairing = HostGuestPairing(
            ...     packing_coefficient=0.45,
            ...     guest=Guest(price_per_gram=0.59)
            ... )
            >>> score = pairing.quality_score
            >>> print(f"Score: {score:.1f}/100")
            Score: 95.3/100
        """
        # PC score: optimal at 0.3-0.7
        if self.packing_coefficient < 0.3:
            # Scale up from 0 to full points over 0-0.3 range
            pc_score = (self.packing_coefficient / 0.3) * 50
        elif self.packing_coefficient <= 0.7:
            # Full points in optimal range
            pc_score = 50
        else:
            # Scale down from full points over 0.7-1.0 range
            excess_pc = self.packing_coefficient - 0.7
            pc_score = max(0, 50 - (excess_pc / 0.3) * 50)
        
        # Price score: lower price = higher score
        if self.guest.price_per_gram:
            # Normalize on typical range $0.10-$100.00/g
            # At $0.10/g = 50 points
            # At $10.00/g = 45 points
            # At $100.00/g = 0 points
            # Formula: 50 - (price * 0.5)
            price_score = max(0, 50 - (self.guest.price_per_gram * 0.5))
        else:
            price_score = 25  # Neutral if no price
        
        return pc_score + price_score
    
    def to_dict(self) -> dict:
        """Convert pairing to dictionary."""
        return {
            "id": self.id,
            "cage_id": self.cage_id,
            "cage_name": self.cage.name,
            "cage_volume": round(self.cage.cavity_volume, 2),
            "guest_id": self.guest_id,
            "guest_name": self.guest.name,
            "packing_coefficient": round(self.packing_coefficient, 4),
            "guest_price_per_gram": round(self.guest.price_per_gram, 4) if self.guest.price_per_gram else None,
            "is_viable": self.is_viable,
            "quality_score": round(self.quality_score, 2),
            "notes": self.notes,
        }