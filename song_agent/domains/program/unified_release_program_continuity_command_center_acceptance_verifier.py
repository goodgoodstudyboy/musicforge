from __future__ import annotations

import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_hash as _integrity_hash,
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import (
    ProgramPersistenceError,
    read_program_json as read_json,
    write_program_json as write_json,
)
from song_agent.platform.verification.sanitization import sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff_verifier import (
    COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE,
    COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE,
    COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_command_center_final_handoff_package,
    verify_unified_release_program_continuity_command_center_signoff_package,
)


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
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
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
            source = report.get("source") if isinstance(report.get("source"), dict) else {}
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
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
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
                    response = read_json(Path(response_path))
                    verification = read_json(Path(response_verification_report_path))
                    binding = read_json(Path(response_binding_summary_path))
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


def verify_unified_release_program_continuity_command_center_acceptance_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    signoff_binding_path: Path | str | None = None,
    review_pack_path: Path | str | None = None,
    review_pack_verification_report_path: Path | str | None = None,
    accepted_evidence_dir: Path | str | None = None,
    response_proof_dir: Path | str | None = None,
    command_center_signoff_archive_path: Path | str | None = None,
    command_center_signoff_archive_verification_report_path: Path | str | None = None,
    command_center_final_handoff_path: Path | str | None = None,
    command_center_final_handoff_verification_report_path: Path | str | None = None,
    command_center_signoff_binding_path: Path | str | None = None,
    command_center_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    command_center_evidence_manifest_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 256,
    max_entry_count: int = 100,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=ARCHIVE_PACKAGE_TYPE,
                verification_package_type=ARCHIVE_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpccca_kernel",
                required_entries=frozenset(ARCHIVE_ENTRIES),
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
        return _finish(checks, summary, ARCHIVE_VERIFICATION_PACKAGE_TYPE, _check("urpccca_zip_exists", False, "Receiver Acceptance Archive ZIP exists."))
    summary.update({"zip_sha256": _sha256_path(zip_path), "zip_size_bytes": zip_path.stat().st_size})
    checks.extend(
        [
            _check("urpccca_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "Archive ZIP size is within limit."),
            _check("urpccca_no_trailing_data", _zip_has_no_trailing_data(zip_path), "Archive ZIP has no trailing data."),
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
                    _check("urpccca_no_duplicates", not duplicates, "Archive contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpccca_entry_count", len(infos) <= max_entry_count, "Archive entry count is within limit."),
                    _check("urpccca_uncompressed_size", sum(item.file_size for item in infos) <= max_uncompressed_size_mb * 1024 * 1024, "Archive uncompressed size is within limit."),
                    _check("urpccca_paths_safe", not unsafe, "Archive paths are safe.", {"unsafe": unsafe}),
                    _check("urpccca_allowed_entries", name_set == ARCHIVE_ENTRIES, "Archive has the fixed entry set.", {"extra": sorted(name_set - ARCHIVE_ENTRIES), "missing": sorted(ARCHIVE_ENTRIES - name_set)}),
                ]
            )
            if _has_blockers(checks):
                return _finish(checks, summary, ARCHIVE_VERIFICATION_PACKAGE_TYPE)
            docs = {name: _read_json_entry(archive, name) for name in ARCHIVE_ENTRIES if name.endswith(".json")}
            manifest = docs["manifest.json"]
            signoff = docs["receiver-acceptance-signoff.json"]
            binding = docs["receiver-acceptance-signoff-binding-summary.json"]
            state = docs["receiver-acceptance-state.json"]
            policy = docs["receiver-acceptance-policy.json"]
            report = docs["receiver-acceptance-board-report.json"]
            matrix = docs["receiver-decision-matrix.json"]
            quorum = docs["receiver-quorum-report.json"]
            findings = docs["receiver-findings-register.json"]
            accepted_index = docs["accepted-evidence-index.json"]
            response_index = docs["response-proof-index.json"]
            handoff_summary = docs["source-handoff-summary.json"]
            archive_summary = docs["source-signoff-archive-summary.json"]
            history = _parse_jsonl(archive.read("receiver-acceptance-history.jsonl").decode("utf-8"))
            summary.update({"program_id": report.get("program_id"), "manifest_hash": manifest.get("integrity_hash"), "status": report.get("status"), "accepted_count": (quorum.get("summary") or {}).get("accepted_count")})
            checks.extend(_manifest_checks(archive, manifest, ARCHIVE_ENTRIES, "urpccca"))
            for name, doc in docs.items():
                checks.append(_check(f"urpccca_{_safe_key(name)}_integrity", _integrity_ok(doc), f"{name} integrity is valid."))
            checks.extend(_history_checks(history))
            checks.extend(_archive_internal_checks(manifest, signoff, binding, state, policy, report, matrix, quorum, findings, accepted_index, response_index, handoff_summary, archive_summary, history, require_signed=require_signed))
            if require_signed:
                if not signoff_binding_path or not Path(signoff_binding_path).is_file():
                    checks.append(_check("urpccca_external_signoff_binding_required", False, "External signoff binding is required."))
                else:
                    external_binding = read_json(Path(signoff_binding_path))
                    checks.extend(
                        [
                            _check("urpccca_external_signoff_binding_integrity", _integrity_ok(external_binding), "External signoff binding integrity is valid."),
                            _check("urpccca_external_signoff_binding_hash", external_binding.get("integrity_hash") == binding.get("integrity_hash"), "External signoff binding matches Archive binding."),
                        ]
                    )
            external_required = require_signed
            external_paths = (
                review_pack_path,
                review_pack_verification_report_path,
                accepted_evidence_dir,
                command_center_signoff_archive_verification_report_path,
                command_center_final_handoff_verification_report_path,
                command_center_signoff_binding_path,
                command_center_path,
                command_center_verification_report_path,
                command_center_evidence_manifest_path,
            )
            if external_required and not all(external_paths):
                checks.append(_check("urpccca_external_evidence_required", False, "Current Review Pack, response proofs, accepted evidence, and v12.10 evidence are required."))
            elif all(external_paths):
                checks.extend(
                    _archive_external_checks(
                        report,
                        matrix,
                        quorum,
                        findings,
                        accepted_index,
                        response_index,
                        handoff_summary,
                        archive_summary,
                        review_pack_path,
                        review_pack_verification_report_path,
                        accepted_evidence_dir,
                        response_proof_dir,
                        command_center_signoff_archive_path,
                        command_center_signoff_archive_verification_report_path,
                        command_center_final_handoff_path,
                        command_center_final_handoff_verification_report_path,
                        command_center_signoff_binding_path,
                        command_center_path,
                        command_center_verification_report_path,
                        command_center_evidence_manifest_path,
                    )
                )
            checks.append(_redaction_check(archive, names, "urpccca_redaction"))
    except (
        OSError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        KeyError,
        ProgramPersistenceError,
    ) as exc:
        checks.append(_check("urpccca_zip_readable", False, "Receiver Acceptance Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, ARCHIVE_VERIFICATION_PACKAGE_TYPE)


def validate_response_proof(
    response: dict[str, Any],
    verification: dict[str, Any],
    binding: dict[str, Any],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    projection = _response_public_projection(response)
    response_bytes = _json_bytes(response)
    required_source = {
        "review_pack_id": source.get("review_pack_id"),
        "review_pack_source_hash": source.get("review_pack_source_hash"),
        "review_pack_zip_sha256": source.get("review_pack_zip_sha256"),
        "review_pack_manifest_hash": source.get("review_pack_manifest_hash"),
        "review_pack_verification_report_hash": source.get("review_pack_verification_report_hash"),
        "command_center_signoff_archive_zip_sha256": source.get("command_center_signoff_archive_zip_sha256"),
        "command_center_signoff_archive_manifest_hash": source.get("command_center_signoff_archive_manifest_hash"),
        "command_center_signoff_archive_verification_report_hash": source.get("command_center_signoff_archive_verification_report_hash"),
        "command_center_final_handoff_zip_sha256": source.get("command_center_final_handoff_zip_sha256"),
        "command_center_final_handoff_manifest_hash": source.get("command_center_final_handoff_manifest_hash"),
        "command_center_final_handoff_verification_report_hash": source.get("command_center_final_handoff_verification_report_hash"),
        "command_center_signoff_binding_hash": source.get("command_center_signoff_binding_hash"),
    }
    checks = [
        _check("urpcccar_response_type", response.get("package_type") == RESPONSE_PACKAGE_TYPE, "Response package type is valid."),
        _check("urpcccar_response_integrity", _integrity_ok(response), "Response integrity is valid."),
        _check("urpcccar_response_payload", response.get("payload_hash") == _response_payload_hash(response), "Response payload hash is valid."),
        _check("urpcccar_verification_type", verification.get("package_type") == RESPONSE_VERIFICATION_PACKAGE_TYPE, "Response verification package type is valid."),
        _check("urpcccar_verification_integrity", _integrity_ok(verification), "Response verification integrity is valid."),
        _check("urpcccar_verification_status", verification.get("status") == "passed", "Response verification passed."),
        _check("urpcccar_binding_type", binding.get("package_type") == RESPONSE_BINDING_PACKAGE_TYPE, "Response binding package type is valid."),
        _check("urpcccar_binding_integrity", _integrity_ok(binding), "Response binding integrity is valid."),
        _check("urpcccar_response_sha", verification.get("response_sha256") == binding.get("response_sha256") == _sha256_bytes(response_bytes), "Response byte hash is bound."),
        _check("urpcccar_payload_hash", verification.get("response_payload_hash") == binding.get("response_payload_hash") == response.get("payload_hash"), "Response payload hash is bound."),
        _check("urpcccar_verification_binding", binding.get("response_verification_report_hash") == verification.get("integrity_hash"), "Binding references response verification report."),
        _check("urpcccar_identity", verification.get("reviewer_identity_hash") == binding.get("reviewer_identity_hash") == stable_hash(_reviewer_identity(response)), "Reviewer identity is bound."),
        _check("urpcccar_decision", verification.get("decision_hash") == binding.get("decision_hash") == stable_hash({"decision": response.get("decision")}), "Decision is bound."),
        _check("urpcccar_findings", verification.get("findings_hash") == binding.get("findings_hash") == stable_hash({"findings": response.get("findings") or []}), "Findings are bound."),
        _check("urpcccar_public_projection", verification.get("response_public_projection_hash") == binding.get("response_public_projection_hash") == stable_hash(projection), "Public response projection is bound."),
        _check("urpcccar_decision_allowed", response.get("decision") in {"accepted", "needs_changes", "rejected"}, "Response decision is allowed."),
        _check("urpcccar_role_binding", verification.get("role") == binding.get("role") == response.get("role"), "Reviewer role comes from external proof."),
        _check("urpcccar_org_binding", verification.get("organization") == binding.get("organization") == response.get("organization"), "Reviewer organization comes from external proof."),
        _check("urpcccar_name_binding", verification.get("reviewer") == binding.get("reviewer") == response.get("reviewer"), "Reviewer name comes from external proof."),
        _check("urpcccar_decision_binding", verification.get("decision") == binding.get("decision") == response.get("decision"), "Decision comes from external proof."),
    ]
    for field, expected in required_source.items():
        checks.append(_check(f"urpcccar_source_{_safe_key(field)}", response.get(field) == verification.get(field) == binding.get(field) == expected, f"Response proof binds current {field}."))
    return checks


def write_verification_report(report: dict[str, Any], path: Path | str) -> dict[str, Any]:
    write_json(Path(path), report)
    return report


def verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _current_v1210_checks(
    source: dict[str, Any],
    archive_path: Path,
    handoff_path: Path,
    archive_report_path: Path | str | None,
    handoff_report_path: Path | str | None,
    binding_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_report_path: Path | str | None,
    command_center_evidence_path: Path | str | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    paths = [archive_report_path, handoff_report_path, binding_path, command_center_path, command_center_report_path, command_center_evidence_path]
    if not all(paths) or not all(Path(path).is_file() for path in paths if path):
        return [_check("urpcccarp_v1210_paths", False, "All v12.10 external evidence paths exist.")]
    archive_external = read_json(Path(archive_report_path))
    handoff_external = read_json(Path(handoff_report_path))
    binding = read_json(Path(binding_path))
    archive_runtime = verify_unified_release_program_continuity_command_center_signoff_package(
        archive_path,
        strict=True,
        require_signed=True,
        signoff_binding_path=binding_path,
        command_center_zip_path=command_center_path,
        command_center_verification_report_path=command_center_report_path,
        command_center_external_evidence_manifest_path=command_center_evidence_path,
    )
    handoff_runtime = verify_unified_release_program_continuity_command_center_final_handoff_package(
        handoff_path,
        strict=True,
        require_archive=True,
        archive_zip_path=archive_path,
        archive_verification_report_path=archive_report_path,
        signoff_binding_path=binding_path,
        command_center_zip_path=command_center_path,
        command_center_verification_report_path=command_center_report_path,
        command_center_external_evidence_manifest_path=command_center_evidence_path,
    )
    expected = {
        "command_center_signoff_archive_zip_sha256": _sha256_path(archive_path),
        "command_center_signoff_archive_zip_size_bytes": archive_path.stat().st_size,
        "command_center_signoff_archive_manifest_hash": archive_runtime.get("manifest_hash"),
        "command_center_signoff_archive_verification_report_hash": archive_external.get("integrity_hash"),
        "command_center_final_handoff_zip_sha256": _sha256_path(handoff_path),
        "command_center_final_handoff_zip_size_bytes": handoff_path.stat().st_size,
        "command_center_final_handoff_manifest_hash": handoff_runtime.get("manifest_hash"),
        "command_center_final_handoff_verification_report_hash": handoff_external.get("integrity_hash"),
        "command_center_signoff_binding_hash": binding.get("integrity_hash"),
    }
    checks.extend(
        [
            _check("urpcccarp_archive_external_type", archive_external.get("package_type") == COMMAND_CENTER_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE, "Signoff Archive verification package type is valid."),
            _check("urpcccarp_handoff_external_type", handoff_external.get("package_type") == COMMAND_CENTER_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE, "Final Handoff verification package type is valid."),
            _check("urpcccarp_archive_external_integrity", _integrity_ok(archive_external), "Signoff Archive external report integrity is valid."),
            _check("urpcccarp_handoff_external_integrity", _integrity_ok(handoff_external), "Final Handoff external report integrity is valid."),
            _check("urpcccarp_archive_runtime", archive_runtime.get("status") == "passed" and archive_external.get("status") == "passed", "Signoff Archive runtime and external verification passed.", {"blockers": archive_runtime.get("blockers") or []}),
            _check("urpcccarp_handoff_runtime", handoff_runtime.get("status") == "passed" and handoff_external.get("status") == "passed", "Final Handoff runtime and external verification passed.", {"blockers": handoff_runtime.get("blockers") or []}),
            _check("urpcccarp_archive_external_binding", archive_external.get("zip_sha256") == archive_runtime.get("zip_sha256") and archive_external.get("manifest_hash") == archive_runtime.get("manifest_hash"), "Signoff Archive external report matches nested ZIP."),
            _check("urpcccarp_handoff_external_binding", handoff_external.get("zip_sha256") == handoff_runtime.get("zip_sha256") and handoff_external.get("manifest_hash") == handoff_runtime.get("manifest_hash"), "Final Handoff external report matches nested ZIP."),
        ]
    )
    for field, value in expected.items():
        checks.append(_check(f"urpcccarp_source_{_safe_key(field)}", source.get(field) == value, f"Review Pack source binds {field}."))
    return checks


def _archive_external_checks(
    report: dict[str, Any],
    matrix: dict[str, Any],
    quorum: dict[str, Any],
    findings: dict[str, Any],
    accepted_index: dict[str, Any],
    response_index: dict[str, Any],
    handoff_summary: dict[str, Any],
    archive_summary: dict[str, Any],
    review_pack_path: Path | str | None,
    review_pack_report_path: Path | str | None,
    accepted_dir_value: Path | str | None,
    response_dir_value: Path | str | None,
    signoff_archive_path: Path | str | None,
    signoff_archive_report_path: Path | str | None,
    handoff_path: Path | str | None,
    handoff_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    command_center_path: Path | str | None,
    command_center_report_path: Path | str | None,
    command_center_evidence_path: Path | str | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    review_pack = Path(review_pack_path) if review_pack_path else Path()
    review_report_path = Path(review_pack_report_path) if review_pack_report_path else Path()
    if not review_pack.is_file() or not review_report_path.is_file():
        return [_check("urpccca_review_pack_required", False, "Current Review Pack and verification report exist.")]
    review_external = read_json(review_report_path)
    review_runtime = verify_review_pack(
        review_pack,
        strict=True,
        require_current=True,
        signoff_archive_verification_report_path=signoff_archive_report_path,
        final_handoff_verification_report_path=handoff_report_path,
        signoff_binding_path=signoff_binding_path,
        command_center_zip_path=command_center_path,
        command_center_verification_report_path=command_center_report_path,
        command_center_external_evidence_manifest_path=command_center_evidence_path,
    )
    checks.extend(
        [
            _check("urpccca_review_pack_external_type", review_external.get("package_type") == REVIEW_PACK_VERIFICATION_PACKAGE_TYPE, "Review Pack verification package type is valid."),
            _check("urpccca_review_pack_external_integrity", _integrity_ok(review_external), "Review Pack verification report integrity is valid."),
            _check("urpccca_review_pack_runtime", review_runtime.get("status") == "passed" and review_external.get("status") == "passed", "Review Pack runtime and external verification passed.", {"blockers": review_runtime.get("blockers") or []}),
            _check("urpccca_review_pack_binding", review_external.get("zip_sha256") == review_runtime.get("zip_sha256") == _sha256_path(review_pack) and review_external.get("manifest_hash") == review_runtime.get("manifest_hash"), "Review Pack verification report matches current ZIP."),
        ]
    )
    source = report.get("source") if isinstance(report.get("source"), dict) else {}
    checks.extend(
        [
            _check("urpccca_review_pack_source_hash", source.get("review_pack_source_hash") == review_runtime.get("source_hash"), "Board source binds Review Pack source."),
            _check("urpccca_review_pack_zip_hash", source.get("review_pack_zip_sha256") == review_runtime.get("zip_sha256"), "Board source binds Review Pack ZIP."),
            _check("urpccca_review_pack_manifest_hash", source.get("review_pack_manifest_hash") == review_runtime.get("manifest_hash"), "Board source binds Review Pack manifest."),
            _check("urpccca_review_pack_verification_hash", source.get("review_pack_verification_report_hash") == review_external.get("integrity_hash"), "Board source binds Review Pack verification report."),
        ]
    )
    accepted_dir = Path(accepted_dir_value) if accepted_dir_value else Path()
    response_dir = Path(response_dir_value) if response_dir_value else accepted_dir.parent / "responses"
    indexed_response_ids = {str(row.get("response_id") or "") for row in response_index.get("items") or [] if isinstance(row, dict)}
    external_response_ids = {path.name for path in response_dir.iterdir() if path.is_dir()} if response_dir.is_dir() else set()
    indexed_evidence_ids = {str(row.get("evidence_id") or "") for row in accepted_index.get("items") or [] if isinstance(row, dict)}
    external_evidence_ids = {path.name for path in accepted_dir.iterdir() if path.is_dir()} if accepted_dir.is_dir() else set()
    checks.extend(
        [
            _check("urpccca_external_response_set", external_response_ids == indexed_response_ids, "External response proof set exactly matches the signed index.", {"extra": sorted(external_response_ids - indexed_response_ids), "missing": sorted(indexed_response_ids - external_response_ids)}),
            _check("urpccca_external_evidence_set", external_evidence_ids == indexed_evidence_ids, "External Accepted Evidence set exactly matches the signed index.", {"extra": sorted(external_evidence_ids - indexed_evidence_ids), "missing": sorted(indexed_evidence_ids - external_evidence_ids)}),
        ]
    )
    participants: list[dict[str, Any]] = []
    external_responses: dict[str, dict[str, Any]] = {}
    for row in response_index.get("items") or []:
        if not isinstance(row, dict):
            continue
        response_id = str(row.get("response_id") or "")
        response_path = response_dir / response_id / "response.json"
        verification_path = response_dir / response_id / "response-verification-report.json"
        binding_path = response_dir / response_id / "response-binding-summary.json"
        if not all(path.is_file() for path in (response_path, verification_path, binding_path)):
            checks.append(_check(f"urpccca_response_{_safe_key(response_id)}_external", False, "External response proof exists."))
            continue
        response = read_json(response_path)
        verification = read_json(verification_path)
        binding = read_json(binding_path)
        checks.extend(_prefix_checks(validate_response_proof(response, verification, binding, source), f"urpccca_response_{_safe_key(response_id)}"))
        checks.extend(
            [
                _check(f"urpccca_response_{_safe_key(response_id)}_index_binding", row.get("response_integrity_hash") == response.get("integrity_hash") and row.get("verification_report_hash") == verification.get("integrity_hash") and row.get("binding_hash") == binding.get("integrity_hash"), "Response proof index binds external response proof."),
                _check(f"urpccca_response_{_safe_key(response_id)}_decision", row.get("decision") == binding.get("decision"), "Response proof index decision matches external proof."),
            ]
        )
        external_responses[response_id] = {"response": response, "verification": verification, "binding": binding}
    for row in accepted_index.get("items") or []:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("evidence_id") or "")
        response_id = str(row.get("response_id") or "")
        evidence_zip = accepted_dir / evidence_id / "accepted-evidence.zip"
        evidence_report_path = accepted_dir / evidence_id / "verification-report.json"
        response_bundle = external_responses.get(response_id) or {}
        response_path = response_dir / response_id / "response.json"
        response_verification_path = response_dir / response_id / "response-verification-report.json"
        response_binding_path = response_dir / response_id / "response-binding-summary.json"
        if not evidence_zip.is_file() or not evidence_report_path.is_file():
            checks.append(_check(f"urpccca_evidence_{_safe_key(evidence_id)}_external", False, "External Accepted Evidence exists."))
            continue
        evidence_external = read_json(evidence_report_path)
        evidence_runtime = verify_accepted_evidence(
            evidence_zip,
            strict=True,
            require_response=True,
            response_path=response_path,
            response_verification_report_path=response_verification_path,
            response_binding_summary_path=response_binding_path,
        )
        checks.extend(
            [
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_report_type", evidence_external.get("package_type") == ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, "Accepted Evidence verification package type is valid."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_report_integrity", _integrity_ok(evidence_external), "Accepted Evidence verification report integrity is valid."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_runtime", evidence_runtime.get("status") == "passed" and evidence_external.get("status") == "passed", "Accepted Evidence runtime and external verification passed.", {"blockers": evidence_runtime.get("blockers") or []}),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_zip", row.get("zip_sha256") == evidence_runtime.get("zip_sha256") == evidence_external.get("zip_sha256") == _sha256_path(evidence_zip), "Accepted Evidence index binds current ZIP."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_manifest", row.get("manifest_hash") == evidence_runtime.get("manifest_hash") == evidence_external.get("manifest_hash"), "Accepted Evidence index binds manifest."),
                _check(f"urpccca_evidence_{_safe_key(evidence_id)}_verification", row.get("verification_report_hash") == evidence_external.get("integrity_hash"), "Accepted Evidence index binds verification report."),
            ]
        )
        binding = response_bundle.get("binding") or {}
        participants.append(_participant_from_binding(evidence_id, response_id, binding, row))
    policy = report.get("policy") if isinstance(report.get("policy"), dict) else {}
    rebuilt_findings = _findings_rows(external_responses)
    rebuilt_matrix = _matrix_rows(participants)
    rebuilt_quorum = _quorum_result(policy, participants, external_responses)
    checks.extend(
        [
            _check("urpccca_external_matrix", matrix.get("rows") == rebuilt_matrix, "Decision matrix is rebuilt from external proofs."),
            _check("urpccca_external_findings", findings.get("items") == rebuilt_findings, "Findings register is rebuilt from external proofs."),
            _check("urpccca_external_quorum", quorum.get("summary") == rebuilt_quorum, "Quorum is rebuilt from external proofs."),
            _check("urpccca_external_status", report.get("status") == "signed" and rebuilt_quorum.get("status") == "ready_for_signoff", "Signed Board is externally ready."),
        ]
    )
    checks.extend(
        _source_package_summary_checks(
            handoff_summary,
            archive_summary,
            signoff_archive_path,
            signoff_archive_report_path,
            handoff_path,
            handoff_report_path,
            signoff_binding_path,
        )
    )
    return checks


def _source_package_summary_checks(
    handoff_summary: dict[str, Any],
    archive_summary: dict[str, Any],
    archive_path_value: Path | str | None,
    archive_report_value: Path | str | None,
    handoff_path_value: Path | str | None,
    handoff_report_value: Path | str | None,
    binding_path_value: Path | str | None,
) -> list[dict[str, Any]]:
    values = (archive_path_value, archive_report_value, handoff_path_value, handoff_report_value, binding_path_value)
    if not all(values) or not all(Path(value).is_file() for value in values if value):
        return [_check("urpccca_source_packages_required", False, "Current source packages and reports exist.")]
    archive_path = Path(archive_path_value)
    handoff_path = Path(handoff_path_value)
    archive_report = read_json(Path(archive_report_value))
    handoff_report = read_json(Path(handoff_report_value))
    binding = read_json(Path(binding_path_value))
    return [
        _check("urpccca_source_archive_zip", archive_summary.get("zip_sha256") == _sha256_path(archive_path) == archive_report.get("zip_sha256"), "Source Archive summary binds current ZIP."),
        _check("urpccca_source_archive_manifest", archive_summary.get("manifest_hash") == archive_report.get("manifest_hash"), "Source Archive summary binds manifest."),
        _check("urpccca_source_archive_verification", archive_summary.get("verification_report_hash") == archive_report.get("integrity_hash"), "Source Archive summary binds verification report."),
        _check("urpccca_source_handoff_zip", handoff_summary.get("zip_sha256") == _sha256_path(handoff_path) == handoff_report.get("zip_sha256"), "Source Handoff summary binds current ZIP."),
        _check("urpccca_source_handoff_manifest", handoff_summary.get("manifest_hash") == handoff_report.get("manifest_hash"), "Source Handoff summary binds manifest."),
        _check("urpccca_source_handoff_verification", handoff_summary.get("verification_report_hash") == handoff_report.get("integrity_hash"), "Source Handoff summary binds verification report."),
        _check("urpccca_source_signoff_binding", handoff_summary.get("signoff_binding_hash") == archive_summary.get("signoff_binding_hash") == binding.get("integrity_hash"), "Source summaries bind independent v12.10 signoff binding."),
    ]


def _archive_internal_checks(
    manifest: dict[str, Any],
    signoff: dict[str, Any],
    binding: dict[str, Any],
    state: dict[str, Any],
    policy: dict[str, Any],
    report: dict[str, Any],
    matrix: dict[str, Any],
    quorum: dict[str, Any],
    findings: dict[str, Any],
    accepted_index: dict[str, Any],
    response_index: dict[str, Any],
    handoff_summary: dict[str, Any],
    archive_summary: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    require_signed: bool,
) -> list[dict[str, Any]]:
    event = next((row for row in reversed(history) if row.get("event_type") == "receiver_acceptance_signoff_created"), {})
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    docs = {
        "signoff_hash": signoff,
        "signoff_binding_hash": binding,
        "state_hash": state,
        "policy_hash": policy,
        "board_report_hash": report,
        "decision_matrix_hash": matrix,
        "quorum_report_hash": quorum,
        "findings_register_hash": findings,
        "accepted_evidence_index_hash": accepted_index,
        "response_proof_index_hash": response_index,
        "source_handoff_summary_hash": handoff_summary,
        "source_signoff_archive_summary_hash": archive_summary,
    }
    checks = [
        _check("urpccca_manifest_type", manifest.get("package_type") == ARCHIVE_PACKAGE_TYPE, "Archive manifest package type is valid."),
        _check("urpccca_signoff_type", signoff.get("package_type") == SIGNOFF_PACKAGE_TYPE, "Signoff package type is valid."),
        _check("urpccca_binding_type", binding.get("package_type") == SIGNOFF_BINDING_PACKAGE_TYPE, "Signoff binding package type is valid."),
        _check("urpccca_signoff_status", (not require_signed) or signoff.get("status") == "signed" and report.get("status") == "signed" and state.get("status") == "signed", "Archive is signed when required."),
        _check("urpccca_signoff_payload", signoff.get("payload_hash") == stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}}), "Signoff payload hash is valid."),
        _check("urpccca_binding_signoff", binding.get("signoff_hash") == signoff.get("integrity_hash") == state.get("signoff_hash"), "Binding and state match signoff."),
        _check("urpccca_binding_signer", binding.get("signed_by") == signoff.get("signed_by") and binding.get("role") == signoff.get("role") and binding.get("signed_at") == signoff.get("signed_at"), "Binding matches signoff public fields."),
        _check("urpccca_binding_history", binding.get("history_event_hash") == event.get("event_hash") == state.get("signoff_event_hash"), "Binding and state match signoff history event."),
        _check("urpccca_event_signoff", event.get("signoff_hash") == signoff.get("integrity_hash") and event.get("signoff_payload_hash") == signoff.get("payload_hash"), "History event binds signoff."),
        _check("urpccca_report_policy", report.get("policy_hash") == quorum.get("policy_hash") == stable_hash(report.get("policy") or {}), "Board report and quorum bind policy."),
        _check("urpccca_policy_document", all(policy.get(key) == (report.get("policy") or {}).get(key) for key in ("min_accepted_count", "min_organization_count", "required_roles", "block_on_rejected", "block_on_needs_changes", "block_on_critical_findings")), "Archived policy document matches the signed Board policy."),
    ]
    for key, doc in docs.items():
        checks.append(_check(f"urpccca_manifest_{_safe_key(key)}", source.get(key) == doc.get("integrity_hash"), f"Manifest binds {key}."))
    signoff_docs = {
        "board_report_hash": report,
        "decision_matrix_hash": matrix,
        "quorum_report_hash": quorum,
        "findings_register_hash": findings,
        "accepted_evidence_index_hash": accepted_index,
        "response_proof_index_hash": response_index,
    }
    for key, doc in signoff_docs.items():
        checks.append(_check(f"urpccca_signoff_{_safe_key(key)}", signoff.get(key) == binding.get(key) == doc.get("integrity_hash"), f"Signoff and binding bind {key}."))
    return checks


def _package_index_matches(index: dict[str, Any], archive: zipfile.ZipFile, source: dict[str, Any]) -> bool:
    rows = index.get("packages") if isinstance(index.get("packages"), list) else []
    expected = [
        {
            "component_type": "command_center_signoff_archive",
            "path": "packages/command-center-signoff-archive.zip",
            "package_type": COMMAND_CENTER_SIGNOFF_ARCHIVE_PACKAGE_TYPE,
            "zip_sha256": source.get("command_center_signoff_archive_zip_sha256"),
            "zip_size_bytes": source.get("command_center_signoff_archive_zip_size_bytes"),
            "manifest_hash": source.get("command_center_signoff_archive_manifest_hash"),
            "verification_report_hash": source.get("command_center_signoff_archive_verification_report_hash"),
        },
        {
            "component_type": "command_center_final_handoff",
            "path": "packages/command-center-final-handoff.zip",
            "package_type": COMMAND_CENTER_FINAL_HANDOFF_PACKAGE_TYPE,
            "zip_sha256": source.get("command_center_final_handoff_zip_sha256"),
            "zip_size_bytes": source.get("command_center_final_handoff_zip_size_bytes"),
            "manifest_hash": source.get("command_center_final_handoff_manifest_hash"),
            "verification_report_hash": source.get("command_center_final_handoff_verification_report_hash"),
        },
    ]
    if rows != expected:
        return False
    return all(
        row["zip_sha256"] == _sha256_bytes(archive.read(row["path"])) and int(row["zip_size_bytes"] or -1) == len(archive.read(row["path"]))
        for row in expected
    )


def _participant_from_binding(evidence_id: str, response_id: str, binding: dict[str, Any], index_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "response_id": response_id,
        "reviewer": binding.get("reviewer"),
        "organization": binding.get("organization"),
        "role": binding.get("role"),
        "decision": binding.get("decision"),
        "reviewer_identity_hash": binding.get("reviewer_identity_hash"),
        "decision_hash": binding.get("decision_hash"),
        "response_binding_hash": binding.get("integrity_hash"),
        "accepted_evidence_verification_hash": index_row.get("verification_report_hash"),
    }


def _matrix_rows(participants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(participants, key=lambda row: (str(row.get("role") or ""), str(row.get("response_id") or "")))


def _findings_rows(responses: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for response_id, bundle in sorted(responses.items()):
        for index, finding in enumerate(bundle["response"].get("findings") or [], start=1):
            if not isinstance(finding, dict):
                continue
            rows.append(
                {
                    "response_id": response_id,
                    "finding_id": str(finding.get("finding_id") or f"finding-{index:03d}"),
                    "severity": str(finding.get("severity") or "info").lower(),
                    "category": str(finding.get("category") or "general"),
                    "summary": str(finding.get("summary") or "")[:500],
                    "finding_hash": stable_hash(finding),
                }
            )
    return rows


def _quorum_result(policy: dict[str, Any], participants: list[dict[str, Any]], responses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    accepted = [row for row in participants if row.get("decision") == "accepted"]
    roles = {str(row.get("role") or "") for row in accepted}
    organizations = {str(row.get("organization") or "") for row in accepted}
    required_roles = set(policy.get("required_roles") or ["continuity_owner", "operations_owner"])
    blockers: list[str] = []
    if len(accepted) < int(policy.get("min_accepted_count") or 2):
        blockers.append("min_accepted_count")
    if len(organizations) < int(policy.get("min_organization_count") or 2):
        blockers.append("min_organization_count")
    missing_roles = sorted(required_roles - roles)
    if missing_roles:
        blockers.append("required_roles")
    decisions = [bundle["binding"].get("decision") for bundle in responses.values()]
    if policy.get("block_on_rejected", True) and "rejected" in decisions:
        blockers.append("rejected_response")
    if policy.get("block_on_needs_changes", True) and "needs_changes" in decisions:
        blockers.append("needs_changes_response")
    critical = any(str(finding.get("severity") or "").lower() == "critical" for bundle in responses.values() for finding in bundle["response"].get("findings") or [] if isinstance(finding, dict))
    if policy.get("block_on_critical_findings", True) and critical:
        blockers.append("critical_finding")
    return {
        "status": "blocked" if blockers else "ready_for_signoff",
        "accepted_count": len(accepted),
        "organization_count": len(organizations),
        "required_roles": sorted(required_roles),
        "missing_roles": missing_roles,
        "blockers": blockers,
    }


def _response_public_projection(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "package_type": f"{RESPONSE_PACKAGE_TYPE}_public_projection",
        "program_id": response.get("program_id"),
        "response_id": response.get("response_id"),
        "reviewer": response.get("reviewer"),
        "organization": response.get("organization"),
        "role": response.get("role"),
        "decision": response.get("decision"),
        "findings": response.get("findings") or [],
        "created_at": response.get("created_at"),
    }


def _reviewer_identity(response: dict[str, Any]) -> dict[str, Any]:
    return {"reviewer": response.get("reviewer"), "organization": response.get("organization"), "role": response.get("role")}


def _source_projection(source: dict[str, Any]) -> dict[str, Any]:
    return {field: source.get(field) for field in SOURCE_FIELDS}


def _response_payload_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in response.items() if key not in {"payload_hash", "integrity_hash"}})


def _with_integrity(doc: dict[str, Any]) -> dict[str, Any]:
    output = dict(doc)
    output["integrity_hash"] = _integrity_hash(output)
    return output


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], required: set[str], prefix: str) -> list[dict[str, Any]]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = required - {"manifest.json"}
    checks = [
        _check(f"{prefix}_manifest_integrity", _integrity_ok(manifest), "Manifest integrity is valid."),
        _check(f"{prefix}_manifest_files_exact", declared == expected, "Manifest files match fixed entries.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
    ]
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in expected:
            continue
        data = archive.read(rel)
        checks.append(_check(f"{prefix}_manifest_file_{_safe_key(rel)}", row.get("sha256") == _sha256_bytes(data) and int(row.get("size_bytes") or -1) == len(data), "Manifest file hash and size match ZIP entry."))
    return checks


def _history_checks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [_check("urpccca_history_required", False, "Signoff history exists.")]
    checks: list[dict[str, Any]] = []
    previous = ""
    for index, row in enumerate(rows, start=1):
        expected_payload = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in {**row, "payload_hash": expected_payload}.items() if key != "event_hash"})
        checks.extend(
            [
                _check(f"urpccca_history_{index:03d}_previous", str(row.get("previous_event_hash") or "") == previous, "History previous hash matches."),
                _check(f"urpccca_history_{index:03d}_payload", row.get("payload_hash") == expected_payload, "History payload hash matches."),
                _check(f"urpccca_history_{index:03d}_event", row.get("event_hash") == expected_event, "History event hash matches."),
            ]
        )
        previous = str(row.get("event_hash") or "")
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str], check_id: str) -> dict[str, Any]:
    return archive_redaction_check(archive, names, check_id=check_id)


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(value: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower() or "item"


def _prefix_checks(checks: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    return [{**row, "check_id": f"{prefix}_{row.get('check_id')}"} for row in checks]


def _has_blockers(checks: list[dict[str, Any]]) -> bool:
    return any(row.get("status") == "failed" and row.get("severity") == "blocking" for row in checks)


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], package_type: str, *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    return build_verification_report(
        package_type=package_type,
        checks=checks,
        summary=summary,
        schema_version=SCHEMA_VERSION,
    )
