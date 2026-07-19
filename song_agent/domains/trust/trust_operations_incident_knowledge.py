# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path

import hashlib as hashlib
import json as json
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_hub_incidents import TrustOperationsIncidentStore as TrustOperationsIncidentStore, incident_hash as incident_hash
from song_agent.domains.trust.trust_operations_incident_knowledge_contracts import KNOWLEDGE_EXPORT_ENTRIES as KNOWLEDGE_EXPORT_ENTRIES, TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_KNOWLEDGE_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION as TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE, TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE as TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE, _classify_incident as _classify_incident, knowledge_hash as knowledge_hash, knowledge_manifest_hash as knowledge_manifest_hash












TRUST_OPERATIONS_KNOWLEDGE_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}




from song_agent.domains.trust import v142_toik_readiness as _v142_toik_readiness
from song_agent.domains.trust.v142_toik_readiness import (
    TrustOperationsKnowledgeError,
    TrustOperationsKnowledgeNotFoundError,
    TrustOperationsKnowledgeStateError,
    _knowledge_report_status,
    _knowledge_summary,
    _entries_summary,
    _guards_summary,
    _guard_run_summary,
    _incident_matches_entry,
    _write_readme,
    _file_record,
    _walk_files,
    _zip_entries,
    _write_zip,
    _sha256,
    _read_json,
    _read_json_default,
    _write_json,
    _mkdir,
    _next_id,
    _safe_id,
    _now,
    _sanitize,
    _fs_path,
)







class TrustOperationsIncidentKnowledgeStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations-knowledge",
        *,
        incident_store: TrustOperationsIncidentStore | None = None,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.incident_store = incident_store or TrustOperationsIncidentStore(hub_store=self.hub_store)
        self.lock = threading.RLock()

    def hub_dir(self, hub_id: str) -> Path:
        return self.root / _safe_id(hub_id)

    def base_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "knowledge-base.json"

    def entries_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "entries"

    def entry_path(self, hub_id: str, entry_id: str) -> Path:
        return self.entries_dir(hub_id) / (_safe_id(entry_id) + ".json")

    def guards_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "guards"

    def guard_path(self, hub_id: str, guard_id: str) -> Path:
        return self.guards_dir(hub_id) / (_safe_id(guard_id) + ".json")

    def guard_run_path(self, hub_id: str, guard_id: str) -> Path:
        return self.guards_dir(hub_id) / _safe_id(guard_id) / "guard-run-report.json"

    def recurrence_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "recurrence-report.json"

    def source_snapshot_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "knowledge-source-snapshot.json"

    def export_dir(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "exports" / "current"

    def zip_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "trust-operations-incident-knowledge.zip"

    def verification_report_path(self, hub_id: str) -> Path:
        return self.hub_dir(hub_id) / "trust-operations-incident-knowledge-verification-report.json"

    def refresh(self, hub_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            source = self._source_summary(hub_id, payload)
            incidents = self.incident_store.list_incidents(hub_id, include_archived=True)
            existing_by_source = {str(item.get("source", {}).get("incident_hash") or ""): item for item in self.list_entries(hub_id, include_hidden=True)}
            entry_ids: list[str] = []
            created_count = 0
            updated_count = 0
            skipped_count = 0
            for incident in incidents:
                if not self._incident_eligible(incident):
                    skipped_count += 1
                    continue
                incident_source_hash = str(incident.get("integrity_hash") or "")
                existing = existing_by_source.get(incident_source_hash)
                entry_id = str(existing.get("entry_id") or _next_id(self.entries_dir(hub_id), "ike")) if existing else _next_id(self.entries_dir(hub_id), "ike")
                entry = self._entry_from_incident(hub_id, entry_id, incident, source, existing, now)
                _write_json(self.entry_path(hub_id, entry_id), entry)
                entry_ids.append(entry_id)
                if existing:
                    updated_count += 1
                else:
                    created_count += 1
            guards = self.list_guards(hub_id, include_archived=True)
            recurrence = self.refresh_recurrence(hub_id, now=now, write=False)
            base = {
                "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE,
                "hub_id": hub_id,
                "knowledge_base_id": "toh-kb-000001",
                "status": "ready" if source.get("incident_verification_status") == "passed" else "blocked",
                "created_at": _read_json_default(self.base_path(hub_id), {}).get("created_at") or now,
                "updated_at": now,
                "source": source,
                "entry_ids": sorted(set(entry_ids)),
                "guard_ids": sorted(str(item.get("guard_id") or "") for item in guards if item.get("status") != "archived"),
                "summary": _knowledge_summary(self.list_entries(hub_id), guards, recurrence),
            }
            base["integrity_hash"] = knowledge_hash(base)
            _write_json(self.base_path(hub_id), base)
            _write_json(self.source_snapshot_path(hub_id), source)
            if payload.get("refresh_recurrence", True):
                self.refresh_recurrence(hub_id, now=now)
            return _sanitize({"knowledge_base": base, "created_count": created_count, "updated_count": updated_count, "skipped_count": skipped_count, "entries": self.list_entries(hub_id)})

    def read_base(self, hub_id: str) -> DomainDocument:
        if not self.base_path(hub_id).exists():
            raise TrustOperationsKnowledgeNotFoundError("Trust Operations Incident Knowledge Base not found.")
        return _read_json(self.base_path(hub_id))

    def list_entries(self, hub_id: str, *, include_hidden: bool = False) -> list[DomainDocument]:
        root = self.entries_dir(hub_id)
        if not root.exists():
            return []
        rows = []
        for path in sorted(root.glob("*.json")):
            entry = _read_json(path)
            if entry.get("status") == "hidden" and not include_hidden:
                continue
            rows.append(_sanitize(entry))
        return rows

    def read_entry(self, hub_id: str, entry_id: str) -> DomainDocument:
        path = self.entry_path(hub_id, entry_id)
        if not path.exists():
            raise TrustOperationsKnowledgeNotFoundError("Trust Operations Knowledge Entry not found.")
        return _read_json(path)

    def hide_entry(self, hub_id: str, entry_id: str, *, now: str | None = None) -> DomainDocument:
        return self._set_entry_status(hub_id, entry_id, "hidden", now=now)

    def unhide_entry(self, hub_id: str, entry_id: str, *, now: str | None = None) -> DomainDocument:
        return self._set_entry_status(hub_id, entry_id, "active", now=now)

    def list_guards(self, hub_id: str, *, include_archived: bool = False) -> list[DomainDocument]:
        root = self.guards_dir(hub_id)
        if not root.exists():
            return []
        rows = []
        for path in sorted(root.glob("rg-*.json")):
            guard = _read_json(path)
            if guard.get("status") == "archived" and not include_archived:
                continue
            rows.append(_sanitize(guard))
        return rows

    def read_guard(self, hub_id: str, guard_id: str) -> DomainDocument:
        path = self.guard_path(hub_id, guard_id)
        if not path.exists():
            raise TrustOperationsKnowledgeNotFoundError("Trust Operations Regression Guard not found.")
        return _read_json(path)

    def create_guard(self, hub_id: str, entry_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            entry = self.read_entry(hub_id, entry_id)
            if entry.get("status") == "hidden":
                raise TrustOperationsKnowledgeStateError("Hidden Knowledge Entry cannot create regression guard.")
            recommended = _as_document(entry.get("recommended_guard"))
            guard_type = str(payload.get("guard_type") or recommended.get("guard_type") or "manual_required")
            if guard_type not in {"external_report_coverage", "external_report_binding", "redaction_regression", "zip_safety_regression", "stale_guard_regression", "manual_required"}:
                raise TrustOperationsKnowledgeStateError("Unsupported regression guard type.")
            existing = next((item for item in self.list_guards(hub_id, include_archived=True) if item.get("source", {}).get("knowledge_entry_hash") == entry.get("integrity_hash") and item.get("guard_type") == guard_type and item.get("status") != "archived"), None)
            if existing:
                return _sanitize(existing)
            guard_id = _safe_id(str(payload.get("guard_id") or _next_id(self.guards_dir(hub_id), "rg")))
            guard = {
                "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
                "hub_id": hub_id,
                "guard_id": guard_id,
                "entry_id": entry_id,
                "guard_type": guard_type,
                "status": "active" if guard_type != "manual_required" else "manual_required",
                "created_at": now,
                "updated_at": now,
                "title": sanitize_sensitive_text(str(payload.get("title") or recommended.get("title") or f"Regression guard for {entry_id}")[:200]),
                "scope": {
                    "component_type": entry.get("component_type"),
                    "component_id": entry.get("component_id"),
                    "failure_mode": entry.get("failure_mode"),
                    "category": entry.get("category"),
                },
                "policy": {
                    "require_passed_external_report": guard_type in {"external_report_coverage", "external_report_binding"},
                    "require_no_sensitive_text": guard_type == "redaction_regression",
                    "manual_required": guard_type == "manual_required",
                },
                "source": {
                    "knowledge_entry_hash": entry.get("integrity_hash"),
                    "incident_hash": entry.get("source", {}).get("incident_hash"),
                    "source_hash": entry.get("source_hash"),
                },
            }
            guard["integrity_hash"] = knowledge_hash(guard)
            _write_json(self.guard_path(hub_id, guard_id), guard)
            self._refresh_base_summary(hub_id, now=now)
            return _sanitize(guard)

    def run_guard(self, hub_id: str, guard_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            guard = self.read_guard(hub_id, guard_id)
            checks = self._guard_checks(hub_id, guard)
            status = "manual_required" if guard.get("guard_type") == "manual_required" else ("passed" if all(item.get("status") == "passed" for item in checks) else "failed")
            run: ImplementationDocument = {
                "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
                "hub_id": hub_id,
                "guard_id": guard_id,
                "guard_run_id": "grr-000001",
                "status": status,
                "run_at": now,
                "source": {
                    "guard_hash": guard.get("integrity_hash"),
                    "knowledge_entry_hash": guard.get("source", {}).get("knowledge_entry_hash"),
                },
                "checks": checks,
            }
            run["integrity_hash"] = knowledge_hash(run)
            guard["status"] = status if status != "passed" else "active"
            guard["last_run"] = {"status": status, "run_at": now, "guard_run_hash": run["integrity_hash"], "guard_hash_before_run": _as_document(run.get("source")).get("guard_hash")}
            guard["updated_at"] = now
            guard["integrity_hash"] = knowledge_hash(guard)
            _write_json(self.guard_path(hub_id, guard_id), guard)
            _write_json(self.guard_run_path(hub_id, guard_id), run)
            self._refresh_base_summary(hub_id, now=now)
            return _sanitize(run)

    def run_all_guards(self, hub_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            runs = []
            for guard in self.list_guards(hub_id):
                if guard.get("status") == "archived":
                    continue
                runs.append(self.run_guard(hub_id, str(guard.get("guard_id") or ""), now=now))
            summary = _guard_run_summary(runs)
            return _sanitize({"hub_id": hub_id, "runs": runs, "summary": summary})

    def refresh_recurrence(self, hub_id: str, *, now: str | None = None, write: bool = True) -> DomainDocument:
        now = now or _now()
        entries = self.list_entries(hub_id, include_hidden=False)
        open_incidents = [item for item in self.incident_store.list_incidents(hub_id, include_archived=False) if item.get("status") not in {"closed", "archived"}]
        matches: list[ImplementationDocument] = []
        for entry in entries:
            for incident in open_incidents:
                if _incident_matches_entry(incident, entry):
                    matches.append({"entry_id": entry.get("entry_id"), "incident_id": incident.get("incident_id"), "failure_mode": entry.get("failure_mode"), "severity": incident.get("severity")})
        report = {
            "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE,
            "hub_id": hub_id,
            "generated_at": now,
            "status": "failed" if matches else "passed",
            "summary": {"recurrence_count": len(matches), "open_incident_count": len(open_incidents)},
            "matches": matches,
            "source": {"entry_count": len(entries), "open_incident_count": len(open_incidents), "incident_board_hash": _read_json_default(self.incident_store.board_path(hub_id), {}).get("integrity_hash")},
        }
        report["integrity_hash"] = knowledge_hash(report)
        if write:
            _write_json(self.recurrence_path(hub_id), report)
            self._refresh_base_summary(hub_id, now=now)
        return _sanitize(report)

    def export_knowledge(self, hub_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            base = self.read_base(hub_id)
            self._assert_source_current(hub_id, base)
            entries = self.list_entries(hub_id, include_hidden=True)
            guards = self.list_guards(hub_id, include_archived=True)
            runs = self._latest_guard_runs(hub_id, guards)
            recurrence = _read_json_default(self.recurrence_path(hub_id), default=self.refresh_recurrence(hub_id, now=now, write=False))
            source = _read_json_default(self.source_snapshot_path(hub_id), default=_as_document(base.get("source")))
            export_dir = self.export_dir(hub_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            entries_doc = {"schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE, "entries": entries, "summary": _entries_summary(entries)}
            entries_doc["integrity_hash"] = knowledge_hash(entries_doc)
            guards_doc = {"schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE, "guards": guards, "summary": _guards_summary(guards)}
            guards_doc["integrity_hash"] = knowledge_hash(guards_doc)
            runs_doc = {"schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE, "runs": runs, "summary": _guard_run_summary(runs)}
            runs_doc["integrity_hash"] = knowledge_hash(runs_doc)
            source_doc = {"schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE, **source}
            source_doc["integrity_hash"] = knowledge_hash(source_doc)
            report = {
                "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE,
                "hub_id": hub_id,
                "generated_at": now,
                "status": _knowledge_report_status(base, guards_doc, runs_doc, recurrence),
                "source": {
                    "knowledge_base_hash": base.get("integrity_hash"),
                    "entries_hash": entries_doc.get("integrity_hash"),
                    "guards_hash": guards_doc.get("integrity_hash"),
                    "guard_run_summary_hash": runs_doc.get("integrity_hash"),
                    "recurrence_hash": recurrence.get("integrity_hash"),
                    "source_summary_hash": source_doc.get("integrity_hash"),
                },
                "summary": _knowledge_summary(entries, guards, recurrence, runs),
            }
            report["integrity_hash"] = knowledge_hash(report)
            _write_json(export_dir / "knowledge-base.json", base)
            _write_json(export_dir / "knowledge-report.json", report)
            _write_json(export_dir / "entries.json", entries_doc)
            _write_json(export_dir / "regression-guards.json", guards_doc)
            _write_json(export_dir / "guard-run-summary.json", runs_doc)
            _write_json(export_dir / "recurrence-report.json", recurrence)
            _write_json(export_dir / "source-summary.json", source_doc)
            _write_readme(export_dir)
            manifest = {
                "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Incident Knowledge", "version": __version__},
                "hub_id": hub_id,
                "generated_at": now,
                "source_hash": base.get("source", {}).get("source_hash"),
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-knowledge-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "integrity": {
                    "knowledge_base_hash": base.get("integrity_hash"),
                    "knowledge_report_hash": report.get("integrity_hash"),
                    "entries_hash": entries_doc.get("integrity_hash"),
                    "guards_hash": guards_doc.get("integrity_hash"),
                    "guard_run_summary_hash": runs_doc.get("integrity_hash"),
                    "recurrence_hash": recurrence.get("integrity_hash"),
                    "source_summary_hash": source_doc.get("integrity_hash"),
                },
            }
            manifest["integrity_hash"] = knowledge_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-knowledge-manifest.json", manifest)
            return _sanitize(manifest)

    def build_zip(self, hub_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or _now()
            export_dir = self.export_dir(hub_id)
            manifest_path = export_dir / "trust-operations-knowledge-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsKnowledgeStateError("Trust Operations Knowledge export is missing.")
            base = self.read_base(hub_id)
            if manifest.get("integrity", {}).get("knowledge_base_hash") != base.get("integrity_hash"):
                raise TrustOperationsKnowledgeStateError("Trust Operations Knowledge export is stale.")
            self._assert_source_current(hub_id, base)
            zip_path = self.zip_path(hub_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = knowledge_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            return {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "hub_id": hub_id}

    def verify_zip(self, hub_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.trust_operations_incident_knowledge_verifier import verify_trust_operations_incident_knowledge_package

        payload = payload or {}
        report = verify_trust_operations_incident_knowledge_package(
            self.zip_path(hub_id),
            strict=bool(payload.get("strict", False)),
            require_guards_passed=bool(payload.get("require_guards_passed", False)),
            require_no_open_recurrence=bool(payload.get("require_no_open_recurrence", False)),
            incident_board_package_path=payload.get("incident_board_package_path") or self.incident_store.zip_path(hub_id),
            incident_board_verification_report_path=payload.get("incident_board_verification_report_path"),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
        )
        _write_json(self.verification_report_path(hub_id), report)
        return report

    def _set_entry_status(self, hub_id: str, entry_id: str, status: str, *, now: str | None) -> ImplementationDocument:
        with self.lock:
            now = now or _now()
            entry = self.read_entry(hub_id, entry_id)
            entry["status"] = status
            entry["updated_at"] = now
            entry["integrity_hash"] = knowledge_hash(entry)
            _write_json(self.entry_path(hub_id, entry_id), entry)
            self._refresh_base_summary(hub_id, now=now)
            return _sanitize(entry)

    def _source_summary(self, hub_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        incident_report = _read_json_default(_as_path(payload.get("incident_board_verification_report_path")) if payload.get("incident_board_verification_report_path") else self.incident_store.verification_report_path(hub_id), default={})
        hub_report = _read_json_default(_as_path(payload.get("hub_verification_report_path")) if payload.get("hub_verification_report_path") else self._hub_verification_path_from_incident(hub_id, incident_report), default={})
        board = _read_json_default(self.incident_store.board_path(hub_id), default={})
        source = {
            "hub_id": hub_id,
            "incident_board_hash": board.get("integrity_hash"),
            "incident_verification_report_hash": verification_hash(incident_report) if incident_report else None,
            "incident_verification_status": incident_report.get("status") if incident_report else None,
            "incident_zip_sha256": incident_report.get("zip_sha256") if incident_report else None,
            "incident_manifest_hash": incident_report.get("manifest_hash") if incident_report else None,
            "hub_report_hash": incident_report.get("hub_report_hash") or hub_report.get("source_hash"),
            "hub_verification_report_hash": verification_hash(hub_report) if hub_report else incident_report.get("hub_verification_report_hash"),
            "hub_verification_status": hub_report.get("status") if hub_report else None,
        }
        source["source_hash"] = stable_hash(source)
        return source

    def _hub_verification_path_from_incident(self, hub_id: str, incident_report: ImplementationDocument) -> Path:
        hub_report_hash = str(incident_report.get("hub_verification_report_hash") or "")
        current = _read_json_default(self.hub_store.current_report_path(hub_id), default={})
        report_id = str(current.get("report_id") or "")
        candidate = self.hub_store.verification_report_path(hub_id, report_id) if report_id else Path()
        if candidate and candidate.exists():
            value = _read_json_default(candidate, default={})
            if not hub_report_hash or verification_hash(value) == hub_report_hash:
                return candidate
        return candidate

    def _incident_eligible(self, incident: ImplementationDocument) -> bool:
        if incident.get("status") != "closed" or incident.get("stale"):
            return False
        closeout = _read_json_default(self.incident_store.closeout_path(str(incident.get("hub_id") or ""), str(incident.get("incident_id") or "")), default={})
        return closeout.get("status") == "passed" and closeout.get("integrity_hash") == incident_hash(closeout)

    def _entry_from_incident(self, hub_id: str, entry_id: str, incident: ImplementationDocument, source: ImplementationDocument, existing: ImplementationDocument | None, now: str) -> ImplementationDocument:
        detected = _as_document(incident.get("detected_from"))
        closeout = _read_json_default(self.incident_store.closeout_path(hub_id, str(incident.get("incident_id") or "")), default={})
        classification = _classify_incident(incident)
        status = str(existing.get("status") or "active") if existing else "active"
        if status not in {"active", "hidden"}:
            status = "active"
        entry = {
            "schema_version": TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION,
            "hub_id": hub_id,
            "entry_id": entry_id,
            "status": status,
            "incident_id": incident.get("incident_id"),
            "title": sanitize_sensitive_text(str(incident.get("title") or "Trust Operations incident")[:200]),
            "category": incident.get("category"),
            "severity": incident.get("severity"),
            "component_type": detected.get("component_type"),
            "component_id": detected.get("component_id"),
            "failure_mode": classification["failure_mode"],
            "root_cause": classification["root_cause"],
            "preventive_pattern": classification["preventive_pattern"],
            "lesson": sanitize_sensitive_text(str(closeout.get("reason") or incident.get("description") or "")[:500]),
            "recommended_guard": {
                "guard_type": classification["guard_type"],
                "title": classification["guard_title"],
                "reason": classification["guard_reason"],
            },
            "source": {
                "incident_hash": incident.get("integrity_hash"),
                "closeout_hash": closeout.get("integrity_hash"),
                "incident_verification_report_hash": source.get("incident_verification_report_hash"),
                "hub_verification_report_hash": source.get("hub_verification_report_hash"),
                "source_fingerprint": detected.get("source_fingerprint"),
            },
            "created_at": (existing or {}).get("created_at") or now,
            "updated_at": now,
        }
        entry["source_hash"] = stable_hash(entry["source"])
        entry["integrity_hash"] = knowledge_hash(entry)
        return entry

    def _guard_checks(self, hub_id: str, guard: ImplementationDocument) -> list[ImplementationDocument]:
        guard_type = str(guard.get("guard_type") or "manual_required")
        if guard_type == "manual_required":
            return [{"check_id": "guard_manual_required", "status": "manual_required", "severity": "manual", "message": "Manual regression guard requires human execution."}]
        scope = _as_document(guard.get("scope"))
        component_type = str(scope.get("component_type") or "")
        current_report_id = str(_read_json_default(self.hub_store.current_report_path(hub_id), default={}).get("report_id") or "")
        docs: dict[str, ImplementationDocument] = {}
        try:
            docs = self.hub_store._read_report_docs(hub_id, current_report_id) if current_report_id else {}
            if docs:
                self.hub_store._assert_report_docs_current(docs)
        except Exception:
            docs = {}
        evidence_rows = []
        delivery_doc = _as_document(docs.get("delivery_evidence_index"))
        for row in delivery_doc.get("evidence", []) if isinstance(delivery_doc.get("evidence"), list) else []:
            if isinstance(row, dict) and (not component_type or row.get("component_type") == component_type):
                evidence_rows.append(row)
        if guard_type in {"external_report_coverage", "external_report_binding"}:
            expected_count = len(evidence_rows)
            passed_count = sum(1 for row in evidence_rows if row.get("status") == "passed" and row.get("verification_report_hash"))
            return [
                {"check_id": "hub_source_current", "status": "passed" if docs else "failed", "severity": "blocking", "message": "Current Hub report is readable and current." if docs else "Current Hub report is missing or stale."},
                {"check_id": "external_report_coverage", "status": "passed" if expected_count and passed_count == expected_count else "failed", "severity": "blocking", "message": f"{passed_count}/{expected_count} {component_type or 'delivery'} evidence rows have passed external reports."},
            ]
        if guard_type == "redaction_regression":
            blockers = docs.get("blocker_register", {}).get("blockers", []) if isinstance(docs.get("blocker_register"), dict) else []
            redaction_blockers = [item for item in blockers if isinstance(item, dict) and "redaction" in str(item).lower()]
            return [{"check_id": "redaction_regression", "status": "passed" if not redaction_blockers else "failed", "severity": "blocking", "message": "No redaction blockers found." if not redaction_blockers else "Redaction blockers remain."}]
        if guard_type == "zip_safety_regression":
            blockers = docs.get("blocker_register", {}).get("blockers", []) if isinstance(docs.get("blocker_register"), dict) else []
            zip_blockers = [item for item in blockers if isinstance(item, dict) and any(marker in str(item).lower() for marker in ("zip", "duplicate", "path", "backslash"))]
            return [{"check_id": "zip_safety_regression", "status": "passed" if not zip_blockers else "failed", "severity": "blocking", "message": "No ZIP safety blockers found." if not zip_blockers else "ZIP safety blockers remain."}]
        return [{"check_id": "generic_regression_guard", "status": "passed" if docs else "failed", "severity": "blocking", "message": "Generic guard source is current." if docs else "Generic guard source is missing."}]

    def _latest_guard_runs(self, hub_id: str, guards: list[ImplementationDocument]) -> list[ImplementationDocument]:
        rows = []
        for guard in guards:
            path = self.guard_run_path(hub_id, str(guard.get("guard_id") or ""))
            if path.exists():
                rows.append(_read_json(path))
        return rows

    def _assert_source_current(self, hub_id: str, base: ImplementationDocument) -> None:
        current = self._source_summary(hub_id, {})
        expected = _as_document(base.get("source"))
        for key in ("incident_verification_report_hash", "incident_zip_sha256", "incident_manifest_hash", "hub_verification_report_hash"):
            if expected.get(key) != current.get(key):
                raise TrustOperationsKnowledgeStateError("Trust Operations Knowledge source is stale. Refresh before export.")

    def _refresh_base_summary(self, hub_id: str, *, now: str) -> None:
        if not self.base_path(hub_id).exists():
            return
        base = self.read_base(hub_id)
        base["summary"] = _knowledge_summary(self.list_entries(hub_id), self.list_guards(hub_id), _read_json_default(self.recurrence_path(hub_id), default={}), self._latest_guard_runs(hub_id, self.list_guards(hub_id)))
        base["updated_at"] = now
        base["guard_ids"] = sorted(str(item.get("guard_id") or "") for item in self.list_guards(hub_id) if item.get("status") != "archived")
        base["integrity_hash"] = knowledge_hash(base)
        _write_json(self.base_path(hub_id), base)

_v142_toik_readiness.bind_globals(globals())
