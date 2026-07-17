# Architecture Debt

| ID | Debt | Owner | Deadline | Blocking condition |
|---|---|---|---|---|
| ARCH-014 | Migrated domain modules listed in `architecture-v14-quality.json` exceed the default 600-line module budget. | Bounded-context owners | v14.2.0 | ADR-015 freezes per-file ceilings plus aggregate module count, thousand-line count, largest-module size, and total oversized lines. |
| TYPE-003 | Active-tree type precision still relies on explicit `Any` annotations, especially in API route contexts and legacy-shaped domain documents. | Platform, application, interface, and bounded-context owners | v14.2.0 | `architecture-v14-quality.json` freezes total, layer, and per-file explicit-`Any` budgets; no file, layer, or total budget may grow. |

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
active tree is fully precise: explicit `Any` is now counted by total, layer, and
file, and those budgets are locked as a v14.2 cleanup target.

ARCH-014 is not closed. ADR-015 formally reapproves it through v14.2.0 after a
measured aggregate reduction. v14.1.1 adds the missing per-file no-growth
updater check so aggregate reductions cannot hide individual module growth.
