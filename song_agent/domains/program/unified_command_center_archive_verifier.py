from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_verifier import UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_package as verify_unified_command_center_package


UNIFIED_COMMAND_CENTER_ARCHIVE_PACKAGE_TYPE = "musicforge_unified_command_center_archive"
UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_archive_verification"
UNIFIED_COMMAND_CENTER_ARCHIVE_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "README.txt",
    "manifest.json",
    "center.json",
    "command-center-report.json",
    "readiness-matrix.json",
    "evidence-inventory.json",
    "verification-report.json",
    "signoff.json",
    "signoff-binding-summary.json",
    "signoff-history.jsonl",
    "change-requests.json",
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


def verify_unified_command_center_archive_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_current_ucc: bool = False,
    command_center_zip_path: Path | str | None = None,
    command_center_verification_report_path: Path | str | None = None,
    signoff_binding_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_archive_zip_exists", False, "Unified Command Center Archive ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_archive_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_archive_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_archive_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_archive_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("ucc_archive_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.append(_check("ucc_archive_allowed_entries", not extra, "Archive ZIP contains only fixed entries.", {"extra": extra}))
            checks.append(_check("ucc_archive_required_entries", not missing, "Archive ZIP contains all required entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            center = _read_json_entry(archive, "center.json")
            report = _read_json_entry(archive, "command-center-report.json")
            readiness = _read_json_entry(archive, "readiness-matrix.json")
            inventory = _read_json_entry(archive, "evidence-inventory.json")
            verification = _read_json_entry(archive, "verification-report.json")
            signoff = _read_json_entry(archive, "signoff.json")
            signoff_binding = _read_json_entry(archive, "signoff-binding-summary.json")
            change_requests = _read_json_entry(archive, "change-requests.json")
            history_text = archive.read("signoff-history.jsonl").decode("utf-8")
            history = _parse_jsonl(history_text)

            summary.update({"center_id": manifest.get("center_id"), "manifest_hash": manifest.get("integrity_hash"), "signoff_hash": signoff.get("integrity_hash")})
            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.append(_check("ucc_archive_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_ARCHIVE_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_archive_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            for check_id, doc in (
                ("ucc_archive_center_integrity", center),
                ("ucc_archive_report_integrity", report),
                ("ucc_archive_readiness_integrity", readiness),
                ("ucc_archive_inventory_integrity", inventory),
                ("ucc_archive_verification_integrity", verification),
                ("ucc_archive_signoff_integrity", signoff),
                ("ucc_archive_signoff_binding_integrity", signoff_binding),
                ("ucc_archive_change_requests_integrity", change_requests),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_history_checks(history, signoff))
            checks.extend(_signoff_binding_checks(signoff_binding, signoff, history, verification))
            if signoff_binding_path:
                checks.extend(_external_signoff_binding_checks(signoff_binding_path, signoff_binding))
            source = _as_document(manifest.get("source"))
            checks.extend(
                [
                    _check("ucc_archive_signoff_status", signoff.get("status") == "signed" or not require_signed, "Signoff is signed when required."),
                    _check("ucc_archive_center_binding", source.get("center_hash") == center.get("integrity_hash"), "Archive binds center hash."),
                    _check("ucc_archive_report_binding", source.get("report_hash") == report.get("integrity_hash") == signoff.get("report_hash"), "Archive binds signed report hash."),
                    _check("ucc_archive_readiness_binding", source.get("readiness_hash") == readiness.get("integrity_hash") == signoff.get("readiness_hash"), "Archive binds readiness matrix hash."),
                    _check("ucc_archive_inventory_binding", source.get("inventory_hash") == inventory.get("integrity_hash") == signoff.get("inventory_hash"), "Archive binds inventory hash."),
                    _check("ucc_archive_verification_binding", source.get("verification_hash") == verification.get("integrity_hash") == signoff.get("verification_hash"), "Archive binds UCC verification report hash."),
                    _check("ucc_archive_signoff_binding", source.get("signoff_binding_hash") == signoff_binding.get("integrity_hash"), "Archive binds signoff binding summary hash."),
                    _check("ucc_archive_ucc_zip_binding", source.get("ucc_zip_sha256") == signoff.get("ucc_zip_sha256") == verification.get("zip_sha256"), "Archive binds verified UCC ZIP sha256."),
                    _check("ucc_archive_ucc_manifest_binding", source.get("ucc_manifest_hash") == signoff.get("ucc_manifest_hash") == verification.get("manifest_hash"), "Archive binds verified UCC manifest hash."),
                    _check("ucc_archive_verification_package_type", verification.get("package_type") == UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, "UCC verification package type is valid."),
                    _check("ucc_archive_verification_status", verification.get("status") == "passed", "UCC verification report is passed."),
                ]
            )
            if require_current_ucc:
                checks.extend(_current_ucc_checks(command_center_zip_path, command_center_verification_report_path, signoff))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_archive_zip_readable", False, "Unified Command Center Archive ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_archive_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_archive_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _current_ucc_checks(zip_path: Path | str | None, report_path: Path | str | None, signoff: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    if not zip_path:
        return [_check("ucc_archive_current_ucc_zip_required", False, "Current UCC ZIP is required.")]
    if not report_path:
        return [_check("ucc_archive_current_ucc_verification_required", False, "Current UCC verification report is required.")]
    zip_path = Path(zip_path)
    report_path = Path(report_path)
    checks.append(_check("ucc_archive_current_ucc_zip_exists", zip_path.exists(), "Current UCC ZIP exists."))
    checks.append(_check("ucc_archive_current_ucc_verification_exists", report_path.exists(), "Current UCC verification report exists."))
    if any(check["status"] == "failed" for check in checks):
        return checks
    external = _read_json_file(report_path)
    manifest_hash = _zip_manifest_hash(zip_path)
    actual_sha = _sha256_path(zip_path)
    checks.extend(
        [
            _check("ucc_archive_current_verification_integrity", _integrity_ok(external), "Current UCC verification report integrity is valid."),
            _check("ucc_archive_current_verification_package_type", external.get("package_type") == UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, "Current UCC verification report package type is valid."),
            _check("ucc_archive_current_verification_status", external.get("status") == "passed", "Current UCC verification report is passed.", {"external_status": external.get("status")}),
            _check("ucc_archive_current_zip_binding", signoff.get("ucc_zip_sha256") == actual_sha == external.get("zip_sha256"), "Current UCC ZIP matches signoff."),
            _check("ucc_archive_current_manifest_binding", signoff.get("ucc_manifest_hash") == external.get("manifest_hash") == manifest_hash, "Current UCC manifest matches signoff."),
            _check("ucc_archive_current_verification_binding", signoff.get("verification_hash") == external.get("integrity_hash"), "Current UCC verification report matches signoff."),
        ]
    )
    return checks


def _zip_manifest_hash(zip_path: Path | str) -> str | None:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            manifest = _read_json_entry(archive, "manifest.json")
            return manifest.get("integrity_hash")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return None


def _history_checks(history: list[ImplementationDocument], signoff: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    previous = ""
    created_event: dict[str, Any] | None = None
    for index, event in enumerate(history):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        expected_event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"ucc_archive_history_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History event payload hash is valid."))
        checks.append(_check(f"ucc_archive_history_{index:03d}_event_hash", event.get("event_hash") == expected_event_hash, "History event hash is valid."))
        checks.append(_check(f"ucc_archive_history_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History event chain is contiguous."))
        previous = str(event.get("event_hash") or "")
        if event.get("event_type") == "ucc_signoff_created":
            created_event = event
    checks.append(_check("ucc_archive_history_has_signoff_event", bool(created_event), "History contains a signoff event."))
    if created_event:
        checks.extend(
            [
                _check("ucc_archive_history_signoff_hash", created_event.get("signoff_hash") == signoff.get("integrity_hash"), "History signoff hash matches signoff."),
                _check("ucc_archive_history_signed_by", created_event.get("signed_by") == signoff.get("signed_by"), "History signed_by matches signoff."),
                _check("ucc_archive_history_report_hash", created_event.get("report_hash") == signoff.get("report_hash"), "History report hash matches signoff."),
            ]
        )
    return checks


def _external_signoff_binding_checks(binding_path: Path | str, packaged_binding: ImplementationDocument) -> list[ImplementationDocument]:
    path = Path(binding_path)
    checks = [_check("ucc_archive_external_signoff_binding_exists", path.exists(), "External signoff binding summary exists.")]
    if not path.exists():
        return checks
    external = _read_json_file(path)
    checks.extend(
        [
            _check("ucc_archive_external_signoff_binding_integrity", _integrity_ok(external), "External signoff binding integrity is valid."),
            _check("ucc_archive_external_signoff_binding_hash", external.get("integrity_hash") == packaged_binding.get("integrity_hash"), "Packaged signoff binding matches external signoff binding."),
            _check("ucc_archive_external_signoff_binding_payload", stable_hash({key: value for key, value in external.items() if key != "integrity_hash"}) == packaged_binding.get("integrity_hash"), "External signoff binding payload matches packaged binding hash."),
        ]
    )
    return checks


def _signoff_binding_checks(binding: ImplementationDocument, signoff: ImplementationDocument, history: list[ImplementationDocument], verification: ImplementationDocument) -> list[ImplementationDocument]:
    created_event = next((event for event in history if event.get("event_type") == "ucc_signoff_created"), None)
    source = _as_document(binding.get("source"))
    checks = [
        _check("ucc_archive_signoff_binding_package_type", binding.get("package_type") == "musicforge_unified_command_center_signoff_binding", "Signoff binding package type is valid."),
        _check("ucc_archive_signoff_binding_signoff_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Signoff binding matches signoff hash."),
        _check("ucc_archive_signoff_binding_payload_hash", binding.get("signoff_payload_hash") == signoff.get("payload_hash"), "Signoff binding matches signoff payload hash."),
        _check("ucc_archive_signoff_binding_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Signoff binding matches signed_by."),
        _check("ucc_archive_signoff_binding_role", binding.get("role") == signoff.get("role"), "Signoff binding matches role."),
        _check("ucc_archive_signoff_binding_reason", binding.get("reason") == signoff.get("reason"), "Signoff binding matches reason."),
        _check("ucc_archive_signoff_binding_signed_at", binding.get("signed_at") == signoff.get("signed_at"), "Signoff binding matches signed_at."),
        _check("ucc_archive_signoff_binding_source_hash", source.get("source_hash") == signoff.get("source_hash"), "Signoff binding matches source hash."),
        _check("ucc_archive_signoff_binding_report_hash", source.get("report_hash") == signoff.get("report_hash"), "Signoff binding matches report hash."),
        _check("ucc_archive_signoff_binding_readiness_hash", source.get("readiness_hash") == signoff.get("readiness_hash"), "Signoff binding matches readiness hash."),
        _check("ucc_archive_signoff_binding_inventory_hash", source.get("inventory_hash") == signoff.get("inventory_hash"), "Signoff binding matches inventory hash."),
        _check("ucc_archive_signoff_binding_verification_hash", source.get("verification_hash") == signoff.get("verification_hash") == verification.get("integrity_hash"), "Signoff binding matches verification hash."),
        _check("ucc_archive_signoff_binding_ucc_zip_sha", source.get("ucc_zip_sha256") == signoff.get("ucc_zip_sha256") == verification.get("zip_sha256"), "Signoff binding matches UCC ZIP sha256."),
        _check("ucc_archive_signoff_binding_ucc_manifest", source.get("ucc_manifest_hash") == signoff.get("ucc_manifest_hash") == verification.get("manifest_hash"), "Signoff binding matches UCC manifest hash."),
    ]
    if created_event:
        checks.extend(
            [
                _check("ucc_archive_signoff_binding_history_event_hash", binding.get("history_event_hash") == created_event.get("event_hash"), "Signoff binding matches history signoff event hash."),
                _check("ucc_archive_signoff_binding_history_payload_hash", binding.get("history_event_payload_hash") == created_event.get("payload_hash"), "Signoff binding matches history signoff event payload hash."),
                _check("ucc_archive_signoff_binding_history_previous", str(binding.get("history_previous_event_hash") or "") == str(created_event.get("previous_event_hash") or ""), "Signoff binding matches history previous event hash."),
            ]
        )
    else:
        checks.append(_check("ucc_archive_signoff_binding_history_event_hash", False, "Signoff binding requires a history signoff event."))
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    files = _as_list(manifest.get("files"))
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
        _check("ucc_archive_manifest_declares_files", declared == effective, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective), "undeclared": sorted(effective - declared)}),
        _check("ucc_archive_manifest_fixed_files", declared == expected, "Manifest files match fixed archive structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
        _check("ucc_archive_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
    ]


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_ARCHIVE_SCHEMA_VERSION,
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


def _parse_jsonl(text: str) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


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
    return _check("ucc_archive_redaction_scan", not offenders, "Archive text files contain no obvious secrets or local workspace paths.", {"offenders": offenders})


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
