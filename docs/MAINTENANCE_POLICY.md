# Maintenance Policy

MusicForge v14.0 is the supported LTS baseline. The domain cutover and active
compatibility retirement are complete; maintenance work must preserve v13.8
public contracts and the v14 architecture, migration, and security ratchets.

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
- Architecture maintenance must preserve zero active compatibility edges and
  may only reduce registered module-size/type debt. Changing ownership labels
  or baseline allowances is not a migration.

## Long-Term Checks

Run GA checks periodically:

```powershell
python -m song_agent.cli ga-check --json
python -m song_agent.cli release-check --profile ga --skip-tests --json
```

## LTS Maintenance Center

Use the Maintenance Center for local backup, upgrade, migration, and periodic
review:

```powershell
python -m song_agent.cli maintenance status --json
python -m song_agent.cli maintenance check run --profile daily --json
python -m song_agent.cli maintenance check run --profile weekly --json
```

Profiles:

- `daily`: status, Git, ignored config, and backup freshness.
- `weekly`: daily checks plus a verified workspace backup.
- `release`: weekly checks plus upgrade preflight with a verified backup.
- `emergency`: doctor-grade smoke for hotfix triage.

Never commit `.musicforge/provider.json`, `.musicforge/renderer.json`, generated
maintenance backups, or restore targets.
