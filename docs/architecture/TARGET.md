# v14 Domain-Cutover Modular Monolith

The v14 cutover keeps MusicForge as one local application while enforcing:

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
queries. Anonymous `part_###` modules, wildcard composition, dynamic symbol
forwarding, and interface-owned Store wiring are removed. Supported old Python
imports are explicit static facades that point inward to domain-owned
implementations and are never imported by active code.

## Compatibility Retirement

- Active code has zero imports into the compatibility layer.
- Historical v13 implementations and release checks are archive-only and run
  only in legacy/full/nightly verification.
- A public import is retained only when its compatibility decision names an
  owner, replacement, differential tests, and removal policy.
- Compatibility facades contain no business branch, persistence write,
  wildcard export, or dynamic resolver.

Microservices, network queues, distributed transactions, and package-internal
self-attestation are outside the target architecture.
