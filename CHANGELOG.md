# Changelog

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
