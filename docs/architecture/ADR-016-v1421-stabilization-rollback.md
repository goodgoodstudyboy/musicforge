# ADR-016: v14.2.1 Stabilization Rollback

Status: Accepted

Date: 2026-07-20

## Context

The published v14.2.0 implementation attempted to satisfy TYPE-003 and
ARCH-014 by generating 234 `v142_*.py` modules and rewriting production
modules around runtime global binding. Those generated modules were excluded
from mypy, carried file-wide static-analysis suppressions, and did not have
independent domain responsibilities. The release artifacts and CI run were
authentic, but the implementation did not satisfy the v14.2 architecture
acceptance criteria.

The public v14.2.0 tag and Release remain immutable historical records. They
must not be described as the recommended stable baseline.

## Decision

v14.2.1 is a stabilization rollback, not a claim that the original v14.2 debt
targets were completed.

- Restore the production structure from the reviewed v14.1.2 baseline.
- Remove all generated `v142_*.py` modules and the mechanical splitter.
- Remove the mypy exclusion and every file-wide suppression introduced by the
  generated split.
- Prohibit `bind_globals(globals())` in the active tree.
- Preserve the useful Explicit Any collector work, upgrade it to schema 4,
  and count function-local annotations, nested functions, methods, scoped
  imports, aliases, module aliases, quoted annotations, and `TYPE_CHECKING`
  aliases.
- Add `v1421.stabilization_rollback_smoke` to every v14 release profile.
- Bind the recovery ceilings in production code and in
  `architecture-v14-quality.json`; the updater may lower them but cannot
  silently raise them.
- Bind the complete per-file Explicit Any budget map and module-size ceiling
  map to code-reviewed hashes so an internally re-signed policy cannot
  reallocate debt between files.

## Recovery Ceilings

Schema 4 measures the restored active tree as follows:

| Metric | v14.2.1 ceiling |
|---|---:|
| Active Python files | 700 |
| Explicit Any | 12,040 |
| Files containing Explicit Any | 470 |
| `dict[str, Any]` | 5,605 |
| `ImplementationDocument` | 7,118 |
| Oversized modules | 137 |
| Modules over 1,000 lines | 37 |
| Largest module | 2,226 lines |
| Total oversized-module lines | 124,043 |

Layer ceilings are stored in the quality policy and mirrored by the hard
release gate. They are recovery ceilings, not the original v14.2 completion
targets.

## Debt Status

ARCH-014 and TYPE-003 remain open through v14.3.0. This ADR reapproves only the
restored, measured v14.1.2 architecture under stricter collector semantics. A
future cleanup must use responsibility-oriented modules, direct imports,
typed contracts, and differential behavior tests. Mechanical extraction,
runtime global injection, mypy exclusions, and file-wide suppressions are not
approved migration techniques.

## Release Evidence

v14.2.1 requires all of the following on the final commit:

- repository-wide Ruff;
- full active-tree mypy with no exclusion for generated files;
- full active pytest;
- v14, latest, security, GA, and full release-check profiles;
- final-SHA Quality and Nightly LTS workflows;
- a reviewer package with checksum and verification JSON.

Missing final-SHA evidence blocks stable-baseline approval even when the code
and tag have already been published.

## Consequences

The hotfix increases the measured type and module debt relative to v14.2.0
because it removes an invalid accounting shortcut. Product behavior and
persistent evidence formats return to the v14.1.2 implementation. No data
migration is required.
