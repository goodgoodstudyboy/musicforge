# Maintenance Policy

MusicForge v10 is the GA/LTS baseline. Maintenance work should preserve stable
local operation before adding new proof-chain layers.

## Supported Work

- Security and verifier hardening.
- Installation, documentation, and Studio health improvements.
- Deterministic bug fixes.
- Test reliability and release-check profile improvements.
- Backward-compatible API and CLI fixes.

## Release Discipline

- Every release updates version metadata and `CHANGELOG.md`.
- Every release runs `doctor`, `release-check --profile ga`, and the targeted
  tests for the changed area.
- Hotfix releases must include a regression for the reproduced issue.
- Signed evidence and archives remain immutable unless reset through the
  established Change Request flow for that domain.

## Long-Term Checks

Run GA checks periodically:

```powershell
python -m song_agent.cli ga-check --json
python -m song_agent.cli release-check --profile ga --skip-tests --json
```

