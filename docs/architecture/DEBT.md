# Architecture Debt

| ID | Debt | Owner | Deadline | Blocking condition |
|---|---|---|---|---|
| ARCH-006 | The 51-line `release_checks.py` archive adapter and legacy GA `--require-*` aliases remain for archived evidence compatibility. | Release engineering | v13.7 / v13.6 | New production imports or new behavior on these surfaces blocks release. |
| ARCH-007 | Historical flat-domain import cycles remain visible in `all_import_cycles`; active adapters still have an explicitly reported, ratcheted set of compatibility imports. | Domain owners | ongoing | Any new compatibility import, increase over the v13 baseline, or compatibility-to-platform/application reverse dependency blocks release. |
| ARCH-008 | 245 legacy modules remain compatibility code rather than migrated production modules. | Architecture | v13.5 | `architecture-debt.json` assigns every module an owner, reason, target version, and live inbound count. |
| ARCH-009 | Pre-v13 CLI/API handlers exceed the v13 module/function limits. | Interfaces | v13.5 | Explicit no-growth debt; new modules are capped at 400 lines and new functions at 80/100 lines. |
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
