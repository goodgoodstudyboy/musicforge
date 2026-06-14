# Changelog

## v8.4.0 - 2026-06-14

### Added
- Public Trust Center Distribution Kit for bundling the Public Trust Center ZIP, delivery anchor, Anchor Registry ZIP, Anchor Transparency ZIP, current checkpoint, and verification reports into one external handoff package.
- `verify-public-trust-center-distribution-kit-package` CLI with strict/deep offline verification, nested ZIP allow-list checks, manifest/hash validation, redaction scan, and stale package protection.
- Public Trust Center CLI/API/Studio controls for Distribution Kit refresh, export, ZIP, verify, and download.
- release-check v8.4 smoke covering nested package tamper, anchor/checkpoint tamper, duplicate/path/backslash/.MusicForge/nested ZIP safety, manifest spoofing, redaction, and stale export/ZIP rejection.

### Verified
- `python -m pytest tests\test_public_trust_center_distribution_kit.py tests\test_cli_public_trust_center.py::test_public_trust_center_distribution_kit_cli tests\test_server_public_trust_center.py::test_server_public_trust_center_api tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v84_public_trust_center_distribution_kit_smoke -q`

## v8.3.1 - 2026-06-14

### Fixed
- Anchor Transparency export and ZIP creation now re-check the current Anchor Registry state before writing artifacts, so a registry revoke/supersede after report refresh blocks stale transparency packages instead of producing verifier-failed ZIPs.
- release-check v8.3 smoke now covers refresh -> registry revoke -> export/ZIP rejection.

### Verified
- `python -m pytest tests\test_public_trust_center_anchor_transparency.py tests\test_release_check.py::test_v83_public_trust_center_anchor_transparency_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --skip-tests --json`

## v8.3.0 - 2026-06-14

### Added
- Public Trust Center Anchor Transparency Ledger with checkpoint creation, export, ZIP, and offline verification.
- `verify-public-trust-center-anchor-transparency-package` CLI and Public Trust Center CLI/API/Studio controls for transparency workflows.
- Public Trust Center verifier support for `--anchor-transparency`, `--anchor-checkpoint`, `--require-anchor-transparency-current`, and `--require-anchor-checkpoint`.
- release-check v8.3 smoke covering checkpoint binding, full ledger re-sign tamper, registry summary tamper, ZIP safety, manifest spoofing, and redaction.

### Verified
- `python -m pytest tests\test_public_trust_center_anchor_transparency.py tests\test_cli_public_trust_center.py::test_public_trust_center_anchor_transparency_cli tests\test_server_public_trust_center.py::test_server_public_trust_center_api tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v83_public_trust_center_anchor_transparency_smoke -q`

## v8.2.0 - 2026-06-13

### Added
- Public Trust Center Anchor Registry for registering, publishing, revoking, exporting, zipping, and offline-verifying current delivery anchors.
- `verify-public-trust-center-anchor-registry-package` CLI plus Public Trust Center CLI/API/Studio controls for anchor registry workflows.
- Public Trust Center verifier support for `--anchor-registry`, `--require-anchor-registry-current`, `--require-anchor-published`, and `--require-anchor-not-revoked`.
- release-check v8.2 smoke covering anchor publication, PTC binding, signature tamper, current-anchor tamper, revoke checks, ZIP safety, manifest spoofing, and redaction.

### Verified
- `python -m pytest tests\test_public_trust_center_anchor_registry.py tests\test_cli_public_trust_center.py tests\test_server_public_trust_center.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v82_public_trust_center_anchor_registry_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --skip-tests --json`

## v8.1.3 - 2026-06-13

### Fixed
- Public Trust Center delivery verification now requires an external delivery anchor when delivery requirements are enabled.
- The delivery anchor binds the current Trust Center ZIP hash, manifest hash, source hash, and delivery fingerprint sidecar fingerprints, so a fully re-signed ZIP cannot pass delivery verification without the matching external anchor.
- CLI/API verification paths now pass or auto-discover the delivery anchor, and v8.1 smoke covers summary-plus-fingerprint full re-sign tampering.

### Verified
- `python -m pytest tests\test_public_trust_center.py tests\test_server_public_trust_center.py tests\test_cli_public_trust_center.py tests\test_release_check.py::test_v80_public_trust_center_smoke tests\test_release_check.py::test_v81_public_trust_center_delivery_smoke -q`

## v8.1.2 - 2026-06-13

### Fixed
- Public Trust Center delivery evidence now includes independent delivery fingerprint sidecars, so delivery summaries cannot be fully re-signed by rewriting `trust-center-report.json`, data files, HTML, manifest, and delivery summary sidecars together.
- The offline verifier now checks delivery summary sidecars against delivery fingerprint sidecars and uses those fingerprints as the source for delivery full-resign guards.
- v8.1 release-check smoke now covers the stronger payload-plus-evidence re-sign attack.

### Verified
- `python -m pytest tests\test_public_trust_center.py tests\test_release_check.py::test_v80_public_trust_center_smoke tests\test_release_check.py::test_v81_public_trust_center_delivery_smoke -q`

## v8.1.1 - 2026-06-13

### Fixed
- Public Trust Center delivery verification sidecars now bind data pages to independently re-read delivery evidence instead of trusting `trust-center-report.json` source fields.
- Explicit delivery verifier requirements no longer treat `not_configured` Distribution, Submission, or Release Operations domains as passing evidence.
- Delivery readiness now treats a missing Release ZIP as a critical readiness gap even when Release Signoff is present.

### Verified
- `python -m pytest tests\test_public_trust_center.py tests\test_release_check.py::test_v80_public_trust_center_smoke tests\test_release_check.py::test_v81_public_trust_center_delivery_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --skip-tests --json`
- `python -m song_agent.cli doctor`

## v8.1.0 - 2026-06-13

### Added
- Public Trust Center now aggregates delivery-chain evidence across Release, Distribution, Submission, Submission Evidence, and Release Operations.
- Trust Center exports now include delivery indexes, readiness/risk reports, operations package fingerprints, and independent delivery verification sidecars.
- CLI/API/verifier support delivery requirement flags for readiness, distribution, submission, submission evidence, operations signoff, operations audit, and operations reviewer pack checks.
- Studio Public Trust Center controls now show delivery-chain scope and submit delivery-inclusive refresh/verify payloads.
- release-check now includes `v81.public_trust_center_delivery_smoke` in the v8/latest/quick profiles.

### Fixed
- The Public Trust Center verifier now rejects fully re-signed forged delivery summaries by comparing data pages against independent delivery verification sidecars.

### Verified
- `python -m pytest tests\test_public_trust_center.py tests\test_server_public_trust_center.py tests\test_cli_public_trust_center.py tests\test_release_check.py::test_v80_public_trust_center_smoke tests\test_release_check.py::test_v81_public_trust_center_delivery_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --skip-tests --json`

## v8.0.2 - 2026-06-13

### Fixed
- Public Trust Center exports now include per-package verification summary sidecars derived from the underlying Registry, Portal, Transparency, and Acknowledgement verification reports.
- The Public Trust Center verifier now rejects fully re-signed forged package fingerprints even when `trust-center-report.json`, `public-package-verification-index.json`, data files, HTML, and manifest are all rewritten together.
- v8 release-check smoke now covers the stronger sidecar-inclusive full-resign forgery path.

### Verified
- `python -m pytest tests\test_public_trust_center.py tests\test_release_check.py::test_v80_public_trust_center_smoke -q`

## v8.0.1 - 2026-06-12

### Fixed
- Public Trust Center exports now include `data/public-package-verification-index.json`, a package verification index binding public package fingerprints to their verification summaries.
- The Public Trust Center offline verifier now cross-checks package-index and verification-index entries against the sidecar, so fully re-signed forged package fingerprints fail verification.
- `release-check` now includes a `v8` profile and the v8 smoke covers full-resign package fingerprint forgery.

### Verified
- `python -m pytest tests\test_public_trust_center.py tests\test_release_check.py::test_v80_public_trust_center_smoke -q`

## v8.0.0 - 2026-06-12

### Added
- Public Trust Center reports for aggregating public-safe Release, Portfolio Governance, Registry, Portal, Transparency, and Acknowledgement evidence into one read-only trust portal.
- Static Public Trust Center exports and ZIP packages with report, data indexes, HTML pages, package/verification indexes, risk register, manifest, and offline verifier.
- API, CLI, Studio controls, and release-check matrix coverage for Trust Center refresh, export, ZIP, verify, archive, and download flows.
- v8 release-check smoke covers report/data/html full-resign tamper, manifest spoofing, duplicate entries, dangerous paths, backslash entries, `.MusicForge` variants, nested ZIPs, redaction, and stale export/ZIP guards.

### Verified
- `python -m pytest tests\test_public_trust_center.py tests\test_server_public_trust_center.py tests\test_cli_public_trust_center.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v80_public_trust_center_smoke -q`
- `python -m pytest tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py tests\test_release_check.py::test_v75_release_check_matrix_smoke tests\test_release_check.py::test_v80_public_trust_center_smoke -q`

## v7.9.1 - 2026-06-12

### Fixed
- Acknowledgement Evidence ZIPs now include response verification and original response binding sidecars.
- The offline acknowledgement verifier now rejects fully re-signed forged evidence summaries by comparing public summary fields against the original accepted response binding.
- v7.9 release-check smoke now covers the stronger full-resign evidence forgery path.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_transparency_acknowledgement.py tests\test_release_check.py::test_v79_attestation_transparency_acknowledgement_smoke -q`

## v7.9.0 - 2026-06-11

### Added
- Transparency Acknowledgement Pack workflow for external confirmation of the current Transparency ZIP, manifest, and feed source.
- Acknowledgement response import now requires explicit source binding to the current pack and Transparency evidence; the importer does not fill binding fields for bare JSON responses.
- Accepted acknowledgement responses can produce public-safe Acknowledgement Evidence ZIPs, while needs_changes/rejected responses create local Change Request drafts only.
- API, CLI, Studio controls, offline verifier, and release-check matrix coverage for pack/evidence refresh, export, ZIP, verify, response import, and Change Request creation.
- v7.9 release-check smoke covers missing source binding, wrong source binding, evidence full-resign tamper, stale export/ZIP guards, duplicate/path/backslash/.MusicForge/nested package guards, manifest spoofing, and redaction.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_transparency_acknowledgement.py tests\test_server_release_portfolio_governance_attestation_transparency_acknowledgement.py tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_transparency_acknowledgement_cli_verify tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v79_attestation_transparency_acknowledgement_smoke -q`

## v7.8.1 - 2026-06-11

### Fixed
- Transparency verifier now derives expected event semantics from the package public state/source and rejects fully re-signed forged events.
- Transparency verifier now derives expected notice semantics from package state/events and rejects fully re-signed forged notices.
- v7.8 release-check smoke covers event and notice full-resign attacks.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_transparency.py tests\test_release_check.py::test_v78_attestation_transparency_feed_smoke -q`

## v7.8.0 - 2026-06-11

### Added
- Public Attestation Transparency Feed for binding current Registry, Portal, Public Attestation, and Accepted Evidence fingerprints into a public-safe event chain.
- Transparency export/ZIP package with feed, report, notices, package fingerprints, binding summaries, and offline verifier.
- API, CLI, Studio controls, and release-check matrix coverage for Transparency refresh/export/ZIP/verify flows.
- Transparency verifier covers event hash-chain tamper, data sidecar binding, duplicate/path/backslash/nested `.musicforge` guards, manifest spoofing, stale export/ZIP, package type, and redaction scans.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_transparency.py tests\test_server_release_portfolio_governance_attestation_transparency.py tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_transparency_cli_export_verify tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v78_attestation_transparency_feed_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v7.7.1 - 2026-06-11

### Fixed
- Registry and Portal exports now include `data/accepted-evidence-verification-summary.json` and bind it through their manifests.
- Registry/Portal `--require-accepted-evidence` now requires the public summary, manifest external review fields, and verification sidecar to agree, so forged accepted-evidence summaries no longer pass.
- v7.7 release-check smoke now covers forged Registry and Portal accepted-evidence summaries.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_accepted_evidence.py tests\test_release_check.py::test_v77_attestation_accepted_evidence_smoke -q`
- `python -m pytest tests\test_release_portfolio_governance_attestation_registry.py tests\test_release_portfolio_governance_attestation_portal.py -q`

## v7.7.0 - 2026-06-11

### Added
- Public Attestation Accepted Evidence workflow for turning a verified accepted Portal Review Response into a public-safe evidence record and portable ZIP.
- Registry and Portal summaries can now include accepted external review evidence, and their offline verifiers support `--require-accepted-evidence`.
- API, CLI, Studio controls, and release-check matrix coverage for Accepted Evidence refresh/export/ZIP/verify/archive flows.
- Accepted Evidence verifier covers source binding, public summary binding, duplicate/path/backslash/nested `.musicforge` guards, manifest spoofing, package type, and redaction scans.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_accepted_evidence.py tests\test_server_release_portfolio_governance_attestation_accepted_evidence.py tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_accepted_evidence_cli_export_verify tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v77_attestation_accepted_evidence_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v7.6.1 - 2026-06-10

### Fixed
- Portal Review Response import now requires external payloads to explicitly include `review_pack_id` and `review_pack_source_hash`; the importer no longer fills source-binding evidence for bare JSON responses.
- Stale Portal Review Responses continue to verify as failed and cannot create Change Request drafts.
- v7.6 release-check smoke now covers bare JSON response import rejection.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_portal_review.py tests\test_server_release_portfolio_governance_attestation_portal_review.py tests\test_release_check.py::test_v76_attestation_portal_review_response_smoke -q`

## v7.6.0 - 2026-06-10

### Added
- Public Attestation Portal Review Response workflow with exportable review packs, external response ZIP verification, response import, and needs_changes/rejected Change Request draft creation.
- Offline verifiers for Portal Review Pack and Portal Review Response packages, including manifest hash checks, source binding, duplicate/path/backslash/nested `.musicforge` package guards, package type checks, and redaction scans.
- Studio controls and API routes for refreshing/exporting/verifying Review Packs, importing responses, and creating Change Request drafts.
- `v76.attestation_portal_review_response_smoke` in the release-check matrix for latest/v7 profiles.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_portal_review.py tests\test_server_release_portfolio_governance_attestation_portal_review.py tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_portal_review_cli_export_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_attestation_portal_response_cli_json_report_out tests\test_release_check.py::test_v76_attestation_portal_review_response_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v7.5.1 - 2026-06-10

### Fixed
- `release-check` execution now fails when profile/group/since/only filters select zero checks, preventing false-green reports with `total=0`.
- `release-check --list` now preserves an empty selection as `{"checks": []}` instead of falling back to the full matrix.
- JSON summaries now include `checks_with_warnings`, `expected_warnings`, and `unexpected_warnings` so expected-warning checks are visible without marking the check failed.

### Verified
- `python -m pytest tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile latest --group audio --json`
- `python -m song_agent.cli release-check --profile latest --since 9.0 --json`

## v7.5.0 - 2026-06-10

### Added
- Release Check Verification Matrix with stable check ids, profile/group/since/only selection, per-check timing, JSON reports, timing reports, and visible progress output.
- `release-check` CLI options for `--profile`, `--group`, `--since`, `--only`, `--list`, `--json`, `--report-out`, `--timing-out`, `--fail-fast`, `--timeout-seconds`, and `--skip-tests`.
- v7.5 release-check matrix smoke covering selection, timeout reporting, expected warning recording, JSON serialization, and report redaction.

### Verified
- `python -m pytest tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py tests\test_release_check.py::test_v74_release_portfolio_governance_attestation_portal_smoke tests\test_release_check.py::test_v75_release_check_matrix_smoke -q`

## v7.4.1 - 2026-06-10

### Fixed
- Attestation Portal export now includes Registry and Public Attestation verification summary sidecars.
- Attestation Portal verifier now binds `portal-report.json`, data summaries, and manifest evidence back to the verification summary sidecars so fully re-signed Portal packages cannot point at forged Registry or Attestation fingerprints.
- v7.4 release-check smoke now covers full Portal re-signing and verification summary tamper regressions.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_portal.py tests\test_release_check.py::test_v74_release_portfolio_governance_attestation_portal_smoke -q`

## v7.4.0 - 2026-06-09

### Added
- Release Portfolio Governance Attestation Portal Snapshot for building static offline HTML/JSON portal packages from verified Public Attestation Registry evidence.
- `release-portfolio-governance-attestation-portal` and `verify-release-portfolio-governance-attestation-portal` CLI commands with current, registry, and attestation evidence requirements.
- API routes under `/api/release-portfolio-audits/<portfolio-id>/governance-attestation-portal` plus Studio controls in the Portfolio Audit workspace.
- Offline Portal ZIP verifier covering manifest/report/data binding, HTML safety, duplicate/path/backslash checks, nested package exclusion, manifest spoofing, package type, and redaction checks.
- v7.4 release-check smoke covering portal export/verify, immutable delete/rebuild guards, report/data tamper, HTML script/remote-link injection, ZIP path safety, spoofing, package type, and redaction regressions.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_portal.py tests\test_server_release_portfolio_governance_evidence_vault.py::test_server_release_portfolio_governance_evidence_vault_routes tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_portal_cli_export_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_attestation_portal_cli_json_report_out tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v74_release_portfolio_governance_attestation_portal_smoke -q`

## v7.3.1 - 2026-06-09

### Fixed
- Public Attestation Registry verifier now derives `registry-report.source` evidence from `registry.json` current entry data instead of trusting re-signed sidecar summaries.
- Public Attestation Registry verifier now checks `package-index.json` items against `registry.entries` and binds chain summary fields back to the registry/current event snapshot.
- v7.3 release-check smoke now covers fully re-signed `registry-report` and `package-index` tamper packages.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_registry.py tests\test_server_release_portfolio_governance_evidence_vault.py::test_server_release_portfolio_governance_evidence_vault_routes tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_registry_cli_lifecycle_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_attestation_registry_cli_json_report_out tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v73_release_portfolio_governance_attestation_registry_smoke -q`

## v7.3.0 - 2026-06-09

### Added
- Release Portfolio Governance Attestation Registry for registering, publishing, superseding, and revoking Public Attestation certificate entries without deleting lifecycle history.
- `release-portfolio-governance-attestation-registry` and `verify-release-portfolio-governance-attestation-registry` CLI commands with current/published registry requirement flags.
- API routes under `/api/release-portfolio-audits/<portfolio-id>/governance-attestation-registry` plus Studio controls in the Portfolio Audit workspace.
- Offline Attestation Registry ZIP verifier covering registry/report/manifest/chain integrity, current entry requirements, duplicate certificate ambiguity, nested ZIP and `.musicforge/` exclusion, unsafe/backslash paths, manifest spoofing, package type, and redaction checks.
- v7.3 release-check smoke covering register/publish/supersede/revoke lifecycle, immutable delete/rebuild guards, tamper, duplicate/path/backslash/case `.MusicForge/`, nested package, manifest spoof, package type, missing current, and redaction regressions.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation_registry.py tests\test_server_release_portfolio_governance_evidence_vault.py::test_server_release_portfolio_governance_evidence_vault_routes tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_registry_cli_lifecycle_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_attestation_registry_cli_json_report_out tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v73_release_portfolio_governance_attestation_registry_smoke -q`

## v7.2.1 - 2026-06-09

### Fixed
- Public Attestation verifier now binds `manifest.evidence_vault` and `certificate.evidence_vault` back to `attestation-report.source.evidence_vault_*` fingerprints.
- Public Attestation verifier now rejects case variants of `.musicforge/`, `nested/`, and nested `.zip` entries in public certificate packages.
- v7.2 release-check smoke now covers forged Evidence Vault fingerprints and `.MusicForge/` internal directory variants.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation.py tests\test_release_check.py::test_v72_release_portfolio_governance_attestation_smoke -q`

## v7.2.0 - 2026-06-09

### Added
- Release Portfolio Governance Public Attestation for generating lightweight certificate packages from current, deep-verified Evidence Vault evidence.
- `release-portfolio-governance-attestation` and `verify-release-portfolio-governance-attestation` CLI commands with strict Vault and Final Board requirement flags.
- API routes under `/api/release-portfolio-audits/<portfolio-id>/governance-attestation` plus Studio controls in the Portfolio Audit workspace.
- Public Attestation verifier covering certificate/report/manifest hash binding, Vault verification fingerprints, nested ZIP exclusion, duplicate/path/backslash safety, manifest spoofing, package type, and redaction checks.
- v7.2 release-check smoke covering external verification, stale Vault verification, immutable delete/rebuild guards, certificate/report tamper, nested package, duplicate/path/backslash/spoof/package-type/redaction regressions.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_attestation.py tests\test_server_release_portfolio_governance_evidence_vault.py tests\test_cli_release_operations.py::test_release_portfolio_governance_attestation_cli_export_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_attestation_cli_json_report_out tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v72_release_portfolio_governance_attestation_smoke -q`

## v7.1.1 - 2026-06-09

### Fixed
- Evidence Vault ZIP verifier now requires `vault-report.json`, `package-index.json`, `verification-index.json`, `chain-of-custody.json`, and `manifest.json` to bind the same `source_hash`.
- Evidence Vault verification now fails when the report summary is re-signed against a different source snapshot while package, verification, or chain sidecars still describe the old source.
- v7.1 release-check smoke now covers source hash mismatch tampering and uses stricter signed vault delete/rebuild assertions.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_evidence_vault.py tests\test_release_check.py::test_v71_release_portfolio_governance_evidence_vault_smoke -q`

## v7.1.0 - 2026-06-08

### Added
- Release Portfolio Governance Evidence Vault for bundling Final Board Archive, Governance Reviewer Pack, Governance Audit, Governance Archives, and optional Governance Queue packages into a portable long-term evidence package.
- `release-portfolio-governance-evidence-vault` and `verify-release-portfolio-governance-evidence-vault` CLI commands with strict, deep nested verification, Final Board, reviewer pack, audit, archive, and queue package requirement flags.
- API routes under `/api/release-portfolio-audits/<portfolio-id>/governance-evidence-vault` plus Studio controls in the Portfolio Audit workspace.
- Evidence Vault ZIP verifier covering nested package hash binding, nested verification report binding, duplicate ZIP entries, dangerous/backslash paths, manifest spoofing, wrong package type, redaction, ZIP size limits, and deep clean-room verification.
- v7.1 release-check smoke covering external deep verification, stale nested verification, signed vault immutability after deletion, nested package tamper, duplicate/path/backslash/spoof/package-type/redaction regressions.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_evidence_vault.py tests\test_server_release_portfolio_governance_evidence_vault.py tests\test_cli_release_operations.py::test_release_portfolio_governance_evidence_vault_cli_export_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_evidence_vault_cli_json_report_out tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v71_release_portfolio_governance_evidence_vault_smoke -q`

## v7.0.1 - 2026-06-08

### Fixed
- Final Board Archive and ZIP immutability now uses persisted history tied to the current signoff integrity hash, so deleting export files or the ZIP cannot bypass the signed archive rebuild guard.
- Final Board history now records signoff integrity hashes for signed/exported/zipped events while preserving compatibility with v7.0.0 history entries.
- v7.0 release-check smoke now covers signoff -> export/zip -> delete export/zip -> rebuild blocked.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_final_board.py tests\test_release_check.py::test_v70_release_portfolio_governance_final_board_smoke -q`

## v7.0.0 - 2026-06-08

### Added
- Release Portfolio Governance Final Board for binding current Governance Reviewer Pack verification, Governance Audit verification, verified Governance Archive coverage, external reviewer responses, and final signoff evidence into a portable archive.
- `release-portfolio-governance-final-board` and `verify-release-portfolio-governance-final-board` CLI commands with reviewer response, signed, reviewer pack, audit, archive, no-force, and reset-causality verification flags.
- API routes under `/api/release-portfolio-audits/<portfolio-id>/governance-final-board` plus Studio controls in the Portfolio Audit workspace.
- Final Board Archive ZIP verifier covering report/signoff/response/change-request integrity, duplicate ZIP entries, dangerous/backslash paths, manifest spoofing, wrong package type, redaction, and offline clean-room verification.
- v7.0 release-check smoke covering missing and needs_changes reviewer responses, stale Reviewer Pack verification, stale Governance Audit verification, signed archive immutability, tamper, path, spoof, package type, and redaction regressions.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_final_board.py tests\test_server_release_portfolio_governance_final_board.py tests\test_cli_release_operations.py::test_release_portfolio_governance_final_board_cli_refresh_import_sign_export_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_final_board_cli_json_report_out tests\test_release_check.py::test_v70_release_portfolio_governance_final_board_smoke -q`

## v6.9.1 - 2026-06-07

### Fixed
- Portfolio Governance Audit verification reports now record the verified Audit ZIP sha256, ZIP size, and Audit export manifest hash.
- Portfolio Governance Reviewer Pack now rejects stale Governance Audit verification reports when the Audit ZIP or export manifest has changed after verification.
- v6.9 release-check smoke now covers verify -> rebuild Governance Audit ZIP -> Reviewer Pack refresh failed until Audit verification is rerun.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_audit.py tests\test_release_portfolio_governance_reviewer_pack.py tests\test_release_check.py::test_v69_release_portfolio_governance_reviewer_pack_smoke -q`

## v6.9.0 - 2026-06-07

### Added
- Release Portfolio Governance Reviewer Pack for turning v6.8 Governance Audit Ledger evidence into a portable human review package with reviewer report, retrospective, evidence index, timeline, Markdown guide, export, ZIP, and offline verification.
- `release-portfolio-governance-reviewer-pack` and `verify-release-portfolio-governance-reviewer-pack` CLI commands with audit, signed queue, archive, no-force, and reset-causality verification flags.
- API routes under `/api/release-portfolio-audits/<portfolio-id>/governance-reviewer-pack` plus Studio controls in the Portfolio Audit workspace.
- v6.9 release-check smoke covering external clean-room verification, stale audit guard, report tamper, duplicate ZIP, dangerous/backslash entries, manifest spoof, wrong package type, and redaction.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_reviewer_pack.py tests\test_server_release_portfolio_governance_reviewer_pack.py tests\test_cli_release_operations.py::test_release_portfolio_governance_reviewer_pack_cli_refresh_export_verify tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_reviewer_pack_cli_json_report_out tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v69_release_portfolio_governance_reviewer_pack_smoke -q`

## v6.8.1 - 2026-06-07

### Fixed
- Portfolio Governance Archive verification reports now record archive ZIP sha256, ZIP size, and archive manifest hash.
- Portfolio Governance Audit now fails when a signed Governance Queue's Archive ZIP or manifest no longer matches the saved archive verification report.
- Portfolio Governance Audit ZIP verifier now requires `manifest.package_type == "release_portfolio_governance_audit"` even when manifest integrity is recomputed.
- v6.8 release-check smoke now covers stale archive verification evidence and wrong package type tampering.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_audit.py tests\test_release_portfolio_governance_signoff.py tests\test_release_check.py::test_v68_release_portfolio_governance_audit_ledger_smoke -q`

## v6.8.0 - 2026-06-06

### Added
- Release Portfolio Governance Audit Ledger for linking Portfolio Audit, Governance Queues, queue verification, signoff, archive verification, Change Requests, and reset causality into a hash-chained evidence package.
- Governance Audit export/ZIP with ledger JSONL, report JSON, portfolio/queue/signoff/archive/change-request summaries, Markdown review notes, manifest integrity, and redaction summary.
- Offline `verify-release-portfolio-governance-audit-package` CLI with signed/archive requirements, ledger chain validation, report/manifest integrity checks, reset Change Request causality checks, duplicate/path/backslash/spoof/redaction protections, and clean-room verification support.
- API routes under `/api/release-portfolio-audits/<portfolio-id>/governance-audit` plus Studio controls in the Portfolio Audit workspace.
- v6.8 release-check smoke covering passed audit export, external verification, stale export/ZIP blocking, report tamper, ledger reorder, duplicate ZIP, dangerous/backslash entries, manifest spoof, and redaction.

### Verified
- `python -m pytest tests\test_release_portfolio_governance_audit.py tests\test_server_release_portfolio_governance_audit.py tests\test_cli_release_operations.py::test_verify_release_portfolio_governance_audit_cli_json_report_out tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v66_release_portfolio_governance_queue_smoke tests\test_release_check.py::test_v67_release_portfolio_governance_signoff_smoke tests\test_release_check.py::test_v68_release_portfolio_governance_audit_ledger_smoke -q`

## v6.7.1 - 2026-06-06

### Fixed
- Portfolio Governance Queue verification reports now record the verified ZIP sha256, size, and manifest hash.
- Portfolio Governance Signoff now rejects stale queue verification reports when the Governance Queue ZIP or export manifest has changed after verification.
- Governance Archive verifier now checks that archived queue verification evidence matches the signed queue ZIP and export manifest evidence.
- v6.7 release-check smoke now covers verify -> rebuild ZIP -> signoff blocked -> reverify -> signoff passed.

### Verified
- `python -m pytest tests\test_release_portfolio_governance.py tests\test_release_portfolio_governance_signoff.py tests\test_server_release_portfolio_governance_signoff.py tests\test_release_check.py::test_v67_release_portfolio_governance_signoff_smoke -q`

## v6.7.0 - 2026-06-06

### Added
- Release Portfolio Governance Signoff for closing Governance Queues with signed queue, action-plan, execution, manual-action, source, and queue-verifier evidence.
- Portfolio Governance Change Requests for approved one-time signoff resets.
- Governance Archive export/ZIP plus offline verifier for signed queue closeout evidence, including duplicate/path/backslash/spoof/redaction/tamper checks.
- API, CLI, Studio, and release-check coverage for Governance Signoff, Change Requests, Archive ZIPs, and signed queue immutability.

### Verified
- `python -m pytest tests\test_release_portfolio_governance.py tests\test_release_portfolio_governance_signoff.py tests\test_server_release_portfolio_governance.py tests\test_server_release_portfolio_governance_signoff.py tests\test_cli_release_operations.py::test_release_portfolio_governance_queue_cli_create_run_export_verify tests\test_cli_release_operations.py::test_release_portfolio_governance_signoff_cli_sign_archive_verify tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v66_release_portfolio_governance_queue_smoke tests\test_release_check.py::test_v67_release_portfolio_governance_signoff_smoke -q`

## v6.6.1 - 2026-06-05

### Fixed
- Governance Queue export and ZIP rebuild now block stale Portfolio Audit sources instead of allowing old queues to become external evidence packages.
- v6.6 release-check smoke now covers stale export and stale ZIP rebuild guards.

### Verified
- `python -m pytest tests\test_release_portfolio_governance.py tests\test_server_release_portfolio_governance.py tests\test_release_check.py::test_v66_release_portfolio_governance_queue_smoke -q`

## v6.6.0 - 2026-06-05

### Added
- Release Portfolio Governance Queue for turning Portfolio Audit risks and recommendations into auditable safe/manual action plans.
- Safe queue execution for local refresh/export/zip/verify actions covering Reviewer Packs, Operations Audit packages, Operations Archive verification, and Portfolio evidence refresh/export/verify.
- Manual-required queue items for signoff, reset, approval, human review, provider work, external upload, process rule promotion, and portfolio policy changes.
- Governance Queue export/ZIP with `queue.json`, `action-plan.json`, `execution-report.json`, `manual-action-list.json`, source summary, action source map, Markdown action guides, manifest integrity binding, and offline verifier.
- API routes under `/api/release-portfolio-governance-queues` plus Portfolio Audit queue creation at `/api/release-portfolio-audits/<portfolio-id>/governance-queues`.
- CLI commands `release-portfolio-governance-queue` and `verify-release-portfolio-governance-package`.
- Studio Portfolio Governance Queue panel inside the Portfolio Audit workspace with create, run-safe, export, ZIP, verify, and download controls.
- v6.6 release-check smoke covering duplicate source queue guard, stale run-safe guard, post-portfolio-refresh-required evidence, action-plan tamper, execution-report tamper, duplicate ZIP, dangerous/backslash entries, manifest spoof, redaction, and external clean-room verification.

### Verified
- `python -m pytest tests\test_release_portfolio_governance.py tests\test_server_release_portfolio_governance.py tests\test_cli_release_operations.py::test_release_portfolio_governance_queue_cli_create_run_export_verify tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v66_release_portfolio_governance_queue_smoke -q`

## v6.5.0 - 2026-06-05

### Added
- Release Portfolio Audit for cross-release readiness, trend, risk, reviewer-pack, audit, archive, runbook, and change-control summaries.
- Portfolio Export/ZIP with `portfolio-audit-report.json`, trend report, risk register, release index, reviewer/audit/runbook/change summaries, Markdown review docs, and manifest integrity binding.
- Offline `verify-release-portfolio-audit-package` CLI with strict ZIP path safety, duplicate entry, manifest spoof, report/trend/risk integrity, reviewer/audit/archive requirements, and redaction scanning.
- API routes under `/api/release-portfolio-audits` for create, list, refresh, report, trends, risks, export, ZIP, verify, download, and archive.
- Studio Portfolio Audit workspace with release readiness ranking, Portfolio Risk Register, deterministic recommendations, trend report, and safe export/verify controls.
- v6.5 release-check smoke covering passed portfolio verification, external clean-room verification, report/trend/risk tamper, missing required entry, duplicate ZIP, dangerous/backslash entries, manifest spoof, redaction, and missing required Reviewer Pack evidence.

### Verified
- `python -m pytest tests\test_release_portfolio_audit.py tests\test_server_release_portfolio_audit.py tests\test_cli_release_operations.py::test_release_portfolio_audit_cli_create_export_verify tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v65_release_portfolio_audit_smoke -q`

## v6.4.1 - 2026-06-04

### Fixed
- Reviewer Pack `--require-audit` now requires a passed Operations Audit package verification report, not just Audit Report summary evidence.
- Reviewer Pack refresh now marks missing or failed Operations Audit package verification as a blocking issue.
- v6.4 release-check smoke now covers missing Audit package verification for Reviewer Pack external verification.

### Verified
- `python -m pytest tests\test_release_operations_reviewer_pack.py tests\test_release_operations_reviewer_pack_verifier.py tests\test_release_check.py::test_v64_release_operations_reviewer_pack_smoke -q`

## v6.4.0 - 2026-06-04

### Added
- Release Operations Reviewer Pack with reviewer-facing report, retrospective report, Markdown guide, evidence index, risk summary, export directory, and portable ZIP.
- Offline `verify-release-operations-reviewer-pack` CLI with strict ZIP path safety, duplicate entry, manifest spoof, report integrity, retrospective integrity, signed/archive/audit requirements, and Markdown/JSON redaction scanning.
- API routes under `/api/releases/<release>/operations/reviewer-pack` for refresh, export, ZIP, verify, and download.
- Studio Release Operations Reviewer Pack controls with Reviewer and Retrospective summary cards.
- v6.4 release-check smoke covering external verification, reviewer report tamper, retrospective tamper, missing guide, duplicate ZIP, dangerous/backslash entries, manifest spoof, and Markdown redaction.

### Verified
- `python -m pytest tests\test_release_operations_reviewer_pack.py tests\test_server_release_operations_reviewer_pack.py tests\test_cli_release_operations.py::test_release_operations_reviewer_pack_cli_create_export_verify tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v64_release_operations_reviewer_pack_smoke -q`

## v6.3.1 - 2026-06-04

### Fixed
- Operations Audit `require_archive` now requires both archive export evidence and a passed Operations Archive verification report.
- Operations Audit reports now block when an Operations Archive manifest exists without corresponding archive verification evidence.
- Operations Signoff reset history and Release reset events now persist the reset payload hash so re-sign cycles keep auditable Change Request causality.
- Audit verifier now validates reset causality across current reset records, signoff history reset records, and Release event reset records.
- v6.3 release-check smoke now covers missing archive verification and tampered historical reset Change Request evidence.

### Verified
- `python -m pytest tests\test_release_operations_audit.py tests\test_release_check.py::test_v63_release_operations_audit_ledger_smoke tests\test_server_release_operations_audit.py tests\test_cli_release_operations.py tests\test_release_operations_signoff.py tests\test_server_release_operations_signoff.py -q`

## v6.3.0 - 2026-06-04

### Added
- Release Operations Audit Ledger with hash-chained entries covering Release events, Operations Reports, Runbooks, Operations Signoff, Change Requests, Archive evidence, package verifiers, and reset causality.
- Operations Audit Export/ZIP with `operations-audit-report.json`, `operations-audit-ledger.jsonl`, Operations/Signoff/Runbook summaries, Change Request ledger, package verifier ledger, README, and manifest.
- Offline `verify-release-operations-audit-package` CLI with ledger chain checks, report/manifest/file hash checks, reset Change Request causality, required signed/archive gates, duplicate/path/backslash/spoof guards, and redaction scanning.
- API routes under `/api/releases/<release>/operations/audit` for refresh, entries, graph, export, ZIP, verify, and download.
- Studio Release Operations Audit Ledger controls.
- v6.3 release-check smoke covering audit/external verification, tamper, missing ledger, reordered ledger, duplicate ZIP, dangerous/backslash entries, manifest spoof, redaction, and applied Change Request reset evidence.

### Verified
- `python -m pytest tests\test_release_operations_audit.py tests\test_server_release_operations_audit.py tests\test_cli_release_operations.py tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v63_release_operations_audit_ledger_smoke -q`

## v6.2.1 - 2026-06-04

### Fixed
- Operations Signoff reset now requires an approved Operations Change Request; a reason alone can no longer reset archived Operations evidence.
- Reset validates Change Request integrity and marks the approved Change Request as `applied` after reset, blocking reuse of the same request.
- v6.2 release-check smoke now covers reset without Change Request and reuse of an applied Change Request.

### Verified
- `python -m pytest tests\test_release_operations_signoff.py tests\test_server_release_operations_signoff.py tests\test_cli_release_operations.py tests\test_release_check.py::test_v62_release_operations_signoff_archive_smoke -q`

## v6.2.0 - 2026-06-03

### Added
- Release Operations Signoff for archiving an accepted Operations Report after Runbook and package verifier evidence are clean.
- Operations Archive Export/ZIP with `operations-signoff.json`, `operations-report.json`, Runbook summary, verifier summaries, package ledger, change request summary, and archive manifest.
- Offline `verify-release-operations-archive-package` CLI with signed requirement, path safety, duplicate entry, manifest/file hash, signoff payload hash, report integrity, ledger hash, redaction, and spoof checks.
- Operations Change Requests for audited reset control after Operations Signoff.
- Studio Release Operations Signoff controls for sign, archive export/ZIP/verify, change request creation, and reset.
- v6.2 release-check smoke covering signoff, archive verification, external verification, stale blocking, signoff/report tamper, duplicate ZIP, dangerous/backslash entries, manifest spoof, redaction, and approved change-request reset.

### Fixed
- Release Export helper functions now reject signed or archived Release rebuilds by default; internal signoff sidecar refresh uses the explicit `allow_signed=True` channel.

### Verified
- `python -m pytest tests\test_release_operations_signoff.py tests\test_server_release_operations_signoff.py tests\test_cli_release_operations.py tests\test_release_check.py::test_v62_release_operations_signoff_archive_smoke tests\test_release_export.py tests\test_release_operations.py tests\test_release_operations_runbook.py tests\test_server_release_operations.py tests\test_server_release_operations_runbook.py tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls -q`

## v6.1.1 - 2026-06-03

### Fixed
- Release Operations Runbook safe export and ZIP actions now respect signed or archived Release immutability before rebuilding metadata, Release Export, or Release ZIP evidence.
- Distribution Runbook export and ZIP actions now respect signed target immutability instead of bypassing Distribution route-level guards.
- v6.1 release-check smoke now covers signed Release/Distribution mutation blocking and verifies existing export ZIP bytes remain unchanged.

### Verified
- `python -m pytest tests\test_release_operations_runbook.py tests\test_server_release_operations_runbook.py tests\test_cli_release_operations.py::test_release_operations_runbook_cli_create_export_verify tests\test_release_check.py::test_v61_release_operations_runbook_smoke -q`

## v6.1.0 - 2026-06-03

### Added
- Release Operations Runbook store for turning Operations Dashboard `next_actions` into an audited local action queue.
- Runbook execution supports only safe refresh/export/zip/verify actions; signoff, reset, submitted/accepted status changes, provider work, uploads, and manual reviews remain `manual_required`.
- Runbook stale guard binds execution to the Operations Report source hash and blocks safe execution with 409 after Release state changes.
- Runbook Export/ZIP with `runbook.json`, `execution-report.json`, before/after Operations reports, `README.txt`, and `runbook-manifest.json`.
- Offline `verify-release-operations-runbook-package` CLI with unsafe path, raw backslash entry, duplicate entry, manifest spoof, file hash, integrity, stale, and redaction checks.
- Studio Release Operations Runbook controls for create, run safe actions, refresh stale status, export, ZIP, verify, and download.
- v6.1 release-check smoke covering manual-required non-execution, stale 409, external package verification, tamper, duplicate ZIP, dangerous path, backslash path, manifest spoof, and redaction guards.

### Verified
- `python -m pytest tests\test_release_operations_runbook.py tests\test_server_release_operations_runbook.py tests\test_release_check.py::test_v61_release_operations_runbook_smoke tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls -q`

## v6.0.0 - 2026-06-03

### Added
- Release Operations Dashboard for read-only readiness aggregation across Release, Metadata, Audio, Rights, Format Decision, Distribution, Submission, Submission Evidence, package exports, and verifier summaries.
- Operations API routes under `/api/releases/<release>/operations` for overview, refresh, export, ZIP, download, and verifier checks without signing, resetting, uploading, or mutating existing delivery evidence.
- Portable Operations Export/ZIP with `operations-report.json`, `readiness-summary.json`, `evidence-graph.json`, `verifier-summaries.json`, `README.txt`, and `operations-manifest.json`.
- Offline `verify-release-operations-package` CLI with ZIP path safety, duplicate entry detection, manifest/file hash checks, report integrity checks, stage requirement checks, and redaction scanning.
- Studio Release Operations panel showing current stage, blockers, warnings, stage progress, next actions, and Operations export/verify controls.
- v6.0 release-check smoke covering submission-ready to accepted stage progression, external Operations package verification, report tamper, duplicate ZIP entry, and redaction guards.

### Verified
- `python -m pytest tests\test_release_operations.py tests\test_server_release_operations.py tests\test_cli_release_operations.py tests\test_release_check.py::test_v60_release_operations_dashboard_smoke tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v5.9.0 - 2026-06-02

### Added
- Submission Evidence Archive for signed Submission Packages, including platform receipt, feedback, needs-changes, acceptance, rejection, round, attachment, report, export, ZIP, and signoff evidence.
- Existing Submission external status APIs now create evidence records behind `record-submission`, `record-feedback`, and `accepted` while preserving the old API shape.
- Submission Evidence API routes under `/api/releases/<release>/submissions/<submission>/evidence`, including attachment upload, report refresh, export/ZIP, verifier, signoff, and reset.
- Offline `verify-submission-evidence-package` CLI with ZIP path safety, duplicate entry detection, manifest hash checks, signoff sidecar checks, evidence/report/attachment integrity checks, nested Submission Package deep verification, and redaction scanning.
- Studio Submission Evidence controls for report refresh, evidence export/ZIP/verify/sign/reset.
- v5.9 release-check smoke covering upload-only attachment safety, automatic evidence from legacy status endpoints, evidence signoff immutability, external verifier, and signoff/report/duplicate ZIP tamper guards.

### Security
- Evidence attachments reject `source_path`, `local_path`, `file_path`, unsafe filenames, unsupported content types, oversized uploads, and text attachments containing sensitive values.
- Evidence records bind signed Submission Package source snapshots, distribution package hashes, submission signoff hashes, item snapshot hashes, and attachment hashes.

### Verified
- `python -m pytest tests\test_submission_evidence.py tests\test_server_submission_evidence.py tests\test_cli_verify_submission_evidence.py tests\test_release_check.py::test_v59_submission_evidence_archive_smoke -q`

## v5.8.1 - 2026-06-02

### Fixed
- Rights Clearance reports now aggregate required source provenance from each Release track's Project version, Final Export, job artifacts, context pack, editor clip/template metadata, and provider provenance summaries.
- `require_rights_clearance=true` now blocks signoff when required asset/reference/context/editor/provider sources are not explicitly covered by cleared, owned, public-domain, or waived rights source usages.
- Hidden, missing, or stale asset/reference/context pack sources now fail the rights report instead of allowing original-only declarations to pass.
- v5.8 release-check smoke now covers a project with `reference_refs`: original-only rights fails with 409, then passes only after the reference source is manually cleared.

### Verified
- `python -m pytest tests\test_rights_clearance.py tests\test_release_check.py::test_v58_rights_clearance_smoke -q`

## v5.8.0 - 2026-06-02

### Added
- Rights Clearance Workbench for Release parties, track contributor splits, source usage declarations, manual clearance reviews, current reports, and integrity hashes.
- Release Signoff gate `require_rights_clearance=true`, blocking missing, stale, tampered, non-manual, incomplete split, uncleared source, metadata-credit mismatch, or redaction-polluted rights evidence.
- Release Export sidecars under `rights/` plus offline `verify-release --require-rights-clearance` validation.
- Distribution and Submission package rights summaries, signoff gates, and offline `verify-distribution-package --require-rights-clearance` / `verify-submission-package --require-rights-clearance`.
- Studio Release workspace controls for creating rights parties, saving track rights, accepting manual clearance, refreshing the rights report, and requiring rights clearance at signoff.
- v5.8 release-check smoke covering missing-rights block, manual clearance pass, Release/Distribution/Submission signoff, offline verification, and rights report tamper detection.

### Verified
- `python -m pytest tests\test_rights_clearance.py tests\test_release_check.py::test_v58_rights_clearance_smoke tests\test_cli_verify_release.py tests\test_cli_verify_distribution.py tests\test_cli_verify_submission.py -q`

## v5.7.1 - 2026-06-01

### Fixed
- Distribution Format Decision gates now enforce target role compatibility: delivery targets such as `demo_pitch` require selected profiles, while `internal_archive` may use archive profiles.
- Distribution Export and `verify-distribution-package --require-format-decision` now recompute target role coverage instead of trusting selected-plus-archive coverage.
- v5.7 release-check smoke now covers `demo_pitch` archive-only rejection and `internal_archive` archive-profile acceptance.

### Verified
- `python -m pytest tests\test_format_decisions.py tests\test_release_check.py::test_v57_release_format_decision_smoke -q`

## v5.7.0 - 2026-06-01

### Added
- Release Format Decision Workbench for comparing required encoded audio profiles, creating scoring matrices, recommendations, and manual decision reports.
- Release Signoff gate `require_format_decision=true`, requiring selected delivery profiles to be covered by a current, integrity-checked decision report.
- Release Export sidecars under `format-decision/` plus offline `verify-release --require-format-decision` validation.
- Distribution Target format decision summaries, Distribution Signoff gate support, Distribution Export sidecar evidence, and `verify-distribution-package --require-format-decision`.
- Studio Release workspace controls and CLI `format-decision` workflow for creating sessions, selecting/archive/rejecting profiles, activating reports, and writing report files.
- v5.7 release-check smoke covering selected/archive/rejected profiles, signoff blocking for non-selected required profiles, export evidence, external verification, and report tamper detection.

### Verified
- `python -m pytest tests\test_format_decisions.py tests\test_server_audio_encoding.py tests\test_distribution_encoded_audio.py tests\test_release_check.py::test_v57_release_format_decision_smoke tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_webui.py::test_webui_contains_runtime_tabs -q`

## v5.6.1 - 2026-06-01

### Fixed
- Release Signoff `require_encoded_audio_review=true` now accepts full Release Export encoded acceptance evidence when the signoff only requires a profile subset such as `mp3_320`.
- Release encoded audio acceptance export gate now verifies required profile/track coverage from the exported sidecar instead of comparing the full-export summary hash to a profile-scoped gate summary.
- `verify-release --require-encoded-audio-review --require-audio-formats ...` now honors explicit required profile subsets instead of treating every exported encoded profile as required.
- v5.6 release-check smoke now covers MP3+FLAC full export with MP3-only encoded audio review signoff.

### Verified
- `python -m pytest tests\test_server_audio_encoding.py tests\test_release_check.py::test_v56_encoded_audio_acceptance_smoke -q`

## v5.6.0 - 2026-05-31

### Added
- Encoded Audio Acceptance store for per-profile health reports, per-track listening reviews, source hashes, integrity hashes, stale checks, and redaction scanning.
- Release encoded audio acceptance APIs plus CLI summary command for refreshing health and writing acceptance reports.
- Release Signoff gate `require_encoded_audio_review=true`, blocking missing, synthetic-only, stale, tampered, duplicate, or non-manual encoded review evidence.
- Release Export sidecars for `encoded-audio-acceptance-summary.json`, `encoded-audio-health/`, and `encoded-audio-reviews/`, with `verify-release --require-encoded-audio-review` offline validation.
- Distribution Signoff and Export support for encoded audio acceptance evidence under `encoded-audio-acceptance/`, with `verify-distribution-package --require-encoded-audio-review` offline validation.
- Studio controls for encoded audio acceptance health refresh and encoded review signoff requirement.
- v5.6 release-check smoke covering missing review blocks, synthetic-only rejection, manual accepted review, Release/Distribution export evidence, offline verification, encoded file tamper, review sidecar tamper, and fake-runner rejection.

### Fixed
- Deep Windows export paths now use a shorter atomic JSON temp filename, avoiding sidecar write failures in nested Release/Distribution package directories.

### Verified
- `python -m pytest tests\test_audio_encoding.py tests\test_server_audio_encoding.py tests\test_distribution_encoded_audio.py tests\test_encoded_audio_acceptance.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls tests\test_release_check.py::test_v55_distribution_audio_formats_smoke tests\test_release_check.py::test_v56_encoded_audio_acceptance_smoke -q`

## v5.5.1 - 2026-05-30

### Fixed
- Public audio encoder config and Studio no longer persist `fake_runner`; fake encoder evidence is rejected by encoded audio gates and offline verifiers.
- Distribution layout now packages required encoded audio profiles even when `primary_audio_format` is omitted.
- Distribution package verifier now requires encoded layout entries and per-track/profile package evidence when `--require-encoded-audio` is used.

### Verified
- `python -m pytest tests\test_audio_encoding.py tests\test_server_audio_encoding.py tests\test_distribution_encoded_audio.py tests\test_distribution_layout.py tests\test_release_check.py::test_v55_distribution_audio_formats_smoke -q`

## v5.5.0 - 2026-05-29

### Added
- Distribution Audio Formats with built-in `wav_master`, `mp3_320`, `mp3_v0`, `flac_lossless`, and `aac_256` encoding profiles.
- Local audio encoder config plus deterministic fake runner support for tests and release-check without requiring real FFmpeg.
- Release encoded audio API/CLI for rendering, verifying, resetting, downloading per-track outputs, and managing profile evidence.
- Release Signoff gate `require_encoded_audio=true`, including stale Release Export detection after encoded audio is rendered.
- Release Export and `verify-release --require-encoded-audio --require-audio-formats ...` support for encoded audio summaries.
- Distribution Target audio format options, encoded layout packaging, encoded sidecar manifests, and `verify-distribution-package --require-encoded-audio`.
- Studio controls for encoded audio render/verify/reset, encoded signoff requirement, and Distribution primary audio format selection.
- v5.5 release-check smoke covering missing encoded signoff block, fake-runner MP3/FLAC render, stale export guard, signed-release mutation guard, Distribution MP3 package verification, and fake MP3 tamper failure.

### Verified
- `python -m pytest tests\test_audio_encoding.py tests\test_server_audio_encoding.py tests\test_distribution_encoded_audio.py tests\test_release_check.py::test_v55_distribution_audio_formats_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v5.4.1 - 2026-05-29

### Fixed
- Release Signoff `require_mastering_qa=true` now requires a selected mastered candidate with accepted manual A/B review; analysis-only mastering no longer satisfies the gate.
- Release Signoff now rejects stale Release Exports when current Mastering QA evidence was created or selected after export generation.
- `verify-release --require-mastering` now requires selected candidate evidence instead of accepting a passed analysis summary alone.
- v5.4 release-check smoke now covers analysis-only signoff rejection and export-before-mastering stale rejection.

### Verified
- `python -m pytest tests\test_mastering_qa.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v54_mastering_qa_smoke -q`

## v5.4.0 - 2026-05-29

### Added
- Mastering QA with built-in Mastering Profiles, Release-level analysis, deterministic gain/trim planning, mastered candidate rendering, manual candidate review, and selected mastered WAV evidence.
- Release Signoff gate `require_mastering_qa=true`, blocking missing, stale, tampered, or non-manual mastering evidence.
- Release Export now uses the selected mastered candidate WAV as each track's packaged `song.wav` and writes `mastering/summary.json`, analysis, plan, selected candidate, and mastered track WAV evidence.
- `verify-release --require-mastering` validates Mastering QA summaries, selected candidate integrity, manual review evidence, and packaged mastered WAV hashes offline.
- Studio Release workspace controls for Mastering QA analysis, plan creation, candidate rendering, manual acceptance, selection, reset, and signoff requirement.
- v5.4 release-check smoke covering missing mastering signoff block, profile lookup, analyze/plan/candidate/review/select, export, signoff, external verification, signed-release mutation block, and ZIP tamper failures.

### Verified
- `python -m pytest tests\test_mastering_qa.py tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check`

## v5.3.1 - 2026-05-28

### Fixed
- Release Signoff `require_audio_revision_closeout=true` now hard-blocks newly added active `needs_fix`/`rejected` audio review markers that are not covered by a non-stale Audio Revision issue/session.
- Audio Revision candidate preview and apply now use the configured renderer path for real WAV output; renderer failures leave candidates unreviewable/unselectable/unappliable instead of writing placeholder audio.
- Audio Revision apply now creates child Project Versions with `audio_revision_mix_edit`.
- Release Export now keeps selected candidates/issues from multiple Audio Revision sessions under session-prefixed filenames so later sessions do not overwrite earlier evidence.
- `verify-release --require-audio-revisions` now accepts multi-session revision history when at least one applied revision candidate matches the current track version, while still failing tampered or mismatched evidence.

### Verified
- `python -m pytest tests\test_audio_revision.py tests\test_release_check.py::test_v53_audio_revision_workbench_smoke -q`

## v5.3.0 - 2026-05-28

### Added
- Audio Revision Workbench for Release tracks, turning per-track audio review markers into auditable revision issues and deterministic mix candidates.
- Candidate preview rendering with MIDI/WAV, audio health, stem health, manual A/B review, single-candidate selection, and apply-as-child-version flow.
- Audio revision session closeout with recheck evidence, high/critical issue blockers, force-close guardrails, and Release Signoff `require_audio_revision_closeout=true`.
- Release Export and `verify-release --require-audio-revisions` evidence for sessions, issues, selected candidates, closeouts, hashes, and applied Release Track version matching.
- Studio Release workspace panel for creating revision sessions, listing issues/candidates, reviewing/selecting/applying candidates, refreshing recheck status, and closing sessions.
- v5.3 release-check smoke covering marker-to-issue, candidate generation, artifact path pollution, manual candidate review, apply, stale old review, recheck, closeout, signoff, external verify, and ZIP candidate tamper.

### Fixed
- Per-track audio review evidence now separates current track-version reviews from historical reviews so an old stale `needs_fix` review does not block the newly applied and rechecked Release track.
- Audio revision closeout refuses `force=true` when stale/tampered evidence or unresolved high/critical issues are present.

### Verified
- `python -m pytest tests\test_audio_revision.py tests\test_release_check.py::test_v53_audio_revision_workbench_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m pytest tests\test_audio_review_evidence.py tests\test_release_audio.py tests\test_mix_controls.py tests\test_server_mix_controls.py -q`

## v5.2.1 - 2026-05-27

### Fixed
- Release Signoff `require_current_mix_state=true` now hard-blocks stale `mix-state.json` evidence when the current Final Export `song-plan.json` or `song.mid` no longer matches the mix source hashes.
- `verify-release` now validates packaged `mix-state.json` against the ZIP's own `song-plan.json` and `song.mid` when current mix evidence is required.

### Added
- Server and v5.2 release-check regressions for tampered MIDI/current mix source mismatch.

### Verified
- `python -m pytest tests\test_server_mix_controls.py tests\test_release_check.py::test_v52_arrangement_mix_controls_smoke -q`

## v5.2.0 - 2026-05-26

### Added
- Arrangement Mix Controls with Mix State, Mix Patch, preview MIDI rendering, and apply-to-child-version flow.
- Track volume, pan, mute/solo, velocity scale, and section-level automation support with MIDI pan/volume controller output.
- Mix stem rendering plus `stems/stem-health.json` evidence copied through Final Export and Release Export.
- Release Audio Review marker-to-Mix-Patch draft endpoint.
- Release Signoff gates for `require_current_mix_state` and `require_stem_audio_health`.
- Studio Mix Board controls and Release signoff checkboxes for mix/stem evidence.
- v5.2 release-check smoke covering preview, apply, stem health, marker draft, signoff, external verification, and stem-health tamper detection.

### Verified
- `python -m pytest tests\test_mix_controls.py tests\test_server_mix_controls.py tests\test_release_check.py::test_v52_arrangement_mix_controls_smoke tests\test_webui.py::test_webui_contains_mix_board_controls tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_server_audio_reviews.py tests\test_release_verifier.py -q`

## v5.1.0 - 2026-05-26

### Added
- Per-track Release Audio Review evidence store with source hash, integrity hash, stale detection, marker-to-section mapping, and marker-to-ReviewTask feedback.
- Release Audio Review API and Studio Audio Review Board for creating manual track reviews and refreshing coverage summaries.
- Release Signoff gate `require_per_track_audio_review=true`, requiring every Release track to have current manual accepted WAV review evidence.
- Release Export now includes `audio-reviews/summary.json` and per-review JSON files in the manifest and ZIP.
- `verify-release --require-audio --require-human-review` now validates per-track audio review hashes and WAV hash matching offline.
- v5.1 release-check smoke covering missing review, synthetic-only review, successful signoff, portable verification, tamper detection, and marker task creation.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v5.0.0 - 2026-05-25

### Added
- Real Audio Baseline: deterministic WAV health checks for duration, format, silence, RMS, clipping, and integrity hash.
- Renderer Profile store/API/CLI with legacy `.musicforge/renderer.json` compatibility and redacted public summaries.
- Acceptance reports now include WAV audio health summaries and manual WAV review evidence binding.
- Release Audio QA endpoint and Release Signoff gates for `require_audio_health`, `require_human_audio_review`, and current audio evidence.
- Release Export includes `audio-summary.json`, and `verify-release --require-audio --require-human-review` validates portable audio evidence.
- `audio-health` CLI and v5.0 release-check smoke.

### Verified
- `python -m pytest tests\test_audio_health.py tests\test_music_acceptance.py tests\test_release_audio.py tests\test_release_verifier.py tests\test_release_check.py::test_v50_real_audio_baseline_smoke -q`

## v4.14.1 - 2026-05-24

### Fixed
- Planning Rule Impact Reports now bind derived evidence with `integrity_hash`, including status, summary, adoption, before/after metrics, risk drift, samples, and warnings.
- Release Signoff with `require_planning_rule_impact=true` now hard-blocks tampered Impact Reports, even when `force=true`.

### Added
- Store, server, and release-check regressions for tampered Impact Report derived conclusions.

### Verified
- `python -m pytest tests\test_planning_rule_impact.py tests\test_server_planning_rule_impact.py tests\test_cli_planning_rule_impact.py tests\test_release_check.py::test_v414_planning_rule_impact_smoke -q`

## v4.14.0 - 2026-05-24

### Added
- Planning Rule Impact Monitoring reports for active rule adoption, Outcome Review effectiveness, risk drift, and rollback recommendations.
- Planning Rule Impact API, CLI commands, Studio panel, Project/Release/Final Export summaries, and Release Signoff evidence.
- Release Signoff gate for `require_planning_rule_impact=true`, including stale hard-blocks and force-audited rollback recommendations.
- release-check v4.14 smoke covering impact export summaries, signoff, stale guard, rollback recommendation handling, and redaction.

### Verified
- `python -m pytest tests\test_planning_rule_impact.py tests\test_server_planning_rule_impact.py tests\test_cli_planning_rule_impact.py tests\test_release_check.py::test_v414_planning_rule_impact_smoke -q`

## v4.13.1 - 2026-05-24

### Fixed
- Planning Rule Governance Release Signoff now verifies both frozen ruleset payload integrity and `version.json` source evidence integrity.
- Tampering `promoted_from` or `approval` in a Planning Rule Version now blocks `require_planning_rule_governance=true` signoff.

### Added
- Store, server, and release-check regressions for tampered Planning Rule Version evidence.

### Verified
- `python -m pytest tests\test_planning_rule_governance.py tests\test_server_planning_rule_governance.py tests\test_release_check.py::test_v413_planning_rule_governance_smoke -q`

## v4.13.0 - 2026-05-22

### Added
- Planning Rule Governance store for promotion requests, approval, active rule versions, frozen ruleset payloads, and rollback.
- Planning Rule Governance API, CLI commands, Studio panel, Project/Release/Final Export summaries, and Release Signoff evidence.
- New Acceptance Fix Plans now record active planning rule version evidence, or explicit `legacy_default` when no active version exists.
- release-check v4.13 smoke covering promotion, active version traceability, signoff gate, stale evidence guard, rollback, and redaction.

### Verified
- `python -m pytest tests\test_planning_rule_governance.py tests\test_server_planning_rule_governance.py tests\test_cli_planning_rule_governance.py tests\test_release_check.py::test_v413_planning_rule_governance_smoke -q`

## v4.12.0 - 2026-05-21

### Added
- Planning Rule Set and Planning Rule Simulation stores for deterministic Outcome Review replay.
- Planning ruleset/simulation API, CLI, Studio panel, Project/Release/Final Export summaries, and Release Signoff evidence.
- release-check v4.12 smoke covering synthetic-only penalty, export summaries, signoff gate, stale guard, and redaction.

### Verified
- `python -m pytest tests\test_planning_rule_simulation.py tests\test_server_planning_rule_simulation.py tests\test_cli_planning_rule_simulation.py tests\test_release_check.py::test_v412_planning_rule_simulation_smoke -q`

## v4.11.1 - 2026-05-21

### Fixed
- Outcome Review no longer treats synthetic-only recheck acceptance as manual confirmation.
- Fix Sprint delta reports now carry recheck manual/synthetic accepted and review counts for downstream evidence.

### Added
- Store, API, and release-check regressions for synthetic-only recheck warnings.

### Verified
- `python -m pytest tests\test_acceptance_fix_sprints.py tests\test_acceptance_fix_plan_reviews.py tests\test_server_acceptance_fix_plan_reviews.py tests\test_release_check.py::test_v411_fix_plan_outcome_review_smoke -q`

## v4.11.0 - 2026-05-21

### Added
- Acceptance Fix Plan Outcome Review reports for used Fix Plans and closed Fix Sprints.
- Deterministic plan effectiveness, ranking alignment, KB helpfulness, item outcome, and calibration hint summaries.
- API, CLI, Studio controls, Project/Release/Final Export summaries, and Release Signoff evidence for outcome reviews.
- release-check v4.11 smoke covering refresh, export summaries, signoff gate, stale guard, and redaction.

### Verified
- `python -m pytest tests\test_acceptance_fix_plan_reviews.py tests\test_server_acceptance_fix_plan_reviews.py tests\test_cli_acceptance_fix_plan_review.py tests\test_release_check.py::test_v411_fix_plan_outcome_review_smoke tests\test_webui.py::test_webui_contains_acceptance_workspace -q`

## v4.10.1 - 2026-05-21

### Fixed
- Acceptance Fix Plans can now create only one Fix Sprint; repeated create-fix-sprint attempts return 409 without overwriting execution evidence.

### Added
- Store, API, CLI, and release-check regressions for duplicate Fix Sprint creation from the same Fix Plan.

### Verified
- `python -m pytest tests\test_acceptance_fix_planning.py tests\test_server_acceptance_fix_planning.py tests\test_cli_acceptance_fix_plan.py tests\test_release_check.py::test_v410_knowledge_assisted_fix_planning_smoke -q`

## v4.10.0 - 2026-05-21

### Added
- Knowledge-assisted Acceptance Fix Plan store, API, CLI, and Studio controls for ranking Acceptance Analytics recommendations with KB evidence before creating a Fix Sprint.
- Fix Plan source hashes and stale guards covering analytics recommendations and referenced KB entry summaries.
- Project Export, Release Export, Final Export, and Release Signoff summaries for Acceptance Fix Plan evidence.
- release-check v4.10 smoke covering plan creation, KB matching, Fix Sprint creation, stale KB evidence blocking, hidden KB exclusion/inclusion, export summaries, and redaction.

### Verified
- `python -m pytest tests\test_acceptance_fix_planning.py tests\test_server_acceptance_fix_planning.py tests\test_cli_acceptance_fix_plan.py tests\test_release_check.py::test_v410_knowledge_assisted_fix_planning_smoke tests\test_webui.py::test_webui_contains_acceptance_workspace -q`

## v4.9.1 - 2026-05-21

### Fixed
- Hidden Acceptance KB entries now stay hidden across refreshes for the same source fingerprint.

### Added
- Store, API, and release-check regressions for hide -> refresh preserving hidden KB entry visibility.

### Verified
- `python -m pytest tests\test_acceptance_kb.py tests\test_server_acceptance_kb.py tests\test_cli_acceptance_kb.py tests\test_release_check.py::test_v49_acceptance_knowledge_base_smoke -q`

## v4.9.0 - 2026-05-21

### Added
- Acceptance Knowledge Base store, API, and CLI for turning closed, non-stale Acceptance Fix Sprints into local issue/fix/outcome entries.
- Deterministic effectiveness scoring, issue/style/song patterns, KB search, and advisory recommendations that never create tasks or apply edits automatically.
- Studio Acceptance Knowledge Base panel with summary, issue patterns, style patterns, and recommendation controls.
- Project Export, Release Export, Final Export, and Release Signoff now include sanitized KB summaries only.
- release-check v4.9 smoke covers KB refresh, entry generation, search, recommendation, export summaries, and redaction.

### Verified
- `python -m pytest tests\test_acceptance_kb.py tests\test_server_acceptance_kb.py tests\test_cli_acceptance_kb.py tests\test_release_check.py::test_v49_acceptance_knowledge_base_smoke tests\test_webui.py::test_webui_contains_acceptance_workspace -q`

## v4.8.1 - 2026-05-20

### Fixed
- Stale Acceptance Fix Sprints can no longer be force-closed; `force=true` only bypasses closeout checks, not source analytics integrity.
- Release Signoff rechecks Acceptance Fix Sprint stale state, so closed-but-stale Fix Sprint evidence is reported as failed when `require_acceptance_fix_sprint=true`.

### Added
- Store, API, and release-check regressions for stale Fix Sprint force close returning 409.

### Verified
- `python -m pytest tests\test_acceptance_fix_sprints.py tests\test_server_acceptance_fix_sprints.py tests\test_release_check.py::test_v48_acceptance_fix_sprint_smoke -q`

## v4.8.0 - 2026-05-20

### Added
- Acceptance-driven Fix Sprint store, API, and CLI for turning fresh Acceptance Analytics recommendations into audited fix items, ReviewTask creation, recheck Acceptance Suites, delta reports, and closeout reports.
- Studio Acceptance Fix Sprints controls for creating a sprint from analytics, creating ReviewTasks, creating recheck suites, refreshing deltas, and closing the loop.
- Project Export, Final Export, and Release Export now write Acceptance Fix Sprint summaries; Release Signoff can require closed Fix Sprint evidence with `require_acceptance_fix_sprint=true`.
- release-check v4.8 smoke covers Fix Sprint creation, duplicate ReviewTask binding, recheck/delta/closeout, Release Export/Signoff evidence, and stale source guard returning 409.

### Fixed
- Acceptance Analytics source state now excludes downstream `acceptance_fix_sprint` ReviewTasks and non-suite-scope recheck suites, so a Fix Sprint does not make its own source report stale while still blocking genuinely stale source reports before task creation.

### Verified
- `python -m pytest tests\test_acceptance_fix_sprints.py tests\test_server_acceptance_fix_sprints.py tests\test_cli_acceptance_fix_sprint.py tests\test_release_check.py::test_v48_acceptance_fix_sprint_smoke -q`

## v4.7.1 - 2026-05-20

### Fixed
- Stale Acceptance Analytics reports can no longer create recommendation ReviewTasks. Users must refresh analytics before turning a recommendation into a task.

### Added
- Server regression and release-check v4.7 smoke coverage for stale recommendation create returning 409 while fresh creation and duplicate open-task detection still work.

### Verified
- `python -m pytest tests\test_server_acceptance_analytics.py::test_acceptance_analytics_recommendation_create_review_task tests\test_release_check.py::test_v47_acceptance_analytics_smoke -q`

## v4.7.0 - 2026-05-20

### Added
- Acceptance Analytics reports for global, suite, release, and project scopes, with deterministic source hashes, stale detection, songbook heatmaps, issue taxonomy, reviewer summaries, trends, weakness rankings, and manual-only recommendations.
- `acceptance-analytics` CLI for refreshing/reporting analytics with JSON output, report export, and readiness threshold exits.
- API endpoints for analytics refresh/detail plus explicit recommendation-to-ReviewTask creation with duplicate open-task guards.
- Studio Acceptance Analytics dashboards for global, suite, and release views.
- Release Export now writes `acceptance-analytics-summary.json`, and Release Signoff records analytics evidence; blocked analytics readiness returns 409 unless force signoff is explicitly audited.
- release-check v4.7 smoke covers heatmap coverage, blocked readiness, stale report detection, explicit ReviewTask creation, Release Signoff blocking, forced analytics evidence, and export summaries.

### Verified
- `python -m pytest tests\test_acceptance_analytics.py tests\test_server_acceptance_analytics.py tests\test_cli_acceptance_analytics.py tests\test_webui.py::test_webui_contains_acceptance_workspace tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v47_acceptance_analytics_smoke -q`

## v4.6.1 - 2026-05-20

### Fixed
- Human Review Pack source hashes now bind only the listened suite/case content, health, and MIDI/WAV artifacts, so importing listening reviews does not make the original pack stale.
- Human review response imports now reject any review whose `song_id` does not exactly match the corresponding Pack case.

### Added
- release-check v4.6 smoke now covers same-pack revised response import, non-stale Pack state after imports, and `song_id` mismatch rejection.

### Verified
- `python -m pytest tests\test_human_review_pack.py tests\test_release_check.py::test_v46_human_review_pack_smoke -q`

## v4.6.0 - 2026-05-19

### Added
- Human Review Pack export for Acceptance Suites, including portable `index.html`, MIDI/WAV assets, response template, manifest, checksums, and ZIP download.
- `verify-human-review-pack` CLI for offline ZIP verification with path-safety, duplicate-entry, hash, static HTML, MIDI/WAV header, and redaction checks.
- Human review response import writes manual listening reviews back to Acceptance cases, preserves source/tags/markers, rejects `source_path`, enforces pack source hashes, and blocks stale imports.
- `needs_fix` and `rejected` imported reviews now create audited follow-up records and project ReviewTasks when the Acceptance case is linked to a Project version.
- Acceptance reports and Release Signoff acceptance gates now include Human Review Pack evidence summaries.
- Studio Acceptance workspace controls for creating, zipping, verifying, downloading, and importing Human Review Packs.
- release-check v4.6 smoke covers 12-song release-candidate pack export, external verification, needs-fix import, stale/source_path guards, full accepted re-review, Release Signoff evidence, and tampered ZIP failure.

### Verified
- `python -m pytest tests\test_human_review_pack.py tests\test_cli_human_review_pack.py tests\test_server_acceptance.py tests\test_release_check.py::test_v46_human_review_pack_smoke -q`

## v4.5.1 - 2026-05-19

### Fixed
- Release-ready Acceptance reports now require complete Regression Songbook coverage for release-ready profiles.
- `release_candidate` and `audio_required` reports must cover all 12 built-in song IDs, with no duplicate song IDs, and every song must have a manual accepted review before `release_ready=true`.
- Release Signoff now rejects incomplete-songbook Acceptance Suites even if their existing cases were manually accepted.

### Added
- Acceptance report summaries now include `expected_case_count`, `missing_song_ids`, `duplicate_song_ids`, and `songbook_coverage_status`.
- release-check v4.5 smoke now covers both synthetic release-candidate rejection and one-song manual release-candidate rejection.

### Verified
- `python -m pytest tests\test_music_acceptance.py tests\test_server_releases.py::test_release_signoff_blocks_non_manual_release_candidate_acceptance tests\test_server_releases.py::test_release_signoff_blocks_incomplete_manual_release_candidate_acceptance tests\test_release_check.py::test_v45_acceptance_profiles_songbook_smoke tests\test_cli_acceptance_check.py::test_cli_acceptance_release_candidate_auto_review_cannot_pass -q`

## v4.5.0 - 2026-05-19

### Added
- Acceptance Profiles for repeatable music gates: `midi_smoke`, `developer_manual`, `release_candidate`, and `audio_required`.
- Built-in 12-song Regression Songbook with stable song IDs, requests, expectations, and Studio/API exposure.
- `acceptance-check --profile ...` and `acceptance-diff` for profile-based acceptance runs and songbook-aligned regression comparisons.
- Manual release-candidate gate: synthetic reviews can support smoke tests, but release-ready acceptance requires manual listening reviews.
- Release Signoff acceptance binding blocks non-manual or non-release-ready acceptance reports unless force signoff is used and audited.
- Studio Acceptance controls for profile selection, regression songbook browsing, songbook case creation, and acceptance status display.
- release-check v4.5 smoke covering profiles, songbook, diff, synthetic release-candidate failure, and Release Signoff acceptance blocking.

### Verified
- `python -m pytest tests\test_webui.py::test_webui_contains_acceptance_workspace tests\test_cli_acceptance_check.py tests\test_music_acceptance.py tests\test_server_acceptance.py tests\test_server_releases.py::test_release_signoff_blocks_non_manual_release_candidate_acceptance tests\test_release_check.py::test_v45_acceptance_profiles_songbook_smoke -q`

## v4.4.1 - 2026-05-18

### Fixed
- `acceptance-check --render-audio never` now creates a MIDI-only suite by setting `require_audio_if_renderer_configured=false`, so local renderer config cannot force a missing WAV failure.
- Music health reports preserve `audio_status=skipped_by_request` for MIDI-only acceptance runs instead of treating skipped audio as a renderer failure.

### Clarified
- `--auto-review` remains synthetic CI/smoke evidence only; human release readiness still requires manual playback review records.

### Verified
- `python -m pytest tests\test_cli_acceptance_check.py tests\test_music_health.py tests\test_music_acceptance.py tests\test_server_acceptance.py -q`

## v4.4.0 - 2026-05-18

### Added
- Music Acceptance Lab for developer self-check suites, generated acceptance cases, deterministic SongPlan/MIDI/WAV health checks, listening review records, reports, and signoff.
- `python -m song_agent.cli acceptance-check` for six-song local acceptance runs, optional synthetic CI reviews, JSON output, and report export.
- Studio Acceptance workspace for suite creation, case generation, health checks, MIDI/audio access, listening review entry, report build, signoff, and reset.
- release-check v4.4 smoke covering acceptance API flow, renderer-not-configured MIDI-only acceptance, signed-suite mutation guards, report tamper detection, missing-MIDI health failure, and redaction.

### Fixed
- Acceptance signoff now makes suites read-only for case/audio/review/report/archive mutations until signoff is reset.
- Acceptance reports include source/content integrity checks so tampered review data or tampered report payloads fail verification instead of remaining silently trusted.

### Verified
- `python -m pytest tests\test_music_health.py tests\test_music_acceptance.py tests\test_cli_acceptance_check.py tests\test_server_acceptance.py tests\test_webui.py::test_webui_contains_acceptance_workspace tests\test_release_check.py::test_v44_music_acceptance_lab_smoke -q`

## v4.3.1 - 2026-05-18

### Fixed
- Submission external status updates now require a signed Submission package before recording submitted, feedback, or accepted events.
- `record-submission` now only accepts ready, current items, so pending targets without Distribution ZIP/signoff cannot be marked submitted.
- `record-feedback` and `accepted` now require a submitted/feedback/needs_changes item state before mutating external status.
- release-check v4.3 smoke covers unsigned Submission and pending item status-transition guards.

### Verified
- `python -m pytest tests\test_server_submissions.py tests\test_submissions.py tests\test_release_check.py::test_v43_submission_workspace_smoke -q`

## v4.3.0 - 2026-05-18

### Added
- Submission Workspace for grouping signed Distribution Targets into local multi-platform submission batches.
- Submission QA, Export, ZIP, Signoff, external submitted/feedback/accepted records, and signed-package mutation guards.
- Portable `verify-submission-package` CLI with deep nested Distribution Package verification, sidecar signoff payload checks, ZIP safety, duplicate entry, hash, CSV formula, and redaction checks.
- Studio Release page controls for creating submission batches, running QA/Export/ZIP/Verify/Sign, and recording external status updates.
- release-check v4.3 smoke covering offline verification, signed mutation blocking, signoff sidecar tamper, nested target ZIP tamper, duplicate entry, and backslash entry failures.

### Scope
- Submission Workspace is local preparation and tracking only. It does not upload to platforms, connect to distributor APIs, or store platform credentials.

### Verified
- `python -m pytest tests\test_submissions.py tests\test_cli_verify_submission.py tests\test_server_submissions.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v43_submission_workspace_smoke -q`

## v4.2.1 - 2026-05-17

### Fixed
- Distribution Layout now rejects rendered audio/artwork/lyrics paths whose filename extension does not match the actual source extension, preventing MIDI fallback bytes from being exported under a hardcoded `.wav` package path.
- `verify-distribution-package` now catches invalid/tampered template `file_naming` rules and returns a failed verification report instead of raising an exception.
- release-check v4.2 smoke now covers only-MIDI + hardcoded-WAV layout failure and bad `template-pack.json` verifier failure reporting.

### Verified
- `python -m pytest tests\test_distribution_layout.py tests\test_distribution.py tests\test_release_check.py::test_v42_distribution_layout_contract_smoke -q`

## v4.2.0 - 2026-05-17

### Added
- Distribution Package Layout Contract centralizes template `file_naming` into a single auditable planner for audio, artwork, and lyrics package paths.
- Distribution Export now writes `layout/manifest-layout.json` and `layout/file-tree.txt`, includes layout summary/hash metadata, and uses the layout plan for copied package files.
- Distribution QA, Studio, and API now expose Layout preview/refresh so package paths can be inspected before export.
- `verify-distribution-package` validates layout sidecar hashes, manifest/layout consistency, layout file hashes, artwork package path binding, custom lyrics paths, and legacy v4.1 layout-missing compatibility.
- release-check v4.2 smoke covers custom audio/artwork/lyrics naming, external verification, layout tamper detection, artwork path tamper detection, unsafe patterns, and bad artwork variables.

### Fixed
- Template `file_naming.artwork` now rejects track-scoped variables instead of silently accepting rules that cannot be rendered for release-scoped artwork.
- Distribution audio layout preserves custom subdirectories and falls back to signed Release Export MIDI when WAV audio is absent.

### Verified
- `python -m pytest tests\test_distribution_layout.py tests\test_distribution_templates.py tests\test_distribution.py tests\test_server_distribution.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v42_distribution_layout_contract_smoke -q`

## v4.1.2 - 2026-05-17

### Fixed
- Distribution Template Pack delete now returns 409 while any Distribution target still references the template, including unsigned targets.
- Template Pack delete no longer leaves targets with dangling `template_pack_id` values that would let QA/Export run without the intended template rules or checklist.
- release-check v4.1 smoke now verifies referenced template deletion is blocked before and after Distribution target signoff.

### Verified
- `python -m pytest tests\test_server_distribution.py tests\test_distribution_templates.py tests\test_distribution_checklist.py tests\test_release_check.py::test_v41_distribution_template_packs_smoke -q`

## v4.1.1 - 2026-05-17

### Fixed
- Global Distribution Template Pack update/delete now scans dependent Distribution targets and returns 409 when any signed or force-signed target is bound to that template.
- Template Pack changes that affect unsigned dependent targets now mark their QA/export summaries stale instead of leaving old summaries looking current.
- release-check v4.1 smoke now verifies signed-target global template update/delete guards.

### Verified
- `python -m pytest tests\test_server_distribution.py tests\test_release_check.py::test_v41_distribution_template_packs_smoke tests\test_distribution_templates.py tests\test_distribution.py -q`

## v4.1.0 - 2026-05-17

### Added
- Platform Template Packs for local Distribution Prep rules, metadata CSV mapping, file naming, and submission checklist definitions.
- Distribution targets can bind a template pack; template rules and checklist status now participate in Distribution QA source hashing and export gates.
- Distribution packages include `template-pack.json`, `template-summary.json`, template CSV output, and checklist JSON/Markdown docs.
- `verify-distribution-package` now validates template hashes, template summary hashes, checklist payload hashes, checklist status, and tamper scenarios.
- Studio Distribution Prep now exposes template pack selection, local template creation/clone controls, and checklist actions.
- release-check v4.1 smoke covers template import safety, mapping/checklist QA, export/verify, signed-target mutation guards, and template/checklist ZIP tamper detection.

### Scope
- Platform Template Packs are local preparation templates only. They are not official platform rules and do not upload, submit, connect to distributor APIs, or store platform credentials.

### Verified
- `python -m pytest tests\test_distribution_templates.py tests\test_distribution_checklist.py tests\test_distribution.py tests\test_server_distribution.py tests\test_release_check.py::test_v41_distribution_template_packs_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v4.0.1 - 2026-05-17

### Fixed
- Distribution artwork import now rejects `source_path` payloads and only accepts uploaded base64 content, preventing API clients from reading server-local files.
- Distribution target signoff now checks signed-target mutability before refreshing QA, so repeat signoff returns 409 without changing `qa.json`.
- release-check v4.0 smoke now verifies `source_path` rejection and repeat signoff no-mutation behavior.

### Verified
- `python -m pytest tests\test_server_distribution.py tests\test_release_check.py::test_v40_distribution_prep_smoke tests\test_distribution.py tests\test_cli_verify_distribution.py -q`

## v4.0.0 - 2026-05-16

### Added
- Distribution Prep targets under each Release with built-in `generic_dsp`, `demo_pitch`, and `internal_archive` profiles.
- Distribution artwork import and QA for PNG/JPEG headers, dimensions, size limits, and selected artwork binding.
- Distribution QA source hashing over signed Release Export/ZIP/signoff, Release Metadata/QA, target options, profile, and artwork state.
- Distribution Export/ZIP packages with `distribution-manifest.json`, metadata JSON/CSV, lyrics, artwork, docs, optional audio, and signed sidecar payload hash binding for `distribution-signoff.json`.
- `python -m song_agent.cli verify-distribution-package <zip>` for offline package validation, including path safety, duplicate entries, ZIP bomb guard, manifest file hashes, signoff hash binding, artwork/WAV headers, CSV formula safety, and redaction scanning.
- Studio Distribution Prep controls and release-check v4.0 smoke coverage for package export, external verification, signed mutation blocking, signoff tamper failure, CSV formula pollution, and backslash ZIP entry failure.

### Scope
- Distribution Prep is local preparation and verification only. It does not upload to DSPs, call distributor APIs, or save platform credentials.

### Verified
- `python -m pytest tests\test_distribution.py tests\test_server_distribution.py tests\test_cli_verify_distribution.py tests\test_release_check.py::test_v40_distribution_prep_smoke tests\test_webui.py -q`

## v3.9.1 - 2026-05-16

### Fixed
- Signed releases now block `POST /api/releases/<id>/export`, `POST /api/releases/<id>/export/zip`, and `POST /api/releases/<id>/metadata/export` with 409 until signoff is reset, preserving the signed Release Export manifest hash and ZIP verification chain.
- release-check v3.9 smoke now verifies signed release export mutation is blocked for all three write endpoints.

### Verified
- `python -m pytest tests\test_server_release_metadata.py tests\test_release_check.py::test_v39_release_metadata_smoke -q`

## v3.9.0 - 2026-05-16

### Added
- Release Metadata documents under `.musicforge/releases/<release-id>/metadata.json` with release title, artists, label, language, release date, UPC, rights notes, track ISRC, explicit/instrumental flags, lyrics, and credits.
- Metadata QA for required fields, UPC/ISRC formats, duplicate ISRCs, tracklist consistency, lyrics/explicit/instrumental warnings, credits coverage, confirmation state, and sensitive value redaction.
- Metadata export files in Release Export and ZIP: `release-metadata.json`, `platform-metadata.csv`, `credits.csv`, and `lyrics/*.txt`.
- Release API endpoints for metadata init/save/QA/export plus platform and credits CSV downloads.
- Studio Release Metadata panel with initialize, save, QA refresh, export, and CSV download controls.
- `verify-release` metadata checks for manifest metadata summaries, protected metadata files, UTF-8 CSV parsing, tracklist consistency, metadata payload hash, lyrics/CSV/JSON redaction, and old pre-v3.9 ZIP compatibility warnings.
- release-check v3.9 smoke covering metadata init, QA, export, ZIP verification, missing metadata file failure, and metadata redaction failure.

### Verified
- `python -m pytest tests\test_release_metadata.py tests\test_server_release_metadata.py tests\test_release_export.py tests\test_release_verifier.py tests\test_server_releases.py tests\test_release_check.py tests\test_webui.py -q`

## v3.8.1 - 2026-05-16

### Fixed
- Release Export now records a signed sidecar payload hash for `release-signoff.json`, and `verify-release` fails if signed display fields such as `signed_by` or `signed_at` are tampered after ZIP creation.
- `verify-release` now inspects raw ZIP central-directory names and treats backslash entries as blocking path-safety failures instead of normalizing them to POSIX paths.

### Verified
- `python -m pytest tests\test_release_verifier.py tests\test_server_releases.py tests\test_release_check.py::test_v38_release_zip_verifier_smoke -q`

## v3.8.0 - 2026-05-15

### Added
- Release ZIP verifier module and `python -m song_agent.cli verify-release <zip>` CLI for portable, workspace-independent Release ZIP validation.
- Verification reports with human output, `--json`, `--report-out`, `--strict`, `--require-audio`, `--require-stems`, ZIP size, uncompressed size, entry count, path safety, duplicate entry, manifest/files/hash, signoff hash, track core artifact, MIDI/WAV header, stems, and redaction checks.
- release-check v3.8 smoke that copies a Release ZIP into a clean external directory and verifies failure cases for hash mismatch, dangerous entries, duplicate entries, spoofed `manifest.zip.entries`, redaction pollution, and ZIP bomb metadata.

### Fixed
- Release Export now sanitizes copied JSON/TXT track files before packaging, preventing local Project paths from leaking into portable Release ZIPs.

### Verified
- `python -m pytest tests\test_release_verifier.py tests\test_cli_verify_release.py tests\test_release_check.py tests\test_release_export.py tests\test_server_releases.py -q`

## v3.7.1 - 2026-05-15

### Fixed
- Release Signoff now binds to the final Release Export manifest after `release-signoff.json` has been written and the Release ZIP has been rebuilt, so the signoff record, disk manifest, and ZIP-contained manifest agree on `export_manifest_hash`.
- Release Export manifest ZIP metadata no longer writes the ZIP's own SHA back into `manifest.json`, avoiding self-referential manifest/ZIP hash drift.
- Batch stem audio completion now counts `skipped` stems as terminal when updating batch item stem audio progress, reducing release-check flakiness around stem audio waits.

### Verified
- `python -m pytest tests\test_server_releases.py tests\test_release_export.py tests\test_release_check.py tests\test_batch_stems.py -q`

## v3.7.0 - 2026-05-15

### Added
- Release Workspace persistence under `.musicforge/releases/<release-id>/` for multi-track EP/album/demo-pack assembly from Project Delivery QA and Signoff-approved Final Exports.
- Release Store, Release QA, Release Export, Release ZIP, and Release Signoff flows with track ordering, project snapshot refresh, stale guards, signed-release mutation blocking, reset history, and path-safe ZIP creation.
- Release APIs plus Project `release-targets` and `add-to-release` endpoints.
- Studio top-level Releases workspace and Project Final Export `Add to Release` controls.
- release-check v3.7 smoke covering multi-project release assembly, QA, export, ZIP download, signoff, signed mutation blocking, stale Project artifact detection, raw Release JSON redaction, and ZIP metadata/path safety.

### Scope
- Release Workspace is a local packaging and audit layer only. It does not rebuild Project Final Exports, change Project final versions, upload releases, call providers, auto-sign, or publish to external stores.

### Verified
- `python -m pytest tests\test_releases.py tests\test_release_qa.py tests\test_release_export.py tests\test_server_releases.py tests\test_webui.py -q`

## v3.6.1 - 2026-05-15

### Fixed
- Delivery QA now enforces a built-in required Final Export baseline instead of trusting `manifest.files` alone. `manifest.json`, `README.txt`, `project-export.json`, `song-plan.json`, and `song.mid` must exist even if a polluted manifest removes those entries.
- Delivery QA now scans the raw Final Export manifest for sensitive values before returning a sanitized report, so polluted fields such as `zip.path = C:\...` fail `redaction_scan`.
- Final Export ZIP metadata no longer writes a local absolute `zip.path` into `manifest.json` or the ZIP-contained manifest.

### Verified
- `python -m pytest tests\test_delivery_qa.py tests\test_server_delivery_qa.py tests\test_final_export.py tests\test_release_check.py -q`

## v3.6.0 - 2026-05-15

### Added
- Project-level Delivery QA Reports that verify final version selection, Final Export manifest consistency, required artifact presence, artifact path safety, ZIP integrity, review sprint closeout/signoff alignment, and delivery payload redaction.
- Delivery Signoff records with normal/force signoff, required override reasons, duplicate-sign protection, reset history, and project events.
- Delivery QA and Signoff APIs plus Studio Final Export Delivery QA controls for refresh, sign, force sign, reset, checks, artifacts, and ZIP state.
- Project Export and Final Export manifest summaries for delivery QA and delivery signoff.
- release-check v3.6 smoke covering failed QA before ZIP, successful QA/signoff, duplicate signoff rejection, reset history, stale ZIP detection, polluted ZIP failure, export summaries, final export summaries, and redaction.

### Scope
- Delivery QA is a local verification and audit layer only. It does not rebuild Final Export, rebuild ZIPs, call providers, apply candidates, change project final version, or upload anything.

### Verified
- `python -m pytest tests\test_delivery_qa.py tests\test_server_delivery_qa.py tests\test_final_export.py tests\test_projects.py tests\test_webui.py tests\test_server_auth.py tests\test_release_check.py -q`

## v3.5.1 - 2026-05-15

### Fixed
- Closeout no longer treats the project `latest_version_id` as a delivery-confirmed final version. A Sprint with resolved tasks but no applied candidate version, selected version, or final version now fails the `missing_applied_version` gate and normal close returns 409.

### Verified
- `python -m pytest tests\test_review_sprint_closeout.py tests\test_server_review_sprint_closeout.py tests\test_release_check.py -q`

## v3.5.0 - 2026-05-15

### Added
- Review Sprint Closeout Reports with gate checks for open/stale tasks, blocking conflicts, pending/failed Action Queue items, stale recommendations or Judge Reports, metrics readiness, and missing applied/selected versions.
- Sprint Signoff Records written separately from closeout reports, including forced-close audit metadata, selected version, closeout hash, acknowledged blockers, and acknowledged warnings.
- Close Sprint now refreshes closeout and returns 409 when the gate fails unless `force=true` is supplied with a non-empty `override_reason`.
- Closeout and Signoff APIs plus Studio Review Sprints controls for refreshing closeout, normal close, force close, and signoff display.
- Project Export, Final Export, Sprint Metrics, Project Review Metrics, and release-check now include compact closeout/signoff summaries.

### Scope
- Closeout is a local gate and audit layer only. It does not apply candidates, resolve tasks, call providers, auto-close Sprints, create final exports, or publish anything.

### Verified
- `python -m pytest tests\test_review_sprint_closeout.py tests\test_server_review_sprint_closeout.py tests\test_review_sprints.py tests\test_projects.py tests\test_final_export.py tests\test_review_sprint_metrics.py tests\test_webui.py -q`

## v3.4.1 - 2026-05-15

### Fixed
- Final Export review judge summaries now use `review_metrics_summary.latest_sprint_id` to select the matching Sprint judge summary in multi-Sprint projects.
- Project Export and Sprint Metrics now re-evaluate Judge Report stale state instead of reading raw `judge-report.json` as completed.
- Judge Report source hashes no longer become stale solely because a candidate was manually applied; content changes still mark the report stale.

### Verified
- `python -m pytest tests\test_final_export.py tests\test_projects.py tests\test_review_judge.py tests\test_review_sprint_metrics.py -q`

## v3.4.0 - 2026-05-14

### Added
- Provider Judge reports for ReviewTask candidates with strict JSON validation, source hashing, stale detection, per-candidate fit/precision/musicality/novelty/risk/confidence scores, and sanitized provider usage.
- ReviewTask Judge Report APIs plus Sprint Judge Summary get/refresh APIs.
- Decision Reports, manual apply metadata, Project Compare, Project Export, Final Export, and provider usage now include compact judge summaries.
- Review Sprint Action Queues can include `refresh_judge_report` provider-safe items; they remain skipped unless `include_provider=true` is supplied.
- Sprint Metrics and Project Review Metrics now include judge task counts, stale judge counts, judge tokens, local/judge disagreement, high-risk candidate counts, and judge apply match rate.
- Studio Review Workbench and Review Sprints now expose Judge Report, Judge Summary, provider-safe queue rows, and advisory/manual-apply wording.
- release-check now includes a v3.4 smoke covering task judge, sprint judge, queue default skip/provider opt-in, manual apply provenance, metrics, export/final export, usage, and redaction.

### Scope
- Provider Judge is advisory only. It does not generate candidates, apply candidates, resolve ReviewTasks, close ReviewSprints, or override manual decisions.

### Verified
- `python -m pytest tests\test_review_judge.py tests\test_server_review_judge.py tests\test_review_sprint_actions.py tests\test_server_review_sprint_actions.py tests\test_review_sprint_metrics.py tests\test_server_review_sprint_metrics.py tests\test_webui.py tests\test_release_check.py -q`

## v3.3.1 - 2026-05-14

### Fixed
- Final Export review metrics now use `review_metrics_summary.latest_sprint_id` to select the matching Sprint metrics summary, so multi-Sprint exports no longer mix the latest Sprint ID/readiness with an older Sprint's completion, quality delta, or warnings.

### Verified
- `python -m pytest tests\test_final_export.py tests\test_server_review_sprint_metrics.py tests\test_release_check.py -q`

## v3.3.0 - 2026-05-14

### Added
- Review Sprint Metrics Reports with task status, candidate funnel, recommendation adoption, Action Queue execution, provider usage, manual decision, quality delta, and readiness summaries.
- Project Review Metrics with project-level sprint totals, provider tokens, applied candidate counts, latest readiness, and quality trend.
- Metrics APIs for Sprint get/refresh and Project get/refresh, with cached derived JSON files and refresh events.
- Studio Review Sprints Dashboard panel plus Project Review Metrics summary.
- Project Export and Final Export now include compact review metrics summaries without exporting raw provider prompts, local paths, or full metrics reports.
- release-check now includes a v3.3 smoke covering dashboard metrics, project metrics, export/final export summaries, provider usage, manual apply metrics, quality delta, readiness, and redaction.

### Scope
- v3.3.0 only reads existing Review Sprint/Task/Candidate/Queue/provider/quality data and writes derived metrics reports. It does not auto-apply, auto-resolve, auto-close, or call provider judgment.

### Verified
- `python -m pytest tests\test_review_sprint_metrics.py tests\test_server_review_sprint_metrics.py tests\test_webui.py -q`

## v3.2.1 - 2026-05-14

### Fixed
- Review Sprint Action Queue runs no longer leave a queue stuck in `running` when provider-safe items are skipped because `include_provider=true` was not supplied.

### Verified
- `python -m pytest tests\test_review_sprint_actions.py tests\test_server_review_sprint_actions.py tests\test_release_check.py -q`

## v3.2.0 - 2026-05-14

### Added
- Review Sprint Action Queues that convert Recommendation Reports into persisted, auditable queue items with statuses, safety classes, event streams, and stale report hashes.
- Action Queue APIs for create/list/detail/run/archive, including selected-item execution, completed-item idempotency, provider opt-in, and queue-level event history.
- Safe Action Queue execution for saving recommended Context Packs, generating task-scoped local/provider candidates, refreshing Decision Reports, and refreshing sprint conflicts/recommendations.
- Studio Review Sprints Action Queue panel with queue creation, safe selection, provider authorization, run controls, manual-required rows, and queue summaries.
- Project Compare, Project Export, Final Export, and review candidate apply metadata now include compact Review Sprint Action Queue provenance.
- release-check now includes a v3.2 smoke covering queue creation, safe local/context execution, provider default skip, provider opt-in, Decision Report refresh, manual apply provenance, export/final export, stale recommendation blocking, stale context blocking, usage, and redaction.

### Scope
- v3.2.0 still does not auto-apply candidates, auto-resolve tasks, auto-close sprints, or create final exports automatically. Provider queue items remain skipped unless explicitly allowed for that run.

### Verified
- `python -m pytest tests\test_review_sprint_actions.py tests\test_server_review_sprint_actions.py tests\test_release_check.py tests\test_webui.py -q`

## v3.1.0 - 2026-05-14

### Added
- Review Sprint Recommendation Reports with deterministic task ordering, per-task recommended actions, scoring reasons, conflict awareness, and context pack previews.
- Review Sprint recommendation APIs for GET, refresh, and manual Context Pack save from a recommendation.
- Studio Review Sprints recommendations panel with next-action summaries, manual-apply warning, refresh, and Save Context Pack controls.
- Project Compare, Project Export, Final Export, and edit metadata now include Review Sprint recommendation summaries without exporting full context candidate details.
- release-check now includes a v3.1 smoke covering recommendation refresh, Context Pack save, stale source rejection, no-op recommendation APIs, provider generation with saved context, apply provenance, export, and final export.

### Scope
- v3.1.0 does not auto-apply candidates, auto-resolve tasks, or auto-generate candidates. Recommendations are advisory and all execution still requires explicit user action.

### Verified
- `python -m pytest tests\test_review_sprint_recommendations.py tests\test_review_sprints.py tests\test_server_review_sprint_recommendations.py tests\test_server_review_sprints.py tests\test_webui.py -q`

## v3.0.0 - 2026-05-13

### Added
- Review Sprints for organizing multiple ReviewTasks with ordered task refs, status/count summaries, conflict reports, and event history.
- Review Sprint APIs for create/list/detail, task add/remove/reorder, refresh/close/archive, conflict refresh, and batch local/provider candidate generation.
- Studio Review Sprints workspace plus Review Workbench add-to-sprint controls.
- Project Compare, Project Export, Final Export, and provider usage reports now include Review Sprint provenance and sprint rollups.
- release-check now includes a v3.0 smoke covering sprint conflicts, batch local/provider candidates, artifact path pollution, single-candidate apply, export, final export, and usage.

### Scope
- Review Sprints never batch-apply edits. They organize ReviewTasks and create candidates only; every apply still goes through the existing one-task, one-candidate ReviewTask guard.

### Verified
- `python -m pytest tests\test_review_sprints.py tests\test_server_review_sprints.py tests\test_final_export.py tests\test_project_compare.py tests\test_server_review_tasks.py tests\test_webui.py -q`

## v2.9.0 - 2026-05-13

### Added
- Provider review candidates for Review Tasks using the new `provider-review-candidates` prompt template and existing constrained ProviderEditPatch validation.
- Decision Report storage at `review-tasks/<task-id>/decision-report.json`, with local/provider ranking, source breakdown, risk flags, and manual-apply recommendation.
- Review Workbench controls for generating provider candidates, refreshing the Decision Report, and seeing provider/local source badges.
- Project Compare, Project Export, Final Export, and provider usage reports now include provider review candidate provenance and decision summaries.
- release-check now includes a v2.9 mock-provider smoke covering provider candidates, decision reports, candidate MIDI, artifact path pollution, apply, exports, and usage reporting.

### Scope
- Provider output is only a candidate source and explanation aid. It cannot auto-apply, cannot bypass local validation/scoring, and cannot replace the one-candidate-per-task apply guard.

### Verified
- `python -m pytest tests\test_review_tasks.py tests\test_server_review_tasks.py tests\test_webui.py -q`

## v2.8.0 - 2026-05-13

### Added
- Review Workbench for turning audition reviews into persistent Review Tasks with status, target, marker-coordinate, and follow-up provenance.
- Local review candidates with conservative, balanced, and bold strategies, ranking, validator/quality summaries, MIDI download, and optional WAV rendering through the local renderer.
- Candidate apply creates one official child Project Version from parent + candidate intents, not from cached candidate SongPlan files.
- ReviewTask lifecycle APIs for generate candidates, apply one candidate, resolve, mark needs_more_work with a linked follow-up task, and archive.
- Studio Review Workbench tab plus Review Board actions to create Review Tasks from audition reviews.
- Project Compare, Project Export, Final Export, and release-check now include review task and selected candidate provenance.

### Scope
- v2.8.0 keeps provider review candidates deferred. The completed workflow is local-first and deterministic.

### Verified
- `python -m pytest tests\test_review_tasks.py tests\test_server_review_tasks.py tests\test_server_review_edits.py tests\test_webui.py -q`

## v2.7.1 - 2026-05-12

### Fixed
- Review Edit now interprets audition review marker beats relative to the audition range start, so custom and changed_sections audition markers target the correct parent SongPlan section.

### Verified
- `python -m pytest tests\test_review_edits.py tests\test_server_review_edits.py -q`

## v2.7.0 - 2026-05-12

### Added
- Review-driven edit planning that maps sanitized audition review notes, status, rating, tags, and markers into safe local `EditIntent` objects.
- Review edit preview API that stores `review-edits/<review-edit-id>/review-edit.json`, candidate SongPlan, validator report, and summary.
- Review edit create API that produces a non-destructive child Project Version and records review provenance in edit metadata.
- Optional provider review edit preview route using a dedicated `provider-review-edit-intent` template and existing ProviderEditPatch validation.
- Audition review to Context Pack API for turning favorite/high-value audition assets into reusable context.
- Studio Review Board Next Actions: Preview Edit, Create Local Edit, Provider Preview, and Create Context Pack.
- Project Compare, Project Export, Final Export, and release-check now include review edit provenance summaries.

### Scope
- v2.7.0 is user-triggered only. Reviews do not automatically modify versions, and review text is never executed as arbitrary patch operations.

### Verified
- `python -m pytest tests\test_review_edits.py tests\test_server_review_edits.py tests\test_webui.py -q`

## v2.6.0 - 2026-05-12

### Added
- Audition Review Board for editor auditions with rating, status, favorite, notes, tags, marker metadata, filtering, and summary counts.
- Review marker APIs with beat bounds, supported kinds/severity, event logging, and sensitive text redaction.
- API to save an audition slice as a Creative Asset by rebuilding asset content from the audition SongPlan rather than copying cached audio or arbitrary paths.
- Studio review controls for scoring auditions, adding markers, filtering favorites, and saving audition motifs into the asset library.
- Audition review summary now flows into editor apply metadata, Project Compare, Project Export, Final Export summaries, and release-check.
- release-check now includes a v2.6 audition review smoke covering review redaction, markers, asset creation, apply metadata, compare, and project export.

### Scope
- v2.6.0 keeps review as metadata only; it does not modify preview patches, parent versions, or generated music content, and it does not include realtime waveform editing or automatic AI review.

### Verified
- `python -m pytest tests\test_editor_review.py tests\test_server_editor_review.py tests\test_server_editor_audition.py tests\test_webui.py -q`

## v2.5.1 - 2026-05-12

### Fixed
- Preview WAV rendering now recomputes the preview plan from the parent version SongPlan and stored editor patch before regenerating MIDI and WAV.
- Preview audio no longer trusts cached `editor-previews/<preview-id>/song.mid` or `song-plan.json`, keeping A/B playback aligned with the version that Apply would create.

### Verified
- `python -m pytest tests\test_server_editor_audition.py tests\test_editor_audition.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.5.0 - 2026-05-12

### Added
- Editor Preview audio status and render/download support for Preview WAV.
- Project Version parent WAV render/download routes for A/B listening in Studio.
- Editor Audition cache under Project editor previews with parent/preview sources, full song/section/changed/custom ranges, and all/solo/mute track modes.
- Audition MIDI download and optional WAV rendering using the existing local renderer configuration.
- Studio Project Editor A/B audio controls and Audition panel.
- Audition summary now flows into visual editor apply metadata, Project Compare, Project Export, Final Export summaries, and release-check.
- release-check now includes a v2.5 editor audition smoke covering parent/preview auditions, solo MIDI, renderer-missing audio error, apply metadata, compare, and project export.

### Scope
- v2.5.0 keeps audition artifacts as local editor-preview cache only; it does not copy temporary audition WAVs into Final Export and does not add realtime browser mixing.

### Verified
- `python -m pytest tests\test_webui.py tests\test_editor_audition.py tests\test_server_editor_audition.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.4.1 - 2026-05-12

### Fixed
- Multi-track template draft insert now validates `lane_mappings[].lane_id` against the selected template before generating operations.
- Unknown template lane IDs now return a clear `400 Unknown template lane_id: ...` instead of the generic no-notes conflict.

### Verified
- `python -m pytest tests\test_editor_templates.py tests\test_server_editor_templates.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.4.0 - 2026-05-11

### Added
- Editor Template Store for reusable section and track templates under `.musicforge/editor-templates/`.
- MultiTrackClip support for extracting full Project Version sections into role-based lanes.
- Section Template and Track Template APIs, including source hash summaries and hide/delete routes.
- Multi-track template mapping and draft insert APIs that reuse the visual editor patch engine and support current Patch Queue state.
- Studio Editor Templates panel, Project Editor Template Browser, Save Section Template, Save Track Template, and Draft Insert Template controls.
- Template provenance now flows through editor preview apply, Project Compare, Project Export, Final Export, and release-check.
- release-check now includes a v2.4 editor template smoke covering save, mapping, draft, preview, apply, compare, project export, and final export.

### Scope
- v2.4.0 intentionally keeps template reuse local and deterministic; it does not add DAW-style drag editing, realtime playback, audio-to-MIDI, MP3 import, AI arranger solving, or mixing automation.

### Verified
- `python -m pytest tests\test_editor_templates.py tests\test_server_editor_templates.py tests\test_server_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.3.2 - 2026-05-11

### Fixed
- Clip provenance group IDs now include the actual generated insert operations, so repeated inserts of the same clip at the same position but with different transpose/velocity/replace options remain separate audit records.

### Verified
- `python -m pytest tests\test_server_editor_clips.py tests\test_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.3.1 - 2026-05-11

### Fixed
- Clip `replace_range` drafts can now receive the current Project Editor Patch Queue and compute replacement deletes against the accumulated draft state, avoiding duplicate deletion of base note IDs.
- Studio clip provenance is now derived from `clip_group_id` on queued operations, so normal manual edits do not clear existing clip insert metadata.
- Editor clip draft responses now include a `combined_patch` for clients that want to preview/apply the accumulated queue in one request.

### Verified
- `python -m pytest tests\test_editor_clips.py tests\test_server_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.3.0 - 2026-05-11

### Added
- EditorClip layer for reusable note fragments from Assets, Reference MIDI slices, and Project Version sections/ranges.
- Project Editor APIs for listing reusable clips and creating nonpersistent clip insert drafts.
- Studio Clip Browser with overlay/replace insert modes, transpose, velocity scaling, and quantize controls.
- Clip insert metadata now flows through Editor Preview apply, Project Compare, Project Export, and Final Export summaries.
- release-check now includes a v2.3 editor clip insert smoke covering draft, preview, apply, compare, and export metadata.

### Scope
- v2.3.0 intentionally keeps clip insertion to a single target track and does not add audio-to-MIDI, MP3 import, automatic BPM/key detection, or a full DAW arranger.

### Verified
- `python -m pytest tests\test_editor_clips.py tests\test_server_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.2.2 - 2026-05-10

### Fixed
- Draft editor views now include notes created by `add_note` and `duplicate_section copy_notes` as visible `derived-note-*` entries.
- Derived draft notes are shown for audition/inspection but marked non-editable until the patch is previewed/applied or cleared.
- release-check now verifies the HTTP draft flow includes a derived note created during the same patch.

### Verified
- `python -m pytest tests\test_editor_view.py tests\test_server_editor_draft.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.2.1 - 2026-05-10

### Fixed
- Draft editor views now preserve base section and track identities after structural edits, so continued draft edits target the visible base section or track instead of a re-numbered array position.
- Newly added or duplicated draft-only sections/tracks are marked as derived and non-editable in the Studio controls until the user previews/applies or clears the patch.
- release-check now exercises the Project Editor draft flow through real HTTP calls, including delete-section followed by continued editing of the visible section ID.

### Verified
- `python -m pytest tests\test_editor_view.py tests\test_song_editor_structure.py tests\test_server_editor_draft.py tests\test_server_editor_structure.py tests\test_server_edits.py::test_project_editor_apply_ignores_polluted_preview_song_plan tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.2.0 - 2026-05-10

### Added
- Editor View Model for arranger timeline and piano-roll rendering, including section blocks, track lanes, note rectangles, pitch range, and note-to-section assignment.
- Nonpersistent Editor Draft API at `POST /api/projects/<project-id>/versions/<version-id>/editor-draft`, with optional view/diff output and no preview/run/project writes.
- Studio Project Editor now includes Arranger Timeline, Piano Roll, Inspector controls, Patch Queue, Undo/Redo, and Draft Refresh.
- release-check now includes a v2.2 interactive editor smoke covering draft, preview, apply, and metadata continuity.

### Scope
- v2.2.0 intentionally does not add a full DAW, realtime browser synthesizer, recording, audio-to-MIDI, drag editing, multi-user collaboration, or cloud storage.

### Verified
- `python -m pytest tests\test_editor_view.py tests\test_server_editor_draft.py tests\test_song_editor.py tests\test_song_editor_structure.py tests\test_server_editor_structure.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.1.2 - 2026-05-09

### Fixed
- Visual Editor note operations now resolve `note-*` IDs from the base editor state's `track_id` plus note identity, so earlier track structure edits in the same patch cannot make later note operations fail.
- Note identity is refreshed after `update_note`, `delete_notes`, `move_notes`, `transpose_notes`, `quantize_notes`, and `scale_velocity` within a patch.
- Section structure operations now keep base note identities aligned when notes are shifted, cropped, trimmed, or remapped by section movement.

### Verified
- `python -m pytest tests\test_song_editor_structure.py -q`
- `python -m pytest tests\test_song_editor.py tests\test_song_editor_structure.py tests\test_editor_previews.py tests\test_server_editor_structure.py tests\test_server_edits.py tests\test_projects.py tests\test_project_compare.py tests\test_final_export.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.1.1 - 2026-05-09

### Fixed
- Visual Editor patch operations now resolve `section-*` and `track-*` IDs against the base editor state, so structure edits earlier in the same patch cannot retarget later operations to the wrong section or track.
- Track identity now follows `rename_track` within the same patch, while deleted base IDs become unavailable for later operations.

### Verified
- `python -m pytest tests\test_song_editor_structure.py tests\test_editor_previews.py tests\test_server_editor_structure.py tests\test_server_edits.py::test_project_editor_apply_ignores_polluted_preview_song_plan -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.1.0 - 2026-05-08

### Added
- Visual Editor structure patch operations for add/duplicate/delete/resize/move section and add/duplicate/delete/rename track.
- Section timeline normalization with deterministic note shifting, copying, cropping, and bounds checks.
- Editor Preview History APIs for listing previews, reading patch summaries, and cleaning old unapplied previews.
- Studio structure editor controls and Preview History management.
- Project diff, Project Compare, Project Export, Final Export, and release-check now surface structure edit summaries.

### Scope
- v2.1.0 intentionally does not add a full DAW, piano-roll drag editing, MIDI import merge, arranger solver, or realtime audio playback.

### Verified
- `python -m pytest tests\test_song_editor.py tests\test_song_editor_structure.py tests\test_editor_previews.py -q`
- `python -m pytest tests\test_server_editor_structure.py tests\test_server_auth.py tests\test_projects.py tests\test_project_compare.py tests\test_final_export.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.0.1 - 2026-05-08

### Fixed
- Visual Editor Apply now writes and renders the recomputed editor patch result, instead of trusting the persisted preview `song-plan.json`.
- Editor Apply records a warning when a preview plan differs from the recomputed patch result, preserving the official child version from the trusted patch path.

### Verified
- `python -m pytest tests\test_server_edits.py::test_project_editor_apply_ignores_polluted_preview_song_plan tests\test_server_edits.py::test_project_editor_preview_apply_creates_manual_editor_version tests\test_song_editor.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.0.0 - 2026-05-08

### Added
- Visual SongPlan Editor for Project Versions with editor state, stable section/track/note IDs, patch preview, MIDI preview, and apply-as-version.
- Editor Patch engine for safe section chord/lyrics edits, track instrument edits, note add/update/delete/move/transpose/quantize/velocity operations.
- Persistent Project editor previews under `.musicforge/projects/<project>/editor-previews/`.
- Manual editor apply creates a new Project Version with `manual_editor_edit` lineage, `editor-patch.json`, `edit-metadata.json`, validator report, summary, and MIDI render.
- Studio Project Editor tab for local visual/manual SongPlan edits.
- Project diff, Project Compare, Project Export, and release-check now surface visual editor metadata.

### Scope
- v2.0.0 intentionally does not add a full DAW, browser synthesizer, realtime audio engine, recording, audio-to-MIDI, MP3/FLAC import, or section/track structural rearranging.

### Verified
- `python -m pytest tests\test_song_editor.py tests\test_server_edits.py tests\test_projects.py tests\test_project_compare.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.9.1 - 2026-05-08

### Fixed
- Context Pack creation is now protected by a store-level `RLock` and atomic directory reservation, preventing duplicate `pack-*` IDs under concurrent API requests.
- Context Pack creation cleanup now only removes the current thread's incomplete reservation, avoiding cross-thread directory deletion during failures.
- Library search now prefers newer items when score, favorite status, and quality score are tied.

### Verified
- `python -m pytest tests\test_context_packs.py tests\test_library_index.py tests\test_server_library_context.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.9.0 - 2026-05-08

### Added
- Local Library Index for searchable Creative Assets and References with deterministic scoring and score breakdowns.
- Library search and recommendation APIs for local, explainable retrieval without embeddings or external services.
- Persistent Context Packs under `.musicforge/context-packs/` with stale/hidden source validation.
- `context_pack_id` support for jobs, Project versions, variations, local/provider edits, provider previews, candidate groups, and Prompt A/B.
- Project Export and Final Export now include sanitized Context Pack summaries.
- Studio Library workflow with search, recommendation, Context Pack save/apply preview, and context selectors.
- Release-check now covers the v1.9 library/context-pack workflow.

### Scope
- v1.9.0 intentionally does not add vector databases, embeddings, audio fingerprinting, MP3, audio-to-MIDI, or automatic application of recommended context.

### Verified
- `python -m pytest tests\test_library_index.py tests\test_context_packs.py tests\test_server_library_context.py tests\test_projects.py::test_export_project_collects_context_pack_summaries tests\test_final_export.py::test_final_export_manifest_includes_context_pack_summary tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.8.0 - 2026-05-08

### Added
- Reference analysis reports for imported PCM WAV, MIDI, lyrics text, and style-note references.
- WAV summaries now include duration, sample rate, channels, sample width, peak, RMS, silence ratio, loudness hint, and bounded waveform envelopes.
- Lightweight Standard MIDI parser for format 0/1, PPQ, tempo, time signature, running status, program changes, note pairing, and role hints.
- MIDI reference slice suggestions, fixed-path slice MIDI/WAV previews, and note-based Creative Asset creation from slices.
- Studio References analysis tools with Analyze, MIDI slice generation, preview render/download, WAV envelope, MIDI track summaries, and slice asset actions.
- Project export, Final Export, provider reference summaries, and release-check now include bounded, sanitized analysis summaries.

### Scope
- v1.8.0 intentionally does not add MP3 import, audio-to-MIDI, audio transcription, BPM/key auto-detection, or heavy audio-analysis dependencies.

### Verified
- `python -m pytest tests\test_midi_analysis.py tests\test_reference_analysis.py tests\test_server_reference_analysis.py tests\test_server_auth.py tests\test_projects.py::test_export_project_includes_redacted_reference_refs tests\test_final_export.py::test_final_export_includes_sanitized_reference_refs_without_original_files tests\test_webui.py tests\test_references.py tests\test_provider_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.7.2 - 2026-05-08

### Fixed
- Value-level redaction now covers arbitrary Windows drive paths such as `D:\Music\...`.
- Value-level redaction now covers UNC and network-share style paths such as `\\server\share\...` and `//server/share/...`.
- Reference summaries, provider prompt summaries, Project export, Final Export, and release-check now share the expanded local-path redaction coverage.

### Verified
- `python -m pytest tests\test_references.py tests\test_projects.py tests\test_final_export.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.7.1 - 2026-05-08

### Fixed
- Reference metadata summaries now redact sensitive values embedded in free-text fields such as `source_note`, `license_note`, `text_excerpt`, and descriptions.
- Project export and Final Export now apply value-level redaction to reference summaries even when local artifact JSON was polluted.
- Reference import now rejects control-character and unsafe quoted filenames, and legacy/polluted filenames are safely downgraded before download.
- File downloads now emit sanitized `Content-Disposition` filenames with RFC 5987 `filename*` support.
- Reference import now rejects oversized request bodies before reading and base64-decoding them.

### Verified
- `python -m pytest tests\test_references.py tests\test_server_references.py tests\test_projects.py tests\test_final_export.py tests\test_assets.py tests\test_server_assets.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.7.0 - 2026-05-08

### Added
- Local Reference Library under `.musicforge/references/` for safe WAV, MIDI, lyrics text, and style-note imports.
- Reference import validates extension, header/UTF-8 content, size limits, path-like filenames, and duplicate SHA-256 content.
- Reference APIs for import/list/detail/update, hide/favorite/delete, fixed-path original download, Project link/unlink, and reference-to-asset conversion.
- `reference_refs` for jobs, Project versions, variations, local/provider edits, provider previews, candidate groups, and Prompt A/B.
- Project export and Final Export now include sanitized reference summaries without copying original reference files into final delivery bundles or ZIPs.
- Studio References workspace with safe import, search/filter, metadata editing, Project linking, asset conversion, and reference selectors.
- Release-check now covers reference import, dedupe, usage tracking, Project export, Final Export, and redaction behavior.

### Scope
- v1.7.0 intentionally does not add MP3 import, audio transcription, audio-to-MIDI, waveform analysis, BPM detection, or key detection.

### Verified
- `python -m pytest tests\test_references.py tests\test_server_references.py tests\test_server_auth.py -q`
- `python -m pytest tests\test_projects.py tests\test_final_export.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.6.1 - 2026-05-07

### Fixed
- Project export now redacts sensitive keys from asset reference `source` and `content_summary` metadata even if local artifact JSON was polluted.
- Final Export now applies the same secondary asset reference redaction before writing manifest summaries and `assets/<asset-id>.json`.

### Verified
- `python -m pytest tests\test_projects.py tests\test_final_export.py -q`
- `python -m pytest tests\test_assets.py tests\test_server_assets.py tests\test_projects.py tests\test_final_export.py tests\test_server_auth.py -q`
- `python -m song_agent.cli release-check`

## v1.6.0 - 2026-05-07

### Added
- Local Creative Asset Library under `.musicforge/assets/` with per-asset metadata, source fragments, events, MIDI preview, and optional WAV preview.
- Asset extraction from completed jobs, Project versions, and provider edit candidates.
- Asset references for job generation, Project version creation, variation, local/provider edit, provider previews, candidate groups, and Prompt A/B.
- Studio Assets workspace with search/filter, metadata editing, hide/favorite/delete, MIDI/WAV preview controls, extraction buttons, and asset selectors.
- Project export and Final Export now include sanitized asset reference summaries.
- Release-check now covers creative asset extraction, reuse, usage tracking, Project export, and Final Export asset refs.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.5.1 - 2026-05-07

### Fixed
- Stale provider edit candidate groups now return `409` for candidate MIDI/WAV downloads and candidate/group re-render endpoints.
- Prompt A/B creation now rolls back already-created candidate groups if a later template fails, preventing orphaned usage and UI artifacts.

### Verified
- `python -m pytest tests\test_server_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.5.0 - 2026-05-07

### Added
- Provider edit candidates now render MIDI previews and expose safe candidate MIDI download URLs.
- Candidate WAV previews can be rendered when the local renderer is configured, with Studio playback controls.
- Provider usage reports aggregate jobs and candidate groups by model, operation, and prompt template, with optional local pricing.
- Lightweight Prompt A/B experiments generate multiple candidate groups from different prompt templates for manual comparison.
- Release-check now covers candidate audition artifacts, usage reporting, and Prompt A/B smoke behavior.

### Verified
- `python -m pytest tests\test_candidate_groups.py tests\test_server_edits.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.4.1 - 2026-05-07

### Fixed
- Provider candidate apply now writes explicit `candidate_group_id` and `candidate_id` fields into the official child version edit metadata.
- Candidate-derived versions remain traceable to their selected candidate even if the original candidate group review artifacts are deleted later.
- Release-check now verifies provider candidate metadata survives candidate group deletion.

### Verified
- `python -m pytest tests\test_server_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.4.0 - 2026-05-07

### Added
- Provider Edit Candidate Groups for generating, storing, ranking, applying, and deleting multiple provider edit candidates.
- Built-in `provider-edit-candidates` prompt template and OpenAI-compatible multi-candidate edit response support.
- Deterministic candidate scoring based on quality, validator status, provider confidence, novelty, and instruction fit.
- Project Candidate APIs and Studio Candidates tab for Generate Candidates, candidate review, Apply Candidate, and Delete Candidate Group.
- Project provider usage now includes candidate group generation usage in addition to applied provider edit versions.
- Release-check coverage for the v1.4 multi-candidate provider edit workflow.

### Verified
- `python -m pytest tests\test_candidate_groups.py tests\test_candidate_scoring.py tests\test_provider_edits.py tests\test_provider_client.py tests\test_prompt_templates.py tests\test_server_edits.py tests\test_server_auth.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.3.1 - 2026-05-07

### Fixed
- Removed a duplicate Project edit-preview route branch from the Studio server router.
- Provider edit previews now record a parent song-plan source hash and reject stale applies after the parent version changes.
- Provider edit previews can no longer be applied more than once.
- OpenAI-compatible provider edit responses now preserve returned `usage` token counts and request ids for preview/apply audit records.
- Provider edit apply usage now reuses preview usage data instead of always writing zero-token placeholders when the provider supplies usage.

### Verified
- `python -m pytest tests\test_provider_client.py tests\test_provider_edits.py tests\test_server_edits.py tests\test_server_auth.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.3.0 - 2026-05-07

### Added
- Prompt Template Store with built-in provider edit templates, local overrides under `.musicforge/prompt-templates.json`, and Studio controls.
- Provider edit patch schema for constrained natural-language edits, including operation, chord, target, size, and secret/path validation.
- Provider-backed Project edit preview/apply APIs that keep previews out of official Project versions until applied.
- Studio Provider Edit workflow with Generate Preview and Apply Preview controls.
- Provider edit usage/audit records and project-level usage summaries without storing API keys.
- Release-check coverage for v1.2.1 hardening and v1.3 provider edit smoke.

### Fixed
- Final Export rebuilds now invalidate stale `final-export.zip` files and do not carry old ZIP manifest metadata forward.
- Edit preset payload validation now checks deeper nested data, size limits, secret-like fields, and merged intent validity.
- Project Compare handles missing left/right inputs, corrupt edit metadata, old versions, and missing artifacts without server errors.
- Studio Compare uses responsive panels and horizontal table scrolling for long text and narrow screens.

### Verified
- `python -m pytest tests\test_prompt_templates.py tests\test_provider_edits.py tests\test_provider_client.py tests\test_server_edits.py tests\test_server_projects.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.2.0 - 2026-05-06

### Added
- Edit preset library with built-in presets, local user presets under `.musicforge/edit-presets.json`, Studio preset apply/save controls, and Project edit preset metadata.
- Project version Compare API and Studio A/B review view with quality, gate, edit metadata, section, track, MIDI, and WAV availability.
- Safe Final Export ZIP generation and download, including ZIP sha256, size, and entry count recorded in the final export manifest.
- Project search and filters for name/description/version text, status, hidden projects, and variant type.
- Release-check coverage for the v1.2 workflow: preset edit, compare, final export, and ZIP entry safety.

### Verified
- `python -m pytest tests\test_edit_presets.py tests\test_project_compare.py tests\test_final_export.py tests\test_server_edits.py tests\test_server_projects.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.1.1 - 2026-05-06

### Fixed
- Section harmony edits now reject unsupported explicit payload chord names such as `Hmaj7` before writing `SongPlan.sections[].chords`.
- Instruction-parsed harmony chords are filtered through the supported local MIDI chord set, with empty results falling back to the safe default progression.

### Verified
- `python -m pytest tests\test_edits.py tests\test_server_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.1.0 - 2026-05-06

### Added
- Local non-destructive Project edit workflow with `EditIntent`, target validation, deterministic section/track/lyrics/melody edits, and edit-derived child versions.
- Edit jobs that write `data/edit-metadata.json`, regenerate SongPlan/MIDI/validator/summary artifacts, and preserve parent run artifacts.
- Project edit APIs, edit target preview, job edit metadata API, Project diff edit/section/track summaries, and Studio Edit controls.
- Release-check edit smoke coverage for parent protection and child MIDI generation.

### Verified
- `python -m pytest tests\test_edits.py tests\test_server_edits.py tests\test_server_projects.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.0.2 - 2026-05-06

### Fixed
- Quality Gate `require_stems=True` now rejects stem manifests that do not cover all note-bearing SongPlan tracks, including empty manifests with matching source hashes.

### Verified
- `python -m pytest tests\test_project_quality.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.0.1 - 2026-05-06

### Fixed
- Final Export now rejects polluted stem manifest paths outside `runs/<job-id>/stems/` and skips the stem bundle instead of copying non-stem files.
- Quality Gate `require_stems=True` now validates that each note-bearing stem MIDI file exists and that manifest paths remain inside the job stems directory.

### Verified
- `python -m pytest tests\test_final_export.py tests\test_project_quality.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.0.0 - 2026-05-06

### Added
- Project version lineage with `parent_version_id`, `variant_type`, and `change_summary`.
- Project variation API for creating child versions from any existing version with a controlled request patch.
- Project Quality Gate configuration, per-version evaluation, evaluate-all, and final-version blocking with force override events.
- Final Export Bundle under `.musicforge/projects/<project-id>/final-export/` with manifest, README, Project export, SongPlan, MIDI, optional WAV, quality report, and non-stale stems.
- Studio Project controls for Variation, Quality Gate, Final Export, lineage columns, gate status, and per-version actions.
- Release-check final export smoke coverage.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli release-check`
- `python -m song_agent.cli doctor`
- Local single and multinode CLI smoke.
- Studio v1 page smoke; only `favicon.ico` 404 was observed.

## v0.9.1 - 2026-05-06

### Fixed
- CLI `--force` now removes stale `stems/` artifacts along with `data/`, `renders/`, and `logs/`.

### Verified
- `python -m pytest tests\test_cli.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v0.9.0 - 2026-05-06

### Added
- Project workspace metadata under `.musicforge/projects/<project-id>/` with project state, versions, events, and export manifests.
- Project APIs for create/list/detail, version creation, existing-job import, selected/final version markers, diff, export, hide/unhide, and metadata-only delete.
- Studio Projects workspace with project list, version table, new version creation, existing job import, selected/final controls, compare, export JSON, and events.
- Batch CSV optional `project`, `version_name`, and `version_note` columns with automatic completed-job archival into Projects.
- Batch export fields for project/version links.

### Verified
- `python -m pytest -q`
- Project API/auth tests and Batch Project archival tests.

## v0.8.1 - 2026-05-06

### Fixed
- Stem manifests now include a SongPlan source hash and stale manifests are invalidated when `data/song-plan.json` changes.
- Job reruns and node retry now clear existing stem MIDI/WAV artifacts so regenerated songs cannot expose previous-version stems.
- Stem MIDI/WAV download routes now reject stale manifests before serving files.
- Partial stem-audio renders now report `partial_completed` instead of top-level `not_started`.

### Verified
- `python -m pytest tests\test_stems.py tests\test_server_stems.py tests\test_server_nodes.py tests\test_batch_stems.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v0.8.0 - 2026-05-06

### Added
- Stem manifest and per-track MIDI export under `runs/<job-id>/stems/`.
- Job APIs for listing stems, rendering MIDI stems, rendering stem WAV files, and downloading individual stem MIDI/WAV artifacts.
- Studio Stems tab with Render Stems, Render Stem Audio, per-track downloads, audio controls, and simple Solo/Mute actions.
- Batch stem rendering APIs for MIDI stems, stem audio, failed stem retry, and failed stem-audio retry.
- Batch item stem metadata and export fields for manifest path, stem count, completed stem audio count, and stem errors.
- Path-safe stem file access that resolves downloads from the manifest instead of trusting request paths.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli release-check`
- Local single and multinode CLI smoke.
- Job and batch stem API tests with fake WAV renderer.

## v0.7.1 - 2026-05-06

### Fixed
- Runtime Timeline and Quality views now infer quality metadata for legacy `song-plan.json` files without rewriting artifacts.
- `GET /api/jobs/<job-id>/quality` now returns a clear 409 while `song-plan.json` is not available.
- Validator views merge quality warnings with validator warnings, including when `validator-report.json` is missing.
- Quality analyzer false positives were tightened for instrumental detection, bass-root octave/passing-note cases, and hook repetition.
- Provider-backed SongPlan output now gets local quality inference when a provider omits the optional `quality` field.
- Studio Quality tab now shows a friendly pending message plus warning and critic summary blocks.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli release-check`
- Local quality API smoke for pending jobs and legacy SongPlan inference.

## v0.7.0 - 2026-05-06

### Added
- Compatible SongPlan quality metadata with motif, section intent, hook sections, warnings, and dimension scores.
- `song_agent.music_quality` analyzer for structure, melody, harmony, arrangement, and lyric-fit scoring.
- Quality-aware deterministic and multinode generation with lifted chorus melody, section energy/tension/density, and hook metadata.
- Critic reports now include quality issues, dimension scores, and summaries; repair can apply low-risk quality metadata fixes.
- Provider prompts and mock provider node outputs now describe energy, tension, density, role, transition, and hook candidates.
- `GET /api/jobs/<job-id>/quality` and Studio Quality tab for overall score, dimension scores, motif, section intents, and issues.
- Timeline view now includes section role, energy, tension, density, and hook markers.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- Local single CLI smoke with quality metadata.
- Local multinode CLI smoke with quality metadata.

## v0.6.2 - 2026-05-06

### Added
- Batch audio render APIs for `POST /api/batches/<batch-id>/render-audio` and `POST /api/batches/<batch-id>/render-failed-audio`.
- Batch item audio metadata: `audio_status`, `audio_path`, and `audio_error`.
- Batch export now includes WAV render status and path information.
- Studio Batch actions for Render Audio and Render Failed Audio, plus per-item audio status and WAV path columns.

### Fixed
- JSON artifacts are written with same-directory atomic replacement to avoid Studio polling or background runners reading partially written files.

### Verified
- `python -m pytest -q`
- Batch audio smoke for missing renderer, missing MIDI, partial success, retry failed audio, and export metadata.

## v0.6.1 - 2026-05-05

### Fixed
- Public unauthenticated `/api/info` no longer returns local filesystem paths when Studio auth is enabled.
- Authorized `/api/info` requests still return full local Studio metadata for the unlocked session.

### Verified
- `python -m pytest -q`
- Auth-mode `/api/info` smoke for unauthenticated and Bearer-authenticated requests.
- `python -m song_agent.cli release-check`

## v0.6.0 - 2026-05-05

### Added
- Studio access-token configuration with `--access-token` and `MUSICFORGE_ACCESS_TOKEN`.
- Startup protection that refuses non-loopback hosts without an access token.
- Bearer-token API authentication for jobs, provider, renderer, batch, artifacts, audio, and file-system actions.
- Public `/api/info` auth status that avoids returning sensitive config details.
- Studio access-token prompt using `sessionStorage`, authenticated fetch, and 401 lock-back behavior.
- `python -m song_agent.cli release-check` for local release safety checks.
- Tests for auth config, CLI startup protection, server auth, Studio auth UI, and release-check helpers.

### Verified
- `python -m pytest -q`
- localhost no-token Studio smoke.
- non-localhost no-token startup rejection.
- Bearer auth API smoke for missing, wrong, and correct tokens.
- `python -m song_agent.cli release-check`

## v0.5.0 - 2026-05-05

### Added
- Local audio renderer configuration under `.musicforge/renderer.json` with environment variable overrides.
- Renderer APIs for read, save, reset, and test.
- FluidSynth MIDI-to-WAV command builder using list argv and `shell=False`.
- Manual `POST /api/jobs/<job-id>/render-audio` to render `runs/<job-id>/renders/song.wav`.
- `GET /api/jobs/<job-id>/audio` for WAV playback/download.
- Audio artifact discovery and validator view audio metadata after successful render.
- Studio Renderer Settings form, Render Audio action, WAV download link, and `<audio controls>` playback.
- Fake-runner tests so automated validation does not require FluidSynth or a real SoundFont.

### Verified
- `python -m pytest -q`
- Local renderer API smoke with missing SoundFont error.
- Fake renderer smoke for `render-audio` and WAV endpoint.
- Studio page smoke for Renderer Settings and audio controls.

## v0.4.0 - 2026-05-05

### Added
- CSV batch import with row-level validation for required fields, duration, tempo, generation mode, pipeline mode, and concurrency.
- Persistent batch metadata under `.musicforge/batches/<batch-id>/` with `batch.json`, `items.json`, `events.jsonl`, and generated `export.json`.
- Batch APIs for list, detail, import, launch, pause, resume, retry failed items, export, hide, unhide, delete, and open folder.
- Standard-library batch runner that launches existing job runs with a configurable max concurrency from 1 to 4.
- Batch retry behavior that creates new jobs for failed or cancelled items while preserving completed items.
- Studio Batch workspace for CSV file/text import, launch controls, pause/resume, retry failed, export, hide/unhide/delete, and job-detail linking.
- Tests for batch parsing, persistence, safe deletion, server endpoints, concurrency limits, provider readiness, and Studio batch controls.

### Verified
- `python -m pytest -q`
- Local batch API smoke for import, launch, completion, export, hide, and delete.

## v0.3.2 - 2026-05-05

### Fixed
- `harmony_planner` retry now invalidates and reruns `arrangement_planner`, keeping section chords and chord/bass tracks consistent.
- Node retry API now starts retry work in a background thread and returns `202 Accepted`, so Studio is not blocked by slow provider calls.

### Verified
- `python -m pytest -q`
- Local multinode harmony retry smoke.
- Node retry API returns `202` and job status is polled to completion.

## v0.3.1 - 2026-05-05

### Added
- Explicit multinode dependency graph with upstream, downstream, and affected-node helpers.
- Node invalidation metadata: `invalidated_at`, `invalidated_by`, `retry_count`, `last_error`, and `depends_on`.
- NodeStore helpers for invalidating nodes, reading required cached outputs, and checking completed node records.
- `rerun_multinode_from_node()` to reuse upstream node outputs and rerun the selected node plus downstream nodes.
- Real `POST /api/jobs/<job-id>/nodes/<node-name>/retry` behavior for multinode jobs.
- `GET /api/jobs/<job-id>/nodes/<node-name>/dependencies` for retry confirmation and inspection.
- Studio Retry node controls in the Nodes tab with affected downstream confirmation.

### Changed
- Node retry rewrites final `song-plan.json`, `song.mid`, `validator-report.json`, job summary, and job state.
- Node summaries now include retry/invalidation/dependency metadata and `can_retry`.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\v031-single-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v031-multinode-check --force --pipeline-mode multinode`
- Studio API smoke for local multinode node retry and mock-provider multinode node retry.

## v0.3.0 - 2026-05-05

### Added
- Multi-agent music planning node schemas for brief, style, structure, lyrics, harmony, melody, arrangement, critic, and repair records.
- Safe `NodeStore` persistence under `runs/<job-id>/data/nodes/`.
- Deterministic multinode pipeline that writes every node record and builds the final MIDI-safe `SongPlan`.
- Provider-backed planning nodes for brief, style, structure, lyrics, and harmony with strict JSON/schema validation.
- Critic and repair nodes for basic arrangement checks, missing bass/drums repair, and MIDI note clamping.
- `pipeline_mode=single|multinode` for CLI and Studio jobs.
- `run-options.json` to keep resume behavior tied to generation and pipeline modes.
- Node inspection APIs: `GET /api/jobs/<job-id>/nodes` and `GET /api/jobs/<job-id>/nodes/<node-name>`.
- Studio Nodes tab with node summaries and full JSON preview.
- Provider node prompt files under `song_agent/prompts/nodes/`.

### Changed
- Job state now records both `generation_mode` and `pipeline_mode`.
- Multinode resume checks node builder output instead of only `song-plan.json`.
- Resume now rejects generation or pipeline mode mismatches instead of reusing incompatible artifacts.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\v030-single-local-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v030-multinode-local-check --force --pipeline-mode multinode`
- Local Studio API smoke with mock provider, `generation_mode=provider`, `pipeline_mode=multinode`, node API reads, and masked provider snapshot.

## v0.2.1 - 2026-05-05

### Added
- Job heartbeat fields and retry metadata in persisted job state.
- Pipeline stage-boundary cancellation checks.
- `POST /api/jobs/<job-id>/retry` for failed, stalled, and interrupted jobs.
- Watchdog tick and background watchdog thread for stale running jobs.
- Studio display for attempt count, retry count, heartbeat, and stalled state.
- Studio Retry action for failed, stalled, and interrupted jobs.
- Tests for cancel boundaries, retry behavior, provider snapshot masking, watchdog, and UI retry controls.

### Fixed
- Provider request errors now redact echoed keys, bearer tokens, and token-like fields before surfacing errors.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli examples\song_request.json --out runs\v021-local-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v021-local-generate-check --force`
- Local mock provider smoke with provider-mode job, retry path, and masked snapshot.

## v0.2.0 - 2026-05-05

### Added
- Local provider configuration storage under `.musicforge/provider.json`.
- Masked provider public config and environment variable overrides.
- Provider APIs for read, save, reset, and test.
- Mock provider client for tests and local UI smoke.
- OpenAI-compatible chat completions client using the Python standard library.
- Provider-backed SongPlan pipeline with strict JSON, schema, and validator checks.
- Studio provider settings form and `local` / `provider` generation mode selector.
- Provider job snapshots written as masked `provider-snapshot.json`.
- `python -m song_agent.cli doctor` and optional `--provider-test`.
- Tests for provider config, provider API, clients, provider pipeline, job integration, and doctor CLI.

### Changed
- Local deterministic generation remains the default and does not require provider config.
- Provider mode fails jobs cleanly when provider calls or model output validation fail.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli examples\song_request.json --out runs\v020-local-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v020-local-generate-check --force`
- Local panel smoke with mock provider: save, test, provider-mode job, timeline/tracks/validator, masked snapshot.

## v0.1.2 - 2026-05-05

### Added
- Runtime view builders for timeline, tracks, validator, and summary data from existing run artifacts.
- Job APIs for `timeline`, `tracks`, and `validator` views.
- Studio tabs for Timeline, Tracks, Validator, SongPlan JSON, Logs, and Artifacts.
- Job management actions for hide, unhide, cancel, and delete.
- Hidden job filtering with `GET /api/jobs?include_hidden=1`.
- Startup recovery that marks leftover `queued`, `running`, `paused`, and `waiting_retry` jobs as `interrupted`.
- Backward-compatible `job-state.json` loading for newly added job fields.
- Tests for runtime views, job action boundaries, safe deletion, and startup recovery.

### Changed
- `JobState` now tracks deletion/interruption metadata and start/finish timestamps.
- Runtime artifact endpoints return explicit JSON errors when required artifacts are not ready.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\v012-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v012-generate-check --force`
- Local panel smoke through `python -m song_agent.cli serve --host 127.0.0.1 --port 8787`

## v0.1.1 - 2026-05-05

### Added
- Local MusicForge Studio web panel served by `python -m song_agent.cli serve`.
- `generate` CLI subcommand while preserving the original positional CLI flow.
- Standard-library HTTP API for info, templates, jobs, events, artifacts, song plans, and MIDI downloads.
- Background job runner with `job-state.json` persisted under each run directory.
- Single-page HTML/CSS/JS workspace for creating jobs, polling status, viewing logs, inspecting SongPlan JSON, and downloading MIDI.
- Startup discovery of completed jobs with persisted job state.
- Tests for web UI shell and server job flow.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\panel-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\panel-generate-check --force`
- `python -m song_agent.cli serve --host 127.0.0.1 --port 8787`

## v0.1.0 - 2026-05-05

### Added
- Local graph runner with step events and run summaries.
- Artifact-first project IO under `runs/<run-id>/`.
- Deterministic composer for a local, model-optional MIDI demo.
- `SongPlan` serialization, deserialization, and deterministic validation.
- No-dependency Standard MIDI writer with melody, chords, bass, and drums tracks.
- CLI full local generation flow from request JSON to `song-plan.json` and `song.mid`.
- `--resume` request consistency guard.
- `--force` overwrite path for known run artifacts.
- CLI handling for expected local errors without Python tracebacks.
- MIDI semantic tests for header, tracks, tempo, programs, drum channel, note pairs, and EOT.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\release-check --force`
