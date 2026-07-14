# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-14

### Added
- `guests` table: `rotatable_bonds` column, computed via RDKit (`Descriptors.NumRotatableBonds`) at guest creation time (`GuestCalculator.calculate_rotatable_bonds`) and displayed as "NRB" in `guest`/`match` CLI output.
- `GuestCalculator.recalculate_rotatable_bonds()`: recompute a guest's rotatable bond count from its stored SMILES (mainly for backfilling guests created before this field existed).
- `Match.guest_rotatable_bonds`: denormalized rotatable bond count, joined in alongside `guest_price_per_gram`.
- Lightweight column-migration step in `init_db()` (`ALTER TABLE ... ADD COLUMN`) so existing databases pick up new columns like `rotatable_bonds` without a full reset.

### Changed
- `quality_score` now has three weighted components instead of two: packing coefficient (0-40, was 0-50), price (0-40, was 0-50), and guest flexibility (0-20, new) -- a rigid guest (0 rotatable bonds) gets full flexibility credit, decaying on a saturating curve (`QUALITY_FLEXIBILITY_HALF_SATURATION`, default 4 bonds) so each additional rotatable bond costs less than the last. A guest with no rotatable bond count yet gets neutral half credit, mirroring the existing missing-price handling. New config: `QUALITY_PC_WEIGHT`, `QUALITY_PRICE_WEIGHT`, `QUALITY_FLEXIBILITY_WEIGHT`, `QUALITY_FLEXIBILITY_HALF_SATURATION`.

## [0.2.0] - 2026-07-14 

### Added
- PubChem lookups: fetch guest molecules by name/CAS number via `supramatch.discovery.pubchem_client` (`supramatch guest fetch <query>`).
- Vendor price lookups via ChemPrice (Mcule, Molport, Chemspace): `Price` model, `prices` table, `supramatch.discovery.price_lookup`, and new `supramatch price lookup` / `supramatch price list` commands.
- `supramatch.pipeline.run_pipeline()` and `supramatch pipeline run`: end-to-end command that resolves a cage and guests, creates matches, prices the viable ones, and returns ranked results in one call.
- Config: `MCULE_API_KEY`, `MOLPORT_API_KEY`, `CHEMSPACE_API_KEY`, `PUBCHEM_REQUEST_DELAY`, `PUBCHEM_CID_BATCH_SIZE`, `PRICE_TTL_DAYS` (see `.env.example`).
- `guests` table: `iupac_name`, `pubchem_cid`, `molecular_formula` columns.

### Changed
- `guests` table: renamed `molar_mass` to `molecular_weight`.
- `matches.quality_score` and `matches.is_viable` are no longer stored columns; both are now computed at read time (in `Match`) since quality score depends on price data that can change independently after a match is created.
- `quality_score`'s packing-coefficient component now falls off on a smooth quadratic curve centered on the ideal PC, bottoming out at 0 at `QUALITY_PC_WINDOW_MULTIPLIER` (default 3) times `PC_TOLERANCE_DEFAULT` away from ideal, instead of a flat plateau within tolerance followed by a linear falloff — removes the scoring cliff at the tolerance boundary (`is_viable` still uses that boundary as its own pass/fail cutoff).
- `quality_score`'s price component is now scored on a log scale, bottoming out at 0 at `QUALITY_PRICE_CEILING` (default $100/g), so a given price change matters more near the low end (e.g. $1 → $2) than the same dollar change near the high end (e.g. $90 → $100), instead of scoring linearly.
- A guest's "best price" (used as the price input to `quality_score`) now excludes vendor quotes below `MIN_PURITY_PCT` (default 95%), including quotes with no purity reported at all — a cheap quote can no longer win on price alone if it doesn't clear the purity bar.
- `Price.purity` (and the `prices.purity` column) changed from a free-text string to a numeric percent (e.g. `95.0` instead of `"95%"`).

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

[unreleased]: https://github.com/meganklu/supramatch/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/meganklu/supramatch/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/meganklu/supramatch/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/meganklu/supramatch/releases/tag/v0.1.0
