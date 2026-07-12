# Target Modular Monolith

The v13 target keeps MusicForge as one local application while enforcing:

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
queries. Compatibility facades only forward to new modules. The v13 cutover
removes superseded implementation paths after differential and migration tests
pass.

Microservices, network queues, distributed transactions, and package-internal
self-attestation are outside the target architecture.
