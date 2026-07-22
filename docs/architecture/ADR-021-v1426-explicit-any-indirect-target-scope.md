# ADR-021: v14.2.6 Explicit Any Indirect-Target Scope

Status: Accepted

Date: 2026-07-22

## Context

Collector schema 8 modeled direct assignments and imports redirected through
`global` or `nonlocal`. Indirect target forms still replaced a binding with the
trusted `other` state. A class body could therefore redirect a `for`, `with`,
or `match` target to a module alias, assign `typing.Any` at runtime, and make
later module annotations disappear from the Explicit Any ratchet.

## Decision

MusicForge v14.2.6 adopts collector schema 9.

- Bind `for`/`async for`, `with`/`async with`, and `match` capture targets as
  `uncertain` when the collector cannot derive their runtime value exactly.
- Preserve `uncertain` through lexical and control-flow merges.
- Count an annotation that resolves through an uncertain binding and emit a
  hard scope-flow blocker. This is fail-closed behavior, not proof that the
  runtime value is necessarily `typing.Any`.
- Do not block an ordinary indirect value that is never consumed as a type
  annotation.
- Retain every schema 8 total, layer, affected-file, per-file, complexity, and
  recovery ceiling. The migration cannot authorize growth.

## Verification

Unit tests and `v1426.explicit_any_indirect_target_scope_smoke` execute the
`TYPE_CHECKING` class-global attack with `for`, `with`, and `match` targets.
Each variant must produce 100 runtime annotations, pass project Ruff and strict
mypy, count 100 annotations, emit the uncertain-binding blocker, and trip the
total, layer, and file ratchets.

## Consequences

The active tree remains free of scope-flow blockers. Schema 9 closes this
known indirect-target gap without claiming full Python data-flow analysis.
v14.3 must consume a mature semantic-analysis result or explicitly reject
unsupported dynamic binding forms. ARCH-014 and TYPE-003 remain open through
v14.3.0.
