# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_continuous_assurance import TrustOperationsAssuranceStore as TrustOperationsAssuranceStore
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_assurance_watch_contracts import ASSURANCE_WATCH_ARCHIVE_ENTRIES as ASSURANCE_WATCH_ARCHIVE_ENTRIES, TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION, watch_hash as watch_hash, watch_manifest_hash as watch_manifest_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

TrustOperationsAssuranceWatchStateError = _make_deferred_global('TrustOperationsAssuranceWatchStateError')
ch = _make_deferred_global('ch')
item = _make_deferred_global('item')
run = _make_deferred_global('run')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsAssuranceWatchStateError, ch, item, run
    TrustOperationsAssuranceWatchStateError = namespace.get('TrustOperationsAssuranceWatchStateError', TrustOperationsAssuranceWatchStateError)
    ch = namespace.get('ch', ch)
    item = namespace.get('item', item)
    run = namespace.get('run', run)
    _bind_deferred_defaults(namespace)






def _default_schedule(now: str | None = None) -> DomainDocument:
    now = now or _now()
    schedule = {
        "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
        "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE,
        "schedule_id": "default",
        "status": "active",
        "name": "Default Trust Operations Assurance Watch Schedule",
        "scope": {"hub_ids": ["hub"], "include_all_hubs": False},
        "cadence": {"interval_days": 7, "grace_days": 1, "max_overdue_days": 14},
        "requirements": {
            "require_latest_assurance_passed": True,
            "require_latest_assurance_verified": True,
            "require_hub_binding_current": True,
            "require_no_failed_delivery": True,
            "require_no_open_blocking_incident": True,
            "require_no_expired_exception": True,
        },
        "actions": {
            "create_refresh_action_when_due": True,
            "create_incident_review_action_on_blocker": True,
            "create_change_request_action_on_signed_stale": True,
        },
        "created_at": now,
        "updated_at": now,
    }
    schedule["integrity_hash"] = watch_hash(schedule)
    return schedule

def _external_row(component_type: str, archive_path: Path | None, report_path: Path | None, manifest_entry: str) -> DomainDocument:
    report = _read_json_default(report_path, default={}) if report_path else {}
    manifest = _read_zip_json_optional(archive_path, manifest_entry) if archive_path and manifest_entry else {}
    zip_sha = _sha256(archive_path) if archive_path and archive_path.exists() else report.get("zip_sha256")
    zip_size = os.stat(_fs_path(archive_path)).st_size if archive_path and archive_path.exists() else report.get("zip_size_bytes")
    manifest_hash = manifest.get("integrity_hash") or report.get("manifest_hash")
    status = str(report.get("status") or "missing")
    component_id = str((_as_document(report.get("summary"))).get("run_id") or report.get("run_id") or component_type)
    row = {
        "component_type": component_type,
        "component_id": component_id,
        "package_type": report.get("package_type"),
        "verification_status": status,
        "zip_sha256": zip_sha,
        "zip_size_bytes": zip_size,
        "manifest_hash": manifest_hash,
        "verification_report_hash": verification_hash(report) if report else None,
        "source_hash": report.get("source_hash"),
        "generated_at": report.get("generated_at"),
        "summary": _as_document(report.get("summary")),
        "_archive_path": str(archive_path) if archive_path else None,
        "_report_path": str(report_path) if report_path else None,
    }
    if report:
        if report.get("zip_sha256") not in {None, zip_sha}:
            row["verification_status"] = "failed"
            row["stale_reason"] = "zip_sha256_mismatch"
        if report.get("zip_size_bytes") not in {None, zip_size}:
            row["verification_status"] = "failed"
            row["stale_reason"] = "zip_size_mismatch"
        if report.get("manifest_hash") not in {None, manifest_hash}:
            row["verification_status"] = "failed"
            row["stale_reason"] = "manifest_hash_mismatch"
    return row

def _public_row(row: DomainDocument) -> DomainDocument:
    return {key: value for key, value in row.items() if not str(key).startswith("_")}

def _action(action_id: str, queue_id: str, hub_id: str, action_type: str, severity: str, reason: str, row: DomainDocument, now: str) -> DomainDocument:
    action = {
        "action_id": action_id,
        "queue_id": queue_id,
        "hub_id": hub_id,
        "action_type": action_type,
        "status": "pending",
        "severity": severity,
        "reason": reason,
        "source": {
            "queue_row_hash": stable_hash({key: value for key, value in row.items() if key not in {"action_ids", "integrity_hash"}}),
            "latest_assurance_run_id": row.get("latest_assurance_run_id"),
        },
        "manual_required": True,
        "safe_to_auto_run": False,
        "created_at": now,
    }
    action["integrity_hash"] = watch_hash(action)
    return action

def _actions_for_row(row: DomainDocument) -> list[tuple[str, str, str]]:
    actions: list[tuple[str, str, str]] = []
    due_status = row.get("due_status")
    if due_status == "missing":
        actions.append(("refresh_assurance", "high", "Assurance run is missing."))
    elif due_status == "overdue":
        actions.append(("refresh_assurance", "high", "Assurance run is overdue."))
    elif due_status == "due":
        actions.append(("refresh_assurance", "medium", "Assurance run is due."))
    if "assurance_verification_not_passed" in row.get("reasons", []):
        actions.append(("verify_assurance_archive", "high", "Assurance archive verification is missing or failed."))
    if "assurance_run_failed" in row.get("reasons", []):
        actions.append(("manual_delivery_review_required", "high", "Assurance run failed and requires manual review."))
    return actions

def _queue_summary(rows: list[DomainDocument], action_pack: DomainDocument) -> DomainDocument:
    actions_summary = _as_document(action_pack.get("summary"))
    return {
        "hub_count": len(rows),
        "clear_count": sum(1 for row in rows if row.get("readiness") == "clear"),
        "due_count": sum(1 for row in rows if row.get("due_status") == "due"),
        "overdue_count": sum(1 for row in rows if row.get("due_status") == "overdue"),
        "stale_count": sum(1 for row in rows if row.get("drift_status") == "stale"),
        "failed_count": sum(1 for row in rows if row.get("readiness") == "blocked" or row.get("drift_status") in {"failed", "missing"}),
        "blocking_action_count": int(actions_summary.get("blocking_count") or 0),
        "manual_action_count": int(actions_summary.get("manual_required_count") or 0),
    }

def _queue_status(summary: DomainDocument) -> str:
    if int(summary.get("failed_count") or 0) or int(summary.get("overdue_count") or 0) or int(summary.get("blocking_action_count") or 0):
        return "blocked"
    if int(summary.get("due_count") or 0) or int(summary.get("manual_action_count") or 0):
        return "warning"
    return "clear"

def _action_summary(actions: list[DomainDocument]) -> DomainDocument:
    return {
        "action_count": len(actions),
        "blocking_count": sum(1 for action in actions if action.get("severity") in {"critical", "high"}),
        "manual_required_count": sum(1 for action in actions if action.get("manual_required")),
        "safe_auto_count": sum(1 for action in actions if action.get("safe_to_auto_run")),
    }

def _manifest(queue: DomainDocument, export_dir: Path, now: str) -> DomainDocument:
    schedule = _read_json_required(export_dir / "schedule-snapshot.json", "Schedule snapshot is missing.")
    run_index = _read_json_required(export_dir / "assurance-run-index.json", "Assurance run index is missing.")
    action_pack = _read_json_required(export_dir / "drift-action-pack.json", "Drift action pack is missing.")
    external_summary = _read_json_required(export_dir / "external-verification-summary.json", "External verification summary is missing.")
    history_hash = _sha256(export_dir / "watch-history.jsonl")
    source = {
        "watch_queue_hash": queue.get("integrity_hash"),
        "schedule_hash": schedule.get("integrity_hash"),
        "assurance_run_index_hash": run_index.get("integrity_hash"),
        "drift_action_pack_hash": action_pack.get("integrity_hash"),
        "external_verification_summary_hash": external_summary.get("integrity_hash"),
        "history_hash": history_hash,
    }
    manifest = {
        "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
        "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE,
        "tool": {"name": "MusicForge Trust Operations Assurance Watch", "version": __version__},
        "queue_id": queue.get("queue_id"),
        "schedule_id": queue.get("schedule_id"),
        "status": queue.get("status"),
        "source_hash": queue.get("source_hash"),
        "source": source,
        "generated_at": now,
        "files": _manifest_files(export_dir),
        "zip": {},
    }
    manifest["integrity_hash"] = watch_manifest_hash(manifest)
    return manifest

def _manifest_files(export_dir: Path) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for path, rel in _zip_entries(export_dir):
        if rel == "trust-operations-assurance-watch-manifest.json":
            continue
        rows.append({"path": rel, "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)})
    return sorted(rows, key=lambda row: row["path"])

def _due_status(last_at: str, now: str, interval_days: int, grace_days: int) -> tuple[str, str | None]:
    base = _parse_dt(last_at)
    current = _parse_dt(now)
    if not base or not current:
        return "unknown", None
    next_due = base + timedelta(days=max(0, interval_days))
    if current <= next_due:
        return "not_due", next_due.isoformat()
    if current <= next_due + timedelta(days=max(0, grace_days)):
        return "due", next_due.isoformat()
    return "overdue", next_due.isoformat()

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def _latest_run(runs: list[DomainDocument]) -> DomainDocument | None:
    if not runs:
        return None
    return sorted(runs, key=lambda run: str(run.get("created_at") or run.get("updated_at") or run.get("run_id") or ""))[-1]

def _source_paths(payload: DomainDocument) -> DomainDocument:
    return {
        "assurance_archive_path": [str(path) for path in _paths(payload.get("assurance_archive_path") or payload.get("assurance_archive"))],
        "assurance_verification_report_path": [str(path) for path in _paths(payload.get("assurance_verification_report_path") or payload.get("assurance_verification_report"))],
        "hub_package_path": [str(path) for path in _paths(payload.get("hub_package_path") or payload.get("hub_package"))],
        "hub_verification_report_path": [str(path) for path in _paths(payload.get("hub_verification_report_path") or payload.get("hub_verification_report"))],
    }

def _verifier_kwargs_from_source_paths(source_paths: DomainDocument) -> DomainDocument:
    return {
        "assurance_archive_path": _first_path(source_paths.get("assurance_archive_path")),
        "assurance_verification_report_path": _first_path(source_paths.get("assurance_verification_report_path")),
        "hub_package_path": _first_path(source_paths.get("hub_package_path")),
        "hub_verification_report_path": _first_path(source_paths.get("hub_verification_report_path")),
    }

def _paths(value: object) -> list[Path]:
    if value is None or value == "":
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, (list, tuple)):
        return [Path(item) for item in value if item]
    return []

def _first_path(value: object) -> Path | None:
    values = _paths(value)
    return values[0] if values else None

def _list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]

def _read_json_required(path: Path, message: str) -> DomainDocument:
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TrustOperationsAssuranceWatchStateError(message) from exc

def _read_json_default(path: Path | None, *, default: DomainDocument) -> DomainDocument:
    try:
        if path is None or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)

def _read_zip_json_optional(zip_path: Path | None, entry: str) -> DomainDocument:
    if not zip_path:
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}

def _write_json(path: Path, payload: DomainDocument) -> Path:
    _mkdir(path.parent)
    return write_json(path, _sanitize(payload))

def _write_internal_json(path: Path, payload: DomainDocument) -> Path:
    _mkdir(path.parent)
    return write_json(path, payload)

def _append_jsonl(path: Path, payload: DomainDocument) -> None:
    _mkdir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""

def _write_readme(export_dir: Path) -> None:
    (export_dir / "README.txt").write_text(
        "MusicForge Trust Operations Assurance Watch Archive\n"
        "This package contains a local schedule queue and drift action pack. It does not execute repairs.\n",
        encoding="utf-8",
    )

def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for path in sorted(export_dir.rglob("*")):
        if path.is_file():
            rows.append((path, path.relative_to(export_dir).as_posix()))
    return rows

def _write_zip(zip_path: Path, export_dir: Path) -> None:
    _mkdir(zip_path.parent)
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, rel in _zip_entries(export_dir):
            archive.write(_fs_path(path), rel)

def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _next_id(directory: Path, prefix: str) -> str:
    _mkdir(directory)
    existing = []
    for path in directory.iterdir():
        if path.is_dir() and path.name.startswith(prefix + "-"):
            try:
                existing.append(int(path.name.rsplit("-", 1)[1]))
            except (IndexError, ValueError):
                continue
    return f"{prefix}-{(max(existing) if existing else 0) + 1:06d}"

def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"

def _deep_update(target: DomainDocument, patch: DomainDocument) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value

def _clone(value: DomainDocument) -> DomainDocument:
    return json.loads(json.dumps(value, ensure_ascii=False))

def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def _fs_path(path: Path) -> str:
    return str(path)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sanitize(value: object) -> DomainDocument:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS)

def _sanitize_text(text: str) -> str:
    return sanitize_sensitive_text(text)
