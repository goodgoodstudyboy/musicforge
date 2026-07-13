# Architecture Review Runbook

1. Run architecture boundaries and metrics tests.
2. Inspect the actual diff for new layer violations and compatibility growth.
3. Verify new package verifiers use the Verification Kernel.
4. Verify mutable workflows use lifecycle and persistence authorities.
5. Confirm interface code delegates through registries and application APIs.
6. Confirm release-check IDs, security assertions, and hard budgets remain.
7. Review `docs/deprecations.json`; no deletion is allowed without zero active
   imports, migration evidence, and rollback coverage.
8. Run current release, latest, GA, and security profiles before release.
