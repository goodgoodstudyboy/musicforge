from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.quality.release_audio_quality_actions_verifier import RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE, verify_release_audio_quality_action_queue_package
from song_agent.application.legacy_dependencies.releases import stable_hash


RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_PACKAGE_TYPE = "release_audio_quality_action_queue_signoff_archive"
RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE = "release_audio_quality_action_queue_signoff_archive_verification"
RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "action-queue.json",
    "source-binding.json",
    "action-items.json",
    "action-results.json",
    "manual-actions.json",
    "manual-resolutions.json",
    "queue-summary.json",
    "queue-verification-report.json",
    "closeout-report.json",
    "action-queue-signoff.json",
    "action-queue-signoff-history.jsonl",
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


def verify_release_audio_quality_action_queue_signoff_archive_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_current_queue: bool = False,
    queue_zip_path: Path | str | None = None,
    queue_verification_report_path: Path | str | None = None,
    observatory_zip_path: Path | str | None = None,
    observatory_verification_report_path: Path | str | None = None,
    evidence_root: Path | str | None = None,
    require_no_unresolved_manual: bool = False,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_path": str(zip_path), "zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None, "queue_id": None, "release_ids": []}
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_quality_action_queue_signoff_archive_zip_exists", False, "Archive ZIP exists."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_quality_action_queue_signoff_archive_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_no_nested_zip", not nested, "ZIP contains no nested ZIP entries.", {"nested": nested}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            extra_entries = sorted(set(names) - REQUIRED_ENTRIES)
            missing_entries = sorted(REQUIRED_ENTRIES - set(names))
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_zip_allowed_entries", not extra_entries, "ZIP contains only fixed signoff archive entries.", {"extra": extra_entries}))
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_zip_expected_entries", not missing_entries, "ZIP contains all required signoff archive entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            queue = _read_json_entry(archive, "action-queue.json")
            source_binding = _read_json_entry(archive, "source-binding.json")
            items = _read_json_entry(archive, "action-items.json")
            results = _read_json_entry(archive, "action-results.json")
            manual_actions = _read_json_entry(archive, "manual-actions.json")
            resolutions = _read_json_entry(archive, "manual-resolutions.json")
            queue_summary = _read_json_entry(archive, "queue-summary.json")
            queue_verification = _read_json_entry(archive, "queue-verification-report.json")
            closeout = _read_json_entry(archive, "closeout-report.json")
            signoff = _read_json_entry(archive, "action-queue-signoff.json")
            history = _read_jsonl_entry(archive, "action-queue-signoff-history.jsonl")

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["queue_id"] = manifest.get("queue_id") or queue.get("queue_id")
            summary["release_ids"] = (closeout.get("summary") or {}).get("release_ids") or (queue_summary.get("summary") or {}).get("release_ids") or []
            summary["closeout_status"] = closeout.get("status")
            summary["signoff_status"] = signoff.get("status")

            documents = {
                "manifest": manifest,
                "queue": queue,
                "source_binding": source_binding,
                "items": items,
                "results": results,
                "manual_actions": manual_actions,
                "manual_resolutions": resolutions,
                "summary": queue_summary,
                "queue_verification": queue_verification,
                "closeout": closeout,
                "signoff": signoff,
            }
            checks.extend(_manifest_checks(archive, manifest, set(names)))
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_PACKAGE_TYPE, "Manifest package_type is release_audio_quality_action_queue_signoff_archive."))
            checks.append(_check("release_audio_quality_action_queue_signoff_archive_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_SCHEMA_VERSION, "Manifest schema version is supported."))
            for check_id, document in (
                ("release_audio_quality_action_queue_signoff_archive_manifest_integrity", manifest),
                ("release_audio_quality_action_queue_signoff_archive_queue_integrity", queue),
                ("release_audio_quality_action_queue_signoff_archive_source_binding_integrity", source_binding),
                ("release_audio_quality_action_queue_signoff_archive_items_integrity", items),
                ("release_audio_quality_action_queue_signoff_archive_results_integrity", results),
                ("release_audio_quality_action_queue_signoff_archive_manual_actions_integrity", manual_actions),
                ("release_audio_quality_action_queue_signoff_archive_manual_resolutions_integrity", resolutions),
                ("release_audio_quality_action_queue_signoff_archive_summary_integrity", queue_summary),
                ("release_audio_quality_action_queue_signoff_archive_queue_verification_integrity", queue_verification),
                ("release_audio_quality_action_queue_signoff_archive_closeout_integrity", closeout),
                ("release_audio_quality_action_queue_signoff_archive_signoff_integrity", signoff),
            ):
                checks.append(_check(check_id, _integrity_ok(document), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(documents, history, require_signed=require_signed, require_no_unresolved_manual=require_no_unresolved_manual))
            if require_current_queue:
                checks.extend(
                    _external_queue_checks(
                        queue,
                        source_binding,
                        items,
                        results,
                        manual_actions,
                        queue_summary,
                        queue_verification,
                        signoff,
                        queue_zip_path=queue_zip_path,
                        queue_verification_report_path=queue_verification_report_path,
                        observatory_zip_path=observatory_zip_path,
                        observatory_verification_report_path=observatory_verification_report_path,
                        evidence_root=evidence_root,
                    )
                )
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_quality_action_queue_signoff_archive_zip_readable", False, "Archive ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_quality_action_queue_signoff_archive_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_quality_action_queue_signoff_archive_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _external_queue_checks(
    queue: dict[str, Any],
    source_binding: dict[str, Any],
    items: dict[str, Any],
    results: dict[str, Any],
    manual_actions: dict[str, Any],
    queue_summary: dict[str, Any],
    queue_verification: dict[str, Any],
    signoff: dict[str, Any],
    *,
    queue_zip_path: Path | str | None,
    queue_verification_report_path: Path | str | None,
    observatory_zip_path: Path | str | None,
    observatory_verification_report_path: Path | str | None,
    evidence_root: Path | str | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not queue_zip_path or not queue_verification_report_path:
        return [_check("release_audio_quality_action_queue_signoff_archive_current_queue_required", False, "Current queue ZIP and queue verification report are required.")]
    queue_zip = Path(queue_zip_path)
    report_path = Path(queue_verification_report_path)
    try:
        external_report = read_json(report_path)
        runtime = verify_release_audio_quality_action_queue_package(
            queue_zip,
            strict=True,
            require_current_observatory=True,
            observatory_zip_path=observatory_zip_path,
            observatory_verification_report_path=observatory_verification_report_path,
            evidence_root=evidence_root,
            require_no_blocking=False,
        )
    except Exception as exc:
        return [_check("release_audio_quality_action_queue_signoff_archive_current_queue_readable", False, f"Current queue evidence could not be verified: {exc}")]
    external_ok = (
        external_report.get("package_type") == RELEASE_AUDIO_QUALITY_ACTION_QUEUE_VERIFICATION_PACKAGE_TYPE
        and _integrity_ok(external_report)
        and external_report.get("status") == "passed"
        and runtime.get("status") == "passed"
        and external_report.get("zip_sha256") == _sha256_path(queue_zip)
        and int(external_report.get("zip_size_bytes") or -1) == queue_zip.stat().st_size
        and external_report.get("manifest_hash") == runtime.get("manifest_hash")
    )
    checks.append(_check("release_audio_quality_action_queue_signoff_archive_current_queue_verification", external_ok, "Queue verification report matches the current queue ZIP."))
    with zipfile.ZipFile(queue_zip) as archive:
        expected_queue = _read_json_entry(archive, "action-queue.json")
        expected_source = _read_json_entry(archive, "source-binding.json")
        expected_items = _read_json_entry(archive, "action-items.json")
        expected_results = _read_json_entry(archive, "action-results.json")
        expected_manual = _read_json_entry(archive, "manual-actions.json")
        expected_summary = _read_json_entry(archive, "queue-summary.json")
    checks.extend(
        [
            _check("release_audio_quality_action_queue_signoff_archive_queue_doc_current", _semantic_hash(queue) == _semantic_hash(expected_queue), "Archive queue document matches current queue ZIP."),
            _check("release_audio_quality_action_queue_signoff_archive_source_doc_current", _semantic_hash(source_binding) == _semantic_hash(expected_source), "Archive source binding matches current queue ZIP."),
            _check("release_audio_quality_action_queue_signoff_archive_items_doc_current", _semantic_hash(items) == _semantic_hash(expected_items), "Archive action items match current queue ZIP."),
            _check("release_audio_quality_action_queue_signoff_archive_results_doc_current", _semantic_hash(results) == _semantic_hash(expected_results), "Archive action results match current queue ZIP."),
            _check("release_audio_quality_action_queue_signoff_archive_manual_doc_current", _semantic_hash(manual_actions) == _semantic_hash(expected_manual), "Archive manual actions match current queue ZIP."),
            _check("release_audio_quality_action_queue_signoff_archive_summary_doc_current", _semantic_hash(queue_summary) == _semantic_hash(expected_summary), "Archive queue summary matches current queue ZIP."),
            _check("release_audio_quality_action_queue_signoff_archive_queue_verification_current", _semantic_hash(queue_verification) == _semantic_hash(_public_queue_verification_report(external_report)), "Archive embeds the current public queue verification projection."),
            _check("release_audio_quality_action_queue_signoff_archive_signoff_queue_zip_binding", (signoff.get("source") or {}).get("queue_zip_sha256") == _sha256_path(queue_zip), "Signoff binds current queue ZIP sha256."),
            _check("release_audio_quality_action_queue_signoff_archive_signoff_queue_manifest_binding", (signoff.get("source") or {}).get("queue_manifest_hash") == runtime.get("manifest_hash"), "Signoff binds current queue manifest hash."),
        ]
    )
    return checks


def _document_binding_checks(documents: dict[str, dict[str, Any]], history: list[dict[str, Any]], *, require_signed: bool, require_no_unresolved_manual: bool) -> list[dict[str, Any]]:
    manifest = documents["manifest"]
    queue = documents["queue"]
    source = documents["source_binding"]
    items = documents["items"]
    results = documents["results"]
    manual = documents["manual_actions"]
    resolutions = documents["manual_resolutions"]
    queue_summary = documents["summary"]
    queue_verification = documents["queue_verification"]
    closeout = documents["closeout"]
    signoff = documents["signoff"]
    manual_summary = resolutions.get("summary") if isinstance(resolutions.get("summary"), dict) else {}
    closeout_source = closeout.get("source") if isinstance(closeout.get("source"), dict) else {}
    signoff_source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
    signoff_event: dict[str, Any] = {}
    for row in reversed(history):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if row.get("event_type") == "action_queue_signoff_created" and payload.get("signoff_hash") == signoff.get("integrity_hash"):
            signoff_event = row
            break
    signoff_payload = signoff_event.get("payload") if isinstance(signoff_event.get("payload"), dict) else {}
    checks = [
        _check("release_audio_quality_action_queue_signoff_archive_manifest_queue_binding", manifest.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds signoff hash."),
        _check("release_audio_quality_action_queue_signoff_archive_manifest_closeout_binding", manifest.get("closeout_hash") == closeout.get("integrity_hash"), "Manifest binds closeout hash."),
        _check("release_audio_quality_action_queue_signoff_archive_manifest_queue_verification_binding", manifest.get("queue_verification_report_hash") == queue_verification.get("original_integrity_hash") and manifest.get("embedded_queue_verification_report_hash") == queue_verification.get("integrity_hash"), "Manifest binds queue verification report and embedded public projection."),
        _check("release_audio_quality_action_queue_signoff_archive_closeout_queue_binding", closeout_source.get("queue_integrity_hash") == queue.get("integrity_hash") and closeout_source.get("source_binding_hash") == source.get("integrity_hash") and closeout_source.get("items_hash") == items.get("integrity_hash") and closeout_source.get("results_hash") == results.get("integrity_hash") and closeout_source.get("manual_actions_hash") == manual.get("integrity_hash"), "Closeout binds queue documents."),
        _check("release_audio_quality_action_queue_signoff_archive_closeout_resolution_binding", closeout_source.get("manual_resolutions_hash") == resolutions.get("integrity_hash"), "Closeout binds manual resolutions."),
        _check("release_audio_quality_action_queue_signoff_archive_closeout_verification_binding", closeout_source.get("queue_verification_report_hash") == queue_verification.get("original_integrity_hash"), "Closeout binds original queue verification report."),
        _check("release_audio_quality_action_queue_signoff_archive_closeout_status", closeout.get("status") == "passed", "Closeout status is passed."),
        _check("release_audio_quality_action_queue_signoff_archive_signoff_present", signoff.get("status") == "signed" if require_signed else bool(signoff), "Signoff is signed when required."),
        _check("release_audio_quality_action_queue_signoff_archive_signoff_closeout_binding", signoff_source.get("closeout_hash") == closeout.get("integrity_hash"), "Signoff binds closeout."),
        _check("release_audio_quality_action_queue_signoff_archive_signoff_resolution_binding", signoff_source.get("manual_resolutions_hash") == resolutions.get("integrity_hash"), "Signoff binds manual resolutions."),
        _check("release_audio_quality_action_queue_signoff_archive_signoff_verification_binding", signoff_source.get("queue_verification_report_hash") == queue_verification.get("original_integrity_hash"), "Signoff binds original queue verification report."),
        _check("release_audio_quality_action_queue_signoff_archive_history_chain", _history_chain_ok(history), "Signoff history hash-chain is valid."),
        _check("release_audio_quality_action_queue_signoff_archive_history_signoff_event", bool(signoff_event), "Signoff history contains an event for the archived signoff."),
        _check("release_audio_quality_action_queue_signoff_archive_history_payload_binding", signoff_payload.get("signoff_payload_hash") == signoff.get("payload_hash") and signoff_payload.get("closeout_hash") == closeout.get("integrity_hash"), "Signoff history payload binds signoff payload and closeout."),
    ]
    if require_no_unresolved_manual:
        checks.append(_check("release_audio_quality_action_queue_signoff_archive_no_unresolved_manual", int(manual_summary.get("unresolved_count") or 0) == 0 and int(manual_summary.get("rejected_count") or 0) == 0 and int(manual_summary.get("deferred_count") or 0) == 0, "Manual actions are fully resolved.", manual_summary))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], names: set[str]) -> list[dict[str, Any]]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
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
        _check("release_audio_quality_action_queue_signoff_archive_manifest_integrity_hash", _integrity_ok(manifest), "Manifest integrity hash is valid."),
        _check("release_audio_quality_action_queue_signoff_archive_manifest_declares_files", declared == effective_names, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective_names), "undeclared": sorted(effective_names - declared)}),
        _check("release_audio_quality_action_queue_signoff_archive_manifest_fixed_files", declared == expected_files, "Manifest files match fixed signoff archive structure.", {"extra": sorted(declared - expected_files), "missing": sorted(expected_files - declared)}),
        _check("release_audio_quality_action_queue_signoff_archive_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
        _check("release_audio_quality_action_queue_signoff_archive_manifest_zip_entries_untrusted", True, "manifest.zip.entries is not used as an allow-list."),
    ]


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_QUALITY_ACTION_QUEUE_SIGNOFF_ARCHIVE_SCHEMA_VERSION,
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


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, blocking: bool = True) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    data = json.loads(archive.read(name).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


def _read_jsonl_entry(archive: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in archive.read(name).decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _history_chain_ok(history: list[dict[str, Any]]) -> bool:
    previous: str | None = None
    for event in history:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(payload):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = str(event.get("event_hash") or "")
    return bool(history)


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _semantic_hash(value: Any) -> str:
    def scrub(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: scrub(val) for key, val in sorted(item.items()) if key not in {"created_at", "updated_at", "generated_at", "integrity_hash"}}
        if isinstance(item, list):
            return [scrub(val) for val in item]
        return item

    return stable_hash(scrub(value))


def _public_queue_verification_report(report: dict[str, Any]) -> dict[str, Any]:
    public = {
        key: value
        for key, value in report.items()
        if key not in {"summary", "checks", "integrity_hash"}
    }
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    public["summary"] = {key: value for key, value in summary.items() if key != "zip_path"}
    public["original_integrity_hash"] = report.get("integrity_hash")
    public["integrity_hash"] = _integrity_hash(public)
    return public


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
    return _check("release_audio_quality_action_queue_signoff_archive_redaction", not offenders, "Archive contains no obvious secrets or local workspace paths.", {"offenders": offenders})


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
