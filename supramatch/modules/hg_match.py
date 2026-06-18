"""
Match guest molecules to host cages based on packing coefficient and price.

Evaluation Criteria:
    - Packing Coefficient (PC): Geometric fit (0.3-0.7 optimal)
    - Price per Gram ($/g): Cost efficiency
    - Quality Score: Combined metric (0-100)
"""

import sys
from pathlib import Path
from typing import List, Optional
from sqlalchemy import desc, asc, select

from ..db.models import Guest
from ..db.models import Cage, Guest, HostGuestPairing
from ..db.database import get_session

from supramatch.config import HG_MATCH_CONFIG

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
        if cage_volume <= 0 or guest_volume <= 0:
            raise ValueError("Volumes must be positive values")
        
        pc = guest_volume / cage_volume
        
        return min(pc, 1.0)  # Cap at 1.0
    
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
        cage = self.session.get(Cage, cage_id)
        guest = self.session.get(Guest, guest_id)
        
        if not cage:
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        if not guest:
            raise ValueError(f"Guest with ID {guest_id} not found")
        
        # Check if pairing already exists
        stmt = select(HostGuestPairing).filter_by(cage_id=cage_id, guest_id=guest_id)
        existing = self.session.scalars(stmt).first()
        
        if existing:
            raise ValueError(f"Pairing already exists for cage {cage_id} and guest {guest_id}")
        
        # Calculate packing coefficient
        pc = self.calculate_packing_coefficient(cage.cavity_volume, guest.molecular_volume)
        
        # Determine viability (default: optimal range 0.3-0.7, config viability threshold)
        if self.viable_threshold:
            is_viable = self.pc_min_default <= pc <= self.pc_max_default
        else:
            is_viable = True
        
        pairing = HostGuestPairing(
            cage_id=cage_id,
            guest_id=guest_id,
            packing_coefficient=pc,
            is_viable=is_viable
        )
        
        self.session.add(pairing)
        self.session.commit()
        
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
        # Use defaults from config if not provided
        if pc_min is None:
            pc_min = self.pc_min_default
        if pc_max is None:
            pc_max = self.pc_max_default

        cage = self.session.get(Cage, cage_id)
        
        if not cage:
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        # Build query
        stmt = select(HostGuestPairing).where(
            HostGuestPairing.cage_id == cage_id,
            HostGuestPairing.packing_coefficient >= pc_min,
            HostGuestPairing.packing_coefficient <= pc_max
        )
        
        if only_viable:
            stmt = stmt.where(HostGuestPairing.is_viable == True)
        
        needs_guest_join = max_price is not None or min_price is not None
        if needs_guest_join:
            stmt = stmt.join(Guest)
        
            if max_price is not None:
                stmt = stmt.where(Guest.price_per_gram <= max_price)
            
            if min_price is not None:
                stmt = stmt.where(Guest.price_per_gram >= min_price)
    
        result = self.session.execute(stmt)
        pairings = result.scalars().all()

        # Apply sorting
        if sort_by == 'quality_score':
            pairings.sort(key=lambda p: p.quality_score, reverse=True)
        elif sort_by == 'packing_coefficient':
            pairings.sort(key=lambda p: p.packing_coefficient, reverse=True)
        elif sort_by == 'price':
            pairings.sort(key=lambda p: p.guest.price_per_gram if p.guest.price_per_gram else float('inf'))
        
        if limit:
            pairings = pairings[:limit]
        
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
        cage = self.session.get(Cage, cage_id)
        
        if not cage:
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        # Get guest list
        stmt = select(Guest)
        if guest_ids:
            stmt = stmt.where(Guest.id.in_(guest_ids))
        guests = self.session.execute(stmt).all()
        
        results = {'created': 0, 'skipped': 0, 'failed': 0}
        
        for guest in guests:
            try:
                # Check if pairing already exists
                stmt = select(HostGuestPairing).filter_by(cage_id=cage_id, guest_id=guest_id)
                existing = self.session.scalars(stmt).first()
                
                if existing:
                    results['skipped'] += 1
                    continue
                
                self.create_pairing(cage_id, guest.id)
                results['created'] += 1
            
            except Exception as e:
                results['failed'] += 1
        
        return results
    
    def get_pairing(self, pairing_id: int) -> Optional[HostGuestPairing]:
        """Get a specific pairing."""
        return self.session.get(HostGuestPairing, pairing_id)
    
    def update_pairing_notes(self, pairing_id: int, notes: str) -> bool:
        """Update notes for a pairing."""
        pairing = self.session.get(HostGuestPairing, pairing_id)
        
        if pairing:
            pairing.notes = notes
            self.session.commit()
            return True
        
        return False
    
    def delete_pairing(self, pairing_id: int) -> bool:
        """Delete a pairing."""
        pairing = self.session.get(HostGuestPairing, pairing_id)
        
        if pairing:
            self.session.delete(pairing)
            self.session.commit()
            return True
        
        return False
    
    def delete_all_pairings_for_cage(self, cage_id: int) -> int:
        """Delete all pairings for a cage."""
        stmt = delete(HostGuestPairing).where(cage_id=cage_id)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount
    
    def close(self):
        """Close database session."""
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
    from supramatch.utils.helpers import format_volume, format_price, format_packing_coefficient

    if len(args) < 3:
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