# ADR 0004: Evidence Lifecycle Kernel

Status: Accepted and active since v12.16.

## Decision

MusicForge uses composable platform lifecycle services for hash-chained event
history, signoff transitions, Change Request authorization, reset proofs,
generation rotation, immutable snapshots, and archive construction. Domain
stores own business policy and runtime evidence verification, not lifecycle
hash algorithms.

## Compatibility

Existing signed JSON, JSONL, ZIP layouts, public commands, and blocker semantics
remain supported. Reading legacy history never rewrites it. An explicit
migration creates a separate byte-identical or schema-upgraded target, a
rollback copy, and a report containing source and target hashes.

## Security Consequences

Missing or invalid history cannot downgrade existing signed artifacts to an
unsigned state. Reset requires an approved, action-scoped, target/source-bound,
unused Change Request. A reset rotates generation, and an old generation cannot
be used as current evidence. Domain gates continue to runtime verify external
packages; the lifecycle kernel does not replace those checks.
