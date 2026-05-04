# MVP Plan

## Version 0.1: Instrumental MIDI Song Agent

Goal: from a user brief, generate a complete song sketch as MIDI.

Inputs:

- title
- language
- style
- theme
- duration seconds
- key preference
- tempo preference
- optional lyrics
- instrumental or vocal guide

Outputs:

- `song.json`: structured song plan
- `song.mid`: rendered MIDI
- `README.md`: run metadata and prompts used

Acceptance criteria:

- User can run one command with a JSON request.
- Agent calls one configured LLM provider.
- Agent produces valid structured JSON.
- Deterministic validator catches broken bar lengths and invalid notes.
- MIDI contains at least melody, chords, bass, and drums.

## Version 0.2: Local Audio Rendering

Goal: render generated MIDI to WAV/MP3 using local tools.

Likely path:

- FluidSynth + General MIDI soundfont for WAV
- FFmpeg for MP3 conversion
- Later: MuseScore export for better default playback

## Version 0.3: Web Console

Goal: a local browser UI for non-technical usage.

Screens:

- Song brief form
- Generation progress timeline
- Version list
- Audio player
- Lyrics and structure editor
- Regenerate section / make variant actions

## Version 0.4: DAW Bridge

Goal: hand off structured song data to a real production environment.

Candidate integrations:

- REAPER MCP
- Ableton MCP
- LMMS project export
- MusicXML/MIDI export bundle

## Version 0.5: Open Singing Backend

Goal: optional vocal rendering without commercial black-box song APIs.

This should be treated as a separate research spike after instrumental output
works reliably.

