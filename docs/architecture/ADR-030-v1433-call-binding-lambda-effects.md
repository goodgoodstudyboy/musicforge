# ADR-030: Conservative Call Binding and Lambda Effects

## Status

Accepted for v14.3.3.

## Context

Collector schema 14 records generic call effects and finite local-function
summaries, but its summary binder only matched direct positional and named
arguments. Definition-time defaults, variadic parameters, literal `*`/`**`
expansion, and lambda closures could therefore omit an object from the caller
effect graph. A later Any-related write could use that missing edge to reach an
annotation while the total, layer, file, and scope ratchets remained clear.

## Decision

Collector schema 15 introduces one conservative call-binding result shared by
return-value and mutation-effect analysis.

- Function summaries preserve positional-only boundaries, ordered
  keyword-only parameters, variadic parameters, and definition-time default
  `FlowValue` bindings.
- Literal positional and keyword expansions are bound using Python call
  semantics. Missing, duplicate, dynamic, or otherwise unresolved bindings do
  not use a partial summary; they fall back to the generic may-alias call
  effect with every explicit, default, and captured participant.
- Variadic arguments are represented as data-flow containers or mappings, and
  summaries that expose parameter members connect those stored values at the
  caller.
- Lambdas use the same callable summary builder as named functions. Their
  defaults, body effects, free-variable storage, alias returns, and factory
  return identity remain attached to the callable component.
- Rebinding a free variable retained by a function or lambda is treated as an
  unknown late-bound capture. Until binding-cell analysis exists, annotation
  use fails closed instead of trusting the definition-time object identity.
- Callable summaries are resolved through all original identities in a
  compacted may-alias component, not only its current union-find root.

This is deliberately conservative. It does not attempt to execute arbitrary
Python binding logic. Any call that cannot be proven to match a local summary
uses the existing generic call-effect model instead of failing open.

## Invariants

- The Explicit Any total, affected-file, layer, per-file, complexity,
  recovery, coverage, and performance ceilings do not increase.
- Runtime-only calls that never feed an annotation remain non-blocking.
- Definition-time defaults are evaluated in the enclosing lexical scope.
- A lambda returned by a factory cannot lose the closure object that its body
  may mutate.

## Verification

- Runtime, Ruff, strict-mypy, collector, and four-layer ratchet regressions
  cover positional defaults, keyword-only defaults, `*args`, `**kwargs`,
  literal `*`/`**` expansion, direct lambdas, lambda defaults, and lambda
  factories, plus function and lambda free-variable rebinding.
- The v14.3 attack corpus includes all of those paths.
- `v1433.call_binding_lambda_effect_smoke` is required by v14, latest,
  security, GA, full, and publish profiles.
- Existing schema 14 call-effect, shadowing, compaction, and single-pass
  regressions remain green.
- Function-summary may-store analysis resolves each participant and parameter
  component once per operation, then computes captured pre-function roots once
  for the complete participant set. Every captured root still connects to the
  same matched parameter, preserving the conservative alias relation.
- Generic call effects join all participants once, then connect the result to
  that already-merged component. Common one-identity component sets are reused
  while union-find roots are still resolved on every read.
- Typing metrics skip per-annotation source slicing when a source file does not
  contain `ImplementationDocument`. This is an exact file-level precondition,
  not a sampling or evidence omission.
- These changes remove repeated graph and source work while retaining the
  existing 180-second Windows CI ceiling.

## Consequences

Callable analysis now has one parameter-binding authority and one fallback
rule. New syntax support must extend that authority or fail closed; callers
must not add independent partial binders.
