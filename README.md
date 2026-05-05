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
POST /api/jobs/<job-id>/nodes/<node-name>/retry
```

Node-level retry is an API placeholder in v0.3.0 and returns `501`; full
downstream invalidation and replay is deferred to v0.3.1.

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
