# ADR 0003: Persistence Authority

Status: Accepted and active since v12.17.

## Decision

SQLite will become the authoritative index for mutable workflow state, while
immutable ZIPs, reports, bindings, and public evidence remain filesystem
artifacts. Offline verifiers never depend on the local database.

## Transaction Boundary

Multi-file updates use a file unit of work, staged writes, atomic replacement,
database transactions, and cross-process locks. Migrations are versioned,
restartable, and reversible before cutover. Active v12 Store writes share a
workspace file lock; read-only offline verifiers do not take that lock.

## Consequences

The database is not public evidence. Backup, restore, migration, and crash
recovery tests are required before mutable workflows move to this authority.
Legacy JSON remains a read-compatible source during migration and is never
deleted automatically.
