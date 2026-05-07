# Song Agent

An open, model-provider-agnostic songwriting agent.

The goal is not to wrap Suno, Udio, Mureka, ElevenLabs Music, or any other
closed music generator. The core idea is:

1. Use a frontier/world model API for reasoning, lyrics, composition, and
   arrangement planning.
2. Emit open musical formats such as JSON, MIDI, MusicXML, ABC, or Strudel code.
3. Render with open or locally controlled tools such as FluidSynth, MuseScore,
   REAPER, Ableton, LMMS, Strudel, or Tone.js.

## MVP

The first working version generates an instrumental song demo:

```text
song brief
  -> lyrics and structure
  -> chords
  -> melody
  -> bass and drums
  -> MIDI
  -> WAV/MP3 render
```

Human vocals are intentionally deferred. Singing synthesis is a separate
problem and needs a dedicated open backend.

Current local MVP:

```powershell
python -m song_agent.cli examples\song_request.json --dry-run
python -m song_agent.cli examples\song_request.json --out runs\demo
python -m song_agent.cli generate examples\song_request.json --out runs\demo
python -m song_agent.cli generate examples\song_request.json --out runs\demo-nodes --pipeline-mode multinode
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

The full run writes:

```text
runs/demo/data/request.json
runs/demo/data/run-options.json
runs/demo/data/nodes/*.json
runs/demo/data/song-plan.json
runs/demo/data/run-summary.json
runs/demo/logs/events.jsonl
runs/demo/renders/song.mid
```

The default generation path is model-optional: it uses a deterministic composer
so the JSON-to-MIDI loop can be tested without network access.

## Local Studio

The browser panel runs locally and uses the same deterministic pipeline as the
CLI:

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`, fill in a song request, and start a job. Completed
jobs write `job-state.json`, `song-plan.json`, `events.jsonl`, and `song.mid`
under `runs/<job-id>/`.

v0.6.0 adds local access control for Studio. Loopback hosts can still run without
a token:

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

Binding to a non-localhost host requires a token:

```powershell
python -m song_agent.cli serve --host 0.0.0.0 --port 8787 --access-token <token>
```

You can also use `MUSICFORGE_ACCESS_TOKEN`. When auth is enabled, Studio stores
the token only in `sessionStorage` and sends it as `Authorization: Bearer ...`.
`GET /api/info` remains public and reports whether auth is required; jobs,
provider, renderer, batch, artifacts, audio, delete, open-folder, and render
actions require Bearer auth.

The v0.1.2 panel adds single-job inspection and management:

- Timeline, Tracks, Validator, SongPlan JSON, Logs, and Artifacts tabs.
- `hide` / `unhide` for keeping old jobs out of the default list without
  deleting files.
- `cancel` for queued/running jobs and `delete` for non-running jobs, with run
  directory path checks before deletion.
- Startup recovery that marks leftover `queued` or `running` jobs as
  `interrupted` instead of showing them as active forever.

Runtime view APIs:

```text
GET /api/jobs/<job-id>/timeline
GET /api/jobs/<job-id>/tracks
GET /api/jobs/<job-id>/quality
GET /api/jobs/<job-id>/validator
POST /api/jobs/<job-id>/hide
POST /api/jobs/<job-id>/unhide
POST /api/jobs/<job-id>/cancel
POST /api/jobs/<job-id>/delete
```

## Music Quality Layer

v0.7.0 adds compatible quality metadata to `song-plan.json`. Existing plans
without this field still load and render, while new local and multinode runs add:

- primary motif metadata
- section role, energy, tension, density, transition, and hook markers
- hook section list
- structure, melody, harmony, arrangement, lyric-fit, and overall scores
- quality warnings and critic issues

Studio exposes this through the Quality tab. The Timeline tab also shows section
energy, tension, density, role, and hook markers so a generated song can be
checked as a musical structure, not only as MIDI data.

v0.7.1 keeps this layer backward compatible: old `song-plan.json` files without
`quality` are inferred in Runtime, Timeline, Validator, and Quality views without
rewriting the artifact.

## Batch Production

v0.4.0 adds local batch production to Studio. Batch metadata is stored under
`.musicforge/batches/<batch-id>/`, while every generated song still writes a
normal job run under `runs/<job-id>/`.

The Batch workspace can import CSV from a file or textarea, launch items with a
max concurrency from 1 to 4, pause queued work, resume, retry failed items,
export a JSON report, and open each linked job detail.

CSV columns:

```text
title,language,style,theme,duration_seconds,tempo_bpm,key,vocal_mode,lyrics,generation_mode,pipeline_mode
```

Required columns are `title`, `language`, `style`, and `theme`. Defaults are
`duration_seconds=180`, `vocal_mode=guide_melody`, `generation_mode=local`, and
`pipeline_mode=multinode`. Row-level `generation_mode` and `pipeline_mode`
values override the batch defaults.

Optional Project archival columns:

```text
project,version_name,version_note
```

When `project` is present, a completed batch item is automatically attached as a
Project version. Existing CSV files without those columns keep the old behavior.

Batch APIs:

```text
GET  /api/batches
GET  /api/batches/<batch-id>
POST /api/batches/import-csv
POST /api/batches/<batch-id>/launch
POST /api/batches/<batch-id>/pause
POST /api/batches/<batch-id>/resume
POST /api/batches/<batch-id>/retry-failed
GET  /api/batches/<batch-id>/export
POST /api/batches/<batch-id>/hide
POST /api/batches/<batch-id>/unhide
POST /api/batches/<batch-id>/delete
POST /api/batches/<batch-id>/open-folder
```

## Project Workspace

v0.9.0 adds Project workspace metadata for organizing multiple generated jobs
as versions of the same song. v1.0.0 extends this into a controlled creation
and delivery workflow: versions can branch from selected/final/any parent
version, quality gates can block low-scoring final candidates, and final export
bundles collect the approved artifacts for handoff. v1.2.0 rounds out the
workspace with reusable edit presets, A/B version comparison, safe Final Export
ZIP delivery, and Project list search/filter controls.

Project metadata lives under
`.musicforge/projects/<project-id>/` and does not copy or delete run artifacts:

```text
.musicforge/projects/<project-id>/project.json
.musicforge/projects/<project-id>/versions.json
.musicforge/projects/<project-id>/events.jsonl
.musicforge/projects/<project-id>/export.json
.musicforge/projects/<project-id>/quality-gate.json
.musicforge/projects/<project-id>/final-export/
.musicforge/projects/<project-id>/final-export.zip
.musicforge/edit-presets.json
```

A Project can hold several versions, each referencing one existing job/run.
Studio can create a Project, create a new version job from the current song
form, attach an existing job, mark selected/final versions, compare two
versions, and export a Project manifest. Deleting a Project removes only Project
metadata; job runs still use the normal Job delete flow.

Project versions now record lineage and release metadata:

- `parent_version_id`
- `variant_type`
- `change_summary`
- `quality_gate_status`
- `quality_gate_score`
- `final_export_path`

Variation creation reuses the parent version request and applies an explicit
patch for allowed request fields such as style, theme, tempo, key, duration, and
lyrics. The new child job can run in local or provider mode and single or
multinode pipeline mode.

v1.1.0 adds non-destructive local edit versions. Pick a completed Project
version, choose an edit type and target, and MusicForge creates a new child
version instead of modifying the parent run. The first local edit engine supports
section energy, section harmony, track density, lyrics rewrite, melody
variation, and light arrangement edits. Each edit job writes:

```text
runs/<job-id>/data/edit-metadata.json
runs/<job-id>/data/song-plan.json
runs/<job-id>/renders/song.mid
```

Edit metadata records the parent version/job, target, instruction, preserve
constraints, strength, summary, and warnings. Stems and audio are not inherited;
render them again for the edited version when needed.

Edit presets can be applied from Studio's Project Edit tab. Built-in presets
cover common edits such as lifting the final chorus, simplifying verse bass,
brightening chorus harmony, and rewriting a chorus hook. User presets are stored
locally in `.musicforge/edit-presets.json`, which is ignored by Git. Presets
store only generic edit intent defaults, not project IDs, version IDs, job IDs,
tokens, or local file paths. Section harmony presets are validated against the
supported local MIDI chord set before they can be saved or applied.

v1.3.0 adds provider-backed edit previews. In Studio, choose Provider mode in
the Project Edit tab, write a natural-language instruction, then Generate
Preview. The provider returns a constrained edit patch only; MusicForge applies
that patch locally, validates the resulting SongPlan, and stores preview files
under:

```text
.musicforge/projects/<project-id>/edit-previews/<preview-id>/
  preview.json
  patch.json
  candidate-song-plan.json
  validator-report.json
  quality.json
```

Apply Preview creates the official child Project version. Preview alone does
not modify the parent version, selected version, final version, or version
list. Provider usage records are written to `runs/<job-id>/data/provider-usage.json`
after apply; they contain model, operation, template, status, request id, and
token counts when the provider returns usage data, but no API key or raw
credential.

v1.4.0 adds Provider Edit Candidate Groups. In the Project Candidates tab,
choose a parent version, set Candidate Count from 2 to 5, and Generate
Candidates. MusicForge stores each provider patch candidate under the Project,
applies it locally to a candidate SongPlan, validates it, scores it, and ranks
the ready candidates. Candidate groups do not create official Project versions
until one candidate is applied.

```text
.musicforge/projects/<project-id>/candidate-groups/<group-id>/
  group.json
  provider-usage.json
  candidates/
    cand-001/
      candidate.json
      patch.json
      candidate-song-plan.json
      validator-report.json
      quality.json
      critic.json
```

Candidate groups are bound to the parent `song-plan.json` source hash. If the
parent changes after candidate generation, applying the group is rejected as
stale. Applying a candidate creates one official child Project version; the
remaining candidates stay as review artifacts and are not added to the version
list.

Prompt templates are managed from Studio's Prompt Templates panel and stored in
`.musicforge/prompt-templates.json`, which is ignored by Git. Built-in provider
edit templates can be overridden locally and reset. Templates are validated for
size and local absolute path leakage before saving.

Quality Gate is stored per Project. Defaults require the generated `SongPlan`
to meet baseline quality scores, but do not require WAV or stems because local
audio rendering depends on user renderer setup. Setting final evaluates the gate
and rejects failed versions unless `force=true` is used; force overrides are
recorded in Project events.

Final Export writes a directory bundle under the Project:

```text
.musicforge/projects/<project-id>/final-export/
  manifest.json
  README.txt
  project-export.json
  song-plan.json
  run-summary.json
  validator-report.json
  quality-report.json
  song.mid
  song.wav
  stems/
```

The bundle copies only files from the selected version's run directory. Stale
stem manifests are detected by source hash and skipped instead of copying old
track material.

Final Export ZIP builds `.musicforge/projects/<project-id>/final-export.zip`
from the existing `final-export/` directory. ZIP entries are relative paths
only; symlinks, `..`, absolute paths, and files outside the final-export
directory are rejected or skipped. The manifest records ZIP size, sha256, and
entry count for handoff checks.

The Compare tab uses the Project Compare API to show A/B quality, gate status,
edit preset metadata, changed sections, changed tracks, MIDI links, and WAV
players when audio exists. The recommendation field is deterministic guidance
only; it never changes selected or final versions.

Project APIs:

```text
GET  /api/projects?q=<text>&status=<status>&variant_type=<type>&hidden=false&include_hidden=false
POST /api/projects
GET  /api/projects/<project-id>
POST /api/projects/<project-id>/versions
POST /api/projects/<project-id>/versions/from-job
POST /api/projects/<project-id>/versions/<version-id>/variation
POST /api/projects/<project-id>/versions/<version-id>/edit
GET  /api/projects/<project-id>/versions/<version-id>/edit
GET  /api/projects/<project-id>/versions/<version-id>/edit-targets
POST /api/projects/<project-id>/versions/<version-id>/edit-preview
POST /api/projects/<project-id>/versions/<version-id>/edit-preview/<preview-id>/apply
POST /api/projects/<project-id>/versions/<version-id>/edit-preview/<preview-id>/delete
POST /api/projects/<project-id>/versions/<version-id>/edit-candidates
GET  /api/projects/<project-id>/candidate-groups
GET  /api/projects/<project-id>/candidate-groups/<group-id>
POST /api/projects/<project-id>/candidate-groups/<group-id>/apply
POST /api/projects/<project-id>/candidate-groups/<group-id>/delete
POST /api/projects/<project-id>/versions/<version-id>/evaluate
POST /api/projects/<project-id>/selected
POST /api/projects/<project-id>/final
GET  /api/projects/<project-id>/quality-gate
POST /api/projects/<project-id>/quality-gate
POST /api/projects/<project-id>/quality-gate/evaluate-all
GET  /api/projects/<project-id>/final-export
POST /api/projects/<project-id>/final-export
POST /api/projects/<project-id>/final-export/zip
GET  /api/projects/<project-id>/final-export.zip
GET  /api/projects/<project-id>/diff?left=v001&right=v002
GET  /api/projects/<project-id>/compare?left=v001&right=v002
GET  /api/projects/<project-id>/provider-usage
GET  /api/projects/<project-id>/export
GET  /api/projects/<project-id>/events
POST /api/projects/<project-id>/hide
POST /api/projects/<project-id>/unhide
POST /api/projects/<project-id>/delete
GET  /api/jobs/<job-id>/edit
GET  /api/edit-presets
POST /api/edit-presets
GET  /api/edit-presets/<preset-id>
POST /api/edit-presets/<preset-id>
POST /api/edit-presets/<preset-id>/delete
POST /api/edit-presets/reset
GET  /api/prompt-templates
GET  /api/prompt-templates/<template-id>
POST /api/prompt-templates/<template-id>
POST /api/prompt-templates/<template-id>/reset
POST /api/prompt-templates/reset
GET  /api/jobs/<job-id>/provider-usage
```

## Multi-node Pipeline

v0.3.0 adds a selectable multinode backend for inspecting each planning stage
before MIDI rendering. It keeps `single` as the default for backward
compatibility, while `multinode` writes structured node records under
`runs/<job-id>/data/nodes/`.

First-pass node order:

```text
brief_planner
style_planner
structure_planner
lyric_planner
harmony_planner
melody_planner
arrangement_planner
critic
repair
song_plan_builder
```

Node APIs:

```text
GET  /api/jobs/<job-id>/nodes
GET  /api/jobs/<job-id>/nodes/<node-name>
GET  /api/jobs/<job-id>/nodes/<node-name>/dependencies
POST /api/jobs/<job-id>/nodes/<node-name>/retry
```

v0.3.1 adds node-level retry for multinode jobs. Retrying a node invalidates
that node plus downstream nodes, reuses completed upstream node outputs, then
rewrites the final SongPlan, MIDI, validator report, summary, and job state.
Studio exposes this through the Nodes tab with a downstream-node confirmation.
As of v0.3.2, node retry runs in the background and the API returns `202
Accepted`; Studio polls job state until the retry completes.

## Provider Mode

v0.2.0 adds optional provider-backed `SongPlan` generation while keeping local
deterministic generation as the default.

Provider settings are stored locally in `.musicforge/provider.json`, which is
ignored by Git. API keys are never returned by the HTTP API, job state, or
provider snapshot except as a masked value.

Provider APIs:

```text
GET  /api/provider
POST /api/provider
POST /api/provider/reset
POST /api/provider/test
```

Supported first-pass provider wires:

- `mock`: local test provider with no network access.
- `openai_chat_completions`: OpenAI-compatible `/chat/completions` wire format.

The Studio form can save, reset, and test provider settings. Song jobs can run
in `local` or `provider` mode. Provider mode validates model output through
`SongPlan.from_dict()` and the same MIDI-safe validator before rendering.

## Job Controls

v0.2.1 adds task control and running protection for the local Studio:

- queued jobs can be cancelled before they start.
- running jobs accept cancel requests and stop at pipeline stage boundaries.
- failed, stalled, and interrupted jobs can be retried from the original input.
- retry appends events, increments retry metadata, and keeps provider snapshots masked.
- running jobs write `heartbeat_at`; stale running jobs are marked `stalled` by a watchdog.
- Studio job details show attempt count, retry count, heartbeat, and stalled state.

Local setup checks:

```powershell
python -m song_agent.cli doctor
python -m song_agent.cli doctor --provider-test
python -m song_agent.cli release-check
```

## Audio Rendering

v0.5.0 adds optional local WAV rendering for completed jobs:

```text
runs/<job-id>/renders/song.mid -> runs/<job-id>/renders/song.wav
```

The first renderer backend is FluidSynth with a local SoundFont. MIDI generation
does not require renderer configuration, and audio render failures do not change
a completed job into a failed job.

Renderer settings are stored in `.musicforge/renderer.json`, which is ignored by
Git. The Studio Renderer Settings form can save, reset, and test:

- renderer type: `fluidsynth`
- FluidSynth executable path
- SoundFont path (`.sf2` or `.sf3`)
- sample rate
- gain

Environment overrides:

```text
MUSICFORGE_RENDERER_TYPE
MUSICFORGE_FLUIDSYNTH_PATH
MUSICFORGE_SOUNDFONT_PATH
MUSICFORGE_AUDIO_SAMPLE_RATE
MUSICFORGE_AUDIO_GAIN
```

Renderer APIs:

```text
GET  /api/renderer
POST /api/renderer
POST /api/renderer/reset
POST /api/renderer/test
POST /api/jobs/<job-id>/render-audio
GET  /api/jobs/<job-id>/audio
```

In Studio, open a completed job and click `Render Audio`. When `song.wav`
exists, the job detail shows a browser audio player and a WAV download link.

## Stem Export

v0.8.0 adds per-track stem export for the tracks already present in
`song-plan.json`:

```text
runs/<job-id>/stems/manifest.json
runs/<job-id>/stems/midi/<stem-id>.mid
runs/<job-id>/stems/audio/<stem-id>.wav
```

The first pass renders one MIDI stem per SongPlan track. If a local FluidSynth
renderer is configured, each stem MIDI can also be rendered to a WAV stem.
Studio exposes this through the Stems tab with per-track download links, audio
players, and simple Solo/Mute controls.

Stem manifests are bound to the current `data/song-plan.json` by a source hash.
If a job retry, node retry, or direct SongPlan rewrite changes the source plan,
old stem artifacts are invalidated before they can be reused or downloaded.

Stem APIs:

```text
GET  /api/jobs/<job-id>/stems
POST /api/jobs/<job-id>/render-stems
POST /api/jobs/<job-id>/render-stem-audio
GET  /api/jobs/<job-id>/stems/<stem-id>/midi
GET  /api/jobs/<job-id>/stems/<stem-id>/audio
POST /api/batches/<batch-id>/render-stems
POST /api/batches/<batch-id>/render-stem-audio
POST /api/batches/<batch-id>/render-failed-stems
POST /api/batches/<batch-id>/render-failed-stem-audio
```

Stem downloads are resolved through `manifest.json`; request path segments are
not used as arbitrary file paths. Batch export includes stem status, manifest
path, stem count, completed stem-audio count, and stem error fields.

## Initial Direction

- Agent core: Python
- Control surface: CLI first, web console second
- LLM providers: OpenAI-compatible API first, then Anthropic/Qwen/DeepSeek
- Music interchange: structured JSON + MIDI/MusicXML
- Renderer target: MIDI first, then MuseScore/FluidSynth/REAPER adapters

## Project Layout

```text
song_agent/
  agent/        Fixed and multinode songwriting workflows
  providers/    LLM provider adapters
  renderers/    MIDI/audio render backends
  schemas/      Song data contracts
  prompts/      Prompt templates
docs/
  ARCHITECTURE.md
  MVP_PLAN.md
examples/
  song_request.json
```
