# Architecture Debt

| ID | Debt | Owner | Deadline | Blocking condition |
|---|---|---|---|---|
| ARCH-014 | Migrated domain modules listed in `architecture-v14-quality.json` exceed the default 600-line module budget. | Bounded-context owners | v14.3.0 | ADR-016 restores the reviewed v14.1.2 structure and freezes per-file ceilings plus aggregate module count, thousand-line count, largest-module size, and total oversized lines. |
| TYPE-003 | Active-tree type precision still relies on explicit `Any` annotations, especially in API route contexts and legacy-shaped domain documents. | Platform, application, interface, and bounded-context owners | v14.3.0 | Schema-12 metrics use an explicit alias data-flow kernel and freeze total, layer, affected-file, and per-file explicit-`Any` budgets; unresolved Any-relevant scope flow is blocking and no file, layer, or total budget may grow. |

Debt entries cannot be closed by deleting tests or weakening runtime
verification. Closure requires migrated production callers and differential
tests.

Closed in v12.15: ARCH-003. All active v12 Program/Continuity verifier
envelopes now use `platform.verification`; the remaining legacy-domain helper
counts are locked to a lower ratchet and may only decrease.

Closed in v12.16: active v12 lifecycle stores use `platform.lifecycle` for
history writes, reset authorization, generation rotation, and immutable-state
guards. Legacy domains remain under the no-growth architecture ratchet.

Closed in v13.0: ARCH-001, ARCH-002, ARCH-004, and ARCH-005. GA no longer
depends on release-check internals; the active production graph is acyclic;
interface/release facades meet hard limits; and schema-2 migration plus active
mutable state use the persistence authority.

Closed in v13.4: the Unified Release Program vertical slice now has physical
domain and application ownership. Its flat modules are compatibility exports,
and its active API/CLI registries dispatch through application services.

Closed in v13.5: ARCH-009 and the Program HTTP module-size portion of ARCH-010. All Python
interface modules meet the hard module limit, API inventory is explicit,
runtime and route implementations are split, and Studio uses real ES modules.

Closed in v13.6: ARCH-011. GA, Release, and Program decisions use the Evidence
Graph and Policy Engine as the authoritative gate.

Closed in v13.7: ARCH-006 and PERF-001. The expired release-check facade is
removed, current profiles reject legacy callables, and CI separates active,
legacy, full, migration, and final-SHA evidence under hard profile budgets.

v13.8 recertified the active modular LTS line while retaining the explicitly
cataloged compatibility surface for v13 consumers. The reviewer package shows
both total and active source size; compatibility retirement remains a v14.0
major-version task and cannot grow during the v13 LTS line.

## v14 Closure

`architecture-v14-migration.json` freezes the v13.8.0 inventory and
`architecture-v14-policy.json` ratchets every migration wave. v14.0 closes
ARCH-007, ARCH-008, ARCH-010, ARCH-012, and QUAL-001: active compatibility
edges, active legacy dependencies, anonymous Python parts, wildcard imports,
dynamic forwarding, direct interface Store references, oversized active
functions, duplicate ZIP helpers, and custom lifecycle algorithms are zero.
The retained flat modules are static public facades with no active implementation.

At v14.0, remaining module-size and active typing debt was fully enumerated in
`architecture-v14-quality.json` as ARCH-014 and TYPE-002. Moving a deadline,
changing a layer label, shrinking checked roots, or deleting tests does not
close a debt entry.

## v14.1 Closure

TYPE-002 is closed in v14.1. The configured mypy roots are the complete active
`platform`, `application`, `domains`, `capabilities`, and `interfaces` trees,
and both CI and release-check require zero errors. Repository-wide Ruff now
checks `song_agent`, `tests`, and `tools`; the only ignores are the documented
static public facades in `pyproject.toml`.

v14.1.1 separates TYPE-003 from TYPE-002. Zero mypy errors does not mean the
active tree is fully precise: explicit `Any` is counted by total, layer, and
file, and those budgets are locked as a v14.2 cleanup target. v14.1.2 fixes the
counter so aliases imported from `typing.Any` and `typing_extensions.Any`,
module aliases, nested annotations, and quoted annotations are included in the
same ratchet.

ARCH-014 is not closed. ADR-015 formally reapproves it through v14.2.0 after a
measured aggregate reduction. v14.1.1 adds the missing per-file no-growth
updater check so aggregate reductions cannot hide individual module growth.

## v14.2.1 Stabilization

The published v14.2.0 generated split did not satisfy the architecture plan:
generated modules were excluded from mypy and depended on runtime global
binding. ADR-016 rolls that implementation back without moving or deleting the
public tag. The restored debt is measured honestly under collector schema 4.
ARCH-014 and TYPE-003 remain open through v14.3.0; neither is described as
closed by this hotfix.

## v14.2.2 Collector Hotfix

ADR-017 supersedes only the collector portion of ADR-016. Schema 5 closes the
conditional-import and ordinary-shadowing blind spots while retaining every
v14.2.1 recovery ceiling. The corrected active tree is lower than the prior
ceiling, so the migration does not authorize any total, layer, affected-file,
or per-file increase. ARCH-014 and TYPE-003 remain open through v14.3.0.

## v14.2.3 Lambda Scope Hotfix

ADR-018 upgrades the collector to schema 6 and prevents lambda-local named
expressions from changing an outer binding. The current active tree has no such
attack pattern, so total, layer, affected-file, per-file, and recovery ceilings
remain unchanged. ARCH-014 and TYPE-003 remain open through v14.3.0.

## v14.2.4 Definition-Time Scope Hotfix

ADR-019 upgrades the collector to schema 7 and visits lambda, function,
async-function, and class definition-time expressions in their enclosing
scope. The current active tree has no definition-time alias attack pattern, so
total, layer, affected-file, per-file, and recovery ceilings remain unchanged.
ARCH-014 and TYPE-003 remain open through v14.3.0.

## v14.2.5 Class-Global Scope Hotfix

ADR-020 upgrades the collector to schema 8 and models module bindings written
from an immediately executed class body through `global`. Any-relevant dynamic
`global` or `nonlocal` flow that cannot be modeled exactly becomes a hard
quality blocker. The active tree has no such blocker and all schema 7 ceilings
remain unchanged. ARCH-014 and TYPE-003 remain open through v14.3.0.

## v14.2.6 Indirect-Target Scope Hotfix

ADR-021 upgrades the collector to schema 9. Indirect targets introduced by
`for`, `with`, and `match` are represented as uncertain rather than trusted
non-Any bindings when exact data-flow inference is unavailable. If a later
annotation depends on that binding, collection fails closed and counts the
annotation against the ratchet. The active tree has no such blocker and all
schema 8 ceilings remain unchanged. ARCH-014 and TYPE-003 remain open through
v14.3.0.

## v14.2.7 Derived Uncertain Flow Hotfix

ADR-022 upgrades the collector to schema 10. A compound right-hand-side
expression now retains an uncertain dependency instead of being reclassified
as trusted `other`; the hard blocker remains deferred until an annotation
consumes that value. The active tree has no such blocker and all schema 9
ceilings remain unchanged. ARCH-014 and TYPE-003 remain open through v14.3.0.

## v14.2.8 Object Alias Flow Hotfix

ADR-023 upgrades the collector to schema 11. Names now retain possible object
identities across assignment and branch merge, so mutation through an alias
cannot be read back through another name as trusted `other`. Ordinary rebind
disconnects the previous alias group. The active tree remains at 11,993
Explicit Any annotations, 461 affected files, and zero scope blockers; all
schema 10 ceilings remain unchanged. ARCH-014 and TYPE-003 remain open through
v14.3.0, where the collector must move to a mature semantic data-flow model.

## v14.2.9 Alias Data-Flow Kernel

ADR-024 upgrades the collector to schema 12 and moves identity, member,
unpacking, escape-origin, reachability, and taint semantics into an independent
abstract data-flow kernel. Non-direct aliases transported through literals,
attributes, subscripts, and calls can no longer launder an Any mutation.
Active measurements and all schema 11 ceilings remain unchanged. ARCH-014 and
TYPE-003 remain open through v14.3.0.
