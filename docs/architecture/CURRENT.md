# Current Architecture

MusicForge v12.15 is a local-first modular monolith in transition from a large
flat package. It remains one Python process, one installation, and one local
workspace. The existing CLI, HTTP API, Studio, evidence packages, and offline
verifiers remain compatible while platform contracts are introduced.

## Current Layers

- `song_agent/platform/`: dependency-free shared contracts and the shared
  Verification Kernel; lifecycle and persistence primitives follow in later
  roadmap stages.
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

## Baseline

`architecture-baseline.json` is authoritative for the current ratchets. Runtime
metrics are generated at `runs/architecture/metrics.json` and are not committed.
Historical cycles and exceptions may be removed without changing the baseline;
new cycles, exceptions, modules, or mega-file growth require an explicit
baseline review.
