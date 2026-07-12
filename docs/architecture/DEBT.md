# Architecture Debt

| ID | Debt | Owner | Deadline | Blocking condition |
|---|---|---|---|---|
| ARCH-001 | `ga_readiness` directly invokes `release_check_runner`. This is the only approved dependency exception. | Release engineering | v12.20 | Any second exception, or broader GA dependency on release-check internals, blocks release. |
| ARCH-002 | Legacy Store/Verifier modules outside the active v12 chain contain production import cycles recorded in `architecture-baseline.json`. | Domain owners | v13.0 | New cycle or interface module in a production cycle blocks release. |
| ARCH-004 | `server.py`, `cli.py`, `webui.py`, and `release_checks.py` remain mega-files. | Interface and release engineering | v12.18/v12.20 | Any tracked file growth above v12.14 baseline blocks release. |
| ARCH-005 | Mutable-state SQLite indexing coexists with legacy JSON read compatibility until the v13 cutover. | Persistence platform | v13.0 | New mutable stores bypassing `WorkspaceLock`, or treating SQLite as public evidence, blocks release. |

Debt entries cannot be closed by deleting tests or weakening runtime
verification. Closure requires migrated production callers and differential
tests.

Closed in v12.15: ARCH-003. All active v12 Program/Continuity verifier
envelopes now use `platform.verification`; the remaining legacy-domain helper
counts are locked to a lower ratchet and may only decrease.

Closed in v12.16: active v12 lifecycle stores use `platform.lifecycle` for
history writes, reset authorization, generation rotation, and immutable-state
guards. Legacy domains remain under the no-growth architecture ratchet.
