# ADR-017: v14.2.2 Explicit Any Scope Collector

Status: Accepted

Date: 2026-07-20

## Context

Collector schema 4 restored function-body and alias coverage, but it only
expanded imports under `TYPE_CHECKING`. An alias imported under ordinary
control flow could therefore annotate arbitrary fields without entering the
Explicit Any ratchet. Unbound bare names such as a locally declared class named
`Any` were also treated as `typing.Any`, creating false positives.

Because this collector is a release quality gate, a deterministic bypass is a
release blocker even though runtime product behavior is unaffected.

## Decision

MusicForge v14.2.2 adopts collector schema 5.

- Scan imports and aliases in the same lexical scope under `if`, `try/except`,
  `with`, `for`, `while`, and `match`, including function-local scopes.
- Treat a conflicting branch as Any-capable when any branch can bind the name
  to `typing.Any` or a typing module. A branch conflict cannot resolve to zero.
- Record plain class, function, parameter, import, and assignment bindings as
  non-typing names when no Any-capable source exists.
- Require an explicit `typing` or `typing_extensions` import binding. Bare
  names are not implicitly trusted as typing symbols.
- Preserve nested annotations, quoted annotations, `TypeAlias`, module aliases,
  and alias-chain coverage from schema 4.
- Keep all v14.2.1 recovery ceilings unchanged. Schema migration cannot waive
  total, affected-file, layer, or per-file growth.

## Verification

The unit and release-check attack corpus includes:

- module and function-local conditional imports;
- `try/except` conflicting bindings;
- `with`, loop, and `match` imports;
- 100 conditional aliases crossing every ratchet level;
- plain class, function, and assignment shadow bindings;
- existing direct, module, nested, quoted, and type-alias cases.

`v1421.stabilization_rollback_smoke` retains these probes, and
`v1422.explicit_any_scope_smoke` makes schema 5 independently visible in every
current v14 publication profile.

## Consequences

The corrected active-tree measurement is allowed to decrease but not increase.
No product schema or persistent evidence format changes. ARCH-014 and TYPE-003
remain open through v14.3.0.
