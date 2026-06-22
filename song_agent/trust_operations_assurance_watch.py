from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.public_trust_center_publication_monitoring import verification_hash
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
from song_agent.trust_operations_hub import TrustOperationsHubStore


TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION = 1
TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE = "musicforge_trust_operations_assurance_schedule"
TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_queue"
TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_assurance_run_index"
TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE = "musicforge_trust_operations_assurance_drift_action_pack"
TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_external_summary"
TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_manifest"
TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}
TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}

ASSURANCE_WATCH_ARCHIVE_ENTRIES = {
    "README.txt",
    "trust-operations-assurance-watch-manifest.json",
    "watch-queue.json",
    "schedule-snapshot.json",
    "assurance-run-index.json",
    "drift-action-pack.json",
    "external-verification-summary.json",
    "watch-history.jsonl",
}


class TrustOperationsAssuranceWatchError(ValueError):
    pass


class TrustOperationsAssuranceWatchNotFoundError(TrustOperationsAssuranceWatchError):
    pass


class TrustOperationsAssuranceWatchStateError(TrustOperationsAssuranceWatchError):
    pass


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

    def ensure_default_schedule(self) -> dict[str, Any]:
        return self.read_schedule("default")

    def read_schedule(self, schedule_id: str = "default") -> dict[str, Any]:
        path = self.schedule_path(schedule_id)
        if not path.exists():
            if schedule_id != "default":
                raise TrustOperationsAssuranceWatchNotFoundError(f"Assurance Watch schedule not found: {schedule_id}")
            return self.write_schedule(_default_schedule())
        return _read_json_required(path, "Assurance Watch schedule cannot be read.")

    def write_schedule(self, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def list_queues(self, schedule_id: str | None = None) -> list[dict[str, Any]]:
        if not self.queues_dir().exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(self.queues_dir().glob("*/watch-queue.json")):
            queue = _read_json_default(path, default={})
            if not queue:
                continue
            if schedule_id and queue.get("schedule_id") != schedule_id:
                continue
            rows.append(_sanitize(queue))
        return rows

    def read_queue(self, queue_id: str) -> dict[str, Any]:
        queue = _read_json_default(self.queue_path(queue_id), default={})
        if not queue:
            raise TrustOperationsAssuranceWatchNotFoundError(f"Assurance Watch queue not found: {queue_id}")
        return _sanitize(queue)

    def summary(self, queue_id: str) -> dict[str, Any]:
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
        payload: dict[str, Any] | None = None,
        *,
        schedule_id: str = "default",
        now: str | None = None,
    ) -> dict[str, Any]:
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
            queue["status"] = _queue_status(queue["summary"])
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

    def export_watch(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def build_watch_zip(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
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

    def verify_watch_zip(self, queue_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.trust_operations_assurance_watch_verifier import verify_trust_operations_assurance_watch_package

        payload = payload or {}
        stored = _read_json_default(self.source_paths_path(queue_id), default={}).get("paths")
        source_paths = _source_paths(payload) if payload else (stored if isinstance(stored, dict) else {})
        report = verify_trust_operations_assurance_watch_package(
            self.watch_zip_path(queue_id),
            strict=bool(payload.get("strict", False)),
            require_clear=bool(payload.get("require_clear", True)),
            require_current=bool(payload.get("require_current", True)),
            **_verifier_kwargs_from_source_paths(source_paths),
        )
        _write_json(self.verification_report_path(queue_id), report)
        return report

    def _hub_ids(self, schedule: dict[str, Any], payload: dict[str, Any]) -> list[str]:
        if payload.get("hub_ids"):
            return [str(item) for item in _list(payload.get("hub_ids"))]
        if payload.get("hub_id"):
            return [str(payload.get("hub_id"))]
        scope = schedule.get("scope") if isinstance(schedule.get("scope"), dict) else {}
        ids = [str(item) for item in _list(scope.get("hub_ids")) if str(item)]
        if ids:
            return ids
        runs = self.assurance_store.list_runs()
        ids = sorted({str(run.get("hub_id") or "") for run in runs if run.get("hub_id")})
        return ids or ["hub"]

    def _build_sources(self, queue_id: str, schedule: dict[str, Any], hub_ids: list[str], source_paths: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        raw_rows: list[dict[str, Any]] = []
        assurance_archive = _first_path(source_paths.get("assurance_archive_path"))
        assurance_report_path = _first_path(source_paths.get("assurance_verification_report_path"))
        hub_package = _first_path(source_paths.get("hub_package_path"))
        hub_report = _first_path(source_paths.get("hub_verification_report_path"))
        external_assurance_report = _read_json_default(assurance_report_path, default={}) if assurance_report_path else {}
        if assurance_archive or assurance_report_path:
            raw_rows.append(_external_row("assurance", assurance_archive, assurance_report_path, "trust-operations-assurance-manifest.json"))
        if hub_package or hub_report:
            raw_rows.append(_external_row("hub", hub_package, hub_report, "trust-operations-hub-manifest.json"))
        run_rows: list[dict[str, Any]] = []
        for hub_id in hub_ids:
            latest = _latest_run(self.assurance_store.list_runs(hub_id))
            if not latest and external_assurance_report:
                summary = external_assurance_report.get("summary") if isinstance(external_assurance_report.get("summary"), dict) else {}
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

    def _build_rows_and_actions(self, queue_id: str, schedule: dict[str, Any], hub_ids: list[str], run_index: dict[str, Any], external_summary: dict[str, Any], now: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        runs_by_hub = {str(row.get("hub_id") or ""): row for row in run_index.get("runs", []) if isinstance(row, dict)}
        cadence = schedule.get("cadence") if isinstance(schedule.get("cadence"), dict) else {}
        interval_days = int(cadence.get("interval_days") or 7)
        grace_days = int(cadence.get("grace_days") or 1)
        requirements = schedule.get("requirements") if isinstance(schedule.get("requirements"), dict) else {}
        require_verified = bool(requirements.get("require_latest_assurance_verified", True))
        rows: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
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
            row = {
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
        action_pack = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE,
            "queue_id": queue_id,
            "status": "clear",
            "actions": actions,
            "summary": _action_summary(actions),
            "source": {"external_verification_summary_hash": external_summary.get("integrity_hash")},
        }
        action_pack["status"] = "blocked" if action_pack["summary"]["blocking_count"] else "warning" if action_pack["summary"]["action_count"] else "clear"
        action_pack["integrity_hash"] = watch_hash(action_pack)
        return sorted(rows, key=lambda row: str(row.get("hub_id") or "")), action_pack

    def _ensure_queue_current(self, queue: dict[str, Any], payload: dict[str, Any], *, now: str | None = None) -> None:
        if queue.get("integrity_hash") != watch_hash(queue):
            raise TrustOperationsAssuranceWatchStateError("Assurance Watch queue integrity failed.")
        stored = _read_json_default(self.source_paths_path(str(queue.get("queue_id") or "")), default={}).get("paths")
        source_paths = _source_paths(payload) if payload else (stored if isinstance(stored, dict) else {})
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

    def _append_history(self, queue_id: str, payload: dict[str, Any]) -> None:
        _append_jsonl(self.history_path(queue_id), payload)


def watch_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS})


def watch_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})


def _default_schedule(now: str | None = None) -> dict[str, Any]:
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


def _external_row(component_type: str, archive_path: Path | None, report_path: Path | None, manifest_entry: str) -> dict[str, Any]:
    report = _read_json_default(report_path, default={}) if report_path else {}
    manifest = _read_zip_json_optional(archive_path, manifest_entry) if archive_path and manifest_entry else {}
    zip_sha = _sha256(archive_path) if archive_path and archive_path.exists() else report.get("zip_sha256")
    zip_size = os.stat(_fs_path(archive_path)).st_size if archive_path and archive_path.exists() else report.get("zip_size_bytes")
    manifest_hash = manifest.get("integrity_hash") or report.get("manifest_hash")
    status = str(report.get("status") or "missing")
    component_id = str((report.get("summary") if isinstance(report.get("summary"), dict) else {}).get("run_id") or report.get("run_id") or component_type)
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
        "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {},
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


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not str(key).startswith("_")}


def _action(action_id: str, queue_id: str, hub_id: str, action_type: str, severity: str, reason: str, row: dict[str, Any], now: str) -> dict[str, Any]:
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


def _actions_for_row(row: dict[str, Any]) -> list[tuple[str, str, str]]:
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


def _queue_summary(rows: list[dict[str, Any]], action_pack: dict[str, Any]) -> dict[str, Any]:
    actions_summary = action_pack.get("summary") if isinstance(action_pack.get("summary"), dict) else {}
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


def _queue_status(summary: dict[str, Any]) -> str:
    if int(summary.get("failed_count") or 0) or int(summary.get("overdue_count") or 0) or int(summary.get("blocking_action_count") or 0):
        return "blocked"
    if int(summary.get("due_count") or 0) or int(summary.get("manual_action_count") or 0):
        return "warning"
    return "clear"


def _action_summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "action_count": len(actions),
        "blocking_count": sum(1 for action in actions if action.get("severity") in {"critical", "high"}),
        "manual_required_count": sum(1 for action in actions if action.get("manual_required")),
        "safe_auto_count": sum(1 for action in actions if action.get("safe_to_auto_run")),
    }


def _manifest(queue: dict[str, Any], export_dir: Path, now: str) -> dict[str, Any]:
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


def _manifest_files(export_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def _latest_run(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not runs:
        return None
    return sorted(runs, key=lambda run: str(run.get("created_at") or run.get("updated_at") or run.get("run_id") or ""))[-1]


def _source_paths(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "assurance_archive_path": [str(path) for path in _paths(payload.get("assurance_archive_path") or payload.get("assurance_archive"))],
        "assurance_verification_report_path": [str(path) for path in _paths(payload.get("assurance_verification_report_path") or payload.get("assurance_verification_report"))],
        "hub_package_path": [str(path) for path in _paths(payload.get("hub_package_path") or payload.get("hub_package"))],
        "hub_verification_report_path": [str(path) for path in _paths(payload.get("hub_verification_report_path") or payload.get("hub_verification_report"))],
    }


def _verifier_kwargs_from_source_paths(source_paths: dict[str, Any]) -> dict[str, Any]:
    return {
        "assurance_archive_path": _first_path(source_paths.get("assurance_archive_path")),
        "assurance_verification_report_path": _first_path(source_paths.get("assurance_verification_report_path")),
        "hub_package_path": _first_path(source_paths.get("hub_package_path")),
        "hub_verification_report_path": _first_path(source_paths.get("hub_verification_report_path")),
    }


def _paths(value: Any) -> list[Path]:
    if value is None or value == "":
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, (list, tuple)):
        return [Path(item) for item in value if item]
    return []


def _first_path(value: Any) -> Path | None:
    values = _paths(value)
    return values[0] if values else None


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _read_json_required(path: Path, message: str) -> dict[str, Any]:
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TrustOperationsAssuranceWatchStateError(message) from exc


def _read_json_default(path: Path | None, *, default: dict[str, Any]) -> dict[str, Any]:
    try:
        if path is None or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _read_zip_json_optional(zip_path: Path | None, entry: str) -> dict[str, Any]:
    if not zip_path:
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    _mkdir(path.parent)
    return write_json(path, _sanitize(payload))


def _write_internal_json(path: Path, payload: dict[str, Any]) -> Path:
    _mkdir(path.parent)
    return write_json(path, payload)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
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


def _deep_update(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _clone(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _fs_path(path: Path) -> str:
    return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS)


def _sanitize_text(text: str) -> str:
    return sanitize_sensitive_text(text)
