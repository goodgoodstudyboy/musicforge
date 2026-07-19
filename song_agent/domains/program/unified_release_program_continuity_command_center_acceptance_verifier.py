# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path

import json as json
import re as re
import tempfile as tempfile
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.contracts.packages import PackageSpec as PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope as verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_hash as _integrity_hash,
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report as build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check as archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import ProgramPersistenceError as ProgramPersistenceError, read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE, COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE, COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE as COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_command_center_final_handoff_package as verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_signoff_package as verify_unified_release_program_continuity_command_center_signoff_package


SCHEMA_VERSION = 1
REVIEW_PACK_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_review_pack"
REVIEW_PACK_VERIFICATION_PACKAGE_TYPE = f"{REVIEW_PACK_PACKAGE_TYPE}_verification"
RESPONSE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_response"
RESPONSE_VERIFICATION_PACKAGE_TYPE = f"{RESPONSE_PACKAGE_TYPE}_verification"
RESPONSE_BINDING_PACKAGE_TYPE = f"{RESPONSE_PACKAGE_TYPE}_binding"
ACCEPTED_EVIDENCE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_acceptance_accepted_evidence"
ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE = f"{ACCEPTED_EVIDENCE_PACKAGE_TYPE}_verification"
BOARD_REPORT_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_receiver_acceptance_board"
SIGNOFF_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_receiver_acceptance_signoff"
SIGNOFF_BINDING_PACKAGE_TYPE = f"{SIGNOFF_PACKAGE_TYPE}_binding"
ARCHIVE_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_command_center_receiver_acceptance_archive"
ARCHIVE_VERIFICATION_PACKAGE_TYPE = f"{ARCHIVE_PACKAGE_TYPE}_verification"

REVIEW_PACK_ENTRIES = {
    "manifest.json",
    "README.txt",
    "review-pack-report.json",
    "package-index.json",
    "verification-summary.json",
    "packages/command-center-signoff-archive.zip",
    "packages/command-center-final-handoff.zip",
}
ACCEPTED_EVIDENCE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "accepted-evidence.json",
    "original-response-public.json",
    "response-verification-summary.json",
    "response-binding-summary.json",
}
ARCHIVE_ENTRIES = {
    "manifest.json",
    "README.txt",
    "receiver-acceptance-signoff.json",
    "receiver-acceptance-signoff-binding-summary.json",
    "receiver-acceptance-history.jsonl",
    "receiver-acceptance-state.json",
    "receiver-acceptance-policy.json",
    "receiver-acceptance-board-report.json",
    "receiver-decision-matrix.json",
    "receiver-quorum-report.json",
    "receiver-findings-register.json",
    "accepted-evidence-index.json",
    "response-proof-index.json",
    "source-handoff-summary.json",
    "source-signoff-archive-summary.json",
}

SOURCE_FIELDS = (
    "program_id",
    "command_center_signoff_archive_zip_sha256",
    "command_center_signoff_archive_zip_size_bytes",
    "command_center_signoff_archive_manifest_hash",
    "command_center_signoff_archive_verification_report_hash",
    "command_center_final_handoff_zip_sha256",
    "command_center_final_handoff_zip_size_bytes",
    "command_center_final_handoff_manifest_hash",
    "command_center_final_handoff_verification_report_hash",
    "command_center_signoff_binding_hash",
    "command_center_zip_sha256",
    "command_center_manifest_hash",
    "command_center_verification_report_hash",
    "external_evidence_manifest_hash",
)

def verify_review_pack(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    signoff_archive_verification_report_path: Path | str | None = None,
    final_handoff_verification_report_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
    command_center_zip_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    command_center_external_evidence_manifest_path: Path | str | None = None,
    max_zip_size_mb: int = 512,
    max_uncompressed_size_mb: int = 1024,
    max_entry_count: int = 100,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=REVIEW_PACK_PACKAGE_TYPE,
                verification_package_type=REVIEW_PACK_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpcccarp_kernel",
                required_entries=frozenset(REVIEW_PACK_ENTRIES),
                optional_entries=frozenset(),
                nested_zip_policy="allowlisted",
                allowed_nested_entries=frozenset({
                    "packages/command-center-signoff-archive.zip",
                    "packages/command-center-final-handoff.zip",
                }),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.is_file():
        return _finish(checks, summary, REVIEW_PACK_VERIFICATION_PACKAGE_TYPE, _check("urpcccarp_zip_exists", False, "Review Pack ZIP exists."))
    summary.update({"zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size})
    checks.extend(
        [
            _check("urpcccarp_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "Review Pack ZIP size is within limit."),
            _check("urpcccarp_no_trailing_data", _zip_has_no_trailing_data(zip_path), "Review Pack ZIP has no trailing data."),
        ]
    )
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            checks.extend(
                [
                    _check("urpcccarp_no_duplicates", not duplicates, "Review Pack contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpcccarp_entry_count", len(infos) <= max_entry_count, "Review Pack entry count is within limit."),
                    _check("urpcccarp_uncompressed_size", sum(item.file_size for item in infos) <= max_uncompressed_size_mb * 1024 * 1024, "Review Pack uncompressed size is within limit."),
                    _check("urpcccarp_paths_safe", not unsafe, "Review Pack paths are safe.", {"unsafe": unsafe}),
                    _check("urpcccarp_allowed_entries", name_set == REVIEW_PACK_ENTRIES, "Review Pack has the fixed entry set.", {"extra": sorted(name_set - REVIEW_PACK_ENTRIES), "missing": sorted(REVIEW_PACK_ENTRIES - name_set)}),
                ]
            )
            if _has_blockers(checks):
                return _finish(checks, summary, REVIEW_PACK_VERIFICATION_PACKAGE_TYPE)
            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "review-pack-report.json")
            package_index = _read_json_entry(archive, "package-index.json")
            verification = _read_json_entry(archive, "verification-summary.json")
            source = _as_document(report.get("source"))
            summary.update({"program_id": report.get("program_id"), "manifest_hash": manifest.get("integrity_hash"), "source_hash": report.get("source_hash"), "status": report.get("status")})
            checks.extend(_manifest_checks(archive, manifest, REVIEW_PACK_ENTRIES, "urpcccarp"))
            checks.extend(
                [
                    _check("urpcccarp_manifest_package_type", manifest.get("package_type") == REVIEW_PACK_PACKAGE_TYPE, "Review Pack manifest package type is valid."),
                    _check("urpcccarp_report_integrity", _integrity_ok(report), "Review Pack report integrity is valid."),
                    _check("urpcccarp_package_index_integrity", _integrity_ok(package_index), "Review Pack package index integrity is valid."),
                    _check("urpcccarp_verification_integrity", _integrity_ok(verification), "Review Pack verification summary integrity is valid."),
                    _check("urpcccarp_source_hash", report.get("source_hash") == stable_hash(_source_projection(source)), "Review Pack source hash is valid."),
                    _check("urpcccarp_status_ready", report.get("status") == "ready", "Review Pack is ready."),
                    _check("urpcccarp_package_index_exact", _package_index_matches(package_index, archive, source), "Package index is fixed and matches nested packages."),
                    _check("urpcccarp_manifest_report", (manifest.get("source") or {}).get("review_pack_report_hash") == report.get("integrity_hash"), "Manifest binds Review Pack report."),
                    _check("urpcccarp_manifest_package_index", (manifest.get("source") or {}).get("package_index_hash") == package_index.get("integrity_hash"), "Manifest binds package index."),
                    _check("urpcccarp_manifest_verification", (manifest.get("source") or {}).get("verification_summary_hash") == verification.get("integrity_hash"), "Manifest binds verification summary."),
                ]
            )
            if require_current:
                required_paths = (
                    signoff_archive_verification_report_path,
                    final_handoff_verification_report_path,
                    signoff_binding_path,
                    command_center_zip_path,
                    command_center_verification_report_path,
                    command_center_external_evidence_manifest_path,
                )
                if not all(required_paths):
                    checks.append(_check("urpcccarp_current_evidence_required", False, "Current v12.10 external evidence is required."))
                else:
                    with tempfile.TemporaryDirectory(prefix="mf-urpcccarp-") as temp:
                        root = Path(temp).resolve()
                        archive_path = root / "command-center-signoff-archive.zip"
                        handoff_path = root / "command-center-final-handoff.zip"
                        archive_path.write_bytes(archive.read("packages/command-center-signoff-archive.zip"))
                        handoff_path.write_bytes(archive.read("packages/command-center-final-handoff.zip"))
                        checks.extend(
                            _current_v1210_checks(
                                source,
                                archive_path,
                                handoff_path,
                                signoff_archive_verification_report_path,
                                final_handoff_verification_report_path,
                                signoff_binding_path,
                                command_center_zip_path,
                                command_center_verification_report_path,
                                command_center_external_evidence_manifest_path,
                            )
                        )
            checks.append(_redaction_check(archive, names, "urpcccarp_redaction"))
    except (
        OSError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        KeyError,
        ProgramPersistenceError,
    ) as exc:
        checks.append(_check("urpcccarp_zip_readable", False, "Review Pack ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, REVIEW_PACK_VERIFICATION_PACKAGE_TYPE)


def verify_accepted_evidence(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_response: bool = False,
    response_path: Path | str | None = None,
    response_verification_report_path: Path | str | None = None,
    response_binding_summary_path: Path | str | None = None,
    max_zip_size_mb: int = 64,
    max_uncompressed_size_mb: int = 128,
    max_entry_count: int = 100,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                verification_package_type=ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpcccae_kernel",
                required_entries=frozenset(ACCEPTED_EVIDENCE_ENTRIES),
                optional_entries=frozenset(),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.is_file():
        return _finish(checks, summary, ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, _check("urpcccae_zip_exists", False, "Accepted Evidence ZIP exists."))
    summary.update({"zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size})
    checks.extend(
        [
            _check("urpcccae_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "Accepted Evidence ZIP size is within limit."),
            _check("urpcccae_no_trailing_data", _zip_has_no_trailing_data(zip_path), "Accepted Evidence ZIP has no trailing data."),
        ]
    )
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            checks.extend(
                [
                    _check("urpcccae_no_duplicates", not duplicates, "Accepted Evidence contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpcccae_entry_count", len(infos) <= max_entry_count, "Accepted Evidence entry count is within limit."),
                    _check("urpcccae_uncompressed_size", sum(item.file_size for item in infos) <= max_uncompressed_size_mb * 1024 * 1024, "Accepted Evidence uncompressed size is within limit."),
                    _check("urpcccae_paths_safe", not unsafe, "Accepted Evidence paths are safe.", {"unsafe": unsafe}),
                    _check("urpcccae_allowed_entries", name_set == ACCEPTED_EVIDENCE_ENTRIES, "Accepted Evidence has the fixed entry set.", {"extra": sorted(name_set - ACCEPTED_EVIDENCE_ENTRIES), "missing": sorted(ACCEPTED_EVIDENCE_ENTRIES - name_set)}),
                ]
            )
            if _has_blockers(checks):
                return _finish(checks, summary, ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE)
            manifest = _read_json_entry(archive, "manifest.json")
            accepted = _read_json_entry(archive, "accepted-evidence.json")
            public = _read_json_entry(archive, "original-response-public.json")
            verification_summary = _read_json_entry(archive, "response-verification-summary.json")
            binding_summary = _read_json_entry(archive, "response-binding-summary.json")
            summary.update({"program_id": accepted.get("program_id"), "evidence_id": accepted.get("evidence_id"), "response_id": accepted.get("response_id"), "manifest_hash": manifest.get("integrity_hash"), "status": accepted.get("status")})
            checks.extend(_manifest_checks(archive, manifest, ACCEPTED_EVIDENCE_ENTRIES, "urpcccae"))
            checks.extend(
                [
                    _check("urpcccae_manifest_type", manifest.get("package_type") == ACCEPTED_EVIDENCE_PACKAGE_TYPE, "Accepted Evidence manifest package type is valid."),
                    _check("urpcccae_accepted_integrity", _integrity_ok(accepted), "Accepted Evidence integrity is valid."),
                    _check("urpcccae_public_integrity", _integrity_ok(public), "Public response projection integrity is valid."),
                    _check("urpcccae_verification_summary_integrity", _integrity_ok(verification_summary), "Response verification summary integrity is valid."),
                    _check("urpcccae_binding_summary_integrity", _integrity_ok(binding_summary), "Response binding summary integrity is valid."),
                    _check("urpcccae_status", accepted.get("status") == "accepted" and accepted.get("decision") == "accepted", "Accepted Evidence decision is accepted."),
                    _check("urpcccae_public_hash", accepted.get("response_public_projection_hash") == public.get("integrity_hash"), "Accepted Evidence binds public response projection."),
                    _check("urpcccae_verification_hash", accepted.get("response_verification_report_hash") == verification_summary.get("verification_report_hash"), "Accepted Evidence binds response verification report."),
                    _check("urpcccae_binding_hash", accepted.get("response_binding_hash") == binding_summary.get("integrity_hash"), "Accepted Evidence binds response binding summary."),
                    _check("urpcccae_role", accepted.get("role") == binding_summary.get("role"), "Accepted role comes from binding proof."),
                    _check("urpcccae_organization", accepted.get("organization") == binding_summary.get("organization"), "Accepted organization comes from binding proof."),
                    _check("urpcccae_decision", accepted.get("decision") == binding_summary.get("decision") == "accepted", "Accepted decision comes from binding proof."),
                ]
            )
            if require_response:
                paths = (response_path, response_verification_report_path, response_binding_summary_path)
                if not all(paths) or not all(Path(path).is_file() for path in paths if path):
                    checks.append(_check("urpcccae_external_response_required", False, "External response proof files are required."))
                else:
                    response = read_json(_as_path(response_path))
                    verification = read_json(_as_path(response_verification_report_path))
                    binding = read_json(_as_path(response_binding_summary_path))
                    checks.extend(validate_response_proof(response, verification, binding, binding_summary))
                    checks.extend(
                        [
                            _check("urpcccae_external_public", public == _with_integrity(_response_public_projection(response)), "Public response projection matches external response."),
                            _check("urpcccae_external_verification", verification_summary.get("verification_report_hash") == verification.get("integrity_hash"), "Verification summary matches external report."),
                            _check("urpcccae_external_binding", binding_summary.get("integrity_hash") == binding.get("integrity_hash"), "Binding summary matches external proof."),
                        ]
                    )
            checks.append(_redaction_check(archive, names, "urpcccae_redaction"))
    except (
        OSError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        KeyError,
        ProgramPersistenceError,
    ) as exc:
        checks.append(_check("urpcccae_zip_readable", False, "Accepted Evidence ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE)


from song_agent.domains.program import v142_urpcccav_readiness as _v142_urpcccav_readiness
from song_agent.domains.program.v142_urpcccav_readiness import verify_unified_release_program_continuity_command_center_acceptance_package as verify_unified_release_program_continuity_command_center_acceptance_package, validate_response_proof as validate_response_proof, write_verification_report as write_verification_report, verification_exit_code as verification_exit_code, _current_v1210_checks as _current_v1210_checks, _archive_external_checks as _archive_external_checks
from song_agent.domains.program import v142_urpcccav_evidence as _v142_urpcccav_evidence
from song_agent.domains.program.v142_urpcccav_evidence import _source_package_summary_checks as _source_package_summary_checks, _archive_internal_checks as _archive_internal_checks, _package_index_matches as _package_index_matches, _participant_from_binding as _participant_from_binding, _matrix_rows as _matrix_rows, _findings_rows as _findings_rows, _quorum_result as _quorum_result, _response_public_projection as _response_public_projection, _reviewer_identity as _reviewer_identity, _source_projection as _source_projection, _response_payload_hash as _response_payload_hash, _with_integrity as _with_integrity, _manifest_checks as _manifest_checks, _history_checks as _history_checks, _redaction_check as _redaction_check, _read_json_entry as _read_json_entry, _parse_jsonl as _parse_jsonl, _json_bytes as _json_bytes, _safe_key as _safe_key, _prefix_checks as _prefix_checks, _has_blockers as _has_blockers, _finish as _finish

_v142_urpcccav_readiness.bind_globals(globals())
_v142_urpcccav_evidence.bind_globals(globals())
