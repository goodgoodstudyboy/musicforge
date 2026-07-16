from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_archive_verifier import UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_archive_package as verify_unified_command_center_archive_package
from song_agent.domains.program.unified_command_center_handoff_verifier import UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package
from song_agent.domains.program.unified_command_center_verifier import UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_package as verify_unified_command_center_package


UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE = "musicforge_unified_command_center_continuous_review"
UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_continuous_review_verification"
UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "README.txt",
    "manifest.json",
    "review-plan.json",
    "review-source.json",
    "drift-report.json",
    "incident-board.json",
    "recovery-drill-report.json",
    "review-runbook.json",
    "review-runbook-result.json",
    "change-request-drafts.json",
    "package-fingerprints.json",
}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_unified_command_center_continuous_review_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_clear: bool = False,
    require_recovery_drill: bool = False,
    require_current_review: bool = False,
    archive_zip_path: Path | str | None = None,
    archive_verification_report_path: Path | str | None = None,
    handoff_zip_path: Path | str | None = None,
    handoff_verification_report_path: Path | str | None = None,
    command_center_zip_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
    ga_readiness_report_path: Path | str | None = None,
    release_check_report_path: Path | str | None = None,
    max_zip_size_mb: int = 64,
    max_uncompressed_size_mb: int = 256,
    max_entry_count: int = 200,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_review_zip_exists", False, "Continuous Review ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_review_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_review_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_review_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_review_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("ucc_review_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("ucc_review_no_nested_zip", not nested, "Continuous Review ZIP does not contain nested ZIP files.", {"nested": nested}))
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.append(_check("ucc_review_allowed_entries", not extra, "Continuous Review ZIP contains only fixed entries.", {"extra": extra}))
            checks.append(_check("ucc_review_required_entries", not missing, "Continuous Review ZIP contains all required entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            plan = _read_json_entry(archive, "review-plan.json")
            source = _read_json_entry(archive, "review-source.json")
            drift = _read_json_entry(archive, "drift-report.json")
            incidents = _read_json_entry(archive, "incident-board.json")
            drill = _read_json_entry(archive, "recovery-drill-report.json")
            runbook = _read_json_entry(archive, "review-runbook.json")
            runbook_result = _read_json_entry(archive, "review-runbook-result.json")
            cr_drafts = _read_json_entry(archive, "change-request-drafts.json")
            fingerprints = _read_json_entry(archive, "package-fingerprints.json")

            summary.update({"review_id": manifest.get("review_id"), "center_id": manifest.get("center_id"), "manifest_hash": manifest.get("integrity_hash")})
            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.append(_check("ucc_review_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_review_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            for check_id, doc in (
                ("ucc_review_plan_integrity", plan),
                ("ucc_review_source_integrity", source),
                ("ucc_review_drift_integrity", drift),
                ("ucc_review_incident_integrity", incidents),
                ("ucc_review_recovery_drill_integrity", drill),
                ("ucc_review_runbook_integrity", runbook),
                ("ucc_review_runbook_result_integrity", runbook_result),
                ("ucc_review_change_request_drafts_integrity", cr_drafts),
                ("ucc_review_package_fingerprints_integrity", fingerprints),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))

            manifest_source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
            checks.extend(
                [
                    _check("ucc_review_source_hash_binding", source.get("source_hash") == drift.get("source_hash") == incidents.get("source_hash") == drill.get("source_hash") == runbook.get("source_hash"), "Review documents bind the same source hash."),
                    _check("ucc_review_manifest_source_binding", manifest_source.get("review_source_hash") == source.get("integrity_hash"), "Manifest binds review source."),
                    _check("ucc_review_manifest_drift_binding", manifest_source.get("drift_report_hash") == drift.get("integrity_hash"), "Manifest binds drift report."),
                    _check("ucc_review_manifest_incident_binding", manifest_source.get("incident_board_hash") == incidents.get("integrity_hash"), "Manifest binds incident board."),
                    _check("ucc_review_manifest_recovery_binding", manifest_source.get("recovery_drill_hash") == drill.get("integrity_hash"), "Manifest binds recovery drill."),
                    _check("ucc_review_manifest_fingerprints_binding", manifest_source.get("package_fingerprints_hash") == fingerprints.get("integrity_hash"), "Manifest binds package fingerprints."),
                    _check("ucc_review_plan_source_binding", plan.get("review_id") == source.get("review_id") == manifest.get("review_id"), "Plan, source, and manifest bind the same review id."),
                    _check("ucc_review_drift_summary_binding", _drift_summary_ok(drift), "Drift summary matches drift rows."),
                    _check("ucc_review_incident_summary_binding", _incident_summary_ok(incidents), "Incident summary matches incident rows."),
                    _check("ucc_review_recovery_summary_binding", _recovery_summary_ok(drill), "Recovery drill summary matches steps."),
                    _check("ucc_review_fingerprints_source_binding", fingerprints.get("source_hash") == source.get("source_hash"), "Package fingerprints bind review source hash."),
                ]
            )
            if require_clear:
                checks.append(_check("ucc_review_require_clear", drift.get("status") == "passed" and incidents.get("status") == "clear", "Continuous Review has no blocking drift or open incident.", {"drift_status": drift.get("status"), "incident_status": incidents.get("status")}))
            if require_recovery_drill:
                checks.append(_check("ucc_review_require_recovery_drill", drill.get("status") == "passed", "Recovery drill passed.", {"status": drill.get("status")}))
            if require_current_review or strict:
                checks.extend(
                    _current_review_checks(
                        source,
                        fingerprints,
                        archive_zip_path=archive_zip_path,
                        archive_verification_report_path=archive_verification_report_path,
                        handoff_zip_path=handoff_zip_path,
                        handoff_verification_report_path=handoff_verification_report_path,
                        command_center_zip_path=command_center_zip_path,
                        command_center_verification_report_path=command_center_verification_report_path,
                        signoff_binding_path=signoff_binding_path,
                        ga_readiness_report_path=ga_readiness_report_path,
                        release_check_report_path=release_check_report_path,
                        require_handoff=bool((source.get("inputs") or {}).get("handoff", {}).get("required", True)),
                    )
                )
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_review_zip_readable", False, "Continuous Review ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_continuous_review_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_continuous_review_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _current_review_checks(
    source: ImplementationDocument,
    fingerprints: ImplementationDocument,
    *,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_zip_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
    ga_readiness_report_path: Path | str | None,
    release_check_report_path: Path | str | None,
    require_handoff: bool,
) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    inputs = source.get("inputs") if isinstance(source.get("inputs"), dict) else {}
    archive_input = inputs.get("archive") if isinstance(inputs.get("archive"), dict) else {}
    handoff_input = inputs.get("handoff") if isinstance(inputs.get("handoff"), dict) else {}
    ucc_input = inputs.get("ucc") if isinstance(inputs.get("ucc"), dict) else {}
    ga_input = inputs.get("ga") if isinstance(inputs.get("ga"), dict) else {}
    release_check_input = inputs.get("release_check") if isinstance(inputs.get("release_check"), dict) else {}
    fp_items = {str(row.get("component")): row for row in fingerprints.get("items", []) if isinstance(row, dict)}

    if not archive_zip_path:
        checks.append(_check("ucc_review_current_archive_zip_required", False, "Current archive ZIP is required."))
    if not archive_verification_report_path:
        checks.append(_check("ucc_review_current_archive_verification_required", False, "Current archive verification report is required."))
    if not command_center_zip_path:
        checks.append(_check("ucc_review_current_ucc_zip_required", False, "Current UCC ZIP is required."))
    if not command_center_verification_report_path:
        checks.append(_check("ucc_review_current_ucc_verification_required", False, "Current UCC verification report is required."))
    if require_handoff and not handoff_zip_path:
        checks.append(_check("ucc_review_current_handoff_zip_required", False, "Current handoff ZIP is required."))
    if require_handoff and not handoff_verification_report_path:
        checks.append(_check("ucc_review_current_handoff_verification_required", False, "Current handoff verification report is required."))
    if any(check["status"] == "failed" for check in checks):
        return checks

    archive_external = _read_json_file(Path(archive_verification_report_path)) if archive_verification_report_path else {}
    archive_runtime = verify_unified_command_center_archive_package(
        archive_zip_path,
        strict=True,
        require_signed=True,
        require_current_ucc=bool(command_center_zip_path and command_center_verification_report_path),
        command_center_zip_path=command_center_zip_path,
        command_center_verification_report_path=command_center_verification_report_path,
        signoff_binding_path=signoff_binding_path,
    )
    checks.extend(
        [
            _check("ucc_review_current_archive_verification_integrity", _integrity_ok(archive_external), "Current archive verification integrity is valid."),
            _check("ucc_review_current_archive_status", archive_external.get("status") == "passed" and archive_runtime.get("status") == "passed", "Current archive verification passed.", {"external_status": archive_external.get("status"), "runtime_status": archive_runtime.get("status")}),
            _check("ucc_review_current_archive_zip_binding", archive_input.get("zip_sha256") == _sha256_path(archive_zip_path) == archive_external.get("zip_sha256") == archive_runtime.get("zip_sha256"), "Packaged review binds current archive ZIP."),
            _check("ucc_review_current_archive_manifest_binding", archive_input.get("manifest_hash") == archive_external.get("manifest_hash") == archive_runtime.get("manifest_hash"), "Packaged review binds current archive manifest."),
            _check("ucc_review_current_archive_verification_binding", archive_input.get("verification_hash") == archive_external.get("integrity_hash"), "Packaged review binds current archive verification report."),
            _check("ucc_review_current_archive_package_type", archive_external.get("package_type") == UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE, "Archive verification package type is valid."),
        ]
    )
    archive_fp = fp_items.get("archive", {})
    checks.append(_check("ucc_review_current_archive_fingerprint", archive_fp.get("zip_sha256") == archive_input.get("zip_sha256") and archive_fp.get("verification_hash") == archive_input.get("verification_hash"), "Archive fingerprint sidecar matches review source."))

    if command_center_zip_path and command_center_verification_report_path:
        ucc_external = _read_json_file(Path(command_center_verification_report_path))
        ucc_runtime = _ucc_zip_summary(command_center_zip_path)
        checks.extend(
            [
                _check("ucc_review_current_ucc_verification_integrity", _integrity_ok(ucc_external), "Current UCC verification integrity is valid."),
                _check("ucc_review_current_ucc_status", ucc_external.get("status") == "passed" and ucc_runtime.get("status") != "failed", "Current UCC verification is usable.", {"external_status": ucc_external.get("status"), "runtime_status": ucc_runtime.get("status")}),
                _check("ucc_review_current_ucc_zip_binding", ucc_input.get("zip_sha256") == _sha256_path(command_center_zip_path) == ucc_external.get("zip_sha256"), "Packaged review binds current UCC ZIP."),
                _check("ucc_review_current_ucc_manifest_binding", ucc_input.get("manifest_hash") == ucc_external.get("manifest_hash") == ucc_runtime.get("manifest_hash"), "Packaged review binds current UCC manifest."),
                _check("ucc_review_current_ucc_verification_binding", ucc_input.get("verification_hash") == ucc_external.get("integrity_hash"), "Packaged review binds current UCC verification report."),
                _check("ucc_review_current_ucc_package_type", ucc_external.get("package_type") == UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, "UCC verification package type is valid."),
            ]
        )

    if require_handoff:
        handoff_external = _read_json_file(Path(handoff_verification_report_path)) if handoff_verification_report_path else {}
        handoff_runtime = verify_unified_command_center_handoff_package(
            handoff_zip_path,
            strict=True,
            require_archive=True,
            archive_zip_path=archive_zip_path,
            archive_verification_report_path=archive_verification_report_path,
        )
        checks.extend(
            [
                _check("ucc_review_current_handoff_verification_integrity", _integrity_ok(handoff_external), "Current handoff verification integrity is valid."),
                _check("ucc_review_current_handoff_status", handoff_external.get("status") == "passed" and handoff_runtime.get("status") == "passed", "Current handoff verification passed.", {"external_status": handoff_external.get("status"), "runtime_status": handoff_runtime.get("status")}),
                _check("ucc_review_current_handoff_zip_binding", handoff_input.get("zip_sha256") == _sha256_path(handoff_zip_path) == handoff_external.get("zip_sha256") == handoff_runtime.get("zip_sha256"), "Packaged review binds current handoff ZIP."),
                _check("ucc_review_current_handoff_manifest_binding", handoff_input.get("manifest_hash") == handoff_external.get("manifest_hash") == handoff_runtime.get("manifest_hash"), "Packaged review binds current handoff manifest."),
                _check("ucc_review_current_handoff_verification_binding", handoff_input.get("verification_hash") == handoff_external.get("integrity_hash"), "Packaged review binds current handoff verification report."),
                _check("ucc_review_current_handoff_package_type", handoff_external.get("package_type") == UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE, "Handoff verification package type is valid."),
            ]
        )
        handoff_fp = fp_items.get("handoff", {})
        checks.append(_check("ucc_review_current_handoff_fingerprint", handoff_fp.get("zip_sha256") == handoff_input.get("zip_sha256") and handoff_fp.get("verification_hash") == handoff_input.get("verification_hash"), "Handoff fingerprint sidecar matches review source."))
    checks.extend(_external_status_checks(inputs))
    if ga_readiness_report_path:
        ga_current = _report_binding_from_path(Path(ga_readiness_report_path))
        checks.extend(
            [
                _check("ucc_review_current_ga_status", ga_current.get("status") == "passed", "Current GA readiness report is passing.", {"status": ga_current.get("status")}),
                _check("ucc_review_current_ga_binding", ga_input.get("report_hash") == ga_current.get("report_hash") and ga_input.get("path_hash") == ga_current.get("path_hash"), "Packaged review binds current GA readiness report."),
            ]
        )
    elif ga_input.get("status") not in {None, "not_configured", "not_required"}:
        checks.append(_check("ucc_review_current_ga_report_required", False, "Current GA readiness report is required to re-check packaged GA evidence."))
    if release_check_report_path:
        release_check_current = _report_binding_from_path(Path(release_check_report_path))
        checks.extend(
            [
                _check("ucc_review_current_release_check_status", release_check_current.get("status") == "passed", "Current release-check report is passing.", {"status": release_check_current.get("status")}),
                _check("ucc_review_current_release_check_binding", release_check_input.get("report_hash") == release_check_current.get("report_hash") and release_check_input.get("path_hash") == release_check_current.get("path_hash"), "Packaged review binds current release-check report."),
            ]
        )
    elif release_check_input.get("status") not in {None, "not_configured", "not_required"}:
        checks.append(_check("ucc_review_current_release_check_report_required", False, "Current release-check report is required to re-check packaged release-check evidence."))
    return checks


PASSING_EVIDENCE_STATUSES = {"passed", "ready", "clear", "signed", "accepted", "ok"}


def _normalized_evidence_status(value: Any) -> str:
    raw = value
    if isinstance(value, dict):
        raw = value.get("status")
        if raw is None and value.get("ok") is True:
            raw = "passed"
    status = str(raw or "unknown").strip().lower()
    return "passed" if status in PASSING_EVIDENCE_STATUSES else status


def _status_is_passing_or_absent(status: Any) -> bool:
    return _normalized_evidence_status(status) in {"passed", "not_configured", "not_required", "skipped"}


def _external_status_checks(inputs: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    ga = inputs.get("ga") if isinstance(inputs.get("ga"), dict) else {}
    release_check = inputs.get("release_check") if isinstance(inputs.get("release_check"), dict) else {}
    checks.append(_check("ucc_review_ga_status", _status_is_passing_or_absent(ga.get("status")), "Packaged GA readiness evidence is passing or absent.", {"status": ga.get("status")}))
    checks.append(_check("ucc_review_release_check_status", _status_is_passing_or_absent(release_check.get("status")), "Packaged release-check evidence is passing or absent.", {"status": release_check.get("status")}))
    external = inputs.get("external_evidence") if isinstance(inputs.get("external_evidence"), list) else []
    failed = [
        {
            "component": row.get("component") or row.get("component_type") or row.get("evidence_type"),
            "component_id": row.get("component_id") or row.get("evidence_id"),
            "status": row.get("status"),
        }
        for row in external
        if isinstance(row, dict) and not _status_is_passing_or_absent(row.get("status"))
    ]
    checks.append(_check("ucc_review_external_evidence_status", not failed, "Packaged external evidence rows are passing or absent.", {"failed": failed}))
    return checks


def _report_binding_from_path(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {"status": "missing", "report_hash": None, "path_hash": None}
    try:
        payload = _read_json_file(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"status": "failed", "report_hash": None, "path_hash": _sha256_path(path), "error": sanitize_sensitive_text(str(exc))}
    return {
        "status": _normalized_evidence_status(payload),
        "report_hash": payload.get("integrity_hash") or _integrity_hash(payload),
        "path_hash": _sha256_path(path),
    }


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = REQUIRED_ENTRIES - {"manifest.json"}
    effective = names - {"manifest.json"}
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if not rel or rel not in names:
            continue
        data = archive.read(rel)
        info = archive.getinfo(rel)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(rel)
    return [
        _check("ucc_review_manifest_declares_files", declared == effective, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective), "undeclared": sorted(effective - declared)}),
        _check("ucc_review_manifest_fixed_files", declared == expected, "Manifest files match fixed continuous review structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
        _check("ucc_review_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
    ]


def _ucc_zip_summary(zip_path: Path | str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            manifest = _read_json_entry(archive, "manifest.json")
            return {
                "status": "passed" if _integrity_ok(manifest) else "failed",
                "zip_sha256": _sha256_path(zip_path),
                "manifest_hash": manifest.get("integrity_hash"),
            }
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError):
        return {"status": "failed", "zip_sha256": _sha256_path(zip_path), "manifest_hash": None}


def _drift_summary_ok(drift: ImplementationDocument) -> bool:
    rows = [row for row in drift.get("drifts", []) if isinstance(row, dict)]
    summary = drift.get("summary") if isinstance(drift.get("summary"), dict) else {}
    blocking = sum(1 for row in rows if row.get("severity") in {"critical", "high"} and row.get("status") == "open")
    return int(summary.get("drift_count") or 0) == len(rows) and int(summary.get("blocking_drift_count") or 0) == blocking


def _incident_summary_ok(board: ImplementationDocument) -> bool:
    rows = [row for row in board.get("incidents", []) if isinstance(row, dict)]
    summary = board.get("summary") if isinstance(board.get("summary"), dict) else {}
    open_count = sum(1 for row in rows if row.get("status") == "open")
    critical = sum(1 for row in rows if row.get("status") == "open" and row.get("severity") == "critical")
    return int(summary.get("open_count") or 0) == open_count and int(summary.get("critical_count") or 0) == critical


def _recovery_summary_ok(drill: ImplementationDocument) -> bool:
    steps = [row for row in drill.get("steps", []) if isinstance(row, dict)]
    summary = drill.get("summary") if isinstance(drill.get("summary"), dict) else {}
    failed = sum(1 for row in steps if row.get("status") == "failed")
    return int(summary.get("failed_count") or 0) == failed


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {**summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, blocking: bool = True) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_json_file(path: Path) -> ImplementationDocument:
    return json.loads(path.read_text(encoding="utf-8"))


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    path = Path(name)
    if path.is_absolute():
        return False
    return all(part and part not in {".", ".."} and ":" not in part for part in name.split("/"))


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    offenders: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            offenders.append(name)
    return _check("ucc_review_redaction_scan", not offenders, "Continuous Review package contains no obvious secrets or local workspace paths.", {"offenders": offenders})


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
