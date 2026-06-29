from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import write_json
from song_agent.release_audio_quality_actions import (
    RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE,
    RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
    build_expected_action_documents_from_observatory,
)
from song_agent.releases import stable_hash


RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE = "release_audio_quality_action_queue_verification"

REQUIRED_ENTRIES = {
    "manifest.json",
    "action-queue.json",
    "source-binding.json",
    "action-items.json",
    "action-results.json",
    "manual-actions.json",
    "queue-summary.json",
    "README.txt",
}
OPTIONAL_ENTRIES = {"queue-history.jsonl"}

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


def verify_release_audio_quality_action_queue_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current_observatory: bool = False,
    observatory_zip_path: Path | str | None = None,
    observatory_verification_report_path: Path | str | None = None,
    evidence_root: Path | str | None = None,
    require_no_blocking: bool = True,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_path": str(zip_path), "zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None, "queue_id": None, "release_ids": []}
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_quality_action_queue_zip_exists", False, "Release Audio Quality Action Queue ZIP exists."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_quality_action_queue_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_quality_action_queue_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("release_audio_quality_action_queue_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_quality_action_queue_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("release_audio_quality_action_queue_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("release_audio_quality_action_queue_no_nested_zip", not nested, "ZIP contains no nested ZIP entries.", {"nested": nested}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            expected_entries = set(REQUIRED_ENTRIES)
            if "queue-history.jsonl" in names:
                expected_entries.add("queue-history.jsonl")
            extra_entries = sorted(set(names) - expected_entries)
            missing_entries = sorted(expected_entries - set(names))
            checks.append(_check("release_audio_quality_action_queue_zip_allowed_entries", not extra_entries, "ZIP contains only fixed Action Queue entries.", {"extra": extra_entries}))
            checks.append(_check("release_audio_quality_action_queue_zip_expected_entries", not missing_entries, "ZIP contains all expected Action Queue entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            queue = _read_json_entry(archive, "action-queue.json")
            source_binding = _read_json_entry(archive, "source-binding.json")
            items = _read_json_entry(archive, "action-items.json")
            results = _read_json_entry(archive, "action-results.json")
            manual_actions = _read_json_entry(archive, "manual-actions.json")
            queue_summary = _read_json_entry(archive, "queue-summary.json")
            history_rows = _read_jsonl_entry(archive, "queue-history.jsonl") if "queue-history.jsonl" in names else []

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["queue_id"] = queue.get("queue_id") or manifest.get("queue_id")
            summary["release_ids"] = (queue_summary.get("summary") or {}).get("release_ids") or (source_binding.get("observatory") or {}).get("release_ids") or []
            summary["queue_status"] = queue_summary.get("status")
            summary["manual_required_count"] = (queue_summary.get("summary") or {}).get("manual_required_count")
            summary["blocked_count"] = (queue_summary.get("summary") or {}).get("blocked_count")
            summary["failed_count"] = (queue_summary.get("summary") or {}).get("failed_count")
            summary["critical_unhandled_count"] = (queue_summary.get("summary") or {}).get("critical_unhandled_count")

            documents = {
                "manifest": manifest,
                "queue": queue,
                "source_binding": source_binding,
                "items": items,
                "results": results,
                "manual_actions": manual_actions,
                "summary": queue_summary,
            }
            checks.extend(_manifest_checks(archive, manifest, set(names), expected_entries=expected_entries, strict=strict))
            checks.append(_check("release_audio_quality_action_queue_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_QUALITY_ACTION_QUEUE_PACKAGE_TYPE, "Manifest package_type is release_audio_quality_action_queue."))
            checks.append(_check("release_audio_quality_action_queue_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION, "Manifest schema version is supported."))
            for check_id, document in (
                ("release_audio_quality_action_queue_manifest_integrity", manifest),
                ("release_audio_quality_action_queue_queue_integrity", queue),
                ("release_audio_quality_action_queue_source_binding_integrity", source_binding),
                ("release_audio_quality_action_queue_items_integrity", items),
                ("release_audio_quality_action_queue_results_integrity", results),
                ("release_audio_quality_action_queue_manual_actions_integrity", manual_actions),
                ("release_audio_quality_action_queue_summary_integrity", queue_summary),
            ):
                checks.append(_check(check_id, _integrity_ok(document), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(documents))
            checks.extend(_action_semantics_checks(items, results, manual_actions, queue_summary, require_no_blocking=require_no_blocking))
            checks.extend(_history_checks(history_rows))
            if require_current_observatory:
                checks.extend(
                    _external_observatory_checks(
                        queue,
                        source_binding,
                        items,
                        observatory_zip_path=observatory_zip_path,
                        observatory_verification_report_path=observatory_verification_report_path,
                        evidence_root=evidence_root,
                    )
                )
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_quality_action_queue_zip_readable", False, "Release Audio Quality Action Queue ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_quality_action_queue_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_quality_action_queue_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_observatory_checks(
    queue: dict[str, Any],
    source_binding: dict[str, Any],
    items: dict[str, Any],
    *,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> list[dict[str, Any]]:
    try:
        expected = build_expected_action_documents_from_observatory(
            queue,
            source_binding,
            observatory_zip_path=observatory_zip_path,
            observatory_verification_report_path=observatory_verification_report_path,
            evidence_root=evidence_root,
        )
    except Exception as exc:
        return [_check("release_audio_quality_action_queue_external_observatory_readable", False, f"External Observatory evidence could not be verified: {exc}")]
    expected_binding = expected["source_binding"]
    expected_items = expected["items"]
    source_ok = _semantic_hash(source_binding) == _semantic_hash(expected_binding)
    item_source = _normalized_items(items.get("items") or [])
    expected_source = _normalized_items(expected_items)
    current_item_source_ids = {str(row.get("source_id")) for row in items.get("items", []) if isinstance(row, dict)}
    valid_source_ids = set(expected_binding.get("source_risk_ids") or []) | set(expected_binding.get("source_recommendation_ids") or [])
    return [
        _check("release_audio_quality_action_queue_external_source_binding", source_ok, "Queue source binding matches current external Observatory evidence."),
        _check("release_audio_quality_action_queue_external_action_items", item_source == expected_source, "Queue action items match external Observatory risks and recommendations."),
        _check("release_audio_quality_action_queue_external_source_ids", current_item_source_ids.issubset(valid_source_ids), "Queue item source ids exist in external Observatory evidence.", {"unknown": sorted(current_item_source_ids - valid_source_ids)}),
    ]


def _document_binding_checks(documents: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    manifest = documents["manifest"]
    queue = documents["queue"]
    source_binding = documents["source_binding"]
    items = documents["items"]
    results = documents["results"]
    manual_actions = documents["manual_actions"]
    queue_summary = documents["summary"]
    source_hash = source_binding.get("source_hash")
    doc_hashes = queue_summary.get("document_hashes") if isinstance(queue_summary.get("document_hashes"), dict) else {}
    same_source = all(doc.get("source_hash") == source_hash for doc in (queue, items, results, manual_actions, queue_summary) if doc.get("source_hash") is not None)
    return [
        _check("release_audio_quality_action_queue_manifest_queue_binding", manifest.get("action_queue_hash") == queue.get("integrity_hash"), "Manifest binds action queue."),
        _check("release_audio_quality_action_queue_manifest_source_binding", manifest.get("source_binding_hash") == source_binding.get("integrity_hash"), "Manifest binds source binding."),
        _check("release_audio_quality_action_queue_manifest_items_binding", manifest.get("action_items_hash") == items.get("integrity_hash"), "Manifest binds action items."),
        _check("release_audio_quality_action_queue_manifest_results_binding", manifest.get("action_results_hash") == results.get("integrity_hash"), "Manifest binds action results."),
        _check("release_audio_quality_action_queue_manifest_manual_binding", manifest.get("manual_actions_hash") == manual_actions.get("integrity_hash"), "Manifest binds manual actions."),
        _check("release_audio_quality_action_queue_manifest_summary_binding", manifest.get("summary_hash") == queue_summary.get("integrity_hash"), "Manifest binds summary."),
        _check("release_audio_quality_action_queue_source_hash_binding", same_source and manifest.get("source_hash") == source_hash, "Queue documents bind the same source hash."),
        _check("release_audio_quality_action_queue_summary_document_hashes", doc_hashes.get("action_queue") == queue.get("integrity_hash") and doc_hashes.get("source_binding") == source_binding.get("integrity_hash") and doc_hashes.get("action_items") == items.get("integrity_hash") and doc_hashes.get("action_results") == results.get("integrity_hash") and doc_hashes.get("manual_actions") == manual_actions.get("integrity_hash"), "Summary binds all queue documents."),
    ]


def _action_semantics_checks(items: dict[str, Any], results: dict[str, Any], manual_actions: dict[str, Any], summary: dict[str, Any], *, require_no_blocking: bool) -> list[dict[str, Any]]:
    item_rows = [row for row in items.get("items", []) if isinstance(row, dict)]
    result_rows = [row for row in results.get("results", []) if isinstance(row, dict)]
    manual_rows = [row for row in manual_actions.get("manual_actions", []) if isinstance(row, dict)]
    item_ids = {str(row.get("item_id")) for row in item_rows}
    result_ids = {str(row.get("item_id")) for row in result_rows}
    manual_ids = {str(row.get("item_id")) for row in manual_rows}
    data = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    completed = sum(1 for row in result_rows if row.get("status") == "completed")
    blocked = sum(1 for row in result_rows if row.get("status") == "blocked")
    failed = sum(1 for row in result_rows if row.get("status") == "failed")
    manual_ids_for_count = {str(row.get("item_id")) for row in manual_rows if row.get("item_id")}
    manual_ids_for_count.update(str(row.get("item_id")) for row in result_rows if row.get("status") == "manual_required" and row.get("item_id"))
    manual_count = len(manual_ids_for_count)
    pending = max(0, len(item_rows) - len(result_rows))
    mutating_completed = [row.get("item_id") for row in item_rows if row.get("action_type") in {"signoff_release", "reset_signoff", "apply_audio_fix", "activate_baseline", "approve_baseline_change"} and row.get("item_id") in {result.get("item_id") for result in result_rows if result.get("status") == "completed"}]
    checks = [
        _check("release_audio_quality_action_queue_result_item_ids", result_ids.issubset(item_ids), "Action results reference existing items.", {"unknown": sorted(result_ids - item_ids)}),
        _check("release_audio_quality_action_queue_manual_item_ids", manual_ids.issubset(item_ids), "Manual actions reference existing items.", {"unknown": sorted(manual_ids - item_ids)}),
        _check("release_audio_quality_action_queue_summary_counts", _safe_int(data.get("item_count"), -1) == len(item_rows) and _safe_int(data.get("completed_count"), -1) == completed and _safe_int(data.get("blocked_count"), -1) == blocked and _safe_int(data.get("failed_count"), -1) == failed and _safe_int(data.get("pending_count"), -1) == pending, "Queue summary counts match items and results."),
        _check("release_audio_quality_action_queue_manual_count", _safe_int(data.get("manual_required_count"), -1) == manual_count, "Manual required count matches manual actions and results."),
        _check("release_audio_quality_action_queue_no_mutating_completed", not mutating_completed, "Mutating actions were not auto-completed.", {"mutating_completed": mutating_completed}),
    ]
    if require_no_blocking:
        checks.append(_check("release_audio_quality_action_queue_no_blocking", blocked == 0 and failed == 0 and _safe_int(data.get("critical_unhandled_count"), 0) == 0, "Queue has no blocked, failed, or unhandled critical actions.", {"blocked": blocked, "failed": failed, "critical_unhandled": data.get("critical_unhandled_count")}))
    return checks


def _history_checks(history_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not history_rows:
        return [_check("release_audio_quality_action_queue_history_present", True, "Queue history is optional in this package.")]
    previous = None
    failed = []
    for row in history_rows:
        if row.get("previous_event_hash") != previous:
            failed.append(str(row.get("event_id") or "?"))
        expected_payload_hash = stable_hash(row.get("payload") or {})
        expected_event_hash = stable_hash({key: value for key, value in row.items() if key != "event_hash"})
        if row.get("payload_hash") != expected_payload_hash or row.get("event_hash") != expected_event_hash:
            failed.append(str(row.get("event_id") or "?"))
        previous = row.get("event_hash")
    return [_check("release_audio_quality_action_queue_history_chain", not failed, "Queue history hash-chain is valid.", {"failed_events": failed})]


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], names: set[str], *, expected_entries: set[str], strict: bool) -> list[dict[str, Any]]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = expected_entries - {"manifest.json"}
    undeclared = sorted(effective_names - declared)
    extra_declared = sorted(declared - effective_names)
    fixed_extra_declared = sorted(declared - expected_files)
    fixed_missing_declared = sorted(expected_files - declared)
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = archive.getinfo(path)
        data = archive.read(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("release_audio_quality_action_queue_manifest_integrity_hash", _integrity_ok(manifest), "Manifest integrity hash is valid."),
        _check("release_audio_quality_action_queue_manifest_declares_files", not undeclared and not extra_declared, "Manifest files match ZIP entries.", {"undeclared": undeclared, "extra_declared": extra_declared}),
        _check("release_audio_quality_action_queue_manifest_fixed_files", not fixed_extra_declared and not fixed_missing_declared, "Manifest files match fixed Action Queue structure.", {"extra": fixed_extra_declared, "missing": fixed_missing_declared}),
        _check("release_audio_quality_action_queue_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
        _check("release_audio_quality_action_queue_manifest_zip_entries_untrusted", strict or True, "manifest.zip.entries is not used as an allow-list."),
    ]


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SCHEMA_VERSION,
        "status": status,
        "summary": {**summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    return report


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, blocking: bool = True) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_jsonl_entry(archive: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    rows = []
    for line in archive.read(name).decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _semantic_hash(value: Any) -> str:
    def scrub(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: scrub(val) for key, val in sorted(item.items()) if key not in {"created_at", "updated_at", "generated_at", "integrity_hash", "verification_report_hash"}}
        if isinstance(item, list):
            return [scrub(val) for val in item]
        return item

    return stable_hash(scrub(value))


def _normalized_items(items: list[Any]) -> list[dict[str, Any]]:
    rows = [row for row in items if isinstance(row, dict)]
    normalized = []
    for row in rows:
        normalized.append(
            {
                "source_type": row.get("source_type"),
                "source_id": row.get("source_id"),
                "source_check_id": row.get("source_check_id"),
                "severity": row.get("severity"),
                "action_type": row.get("action_type"),
                "execution_mode": row.get("execution_mode"),
                "target": row.get("target"),
                "inputs": row.get("inputs"),
                "requires_manual": row.get("requires_manual"),
                "can_auto_execute": row.get("can_auto_execute"),
            }
        )
    return sorted(normalized, key=lambda row: stable_hash(row))


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    path = Path(name)
    if path.is_absolute():
        return False
    parts = name.split("/")
    return all(part and part not in {".", ".."} and ":" not in part for part in parts)


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    offenders: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            offenders.append(name)
    return _check("release_audio_quality_action_queue_redaction", not offenders, "Package contains no obvious secrets or local workspace paths.", {"offenders": offenders})


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
