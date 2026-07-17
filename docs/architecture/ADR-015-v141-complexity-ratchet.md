# ADR-015: v14.1 Module Complexity Ratchet

Status: Accepted

Date: 2026-07-17

## Context

v14.0 completed bounded-context ownership, dependency direction, and
compatibility retirement, but it did not split every large domain module. The
v14.0 quality policy registered 137 modules above 600 lines, including 37
modules above 1000 lines. Treating that inventory as closed would make the
architecture report misleading; attempting 137 unrelated extractions in one
hot release would make behavioral review unreliable.

v14.1 closes the active-tree typing debt and repository-wide Ruff debt. During
that work the registered oversized modules decreased from 124,211 aggregate
lines to 124,043 lines without adding an oversized module or oversized
function.

## Decision

ARCH-014 remains open and moves to v14.2.0. This is an explicit reapproval, not
a declaration that complexity debt is gone. `architecture-v14-quality.json`
is the machine-enforced authority and now applies all of these limits:

- no more than 137 modules may exceed 600 lines;
- no more than 37 modules may exceed 1000 lines;
- the largest module may not exceed 2,226 lines;
- aggregate lines across oversized modules may not exceed 124,043;
- each registered module retains an individual no-growth ceiling;
- no unregistered oversized module or oversized function is allowed.

v14.1.1 adds the missing machine check for that individual ceiling. The
quality policy updater must reject any registered module whose current line
count is above its previous `max_lines`, even if another module shrinks enough
to reduce the aggregate oversized-line total.

The initial v14.1.0 aggregate reduction included these one-time per-file
ceiling increases relative to v14.0.1. They are accepted as reviewed migration
fallout, not as precedent for future rebasing:

| Path | v14.0.1 | v14.1.x |
|---|---:|---:|
| `song_agent/domains/creation/agent/multinode_pipeline.py` | 908 | 909 |
| `song_agent/domains/creation/encoded_audio_acceptance.py` | 1105 | 1107 |
| `song_agent/domains/delivery/format_decisions.py` | 1009 | 1011 |
| `song_agent/domains/delivery/release_export.py` | 685 | 687 |
| `song_agent/domains/program/unified_command_center.py` | 823 | 825 |
| `song_agent/domains/program/unified_command_center_verifier.py` | 920 | 922 |
| `song_agent/domains/quality/acceptance_fix_plan_reviews.py` | 811 | 813 |
| `song_agent/domains/quality/acceptance_kb.py` | 759 | 761 |
| `song_agent/domains/quality/audio_encoding.py` | 895 | 897 |
| `song_agent/domains/quality/audio_lab.py` | 1021 | 1023 |
| `song_agent/domains/quality/audio_revision.py` | 1523 | 1525 |
| `song_agent/domains/quality/mastering_qa.py` | 1038 | 1041 |
| `song_agent/domains/quality/music_acceptance.py` | 1407 | 1410 |
| `song_agent/domains/quality/release_audio_command_center.py` | 735 | 737 |
| `song_agent/domains/quality/release_audio_quality_action_signoff.py` | 702 | 704 |
| `song_agent/domains/quality/release_audio_regression_verifier.py` | 743 | 744 |
| `song_agent/domains/quality/release_audio_timeline.py` | 796 | 798 |
| `song_agent/domains/quality/review_sprint_metrics.py` | 1002 | 1003 |
| `song_agent/domains/studio/song_editor.py` | 1633 | 1638 |
| `song_agent/domains/trust/ga_readiness.py` | 2123 | 2130 |
| `song_agent/domains/trust/ga_readiness_verifier.py` | 2218 | 2226 |
| `song_agent/domains/trust/public_trust_center_acceptance_board.py` | 1370 | 1372 |
| `song_agent/domains/trust/public_trust_center_distribution_kit_acceptance.py` | 864 | 866 |
| `song_agent/domains/trust/release_portfolio_audit.py` | 930 | 932 |
| `song_agent/domains/trust/release_portfolio_governance.py` | 1003 | 1005 |
| `song_agent/domains/trust/release_portfolio_governance_attestation.py` | 637 | 639 |
| `song_agent/domains/trust/trust_operations_assurance_watch.py` | 851 | 852 |
| `song_agent/domains/trust/trust_operations_continuous_assurance.py` | 775 | 781 |
| `song_agent/domains/trust/trust_operations_control_signoff.py` | 757 | 759 |
| `song_agent/domains/trust/trust_operations_final_readiness.py` | 876 | 882 |
| `song_agent/domains/trust/trust_operations_hub_incidents.py` | 1170 | 1171 |

The next extraction work must proceed by bounded context with behavior and
contract tests. A module may leave the debt register only by reaching 600 lines
or fewer. The policy cannot be relaxed by editing the JSON alone: this ADR is
required by the quality verifier and any later reapproval requires a new ADR.

## Consequences

v14.1 may be described as closing TYPE-002 and full-repository lint debt while
reducing and hardening ARCH-014. It must not be described as eliminating all
module complexity debt. New business work remains subordinate to the v14.2
extraction milestone.
