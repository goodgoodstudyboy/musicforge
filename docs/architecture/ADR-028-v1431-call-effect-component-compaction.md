# ADR-028: v14.3.1 Call-Effect Component Compaction

## Status

Accepted for v14.3.1.

## Context

ADR-026 joined unresolved call participants in union-find may-alias components.
The first implementation also copied every component member into `FlowValue`
identity and origin sets. Large components therefore caused repeated member
expansion during every expression read and made the v14 interface boundary
check exceed its unchanged CI duration budget.

## Decision

`FlowValue` stores only canonical component representatives. Component members,
cells, wildcard values, escape state, and taint remain owned by the data-flow
kernel. Operations canonicalize stale representatives through union-find before
reading or writing state. Only checks that need original identity metadata,
such as function-analysis checkpoints, inspect component members.

## Invariants

- may-alias, member-read, member-write, escape, and taint decisions are
  unchanged;
- local function summaries can still distinguish pre-function captured
  objects from temporary analysis objects;
- a 1,000-object unresolved call keeps flow values bounded to one component
  representative;
- Explicit Any, layer, file, complexity, coverage, recovery, and duration
  ceilings are not increased.

## Verification

Kernel tests cover compact large components and existing alias semantics.
`v1431.call_effect_component_compaction_smoke` verifies bounded representation,
component taint propagation, ADR presence, and unchanged ceilings.
