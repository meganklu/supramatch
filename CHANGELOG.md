# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- PubChem lookups: fetch guest molecules by name/CAS number via `supramatch.discovery.pubchem_client` (`supramatch guest fetch <query>`).
- Vendor price lookups via ChemPrice (Mcule, Molport, Chemspace): `Price` model, `prices` table, `supramatch.discovery.price_lookup`, and new `supramatch price lookup` / `supramatch price list` commands.
- `supramatch.pipeline.run_pipeline()` and `supramatch pipeline run`: end-to-end command that resolves a cage and guests, creates matches, prices the viable ones, and returns ranked results in one call.
- Config: `MCULE_API_KEY`, `MOLPORT_API_KEY`, `CHEMSPACE_API_KEY`, `PUBCHEM_REQUEST_DELAY`, `PUBCHEM_CID_BATCH_SIZE`, `PRICE_TTL_DAYS` (see `.env.example`).
- `guests` table: `iupac_name`, `pubchem_cid`, `molecular_formula` columns.

### Changed
- `guests` table: renamed `molar_mass` to `molecular_weight`.
- `matches.quality_score` and `matches.is_viable` are no longer stored columns; both are now computed at read time (in `Match`) since quality score depends on price data that can change independently after a match is created.

### Removed
- `supramatch.modules.scraper` (`ChemicalScraper`) and the `ENABLE_SCRAPER` feature flag, superseded by ChemPrice-based vendor pricing.
- `guests` table: `price_per_gram`, `supplier`, `url` columns, superseded by the `prices` table.

## [0.1.0] - 2026-07-13

### Added
- `supramatch cage` commands: load a cage from a PDB file and calculate its cavity volume (`CageCalculator`).
- `supramatch guest` commands: load, import (from file), list, search, calculate, and delete guest molecules, with molecular volume/molar mass computed via RDKit (`GuestCalculator`).
- `supramatch match` commands: match guests to a cage by packing coefficient, with a configurable ideal/tolerance window and a computed quality score (`MatchingEngine`).
- `supramatch db` commands: initialize and manage the SQLite database (`cages`, `guests`, `matches` tables).
- Configuration via `.env` (`CAGE_GRID_SPACING`, `GUEST_RANDOM_SEED`, `PC_IDEAL_DEFAULT`, `PC_TOLERANCE_DEFAULT`, decimal-precision and cache/scraper feature flags, etc.).
- Logging to console and file, configurable via `LOG_LEVEL`/`LOG_FILE`.

[unreleased]: https://github.com/meganklu/supramatch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/meganklu/supramatch/releases/tag/v0.1.0
