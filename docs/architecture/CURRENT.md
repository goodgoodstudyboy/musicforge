# Current Architecture

MusicForge v14.0.0 is a local-first modular monolith. It remains one Python
process, one installation, and one local workspace. All active product paths
follow `interfaces -> application -> domains -> platform`. The six bounded
contexts are Creation, Studio, Quality, Delivery, Trust, and Program. Retained
flat Python imports are static public facades and are not imported by active
code. Historical release checks are read-only compatibility paths.

## Current Layers

- `song_agent/platform/`: dependency-free shared contracts plus shared
  verification, lifecycle, and persistence kernels.
- `song_agent/application/`: orchestration that coordinates domain behavior;
  active code does not import `legacy_dependencies`.
- `song_agent/domains/`: explicit creation, studio, quality, delivery, trust,
  and program bounded contexts.
- `song_agent/interfaces/`: registry-driven CLI, API, and Studio adapters with
  no direct Store wiring, wildcard composition, or dynamic symbol forwarding.
- `song_agent/release_check/`: domain-owned matrix, runner, performance, and
  check providers. The historical monolith is archive-only.

## v12.14 Changes

- `JobState` is owned by `application/jobs/model.py`; `server.JobState` remains
  a compatibility export.
- Song generation is owned by `application/generation/service.py`;
  `cli.generate_request` remains a compatibility export.
- Audio Campaign release coverage is an application service shared by Server
  and release-check.
- The production import graph no longer contains the Server/CLI cycle or the
  `mix_render -> server` dependency.
- AST guardrails enforce module ownership, dependency direction, cycle,
  mega-file, and duplicate security-helper ratchets.

## v12.15 Changes

- `platform/verification/` owns ZIP safety, hashing, manifest validation,
  redaction, history checks, evidence identity checks, and report envelopes.
- `PackageSpec` fixes package layouts in code; a package manifest cannot extend
  its verifier allow-list.
- All active v12 Program/Continuity verifiers use the kernel for their security
  envelope and retain only domain-specific semantic checks locally.
- Public verifier functions, CLI commands, API routes, package schemas, and
  external evidence requirements remain compatible.
- The duplicate security-helper ratchet was lowered to the post-migration
  count; remaining copies belong to older domains and may only decrease.

## v12.16 Changes

- `platform/lifecycle/` owns history-chain writes, signoff transition guards,
  reset authorization, generation documents, immutable snapshot checks, and
  archive construction.
- Active v12 Program/Continuity stores no longer calculate history event hashes
  locally. Domain stores retain only current-source, policy, and evidence
  semantics.
- Change Control reset entry points use one approved, action-scoped,
  target/source-bound, single-use authorization rule and still run their
  domain runtime checks.
- Legacy histories remain byte-for-byte read compatible. Explicit migration
  creates a separate target and rollback copy with a fingerprint report.

## v12.17 Changes

- `.musicforge/state/musicforge.db` stores mutable workflow indexes,
  generation/status metadata, transaction records, migration ledgers, and ID
  counters using SQLite WAL and explicit transactions.
- Signed reports, bindings, JSONL history, archives, and public ZIP evidence
  remain filesystem artifacts. Offline verification never reads SQLite.
- Active v12 Stores share a PID-aware cross-process write lock; verifier-only
  paths remain lock-free.
- Multi-file platform writes use immutable generation directories and an atomic
  current pointer, with intent/marker recovery across every commit boundary.
- Legacy v12.9-v12.12 state migration is explicit, backed up, hash verified,
  idempotent, reversible, and never deletes source evidence.

## Baseline

`architecture-v14-policy.json` and the v14 migration/retirement/quality/contract
documents are authoritative for current ratchets. Runtime metrics are generated
under `runs/` and are not committed. The active graph has no production cycles,
boundary violations, dependency exceptions, or compatibility imports.

## v13 Cutover

- All active Program verifiers use `platform.verification.PackageSpec`.
- Active signoff/reset/archive workflows use `platform.lifecycle`.
- Active mutable Program stores use SQLite transactions and `WorkspaceLock`.
- Release and GA gates accept Evidence Graph manifests and policy profiles.
- `release_check_matrix.py` and `release_check_runner.py` were removed; the
  canonical package owns those APIs.
- Schema 2 migration requires a verified backup, source preservation,
  rollback rehearsal, and a verified migration evidence archive.

## v13.4 Program Vertical Slice

- Active Unified Release Program Stores and verifiers live under
  `domains/program`; flat `unified_release_program*.py` modules are short
  compatibility exports only.
- `application/program` owns Program composition and operation dispatch.
- The Program API uses an explicit route registry and delegates to the
  application HTTP adapter; the interface route contains no Store behavior.
- Active Program CLI commands use compact command specs and application
  components. Program domain/application modules have no compatibility
  imports, and the production import graph remains acyclic.

## v13.5 Interface Decomposition

- API inventory is a fixed 117-route manifest with versioned schemas; server
  startup no longer parses `_handle_request` source.
- CLI command implementations and API route families are physically split at
  behavior boundaries. Every Python interface module is below 600 lines and
  command modules do not import Stores directly.
- `interfaces/api/runtime.py` is a 43-line facade over bounded dependency,
  JobStore, BatchRunner, and helper modules.
- Program HTTP routing is split by Program capability. Release signoff now
  enters through an application use-case instead of a 1000-line API handler.
- Studio loads fixed-manifest ES modules; `app.js` is a 14-line entry and each
  product panel is an independently loaded module.
- Remaining flat modules have one active anti-corruption import each. Active
  compatibility edges fell from 407 to 227; active cycles and boundary
  violations remain zero.

## v13.6 Policy Cutover

- Evidence Graph and Policy Engine decisions are authoritative for GA,
  Release, and Program gates; legacy require summaries are non-authoritative.
- Capability metadata binds CLI, API, Web, release-check, and policy ownership.
- Shared redaction moved into the Verification Kernel and active compatibility
  edges fell from 227 to 226.

## v13.7 Release Governance

- `latest`, `ga`, `v13`, and `security` reject legacy callable provenance.
- Historical release checks are labeled and isolated to full/nightly or their
  historical major profile; the expired `release_checks.py` facade is removed.
- Test modules have explicit marker-manifest ownership; quality/nightly verify
  the final SHA and separate active, legacy, full, migration, and coverage
  evidence.
- Root documentation is bounded and indexed. Final reviewer packages require
  current quality/nightly, full/current release profiles, active/legacy tests,
  and non-empty byte-identical migration rollback evidence.
- The quality acceptance-diff implementation moved into its bounded context,
  reducing active compatibility edges from 226 to 225.

## v13.8 LTS Recertification

- Final structural certification requires zero Program-slice compatibility
  imports, zero legacy callables in current profiles, no open structural P1,
  and a non-empty migration with byte-identical rollback.
- Source comparison exposes total, active, and compatibility lines. The active
  modular source is compared with v12.13; the supported v13 compatibility
  source is retained in the report and cannot grow through the architecture
  ratchet.
- Final reviewer verification binds quality/nightly attestations, full and
  current release-check profiles, active and legacy suites, migration,
  performance, release alignment, architecture, and final SHA.
- Run-state contracts moved to `platform/contracts`; active compatibility
  edges fell from 225 to 224 while the Program slice remains at zero.

## v14.0 Domain Cutover

- 270 production modules moved into six bounded contexts; 271 retained public
  imports are static facades with no business implementation.
- Active compatibility edges, `legacy_dependencies` imports, duplicate ZIP
  security helpers, custom lifecycle algorithms, wildcard interface imports,
  dynamic forwarding, anonymous Python part modules, and direct interface Store
  references are all zero.
- CLI parser semantics, API route schemas, Studio control IDs/endpoints, and
  public output/exit policies are frozen against v13.8 and independently checked.
- Mutable state migration writes a verified backup, prepared intent, committed
  report, and commit marker. Signed evidence, history, bindings, anchors,
  checkpoints, current pointers, and ZIPs are not rewritten.
- v14 quality policy enforces active and migrated coverage, strict shared-kernel
  typing, no new active mypy debt, and explicit v14.1 owners for remaining large
  domain modules.
