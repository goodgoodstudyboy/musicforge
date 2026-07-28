# ADR-031: Late-Bound Lexical Capture Cells

## Status

Accepted for v14.3.4.

## Context

Collector schema 15 retained closure objects that already had a data-flow
identity when a callable was defined. Python closures resolve lexical names at
call time, so a function or lambda defined before the first assignment to a
free variable had no object identity to retain. A later assignment could then
transport an object through that closure without entering the Explicit Any
graph.

## Decision

Collector schema 16 represents every statically resolvable free-variable
capture as a stable lexical cell keyed by `(scope_id, name)`.

- Every module and function analysis scope receives a stable scope ID.
- Bound-name ownership is collected for the same lexical scope without
  treating class bodies as closure scopes.
- A free name receives a cell even when no object exists at definition time.
- First binding and subsequent rebinding connect the current value to that
  cell. Callable summaries retain the cell reference and refresh it before
  applying mutation or return effects.
- Sibling callables that redirect a binding through `nonlocal` or `global`
  update the same owner cell; rebinding need not appear directly in the owner
  body after the captured callable definition.
- Returned callables preserve capture-to-parameter substitution explicitly;
  callable objects are not unioned with all closure objects.
- A capture that is still unresolved while another callable summary is being
  constructed retains its cell without inventing a value. Its statically
  owned binding resolves the cell before a runtime-reachable summary effect
  can transport that value.

## Invariants

- Explicit Any total, affected-file, layer, per-file, complexity, recovery,
  coverage, and performance ceilings cannot increase.
- Named functions, lambdas, factories, and nested functions use the same cell
  model.
- Captured values are not treated as aliases of the callable object itself.
- The full pytest duration budget remains 3,600 seconds.

## Verification

- Runtime probes cover named functions, lambdas, factories, nested functions,
  named-expression first binding, explicit `nonlocal`, sibling `nonlocal`
  rebinding, and helper `global` rebinding before producing 100 runtime Any
  annotations.
- Every probe passes repository Ruff and strict mypy while the collector counts
  100 annotations and triggers scope, total, layer, and file blockers.
- `v1434.late_bound_lexical_capture_smoke` is required by v14, latest,
  security, GA, full, and publish profiles.
- Existing callable binding, lambda factory, return-alias, data-flow, and
  ordinary-call negative regressions remain green.

## Consequences

Closure authority now follows Python lexical names rather than definition-time
object availability. Future callable analysis must extend the cell and summary
model or fail closed; it must not reintroduce object-snapshot capture logic.
