# ADR-015: v14.1 Module Complexity Ratchet

Status: Accepted

Date: 2026-07-17

## Context

v14.0 completed bounded-context ownership, dependency direction, and
compatibility retirement, but it did not split every large domain module. The
v14.0 quality policy registered 137 modules above 600 lines, including 37
modules above 1000 lines. Treating that inventory as closed would make the
architecture report misleading; attempting 137 unrelated extractions in one
hot release would make behavioral review unreliable.

v14.1 closes the active-tree typing debt and repository-wide Ruff debt. During
that work the registered oversized modules decreased from 124,211 aggregate
lines to 124,043 lines without adding an oversized module or oversized
function.

## Decision

ARCH-014 remains open and moves to v14.2.0. This is an explicit reapproval, not
a declaration that complexity debt is gone. `architecture-v14-quality.json`
is the machine-enforced authority and now applies all of these limits:

- no more than 137 modules may exceed 600 lines;
- no more than 37 modules may exceed 1000 lines;
- the largest module may not exceed 2,226 lines;
- aggregate lines across oversized modules may not exceed 124,043;
- each registered module retains an individual no-growth ceiling;
- no unregistered oversized module or oversized function is allowed.

The next extraction work must proceed by bounded context with behavior and
contract tests. A module may leave the debt register only by reaching 600 lines
or fewer. The policy cannot be relaxed by editing the JSON alone: this ADR is
required by the quality verifier and any later reapproval requires a new ADR.

## Consequences

v14.1 may be described as closing TYPE-002 and full-repository lint debt while
reducing and hardening ARCH-014. It must not be described as eliminating all
module complexity debt. New business work remains subordinate to the v14.2
extraction milestone.
