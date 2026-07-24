# ADR-025: v14.2.10 Explicit Any Alias Fail-Closed Semantics

Status: Accepted

Date: 2026-07-24

## Context

Collector schema 12 introduced an independent object data-flow kernel, but
three Python runtime semantics remained outside that model:

- a value-less annotated assignment records metadata and does not rebind its
  target;
- an extended unpack maps suffix targets from the end of the source; and
- a function can mutate an object supplied by its caller.

Treating the first two forms as ordinary assignments lost valid aliases. The
third form used an escaped parameter without a source origin, so an
Any-relevant write could not be propagated to the caller. All three gaps could
hide a runtime `typing.Any` behind a binding that the collector considered
ordinary.

## Decision

MusicForge v14.2.10 adopts collector schema 13 and extends the schema 12
data-flow model instead of adding syntax-specific allow rules.

- A value-less `AnnAssign` counts its annotation and leaves every runtime
  binding and object identity unchanged.
- Container objects retain a known literal length. Extended unpacking maps
  prefix targets from the start and suffix targets from the end. If the source
  length is unknown, every result retains the complete source provenance and
  remains unknown until annotation consumption fails closed.
- Function parameters are escaped objects with no source origin. An
  Any/uncertain member write through such an object emits
  `unsupported_interprocedural_any_write`.
- Direct-name calls use a bounded function write summary to propagate an
  Any/uncertain parameter mutation to the corresponding positional or keyword
  argument. This is a finite effect summary, not general Python execution.
- Ordinary unknown runtime values are not promoted to Any-related writes.
  They continue to carry provenance and fail only if an annotation consumes
  an unresolved binding. This distinction keeps the active tree free of
  unrelated false positives.
- Indirect call targets and metaprogramming are not accepted as authorities
  for constructing type aliases. If their Any-relevant write cannot be
  resolved, the definition-time scope blocker remains authoritative.
- Every schema 12 total, layer, affected-file, per-file, complexity, and
  recovery ceiling remains unchanged. The updater cannot authorize growth
  during the 12-to-13 migration. The policy validator independently pins the
  schema 13 total, affected-file, and layer values in addition to the existing
  per-file budget hash.

## Verification

The release gate executes three source-level attacks:

1. alias followed by a value-less annotation;
2. extended unpack with a suffix alias; and
3. a function parameter member write followed by a direct call.

Each probe must produce runtime `typing.Any`, 100 annotations, a collector
count of 100, a scope-flow blocker, and total/layer/file ratchet failures while
remaining valid under project Ruff and strict mypy. Unit tests separately
cover known and unknown-length unpacking, unresolved escaped parameters,
ordinary interprocedural writes, keyword calls, and safe annotation-only
statements.

The active-tree measurement must remain 11,993 Explicit Any annotations, 461
affected files, and zero scope blockers.

## Consequences

Schema 13 closes the three known fail-open paths without claiming whole-program
Python interpretation. The collector now has an explicit boundary: exact local
object flow and finite direct-call write effects are modeled; unsupported
Any-relevant dynamic call effects are prohibited. ARCH-014 and TYPE-003 remain
open through v14.3.0.
