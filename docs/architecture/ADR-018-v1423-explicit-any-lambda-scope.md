# ADR-018: v14.2.3 Explicit Any Lambda Scope

Status: Accepted

Date: 2026-07-21

## Context

Collector schema 5 treated a lambda body as part of its enclosing lexical
scope. A named expression such as `(Alias := int)` therefore replaced an outer
`typing.Any` alias in collector state even though Python binds that name only
inside the lambda. Subsequent outer annotations could then evade every
Explicit Any ratchet while remaining valid under mypy.

## Decision

MusicForge v14.2.3 adopts collector schema 6.

- Do not visit lambda bodies while collecting annotations. Python lambda
  parameters cannot carry annotations, so the body contains no annotation
  ownership for this collector.
- Do not allow lambda parameters, named expressions, or nested lambdas to
  mutate the enclosing collector binding state.
- Retain schema 5 control-flow imports, branch conflict handling, ordinary
  shadow bindings, quoted annotations, aliases, and module aliases.
- Keep all v14.2.1 recovery ceilings and schema 5 measured budgets unchanged.
  The schema migration cannot authorize total, layer, affected-file, or
  per-file growth.

## Verification

Unit tests and `v1423.explicit_any_lambda_scope_smoke` cover lambda parameter
shadowing, a lambda walrus assignment, nested lambdas, and 100 outer Any
annotations. The attack must remain visible to total, layer, and per-file
ratchets.

## Consequences

The active-tree Explicit Any measurement is unchanged because the current tree
contains no lambda-plus-walrus attack pattern. No product runtime, evidence
schema, or public interface changes. ARCH-014 and TYPE-003 remain open through
v14.3.0.
