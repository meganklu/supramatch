"""
Match guest molecules to host cages based on packing coefficient and price.

Evaluation Criteria:
    - Packing Coefficient (PC): Geometric fit (0.55 ± 0.09 optimal)
    - Price per Gram ($/g): Cost efficiency
    - Quality Score: Combined metric (0-100)
"""

import logging
from typing import List, Optional
from supramatch.db import queries
from supramatch.db.database import get_connection, close_connection
from supramatch.models.cage import Cage
from supramatch.models.guest import Guest
from supramatch.models.match import Match
from supramatch.config import HG_MATCH_CONFIG
from supramatch.utils.helpers import format_packing_coefficient

logger = logging.getLogger(__name__)

class MatchingEngine:
    """
    Match guest molecules to host cages based on packing coefficient and price.

    Evaluation:
        - Primary: Packing coefficient (geometric fit)
        - Secondary: Price per gram (cost efficiency)
    """

    def __init__(self):
        self.conn = get_connection()

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

    # ==================== LOOKUPS ====================

    def get_cage(self, cage_id: int) -> Optional[Cage]:
        """Retrieve a cage by ID."""
        return queries.get_cage_by_id(self.conn, cage_id)

    def get_guest(self, guest_id: int) -> Optional[Guest]:
        """Retrieve a guest by ID."""
        return queries.get_guest_by_id(self.conn, guest_id)

    # ==================== DATABASE OPERATIONS ====================

    def create_match(
        self,
        cage_id: int,
        guest_id: int
    ) -> Match:
        """
        Create a match and calculate metrics.

        Args:
            cage_id: Cage ID.
            guest_id: Guest ID.

        Returns:
            Match: The created match.

        Raises:
            ValueError: If cage/guest not found or match already exists.
        """
        logger.debug(f"Creating match: cage_id={cage_id}, guest_id={guest_id}")

        cage = queries.get_cage_by_id(self.conn, cage_id)
        guest = queries.get_guest_by_id(self.conn, guest_id)

        if not cage:
            logger.error(f"Cage with ID {cage_id} not found")
            raise ValueError(f"Cage with ID {cage_id} not found")

        if not guest:
            logger.error(f"Guest with ID {guest_id} not found")
            raise ValueError(f"Guest with ID {guest_id} not found")

        # Check if match already exists
        existing = queries.get_match_by_cage_guest(self.conn, cage_id, guest_id)

        if existing:
            logger.warning(f"Match already exists for cage {cage_id} and guest {guest_id}")
            raise ValueError(f"Match already exists for cage {cage_id} and guest {guest_id}")

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
        logger.debug(f"Match viable: {is_viable}")

        match = queries.create_match(
            self.conn,
            cage_id=cage_id,
            guest_id=guest_id,
            packing_coefficient=pc,
            quality_score=quality_score,
            is_viable=is_viable
        )

        logger.info(f"Created match: {cage.name} + {guest.name} (PC={pc_str}, quality={quality_score})")
        return match

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
    ) -> List[Match]:
        """
        Find matching guests for a cage with multiple filter criteria.

        Args:
            cage_id: Cage ID.
            pc_ideal: Ideal packing coefficient.
            pc_tolerance: Packing coefficient range tolerance.
            max_price: Maximum guest price per gram ($/g).
            min_price: Minimum guest price per gram ($/g).
            only_viable: Only return matches marked as viable.
            sort_by: Sort key:
                - 'quality_score': Combined metric (descending) (default)
                - 'packing_coefficient': Geometric fit (closest to ideal packing coefficient)
                - 'price': Cost per gram (ascending)
            limit: Maximum number of results.

        Returns:
            list: List of matching Match objects.

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
            >>> for match in matches:
            ...     print(f"{match.guest_name}: {match.quality_score:.1f}/100")
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

        cage = queries.get_cage_by_id(self.conn, cage_id)

        if not cage:
            logger.error(f"Cage with ID {cage_id} not found")
            raise ValueError(f"Cage with ID {cage_id} not found")

        matches = queries.find_matches_for_cage(
            self.conn,
            cage_id,
            pc_ideal,
            pc_tolerance,
            max_price=max_price,
            min_price=min_price,
            only_viable=only_viable,
            sort_by=sort_by,
            limit=limit,
        )

        logger.info(f"Found {len(matches)} match(es) for {cage.name}")

        return matches

    def batch_create_matches(self, cage_id: int, guest_ids: List[int] = None) -> dict:
        """
        Create matches for a cage with multiple guests.

        Args:
            cage_id: Cage ID.
            guest_ids: List of guest IDs (if None, use all guests).

        Returns:
            dict: Results with keys 'created', 'skipped', 'failed'.
        """
        logger.debug(f"Creating matches: cage_id={cage_id}")

        cage = queries.get_cage_by_id(self.conn, cage_id)

        if not cage:
            logger.error(f"Cage with ID {cage_id} not found")
            raise ValueError(f"Cage with ID {cage_id} not found")

        # Get guest list
        if guest_ids:
            logger.debug(f"Selecting guests from list of guest_ids")
            guests = queries.get_guests_by_ids(self.conn, guest_ids)
        else:
            guests = queries.list_guests(self.conn)

        results = {'created': 0, 'skipped': 0, 'failed': 0}

        for guest in guests:
            try:
                logger.debug(f"Creating match: cage_id={cage_id}, guest_id={guest.id}")

                # Check if match already exists
                existing = queries.get_match_by_cage_guest(self.conn, cage_id, guest.id)

                if existing:
                    logger.debug(f"Match already exists for cage {cage_id} and guest {guest.id}")
                    results['skipped'] += 1
                    continue

                self.create_match(cage_id, guest.id)
                results['created'] += 1

            except Exception as e:
                logger.error(f"Failed to create match between cage_id={cage_id} and guest_id={guest.id}: {e}", exc_info=True)
                results['failed'] += 1

        logger.info(f"Created matches for cage_id={cage_id}: {results['created']} created, {results['skipped']} skipped, {results['failed']} failed")
        return results

    def list_matches_for_cage(self, cage_id: int) -> List[Match]:
        """Get all matches for a cage, regardless of fit or viability."""
        logger.debug(f"Retrieving all matches for cage_id={cage_id}")
        return queries.list_matches_for_cage(self.conn, cage_id)

    def get_match(self, match_id: int) -> Optional[Match]:
        """Get a specific match."""
        logger.debug(f"Retrieving match with ID: {match_id}")
        return queries.get_match(self.conn, match_id)

    def update_match_notes(self, match_id: int, notes: str) -> bool:
        """Update notes for a match."""
        logger.debug(f"Updating notes for match with ID: {match_id}")
        match = queries.get_match(self.conn, match_id)

        if match:
            queries.update_match_notes(self.conn, match_id, notes)
            logger.info(f"Updated match_id={match_id} notes from '{match.notes}' to '{notes}'")
            return True

        logger.warning(f"Match with ID {match_id} not found")
        return False

    def delete_match(self, match_id: int) -> bool:
        """Delete a match."""
        logger.debug(f"Deleting match with ID: {match_id}")

        match = queries.get_match(self.conn, match_id)

        if match:
            queries.delete_match(self.conn, match_id)
            logger.info(f"Deleted match")
            return True

        logger.warning(f"Match with ID {match_id} not found")
        return False

    def delete_all_matches_for_cage(self, cage_id: int) -> int:
        """Delete all matches for a cage."""
        logger.debug(f"Deleting matches with cage_id={cage_id}")
        count = queries.delete_matches_for_cage(self.conn, cage_id)
        logger.info(f"Deleted {count} match(es)")
        return count

    def close(self):
        """Close database connection."""
        logger.debug("Closing MatchingEngine connection")
        close_connection()
