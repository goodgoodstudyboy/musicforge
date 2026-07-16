# Architecture Review Runbook

1. Run architecture boundaries and metrics tests.
2. Inspect the actual diff for new layer violations and compatibility growth.
3. Verify new package verifiers use the Verification Kernel.
4. Verify mutable workflows use lifecycle and persistence authorities.
5. Confirm interface code delegates through registries and application APIs.
6. Confirm release-check IDs, security assertions, and hard budgets remain.
7. Review `docs/deprecations.json`; no deletion is allowed without zero active
   imports, migration evidence, and rollback coverage.
8. Run v14, latest, GA, full, and security profiles before release.
9. Generate the reviewer package and verify it contains no absolute workspace
   paths or secrets.
10. Run default pytest for active code, both partitions of every active-slow
    layer, and all four `legacy_*` nightly shards; do not infer compatibility
    from a fast marker exclusion.
11. Download the quality and nightly attestation artifacts for the final SHA;
    local-equivalent evidence is acceptable only when remote publication is
    unavailable and must be labeled as such.
12. Build and verify the final reviewer package. Confirm the source comparison
    exposes total, active, and compatibility lines rather than hiding the
    supported compatibility surface.
13. Confirm migration, performance, and release-alignment evidence each carry
    the same final SHA as the release-check and CI attestations.
