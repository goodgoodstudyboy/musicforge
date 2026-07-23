# ADR-022: v14.2.7 Explicit Any Derived Uncertain Flow

Status: Accepted

Date: 2026-07-23

## Context

Collector schema 9 preserved an `uncertain` binding only when the right-hand
side was a direct name. A compound expression such as `Alias[0]`,
`(Alias,)[0]`, or `factory(Alias)` was scanned for direct `Any` annotations and
then downgraded to `other`. An indirect class-global `for`, `with`, or `match`
binding could therefore be transformed once and disappear from every Explicit
Any ratchet while still evaluating to `typing.Any` at runtime.

## Decision

MusicForge v14.2.7 adopts collector schema 10.

- Inspect the complete right-hand-side AST before assigning a binding kind.
- If any expression dependency resolves to `uncertain`, preserve the
  `uncertain` state through subscripts, attributes, containers, calls,
  conditional expressions, Boolean expressions, and chained assignments.
- When an Any-capable value is written through a statically identifiable
  attribute or subscript target, taint its root object so a later read cannot
  launder the value through mutable storage.
- Emit a hard blocker and count usage only when an annotation consumes the
  uncertain result. Ordinary runtime values that are never used as annotations
  remain non-blocking.
- Preserve every schema 9 total, layer, affected-file, per-file, complexity,
  and recovery ceiling. The 9-to-10 migration cannot authorize growth.

## Verification

Unit tests and `v1427.explicit_any_derived_uncertain_scope_smoke` execute the
class-global `for`, `with`, and `match` attacks followed by derived
expressions. Each attack must evaluate to `typing.Any`, create 100 runtime
annotations, pass project Ruff and strict mypy, count 100 annotations, emit the
uncertain-binding blocker, and fail total, layer, and file ratchets.

Additional tests cover attribute, container, call, conditional, Boolean, and
multi-level propagation, plus the non-annotation negative case.

## Consequences

The active tree remains free of scope-flow blockers. This fail-closed taint is
deliberately conservative and does not claim to be a complete Python semantic
analyzer. v14.3 must consume mature semantic-analysis output or explicitly
prohibit unsupported dynamic binding forms. ARCH-014 and TYPE-003 remain open
through v14.3.0.
