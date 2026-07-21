# ADR-019: v14.2.4 Explicit Any Definition-Time Scope

Status: Accepted

Date: 2026-07-21

## Context

Collector schema 6 isolated lambda bodies but skipped the entire lambda node.
Python evaluates lambda defaults in the enclosing scope when the lambda is
created. Function decorators and defaults, and class decorators, bases, and
keywords, follow the same outer-scope rule. A named expression in one of these
locations could therefore replace an alias with `typing.Any` while the
collector retained an older non-Any binding.

## Decision

MusicForge v14.2.4 adopts collector schema 7.

- Visit lambda positional and keyword defaults in the enclosing scope, then
  skip the lambda body.
- Visit function and async-function decorators, positional defaults, and
  keyword defaults before counting the signature and entering the function
  body scope.
- Visit class decorators, bases, and keywords before entering the class body
  scope.
- Preserve Python definition order: decorators precede defaults for functions,
  and decorators precede bases and keywords for classes.
- Retain every schema 6 total, layer, affected-file, per-file, and recovery
  ceiling. The migration cannot authorize growth.

## Verification

Unit tests and `v1424.explicit_any_definition_time_scope_smoke` cover the exact
`TYPE_CHECKING` attack with 100 annotations for lambda, function, and async
function defaults. They also cover function/class decorators, class bases,
class keywords, and an order-sensitive case where a later default or base
restores a non-Any binding.

## Consequences

The active-tree measurement remains unchanged because the current source has
no matching definition-time alias attack. No product runtime, persistence,
evidence schema, or public interface changes. ARCH-014 and TYPE-003 remain open
through v14.3.0.
