from __future__ import annotations

from song_agent.platform.contracts import DomainDocument

from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_SCHEMA_VERSION = 1


TRUST_OPERATIONS_HUB_PACKAGE_TYPE = "musicforge_trust_operations_hub"


TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE = "musicforge_trust_operations_hub_signoff"


TRUST_OPERATIONS_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


HUB_EXPORT_ENTRIES = {
    "README.txt",
    "trust-operations-hub-manifest.json",
    "hub-report.json",
    "readiness-matrix.json",
    "blocker-register.json",
    "manual-action-queue.json",
    "evidence-binding-index.json",
    "verification-summary-index.json",
    "source-state.json",
    "delivery-evidence-index.json",
    "delivery-readiness-matrix.json",
    "delivery-blocker-register.json",
    "delivery-manual-action-queue.json",
    "signoff-summary.json",
    "checksum/SHA256SUMS.json",
    "checksum/SHA256SUMS.txt",
}


DELIVERY_VERIFICATION_COMPONENTS = (
    {
        "component_type": "release_verification",
        "component_id_prefix": "release",
        "requirement": "release_verified",
        "payload_key": "release_verification_path",
        "payload_keys": "release_verification_paths",
    },
    {
        "component_type": "distribution_verification",
        "component_id_prefix": "distribution",
        "requirement": "distribution_verified",
        "payload_key": "distribution_verification_path",
        "payload_keys": "distribution_verification_paths",
    },
    {
        "component_type": "submission_verification",
        "component_id_prefix": "submission",
        "requirement": "submission_verified",
        "payload_key": "submission_verification_path",
        "payload_keys": "submission_verification_paths",
    },
    {
        "component_type": "submission_evidence_verification",
        "component_id_prefix": "submission-evidence",
        "requirement": "submission_evidence_verified",
        "payload_key": "submission_evidence_verification_path",
        "payload_keys": "submission_evidence_verification_paths",
    },
    {
        "component_type": "release_operations_verification",
        "component_id_prefix": "release-operations",
        "requirement": "release_operations_verified",
        "payload_key": "release_operations_verification_path",
        "payload_keys": "release_operations_verification_paths",
    },
)


def hub_hash(doc: DomainDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_HASH_EXCLUDE_KEYS})


def hub_manifest_hash(manifest: DomainDocument) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})
