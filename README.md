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

The first working version should generate an instrumental song demo:

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

## Initial Direction

- Agent core: Python
- Control surface: CLI first, web console second
- LLM providers: OpenAI-compatible API first, then Anthropic/Qwen/DeepSeek
- Music interchange: structured JSON + MIDI/MusicXML
- Renderer target: MIDI first, then MuseScore/FluidSynth/REAPER adapters

## Project Layout

```text
song_agent/
  agent/        Fixed songwriting workflow
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

