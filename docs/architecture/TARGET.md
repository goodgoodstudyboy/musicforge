# Modular Monolith LTS

The v13 cutover keeps MusicForge as one local application while enforcing:

```text
interfaces -> application -> domains -> platform
```

The six bounded contexts are `creation`, `studio`, `quality`, `delivery`,
`trust`, and `program`. Cross-domain workflows are coordinated by application
services and versioned contracts, not by another Board, Center, or global base
class.

## Platform Capabilities

- Versioned evidence, package, lifecycle, verification, and error contracts.
- One ZIP-security and verification kernel.
- Composable signoff, history, reset, generation, and archive services.
- Transactional local persistence with cross-process locking and migrations.
- Evidence Graph and Policy Engine for Release and GA gates.

## Interface Shape

CLI, API, and Web modules are thin adapters over application commands and
queries. Superseded matrix/runner facades are removed. The small historical
release-check adapter remains archive-only through v13.1 so old evidence tests
stay readable.

Microservices, network queues, distributed transactions, and package-internal
self-attestation are outside the target architecture.
