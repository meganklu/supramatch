"""
Vendor price lookups via ChemPrice (mcule, molport).

Grounded against meganklu/ChemPrice@9eda518 (our fork -- see
requirements.txt), and against live runs, while designing this:

- PriceCollector.check() must be called once before querying -- it's what
  actually validates credentials against each vendor (and sets the
  *_api_key_valid flags collect() reads); skipping it makes lookups
  silently return nothing, with no error.
- All vendors are queried together via PriceCollector.collect(), which
  auto-detects which vendors have a valid key (from check()) and fetches
  all of them in one merged call. Earlier versions of this module fetched
  them separately to protect against MCule's old rate-limit-hungry iQuote
  flow (~15-30 requests per fetch); the current fork's MCule integration
  is a single batched POST /compounds/ call that self-throttles internally
  to stay under MCule's burst limit, so that workaround is no longer
  needed here.
- .selectBest(df), chemprice's "filter to the cheapest row per SMILES per
  unit" step, is skipped in favor of calling
  chemprice.utils.add_standardized_columns() directly -- the part of
  chemprice that does the unit-ratio math (USD/g, USD/mol, USD/l) without
  also filtering rows. Every standardized quote gets stored rather than
  pre-filtering to "the cheapest" here; supramatch.db.queries' best-price
  subquery already picks the cheapest at read time, so storing everything
  is both safer and more informative (keeps full vendor quote history
  instead of a filtered subset). This is a storage-design choice, not a
  workaround -- selectBest() itself is fine to use as of the pandas fix.
- The result only echoes back "Input SMILES" (what we sent), not any guest
  ID, so results have to be joined back to guests by SMILES.
- MolPort/MCule/Chemspace searches are exact-structure matches (MolPort's v1 API via
  match_types=["exact"], MCule's /search/exact/), including isotope labels
  and stereochemistry. A guest whose SMILES carries an isotope label (e.g. a
  deuterium `[2H]`) can come back with zero vendor hits even when the
  unlabeled parent compound is widely available commercially -- confirmed
  live: `[2H]C1CCC[C@H]2[C@@H]1CCCC2` (labeled cis-decalin) found nothing,
  while `C1CCC2CCCCC2C1` (plain cis-decalin) matched immediately. This
  module deliberately does not normalize isotope labels away -- a guest's
  SMILES is its real chemical identity (isotope labeling can be intentional,
  e.g. for NMR studies), so silently substituting a different compound just
  to find a price would misrepresent what was actually priced.
"""

import logging
import math
from typing import Dict, List, Optional
from chemprice import PriceCollector
from chemprice import utils as chemprice_utils
from supramatch.db import queries
from supramatch.config import PRICE_CONFIG
from supramatch.models.guest import Guest

logger = logging.getLogger(__name__)


class PriceLookup:
    """Looks up and stores vendor price quotes for guests via ChemPrice."""

    def __init__(self):
        self.collector = PriceCollector()

        if PRICE_CONFIG["mcule_api_key"]:
            self.collector.setMCuleApiKey(PRICE_CONFIG["mcule_api_key"])
        if PRICE_CONFIG["molport_api_key"]:
            self.collector.setMolportApiKey(PRICE_CONFIG["molport_api_key"])
        if PRICE_CONFIG["chemspace_api_key"]:
            self.collector.setChemSpaceApiKey(PRICE_CONFIG["chemspace_api_key"])

        if not PRICE_CONFIG["mcule_api_key"] and not PRICE_CONFIG["molport_api_key"] and not PRICE_CONFIG["chemspace_api_key"]:
            logger.warning(
                "No MCULE_API_KEY, MOLPORT_API_KEY, or CHEMSPACE_API_KEY configured -- price lookups will find nothing"
            )

        self._checked = False

    def _ensure_checked(self) -> None:
        """Validate configured credentials once per PriceLookup instance."""
        if not self._checked:
            self.collector.check(Molport=True, ChemSpace=True, MCule=True)
            self._checked = True

    def lookup_and_store(
        self,
        conn,
        guests: List[Guest],
        ttl_days: Optional[int] = None,
        refresh: bool = False,
    ) -> dict:
        """
        Look up vendor prices for the given guests and store the results.

        Args:
            conn: sqlite3 connection.
            guests: Guest objects to look up prices for.
            ttl_days: Skip a guest if it already has a price quote newer than
                this many days (defaults to PRICE_CONFIG's ttl_days).
            refresh: If True, look up every guest regardless of existing recent prices.

        Returns:
            dict: {'queried': N, 'skipped': N, 'priced': N}
        """
        if ttl_days is None:
            ttl_days = PRICE_CONFIG["ttl_days"]

        targets = []
        skipped = 0
        for guest in guests:
            if not refresh and queries.guest_has_recent_price(conn, guest.id, ttl_days):
                skipped += 1
                continue
            targets.append(guest)

        if not targets:
            return {"queried": 0, "skipped": skipped, "priced": 0}

        self._ensure_checked()

        # A guest's SMILES is the only thing ChemPrice echoes back, so keep
        # a reverse map to attribute results to guest(s) after the fact.
        smiles_to_guests: Dict[str, List[Guest]] = {}
        for guest in targets:
            smiles_to_guests.setdefault(guest.smiles, []).append(guest)

        smiles_list = list(smiles_to_guests.keys())
        logger.info(f"Querying ChemPrice for {len(smiles_list)} guest(s)")

        try:
            # collect() queries every vendor check() found a valid key for
            # (MolPort, MCule, and Chemspace) in one call and returns them already merged.
            raw = self.collector.collect(smiles_list)
        except Exception as e:
            logger.error(f"ChemPrice lookup failed: {e}", exc_info=True)
            return {"queried": len(targets), "skipped": skipped, "priced": 0}

        try:
            standardized = chemprice_utils.add_standardized_columns(raw)
        except Exception as e:
            logger.error(f"Failed to standardize ChemPrice results: {e}", exc_info=True)
            return {"queried": len(targets), "skipped": skipped, "priced": 0}

        priced_guest_ids = set()
        for _, row in standardized.iterrows():
            matching_guests = smiles_to_guests.get(row.get("Input SMILES"), [])
            price_usd = _to_float(row.get("Price_USD"))
            usd_per_gram = _to_float(row.get("USD/g"))
            usd_per_mol = _to_float(row.get("USD/mol"))
            usd_per_liter = _to_float(row.get("USD/l"))

            # A row with no price at all in any form isn't worth storing.
            if price_usd is None and usd_per_gram is None and usd_per_mol is None and usd_per_liter is None:
                continue

            for guest in matching_guests:
                queries.create_price(
                    conn,
                    guest_id=guest.id,
                    source=_clean_str(row.get("Source")) or "unknown",
                    supplier_name=_clean_str(row.get("Supplier Name")),
                    purity=_to_float(row.get("Purity")),
                    amount=_to_float(row.get("Amount")),
                    measure=_clean_str(row.get("Measure")),
                    price_usd=price_usd,
                    usd_per_gram=usd_per_gram,
                    usd_per_mol=usd_per_mol,
                    usd_per_liter=usd_per_liter,
                )
                priced_guest_ids.add(guest.id)

        logger.info(f"Stored prices for {len(priced_guest_ids)} of {len(targets)} queried guest(s)")
        return {
            "queried": len(targets),
            "skipped": skipped,
            "priced": len(priced_guest_ids),
        }


def _to_float(value) -> Optional[float]:
    """ChemPrice's dataframes coerce many columns to str, including NaN -> 'nan'."""
    if value in (None, "", "nan"):
        return None
    try:
        f = float(value)
        return f if not math.isnan(f) else None
    except (TypeError, ValueError):
        return None


def _clean_str(value) -> Optional[str]:
    if value in (None, "", "nan"):
        return None
    return str(value)
