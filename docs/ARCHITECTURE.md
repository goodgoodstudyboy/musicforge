# Architecture

## Product Definition

This project is a songwriting agent with a control console. It uses general
LLM APIs for music reasoning and produces open musical artifacts that can be
rendered locally.

Non-goals:

- No Suno/Udio/Mureka/ElevenLabs/Lyria style closed music-generation API as the
  core renderer.
- No dependency on a local foundation model for the MVP.
- No promise of realistic human vocals in the first version.

## Core Workflow

```text
1. Intent capture
   User provides title, language, style, theme, duration, vocal/instrumental
   preference, and optional lyrics.

2. Song brief normalization
   Agent converts messy user input into a strict SongRequest.

3. Lyrics
   Agent writes or edits lyrics with section labels.

4. Composition plan
   Agent chooses key, tempo, meter, form, section lengths, energy curve,
   instrumentation, and arrangement notes.

5. Harmonic plan
   Agent writes chord progressions per section.

6. Melody plan
   Agent writes a singable melody as timed note events.

7. Arrangement
   Agent creates bass, drums, pads, hooks, fills, and transitions.

8. Validation
   Deterministic code checks bar lengths, note ranges, durations, and schema
   validity before rendering.

9. Rendering
   Renderer emits MIDI first. Later renderers can produce WAV/MP3 through
   FluidSynth, MuseScore, REAPER, Ableton, or a browser engine.

10. Revision
   Agent can generate variants or revise from user feedback.
```

## Boundary Between LLM and Deterministic Code

The LLM is allowed to make creative decisions. It should not be trusted to
produce final low-level files directly.

LLM responsibilities:

- Lyrics
- Song structure
- Style interpretation
- Chord choices
- Melody ideas
- Arrangement notes
- Revision suggestions

Deterministic code responsibilities:

- JSON schema validation
- Musical duration checks
- MIDI serialization
- Renderer invocation
- File organization
- Reproducible build logs

## Provider Strategy

The agent should support multiple model providers behind one interface:

- OpenAI-compatible chat/completions or responses adapter
- Anthropic adapter
- Qwen/DashScope adapter
- DeepSeek adapter
- Local Ollama adapter later

Provider output must be normalized into the same internal schema.

## Renderer Strategy

Phase 1:

- Emit `.mid`
- Optionally render `.wav` if FluidSynth and a soundfont are installed

Phase 2:

- Emit MusicXML for MuseScore
- Emit Strudel/Tone.js code for browser playback

Phase 3:

- Control REAPER or Ableton through MCP/OSC/scripts
- Add VST instrument routing and mix templates

## Human Vocals

Human vocals are not part of the MVP. A future open-vocals path could use:

- Synthesizer V compatible workflow where licensing allows it
- DiffSinger/OpenUtau/UTAU-style singing synthesis
- Phoneme and note alignment generated from the melody/lyrics schema

