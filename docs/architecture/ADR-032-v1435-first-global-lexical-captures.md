# ADR-032: First-Created Module Global Lexical Captures

## Status

Accepted for v14.3.5.

## Context

Collector schema 16 created lexical cells only when a callable free name had a
statically known owner. A normal free name in a function follows Python's
global lookup when no enclosing function binds it, even if the module binding
is first created later by a sibling helper using `global`. Returning no cell in
that case disconnected the captured read from the helper write and allowed
Any-bearing object flow to escape the ratchet.

## Decision

Collector schema 17 applies Python name resolution directly:

- An ordinary callable free name first searches enclosing function scopes.
- If no enclosing function owns the name, the capture uses the module lexical
  cell keyed by the stable module scope ID and name.
- A sibling helper's `global` write binds the same module cell, whether or not
  the module had a prior static assignment.
- An explicit `nonlocal` declaration never falls back to the module. Missing
  enclosing ownership remains unresolved and fail-closed.
- Named functions, lambdas, factories, and nested returned callables use the
  same rule.

## Invariants

- Explicit Any total, affected-file, layer, per-file, complexity, recovery,
  coverage, and performance ceilings cannot increase.
- The change does not add a suppression exception or weaken Ruff or mypy.
- Existing schema 16 lexical-cell, call-effect, argument-binding, alias, and
  data-flow behavior remains authoritative.

## Verification

Each attack probe defines a callable before any module `Store` binding, creates
`Store` only through a sibling helper's `global` assignment, transports an
Any-bearing alias, and then creates 100 runtime Any annotations. Named,
lambda, factory, and nested-function variants must pass repository Ruff and
strict mypy while collector scope, total, layer, and file ratchets all fail.

`v1435.first_global_lexical_capture_smoke` is required by the v14, latest,
security, GA, full, and publish profiles.

## Consequences

Module-global lookup no longer depends on a pre-existing static module binding.
Future lexical-flow changes must preserve Python's distinction between ordinary
global fallback and explicit `nonlocal` ownership.
