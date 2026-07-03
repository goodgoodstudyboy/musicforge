from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_command_center_continuous_review_verifier import (
    UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE,
    verify_unified_command_center_continuous_review_package,
)


UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response_verification"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE = "musicforge_unified_command_center_drift_response_change_request_binding_report"
UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "README.txt",
    "manifest.json",
    "response-case.json",
    "response-source.json",
    "response-plan.json",
    "action-queue.json",
    "action-results.json",
    "change-request-bindings.json",
    "recheck-summary.json",
    "closeout-report.json",
    "package-fingerprints.json",
    "events.jsonl",
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


def verify_unified_command_center_drift_response_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_closed: bool = False,
    require_recheck_clear: bool = False,
    require_current_review: bool = False,
    source_review_zip_path: Path | str | None = None,
    source_review_verification_report_path: Path | str | None = None,
    recheck_review_zip_path: Path | str | None = None,
    recheck_review_verification_report_path: Path | str | None = None,
    change_request_binding_report_path: Path | str | None = None,
    archive_zip_path: Path | str | None = None,
    archive_verification_report_path: Path | str | None = None,
    handoff_zip_path: Path | str | None = None,
    handoff_verification_report_path: Path | str | None = None,
    command_center_zip_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
    max_zip_size_mb: int = 64,
    max_uncompressed_size_mb: int = 256,
    max_entry_count: int = 200,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_drift_response_zip_exists", False, "Drift Response ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_drift_response_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_drift_response_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_drift_response_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_drift_response_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("ucc_drift_response_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("ucc_drift_response_no_nested_zip", not nested, "Drift Response ZIP does not contain nested ZIP files.", {"nested": nested}))
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.append(_check("ucc_drift_response_allowed_entries", not extra, "Drift Response ZIP contains only fixed entries.", {"extra": extra}))
            checks.append(_check("ucc_drift_response_required_entries", not missing, "Drift Response ZIP contains all required entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            case = _read_json_entry(archive, "response-case.json")
            source = _read_json_entry(archive, "response-source.json")
            plan = _read_json_entry(archive, "response-plan.json")
            queue = _read_json_entry(archive, "action-queue.json")
            results = _read_json_entry(archive, "action-results.json")
            cr_bindings = _read_json_entry(archive, "change-request-bindings.json")
            recheck = _read_json_entry(archive, "recheck-summary.json")
            closeout = _read_json_entry(archive, "closeout-report.json")
            fingerprints = _read_json_entry(archive, "package-fingerprints.json")
            events = _read_jsonl_entry(archive, "events.jsonl")

            summary.update({"response_id": manifest.get("response_id"), "center_id": manifest.get("center_id"), "manifest_hash": manifest.get("integrity_hash")})
            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.append(_check("ucc_drift_response_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_drift_response_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            for check_id, doc in (
                ("ucc_drift_response_case_integrity", case),
                ("ucc_drift_response_source_integrity", source),
                ("ucc_drift_response_plan_integrity", plan),
                ("ucc_drift_response_queue_integrity", queue),
                ("ucc_drift_response_results_integrity", results),
                ("ucc_drift_response_cr_bindings_integrity", cr_bindings),
                ("ucc_drift_response_recheck_integrity", recheck),
                ("ucc_drift_response_closeout_integrity", closeout),
                ("ucc_drift_response_fingerprints_integrity", fingerprints),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.append(_check("ucc_drift_response_events_chain", _events_chain_ok(events), "Events form a valid hash chain."))

            manifest_source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
            checks.extend(
                [
                    _check("ucc_drift_response_id_binding", manifest.get("response_id") == case.get("response_id") == source.get("response_id") == plan.get("response_id") == queue.get("response_id") == closeout.get("response_id"), "Response documents bind the same response id."),
                    _check("ucc_drift_response_source_hash_binding", source.get("source_hash") == plan.get("source_hash") == queue.get("source_hash") == results.get("source_hash") == cr_bindings.get("source_hash") == recheck.get("source_hash") == closeout.get("source_hash") == fingerprints.get("source_hash"), "Response documents bind the same source hash."),
                    _check("ucc_drift_response_manifest_case_binding", manifest_source.get("response_case_hash") == case.get("integrity_hash"), "Manifest binds response case."),
                    _check("ucc_drift_response_manifest_source_binding", manifest_source.get("response_source_hash") == source.get("integrity_hash"), "Manifest binds response source."),
                    _check("ucc_drift_response_manifest_plan_binding", manifest_source.get("response_plan_hash") == plan.get("integrity_hash"), "Manifest binds response plan."),
                    _check("ucc_drift_response_manifest_queue_binding", manifest_source.get("action_queue_hash") == queue.get("integrity_hash"), "Manifest binds action queue."),
                    _check("ucc_drift_response_manifest_results_binding", manifest_source.get("action_results_hash") == results.get("integrity_hash"), "Manifest binds action results."),
                    _check("ucc_drift_response_manifest_cr_binding", manifest_source.get("change_request_bindings_hash") == cr_bindings.get("integrity_hash"), "Manifest binds CR bindings."),
                    _check("ucc_drift_response_manifest_recheck_binding", manifest_source.get("recheck_summary_hash") == recheck.get("integrity_hash"), "Manifest binds recheck summary."),
                    _check("ucc_drift_response_manifest_closeout_binding", manifest_source.get("closeout_report_hash") == closeout.get("integrity_hash"), "Manifest binds closeout report."),
                    _check("ucc_drift_response_manifest_fingerprint_binding", manifest_source.get("package_fingerprints_hash") == fingerprints.get("integrity_hash"), "Manifest binds package fingerprints."),
                    _check("ucc_drift_response_action_summary", _action_summary_ok(queue, results, cr_bindings), "Action and CR summaries match rows."),
                    _check("ucc_drift_response_closeout_summary", _closeout_summary_ok(closeout), "Closeout summary matches blockers."),
                ]
            )
            if require_closed:
                checks.append(_check("ucc_drift_response_require_closed", closeout.get("status") == "closed" and case.get("status") == "closed", "Drift Response is closed.", {"case_status": case.get("status"), "closeout_status": closeout.get("status")}))
                checks.extend(_change_request_proof_checks(queue, cr_bindings, change_request_binding_report_path))
            if require_recheck_clear:
                checks.append(_check("ucc_drift_response_require_recheck_clear", recheck.get("status") == "passed" and closeout.get("recheck_status") == "passed", "Response recheck is clear.", {"recheck_status": recheck.get("status")}))
            if require_current_review or strict:
                checks.extend(
                    _current_review_checks(
                        source,
                        recheck,
                        source_review_zip_path=source_review_zip_path,
                        source_review_verification_report_path=source_review_verification_report_path,
                        recheck_review_zip_path=recheck_review_zip_path,
                        recheck_review_verification_report_path=recheck_review_verification_report_path,
                        archive_zip_path=archive_zip_path,
                        archive_verification_report_path=archive_verification_report_path,
                        handoff_zip_path=handoff_zip_path,
                        handoff_verification_report_path=handoff_verification_report_path,
                        command_center_zip_path=command_center_zip_path,
                        command_center_verification_report_path=command_center_verification_report_path,
                        signoff_binding_path=signoff_binding_path,
                    )
                )
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_drift_response_zip_readable", False, "Drift Response ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_drift_response_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_drift_response_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _current_review_checks(
    source: dict[str, Any],
    recheck: dict[str, Any],
    *,
    source_review_zip_path: Path | str | None,
    source_review_verification_report_path: Path | str | None,
    recheck_review_zip_path: Path | str | None,
    recheck_review_verification_report_path: Path | str | None,
    archive_zip_path: Path | str | None,
    archive_verification_report_path: Path | str | None,
    handoff_zip_path: Path | str | None,
    handoff_verification_report_path: Path | str | None,
    command_center_zip_path: Path | str | None,
    command_center_verification_report_path: Path | str | None,
    signoff_binding_path: Path | str | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    source_binding = source.get("source_review") if isinstance(source.get("source_review"), dict) else {}
    recheck_binding = recheck.get("review") if isinstance(recheck.get("review"), dict) else {}
    if not source_review_zip_path:
        checks.append(_check("ucc_drift_response_source_review_zip_required", False, "Source Continuous Review ZIP is required."))
    if not source_review_verification_report_path:
        checks.append(_check("ucc_drift_response_source_review_verification_required", False, "Source Continuous Review verification report is required."))
    if not recheck_review_zip_path:
        checks.append(_check("ucc_drift_response_recheck_review_zip_required", False, "Recheck Continuous Review ZIP is required."))
    if not recheck_review_verification_report_path:
        checks.append(_check("ucc_drift_response_recheck_review_verification_required", False, "Recheck Continuous Review verification report is required."))
    if any(check["status"] == "failed" for check in checks):
        return checks

    source_external = _read_json_file(Path(source_review_verification_report_path)) if source_review_verification_report_path else {}
    source_runtime = verify_unified_command_center_continuous_review_package(
        source_review_zip_path,
        strict=True,
        require_clear=False,
        require_recovery_drill=False,
        require_current_review=True,
        archive_zip_path=archive_zip_path,
        archive_verification_report_path=archive_verification_report_path,
        handoff_zip_path=handoff_zip_path,
        handoff_verification_report_path=handoff_verification_report_path,
        command_center_zip_path=command_center_zip_path,
        command_center_verification_report_path=command_center_verification_report_path,
        signoff_binding_path=signoff_binding_path,
    )
    checks.extend(
        [
            _check("ucc_drift_response_source_review_verification_integrity", _integrity_ok(source_external), "Source review verification integrity is valid."),
            _check("ucc_drift_response_source_review_package_type", source_external.get("package_type") == UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE, "Source review verification package type is valid."),
            _check("ucc_drift_response_source_review_status_failed", source_external.get("status") == "failed" or source_runtime.get("status") == "failed", "Source review represents a failed drift state.", {"external_status": source_external.get("status"), "runtime_status": source_runtime.get("status")}),
            _check("ucc_drift_response_source_review_zip_binding", source_binding.get("zip_sha256") == _sha256_path(source_review_zip_path) == source_external.get("zip_sha256") == source_runtime.get("zip_sha256"), "Response binds source review ZIP."),
            _check("ucc_drift_response_source_review_manifest_binding", source_binding.get("manifest_hash") == source_external.get("manifest_hash") == source_runtime.get("manifest_hash"), "Response binds source review manifest."),
            _check("ucc_drift_response_source_review_verification_binding", source_binding.get("verification_hash") == source_external.get("integrity_hash"), "Response binds source review verification report."),
        ]
    )

    recheck_external = _read_json_file(Path(recheck_review_verification_report_path)) if recheck_review_verification_report_path else {}
    recheck_runtime = verify_unified_command_center_continuous_review_package(
        recheck_review_zip_path,
        strict=True,
        require_clear=True,
        require_recovery_drill=True,
        require_current_review=True,
        archive_zip_path=archive_zip_path,
        archive_verification_report_path=archive_verification_report_path,
        handoff_zip_path=handoff_zip_path,
        handoff_verification_report_path=handoff_verification_report_path,
        command_center_zip_path=command_center_zip_path,
        command_center_verification_report_path=command_center_verification_report_path,
        signoff_binding_path=signoff_binding_path,
    )
    checks.extend(
        [
            _check("ucc_drift_response_recheck_verification_integrity", _integrity_ok(recheck_external), "Recheck review verification integrity is valid."),
            _check("ucc_drift_response_recheck_package_type", recheck_external.get("package_type") == UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE, "Recheck review verification package type is valid."),
            _check("ucc_drift_response_recheck_status_passed", recheck_external.get("status") == "passed" and recheck_runtime.get("status") == "passed", "Recheck review is passed.", {"external_status": recheck_external.get("status"), "runtime_status": recheck_runtime.get("status")}),
            _check("ucc_drift_response_recheck_zip_binding", recheck_binding.get("zip_sha256") == _sha256_path(recheck_review_zip_path) == recheck_external.get("zip_sha256") == recheck_runtime.get("zip_sha256"), "Response binds recheck review ZIP."),
            _check("ucc_drift_response_recheck_manifest_binding", recheck_binding.get("manifest_hash") == recheck_external.get("manifest_hash") == recheck_runtime.get("manifest_hash"), "Response binds recheck review manifest."),
            _check("ucc_drift_response_recheck_verification_binding", recheck_binding.get("verification_hash") == recheck_external.get("integrity_hash"), "Response binds recheck verification report."),
        ]
    )
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("entry") or row.get("path")) for row in files if isinstance(row, dict) and (row.get("entry") or row.get("path"))}
    expected = REQUIRED_ENTRIES - {"manifest.json"}
    checks.append(_check("ucc_drift_response_manifest_files_fixed", declared == expected, "Manifest files match fixed Drift Response structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}))
    for row in files:
        if not isinstance(row, dict) or not (row.get("entry") or row.get("path")):
            continue
        rel = str(row.get("entry") or row.get("path"))
        if rel not in name_set:
            checks.append(_check(f"ucc_drift_response_manifest_file_{rel}", False, "Manifest file exists in ZIP.", {"path": rel}))
            continue
        data = archive.read(rel)
        checks.append(_check(f"ucc_drift_response_manifest_hash_{rel}", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry.", {"path": rel}))
    return checks


def _action_summary_ok(queue: dict[str, Any], results: dict[str, Any], cr_bindings: dict[str, Any]) -> bool:
    items = [row for row in queue.get("items", []) if isinstance(row, dict)]
    result_rows = [row for row in results.get("results", []) if isinstance(row, dict)]
    cr_rows = [row for row in cr_bindings.get("items", []) if isinstance(row, dict)]
    q_summary = queue.get("summary") if isinstance(queue.get("summary"), dict) else {}
    r_summary = results.get("summary") if isinstance(results.get("summary"), dict) else {}
    c_summary = cr_bindings.get("summary") if isinstance(cr_bindings.get("summary"), dict) else {}
    return (
        int(q_summary.get("action_count") or 0) == len(items)
        and int(q_summary.get("manual_required_count") or 0) == sum(1 for row in items if row.get("status") == "manual_required")
        and int(r_summary.get("completed_count") or 0) == sum(1 for row in result_rows if row.get("status") == "completed")
        and int(r_summary.get("manual_required_count") or 0) == sum(1 for row in result_rows if row.get("status") == "manual_required")
        and int(c_summary.get("approved_count") or 0) == sum(1 for row in cr_rows if row.get("status") == "approved")
    )


def _change_request_proof_checks(queue: dict[str, Any], cr_bindings: dict[str, Any], report_path: Path | str | None) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    manual_items = [row for row in queue.get("items", []) if isinstance(row, dict) and not row.get("safe")]
    if not manual_items:
        return checks
    if not report_path:
        return [_check("ucc_drift_response_cr_proof_required", False, "External Change Request binding report is required for closed Drift Response packages.")]
    path = Path(report_path)
    if not path.exists():
        return [_check("ucc_drift_response_cr_proof_exists", False, "External Change Request binding report exists.", {"path": str(path)})]
    try:
        report = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [_check("ucc_drift_response_cr_proof_readable", False, "External Change Request binding report can be read.", {"error": sanitize_sensitive_text(str(exc))})]

    proof_rows = [row for row in report.get("items", []) if isinstance(row, dict)]
    binding_rows = [row for row in cr_bindings.get("items", []) if isinstance(row, dict)]
    manual_by_item = {str(row.get("item_id")): row for row in manual_items}
    proof_by_item = {str(row.get("item_id")): row for row in proof_rows}
    binding_by_item = {str(row.get("item_id")): row for row in binding_rows}
    manual_ids = set(manual_by_item)
    proof_ids = set(proof_by_item)
    binding_ids = set(binding_by_item)
    cr_ids = [str(row.get("change_request_id") or "") for row in proof_rows if row.get("change_request_id")]
    duplicate_cr_ids = sorted({value for value in cr_ids if cr_ids.count(value) > 1})

    checks.extend(
        [
            _check("ucc_drift_response_cr_proof_package_type", report.get("package_type") == UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE, "External Change Request binding report package type is valid."),
            _check("ucc_drift_response_cr_proof_integrity", _integrity_ok(report), "External Change Request binding report integrity hash is valid."),
            _check("ucc_drift_response_cr_proof_response_binding", report.get("response_id") == queue.get("response_id") == cr_bindings.get("response_id"), "External CR report binds the same response id."),
            _check("ucc_drift_response_cr_proof_source_binding", report.get("source_hash") == queue.get("source_hash") == cr_bindings.get("source_hash"), "External CR report binds the same source hash."),
            _check("ucc_drift_response_cr_proof_queue_binding", report.get("action_queue_hash") == queue.get("integrity_hash"), "External CR report binds the action queue."),
            _check("ucc_drift_response_cr_proof_bindings_binding", report.get("change_request_bindings_hash") == cr_bindings.get("integrity_hash"), "External CR report binds the package CR bindings."),
            _check("ucc_drift_response_cr_proof_item_coverage", proof_ids == manual_ids == binding_ids, "External CR report covers every manual action item exactly.", {"missing_proof": sorted(manual_ids - proof_ids), "extra_proof": sorted(proof_ids - manual_ids), "missing_binding": sorted(manual_ids - binding_ids)}),
            _check("ucc_drift_response_cr_proof_unique_change_requests", not duplicate_cr_ids, "External CR report does not reuse a Change Request id across manual items.", {"duplicates": duplicate_cr_ids}),
        ]
    )
    if any(check["status"] == "failed" for check in checks):
        return checks

    for item_id in sorted(manual_ids):
        item = manual_by_item[item_id]
        proof = proof_by_item[item_id]
        binding = binding_by_item[item_id]
        expected_approval_hash = _approval_hash(binding)
        expected_proof_hash = stable_hash({key: value for key, value in proof.items() if key != "proof_hash"})
        checks.extend(
            [
                _check(f"ucc_drift_response_cr_proof_{item_id}_status", proof.get("status") == "approved" and binding.get("status") == "approved", "CR proof and binding are approved.", {"item_id": item_id}),
                _check(f"ucc_drift_response_cr_proof_{item_id}_drift", proof.get("source_drift_id") == item.get("source_drift_id") == binding.get("source_drift_id"), "CR proof binds the source drift id.", {"item_id": item_id}),
                _check(f"ucc_drift_response_cr_proof_{item_id}_action", proof.get("action") == item.get("action") == binding.get("action"), "CR proof binds the action.", {"item_id": item_id}),
                _check(f"ucc_drift_response_cr_proof_{item_id}_component", proof.get("component_type") == item.get("component_type") == binding.get("component_type") and proof.get("component_id") == item.get("component_id") == binding.get("component_id"), "CR proof binds the component.", {"item_id": item_id}),
                _check(f"ucc_drift_response_cr_proof_{item_id}_approval_hash", proof.get("approval_hash") == binding.get("approval_hash") == expected_approval_hash, "CR proof binds the approval payload.", {"item_id": item_id}),
                _check(f"ucc_drift_response_cr_proof_{item_id}_proof_hash", proof.get("proof_hash") == expected_proof_hash, "CR proof hash is valid.", {"item_id": item_id}),
            ]
        )
    return checks


def _approval_hash(binding: dict[str, Any]) -> str:
    return stable_hash(
        {
            "change_request_id": binding.get("change_request_id"),
            "status": binding.get("status"),
            "approved_by": binding.get("approved_by"),
            "approved_at": binding.get("approved_at"),
            "reason": binding.get("reason"),
            "evidence_hash": binding.get("evidence_hash"),
        }
    )


def _closeout_summary_ok(closeout: dict[str, Any]) -> bool:
    blockers = closeout.get("blockers") if isinstance(closeout.get("blockers"), list) else []
    summary = closeout.get("summary") if isinstance(closeout.get("summary"), dict) else {}
    return int(summary.get("blocker_count") or 0) == len(blockers)


def _events_chain_ok(events: list[dict[str, Any]]) -> bool:
    previous = ""
    if not events:
        return False
    for event in events:
        if event.get("previous_event_hash") != previous:
            return False
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        if event.get("payload_hash") != payload_hash:
            return False
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event.get("event_hash") != event_hash:
            return False
        previous = str(event.get("event_hash") or "")
    return True


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_jsonl_entry(archive: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    rows = []
    for line in archive.read(name).decode("utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    findings = []
    for name in names:
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                findings.append({"entry": name, "pattern": pattern.pattern.decode("utf-8", errors="replace")})
    return _check("ucc_drift_response_redaction", not findings, "Package does not contain token-like or local path secrets.", {"findings": findings})


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra_checks: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra_checks)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed"]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    report = {
        "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    return report


def _check(check_id: str, passed: bool, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "detail": detail or {}}


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    path = Path(name)
    if path.is_absolute():
        return False
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    lowered = name.lower()
    return not (lowered.startswith(".musicforge/") or "/.musicforge/" in lowered)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
