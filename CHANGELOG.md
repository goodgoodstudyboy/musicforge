# Changelog

This file contains the current v14 major line. Earlier history is preserved in
[`docs/changelog/CHANGELOG-v13.0-v13.8.md`](docs/changelog/CHANGELOG-v13.0-v13.8.md)
and [`docs/changelog/CHANGELOG-v0-v13.6.md`](docs/changelog/CHANGELOG-v0-v13.6.md).

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
