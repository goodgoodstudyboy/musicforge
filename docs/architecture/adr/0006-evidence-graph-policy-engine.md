# ADR 0006: Runtime Evidence Graph and Declarative Gate Policy

Status: Accepted in v12.19.

## Decision

New GA, Release, Distribution, and Program gates are expressed as a
`PolicyProfile` evaluated against an `EvidenceGraph`. Graph nodes are created
from current packages, external verification reports, independent proofs, and
the runtime verifier registered for the component capability. Package summaries
and old passed reports are not authoritative inputs by themselves.

Integrity, current-generation, runtime-verification, and no-blocker
requirements are mandatory in the policy engine. Verification reports cannot
be reused across different evidence identities. Local proof paths are not part
of the serialized graph.

## Consequences

Capability registration fixes package and verification types, verifier entry
points, required proofs, and policy membership. Manifests cannot select
arbitrary verifier functions. GA report verification rebuilds the graph and
compares its hash with the report binding. Release policy failure is a hard
gate and cannot be overridden with `force=true`.

Legacy `require_*` options remain compatibility aliases through v12, are
documented as deprecated, and cannot be extended with new independent gate
branches. v13 removes aliases that have completed policy parity and migration.
