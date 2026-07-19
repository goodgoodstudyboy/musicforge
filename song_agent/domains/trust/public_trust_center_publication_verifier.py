# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib as hashlib
import json as json
import os as os
import re as re
import struct as struct
import tempfile as tempfile
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package as verify_public_trust_center_acceptance_board_signoff_archive_package
from song_agent.domains.trust.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package as verify_public_trust_center_acceptance_board_package
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import acceptance_board_verification_hash as acceptance_board_verification_hash
from song_agent.domains.trust.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package as verify_public_trust_center_anchor_registry_package
from song_agent.domains.trust.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package as verify_public_trust_center_anchor_transparency_package
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import verification_hash as _accepted_evidence_verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.trust.public_trust_center_publication_contracts import PUBLICATION_BLOCKED_KEYS as PUBLICATION_BLOCKED_KEYS, PUBLICATION_PACKAGE_TYPE as PUBLICATION_PACKAGE_TYPE, PUBLICATION_REQUIRED_PACKAGE_KEYS as PUBLICATION_REQUIRED_PACKAGE_KEYS, PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE as PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE, publication_channel_state_hash as publication_channel_state_hash, publication_manifest_hash as publication_manifest_hash, publication_report_hash as publication_report_hash, sidecar_hash as sidecar_hash
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package as verify_public_trust_center_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash

PUBLICATION_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 512
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = PUBLICATION_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})
accepted_evidence_verification_hash = _accepted_evidence_verification_hash
BASE_REQUIRED_ENTRIES = {
    "README.txt",
    "publication-manifest.json",
    "publication-report.json",
    "package-index.json",
    "verification-index.json",
    "mirror-policy.json",
    "checksum/SHA256SUMS.txt",
    "checksum/SHA256SUMS.json",
    "site/index.html",
    "site/trust-center.html",
    "site/packages.html",
    "site/verification.html",
    "anchors/ptc-anchor-checkpoint-current.json",
    "anchors/public-trust-center.delivery-anchor.json",
}
FIXED_PACKAGE_PATHS = {
    "packages/public-trust-center.zip",
    "packages/public-trust-center-distribution-kit.zip",
    "packages/public-trust-center-anchor-registry.zip",
    "packages/public-trust-center-anchor-transparency.zip",
    "packages/public-trust-center-acceptance-board.zip",
    "packages/public-trust-center-acceptance-board-signoff-archive.zip",
}
FIXED_VERIFICATION_PATHS = {
    "verification-reports/public-trust-center-verification-report.json",
    "verification-reports/distribution-kit-verification-report.json",
    "verification-reports/anchor-registry-verification-report.json",
    "verification-reports/anchor-transparency-verification-report.json",
    "verification-reports/acceptance-board-verification-report.json",
    "verification-reports/acceptance-board-signoff-archive-verification-report.json",
}


def verify_public_trust_center_publication_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_ready: bool = False,
    require_acceptance_board_signoff: bool = False,
    require_anchor_current: bool = False,
    require_no_revoked: bool = False,
    publication_channel_state_path: Path | str | None = None,
    require_channel_state_zip_match: bool = True,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _PublicationVerifier(
        Path(zip_path),
        strict=strict,
        deep=deep,
        require_ready=require_ready,
        require_acceptance_board_signoff=require_acceptance_board_signoff,
        require_anchor_current=require_anchor_current,
        require_no_revoked=require_no_revoked,
        publication_channel_state_path=Path(publication_channel_state_path) if publication_channel_state_path else None,
        require_channel_state_zip_match=require_channel_state_zip_match,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def verify_public_trust_center_publication_mirror(
    mirror_dir: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_acceptance_board_signoff: bool = False,
    require_anchor_current: bool = False,
    require_no_revoked: bool = False,
    publication_channel_state_path: Path | str | None = None,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    mirror = Path(mirror_dir)
    tmp_zip: Path | None = None
    if not mirror.exists() or not mirror.is_dir() or mirror.is_symlink():
        return _failed_report("mirror", "ptcpub_mirror_open", "Publication mirror directory does not exist or is not a regular directory.", now=now)
    entries = _walk_files(mirror)
    if len(entries) > max_entry_count:
        return _failed_report("mirror", "ptcpub_mirror_entry_count", "Publication mirror has too many files.", now=now)
    try:
        with tempfile.TemporaryDirectory(prefix="mf-ptc-pub-mirror-") as tmp:
            tmp_zip = Path(tmp) / "mirror.zip"
            with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in entries:
                    with open(_fs_path(path), "rb") as handle:
                        archive.writestr(path.relative_to(mirror).as_posix(), handle.read())
            report = verify_public_trust_center_publication_package(
                tmp_zip,
                strict=strict,
                deep=False,
                require_ready=require_ready,
                require_acceptance_board_signoff=require_acceptance_board_signoff,
                require_anchor_current=require_anchor_current,
                require_no_revoked=require_no_revoked,
                publication_channel_state_path=publication_channel_state_path,
                require_channel_state_zip_match=False,
                now=now,
            )
            report["package_kind"] = "public_trust_center_publication_mirror"
            report["mirror_root"] = mirror.name
            return report
    finally:
        if tmp_zip is not None and tmp_zip.exists():
            tmp_zip.unlink(missing_ok=True)


def write_public_trust_center_publication_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_publication_verification_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Public Trust Center Publication verification")
    print(f"status: {report.get('status')}")
    print(f"publication: {summary.get('publication_id') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")


def public_trust_center_publication_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


from song_agent.domains.trust import v142_ptcpv_readiness as _v142_ptcpv_readiness
from song_agent.domains.trust.v142_ptcpv_readiness import (
    _PublicationVerifier,
    _failed_report,
    _expected_entries,
    _expected_package_index,
    _strip_integrity_list,
    _is_safe_entry,
    _is_forbidden_entry,
    _sha256_file,
)
from song_agent.domains.trust import v142_ptcpv_evidence as _v142_ptcpv_evidence
from song_agent.domains.trust.v142_ptcpv_evidence import (
    _sha256_entry,
    _verification_hash,
    _read_zip_json,
    _read_json_file,
    _counts,
    _redaction_findings,
    _blocked_key_findings,
    _walk_files,
    _fs_path,
    _from_fs_path,
)

_v142_ptcpv_readiness.bind_globals(globals())
_v142_ptcpv_evidence.bind_globals(globals())
