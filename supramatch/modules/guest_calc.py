"""
Calculate and manage guest molecule properties in the database.
    
Volumes calculated from SMILES using RDKit's ComputeMolVolume()
"""

import sys
from pathlib import Path
from typing import Optional, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

from ..db.database import get_session
from ..db.models import Guest

class GuestCalculator:
    """
    Handles guest molecule calculations and database operations.
    
    Volumes:
        All calculations are in Å³
        Volume calculated via RDKit using the rdkit.Chem.AllChem module
    """
    
    def __init__(self):
        self.session = get_session()
    
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
        if not smiles or not isinstance(smiles, str):
            raise ValueError("SMILES must be a non-empty string")
        
        try:
            mol = Chem.MolFromSmiles(smiles)
            
            if mol is None:
                raise ValueError(f"Invalid SMILES string: {smiles}")
            
            # Add hydrogens
            mol = Chem.AddHs(mol)
            
            # Embed molecule with 3D coordinates
            conf_id = AllChem.EmbedMolecule(mol, randomSeed=0xf00d)
            
            if conf_id == -1:
                # Fallback for difficult molecules
                AllChem.EmbedMolecule(mol, AllChem.ETKDG())
            
            # Optimize geometry
            AllChem.MMFFOptimizeMolecule(mol)
            
            # Calculate volume (in cubic angstroms)
            volume = AllChem.ComputeMolVolume(mol)
            
            if volume is None or volume <= 0:
                raise ValueError("Invalid volume calculation result")
            
            return volume
        
        except Exception as e:
            raise ValueError(f"Failed to calculate volume for SMILES '{smiles}': {e}")
    
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
        if not name or not isinstance(name, str):
            raise ValueError("Name must be a non-empty string")
        
        if not smiles or not isinstance(smiles, str):
            raise ValueError("SMILES must be a non-empty string")
        
        # Check if guest already exists by CAS number or name
        if cas_number:
            existing = self.session.query(Guest).filter_by(cas_number=cas_number).first()
            if existing:
                raise ValueError(f"Guest with CAS number '{cas_number}' already exists")
        
        existing = self.session.query(Guest).filter_by(name=name).first()
        if existing:
            raise ValueError(f"Guest with name '{name}' already exists")
        
        # Validate molar mass
        if molar_mass is not None and molar_mass < 0:
            raise ValueError("Molar mass cannot be negative")

        # Validate price
        if price_per_gram is not None and price_per_gram < 0:
            raise ValueError("Price cannot be negative")
        
        # Calculate properties
        molecular_volume = self.calculate_volume(smiles)
        
        # Validate physical state
        valid_states = {'solid', 'liquid', 'gas'}
        if physical_state and physical_state.lower() not in valid_states:
            raise ValueError(f"Physical state must be one of {valid_states}")
        
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
        
        return guest
    
    def get_guest(self, guest_id: int = None, cas_number: str = None, name: str = None) -> Optional[Guest]:
        """Retrieve a guest from the database."""
        if guest_id:
            return self.session.query(Guest).get(guest_id)
        elif cas_number:
            return self.session.query(Guest).filter_by(cas_number=cas_number).first()
        elif name:
            return self.session.query(Guest).filter_by(name=name).first()
        return None
    
    def search_guests(self, name_pattern: str = None, supplier: str = None):
        """Search for guests with flexible criteria."""
        query = self.session.query(Guest)
        
        if name_pattern:
            query = query.filter(Guest.name.ilike(f"%{name_pattern}%"))
        
        if supplier:
            query = query.filter_by(supplier=supplier)
        
        return query.all()
    
    def list_guests(self, limit: int = None, offset: int = 0):
        """Get all guests from the database with optional pagination."""
        query = self.session.query(Guest).offset(offset)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def update_guest_price(self, guest_id: int, new_price_per_gram: float) -> bool:
        """Update guest price without recalculating properties."""
        if new_price_per_gram < 0:
            raise ValueError("Price cannot be negative")
        
        guest = self.session.query(Guest).get(guest_id)
        
        if guest:
            guest.price_per_gram = new_price_per_gram
            self.session.commit()
            return True
        
        return False
    
    def update_guest_url(self, guest_id: int, url: str) -> bool:
        """Update guest supplier URL."""
        guest = self.session.query(Guest).get(guest_id)
        
        if guest:
            guest.url = url
            self.session.commit()
            return True
        
        return False
    
    def recalculate_volume(self, guest_id: int) -> Optional[float]:
        """Recalculate volume for a guest from stored SMILES."""
        guest = self.session.query(Guest).get(guest_id)
        
        if not guest or not guest.smiles:
            return None
        
        try:
            new_volume = self.calculate_volume(guest.smiles)
            guest.molecular_volume = new_volume
            self.session.commit()
            return new_volume
        
        except Exception as e:
            self.session.rollback()
            raise ValueError(f"Failed to recalculate volume: {e}")
    
    def delete_guest(self, guest_id: int) -> bool:
        """Delete a guest from the database."""
        guest = self.session.query(Guest).get(guest_id)
        
        if guest:
            self.session.delete(guest)
            self.session.commit()
            return True
        
        return False
    
    def close(self):
        """Close database session."""
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
    
    calculator = GuestCalculator()
    
    try:
        if not name:
            # Just calculate properties without storing
            molecular_volume = calculator.calculate_volume(smiles=smiles)
            print(f"Volume: {molecular_volume:.2f} Å³")
        else:
            # Create guest in database
            guest = calculator.create_guest(name, smiles, molar_mass, cas_number, supplier, price_per_gram, physical_state, url)
            print(f"✓ Created guest '{guest.name}'")
            print(f"  Volume: {guest.molecular_volume:.2f} Å³")
        
        calculator.close()
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        calculator.close()
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))