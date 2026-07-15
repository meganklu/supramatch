"""
PubChem PUG REST client for compound discovery.

Grounded against the live API (not just docs) while designing this:

- Name/CAS -> CID resolution can't be batched: a comma-separated list of
  names in a single request fails outright (PUGREST.NotFound) even when
  every individual name is valid, so each identifier needs its own request,
  paced to stay within PubChem's rate limits.
- CID -> properties *can* be batched: a comma-separated CID list in one
  request works, and a bad/nonexistent CID doesn't break the batch -- it
  just comes back with an otherwise-empty row for that CID.
- `CanonicalSMILES`/`IsomericSMILES` are stale property names; the current
  API returns `SMILES` (isomeric) and `ConnectivitySMILES` (connectivity-only)
  instead. This client requests `SMILES`.
- `Title` is PubChem's friendly/common display name (e.g. "Aspirin"), distinct
  from `IUPACName` (e.g. "2-acetyloxybenzoic acid") -- used as the preferred
  guest name, with IUPACName and the original query as fallbacks.
- Physical state and density are deliberately NOT fetched here: both only
  exist as free-text in PubChem's curated "Experimental Properties" (not a
  standard PUG REST property), have thin coverage, and can be actively
  misleading (e.g. methane's physical-description data includes a "Liquid"
  entry referring to its cryogenic storage form, not its state at room
  temperature). Possible false-confidence risk.
- CAS numbers aren't a PUG REST `property`, and PubChem has no endpoint that
  returns "the" CAS number for a CID: `xrefs/RN` returns a CID's full
  registry-numbers list, mixing CAS numbers together with EC/EINECS numbers
  with no marker for which entry is "the" CAS number. An earlier version of
  this client guessed one out (smallest CAS-shaped number in the list), but
  that heuristic picked the wrong registration often enough in practice to
  be untrustworthy. So this client no longer guesses: `cas_number` is only
  populated when the caller's own query was itself CAS-shaped (see
  `supramatch.utils.helpers.is_cas_shaped`), in which case that exact input
  is used verbatim -- a name-based lookup (e.g. "aspirin") always comes back
  with `cas_number` None.
- A CAS number resolving to nothing via `compound/name` doesn't necessarily
  mean PubChem has no record of it: PubChem's name/synonym index doesn't
  always include a compound's CAS number even when its registry-numbers
  (`xref/RN`) index does. Verified live: CAS 1066-27-9 404s via
  `compound/name/1066-27-9/cids/JSON` but resolves via
  `compound/xref/RN/1066-27-9/cids/JSON`. So `resolve_to_cid` falls back to
  an `xref/RN` lookup for CAS-shaped identifiers the name endpoint misses,
  before concluding the identifier is genuinely unresolvable (as opposed to
  just a wrong/nonexistent CAS number, e.g. a transcription error).
"""

import time
import logging
from typing import Dict, List, Optional
from urllib.parse import quote
import requests
from supramatch.config import PUBCHEM_CONFIG
from supramatch.utils.helpers import is_cas_shaped

logger = logging.getLogger(__name__)

PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PROPERTIES = ["Title", "IUPACName", "SMILES", "MolecularWeight", "MolecularFormula"]


def resolve_to_cid(identifier: str) -> Optional[int]:
    """
    Resolve a compound name or CAS number to a PubChem CID.

    Tries PubChem's name/synonym search first. If that finds nothing and
    `identifier` is CAS-shaped, falls back to the xref/RN (registry number)
    lookup, since PubChem's name index doesn't always include a compound's
    CAS number even when its registry-numbers index does (see module
    docstring).

    Args:
        identifier: Compound name or CAS registry number.

    Returns:
        int: The first matching CID, or None if not found by either method.
    """
    cid = _get_cid(f"{PUG_BASE}/compound/name/{quote(identifier, safe='')}/cids/JSON", identifier)
    if cid is not None:
        return cid

    if is_cas_shaped(identifier):
        cid = _get_cid(f"{PUG_BASE}/compound/xref/RN/{quote(identifier, safe='')}/cids/JSON", identifier)
        if cid is not None:
            return cid

    logger.warning(f"PubChem could not resolve '{identifier}' by name or registry number")
    return None


def _get_cid(url: str, identifier: str) -> Optional[int]:
    """Fetch a single CID from a PUG REST `.../cids/JSON` endpoint, or None on any failure."""
    try:
        response = requests.get(url, timeout=10)
    except requests.exceptions.RequestException as e:
        logger.error(f"PubChem request failed for '{identifier}': {e}")
        return None

    if response.status_code != 200:
        return None

    cids = response.json().get("IdentifierList", {}).get("CID", [])
    return cids[0] if cids else None


def resolve_many_to_cids(identifiers: List[str]) -> Dict[str, Optional[int]]:
    """
    Resolve multiple names/CAS numbers to CIDs.

    One request per identifier, paced by PUBCHEM_CONFIG's request delay,
    since name-based lookups can't be batched (see module docstring).

    Args:
        identifiers: Compound names or CAS registry numbers.

    Returns:
        dict: Maps each input identifier to its resolved CID, or None if not found.
    """
    delay = PUBCHEM_CONFIG["request_delay_seconds"]
    results: Dict[str, Optional[int]] = {}
    for i, identifier in enumerate(identifiers):
        results[identifier] = resolve_to_cid(identifier)
        if i < len(identifiers) - 1:
            time.sleep(delay)
    return results


def fetch_properties_by_cid(cids: List[int]) -> List[dict]:
    """
    Fetch compound properties for a batch of CIDs.

    Requests are chunked to PUBCHEM_CONFIG's batch size. A bad/nonexistent
    CID doesn't break its chunk -- it just comes back with an otherwise-empty
    entry for that CID.

    Args:
        cids: PubChem CIDs to fetch properties for.

    Returns:
        list[dict]: One entry per CID (as returned by PubChem's PropertyTable).
    """
    if not cids:
        return []

    chunk_size = PUBCHEM_CONFIG["cid_batch_size"]
    delay = PUBCHEM_CONFIG["request_delay_seconds"]
    results: List[dict] = []

    for start in range(0, len(cids), chunk_size):
        chunk = cids[start:start + chunk_size]
        cid_list = ",".join(str(c) for c in chunk)
        url = f"{PUG_BASE}/compound/cid/{cid_list}/property/{','.join(_PROPERTIES)}/JSON"

        try:
            response = requests.get(url, timeout=30)
        except requests.exceptions.RequestException as e:
            logger.error(f"PubChem property fetch failed for chunk starting at {start}: {e}")
            continue

        if response.status_code != 200:
            logger.error(f"PubChem property fetch failed for chunk starting at {start}: HTTP {response.status_code}")
            continue

        results.extend(response.json().get("PropertyTable", {}).get("Properties", []))

        if start + chunk_size < len(cids):
            time.sleep(delay)

    return results


def fetch_compound(query: str) -> Optional[dict]:
    """
    Resolve a single compound name/CAS number and fetch its properties.

    Args:
        query: Compound name or CAS registry number.

    Returns:
        dict: {cid, name, iupac_name, smiles, molecular_weight, formula,
        cas_number}, where `name` prefers PubChem's Title, falling back to
        IUPACName, falling back to the original query. `cas_number` is the
        query itself if it was CAS-shaped, otherwise None -- PubChem has no
        reliable way to derive a CAS number from a name-based lookup (see
        module docstring). Returns None if the compound could not be
        resolved or has no usable SMILES.
    """
    cid = resolve_to_cid(query)
    if cid is None:
        logger.warning(f"Could not resolve '{query}' to a PubChem CID")
        return None

    properties = fetch_properties_by_cid([cid])
    if not properties or "SMILES" not in properties[0]:
        logger.warning(f"No usable properties returned for '{query}' (CID {cid})")
        return None

    prop = properties[0]
    iupac_name = prop.get("IUPACName")
    title = prop.get("Title")
    stripped_query = query.strip()
    cas_number = stripped_query if is_cas_shaped(stripped_query) else None
    return {
        "cid": cid,
        "name": title or iupac_name or query,
        "iupac_name": iupac_name,
        "smiles": prop.get("SMILES"),
        "molecular_weight": _to_float(prop.get("MolecularWeight")),
        "formula": prop.get("MolecularFormula"),
        "cas_number": cas_number,
    }


def _to_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
