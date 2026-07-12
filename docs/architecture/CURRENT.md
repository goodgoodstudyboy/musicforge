# Current Architecture

MusicForge v12.14 is a local-first modular monolith in transition from a large
flat package. It remains one Python process, one installation, and one local
workspace. The existing CLI, HTTP API, Studio, evidence packages, and offline
verifiers remain compatible while platform contracts are introduced.

## Current Layers

- `song_agent/platform/`: dependency-free shared contracts and, from v12.15
  onward, verification and persistence primitives.
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

## Baseline

`architecture-baseline.json` is authoritative for the v12.14 ratchets. Runtime
metrics are generated at `runs/architecture/metrics.json` and are not committed.
Historical cycles and exceptions may be removed without changing the baseline;
new cycles, exceptions, modules, or mega-file growth require an explicit
baseline review.
