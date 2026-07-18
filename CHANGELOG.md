# Changelog

This file contains the current v14 major line. Earlier history is preserved in
[`docs/changelog/CHANGELOG-v13.0-v13.8.md`](docs/changelog/CHANGELOG-v13.0-v13.8.md)
and [`docs/changelog/CHANGELOG-v0-v13.6.md`](docs/changelog/CHANGELOG-v0-v13.6.md).

## v14.1.2 - 2026-07-18

- Fixed the explicit-`Any` quality collector so aliases from `typing.Any` and
  `typing_extensions.Any`, module aliases such as `import typing as t`, nested
  annotations, and quoted annotations are all counted.
- Added a collector schema version to the typing ratchet so older incomplete
  explicit-`Any` baselines cannot be reused silently.
- Rebuilt explicit-`Any` total, layer, and per-file budgets with the corrected
  collector while keeping TYPE-003 open for v14.2 precision cleanup.
- Added regression coverage for direct, alias, module-alias, nested, quoted, and
  100-field alias growth cases.

## v14.1.1 - 2026-07-17

- Fixed the v14.1 complexity ratchet updater so one oversized module cannot
  grow while another module shrinks enough to reduce the aggregate total.
- Documented the v14.1 one-time per-file complexity exceptions in ADR-015 and
  kept ARCH-014 open for v14.2 extraction work.
- Added explicit-`Any` quality metrics by total, layer, and file, with machine
  budgets in `architecture-v14-quality.json`.
- Split remaining type-precision debt into TYPE-003 so TYPE-002 continues to
  mean zero active-tree mypy errors rather than "no explicit Any anywhere."

## v14.1.0 - 2026-07-17

- Closed TYPE-002 by migrating the complete active source tree from 12,885
  measured mypy errors to a zero-error hard gate, with typed composition
  contexts and fail-closed JSON boundary coercions.
- Expanded Ruff enforcement to `song_agent`, `tests`, and `tools`; documented
  the two static public-facade exceptions and removed the remaining repository
  lint debt.
- Reduced registered oversized-module lines from 124,211 to 124,043 and added
  hard aggregate complexity limits. ADR-015 explicitly retains ARCH-014 for
  bounded-context extraction in v14.2 rather than claiming it is closed.
- Ratcheted CI security/latest/GA profile budgets down by ten percent and made
  further increases require measured final-SHA evidence.
- Added `v141.quality_debt_closure_smoke` and CI checks that cover the complete
  active mypy roots and full repository lint surface.

## v14.0.1 - 2026-07-15

- Made v14 facade, source-tree, and tracked coverage hashes independent of
  platform line endings so Windows-generated architecture evidence verifies on
  Linux and clean GitHub Actions checkouts.
- Replaced machine-specific raw coverage provenance with canonical semantic
  coverage evidence and added schema, package type, file count, and semantic
  hash validation.
- Added cross-platform hash regressions and adjusted v14 check and CI profile
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
