# Changelog

This file contains the current v13 major line. Earlier history is preserved in
[`docs/changelog/CHANGELOG-v0-v13.6.md`](docs/changelog/CHANGELOG-v0-v13.6.md).

## v13.8.0 - 2026-07-15

- Added final LTS recertification gates for zero open structural P1 blockers,
  zero Program compatibility imports, active-only current profiles, non-empty
  migration, and byte-identical rollback.
- Made source comparison report total, active, and compatibility code
  separately; the active modular source is the v12.13 reduction gate while the
  supported v13 compatibility surface remains visible and hard-ratcheted.
- Strengthened the final reviewer package to independently verify architecture,
  Program imports, active source reduction, final SHA, CI attestations, all
  release profiles, active/legacy suites, migration, performance, and release
  alignment evidence.
- Moved run-state contracts into `platform/contracts`, reducing active
  compatibility edges from 225 to 224 without breaking `song_agent.state`.
- Hardened Program atomic writes and pytest temp ownership for deep Windows
  paths, concurrent xdist runs, timeout recovery, and PID reuse.
- Removed absolute ZIP paths from public verification summaries, hardened
  POSIX path redaction, and stabilized hosted legacy smoke requests under
  parallel Linux CI load.

## v13.7.0 - 2026-07-15

- Made release-check callable provenance explicit and prohibited legacy
  callables in `latest`, `ga`, `v13`, and `security`; full/nightly compatibility
  checks remain labeled and isolated.
- Replaced inferred pytest ownership with a checked-in marker manifest and
  fail-closed collection for unregistered test modules.
- Added final-SHA quality/nightly CI, active/compatibility coverage policy,
  migration rehearsal, manual full-LTS workflow, and a verifier for the final
  reviewer package.
- Reduced the root README below 300 lines, archived the prior long-form guide,
  retained only the current major changelog, and added machine-readable docs
  and planning-material indexes.
- Removed the expired `song_agent.release_checks` facade and migrated a quality
  component into its bounded context, continuing the compatibility ratchet.

## v13.6.0 - 2026-07-15

- Made Evidence Graph policy evaluation authoritative for GA readiness,
  Release signoff, and Program gates while retaining non-authoritative legacy
  summaries for compatibility audits.
- Added canonical Release and Program policies, current runtime identity checks,
  and complete capability metadata.
- Consolidated redaction into the Verification Kernel and reduced active
  compatibility imports from 227 to 226.

## v13.5.0 - 2026-07-15

- Replaced runtime route discovery with a fixed route manifest and split CLI,
  API, Program HTTP, and Studio browser entrypoints into bounded modules.
- Centralized remaining compatibility imports behind application adapters and
  reduced active compatibility edges from 407 to 227.

## v13.4.0 - 2026-07-15

- Moved active Unified Release Program stores and verifiers into the Program
  bounded context with typed application services and explicit interfaces.
- Removed compatibility imports from the Program core and reduced repository
  compatibility edges from 494 to 407.

## v13.3.0 - 2026-07-14

- Made `ProgramStateRepository` the write authority for active Program stores,
  added recoverable projection transactions, and verified non-empty workspace
  migration with byte-identical rollback.
- Reduced active compatibility imports from 520 to 494.

## v13.2.0 - 2026-07-14

- Registered active Program verifiers and lifecycle stores with shared kernels
  and added differential attack corpora.
- Moved version authority to `platform.version` and reduced active
  compatibility imports from 521 to 520.

## v13.1.0 - 2026-07-14

- Added immutable architecture baselines, previous-release ratchets, debt
  ownership, interface no-growth limits, and adversarial architecture tests.
- Reduced active compatibility imports from 522 to 521.

## v13.0.2 - 2026-07-14

- Fixed Python 3.11 static type narrowing for manifest size validation.

## v13.0.1 - 2026-07-14

- Hardened shared ZIP/package verification, Evidence Graph runtime identity,
  and Change Request reset authorization.

## v13.0.0 - 2026-07-13

- Introduced the modular-monolith platform/application/domain/interface layout,
  shared Verification/Lifecycle/Persistence/Policy kernels, architecture gates,
  v13 migration evidence, and reviewer package generation.
