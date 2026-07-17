# ADR 0008: v14 Domain Cutover And Compatibility Retirement

Status: accepted in v14.0.0.

## Decision

MusicForge remains a modular monolith. Active dependencies flow from interfaces
to application services, bounded domains, and platform kernels. Creation,
Studio, Quality, Delivery, Trust, and Program own production behavior. Public
flat imports may remain only as explicit static facades and active modules may
not import them.

Verification, lifecycle, persistence, evidence graph, and policy behavior stay
in shared platform kernels. Interface composition may construct dependencies
but route/command modules cannot own Store behavior. Historical release checks
remain labeled legacy and are excluded from current profiles.

## Migration

v13.8.0 is the code and contract baseline. v14 state migration indexes mutable
workflow state only after a verified backup and prepared intent. Signed JSON,
JSONL history, bindings, anchors, checkpoints, and ZIP evidence are never
rewritten. Apply creates a bound commit marker; rollback is rehearsed in an
isolated non-empty workspace and must restore source and logical state hashes.

## Consequences

Architecture, compatibility, public contract, typing, coverage, security,
migration, and reviewer-package checks are hard release gates. Registered large
module debt expires in v14.2 under ADR-015. Any future extraction to services
requires a new ADR and may not weaken offline verification or local transaction
semantics.
