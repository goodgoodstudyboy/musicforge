# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import re as re
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
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_package as verify_unified_release_program_package


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
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
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
) -> DomainDocument:
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
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
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


def write_unified_release_program_handoff_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def write_unified_release_program_review_pack_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def write_unified_release_program_accepted_evidence_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_handoff_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def unified_release_program_review_pack_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def unified_release_program_accepted_evidence_verification_exit_code(report: DomainDocument) -> int:
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
) -> ImplementationDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
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


def _external_handoff_state(path: Path | str | None, archive_manifest: ImplementationDocument, *, require: bool) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    state: ImplementationDocument = {"checks": checks, "program": {}, "operations": {}, "accepted": []}
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


def _external_program_checks(row: ImplementationDocument | None, *, require: bool, state: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[ImplementationDocument] = []
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


from song_agent.domains.program import v142_urphv_readiness as _v142_urphv_readiness
from song_agent.domains.program.v142_urphv_readiness import (
    _external_operations_checks,
    _external_accepted_evidence_checks,
    _path_checks,
    _handoff_semantic_checks,
    _accepted_evidence_semantic_checks,
    _external_response_binding_checks,
    _handoff_document_binding_checks,
    _handoff_signoff_binding_checks,
    _public_external_manifest,
    _external_handoff_binding_checks,
    _manifest_checks,
    _history_checks,
    _finish,
    _read_json_entry,
    _parse_jsonl,
    _redaction_check,
    _safe_check_key,
)

_v142_urphv_readiness.bind_globals(globals())
