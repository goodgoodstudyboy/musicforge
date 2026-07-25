# ADR-026: v14.3 Explicit Any Call-Effect Data Flow

## Status

Accepted for v14.3.0.

## Context

Collector schema 13 tracked direct aliases, member writes, uncertain values,
and selected local-function writes. It did not record an unknown call that
transported ordinary objects before either object became Any-related. A later
write could therefore produce a runtime Any annotation without crossing an
existing data-flow edge.

This is a call-effect problem, not an `append` or `setattr` API problem. Adding
per-method exceptions would continue the incomplete Python-semantics parser
that v14.2.9 was intended to replace.

## Decision

Collector schema 14 uses a generic call-effect model:

- unresolved calls create a may-alias component between their receiver,
  object arguments, and result, even when every value is ordinary at call
  time;
- the component is represented by union-find roots with component-level
  member, wildcard, escape, and taint state;
- member reads and later writes preserve the component, so Any taint cannot be
  laundered by an earlier call;
- local function summaries record directed parameter-to-captured-object
  may-store effects before components are merged, parameter groups that may
  store aliases, parameters written with Any, and parameters returned by alias;
- unresolved bound-method aliases preserve their receiver through callable
  origins, escaped callable objects participate as `__call__` receivers, and
  known class-scope descriptors use static/class/ordinary binding semantics;
- unresolved effects become blockers only when they are consumed by an
  Any/type-alias path, so ordinary calls do not create unrelated findings;
- functions with unknown decorators and decorated classes expose unresolved
  callable/member effects instead of trusting the pre-decoration definition;
- callable roles distinguish proven classes/functions from unresolved
  callable instances, and comprehension results propagate element and
  iterator data without treating the called class as a returned alias;
- known no-storage builtins use declarative call-effect summaries only when no
  local callable identity shadows the builtin.

The model is conservative. It does not claim that may-alias values are equal,
and normal rebinding still creates a new independent identity.

## Security Invariants

The release gate must cover direct and delayed transport through method calls,
method aliases, nested containers, `setattr`, and local helpers. The active
tree must have zero scope-flow blockers. Schema migration must retain the
schema 13 total, affected-file, layer, per-file, complexity, and recovery
ceilings exactly.

## Verification

`v143.explicit_any_call_effect_dataflow_smoke` executes the attack corpus and
requires total, layer, file, and scope-flow blockers. Unit tests also execute
the snippets, Ruff, and strict mypy, and include safe non-Any and builtin
shadowing controls, including a classmethod alias positional-binding probe.
The corpus also replaces a function and a class through decorators before the
alias transport occurs, and covers a single argument retained in a captured
global container plus an escaped callable instance retaining its argument.

## Consequences

This closes the structural call-transport gap without API-specific mutation
rules. Full interprocedural Python analysis remains out of scope; unsupported
dynamic effects that reach annotation authority fail closed.
