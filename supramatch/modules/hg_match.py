"""
Match guest molecules to host cages based on packing coefficient and price.

Evaluation Criteria:
    - Packing Coefficient (PC): Geometric fit (0.55 ± 0.09 optimal)
    - Price per Gram ($/g): Cost efficiency
    - Quality Score: Combined metric (0-100)
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional
from sqlalchemy import desc, asc, select, func
from supramatch.db.models import Guest
from supramatch.db.models import Cage, Guest, HostGuestPairing
from supramatch.db.database import get_session
from supramatch.config import HG_MATCH_CONFIG
from supramatch.utils.helpers import format_volume, format_price, format_packing_coefficient

logger = logging.getLogger(__name__)

class MatchingEngine:
    """
    Match guest molecules to host cages based on packing coefficient and price.
    
    Evaluation:
        - Primary: Packing coefficient (geometric fit)
        - Secondary: Price per gram (cost efficiency)
    """
    
    def __init__(self):
        self.session = get_session()
        
        # Load config parameters
        self.pc_ideal_default = HG_MATCH_CONFIG["pc_ideal_default"]
        self.pc_tolerance_default = HG_MATCH_CONFIG["pc_tolerance_default"]
        self.viable_threshold = HG_MATCH_CONFIG["viable_threshold"]

        logger.debug(
            f"MatchingEngine initialized with config: "
            f"pc_ideal_default={self.pc_ideal_default}, "
            f"pc_tolerance_default={self.pc_tolerance_default}, "
            f"viable_threshold={self.viable_threshold}"
        )
    
    # ==================== CALCULATIONS ====================

    def calculate_packing_coefficient(
        self,
        cage_volume: float,
        guest_volume: float
    ) -> float:
        """
        Calculate packing coefficient for a host-guest pair.
        
        Args:
            cage_volume: Cavity volume in Å³.
            guest_volume: Guest volume in Å³.
        
        Returns:
            float: Packing coefficient (0-1).
        
        Raises:
            ValueError: If volumes are invalid.
        """
        logger.debug(f"Calculating packing coefficient: cage_volume={cage_volume}, guest_volume={guest_volume}")

        if cage_volume <= 0 or guest_volume <= 0:
            logger.error("Volumes must be positive values")
            raise ValueError("Volumes must be positive values")
        
        pc = guest_volume / cage_volume
        pc = min(pc, 1.0)
        pc_str = format_packing_coefficient(pc)
        logger.info(f"Calculated packing coefficent: {pc_str}")
        return pc  # Cap at 1.0

    def calculate_quality_score(
        self,
        packing_coefficient: float,
        guest_price: float
    ) -> float:
        """
        Calculate quality score for a host-guest pair (0-100).
        
        Balances two factors:
        1. Geometric fit (packing coefficient): 0-50 points
           - Optimal range 0.55 ± 0.09 gets full points
           - Outside this range score decreases
        
        2. Cost efficiency (price per gram): 0-50 points
           - Lower price = higher score
           - Assumes typical range $0.10-$100.00/g
        
        Args:
            packing_coefficient: Volume ratio (0–1)
            guest_price: Cost in USD per gram ($/g)

        Returns:
            float: Quality score (0-100), higher is better

        Raises:
            ValueError: If packing coefficient or price are invalid.
        """
        logger.debug(f"Calculating quality score: packing_coefficient={packing_coefficient}, guest_price={guest_price}")

        # PC score: optimal at 0.55 ± 0.09
        if abs(packing_coefficient - self.pc_ideal_default) <= self.pc_tolerance_default:
            # Full points in optimal range
            pc_score = 50
        else:
            # Scale based on amount outside of ideal range
            pc_score = 50 - (abs(packing_coefficient - self.pc_ideal_default) * 100) 
        
        # Price score: lower price = higher score
        if guest_price:
            # Normalize on typical range $0.10-$100.00/g
            # At $0.10/g = ~50 points
            # At $10.00/g = 45 points
            # At $100.00/g = 0 points
            # Formula: 50 - (price * 0.5)
            price_score = max(0, 50 - (guest_price * 0.5))
        else:
            price_score = 25  # Neutral if no price
        
        return pc_score + price_score
    
    # ==================== DATABASE OPERATIONS ====================

    def create_pairing(
        self,
        cage_id: int,
        guest_id: int
    ) -> HostGuestPairing:
        """
        Create a pairing and calculate metrics.
        
        Args:
            cage_id: Cage ID.
            guest_id: Guest ID.
        
        Returns:
            HostGuestPairing: The created pairing object.
        
        Raises:
            ValueError: If cage/guest not found or pairing already exists.
        """
        logger.debug(f"Creating pairing: cage_id={cage_id}, guest_id={guest_id}")

        cage = self.session.get(Cage, cage_id)
        guest = self.session.get(Guest, guest_id)
        
        if not cage:
            logger.error(f"Cage with ID {cage_id} not found")
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        if not guest:
            logger.error(f"Guest with ID {guest_id} not found")
            raise ValueError(f"Guest with ID {guest_id} not found")
        
        # Check if pairing already exists
        stmt = select(HostGuestPairing).filter_by(cage_id=cage_id, guest_id=guest_id)
        existing = self.session.scalars(stmt).first()
        
        if existing:
            logger.warning(f"Pairing already exists for cage {cage_id} and guest {guest_id}")
            raise ValueError(f"Pairing already exists for cage {cage_id} and guest {guest_id}")
        
        # Calculate packing coefficient
        pc = self.calculate_packing_coefficient(cage.cavity_volume, guest.molecular_volume)
        pc_str = format_packing_coefficient(pc)
        logger.debug(f"Packing coefficient calculated: {pc_str}")

        # Calculate quality score
        quality_score = self.calculate_quality_score(pc, guest.price_per_gram)
        logger.debug(f"Quality score calculated: {quality_score}")

        # Determine viability (default: optimal range 0.55 ± 0.09, config viability threshold)
        if self.viable_threshold:
            is_viable = abs(pc - self.pc_ideal_default) <= self.pc_tolerance_default
        else:
            is_viable = True
        logger.debug(f"Pairing viable: {is_viable}")
        
        pairing = HostGuestPairing(
            cage_id=cage_id,
            guest_id=guest_id,
            packing_coefficient=pc,
            quality_score=quality_score,
            is_viable=is_viable
        )
        
        self.session.add(pairing)
        self.session.commit()
        
        logger.info(f"Created pairing: {cage.name} + {guest.name} (PC={pc_str}, quality={quality_score})")
        return pairing
    
    def match_guests_to_cage(
        self,
        cage_id: int,
        pc_ideal: float = None,
        pc_tolerance: float = None,
        max_price: float = None,
        min_price: float = None,
        only_viable: bool = True,
        sort_by: str = 'quality_score',
        limit: int = None
    ) -> List[HostGuestPairing]:
        """
        Find matching guests for a cage with multiple filter criteria.
        
        Args:
            cage_id: Cage ID.
            pc_ideal: Ideal packing coefficient.
            pc_tolerance: Packing coefficient range tolerance.
            max_price: Maximum guest price per gram ($/g).
            min_price: Minimum guest price per gram ($/g).
            only_viable: Only return pairings marked as viable.
            sort_by: Sort key:
                - 'quality_score': Combined metric (descending) (default)
                - 'packing_coefficient': Geometric fit (closest to ideal packing coefficient)
                - 'price': Cost per gram (ascending)
            limit: Maximum number of results.
        
        Returns:
            list: List of matching HostGuestPairing objects.
        
        Raises:
            ValueError: If cage not found.
        
        Example:
            >>> engine = MatchingEngine()
            >>> matches = engine.match_guests_to_cage(
            ...     cage_id=1,
            ...     pc_ideal=0.55,
            ...     pc_tolerance=0.09,
            ...     max_price=5.0,
            ...     sort_by='quality_score',
            ...     limit=10
            ... )
            >>> for pairing in matches:
            ...     print(f"{pairing.guest.name}: {pairing.quality_score:.1f}/100")
        """
        logger.info(f"Finding matches for cage_id={cage_id}")
        logger.debug(f"Filters: pc_ideal={pc_ideal}, pc_tolerance={pc_tolerance}, max_price={max_price}, min_price={min_price}, only_viable={only_viable}, sort_by={sort_by}, limit={limit}")

        # Use defaults from config if not provided
        if pc_ideal is None:
            pc_ideal = self.pc_ideal_default
            logger.debug(f"Ideal packing coefficient set to: {format_packing_coefficient(pc_ideal)}")
        if pc_tolerance is None:
            pc_tolerance = self.pc_tolerance_default
            logger.debug(f"Packing coefficient tolerance set to: {format_packing_coefficient(pc_tolerance)}")

        cage = self.session.get(Cage, cage_id)
        
        if not cage:
            logger.error(f"Cage with ID {cage_id} not found")
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        # Build query
        logger.debug(f"Filtering for cage_id={cage_id}, pc_ideal={pc_ideal}, pc_tolerance={pc_tolerance}")
        stmt = select(HostGuestPairing).where(
            HostGuestPairing.cage_id == cage_id,
            func.abs(HostGuestPairing.packing_coefficient - pc_ideal) <= pc_tolerance
        )
        
        if only_viable:
            logger.debug("Filtering for viable guests")
            stmt = stmt.where(HostGuestPairing.is_viable == True)
        
        needs_guest_join = max_price is not None or min_price is not None or sort_by == 'price'
        if needs_guest_join:
            stmt = stmt.join(Guest)
        
            if max_price is not None:
                logger.debug(f"Filtering for max_price={max_price}")
                stmt = stmt.where(Guest.price_per_gram <= max_price)
            
            if min_price is not None:
                logger.debug(f"Filtering for min_price={min_price}")
                stmt = stmt.where(Guest.price_per_gram >= min_price)

        # Apply sorting
        if sort_by == 'quality_score':
            logger.debug(f"Sorting by quality_score")
            stmt = stmt.order_by(HostGuestPairing.quality_score.desc())
        elif sort_by == 'packing_coefficient':
            logger.debug(f"Sorting by packing_coefficient")
            stmt = stmt.order_by(func.abs(HostGuestPairing.packing_coefficient - pc_ideal).asc())
        elif sort_by == 'price':
            logger.debug(f"Sorting by price")
            stmt = stmt.order_by(Guest.price_per_gram.asc().nulls_last())
        
        pairings = self.session.scalars(stmt).all()

        if limit:
            logger.debug(f"Limiting pairings to {limit}")
            pairings = pairings[:limit]

        logger.info(f"Found {len(pairings)} match(es) for {cage.name}")

        return pairings
    
    def batch_create_pairings(self, cage_id: int, guest_ids: List[int] = None) -> dict:
        """
        Create pairings for a cage with multiple guests.
        
        Args:
            cage_id: Cage ID.
            guest_ids: List of guest IDs (if None, use all guests).
        
        Returns:
            dict: Results with keys 'created', 'skipped', 'failed'.
        """
        logger.debug(f"Creating pairing: cage_id={cage_id}")

        cage = self.session.get(Cage, cage_id)
        
        if not cage:
            logger.error(f"Cage with ID {cage_id} not found")
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        # Get guest list
        stmt = select(Guest)
        if guest_ids:
            logger.debug(f"Selecting guests from list of guest_ids")
            stmt = stmt.where(Guest.id.in_(guest_ids))
        guests = self.session.scalars(stmt).all()
        
        results = {'created': 0, 'skipped': 0, 'failed': 0}
        
        for guest in guests:
            try:
                logger.debug(f"Creating pairing: cage_id={cage_id}, guest_id={guest.id}")

                # Check if pairing already exists
                stmt = select(HostGuestPairing).filter_by(cage_id=cage_id, guest_id=guest.id)
                existing = self.session.scalars(stmt).first()
                
                if existing:
                    logger.debug(f"Pairing already exists for cage {cage_id} and guest {guest.id}")
                    results['skipped'] += 1
                    continue
                
                self.create_pairing(cage_id, guest.id)
                results['created'] += 1
            
            except Exception as e:
                logger.error(f"Failed to create pairing between cage_id={cage_id} and guest_id={guest.id}: {e}", exc_info=True)
                results['failed'] += 1
        
        logger.info(f"Created pairings for cage_id={cage_id}: {results['created']} created, {results['skipped']} skipped, {results['failed']} failed")
        return results
    
    def get_pairing(self, pairing_id: int) -> Optional[HostGuestPairing]:
        """Get a specific pairing."""
        logger.debug(f"Retrieving pairing with ID: {pairing_id}")
        return self.session.get(HostGuestPairing, pairing_id)
    
    def update_pairing_notes(self, pairing_id: int, notes: str) -> bool:
        """Update notes for a pairing."""
        logger.debug(f"Updating notes for pairing with ID: {pairing_id}")
        pairing = self.session.get(HostGuestPairing, pairing_id)
        
        if pairing:
            old_notes = pairing.notes
            pairing.notes = notes
            logger.info(f"Updated pairing_id={pairing_id} notes from '{old_notes}' to '{notes}'")
            self.session.commit()
            return True
        
        logger.warning(f"Pairing with ID {pairing_id} not found")
        return False
    
    def delete_pairing(self, pairing_id: int) -> bool:
        """Delete a pairing."""
        logger.debug(f"Deleting pairing with ID: {pairing_id}")

        pairing = self.session.get(HostGuestPairing, pairing_id)
        
        if pairing:
            self.session.delete(pairing)
            self.session.commit()
            logger.info(f"Deleted pairing")
            return True
        
        logger.warning(f"Pairing with ID {pairing_id} not found")
        return False
    
    def delete_all_pairings_for_cage(self, cage_id: int) -> int:
        """Delete all pairings for a cage."""
        logger.debug(f"Deleting pairing with cage_id={cage_id}")
        stmt = delete(HostGuestPairing).where(cage_id=cage_id)
        result = self.session.execute(stmt)
        self.session.commit()
        logger.info(f"Deleted {results.rowcount} pairings")
        return result.rowcount
    
    def close(self):
        """Close database session."""
        logger.debug("Closing MatchingEngine session")
        self.session.close()