# ADR-020: v14.2.5 Explicit Any Class-Global Scope

Status: Accepted

Date: 2026-07-22

## Context

Collector schema 7 evaluated class definition expressions in the enclosing
scope, then evaluated the class body in an isolated class scope. It did not
model `global` or `nonlocal` declarations. A class body could therefore assign
or import `typing.Any` through a `global` name while the collector retained the
older module binding.

## Decision

MusicForge v14.2.5 adopts collector schema 8.

- Pre-scan each lexical scope for `global` and `nonlocal` declarations.
- Commit bindings from a module-level class body declared `global` to the
  module scope, including imports and assignments.
- Exclude redirected names from the class-local potential-binding map.
- Emit a hard quality blocker for Any-relevant runtime or cross-control-flow
  `global`/`nonlocal` alias mutation that the collector cannot model exactly.
- Keep ordinary non-type global state valid and unblocked.
- Retain every schema 7 total, layer, affected-file, per-file, complexity, and
  recovery ceiling. The migration cannot authorize growth.

## Verification

Unit tests and `v1425.explicit_any_class_global_scope_smoke` cover both the
assignment and import variants of the `TYPE_CHECKING` attack with 100 module
annotations. Additional tests require unsupported function-runtime,
cross-branch, and nonlocal Any flows to fail closed while ordinary global
counters remain accepted.

## Consequences

The active-tree measurement remains unchanged and has no scope-flow blockers.
This is the final planned extension of the handwritten collector. v14.3 must
either consume a mature semantic-analysis result or explicitly prohibit any
remaining unsupported dynamic binding form. ARCH-014 and TYPE-003 remain open
through v14.3.0.
