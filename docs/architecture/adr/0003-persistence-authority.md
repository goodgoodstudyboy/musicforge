# ADR 0003: Persistence Authority

Status: Accepted direction; implementation begins in v12.17.

## Decision

SQLite will become the authoritative index for mutable workflow state, while
immutable ZIPs, reports, bindings, and public evidence remain filesystem
artifacts. Offline verifiers never depend on the local database.

## Transaction Boundary

Multi-file updates use a file unit of work, staged writes, atomic replacement,
database transactions, and cross-process locks. Migrations are versioned,
restartable, and reversible before cutover.

## Consequences

The database is not public evidence. Backup, restore, migration, and crash
recovery tests are required before mutable workflows move to this authority.
