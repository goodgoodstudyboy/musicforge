# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import os as os
import re as re
import zipfile as zipfile
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.creation.final_export import final_export_dir as final_export_dir, final_export_zip_path as final_export_zip_path
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, now_iso as now_iso
from song_agent.domains.studio.projectio import read_json as read_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text


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
    project_export: DomainDocument | None = None,
    final_export_manifest: DomainDocument | None = None,
    now: str | None = None,
) -> DomainDocument:
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
    project_export: DomainDocument | None = None,
    final_export_manifest: DomainDocument | None = None,
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


def mark_delivery_qa_stale(report: DomainDocument | None, *, current_source_hash: str | None = None) -> DomainDocument:
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


def delivery_qa_summary(report: DomainDocument | None) -> DomainDocument:
    if not isinstance(report, dict) or not report:
        return {}
    final_version = _as_document(report.get("final_version"))
    zip_summary = _as_document(report.get("zip"))
    artifact = _as_document(report.get("artifact_integrity"))
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


def delivery_qa_allows_signoff(report: DomainDocument | None) -> bool:
    return bool(isinstance(report, dict) and report.get("handoff_allowed") and report.get("status") in {"passed", "warning"} and not report.get("stale"))


def build_delivery_signoff_record(
    *,
    project_id: str,
    report: DomainDocument,
    payload: DomainDocument | None = None,
    now: str | None = None,
) -> DomainDocument:
    payload = _as_document(payload)
    now = now or now_iso()
    force = bool(payload.get("force", False))
    override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "")).strip()[:1000]
    if force and not override_reason:
        raise ValueError("override_reason is required when force=true.")
    final_version = _as_document(report.get("final_version"))
    final_export = _as_document(report.get("final_export"))
    zip_summary = _as_document(report.get("zip"))
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


def delivery_signoff_summary(record: DomainDocument | None) -> DomainDocument:
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


def signoff_history_event(event: str, previous_signoff: DomainDocument, reason: str, *, now: str | None = None) -> DomainDocument:
    return sanitize_metadata(
        {
            "event": event,
            "created_at": now or now_iso(),
            "reason": sanitize_sensitive_text(str(reason or ""))[:1000],
            "previous_signoff": _as_document(previous_signoff),
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def scan_delivery_payload_for_sensitive_values(payload: Any) -> list[DomainDocument]:
    findings: list[ImplementationDocument] = []

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
        raw = _as_document(data)
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
            "quality_gate": _as_document(clean.get("quality_gate")),
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
            "review_sprint_closeout": _as_document(clean.get("review_sprint_closeout")),
            "review_metrics": _as_document(clean.get("review_metrics")),
            "review_judge": _as_document(clean.get("review_judge")),
            "zip": {key: value for key, value in (clean.get("zip") or {}).items() if key in {"filename", "size_bytes", "sha256", "entry_count", "entries"}} if isinstance(clean.get("zip"), dict) else {},
        },
        blocked_keys=BLOCKED_DELIVERY_KEYS,
    )


def _strip_delivery_summaries(manifest: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in (manifest or {}).items() if key not in {"delivery_qa", "delivery_signoff"}}


def _expected_files(project_dir: Path, manifest: ImplementationDocument, manifest_exists: bool) -> list[ImplementationDocument]:
    export_dir = final_export_dir(project_dir).resolve()
    rows_by_path: dict[str, ImplementationDocument] = {}
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


from song_agent.domains.delivery import v142_dq_readiness as _v142_dq_readiness
from song_agent.domains.delivery.v142_dq_readiness import _expected_file_row as _expected_file_row, _quality_gate_requires_stems as _quality_gate_requires_stems, _required_stem_midi_paths as _required_stem_midi_paths, _actual_export_files as _actual_export_files, _actual_zip_info as _actual_zip_info, _zip_manifest_matches_current as _zip_manifest_matches_current, _final_version_summary as _final_version_summary, _version_by_id as _version_by_id, _final_export_summary as _final_export_summary, _zip_summary as _zip_summary, _quality_gate_summary as _quality_gate_summary, _review_sprint_summary as _review_sprint_summary, _artifact_integrity_summary as _artifact_integrity_summary, _build_checks as _build_checks, _project_export_delivery_probe as _project_export_delivery_probe, _qa_status as _qa_status, _qa_readiness as _qa_readiness, _check as _check, _check_message as _check_message, _file_missing as _file_missing, _stem_audio_partial as _stem_audio_partial, _safe_export_path as _safe_export_path
from song_agent.domains.delivery import v142_dq_evidence as _v142_dq_evidence
from song_agent.domains.delivery.v142_dq_evidence import _validate_relative_path as _validate_relative_path, _path_presence as _path_presence, _sha256 as _sha256, _source_hash as _source_hash, _stable_hash as _stable_hash, _raw_stable_hash as _raw_stable_hash

_v142_dq_readiness.bind_globals(globals())
_v142_dq_evidence.bind_globals(globals())
