from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.delivery.delivery_qa import delivery_qa_source_hash
from song_agent.domains.creation.final_export import final_export_dir, final_export_zip_path, read_final_export_manifest
from song_agent.domains.studio.projectio import read_json
from song_agent.domains.studio.project_repository import ProjectStore, now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS, ReleaseDocument, ReleaseStore, ReleaseTrack, release_document_source, stable_hash


RELEASE_QA_SCHEMA_VERSION = 1
RELEASE_QA_STATUSES = {"passed", "warning", "failed", "stale"}
CORE_REQUIRED_TRACK_FILES = ("manifest.json", "README.txt", "project-export.json", "song-plan.json", "song.mid")
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


def build_release_qa_report(
    *,
    release: ReleaseDocument,
    release_store: ReleaseStore,
    project_store: ProjectStore,
    options: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    options = options or {}
    source = release_source_state(release, project_store=project_store, release_store=release_store)
    checks = _release_checks(release, options, source)
    track_checks: list[dict[str, Any]] = []
    for track in release.tracks:
        track_checks.extend(_track_checks(track, project_store=project_store, options=options, source=source["tracks"].get(track.track_id, {})))
    checks.extend(_cross_track_checks(release))
    checks.append(_redaction_check({"release": release.to_dict(), "raw_release": _raw_release_document(release_store, release.release_id), "source": source}))
    blockers = [check for check in [*checks, *track_checks] if check.get("severity") == "blocking" and check.get("status") == "failed"]
    warnings = [check for check in [*checks, *track_checks] if check.get("severity") == "warning" and check.get("status") == "warning"]
    status = "failed" if blockers else ("warning" if warnings else "passed")
    report = {
        "schema_version": RELEASE_QA_SCHEMA_VERSION,
        "release_id": release.release_id,
        "generated_at": now,
        "status": status,
        "source_hash": release_source_hash_from_state(source),
        "options": _qa_options(options),
        "checks": checks,
        "track_checks": track_checks,
        "blockers": [_check_message(check) for check in blockers],
        "warnings": [_check_message(check) for check in warnings],
        "summary": {
            "status": status,
            "track_count": len(release.tracks),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "source_hash": release_source_hash_from_state(source),
            "generated_at": now,
        },
    }
    return sanitize_metadata(report, blocked_keys=BLOCKED_RELEASE_KEYS)


def release_source_state(
    release: ReleaseDocument,
    *,
    project_store: ProjectStore,
    release_store: ReleaseStore | None = None,
) -> dict[str, Any]:
    tracks: dict[str, Any] = {}
    for track in release.tracks:
        tracks[track.track_id] = _track_source_state(track, project_store)
    return sanitize_metadata(
        {
            "release": release_document_source(release),
            "tracks": tracks,
            "export_manifest_hash": None,
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def release_source_hash(
    release: ReleaseDocument,
    *,
    project_store: ProjectStore,
    release_store: ReleaseStore | None = None,
) -> str:
    return release_source_hash_from_state(release_source_state(release, project_store=project_store, release_store=release_store))


def release_source_hash_from_state(source: dict[str, Any]) -> str:
    return stable_hash(source)


def release_qa_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or summary.get("status") or "missing",
            "track_count": summary.get("track_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "source_hash": data.get("source_hash") or summary.get("source_hash"),
            "generated_at": data.get("generated_at") or summary.get("generated_at"),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def release_qa_allows_export(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> bool:
    if not isinstance(report, dict):
        return False
    if report.get("status") not in {"passed", "warning"}:
        return False
    if current_source_hash and report.get("source_hash") != current_source_hash:
        return False
    return True


def release_qa_allows_signoff(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> bool:
    return release_qa_allows_export(report, current_source_hash=current_source_hash)


def mark_release_qa_stale(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> dict[str, Any]:
    data = dict(report or {})
    data["status"] = "stale"
    data["stale"] = True
    if current_source_hash:
        data["current_source_hash"] = current_source_hash
    return sanitize_metadata(data, blocked_keys=BLOCKED_RELEASE_KEYS)


def build_release_signoff_record(
    *,
    release: ReleaseDocument,
    report: dict[str, Any],
    payload: dict[str, Any] | None = None,
    export_manifest: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    payload = payload or {}
    force = bool(payload.get("force", False))
    if force and not str(payload.get("override_reason") or "").strip():
        raise ValueError("override_reason is required when force=true.")
    if not force and not release_qa_allows_signoff(report):
        raise ValueError("Release QA does not allow signoff.")
    blockers = report.get("blockers", []) if isinstance(report.get("blockers"), list) else []
    warnings = report.get("warnings", []) if isinstance(report.get("warnings"), list) else []
    record = {
        "schema_version": 1,
        "release_id": release.release_id,
        "status": "force_signed" if force else "signed",
        "signed_at": now,
        "signed_by": _safe_text(payload.get("signed_by"), "local-user"),
        "qa_source_hash": report.get("source_hash"),
        "release_source_hash": report.get("source_hash"),
        "export_manifest_hash": stable_hash(export_manifest) if isinstance(export_manifest, dict) and export_manifest else None,
        "forced": force,
        "override_reason": _safe_text(payload.get("override_reason"), "") if force else None,
        "acknowledged_blockers": blockers if force else [],
        "acknowledged_warnings": warnings,
        "notes": _safe_text(payload.get("notes"), ""),
    }
    return sanitize_metadata(record, blocked_keys=BLOCKED_RELEASE_KEYS)


def release_signoff_summary(record: dict[str, Any] | None) -> dict[str, Any]:
    data = record if isinstance(record, dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "not_signed",
            "release_id": data.get("release_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "qa_source_hash": data.get("qa_source_hash"),
            "export_manifest_hash": data.get("export_manifest_hash"),
            "forced": bool(data.get("forced", False)),
            "acceptance_gate": data.get("acceptance_gate") if isinstance(data.get("acceptance_gate"), dict) else {},
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def signoff_history_event(record: dict[str, Any], *, reason: str, now: str | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "timestamp": now or now_iso(),
            "event": "release_signoff_reset",
            "reason": sanitize_sensitive_text(str(reason or ""))[:500],
            "previous_summary": release_signoff_summary(record),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def scan_release_payload_for_sensitive_values(payload: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                child_path = f"{path}.{key_text}" if path else key_text
                if key_text.lower() in BLOCKED_RELEASE_KEYS:
                    findings.append({"path": child_path, "kind": "sensitive_key", "message": "Sensitive key is not allowed."})
                walk(item, child_path)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
            return
        if isinstance(value, str):
            for pattern, kind in SENSITIVE_VALUE_PATTERNS:
                if pattern.search(value):
                    findings.append({"path": path, "kind": kind, "message": f"Sensitive value detected: {kind}."})
                    break

    walk(payload, "")
    return sanitize_metadata(findings, blocked_keys=BLOCKED_RELEASE_KEYS)


def _track_source_state(track: ReleaseTrack, project_store: ProjectStore) -> ImplementationDocument:
    state: dict[str, Any] = {"track_id": track.track_id, "project_id": track.project_id, "version_id": track.version_id}
    try:
        document = project_store.get_project(track.project_id)
        project_dir = project_store.project_dir(track.project_id)
        manifest = read_final_export_manifest(project_dir)
        qa = project_store.read_delivery_qa(track.project_id, default={})
        signoff = project_store.read_delivery_signoff(track.project_id, default={})
        current_qa_source = delivery_qa_source_hash(project_id=track.project_id, project_document=document, project_dir=project_dir, project_export=project_store.project_export_snapshot(track.project_id), final_export_manifest=manifest)
        state.update(
            {
                "project_exists": True,
                "project_hidden": document.state.hidden,
                "project_final_version_id": document.state.final_version_id,
                "version_exists": any(version.version_id == track.version_id for version in document.versions),
                "final_export_manifest_hash": _file_sha256(final_export_dir(project_dir) / "manifest.json"),
                "final_export_zip_hash": _file_sha256(final_export_zip_path(project_dir)),
                "delivery_qa_hash": stable_hash(qa) if qa else None,
                "delivery_qa_status": qa.get("status"),
                "delivery_qa_source_hash": qa.get("source_hash"),
                "delivery_qa_current_source_hash": current_qa_source,
                "delivery_signoff_hash": stable_hash(signoff) if signoff else None,
                "delivery_signoff_status": signoff.get("status"),
                "delivery_signoff_final_version_id": signoff.get("final_version_id"),
                "delivery_signoff_qa_source_hash": signoff.get("delivery_qa_source_hash"),
                "manifest_version_id": manifest.get("version_id"),
            }
        )
    except Exception as exc:
        state.update({"project_exists": False, "error": str(exc)})
    return sanitize_metadata(state, blocked_keys=BLOCKED_RELEASE_KEYS)


def _release_checks(release: ReleaseDocument, options: ImplementationDocument, source: ImplementationDocument) -> list[ImplementationDocument]:
    expected = _expected_track_count(release.release_type)
    track_positions = [(track.disc_number, track.track_number) for track in release.tracks]
    duplicate_positions = len(track_positions) != len(set(track_positions))
    duplicate_project_versions = len({(track.project_id, track.version_id) for track in release.tracks}) != len(release.tracks)
    checks = [
        _check("release_exists", False, "blocking", "Release exists.", 0),
        _check("metadata_complete", not release.name or not release.primary_artist, "warning", "Release name and primary artist should be complete.", 1 if not release.primary_artist else 0),
        _check("track_count", len(release.tracks) < expected, "blocking", f"Release requires at least {expected} track(s).", len(release.tracks)),
        _check("track_order_unique", duplicate_positions, "blocking", "Track disc/number positions must be unique.", 1 if duplicate_positions else 0),
        _check("no_duplicate_project_version", duplicate_project_versions, "warning", "Release includes the same project/version more than once.", 1 if duplicate_project_versions else 0),
    ]
    return checks


def _track_checks(track: ReleaseTrack, *, project_store: ProjectStore, options: ImplementationDocument, source: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    try:
        document = project_store.get_project(track.project_id)
        project_dir = project_store.project_dir(track.project_id)
    except FileNotFoundError:
        return [_track_check(track, "project_exists", True, "blocking", "Project does not exist.", 1)]
    version_exists = any(version.version_id == track.version_id for version in document.versions)
    final_export_path = final_export_dir(project_dir)
    manifest_path = final_export_path / "manifest.json"
    manifest = _read_optional_json(manifest_path)
    qa = project_store.read_delivery_qa(track.project_id, default={})
    signoff = project_store.read_delivery_signoff(track.project_id, default={})
    current_qa_source = source.get("delivery_qa_current_source_hash")
    required_missing = [path for path in CORE_REQUIRED_TRACK_FILES if not _safe_project_export_path(final_export_path, path).exists()]
    if bool(options.get("require_audio", False)) and not _safe_project_export_path(final_export_path, "song.wav").exists():
        required_missing.append("song.wav")
    if bool(options.get("require_stems", False)) and not _safe_project_export_path(final_export_path, "stems/manifest.json").exists():
        required_missing.append("stems/manifest.json")
    checks.extend(
        [
            _track_check(track, "project_exists", False, "blocking", "Project exists.", 0),
            _track_check(track, "version_exists", not version_exists, "blocking", "Track version does not exist.", 1 if not version_exists else 0),
            _track_check(track, "version_is_final", bool(track.version_id != document.state.final_version_id), "blocking", "Track version must match Project final version.", 1 if track.version_id != document.state.final_version_id else 0),
            _track_check(track, "project_not_hidden", bool(document.state.hidden), "blocking", "Hidden Project cannot be released.", 1 if document.state.hidden else 0),
            _track_check(track, "final_export_exists", not final_export_path.exists(), "blocking", "Project Final Export directory is missing.", 1 if not final_export_path.exists() else 0),
            _track_check(track, "final_export_manifest_exists", not manifest_path.exists() or not manifest, "blocking", "Project Final Export manifest is missing or invalid.", 1 if not manifest else 0),
            _track_check(track, "final_export_manifest_safe", bool(manifest and _manifest_has_unsafe_paths(manifest)), "blocking", "Project Final Export manifest contains unsafe paths.", 1 if _manifest_has_unsafe_paths(manifest) else 0),
            _track_check(track, "final_export_core_files", bool(required_missing), "blocking", "Project Final Export core files are missing.", len(required_missing)),
            _track_check(track, "delivery_qa_exists", not bool(qa), "blocking", "Project Delivery QA is missing.", 1 if not qa else 0),
            _track_check(track, "delivery_qa_passed", bool(qa and qa.get("status") not in {"passed", "warning"}), "blocking", "Project Delivery QA must be passed or warning.", 1 if qa and qa.get("status") not in {"passed", "warning"} else 0),
            _track_check(track, "delivery_qa_current", bool(qa and current_qa_source and qa.get("source_hash") != current_qa_source), "blocking", "Project Delivery QA is stale.", 1 if qa and current_qa_source and qa.get("source_hash") != current_qa_source else 0),
            _track_check(track, "delivery_signoff_exists", not bool(signoff), "blocking", "Project Delivery Signoff is missing.", 1 if not signoff else 0),
            _track_check(track, "delivery_signoff_final_version", bool(signoff and signoff.get("final_version_id") != track.version_id), "blocking", "Project Delivery Signoff final version does not match track version.", 1 if signoff and signoff.get("final_version_id") != track.version_id else 0),
            _track_check(track, "delivery_signoff_current", bool(signoff and qa and signoff.get("delivery_qa_source_hash") != qa.get("source_hash")), "blocking", "Project Delivery Signoff is not bound to current Delivery QA.", 1 if signoff and qa and signoff.get("delivery_qa_source_hash") != qa.get("source_hash") else 0),
            _track_check(track, "track_snapshot_current", bool(track.final_export_hash and source.get("final_export_manifest_hash") and track.final_export_hash != source.get("final_export_manifest_hash")), "warning", "Track snapshot differs from current Project Final Export.", 1 if track.final_export_hash and source.get("final_export_manifest_hash") and track.final_export_hash != source.get("final_export_manifest_hash") else 0),
            _track_check(track, "zip_integrity", bool(options.get("require_zip", True) and not _project_zip_ok(project_dir, manifest)), "blocking", "Project Final Export ZIP is missing or stale.", 1 if options.get("require_zip", True) and not _project_zip_ok(project_dir, manifest) else 0),
        ]
    )
    return checks


def _cross_track_checks(release: ReleaseDocument) -> list[ImplementationDocument]:
    titles = [track.title.strip().lower() for track in release.tracks if track.title.strip()]
    artists = {track.artist or release.primary_artist for track in release.tracks if track.artist or release.primary_artist}
    return [
        _check("title_duplicates", len(titles) != len(set(titles)), "warning", "Release has duplicate track titles.", 1 if len(titles) != len(set(titles)) else 0),
        _check("artist_consistency", len(artists) > 1, "warning", "Release has multiple track artists.", len(artists) if len(artists) > 1 else 0),
    ]


def _redaction_check(payload: ImplementationDocument) -> ImplementationDocument:
    findings = scan_release_payload_for_sensitive_values(payload)
    return _check("redaction_scan", bool(findings), "blocking", "Release payload contains sensitive fields or values.", len(findings))


def _check(check_id: str, failed: bool, severity: str, message: str, count: int | float | None = 0) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "scope": "release",
            "check_id": check_id,
            "status": "failed" if failed and severity == "blocking" else ("warning" if failed else "passed"),
            "severity": severity,
            "message": message,
            "count": count,
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _track_check(track: ReleaseTrack, check_id: str, failed: bool, severity: str, message: str, count: int | float | None = 0) -> ImplementationDocument:
    data = _check(check_id, failed, severity, message, count)
    data.update({"scope": "track", "track_id": track.track_id, "project_id": track.project_id, "version_id": track.version_id})
    return sanitize_metadata(data, blocked_keys=BLOCKED_RELEASE_KEYS)


def _check_message(check: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "scope": check.get("scope"),
            "check_id": check.get("check_id"),
            "track_id": check.get("track_id"),
            "message": sanitize_sensitive_text(str(check.get("message") or ""))[:240],
            "count": check.get("count"),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _expected_track_count(release_type: str) -> int:
    return {"single_pack": 1, "demo_pack": 1, "ep": 2, "album": 2}.get(release_type, 1)


def _safe_project_export_path(export_dir: Path, relative_path: str) -> Path:
    safe = _validate_relative_path(relative_path)
    target = (export_dir / safe).resolve()
    target.relative_to(export_dir.resolve())
    return target


def _validate_relative_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or normalized.startswith("/") or normalized.startswith("\\") or normalized.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise ValueError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()


def _manifest_has_unsafe_paths(manifest: ImplementationDocument) -> bool:
    for item in manifest.get("files", []) if isinstance(manifest.get("files"), list) else []:
        if not isinstance(item, dict):
            continue
        try:
            _validate_relative_path(str(item.get("path") or ""))
        except ValueError:
            return True
    return False


def _project_zip_ok(project_dir: Path, manifest: ImplementationDocument) -> bool:
    zip_path = final_export_zip_path(project_dir)
    export_dir = final_export_dir(project_dir)
    if not zip_path.exists() or not zip_path.is_file() or zip_path.is_symlink():
        return False
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            names = [name.replace("\\", "/") for name in archive.namelist() if not name.endswith("/")]
            for name in names:
                _validate_relative_path(name)
            return "manifest.json" in names and all(path in names for path in CORE_REQUIRED_TRACK_FILES if (export_dir / path).exists())
    except (OSError, ValueError, zipfile.BadZipFile):
        return False


def _qa_options(options: ImplementationDocument) -> ImplementationDocument:
    return {
        "require_audio": bool(options.get("require_audio", False)),
        "require_stems": bool(options.get("require_stems", False)),
        "require_zip": bool(options.get("require_zip", True)),
    }


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _raw_release_document(release_store: ReleaseStore, release_id: str) -> ImplementationDocument:
    return _read_optional_json(release_store.release_dir(release_id) / "release.json")


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_text(value: Any, fallback: str) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())[:500]
    return text or fallback
