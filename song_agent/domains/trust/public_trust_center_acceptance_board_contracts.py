from __future__ import annotations

from song_agent.platform.contracts import DomainDocument

from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import ACCEPTANCE_BLOCKED_KEYS
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


ACCEPTANCE_BOARD_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board"


ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_report"


ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_conflict_report"


ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_signoff"


ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_signoff_archive"


ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_signoff_archive_report"


ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS = {"integrity_hash"}


ACCEPTANCE_BOARD_BLOCKED_KEYS = ACCEPTANCE_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"})


SIGNOFF_ARCHIVE_ENTRIES = {
    "board-signoff-archive-manifest.json",
    "board-signoff-archive-report.json",
    "board-signoff.json",
    "board-verification-summary.json",
    "board-fingerprint-summary.json",
    "quorum-fingerprint-summary.json",
    "accepted-evidence-fingerprint-index.json",
    "accepted-evidence-verification-index.json",
    "distribution-kit-fingerprint-summary.json",
    "change-request-summary.json",
    "chain-of-custody.json",
    "README.txt",
    "VERIFY.txt",
}


def acceptance_board_policy_hash(policy: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (policy or {}).items() if key not in ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS})


def acceptance_board_report_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS})


def acceptance_board_conflict_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS})


def acceptance_board_manifest_hash(manifest: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS})


def acceptance_board_signoff_hash(signoff: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (signoff or {}).items() if key not in ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS})


def acceptance_board_signoff_archive_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (payload or {}).items() if key not in ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS})


def acceptance_board_verification_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})


def sidecar_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (payload or {}).items() if key not in ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS})
