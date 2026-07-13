"""
End-to-end pipeline: discover guests, match them to a cage, price the
viable ones, and return ranked results -- all in one call.

This is a thin composition of supramatch's building blocks (CageCalculator,
GuestCalculator, MatchingEngine) for the common case of running the whole
workflow from a script or notebook instead of driving each CLI command by
hand. Nothing here can't be done by calling those classes yourself; this
just saves wiring them together every time.
"""

import logging
from typing import List, Optional
from supramatch.db.database import init_db
from supramatch.modules.cage_calc import CageCalculator
from supramatch.modules.guest_calc import GuestCalculator
from supramatch.modules.matcher import MatchingEngine
from supramatch.models.match import Match

logger = logging.getLogger(__name__)


def run_pipeline(
    cage_pdb_file: Optional[str] = None,
    cage_id: Optional[int] = None,
    cage_name: Optional[str] = None,
    guest_queries: Optional[List[str]] = None,
    guest_ids: Optional[List[int]] = None,
    price_only_viable: bool = True,
    refresh_prices: bool = False,
    pc_ideal: Optional[float] = None,
    pc_tolerance: Optional[float] = None,
    sort_by: str = "quality_score",
    limit: Optional[int] = None,
) -> List[Match]:
    """
    Run the full pipeline: resolve a cage and guests, create matches between
    them, look up vendor prices for the viable ones, and return ranked matches.

    Args:
        cage_pdb_file: Path to a cage PDB file to load (mutually exclusive
            with cage_id -- provide exactly one).
        cage_id: An already-loaded cage's ID (mutually exclusive with cage_pdb_file).
        cage_name: Optional name for a newly-loaded cage (ignored if cage_id is given).
        guest_queries: PubChem names/CAS numbers to fetch and create as guests.
        guest_ids: Already-loaded guests' IDs to include alongside/instead of guest_queries.
        price_only_viable: Only look up prices for guests in matches that are
            viable by the app's default PC target (saves API calls on poor fits).
            Independent of pc_ideal/pc_tolerance below -- see match_guests_to_cage's
            docstring for why those aren't the same knob.
        refresh_prices: Re-query prices even for guests with a recent quote already stored.
        pc_ideal: Packing-coefficient search window center for the *returned*
            matches (defaults to the app's standard PC target if not given).
            Widen this if you priced guests via price_only_viable=False and
            want them to actually show up in the results -- pricing scope and
            the results window are independent, so a guest priced despite a
            poor fit still won't appear here unless the window covers it too.
        pc_tolerance: Packing-coefficient search window width for the returned matches.
        sort_by: How to rank the returned matches: 'quality_score' (default),
            'packing_coefficient', or 'price'.
        limit: Maximum number of matches to return.

    Returns:
        list[Match]: Ranked matches for the cage.

    Raises:
        ValueError: If neither/both of cage_pdb_file and cage_id are given,
            or if no guests could be resolved from guest_queries/guest_ids.

    Example:
        >>> from supramatch.pipeline import run_pipeline
        >>> matches = run_pipeline(
        ...     cage_pdb_file="data/cages/my_cage.pdb",
        ...     guest_queries=["aspirin", "ibuprofen", "caffeine"],
        ...     limit=10,
        ... )
        >>> for m in matches:
        ...     print(f"{m.guest_name}: quality={m.quality_score:.1f}")
    """
    if bool(cage_pdb_file) == bool(cage_id):
        raise ValueError("Provide exactly one of cage_pdb_file or cage_id")

    init_db()
    cage_calc = CageCalculator()
    guest_calc = GuestCalculator()
    matcher = MatchingEngine()

    try:
        # 1. Resolve the cage
        if cage_id is not None:
            cage = cage_calc.get_cage(cage_id=cage_id)
            if not cage:
                raise ValueError(f"Cage with ID {cage_id} not found")
        else:
            cage = cage_calc.create_cage(cage_pdb_file, cage_name=cage_name)

        # 2. Resolve guests (existing IDs plus/instead of freshly-fetched ones)
        guests = []
        for guest_id in (guest_ids or []):
            guest = guest_calc.get_guest(guest_id=guest_id)
            if guest:
                guests.append(guest)
            else:
                logger.warning(f"Guest ID {guest_id} not found, skipping")

        for query in (guest_queries or []):
            try:
                guests.append(guest_calc.create_guest_from_pubchem(query))
            except ValueError as e:
                logger.warning(f"Skipping guest query '{query}': {e}")

        if not guests:
            raise ValueError("No guests resolved from guest_ids/guest_queries")

        # 3. Create matches from geometry alone
        matcher.batch_create_matches(cage.id, [g.id for g in guests])

        # 4. Price the guests worth pricing (gated on viability by MatchingEngine)
        results = matcher.price_viable_matches(
            cage.id, only_viable=price_only_viable, refresh=refresh_prices
        )
        logger.info(
            f"Pricing: {results['priced']} priced, {results['skipped']} skipped, {results['queried']} queried"
        )

        # 5. Return ranked matches
        return matcher.match_guests_to_cage(
            cage.id, pc_ideal=pc_ideal, pc_tolerance=pc_tolerance, sort_by=sort_by, limit=limit
        )

    finally:
        matcher.close()
