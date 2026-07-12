# Current Architecture

MusicForge v12.17 is a local-first modular monolith in transition from a large
flat package. It remains one Python process, one installation, and one local
workspace. The existing CLI, HTTP API, Studio, evidence packages, and offline
verifiers remain compatible while platform contracts are introduced.

## Current Layers

- `song_agent/platform/`: dependency-free shared contracts plus shared
  verification, lifecycle, and persistence kernels.
- `song_agent/application/`: orchestration that coordinates domain behavior.
- Flat `song_agent/*.py` modules: legacy domain modules assigned to one of the
  six bounded contexts in `architecture-baseline.json`.
- `song_agent/cli.py`, `server.py`, and `webui.py`: compatibility interfaces
  pending decomposition in v12.18.
- `release_checks.py`, `release_check_*`, and `architecture_guardrails.py`:
  release engineering. `ga_readiness.py` remains in the trust domain with the
  single temporary dependency exception recorded in `DEBT.md`.

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
Historical cycles and exceptions may be removed without changing the baseline;
new cycles, exceptions, modules, or mega-file growth require an explicit
baseline review.
