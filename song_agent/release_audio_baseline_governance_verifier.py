from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.release_audio_regression_verifier import _external_facts
from song_agent.releases import stable_hash


RELEASE_AUDIO_BASELINE_REGISTRY_PACKAGE_TYPE = "release_audio_baseline_registry"
RELEASE_AUDIO_BASELINE_REGISTRY_VERIFICATION_PACKAGE_TYPE = "release_audio_baseline_registry_verification"
RELEASE_AUDIO_BASELINE_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "registry.json",
    "registry-report.json",
    "active-baselines.json",
    "README.txt",
}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_release_audio_baseline_registry_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_active: bool = False,
    baseline_evidence: dict[str, dict[str, Any]] | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
        "baseline_count": 0,
        "active_count": 0,
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("audio_baseline_registry_zip_exists", False, "Baseline Registry ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("audio_baseline_registry_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("audio_baseline_registry_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("audio_baseline_registry_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("audio_baseline_registry_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("audio_baseline_registry_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            allowed = set(REQUIRED_ENTRIES)
            baseline_ids = sorted(
                {
                    parts[1]
                    for name in name_set
                    for parts in [name.split("/")]
                    if len(parts) == 3 and parts[0] == "baselines" and parts[2] == "baseline.json" and parts[1]
                }
            )
            allowed.update(f"baselines/{baseline_id}/baseline.json" for baseline_id in baseline_ids)
            extra = sorted(name for name in name_set if name not in allowed)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.append(_check("audio_baseline_registry_zip_allowed_entries", not extra, "ZIP contains only Baseline Registry entries.", {"extra": extra}))
            checks.append(_check("audio_baseline_registry_zip_expected_entries", not missing, "ZIP contains required Baseline Registry entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            registry = _read_json_entry(archive, "registry.json")
            report = _read_json_entry(archive, "registry-report.json")
            active = _read_json_entry(archive, "active-baselines.json")
            baselines = _read_baselines(archive, names)
            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["baseline_count"] = len(baselines)
            summary["active_count"] = len([baseline for baseline in baselines if baseline.get("status") == "active"])

            checks.extend(_manifest_checks(archive, manifest, name_set, strict=strict))
            checks.append(_check("audio_baseline_registry_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_BASELINE_REGISTRY_PACKAGE_TYPE, "Manifest package_type is release_audio_baseline_registry."))
            checks.append(_check("audio_baseline_registry_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_BASELINE_SCHEMA_VERSION, "Manifest schema version is supported."))
            checks.append(_check("audio_baseline_registry_manifest_integrity", _integrity_ok(manifest), "Manifest integrity is valid."))
            checks.append(_check("audio_baseline_registry_integrity", _integrity_ok(registry), "Registry integrity is valid."))
            checks.append(_check("audio_baseline_registry_report_integrity", _integrity_ok(report), "Registry report integrity is valid."))
            checks.append(_check("audio_baseline_registry_active_integrity", _integrity_ok(active), "Active baseline index integrity is valid."))
            checks.extend(_document_binding_checks(manifest, registry, report, active, baselines))
            checks.extend(_baseline_checks(baselines, baseline_evidence or {}, require_active=require_active))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("audio_baseline_registry_zip_readable", False, "Baseline Registry ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_baseline_registry_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_baseline_registry_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def build_baseline_source_binding(
    *,
    release_id: str,
    timeline_path: Path | str,
    timeline_report_path: Path | str,
    certification_path: Path | str,
    certification_report_path: Path | str,
) -> dict[str, Any]:
    facts = _external_facts(
        "baseline",
        timeline_path=timeline_path,
        timeline_report_path=timeline_report_path,
        certification_path=certification_path,
        certification_report_path=certification_report_path,
        required=True,
    )
    failed = [check for check in facts.get("checks", []) if check.get("status") == "failed"]
    if failed or not facts.get("binding"):
        raise ValueError("Baseline release audio evidence is not current.")
    binding = facts["binding"]
    binding["release_id"] = release_id
    binding["source_hash"] = stable_hash(_strip_integrity(binding))
    binding["integrity_hash"] = _integrity_hash(binding)
    return binding


def _read_baselines(archive: zipfile.ZipFile, names: list[str]) -> list[dict[str, Any]]:
    baselines: list[dict[str, Any]] = []
    for name in sorted(names):
        if name.startswith("baselines/") and name.endswith("/baseline.json"):
            baselines.append(_read_json_entry(archive, name))
    return baselines


def _baseline_checks(baselines: list[dict[str, Any]], evidence: dict[str, dict[str, Any]], *, require_active: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    active_baselines = [baseline for baseline in baselines if baseline.get("status") == "active"]
    if require_active:
        checks.append(_check("audio_baseline_registry_require_active", bool(active_baselines), "At least one active baseline exists."))
    active_keys: set[str] = set()
    for baseline in baselines:
        baseline_id = str(baseline.get("baseline_id") or "")
        checks.append(_check(f"audio_baseline_{baseline_id}_integrity", _integrity_ok(baseline), f"Baseline {baseline_id} integrity is valid."))
        checks.append(_check(f"audio_baseline_{baseline_id}_status_valid", baseline.get("status") in {"draft", "approved", "active", "superseded", "revoked"}, f"Baseline {baseline_id} status is valid."))
        checks.append(_check(f"audio_baseline_{baseline_id}_approval_history", _history_chain_ok(baseline.get("approval_history") if isinstance(baseline.get("approval_history"), list) else []), f"Baseline {baseline_id} approval history chain is valid."))
        if baseline.get("status") in {"approved", "active"}:
            approval = baseline.get("approval") if isinstance(baseline.get("approval"), dict) else {}
            checks.append(_check(f"audio_baseline_{baseline_id}_approval_present", bool(approval.get("approved_by") and approval.get("reason")), f"Baseline {baseline_id} approval is present."))
        if baseline.get("status") == "active":
            checks.append(_check(f"audio_baseline_{baseline_id}_active_not_revoked", baseline.get("status") not in {"revoked", "superseded"}, f"Baseline {baseline_id} active status is usable."))
            scope_hash = stable_hash(baseline.get("scope") or {})
            duplicate_active = scope_hash in active_keys
            checks.append(_check(f"audio_baseline_{baseline_id}_active_scope_unique", not duplicate_active, f"Baseline {baseline_id} has a unique active scope."))
            active_keys.add(scope_hash)
        expected = evidence.get(baseline_id)
        if expected:
            actual_binding = baseline.get("source_binding") if isinstance(baseline.get("source_binding"), dict) else {}
            checks.append(_check(f"audio_baseline_{baseline_id}_external_binding", stable_hash(_strip_integrity(actual_binding)) == stable_hash(_strip_integrity(expected)), f"Baseline {baseline_id} binds external Timeline/Certification evidence."))
    return checks


def _document_binding_checks(manifest: dict[str, Any], registry: dict[str, Any], report: dict[str, Any], active: dict[str, Any], baselines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline_hashes = {baseline.get("baseline_id"): baseline.get("integrity_hash") for baseline in baselines}
    return [
        _check("audio_baseline_registry_manifest_registry_binding", manifest.get("registry_hash") == registry.get("integrity_hash"), "Manifest binds registry."),
        _check("audio_baseline_registry_manifest_report_binding", manifest.get("report_hash") == report.get("integrity_hash"), "Manifest binds registry report."),
        _check("audio_baseline_registry_manifest_active_binding", manifest.get("active_baselines_hash") == active.get("integrity_hash"), "Manifest binds active baseline index."),
        _check("audio_baseline_registry_report_registry_binding", report.get("registry_hash") == registry.get("integrity_hash"), "Report binds registry."),
        _check("audio_baseline_registry_active_matches_registry", active.get("baseline_hashes") == baseline_hashes, "Active baseline index lists registry baseline hashes."),
    ]


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], names: set[str], *, strict: bool) -> list[dict[str, Any]]:
    del archive
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    manifest_paths = {item.get("path") for item in files if isinstance(item, dict)}
    expected_files = names - {"manifest.json"}
    checks = [
        _check("audio_baseline_registry_manifest_files_match_zip", manifest_paths == expected_files, "Manifest files match ZIP entries."),
    ]
    if strict:
        zip_entries = set((manifest.get("zip") or {}).get("entries") or [])
        checks.append(_check("audio_baseline_registry_manifest_zip_entries_not_authoritative", not zip_entries or zip_entries == names, "manifest.zip.entries does not extend package contents."))
    return checks


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    status = "failed" if blockers else "passed"
    report = {
        "package_type": RELEASE_AUDIO_BASELINE_REGISTRY_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_BASELINE_SCHEMA_VERSION,
        "status": status,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, blocking: bool = True) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "passed" if passed else "failed",
        "severity": "info" if passed else "blocking" if blocking else "warning",
        "message": message,
        "details": details or {},
    }


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    with archive.open(name) as handle:
        data = json.loads(handle.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


def _is_safe_entry(name: str) -> bool:
    normalized = name.replace("\\", "/")
    lowered = normalized.lower()
    if normalized != name or normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        return False
    if re.match(r"^[a-zA-Z]:", normalized):
        return False
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    if normalized.endswith("/"):
        return False
    return True


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    hits: list[str] = []
    for name in names:
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                hits.append(name)
                break
    return _check("audio_baseline_registry_redaction", not hits, "No secrets or local paths are present.", {"hits": sorted(set(hits))})


def _history_chain_ok(history: list[dict[str, Any]]) -> bool:
    previous = None
    for event in history:
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(event.get("payload")):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = event.get("event_hash")
    return True


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _strip_integrity(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _strip_integrity(value) for key, value in payload.items() if key != "integrity_hash"}
    if isinstance(payload, list):
        return [_strip_integrity(item) for item in payload]
    return payload


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
