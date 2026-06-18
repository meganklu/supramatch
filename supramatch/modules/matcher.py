#!/usr/bin/env python

"""
File: modules/matcher.py
Author: Megan K. Lu
Date: 06/18/2026
Description: Match guest molecules to host cages based on packing coefficient and price.

Evaluation Criteria:
    - Packing Coefficient (PC): Geometric fit (0.3-0.7 optimal)
    - Price per Gram ($/g): Cost efficiency
    - Quality Score: Combined metric (0-100)
    - Value Ratio: PC per dollar (higher is better)
"""

import sys
from pathlib import Path
from typing import List, Optional
from sqlalchemy import desc, asc

from ..db.database import get_session
from ..db.models import Cage, Guest, HostGuestPairing


class MatchingEngine:
    """
    Match guest molecules to host cages based on packing coefficient and price.
    
    Evaluation:
        - Primary: Packing coefficient (geometric fit)
        - Secondary: Price per gram (cost efficiency)
    """
    
    def __init__(self):
        self.session = get_session()
    
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
        existing = self.session.query(HostGuestPairing).filter_by(
            cage_id=cage_id,
            guest_id=guest_id
        ).first()
        
        if existing:
            raise ValueError(f"Pairing already exists for cage {cage_id} and guest {guest_id}")
        
        # Calculate packing coefficient
        pc = self.calculate_packing_coefficient(cage.cavity_volume, guest.molecular_volume)
        
        # Determine viability (default: optimal range 0.3-0.7)
        is_viable = 0.3 <= pc <= 0.7
        
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
        pc_min: float = 0.3,
        pc_max: float = 0.7,
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
        cage = self.session.get(Cage, cage_id)
        
        if not cage:
            raise ValueError(f"Cage with ID {cage_id} not found")
        
        # Build query
        query = self.session.query(HostGuestPairing).filter(
            HostGuestPairing.cage_id == cage_id,
            HostGuestPairing.packing_coefficient >= pc_min,
            HostGuestPairing.packing_coefficient <= pc_max
        )
        
        if only_viable:
            query = query.filter(HostGuestPairing.is_viable == True)
        
        if max_price is not None:
            query = query.join(Guest).filter(Guest.price_per_gram <= max_price)
        
        if min_price is not None:
            query = query.join(Guest).filter(Guest.price_per_gram >= min_price)
        
        # Apply sorting
        if sort_by == 'quality_score':
            # Quality score is calculated property, so sort in Python
            pairings = query.all()
            pairings.sort(key=lambda p: p.quality_score, reverse=True)
        elif sort_by == 'packing_coefficient':
            query = query.order_by(desc(HostGuestPairing.packing_coefficient))
            pairings = query.all()
        elif sort_by == 'price':
            query = query.join(Guest).order_by(Guest.price_per_gram)
            pairings = query.all()
        else:
            pairings = query.all()
        
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
        if guest_ids:
            guests = self.session.query(Guest).filter(Guest.id.in_(guest_ids)).all()
        else:
            guests = self.session.query(Guest).all()
        
        results = {'created': 0, 'skipped': 0, 'failed': 0}
        
        for guest in guests:
            try:
                # Check if pairing already exists
                existing = self.session.query(HostGuestPairing).filter_by(
                    cage_id=cage_id,
                    guest_id=guest.id
                ).first()
                
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
        count = self.session.query(HostGuestPairing).filter_by(cage_id=cage_id).delete()
        self.session.commit()
        return count
    
    def close(self):
        """Close database session."""
        self.session.close()


def main(args):
    """
    CLI interface for matching.
    
    Usage:
        python -m supramatch.modules.matcher <cage_id> <command> [--pc-min 0.3] [--pc-max 0.7] 
                             [--max-price 5.0] [--min_price 1.0] [--sort quality_score] [--limit 10]
    
    Command Options:
        - create: Create pairings for a cage with all guests.
        - match: Find matching guests for a cage with multiple filter criteria.

    Sort Options:
        - quality_score: Combined metric (default)
        - packing_coefficient: Geometric fit
        - price: Cost per gram
    
    Example:
        python -m supramatch.modules.matcher 1 create
        python -m supramatch.modules.matcher 1 match --sort quality_score --limit 10
        python -m supramatch.modules.matcher 1 match --pc-min 0.3 --pc-max 0.7 --max-price 5.0
    """
    if len(args) < 3:
        print("Usage: python -m supramatch.modules.matcher <cage_id> <command> [options]", file=sys.stderr)
        return 1
    
    try:
        cage_id = int(args[1])
    except ValueError:
        print(f"Error: cage_id must be an integer", file=sys.stderr)
        return 1

    command = args[2]
    if command == 'create': 
        try:
            engine = MatchingEngine()
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
            print(f"\nMatches for cage '{cage.name}' (Volume: {cage.cavity_volume:.2f} Å³):\n")
            
            print(f"{'#':<4} {'Guest Name':<25} {'PC':>8} {'$/g':>10} {'Score':>8}")
            print("-" * 80)
            
            for idx, pairing in enumerate(matches, 1):
                guest = pairing.guest
                
                print(
                    f"{idx:<4} "
                    f"{guest.name:<25} "
                    f"{pairing.packing_coefficient:>8.3f} "
                    f"${guest.price_per_gram if guest.price_per_gram else 0:>9.2f} "
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