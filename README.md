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
GET /api/jobs/<job-id>/validator
POST /api/jobs/<job-id>/hide
POST /api/jobs/<job-id>/unhide
POST /api/jobs/<job-id>/cancel
POST /api/jobs/<job-id>/delete
```

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
