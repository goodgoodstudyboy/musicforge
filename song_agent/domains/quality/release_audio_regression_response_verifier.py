from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.quality.release_audio_regression_verifier import verify_release_audio_regression_package as verify_release_audio_regression_package
from song_agent.domains.delivery.releases import stable_hash as stable_hash


RELEASE_AUDIO_REGRESSION_RESPONSE_PACKAGE_TYPE = "release_audio_regression_response"
RELEASE_AUDIO_REGRESSION_RESPONSE_VERIFICATION_PACKAGE_TYPE = "release_audio_regression_response_verification"
RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "response-plan.json",
    "action-items.json",
    "waiver-register.json",
    "recheck-closeout.json",
    "regression-binding.json",
    "README.txt",
}
OPTIONAL_ENTRIES = {"response-signoff.json", "response-signoff-history.jsonl"}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_release_audio_regression_response_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_closed: bool = False,
    require_signed: bool = False,
    require_regression_current: bool = False,
    release_audio_regression_path: Path | str | None = None,
    release_audio_regression_verification_report_path: Path | str | None = None,
    baseline_timeline_path: Path | str | None = None,
    baseline_timeline_verification_report_path: Path | str | None = None,
    baseline_certification_path: Path | str | None = None,
    baseline_certification_verification_report_path: Path | str | None = None,
    current_timeline_path: Path | str | None = None,
    current_timeline_verification_report_path: Path | str | None = None,
    current_certification_path: Path | str | None = None,
    current_certification_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
        "release_id": None,
        "response_id": None,
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_regression_response_zip_exists", False, "Release Audio Regression Response ZIP exists."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_regression_response_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_regression_response_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("release_audio_regression_response_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_regression_response_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("release_audio_regression_response_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            expected_entries = set(REQUIRED_ENTRIES)
            if "response-signoff.json" in name_set:
                expected_entries.add("response-signoff.json")
            if "response-signoff-history.jsonl" in name_set:
                expected_entries.add("response-signoff-history.jsonl")
            extra = sorted(name_set - expected_entries)
            missing = sorted(expected_entries - name_set)
            checks.append(_check("release_audio_regression_response_zip_allowed_entries", not extra, "ZIP contains only fixed Response entries.", {"extra": extra}))
            checks.append(_check("release_audio_regression_response_zip_expected_entries", not missing, "ZIP contains all expected Response entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            plan = _read_json_entry(archive, "response-plan.json")
            actions = _read_json_entry(archive, "action-items.json")
            waivers = _read_json_entry(archive, "waiver-register.json")
            closeout = _read_json_entry(archive, "recheck-closeout.json")
            binding = _read_json_entry(archive, "regression-binding.json")
            signoff = _read_json_entry(archive, "response-signoff.json") if "response-signoff.json" in name_set else None
            history = _read_jsonl_entry(archive, "response-signoff-history.jsonl") if "response-signoff-history.jsonl" in name_set else []

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["release_id"] = plan.get("release_id") or manifest.get("release_id")
            summary["response_id"] = plan.get("response_id") or manifest.get("response_id")

            checks.extend(_manifest_checks(archive, manifest, name_set, expected_entries=expected_entries, strict=strict))
            checks.append(_check("release_audio_regression_response_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_REGRESSION_RESPONSE_PACKAGE_TYPE, "Manifest package_type is release_audio_regression_response."))
            checks.append(_check("release_audio_regression_response_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION, "Manifest schema version is supported."))
            for check_id, document in (
                ("release_audio_regression_response_manifest_integrity", manifest),
                ("release_audio_regression_response_plan_integrity", plan),
                ("release_audio_regression_response_actions_integrity", actions),
                ("release_audio_regression_response_waivers_integrity", waivers),
                ("release_audio_regression_response_closeout_integrity", closeout),
                ("release_audio_regression_response_binding_integrity", binding),
            ):
                checks.append(_check(check_id, _integrity_ok(document), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, plan, actions, waivers, closeout, binding))
            checks.extend(_semantic_checks(plan, actions, waivers, closeout, require_closed=require_closed))
            checks.extend(_regression_current_checks(
                binding,
                require_regression_current=require_regression_current,
                release_audio_regression_path=release_audio_regression_path,
                release_audio_regression_verification_report_path=release_audio_regression_verification_report_path,
                baseline_timeline_path=baseline_timeline_path,
                baseline_timeline_verification_report_path=baseline_timeline_verification_report_path,
                baseline_certification_path=baseline_certification_path,
                baseline_certification_verification_report_path=baseline_certification_verification_report_path,
                current_timeline_path=current_timeline_path,
                current_timeline_verification_report_path=current_timeline_verification_report_path,
                current_certification_path=current_certification_path,
                current_certification_verification_report_path=current_certification_verification_report_path,
            ))
            checks.extend(_signoff_checks(signoff, history, manifest, plan, actions, waivers, closeout, binding, require_signed=require_signed))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_regression_response_zip_readable", False, "Release Audio Regression Response ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_regression_response_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_regression_response_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def _semantic_checks(plan: ImplementationDocument, actions: ImplementationDocument, waivers: ImplementationDocument, closeout: ImplementationDocument, *, require_closed: bool) -> list[ImplementationDocument]:
    action_rows = _as_list(actions.get("actions"))
    waiver_rows = _as_list(waivers.get("waivers"))
    high_or_critical_waivers = [row.get("action_id") for row in waiver_rows if str(row.get("severity") or "").lower() in {"high", "critical", "blocking"}]
    unsafe_actions = [row.get("action_id") for row in action_rows if row.get("execution_mode") not in {"draft_only", "manual_required"}]
    closed_ok = closeout.get("status") == "closed" and closeout.get("regression_status_after_recheck") == "passed"
    return [
        _check("release_audio_regression_response_action_modes", not unsafe_actions, "Response actions are draft-only or manual-required.", {"unsafe_actions": unsafe_actions}),
        _check("release_audio_regression_response_high_critical_not_waived", not high_or_critical_waivers, "High and critical regression blockers are not waived.", {"waivers": high_or_critical_waivers}),
        _check("release_audio_regression_response_closeout_status", closed_ok or not require_closed, "Response closeout is closed with passed recheck when required.", {"closeout_status": closeout.get("status"), "regression_status": closeout.get("regression_status_after_recheck")}),
        _check("release_audio_regression_response_plan_status_binding", plan.get("status") in {"open", "closed", "passed", "needs_response"}, "Response plan status is valid."),
    ]


def _regression_current_checks(
    binding: ImplementationDocument,
    *,
    require_regression_current: bool,
    release_audio_regression_path: Path | str | None,
    release_audio_regression_verification_report_path: Path | str | None,
    baseline_timeline_path: Path | str | None,
    baseline_timeline_verification_report_path: Path | str | None,
    baseline_certification_path: Path | str | None,
    baseline_certification_verification_report_path: Path | str | None,
    current_timeline_path: Path | str | None,
    current_timeline_verification_report_path: Path | str | None,
    current_certification_path: Path | str | None,
    current_certification_verification_report_path: Path | str | None,
) -> list[ImplementationDocument]:
    if not require_regression_current:
        return []
    if not release_audio_regression_path or not release_audio_regression_verification_report_path:
        return [_check("release_audio_regression_response_regression_current_required", False, "Current Regression ZIP and verification report are required.")]
    try:
        zip_path = Path(release_audio_regression_path)
        external_report = read_json(Path(release_audio_regression_verification_report_path))
        runtime = verify_release_audio_regression_package(
            zip_path,
            strict=True,
            require_passed=True,
            require_signed=True,
            require_current=True,
            require_baseline_current=True,
            baseline_timeline_path=baseline_timeline_path,
            baseline_timeline_verification_report_path=baseline_timeline_verification_report_path,
            baseline_certification_path=baseline_certification_path,
            baseline_certification_verification_report_path=baseline_certification_verification_report_path,
            current_timeline_path=current_timeline_path,
            current_timeline_verification_report_path=current_timeline_verification_report_path,
            current_certification_path=current_certification_path,
            current_certification_verification_report_path=current_certification_verification_report_path,
        )
        ok = (
            runtime.get("status") == "passed"
            and external_report.get("status") == "passed"
            and _integrity_ok(external_report)
            and external_report.get("zip_sha256") == _sha256_path(zip_path)
            and external_report.get("zip_size_bytes") == zip_path.stat().st_size
            and external_report.get("manifest_hash") == runtime.get("manifest_hash")
            and binding.get("regression_zip_sha256") == external_report.get("zip_sha256")
            and binding.get("regression_manifest_hash") == external_report.get("manifest_hash")
            and binding.get("regression_verification_report_hash") == external_report.get("integrity_hash")
        )
        return [_check("release_audio_regression_response_regression_current", ok, "Response binds current passed Regression Guard evidence.", {"runtime_status": runtime.get("status"), "external_status": external_report.get("status")})]
    except Exception as exc:
        return [_check("release_audio_regression_response_regression_current", False, "Response current Regression check failed.", {"error": str(exc)})]


def _document_binding_checks(manifest: ImplementationDocument, plan: ImplementationDocument, actions: ImplementationDocument, waivers: ImplementationDocument, closeout: ImplementationDocument, binding: ImplementationDocument) -> list[ImplementationDocument]:
    source_hashes = {plan.get("source_hash"), actions.get("source_hash"), waivers.get("source_hash"), closeout.get("source_hash"), binding.get("source_hash")}
    return [
        _check("release_audio_regression_response_manifest_plan_binding", manifest.get("plan_hash") == plan.get("integrity_hash"), "Manifest binds response plan."),
        _check("release_audio_regression_response_manifest_actions_binding", manifest.get("actions_hash") == actions.get("integrity_hash"), "Manifest binds actions."),
        _check("release_audio_regression_response_manifest_waivers_binding", manifest.get("waivers_hash") == waivers.get("integrity_hash"), "Manifest binds waiver register."),
        _check("release_audio_regression_response_manifest_closeout_binding", manifest.get("closeout_hash") == closeout.get("integrity_hash"), "Manifest binds closeout."),
        _check("release_audio_regression_response_manifest_regression_binding", manifest.get("regression_binding_hash") == binding.get("integrity_hash"), "Manifest binds Regression evidence."),
        _check("release_audio_regression_response_source_binding", len(source_hashes) == 1 and manifest.get("source_hash") in source_hashes, "Response documents bind the same source hash."),
    ]


def _signoff_checks(signoff: ImplementationDocument | None, history: list[ImplementationDocument], manifest: ImplementationDocument, plan: ImplementationDocument, actions: ImplementationDocument, waivers: ImplementationDocument, closeout: ImplementationDocument, binding: ImplementationDocument, *, require_signed: bool) -> list[ImplementationDocument]:
    if signoff is None:
        return [_check("release_audio_regression_response_signoff_present", not require_signed, "Response signoff is present when required.")]
    latest = history[-1] if history else {}
    return [
        _check("release_audio_regression_response_signoff_integrity", _integrity_ok(signoff), "Response signoff integrity is valid."),
        _check("release_audio_regression_response_signoff_status", signoff.get("status") == "signed", "Response signoff status is signed."),
        _check("release_audio_regression_response_signoff_plan_binding", signoff.get("plan_hash") == plan.get("integrity_hash"), "Signoff binds response plan."),
        _check("release_audio_regression_response_signoff_actions_binding", signoff.get("actions_hash") == actions.get("integrity_hash"), "Signoff binds actions."),
        _check("release_audio_regression_response_signoff_waivers_binding", signoff.get("waivers_hash") == waivers.get("integrity_hash"), "Signoff binds waivers."),
        _check("release_audio_regression_response_signoff_closeout_binding", signoff.get("closeout_hash") == closeout.get("integrity_hash"), "Signoff binds closeout."),
        _check("release_audio_regression_response_signoff_regression_binding", signoff.get("regression_binding_hash") == binding.get("integrity_hash"), "Signoff binds Regression evidence."),
        _check("release_audio_regression_response_manifest_signoff_binding", manifest.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds response signoff."),
        _check("release_audio_regression_response_signoff_history_chain", _history_chain_ok(history), "Response signoff history hash chain is valid."),
        _check("release_audio_regression_response_signoff_history_latest", (latest.get("payload") or {}).get("signoff_hash") == signoff.get("integrity_hash"), "Latest signoff history event binds current signoff."),
    ]


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str], *, expected_entries: set[str], strict: bool) -> list[ImplementationDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = expected_entries - {"manifest.json"}
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
    zip_entries = set((manifest.get("zip") or {}).get("entries") or [])
    return [
        _check("release_audio_regression_response_manifest_files_present", bool(files), "Manifest declares package files."),
        _check("release_audio_regression_response_manifest_fixed_files", declared == expected_files and effective_names == expected_files, "Manifest and ZIP match fixed Response layout.", {"declared": sorted(declared), "actual": sorted(effective_names), "expected": sorted(expected_files)}),
        _check("release_audio_regression_response_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}),
        _check("release_audio_regression_response_manifest_zip_entries_not_authoritative", not strict or not zip_entries or zip_entries == names, "manifest.zip.entries does not extend package contents."),
    ]


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": RELEASE_AUDIO_REGRESSION_RESPONSE_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_REGRESSION_RESPONSE_SCHEMA_VERSION,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "ok": not blockers,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
        "summary": {**summary, "check_count": len(checks), "blocker_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": [check.get("check_id") for check in blockers],
        "warnings": [check.get("check_id") for check in warnings],
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, blocking: bool = True) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    with archive.open(name) as handle:
        data = json.loads(handle.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


def _read_jsonl_entry(archive: zipfile.ZipFile, name: str) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    with archive.open(name) as handle:
        for raw in handle.read().decode("utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            if not isinstance(item, dict):
                raise ValueError(f"{name} must contain JSON objects.")
            rows.append(item)
    return rows


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    if not name or name.startswith("/") or name.startswith("../") or "/../" in name or name.endswith("/.."):
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered or lowered.endswith(".zip"):
        return False
    return True


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt", ".jsonl")):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("release_audio_regression_response_redaction_scan", not leaks, "Package text files do not contain obvious secrets or local paths.", {"leaks": leaks})


def _history_chain_ok(history: list[ImplementationDocument]) -> bool:
    previous: str | None = None
    for event in history:
        payload = _as_document(event.get("payload"))
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(payload):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = str(event.get("event_hash") or "")
    return bool(history)


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
