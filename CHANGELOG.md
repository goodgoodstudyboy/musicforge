# Changelog

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
