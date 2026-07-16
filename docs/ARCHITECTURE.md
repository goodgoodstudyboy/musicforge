# MusicForge Architecture

MusicForge is a local-first modular monolith. It runs as one Python process,
ships as one package, and stores mutable workspace state and immutable evidence
locally. The v12.14-v14.0 architecture program replaced the historical flat
production package without changing public CLI/API behavior or weakening
offline verification.

v14.0 is the active LTS cutover: all six bounded contexts use shared
verification, lifecycle, persistence, Evidence Graph, and policy kernels.
Retained public import facades have zero active inbound edges and no business
implementation. Historical compatibility remains separately disclosed.

## Dependency Direction

```text
interfaces -> application -> domains -> platform
```

- Interfaces: CLI, HTTP API, and Studio Web UI.
- Application: commands, queries, and cross-domain orchestration.
- Domains: creation, studio, quality, delivery, trust, and program.
- Platform: contracts, verification, lifecycle, persistence, and policy.
- Release engineering may invoke public application/interface APIs but is not a
  production dependency.

## Security Invariants

- External ZIPs, verification reports, binding summaries, and current
  generation evidence are runtime re-verified.
- Package-internal summaries cannot establish their own trust.
- Signed artifacts are immutable; reset requires approved, action-scoped,
  single-use change evidence.
- ZIP entry allow-lists, duplicate/path checks, trailing-data checks, redaction,
  and external proof binding remain hard blockers.
- Architecture refactors must preserve existing blocker behavior through
  differential tests.

## Architecture Governance

`architecture-v14-policy.json` records final module ownership and ratchets. The AST
guardrail rejects new dependency violations, production cycles, unclassified
modules, mega-file growth, and new duplicate security helpers. Runtime metrics
are written to ignored `runs/architecture/metrics.json`.

Detailed documents:

- [Current architecture](architecture/CURRENT.md)
- [Target modular monolith](architecture/TARGET.md)
- [Dependency rules](architecture/DEPENDENCY_RULES.md)
- [Architecture debt](architecture/DEBT.md)
- [ADR 0001: Modular Monolith](architecture/adr/0001-modular-monolith.md)
- [ADR 0002: Evidence Verification Kernel](architecture/adr/0002-evidence-verification-kernel.md)
- [ADR 0003: Persistence Authority](architecture/adr/0003-persistence-authority.md)
- [ADR 0004: Evidence Lifecycle Kernel](architecture/adr/0004-evidence-lifecycle-kernel.md)
- [ADR 0005: Interface Registries](architecture/adr/0005-interface-registries.md)
- [ADR 0006: Evidence Graph and Policy Engine](architecture/adr/0006-evidence-graph-policy-engine.md)
- [ADR 0007: Release Engineering Governance](architecture/adr/0007-release-engineering-governance.md)
- [ADR 0008: v14 Domain Cutover](architecture/adr/0008-v14-domain-cutover.md)
- [Architecture review runbook](ARCHITECTURE_REVIEW_RUNBOOK.md)
- [Data migration runbook](DATA_MIGRATION_RUNBOOK.md)
- [Deprecation catalog](DEPRECATIONS.md)
- [Command reference](commands/README.md)

The original songwriting workflow remains useful historical context and is
retained in [MVP_PLAN.md](MVP_PLAN.md); it is no longer the current system
architecture.
