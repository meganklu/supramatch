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

# name is the friendly/common name (PubChem's "Title" when fetched, or
# user-supplied otherwise); iupac_name is the formal name, populated only
# when available (e.g. from PubChem).
CREATE_GUESTS_TABLE = """
    CREATE TABLE IF NOT EXISTS guests (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        name                TEXT NOT NULL,
        iupac_name          TEXT,
        pubchem_cid         INTEGER,
        cas_number          TEXT UNIQUE,
        smiles              TEXT NOT NULL,
        molecular_weight    REAL,
        molecular_volume    REAL,
        molecular_formula   TEXT,
        physical_state      TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

# Packing coefficient is the only geometric fact stored for a match; whether
# it's "viable" and what its quality_score is are computed at read time
# (see models.match.Match) since quality_score depends on price data in the
# `prices` table that can change independently after the match is created.
CREATE_MATCHES_TABLE = """
    CREATE TABLE IF NOT EXISTS matches (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        cage_id             INTEGER NOT NULL REFERENCES cages(id) ON DELETE CASCADE,
        guest_id            INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
        packing_coefficient REAL NOT NULL,
        notes               TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(cage_id, guest_id)
    )
"""

# One row per vendor quote (a guest can have several, from Mcule/Molport/Chemspace via
# ChemPrice); usd_per_gram/usd_per_mol/usd_per_liter are ChemPrice's own
# standardized ratios, stored as returned rather than recomputed here.
CREATE_PRICES_TABLE = """
    CREATE TABLE IF NOT EXISTS prices (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_id        INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
        source          TEXT NOT NULL,
        supplier_name   TEXT,
        purity          REAL,
        amount          REAL,
        measure         TEXT,
        price_usd       REAL,
        usd_per_gram    REAL,
        usd_per_mol     REAL,
        usd_per_liter   REAL,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cage_name ON cages(name)",
    "CREATE INDEX IF NOT EXISTS idx_cage_cas ON cages(cas_number)",
    "CREATE INDEX IF NOT EXISTS idx_guest_cas ON guests(cas_number)",
    "CREATE INDEX IF NOT EXISTS idx_match_cage ON matches(cage_id)",
    "CREATE INDEX IF NOT EXISTS idx_match_guest ON matches(guest_id)",
    "CREATE INDEX IF NOT EXISTS idx_match_pc ON matches(packing_coefficient)",
    "CREATE INDEX IF NOT EXISTS idx_price_guest ON prices(guest_id)",
    "CREATE INDEX IF NOT EXISTS idx_price_usd_per_gram ON prices(usd_per_gram)",
    "CREATE INDEX IF NOT EXISTS idx_price_created_at ON prices(created_at)",
]

ALL_TABLES = [
    CREATE_CAGES_TABLE,
    CREATE_GUESTS_TABLE,
    CREATE_MATCHES_TABLE,
    CREATE_PRICES_TABLE,
]
