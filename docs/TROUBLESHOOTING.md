# Troubleshooting

## GitHub HTTPS Fails

Check the remote and avoid token-bearing URLs:

```powershell
git remote -v
git ls-remote origin HEAD
```

If one GitHub front-end IP is unreachable, a one-time `http.curloptResolve`
override can be used for that command. Keep the configured remote unchanged.

## Studio Does Not Start

```powershell
python -m song_agent.cli doctor
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

If the port is busy, pick another local port.

## Renderer Missing

MIDI generation can still work without a renderer. Real WAV checks require a
renderer profile and SoundFont. Do not mark audio release readiness until WAV
rendering and audio health are current.

## Provider Missing

Provider features are optional. The deterministic local path should still work.
Use mock provider configuration only for tests and smoke checks.

## Windows Path Issues

Use PowerShell paths in commands and avoid copying local absolute paths into
docs, manifests, or public evidence packages.

