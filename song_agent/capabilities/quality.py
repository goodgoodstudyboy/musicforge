from __future__ import annotations

from song_agent.capabilities.registry import CapabilitySpec, RuntimeVerificationSpec


QUALITY_CAPABILITIES = (
    CapabilitySpec(
        capability_id="quality.audio_certification",
        component_type="release_audio_certification",
        bounded_context="quality",
        application_service="release_audio_certification.verify",
        runtime=RuntimeVerificationSpec(
            module="song_agent.release_audio_certification_verifier",
            function="verify_release_audio_certification_package",
            package_type="release_audio_certification",
            verification_package_type="release_audio_certification_verification",
            defaults=(("strict", True), ("require_passed", True), ("require_signed", True), ("require_real_audio", True), ("require_manual_review", True)),
        ),
        gate_policies=("release.audio_strict", "ga.lts"),
        web_panel="Quality",
    ),
    CapabilitySpec(
        capability_id="quality.audio_timeline",
        component_type="release_audio_timeline",
        bounded_context="quality",
        application_service="release_audio_timeline.verify",
        runtime=RuntimeVerificationSpec(
            module="song_agent.release_audio_timeline_verifier",
            function="verify_release_audio_timeline_package",
            package_type="release_audio_timeline",
            verification_package_type="release_audio_timeline_verification",
            defaults=(("strict", True), ("require_passed", True), ("require_signed", True), ("require_real_audio", True), ("require_manual_review", True), ("require_current_certification", True)),
            proof_arguments=(
                ("certification_package", "release_audio_certification_path"),
                ("certification_verification_report", "release_audio_certification_verification_report_path"),
            ),
            required_proofs=("certification_package", "certification_verification_report"),
        ),
        gate_policies=("release.audio_strict", "ga.lts"),
        web_panel="Quality",
    ),
)
