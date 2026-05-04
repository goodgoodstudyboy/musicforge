# Changelog

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
