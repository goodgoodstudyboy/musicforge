# Evidence Graph and Gate Policies

MusicForge v14.0 uses one runtime-verified Evidence Graph and declarative policy
engine for current GA and Release gates. Its implementation is owned by the
shared platform and bounded domain vertical slices. A graph node is
not a copy of a package summary. It exists only when all of these agree:

- the external package currently exists;
- the external verification report has the registered package type, valid
  integrity hash, and `passed` status;
- report ZIP hash, size, and manifest hash match the current package;
- the capability's registered runtime verifier passes now;
- required external proof files exist and satisfy the verifier's current,
  signoff, quorum, or lifecycle checks.

Integrity, current generation, runtime verification, and no-blocker checks are
platform invariants. A custom or built-in profile cannot turn them off.

## Manifest

Use `musicforge_evidence_graph_manifest` schema version 1:

```json
{
  "schema_version": 1,
  "package_type": "musicforge_evidence_graph_manifest",
  "items": [
    {
      "component_type": "unified_release_program_continuity_command_center_signoff",
      "component_id": "urp-000001",
      "evidence_type": "signed_archive",
      "generation": 1,
      "package_path": "packages/command-center-signoff.zip",
      "verification_report_path": "reports/command-center-signoff-verification.json",
      "proofs": {
        "signoff_binding": "proofs/command-center-signoff-binding.json",
        "command_center_package": "packages/command-center.zip",
        "command_center_verification_report": "reports/command-center-verification.json",
        "external_evidence_manifest": "proofs/command-center-evidence-manifest.json"
      }
    }
  ],
  "edges": [],
  "integrity_hash": "..."
}
```

Generate the hash with
`song_agent.platform.evidence_graph.builder.write_evidence_graph_manifest`.
Each identity is `(component_type, component_id, evidence_type, generation)`.
Duplicate identities, duplicate node ids, and reuse of one verification report
for different identities are blocking errors. Paths are resolved only while
building the graph and are never serialized into its public representation.
HTTP gates additionally confine all referenced files to `.musicforge/`.

## Profiles

Built-in profiles are:

- `release.standard`
- `release.audio_strict`
- `distribution.standard`
- `ga.standard`
- `ga.lts`
- `program.handoff`
- `program.continuity`

Examples:

```powershell
python -m song_agent.cli ga-check --policy ga.lts --evidence-manifest .musicforge/evidence-manifests/ga-lts.json --json
python -m song_agent.cli verify-ga-readiness-report runs/ga-readiness/ga-readiness-report.json --policy ga.lts --evidence-manifest .musicforge/evidence-manifests/ga-lts.json --json
```

The verifier requires an explicit `--policy` for every policy-bound report. It
does not trust a re-signed report to choose or downgrade its own policy.

For Release signoff API requests, use `gate_policy` and
`evidence_manifest_id`. The ID resolves to
`.musicforge/evidence-manifests/<id>.json`; arbitrary host paths are rejected.
`force=true` does not bypass policy failures.

## Legacy Migration

The historical GA `--require-*` flags are v13 compatibility aliases and emit a
deprecation warning. New gates must use a policy and an Evidence Graph manifest.
v14 removes aliases only after CLI/API differential tests prove parity and the
decision is recorded in `docs/deprecations.json`.

Runtime-verifier selection comes from the capability registry. A manifest
cannot name or replace a verifier. Capability inventory is available through
`song_agent.capabilities.capability_registry.inventory()`.
