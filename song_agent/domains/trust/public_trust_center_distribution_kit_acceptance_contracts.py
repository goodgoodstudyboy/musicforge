from __future__ import annotations

from song_agent.platform.contracts import DomainDocument

from song_agent.domains.trust.public_trust_center_distribution_kit_contracts import DISTRIBUTION_KIT_BLOCKED_KEYS
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


ACCEPTED_EVIDENCE_PACKAGE_TYPE = "musicforge_public_trust_center_distribution_kit_accepted_evidence"


ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_distribution_kit_accepted_evidence_report"


ACCEPTANCE_BLOCKED_KEYS = DISTRIBUTION_KIT_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"})


ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


def accepted_evidence_hash(evidence: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (evidence or {}).items() if key not in ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS})


def accepted_evidence_manifest_hash(manifest: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS})


def verification_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})
