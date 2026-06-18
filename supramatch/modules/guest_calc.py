"""
Calculate guest properties, import from files, and manage database operations.
    
Volumes calculated from SMILES using RDKit's ComputeMolVolume()
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from sqlalchemy import select
from supramatch.db.base import Base, TimestampMixin 
from supramatch.db.models import Guest
from supramatch.db.database import get_session
from supramatch.config import GUEST_CALC_CONFIG
from supramatch.utils.helpers import format_volume, format_price

logger = logging.getLogger(__name__)

class GuestCalculator:
    """
    Handles guest molecule calculations and database operations.
    
    Volumes:
        All calculations are in Å³
        Volume calculated via RDKit using the rdkit.Chem.AllChem module
    """
    
    def __init__(self):
        self.session = get_session()

        # Load config parameters
        self.random_seed = GUEST_CALC_CONFIG["random_seed"]
        self.optimize_geometry = GUEST_CALC_CONFIG["optimize_geometry"]

        logger.debug(
            f"GuestCalculator initialized with config: "
            f"random_seed={self.random_seed}, "
            f"optimize_geometry={self.optimize_geometry}"
        )

    # ==================== CALCULATIONS ====================
    
    def calculate_volume(self, smiles: str) -> float:
        """
        Calculates the volume of a guest molecule from SMILES.

        Args:
            smiles: SMILES string for the guest molecule.

        Returns:
            float: The volume of the guest molecule in Å³.
        
        Raises:
            ValueError: If SMILES is invalid or calculation fails.
        
        Example:
            >>> calc = GuestCalculator()
            >>> volume = calc.calculate_volume('c1ccccc1')  # Benzene
            >>> print(f"Volume: {volume:.2f} Å³")
            Volume: 89.20 Å³
        """
        logger.debug(f"Calculating volume for SMILES: {smiles}")

        if not smiles or not isinstance(smiles, str):
            logger.error("Invalid SMILES: must be non-empty string")
            raise ValueError("SMILES must be a non-empty string")
        
        try:
            mol = Chem.MolFromSmiles(smiles)
            
            if mol is None:
                logger.error(f"Invalid SMILES string: {smiles}")
                raise ValueError(f"Invalid SMILES string: {smiles}")

            logger.debug(f"SMILES parsed successfully")
            
            # Add hydrogens
            mol = Chem.AddHs(mol)
            
            # Embed molecule with 3D coordinates
            conf_id = AllChem.EmbedMolecule(mol, randomSeed=self.random_seed)
            
            if conf_id == -1:
                # Fallback for difficult molecules
                logger.debug(f"Failed to embed with seed, using ETKDG")
                AllChem.EmbedMolecule(mol, AllChem.ETKDG())
            
            # Optimize geometry
            if self.optimize_geometry:
                logger.debug(f"Optimizing molecular geometry")
                AllChem.MMFFOptimizeMolecule(mol)
            
            # Calculate volume (in cubic angstroms)
            volume = AllChem.ComputeMolVolume(mol)
            volume_str = format_volume(volume)
            logger.debug(f"Volume calculated: {volume_str}")
            
            if volume is None or volume <= 0:
                logger.error(f"Invalid volume: {volume}")
                raise ValueError("Invalid volume calculation result")
            
            logger.info(f"Successfully calculated volume for SMILES: {volume_str}")
            return volume
        
        except Exception as e:
            logger.error(f"Failed to calculate volume: {e}", exc_info=True)
            raise ValueError(f"Failed to calculate volume for SMILES '{smiles}': {e}")
    
    # ==================== DATABASE OPERATIONS ====================

    def create_guest(
        self,
        name: str,
        smiles: str,
        molar_mass: float = None,
        cas_number: str = None,
        supplier: str = None,
        price_per_gram: float = None,
        physical_state: str = None,
        url: str = None
    ) -> Guest:
        """
        Create a new guest molecule in the database with calculated properties.
        
        Args:
            name: Common name of the molecule.
            smiles: SMILES string.
            molar_mass: Molar mass in g/mol.
            cas_number: CAS registry number.
            supplier: Supplier name (e.g., 'Sigma-Aldrich').
            price_per_gram: Price in USD per gram ($/g).
            physical_state: 'solid', 'liquid', or 'gas'.
            url: Product URL.
        
        Returns:
            Guest: The created guest object.
        
        Raises:
            ValueError: If guest already exists, SMILES invalid, or calculation fails.
        
        Example:
            >>> calc = GuestCalculator()
            >>> guest = calc.create_guest(
            ...     name='Benzene',
            ...     smiles='c1ccccc1',
            ...     price_per_gram=0.59,
            ...     supplier='Sigma-Aldrich'
            ... )
            >>> print(f"Created: {guest.name}")
            >>> print(f"Volume: {guest.molecular_volume:.2f} Å³")
            >>> print(f"Price: ${guest.price_per_gram:.2f}/g")
        """
        logger.info(f"Creating guest: {name}")
        logger.debug(f"SMILES: {smiles}, CAS: {cas_number}")
        
        if not name or not isinstance(name, str):
            logger.error("Name must be a non-empty string")
            raise ValueError("Name must be a non-empty string")
        
        if not smiles or not isinstance(smiles, str):
            logger.error("SMILES must be a non-empty string")
            raise ValueError("SMILES must be a non-empty string")
        
        # Check if guest already exists by CAS number or name
        if cas_number:
            stmt = select(Guest).filter_by(cas_number=cas_number)
            existing = self.session.scalars(stmt).first()
            if existing:
                logger.warning(f"Guest with CAS number '{cas_number}' already exists in database")
                raise ValueError(f"Guest with CAS number '{cas_number}' already exists in database")
        
        stmt = select(Guest).filter_by(name=name)
        existing = self.session.scalars(stmt).first()
        if existing:
            logger.warning(f"Guest with name '{name}' already exists in database")
            raise ValueError(f"Guest with name '{name}' already exists in database")
        
        # Validate molar mass
        if molar_mass is not None and molar_mass < 0:
            logger.error("Molar mass cannot be negative")
            raise ValueError("Molar mass cannot be negative")

        # Validate price
        if price_per_gram is not None and price_per_gram < 0:
            logger.error("Price cannot be negative")
            raise ValueError("Price cannot be negative")
        
        # Validate physical state
        valid_states = {'solid', 'liquid', 'gas'}
        if physical_state and physical_state.lower() not in valid_states:
            logger.error(f"Physical state must be one of {valid_states}")
            raise ValueError(f"Physical state must be one of {valid_states}")
        
        try: 
            # Calculate properties
            logger.debug(f"Calculating properties for {name}")
            molecular_volume = self.calculate_volume(smiles)
            volume_str = format_volume(molecular_volume)

            # Create guest object
            guest = Guest(
                name=name,
                smiles=smiles,
                molar_mass=molar_mass,
                cas_number=cas_number,
                molecular_volume=molecular_volume,
                price_per_gram=price_per_gram,
                supplier=supplier,
                physical_state=physical_state.lower() if physical_state else None,
                url=url
            )

            self.session.add(guest)
            self.session.commit()
            
            logger.info(f"Created guest '{name}': Volume={volume_str}")
            return guest

        except Exception as e:
            logger.error(f"Failed to create guest {name}: {e}", exc_info=True)
            raise
    
    def get_guest(self, guest_id: int = None, cas_number: str = None, name: str = None) -> Optional[Guest]:
        """Retrieve a guest from the database."""
        if guest_id:
            logger.debug(f"Retrieving guest with ID: {guest_id}")
            return self.session.get(Guest, guest_id)
        elif cas_number:
            logger.debug(f"Retrieving guest with CAS number: {cas_number}")
            stmt = select(Guest).filter_by(cas_number=cas_number)
            return self.session.scalars(stmt).first()
        elif name:
            logger.debug(f"Retrieving guest with name: {name}")
            stmt = select(Guest).filter_by(name=name)
            return self.session.scalars(stmt).first()
        return None
    
    def search_guests(self, name_pattern: str = None, supplier: str = None):
        """Search for guests with flexible criteria."""
        stmt = select(Guest)
        
        if name_pattern:
            logger.debug(f"Searching for guests with name pattern: {name_pattern}")
            stmt = stmt.where(Guest.name.ilike(f"%{name_pattern}%"))
        
        if supplier:
            logger.debug(f"Searching for guests with supplier: {supplier}")
            stmt = stmt.filter_by(supplier=supplier)
        
        return self.session.scalars(stmt).all()
    
    def list_guests(self, limit: int = None, offset: int = 0):
        """Get all guests from the database with optional pagination."""
        logger.debug("Retrieving all guests from database")
        stmt = select(Guest).offset(offset)
        
        if limit:
            logger.debug(f"Limiting guest retrieval to {limit}")
            stmt = stmt.limit(limit)
        
        guests = self.session.scalars(stmt).all()
        logger.info(f"Found {len(guests)} guests in database")
        return guests
    
    def update_guest_price(self, guest_id: int, new_price_per_gram: float) -> bool:
        """Update guest price without recalculating properties."""
        logger.debug(f"Updating price for guest ID: {guest_id}")

        if new_price_per_gram < 0:
            logger.error("Price cannot be negative")
            raise ValueError("Price cannot be negative")
        
        guest = self.session.get(Guest, guest_id)
        
        if guest:
            logger.info(f"Updating price for {guest.name}")
            old_price = guest.price_per_gram
            old_price_str = format_price(old_price)
            guest.price_per_gram = new_price_per_gram
            new_price_str = format_price(new_price_per_gram)
            self.session.commit()
            logger.info(f"Updated {guest.name} price from {old_price_str} to {new_price_str}")
            return True
        
        logger.warning(f"Guest with ID {guest_id} not found")
        return False
    
    def update_guest_url(self, guest_id: int, url: str) -> bool:
        """Update guest supplier URL."""
        logger.debug(f"Updating URL for guest ID: {guest_id}")
        guest = self.session.get(Guest, guest_id)
        
        if guest:
            logger.info(f"Updating URL for {guest.name}")
            old_url = guest.url
            guest.url = url
            self.session.commit()
            logger.info(f"Updated {guest.name} URL from {old_url} to {url}")
            return True
        
        logger.warning(f"Guest with ID {guest_id} not found")
        return False
    
    def recalculate_volume(self, guest_id: int) -> Optional[float]:
        """Recalculate volume for a guest from stored SMILES."""
        logger.debug(f"Recalculating volume for guest ID: {guest_id}")
        guest = self.session.get(Guest, guest_id)
        
        if not guest:
            logger.warning(f"Guest with ID {guest_id} not found")
            return None

        if not guest.smiles:
            logger.warning(f"Guest with ID {guest_id} does not have SMILES stored")
            return None
        
        try:
            logger.info(f"Recalculating volume for {guest.name}")
            old_volume = guest.molecular_volume
            old_volume_str = format_volume(old_volume)
            new_volume = self.calculate_volume(guest.smiles)
            new_volume_str = format_volume(new_volume)
            guest.molecular_volume = new_volume
            self.session.commit()
            logger.info(f"Updated {guest.name} volume from {old_volume_str} to {new_volume_str}")
            return new_volume
        
        except Exception as e:
            logger.error(f"Failed to recalculate volume for {guest.name}: {e}")
            self.session.rollback()
            raise ValueError(f"Failed to recalculate volume: {e}")
    
    def delete_guest(self, guest_id: int) -> bool:
        """Delete a guest from the database."""
        logger.debug(f"Deleting guest with ID: {guest_id}")

        guest = self.session.get(Guest, guest_id)
        
        if guest:
            guest_name = guest.name
            self.session.delete(guest)
            self.session.commit()
            logger.info(f"Deleted guest '{guest_name}'")
            return True
        
        logger.warning(f"Guest with ID {guest_id} not found")
        return False
    
    def close(self):
        """Close database session."""
        logger.debug("Closing GuestCalculator session")
        self.session.close()

def main(args):
    """
    CLI interface for guest calculations.
    
    Usage:
        python -m supramatch.modules.guest_calc <smiles> [--name Benzene] [--mass 78.11] [--cas 71-43-2]
                                                [--supplier Sigma-Aldrich] [--price 66.10] [--state liquid]
                                                [--url https://www.sigmaaldrich.com/US/en/product/sial/401765?srsltid=AfmBOorEti16SKK4bnwJ6WVzfspI86AYKTrERWWSVn3sCkd3fbFlpADa]
    
    Examples:
        python -m supramatch.modules.guest_calc c1ccccc1 --name Benzene --cas 71-43-2
        python -m supramatch.modules.guest_calc "Br[C@]12C[C@@H]3C[C@H](C1)C[C@@](Br)(C3)C2" --name 1,3-Dibromoadamantane --cas 876-53-9 --price 75.75
    """
    if len(args) < 2:
        logger.error("Missing required arguments")
        print("Usage: python -m supramatch.modules.guest_calc <smiles> [options]", file=sys.stderr)
        return 1
    
    smiles = args[1]
    name = None
    molar_mass = None
    cas_number = None
    supplier = None
    price_per_gram = None
    physical_state = None
    url = None

    i = 2
    while i < len(args):
        if args[i] == '--name':
            name = args[i + 1]
            i += 2
        elif args[i] == '--mass':
            molar_mass = float(args[i + 1])
            i += 2
        elif args[i] == '--cas':
            cas_number = args[i + 1]
            i += 2
        elif args[i] == '--supplier':
            supplier = args[i + 1]
            i += 2
        elif args[i] == '--price':
            price_per_gram = float(args[i + 1])
            i += 2
        elif args[i] == '--state':
            physical_state = args[i + 1]
            i += 2
        elif args[i] == '--url':
            url = args[i + 1]
            i += 2
        else:
            print(f"Warning: unknown option: {args[i]}")
            i += 1
    
    logger.info(f"SMILES: {smiles}, Guest name: {name}, Molar mass: {molar_mass} g/mol, CAS: {cas_number}, Supplier: {supplier}, Price: {format_price(price_per_gram)}, Physical state: {physical_state}, URL: {url}")

    calculator = GuestCalculator()
    
    try:
        if not name:
            # Just calculate properties without storing
            molecular_volume = calculator.calculate_volume(smiles=smiles)
            volume_str = format_volume(molecular_volume)
            logger.info(f"Successfully calculated volume: {volume_str}")
            print(f"Volume: {volume_str}")
        else:
            # Create guest in database
            guest = calculator.create_guest(name, smiles, molar_mass, cas_number, supplier, price_per_gram, physical_state, url)
            volume_str = format_volume(guest.molecular_volume)
            logger.info(f"Successfully created guest: {guest.name}")
            print(f"✓ Created guest '{guest.name}'")
            print(f"  Volume: {volume_str}")
        
        calculator.close()
        return 0
    
    except Exception as e:
        logger.error(f"Error creating guest: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        calculator.close()
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))