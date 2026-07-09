"""Raw SQL query functions for cages, guests, and matches."""

import sqlite3
from datetime import datetime
from typing import List, Optional
from supramatch.models.cage import Cage
from supramatch.models.guest import Guest
from supramatch.models.match import Match


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
        molar_mass=row["molar_mass"],
        molecular_volume=row["molecular_volume"],
        cas_number=row["cas_number"],
        price_per_gram=row["price_per_gram"],
        supplier=row["supplier"],
        physical_state=row["physical_state"],
        url=row["url"],
        created_at=_parse_datetime(row["created_at"]),
    )


def _row_to_match(row: sqlite3.Row) -> Match:
    columns = row.keys()
    return Match(
        id=row["id"],
        cage_id=row["cage_id"],
        guest_id=row["guest_id"],
        packing_coefficient=row["packing_coefficient"],
        quality_score=row["quality_score"],
        is_viable=bool(row["is_viable"]),
        notes=row["notes"],
        created_at=_parse_datetime(row["created_at"]),
        cage_name=row["cage_name"] if "cage_name" in columns else None,
        cage_cavity_volume=row["cage_cavity_volume"] if "cage_cavity_volume" in columns else None,
        guest_name=row["guest_name"] if "guest_name" in columns else None,
        guest_price_per_gram=row["guest_price_per_gram"] if "guest_price_per_gram" in columns else None,
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
    molar_mass: Optional[float] = None,
    cas_number: Optional[str] = None,
    supplier: Optional[str] = None,
    price_per_gram: Optional[float] = None,
    physical_state: Optional[str] = None,
    url: Optional[str] = None,
) -> Guest:
    """Insert a new guest and return it."""
    cur = conn.execute(
        """
        INSERT INTO guests (
            name, cas_number, smiles, molar_mass, molecular_volume,
            price_per_gram, supplier, physical_state, url, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (name, cas_number, smiles, molar_mass, molecular_volume,
         price_per_gram, supplier, physical_state, url),
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
    supplier: Optional[str] = None,
) -> List[Guest]:
    """Search for guests with flexible criteria."""
    sql = "SELECT * FROM guests WHERE 1=1"
    params: list = []

    if name_pattern:
        sql += " AND name LIKE ?"
        params.append(f"%{name_pattern}%")

    if supplier:
        sql += " AND supplier = ?"
        params.append(supplier)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_guest(row) for row in rows]


def list_guests(conn: sqlite3.Connection, limit: Optional[int] = None, offset: int = 0) -> List[Guest]:
    """List all guests with optional pagination."""
    sql = "SELECT * FROM guests ORDER BY id LIMIT ? OFFSET ?"
    rows = conn.execute(sql, (limit if limit else -1, offset)).fetchall()
    return [_row_to_guest(row) for row in rows]


def update_guest_price(conn: sqlite3.Connection, guest_id: int, new_price_per_gram: float) -> bool:
    """Update a guest's price per gram."""
    cur = conn.execute(
        "UPDATE guests SET price_per_gram = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_price_per_gram, guest_id),
    )
    conn.commit()
    return cur.rowcount > 0


def update_guest_url(conn: sqlite3.Connection, guest_id: int, url: str) -> bool:
    """Update a guest's supplier URL."""
    cur = conn.execute(
        "UPDATE guests SET url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (url, guest_id),
    )
    conn.commit()
    return cur.rowcount > 0


def update_guest_volume(conn: sqlite3.Connection, guest_id: int, new_volume: float) -> bool:
    """Update a guest's molecular volume."""
    cur = conn.execute(
        "UPDATE guests SET molecular_volume = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_volume, guest_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_guest(conn: sqlite3.Connection, guest_id: int) -> bool:
    """Delete a guest (and its matches, via ON DELETE CASCADE)."""
    cur = conn.execute("DELETE FROM guests WHERE id = ?", (guest_id,))
    conn.commit()
    return cur.rowcount > 0


def count_guests(conn: sqlite3.Connection) -> int:
    """Count all guests."""
    return conn.execute("SELECT COUNT(*) FROM guests").fetchone()[0]


# ==================== MATCHES ====================

_MATCH_SELECT = """
    SELECT
        matches.*,
        cages.name AS cage_name,
        cages.cavity_volume AS cage_cavity_volume,
        guests.name AS guest_name,
        guests.price_per_gram AS guest_price_per_gram
    FROM matches
    JOIN cages ON cages.id = matches.cage_id
    JOIN guests ON guests.id = matches.guest_id
"""


def create_match(
    conn: sqlite3.Connection,
    cage_id: int,
    guest_id: int,
    packing_coefficient: float,
    quality_score: float,
    is_viable: bool = True,
    notes: Optional[str] = None,
) -> Match:
    """Insert a new match and return it."""
    cur = conn.execute(
        """
        INSERT INTO matches (
            cage_id, guest_id, packing_coefficient, quality_score, is_viable, notes,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (cage_id, guest_id, packing_coefficient, quality_score, int(is_viable), notes),
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
    only_viable: bool = True,
    sort_by: str = "quality_score",
    limit: Optional[int] = None,
) -> List[Match]:
    """Find matches for a cage filtered by packing coefficient range, price, and viability."""
    sql = f"{_MATCH_SELECT} WHERE matches.cage_id = ? AND ABS(matches.packing_coefficient - ?) <= ?"
    params: list = [cage_id, pc_ideal, pc_tolerance]

    if only_viable:
        sql += " AND matches.is_viable = 1"

    if max_price is not None:
        sql += " AND guests.price_per_gram <= ?"
        params.append(max_price)

    if min_price is not None:
        sql += " AND guests.price_per_gram >= ?"
        params.append(min_price)

    if sort_by == "packing_coefficient":
        sql += " ORDER BY ABS(matches.packing_coefficient - ?) ASC"
        params.append(pc_ideal)
    elif sort_by == "price":
        # NULL prices sort last, then ascending
        sql += " ORDER BY guests.price_per_gram IS NULL, guests.price_per_gram ASC"
    else:
        sql += " ORDER BY matches.quality_score DESC"

    if limit:
        sql += " LIMIT ?"
        params.append(limit)

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
