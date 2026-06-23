# Backup Restore Runbook

MusicForge LTS backups protect local `.musicforge/` business state. They are for
local recovery, not public trust evidence.

## Create

```powershell
python -m song_agent.cli maintenance backup create --mode workspace --json
```

`workspace` is the default mode. It backs up project, release, acceptance, trust,
and maintenance metadata while excluding local secrets and machine-specific
configuration.

Excluded by design:

- `.musicforge/provider.json`
- `.musicforge/renderer.json`
- token or key-like files
- provider snapshots
- recursive maintenance backup directories

## Verify

```powershell
python -m song_agent.cli maintenance backup verify --backup-id mb-000001 --json
python -m song_agent.cli verify-maintenance-backup .musicforge\maintenance\backups\mb-000001\musicforge-maintenance-backup.zip --json
```

The verifier checks ZIP path safety, duplicate entries, manifest spoofing, file
hashes, forbidden local config, redaction, entry count, and size limits.

## Restore Plan

```powershell
python -m song_agent.cli maintenance backup restore-plan --backup-id mb-000001 --target C:\tmp\musicforge-restore --json
```

Restore plan is dry-run only. It lists files that would be written under the
target `.musicforge/` and reminds the operator to recreate provider and renderer
local config manually.

## Restore

```powershell
python -m song_agent.cli maintenance backup restore --backup-id mb-000001 --target C:\tmp\musicforge-restore --confirm --json
```

Restore refuses unsafe paths and non-empty targets by default. Do not restore
into the current workspace unless explicitly intended and reviewed.
