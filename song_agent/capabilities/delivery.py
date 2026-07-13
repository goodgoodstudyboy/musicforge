from __future__ import annotations

from song_agent.capabilities.model import CapabilitySpec, RuntimeVerificationSpec


def _spec(
    capability_id: str,
    component_type: str,
    module: str,
    function: str,
    package_type: str,
    verification_package_type: str,
    defaults: tuple[tuple[str, object], ...],
) -> CapabilitySpec:
    return CapabilitySpec(
        capability_id=capability_id,
        component_type=component_type,
        bounded_context="delivery",
        application_service=f"{capability_id}.verify",
        runtime=RuntimeVerificationSpec(
            module=module,
            function=function,
            package_type=package_type,
            verification_package_type=verification_package_type,
            defaults=defaults,
        ),
        gate_policies=("release.standard", "distribution.standard", "ga.standard", "ga.lts"),
        web_panel="Delivery",
    )


DELIVERY_CAPABILITIES = (
    _spec(
        "release.package",
        "release",
        "song_agent.release_verifier",
        "verify_release_zip",
        "musicforge_release",
        "musicforge_release_verification",
        (("strict", True),),
    ),
    _spec(
        "distribution.package",
        "distribution",
        "song_agent.distribution_verifier",
        "verify_distribution_package",
        "musicforge_distribution_package",
        "musicforge_distribution_verification",
        (("strict", True),),
    ),
    _spec(
        "submission.package",
        "submission",
        "song_agent.submission_verifier",
        "verify_submission_package",
        "musicforge_submission_package",
        "musicforge_submission_verification",
        (("strict", True), ("deep", True)),
    ),
    _spec(
        "release.operations",
        "release_operations",
        "song_agent.release_operations_verifier",
        "verify_release_operations_package",
        "musicforge_release_operations",
        "musicforge_release_operations_verification",
        (("strict", True),),
    ),
)
