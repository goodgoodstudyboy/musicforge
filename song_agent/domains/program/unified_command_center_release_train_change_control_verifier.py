from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.persistence.file_artifacts import read_json_document as read_json, write_json_atomic as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package


UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_change_control"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_change_control_verification"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "change-control-report.json",
    "change-control-index.json",
    "change-request-summaries.json",
    "change-request-history.jsonl",
    "archive-history-index.json",
    "README.txt",
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


def verify_unified_command_center_release_train_change_control_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_reset_applied: bool = False,
    require_current_train: bool = False,
    train_archive_path: Path | str | None = None,
    train_archive_verification_report_path: Path | str | None = None,
    train_signoff_binding_path: Path | str | None = None,
    external_evidence_manifest_path: Path | str | None = None,
    reset_proof_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_train_change_control_zip_exists", False, "Change Control ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_train_change_control_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = [name for name in names if not _is_safe_entry(name)]
            nested = [name for name in names if name.lower().endswith(".zip")]
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.extend(
                [
                    _check("ucc_train_change_control_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("ucc_train_change_control_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("ucc_train_change_control_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("ucc_train_change_control_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("ucc_train_change_control_no_nested_zip", not nested, "Change Control ZIP does not embed ZIP packages.", {"nested": nested}),
                    _check("ucc_train_change_control_allowed_entries", not extra, "Change Control ZIP contains only fixed entries.", {"extra": extra}),
                    _check("ucc_train_change_control_required_entries", not missing, "Change Control ZIP contains all required entries.", {"missing": missing}),
                ]
            )
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "change-control-report.json")
            index = _read_json_entry(archive, "change-control-index.json")
            summaries = _read_json_entry(archive, "change-request-summaries.json")
            archive_history = _read_json_entry(archive, "archive-history-index.json")
            history = _parse_jsonl(archive.read("change-request-history.jsonl").decode("utf-8"))
            summary.update(
                {
                    "train_id": manifest.get("train_id") or report.get("train_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": report.get("status"),
                    "applied_reset_count": report.get("summary", {}).get("applied_reset_count", 0),
                }
            )
            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.extend(
                [
                    _check("ucc_train_change_control_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("ucc_train_change_control_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            for check_id, doc in (
                ("ucc_train_change_control_manifest_integrity", manifest),
                ("ucc_train_change_control_report_integrity", report),
                ("ucc_train_change_control_index_integrity", index),
                ("ucc_train_change_control_summaries_integrity", summaries),
                ("ucc_train_change_control_archive_history_integrity", archive_history),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, report, index, summaries, archive_history))
            checks.extend(_history_checks(history, summaries))
            checks.extend(_reset_semantics_checks(report, summaries, archive_history, require_reset_applied=require_reset_applied))
            checks.extend(_external_reset_proof_checks(reset_proof_path, summaries, require=require_reset_applied))
            checks.extend(
                _current_train_checks(
                    report,
                    require=require_current_train,
                    train_archive_path=train_archive_path,
                    train_archive_verification_report_path=train_archive_verification_report_path,
                    train_signoff_binding_path=train_signoff_binding_path,
                    external_evidence_manifest_path=external_evidence_manifest_path,
                )
            )
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_train_change_control_zip_readable", False, "Change Control ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_release_train_change_control_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_release_train_change_control_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _current_train_checks(
    report: ImplementationDocument,
    *,
    require: bool,
    train_archive_path: Path | str | None,
    train_archive_verification_report_path: Path | str | None,
    train_signoff_binding_path: Path | str | None,
    external_evidence_manifest_path: Path | str | None,
) -> list[ImplementationDocument]:
    if not require:
        return []
    checks: list[dict[str, Any]] = []
    if not train_archive_path or not train_archive_verification_report_path or not train_signoff_binding_path or not external_evidence_manifest_path:
        return [_check("ucc_train_change_control_current_train_external_required", False, "Current Release Train archive, verification report, signoff binding, and evidence manifest are required.")]
    archive_path = Path(train_archive_path)
    verification_path = Path(train_archive_verification_report_path)
    checks.append(_check("ucc_train_change_control_current_train_archive_exists", archive_path.exists(), "Current train archive exists."))
    checks.append(_check("ucc_train_change_control_current_train_verification_exists", verification_path.exists(), "Current train verification report exists."))
    if not archive_path.exists() or not verification_path.exists():
        return checks
    external = _read_json_file(verification_path)
    runtime = verify_unified_command_center_release_train_package(
        archive_path,
        strict=True,
        require_go=True,
        require_signed=True,
        external_evidence_manifest_path=external_evidence_manifest_path,
        signoff_binding_path=train_signoff_binding_path,
    )
    current = report.get("current_train") if isinstance(report.get("current_train"), dict) else {}
    checks.extend(
        [
            _check("ucc_train_change_control_current_train_verification_integrity", _integrity_ok(external), "Current train verification report integrity is valid."),
            _check("ucc_train_change_control_current_train_runtime_passed", runtime.get("status") == "passed", "Current train runtime verification passes.", {"blockers": runtime.get("blockers", [])}),
            _check("ucc_train_change_control_current_train_external_passed", external.get("status") == "passed", "Current train external verification report passed."),
            _check("ucc_train_change_control_current_train_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == current.get("archive_zip_sha256"), "Current train ZIP hash matches report and verification."),
            _check("ucc_train_change_control_current_train_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash") == current.get("archive_manifest_hash"), "Current train manifest hash matches report and verification."),
            _check("ucc_train_change_control_current_train_verification_hash", _integrity_hash(external) == current.get("verification_report_hash"), "Current train verification report hash matches report."),
        ]
    )
    return checks


def _external_reset_proof_checks(path: Path | str | None, summaries: ImplementationDocument, *, require: bool) -> list[ImplementationDocument]:
    applied = [row for row in summaries.get("requests", []) if isinstance(row, dict) and row.get("status") == "applied"]
    if not require:
        return []
    if not applied:
        return [_check("ucc_train_change_control_reset_applied_required", False, "At least one applied reset is required.")]
    if not path:
        return [_check("ucc_train_change_control_external_reset_proof_required", False, "External reset proof is required.")]
    proof_path = Path(path)
    checks = [_check("ucc_train_change_control_external_reset_proof_exists", proof_path.exists(), "External reset proof exists.")]
    if not proof_path.exists():
        return checks
    proof = _read_json_file(proof_path)
    latest = applied[-1]
    checks.extend(
        [
            _check("ucc_train_change_control_external_reset_proof_integrity", _integrity_ok(proof), "External reset proof integrity is valid."),
            _check("ucc_train_change_control_external_reset_proof_hash", proof.get("integrity_hash") == latest.get("reset_proof_hash"), "External reset proof hash matches package summary."),
            _check("ucc_train_change_control_external_reset_request", proof.get("change_request_id") == latest.get("change_request_id"), "External reset proof request id matches."),
            _check("ucc_train_change_control_external_reset_event", proof.get("reset_event_hash") == latest.get("reset_event_hash"), "External reset proof reset event hash matches."),
        ]
    )
    return checks


def _reset_semantics_checks(report: ImplementationDocument, summaries: ImplementationDocument, archive_history: ImplementationDocument, *, require_reset_applied: bool) -> list[ImplementationDocument]:
    requests = [row for row in summaries.get("requests", []) if isinstance(row, dict)]
    applied = [row for row in requests if row.get("status") == "applied"]
    duplicate_applied = sorted({row.get("change_request_id") for row in applied if [item.get("change_request_id") for item in applied].count(row.get("change_request_id")) > 1})
    history_hashes = {row.get("previous_signoff_hash") for row in archive_history.get("items", []) if isinstance(row, dict)}
    missing_history = [row.get("previous_signoff_hash") for row in applied if row.get("previous_signoff_hash") not in history_hashes]
    checks = [
        _check("ucc_train_change_control_applied_cr_single_use", not duplicate_applied, "Applied Change Requests are unique.", {"duplicates": duplicate_applied}),
        _check("ucc_train_change_control_applied_reset_archive_history", not missing_history, "Applied resets have archive-history entries.", {"missing": missing_history}),
        _check("ucc_train_change_control_summary_applied_count", int(report.get("summary", {}).get("applied_reset_count") or 0) == len(applied), "Applied reset count matches request summary."),
    ]
    if require_reset_applied:
        checks.append(_check("ucc_train_change_control_require_reset_applied", bool(applied), "At least one reset was applied."))
    return checks


def _document_binding_checks(manifest: ImplementationDocument, report: ImplementationDocument, index: ImplementationDocument, summaries: ImplementationDocument, archive_history: ImplementationDocument) -> list[ImplementationDocument]:
    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    return [
        _check("ucc_train_change_control_report_hash_binding", source.get("report_hash") == report.get("integrity_hash"), "Manifest binds report."),
        _check("ucc_train_change_control_index_hash_binding", source.get("index_hash") == index.get("integrity_hash"), "Manifest binds index."),
        _check("ucc_train_change_control_summaries_hash_binding", source.get("summaries_hash") == summaries.get("integrity_hash"), "Manifest binds request summaries."),
        _check("ucc_train_change_control_archive_history_hash_binding", source.get("archive_history_hash") == archive_history.get("integrity_hash"), "Manifest binds archive history index."),
        _check("ucc_train_change_control_source_hash_binding", manifest.get("source_hash") == report.get("source_hash") == index.get("source_hash") == summaries.get("source_hash") == archive_history.get("source_hash"), "Source hash is consistent across change-control documents."),
    ]


def _history_checks(history: list[ImplementationDocument], summaries: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    previous_by_request: dict[str, str] = {}
    reset_events = {}
    for index, event in enumerate(history):
        request_id = str(event.get("change_request_id") or "")
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = previous_by_request.get(request_id, "")
        checks.append(_check(f"ucc_train_change_control_history_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History event payload hash is valid."))
        checks.append(_check(f"ucc_train_change_control_history_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"ucc_train_change_control_history_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History hash chain is contiguous within its change request."))
        previous_by_request[request_id] = str(event.get("event_hash") or "")
        if event.get("event_type") == "train_change_request_reset_applied":
            reset_events[request_id] = event
    for request in summaries.get("requests", []):
        if isinstance(request, dict) and request.get("status") == "applied":
            event = reset_events.get(str(request.get("change_request_id") or ""))
            checks.append(_check(f"ucc_train_change_control_reset_event_{_safe_check_key(str(request.get('change_request_id')))}", bool(event) and event.get("reset_event_hash") == request.get("reset_event_hash"), "Applied request has matching reset history event."))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    declared = {str(row.get("path") or "") for row in files}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    checks.append(_check("ucc_train_change_control_manifest_files_fixed", declared == expected_files, "Manifest files match fixed Change Control layout.", {"missing": sorted(expected_files - declared), "extra": sorted(declared - expected_files)}))
    mismatches = []
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in names:
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        data = archive.read(rel)
        if row.get("size_bytes") != len(data) or row.get("sha256") != _sha256_bytes(data):
            mismatches.append({"path": rel, "reason": "hash_or_size"})
    checks.append(_check("ucc_train_change_control_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".jsonl", ".txt", ".md")):
            continue
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                leaks.append(name)
                break
    return _check("ucc_train_change_control_redaction_scan", not leaks, "Change Control text files do not contain obvious secrets or local paths.", {"leaks": sorted(set(leaks))})


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    all_checks = [*checks, *extra]
    blockers = [check["check_id"] for check in all_checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check["check_id"] for check in all_checks if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_CHANGE_CONTROL_SCHEMA_VERSION,
        "status": status,
        "summary": summary,
        "checks": all_checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, severity: str = "blocking") -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message, "details": details or {}}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_json_file(path: Path | str) -> ImplementationDocument:
    return read_json(Path(path))


def _parse_jsonl(text: str) -> list[ImplementationDocument]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    path = Path(name)
    lowered = name.lower()
    return bool(name and not path.is_absolute() and ".." not in path.parts and not lowered.startswith(".musicforge/") and "/.musicforge/" not in lowered)


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


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")[:120] or "row"
