"""Database schema definitions."""

CREATE_CAGES_TABLE = """
    CREATE TABLE IF NOT EXISTS cages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT UNIQUE NOT NULL,
        cas_number      TEXT UNIQUE,
        pdb_file        TEXT,
        cavity_volume   REAL,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_GUESTS_TABLE = """
    CREATE TABLE IF NOT EXISTS guests (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        name                TEXT NOT NULL,
        cas_number          TEXT UNIQUE,
        smiles              TEXT NOT NULL,
        molar_mass          REAL,
        molecular_volume    REAL,
        price_per_gram      REAL,
        supplier            TEXT,
        physical_state      TEXT,
        url                 TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_MATCHES_TABLE = """
    CREATE TABLE IF NOT EXISTS matches (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        cage_id             INTEGER NOT NULL REFERENCES cages(id) ON DELETE CASCADE,
        guest_id            INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
        packing_coefficient REAL NOT NULL,
        quality_score       REAL NOT NULL,
        is_viable           INTEGER DEFAULT 1,
        notes               TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(cage_id, guest_id)
    )
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cage_name ON cages(name)",
    "CREATE INDEX IF NOT EXISTS idx_cage_cas ON cages(cas_number)",
    "CREATE INDEX IF NOT EXISTS idx_guest_cas ON guests(cas_number)",
    "CREATE INDEX IF NOT EXISTS idx_guest_supplier ON guests(supplier)",
    "CREATE INDEX IF NOT EXISTS idx_guest_price_per_gram ON guests(price_per_gram)",
    "CREATE INDEX IF NOT EXISTS idx_match_cage ON matches(cage_id)",
    "CREATE INDEX IF NOT EXISTS idx_match_guest ON matches(guest_id)",
    "CREATE INDEX IF NOT EXISTS idx_match_pc ON matches(packing_coefficient)",
    "CREATE INDEX IF NOT EXISTS idx_match_quality ON matches(quality_score)",
    "CREATE INDEX IF NOT EXISTS idx_match_viable ON matches(is_viable)",
]

ALL_TABLES = [
    CREATE_CAGES_TABLE,
    CREATE_GUESTS_TABLE,
    CREATE_MATCHES_TABLE,
]
