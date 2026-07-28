# Changelog

This file contains the current v14 major line. Earlier history is preserved in
[`docs/changelog/CHANGELOG-v13.0-v13.8.md`](docs/changelog/CHANGELOG-v13.0-v13.8.md)
and [`docs/changelog/CHANGELOG-v0-v13.6.md`](docs/changelog/CHANGELOG-v0-v13.6.md).

## v14.3.5 - 2026-07-29

- Resolved ordinary callable free names without an enclosing function owner
  through a stable module lexical cell, including names first created by a
  sibling helper's `global` write.
- Preserved fail-closed handling for invalid explicit `nonlocal` references;
  the module fallback applies only to normal Python global-name lookup.
- Added named-function, lambda, factory, and nested-function runtime, Ruff,
  strict-mypy, collector, four-layer ratchet, and release-check regressions
  for first-created module globals.
- Split the interface/application boundary scan from the independent Explicit
  Any data-flow gate, reducing repeated full-tree analysis while retaining the
  existing 180-second hard budget and both release checks.
- Upgraded the Explicit Any collector to schema 17 without raising typing,
  file, layer, complexity, recovery, coverage, or performance ceilings.

## v14.3.4 - 2026-07-28

- Replaced definition-time-only closure retention with stable lexical capture
  cells for every statically resolvable free variable.
- Re-resolved captured cells at call-summary application and preserved capture
  substitution through factories and nested returned callables.
- Added named-function, lambda, factory, nested-function, named-expression,
  explicit/sibling `nonlocal`, and helper `global` runtime, Ruff, strict-mypy,
  collector, four-layer ratchet, and release-check regressions.
- Upgraded the Explicit Any collector to schema 16 without raising typing,
  file, layer, complexity, recovery, coverage, or performance ceilings.
- Kept the local full pytest hard budget at 3,600 seconds and changed default
  xdist parallelism from a fixed four workers to a bounded adaptive policy:
  four workers on GitHub Actions and four to eight workers locally.

## v14.3.3 - 2026-07-27

- Added one conservative Python call binder for positional-only,
  keyword-only, default, variadic, and literal expanded arguments.
- Persisted definition-time default values in callable summaries and routed
  incomplete bindings through generic may-alias effects instead of partial
  summaries.
- Unified lambda and named-function effect analysis, including closure storage
  and callable identity across factory returns and compacted components.
- Added runtime/Ruff/strict-mypy call-binding, lambda, and late-bound closure
  attack regressions, expanded the v14.3 attack corpus, and added
  `v1433.call_binding_lambda_effect_smoke`.
- Removed repeated call-effect component joins, batched function-summary
  capture comparisons, reused common component-root sets, and skipped source
  slicing in files without `ImplementationDocument` so the expanded call
  model remains below the unchanged 180-second Windows CI budget.
- Upgraded the Explicit Any collector to schema 15 without raising any typing,
  file, layer, complexity, recovery, coverage, or performance ceiling.

## v14.3.2 - 2026-07-26

- Replaced four repeated AST walks per expression with one binding scan while
  preserving the schema 14 Any, unknown, quoted-annotation, and shadowing
  semantics.
- Reused one immutable `FlowValue` per AST expression occurrence so assignment,
  call-summary, and visitor phases do not repeat equivalent data-flow work.
- Parsed repeated quoted annotations once while retaining scope-sensitive
  counting, shared the immutable parsed syntax across source files, and reduced
  both runtime and potential-binding annotation classification to one traversal.
- Reduced the v14 interface/application boundary gate from about 51 seconds to
  about 27 seconds locally after v14.3.1 still exceeded the unchanged
  180-second budget on Windows CI.
- Added ADR-029 and `v1432.expression_binding_single_pass_smoke`; no quality,
  complexity, coverage, or performance ceiling was raised.

## v14.3.1 - 2026-07-26

- Compacted call-effect flow values to union-find representatives while
  retaining component-level member, escape, and taint semantics.
- Removed the component-member set amplification that made the v14 interface
  boundary check exceed its unchanged 180-second CI budget.
- Added ADR-028, a 1,000-object compaction regression, and
  `v1431.call_effect_component_compaction_smoke` without raising any quality,
  complexity, coverage, or performance ceiling.

## v14.3.0 - 2026-07-25

- Replaced call-time Any heuristics with a generic call-effect data-flow model
  that records ordinary alias transport before later Any mutation.
- Added union-find may-alias components, component-level member and taint
  state, directed local-function may-store/return summaries, callable roles,
  comprehension result flow, and bound-method origins.
- Added ADR-026, eleven runtime/Ruff/strict-mypy attack regressions, safe
  controls, and `v143.explicit_any_call_effect_dataflow_smoke` while preserving
  every schema 13 typing, file, layer, complexity, and recovery ceiling.

## v14.2.10 - 2026-07-24

- Upgraded the Explicit Any collector to schema 13 and aligned value-less
  annotations plus extended unpack suffixes with Python runtime semantics.
- Added bounded direct-call member-write summaries and a fail-closed blocker
  for Any/uncertain writes through unresolved interprocedural objects.
- Added ADR-025, data-flow unit tests, three runtime/Ruff/strict-mypy attack
  regressions, and `v14210.explicit_any_alias_fail_closed_smoke` without
  raising any typing, complexity, per-file, or recovery ceiling.

## v14.2.9 - 2026-07-24

- Replaced incremental object-alias handling with an independent schema 12
  abstract data-flow kernel for identities, member cells, dynamic escape,
  possible origins, reachability, and mutation-time taint.
- Closed destructuring, subscript, attribute, and call-return alias laundering
  while retaining safe rebind behavior and avoiding ordinary factory-call
  false positives.
- Added ADR-024, kernel unit tests, runtime/Ruff/strict-mypy attack regressions,
  and `v1429.explicit_any_alias_dataflow_smoke` without raising any typing,
  complexity, per-file, or recovery ceiling.

## v14.2.8 - 2026-07-23

- Upgraded the Explicit Any collector to schema 11 with lexical-scope
  may-alias identity tracking for direct, multi-level, class-object, and
  branch aliases.
- Attribute/subscript writes, in-place augmented mutation, and direct or
  derived Any-related dynamic escape now taint every possible alias, while
  ordinary reassignment disconnects the previous alias group and ordinary
  unresolved values do not pollute unrelated types.
- Added ADR-023, runtime/Ruff/strict-mypy object-alias regressions, and the
  `v1428.explicit_any_object_alias_scope_smoke` critical release gate without
  raising any typing, complexity, per-file, or recovery ceiling.

## v14.2.7 - 2026-07-23

- Upgraded the Explicit Any collector to schema 10 so an uncertain binding
  remains uncertain across subscripts, attributes, containers, calls,
  conditional/Boolean expressions, and chained assignments.
- Added exact runtime/Ruff/strict-mypy regressions for derived class-global
  `for`, `with`, and `match` attacks, including all three ratchet layers and a
  non-annotation negative case.
- Added ADR-022 and the
  `v1427.explicit_any_derived_uncertain_scope_smoke` release gate without
  raising any typing, complexity, per-file, or recovery ceiling.

## v14.2.6 - 2026-07-22

- Upgraded the Explicit Any collector to schema 9 so indirect `for`, `with`,
  and `match` targets redirected through `global`/`nonlocal` cannot silently
  become trusted non-Any bindings.
- Added an explicit uncertain binding state that fails closed when a later
  annotation depends on an indirect binding the collector cannot derive
  exactly, while ordinary non-type indirect targets remain valid.
- Added ADR-021, runtime/Ruff/strict-mypy 100-annotation attack regressions,
  and the `v1426.explicit_any_indirect_target_scope_smoke` release gate without
  raising any typing, complexity, per-file, or recovery ceiling.

## v14.2.5 - 2026-07-22

- Upgraded the Explicit Any collector to schema 8 so `global` assignment and
  import inside an immediately executed class body update the module binding.
- Added hard scope-flow blockers for Any-relevant runtime and cross-control-flow
  `global`/`nonlocal` mutations that cannot be modeled deterministically.
- Added ADR-020, exact 100-annotation assignment/import regressions, and the
  `v1425.explicit_any_class_global_scope_smoke` release gate without raising
  any typing, complexity, per-file, or recovery ceiling.

## v14.2.4 - 2026-07-21

- Upgraded the Explicit Any collector to schema 7 so lambda, function,
  async-function, and class definition-time expressions update their enclosing
  binding scope in Python evaluation order.
- Added exact `TYPE_CHECKING` regressions for lambda positional defaults,
  function positional defaults, async keyword defaults, decorators, class
  bases, and class keywords.
- Preserved every schema 6 total, layer, affected-file, per-file, and recovery
  ceiling; no quality budget was raised.

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
