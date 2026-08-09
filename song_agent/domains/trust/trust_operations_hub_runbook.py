from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_text

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStateError as TrustOperationsHubStateError, TrustOperationsHubStore as TrustOperationsHubStore, hub_hash as hub_hash
from song_agent.domains.trust.trust_operations_hub_runbook_contracts import RUNBOOK_EXPORT_ENTRIES as RUNBOOK_EXPORT_ENTRIES, TRUST_OPERATIONS_RUNBOOK_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_RUNBOOK_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_RUNBOOK_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_RUNBOOK_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_RUNBOOK_PACKAGE_TYPE as TRUST_OPERATIONS_RUNBOOK_PACKAGE_TYPE, TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE as TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE, TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION as TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION, runbook_hash as runbook_hash






TRUST_OPERATIONS_RUNBOOK_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}




SAFE_ACTIONS = {"hub.export", "hub.zip", "hub.verify"}


class TrustOperationsHubRunbookError(ValueError):
    pass


class TrustOperationsHubRunbookNotFoundError(TrustOperationsHubRunbookError):
    pass


class TrustOperationsHubRunbookStateError(TrustOperationsHubRunbookError):
    pass


class TrustOperationsHubRunbookStore:
    def __init__(self, hub_store: TrustOperationsHubStore | None = None, root: Path | str = Path(".musicforge") / "trust-operations-runbooks") -> None:
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.root = Path(root).resolve()
        self.lock = threading.RLock()

    def runbooks_dir(self, hub_id: str) -> Path:
        return self.root / "hubs" / _safe_id(hub_id) / "runbooks"

    def runbook_dir(self, hub_id: str, runbook_id: str) -> Path:
        return self.runbooks_dir(hub_id) / _safe_id(runbook_id)

    def runbook_path(self, hub_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(hub_id, runbook_id) / "runbook.json"

    def result_path(self, hub_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(hub_id, runbook_id) / "runbook-result.json"

    def events_path(self, hub_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(hub_id, runbook_id) / "runbook-events.jsonl"

    def source_paths_path(self, hub_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(hub_id, runbook_id) / "source-paths.json"

    def export_dir(self, hub_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(hub_id, runbook_id) / "export"

    def zip_path(self, hub_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(hub_id, runbook_id) / "trust-operations-hub-runbook.zip"

    def create_runbook(self, hub_id: str, report_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            if self.hub_store._signoff_state(hub_id)["status"] == "signed":
                raise TrustOperationsHubRunbookStateError("Signed Trust Operations Hub cannot create a new runbook. Reset signoff with an approved change request first.")
            docs = self.hub_store._read_report_docs(hub_id, report_id)
            self.hub_store._assert_report_docs_current(docs)
            source_paths = self.hub_store._read_source_paths(hub_id, report_id)
            self.hub_store._assert_external_sources_current(docs, source_paths)
            runbook_id = _safe_id(str(payload.get("runbook_id") or _next_id(self.runbooks_dir(hub_id), "trust-hub-runbook")))
            actions = _safe_actions(hub_id, report_id)
            actions.extend(_manual_actions(docs))
            runbook = {
                "schema_version": TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_RUNBOOK_PACKAGE_TYPE,
                "hub_id": hub_id,
                "report_id": report_id,
                "runbook_id": runbook_id,
                "created_at": now,
                "status": "pending",
                "source": _source_from_docs(docs),
                "actions": actions,
                "summary": _action_summary(actions),
            }
            runbook["integrity_hash"] = runbook_hash(runbook)
            result = _empty_result(hub_id, report_id, runbook_id, _as_text(runbook["integrity_hash"]), now)
            _write_json(self.runbook_path(hub_id, runbook_id), runbook)
            _write_json(self.result_path(hub_id, runbook_id), result)
            write_json(self.source_paths_path(hub_id, runbook_id), source_paths)
            self._write_event(hub_id, runbook_id, "runbook_created", {"runbook_hash": runbook["integrity_hash"]}, now=now)
            return _sanitize(runbook)

    def read_runbook(self, hub_id: str, runbook_id: str) -> dict[str, Any]:
        path = self.runbook_path(hub_id, runbook_id)
        if not path.exists():
            raise TrustOperationsHubRunbookNotFoundError("Trust Operations Hub Runbook not found.")
        return read_json(path)

    def run_safe_actions(self, hub_id: str, runbook_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            if self.hub_store._signoff_state(hub_id)["status"] == "signed":
                raise TrustOperationsHubRunbookStateError("Signed Trust Operations Hub cannot run automated actions. Reset signoff with an approved change request first.")
            runbook = self.read_runbook(hub_id, runbook_id)
            self._assert_runbook_current(hub_id, runbook)
            events = _read_jsonl(self.events_path(hub_id, runbook_id))
            item_results: list[dict[str, Any]] = []
            for action in runbook.get("actions", []) if isinstance(runbook.get("actions"), list) else []:
                if not isinstance(action, dict):
                    continue
                action_type = str(action.get("action_type") or "")
                if action_type not in SAFE_ACTIONS:
                    item_results.append({"action_id": action.get("action_id"), "action_type": action_type, "status": "manual_required", "reason": "Manual-only action was not executed."})
                    continue
                try:
                    if action_type == "hub.export":
                        self.hub_store.export_report(hub_id, str(runbook.get("report_id") or ""))
                    elif action_type == "hub.zip":
                        self.hub_store.build_zip(hub_id, str(runbook.get("report_id") or ""))
                    elif action_type == "hub.verify":
                        source_paths = read_json(self.source_paths_path(hub_id, runbook_id)) if self.source_paths_path(hub_id, runbook_id).exists() else {}
                        verify_payload = {key[:-1] if key.endswith("s") else key: (value[0] if isinstance(value, list) and value else value) for key, value in source_paths.items()}
                        verify_payload.update({"strict": True, "require_current": True})
                        self.hub_store.verify_zip(hub_id, str(runbook.get("report_id") or ""), verify_payload)
                    status = "completed"
                    reason = "Safe action completed."
                except (TrustOperationsHubStateError, OSError, ValueError) as exc:
                    status = "blocked"
                    reason = str(exc)
                item_results.append({"action_id": action.get("action_id"), "action_type": action_type, "status": status, "reason": reason})
                events.append(_event("runbook_action_" + status, {"action_id": action.get("action_id"), "action_type": action_type, "reason": reason}, previous=events[-1] if events else None, now=now))
            result = {
                "schema_version": TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE,
                "hub_id": hub_id,
                "report_id": runbook.get("report_id"),
                "runbook_id": runbook_id,
                "run_at": now,
                "status": "completed_with_manual_actions" if any(item.get("status") == "manual_required" for item in item_results) else "completed",
                "source": {"runbook_hash": runbook.get("integrity_hash")},
                "results": item_results,
                "summary": _result_summary(item_results),
            }
            if any(item.get("status") == "blocked" for item in item_results):
                result["status"] = "blocked"
            result["integrity_hash"] = runbook_hash(result)
            _write_json(self.result_path(hub_id, runbook_id), result)
            _write_jsonl(self.events_path(hub_id, runbook_id), events)
            return _sanitize(result)

    def export_runbook(self, hub_id: str, runbook_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            runbook = self.read_runbook(hub_id, runbook_id)
            self._assert_runbook_current(hub_id, runbook)
            result = read_json(self.result_path(hub_id, runbook_id)) if self.result_path(hub_id, runbook_id).exists() else _empty_result(hub_id, str(runbook.get("report_id") or ""), runbook_id, str(runbook.get("integrity_hash") or ""), now)
            export_dir = self.export_dir(hub_id, runbook_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir / "checksum")
            _write_json(export_dir / "runbook.json", runbook)
            _write_json(export_dir / "runbook-result.json", result)
            events = _read_jsonl(self.events_path(hub_id, runbook_id))
            (export_dir / "runbook-events.jsonl").write_text("\n".join(json.dumps(_sanitize(event), ensure_ascii=False, sort_keys=True) for event in events) + ("\n" if events else ""), encoding="utf-8")
            _write_readme(export_dir)
            checksum = _checksum_json(export_dir)
            _write_json(export_dir / "checksum" / "SHA256SUMS.json", checksum)
            _write_sha256sums(export_dir, checksum)
            manifest = {
                "schema_version": TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_RUNBOOK_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Hub Runbook", "version": __version__},
                "hub_id": hub_id,
                "report_id": runbook.get("report_id"),
                "runbook_id": runbook_id,
                "generated_at": now,
                "source": {"runbook_hash": runbook.get("integrity_hash"), "result_hash": result.get("integrity_hash"), "event_chain_hash": events[-1].get("event_hash") if events else None},
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-hub-runbook-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = runbook_hash(manifest)
            _write_json(export_dir / "trust-operations-hub-runbook-manifest.json", manifest)
            return _sanitize(manifest)

    def build_zip(self, hub_id: str, runbook_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            export_dir = self.export_dir(hub_id, runbook_id)
            manifest_path = export_dir / "trust-operations-hub-runbook-manifest.json"
            manifest = read_json(manifest_path) if manifest_path.exists() else {}
            if not manifest:
                raise TrustOperationsHubRunbookStateError("Trust Operations Hub Runbook export is missing.")
            runbook = self.read_runbook(hub_id, runbook_id)
            self._assert_runbook_current(hub_id, runbook)
            if manifest.get("source", {}).get("runbook_hash") != runbook.get("integrity_hash"):
                raise TrustOperationsHubRunbookStateError("Trust Operations Hub Runbook export is stale.")
            zip_path = self.zip_path(hub_id, runbook_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = runbook_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            return {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "runbook_id": runbook_id}

    def _assert_runbook_current(self, hub_id: str, runbook: ImplementationDocument) -> None:
        if runbook.get("integrity_hash") != runbook_hash(runbook):
            raise TrustOperationsHubRunbookStateError("Trust Operations Hub Runbook integrity failed.")
        report_id = str(runbook.get("report_id") or "")
        docs = self.hub_store._read_report_docs(hub_id, report_id)
        self.hub_store._assert_report_docs_current(docs)
        source = _source_from_docs(docs)
        if source != runbook.get("source"):
            raise TrustOperationsHubRunbookStateError("Trust Operations Hub Runbook source is stale. Refresh Hub report and create a new runbook.")
        self.hub_store._assert_external_sources_current(docs, self.hub_store._read_source_paths(hub_id, report_id))

    def _write_event(self, hub_id: str, runbook_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> None:
        events = _read_jsonl(self.events_path(hub_id, runbook_id))
        events.append(_event(event_type, payload, previous=events[-1] if events else None, now=now))
        _write_jsonl(self.events_path(hub_id, runbook_id), events)





def _safe_actions(hub_id: str, report_id: str) -> list[ImplementationDocument]:
    return [
        {"action_id": "hub-safe-001", "action_type": "hub.export", "status": "pending", "allowed_automation": True, "component_id": hub_id, "report_id": report_id},
        {"action_id": "hub-safe-002", "action_type": "hub.zip", "status": "pending", "allowed_automation": True, "component_id": hub_id, "report_id": report_id},
        {"action_id": "hub-safe-003", "action_type": "hub.verify", "status": "pending", "allowed_automation": True, "component_id": hub_id, "report_id": report_id},
    ]


def _manual_actions(docs: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    actions: list[dict[str, Any]] = []
    for key in ("manual_action_queue", "delivery_manual_action_queue"):
        for action in docs[key].get("actions", []) if isinstance(docs[key].get("actions"), list) else []:
            if not isinstance(action, dict):
                continue
            actions.append({**action, "status": "manual_required", "allowed_automation": False})
    return actions


def _source_from_docs(docs: dict[str, ImplementationDocument]) -> ImplementationDocument:
    return {
        "hub_report_hash": docs["hub_report"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness_matrix"].get("integrity_hash"),
        "delivery_readiness_matrix_hash": docs["delivery_readiness_matrix"].get("integrity_hash"),
        "blocker_register_hash": docs["blocker_register"].get("integrity_hash"),
        "delivery_blocker_register_hash": docs["delivery_blocker_register"].get("integrity_hash"),
        "manual_action_queue_hash": docs["manual_action_queue"].get("integrity_hash"),
        "delivery_manual_action_queue_hash": docs["delivery_manual_action_queue"].get("integrity_hash"),
        "evidence_binding_index_hash": docs["evidence_binding_index"].get("integrity_hash"),
        "delivery_evidence_index_hash": docs["delivery_evidence_index"].get("integrity_hash"),
    }


def _action_summary(actions: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "action_count": len(actions),
        "safe_action_count": sum(1 for action in actions if action.get("action_type") in SAFE_ACTIONS and action.get("allowed_automation") is True),
        "manual_required_count": sum(1 for action in actions if action.get("status") == "manual_required"),
    }


def _result_summary(results: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "result_count": len(results),
        "completed_count": sum(1 for item in results if item.get("status") == "completed"),
        "blocked_count": sum(1 for item in results if item.get("status") == "blocked"),
        "manual_required_count": sum(1 for item in results if item.get("status") == "manual_required"),
    }


def _empty_result(hub_id: str, report_id: str, runbook_id: str, runbook_hash_value: str, now: str) -> ImplementationDocument:
    result = {
        "schema_version": TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION,
        "package_type": TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE,
        "hub_id": hub_id,
        "report_id": report_id,
        "runbook_id": runbook_id,
        "run_at": now,
        "status": "pending",
        "source": {"runbook_hash": runbook_hash_value},
        "results": [],
        "summary": _result_summary([]),
    }
    result["integrity_hash"] = runbook_hash(result)
    return result


def _event(event_type: str, payload: ImplementationDocument, *, previous: ImplementationDocument | None, now: str) -> ImplementationDocument:
    event = {"event_type": event_type, "created_at": now, "payload": sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_RUNBOOK_BLOCKED_KEYS), "previous_event_hash": previous.get("event_hash") if previous else None}
    event["event_hash"] = stable_hash(event)
    return event


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:100] or "item"


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: list[ImplementationDocument]) -> None:
    _mkdir(path.parent)
    path.write_text("\n".join(json.dumps(_sanitize(row), ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    return write_json(path, _sanitize(payload))


def _checksum_json(export_dir: Path) -> ImplementationDocument:
    rows = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.relative_to(export_dir).as_posix() not in {"checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt", "trust-operations-hub-runbook-manifest.json"}]
    data = {"schema_version": TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION, "files": rows}
    data["integrity_hash"] = runbook_hash(data)
    return data


def _write_sha256sums(export_dir: Path, checksum_json: ImplementationDocument) -> None:
    lines = [f"{item.get('sha256')}  {item.get('path')}" for item in checksum_json.get("files", []) if isinstance(item, dict)]
    (export_dir / "checksum" / "SHA256SUMS.txt").write_text(sanitize_sensitive_text("\n".join(lines) + "\n"), encoding="utf-8")


def _write_readme(export_dir: Path) -> None:
    (export_dir / "README.txt").write_text("MusicForge Trust Operations Hub Runbook\n\nThis package contains safe operations runbook actions and execution evidence.\n", encoding="utf-8")


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    root = root.resolve()
    for dirpath, _dirnames, filenames in os.walk(_fs_path(root)):
        current = _from_fs_path(str(dirpath))
        for filename in filenames:
            path = current / filename
            if os.path.isfile(_fs_path(path)) and not os.path.islink(_fs_path(path)):
                rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(root).as_posix())


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _write_zip(zip_path: Path, root: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.tmp")
    _mkdir(zip_path.parent)
    if tmp_path.exists():
        tmp_path.unlink()
    with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)
    tmp_path.replace(zip_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value


def _from_fs_path(value: str) -> Path:
    if os.name == "nt" and value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if os.name == "nt" and value.startswith("\\\\?\\"):
        return Path(value[4:])
    return Path(value)


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_RUNBOOK_BLOCKED_KEYS)


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)
