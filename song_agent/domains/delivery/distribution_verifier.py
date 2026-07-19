# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import csv as csv
import hashlib as hashlib
import io as io
import json as json
import re as re
import struct as struct
import sys as sys
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution_export import DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS as DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS
from song_agent.domains.delivery.distribution_layout import RESERVED_LAYOUT_PATHS as RESERVED_LAYOUT_PATHS, effective_file_naming as effective_file_naming, layout_payload_hash as layout_payload_hash, validate_layout_path as validate_layout_path
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_checklist import checklist_payload_hash as checklist_payload_hash, checklist_summary as checklist_summary
from song_agent.domains.delivery.distribution_templates import DistributionTemplateError as DistributionTemplateError, template_content_hash as template_content_hash, template_summary as template_summary, validate_template_pack as validate_template_pack
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.quality.audio_encoding import detect_audio_format_bytes as detect_audio_format_bytes, encoded_manifest_integrity_ok as encoded_manifest_integrity_ok, encoded_audio_summary_integrity_ok as encoded_audio_summary_integrity_ok, encoded_audio_summary_uses_fake as encoded_audio_summary_uses_fake, encoded_manifest_uses_fake as encoded_manifest_uses_fake
from song_agent.domains.creation.encoded_audio_acceptance import encoded_audio_acceptance_summary_hash as encoded_audio_acceptance_summary_hash, encoded_audio_acceptance_summary_integrity_ok as encoded_audio_acceptance_summary_integrity_ok, encoded_audio_review_integrity_hash as encoded_audio_review_integrity_hash, encoded_audio_review_integrity_ok as encoded_audio_review_integrity_ok
from song_agent.domains.delivery.format_decisions import distribution_target_format_decision_coverage as distribution_target_format_decision_coverage, format_distribution_decision_summary_integrity_ok as format_distribution_decision_summary_integrity_ok
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.rights_clearance import verify_rights_summary_evidence as verify_rights_summary_evidence
from song_agent.domains.delivery.v142_dv_readiness import _DistributionPackageVerifierReadinessMixin
from song_agent.domains.delivery import v142_dv_readiness as _v142_dv_readiness
from song_agent.domains.delivery.v142_dv_evidence import _DistributionPackageVerifierEvidenceMixin
from song_agent.domains.delivery import v142_dv_evidence as _v142_dv_evidence



DISTRIBUTION_VERIFICATION_SCHEMA_VERSION = 1
DISTRIBUTION_VERIFICATION_PACKAGE_TYPE = "musicforge_distribution_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json", "package.json", "release.json", "tracklist.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"distribution-manifest.json", "distribution-signoff.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def verify_distribution_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_audio: bool = False,
    require_artwork: bool = False,
    require_encoded_audio: bool = False,
    require_encoded_audio_review: bool = False,
    require_format_decision: bool = False,
    require_rights_clearance: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> DomainDocument:
    verifier = _DistributionPackageVerifier(
        Path(zip_path),
        strict=strict,
        require_audio=require_audio,
        require_artwork=require_artwork,
        require_encoded_audio=require_encoded_audio,
        require_encoded_audio_review=require_encoded_audio_review,
        require_format_decision=require_format_decision,
        require_rights_clearance=require_rights_clearance,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def distribution_verification_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "package_id": summary.get("package_id"),
            "release_id": summary.get("release_id"),
            "target_id": summary.get("target_id"),
            "profile_id": summary.get("profile_id"),
            "entry_count": summary.get("entry_count", 0),
            "checked_file_count": summary.get("checked_file_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def write_distribution_verification_report(report: DomainDocument, path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))


def print_distribution_verification_report(report: DomainDocument) -> None:
    summary = distribution_verification_summary(report)
    print("MusicForge distribution package verification")
    print(f"status: {summary.get('status')}")
    print(f"package: {summary.get('package_id') or 'unknown'}")
    print(f"release: {summary.get('release_id') or 'unknown'}")
    print(f"target: {summary.get('target_id') or 'unknown'}")
    print(f"profile: {summary.get('profile_id') or 'unknown'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"checked files: {summary.get('checked_file_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = _as_list(report.get(key))
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            check_id = item.get("check_id", "unknown") if isinstance(item, dict) else "unknown"
            message = item.get("message", str(item)) if isinstance(item, dict) else str(item)
            print(f"  [{check_id}] {message}")
        if len(items) > 10:
            print(f"  ... {len(items) - 10} more")


def distribution_verification_exit_code(report: DomainDocument) -> int:
    return 1 if report.get("status") == "failed" else 0


class _DistributionPackageVerifier(_DistributionPackageVerifierReadinessMixin, _DistributionPackageVerifierEvidenceMixin):
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_audio: bool,
        require_artwork: bool,
        require_encoded_audio: bool,
        require_encoded_audio_review: bool,
        require_format_decision: bool,
        require_rights_clearance: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_audio = require_audio
        self.require_artwork = require_artwork
        self.require_encoded_audio = require_encoded_audio
        self.require_encoded_audio_review = require_encoded_audio_review
        self.require_format_decision = require_format_decision
        self.require_rights_clearance = require_rights_clearance
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[ImplementationDocument] = []
        self.files: list[ImplementationDocument] = []
        self.redaction_findings: list[ImplementationDocument] = []
        self.manifest: ImplementationDocument = {}
        self.signoff: ImplementationDocument = {}
        self.package: ImplementationDocument = {}
        self.release: ImplementationDocument = {}
        self.tracklist: ImplementationDocument = {}
        self.template: ImplementationDocument = {}
        self.template_summary_doc: ImplementationDocument = {}
        self.checklist: ImplementationDocument = {}
        self.layout: ImplementationDocument = {}
        self.encoded_audio_summary: ImplementationDocument = {}
        self.encoded_audio_manifests: dict[str, ImplementationDocument] = {}
        self.encoded_audio_acceptance_summary: ImplementationDocument = {}
        self.encoded_audio_acceptance_reviews: dict[str, ImplementationDocument] = {}
        self.format_decision_summary: ImplementationDocument = {}
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0






















def _distribution_signoff_hash_payload(signoff: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in signoff.items() if key not in DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}


def _formula_cell(cell: str) -> bool:
    text = str(cell or "")
    return bool(text and text.startswith(FORMULA_PREFIXES) and not text.startswith("'"))


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def _version_at_least(version: str, minimum: str) -> bool:
    def parts(value: str) -> tuple[int, int, int]:
        raw = str(value or "0.0.0").split("-", 1)[0].lstrip("v")
        nums = []
        for item in raw.split(".")[:3]:
            try:
                nums.append(int(item))
            except ValueError:
                nums.append(0)
        while len(nums) < 3:
            nums.append(0)
        return nums[0], nums[1], nums[2]

    return parts(version) >= parts(minimum)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_findings(path: str, text: str) -> list[ImplementationDocument]:
    findings: list[ImplementationDocument] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": kind, "message": f"{path} contains a local path-like value."})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "sensitive_value", "message": f"{path} contains a sensitive value pattern: {replacement}."})
    return findings


def _blocked_key_findings(path: str, value: Any, *, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[ImplementationDocument] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in DISTRIBUTION_BLOCKED_KEYS:
                findings.append({"path": path, "field": child_path, "kind": "blocked_key", "message": f"{path} contains blocked key {child_path}."})
            findings.extend(_blocked_key_findings(path, item, prefix=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(path, item, prefix=f"{prefix}[{index}]"))
    return findings


def _main() -> None:
    report = verify_distribution_package(Path(sys.argv[1]))
    print_distribution_verification_report(report)
    raise SystemExit(distribution_verification_exit_code(report))


if __name__ == "__main__":
    _main()

_v142_dv_readiness.bind_globals(globals())
_v142_dv_evidence.bind_globals(globals())
