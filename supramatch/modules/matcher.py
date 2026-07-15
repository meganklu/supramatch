"""
Match guest molecules to host cages based on structural properties and pricing.

Evaluation Criteria:
    - Packing Coefficient (PC): Geometric fit (0.55 ± 0.09 optimal)
    - Price per Gram ($/g): Cost efficiency
    - Rotatable Bonds: Guest conformational flexibility (fewer is better)
    - Quality Score: Combined metric (0-100)

Note:
    Matches only ever store packing_coefficient. is_viable and quality_score
    are computed properties on Match (see supramatch.models.match) so they
    never go stale relative to the app's current config or the latest price
    data -- there's no separate "rescore" step after a `price lookup` run.
"""

import logging
from typing import List, Optional
from supramatch.db import queries
from supramatch.db.database import get_connection, close_connection
from supramatch.discovery.price_lookup import PriceLookup
from supramatch.models.cage import Cage
from supramatch.models.guest import Guest
from supramatch.models.match import Match
from supramatch.config import HG_MATCH_CONFIG
from supramatch.utils.helpers import format_packing_coefficient

logger = logging.getLogger(__name__)

class MatchingEngine:
    """
    Match guest molecules to host cages based on structural properties and pricing.

    Evaluation:
        - Primary: Packing coefficient (geometric fit)
        - Secondary: Price per gram (cost efficiency)
        - Tertiary: Rotatable bond count (conformational flexibility)
    """

    def __init__(self):
        self.conn = get_connection()

        # Search defaults (overridable per-call in match_guests_to_cage)
        self.pc_ideal_default = HG_MATCH_CONFIG["pc_ideal_default"]
        self.pc_tolerance_default = HG_MATCH_CONFIG["pc_tolerance_default"]

        logger.debug(
            f"MatchingEngine initialized with config: "
            f"pc_ideal_default={self.pc_ideal_default}, "
            f"pc_tolerance_default={self.pc_tolerance_default}"
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
        Create a match from geometry alone (no price required).

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

        match = queries.create_match(
            self.conn,
            cage_id=cage_id,
            guest_id=guest_id,
            packing_coefficient=pc,
        )

        logger.info(f"Created match: {cage.name} + {guest.name} (PC={pc_str})")
        return match

    def match_guests_to_cage(
        self,
        cage_id: int,
        pc_ideal: float = None,
        pc_tolerance: float = None,
        max_price: float = None,
        min_price: float = None,
        sort_by: str = 'quality_score',
        limit: int = None,
        in_inventory_only: bool = False,
    ) -> List[Match]:
        """
        Find matching guests for a cage with multiple filter criteria.

        Args:
            cage_id: Cage ID.
            pc_ideal: Ideal packing coefficient (search window center; defaults
                to the app's standard PC target if not given).
            pc_tolerance: Packing coefficient range tolerance (search window width;
                defaults to the app's standard tolerance if not given).
            max_price: Maximum guest price per gram ($/g).
            min_price: Minimum guest price per gram ($/g).
            sort_by: Sort key:
                - 'quality_score': Combined metric (descending) (default)
                - 'packing_coefficient': Geometric fit (closest to ideal packing coefficient)
                - 'price': Cost per gram (ascending)
            limit: Maximum number of results.
            in_inventory_only: Only return matches whose guest is currently
                in our physical inventory (see Guest.in_inventory).

        Returns:
            list: List of matching Match objects.

        Raises:
            ValueError: If cage not found.

        Note:
            There's no separate "only viable" filter here: the pc_ideal/pc_tolerance
            window *is* the viability concept for a search (it defaults to the app's
            standard range). Layering a second, fixed-default viability check on top
            would either be redundant with that window (when using the defaults) or
            silently return nothing when searching a different window that doesn't
            overlap the default range. Match.is_viable is still available for
            display, and is used as a filter by `price lookup`, which has no
            competing search-window concept to conflict with.

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
        logger.debug(f"Filters: pc_ideal={pc_ideal}, pc_tolerance={pc_tolerance}, max_price={max_price}, min_price={min_price}, sort_by={sort_by}, limit={limit}")

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
            in_inventory_only=in_inventory_only,
        )

        if sort_by == 'packing_coefficient':
            matches.sort(key=lambda m: abs(m.packing_coefficient - pc_ideal))
        elif sort_by == 'price':
            matches.sort(key=lambda m: (m.guest_price_per_gram is None, m.guest_price_per_gram))
        else:
            matches.sort(key=lambda m: m.quality_score, reverse=True)

        if limit:
            matches = matches[:limit]

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

    def price_viable_matches(
        self,
        cage_id: int,
        only_viable: bool = True,
        refresh: bool = False,
        price_lookup: Optional[PriceLookup] = None,
    ) -> dict:
        """
        Look up and store vendor prices for guests in this cage's matches.

        This is the match-domain counterpart to GuestCalculator.create_guest_from_pubchem:
        both the `price lookup` CLI command and any library/script usage
        should call this rather than pulling matches apart and driving
        PriceLookup themselves, so there's one place that decides which
        guests are worth pricing for a cage.

        Args:
            cage_id: Cage ID.
            only_viable: Only price guests in matches that are viable by the
                app's default PC target -- the whole point of gating on
                viability is to avoid spending API calls on guests that are
                clearly a poor geometric fit.
            refresh: Re-query prices even for guests with a recent quote already stored.
            price_lookup: Reuse an existing PriceLookup instance (e.g. across
                several cages in one script) instead of creating a fresh one --
                avoids re-validating vendor credentials (a live network check)
                on every call.

        Returns:
            dict: {'queried': N, 'skipped': N, 'priced': N}, as returned by
            PriceLookup.lookup_and_store.

        Example:
            >>> engine = MatchingEngine()
            >>> results = engine.price_viable_matches(cage_id=1)
            >>> print(f"Priced {results['priced']} guest(s)")
        """
        logger.debug(f"Pricing matches for cage_id={cage_id}: only_viable={only_viable}, refresh={refresh}")

        matches = self.list_matches_for_cage(cage_id)
        if only_viable:
            matches = [m for m in matches if m.is_viable]

        guest_ids = list({m.guest_id for m in matches})
        if not guest_ids:
            logger.info(f"No guests to price for cage_id={cage_id}")
            return {"queried": 0, "skipped": 0, "priced": 0}

        guests = queries.get_guests_by_ids(self.conn, guest_ids)

        if price_lookup is None:
            price_lookup = PriceLookup()

        return price_lookup.lookup_and_store(self.conn, guests, refresh=refresh)

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
