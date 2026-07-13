# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
