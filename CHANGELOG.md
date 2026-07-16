# Changelog

This file contains the current v14 major line. Earlier history is preserved in
[`docs/changelog/CHANGELOG-v13.0-v13.8.md`](docs/changelog/CHANGELOG-v13.0-v13.8.md)
and [`docs/changelog/CHANGELOG-v0-v13.6.md`](docs/changelog/CHANGELOG-v0-v13.6.md).

## v14.0.1 - 2026-07-15

- Made v14 facade, source-tree, and tracked coverage hashes independent of
  platform line endings so Windows-generated architecture evidence verifies on
  Linux and clean GitHub Actions checkouts.
- Replaced machine-specific raw coverage provenance with canonical semantic
  coverage evidence and added schema, package type, file count, and semantic
  hash validation.
- Added cross-platform hash regressions and adjusted the three v14 hard
  duration budgets to measured shared-runner execution times without reducing
  architecture, security, typing, or coverage requirements.

## v14.0.0 - 2026-07-15

- Migrated 270 production modules into the Creation, Studio, Quality, Delivery,
  Trust, and Program bounded contexts and reduced active-to-compatibility imports
  from 224 to zero without changing public CLI, API, or Studio contracts.
- Retired 271 compatibility implementations into explicit static facades with
  zero active implementation lines, wildcard exports, dynamic forwarding, or
  current-profile legacy callables.
- Removed interface-owned Store wiring and anonymous Python part modules,
  split oversized interface/application/domain functions, and enforced final
  architecture, type-debt, coverage, and complexity ratchets.
- Consolidated ZIP security and lifecycle history behavior on the shared
  Verification and Lifecycle kernels while retaining active attack corpora.
- Added v14 mutable-state migration plan/apply/rollback with verified backup,
  intent, commit marker, immutable evidence preservation, and byte-identical
  isolated rollback rehearsal.
- Added machine-readable CLI/API/Studio contract compatibility evidence and a
  final-SHA reviewer package that independently recomputes source, migration,
  security, quality, capability, CI, profile, and release-alignment evidence.
