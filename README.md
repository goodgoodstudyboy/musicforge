# MusicForge

MusicForge is a local-first music generation, review, release, and trust
operations workspace. The v14 line is a modular monolith: production use cases
are organized under `platform`, `application`, `domains`, `capabilities`, and
`interfaces`. Active code has no dependency on the retained static compatibility
facades; historical evidence remains readable and auditable.

## Install

MusicForge requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m song_agent.cli doctor
```

On POSIX shells:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m song_agent.cli doctor
```

## Start Studio

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Provider and renderer credentials remain in
ignored `.musicforge/` configuration files. Never commit those files.

## Core Workflow

1. Configure a provider and a real audio renderer.
2. Create or open a project and generate a song plan.
3. Render and review real WAV output in Audio Lab.
4. Resolve `needs_fix` work through Audio Fix Sprint and recheck.
5. Build Release Audio Certification and its current Timeline.
6. Run release, Program, continuity, and policy gates required by the release.
7. Sign only after runtime verification reports the current evidence as ready.

Synthetic/test audio is never release-ready and cannot replace manual
listening acceptance.

## Quality Gates

v14.1 checks the complete active modular-monolith tree with mypy and checks the
entire repository with Ruff. v14.2.1 restores the reviewed v14.1.2 production
structure after the rejected generated split in v14.2.0, and upgrades Explicit
`Any` counting to include function-local and nested-scope annotations. ADR-016
keeps ARCH-014 and TYPE-003 open under immutable recovery ceilings; v14.2.1
does not claim that the original v14.2 cleanup targets were completed.

```powershell
python -m mypy --no-incremental
python -m ruff check song_agent tests tools
python -m pytest tests/test_v14_quality_ratchets.py -q
```

## Common Commands

```powershell
python -m song_agent.cli --help
python -m song_agent.cli doctor
python -m song_agent.cli release-check --profile v14 --skip-tests --json
python -m song_agent.cli release-check --profile security --skip-tests --json
python -m song_agent.cli release-check --profile latest --skip-tests --json
python -m song_agent.cli release-check --profile ga --skip-tests --json
```

State maintenance:

```powershell
song-agent-state --workspace .musicforge v13-plan
song-agent-state --workspace .musicforge v13-apply
song-agent-state --workspace .musicforge v13-rollback-rehearsal
song-agent-state --workspace .musicforge v14-plan
song-agent-state --workspace .musicforge v14-rollback-rehearsal
song-agent-state --workspace .musicforge v14-apply
```

## Release Checks

Current LTS profiles (`latest`, `ga`, `v14`, and `security`) resolve only active
callables. Historical smoke implementations are labeled `legacy` and run only
in the explicit full/nightly compatibility suites or their historical major
profile.

```powershell
python -m song_agent.cli release-check --profile v14 --skip-tests --json
python -m song_agent.cli release-check --profile full --skip-tests --json
python -m pytest -m "not legacy"
python -m pytest -m "legacy"
```

Final LTS certification also requires `full`, active/legacy test attestations,
non-empty rollback evidence, performance evidence, release alignment, and
quality/nightly evidence all bound to the final commit. Build the reviewer
package only after those reports exist:

```powershell
python tools/build_v14_final_reviewer_package.py --evidence-dir runs/v14-evidence --output runs/v14-reviewer
python tools/verify_v14_reviewer_package.py runs/v14-reviewer --expected-sha (git rev-parse HEAD) --require-final
```

Every test module has an explicit primary owner in
`tests/marker-manifest.json`. Update and review the manifest when adding tests:

```powershell
python tools/update_test_marker_manifest.py
python tools/update_test_marker_manifest.py --check
```

## Architecture

Production dependencies point inward:

```text
interfaces -> application -> domains -> platform
                         -> capabilities
```

The architecture gate rejects production cycles, domain-to-interface imports,
dynamic internal imports, compatibility growth, and oversized new active
modules/functions. See:

- [Architecture](docs/ARCHITECTURE.md)
- [Current architecture](docs/architecture/CURRENT.md)
- [Architecture review runbook](docs/ARCHITECTURE_REVIEW_RUNBOOK.md)
- [Architecture debt](docs/architecture/DEBT.md)
- [Evidence graph and policies](docs/EVIDENCE_GRAPH_AND_POLICIES.md)

## Security Model

Package verification, ZIP safety, external evidence binding, immutable
signoff, reset authorization, and event-chain validation are shared platform
responsibilities. Current gates runtime-verify evidence; a stored `passed`
report is not sufficient after the source package changes.

- [Security and secrets](docs/SECURITY_AND_SECRETS.md)
- [Release runbook](docs/RELEASE_RUNBOOK.md)
- [Data migration runbook](docs/DATA_MIGRATION_RUNBOOK.md)
- [Backup and restore](docs/BACKUP_RESTORE_RUNBOOK.md)

## Documentation

- [Getting started](docs/GETTING_STARTED.md)
- [Music review guide](docs/MUSIC_REVIEW_GUIDE.md)
- [Local acceptance runbook](docs/LOCAL_ACCEPTANCE_RUNBOOK.md)
- [Maintenance policy](docs/MAINTENANCE_POLICY.md)
- [Upgrade runbook](docs/UPGRADE_RUNBOOK.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Command reference](docs/commands/README.md)
- [Documentation index](docs/INDEX.md)
- [Planning material index](material/README.md)
- [Changelog](CHANGELOG.md)

The pre-v13.7 long-form README is retained under
`docs/archive/README-v13.6.md` for historical lookup. It is not the current
operational contract. The v13 major changelog is archived under
`docs/changelog/CHANGELOG-v13.0-v13.8.md`.

## Repository Layout

```text
song_agent/platform/       shared verification, lifecycle, persistence, policy
song_agent/application/    use-case orchestration and compatibility adapters
song_agent/domains/        bounded business contexts
song_agent/capabilities/   product capability metadata
song_agent/interfaces/     CLI, HTTP API, and Studio adapters
song_agent/release_check/  release matrix, runner, checks, and LTS audit
tests/                     active and explicitly marked compatibility tests
docs/                      current product and engineering documentation
material/                  historical implementation plans and audit inputs
```

## License And Contributions

Keep changes scoped, preserve external contracts unless a migration is
provided, add tests appropriate to the risk, and run the relevant release profiles.
Do not weaken verification or classify production dependencies as
compatibility merely to satisfy a metric.
