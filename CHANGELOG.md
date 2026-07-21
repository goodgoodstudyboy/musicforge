# Changelog

This file contains the current v14 major line. Earlier history is preserved in
[`docs/changelog/CHANGELOG-v13.0-v13.8.md`](docs/changelog/CHANGELOG-v13.0-v13.8.md)
and [`docs/changelog/CHANGELOG-v0-v13.6.md`](docs/changelog/CHANGELOG-v0-v13.6.md).

## v14.2.3 - 2026-07-21

- Upgraded the Explicit Any collector to schema 6 so lambda parameters,
  assignment expressions, and nested lambdas cannot mutate an enclosing
  collector binding.
- Added a 100-annotation lambda-walrus attack regression to unit tests and the
  published v14 release-check matrix.
- Preserved every v14.2.1 recovery ceiling and schema 5 measured budget; the
  active-tree Explicit Any totals remain unchanged.

## v14.2.2 - 2026-07-20

- Upgraded the Explicit Any collector to schema 5 so aliases imported inside
  ordinary `if`, `try/except`, `with`, `for`, `while`, and `match` control flow
  are included in their lexical scope, including function-local imports.
- Made conflicting branch bindings fail closed while ordinary classes,
  functions, and assignments named like `Any` remain non-typing bindings when
  no `typing.Any` source exists.
- Added direct, conditional, nested, quoted, shadowing, and 100-alias growth
  regressions to unit tests and the published v14 release-check matrix.
- Preserved the v14.2.1 recovery ceilings and tightened measured total, layer,
  affected-file, and per-file budgets under collector schema 5.

## v14.2.1 - 2026-07-20

- Reverted the v14.2.0 generated `v142_*.py` extraction and restored the
  reviewed v14.1.2 production structure; the public v14.2.0 release remains a
  historical, non-recommended baseline.
- Removed the generated splitter, mypy exclusion, file-wide suppressions, and
  runtime `bind_globals(globals())` wiring introduced by v14.2.0.
- Upgraded the Explicit Any collector to schema 4 so function-local variables,
  nested functions, methods, scoped imports, `TYPE_CHECKING`, aliases, module
  aliases, and quoted annotations are counted.
- Added ADR-016 and a hard `v1421.stabilization_rollback_smoke` to every current
  v14 release profile. ARCH-014 and TYPE-003 remain open through v14.3.0.
- Cached v14 typing and complexity measurements by normalized source content
  and policy while failing closed on concurrent source changes, keeping the
  Windows release profiles inside their existing hard duration budgets.

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
