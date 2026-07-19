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

TrustOperationsAssuranceWatchNotFoundError = _make_deferred_global('TrustOperationsAssuranceWatchNotFoundError')
TrustOperationsAssuranceWatchStateError = _make_deferred_global('TrustOperationsAssuranceWatchStateError')
_action = _make_deferred_global('_action')
_action_summary = _make_deferred_global('_action_summary')
_actions_for_row = _make_deferred_global('_actions_for_row')
_append_jsonl = _make_deferred_global('_append_jsonl')
_clone = _make_deferred_global('_clone')
_deep_update = _make_deferred_global('_deep_update')
_default_schedule = _make_deferred_global('_default_schedule')
_due_status = _make_deferred_global('_due_status')
_external_row = _make_deferred_global('_external_row')
_first_path = _make_deferred_global('_first_path')
_fs_path = _make_deferred_global('_fs_path')
_latest_run = _make_deferred_global('_latest_run')
_list = _make_deferred_global('_list')
_manifest = _make_deferred_global('_manifest')
_mkdir = _make_deferred_global('_mkdir')
_next_id = _make_deferred_global('_next_id')
_now = _make_deferred_global('_now')
_public_row = _make_deferred_global('_public_row')
_queue_status = _make_deferred_global('_queue_status')
_queue_summary = _make_deferred_global('_queue_summary')
_read_json_default = _make_deferred_global('_read_json_default')
_read_json_required = _make_deferred_global('_read_json_required')
_read_text = _make_deferred_global('_read_text')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_source_paths = _make_deferred_global('_source_paths')
_verifier_kwargs_from_source_paths = _make_deferred_global('_verifier_kwargs_from_source_paths')
_write_internal_json = _make_deferred_global('_write_internal_json')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
entry = _make_deferred_global('entry')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global TrustOperationsAssuranceWatchNotFoundError, TrustOperationsAssuranceWatchStateError, _action, _action_summary, _actions_for_row, _append_jsonl, _clone, _deep_update
    global _default_schedule, _due_status, _external_row, _first_path, _fs_path, _latest_run, _list
    global _manifest, _mkdir, _next_id, _now, _public_row, _queue_status, _queue_summary, _read_json_default
    global _read_json_required, _read_text, _safe_id, _sanitize, _sha256, _source_paths, _verifier_kwargs_from_source_paths, _write_internal_json
    global _write_json, _write_readme, _write_zip, _zip_entries, entry, item, key, value
    TrustOperationsAssuranceWatchNotFoundError = namespace.get('TrustOperationsAssuranceWatchNotFoundError', TrustOperationsAssuranceWatchNotFoundError)
    TrustOperationsAssuranceWatchStateError = namespace.get('TrustOperationsAssuranceWatchStateError', TrustOperationsAssuranceWatchStateError)
    _action = namespace.get('_action', _action)
    _action_summary = namespace.get('_action_summary', _action_summary)
    _actions_for_row = namespace.get('_actions_for_row', _actions_for_row)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _clone = namespace.get('_clone', _clone)
    _deep_update = namespace.get('_deep_update', _deep_update)
    _default_schedule = namespace.get('_default_schedule', _default_schedule)
    _due_status = namespace.get('_due_status', _due_status)
    _external_row = namespace.get('_external_row', _external_row)
    _first_path = namespace.get('_first_path', _first_path)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _latest_run = namespace.get('_latest_run', _latest_run)
    _list = namespace.get('_list', _list)
    _manifest = namespace.get('_manifest', _manifest)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _next_id = namespace.get('_next_id', _next_id)
    _now = namespace.get('_now', _now)
    _public_row = namespace.get('_public_row', _public_row)
    _queue_status = namespace.get('_queue_status', _queue_status)
    _queue_summary = namespace.get('_queue_summary', _queue_summary)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_json_required = namespace.get('_read_json_required', _read_json_required)
    _read_text = namespace.get('_read_text', _read_text)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _source_paths = namespace.get('_source_paths', _source_paths)
    _verifier_kwargs_from_source_paths = namespace.get('_verifier_kwargs_from_source_paths', _verifier_kwargs_from_source_paths)
    _write_internal_json = namespace.get('_write_internal_json', _write_internal_json)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    entry = namespace.get('entry', entry)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)






class TrustOperationsAssuranceWatchStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations" / "assurance-watch",
        *,
        assurance_store: TrustOperationsAssuranceStore | None = None,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.assurance_store = assurance_store or TrustOperationsAssuranceStore(hub_store=self.hub_store)
        self.lock = threading.RLock()

    def schedules_dir(self) -> Path:
        return self.root / "schedules"

    def schedule_path(self, schedule_id: str = "default") -> Path:
        return self.schedules_dir() / (_safe_id(schedule_id) + ".json")

    def queues_dir(self) -> Path:
        return self.root / "queues"

    def queue_dir(self, queue_id: str) -> Path:
        return self.queues_dir() / _safe_id(queue_id)

    def queue_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "watch-queue.json"

    def schedule_snapshot_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "schedule-snapshot.json"

    def run_index_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "assurance-run-index.json"

    def action_pack_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "drift-action-pack.json"

    def external_summary_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "external-verification-summary.json"

    def source_paths_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "source-paths.json"

    def history_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "watch-history.jsonl"

    def export_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "export"

    def watch_zip_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "trust-operations-assurance-watch.zip"

    def verification_report_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "trust-operations-assurance-watch-verification-report.json"

    def ensure_default_schedule(self) -> DomainDocument:
        return self.read_schedule("default")

    def read_schedule(self, schedule_id: str = "default") -> DomainDocument:
        path = self.schedule_path(schedule_id)
        if not path.exists():
            if schedule_id != "default":
                raise TrustOperationsAssuranceWatchNotFoundError(f"Assurance Watch schedule not found: {schedule_id}")
            return self.write_schedule(_default_schedule())
        return _read_json_required(path, "Assurance Watch schedule cannot be read.")

    def write_schedule(self, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            schedule = _default_schedule(now)
            _deep_update(schedule, {key: _sanitize(value) for key, value in payload.items() if key not in {"integrity_hash"}})
            schedule["schedule_id"] = _safe_id(str(schedule.get("schedule_id") or "default"))
            schedule["updated_at"] = now
            schedule["integrity_hash"] = watch_hash(schedule)
            _write_json(self.schedule_path(str(schedule["schedule_id"])), schedule)
            return _sanitize(schedule)

    def list_queues(self, schedule_id: str | None = None) -> list[DomainDocument]:
        if not self.queues_dir().exists():
            return []
        rows: list[DomainDocument] = []
        for path in sorted(self.queues_dir().glob("*/watch-queue.json")):
            queue = _read_json_default(path, default={})
            if not queue:
                continue
            if schedule_id and queue.get("schedule_id") != schedule_id:
                continue
            rows.append(_sanitize(queue))
        return rows

    def read_queue(self, queue_id: str) -> DomainDocument:
        queue = _read_json_default(self.queue_path(queue_id), default={})
        if not queue:
            raise TrustOperationsAssuranceWatchNotFoundError(f"Assurance Watch queue not found: {queue_id}")
        return _sanitize(queue)

    def summary(self, queue_id: str) -> DomainDocument:
        return {
            "queue": self.read_queue(queue_id),
            "schedule": _read_json_default(self.schedule_snapshot_path(queue_id), default={}),
            "run_index": _read_json_default(self.run_index_path(queue_id), default={}),
            "action_pack": _read_json_default(self.action_pack_path(queue_id), default={}),
            "external_verification_summary": _read_json_default(self.external_summary_path(queue_id), default={}),
            "verification": _read_json_default(self.verification_report_path(queue_id), default={}),
        }

    def refresh_queue(
        self,
        payload: DomainDocument | None = None,
        *,
        schedule_id: str = "default",
        now: str | None = None,
    ) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            schedule = self.read_schedule(schedule_id)
            if payload.get("hub_id") or payload.get("hub_ids") or payload.get("include_all_hubs") is not None:
                schedule = _clone(schedule)
                schedule.setdefault("scope", {})
                if payload.get("hub_id"):
                    schedule["scope"]["hub_ids"] = [str(payload.get("hub_id"))]
                if payload.get("hub_ids"):
                    schedule["scope"]["hub_ids"] = [str(item) for item in _list(payload.get("hub_ids"))]
                if payload.get("include_all_hubs") is not None:
                    schedule["scope"]["include_all_hubs"] = bool(payload.get("include_all_hubs"))
                schedule["integrity_hash"] = watch_hash(schedule)
            queue_id = _safe_id(str(payload.get("queue_id") or _next_id(self.queues_dir(), "toawq")))
            source_paths = _source_paths(payload)
            hub_ids = self._hub_ids(schedule, payload)
            run_index, external_summary, raw_external_rows = self._build_sources(queue_id, schedule, hub_ids, source_paths)
            rows, action_pack = self._build_rows_and_actions(queue_id, schedule, hub_ids, run_index, external_summary, now)
            source = {
                "schedule_hash": schedule.get("integrity_hash"),
                "assurance_run_index_hash": run_index.get("integrity_hash"),
                "external_verification_summary_hash": external_summary.get("integrity_hash"),
                "drift_action_pack_hash": action_pack.get("integrity_hash"),
            }
            queue = {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE,
                "queue_id": queue_id,
                "schedule_id": schedule.get("schedule_id") or schedule_id,
                "created_at": now,
                "refreshed_at": now,
                "source": source,
                "source_hash": stable_hash(source),
                "rows": rows,
                "summary": _queue_summary(rows, action_pack),
            }
            queue["status"] = _queue_status(_as_document(queue["summary"]))
            queue["readiness"] = queue["status"]
            queue["integrity_hash"] = watch_hash(queue)
            _mkdir(self.queue_dir(queue_id))
            _write_json(self.queue_path(queue_id), queue)
            _write_json(self.schedule_snapshot_path(queue_id), schedule)
            _write_json(self.run_index_path(queue_id), run_index)
            _write_json(self.action_pack_path(queue_id), action_pack)
            _write_json(self.external_summary_path(queue_id), external_summary)
            _write_internal_json(self.source_paths_path(queue_id), {"queue_id": queue_id, "schedule_id": schedule_id, "paths": source_paths})
            self._append_history(queue_id, {"event_type": "assurance_watch_queue_refreshed", "created_at": now, "queue_id": queue_id, "source_hash": queue["source_hash"], "status": queue["status"]})
            return {
                "queue": _sanitize(queue),
                "schedule": _sanitize(schedule),
                "assurance_run_index": _sanitize(run_index),
                "drift_action_pack": _sanitize(action_pack),
                "external_verification_summary": _sanitize(external_summary),
                "raw_external_rows": _sanitize({"rows": raw_external_rows}),
            }

    def export_watch(self, queue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            queue = self.read_queue(queue_id)
            self._ensure_queue_current(queue, payload or {}, now=now)
            export_dir = self.export_dir(queue_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            _write_readme(export_dir)
            for source, name in (
                (self.queue_path(queue_id), "watch-queue.json"),
                (self.schedule_snapshot_path(queue_id), "schedule-snapshot.json"),
                (self.run_index_path(queue_id), "assurance-run-index.json"),
                (self.action_pack_path(queue_id), "drift-action-pack.json"),
                (self.external_summary_path(queue_id), "external-verification-summary.json"),
            ):
                shutil.copy2(_fs_path(source), _fs_path(export_dir / name))
            (export_dir / "watch-history.jsonl").write_text(_read_text(self.history_path(queue_id)), encoding="utf-8")
            manifest = _manifest(queue, export_dir, now)
            _write_json(export_dir / "trust-operations-assurance-watch-manifest.json", manifest)
            self._append_history(queue_id, {"event_type": "assurance_watch_exported", "created_at": now, "queue_id": queue_id, "manifest_hash": manifest["integrity_hash"]})
            return _sanitize(manifest)

    def build_watch_zip(self, queue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            queue = self.read_queue(queue_id)
            self._ensure_queue_current(queue, payload or {}, now=now)
            export_dir = self.export_dir(queue_id)
            manifest_path = export_dir / "trust-operations-assurance-watch-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsAssuranceWatchStateError("Assurance Watch export is missing.")
            if manifest.get("source_hash") != queue.get("source_hash"):
                raise TrustOperationsAssuranceWatchStateError("Assurance Watch export is stale.")
            zip_path = self.watch_zip_path(queue_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {
                "created_at": now,
                "filename": zip_path.name,
                "entry_count": len(entries),
                "entries": [entry for _path, entry in entries],
                "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries),
            }
            manifest["integrity_hash"] = watch_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "queue_id": queue_id}
            self._append_history(queue_id, {"event_type": "assurance_watch_zip_built", "created_at": now, "queue_id": queue_id, "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]})
            return _sanitize(info)

    def verify_watch_zip(self, queue_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.trust_operations_assurance_watch_verifier import verify_trust_operations_assurance_watch_package

        payload = payload or {}
        stored = _read_json_default(self.source_paths_path(queue_id), default={}).get("paths")
        source_paths = _source_paths(payload) if payload else (_as_document(stored))
        report = verify_trust_operations_assurance_watch_package(
            self.watch_zip_path(queue_id),
            strict=bool(payload.get("strict", False)),
            require_clear=bool(payload.get("require_clear", True)),
            require_current=bool(payload.get("require_current", True)),
            **_verifier_kwargs_from_source_paths(source_paths),
        )
        _write_json(self.verification_report_path(queue_id), report)
        return report

    def _hub_ids(self, schedule: DomainDocument, payload: DomainDocument) -> list[str]:
        if payload.get("hub_ids"):
            return [str(item) for item in _list(payload.get("hub_ids"))]
        if payload.get("hub_id"):
            return [str(payload.get("hub_id"))]
        scope = _as_document(schedule.get("scope"))
        ids = [str(item) for item in _list(scope.get("hub_ids")) if str(item)]
        if ids:
            return ids
        runs = self.assurance_store.list_runs()
        ids = sorted({str(run.get("hub_id") or "") for run in runs if run.get("hub_id")})
        return ids or ["hub"]

    def _build_sources(self, queue_id: str, schedule: DomainDocument, hub_ids: list[str], source_paths: DomainDocument) -> tuple[DomainDocument, list[DomainDocument]]:
        raw_rows: list[DomainDocument] = []
        assurance_archive = _first_path(source_paths.get("assurance_archive_path"))
        assurance_report_path = _first_path(source_paths.get("assurance_verification_report_path"))
        hub_package = _first_path(source_paths.get("hub_package_path"))
        hub_report = _first_path(source_paths.get("hub_verification_report_path"))
        external_assurance_report = _read_json_default(assurance_report_path, default={}) if assurance_report_path else {}
        if assurance_archive or assurance_report_path:
            raw_rows.append(_external_row("assurance", assurance_archive, assurance_report_path, "trust-operations-assurance-manifest.json"))
        if hub_package or hub_report:
            raw_rows.append(_external_row("hub", hub_package, hub_report, "trust-operations-hub-manifest.json"))
        run_rows: list[DomainDocument] = []
        for hub_id in hub_ids:
            latest = _latest_run(self.assurance_store.list_runs(hub_id))
            if not latest and external_assurance_report:
                summary = _as_document(external_assurance_report.get("summary"))
                report_hub_id = str(summary.get("hub_id") or "")
                if not report_hub_id or report_hub_id == hub_id:
                    latest = {
                        "hub_id": hub_id,
                        "run_id": summary.get("run_id") or external_assurance_report.get("run_id"),
                        "status": "passed" if external_assurance_report.get("status") == "passed" else external_assurance_report.get("status") or "missing",
                        "readiness": summary.get("readiness") or external_assurance_report.get("readiness") or "",
                        "source_hash": external_assurance_report.get("source_hash"),
                        "created_at": external_assurance_report.get("generated_at"),
                    }
            if not latest:
                run_rows.append({"hub_id": hub_id, "run_id": None, "status": "missing", "readiness": "missing"})
                continue
            run_id = str(latest.get("run_id") or "")
            report = _read_json_default(assurance_report_path or self.assurance_store.verification_report_path(run_id), default={})
            archive_path = assurance_archive or self.assurance_store.archive_zip_path(run_id)
            run_rows.append(
                {
                    "hub_id": hub_id,
                    "run_id": run_id,
                    "status": latest.get("status") or "missing",
                    "readiness": latest.get("readiness") or "",
                    "source_hash": latest.get("source_hash"),
                    "archive_zip_sha256": _sha256(archive_path) if archive_path and archive_path.exists() else report.get("zip_sha256"),
                    "archive_zip_size_bytes": os.stat(_fs_path(archive_path)).st_size if archive_path and archive_path.exists() else report.get("zip_size_bytes"),
                    "archive_manifest_hash": report.get("manifest_hash"),
                    "verification_report_hash": verification_hash(report) if report else None,
                    "verification_status": report.get("status") or "missing",
                    "created_at": latest.get("created_at"),
                    "verified_at": report.get("generated_at") or latest.get("created_at"),
                }
            )
        run_index = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE,
            "schedule_id": schedule.get("schedule_id"),
            "runs": sorted(run_rows, key=lambda row: str(row.get("hub_id") or "")),
        }
        run_index["integrity_hash"] = watch_hash(run_index)
        external_summary = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE,
            "queue_id": queue_id,
            "items": sorted([_public_row(row) for row in raw_rows], key=lambda row: (str(row.get("component_type") or ""), str(row.get("component_id") or ""))),
            "summary": {
                "item_count": len(raw_rows),
                "passed_count": sum(1 for row in raw_rows if row.get("verification_status") == "passed"),
                "failed_count": sum(1 for row in raw_rows if row.get("verification_status") == "failed"),
                "missing_count": sum(1 for row in raw_rows if row.get("verification_status") in {"missing", ""}),
            },
        }
        external_summary["integrity_hash"] = watch_hash(external_summary)
        return run_index, external_summary, raw_rows

    def _build_rows_and_actions(self, queue_id: str, schedule: DomainDocument, hub_ids: list[str], run_index: DomainDocument, external_summary: DomainDocument, now: str) -> tuple[list[DomainDocument], DomainDocument]:
        runs_by_hub = {str(row.get("hub_id") or ""): row for row in run_index.get("runs", []) if isinstance(row, dict)}
        cadence = _as_document(schedule.get("cadence"))
        interval_days = int(cadence.get("interval_days") or 7)
        grace_days = int(cadence.get("grace_days") or 1)
        requirements = _as_document(schedule.get("requirements"))
        require_verified = bool(requirements.get("require_latest_assurance_verified", True))
        rows: list[DomainDocument] = []
        actions: list[DomainDocument] = []
        for hub_id in hub_ids:
            run = runs_by_hub.get(hub_id, {"hub_id": hub_id, "status": "missing", "verification_status": "missing"})
            due_status, next_due_at = _due_status(str(run.get("verified_at") or run.get("created_at") or ""), now, interval_days, grace_days)
            reasons: list[str] = []
            readiness = "clear"
            drift_status = "clear"
            if not run.get("run_id"):
                due_status = "missing"
                readiness = "blocked"
                drift_status = "missing"
                reasons.append("assurance_run_missing")
            if run.get("status") not in {"passed", None}:
                readiness = "blocked"
                drift_status = "failed"
                reasons.append("assurance_run_failed")
            if require_verified and run.get("verification_status") != "passed":
                readiness = "blocked"
                drift_status = "failed" if run.get("verification_status") == "failed" else "missing"
                reasons.append("assurance_verification_not_passed")
            if due_status == "overdue":
                readiness = "blocked"
                reasons.append("assurance_overdue")
            elif due_status == "due" and readiness == "clear":
                readiness = "warning"
                reasons.append("assurance_due")
            row: DomainDocument = {
                "hub_id": hub_id,
                "latest_assurance_run_id": run.get("run_id"),
                "latest_assurance_status": run.get("status") or "missing",
                "latest_assurance_verified": run.get("verification_status") == "passed",
                "last_verified_at": run.get("verified_at"),
                "next_due_at": next_due_at,
                "due_status": due_status,
                "drift_status": drift_status,
                "readiness": readiness,
                "reasons": reasons,
                "action_ids": [],
            }
            for action_type, severity, reason in _actions_for_row(row):
                action_id = f"toaa-{len(actions) + 1:06d}"
                action = _action(action_id, queue_id, hub_id, action_type, severity, reason, row, now)
                actions.append(action)
                row["action_ids"].append(action_id)
            row["integrity_hash"] = watch_hash(row)
            rows.append(row)
        action_pack: DomainDocument = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE,
            "queue_id": queue_id,
            "status": "clear",
            "actions": actions,
            "summary": _action_summary(actions),
            "source": {"external_verification_summary_hash": external_summary.get("integrity_hash")},
        }
        action_summary = _as_document(action_pack.get("summary"))
        action_pack["status"] = "blocked" if action_summary.get("blocking_count") else "warning" if action_summary.get("action_count") else "clear"
        action_pack["integrity_hash"] = watch_hash(action_pack)
        return sorted(rows, key=lambda row: str(row.get("hub_id") or "")), action_pack

    def _ensure_queue_current(self, queue: DomainDocument, payload: DomainDocument, *, now: str | None = None) -> None:
        if queue.get("integrity_hash") != watch_hash(queue):
            raise TrustOperationsAssuranceWatchStateError("Assurance Watch queue integrity failed.")
        stored = _read_json_default(self.source_paths_path(str(queue.get("queue_id") or "")), default={}).get("paths")
        source_paths = _source_paths(payload) if payload else (_as_document(stored))
        schedule = _read_json_default(self.schedule_snapshot_path(str(queue.get("queue_id") or "")), default={})
        hub_ids = [str(row.get("hub_id") or "") for row in queue.get("rows", []) if isinstance(row, dict) and row.get("hub_id")]
        run_index, external_summary, _raw = self._build_sources(str(queue.get("queue_id") or ""), schedule, hub_ids, source_paths)
        refreshed_at = str(queue.get("refreshed_at") or _now())
        rows_for_source, action_pack_for_source = self._build_rows_and_actions(str(queue.get("queue_id") or ""), schedule, hub_ids, run_index, external_summary, refreshed_at)
        source = {
            "schedule_hash": schedule.get("integrity_hash"),
            "assurance_run_index_hash": run_index.get("integrity_hash"),
            "external_verification_summary_hash": external_summary.get("integrity_hash"),
            "drift_action_pack_hash": action_pack_for_source.get("integrity_hash"),
        }
        if stable_hash(source) != queue.get("source_hash"):
            raise TrustOperationsAssuranceWatchStateError("Assurance Watch queue source is stale. Refresh before export.")
        rows, action_pack = self._build_rows_and_actions(str(queue.get("queue_id") or ""), schedule, hub_ids, run_index, external_summary, now or refreshed_at)
        if _queue_summary(rows, action_pack) != queue.get("summary"):
            raise TrustOperationsAssuranceWatchStateError("Assurance Watch queue summary is stale. Refresh before export.")

    def _append_history(self, queue_id: str, payload: DomainDocument) -> None:
        _append_jsonl(self.history_path(queue_id), payload)
