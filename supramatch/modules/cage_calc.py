#!/usr/bin/env python

"""
File: modules/cage_calc.py
Author: Megan K. Lu
Date: 06/16/2026
Description: Calculate and manage cage cavity volumes in the database.

Volume Units:
    All volumes are in cubic angstroms (Å³)
"""

import sys
from pathlib import Path
from typing import Optional
from CageCavityCalc.CageCavityCalc import cavity

from ..db.database import get_session
from ..db.models import Cage

class CageCalculator:
    """
    Handles cage volume calculations and database operations.
    
    Volumes:
        All calculations are in Å³
    """
    
    def __init__(self):
        self.session = get_session()
        self.grid_spacing = 0.5
        self.distance_threshold_multiplier = 2.0
    
    def calculate_volume(self, cage_pdb_file: str) -> float:
        """
        Calculates the volume of the cage cavity from a PDB file.

        Args:
            cage_pdb_file: Path to cage PDB file.

        Returns:
            float: The volume of the cage cavity in Å³.
        
        Raises:
            FileNotFoundError: If PDB file doesn't exist.
            ValueError: If volume calculation fails.
        
        Example:
            >>> calc = CageCalculator()
            >>> volume = calc.calculate_volume('cage.pdb')
            >>> print(f"Volume: {volume:.2f} Å³")
            Volume: 234.50 Å³
        """
        if not Path(cage_pdb_file).exists():
            raise FileNotFoundError(f"PDB file not found: {cage_pdb_file}")
        
        try:
            cav = cavity()
            cav.read_file(cage_pdb_file)
            
            # Calculate window radius
            window_radius = cav.calculate_window()
            
            # Set distance threshold
            cav.distance_threshold_for_90_deg_angle = (
                window_radius * self.distance_threshold_multiplier
            )
            
            if cav.distance_threshold_for_90_deg_angle < 5:
                cav.distance_threshold_for_90_deg_angle = 5
            
            # Set grid parameters
            cav.grid_spacing = float(self.grid_spacing)
            cav.dummy_atom_radii = float(self.grid_spacing)
            
            # Calculate and return volume (in cubic angstroms)
            volume = cav.calculate_volume()
            
            if volume is None or volume <= 0:
                raise ValueError("Invalid volume calculation result")
            
            return volume
        
        except Exception as e:
            raise ValueError(f"Failed to calculate cavity volume: {e}")
    
    def extract_cage_name(self, cage_pdb_file: str) -> str:
        """
        Extracts cage name from PDB COMPND line.
        
        Args:
            cage_pdb_file: Path to cage PDB file.
        
        Returns:
            str: Cage name or filename stem if not found.
        """
        try:
            with open(cage_pdb_file, "r") as file:
                for line in file:
                    if line.startswith("COMPND"):
                        name = line[6:].strip()
                        if name:
                            return name
        except FileNotFoundError:
            pass
        
        return Path(cage_pdb_file).stem
    
    def create_cage(
        self,
        pdb_file: str,
        cage_name: str = None,
        cas_number: str = None
    ) -> Cage:
        """
        Create a new cage in the database with calculated volume.
        
        Args:
            pdb_file: Path to cage PDB file.
            cage_name: Optional cage name (extracted from PDB if not provided).
            cas_number: Optional CAS number.
        
        Returns:
            Cage: The created cage object.
        
        Raises:
            ValueError: If cage already exists or calculation fails.
            FileNotFoundError: If PDB file doesn't exist.
        
        Example:
            >>> calc = CageCalculator()
            >>> cage = calc.create_cage('cage.pdb', 'MyCage')
            >>> print(f"Created: {cage.name}, Volume: {cage.cavity_volume:.2f} Å³")
            Created: MyCage, Volume: 234.50 Å³
        """
        pdb_path = Path(pdb_file)
        
        if not pdb_path.exists():
            raise FileNotFoundError(f"PDB file not found: {pdb_file}")
        
        # Extract name if not provided
        if cage_name is None:
            cage_name = self.extract_cage_name(str(pdb_path))
        
        # Check if cage already exists
        existing = self.session.query(Cage).filter_by(name=cage_name).first()
        if existing:
            raise ValueError(f"Cage '{cage_name}' already exists in database")
        
        # Calculate volume (in cubic angstroms)
        volume = self.calculate_volume(str(pdb_path))
        
        # Create cage object
        cage = Cage(
            name=cage_name,
            cas_number=cas_number,
            pdb_file=str(pdb_path.absolute()),
            cavity_volume=volume
        )
        
        self.session.add(cage)
        self.session.commit()
        
        return cage
    
    def get_cage(self, cage_id: int = None, cage_name: str = None) -> Optional[Cage]:
        """
        Retrieve a cage from the database.
        
        Args:
            cage_id: Cage ID (primary key).
            cage_name: Cage name.
        
        Returns:
            Cage: The cage object or None if not found.
        """
        if cage_id:
            return self.session.query(Cage).get(cage_id)
        elif cage_name:
            return self.session.query(Cage).filter_by(name=cage_name).first()
        return None
    
    def list_cages(self):
        """
        Get all cages from the database.
        
        Returns:
            list: List of all Cage objects.
        """
        return self.session.query(Cage).all()
    
    def update_cage_volume(self, cage_id: int, recalculate: bool = False) -> Optional[float]:
        """
        Update cage volume by recalculating from PDB file.
        
        Args:
            cage_id: Cage ID.
            recalculate: If True, recalculate volume from PDB file.
        
        Returns:
            float: New volume in Ų or None if cage not found.
        """
        cage = self.session.query(Cage).get(cage_id)
        
        if not cage:
            return None
        
        if recalculate and cage.pdb_file:
            try:
                new_volume = self.calculate_volume(cage.pdb_file)
                cage.cavity_volume = new_volume
                self.session.commit()
                return new_volume
            except Exception as e:
                self.session.rollback()
                raise ValueError(f"Failed to recalculate volume: {e}")
        
        return cage.cavity_volume
    
    def delete_cage(self, cage_id: int) -> bool:
        """
        Delete a cage from the database.
        
        Args:
            cage_id: Cage ID.
        
        Returns:
            bool: True if deleted, False if not found.
        """
        cage = self.session.query(Cage).get(cage_id)
        
        if cage:
            self.session.delete(cage)
            self.session.commit()
            return True
        
        return False
    
    def close(self):
        """Close database session."""
        self.session.close()

def main(args):
    """
    CLI interface for cage calculations.
    
    Usage:
        python -m supramatch.modules.cage_calc <pdb_file> [--name name] [--cas number]
    
    Example:
        python -m supramatch.modules.cage_calc data/cage.pdb --name MyCage
    """
    if len(args) < 2:
        print("Usage: python -m supramatch.modules.cage_calc <pdb_file> [--name name] [--cas number]", file=sys.stderr)
        return 1
    
    pdb_file = args[1]
    cage_name = None
    cas_number = None

    i = 2
    while i < len(args):
        if args[i] == '--name':
            cage_name = args[i + 1]
            i += 2
        elif args[i] == '--cas':
            cas_number = args[i + 1]
            i += 2
        else:
            print(f"Warning: unknown option: {args[i]}")
            i += 1
    
    calculator = CageCalculator()
    
    try:
        cage = calculator.create_cage(pdb_file, cage_name, cas_number)
        print(f"✓ Created cage '{cage.name}': {cage.cavity_volume:.2f} Å³")
        calculator.close()
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        calculator.close()
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))