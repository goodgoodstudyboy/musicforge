# Local Acceptance Runbook

MusicForge separates automated smoke evidence from human listening evidence.
Synthetic auto-review is useful for CI and development checks, but it is not
manual music approval.

## MIDI Smoke

Use this when a renderer is unavailable:

```powershell
python -m song_agent.cli acceptance-check --profile midi_smoke --auto-review --render-audio never --report-out runs\acceptance-midi-smoke.json
```

This proves deterministic generation and MIDI health. It does not prove release
audio readiness.

## Developer Manual Review

```powershell
python -m song_agent.cli acceptance-check --profile developer_manual --render-audio auto --report-out runs\acceptance-developer-manual.json
```

Play the generated MIDI or WAV files and record manual review results in Studio
or through the acceptance workflow. Do not replace this with `--auto-review`
when claiming manual readiness.

## Release Candidate

```powershell
python -m song_agent.cli acceptance-check --profile release_candidate --render-audio auto
```

The release-candidate profile must cover the built-in 12-song Regression
Songbook. Duplicate song IDs do not count as coverage. Every required song ID
needs a manual accepted review before it can be treated as release-ready.

## Audio Required

If the release claims real audio readiness, use a renderer-backed profile and
require audio:

```powershell
python -m song_agent.cli acceptance-check --profile audio_required --render-audio require --manual-required
```

If WAV rendering is unavailable, do not claim audio release readiness. Release
and Distribution audio gates must remain blocked until current WAV evidence and
manual listening review exist.

## Audio Lab Listening Loop

Audio Lab is the local workflow for rendering, listening, marking issues, and
creating repair drafts:

```powershell
python -m song_agent.cli audio-lab status --json
python -m song_agent.cli audio-lab smoke --cases 1 --render-audio required --json
python -m song_agent.cli audio-lab session create --from-smoke alsm-000001 --json
python -m song_agent.cli audio-lab session review als-000001 item-001 --result accepted --rating 4 --reviewer "Developer" --role "developer" --playback-confirmed --json
```

`--render-audio never` remains MIDI-only. A manual Audio Lab review only counts
as real audio evidence when it binds to a current WAV hash and records
`playback_confirmed=true`.
