# ADR-033: v14.4 Wave 0 Canonical Governance Freeze

## Status

Accepted for Wave 0 review. Wave 1 remains blocked until reviewer approval.

## Context

The active tree contains many Stores, public entry points, package documents,
verifiers, and release gates. Symbol counts alone cannot identify a business
capability, prove physical state ownership, or prevent an equal-count surface
swap. Wave 0 must freeze semantic ownership without adding product behavior.

## Decision

Wave 0 defines four human-maintained, integrity-bound registries:

1. The Capability Registry assigns every Store, CLI/API entry, package,
   verifier, schema, panel, and release check to one stable capability.
2. The State Authority Registry declares Store roles, physical root authority,
   relative path, read/write access, generation semantics, and source evidence.
3. The Package Registry declares package types, schema kinds, legacy raw-write
   source positions, and runtime-guarded writer contracts.
4. The Waiver Registry can authorize one exact, approved, time-bounded old to
   new metadata transition. The current registry has no active waiver.

The generated Catalog verifies source against those registries. The generated
Baseline freezes identity sets, complete registry metadata, dependency edges,
typing and complexity ceilings, coverage minimums, and performance budgets.
Neither generator invents ownership or bootstraps a missing baseline.

## Capability Rules

- One business capability has one `capability_id` across Store, CLI, API,
  package, verifier, schema, panel, release check, tests, migration, and rollback.
- Owner, source of truth, classification, and dependency declarations are
  mandatory.
- Every observed surface has exactly one owner.
- New business surfaces are prohibited during v14.4.
- Removing a surface or dependency is allowed; replacing it with a different
  identity is growth and fails.

## State Rules

- Store class names never prove physical uniqueness.
- Every writable namespace is `root_authority_id + relative_path_template`.
- Path evidence binds a normalized exact source fragment and source span.
- Same-root equality and parent/child overlap fail closed.
- Cross-root overlap is checked after the real Server composition resolves all
  runtime-required roots.
- Server startup, doctor, and the Wave 0 gate load the same packaged Registry
  and Baseline through one validated loader.
- Empty, damaged, stale, or mismatched policies fail closed, including in an
  isolated wheel installation.
- An overlap exception binds both Store IDs, root IDs, namespace hashes,
  baseline hash, approval, owner, ADR, and expiry. Rebinding either path
  invalidates it. Every remaining exception expires when version 14.4.0 is
  reached.

## Package Rules

- Each public package/report/sidecar/event/document discriminator is registered.
- Legacy raw writes are frozen by normalized source position, exact source
  evidence, policy, and capability.
- Each parameterized production writer has a qualified-symbol contract and a
  minimal independent allowed type set.
- Runtime guards use a private immutable index. Public loaders return copies and
  cannot mutate runtime authorization.
- Runtime policy is independently rebound to the approved Package Registry
  projection and fixed hashes.
- Unknown writers and unregistered values fail before document creation;
  nullable values are allowed only for explicitly declared writers.
- The canonical guard import, alias, binding hash, full normalized module source
  hash, and exact write-expression source hash are frozen.
- Dynamic rebinding changes the full module source hash and fails the contract.

Python inheritance, factories, re-exports, descriptors, and dynamic dispatch
are not interpreted as a homemade Python runtime. Safety comes from the guard
executing at the registered writer boundary and from freezing every new
`musicforge_*` literal. Unsupported raw writer growth fails rather than being
guessed.

## Source Evidence

Runtime evidence must not use `ast.dump()` or `ast.unparse()`. ADR-034 defines
source evidence schema 1 and the exact one-time migration from the earlier
interpreter-dependent format. Site identity is source path plus line, column,
end line, and end column; candidate labels cannot allocate occurrence numbers.

## Ratchets

- Any, complexity, debt, duration, and architecture maxima can only decrease.
- Coverage minima can only increase.
- Every file ceiling is independent and cannot be offset by another file.
- Dependency edges are compared by identity, not count.
- Frozen metadata rewrites require an exact waiver containing baseline,
  old/new hashes, approval identity/time, owner, expiry, and ADR binding.
- Waivers cannot be reused after a baseline or target value changes.

## Enforcement

`tools/update_v144_wave0_catalog.py` refuses a missing or wrong-schema baseline,
has no bootstrap/force mode, and checks regressions before writing. Registry
validation independently checks envelope schemas and integrity. CI runs updater
`--check`, mypy, Ruff, architecture tests, and the v14 release profile on real
Python 3.11 and 3.14 on Windows and Linux.

## Verification

- `tests/test_v144_wave0.py`
- isolated wheel installation and repository-external Server startup
- runtime policy mutation and full-resign attacks
- State path/overlap/rebinding attacks
- package writer guard, unknown writer, and cross-writer attacks
- source line-ending and source-position identity regressions
- `v144.wave0_catalog_baseline_smoke`

## Consequences

Wave 0 is a governance foundation only. Later waves may remove debt, surfaces,
and dependency edges under the directional ratchets. They may not use Wave 0
as permission to add product features, raise ceilings, rewrite ownership, or
silently rebaseline evidence.
