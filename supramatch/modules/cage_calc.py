"""
Calculate and manage cage cavity volumes in the database.

Uses CageCavityCalc
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from CageCavityCalc.CageCavityCalc import cavity
from sqlalchemy import select
from supramatch.db.base import Base, TimestampMixin 
from supramatch.db.models import Cage
from supramatch.db.database import get_session
from supramatch.config import CAGE_CALC_CONFIG
from supramatch.utils.helpers import format_volume

logger = logging.getLogger(__name__)

class CageCalculator:
    """
    Handles cage volume calculations and database operations.
    
    Volumes:
        All calculations are in Å³
    """
    
    def __init__(self):
        self.session = get_session()

        # Load config parameters
        self.grid_spacing = CAGE_CALC_CONFIG["grid_spacing"]
        self.distance_threshold_multiplier = CAGE_CALC_CONFIG["distance_threshold_multiplier"]
        self.min_distance_threshold = CAGE_CALC_CONFIG["min_distance_threshold"]

        logger.debug(
            f"CageCalculator initialized with config: "
            f"grid_spacing={self.grid_spacing}, "
            f"distance_threshold_multiplier={self.distance_threshold_multiplier}, "
            f"min_distance_threshold={self.min_distance_threshold}"
        )
    
    # ==================== CALCULATIONS ====================

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
            logger.error(f"PDB file not found: {cage_pdb_file}")
            raise FileNotFoundError(f"PDB file not found: {cage_pdb_file}")
        
        logger.debug(f"Calculating volume for PDB file: {cage_pdb_file}")

        try:
            cav = cavity()
            cav.read_file(cage_pdb_file)
            logger.debug(f"PDB file read successfully")
            
            # Calculate window radius
            window_radius = cav.calculate_window()
            logger.debug(f"Window radius calculated: {window_radius:.2f}")
            
            # Set distance threshold
            cav.distance_threshold_for_90_deg_angle = (
                window_radius * self.distance_threshold_multiplier
            )
            
            if cav.distance_threshold_for_90_deg_angle < self.min_distance_threshold:
                logger.debug(f"Distance threshold below minimum, setting to {self.min_distance_threshold}")
                cav.distance_threshold_for_90_deg_angle = self.min_distance_threshold

            logger.debug(f"Distance threshold set to: {cav.distance_threshold_for_90_deg_angle:.2f}")
            
            # Set grid parameters
            cav.grid_spacing = float(self.grid_spacing)
            cav.dummy_atom_radii = float(self.grid_spacing)
            
            # Calculate and return volume (in cubic angstroms)
            volume = cav.calculate_volume()
            volume_str = format_volume(volume)
            logger.debug(f"Cavity volume calculated: {volume_str}")
            
            if volume is None or volume <= 0:
                logger.error(f"Invalid volume calculation result: {volume}")
                raise ValueError("Invalid volume calculation result")
            
            logger.info(f"Successfully calculated cavity volume: {volume_str}")
            return volume
        
        except Exception as e:
            logger.error(f"Failed to calculate cavity volume: {e}", exc_info=True)
            raise ValueError(f"Failed to calculate cavity volume: {e}")
    
    # ==================== UTILITIES ====================

    def extract_cage_name(self, cage_pdb_file: str) -> str:
        """
        Extracts cage name from PDB COMPND line.
        
        Args:
            cage_pdb_file: Path to cage PDB file.
        
        Returns:
            str: Cage name or filename stem if not found.
        """
        logger.debug(f"Extracting cage name from: {cage_pdb_file}")

        try:
            with open(cage_pdb_file, "r") as file:
                for line in file:
                    if line.startswith("COMPND"):
                        name = line[6:].strip()
                        if name:
                            logger.debug(f"Cage name extracted from PDB: {name}")
                            return name
        except FileNotFoundError:
            logger.warning(f"Could not read PDB file: {cage_pdb_file}")
        
        # Fallback to filename stem
        name = Path(cage_pdb_file).stem
        logger.debug(f"Using filename stem as cage name: {name}")
        return name
    
    # ==================== DATABASE OPERATIONS ====================

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
        logger.info(f"Creating cage from PDB file: {pdb_file}")

        pdb_path = Path(pdb_file)
        
        if not pdb_path.exists():
            logger.error(f"PDB file not found: {pdb_file}")
            raise FileNotFoundError(f"PDB file not found: {pdb_file}")
        
        # Extract name if not provided
        if cage_name is None:
            cage_name = self.extract_cage_name(str(pdb_path))

        logger.debug(f"Cage name: {cage_name}")

        # Check if cage already exists
        stmt = select(Cage).filter_by(name=cage_name)
        existing = self.session.scalars(stmt).first()
        if existing:
            logger.warning(f"Cage '{cage_name}' already exists in database")
            raise ValueError(f"Cage '{cage_name}' already exists in database")
        
        # Calculate volume (in cubic angstroms)
        logger.debug(f"Calculating cavity volume for {cage_name}")
        volume = self.calculate_volume(str(pdb_path))
        volume_str = format_volume(volume)
        
        # Create cage object
        cage = Cage(
            name=cage_name,
            cas_number=cas_number,
            pdb_file=str(pdb_path.absolute()),
            cavity_volume=volume
        )
        
        self.session.add(cage)
        self.session.commit()
        
        logger.info(f"Created cage '{cage_name}' with volume {volume_str}")
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
            logger.debug(f"Retrieving cage with ID: {cage_id}")
            return self.session.get(Cage, cage_id)
        elif cage_name:
            logger.debug(f"Retrieving cage with name: {cage_name}")
            stmt = select(Cage).filter_by(name=cage_name)
            return self.session.scalars(stmt).first()
        return None
    
    def list_cages(self):
        """
        Get all cages from the database.
        
        Returns:
            list: List of all Cage objects.
        """
        logger.debug("Retrieving all cages from database")
        stmt = select(Cage)
        cages = self.session.scalars(stmt).all()
        logger.info(f"Found {len(cages)} cages in database")
        return cages
    
    def update_cage_volume(self, cage_id: int, recalculate: bool = False) -> Optional[float]:
        """
        Update cage volume by recalculating from PDB file.
        
        Args:
            cage_id: Cage ID.
            recalculate: If True, recalculate volume from PDB file.
        
        Returns:
            float: New volume in Ų or None if cage not found.
        """
        logger.debug(f"Updating volume for cage ID: {cage_id}")

        cage = self.session.get(Cage, cage_id)
        
        if not cage:
            logger.warning(f"Cage with ID {cage_id} not found")
            return None
        
        if recalculate and cage.pdb_file:
            try:
                logger.info(f"Recalculating volume for {cage.name}")
                old_volume = cage.cavity_volume
                old_volume_str = format_volume(old_volume)
                new_volume = self.calculate_volume(cage.pdb_file)
                new_volume_str = format_volume(new_volume)
                cage.cavity_volume = new_volume
                self.session.commit()
                logger.info(f"Updated {cage.name} volume from {old_volume_str} to {new_volume_str}")
                return new_volume
            except Exception as e:
                logger.error(f"Failed to recalculate volume for {cage.name}: {e}")
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
        logger.debug(f"Deleting cage with ID: {cage_id}")

        cage = self.session.get(Cage, cage_id)
        
        if cage:
            cage_name = cage.name
            self.session.delete(cage)
            self.session.commit()
            logger.info(f"Deleted cage '{cage_name}'")
            return True

        logger.warning(f"Cage with ID {cage_id} not found")
        return False
    
    def close(self):
        """Close database session."""
        logger.debug("Closing CageCalculator session")
        self.session.close()
