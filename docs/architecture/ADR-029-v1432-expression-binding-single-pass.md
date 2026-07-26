# ADR-029: Expression Binding Single-Pass Scan

## Status

Accepted for v14.3.2.

## Context

The schema 14 call-effect model fixed the unknown-call alias transport gap, but
v14.3.1 still exceeded the unchanged 180-second interface/application boundary
budget on Windows CI. Profiling showed that object-component operations were no
longer dominant. Expression classification separately traversed each AST for
uncertain, unknown, and Any dependencies, and Any detection itself traversed
the same tree twice.

## Decision

Expression binding classification uses one iterative traversal. It resolves
each name once per expression and jointly records uncertain, unknown, direct
Any, qualified `typing.Any`, and quoted annotation evidence. Qualified
attribute bases retain the established shadowing behavior. Actual annotation
counting remains independent and unchanged.

One AST expression occurrence is one Python evaluation, so the collector also
memoizes its immutable `FlowValue` by AST identity. Assignment handling,
call-summary construction, and visitor traversal reuse that value instead of
repeating equivalent call-effect and member-read analysis. Distinct expression
occurrences never share a cached value.

Collector schema 14 remains authoritative because this is an equivalent
execution strategy, not a semantic migration. The Explicit Any total, layer,
file, complexity, coverage, recovery, and 180-second performance ceilings must
not increase.

## Verification

- Existing schema 14 attack and shadowing corpus remains green.
- A dedicated expression probe reports exactly 100 Any annotations.
- A regression confirms repeated analysis of one AST occurrence returns the
  same immutable flow value.
- `v1432.expression_binding_single_pass_smoke` is required by v14, latest,
  security, GA, and full profiles.
- The existing `v140.interface_application_boundary_smoke` remains the hard CI
  performance gate.

## Consequences

The collector keeps conservative fail-closed semantics while avoiding repeated
tree walks. Future data-flow work must profile full-tree behavior and may not
replace semantic checks with budget increases.
