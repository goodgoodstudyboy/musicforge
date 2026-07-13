from __future__ import annotations

from song_agent.platform.contracts.policy import EvidenceRequirement, PolicyProfile, QuorumRequirement


BUILTIN_POLICY_PROFILES: dict[str, PolicyProfile] = {
    "release.standard": PolicyProfile(
        policy_id="release.standard",
        description="Current runtime-verified Release evidence is required.",
        evidence_requirements=(EvidenceRequirement("release", component_types=("release",)),),
    ),
    "release.audio_strict": PolicyProfile(
        policy_id="release.audio_strict",
        description="Release and current human-reviewed audio evidence are required.",
        evidence_requirements=(
            EvidenceRequirement("release", component_types=("release",)),
            EvidenceRequirement("audio_certification", component_types=("release_audio_certification",)),
            EvidenceRequirement("audio_timeline", component_types=("release_audio_timeline",)),
        ),
    ),
    "distribution.standard": PolicyProfile(
        policy_id="distribution.standard",
        description="Current runtime-verified Distribution evidence is required.",
        evidence_requirements=(EvidenceRequirement("distribution", component_types=("distribution",)),),
    ),
    "ga.standard": PolicyProfile(
        policy_id="ga.standard",
        description="At least one current signed Program or Unified Command Center evidence root is required.",
        evidence_requirements=(
            EvidenceRequirement(
                "ga_root",
                component_types=(
                    "unified_release_program",
                    "unified_release_program_continuity_command_center_signoff",
                    "unified_release_program_receiver_acceptance",
                ),
            ),
        ),
    ),
    "ga.lts": PolicyProfile(
        policy_id="ga.lts",
        description="Continuity Command Center signoff and receiver acceptance are required for LTS.",
        evidence_requirements=(
            EvidenceRequirement(
                "continuity_signoff",
                component_types=("unified_release_program_continuity_command_center_signoff",),
            ),
            EvidenceRequirement(
                "receiver_acceptance",
                component_types=(
                    "unified_release_program_receiver_acceptance",
                    "unified_release_program_continuity_command_center_acceptance",
                ),
            ),
        ),
    ),
    "program.handoff": PolicyProfile(
        policy_id="program.handoff",
        description="A current signed and accepted Program Handoff is required.",
        evidence_requirements=(EvidenceRequirement("program_handoff", component_types=("unified_release_program_handoff",)),),
    ),
    "program.continuity": PolicyProfile(
        policy_id="program.continuity",
        description="Current continuity root, command center, and receiver acceptance evidence are required.",
        evidence_requirements=(
            EvidenceRequirement("continuity", component_types=("unified_release_program_continuity",)),
            EvidenceRequirement("continuity_command_center", component_types=("unified_release_program_continuity_command_center",)),
            EvidenceRequirement(
                "continuity_acceptance",
                component_types=(
                    "unified_release_program_continuity_acceptance",
                    "unified_release_program_receiver_acceptance",
                ),
            ),
        ),
        quorum_requirements=(QuorumRequirement("continuity_roots", minimum_count=3),),
    ),
}


def get_policy_profile(policy_id: str) -> PolicyProfile:
    try:
        return BUILTIN_POLICY_PROFILES[policy_id]
    except KeyError as exc:
        raise KeyError(f"Unknown policy profile: {policy_id}") from exc


def policy_profile_ids() -> tuple[str, ...]:
    return tuple(sorted(BUILTIN_POLICY_PROFILES))
