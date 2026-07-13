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
- CAS numbers aren't a PUG REST `property` -- they come from the `xrefs/RN`
  endpoint, which returns a CID's full "registry numbers" list. That list
  mixes CAS numbers together with EC/EINECS numbers and isn't marked with
  which entry is "the" CAS number, so this client picks one out itself:
    - EC numbers always have the shape NNN-NNN-N (3 digits, 3 digits, 1
      check digit); CAS numbers are 2-7 digits, then exactly *2* digits,
      then 1 check digit. The middle segment's digit count (3 vs 2) is what
      tells them apart -- a CAS number's first segment can coincidentally
      also be 3 digits, so segment *count* alone isn't enough.
    - Among the remaining CAS-shaped candidates, the one with the smallest
      leading number is used: PubChem lists a compound's original/primary
      CAS registration alongside later alternate-salt-or-source
      registrations, and the original registration consistently has the
      smallest number. Verified live against aspirin (CID 2244 -> 50-78-2
      out of 6 CAS-shaped candidates), caffeine (CID 2519 -> 58-08-2 out of
      8), and acetaminophen (CID 1983 -> 103-90-2 out of 10), each picked
      correctly.
  Like property batching, `xrefs/RN` accepts a comma-separated CID list in
  one request, and a nonexistent CID doesn't break the batch -- it just
  comes back with no `RN` key for that entry.
"""

import re
import time
import logging
from typing import Dict, List, Optional
from urllib.parse import quote
import requests
from supramatch.config import PUBCHEM_CONFIG

logger = logging.getLogger(__name__)

PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PROPERTIES = ["Title", "IUPACName", "SMILES", "MolecularWeight", "MolecularFormula"]
_CAS_PATTERN = re.compile(r"^(\d{2,7})-\d{2}-\d$")


def resolve_to_cid(identifier: str) -> Optional[int]:
    """
    Resolve a compound name or CAS number to a PubChem CID.

    Args:
        identifier: Compound name or CAS registry number.

    Returns:
        int: The first matching CID, or None if not found.
    """
    url = f"{PUG_BASE}/compound/name/{quote(identifier, safe='')}/cids/JSON"
    try:
        response = requests.get(url, timeout=10)
    except requests.exceptions.RequestException as e:
        logger.error(f"PubChem request failed for '{identifier}': {e}")
        return None

    if response.status_code != 200:
        logger.warning(f"PubChem could not resolve '{identifier}': HTTP {response.status_code}")
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


def fetch_cas_numbers_by_cid(cids: List[int]) -> Dict[int, Optional[str]]:
    """
    Fetch a best-guess CAS registry number for a batch of CIDs.

    Requests are chunked to PUBCHEM_CONFIG's batch size, same as
    `fetch_properties_by_cid`. A bad/nonexistent CID doesn't break its
    chunk -- it just comes back with no `RN` key for that entry, which
    resolves to None below. See the module docstring for how a single CAS
    number is picked out of PubChem's mixed CAS/EC registry-numbers list.

    Args:
        cids: PubChem CIDs to fetch CAS numbers for.

    Returns:
        dict: Maps each input CID to its picked CAS number, or None if it
        has no CAS-shaped registry number.
    """
    if not cids:
        return {}

    chunk_size = PUBCHEM_CONFIG["cid_batch_size"]
    delay = PUBCHEM_CONFIG["request_delay_seconds"]
    results: Dict[int, Optional[str]] = {}

    for start in range(0, len(cids), chunk_size):
        chunk = cids[start:start + chunk_size]
        cid_list = ",".join(str(c) for c in chunk)
        url = f"{PUG_BASE}/compound/cid/{cid_list}/xrefs/RN/JSON"

        try:
            response = requests.get(url, timeout=30)
        except requests.exceptions.RequestException as e:
            logger.error(f"PubChem CAS lookup failed for chunk starting at {start}: {e}")
            continue

        if response.status_code != 200:
            logger.error(f"PubChem CAS lookup failed for chunk starting at {start}: HTTP {response.status_code}")
            continue

        for entry in response.json().get("InformationList", {}).get("Information", []):
            results[entry["CID"]] = _pick_cas_number(entry.get("RN", []))

        if start + chunk_size < len(cids):
            time.sleep(delay)

    return results


def _pick_cas_number(registry_numbers: List[str]) -> Optional[str]:
    """Pick the likeliest CAS number out of a CID's mixed CAS/EC registry-numbers list."""
    candidates = []
    for rn in registry_numbers:
        match = _CAS_PATTERN.match(rn)
        if match:
            candidates.append((int(match.group(1)), rn))

    if not candidates:
        return None
    return min(candidates, key=lambda c: c[0])[1]


def fetch_compound(query: str) -> Optional[dict]:
    """
    Resolve a single compound name/CAS number and fetch its properties.

    Args:
        query: Compound name or CAS registry number.

    Returns:
        dict: {cid, name, iupac_name, smiles, molecular_weight, formula,
        cas_number}, where `name` prefers PubChem's Title, falling back to
        IUPACName, falling back to the original query. `cas_number` is
        PubChem's picked CAS registry number (see module docstring), or
        None if the compound has none on file. Returns None if the compound
        could not be resolved or has no usable SMILES.
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
    cas_number = fetch_cas_numbers_by_cid([cid]).get(cid)
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
