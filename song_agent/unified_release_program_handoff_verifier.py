from __future__ import annotations

import json
import re
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
    sha256_or_integrity as _sha256_or_integrity,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_release_program_operations_verifier import (
    UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_operations_package,
)
from song_agent.unified_release_program_verifier import (
    UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_package,
)


UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE = "musicforge_unified_release_program_handoff_archive"
UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_handoff_verification"
UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE = "musicforge_unified_release_program_handoff_external_evidence_manifest"
UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE = "musicforge_unified_release_program_review_pack"
UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_review_pack_verification"
UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE = "musicforge_unified_release_program_accepted_evidence"
UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_accepted_evidence_verification"
UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_review_response_verification"
UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION = 1

HANDOFF_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "program-handoff-report.json",
    "evidence-inventory.json",
    "recipient-guide.md",
    "decision-board.json",
    "conflict-report.json",
    "accepted-evidence-index.json",
    "handoff-readiness-matrix.json",
    "handoff-gap-plan.json",
    "external-evidence-manifest.json",
    "program-handoff-signoff.json",
    "program-handoff-signoff-binding-summary.json",
    "program-handoff-history.jsonl",
    "verification-summaries/program-verification-summary.json",
    "verification-summaries/operations-verification-summary.json",
    "verification-summaries/accepted-evidence-verification-summaries.json",
}

REVIEW_PACK_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "review-pack-report.json",
    "review-pack-binding-summary.json",
    "recipient-guide.md",
    "data/handoff-summary.json",
    "data/evidence-inventory-public.json",
    "data/risk-summary-public.json",
    "data/reviewer-form-template.json",
}

ACCEPTED_EVIDENCE_REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "original-response-public.json",
    "response-verification-summary.json",
    "response-binding-summary.json",
    "accepted-evidence-report.json",
    "accepted-evidence-binding-summary.json",
}

def verify_unified_release_program_handoff_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_accepted: bool = False,
    require_signed: bool = False,
    external_evidence_manifest_path: Path | str | None = None,
    handoff_signoff_binding_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urph_kernel",
                required_entries=frozenset(HANDOFF_REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE, _check("urph_zip_exists", False, "Program Handoff Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urph_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            extra = sorted(name_set - HANDOFF_REQUIRED_ENTRIES)
            missing = sorted(HANDOFF_REQUIRED_ENTRIES - name_set)
            checks.extend(
                [
                    _check("urph_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urph_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urph_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urph_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urph_no_nested_zip", not nested, "Handoff Archive does not embed ZIP packages.", {"nested": nested}),
                    _check("urph_allowed_entries", not extra, "Handoff Archive contains only fixed entries.", {"extra": extra}),
                    _check("urph_required_entries", not missing, "Handoff Archive contains required entries.", {"missing": missing}),
                ]
            )
            if any(row["status"] == "failed" for row in checks):
                return _finish(checks, summary, UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "program-handoff-report.json")
            inventory = _read_json_entry(archive, "evidence-inventory.json")
            decision = _read_json_entry(archive, "decision-board.json")
            conflicts = _read_json_entry(archive, "conflict-report.json")
            accepted_index = _read_json_entry(archive, "accepted-evidence-index.json")
            readiness = _read_json_entry(archive, "handoff-readiness-matrix.json")
            gap = _read_json_entry(archive, "handoff-gap-plan.json")
            external_manifest = _read_json_entry(archive, "external-evidence-manifest.json")
            signoff = _read_json_entry(archive, "program-handoff-signoff.json")
            binding = _read_json_entry(archive, "program-handoff-signoff-binding-summary.json")
            program_summary = _read_json_entry(archive, "verification-summaries/program-verification-summary.json")
            operations_summary = _read_json_entry(archive, "verification-summaries/operations-verification-summary.json")
            accepted_summary = _read_json_entry(archive, "verification-summaries/accepted-evidence-verification-summaries.json")
            history = _parse_jsonl(archive.read("program-handoff-history.jsonl").decode("utf-8"))
            summary.update(
                {
                    "program_id": manifest.get("program_id") or report.get("program_id"),
                    "handoff_id": manifest.get("handoff_id") or report.get("handoff_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": report.get("status"),
                    "signed": signoff.get("status") == "signed",
                    "accepted_count": int((decision.get("readiness") or {}).get("accepted_count") or 0),
                    "quorum_status": (decision.get("readiness") or {}).get("status"),
                }
            )
            checks.extend(_manifest_checks(archive, manifest, name_set, HANDOFF_REQUIRED_ENTRIES, "urph"))
            checks.extend(
                [
                    _check("urph_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urph_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            for check_id, doc in (
                ("urph_manifest_integrity", manifest),
                ("urph_report_integrity", report),
                ("urph_inventory_integrity", inventory),
                ("urph_decision_integrity", decision),
                ("urph_conflict_integrity", conflicts),
                ("urph_accepted_index_integrity", accepted_index),
                ("urph_readiness_integrity", readiness),
                ("urph_gap_integrity", gap),
                ("urph_external_manifest_integrity", external_manifest),
                ("urph_signoff_integrity", signoff),
                ("urph_signoff_binding_integrity", binding),
                ("urph_program_summary_integrity", program_summary),
                ("urph_operations_summary_integrity", operations_summary),
                ("urph_accepted_summary_integrity", accepted_summary),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_handoff_document_binding_checks(manifest, report, inventory, decision, conflicts, accepted_index, readiness, gap, external_manifest, signoff, binding, program_summary, operations_summary, accepted_summary))
            checks.extend(_history_checks("urph_history", history))
            checks.extend(_handoff_signoff_binding_checks(binding, signoff, history, report, decision, accepted_index, external_manifest, require=require_signed))
            checks.extend(_external_handoff_binding_checks(handoff_signoff_binding_path, binding, signoff, history, report, decision, accepted_index, external_manifest, require=require_signed))
            external_state = _external_handoff_state(external_evidence_manifest_path, external_manifest, require=require_current or require_accepted)
            checks.extend(external_state.pop("checks"))
            checks.extend(_handoff_semantic_checks(report, inventory, decision, accepted_index, program_summary, operations_summary, accepted_summary, external_state, require_current=require_current, require_accepted=require_accepted, require_signed=require_signed))
            checks.append(_redaction_check(archive, names, "urph_redaction_scan"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urph_zip_readable", False, "Handoff Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE)


def verify_unified_release_program_review_pack_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    max_zip_size_mb: int = 64,
    max_uncompressed_size_mb: int = 128,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    del strict
    return _verify_simple_fixed_package(
        zip_path,
        package_type=UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE,
        verification_package_type=UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_VERIFICATION_PACKAGE_TYPE,
        required_entries=REVIEW_PACK_REQUIRED_ENTRIES,
        prefix="urprp",
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        report_entry="review-pack-report.json",
    )


def verify_unified_release_program_accepted_evidence_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_accepted: bool = False,
    response_verification_report_path: Path | str | None = None,
    response_binding_summary_path: Path | str | None = None,
    max_zip_size_mb: int = 64,
    max_uncompressed_size_mb: int = 128,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpae_kernel",
                required_entries=frozenset(ACCEPTED_EVIDENCE_REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, _check("urpae_zip_exists", False, "Accepted Evidence ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpae_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.extend(
                [
                    _check("urpae_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpae_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpae_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpae_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpae_no_nested_zip", not nested, "Accepted Evidence ZIP does not embed ZIP packages.", {"nested": nested}),
                    _check("urpae_allowed_entries", not sorted(name_set - ACCEPTED_EVIDENCE_REQUIRED_ENTRIES), "Accepted Evidence ZIP contains only fixed entries.", {"extra": sorted(name_set - ACCEPTED_EVIDENCE_REQUIRED_ENTRIES)}),
                    _check("urpae_required_entries", not sorted(ACCEPTED_EVIDENCE_REQUIRED_ENTRIES - name_set), "Accepted Evidence ZIP contains required entries.", {"missing": sorted(ACCEPTED_EVIDENCE_REQUIRED_ENTRIES - name_set)}),
                ]
            )
            if any(row["status"] == "failed" for row in checks):
                return _finish(checks, summary, UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE)
            manifest = _read_json_entry(archive, "manifest.json")
            public_response = _read_json_entry(archive, "original-response-public.json")
            response_summary = _read_json_entry(archive, "response-verification-summary.json")
            response_binding = _read_json_entry(archive, "response-binding-summary.json")
            report = _read_json_entry(archive, "accepted-evidence-report.json")
            evidence_binding = _read_json_entry(archive, "accepted-evidence-binding-summary.json")
            summary.update(
                {
                    "program_id": report.get("program_id"),
                    "handoff_id": report.get("handoff_id"),
                    "evidence_id": report.get("evidence_id"),
                    "response_id": report.get("response_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "reviewer_role": (report.get("reviewer") or {}).get("role"),
                    "organization": (report.get("reviewer") or {}).get("organization"),
                    "decision": report.get("decision"),
                }
            )
            checks.extend(_manifest_checks(archive, manifest, name_set, ACCEPTED_EVIDENCE_REQUIRED_ENTRIES, "urpae"))
            checks.append(_check("urpae_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE, "Manifest package type is valid."))
            for check_id, doc in (
                ("urpae_manifest_integrity", manifest),
                ("urpae_public_response_integrity", public_response),
                ("urpae_response_summary_integrity", response_summary),
                ("urpae_response_binding_integrity", response_binding),
                ("urpae_report_integrity", report),
                ("urpae_binding_integrity", evidence_binding),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_accepted_evidence_semantic_checks(public_response, response_summary, response_binding, report, evidence_binding, require_accepted=require_accepted))
            checks.extend(_external_response_binding_checks(response_verification_report_path, response_binding_summary_path, response_summary, response_binding, public_response, report, require=require_accepted))
            checks.append(_redaction_check(archive, names, "urpae_redaction_scan"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpae_zip_readable", False, "Accepted Evidence ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE)


def write_unified_release_program_handoff_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def write_unified_release_program_review_pack_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def write_unified_release_program_accepted_evidence_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_handoff_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def unified_release_program_review_pack_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def unified_release_program_accepted_evidence_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _verify_simple_fixed_package(
    zip_path: Path | str,
    *,
    package_type: str,
    verification_package_type: str,
    required_entries: set[str],
    prefix: str,
    report_entry: str,
    max_zip_size_mb: int,
    max_uncompressed_size_mb: int,
    max_entry_count: int,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=package_type,
                verification_package_type=verification_package_type,
                check_prefix=f"{prefix}_kernel",
                required_entries=frozenset(required_entries),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, verification_package_type, _check(f"{prefix}_zip_exists", False, "ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check(f"{prefix}_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            checks.extend(
                [
                    _check(f"{prefix}_no_duplicate_entries", not sorted({name for name in names if names.count(name) > 1}), "ZIP contains no duplicate entries."),
                    _check(f"{prefix}_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit."),
                    _check(f"{prefix}_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check(f"{prefix}_entry_paths_safe", not [name for name in names if not _is_safe_entry(name)], "ZIP entries are safe POSIX relative paths."),
                    _check(f"{prefix}_allowed_entries", not sorted(name_set - required_entries), "ZIP contains only fixed entries.", {"extra": sorted(name_set - required_entries)}),
                    _check(f"{prefix}_required_entries", not sorted(required_entries - name_set), "ZIP contains required entries.", {"missing": sorted(required_entries - name_set)}),
                ]
            )
            if any(row["status"] == "failed" for row in checks):
                return _finish(checks, summary, verification_package_type)
            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, report_entry)
            binding = _read_json_entry(archive, "review-pack-binding-summary.json") if "review-pack-binding-summary.json" in name_set else {}
            summary.update({"manifest_hash": manifest.get("integrity_hash"), "program_id": report.get("program_id"), "handoff_id": report.get("handoff_id")})
            checks.extend(_manifest_checks(archive, manifest, name_set, required_entries, prefix))
            checks.append(_check(f"{prefix}_manifest_package_type", manifest.get("package_type") == package_type, "Manifest package type is valid."))
            checks.append(_check(f"{prefix}_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            checks.append(_check(f"{prefix}_report_integrity", _integrity_ok(report), "Report integrity hash is valid."))
            if binding:
                checks.append(_check(f"{prefix}_binding_integrity", _integrity_ok(binding), "Binding integrity hash is valid."))
            checks.append(_redaction_check(archive, names, f"{prefix}_redaction_scan"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check(f"{prefix}_zip_readable", False, "ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary, verification_package_type)


def _external_handoff_state(path: Path | str | None, archive_manifest: dict[str, Any], *, require: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    state: dict[str, Any] = {"checks": checks, "program": {}, "operations": {}, "accepted": []}
    if not path:
        if require:
            checks.append(_check("urph_external_evidence_manifest_required", False, "External Handoff evidence manifest is required."))
        return state
    manifest_path = Path(path)
    checks.append(_check("urph_external_evidence_manifest_exists", manifest_path.exists() and manifest_path.is_file(), "External Handoff evidence manifest exists."))
    if not manifest_path.exists() or not manifest_path.is_file():
        return state
    external = read_json(manifest_path)
    state["external_manifest"] = external
    checks.extend(
        [
            _check("urph_external_evidence_manifest_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, "External Handoff evidence manifest package type is valid."),
            _check("urph_external_evidence_manifest_integrity", _integrity_ok(external), "External Handoff evidence manifest integrity hash is valid."),
            _check("urph_external_evidence_manifest_hash", _public_external_manifest(external).get("integrity_hash") == archive_manifest.get("integrity_hash"), "External Handoff evidence manifest public projection matches archive copy."),
        ]
    )
    rows = [row for row in external.get("items", []) if isinstance(row, dict)]
    by_type = {str(row.get("evidence_type") or ""): row for row in rows}
    checks.extend(_external_program_checks(by_type.get("unified_release_program"), require=require, state=state))
    checks.extend(_external_operations_checks(by_type.get("unified_release_program_operations"), by_type.get("unified_release_program"), require=require, state=state))
    accepted_rows = [row for row in rows if row.get("evidence_type") == "program_accepted_evidence"]
    if require and not accepted_rows:
        checks.append(_check("urph_external_accepted_evidence_required", False, "Accepted evidence is required."))
    for index, row in enumerate(accepted_rows, start=1):
        checks.extend(_external_accepted_evidence_checks(row, state=state, index=index, require=require))
    return state


def _external_program_checks(row: dict[str, Any] | None, *, require: bool, state: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not row:
        if require:
            checks.append(_check("urph_external_program_required", False, "External Program evidence is required."))
        return checks
    zip_path = Path(str(row.get("program_zip") or row.get("program_zip_path") or ""))
    report_path = Path(str(row.get("program_verification_report") or row.get("program_verification_report_path") or ""))
    binding_path = Path(str(row.get("program_signoff_binding") or row.get("program_signoff_binding_path") or ""))
    evidence_manifest_path = Path(str(row.get("program_external_evidence_manifest") or row.get("external_evidence_manifest") or row.get("external_evidence_manifest_path") or ""))
    checks.extend(_path_checks("urph_external_program", {"zip": zip_path, "verification": report_path, "binding": binding_path, "external_manifest": evidence_manifest_path}))
    if any(check["status"] == "failed" for check in checks):
        return checks
    external_report = read_json(report_path)
    runtime = verify_unified_release_program_package(zip_path, strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=evidence_manifest_path, program_signoff_binding_path=binding_path)
    state["program"] = {
        "zip_sha256": _sha256_path(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "manifest_hash": runtime.get("manifest_hash"),
        "verification_hash": _integrity_hash(external_report),
        "verification_status": external_report.get("status"),
        "runtime_status": runtime.get("status"),
        "binding_hash": _integrity_hash(read_json(binding_path)),
        "external_manifest_hash": _integrity_hash(read_json(evidence_manifest_path)),
    }
    checks.extend(
        [
            _check("urph_external_program_verification_package_type", external_report.get("package_type") == UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, "Program verification package type is valid."),
            _check("urph_external_program_verification_integrity", _integrity_ok(external_report), "Program verification report integrity is valid."),
            _check("urph_external_program_runtime_passed", runtime.get("status") == "passed", "Current Program runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urph_external_program_report_passed", external_report.get("status") == "passed", "Program verification report passed."),
            _check("urph_external_program_zip_sha256", external_report.get("zip_sha256") == runtime.get("zip_sha256") == state["program"]["zip_sha256"], "Program ZIP hash matches runtime and report."),
            _check("urph_external_program_manifest_hash", external_report.get("manifest_hash") == runtime.get("manifest_hash"), "Program manifest hash matches runtime and report."),
        ]
    )
    return checks


def _external_operations_checks(row: dict[str, Any] | None, program_row: dict[str, Any] | None, *, require: bool, state: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not row:
        if require:
            checks.append(_check("urph_external_operations_required", False, "External Program Operations evidence is required."))
        return checks
    zip_path = Path(str(row.get("operations_zip") or row.get("operations_archive_zip") or row.get("zip_path") or ""))
    report_path = Path(str(row.get("operations_verification_report") or row.get("operations_archive_verification_report") or row.get("verification_report_path") or ""))
    program_zip = Path(str(row.get("program_zip") or (program_row or {}).get("program_zip") or ""))
    program_report = Path(str(row.get("program_verification_report") or (program_row or {}).get("program_verification_report") or ""))
    program_binding = Path(str(row.get("program_signoff_binding") or (program_row or {}).get("program_signoff_binding") or ""))
    external_manifest = Path(str(row.get("program_external_evidence_manifest") or row.get("external_evidence_manifest") or (program_row or {}).get("program_external_evidence_manifest") or (program_row or {}).get("external_evidence_manifest") or ""))
    checks.extend(_path_checks("urph_external_operations", {"zip": zip_path, "verification": report_path, "program_zip": program_zip, "program_verification": program_report, "program_binding": program_binding, "program_external_manifest": external_manifest}))
    if any(check["status"] == "failed" for check in checks):
        return checks
    external_report = read_json(report_path)
    runtime = verify_unified_release_program_operations_package(
        zip_path,
        strict=True,
        require_current=True,
        require_signed_program=True,
        require_continuous_review_clear=True,
        require_lifecycle_audit=True,
        program_zip_path=program_zip,
        program_verification_report_path=program_report,
        program_signoff_binding_path=program_binding,
        external_evidence_manifest_path=external_manifest,
    )
    state["operations"] = {
        "zip_sha256": _sha256_path(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "manifest_hash": runtime.get("manifest_hash"),
        "verification_hash": _integrity_hash(external_report),
        "verification_status": external_report.get("status"),
        "runtime_status": runtime.get("status"),
    }
    checks.extend(
        [
            _check("urph_external_operations_verification_package_type", external_report.get("package_type") == UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, "Operations verification package type is valid."),
            _check("urph_external_operations_verification_integrity", _integrity_ok(external_report), "Operations verification report integrity is valid."),
            _check("urph_external_operations_runtime_passed", runtime.get("status") == "passed", "Current Operations runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check("urph_external_operations_report_passed", external_report.get("status") == "passed", "Operations verification report passed."),
            _check("urph_external_operations_zip_sha256", external_report.get("zip_sha256") == runtime.get("zip_sha256") == state["operations"]["zip_sha256"], "Operations ZIP hash matches runtime and report."),
            _check("urph_external_operations_manifest_hash", external_report.get("manifest_hash") == runtime.get("manifest_hash"), "Operations manifest hash matches runtime and report."),
        ]
    )
    return checks


def _external_accepted_evidence_checks(row: dict[str, Any], *, state: dict[str, Any], index: int, require: bool) -> list[dict[str, Any]]:
    prefix = f"urph_external_accepted_{index:03d}"
    zip_path = Path(str(row.get("accepted_evidence_zip") or row.get("zip_path") or ""))
    report_path = Path(str(row.get("accepted_evidence_verification_report") or row.get("verification_report_path") or ""))
    response_verification = Path(str(row.get("response_verification_report") or row.get("response_verification_report_path") or ""))
    response_binding = Path(str(row.get("response_binding_summary") or row.get("response_binding_summary_path") or ""))
    checks = _path_checks(prefix, {"zip": zip_path, "verification": report_path, "response_verification": response_verification, "response_binding": response_binding})
    if any(check["status"] == "failed" for check in checks):
        return checks
    external_report = read_json(report_path)
    runtime = verify_unified_release_program_accepted_evidence_package(
        zip_path,
        strict=True,
        require_accepted=require,
        response_verification_report_path=response_verification,
        response_binding_summary_path=response_binding,
    )
    item = {
        "evidence_id": runtime.get("summary", {}).get("evidence_id") or row.get("evidence_id"),
        "response_id": runtime.get("summary", {}).get("response_id") or row.get("response_id"),
        "zip_sha256": _sha256_path(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "manifest_hash": runtime.get("manifest_hash"),
        "verification_hash": _integrity_hash(external_report),
        "verification_status": external_report.get("status"),
        "runtime_status": runtime.get("status"),
        "reviewer_role": (runtime.get("summary") or {}).get("reviewer_role"),
        "organization": (runtime.get("summary") or {}).get("organization"),
        "decision": (runtime.get("summary") or {}).get("decision"),
    }
    state.setdefault("accepted", []).append(item)
    checks.extend(
        [
            _check(f"{prefix}_verification_package_type", external_report.get("package_type") == UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, "Accepted Evidence verification package type is valid."),
            _check(f"{prefix}_verification_integrity", _integrity_ok(external_report), "Accepted Evidence verification report integrity is valid."),
            _check(f"{prefix}_runtime_passed", runtime.get("status") == "passed", "Accepted Evidence runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
            _check(f"{prefix}_report_passed", external_report.get("status") == "passed", "Accepted Evidence verification report passed."),
            _check(f"{prefix}_zip_sha256", external_report.get("zip_sha256") == runtime.get("zip_sha256") == item["zip_sha256"], "Accepted Evidence ZIP hash matches runtime and report."),
            _check(f"{prefix}_manifest_hash", external_report.get("manifest_hash") == runtime.get("manifest_hash"), "Accepted Evidence manifest hash matches runtime and report."),
        ]
    )
    return checks


def _path_checks(prefix: str, paths: dict[str, Path]) -> list[dict[str, Any]]:
    return [_check(f"{prefix}_{key}_exists", path.exists() and path.is_file(), f"{key} exists.", {"path": str(path)}) for key, path in paths.items()]


def _handoff_semantic_checks(
    report: dict[str, Any],
    inventory: dict[str, Any],
    decision: dict[str, Any],
    accepted_index: dict[str, Any],
    program_summary: dict[str, Any],
    operations_summary: dict[str, Any],
    accepted_summary: dict[str, Any],
    external: dict[str, Any],
    *,
    require_current: bool,
    require_accepted: bool,
    require_signed: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    program = external.get("program") or {}
    operations = external.get("operations") or {}
    accepted = external.get("accepted") or []
    if external.get("external_manifest"):
        checks.extend(
            [
                _check("urph_program_summary_runtime_binding", not program or program_summary.get("zip_sha256") == program.get("zip_sha256"), "Program summary binds runtime Program ZIP."),
                _check("urph_program_summary_verification_binding", not program or program_summary.get("verification_hash") == program.get("verification_hash"), "Program summary binds runtime Program verification report."),
                _check("urph_operations_summary_runtime_binding", not operations or operations_summary.get("zip_sha256") == operations.get("zip_sha256"), "Operations summary binds runtime Operations ZIP."),
                _check("urph_operations_summary_verification_binding", not operations or operations_summary.get("verification_hash") == operations.get("verification_hash"), "Operations summary binds runtime Operations verification report."),
            ]
        )
    inventory_items = [row for row in inventory.get("items", []) if isinstance(row, dict)]
    inventory_by_type = {row.get("evidence_type"): row for row in inventory_items}
    checks.extend(
        [
            _check("urph_inventory_has_program", "unified_release_program" in inventory_by_type, "Evidence inventory includes Program."),
            _check("urph_inventory_has_operations", "unified_release_program_operations" in inventory_by_type, "Evidence inventory includes Operations."),
        ]
    )
    accepted_rows = [row for row in accepted_index.get("items", []) if isinstance(row, dict)]
    accepted_external_by_id = {row.get("evidence_id"): row for row in accepted}
    for row in accepted_rows:
        ext = accepted_external_by_id.get(row.get("evidence_id"))
        if require_accepted:
            checks.append(_check(f"urph_accepted_external_{_safe_check_key(str(row.get('evidence_id')))}", bool(ext), "Accepted evidence has external verification proof."))
        if ext:
            checks.extend(
                [
                    _check(f"urph_accepted_role_{_safe_check_key(str(row.get('evidence_id')))}", row.get("role") == ext.get("reviewer_role"), "Accepted evidence role matches external proof."),
                    _check(f"urph_accepted_org_{_safe_check_key(str(row.get('evidence_id')))}", row.get("organization") == ext.get("organization"), "Accepted evidence organization matches external proof."),
                    _check(f"urph_accepted_decision_{_safe_check_key(str(row.get('evidence_id')))}", row.get("decision") == ext.get("decision"), "Accepted evidence decision matches external proof."),
                ]
            )
    required_roles = set((decision.get("policy") or {}).get("required_roles") or [])
    roles = {(row.get("reviewer_role") or row.get("role")) for row in accepted if row.get("decision") in {"accepted", "accepted_with_notes"}}
    if require_accepted:
        checks.append(_check("urph_require_accepted_count", len(accepted) >= int((decision.get("policy") or {}).get("minimum_acceptances") or 1), "Required accepted evidence count is met."))
        checks.append(_check("urph_require_accepted_roles", required_roles <= roles, "Required accepted evidence roles are met.", {"missing_roles": sorted(required_roles - roles)}))
        checks.append(_check("urph_require_decision_ready", (decision.get("readiness") or {}).get("status") == "ready_for_signoff", "Decision Board is ready for signoff."))
    if require_current:
        checks.append(_check("urph_require_current_program", program.get("runtime_status") == "passed" and program.get("verification_status") == "passed", "Current Program evidence passed."))
        checks.append(_check("urph_require_current_operations", operations.get("runtime_status") == "passed" and operations.get("verification_status") == "passed", "Current Operations evidence passed."))
    if require_signed:
        checks.append(_check("urph_require_signed_status", report.get("status") == "signed", "Program Handoff report is signed."))
    checks.append(_check("urph_accepted_summary_count", int(accepted_summary.get("summary", {}).get("accepted_count") or 0) == len(accepted_rows), "Accepted evidence verification summary count matches index."))
    return checks


def _accepted_evidence_semantic_checks(
    public_response: dict[str, Any],
    response_summary: dict[str, Any],
    response_binding: dict[str, Any],
    report: dict[str, Any],
    evidence_binding: dict[str, Any],
    *,
    require_accepted: bool,
) -> list[dict[str, Any]]:
    reviewer = report.get("reviewer") if isinstance(report.get("reviewer"), dict) else {}
    return [
        _check("urpae_public_role_binding", public_response.get("reviewer_role") == reviewer.get("role") == response_binding.get("reviewer_role"), "Reviewer role is derived from original response binding."),
        _check("urpae_public_org_binding", public_response.get("organization") == reviewer.get("organization") == response_binding.get("organization"), "Reviewer organization is derived from original response binding."),
        _check("urpae_decision_binding", public_response.get("decision") == report.get("decision") == response_binding.get("decision"), "Decision is derived from original response binding."),
        _check("urpae_response_payload_hash", response_summary.get("response_payload_hash") == response_binding.get("response_payload_hash") == report.get("source", {}).get("response_payload_hash"), "Response payload hash is bound."),
        _check("urpae_binding_response_hash", evidence_binding.get("response_binding_hash") == response_binding.get("integrity_hash"), "Accepted evidence binding matches response binding."),
        _check("urpae_binding_report_hash", evidence_binding.get("accepted_evidence_report_hash") == report.get("integrity_hash"), "Accepted evidence binding matches report."),
        _check("urpae_require_accepted", (not require_accepted) or report.get("decision") in {"accepted", "accepted_with_notes"}, "Accepted evidence decision is accepted."),
    ]


def _external_response_binding_checks(
    response_verification_report_path: Path | str | None,
    response_binding_summary_path: Path | str | None,
    response_summary: dict[str, Any],
    response_binding: dict[str, Any],
    public_response: dict[str, Any],
    report: dict[str, Any],
    *,
    require: bool,
) -> list[dict[str, Any]]:
    if not response_verification_report_path or not response_binding_summary_path:
        if require:
            return [_check("urpae_external_response_proof_required", False, "External response verification and binding proof are required.")]
        return []
    verification_path = Path(response_verification_report_path)
    binding_path = Path(response_binding_summary_path)
    checks = _path_checks("urpae_external_response", {"verification": verification_path, "binding": binding_path})
    if any(row["status"] == "failed" for row in checks):
        return checks
    external_verification = read_json(verification_path)
    external_binding = read_json(binding_path)
    checks.extend(
        [
            _check("urpae_external_response_verification_package_type", external_verification.get("package_type") == UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE, "Response verification package type is valid."),
            _check("urpae_external_response_verification_integrity", _integrity_ok(external_verification), "Response verification integrity is valid."),
            _check("urpae_external_response_binding_integrity", _integrity_ok(external_binding), "Response binding integrity is valid."),
            _check("urpae_external_response_verification_hash", external_verification.get("integrity_hash") == response_summary.get("response_verification_hash"), "Response verification summary matches external report."),
            _check("urpae_external_response_binding_hash", external_binding.get("integrity_hash") == response_binding.get("integrity_hash"), "Response binding summary matches external binding."),
            _check("urpae_external_response_role", external_binding.get("reviewer_role") == public_response.get("reviewer_role") == (report.get("reviewer") or {}).get("role"), "Reviewer role matches external response binding."),
            _check("urpae_external_response_decision", external_binding.get("decision") == public_response.get("decision") == report.get("decision"), "Decision matches external response binding."),
        ]
    )
    return checks


def _handoff_document_binding_checks(
    manifest: dict[str, Any],
    report: dict[str, Any],
    inventory: dict[str, Any],
    decision: dict[str, Any],
    conflicts: dict[str, Any],
    accepted_index: dict[str, Any],
    readiness: dict[str, Any],
    gap: dict[str, Any],
    external_manifest: dict[str, Any],
    signoff: dict[str, Any],
    binding: dict[str, Any],
    program_summary: dict[str, Any],
    operations_summary: dict[str, Any],
    accepted_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    docs = {
        "handoff_report_hash": report,
        "evidence_inventory_hash": inventory,
        "decision_board_hash": decision,
        "conflict_report_hash": conflicts,
        "accepted_evidence_index_hash": accepted_index,
        "readiness_matrix_hash": readiness,
        "gap_plan_hash": gap,
        "external_evidence_manifest_hash": external_manifest,
        "handoff_signoff_hash": signoff,
        "handoff_signoff_binding_hash": binding,
        "program_verification_summary_hash": program_summary,
        "operations_verification_summary_hash": operations_summary,
        "accepted_evidence_verification_summary_hash": accepted_summary,
    }
    return [_check(f"urph_manifest_{key}", source.get(key) == doc.get("integrity_hash"), f"Manifest binds {key}.") for key, doc in docs.items()]


def _handoff_signoff_binding_checks(binding: dict[str, Any], signoff: dict[str, Any], history: list[dict[str, Any]], report: dict[str, Any], decision: dict[str, Any], accepted_index: dict[str, Any], external_manifest: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    if not binding:
        return [_check("urph_signoff_binding_required", not require, "Handoff signoff binding is present when required.")]
    signoff_event = next((row for row in reversed(history) if row.get("event_type") == "unified_release_program_handoff_signoff_created"), {})
    return [
        _check("urph_signoff_binding_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
        _check("urph_signoff_binding_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Signoff binding matches signed_by."),
        _check("urph_signoff_binding_role", binding.get("role") == signoff.get("role"), "Signoff binding matches role."),
        _check("urph_signoff_binding_reason", binding.get("reason") == signoff.get("reason"), "Signoff binding matches reason."),
        _check("urph_signoff_binding_history_event", binding.get("latest_history_event_hash") == signoff_event.get("event_hash"), "Signoff binding matches latest signoff history event."),
        _check("urph_signoff_binding_report_hash", binding.get("handoff_report_hash") == report.get("integrity_hash") == signoff.get("handoff_report_hash"), "Binding report hash matches."),
        _check("urph_signoff_binding_decision_hash", binding.get("decision_board_hash") == decision.get("integrity_hash") == signoff.get("decision_board_hash"), "Binding decision board hash matches."),
        _check("urph_signoff_binding_accepted_index_hash", binding.get("accepted_evidence_index_hash") == accepted_index.get("integrity_hash") == signoff.get("accepted_evidence_index_hash"), "Binding accepted index hash matches."),
        _check("urph_signoff_binding_external_manifest_hash", binding.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash") == signoff.get("external_evidence_manifest_hash"), "Binding external evidence manifest hash matches."),
    ]


def _public_external_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    public_items = []
    allowed_exact = {
        "evidence_id",
        "evidence_type",
        "component_id",
        "program_id",
        "handoff_id",
        "response_id",
        "role",
        "organization",
        "decision",
    }
    allowed_suffixes = ("_hash", "_sha256", "_size_bytes", "_status")
    for row in manifest.get("items", []):
        if not isinstance(row, dict):
            continue
        public_row = {}
        for key, value in row.items():
            if key in allowed_exact or key.endswith(allowed_suffixes):
                public_row[key] = value
        if "evidence_id" not in public_row and row.get("evidence_id"):
            public_row["evidence_id"] = row.get("evidence_id")
        if "evidence_type" not in public_row and row.get("evidence_type"):
            public_row["evidence_type"] = row.get("evidence_type")
        if "component_id" not in public_row and row.get("component_id"):
            public_row["component_id"] = row.get("component_id")
        public_items.append(public_row)
    public = {
        "schema_version": manifest.get("schema_version") or UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
        "package_type": manifest.get("package_type") or UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": manifest.get("program_id"),
        "handoff_id": manifest.get("handoff_id"),
        "created_at": manifest.get("created_at"),
        "items": public_items,
        "summary": {"item_count": len(public_items)},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public


def _external_handoff_binding_checks(path: Path | str | None, binding: dict[str, Any], signoff: dict[str, Any], history: list[dict[str, Any]], report: dict[str, Any], decision: dict[str, Any], accepted_index: dict[str, Any], external_manifest: dict[str, Any], *, require: bool) -> list[dict[str, Any]]:
    if not path:
        if require:
            return [_check("urph_external_signoff_binding_required", False, "External Handoff signoff binding proof is required.")]
        return []
    binding_path = Path(path)
    checks = [_check("urph_external_signoff_binding_exists", binding_path.exists() and binding_path.is_file(), "External Handoff signoff binding proof exists.")]
    if not binding_path.exists() or not binding_path.is_file():
        return checks
    external = read_json(binding_path)
    checks.extend(
        [
            _check("urph_external_signoff_binding_integrity", _integrity_ok(external), "External Handoff signoff binding integrity is valid."),
            _check("urph_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External Handoff signoff binding matches ZIP sidecar hash."),
            _check("urph_external_signoff_binding_signed_by", external.get("signed_by") == binding.get("signed_by") == signoff.get("signed_by"), "External Handoff signoff binding matches signed_by."),
            _check("urph_external_signoff_binding_role", external.get("role") == binding.get("role") == signoff.get("role"), "External Handoff signoff binding matches role."),
            _check("urph_external_signoff_binding_reason", external.get("reason") == binding.get("reason") == signoff.get("reason"), "External Handoff signoff binding matches reason."),
        ]
    )
    checks.extend(_handoff_signoff_binding_checks(external, signoff, history, report, decision, accepted_index, external_manifest, require=require))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str], expected_entries: set[str], prefix: str) -> list[dict[str, Any]]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    file_paths = {str(row.get("path")) for row in files}
    expected_files = expected_entries - {"manifest.json"}
    checks = [
        _check(f"{prefix}_manifest_files_exact", file_paths == expected_files, "Manifest files match fixed layout.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check(f"{prefix}_manifest_no_zip_entry_spoof", set(manifest.get("zip", {}).get("entries") or []) <= name_set, "Manifest ZIP entries do not spoof extra paths."),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            checks.append(_check(f"{prefix}_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP.", {"path": rel}))
            continue
        data = archive.read(rel)
        checks.append(_check(f"{prefix}_manifest_file_{_safe_check_key(rel)}_hash", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry.", {"path": rel}))
    return checks


def _history_checks(prefix: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    previous = ""
    for index, event in enumerate(rows):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"{prefix}_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History payload hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"{prefix}_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History hash chain is contiguous."))
        previous = str(event.get("event_hash") or "")
    return checks


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], package_type: str, first_check: dict[str, Any] | None = None) -> dict[str, Any]:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=package_type,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _parse_jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _redaction_check(archive: zipfile.ZipFile, names: list[str], check_id: str) -> dict[str, Any]:
    return archive_redaction_check(archive, names, check_id=check_id)


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"
