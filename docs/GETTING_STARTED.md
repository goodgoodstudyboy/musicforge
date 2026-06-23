# Getting Started

This guide gets MusicForge running on a clean Windows development machine.

## Requirements

- Python 3.11 or newer.
- Git.
- PowerShell.
- Optional for real WAV output: a local renderer profile and SoundFont.
- Optional for provider-assisted features: a local provider config.

The default generation path is deterministic and can create MIDI without a
network provider.

## Clone

```powershell
git clone https://github.com/goodgoodstudyboy/musicforge.git
cd musicforge
git remote -v
```

Use an HTTPS remote that includes the GitHub user name if credential selection
is confusing:

```powershell
git remote set-url origin https://goodgoodstudyboy@github.com/goodgoodstudyboy/musicforge.git
```

Do not put tokens in the remote URL.

## Install

```powershell
python -m pip install -e .[dev]
```

## Start Studio

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`.

## Generate A Song

```powershell
python -m song_agent.cli examples\song_request.json --out runs\quickstart --force
```

The run writes request data, a SongPlan, events, and `song.mid` under `runs/`.

## Health Checks

```powershell
python -m song_agent.cli doctor
python -m song_agent.cli release-check --profile quick --skip-tests --json
python -m song_agent.cli ga-check --json
```

`doctor` should pass before normal development. `ga-check` may warn when manual
listening review, real audio, or final handoff evidence is not present; those
warnings become blocking only when the related strict flags are enabled.

