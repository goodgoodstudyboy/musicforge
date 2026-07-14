# Architecture Debt

| ID | Debt | Owner | Deadline | Blocking condition |
|---|---|---|---|---|
| ARCH-006 | The 51-line `release_checks.py` archive adapter and legacy GA `--require-*` aliases remain for archived evidence compatibility. | Release engineering | v13.7 / v13.6 | New production imports or new behavior on these surfaces blocks release. |
| ARCH-007 | Historical flat-domain import cycles remain visible in `all_import_cycles`; active adapters still have an explicitly reported, ratcheted set of compatibility imports. | Domain owners | ongoing | Any new compatibility import, increase over the v13 baseline, or compatibility-to-platform/application reverse dependency blocks release. |
| ARCH-008 | Legacy modules outside the migrated Program vertical slice remain compatibility code rather than migrated production modules. | Architecture | v13.8 | Every active import is centralized in `application/legacy_dependencies`; direct interface/domain imports block release and the facade inventory may only shrink. |
| ARCH-010 | Physically migrated Program implementations retain pre-v13 module/function size debt, including five bounded HTTP family functions above 80 lines. | Program | v13.8 | Only files traceable to the v13.3 flat source and bounded to at most 5% migration/security-adapter growth are temporarily accepted; HTTP function debt must close in v13.6 and all remaining debt expires automatically at v13.8. |
| ARCH-011 | The migrated Release signoff application use-case still contains the legacy `require_*` policy tree. | Delivery | v13.6 | API delegation is thin in v13.5; v13.6 must replace the tree with Policy Engine evaluation and bounded gate providers. |
| ARCH-012 | 227 single-target anti-corruption facades isolate flat compatibility modules but are not final domain ownership. | Architecture | v13.8 | The active edge count is hard-ratcheted; facades cannot gain behavior and must be removed by domain migration before LTS certification. |
| PERF-001 | Archive-only release-check smoke requires four parallel nightly shards; a single-process legacy run exceeds 30 minutes. | Release engineering | v13.7 | Any current profile exceeding its hard budget, or a nightly shard exceeding 30 minutes, blocks release. |
| QUAL-001 | Historical compatibility modules still carry pre-v13 Ruff and typing debt; hard lint/type gates cover the modular core while the full compatibility inventory remains under no-growth review. | Domain owners | v13.2 | Any new violation in the modular core, expansion of an excluded scope, or removal of compatibility tests blocks release. |

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
