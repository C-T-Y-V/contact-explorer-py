# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-11-13

### Added
- **Core Engine:**
  - Thread-safe SQLite persistence layer with WAL (Write-Ahead Logging) mode and cascading foreign keys.
  - Multi-phone number and multi-email contact data model with custom label support.
  - Hierarchical folder/group categorization and arbitrary tagging.
  - 30-day soft-delete recycle bin with complete snapshot serialization and instant rollback.
  - Audit trail event logging tracking contact creation, edits, merges, and restores.
- **Search & Intelligence:**
  - Multi-field tokenized query engine (`group:`, `tag:`, `company:`, `city:`, `note:`, `favorite:`).
  - Fuzzy string matching scoring algorithm with normalization.
  - Local duplicate contact detection engine with score thresholding and multi-field merging.
  - Smart group dynamic rule evaluation and offline tag recommendations.
- **Data Transfer & Formats:**
  - Full roundtrip CSV import and export with RFC 4180 standard escaping.
  - vCard (VCF) 3.0 / 4.0 parsing and serialization engine.
  - Full-vault JSON backup and restore with foreign key relationship reconciliation.
- **Interfaces:**
  - Modern Dark Neon desktop user interface built with Python Tkinter.
  - Dual list/card view modes, split pane preview, multi-selection, and quick actions.
  - Standalone, dependency-free HTTP REST API server with JSON endpoints.
  - CLI commands `contact-explorer` and `contact-explorer-server`.
- **Engineering & CI/CD:**
  - PEP 621 compliant `pyproject.toml` packaging.
  - Comprehensive automated unit and integration test suite with `pytest`.
  - Multi-platform GitHub Actions CI matrix (Ubuntu, Windows, macOS across Python 3.10–3.13).
  - CodeQL automated static analysis security workflow.
  - Complete architecture, data model, and API documentation in `docs/`.
