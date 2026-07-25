# ADR-027: v14.3 Security Gate Priority and Debt Sequencing

## Status

Accepted for v14.3.0.

## Context

ARCH-014 and TYPE-003 were scheduled for v14.3.0. Independent review of
schema 13 found a release-gate P1: ordinary aliases could be transported by an
unknown call before later Any mutation. Shipping debt-reduction edits in the
same change would enlarge the review surface of the security boundary and
violate the stop condition for an unresolved P1.

## Decision

v14.3.0 is limited to ADR-026, its call-effect data-flow implementation, and
release evidence. ARCH-014 and TYPE-003 move once to v14.4.0. No business
feature may enter before those debts close or a new independently reviewed ADR
changes their disposition.

The move does not increase any module, total, layer, affected-file, per-file,
complexity, coverage, performance, or recovery ceiling. The existing numeric
budgets and hashes remain authoritative.

## Consequences

v14.3.0 closes the call-effect P1 but does not claim that complexity or
Explicit Any debt is complete. v14.4.0 is a debt-only release unless review
identifies a higher-priority security defect.
