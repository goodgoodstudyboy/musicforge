# ADR 0007: Release Engineering Governance

## Decision

Release engineering is a package outside the production dependency graph.
Checks are resolved through domain providers; historical implementations live
in a read-only legacy module. Current profiles use contract, security, and thin
integration checks with hard duration budgets. Full historical coverage runs in
nightly shards.

GA receives an optional release-check executor from the interface layer rather
than importing release engineering from production code.

## Consequences

- Existing check IDs and the `song_agent.release_checks` import surface remain
  compatible through v12.20.
- Performance improvements cannot delete historical security assertions.
- Budget exceptions require a reason and expiry version.
