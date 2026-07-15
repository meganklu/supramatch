"""Raw SQL query functions for cages, guests, matches, and prices."""

import sqlite3
from datetime import datetime
from typing import List, Optional
from supramatch.config import HG_MATCH_CONFIG
from supramatch.models.cage import Cage
from supramatch.models.guest import Guest
from supramatch.models.match import Match
from supramatch.models.price import Price


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _row_to_cage(row: sqlite3.Row) -> Cage:
    return Cage(
        id=row["id"],
        name=row["name"],
        cavity_volume=row["cavity_volume"],
        pdb_file=row["pdb_file"],
        cas_number=row["cas_number"],
        created_at=_parse_datetime(row["created_at"]),
    )


def _row_to_guest(row: sqlite3.Row) -> Guest:
    return Guest(
        id=row["id"],
        name=row["name"],
        smiles=row["smiles"],
        molecular_weight=row["molecular_weight"],
        molecular_volume=row["molecular_volume"],
        iupac_name=row["iupac_name"],
        molecular_formula=row["molecular_formula"],
        rotatable_bonds=row["rotatable_bonds"],
        pubchem_cid=row["pubchem_cid"],
        cas_number=row["cas_number"],
        physical_state=row["physical_state"],
        in_inventory=bool(row["in_inventory"]),
        created_at=_parse_datetime(row["created_at"]),
    )


def _row_to_match(row: sqlite3.Row) -> Match:
    columns = row.keys()
    return Match(
        id=row["id"],
        cage_id=row["cage_id"],
        guest_id=row["guest_id"],
        packing_coefficient=row["packing_coefficient"],
        notes=row["notes"],
        created_at=_parse_datetime(row["created_at"]),
        cage_name=row["cage_name"] if "cage_name" in columns else None,
        cage_cavity_volume=row["cage_cavity_volume"] if "cage_cavity_volume" in columns else None,
        guest_name=row["guest_name"] if "guest_name" in columns else None,
        guest_rotatable_bonds=row["guest_rotatable_bonds"] if "guest_rotatable_bonds" in columns else None,
        guest_price_per_gram=row["guest_price_per_gram"] if "guest_price_per_gram" in columns else None,
        guest_in_inventory=bool(row["guest_in_inventory"]) if "guest_in_inventory" in columns else False,
    )


def _row_to_price(row: sqlite3.Row) -> Price:
    columns = row.keys()
    return Price(
        id=row["id"],
        guest_id=row["guest_id"],
        source=row["source"],
        supplier_name=row["supplier_name"],
        purity=row["purity"],
        amount=row["amount"],
        measure=row["measure"],
        price_usd=row["price_usd"],
        usd_per_gram=row["usd_per_gram"],
        usd_per_mol=row["usd_per_mol"],
        usd_per_liter=row["usd_per_liter"],
        created_at=_parse_datetime(row["created_at"]),
        guest_name=row["guest_name"] if "guest_name" in columns else None,
    )


# ==================== CAGES ====================

def create_cage(
    conn: sqlite3.Connection,
    name: str,
    cavity_volume: float,
    pdb_file: Optional[str] = None,
    cas_number: Optional[str] = None,
) -> Cage:
    """Insert a new cage and return it."""
    cur = conn.execute(
        """
        INSERT INTO cages (name, cas_number, pdb_file, cavity_volume, created_at, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (name, cas_number, pdb_file, cavity_volume),
    )
    conn.commit()
    return get_cage_by_id(conn, cur.lastrowid)


def get_cage_by_id(conn: sqlite3.Connection, cage_id: int) -> Optional[Cage]:
    """Retrieve a cage by primary key."""
    row = conn.execute("SELECT * FROM cages WHERE id = ?", (cage_id,)).fetchone()
    return _row_to_cage(row) if row else None


def get_cage_by_name(conn: sqlite3.Connection, name: str) -> Optional[Cage]:
    """Retrieve a cage by unique name."""
    row = conn.execute("SELECT * FROM cages WHERE name = ?", (name,)).fetchone()
    return _row_to_cage(row) if row else None


def list_cages(conn: sqlite3.Connection, limit: Optional[int] = None) -> List[Cage]:
    """List all cages, optionally limited."""
    sql = "SELECT * FROM cages ORDER BY id"
    params: tuple = ()
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_cage(row) for row in rows]


def update_cage_volume(conn: sqlite3.Connection, cage_id: int, new_volume: float) -> bool:
    """Update a cage's cavity volume."""
    cur = conn.execute(
        "UPDATE cages SET cavity_volume = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_volume, cage_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_cage(conn: sqlite3.Connection, cage_id: int) -> bool:
    """Delete a cage (and its matches, via ON DELETE CASCADE)."""
    cur = conn.execute("DELETE FROM cages WHERE id = ?", (cage_id,))
    conn.commit()
    return cur.rowcount > 0


def count_cages(conn: sqlite3.Connection) -> int:
    """Count all cages."""
    return conn.execute("SELECT COUNT(*) FROM cages").fetchone()[0]


def count_matches_for_cage(conn: sqlite3.Connection, cage_id: int) -> int:
    """Count matches for a specific cage."""
    return conn.execute(
        "SELECT COUNT(*) FROM matches WHERE cage_id = ?", (cage_id,)
    ).fetchone()[0]


# ==================== GUESTS ====================

def create_guest(
    conn: sqlite3.Connection,
    name: str,
    smiles: str,
    molecular_volume: float,
    molecular_weight: Optional[float] = None,
    iupac_name: Optional[str] = None,
    molecular_formula: Optional[str] = None,
    rotatable_bonds: Optional[int] = None,
    pubchem_cid: Optional[int] = None,
    cas_number: Optional[str] = None,
    physical_state: Optional[str] = None,
) -> Guest:
    """Insert a new guest and return it."""
    cur = conn.execute(
        """
        INSERT INTO guests (
            name, iupac_name, pubchem_cid, cas_number, smiles, molecular_weight,
            molecular_volume, molecular_formula, rotatable_bonds, physical_state,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (name, iupac_name, pubchem_cid, cas_number, smiles, molecular_weight,
         molecular_volume, molecular_formula, rotatable_bonds, physical_state),
    )
    conn.commit()
    return get_guest_by_id(conn, cur.lastrowid)


def get_guest_by_id(conn: sqlite3.Connection, guest_id: int) -> Optional[Guest]:
    """Retrieve a guest by primary key."""
    row = conn.execute("SELECT * FROM guests WHERE id = ?", (guest_id,)).fetchone()
    return _row_to_guest(row) if row else None


def get_guest_by_cas(conn: sqlite3.Connection, cas_number: str) -> Optional[Guest]:
    """Retrieve a guest by CAS registry number."""
    row = conn.execute("SELECT * FROM guests WHERE cas_number = ?", (cas_number,)).fetchone()
    return _row_to_guest(row) if row else None


def get_guest_by_name(conn: sqlite3.Connection, name: str) -> Optional[Guest]:
    """Retrieve a guest by name."""
    row = conn.execute("SELECT * FROM guests WHERE name = ?", (name,)).fetchone()
    return _row_to_guest(row) if row else None


def get_guest_by_smiles(conn: sqlite3.Connection, smiles: str) -> Optional[Guest]:
    """Retrieve a guest by exact SMILES string match."""
    row = conn.execute("SELECT * FROM guests WHERE smiles = ?", (smiles,)).fetchone()
    return _row_to_guest(row) if row else None


def get_guest_by_pubchem_cid(conn: sqlite3.Connection, pubchem_cid: int) -> Optional[Guest]:
    """Retrieve a guest by the PubChem CID it was fetched from."""
    row = conn.execute("SELECT * FROM guests WHERE pubchem_cid = ?", (pubchem_cid,)).fetchone()
    return _row_to_guest(row) if row else None


def get_guests_by_ids(conn: sqlite3.Connection, guest_ids: List[int]) -> List[Guest]:
    """Retrieve multiple guests by primary key."""
    if not guest_ids:
        return []
    placeholders = ",".join("?" * len(guest_ids))
    rows = conn.execute(
        f"SELECT * FROM guests WHERE id IN ({placeholders})", guest_ids
    ).fetchall()
    return [_row_to_guest(row) for row in rows]


def search_guests(
    conn: sqlite3.Connection,
    name_pattern: Optional[str] = None,
) -> List[Guest]:
    """Search for guests by name."""
    sql = "SELECT * FROM guests WHERE 1=1"
    params: list = []

    if name_pattern:
        sql += " AND name LIKE ?"
        params.append(f"%{name_pattern}%")

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_guest(row) for row in rows]


def list_guests(conn: sqlite3.Connection, limit: Optional[int] = None, offset: int = 0) -> List[Guest]:
    """List all guests with optional pagination."""
    sql = "SELECT * FROM guests ORDER BY id LIMIT ? OFFSET ?"
    rows = conn.execute(sql, (limit if limit else -1, offset)).fetchall()
    return [_row_to_guest(row) for row in rows]


def update_guest_volume(conn: sqlite3.Connection, guest_id: int, new_volume: float) -> bool:
    """Update a guest's molecular volume."""
    cur = conn.execute(
        "UPDATE guests SET molecular_volume = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_volume, guest_id),
    )
    conn.commit()
    return cur.rowcount > 0


def update_guest_rotatable_bonds(conn: sqlite3.Connection, guest_id: int, rotatable_bonds: int) -> bool:
    """Update a guest's rotatable bond count."""
    cur = conn.execute(
        "UPDATE guests SET rotatable_bonds = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (rotatable_bonds, guest_id),
    )
    conn.commit()
    return cur.rowcount > 0


def update_guest_inventory(conn: sqlite3.Connection, guest_id: int, in_inventory: bool) -> bool:
    """Update whether a guest is currently in our physical inventory."""
    cur = conn.execute(
        "UPDATE guests SET in_inventory = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (int(in_inventory), guest_id),
    )
    conn.commit()
    return cur.rowcount > 0


def update_guest_cas(conn: sqlite3.Connection, guest_id: int, cas_number: Optional[str]) -> bool:
    """Update a guest's CAS registry number."""
    cur = conn.execute(
        "UPDATE guests SET cas_number = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (cas_number, guest_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_guest(conn: sqlite3.Connection, guest_id: int) -> bool:
    """Delete a guest (and its matches/prices, via ON DELETE CASCADE)."""
    cur = conn.execute("DELETE FROM guests WHERE id = ?", (guest_id,))
    conn.commit()
    return cur.rowcount > 0


def count_guests(conn: sqlite3.Connection) -> int:
    """Count all guests."""
    return conn.execute("SELECT COUNT(*) FROM guests").fetchone()[0]


# ==================== MATCHES ====================

# A guest's best known price per gram: prefer a directly-quoted usd_per_gram,
# falling back to usd_per_mol / molecular_weight when only a molar quote exists.
# Volume-based quotes (usd_per_liter) can't be converted without density data
# and are left out -- a guest priced only that way is treated as unpriced.
# Quotes below min_purity_pct (or with no purity reported at all, so NULL >=
# threshold is false) are excluded too -- a cheap quote can't win on price
# alone if it doesn't clear the purity bar.
_BEST_PRICE_SUBQUERY = f"""
    SELECT
        prices.guest_id AS guest_id,
        MIN(
            COALESCE(
                prices.usd_per_gram,
                CASE
                    WHEN prices.usd_per_mol IS NOT NULL AND guests.molecular_weight IS NOT NULL
                    THEN prices.usd_per_mol / guests.molecular_weight
                END
            )
        ) AS usd_per_gram
    FROM prices
    JOIN guests ON guests.id = prices.guest_id
    WHERE prices.purity >= {HG_MATCH_CONFIG["min_purity_pct"]}
    GROUP BY prices.guest_id
"""

_MATCH_SELECT = f"""
    SELECT
        matches.*,
        cages.name AS cage_name,
        cages.cavity_volume AS cage_cavity_volume,
        guests.name AS guest_name,
        guests.rotatable_bonds AS guest_rotatable_bonds,
        guests.in_inventory AS guest_in_inventory,
        best_price.usd_per_gram AS guest_price_per_gram
    FROM matches
    JOIN cages ON cages.id = matches.cage_id
    JOIN guests ON guests.id = matches.guest_id
    LEFT JOIN ({_BEST_PRICE_SUBQUERY}) AS best_price ON best_price.guest_id = matches.guest_id
"""


def create_match(
    conn: sqlite3.Connection,
    cage_id: int,
    guest_id: int,
    packing_coefficient: float,
    notes: Optional[str] = None,
) -> Match:
    """Insert a new match and return it."""
    cur = conn.execute(
        """
        INSERT INTO matches (cage_id, guest_id, packing_coefficient, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (cage_id, guest_id, packing_coefficient, notes),
    )
    conn.commit()
    return get_match(conn, cur.lastrowid)


def get_match(conn: sqlite3.Connection, match_id: int) -> Optional[Match]:
    """Retrieve a match by primary key."""
    row = conn.execute(f"{_MATCH_SELECT} WHERE matches.id = ?", (match_id,)).fetchone()
    return _row_to_match(row) if row else None


def get_match_by_cage_guest(conn: sqlite3.Connection, cage_id: int, guest_id: int) -> Optional[Match]:
    """Retrieve the match between a specific cage and guest, if any."""
    row = conn.execute(
        f"{_MATCH_SELECT} WHERE matches.cage_id = ? AND matches.guest_id = ?",
        (cage_id, guest_id),
    ).fetchone()
    return _row_to_match(row) if row else None


def list_matches_for_cage(conn: sqlite3.Connection, cage_id: int) -> List[Match]:
    """List all matches for a cage, regardless of fit or viability."""
    rows = conn.execute(f"{_MATCH_SELECT} WHERE matches.cage_id = ?", (cage_id,)).fetchall()
    return [_row_to_match(row) for row in rows]


def find_matches_for_cage(
    conn: sqlite3.Connection,
    cage_id: int,
    pc_ideal: float,
    pc_tolerance: float,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    in_inventory_only: bool = False,
) -> List[Match]:
    """
    Find matches for a cage within a packing-coefficient window and price bounds.

    Returns every matching candidate, unsorted and unlimited. Viability
    filtering and sorting (including by quality_score, which is computed
    from fields on Match rather than stored) are business-layer concerns
    handled by MatchingEngine, not this query.
    """
    sql = f"{_MATCH_SELECT} WHERE matches.cage_id = ? AND ABS(matches.packing_coefficient - ?) <= ?"
    params: list = [cage_id, pc_ideal, pc_tolerance]

    if max_price is not None:
        sql += " AND best_price.usd_per_gram <= ?"
        params.append(max_price)

    if min_price is not None:
        sql += " AND best_price.usd_per_gram >= ?"
        params.append(min_price)

    if in_inventory_only:
        sql += " AND guests.in_inventory = 1"

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_match(row) for row in rows]


def update_match_notes(conn: sqlite3.Connection, match_id: int, notes: str) -> bool:
    """Update a match's notes."""
    cur = conn.execute(
        "UPDATE matches SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (notes, match_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_match(conn: sqlite3.Connection, match_id: int) -> bool:
    """Delete a match."""
    cur = conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()
    return cur.rowcount > 0


def delete_matches_for_cage(conn: sqlite3.Connection, cage_id: int) -> int:
    """Delete all matches for a cage. Returns the number of rows deleted."""
    cur = conn.execute("DELETE FROM matches WHERE cage_id = ?", (cage_id,))
    conn.commit()
    return cur.rowcount


def count_matches(conn: sqlite3.Connection) -> int:
    """Count all matches."""
    return conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]


# ==================== PRICES ====================

_PRICE_SELECT = """
    SELECT prices.*, guests.name AS guest_name
    FROM prices
    JOIN guests ON guests.id = prices.guest_id
"""


def create_price(
    conn: sqlite3.Connection,
    guest_id: int,
    source: str,
    supplier_name: Optional[str] = None,
    purity: Optional[float] = None,
    amount: Optional[float] = None,
    measure: Optional[str] = None,
    price_usd: Optional[float] = None,
    usd_per_gram: Optional[float] = None,
    usd_per_mol: Optional[float] = None,
    usd_per_liter: Optional[float] = None,
) -> Price:
    """Insert a new vendor price quote and return it."""
    cur = conn.execute(
        """
        INSERT INTO prices (
            guest_id, source, supplier_name, purity, amount, measure,
            price_usd, usd_per_gram, usd_per_mol, usd_per_liter, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (guest_id, source, supplier_name, purity, amount, measure,
         price_usd, usd_per_gram, usd_per_mol, usd_per_liter),
    )
    conn.commit()
    return get_price(conn, cur.lastrowid)


def get_price(conn: sqlite3.Connection, price_id: int) -> Optional[Price]:
    """Retrieve a price quote by primary key."""
    row = conn.execute(f"{_PRICE_SELECT} WHERE prices.id = ?", (price_id,)).fetchone()
    return _row_to_price(row) if row else None


def count_prices(conn: sqlite3.Connection) -> int:
    """Count all stored vendor price quotes."""
    return conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]


def list_prices_for_guest(conn: sqlite3.Connection, guest_id: int) -> List[Price]:
    """List all stored price quotes for a guest, cheapest-per-gram first."""
    rows = conn.execute(
        f"{_PRICE_SELECT} WHERE prices.guest_id = ? "
        "ORDER BY prices.usd_per_gram IS NULL, prices.usd_per_gram ASC",
        (guest_id,),
    ).fetchall()
    return [_row_to_price(row) for row in rows]


def guest_has_recent_price(conn: sqlite3.Connection, guest_id: int, ttl_days: int) -> bool:
    """Check whether a guest already has a price quote newer than ttl_days."""
    row = conn.execute(
        "SELECT 1 FROM prices WHERE guest_id = ? AND created_at >= datetime('now', ?) LIMIT 1",
        (guest_id, f"-{ttl_days} days"),
    ).fetchone()
    return row is not None


def delete_prices_for_guest(conn: sqlite3.Connection, guest_id: int) -> int:
    """Delete all stored price quotes for a guest. Returns the number of rows deleted."""
    cur = conn.execute("DELETE FROM prices WHERE guest_id = ?", (guest_id,))
    conn.commit()
    return cur.rowcount
