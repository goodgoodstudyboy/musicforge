# Changelog

## v13.5.0 - 2026-07-15

- Replaced runtime API route AST discovery with a fixed, versioned 117-route manifest and removed every `legacy-compatible` route schema.
- Split the CLI, API routes, API runtime, Program HTTP adapter, and Studio browser application into bounded production modules while preserving command/help contracts and external APIs.
- Added real browser ES modules served through a fixed script allow-list; the Studio entry is 14 lines and all panel modules are loaded and tested.
- Centralized the remaining compatibility imports behind one application anti-corruption facade per legacy module, reducing active compatibility edges from 407 to 227 with no active cycles or boundary violations.
- Added `v135.interface_decomposition_smoke` and hard checks for interface limits, explicit route registration, Web module references, and the compatibility boundary.

## v13.4.0 - 2026-07-15

- Moved all active Unified Release Program stores and verifiers into the physical `domains/program` bounded context while retaining short flat compatibility exports.
- Added a typed Program application service, explicit API route registry, and compact CLI command registry so active interfaces dispatch through application use cases instead of importing Stores.
- Removed every compatibility import from the Program domain/application core, kept the active production graph acyclic, and reduced repository-wide active compatibility edges from 494 to 407.
- Added Program vertical-slice architecture, API dispatch, CLI handler-size, compatibility-wrapper, and application round-trip checks.

## v13.3.0 - 2026-07-14

- Made `ProgramStateRepository` the write authority for all 13 active Program stores, with content-addressed state, SQLite current versions, event chains, indexes, and validated JSON projections.
- Added recoverable projection transactions for crashes after event append and after projection write, integrated into the shared persistence recovery command.
- Migrated a tracked six-document v12.13 Program workspace fixture with verified backup, non-empty authority import, and byte-identical source rollback.
- Reduced active production imports of legacy `projectio` from 36 to 10 and total active-to-compatibility imports from 520 to 494.

## v13.2.0 - 2026-07-14

- Registered all 13 active Program verifiers with canonical package layouts, external proofs, runtime identities, and lifecycle binding requirements.
- Added a shared differential attack corpus for every active verifier and lifecycle Store, replacing token-only LTS migration claims with executable adoption reports.
- Routed active Program signoff sealing, reset proofs/transitions, and final archive snapshots through `SignoffService`, `ResetService`, and `ArchiveBuilder`.
- Moved version authority to `platform.version` and reduced active-to-compatibility imports from 521 to 520.

## v13.1.0 - 2026-07-14

- Added a previous-release architecture ratchet with immutable baseline hashes, explicit compatibility debt ownership, interface no-growth limits, and independently recomputed reviewer evidence.
- Reduced active production imports into compatibility code from 522 to 521 by moving interface document writes onto platform persistence.
- Added adversarial architecture tests for baseline loosening, hidden compatibility reclassification, new legacy imports, and oversized interface handlers.

## v13.0.2 - 2026-07-14

- Fixed Python 3.11 static type narrowing for manifest size validation so hosted architecture checks exercise the v13.0.1 security hardening successfully.

## v13.0.1 - 2026-07-14

- Hardened the shared Verification Kernel against directory, symlink, special-file, duplicate, size, and frozen-archive attacks in strict and relaxed modes.
- Bound Evidence Graph identities to runtime and external verifier facts instead of manifest claims.
- Made shared Change Request reset authorization fail closed and normalized active Program reset producers.

## v13.0.0 - 2026-07-13

### Changed
- Completed the modular-monolith cutover with an acyclic active production graph and explicit creation, Studio, quality, delivery, trust, and Program bounded contexts.
- Unified active Program verification, lifecycle, mutable persistence, Evidence Graph policy gates, interface registries, and domain-owned release checks on the v12.14-v12.20 kernels.
- Removed the superseded release-check matrix/runner facades; retained the small historical smoke adapter as archive-only compatibility through v13.1.
- Partitioned every active test into exactly one unit, contract, or integration CI shard; pytest uses a managed short temporary root and reclaims each test tree so xdist evidence runs do not exhaust runner disks.
- Restricted quality runs to master/PR/manual triggers, disabled matrix fail-fast for complete diagnostics, and upgraded official checkout/setup-python actions to their Node 24 releases.
- Made CLI parser snapshots semantic instead of depending on Python-version-specific `argparse` line wrapping, and made quality jobs fetch release tags required by the v12.13/v13 source comparison.

### Added
- Schema-2 v13 migration orchestration with dry-run, verified backup enforcement, source preservation, rollback rehearsal, and a verified migration evidence archive.
- `v13` release-check profile and `v130.lts_cutover_smoke` covering architecture hard limits, migration tamper rejection, reviewer package completeness, and path/secret safety.
- Machine-readable v12.13/v13 source comparison, verifier/lifecycle/persistence migration matrices, compatibility inventory, security attack matrix, and final reviewer package generation.

### Security
- Active verifiers have no private ZIP safety implementation; active lifecycle stores have no private history/reset hash algorithm.
- Verification Kernel packages now require a manifest file index and fail closed for missing or non-file ZIP paths; Evidence Graph package-directory inputs also become structured blockers.
- v13 migration evidence emits and requires an external anchor for final LTS verification, blocking internally re-signed target/report/manifest substitutions.
- Release and GA active gates are policy plus evidence-manifest driven and runtime re-verify current external evidence.
- Modular-core import cycles and domain-to-interface dependencies are hard-zero release blockers; the remaining flat compatibility cycles and 522 inbound compatibility edges are disclosed and frozen as no-growth debt.
- POSIX temporary paths and raw symlink targets are rejected or redacted consistently on Windows and Linux runners before cleanup or evidence serialization.

### Performance
- Default pytest runs the complete active suite without duplicating archive-only release-check smokes; those smokes remain intact in four Windows/Linux nightly shards and are distributed by test item so the single archive module uses every xdist worker.
- PR unit and security suites exclude explicitly marked active-slow evidence replays; nightly runs those tests by layer and deterministic two-way partition. Local unit fast is about three minutes, while the measured slow-unit partitions are about 23 and 14 minutes.
- The local aggregate `pytest.full` check keeps a hard 60-minute budget; the 30-minute target applies to each CI/nightly shard. Duplicate-entry warnings intentionally created by adversarial ZIP tests are suppressed only for that aggregate command so unexpected warning classes remain visible.
- The relocated historical provider resolves the repository root explicitly, preserving v10 GA smoke compatibility after the release-check package split.
- Hosted quality shards use two scoped workers rather than oversubscribing four workers on two-core runners; tests that start an HTTP server are assigned to integration, and fast integration coverage is split across two deterministic jobs to keep each hosted shard under the 30-minute target. Cross-platform redaction assertions target public evidence summaries while local project exports retain their documented artifact paths. HTTP clients and asynchronous job polling use bounded hosted-runner-safe deadlines, while local and nightly full coverage retain their existing partitioning.

## v12.20.0 - 2026-07-13

### Changed
- Split release engineering into `song_agent.release_check` matrix, runner, performance, fixture, and domain-check packages; the 26k-line historical smoke implementation is isolated under `checks/legacy`.
- Reduced `song_agent/release_checks.py` to a lazy compatibility facade while preserving historical private smoke imports through the v13 cutover.
- Moved v1-v11 and v12.0-v12.8 monolithic checks out of `latest`/`ga`; their security assertions remain in full, nightly, and explicit historical profiles.
- Removed the GA production dependency on release engineering by injecting the release-check executor from CLI/API interfaces.

### Added
- Windows/Linux CI for architecture, unit/contract shards, security verifiers, latest/GA profiles, package installation, and nightly legacy coverage.
- Pytest test-layer markers, scoped Ruff/mypy/coverage configuration, a machine-readable deprecation catalog, migration runbook, and architecture review runbook.
- `v1220.release_check_governance_smoke` and domain ownership metadata in matrix JSON.

### Performance
- Current checks use a 90-second hard default budget; exceptions require a reason and expiry.
- v12/latest/GA profile budgets are hard gates instead of migration-period warnings.

## v12.19.0 - 2026-07-13

### Added
- Runtime-verified Evidence Graph nodes and the seven built-in Release, Distribution, GA, Handoff, and Continuity policy profiles.
- A bounded-context capability registry that fixes package types, verification report types, runtime verifier adapters, external proof requirements, and interface metadata.
- `ga-check --policy/--evidence-manifest` and matching offline GA report verification, plus a hard Release signoff policy gate that cannot be bypassed with `force=true`.
- release-check `v1219.evidence_policy_smoke` covering stale passed reports, duplicate verification identity, path redaction, profile inventory, and runtime package tamper.

### Changed
- Consolidated Studio's primary navigation into Create, Studio, Quality, Delivery, Trust, Program, and System workspaces.
- Marked legacy GA `--require-*` evidence flags as v13 removal candidates; new gates use policy plus an evidence manifest.

### Security
- Policy profiles cannot disable integrity, current-generation, runtime-verification, or no-blocker invariants.
- HTTP policy manifests and all referenced evidence are confined to the MusicForge workspace; one verification report cannot satisfy multiple component identities.

## v12.18.0 - 2026-07-13

### Added
- Typed CLI `CommandSpec` and HTTP `RouteSpec` registries with deterministic machine-readable inventories, duplicate registration rejection, help/output compatibility snapshots, and a v12.18 release-check smoke.
- Bounded-context CLI command modules and HTTP route mixins for creation, Studio, quality, delivery, trust, Program, maintenance, and release engineering.
- Package-resource Studio HTML, CSS, JavaScript, and panel metadata loaded through `importlib.resources` without adding a Node build chain.

### Changed
- Reduced `song_agent/cli.py`, `song_agent/server.py`, and `song_agent/webui.py` to compatibility facades below their 500/1000/200-line architecture limits.
- Preserved all 173 command entrypoints, current parser help, exit-code policy, 113 concrete API dispatch entries, auth behavior, HTTP contracts, and rendered Studio output.
- Made interface ownership explicit in the modular-monolith architecture guardrail.

### Verified
- `python -m pytest tests\test_interface_registry.py tests\test_cli.py tests\test_cli_doctor.py tests\test_cli_serve_auth.py tests\test_server.py tests\test_server_auth.py tests\test_server_assets.py tests\test_webui.py -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`
- `python -m song_agent.cli release-check --profile latest --skip-tests --json`

## v12.17.0 - 2026-07-13

### Added
- A standard-library SQLite persistence kernel with WAL mode, foreign keys, busy timeout, explicit transactions, schema migrations, optimistic workflow records, and transactional ID allocation.
- A PID-aware, cross-process, thread-reentrant workspace write lock shared by CLI and HTTP Store instances; stale recovery requires a confirmed dead owner or explicit force and never expires a live owner by lease time alone.
- A generation-based File Unit of Work with staged fingerprints, transaction intents, atomic current pointers, database commit metadata, commit markers, crash injection, and restart recovery.
- Explicit legacy v12.9-v12.12 migration planning, verified backups, source hash ledgers, mutable-state indexing, idempotent apply, verified rollback, and a `song-agent-state` maintenance command.
- release-check `v1217.persistence_kernel_smoke`, covering WAL, optimistic conflict, subprocess serialization, crash recovery, corruption blocking, migration, redaction, and Store adoption.

### Changed
- All active v12 Program/Continuity Stores now use one workspace-scoped cross-process lock facade instead of independent process-local `RLock` instances.
- v12.9-v12.12 mutable workflow summaries are synchronized into SQLite as public-safe status/generation/fingerprint indexes; immutable evidence and all offline verifier authority remain filesystem based.
- Read-only verifier modules remain lock-free and independent of the local database.

### Verified
- `python -m pytest tests\test_persistence_kernel.py tests\test_release_check.py::test_v1217_persistence_kernel_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- Program and Program Operations Store regression suites under the cross-process lock facade.
- Crash boundaries before/after generation pointer and database commit, corrupt recovery, migration backup failure, rerun, and rollback.

## v12.16.0 - 2026-07-13

### Added
- A shared Evidence and Lifecycle Kernel with `HistoryChain`, `SignoffService`, `ChangeRequestService`, `ResetService`, `GenerationService`, immutable snapshot guards, archive construction, and stable external evidence manifests.
- Explicit, non-mutating history migration copies with source/target fingerprints, schema versions, row counts, and rollback paths.
- Lifecycle attack tests for missing and reordered history, externally detected full resign, wrong CR action/target/source, re-signed approval, CR reuse, generation mixing, export mutation, and ZIP trailing data.
- release-check `v1216.lifecycle_kernel_smoke`, included in v12, latest, and GA profiles.

### Changed
- Migrated active v12 Program, Operations, Handoff, Vault, Vault Operations, Continuity, Acceptance, Command Center Signoff, Receiver Acceptance, and both Change Control chains to shared history primitives without changing public evidence layouts.
- Centralized reset authorization and generation document construction while retaining each domain's runtime current-source and external-evidence checks.
- Kept legacy signed evidence read-only; migration is explicit and creates a rollback copy rather than rewriting historical JSONL.

### Verified
- `python -m pytest tests\test_lifecycle_kernel.py tests\test_release_check.py::test_v1216_lifecycle_kernel_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- Program, Operations, Handoff, Vault Operations, Continuity, Signoff, Acceptance, reset, and successor-generation regression suites.
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`
- `python -m song_agent.cli release-check --profile latest --skip-tests --json`

## v12.15.0 - 2026-07-13

### Added
- A platform Verification Kernel with shared package contracts, deterministic verification reports, hashing, ZIP central-directory and trailing-data checks, fixed layout and manifest validation, redaction scanning, history-chain validation, and external evidence identity matching.
- `EvidenceRef` and `PackageSpec` contracts for stable component identities and explicit required, optional, dynamic, and nested package layouts.
- A differential kernel attack matrix covering missing and extra entries, duplicates, dangerous paths, raw backslashes, `.MusicForge`, nested ZIPs, trailing data, manifest spoofing, redaction, and wrong package types.
- release-check `v1215.verification_kernel_smoke`, included in v12, latest, and GA profiles.

### Changed
- Migrated all 13 active v12 Program/Continuity verifier modules and their 18 public package verification entry points to the shared Verification Kernel while retaining domain semantic checks and public CLI/API compatibility.
- Unified verification report generation and removed duplicated hashing, ZIP path safety, trailing-data, redaction, and report-envelope helpers from migrated verifiers.
- Moved architecture and Verification Kernel smoke implementations out of the `release_checks.py` mega-file and lowered the duplicate security-helper architecture ratchet.

### Verified
- `python -m pytest tests\test_verification_kernel.py tests\test_release_check.py::test_v1215_verification_kernel_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- Active Program, Operations, Handoff, Vault, Continuity, Acceptance, Command Center, Signoff, Receiver Acceptance, and Change Control verifier regression suites.
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`
- `python -m song_agent.cli release-check --profile latest --skip-tests --json`

## v12.14.0 - 2026-07-12

### Added
- A checked-in modular-monolith architecture baseline with explicit ownership for every Python module, import-cycle inventory, dependency exceptions, mega-file line budgets, and duplicate ZIP-security helper budgets.
- AST-based architecture guardrails that reject new boundary violations, unclassified modules, ownership drift, import cycles, forbidden interface dependencies, mega-file growth, and security-helper duplication.
- Platform contracts plus application-layer homes for job state, generation orchestration, and Release Audio Campaign coverage, while preserving the existing CLI and HTTP compatibility imports.
- Current/target architecture documentation, dependency rules, debt ownership, and ADRs for the modular monolith, verification kernel, and persistence authority.
- release-check `v1214.architecture_guardrails_smoke`, included in the v12, latest, and GA profiles with machine-readable architecture metrics.

### Changed
- Removed the production `server -> cli` dependency, the `mix_render -> server` dependency, and private Release-check imports from the HTTP interface.
- Updated the repository layout documentation to make platform, application, domain, interface, and release-engineering ownership explicit.

### Verified
- `python -m pytest tests\test_architecture_boundaries.py tests\test_architecture_metrics.py tests\test_release_check.py::test_v1214_architecture_guardrails_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`
- `python -m song_agent.cli release-check --profile latest --skip-tests --json`

## v12.13.0 - 2026-07-12

### Added
- Release-check performance budgets with per-check duration limits, slow-check reporting, over-budget reporting, and profile-level budgets in JSON and timing reports.
- A process-scoped v12 Continuity fixture cache that builds trusted evidence once, snapshots it, and restores every attack case into an isolated stable-path checkout.
- Split v12.9-v12.12 checks for semantics, ZIP security, external evidence binding, signed mutation, GA gates, and thin integration; the original monolithic checks remain available in the `full` profile.
- Fingerprint-keyed memoization inside fixture preparation avoids repeating deep verification for identical immutable inputs while invalidating on any ZIP, report, binding, response, or Accepted Evidence byte change.
- `v1213.release_check_acceleration_smoke` covering cache hits, checkout isolation, split selection, `--only`, `--since`, budget summaries, and preservation of functional failures during budget warnings.

### Verified
- `python -m pytest tests\test_release_check_fixtures.py tests\test_release_check_performance.py tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py tests\test_release_check.py::test_v1213_release_check_acceleration_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --since 12.9 --skip-tests --json` (`16/16` passed in about 239 seconds on the release workstation.)
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json` (`25/25` passed in about 346 seconds.)
- `python -m song_agent.cli release-check --profile latest --skip-tests --json` (`80/80` passed in about 461 seconds.)

## v12.12.0 - 2026-07-11

### Added
- Receiver Acceptance Change Control with approved, action-scoped, single-use Change Requests, reset-time proof/binding sidecars, `reset_pending` state, preserved quorum policy, and successor generation signoff.
- Reset rotates the prior Review Pack, response proofs, Accepted Evidence, Board, Archive, and verification report into the historical generation; a successor cannot reuse the previous generation's reviewer evidence.
- Lifecycle Audit Archive with hash-chained events, request/reset/generation indexes, fixed ZIP layout, trailing-data and path safety checks, and historical Receiver Acceptance snapshots retained outside the audit ZIP.
- Offline verification that reconstructs reset causality from the external previous-generation Receiver Acceptance Archive, verification report, signoff binding, signoff, and history event instead of trusting package-internal reset summaries.
- CLI, HTTP API, and Studio workflows for CR creation/approval, controlled reset, lifecycle refresh, Archive export/ZIP/verification, and current gate status.
- Release signoff and GA readiness gates that require both the current v12.11 Receiver Acceptance evidence and the v12.12 lifecycle Archive; reset-pending, stale generations, invalid proofs, and runtime failures are hard blockers.
- release-check `v1212.unified_release_program_continuity_command_center_receiver_acceptance_change_control_smoke` covering action scope, approval target mismatch, CR reuse, reset pending, successor signoff, external-proof full resign, fixed layout, trailing data, and signed local proof mutation.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity_command_center_acceptance_change.py tests\test_release_check.py::test_v1212_unified_release_program_continuity_command_center_receiver_acceptance_change_control_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.11.0 - 2026-07-11

### Added
- Unified Release Program Continuity Command Center Receiver Acceptance workflow with a fixed-layout Review Pack, externally proved receiver responses, immutable Accepted Evidence, multi-organization quorum, findings/conflict registers, and signed takeover evidence.
- Response import requires the external response JSON, response verification report, and response binding summary; the Store does not synthesize trusted role, organization, decision, or source binding from receiver payload fields.
- Signed fixed-layout Receiver Acceptance Archive and offline verifier that runtime re-verifies the current v12.10 Signoff Archive, Final Handoff, Review Pack, every response proof, and every Accepted Evidence ZIP.
- CLI and HTTP API workflows for Review Pack creation/verification, response import, Accepted Evidence creation, Board refresh, signoff, Archive export/ZIP/verification, and gate status.
- Release signoff and GA readiness gates that require current Receiver Acceptance Archive, independent signoff binding, response proof root, Accepted Evidence root, Review Pack, and all current v12.10 source evidence; force signoff cannot bypass failed runtime verification.
- release-check `v1211.unified_release_program_continuity_command_center_receiver_acceptance_smoke` covering missing proof, role forge, rejected/needs-changes blockers, stale handoff, signoff full-resign, history deletion, signed source tamper, declared extra, `.MusicForge`, raw backslash, and trailing data.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity_command_center_acceptance.py tests\test_release_check.py::test_v1211_unified_release_program_continuity_command_center_receiver_acceptance_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.10.0 - 2026-07-10

### Added
- Unified Release Program Continuity Command Center signoff with signoff-time independent binding summary, authoritative hash-chained history, and signed-source runtime preflight.
- Immutable fixed-layout Signoff Archive and lightweight Final Handoff ZIP; both reject declared extras, duplicate or unsafe paths, nested ZIPs, trailing data, redaction findings, and stale v12.9 runtime evidence.
- Approved, action-scoped, single-use Change Request reset with historical Archive preservation and successor signoff support; deleting signoff/export/ZIP files cannot reopen or silently rebuild signed evidence.
- CLI and HTTP API workflows for status, preflight, signoff, Change Request approval/reset, Archive export/ZIP/verify, Final Handoff, and gate verification.
- Release signoff and GA readiness gates that require the external signoff binding plus current Command Center ZIP, verification report, and external evidence manifest; force signoff cannot bypass failed or stale evidence.
- release-check `v1210.unified_release_program_continuity_command_center_signoff_smoke` covering full-resign, missing binding, stale source, deletion guard, CR action scope, reset/successor, fixed layout, and trailing data.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity_command_center_signoff.py tests\test_release_check.py::test_v1210_unified_release_program_continuity_command_center_signoff_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.9.0 - 2026-07-10

### Added
- Unified Release Program Continuity Command Center that aggregates Evidence Vault, Vault Operations, Continuity Recovery, Continuity Distribution Kit, Continuity Acceptance Board, and Acceptance Change Control into one runtime-verified readiness dashboard.
- Fixed-layout Continuity Command Center ZIP and offline verifier with external evidence manifest runtime re-verification, declared-extra rejection, raw path safety, trailing-data detection, redaction scanning, and wrong verification package-type blocking.
- Evidence inventory separates old-report `stale`, current-package `runtime_failed`, and Acceptance lifecycle `reset_pending` states; package export and ZIP build now stop before producing a non-ready artifact.
- Release and GA gates rebuild current component verification from ZIP, manifest, report size/hash, generation, and Acceptance signoff history, so force signoff cannot reuse an old passed report after source tamper or reset.
- Safe runbook handling for Command Center refresh/export/ZIP/verify actions; unsupported safe actions are reported as `skipped_unsupported` instead of completed.
- release-check `v129.unified_release_program_continuity_command_center_smoke` covering ready path, runtime evidence tamper, stale verification report, reset pending, Release/GA gates, wrong package type, declared extra, trailing bytes, and unsupported runbook action handling.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity_command_center.py tests\test_release_check.py::test_v129_unified_release_program_continuity_command_center_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.8.0 - 2026-07-09

### Added
- Unified Release Program Continuity Acceptance Change Control for approved single-use reset of signed Continuity Acceptance Boards, reset proof generation, successor Board lifecycle tracking, fixed-layout change-control archive, and offline verifier.
- CLI and HTTP API endpoints for `unified-release-program-continuity-acceptance-change` plus standalone `verify-unified-release-program-continuity-acceptance-change-package`.
- Continuity Acceptance signoff history now recognizes reset events so old signed Boards stop being current until a successor Board is re-signed and re-verified.
- release-check `v128.unified_release_program_continuity_acceptance_change_control_smoke` covering wrong-action reset rejection, reset gate failure, successor re-sign gate recovery, declared-extra ZIP rejection, and current Acceptance source tamper blocking.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity_acceptance_change.py tests\test_release_check.py::test_v128_unified_release_program_continuity_acceptance_change_control_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.7.0 - 2026-07-08

### Added
- Unified Release Program Continuity Acceptance Board for external disaster-recovery receiver responses, externally supplied response verification / binding proof, accepted evidence, quorum decisions, signed immutable acceptance archive, and fixed-layout offline verifier.
- CLI and HTTP API endpoints for `unified-release-program-continuity-acceptance` plus standalone `verify-unified-release-program-continuity-acceptance-package`.
- Release signoff and GA readiness can require Continuity Acceptance evidence bound to the current Continuity Distribution Kit, external verification report, and signoff binding proof.
- release-check `v127.unified_release_program_continuity_acceptance_board_smoke` covering happy path, missing explicit response binding, role forge rejection, rejected / needs-changes blockers, declared-extra ZIP rejection, signoff full-resign rejection, and signed mutation blocking.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity_acceptance.py tests\test_release_check.py::test_v127_unified_release_program_continuity_acceptance_board_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.6.0 - 2026-07-08

### Added
- Unified Release Program Continuity Distribution Kit for external disaster-recovery handoff, bundling the signed Continuity Archive, Vault Operations Archive, Evidence Vault, external verification reports, signoff bindings, vault anchor, receiver guide, and receiver receipt template into a fixed-layout ZIP.
- Standalone `verify-unified-release-program-continuity-kit-package` and `unified-release-program-continuity-kit` CLI commands, plus HTTP API routes for kit prepare/export/ZIP/verify/gate and receiver receipt import/verification.
- Release signoff and GA readiness can require Continuity Distribution Kit evidence through runtime deep verification instead of trusting package indexes or copied verification reports.
- release-check `v126.unified_release_program_continuity_distribution_kit_smoke` covering happy path, declared-extra rejection, extra nested ZIP rejection, raw backslash rejection, `.MusicForge/` rejection, nested Continuity tamper blocking, receiver receipt wrong-hash failure, and source Continuity tamper blocking.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity_distribution.py tests\test_release_check.py::test_v126_unified_release_program_continuity_distribution_kit_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.5.0 - 2026-07-07

### Added
- Unified Release Program Continuity / Recovery Drill with isolated restore replay, continuity readiness, runbook, signed immutable Continuity Archive, and fixed-layout offline verifier.
- CLI and HTTP API endpoints for `unified-release-program-continuity` plus standalone `verify-unified-release-program-continuity-package`.
- Release signoff and GA readiness can require continuity evidence bound to the current Vault Operations Archive, verification report, and external continuity signoff binding.
- release-check `v125.unified_release_program_continuity_recovery_smoke` covering happy path, missing binding failure, declared-extra rejection, signoff full-resign rejection, source Vault Operations tamper blocking, trailing-data rejection, and signed mutation blocking.

### Verified
- `python -m pytest tests\test_unified_release_program_continuity.py tests\test_release_check.py::test_v125_unified_release_program_continuity_recovery_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.4.0 - 2026-07-07

### Added
- Unified Release Program Vault Operations with Vault Registry, custody policy, runtime custody review, rotation plan, transfer pack, signed immutable Vault Operations Archive, and fixed-layout offline verifier.
- CLI and HTTP API endpoints for `unified-release-program-vault-ops` plus standalone `verify-unified-release-program-vault-operations-package`.
- Release signoff and GA readiness can require Vault Operations evidence with runtime deep Vault verification and external signoff binding proof.
- release-check `v124.unified_release_program_vault_operations_smoke` covering happy path, missing binding failure, declared-extra rejection, signoff full-resign rejection, and signed mutation blocking.

### Verified
- `python -m pytest tests\test_unified_release_program_vault_operations.py tests\test_release_check.py::test_v124_unified_release_program_vault_operations_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.3.0 - 2026-07-07

### Added
- Unified Release Program Evidence Vault with fixed-layout Vault ZIP, nested Program / Operations / Handoff / accepted-evidence packages, public-safe proof indexes, chain-of-custody, replay plan, auditor guide, and ZIP-external `vault-anchor.json`.
- Standalone `verify-unified-release-program-vault-package` and `unified-release-program-vault` CLI commands, plus HTTP API routes for Vault status, refresh, export, ZIP, verify, and gate.
- Release signoff and GA readiness can require Program Evidence Vault evidence with runtime deep verification and external anchor binding.
- release-check `v123.unified_release_program_evidence_vault_smoke` covering happy path, missing anchor failure, declared extra rejection, and nested package tamper rejection.

### Verified
- `python -m pytest tests\test_unified_release_program_vault.py tests\test_release_check.py::test_v123_unified_release_program_evidence_vault_smoke -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.2.1 - 2026-07-06

### Fixed
- Program Final Handoff Decision Board now scans all imported reviewer responses; `rejected` and `needs_changes` responses block readiness/signoff when board policy requires it.
- Release signoff and GA readiness can now require Unified Release Program Handoff archive evidence through runtime gate verification instead of relying on standalone smoke coverage.
- Program Handoff response import and accepted-evidence API responses now report `ok=true` for successful `imported` / `accepted` store results.
- v12.2 smoke now covers `rejected_blocks=blocked` for Program Handoff quorum/signoff.

### Verified
- `python -m pytest tests\test_unified_release_program_handoff.py tests\test_server_unified_release_program_handoff.py tests\test_release_check.py::test_v122_unified_release_program_final_handoff_smoke -q`
- `python -m pytest tests\test_release_check.py::test_v122_unified_release_program_final_handoff_smoke tests\test_cli_release_check_matrix.py tests\test_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`

## v12.2.0 - 2026-07-06

### Added
- Unified Release Program Final Handoff Board with review-pack export, explicit-bound external response import, accepted evidence packages, reviewer quorum decision board, signed immutable Program Handoff Archive ZIP, and offline verifier.
- CLI and HTTP API endpoints for Program Handoff refresh, review-pack export/ZIP/verify, response import, accepted evidence ZIP/verify, decision board refresh, handoff signoff, archive export/ZIP/verify, and standalone `verify-unified-release-program-handoff-package`.
- release-check `v122.unified_release_program_final_handoff_smoke` covering Program/Operations external evidence binding, accepted evidence quorum, declared-extra ZIP rejection, signoff full-resign rejection, and signed mutation blocking.

### Fixed
- Program Handoff Archive no longer stores local runtime evidence paths in its public external evidence manifest; runtime paths stay in the local verifier manifest while the archive carries a public fingerprint projection.
- Handoff verifier now derives accepted roles from external accepted evidence runtime proof instead of trusting package-internal quorum summaries.

### Verified
- `python -m pytest tests\test_unified_release_program_handoff.py tests\test_release_check.py::test_v122_unified_release_program_final_handoff_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`
- `python -m song_agent.cli release-check --profile latest --skip-tests --json`

## v12.1.0 - 2026-07-06

### Added
- Unified Release Program Operations Center with Program Change Requests, approved single-use signoff reset, Operations Runbook safe actions, Continuous Review drift checks, Lifecycle Audit, fixed-layout Operations Archive ZIP, and offline verifier.
- CLI and HTTP API endpoints for Program Operations change-request create/approve, signoff reset, runbook create/run-safe, continuous review, lifecycle audit, archive export/ZIP/verify, and standalone `verify-unified-release-program-operations-package`.
- release-check `v121.unified_release_program_operations_smoke` covering current Program verification, Operations Archive verification, declared-extra ZIP rejection, approved CR reset, and reset-state gate blocking.

### Fixed
- Unified Release Program signoff history now recognizes reset events, so deleted signoff files or reset states cannot be treated as currently signed by Store-level gates.
- Program signoff reset now requires an approved Change Request with `change_type=reset_signoff` and `allowed_actions` containing `reset_program_signoff`, blocking refresh-only CR reset escalation.
- Program Operations archive build and verifier now reject stale or wrong-package-type Program verification reports.
- Program reset state now blocks Operations Archive export/ZIP immediately instead of producing a package that only fails later during offline verification.

### Verified
- `python -m pytest tests\test_unified_release_program_operations.py tests\test_release_check.py::test_v121_unified_release_program_operations_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- `python -m pytest tests\test_unified_release_program.py tests\test_unified_release_program_operations.py tests\test_server_unified_release_program.py tests\test_cli_unified_release_program.py tests\test_release_check.py::test_v120_unified_release_program_board_smoke tests\test_release_check.py::test_v121_unified_release_program_operations_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v12 --skip-tests --json`
- `python -m song_agent.cli release-check --profile latest --skip-tests --json`

## v12.0.0 - 2026-07-06

### Added
- Unified Release Program Board for grouping multiple signed Release Train Handoffs into a Program-level readiness board with train items, dependency graph, readiness matrix, risk register, exception register, gap plan, signoff, immutable ZIP, and offline verifier.
- Program external evidence manifests bind each train item by `item_id`, `train_id`, `handoff_id`, handoff ZIP fingerprint, handoff verification report hash, and handoff signoff binding hash; Program runtime verification rechecks each referenced Handoff instead of trusting package-internal summaries.
- CLI and HTTP API endpoints for Program create, train item add, refresh, signoff, export, ZIP, verify, gate, download, and standalone `verify-unified-release-program-package`.
- release-check `v120.unified_release_program_board_smoke` and `v12` profile covering Program signoff, current external Handoff binding, missing external signoff proof, declared-extra ZIP rejection, and signoff/history/binding/manifest full-resign rejection.

### Fixed
- Program external evidence input now keeps runtime paths only in the external manifest while exported Program packages contain public-safe fingerprint summaries, avoiding local path leakage while preserving offline current verification.

### Verified
- `python -m pytest tests\test_unified_release_program.py tests\test_release_check.py::test_v120_unified_release_program_board_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v11.9.1 - 2026-07-06

### Fixed
- Release Train Final Handoff accepted-evidence quorum now derives reviewer role, organization, decision, and hashes from the original response, response verification report, and response binding summary instead of trusting `accepted-evidence.json` public summary fields.
- Handoff package verifier now rejects accepted evidence whose public summary or embedded binding no longer matches the response sidecars, blocking local full-resign role forgery before signoff and during offline verification.
- v11.9 release-check smoke now covers `technical_reviewer` accepted evidence forged to `release_owner`; signoff remains blocked and verifier reports `ucc_train_handoff_accepted_evidence_external_sidecars_valid=failed`.

### Verified
- `python -m pytest tests\test_unified_command_center_release_train_handoff.py tests\test_release_check.py::test_v119_unified_command_center_release_train_handoff_smoke -q`

## v11.9.0 - 2026-07-05

### Added
- Unified Command Center Release Train Final Handoff Board for consolidating signed Release Train, Change Control reset proof, Lifecycle Audit, external response, accepted evidence, readiness, gap plan, and final handoff signoff.
- Fixed-layout Handoff ZIP and offline verifier with strict allow-list, no nested ZIPs, runtime binding to current Train / Change Control / Lifecycle evidence, external handoff signoff binding proof, response binding, accepted evidence checks, redaction scanning, and full-resign signer tamper rejection.
- CLI and HTTP API endpoints for Handoff create, status, refresh, export, ZIP, verify, response import, accepted evidence, signoff, and standalone package verification.
- release-check `v119.unified_command_center_release_train_handoff_smoke` covering current evidence verification, missing external signoff binding, declared-extra rejection, and signoff/history/binding/manifest full-resign rejection.

### Verified
- `python -m pytest tests\test_unified_command_center_release_train_handoff.py tests\test_cli_unified_command_center_release_train_handoff.py tests\test_release_check.py::test_v119_unified_command_center_release_train_handoff_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v11.8.1 - 2026-07-05

### Fixed
- Release Train Change Control verification now validates `change-request-history.jsonl` as per-request hash chains, so multiple legitimate reset requests no longer look like a broken single global chain.
- Release Train Lifecycle Audit smoke now covers two sequential approved resets, two reset proofs, successor signoff, Change Control verification, and Lifecycle verification.

### Verified
- `python -m pytest tests\test_unified_command_center_release_train_change_control.py tests\test_unified_command_center_release_train_lifecycle.py tests\test_release_check.py::test_v118_unified_command_center_release_train_lifecycle_smoke -q`

## v11.8.0 - 2026-07-05

### Added
- Unified Command Center Release Train Lifecycle Audit for consolidating current train verification, signoff succession, Change Control reset coverage, archive-history, current readiness, gap planning, and evidence fingerprints.
- Fixed-layout Lifecycle Audit ZIP and offline verifier with strict allow-list, ledger hash-chain checks, external current train runtime verification, Change Control runtime verification, signoff binding, external evidence manifest, and reset-proof binding.
- CLI and HTTP API endpoints for Lifecycle status, refresh, export, ZIP, verify, download, and standalone package verification.
- release-check `v118.unified_command_center_release_train_lifecycle_smoke` covering reset lifecycle pass, missing reset proof rejection, declared-extra rejection, and lifecycle report full-resign reset-count rejection.

### Verified
- `python -m pytest tests\test_unified_command_center_release_train_lifecycle.py tests\test_cli_unified_command_center_release_train_lifecycle.py tests\test_server_unified_command_center_release_train_lifecycle.py tests\test_release_check.py::test_v118_unified_command_center_release_train_lifecycle_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v11.7.0 - 2026-07-05

### Added
- Unified Command Center Release Train Change Control for submitted/approved single-use Train Change Requests, impact reports, reset proof, request binding reports, archive-history preservation, and reset/reopen of signed trains.
- Fixed-layout Change Control ZIP and offline verifier with strict allow-list, hash-chained request history, archive-history checks, external reset-proof binding, and optional current Release Train runtime verification.
- CLI and HTTP API endpoints for Change Request create, approve, reset, status, export, ZIP, verify, and download flows.
- Release Train state now understands `ucc_release_train_signoff_reset`; reset trains are not release-ready until they are refreshed, re-signed, re-archived, and re-verified.
- release-check `v117.unified_command_center_release_train_change_control_smoke` covering reset gate blocking, successor signoff, missing reset proof, declared-extra rejection, and forged reset proof hash rejection.

### Verified
- `python -m pytest tests\test_unified_command_center_release_train_change_control.py tests\test_cli_unified_command_center_release_train_change_control.py tests\test_server_unified_command_center_release_train_change_control.py tests\test_release_check.py::test_v117_unified_command_center_release_train_change_control_smoke -q`

## v11.6.1 - 2026-07-04

### Fixed
- Release Train archive verification now requires an external `train-signoff-binding-summary.json` proof when `require_signed=true`, so a ZIP-internal full resign of signoff, history, binding, and manifest cannot forge signer metadata.
- Release Train store, CLI verifier, server Release signoff gate, and release-check v11.6 smoke now pass and validate the external signoff binding proof.
- release-check `v116.unified_command_center_release_train_smoke` now covers full-resign signer tampering with synchronized signoff/history/binding/manifest rewrites.

### Verified
- `python -m pytest tests\test_unified_command_center_release_train.py tests\test_cli_unified_command_center_release_train.py tests\test_server_unified_command_center_release_train.py tests\test_release_check.py::test_v116_unified_command_center_release_train_smoke -q`

## v11.6.0 - 2026-07-04

### Added
- Unified Command Center Release Train for grouping multiple UCCs into waves with dependency checks, per-item external evidence requirements, Go/No-Go readiness, safe runbook output, and signed release-train archive.
- Fixed-layout Release Train archive ZIP and offline verifier with strict allow-list, dependency graph validation, signoff history hash-chain checks, signoff binding sidecar checks, redaction scanning, and external evidence manifest binding by `item_id + center_id + evidence_type`.
- CLI and HTTP API endpoints for Release Train create, item add, refresh, run-safe, signoff, archive export, ZIP, verify, list, status, and download flows.
- Release signoff gate for `require_unified_command_center_release_train=true`.
- release-check `v116.unified_command_center_release_train_smoke` covering manifest reorder, missing external evidence, declared-extra rejection, stale external ZIP rejection, duplicate center guard, dependency cycle guard, deleted-signoff history guard, and signoff signer full-resign rejection.

### Verified
- `python -m pytest tests\test_unified_command_center_release_train.py tests\test_cli_unified_command_center_release_train.py tests\test_server_unified_command_center_release_train.py tests\test_release_check.py::test_v116_unified_command_center_release_train_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v11.5.2 - 2026-07-04

### Fixed
- Reviewer Decision Board signoff no longer merges Board policy from signoff payloads.
- Board policy is now created with defaults only during Board creation and is updated only through unsigned Board refresh with an explicit `policy` field.
- Strict quorum policies remain blocked at signoff time instead of being reset to defaults by `signed_by` / `reason` / `role` payloads.
- release-check `v115.unified_command_center_reviewer_decision_board_smoke` now covers `policy_override=blocked/409/unchanged`.

### Verified
- `python -m pytest tests\test_unified_command_center_reviewer_decision_board.py tests\test_release_check.py::test_v115_unified_command_center_reviewer_decision_board_smoke -q`

## v11.5.1 - 2026-07-03

### Fixed
- Reviewer Decision Board accepted evidence quorum now uses reviewer role, organization, and reviewer identity from the external accepted evidence package instead of trusting payload hints.
- Payload role, organization, or reviewer mismatches now mark the accepted evidence row failed before signoff, so forged role input cannot create a signed Board.
- release-check `v115.unified_command_center_reviewer_decision_board_smoke` now covers `role_override_input=blocked/409`.

### Verified
- `python -m pytest tests\test_unified_command_center_reviewer_decision_board.py tests\test_release_check.py::test_v115_unified_command_center_reviewer_decision_board_smoke -q`

## v11.5.0 - 2026-07-03

### Added
- Unified Command Center Reviewer Decision Board for multi-reviewer decisions, quorum policy, required roles, conflict reporting, decision matrix, signed decision archive, and hash-chained decision history.
- Fixed-layout Reviewer Decision Board archive ZIP and offline verifier that bind Evidence Review packages, accepted evidence ZIPs, accepted evidence verification reports, and original response verification summaries instead of trusting Board-internal role or acceptance summaries.
- CLI and HTTP API endpoints for Board create, refresh, signoff, export, ZIP, verify, status, list, and download flows.
- Release signoff and GA readiness gates for `require_unified_command_center_reviewer_decision_board`.
- release-check `v115.unified_command_center_reviewer_decision_board_smoke` covering quorum, missing external accepted evidence, declared-extra rejection, role full-resign rejection, signed mutation guards, deleted-signoff history guard, rejected required reviewer blocking, and GA gate binding.

### Verified
- `python -m pytest tests\test_unified_command_center_reviewer_decision_board.py tests\test_release_check.py::test_v115_unified_command_center_reviewer_decision_board_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v11.4.1 - 2026-07-03

### Fixed
- Release signoff Evidence Review accepted gate now runtime-verifies the current accepted evidence ZIP and response verification summary instead of trusting a previously passed verification report.
- Server release signoff payloads can pass `unified_command_center_evidence_review_acceptance_response_verification_report` so accepted evidence gates use the same external response binding as GA readiness.
- release-check `v114.unified_command_center_evidence_review_smoke` now covers stale/missing accepted evidence ZIP rejection.

### Verified
- `python -m pytest tests\test_unified_command_center_evidence_review.py tests\test_release_check.py::test_v114_unified_command_center_evidence_review_smoke -q`

## v11.4.0 - 2026-07-03

### Added
- Unified Command Center Evidence Review / Replay packages that bind UCC, Archive, Handoff, Continuous Review, optional Drift Response, CR proof, GA readiness, and release-check evidence into a fixed-layout external reviewer pack.
- Offline Evidence Review verifier that rejects declared extra entries, unsafe paths, nested ZIPs, missing external evidence, stale runtime replay, and package-internal self-certification.
- External review response import with explicit review pack source binding; accepted responses can generate a fixed-layout acceptance evidence package and independent acceptance verifier report.
- CLI and HTTP API endpoints for Evidence Review create, replay, export, ZIP, verify, response import, acceptance evidence, and downloads.
- Release signoff and GA readiness gates for `require_unified_command_center_evidence_review`, including optional accepted external review evidence.
- release-check `v114.unified_command_center_evidence_review_smoke` covering replay, accepted evidence, missing external evidence, declared-extra rejection, naked response rejection, and GA gate binding.

### Verified
- `python -m pytest tests\test_unified_command_center_evidence_review.py tests\test_release_check.py::test_v114_unified_command_center_evidence_review_smoke tests\test_release_check_matrix.py::test_release_check_profile_and_filters tests\test_cli_release_check_matrix.py::test_release_check_cli_v11_profile_lists_unified_command_center -q`
- `python -m song_agent.cli release-check --profile v11 --skip-tests --json`

## v11.3.1 - 2026-07-03

### Fixed
- Unified Command Center Drift Response now requires an external Change Request binding report for closed response verification instead of trusting ZIP-internal CR bindings.
- Drift Response closeout/export writes a CR binding proof report that binds manual action items, source drift IDs, approved CR payload hashes, action queue hash, and CR binding hash.
- Release signoff and GA readiness gates now pass the same external CR proof so local gates and offline verification use one evidence model.
- release-check `v113.unified_command_center_drift_response_smoke` now covers missing CR proof, forged CR binding, wrong-item CR proof, and reused CR proof regressions.

### Verified
- `python -m pytest tests\test_unified_command_center_drift_response.py tests\test_cli_unified_command_center.py::test_unified_command_center_cli_drift_response_lifecycle tests\test_server_unified_command_center.py::test_unified_command_center_api_drift_response_lifecycle tests\test_release_check.py::test_v113_unified_command_center_drift_response_smoke -q`

## v11.3.0 - 2026-07-02

### Added
- Unified Command Center Drift Response cases that turn failed Continuous Review drift into a controlled response plan, safe action queue, approved Change Request bindings, clear recheck binding, and closeout report.
- Fixed-layout Drift Response ZIP export and offline verifier with current source/recheck Continuous Review binding, UCC Archive/Handoff/UCC/signoff binding, event hash-chain checks, fixed entry allow-list, redaction scan, and full-resign regression coverage.
- CLI and HTTP API endpoints for Drift Response create, run-safe, bind-cr, bind-recheck, closeout, export, zip, verify, and download.
- Release signoff and GA readiness gates for `require_unified_command_center_drift_response`.
- release-check `v113.unified_command_center_drift_response_smoke` covering blocked closeout without CR, clear recheck binding, GA gate binding, declared-extra rejection, and recheck full-resign rejection.

### Verified
- `python -m pytest tests\test_unified_command_center_drift_response.py tests\test_cli_unified_command_center.py::test_unified_command_center_cli_drift_response_lifecycle tests\test_server_unified_command_center.py::test_unified_command_center_api_drift_response_lifecycle tests\test_release_check.py::test_v113_unified_command_center_drift_response_smoke tests\test_release_check_matrix.py tests\test_cli_release_check_matrix.py -q`

## v11.2.1 - 2026-07-02

### Fixed
- Unified Command Center Continuous Review now treats failed GA readiness reports, failed release-check reports, and failed external evidence rows as blocking drift instead of only recording them in review source.
- Continuous Review baseline plans now bind GA, release-check, and external evidence fingerprints so changed evidence is detected during later review runs.
- Continuous Review offline verification now fails `require_clear` / current-review checks when packaged GA, release-check, or external evidence status is failed.
- release-check `v112.unified_command_center_continuous_review_smoke` now covers failed GA, failed release-check, and failed external evidence regressions.

### Verified
- `python -m pytest tests\test_unified_command_center_continuous_review.py tests\test_cli_unified_command_center.py::test_unified_command_center_review_cli_blocks_failed_release_check tests\test_server_unified_command_center.py::test_unified_command_center_api_continuous_review_blocks_failed_release_check tests\test_release_check.py::test_v112_unified_command_center_continuous_review_smoke -q`
- `python -m song_agent.cli release-check --profile v11 --skip-tests --json`

## v11.2.0 - 2026-07-02

### Added
- Unified Command Center Continuous Review plans, drift reports, incident boards, recovery drill reports, draft change requests, fixed-layout ZIP export, offline verifier, CLI, API, Studio controls, Release signoff gate, and GA readiness gate.
- Continuous Review binds signed UCC Archive, Final Handoff, UCC ZIP, signoff binding, and verification report fingerprints so signed handoff evidence can be rechecked after release without mutating the signed UCC.
- release-check `v112.unified_command_center_continuous_review_smoke` covers passed review, GA gate binding, stale export blocking, declared-extra rejection, and full-resign clear-forgery rejection.

### Verified
- `python -m pytest tests\test_unified_command_center_continuous_review.py tests\test_cli_unified_command_center.py tests\test_server_unified_command_center.py tests\test_release_check.py::test_v112_unified_command_center_continuous_review_smoke -q`
- `python -m song_agent.cli release-check --profile v11 --skip-tests --json`

## v11.1.1 - 2026-07-01

### Fixed
- Unified Command Center Archive now includes a signoff binding summary generated at signoff time, not archive build time.
- Archive verification now cross-checks the binding summary against `signoff.json`, `signoff-history.jsonl`, UCC ZIP hash, UCC manifest hash, and the UCC verification report.
- Full-resign tampering of archive signer fields is rejected even when `signoff.json`, signoff history, and manifest hashes are recomputed together.
- release-check `v111.unified_command_center_signoff_archive_smoke` now covers the signer full-resign attack.

### Verified
- `python -m pytest tests\test_unified_command_center_signoff.py tests\test_release_check.py::test_v111_unified_command_center_signoff_archive_smoke -q`
- `python -m song_agent.cli release-check --profile v11 --skip-tests --json`

## v11.1.0 - 2026-07-01

### Added
- Unified Command Center Signoff, Change Request reset, immutable Archive ZIP, Final Handoff Pack, offline verifiers, CLI, API, Studio controls, Release signoff gate, and GA readiness gate.
- UCC signoff history now uses a hash chain, so deleting `signoff.json` does not reopen a signed command center.
- UCC Archive verification binds the signed report, readiness matrix, inventory, UCC ZIP hash, manifest hash, and UCC verification report.
- Final Handoff verification binds the handoff package to the current UCC Signoff Archive and archive verification report.
- release-check `v111.unified_command_center_signoff_archive_smoke` covers signed mutation blocking, signoff deletion guard, archive/handoff verification, fixed ZIP allow-list rejection, and duplicate archive rebuild blocking.

### Verified
- `python -m pytest tests\test_unified_command_center.py tests\test_unified_command_center_signoff.py tests\test_cli_unified_command_center.py tests\test_server_unified_command_center.py tests\test_release_check.py::test_v111_unified_command_center_signoff_archive_smoke -q`
- `python -m song_agent.cli release-check --profile v11 --skip-tests --json`

## v11.0.0 - 2026-06-30

### Added
- MusicForge Unified Command Center store, fixed-layout ZIP export, offline verifier, CLI, API, Studio controls, Release signoff gate, and GA readiness gate.
- Unified evidence graph, evidence inventory, readiness matrix, gap plan, safe runbook, and component fingerprint sidecars aggregate Release, Audio Command Center, Trust Operations Hub, Public Trust Center, Distribution, Submission, Operations, Maintenance, GA readiness, and release-check evidence.
- Offline verifier binds package documents to fixed entries and external runtime evidence, rejects stale component fingerprints, declared extra ZIP entries, backslash/path pollution, nested ZIPs, and obvious secrets.
- release-check `v110.unified_command_center_smoke` covers ready generation, safe runbook execution, runtime-failed evidence, stale external release-check evidence, and declared-extra rejection.

### Verified
- `python -m pytest tests\test_unified_command_center.py tests\test_cli_unified_command_center.py tests\test_server_unified_command_center.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v110_unified_command_center_smoke -q`
- `python -m song_agent.cli release-check --profile v11 --skip-tests --json`

## v10.15.1 - 2026-06-30

### Fixed
- Release Audio Command Center refresh now re-runs runtime verifiers for every component instead of trusting previously saved verification reports alone.
- Evidence Inventory, Readiness Matrix, and Gap Plan now expose runtime verification status, runtime blockers, and prioritized stale/runtime-failed/missing follow-up actions.
- Offline Command Center verification now binds runtime status and blockers, so changing runtime-failed evidence to passed and re-signing package JSON is rejected.
- Added independent Store, CLI, and Server regressions for Command Center runtime evidence checks.
- release-check `v1015.release_audio_command_center_smoke` now covers stale/runtime-failed component evidence in addition to full-resign and declared-extra tamper cases.

### Verified
- `python -m pytest tests\test_release_audio_command_center.py tests\test_cli_release_audio_command_center.py tests\test_server_release_audio_command_center.py tests\test_release_check.py::test_v1015_release_audio_command_center_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.15.0 - 2026-06-30

### Added
- Release Audio Command Center store, fixed-layout ZIP export, offline verifier, CLI, API, Studio controls, Release signoff gate, and GA readiness gate.
- Command Center evidence inventory, readiness matrix, gap plan, and safe runbook aggregate Release Audio Certification, Timeline, Regression, Baseline Governance, Regression Response, Observatory, Action Queue, and Action Queue Signoff evidence.
- Offline verifier binds every component to external ZIPs and verification reports, rejects fixed-layout ZIP expansion, and catches internal full-resign attempts against component fingerprints.
- release-check `v1015.release_audio_command_center_smoke` covers end-to-end Command Center refresh/export/ZIP/verify, safe runbook execution, Release gate, GA binding, declared-extra rejection, and full-resign fingerprint tamper.

### Verified
- `python -m pytest tests\test_release_check.py::test_v1015_release_audio_command_center_smoke tests\test_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.14.0 - 2026-06-30

### Added
- Release Audio Quality Action Queue manual resolution, closeout, signoff, immutable archive ZIP, offline verifier, CLI, API, Release signoff gate, and GA readiness gate.
- Signed queues now block refresh/run/export/ZIP mutation through signoff-history evidence, so deleting `action-queue-signoff.json` cannot reopen the queue.
- Signoff archive verification binds the archive to the current Action Queue ZIP, queue verification report, Observatory ZIP, and Observatory verification report while keeping embedded verification summaries redacted.
- release-check `v1014.release_audio_quality_action_queue_signoff_smoke` covers closeout/signoff/archive verification, signed mutation blocking, signoff deletion guard, declared extra ZIP rejection, Release gate, and GA binding.

### Verified
- `python -m pytest tests\test_release_audio_quality_action_signoff.py tests\test_server_release_audio_quality_actions.py tests\test_cli_release_audio_quality_actions.py tests\test_release_check.py::test_v1014_release_audio_quality_action_queue_signoff_smoke -q`
- `python -m song_agent.cli release-check --only v1014.release_audio_quality_action_queue_signoff_smoke --skip-tests --json`

## v10.13.1 - 2026-06-29

### Fixed
- Release Audio Quality Action Queue now persists its action selection policy (`include_risks`, `include_recommendations`, and `severity_floor`) into queue/source evidence.
- Offline verifier now rebuilds expected Action Queue items with the same persisted selection policy, so risks-only, recommendations-only, and severity-filtered queues can verify against current Observatory evidence.
- `manual_required_count` now counts unique manual-required `item_id` values instead of double-counting result rows and manual action rows.
- release-check `v1013.release_audio_quality_action_queue_smoke` now covers a critical risks-only filtered queue and validates the corrected manual action count.

### Verified
- `python -m pytest tests\test_release_audio_quality_actions.py tests\test_server_release_audio_quality_actions.py tests\test_cli_release_audio_quality_actions.py tests\test_release_check.py::test_v1013_release_audio_quality_action_queue_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.13.0 - 2026-06-29

### Added
- Release Audio Quality Action Queue store, fixed-layout ZIP export, offline verifier, CLI, API, and Studio controls for turning Observatory risks/recommendations into auditable safe/manual actions.
- Action Queue source binding to current Release Audio Quality Observatory ZIP, manifest, risk register, recommendation report, and external release evidence root.
- Release signoff `require_release_audio_quality_action_queue=true` gate and GA readiness `ga.release_audio_quality_action_queue` evidence binding.
- release-check `v1013.release_audio_quality_action_queue_smoke` covering safe queue execution, GA binding, stale source export blocking, and full-resign source fingerprint rejection.

### Verified
- `python -m pytest tests\test_release_audio_quality_actions.py tests\test_server_release_audio_quality_actions.py tests\test_cli_release_audio_quality_actions.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v1013_release_audio_quality_action_queue_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.12.0 - 2026-06-28

### Added
- Release Audio Quality Observatory store, fixed-layout ZIP export, offline verifier, CLI, API, and Studio controls for cross-release audio quality trend monitoring.
- Observatory reports aggregate current Release Audio Certification and Timeline evidence into source index, evidence fingerprints, trend report, issue heatmap, baseline drift, remediation cost, risk register, recommendations, and public summary.
- Release signoff can require `require_release_audio_quality_observatory=true`; GA readiness can require external Observatory ZIP/report evidence with current Certification/Timeline binding.
- release-check `v1012.release_audio_quality_observatory_smoke` covers positive Observatory generation, GA binding, internal full-resign rejection, and declared extra ZIP rejection.

### Verified
- `python -m pytest tests\test_release_audio_quality_observatory.py tests\test_server_release_audio_quality_observatory.py tests\test_cli_release_audio_quality_observatory.py tests\test_release_check.py::test_v1012_release_audio_quality_observatory_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.11.1 - 2026-06-28

### Fixed
- Release Audio Baseline Governance gate now rebuilds current Release Audio Timeline/Certification evidence and rejects incompatible baseline track sets.
- Release signoff `require_release_audio_baseline_governance=true` now hard-blocks unrelated or stale baseline usage even when `force=true` is supplied.
- release-check `v1011.release_audio_baseline_response_smoke` now covers baseline/current release mismatch.

### Verified
- `python -m pytest tests\test_release_audio_baseline_response.py tests\test_server_release_audio_baseline_response.py tests\test_release_check.py::test_v1011_release_audio_baseline_response_smoke tests\test_release_check_matrix.py tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.11.0 - 2026-06-28

### Added
- Release Audio Baseline Governance store, approval/activation flow, fixed-layout registry ZIP, offline verifier, CLI, API, and Release signoff gate.
- Release Audio Regression Response store, draft-only safe actions, high/critical waiver guard, recheck closeout, signed fixed-layout ZIP, offline verifier, CLI, API, and Release signoff gate.
- GA readiness checks for `ga.release_audio_baseline_governance` and `ga.release_audio_regression_response`, including external ZIP/report binding.
- release-check `v1011.release_audio_baseline_response_smoke` covering active baseline governance, declared extra registry rejection, response closeout/signoff, GA binding, high waiver rejection, and signed response tamper blocking.

### Verified
- `python -m pytest tests\test_release_audio_baseline_response.py tests\test_server_release_audio_baseline_response.py tests\test_release_check.py::test_v1011_release_audio_baseline_response_smoke tests\test_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.10.0 - 2026-06-28

### Added
- Release Audio Regression Guard store, signoff, fixed-layout ZIP export, offline verifier, CLI, API, and Studio controls.
- Regression reports compare a baseline signed Release Audio Timeline/Certification chain against the current signed Timeline/Certification chain and derive track matrix, issue index, quality delta, and blocker register from external evidence.
- GA readiness and `verify-ga-readiness-report --require-release-audio-regression-guard` now bind Release Audio Regression ZIPs to current baseline/current Timeline and Certification verification reports.
- Release signoff `require_release_audio_regression_guard=true` / `require_release_audio_regression_signed=true` gate that hard-blocks regression blockers and stale external audio evidence even when `force=true` is supplied.
- release-check `v1010.release_audio_regression_guard_smoke` covering positive regression, GA binding, Certification ZIP tamper rejection, internal full-resign rejection, and signed history deletion guard.

### Verified
- `python -m pytest tests\test_release_audio_certification.py tests\test_release_audio_timeline.py tests\test_release_audio_regression.py tests\test_server_release_audio_regression.py tests\test_cli_release_audio_regression.py tests\test_release_check.py::test_v108_release_audio_certification_smoke tests\test_release_check.py::test_v109_release_audio_timeline_smoke tests\test_release_check.py::test_v1010_release_audio_regression_guard_smoke tests\test_release_check_matrix.py tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.9.1 - 2026-06-27

### Fixed
- Release Audio Timeline now re-verifies the current Release Audio Certification ZIP before building timeline bindings, so tampered or stale Certification packages make the timeline failed instead of reusing an old passed verification report.
- Release signoff `require_release_audio_timeline=true` now hard-blocks a stale/tampered underlying Certification ZIP even when `force=true` is supplied.
- GA readiness and `verify-ga-readiness-report --require-release-audio-timeline` now require current Certification ZIP/report binding for Timeline evidence.
- release-check `v109.release_audio_timeline_smoke` now covers tampered Certification ZIP rejection across timeline refresh, timeline gate, Release signoff, and GA verification.

### Verified
- `python -m pytest tests\test_release_audio_timeline.py tests\test_server_release_audio_timeline.py tests\test_cli_release_audio_timeline.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v109_release_audio_timeline_smoke tests\test_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`
- `python -m song_agent.cli doctor`

## v10.9.0 - 2026-06-26

### Added
- Release Audio Certification Timeline store with per-track event ledger, quality trend, issue taxonomy, risk register, evidence bindings, signoff, fixed-layout ZIP export, and offline verifier.
- `release-audio-timeline` and `verify-release-audio-timeline-package` CLI commands plus `/api/releases/<release-id>/audio-timelines/*` API endpoints and Studio controls.
- Release signoff `require_release_audio_timeline=true` / `require_release_audio_timeline_signed=true` gate that binds current signed Release Audio Certification evidence and blocks stale Final Export or Certification drift.
- GA readiness `ga.release_audio_timeline` check and `verify-ga-readiness-report --require-release-audio-timeline` external ZIP/report binding.
- release-check `v109.release_audio_timeline_smoke` covering positive timeline, GA binding, signed stale Final Export blocking, declared extra ZIP rejection, and redaction checks.

### Verified
- `python -m pytest tests\test_release_audio_timeline.py tests\test_server_release_audio_timeline.py tests\test_cli_release_audio_timeline.py tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m pytest tests\test_release_check.py::test_v109_release_audio_timeline_smoke tests\test_release_check_matrix.py::test_release_check_definitions_are_valid tests\test_release_check_matrix.py::test_release_check_profile_and_filters -q`

## v10.8.0 - 2026-06-26

### Added
- Release Audio Certification store, signoff, export ZIP, fixed-layout offline verifier, CLI, API, and Studio-ready release endpoints.
- Release signoff `require_release_audio_certification=true` / `require_release_audio_certification_signed=true` gate that binds the current Release tracks, Final Export hashes, real WAV evidence, manual Audio Campaign reviews, Campaign Governance, and remediation evidence.
- GA readiness `ga.release_audio_certification` check and `verify-ga-readiness-report --require-release-audio-certification` external ZIP/report binding.
- release-check `v108.release_audio_certification_smoke` covering positive certification, GA binding, signed stale Final Export blocking, declared extra ZIP rejection, and redaction checks.

### Verified
- `python -m pytest tests\test_release_audio_certification.py tests\test_server_release_audio_certification.py tests\test_cli_release_audio_certification.py tests\test_release_check.py::test_v108_release_audio_certification_smoke tests\test_release_check_matrix.py -q`
- `python -m pytest tests\test_release_audio_certification.py tests\test_server_release_audio_certification.py tests\test_cli_release_audio_certification.py tests\test_ga_readiness.py tests\test_audio_campaign_governance.py::test_ga_readiness_requires_external_audio_campaign_archive tests\test_audio_campaign_remediation.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v108_release_audio_certification_smoke tests\test_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`
- `python -m song_agent.cli release-check --profile latest --skip-tests --json`

## v10.7.1 - 2026-06-26

### Fixed
- Signed Release Audio Campaign Remediation evidence now rechecks the current Release track Final Export source before gate, export, ZIP build, and verification; stale final-export manifests hard-block instead of reusing old closeout evidence.
- Audio Campaign Remediation ZIP verification now enforces a fixed package allow-list and rejects manifest-declared extra files.
- release-check `v107.release_audio_campaign_remediation_smoke` now covers signed stale final-export blocking and declared extra ZIP entries.

### Verified
- `python -m pytest tests\test_audio_campaign_remediation.py tests\test_server_audio_campaign_remediation.py tests\test_release_check.py::test_v107_release_audio_campaign_remediation_smoke -q`

## v10.7.0 - 2026-06-26

### Added
- Release Audio Campaign Remediation store for turning release-bound Audio Campaign `needs_fix`, `rejected`, and high/critical marker cases into a remediation plan, safe action queue, Audio Fix Sprint links, closeout report, signoff, export ZIP, and offline verification.
- `audio-campaign remediation-*` CLI commands, `/api/releases/<release-id>/audio-campaign-remediation/*` endpoints, and Studio controls for remediation plan, run-safe, closeout, ZIP, and verifier.
- Release signoff `require_audio_campaign_remediation=true` gate that hard-blocks unresolved remediation even when `force=true`; optional `require_audio_campaign_remediation_signed=true` requires signed remediation evidence.
- GA readiness `ga.audio_campaign_remediation` check and verifier external evidence binding for Audio Campaign Remediation ZIPs.
- release-check `v107.release_audio_campaign_remediation_smoke` covering needs_fix issue generation, idempotent run-safe Fix Sprint creation, manual A/B and recheck gates, signed export verification, stale final-export blocking, and Release gate hard blocking.

### Verified
- `python -m pytest tests\test_audio_campaign_remediation.py tests\test_server_audio_campaign_remediation.py tests\test_release_check.py::test_v107_release_audio_campaign_remediation_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v10.6.1 - 2026-06-26

### Fixed
- Release-driven Audio Campaign preflight now blocks stale Release track final-export hashes when the current `final-export/manifest.json` no longer matches the hash captured on the Release track.
- Release signoff `require_audio_campaign=true` now hard-blocks stale Release track Final Export evidence even when `force=true` is supplied.
- release-check `v106.release_driven_audio_campaign_smoke` now covers stale final-export hash rejection.

### Verified
- `python -m pytest tests\test_release_audio_campaign_planner.py tests\test_server_release_audio_campaign_planner.py tests\test_release_check.py::test_v106_release_driven_audio_campaign_smoke -q`

## v10.6.0 - 2026-06-26

### Added
- Release-driven Audio Campaign planner that derives track identities from Release tracks, final-export hashes, and project/version bindings.
- `audio-campaign plan-release`, `preflight-release`, `create-from-release`, `release-status`, and `release-link` CLI commands.
- `/api/releases/<release-id>/audio-campaign-plan/*` endpoints and Studio controls for planning, preflight, campaign creation, status, and link checks.
- Audio Lab session creation from Release track items with copied WAV artifacts so campaign reviews bind to current release-ready audio.
- release-check `v106.release_driven_audio_campaign_smoke` covering plan/preflight/create, Release track coverage, missing WAV blocking, and unrelated Campaign mismatch rejection.

### Verified
- `python -m pytest tests\test_release_audio_campaign_planner.py tests\test_server_release_audio_campaign_planner.py tests\test_cli_release_audio_campaign_planner.py tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v106_release_driven_audio_campaign_smoke tests\test_release_check_matrix.py -q`

## v10.5.1 - 2026-06-26

### Fixed
- Release signoff `require_audio_campaign=true` now requires Audio Campaign cases to cover the current Release tracks by project/version/final-export identity, not just by case count.
- Audio Campaign case indexes now include release-track binding fields needed for Release gate verification.
- release-check `v105.audio_campaign_governance_smoke` now covers mismatched Release/Campaign binding returning 409.

### Verified
- `python -m pytest tests\test_audio_campaign_governance.py tests\test_server_releases.py::test_release_signoff_requires_audio_campaign_governance tests\test_release_check.py::test_v105_audio_campaign_governance_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.5.0 - 2026-06-25

### Added
- Audio Campaign Governance reports, analytics summaries, immutable signed archive ZIPs, and offline archive verification.
- `audio-campaign governance`, `audio-campaign analytics`, `audio-campaign archive-zip`, `audio-campaign verify-archive`, Change Request reset commands, and `verify-audio-campaign-archive-package`.
- GA readiness `ga.audio_campaign` gate with external Audio Campaign Archive verification binding.
- Release signoff `require_audio_campaign=true` gate for signed campaign governance evidence.
- Studio Audio Campaign governance/archive controls and release-check `v105.audio_campaign_governance_smoke`.

### Verified
- `python -m pytest tests\test_audio_campaign_governance.py tests\test_cli_audio_campaigns.py tests\test_server_audio_campaigns.py tests\test_release_check.py::test_v105_audio_campaign_governance_smoke tests\test_release_check_matrix.py -q`

## v10.4.1 - 2026-06-25

### Fixed
- Signed Audio Campaign reports are now frozen read snapshots; `refresh_report()` and report API/CLI reads no longer rewrite signed campaign evidence.
- Explicit Audio Campaign refresh is blocked after signoff until the signoff is reset.
- Audio Campaign export and ZIP builds now validate signed report, case-index, source, and signoff hash bindings before writing package evidence.
- release-check `v104.audio_campaign_smoke` now covers signed refresh guard, frozen report reads, and signed export integrity failure.

### Verified
- `python -m pytest tests\test_audio_campaigns.py tests\test_cli_audio_campaigns.py tests\test_server_audio_campaigns.py tests\test_release_check.py::test_v104_audio_campaign_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.4.0 - 2026-06-25

### Added
- Release Candidate Audio Campaign store for batching Audio Lab sessions into case reports, campaign reports, signoff, export, ZIP, and offline verification.
- `audio-campaign` CLI commands, `/api/audio-campaigns/*` endpoints, and Studio Audio Campaign controls.
- `verify-audio-campaign-package` CLI verifier with real WAV, manual review, closed fix sprint, signoff, marker, ZIP safety, tamper, and redaction checks.
- release-check `v104.audio_campaign_smoke` covering fake WAV blocking, real manual campaign signoff, needs_fix to Audio Fix Sprint closeout, package verification, and redaction failure.

### Verified
- `python -m pytest tests\test_audio_campaigns.py tests\test_server_audio_campaigns.py tests\test_release_check.py::test_v104_audio_campaign_smoke tests\test_release_check_matrix.py tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.3.1 - 2026-06-25

### Fixed
- Audio Fix Sprint now redacts sensitive manual input before persisting sprint names, reviewer fields, candidate/recheck notes, selector names, and closeout owner fields.
- release-check `v103.audio_fix_sprint_smoke` now injects token-like strings, `api_key=...`, and local Windows paths to verify sprint JSON does not preserve the raw sensitive text.

### Verified
- `python -m pytest tests\test_audio_fix_sprints.py tests\test_cli_audio_fix_sprints.py tests\test_server_audio_fix_sprints.py tests\test_release_check.py::test_v103_audio_fix_sprint_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.3.0 - 2026-06-24

### Added
- Audio Fix Sprint store for turning Audio Lab `needs_fix` and `rejected` markers into prioritized repair issues, drafts, local candidates, selected candidates, recheck sessions, and closeout reports.
- `audio-fix-sprint` CLI commands, `/api/audio-fix-sprints/*` endpoints, and Studio Audio Fix Sprint controls.
- release-check `v103.audio_fix_sprint_smoke` covering duplicate open sprint guard, manual A/B selection guard, test-fake audio closeout blocking, real release-ready recheck closeout, and stale source blocking.

### Fixed
- Audio Fix Sprint closeout requires every recheck item to be release-ready audio; test fake or copied test WAV evidence cannot close as fixed.

### Verified
- `python -m pytest tests\test_audio_fix_sprints.py tests\test_cli_audio_fix_sprints.py tests\test_server_audio_fix_sprints.py tests\test_release_check.py::test_v103_audio_fix_sprint_smoke -q`
- `python -m song_agent.cli release-check --profile v10 --skip-tests --json`

## v10.2.1 - 2026-06-24

### Fixed
- Audio Lab session closeout now records `closed_needs_fix` when any manual review is `needs_fix`; only fully accepted sessions close as plain `closed`.
- Audio Lab session reports now surface `test_fake_count`, `real_audio_count`, `release_ready_audio_count`, and `test_fake_audio_not_release_ready` so test WAV evidence cannot be mistaken for real renderer acceptance.
- release-check `v102.audio_lab_real_listening_smoke` now covers `needs_fix` closeout, accepted-only closeout, and session-level test-fake audio evidence.

### Verified
- `python -m pytest tests\test_audio_lab.py tests\test_cli_audio_lab.py tests\test_server_audio_lab.py tests\test_release_check.py::test_v102_audio_lab_real_listening_smoke -q`

## v10.2.0 - 2026-06-24

### Added
- Audio Lab environment checks for local renderer/profile readiness with redacted renderer summaries.
- Audio Lab smoke runs that generate deterministic SongPlan/MIDI artifacts and optionally render WAV through a real renderer profile; tests can inject a `test_fake` WAV writer that is explicitly not release-ready.
- Manual listening sessions with playback confirmation, reviewer name/role requirements, WAV hash binding, stale guards, issue markers, and draft ReviewTask/Audio Revision/Mix Patch repair entry points.
- Audio Lab A/B comparisons that bind left/right artifact hashes and require manual playback confirmation before recording preference.
- `/api/audio-lab/*`, `audio-lab` CLI commands, Studio Audio Lab controls, and release-check `v102.audio_lab_real_listening_smoke`.

### Verified
- `python -m pytest tests\test_audio_lab.py tests\test_cli_audio_lab.py tests\test_server_audio_lab.py tests\test_release_check_matrix.py tests\test_release_check.py::test_v102_audio_lab_real_listening_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v10.1.1 - 2026-06-24

### Fixed
- `maintenance backup restore --overwrite` now creates and verifies a `target-before-restore` backup before writing into a non-empty restore target.
- Restore aborts before writing if the pre-restore backup fails verification.
- `maintenance backup create` now returns failed status and non-zero CLI exit when backup verification fails.
- `POST /api/maintenance/backups` now returns conflict when backup creation produces a failed verification report.
- release-check `v101.lts_maintenance_backup_restore_smoke` now covers overwrite pre-restore backup, pre-restore verification failure, and redaction-polluted backup creation.

### Verified
- `python -m pytest tests\test_lts_maintenance.py tests\test_lts_backup_verifier.py tests\test_cli_lts_maintenance.py tests\test_server_lts_maintenance.py tests\test_release_check.py::test_v101_lts_maintenance_backup_restore_smoke -q`

## v10.1.0 - 2026-06-24

### Added
- LTS Maintenance Center with CLI/API/Studio status, backup list, upgrade preflight, migration, and periodic maintenance checks.
- Maintenance Backup ZIP creation and offline verifier with fixed sidecars, `data/musicforge/` payloads, manifest/hash checks, raw ZIP path checks, duplicate detection, forbidden local config checks, and redaction scan.
- Safe restore planning and confirm-only restore flow that refuses unsafe paths and treats provider/renderer local config as manual reconfiguration.
- `maintenance check` profiles for daily, weekly, release, and emergency operations plus release-check `v101.lts_maintenance_backup_restore_smoke`.
- Backup/restore and upgrade runbooks for GA/LTS handoff.

### Verified
- `python -m pytest tests\test_lts_maintenance.py tests\test_lts_backup_verifier.py tests\test_cli_lts_maintenance.py tests\test_server_lts_maintenance.py tests\test_release_check_matrix.py tests\test_release_check.py::test_v101_lts_maintenance_backup_restore_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v10.0.1 - 2026-06-24

### Fixed
- `verify-ga-readiness-report --require-manual-acceptance` now requires an external Music Acceptance report and verifies manual human review evidence instead of trusting the GA report check row.
- `verify-ga-readiness-report --require-final-readiness` now requires the external Final Handoff ZIP plus its verification report and binds ZIP sha256, size, manifest hash, status, and GA summary fields.
- release-check `v100.ga_lts_readiness_smoke` now covers full-resigned GA readiness reports that forge manual and final readiness rows.

### Verified
- `python -m pytest tests\test_ga_readiness.py tests\test_cli_ga_readiness.py tests\test_release_check.py::test_v100_ga_lts_readiness_smoke -q`

## v10.0.0 - 2026-06-23

### Added
- GA/LTS readiness report, `ga-check` and `verify-ga-readiness-report` CLI, `/api/ga` and `/api/ga/check` endpoints, and Studio System Health panel.
- GA release-check profile with v10 readiness smoke covering docs, manual acceptance requirement, final readiness requirement, and secret redaction.
- Productization docs for getting started, local acceptance, manual music review, release, troubleshooting, maintenance, and secrets handling.

### Verified
- `python -m pytest tests\test_ga_readiness.py tests\test_cli_ga_readiness.py tests\test_server_ga_readiness.py tests\test_release_check.py::test_v100_ga_lts_readiness_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile ga --skip-tests --json`

## v9.9.0 - 2026-06-23

### Added
- Trust Operations Final Readiness Certificate and Handoff Pack for final v9 readiness evidence across Hub, delivery, incidents, Knowledge, Controls, Continuous Assurance, Assurance Watch, and Watch Signoff.
- Fixed-structure Final Handoff ZIP, offline verifier, signed handoff history, Change Request reset, immutable export/ZIP guards, and Hub `--require-final-readiness` gate.
- API, CLI, Studio controls, and release-check `v99.trust_operations_final_readiness_smoke` covering current external evidence binding, full-resign signed-by tamper, ZIP allow-list, redaction, signed delete-bypass guard, reset, and Hub final gate.

### Verified
- `python -m pytest tests\test_trust_operations_final_readiness.py tests\test_server_trust_operations_final_readiness.py tests\test_cli_trust_operations_final_readiness.py tests\test_release_check.py::test_v99_trust_operations_final_readiness_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.8.1 - 2026-06-23

### Fixed
- Assurance Watch Signoff history now records hash-chained events and binds the signoff creation event to the signed reviewer, role, reason, payload hash, signoff hash, and closeout hash.
- Assurance Watch Signoff Archive verifier now rebuilds the history chain and rejects full-resign attempts that modify `watch-signoff.json` public signoff fields while only updating hashes.
- release-check `v98.trust_operations_assurance_watch_signoff_smoke` now covers `full_resign_signed_by=failed`.

### Verified
- `python -m pytest tests\test_trust_operations_assurance_watch_signoff.py tests\test_release_check.py::test_v98_trust_operations_assurance_watch_signoff_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.8.0 - 2026-06-23

### Added
- Trust Operations Assurance Watch Signoff closeout, signed evidence, Change Request reset, immutable archive export/ZIP, and offline verifier.
- Hub verifier `--require-assurance-watch-signoff` gate that requires current Watch, Watch Signoff, Continuous Assurance, and Hub verification evidence.
- API, CLI, Studio controls, and release-check `v98.trust_operations_assurance_watch_signoff_smoke` covering archive-only downgrade, stale Watch verification, signed payload tamper, history tamper, delete-bypass guard, CR reuse, ZIP allow-list, and redaction.

### Verified
- `python -m pytest tests\test_trust_operations_assurance_watch_signoff.py tests\test_cli_trust_operations_assurance_watch_signoff.py tests\test_server_trust_operations_assurance_watch_signoff.py tests\test_release_check.py::test_v98_trust_operations_assurance_watch_signoff_smoke tests\test_cli_release_check_matrix.py::test_release_check_cli_v9_profile_lists_trust_operations_hub tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.7.0 - 2026-06-22

### Added
- Trust Operations Assurance Watch schedules local Continuous Assurance review cadence, builds Watch Queues, and emits Drift Action Packs without executing repairs.
- Fixed-structure Assurance Watch ZIP export plus offline verifier with source-derived queue/action semantics, ZIP safety checks, redaction scan, and external Assurance/Hub current binding.
- Hub verifier `--require-assurance-watch-clear` gate that requires a clear Watch queue, current Watch verification report, current Hub verification report, and matching external Hub evidence.
- API, CLI, Studio controls, and release-check `v97.trust_operations_assurance_watch_smoke` covering clear queue, Hub gate, full-resign queue/action forgery, stale export, extra ZIP entries, and redaction.

### Verified
- `python -m pytest tests\test_trust_operations_assurance_watch.py tests\test_server_trust_operations_assurance_watch.py tests\test_cli_trust_operations_assurance_watch.py tests\test_release_check.py::test_v97_trust_operations_assurance_watch_smoke tests\test_cli_release_check_matrix.py::test_release_check_cli_v9_profile_lists_trust_operations_hub tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.6.1 - 2026-06-22

### Fixed
- Continuous Assurance now blocks explicitly supplied delivery verification reports when any report status is not `passed`.
- Assurance policies with `require_delivery_ready=true` now fail missing delivery verification report types instead of silently passing.
- release-check `v96.trust_operations_continuous_assurance_smoke` now covers `failed_delivery=failed`.

### Verified
- `python -m pytest tests\test_trust_operations_continuous_assurance.py tests\test_release_check.py::test_v96_trust_operations_continuous_assurance_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.6.0 - 2026-06-22

### Added
- Trust Operations Continuous Assurance with policy, run, report, evidence index, external verification summary, fixed-structure Assurance Archive ZIP, and offline verifier.
- Hub verifier `--require-continuous-assurance` gate that binds the current Assurance Archive, Assurance verification report, current Hub ZIP, Hub manifest hash, and Hub verification report.
- CLI/API/Studio controls for Assurance refresh/export/ZIP/verify workflows.
- release-check `v96.trust_operations_continuous_assurance_smoke` covering normal assurance, Hub gate, stale external evidence, full-resign report tamper, and fixed ZIP allow-list enforcement.

### Verified
- `python -m pytest tests\test_trust_operations_continuous_assurance.py tests\test_cli_trust_operations_continuous_assurance.py tests\test_server_trust_operations_continuous_assurance.py tests\test_release_check.py::test_v96_trust_operations_continuous_assurance_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.5.0 - 2026-06-21

### Added
- Trust Operations Control Signoff with signed control evidence, control exceptions, approved Change Request reset, immutable archive export, and offline archive verifier.
- Hub verifier `--require-trust-control-signoff` gate that binds the current Control Signoff Archive, Control Signoff verification report, Control ZIP, Hub ZIP, Incident Board ZIP, and Incident Knowledge ZIP evidence.
- Studio/API/CLI controls for Control Signoff sign/export/ZIP/verify/reset workflows.
- release-check `v95.trust_operations_control_signoff_smoke` covering signoff, Hub gate, stale Control verification, signed-by/source/history full-resign tamper, critical exception forgery, extra ZIP entries, deleted signoff file bypass, and Change Request reuse.

### Verified
- `python -m pytest tests\test_trust_operations_control_signoff.py tests\test_cli_trust_operations_control_signoff.py tests\test_server_trust_operations_control_signoff.py tests\test_release_check.py::test_v95_trust_operations_control_signoff_smoke tests\test_webui.py::test_webui_contains_encoded_audio_acceptance_controls -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.4.0 - 2026-06-21

### Added
- Trust Operations Control Catalog for baseline preventive controls and Knowledge-derived controls.
- Control Policy Bundle, Control Assessment, fixed-structure Control ZIP export, offline verifier, CLI, API, and Studio controls.
- Hub verifier `--require-trust-controls` gate that binds the current Hub ZIP, Hub verification report, Incident Board ZIP, Incident verification report, Incident Knowledge ZIP, Knowledge verification report, and passed Control assessment evidence.
- release-check `v94.trust_operations_control_catalog_smoke` covering normal Control assessment, Hub gate, result full-resign, derived-control downgrade, evidence binding swap, extra ZIP entry, and stale Knowledge verification.

### Verified
- `python -m pytest tests\test_trust_operations_controls.py tests\test_cli_trust_operations_controls.py tests\test_server_trust_operations_controls.py tests\test_release_check.py::test_v94_trust_operations_control_catalog_smoke tests\test_cli_release_check_matrix.py -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.3.1 - 2026-06-20

### Fixed
- Trust Operations Incident Knowledge verification now requires the external Incident Board ZIP and checks Knowledge entries against original incident facts.
- Knowledge verifier now blocks full-resign attempts that downgrade incident severity, root cause, failure mode, or recommended guard type inside the Knowledge ZIP.
- Hub `--require-incident-regression-guards` now requires Knowledge verification evidence bound to the current Incident ZIP sha256, ZIP size, manifest hash, Incident verification report, and Hub verification report.
- release-check v9.3 smoke now covers `entry_full_resign=failed`.

### Verified
- `python -m pytest tests\test_trust_operations_incident_knowledge.py tests\test_cli_trust_operations_incident_knowledge.py tests\test_server_trust_operations_incident_knowledge.py tests\test_release_check.py::test_v93_trust_operations_incident_knowledge_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.3.0 - 2026-06-20

### Added
- Trust Operations Incident Knowledge Base for turning closed, verified Hub incidents into reusable Knowledge Entries.
- Regression Guard generation, guard runs, recurrence reports, fixed-structure Knowledge ZIP export, and offline verifier.
- `trust-operations-incident-knowledge` and `verify-trust-operations-incident-knowledge-package` CLIs.
- `verify-trust-operations-hub-package --require-incident-regression-guards` for binding Hub readiness to current Knowledge ZIP and verification evidence.
- Studio Trust Operations Knowledge controls and release-check `v93.trust_operations_incident_knowledge_smoke`.

### Verified
- `python -m pytest tests\test_trust_operations_incident_knowledge.py tests\test_cli_trust_operations_incident_knowledge.py tests\test_server_trust_operations_incident_knowledge.py tests\test_release_check.py::test_v93_trust_operations_incident_knowledge_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.2.1 - 2026-06-20

### Fixed
- Trust Operations Incident evidence import now rejects forged passed JSON that does not match current Hub delivery verification evidence.
- Incident closeout and Incident ZIP verification now count only passed evidence with valid Hub evidence binding.
- Incident ZIP verifier now blocks forged evidence bindings and confirms closed incidents cover the relevant Hub verifier blocker components.
- release-check v9.2 smoke now covers forged incident evidence rejection.

### Verified
- `python -m pytest tests\test_trust_operations_hub_incidents.py tests\test_cli_trust_operations_hub_incidents.py tests\test_server_trust_operations_hub_incidents.py tests\test_release_check.py::test_v92_trust_operations_hub_incident_response_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.2.0 - 2026-06-19

### Added
- Trust Operations Hub Incident Board for turning Hub blockers and failed delivery verification checks into triage, remediation plan, evidence, fix verification, closeout, export, ZIP, and offline verification records.
- `trust-operations-hub-incidents` CLI for refresh/list/triage/plan/evidence/verify-fix/close/export/ZIP/verify workflows.
- `verify-trust-operations-hub-incident-package` CLI with fixed ZIP structure, event-chain status rebuild, closeout evidence checks, external Hub verification binding, redaction scan, and ZIP safety checks.
- `verify-trust-operations-hub-package --require-incident-closeout` for binding Hub signoff readiness to a current Incident Board package and verification report.
- release-check `v92.trust_operations_hub_incident_response_smoke`.

### Fixed
- Trust Operations Incident Board refresh is idempotent by source fingerprint and no longer creates duplicate incidents for the same unresolved Hub blocker.

### Verified
- `python -m pytest tests\test_trust_operations_hub_incidents.py tests\test_cli_trust_operations_hub_incidents.py tests\test_server_trust_operations_hub_incidents.py tests\test_release_check.py::test_v92_trust_operations_hub_incident_response_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.1.1 - 2026-06-19

### Fixed
- Trust Operations Hub delivery verification now validates every same-type delivery evidence row by `component_type` and `component_id`, instead of accepting the first matching type.
- `verify-trust-operations-hub-package` and `trust-operations-hub` now accept repeated delivery verification report arguments for multi-target delivery chains.
- release-check v9.1 smoke now covers multi-distribution delivery evidence, missing external reports, and full-resign tampering of the second same-type delivery evidence row.

### Verified
- `python -m pytest tests\test_trust_operations_hub.py tests\test_release_check.py::test_v91_trust_operations_hub_delivery_runbook_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.1.0 - 2026-06-19

### Added
- Trust Operations Hub now accepts delivery-chain verification evidence for Release, Distribution, Submission, Submission Evidence, and Release Operations packages.
- Hub exports include delivery evidence, delivery readiness, delivery blockers, and delivery manual action queues as fixed-structure sidecars.
- `verify-trust-operations-hub-package --require-delivery-ready` requires current external delivery verification reports instead of trusting Hub ZIP self-summaries.
- Added Trust Operations Hub Runbook packages for safe local actions: Hub export, ZIP, and verify. Manual, signoff, reset, provider, submit, accept, and review actions remain manual-only.
- Added `trust-operations-hub-runbook` and `verify-trust-operations-hub-runbook-package` CLIs.
- Added release-check `v91.trust_operations_hub_delivery_runbook_smoke`.

### Verified
- `python -m pytest tests\test_trust_operations_hub.py tests\test_trust_operations_hub_runbook.py tests\test_cli_trust_operations_hub.py tests\test_cli_trust_operations_hub_runbook.py tests\test_release_check.py::test_v91_trust_operations_hub_delivery_runbook_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.0.1 - 2026-06-18

### Fixed
- Trust Operations Hub signed immutability now uses `signoff-history.jsonl`, so deleting `signoff.json` no longer unlocks refresh/export/ZIP mutation.
- `verify-trust-operations-hub-package --require-signed` now requires an external Hub signoff sidecar and the Hub verification report used for signoff, binding signed evidence to the current ZIP sha256, ZIP size, manifest hash, Hub report hash, and verification report hash.
- release-check v9 smoke now covers deleted-signoff mutation bypass, missing signed sidecar failure, valid signed sidecar success, old ZIP rejection, and old verification/signoff rejection.

### Verified
- `python -m pytest tests\test_trust_operations_hub.py tests\test_cli_trust_operations_hub.py tests\test_release_check.py::test_v90_trust_operations_hub_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v9.0.0 - 2026-06-18

### Added
- Trust Operations Hub for aggregating Public Trust Center, publication channel state, and publication monitoring verification into a cross-link readiness matrix, blocker register, manual action queue, evidence binding index, and verification summary index.
- Fixed-structure Trust Operations Hub export and ZIP package with offline verifier, strict ZIP safety checks, redaction scan, external current-state binding, and full-resign semantic checks.
- `trust-operations-hub` CLI for create, refresh, export, ZIP, verify, signoff, approved change-request reset, and signed immutability workflows.
- `verify-trust-operations-hub-package` CLI with `--require-ready`, `--require-current`, `--require-signed`, `--require-no-critical-blockers`, and `--require-publication-monitoring-clean`.
- release-check v9 profile and `v90.trust_operations_hub_smoke` covering signed mutation guards, CR reset, stale external publication state, open critical monitoring incidents, full-resign tamper, ZIP safety, and redaction.

### Verified
- `python -m pytest tests\test_trust_operations_hub.py tests\test_cli_trust_operations_hub.py tests\test_release_check.py::test_v90_trust_operations_hub_smoke -q`
- `python -m song_agent.cli release-check --profile v9 --skip-tests --json`

## v8.9.1 - 2026-06-17

### Fixed
- Monitoring ZIPs now include `incident-events.jsonl`, the raw incident event evidence for each exported incident.
- The monitoring verifier rebuilds incident status, severity, event counts, latest event hashes, and summaries from the event log instead of trusting `incident-report.json` fields such as `event_chain_valid`.
- `--require-no-open-critical-incidents` is now enforced from the rebuilt event-log summary, so full-resigning an open critical incident into a resolved summary is rejected.
- release-check v8.9 smoke now covers `incident_full_resign=failed`.

### Verified
- `python -m pytest tests\test_public_trust_center_publication_monitoring.py tests\test_release_check.py::test_v89_public_trust_center_publication_monitoring_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --only v89.public_trust_center_publication_monitoring_smoke --skip-tests --json`

## v8.9.0 - 2026-06-17

### Added
- Public Trust Center Publication Monitoring for running local publication probes, drift detection, incident summaries, monitoring exports, and fixed-structure monitoring ZIP packages.
- `public-trust-center-publication-monitor` CLI for monitor creation, run, export, ZIP, verify, and incident acknowledgement/resolution/waiver workflows.
- `verify-public-trust-center-publication-monitoring-package` CLI with strict ZIP structure checks, manifest/file-index/checksum binding, probe/drift/incident integrity, redaction checks, and external `publication-channel-state.json` current/revoke/supersede gates.
- release-check v8.9 smoke covering passed monitoring, missing external channel state, drift tamper, incident summary tamper, duplicate/dangerous/backslash/.MusicForge/nested/spoof/redaction ZIP defenses, and old monitoring ZIP rejection after real revoke/supersede.

### Verified
- `python -m pytest tests\test_public_trust_center_publication_monitoring.py tests\test_release_check.py::test_v89_public_trust_center_publication_monitoring_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --only v89.public_trust_center_publication_monitoring_smoke --skip-tests --json`

## v8.8.1 - 2026-06-17

### Fixed
- Publication ZIP and mirror verification now require an external `publication-channel-state.json` when `--require-no-revoked` is enabled, so already-built ZIPs are rejected after a real Store revoke or supersede operation.
- Publication channel state records current publication status, ZIP sha256, manifest hash, source hash, report hash, event chain hash, and revoke/supersede lifecycle evidence.
- release-check v8.8 smoke now covers build ZIP -> verify passed, real `revoke_publication()` -> same ZIP failed with channel state, and real `supersede_publication()` -> old ZIP failed with channel state.

### Verified
- `python -m pytest tests\test_public_trust_center_publication.py tests\test_release_check.py::test_v88_public_trust_center_publication_channels_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --only v88.public_trust_center_publication_channels_smoke --skip-tests --json`

## v8.8.0 - 2026-06-16

### Added
- Public Trust Center Publication Channels for creating local publication snapshots, static mirror directories, and publication ZIP packages from the current Trust Center, Distribution Kit, Anchor Registry, Anchor Transparency, and Acceptance Board signoff evidence.
- `verify-public-trust-center-publication-package` and `verify-public-trust-center-publication-mirror` CLIs with strict/deep verification, fixed-entry package checks, manifest/file-index/checksum binding, mirror policy validation, nested package allow-list verification, HTML safety, redaction checks, and revoked/current requirement gates.
- `public-trust-center-publication` CLI for channel creation, refresh, export, ZIP, mirror verification, package verification, revoke, and supersede workflows.
- release-check v8.8 smoke covering ready publication, mirror verification, package tamper, declared extra file, duplicate ZIP entry, dangerous/backslash paths, `.MusicForge` variants, nested ZIP rejection, redaction, and revoked publication rejection.

### Verified
- `python -m pytest tests\test_public_trust_center_publication.py tests\test_release_check.py::test_v88_public_trust_center_publication_channels_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --skip-tests --json`

## v8.7.2 - 2026-06-16

### Fixed
- Public Trust Center `--require-acceptance-board-signoff` now always requires current external evidence instead of accepting an archive-only verification path.
- The PTC verifier now requires the Acceptance Board ZIP, Board verification report, Distribution Kit ZIP, and Accepted Evidence directory when enforcing Acceptance Board Signoff Archive evidence.
- release-check v8.7 smoke now covers the archive-only downgrade path with `ptc_archive_only=failed`.

### Verified
- `python -m pytest tests\test_public_trust_center_acceptance_board.py::test_acceptance_board_signoff_required_by_ptc_and_distribution_kit tests\test_release_check.py::test_v87_public_trust_center_acceptance_board_signoff_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --only v87.public_trust_center_acceptance_board_signoff_smoke --skip-tests --json`

## v8.7.1 - 2026-06-16

### Fixed
- Public Trust Center verifier now supports `--require-acceptance-board-signoff` with an external Acceptance Board Signoff Archive, Board ZIP, Board verification report, Distribution Kit ZIP, and Accepted Evidence directory.
- Public Trust Center Distribution Kit verifier now supports the same Acceptance Board Signoff gate and binds the signoff archive back to the current Kit ZIP.
- release-check v8.7 smoke now covers missing signoff failure and signed signoff success for both top-level Public Trust Center and Distribution Kit verification.

### Verified
- `python -m pytest tests\test_public_trust_center_acceptance_board.py::test_acceptance_board_signoff_required_by_ptc_and_distribution_kit tests\test_release_check.py::test_v87_public_trust_center_acceptance_board_signoff_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --only v87.public_trust_center_acceptance_board_signoff_smoke --skip-tests --json`

## v8.7.0 - 2026-06-16

### Added
- Public Trust Center Acceptance Board Signoff with immutable signed state for board policy, report refresh, export, and board ZIP rebuilds.
- Acceptance Board Signoff Archive export/ZIP/verifier with fixed-entry ZIP validation, signoff/source integrity checks, Board ZIP binding, Board verification report binding, Distribution Kit binding, and external Accepted Evidence binding.
- Acceptance Board Change Request workflow for approved signoff reset; draft requests cannot reset signoff and applied requests cannot be reused.
- CLI/API/Studio controls for Acceptance Board signoff, signoff archive export, ZIP, verification, download, and reset via approved Change Request.
- release-check v8.7 smoke covering signoff, signed mutation blocking, archive verification, Board ZIP replacement, Distribution Kit replacement, Accepted Evidence replacement, delete-and-rebuild blocking, and Change Request reset semantics.

### Verified
- `python -m pytest tests\test_public_trust_center_acceptance_board.py::test_acceptance_board_signoff_archive_roundtrip_and_immutability tests\test_public_trust_center_acceptance_board.py::test_acceptance_board_signoff_reset_requires_approved_change_request tests\test_public_trust_center_acceptance_board.py::test_acceptance_board_signoff_archive_verifier_rejects_external_evidence_replacement tests\test_cli_public_trust_center.py::test_public_trust_center_distribution_kit_cli tests\test_server_public_trust_center.py::test_server_public_trust_center_api tests\test_release_check.py::test_v87_public_trust_center_acceptance_board_signoff_smoke -q`
- `python -m song_agent.cli release-check --profile v8 --only v87.public_trust_center_acceptance_board_signoff_smoke --skip-tests --json`

## v8.6.1 - 2026-06-15

### Fixed
- Acceptance Board verification now binds quorum participants to external Accepted Evidence ZIPs when ready/quorum/role requirements are requested.
- `accepted_evidence_dir` is now an active verifier input, and the verifier cross-checks participant role, organization, result, response payload hash, binding hash, evidence hash, and accepted evidence verification hash against external evidence packages.
- release-check v8.6 smoke now covers a full package re-sign attack that forges a receiver role into a required role.

### Verified
- `python -m pytest tests\test_public_trust_center_acceptance_board.py tests\test_cli_public_trust_center.py::test_public_trust_center_distribution_kit_cli tests\test_release_check.py::test_v86_public_trust_center_acceptance_board_smoke -q`

## v8.6.0 - 2026-06-15

### Added
- Public Trust Center Acceptance Board for aggregating multiple Distribution Kit external acceptance responses into a quorum-based ready/blocked decision.
- Board policy requirements for accepted count, organization count, required roles, needs_changes/rejected handling, critical findings, and current accepted evidence.
- `verify-public-trust-center-acceptance-board-package` CLI with response proof, accepted evidence summary, quorum evidence, external Distribution Kit binding, fixed-entry ZIP, and redaction checks.
- Public Trust Center CLI/API/Studio controls for Acceptance Board policy, refresh, export, ZIP, verify, download, and signoff draft creation.
- release-check v8.6 smoke covering ready quorum, missing role, needs_changes, rejected, stale source, participant full-resign tamper, declared extra file, and Kit mismatch.

### Verified
- `python -m pytest tests\test_public_trust_center_acceptance_board.py tests\test_cli_public_trust_center.py::test_public_trust_center_distribution_kit_cli tests\test_server_public_trust_center.py::test_server_public_trust_center_api tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v86_public_trust_center_acceptance_board_smoke -q`

## v8.5.1 - 2026-06-15

### Fixed
- Accepted Evidence ZIPs now include stored response verification and binding proof sidecars, so reviewer public fields cannot be forged by fully re-signing the evidence report, public response, binding summary, and manifest together.
- Accepted Evidence verifier now cross-checks public response projection hashes, raw response SHA-256, response payload hash, verification hash, and binding summary hash against the stored response artifacts.
- release-check v8.5 smoke now covers full public response re-sign tampering that updates the evidence report and manifest in sync.

### Verified
- `python -m pytest tests\test_public_trust_center_distribution_kit_acceptance.py -q`

## v8.5.0 - 2026-06-15

### Added
- Public Trust Center Distribution Kit Acceptance workflow for generating external response templates, importing explicitly bound receiver responses, and producing accepted evidence ZIPs.
- `verify-public-trust-center-distribution-kit-accepted-evidence-package` CLI with fixed-entry ZIP validation, source binding checks, external Distribution Kit matching, redaction scan, and full-resign tamper coverage.
- Public Trust Center CLI/API/Studio controls for Distribution Kit acceptance templates and accepted evidence export, ZIP, and verification.
- release-check v8.5 smoke covering accepted evidence, missing binding rejection, wrong Kit hash rejection, public response full-resign tamper, declared extra files, redaction, and Kit mismatch.

### Verified
- `python -m pytest tests\test_public_trust_center_distribution_kit_acceptance.py tests\test_cli_public_trust_center.py::test_public_trust_center_distribution_kit_cli tests\test_server_public_trust_center.py::test_server_public_trust_center_api tests\test_webui.py::test_webui_contains_release_workspace_controls tests\test_release_check.py::test_v85_public_trust_center_distribution_kit_acceptance_smoke -q`

## v8.4.1 - 2026-06-15

### Fixed
- Distribution Kit verifier now enforces a fixed ZIP entry allow-list instead of trusting `distribution-kit-manifest.json` to declare additional files.
- `manifest.files[]` and `file-index.json.files[]` must match the fixed Distribution Kit structure, so a fully re-signed package with extra benign-looking text files is rejected.
- release-check v8.4 smoke now covers declared extra file tampering with synchronized manifest/file-index hash recomputation.

### Verified
- `python -m pytest tests\test_public_trust_center_distribution_kit.py tests\test_release_check.py::test_v84_public_trust_center_distribution_kit_smoke -q`

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
