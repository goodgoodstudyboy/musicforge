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
