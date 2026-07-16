# Data Migration Runbook

1. Run `maintenance backup create` and verify the resulting backup.
2. Run the migration with `--dry-run`; archive its compatibility report.
3. Confirm the target schema and required free disk space.
4. Execute under the workspace lock and atomic transaction boundary.
5. Run `doctor`, active package runtime verification, and policy gates.
6. Rehearse rollback into an isolated directory and verify restored hashes.
7. Archive the backup, migration report, post-check report, and rollback report.

An unverified backup is a hard blocker. Migration tools must not mutate a
production workspace when backup verification, locking, or schema preflight
fails.

## v13 LTS Cutover

```powershell
song-agent-state --workspace .musicforge v13-plan
song-agent-state --workspace .musicforge v13-rollback-rehearsal
song-agent-state --workspace .musicforge v13-apply
python -m song_agent.cli doctor
python -m song_agent.cli release-check --profile v13 --skip-tests --json
```

`v13-apply` initializes schema 2, delegates legacy indexing through the verified
backup migrator, preserves every source byte, and writes a post-migration
report. Release engineering additionally builds and verifies a migration
evidence ZIP containing the plan, report, and isolated rollback rehearsal. A
ZIP-external `*.anchor.json` is frozen when the archive is built and binds the
migration/source/target plus final ZIP and manifest fingerprints. Final LTS
verification requires this anchor, so an internally re-signed archive cannot
replace the migration facts.

## v14 Domain Cutover

```powershell
song-agent-state --workspace .musicforge v14-plan
song-agent-state --workspace .musicforge v14-rollback-rehearsal
song-agent-state --workspace .musicforge v14-apply
python -m song_agent.cli doctor
python -m song_agent.cli release-check --profile v14 --skip-tests --json
```

The v14 migrator adopts mutable indexes under a workspace lock and SQLite
transaction. Before apply it fingerprints source files, signed/history/binding
artifacts, and current pointers; it writes a verified backup and a prepared
intent. A successful apply writes a bound migration report and commit marker.
Rollback requires those three integrity-protected documents and restores the
logical mutable index while source evidence remains byte-identical. Never delete
an incomplete intent or fabricate a commit marker; recover from the verified
backup and retain the migration directory for audit.
