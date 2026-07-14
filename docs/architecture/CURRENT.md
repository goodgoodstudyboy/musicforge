# Current Architecture

MusicForge v13.5 is a local-first modular monolith. It remains one Python
process, one installation, and one local workspace. Active v12/v13 Program
paths follow `interfaces -> application -> domains -> platform`. Earlier music
capabilities remain operational through flat compatibility implementations;
their imports are centralized behind application anti-corruption facades and
their complete inbound edge set is disclosed and ratcheted in the architecture
baseline. Historical v1-v11 release checks are read-only compatibility paths.

## Current Layers

- `song_agent/platform/`: dependency-free shared contracts plus shared
  verification, lifecycle, and persistence kernels.
- `song_agent/application/`: orchestration that coordinates domain behavior.
- `song_agent/domains/`: explicit creation, studio, quality, delivery, trust,
  and program bounded contexts.
- `song_agent/interfaces/`: registry-driven CLI, API, and Studio adapters;
  `cli.py`, `server.py`, and `webui.py` are bounded compatibility facades.
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

`architecture-baseline.json` is authoritative for the current ratchets. Runtime
metrics are generated at `runs/architecture/metrics.json` and are not committed.
The active graph has no cycles or domain-to-interface imports. Historical
compatibility cycles and every active-to-compatibility import remain visible in
reviewer metrics. The baseline rejects any new compatibility edge while
allowing this debt to shrink.

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
