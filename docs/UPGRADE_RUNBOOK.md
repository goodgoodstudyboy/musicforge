# Upgrade Runbook

Use this runbook before pulling code, switching tags, or running migrations.

## Preflight

```powershell
python -m song_agent.cli maintenance backup create --mode workspace --json
python -m song_agent.cli maintenance upgrade preflight --target-version 10.1.0 --require-verified-backup --json
```

Preflight checks version order, Git cleanliness, local config tracking,
verified backup availability, and migration state readability.

## Migration

```powershell
python -m song_agent.cli maintenance migration status --json
python -m song_agent.cli maintenance migration plan --json
python -m song_agent.cli maintenance migration run --json
```

Migrations are idempotent. v10.1 initializes maintenance state only; it does not
rewrite existing project, release, acceptance, or trust stores.

## Post-Upgrade

```powershell
python -m song_agent.cli doctor
python -m song_agent.cli maintenance status --json
python -m song_agent.cli release-check --profile latest --skip-tests --json
python -m song_agent.cli release-check --profile ga --skip-tests --json
```

If preflight or post-upgrade checks fail, stop and restore into a clean target
directory from the latest verified backup.
