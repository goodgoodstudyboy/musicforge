# Architecture Debt

| ID | Debt | Owner | Deadline | Blocking condition |
|---|---|---|---|---|
| ARCH-001 | `ga_readiness` directly invokes `release_check_runner`. This is the only approved dependency exception. | Release engineering | v12.20 | Any second exception, or broader GA dependency on release-check internals, blocks release. |
| ARCH-002 | Legacy Store/Verifier modules contain production import cycles recorded in `architecture-baseline.json`. | Verification and lifecycle platform | v12.16 | New cycle or interface module in a production cycle blocks release. |
| ARCH-003 | ZIP entry, path safety, and trailing-data helpers are duplicated across verifier modules. | Verification platform | v12.15 | Helper counts above baseline block release. |
| ARCH-004 | `server.py`, `cli.py`, `webui.py`, and `release_checks.py` remain mega-files. | Interface and release engineering | v12.18/v12.20 | Any tracked file growth above v12.14 baseline blocks release. |

Debt entries cannot be closed by deleting tests or weakening runtime
verification. Closure requires migrated production callers and differential
tests.
