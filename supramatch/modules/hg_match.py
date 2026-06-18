"""
Match guest molecules to host cages based on packing coefficient and price.

Evaluation Criteria:
    - Packing Coefficient (PC): Geometric fit (0.3-0.7 optimal)
    - Price per Gram ($/g): Cost efficiency
    - Quality Score: Combined metric (0-100)
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional
from sqlalchemy import desc, asc, select
from ..db.models import Guest
from ..db.models import Cage, Guest, HostGuestPairing
from ..db.database import get_session
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
        self.pc_min_default = HG_MATCH_CONFIG["pc_min_default"]
        self.pc_max_default = HG_MATCH_CONFIG["pc_max_default"]
        self.viable_threshold = HG_MATCH_CONFIG["viable_threshold"]

        logger.debug(
            f"MatchingEngine initialized with config: "
            f"pc_min={self.pc_min_default}, "
            f"pc_max={self.pc_max_default}, "
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
        logger.debug(f"Calculating packing coefficient: cage_id={cage_id}, guest_id={guest_id}")

        if cage_volume <= 0 or guest_volume <= 0:
            logger.error("Volumes must be positive values")
            raise ValueError("Volumes must be positive values")
        
        pc = guest_volume / cage_volume
        pc = min(pc, 1.0)
        pc_str = format_packing_coefficient(pc)
        logger.info(f"Calculated packing coefficent: {pc_str}")
        return pc  # Cap at 1.0
    
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

        # Determine viability (default: optimal range 0.3-0.7, config viability threshold)
        if self.viable_threshold:
            is_viable = self.pc_min_default <= pc <= self.pc_max_default
        else:
            is_viable = True
        logger.debug(f"Pairing viable: {is_viable}")
        
        pairing = HostGuestPairing(
            cage_id=cage_id,
            guest_id=guest_id,
            packing_coefficient=pc,
            is_viable=is_viable
        )
        
        self.session.add(pairing)
        self.session.commit()
        
        logger.info(f"Created pairing: {cage.name} + {guest.name} (PC={pc_str})")
        return pairing
    
    def match_guests_to_cage(
        self,
        cage_id: int,
        pc_min: float = None,
        pc_max: float = None,
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
            pc_min: Minimum packing coefficient.
            pc_max: Maximum packing coefficient.
            max_price: Maximum guest price per gram ($/g).
            min_price: Minimum guest price per gram ($/g).
            only_viable: Only return pairings marked as viable.
            sort_by: Sort key:
                - 'quality_score': Combined metric (default)
                - 'packing_coefficient': Geometric fit
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
            ...     pc_min=0.3,
            ...     pc_max=0.7,
            ...     max_price=5.0,
            ...     sort_by='quality_score',
            ...     limit=10
            ... )
            >>> for pairing in matches:
            ...     print(f"{pairing.guest.name}: {pairing.quality_score:.1f}/100")
        """
        logger.info(f"Finding matches for cage_id={cage_id}")
        logger.debug(f"Filters: pc_min={pc_min}, pc_max={pc_max}, max_price={max_price}, min_price={min_price}, only_viable={only_viable}, sort_by={sort_by}, limit={limit}")

        # Use defaults from config if not provided
        if pc_min is None:
            pc_min = self.pc_min_default
            logger.debug(f"Packing coefficient minimum set to: {format_packing_coefficient(pc_min)}")
        if pc_max is None:
            pc_max = self.pc_max_default
            logger.debug(f"Packing coefficient maximum set to: {format_packing_coefficient(pc_max)}")

        cage = self.session.get(Cage, cage_id)
        
        if not cage:
            logger.error(f"Cage with ID {cage_id} not found")
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        # Build query
        logger.debug(f"Filtering for cage_id={cage_id}, pc_min={pc_min}, pc_max={pc_max}")
        stmt = select(HostGuestPairing).where(
            HostGuestPairing.cage_id == cage_id,
            HostGuestPairing.packing_coefficient >= pc_min,
            HostGuestPairing.packing_coefficient <= pc_max
        )
        
        if only_viable:
            logger.debug("Filtering for viable guests")
            stmt = stmt.where(HostGuestPairing.is_viable == True)
        
        needs_guest_join = max_price is not None or min_price is not None
        if needs_guest_join:
            stmt = stmt.join(Guest)
        
            if max_price is not None:
                logger.debug(f"Filtering for max_price={max_price}")
                stmt = stmt.where(Guest.price_per_gram <= max_price)
            
            if min_price is not None:
                logger.debug(f"Filtering for min_price={min_price}")
                stmt = stmt.where(Guest.price_per_gram >= min_price)
    
        pairings = self.session.scalars(stmt).all()

        # Apply sorting
        if sort_by == 'quality_score':
            logger.debug(f"Sorting by quality_score")
            pairings.sort(key=lambda p: p.quality_score, reverse=True)
        elif sort_by == 'packing_coefficient':
            logger.debug(f"Sorting by packing_coefficient")
            pairings.sort(key=lambda p: p.packing_coefficient, reverse=True)
        elif sort_by == 'price':
            logger.debug(f"Sorting by price")
            pairings.sort(key=lambda p: p.guest.price_per_gram if p.guest.price_per_gram else float('inf'))
        
        if limit:
            logger.debug(f"Limiting pairings to {limit}")
            pairings = pairings[:limit]

        logger.info(f"Found {len(pairings)} matches for {cage.name}")

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


def main(args):
    """
    CLI interface for matching.
    
    Usage:
        python -m supramatch.modules.hg_match <cage_id> <command> [--pc-min 0.3] [--pc-max 0.7] 
                             [--max-price 5.0] [--min_price 1.0] [--sort quality_score] [--limit 10]
    
    Command Options:
        - create: Create pairings for a cage with all guests.
        - match: Find matching guests for a cage with multiple filter criteria.

    Sort Options:
        - quality_score: Combined metric (default)
        - packing_coefficient: Geometric fit
        - price: Cost per gram
    
    Example:
        python -m supramatch.modules.hg_match 1 create
        python -m supramatch.modules.hg_match 1 match --sort quality_score --limit 10
        python -m supramatch.modules.hg_match 1 match --pc-min 0.3 --pc-max 0.7 --max-price 5.0
        python -m supramatch.modules.hg_match 1 match --pc-min 0.3 --pc-max 0.7 --max-price 5.0 --min-price 1.0 --sort quality_score --limit 10
    """
    if len(args) < 3:
        logger.error("Missing required arguments")
        print("Usage: python -m supramatch.modules.hg_match <cage_id> <command> [options]", file=sys.stderr)
        return 1
    
    try:
        cage_id = int(args[1])
    except ValueError:
        print(f"Error: cage_id must be an integer", file=sys.stderr)
        return 1

    command = args[2]
    if command == 'create': 
        engine = MatchingEngine()

        try:
            engine.batch_create_pairings(cage_id)
            print(f"✓ Created pairings for cage {cage_id}")
            return 0

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            engine.close()
            return 1

    elif command == 'match':
        # Parse optional arguments
        pc_min = 0.3
        pc_max = 0.7
        max_price = None
        min_price = None
        sort_by = 'quality_score'
        limit = None
        
        i = 3
        while i < len(args):
            if args[i] == '--pc-min':
                pc_min = float(args[i + 1])
                i += 2
            elif args[i] == '--pc-max':
                pc_max = float(args[i + 1])
                i += 2
            elif args[i] == '--max-price':
                max_price = float(args[i + 1])
                i += 2
            elif args[i] == '--min-price':
                min_price = float(args[i + 1])
                i += 2
            elif args[i] == '--sort':
                sort_by = args[i + 1]
                i += 2
            elif args[i] == '--limit':
                limit = int(args[i + 1])
                i += 2
            else:
                print(f"Warning: unknown option: {args[i]}")
                i += 1
        
        engine = MatchingEngine()
        
        try:
            matches = engine.match_guests_to_cage(
                cage_id=cage_id,
                pc_min=pc_min,
                pc_max=pc_max,
                max_price=max_price,
                min_price=min_price,
                sort_by=sort_by,
                limit=limit
            )
            
            if not matches:
                print(f"No matches found for cage {cage_id}")
                engine.close()
                return 0
            
            cage = engine.session.get(Cage, cage_id)
            cage_volume_str = format_volume(cage.cavity_volume)
            print(f"\nMatches for cage '{cage.name}' (Volume: {cage_volume_str}):\n")
            
            print(f"{'#':<4} {'Guest Name':<25} {'PC':>8} {'$/g':>10} {'Score':>8}")
            print("-" * 80)
            
            for idx, pairing in enumerate(matches, 1):
                guest = pairing.guest
                
                pc_str = format_packing_coefficient(pairing.packing_coefficient)
                price_str = format_price(guest.price_per_gram)

                print(
                    f"{idx:<4} "
                    f"{guest.name:<25} "
                    f"{pc_str:>8} "
                    f"{price_str:>10} "
                    f"{pairing.quality_score:>8.1f}"
                )
            
            engine.close()
            return 0

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            engine.close()
            return 1

    else:
        print("Error: Invalid command", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))