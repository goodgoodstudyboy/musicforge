# ADR 0001: Modular Monolith

Status: Accepted in v12.14.

## Decision

MusicForge remains one local Python application and is organized as a modular
monolith with the dependency direction `interfaces -> application -> domains ->
platform`.

## Rationale

The product is local-first and relies on filesystem evidence, offline
verification, and atomic local workflows. Microservices would add deployment,
network, and distributed transaction failure modes without solving the current
code ownership problem.

## Consequences

Boundaries are enforced with AST tests and ratchets. Cross-domain behavior uses
application services. Existing facades remain compatible while migration is in
progress, but new business logic cannot be added to them.
