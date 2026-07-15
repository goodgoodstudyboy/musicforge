# Architecture Debt

| ID | Debt | Owner | Deadline | Blocking condition |
|---|---|---|---|---|
| ARCH-007 | Historical flat-domain import cycles remain visible in `all_import_cycles`; active adapters still have an explicitly reported, ratcheted set of compatibility imports. | Domain owners | ongoing | Any new compatibility import, increase over the v13 baseline, or compatibility-to-platform/application reverse dependency blocks release. |
| ARCH-008 | Legacy modules outside the migrated Program vertical slice remain compatibility code rather than migrated production modules. | Architecture | v14.0 | Every active import is centralized in `application/legacy_dependencies`; direct interface/domain imports block release and the facade inventory may only shrink. |
| ARCH-010 | Physically migrated Program implementations retain pre-v13 module/function size debt. | Program | v14.0 | Files remain traceable to the v13.3 flat source and bounded to at most 5% migration/security-adapter growth; new oversized definitions are forbidden. |
| ARCH-012 | 224 active anti-corruption edges isolate flat compatibility modules but are not final domain ownership. | Architecture | v14.0 | The active edge count is hard-ratcheted, the Program slice stays at zero, and facades cannot gain behavior. |
| QUAL-001 | Historical compatibility modules still carry pre-v13 Ruff and typing debt; hard lint/type gates cover the modular core while the full compatibility inventory remains under no-growth review. | Domain owners | v14.0 | Any new violation in the modular core, expansion of an excluded scope, or removal of compatibility tests blocks release. |

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

v13.8 recertifies the active modular LTS line while retaining the explicitly
cataloged compatibility surface for v13 consumers. The reviewer package shows
both total and active source size; compatibility retirement remains a v14.0
major-version task and cannot grow during the v13 LTS line.
