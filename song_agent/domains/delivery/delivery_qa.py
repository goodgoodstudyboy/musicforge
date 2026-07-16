from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.creation.final_export import final_export_dir, final_export_zip_path
from song_agent.domains.studio.project_repository import ProjectDocument, now_iso
from song_agent.domains.studio.projectio import read_json
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text


DELIVERY_QA_SCHEMA_VERSION = 1
DELIVERY_SIGNOFF_SCHEMA_VERSION = 1
DELIVERY_QA_STATUSES = {"passed", "warning", "failed", "stale", "not_ready"}
DELIVERY_READINESS_VALUES = {"ready_to_handoff", "needs_export", "needs_zip", "needs_review", "blocked", "stale", "no_data"}
BLOCKED_DELIVERY_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "local_path",
    "password",
    "provider_snapshot",
    "raw_provider_response",
    "secret",
    "token",
}
SCAN_BLOCKED_KEYS = BLOCKED_DELIVERY_KEYS | {"file"}
ALLOWED_SENSITIVE_KEYS = {"provider_tokens", "token_count", "total_tokens", "input_tokens", "output_tokens"}
SENSITIVE_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}", re.IGNORECASE), "github token"),
    (re.compile(r"ghp_[A-Za-z0-9_]{20,}", re.IGNORECASE), "github token"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}", re.IGNORECASE), "provider key"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{6,}"), "bearer token"),
    (re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s,;]+"), "secret assignment"),
    (re.compile(r"(?i)\b[A-Z]:[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "local path"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "unc path"),
    (re.compile(r"(?<!\S)/Users/[^/\s,;]+(?:/[^\s,;]+)*"), "local path"),
    (re.compile(r"(?<!\S)/home/[^/\s,;]+(?:/[^\s,;]+)*"), "local path"),
)
ZIP_SIZE_WARNING_BYTES = 500 * 1024 * 1024
CORE_REQUIRED_EXPORT_FILES: tuple[tuple[str, str], ...] = (
    ("manifest", "manifest.json"),
    ("readme", "README.txt"),
    ("project_export", "project-export.json"),
    ("song_plan", "song-plan.json"),
    ("midi", "song.mid"),
)


def build_delivery_qa_report(
    *,
    project_id: str,
    project_document: ProjectDocument | Any,
    project_dir: Path,
    project_export: dict[str, Any] | None = None,
    final_export_manifest: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    project_dir = Path(project_dir).resolve()
    source = _delivery_sources(
        project_id=project_id,
        project_document=project_document,
        project_dir=project_dir,
        project_export=project_export,
        final_export_manifest=final_export_manifest,
    )
    final_version = _final_version_summary(project_document)
    final_export = _final_export_summary(source["manifest"], source["manifest_exists"], source["manifest_error"], source["expected_files"], source["actual_files"])
    zip_summary = _zip_summary(source["zip_info"], source["actual_files"], source["manifest"])
    quality_gate = _quality_gate_summary(source["manifest"], final_version)
    review_sprint = _review_sprint_summary(project_export)
    artifact_integrity = _artifact_integrity_summary(source["expected_files"], source["actual_files"])
    checks = _build_checks(
        final_version=final_version,
        final_export=final_export,
        zip_summary=zip_summary,
        quality_gate=quality_gate,
        review_sprint=review_sprint,
        artifact_integrity=artifact_integrity,
        manifest=source["manifest"],
        raw_manifest=source["raw_manifest"],
        project_export=project_export,
        report_probe={
            "final_version": final_version,
            "final_export": final_export,
            "zip": zip_summary,
            "quality_gate": quality_gate,
            "review_sprint": review_sprint,
            "artifact_integrity": artifact_integrity,
        },
    )
    blockers = [check for check in checks if check.get("severity") == "blocking" and check.get("status") == "failed"]
    warnings = [check for check in checks if check.get("severity") == "warning" and check.get("status") == "warning"]
    status = _qa_status(project_document, blockers, warnings)
    readiness = _qa_readiness(status, checks)
    report = {
        "schema_version": DELIVERY_QA_SCHEMA_VERSION,
        "project_id": project_id,
        "created_at": now,
        "source_hash": _source_hash(source),
        "status": status,
        "readiness": readiness,
        "handoff_allowed": status in {"passed", "warning"},
        "stale": False,
        "final_version": final_version,
        "final_export": final_export,
        "zip": zip_summary,
        "quality_gate": quality_gate,
        "review_sprint": review_sprint,
        "artifact_integrity": artifact_integrity,
        "checks": checks,
        "blockers": [_check_message(check) for check in blockers],
        "warnings": [_check_message(check) for check in warnings],
    }
    return sanitize_metadata(report, blocked_keys=BLOCKED_DELIVERY_KEYS)


def delivery_qa_source_hash(
    *,
    project_id: str,
    project_document: ProjectDocument | Any,
    project_dir: Path,
    project_export: dict[str, Any] | None = None,
    final_export_manifest: dict[str, Any] | None = None,
) -> str:
    return _source_hash(
        _delivery_sources(
            project_id=project_id,
            project_document=project_document,
            project_dir=Path(project_dir).resolve(),
            project_export=project_export,
            final_export_manifest=final_export_manifest,
        )
    )


def mark_delivery_qa_stale(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> dict[str, Any]:
    data = dict(report or {})
    checks = [check for check in data.get("checks", []) if isinstance(check, dict)]
    stale_check = _check("delivery_qa_stale", True, "blocking", "Delivery QA is stale. Refresh QA before signoff.", 1)
    if not any(check.get("check_id") == "delivery_qa_stale" for check in checks):
        checks.insert(0, stale_check)
    data.update(
        {
            "status": "stale",
            "readiness": "stale",
            "handoff_allowed": False,
            "stale": True,
            "current_source_hash": current_source_hash,
            "checks": checks,
            "blockers": [_check_message(check) for check in checks if check.get("severity") == "blocking" and check.get("status") == "failed"],
        }
    )
    return sanitize_metadata(data, blocked_keys=BLOCKED_DELIVERY_KEYS)


def delivery_qa_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict) or not report:
        return {}
    final_version = report.get("final_version") if isinstance(report.get("final_version"), dict) else {}
    zip_summary = report.get("zip") if isinstance(report.get("zip"), dict) else {}
    artifact = report.get("artifact_integrity") if isinstance(report.get("artifact_integrity"), dict) else {}
    return sanitize_metadata(
        {
            "schema_version": report.get("schema_version"),
            "project_id": report.get("project_id"),
            "created_at": report.get("created_at"),
            "source_hash": report.get("source_hash"),
            "status": report.get("status"),
            "readiness": report.get("readiness"),
            "handoff_allowed": bool(report.get("handoff_allowed", False)),
            "stale": bool(report.get("stale", False)),
            "blocker_count": len(report.get("blockers") or []),
            "warning_count": len(report.get("warnings") or []),
            "final_version_id": final_version.get("version_id"),
            "artifact_count": artifact.get("checked_count", 0),
            "missing_artifact_count": artifact.get("missing_count", 0),
            "zip_sha256": zip_summary.get("sha256"),
            "zip_matches_manifest": zip_summary.get("matches_manifest"),
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def delivery_qa_allows_signoff(report: dict[str, Any] | None) -> bool:
    return bool(isinstance(report, dict) and report.get("handoff_allowed") and report.get("status") in {"passed", "warning"} and not report.get("stale"))


def build_delivery_signoff_record(
    *,
    project_id: str,
    report: dict[str, Any],
    payload: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    now = now or now_iso()
    force = bool(payload.get("force", False))
    override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "")).strip()[:1000]
    if force and not override_reason:
        raise ValueError("override_reason is required when force=true.")
    final_version = report.get("final_version") if isinstance(report.get("final_version"), dict) else {}
    final_export = report.get("final_export") if isinstance(report.get("final_export"), dict) else {}
    zip_summary = report.get("zip") if isinstance(report.get("zip"), dict) else {}
    blockers = [sanitize_sensitive_text(str(item))[:240] for item in report.get("blockers", []) if str(item).strip()]
    warnings = [sanitize_sensitive_text(str(item))[:240] for item in report.get("warnings", []) if str(item).strip()]
    record = {
        "schema_version": DELIVERY_SIGNOFF_SCHEMA_VERSION,
        "project_id": project_id,
        "signed_at": now,
        "signed_by": sanitize_sensitive_text(str(payload.get("signed_by") or "local-user"))[:120],
        "decision": "approved_for_handoff",
        "delivery_qa_hash": _stable_hash(report),
        "delivery_qa_source_hash": report.get("source_hash"),
        "delivery_qa_status": report.get("status"),
        "final_version_id": final_version.get("version_id") or final_export.get("manifest_version_id"),
        "final_export_sha256": final_export.get("manifest_sha256"),
        "zip_sha256": zip_summary.get("sha256"),
        "force": force,
        "override_reason": override_reason,
        "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:1000],
        "acknowledged_blockers": blockers[:20],
        "acknowledged_warnings": warnings[:20],
    }
    return sanitize_metadata(record, blocked_keys=BLOCKED_DELIVERY_KEYS)


def delivery_signoff_summary(record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, dict) or not record:
        return {"status": "not_signed"}
    forced = bool(record.get("force", record.get("forced", False)))
    return sanitize_metadata(
        {
            "status": "force_signed" if forced else "signed",
            "schema_version": record.get("schema_version"),
            "project_id": record.get("project_id"),
            "signed_at": record.get("signed_at"),
            "signed_by": record.get("signed_by"),
            "decision": record.get("decision"),
            "forced": forced,
            "delivery_qa_status": record.get("delivery_qa_status"),
            "final_version_id": record.get("final_version_id"),
            "final_export_sha256": record.get("final_export_sha256"),
            "zip_sha256": record.get("zip_sha256"),
            "acknowledged_blocker_count": len(record.get("acknowledged_blockers") or []),
            "acknowledged_warning_count": len(record.get("acknowledged_warnings") or []),
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def signoff_history_event(event: str, previous_signoff: dict[str, Any], reason: str, *, now: str | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "event": event,
            "created_at": now or now_iso(),
            "reason": sanitize_sensitive_text(str(reason or ""))[:1000],
            "previous_signoff": previous_signoff if isinstance(previous_signoff, dict) else {},
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def scan_delivery_payload_for_sensitive_values(payload: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                lower = key_text.lower()
                child_path = f"{path}.{key_text}" if path else key_text
                if lower in SCAN_BLOCKED_KEYS and lower not in ALLOWED_SENSITIVE_KEYS:
                    findings.append({"path": child_path, "kind": "blocked_key", "message": f"Sensitive field is present: {key_text}."})
                walk(item, child_path)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, str):
            for pattern, kind in SENSITIVE_VALUE_PATTERNS:
                if pattern.search(value):
                    findings.append({"path": path, "kind": kind, "message": f"Sensitive value detected: {kind}."})
                    break

    walk(payload, "")
    return sanitize_metadata(findings, blocked_keys=BLOCKED_DELIVERY_KEYS)


def _delivery_sources(
    *,
    project_id: str,
    project_document: ProjectDocument | Any,
    project_dir: Path,
    project_export: ImplementationDocument | None,
    final_export_manifest: ImplementationDocument | None,
) -> ImplementationDocument:
    manifest, raw_manifest, manifest_exists, manifest_error = _read_manifest(project_dir, final_export_manifest)
    expected_files = _expected_files(project_dir, manifest, manifest_exists)
    actual_files = _actual_export_files(project_dir)
    zip_info = _actual_zip_info(project_dir, actual_files)
    return {
        "schema_version": DELIVERY_QA_SCHEMA_VERSION,
        "project": _project_source(project_id, project_document),
        "versions": _version_sources(project_document),
        "manifest": _manifest_source(manifest if manifest_exists else {}),
        "raw_manifest": raw_manifest if manifest_exists else {},
        "raw_manifest_sha256": _raw_stable_hash(raw_manifest) if manifest_exists else None,
        "manifest_exists": manifest_exists,
        "manifest_error": manifest_error,
        "expected_files": expected_files,
        "actual_files": actual_files,
        "zip_info": zip_info,
        "review_sprint": _review_sprint_summary(project_export),
    }


def _read_manifest(project_dir: Path, provided: ImplementationDocument | None) -> tuple[ImplementationDocument, ImplementationDocument, bool, str]:
    if isinstance(provided, dict) and provided:
        return sanitize_metadata(provided, blocked_keys=BLOCKED_DELIVERY_KEYS), dict(provided), True, ""
    path = final_export_dir(project_dir) / "manifest.json"
    if not path.exists():
        return {}, {}, False, ""
    try:
        data = read_json(path)
        raw = data if isinstance(data, dict) else {}
        return sanitize_metadata(raw, blocked_keys=BLOCKED_DELIVERY_KEYS), dict(raw), True, ""
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {}, {}, False, f"Final Export manifest is invalid. Rebuild final export. {exc}"


def _project_source(project_id: str, project_document: ProjectDocument | Any) -> ImplementationDocument:
    state = getattr(project_document, "state", None)
    return sanitize_metadata(
        {
            "project_id": project_id,
            "final_version_id": getattr(state, "final_version_id", None),
            "selected_version_id": getattr(state, "selected_version_id", None),
            "latest_version_id": getattr(state, "latest_version_id", None),
            "version_count": getattr(state, "version_count", None),
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _version_sources(project_document: ProjectDocument | Any) -> list[ImplementationDocument]:
    versions = []
    for version in getattr(project_document, "versions", []):
        versions.append(
            {
                "version_id": getattr(version, "version_id", None),
                "status": getattr(version, "status", None),
                "job_id": getattr(version, "job_id", None),
                "quality_score": getattr(version, "quality_score", None),
                "quality_gate_status": getattr(version, "quality_gate_status", None),
                "quality_gate_score": getattr(version, "quality_gate_score", None),
                "updated_at": getattr(version, "updated_at", None),
                "final_export_path": _path_presence(getattr(version, "final_export_path", None)),
            }
        )
    return sanitize_metadata(versions, blocked_keys=BLOCKED_DELIVERY_KEYS)


def _manifest_source(manifest: ImplementationDocument) -> ImplementationDocument:
    clean = _strip_delivery_summaries(manifest)
    return sanitize_metadata(
        {
            "project_id": clean.get("project_id"),
            "version_id": clean.get("version_id"),
            "generated_at": clean.get("generated_at"),
            "quality_gate": clean.get("quality_gate") if isinstance(clean.get("quality_gate"), dict) else {},
            "files": [
                {
                    "kind": item.get("kind"),
                    "path": item.get("path"),
                    "required": bool(item.get("required", False)),
                    "exists": bool(item.get("exists", False)),
                    "skipped": item.get("skipped"),
                }
                for item in clean.get("files", [])
                if isinstance(item, dict)
            ]
            if isinstance(clean.get("files"), list)
            else [],
            "review_sprint_closeout": clean.get("review_sprint_closeout") if isinstance(clean.get("review_sprint_closeout"), dict) else {},
            "review_metrics": clean.get("review_metrics") if isinstance(clean.get("review_metrics"), dict) else {},
            "review_judge": clean.get("review_judge") if isinstance(clean.get("review_judge"), dict) else {},
            "zip": {key: value for key, value in (clean.get("zip") or {}).items() if key in {"filename", "size_bytes", "sha256", "entry_count", "entries"}} if isinstance(clean.get("zip"), dict) else {},
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _strip_delivery_summaries(manifest: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in (manifest or {}).items() if key not in {"delivery_qa", "delivery_signoff"}}


def _expected_files(project_dir: Path, manifest: ImplementationDocument, manifest_exists: bool) -> list[ImplementationDocument]:
    export_dir = final_export_dir(project_dir).resolve()
    rows_by_path: dict[str, dict[str, Any]] = {}
    manifest_items = [item for item in manifest.get("files", []) if isinstance(item, dict)] if isinstance(manifest.get("files"), list) else []
    manifest_by_path = {str(item.get("path") or "").strip(): item for item in manifest_items if str(item.get("path") or "").strip()}

    for kind, path in CORE_REQUIRED_EXPORT_FILES:
        item = manifest_by_path.get(path, {})
        rows_by_path[path] = _expected_file_row(
            export_dir,
            path,
            kind=kind,
            required=True,
            manifest_exists=bool(item.get("exists", False)) if item else path == "manifest.json" and manifest_exists,
            skipped=item.get("skipped") if isinstance(item, dict) else None,
        )

    if _quality_gate_requires_stems(manifest):
        item = manifest_by_path.get("stems/manifest.json", {})
        rows_by_path["stems/manifest.json"] = _expected_file_row(
            export_dir,
            "stems/manifest.json",
            kind="stem_manifest",
            required=True,
            manifest_exists=bool(item.get("exists", False)) if item else False,
            skipped=item.get("skipped") if isinstance(item, dict) else None,
        )
        for path in _required_stem_midi_paths(export_dir):
            item = manifest_by_path.get(path, {})
            rows_by_path[path] = _expected_file_row(
                export_dir,
                path,
                kind="stem_midi",
                required=True,
                manifest_exists=bool(item.get("exists", False)) if item else False,
                skipped=item.get("skipped") if isinstance(item, dict) else None,
            )

    for item in manifest.get("files", []) if isinstance(manifest.get("files"), list) else []:
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("path") or "").strip()
        if not raw_path:
            continue
        manifest_row = _expected_file_row(
            export_dir,
            raw_path,
            kind=str(item.get("kind") or ""),
            required=bool(item.get("required", False)),
            manifest_exists=bool(item.get("exists", False)),
            skipped=item.get("skipped"),
        )
        existing = rows_by_path.get(raw_path)
        if existing:
            existing["kind"] = existing.get("kind") or manifest_row.get("kind")
            existing["required"] = bool(existing.get("required") or manifest_row.get("required"))
            existing["manifest_exists"] = bool(manifest_row.get("manifest_exists"))
            if manifest_row.get("skipped") is not None:
                existing["skipped"] = manifest_row.get("skipped")
            if not existing.get("error") and manifest_row.get("error"):
                existing["error"] = manifest_row.get("error")
        else:
            rows_by_path[raw_path] = manifest_row
    return sanitize_metadata(list(rows_by_path.values()), blocked_keys=BLOCKED_DELIVERY_KEYS)


def _expected_file_row(
    export_dir: Path,
    raw_path: str,
    *,
    kind: str,
    required: bool,
    manifest_exists: bool,
    skipped: Any = None,
) -> ImplementationDocument:
    row = {
        "kind": kind,
        "path": raw_path,
        "required": bool(required),
        "manifest_exists": bool(manifest_exists),
        "safe": False,
        "exists": False,
        "size_bytes": None,
        "sha256": None,
        "error": "",
    }
    if skipped is not None:
        row["skipped"] = skipped
    try:
        target = _safe_export_path(export_dir, raw_path)
        row["safe"] = True
        if target.exists() and target.is_file() and not target.is_symlink():
            row["exists"] = True
            row["size_bytes"] = target.stat().st_size
            row["sha256"] = _sha256(target)
        elif target.is_symlink():
            row["error"] = "Artifact path is a symlink."
        elif row["manifest_exists"] or row["required"]:
            row["error"] = "Artifact file is missing."
    except ValueError as exc:
        row["error"] = str(exc)
    return row


def _quality_gate_requires_stems(manifest: ImplementationDocument) -> bool:
    gate = manifest.get("quality_gate") if isinstance(manifest.get("quality_gate"), dict) else {}
    config = gate.get("config") if isinstance(gate.get("config"), dict) else {}
    if config.get("require_stems"):
        return True
    checks = gate.get("checks") if isinstance(gate.get("checks"), list) else []
    return any(isinstance(check, dict) and check.get("name") == "stems" for check in checks)


def _required_stem_midi_paths(export_dir: Path) -> list[str]:
    manifest_path = export_dir / "stems" / "manifest.json"
    if not manifest_path.exists() or manifest_path.is_symlink():
        return []
    try:
        data = read_json(manifest_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return []
    paths: list[str] = []
    for stem in data.get("stems", []) if isinstance(data, dict) else []:
        if not isinstance(stem, dict) or int(stem.get("note_count") or 0) <= 0:
            continue
        raw_path = str(stem.get("midi_path") or "").strip()
        if raw_path and raw_path not in paths:
            paths.append(raw_path)
    return paths


def _actual_export_files(project_dir: Path) -> list[ImplementationDocument]:
    export_dir = final_export_dir(project_dir).resolve()
    if not export_dir.exists() or not export_dir.is_dir() or export_dir.is_symlink():
        return []
    rows = []
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file():
            continue
        try:
            resolved = file.resolve()
            resolved.relative_to(export_dir)
            rel = resolved.relative_to(export_dir).as_posix()
            _validate_relative_path(rel)
            if file.is_symlink():
                rows.append({"path": rel, "safe": False, "error": "File is a symlink."})
                continue
            rows.append({"path": rel, "safe": True, "size_bytes": file.stat().st_size, "sha256": _sha256(file)})
        except (OSError, ValueError) as exc:
            rows.append({"path": sanitize_sensitive_text(str(file.name)), "safe": False, "error": str(exc)})
    return sanitize_metadata(rows, blocked_keys=BLOCKED_DELIVERY_KEYS)


def _actual_zip_info(project_dir: Path, actual_files: list[ImplementationDocument]) -> ImplementationDocument:
    zip_path = final_export_zip_path(project_dir).resolve()
    project_dir = project_dir.resolve()
    export_dir = final_export_dir(project_dir).resolve()
    try:
        zip_path.relative_to(project_dir)
    except ValueError:
        return {"exists": False, "valid": False, "error": "ZIP path is outside project directory."}
    if not zip_path.exists():
        return {"exists": False, "valid": False, "entries": []}
    if zip_path.is_symlink():
        return {"exists": True, "valid": False, "error": "ZIP path is a symlink.", "entries": []}
    info = {
        "exists": True,
        "valid": True,
        "filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "sha256": _sha256(zip_path),
        "entries": [],
        "entry_count": 0,
        "unsafe_entry_count": 0,
        "mismatched_entry_count": 0,
        "missing_entry_count": 0,
        "extra_entry_count": 0,
        "error": "",
    }
    actual_by_path = {str(row.get("path")): row for row in actual_files if row.get("safe") and row.get("path")}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            entries = []
            for member in archive.infolist():
                if member.is_dir():
                    continue
                entry_name = member.filename.replace("\\", "/")
                row = {
                    "path": entry_name,
                    "safe": False,
                    "size_bytes": member.file_size,
                    "sha256": None,
                    "matches_file": False,
                    "error": "",
                }
                try:
                    safe_entry = _validate_relative_path(entry_name)
                    data = archive.read(member)
                    digest = hashlib.sha256(data).hexdigest()
                    row.update({"path": safe_entry, "safe": True, "sha256": digest})
                    actual = actual_by_path.get(safe_entry)
                    if safe_entry == "manifest.json":
                        row["matches_file"] = _zip_manifest_matches_current(data, export_dir / safe_entry)
                    else:
                        row["matches_file"] = bool(actual and actual.get("sha256") == digest)
                    if actual and not row["matches_file"]:
                        row["error"] = "ZIP entry hash does not match final-export file."
                except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
                    row["error"] = str(exc)
                entries.append(row)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        info.update({"valid": False, "error": f"Final Export ZIP is invalid. {exc}", "entries": []})
        return sanitize_metadata(info, blocked_keys=BLOCKED_DELIVERY_KEYS)
    entry_by_path = {row["path"]: row for row in entries if row.get("safe")}
    actual_paths = set(actual_by_path)
    entry_paths = set(entry_by_path)
    info["entries"] = entries
    info["entry_count"] = len(entries)
    info["unsafe_entry_count"] = len([row for row in entries if not row.get("safe")])
    info["mismatched_entry_count"] = len([row for row in entries if row.get("safe") and not row.get("matches_file")])
    info["missing_entry_count"] = len(actual_paths - entry_paths)
    info["extra_entry_count"] = len(entry_paths - actual_paths)
    return sanitize_metadata(info, blocked_keys=BLOCKED_DELIVERY_KEYS)


def _zip_manifest_matches_current(zipped_bytes: bytes, current_path: Path) -> bool:
    try:
        zipped = json.loads(zipped_bytes.decode("utf-8"))
        current = read_json(current_path)
    except (OSError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        return False
    return _stable_hash({key: value for key, value in zipped.items() if key != "zip"}) == _stable_hash({key: value for key, value in current.items() if key != "zip"})


def _final_version_summary(project_document: ProjectDocument | Any) -> ImplementationDocument:
    state = getattr(project_document, "state", None)
    final_id = getattr(state, "final_version_id", None)
    version = _version_by_id(project_document, final_id)
    return sanitize_metadata(
        {
            "version_id": final_id,
            "exists": bool(version),
            "status": getattr(version, "status", None) if version else None,
            "quality_score": getattr(version, "quality_score", None) if version else None,
            "quality_gate_status": getattr(version, "quality_gate_status", None) if version else None,
            "quality_gate_score": getattr(version, "quality_gate_score", None) if version else None,
            "updated_at": getattr(version, "updated_at", None) if version else None,
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _version_by_id(project_document: ProjectDocument | Any, version_id: str | None) -> Any | None:
    if not version_id:
        return None
    for version in getattr(project_document, "versions", []):
        if getattr(version, "version_id", None) == version_id:
            return version
    return None


def _final_export_summary(manifest: ImplementationDocument, manifest_exists: bool, manifest_error: str, expected: list[ImplementationDocument], actual: list[ImplementationDocument]) -> ImplementationDocument:
    manifest_path = next((row for row in actual if row.get("path") == "manifest.json"), {})
    unsafe_count = len([row for row in expected + actual if row.get("safe") is False])
    missing_required = len([row for row in expected if row.get("required") and not row.get("exists")])
    return sanitize_metadata(
        {
            "exists": bool(manifest_exists),
            "manifest_version_id": manifest.get("version_id") if manifest_exists else None,
            "generated_at": manifest.get("generated_at") if manifest_exists else None,
            "file_count": len(actual),
            "missing_required_count": missing_required,
            "unsafe_file_count": unsafe_count,
            "manifest_sha256": manifest_path.get("sha256"),
            "error": manifest_error,
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _zip_summary(zip_info: ImplementationDocument, actual_files: list[ImplementationDocument], manifest: ImplementationDocument) -> ImplementationDocument:
    manifest_zip = manifest.get("zip") if isinstance(manifest.get("zip"), dict) else {}
    matches_manifest = bool(
        zip_info.get("exists")
        and zip_info.get("valid")
        and zip_info.get("unsafe_entry_count", 0) == 0
        and zip_info.get("mismatched_entry_count", 0) == 0
        and zip_info.get("missing_entry_count", 0) == 0
        and zip_info.get("extra_entry_count", 0) == 0
        and (not manifest_zip.get("sha256") or manifest_zip.get("sha256") == zip_info.get("sha256"))
        and (not manifest_zip.get("entry_count") or int(manifest_zip.get("entry_count") or 0) == int(zip_info.get("entry_count") or 0))
    )
    return sanitize_metadata(
        {
            "exists": bool(zip_info.get("exists")),
            "valid": bool(zip_info.get("valid", False)),
            "filename": zip_info.get("filename") or "final-export.zip",
            "size_bytes": zip_info.get("size_bytes", 0),
            "sha256": zip_info.get("sha256"),
            "entry_count": zip_info.get("entry_count", 0),
            "expected_entry_count": len(actual_files),
            "matches_manifest": matches_manifest,
            "unsafe_entry_count": zip_info.get("unsafe_entry_count", 0),
            "mismatched_entry_count": zip_info.get("mismatched_entry_count", 0),
            "missing_entry_count": zip_info.get("missing_entry_count", 0),
            "extra_entry_count": zip_info.get("extra_entry_count", 0),
            "manifest_sha256": manifest_zip.get("sha256"),
            "manifest_entry_count": manifest_zip.get("entry_count"),
            "error": zip_info.get("error") or "",
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _quality_gate_summary(manifest: ImplementationDocument, final_version: ImplementationDocument) -> ImplementationDocument:
    gate = manifest.get("quality_gate") if isinstance(manifest.get("quality_gate"), dict) else {}
    return sanitize_metadata(
        {
            "status": gate.get("status") or final_version.get("quality_gate_status"),
            "overall_score": gate.get("score", final_version.get("quality_gate_score") or final_version.get("quality_score")),
            "require_stems": _quality_gate_requires_stems(manifest),
            "warnings": gate.get("warnings") if isinstance(gate.get("warnings"), list) else [],
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _review_sprint_summary(project_export: ImplementationDocument | None) -> ImplementationDocument:
    if not isinstance(project_export, dict):
        return {"sprint_count": 0}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    metrics = project_export.get("review_metrics_summary") if isinstance(project_export.get("review_metrics_summary"), dict) else {}
    latest_id = str(metrics.get("latest_sprint_id") or "")
    latest = next((sprint for sprint in sprints if str(sprint.get("sprint_id") or "") == latest_id), None) if latest_id else None
    if latest is None and sprints:
        latest = sprints[0]
        latest_id = str(latest.get("sprint_id") or "")
    closeout = latest.get("closeout_summary") if isinstance(latest, dict) and isinstance(latest.get("closeout_summary"), dict) else {}
    signoff = latest.get("signoff_summary") if isinstance(latest, dict) and isinstance(latest.get("signoff_summary"), dict) else {}
    signoffs = [sprint.get("signoff_summary", {}) for sprint in sprints if isinstance(sprint.get("signoff_summary"), dict)]
    closeouts = [sprint.get("closeout_summary", {}) for sprint in sprints if isinstance(sprint.get("closeout_summary"), dict)]
    return sanitize_metadata(
        {
            "sprint_count": len(sprints),
            "latest_sprint_id": latest_id or None,
            "latest_closeout_status": closeout.get("status"),
            "latest_closeout_readiness": closeout.get("readiness"),
            "latest_signoff_status": signoff.get("status"),
            "signed_sprint_count": len([item for item in signoffs if item.get("status") == "signed"]),
            "forced_close_count": len([item for item in signoffs if item.get("forced")]) or len([item for item in closeouts if item.get("forced")]),
            "selected_version_id": signoff.get("selected_version_id") or closeout.get("recommended_final_version_id"),
            "warning_count": closeout.get("warning_count", 0),
            "blocker_count": closeout.get("blocker_count", 0),
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _artifact_integrity_summary(expected: list[ImplementationDocument], actual: list[ImplementationDocument]) -> ImplementationDocument:
    actual_paths = {str(row.get("path")) for row in actual if row.get("safe") and row.get("path")}
    expected_paths = {str(row.get("path")) for row in expected if row.get("safe") and row.get("path")}
    extra_paths = sorted(actual_paths - expected_paths)
    files = []
    for row in expected:
        files.append(
            {
                "path": row.get("path"),
                "kind": row.get("kind"),
                "required": bool(row.get("required", False)),
                "exists": bool(row.get("exists", False)),
                "safe": bool(row.get("safe", False)),
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
                "error": row.get("error"),
            }
        )
    for path in extra_paths:
        actual_row = next((row for row in actual if row.get("path") == path), {})
        files.append({"path": path, "kind": "extra", "required": False, "exists": True, "safe": True, "size_bytes": actual_row.get("size_bytes"), "sha256": actual_row.get("sha256"), "error": "Extra file not listed in manifest."})
    return sanitize_metadata(
        {
            "checked_count": len(actual),
            "missing_count": len([row for row in expected if row.get("required") and not row.get("exists")]),
            "hash_count": len([row for row in actual if row.get("sha256")]),
            "total_bytes": sum(int(row.get("size_bytes") or 0) for row in actual),
            "extra_count": len(extra_paths),
            "files": files,
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _build_checks(
    *,
    final_version: ImplementationDocument,
    final_export: ImplementationDocument,
    zip_summary: ImplementationDocument,
    quality_gate: ImplementationDocument,
    review_sprint: ImplementationDocument,
    artifact_integrity: ImplementationDocument,
    manifest: ImplementationDocument,
    raw_manifest: ImplementationDocument,
    project_export: ImplementationDocument | None,
    report_probe: ImplementationDocument,
) -> list[ImplementationDocument]:
    final_id = final_version.get("version_id")
    manifest_version = final_export.get("manifest_version_id")
    sprint_count = int(review_sprint.get("sprint_count") or 0)
    review_selected = review_sprint.get("selected_version_id")
    required_missing = int(artifact_integrity.get("missing_count") or 0)
    unsafe_files = int(final_export.get("unsafe_file_count") or 0)
    zip_hash_mismatch = bool(zip_summary.get("manifest_sha256") and zip_summary.get("manifest_sha256") != zip_summary.get("sha256"))
    zip_count_mismatch = bool(zip_summary.get("manifest_entry_count") and int(zip_summary.get("manifest_entry_count") or 0) != int(zip_summary.get("entry_count") or 0))
    redaction_findings = scan_delivery_payload_for_sensitive_values({"manifest": raw_manifest, "project_export_delivery": _project_export_delivery_probe(project_export), "report": report_probe})
    checks = [
        _check("project_final_version", not final_id or not final_version.get("exists"), "blocking", "Project has no final_version_id.", 1 if not final_id else 0),
        _check("final_export_exists", not final_export.get("exists"), "blocking", "Final Export manifest is missing or invalid.", 1 if not final_export.get("exists") else 0),
        _check("final_export_version_match", bool(final_id and manifest_version and manifest_version != final_id), "blocking", "Final Export version does not match Project final version.", 1 if final_id and manifest_version and manifest_version != final_id else 0),
        _check("quality_gate_passed", quality_gate.get("status") not in {"passed", "warning"}, "blocking", "Final Export quality gate is not passed or warning.", 1 if quality_gate.get("status") not in {"passed", "warning"} else 0),
        _check("closeout_signed", sprint_count > 0 and review_sprint.get("latest_signoff_status") != "signed", "blocking", "Latest Review Sprint is not signed off.", sprint_count),
        _check("closeout_version_match", bool(final_id and review_selected and review_selected != final_id), "blocking", "Review Sprint signoff selected version does not match Project final version.", 1 if final_id and review_selected and review_selected != final_id else 0),
        _check("required_artifacts_exist", required_missing > 0, "blocking", "Required Final Export artifacts are missing.", required_missing),
        _check("artifact_path_safe", unsafe_files > 0, "blocking", "Final Export artifact path is unsafe.", unsafe_files),
        _check("artifact_hash_valid", int(artifact_integrity.get("hash_count") or 0) < int(artifact_integrity.get("checked_count") or 0), "blocking", "Final Export artifact hash could not be calculated.", int(artifact_integrity.get("checked_count") or 0) - int(artifact_integrity.get("hash_count") or 0)),
        _check("zip_exists", not zip_summary.get("exists"), "blocking", "Final Export ZIP is missing.", 1 if not zip_summary.get("exists") else 0),
        _check("zip_valid", bool(zip_summary.get("exists") and not zip_summary.get("valid")), "blocking", "Final Export ZIP is invalid.", 1 if zip_summary.get("exists") and not zip_summary.get("valid") else 0),
        _check("zip_manifest_match", bool(zip_summary.get("exists") and not zip_summary.get("matches_manifest")), "blocking", "Final Export ZIP does not match current manifest and files.", 1 if zip_summary.get("exists") and not zip_summary.get("matches_manifest") else 0),
        _check("zip_hash_valid", zip_hash_mismatch or zip_count_mismatch, "blocking", "Final Export ZIP manifest metadata does not match the actual ZIP.", 1 if zip_hash_mismatch or zip_count_mismatch else 0),
        _check("redaction_scan", bool(redaction_findings), "blocking", "Delivery payload contains sensitive fields or values.", len(redaction_findings)),
        _check("audio_missing", _file_missing(artifact_integrity, "audio") and not _file_missing(artifact_integrity, "midi"), "warning", "WAV is not included, but MIDI exists.", 1 if _file_missing(artifact_integrity, "audio") else 0),
        _check("stems_missing", _file_missing(artifact_integrity, "stem_manifest") and not quality_gate.get("require_stems"), "warning", "Stems are not included.", 1 if _file_missing(artifact_integrity, "stem_manifest") else 0),
        _check("stem_audio_partial", _stem_audio_partial(artifact_integrity), "warning", "Some stem WAV files are missing.", 1 if _stem_audio_partial(artifact_integrity) else 0),
        _check("forced_sprint_close", int(review_sprint.get("forced_close_count") or 0) > 0, "warning", "A Review Sprint was force closed.", int(review_sprint.get("forced_close_count") or 0)),
        _check("high_warning_count", int(review_sprint.get("warning_count") or 0) > 0, "warning", "Review Sprint closeout has warnings.", int(review_sprint.get("warning_count") or 0)),
        _check("zip_large", int(zip_summary.get("size_bytes") or 0) > ZIP_SIZE_WARNING_BYTES, "warning", "Final Export ZIP is larger than the recommended size.", int(zip_summary.get("size_bytes") or 0)),
        _check("extra_export_files", int(artifact_integrity.get("extra_count") or 0) > 0, "warning", "Final Export contains files not listed in manifest.", int(artifact_integrity.get("extra_count") or 0)),
    ]
    return checks


def _project_export_delivery_probe(project_export: ImplementationDocument | None) -> ImplementationDocument:
    if not isinstance(project_export, dict):
        return {}
    return {
        "delivery_qa_summary": project_export.get("delivery_qa_summary") if isinstance(project_export.get("delivery_qa_summary"), dict) else {},
        "delivery_signoff_summary": project_export.get("delivery_signoff_summary") if isinstance(project_export.get("delivery_signoff_summary"), dict) else {},
    }


def _qa_status(project_document: ProjectDocument | Any, blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> str:
    if not getattr(project_document, "versions", []):
        return "not_ready"
    if blockers:
        return "failed"
    if warnings:
        return "warning"
    return "passed"


def _qa_readiness(status: str, checks: list[ImplementationDocument]) -> str:
    if status == "not_ready":
        return "no_data"
    if status == "stale":
        return "stale"
    if any(check.get("check_id") == "final_export_exists" and check.get("status") == "failed" for check in checks):
        return "needs_export"
    if any(check.get("check_id") == "zip_exists" and check.get("status") == "failed" for check in checks):
        return "needs_zip"
    if any(check.get("check_id") in {"closeout_signed", "closeout_version_match"} and check.get("status") == "failed" for check in checks):
        return "needs_review"
    if status == "failed":
        return "blocked"
    return "ready_to_handoff"


def _check(check_id: str, failed: bool, severity: str, message: str, count: int | float | None = 0) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "check_id": check_id,
            "status": "failed" if failed and severity == "blocking" else ("warning" if failed else "passed"),
            "severity": severity,
            "message": message,
            "count": count,
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _check_message(check: ImplementationDocument) -> str:
    count = check.get("count")
    suffix = f" ({count})" if count not in {None, "", 0} else ""
    return sanitize_sensitive_text(f"{check.get('check_id')}: {check.get('message')}{suffix}")[:240]


def _file_missing(artifact: ImplementationDocument, kind: str) -> bool:
    for row in artifact.get("files", []) if isinstance(artifact.get("files"), list) else []:
        if isinstance(row, dict) and row.get("kind") == kind:
            return not bool(row.get("exists"))
    return False


def _stem_audio_partial(artifact: ImplementationDocument) -> bool:
    stem_rows = [row for row in artifact.get("files", []) if isinstance(row, dict) and row.get("kind") == "stem_audio"] if isinstance(artifact.get("files"), list) else []
    return bool(stem_rows and any(not row.get("exists") for row in stem_rows) and any(row.get("exists") for row in stem_rows))


def _safe_export_path(export_dir: Path, relative_path: str) -> Path:
    safe = _validate_relative_path(relative_path)
    target = (export_dir / safe).resolve()
    try:
        target.relative_to(export_dir.resolve())
    except ValueError as exc:
        raise ValueError("Artifact path escapes final-export directory.") from exc
    return target


def _validate_relative_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if "\x00" in normalized:
        raise ValueError("Path contains NUL.")
    if not normalized or normalized.startswith("/") or normalized.startswith("\\") or normalized.startswith("//"):
        raise ValueError("Path must be relative.")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part in {"..", "."} for part in parts) or ".." in parts:
        raise ValueError("Path contains traversal.")
    if ":" in parts[0]:
        raise ValueError("Path must not include a drive prefix.")
    safe = PurePosixPath(*parts).as_posix()
    if safe.endswith("/"):
        raise ValueError("Path must reference a file.")
    return safe


def _path_presence(value: Any) -> str | None:
    return "set" if value else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hash(source: ImplementationDocument) -> str:
    return _stable_hash({key: value for key, value in source.items() if key != "raw_manifest"})


def _stable_hash(value: Any) -> str:
    clean = sanitize_metadata(value, blocked_keys=BLOCKED_DELIVERY_KEYS)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _raw_stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
