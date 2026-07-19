# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore
from song_agent.domains.delivery.distribution_export import build_distribution_export_package as build_distribution_export_package, build_distribution_package_zip as build_distribution_package_zip
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_export import build_release_export_bundle as build_release_export_bundle, build_release_export_zip as build_release_export_zip
from song_agent.domains.delivery.release_metadata import attach_metadata_export_to_manifest as attach_metadata_export_to_manifest, export_release_metadata_files as export_release_metadata_files, read_release_metadata as read_release_metadata, read_release_metadata_qa as read_release_metadata_qa
from song_agent.domains.delivery.release_metadata_qa import build_release_metadata_qa_report as build_release_metadata_qa_report, release_metadata_qa_summary as release_metadata_qa_summary
from song_agent.domains.trust.release_operations import ReleaseOperationsStore as ReleaseOperationsStore, operations_report_integrity_hash as operations_report_integrity_hash, operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_verifier import release_operations_verification_summary as release_operations_verification_summary, verify_release_operations_package as verify_release_operations_package
from song_agent.domains.delivery.release_qa import build_release_qa_report as build_release_qa_report, release_qa_summary as release_qa_summary
from song_agent.domains.delivery.release_verifier import verification_summary as verification_summary, verify_release_zip as verify_release_zip
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.delivery.submission_evidence import SubmissionEvidenceStore as SubmissionEvidenceStore, submission_evidence_report_summary as submission_evidence_report_summary
from song_agent.domains.delivery.submission_evidence_verifier import submission_evidence_verification_summary as submission_evidence_verification_summary, verify_submission_evidence_package as verify_submission_evidence_package
from song_agent.domains.delivery.submission_export import build_submission_export_bundle as build_submission_export_bundle, build_submission_package_zip as build_submission_package_zip
from song_agent.domains.delivery.submission_qa import build_submission_qa_report as build_submission_qa_report, submission_qa_summary as submission_qa_summary
from song_agent.domains.delivery.submission_verifier import submission_verification_summary as submission_verification_summary, verify_submission_package as verify_submission_package
from song_agent.domains.delivery.submissions import SubmissionStore as SubmissionStore
from song_agent.domains.trust.release_operations_runbook_contracts import EXECUTION_REPORT_HASH_EXCLUDE_KEYS as EXECUTION_REPORT_HASH_EXCLUDE_KEYS, RUNBOOK_BLOCKED_KEYS as RUNBOOK_BLOCKED_KEYS, RUNBOOK_HASH_EXCLUDE_KEYS as RUNBOOK_HASH_EXCLUDE_KEYS, execution_report_integrity_hash as execution_report_integrity_hash, runbook_integrity_hash as runbook_integrity_hash


RUNBOOK_SCHEMA_VERSION = 1
RUNBOOK_EXPORT_SCHEMA_VERSION = 1




AUTO_SAFE_ACTIONS = {
    "release.qa.refresh",
    "metadata.qa.refresh",
    "metadata.export",
    "release.export",
    "release.zip",
    "release.verify",
    "distribution.qa.refresh",
    "distribution.export",
    "distribution.zip",
    "distribution.verify",
    "submission.qa.refresh",
    "submission.export",
    "submission.zip",
    "submission.verify",
    "submission_evidence.report.refresh",
    "submission_evidence.export",
    "submission_evidence.zip",
    "submission_evidence.verify",
    "operations.refresh",
    "operations.export",
    "operations.zip",
    "operations.verify",
}
MANUAL_REQUIRED_PREFIXES = (
    "release.signoff",
    "distribution.signoff",
    "submission.signoff",
    "submission.record",
    "submission_evidence.signoff",
    "submission_evidence.acceptance",
    "rights.",
    "audio.",
    "mastering.",
    "encoded.",
    "format_decision.",
    "release.add_track",
)


from song_agent.domains.trust import v142_ror_readiness as _v142_ror_readiness
from song_agent.domains.trust.v142_ror_readiness import (
    ReleaseOperationsRunbookError,
    ReleaseOperationsRunbookNotFoundError,
    ReleaseOperationsRunbookStateError,
    runbook_integrity_ok,
    execution_report_integrity_ok,
    runbook_summary,
    _runbook_item,
    _risk_for_action,
    _finalize_runbook,
    _execution_report,
    _source_from_report,
    _report_reference,
    _find_item,
    _signed_or_mutation_error,
    _ensure_release_export_mutable,
    _validate_runbook_id,
    _safe_text,
    _write_json,
    _file_record,
    _zip_entries,
    _sha256,
    _ensure_within,
    _write_readme,
)







class ReleaseOperationsRunbookStore:
    def __init__(
        self,
        *,
        operations_store: ReleaseOperationsStore,
        release_store: ReleaseStore | None = None,
        distribution_store: DistributionStore | None = None,
        submission_store: SubmissionStore | None = None,
        submission_evidence_store: SubmissionEvidenceStore | None = None,
    ) -> None:
        self.operations_store = operations_store
        self.release_store = release_store or operations_store.release_store
        self.distribution_store = distribution_store or operations_store.distribution_store
        self.submission_store = submission_store or operations_store.submission_store
        self.submission_evidence_store = submission_evidence_store or operations_store.submission_evidence_store
        self.lock = threading.RLock()

    def runbooks_root(self, release_id: str) -> Path:
        return self.operations_store.operations_dir(release_id) / "runbooks"

    def runbook_dir(self, release_id: str, runbook_id: str) -> Path:
        return self.runbooks_root(release_id) / _validate_runbook_id(runbook_id)

    def runbook_path(self, release_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(release_id, runbook_id) / "runbook.json"

    def events_path(self, release_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(release_id, runbook_id) / "events.jsonl"

    def execution_report_path(self, release_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(release_id, runbook_id) / "execution-report.json"

    def export_dir(self, release_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(release_id, runbook_id) / "runbook-export"

    def zip_path(self, release_id: str, runbook_id: str) -> Path:
        return self.runbook_dir(release_id, runbook_id) / "runbook-export.zip"

    def list_runbooks(self, release_id: str, *, include_archived: bool = False) -> list[DomainDocument]:
        root = self.runbooks_root(release_id)
        rows: list[ImplementationDocument] = []
        for path in root.glob("*/runbook.json") if root.exists() else []:
            try:
                runbook = sanitize_metadata(read_json(path), blocked_keys=RUNBOOK_BLOCKED_KEYS)
            except Exception:
                continue
            if not include_archived and runbook.get("status") == "archived":
                continue
            rows.append(runbook)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def get_runbook(self, release_id: str, runbook_id: str) -> DomainDocument:
        path = self.runbook_path(release_id, runbook_id)
        if not path.exists():
            raise ReleaseOperationsRunbookNotFoundError("Release Operations Runbook does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=RUNBOOK_BLOCKED_KEYS)

    def create_from_operations_report(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            report = self.operations_store.refresh(release_id, now=now)
            if not operations_report_integrity_ok(report):
                raise ReleaseOperationsRunbookStateError("Operations Report integrity failed.")
            runbook_id = self._reserve_runbook_id(release_id)
            runbook_dir = self.runbook_dir(release_id, runbook_id)
            before = report
            policy = {
                "auto_execute_safe_actions": bool(payload.get("auto_execute_safe_actions", True)),
                "include_provider": bool(payload.get("include_provider", False)),
                "allow_signed_mutation": bool(payload.get("allow_signed_mutation", False)),
                "max_actions_per_run": max(1, min(500, int(payload.get("max_actions_per_run", 50) or 50))),
            }
            items = [_runbook_item(action, index=index, source_hash=report.get("source_hash")) for index, action in enumerate(report.get("next_actions", []) if isinstance(report.get("next_actions"), list) else [], start=1)]
            runbook = {
                "schema_version": RUNBOOK_SCHEMA_VERSION,
                "runbook_id": runbook_id,
                "release_id": release_id,
                "name": _safe_text(payload.get("name"), 160) or f"Runbook {now[:10]}",
                "status": "ready" if items else "completed",
                "created_at": now,
                "updated_at": now,
                "created_by": _safe_text(payload.get("created_by"), 120) or "local",
                "source": _source_from_report(report),
                "policy": policy,
                "summary": {},
                "items": items,
                "operations_report_before": _report_reference(before),
            }
            runbook = _finalize_runbook(runbook)
            runbook_dir.mkdir(parents=True, exist_ok=False)
            _write_json(self.runbook_path(release_id, runbook_id), runbook)
            _write_json(runbook_dir / "operations-report-before.json", before)
            _write_json(self.execution_report_path(release_id, runbook_id), _execution_report(runbook, operations_after={}))
            self._append_event(release_id, runbook_id, "created", {"item_count": len(items)}, now=now)
            return runbook

    def refresh_stale_status(self, release_id: str, runbook_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            runbook = self.get_runbook(release_id, runbook_id)
            stale = self._is_stale(runbook)
            if stale and runbook.get("status") not in {"archived", "stale"}:
                runbook["status"] = "stale"
                for item in runbook.get("items", []) if isinstance(runbook.get("items"), list) else []:
                    if isinstance(item, dict) and item.get("status") in {"pending", "failed", "blocked"}:
                        item["status"] = "stale"
                runbook["updated_at"] = now or now_iso()
                runbook = _finalize_runbook(runbook)
                _write_json(self.runbook_path(release_id, runbook_id), runbook)
                self._append_event(release_id, runbook_id, "stale_detected", {"source_hash": runbook.get("source", {}).get("operations_source_hash")}, now=now)
            return {"runbook": runbook, "stale": stale}

    def run_safe_actions(self, release_id: str, runbook_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            runbook = self.get_runbook(release_id, runbook_id)
            if runbook.get("status") == "archived":
                raise ReleaseOperationsRunbookStateError("Archived runbook cannot run.")
            if self._is_stale(runbook):
                self._mark_stale(release_id, runbook, now=now)
                raise ReleaseOperationsRunbookStateError("Release Operations Runbook is stale. Create a new runbook.")
            max_actions = max(1, min(500, int(payload.get("max_actions_per_run") or runbook.get("policy", {}).get("max_actions_per_run") or 50)))
            runbook["status"] = "running"
            runbook["updated_at"] = now
            _write_json(self.runbook_path(release_id, runbook_id), _finalize_runbook(runbook))
            ran = 0
            for item in runbook.get("items", []) if isinstance(runbook.get("items"), list) else []:
                if ran >= max_actions:
                    break
                if not isinstance(item, dict) or item.get("status") not in {"pending", "failed"}:
                    continue
                if item.get("risk") != "auto_safe":
                    if item.get("status") == "pending":
                        item["status"] = "manual_required" if item.get("risk") == "manual_required" else "blocked"
                    continue
                ran += 1
                self._execute_item(release_id, runbook, item, now=now)
            runbook["updated_at"] = now_iso()
            runbook = _finalize_runbook(runbook)
            _write_json(self.runbook_path(release_id, runbook_id), runbook)
            after = self.operations_store.refresh(release_id)
            _write_json(self.runbook_dir(release_id, runbook_id) / "operations-report-after.json", after)
            _write_json(self.execution_report_path(release_id, runbook_id), _execution_report(runbook, operations_after=after))
            self._append_event(release_id, runbook_id, "run_completed", {"executed_count": ran, "status": runbook.get("status")})
            return runbook

    def retry_item(self, release_id: str, runbook_id: str, item_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            runbook = self.get_runbook(release_id, runbook_id)
            item = _find_item(runbook, item_id)
            if item.get("risk") != "auto_safe":
                raise ReleaseOperationsRunbookStateError("Manual required runbook item cannot be retried automatically.")
            if self._is_stale(runbook):
                self._mark_stale(release_id, runbook, now=now)
                raise ReleaseOperationsRunbookStateError("Release Operations Runbook is stale. Create a new runbook.")
            item["retry_count"] = int(item.get("retry_count") or 0) + 1
            item["status"] = "pending"
            self._execute_item(release_id, runbook, item, now=now or now_iso())
            runbook["updated_at"] = now_iso()
            runbook = _finalize_runbook(runbook)
            _write_json(self.runbook_path(release_id, runbook_id), runbook)
            return runbook

    def waive_item(self, release_id: str, runbook_id: str, item_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
        if len(reason) < 8:
            raise ReleaseOperationsRunbookStateError("Waiver reason must be at least 8 characters.")
        with self.lock:
            runbook = self.get_runbook(release_id, runbook_id)
            item = _find_item(runbook, item_id)
            if item.get("risk") == "auto_safe" and item.get("status") not in {"failed", "blocked"}:
                raise ReleaseOperationsRunbookStateError("Only failed or blocked safe items can be waived.")
            item["status"] = "waived"
            item["waiver"] = {"waived_by": _safe_text(payload.get("waived_by"), 120) or "local", "waived_at": now or now_iso(), "reason": reason, "expires_at": payload.get("expires_at")}
            runbook["updated_at"] = now_iso()
            runbook = _finalize_runbook(runbook)
            _write_json(self.runbook_path(release_id, runbook_id), runbook)
            self._append_event(release_id, runbook_id, "item_waived", {"item_id": item_id, "reason": reason}, now=now)
            return runbook

    def archive_runbook(self, release_id: str, runbook_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            runbook = self.get_runbook(release_id, runbook_id)
            runbook["status"] = "archived"
            runbook["updated_at"] = now or now_iso()
            runbook = _finalize_runbook(runbook)
            _write_json(self.runbook_path(release_id, runbook_id), runbook)
            self._append_event(release_id, runbook_id, "archived", {}, now=now)
            return runbook

    def export_runbook(self, release_id: str, runbook_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            runbook = self.get_runbook(release_id, runbook_id)
            stale = self._is_stale(runbook)
            export_dir = self.export_dir(release_id, runbook_id).resolve()
            root = self.runbook_dir(release_id, runbook_id).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            before = read_json(root / "operations-report-before.json") if (root / "operations-report-before.json").exists() else {}
            after = self.operations_store.refresh(release_id, now=now)
            execution = _execution_report(runbook, operations_after=after, stale=stale)
            _write_json(self.execution_report_path(release_id, runbook_id), execution)
            _write_json(export_dir / "runbook.json", runbook)
            _write_json(export_dir / "execution-report.json", execution)
            _write_json(export_dir / "operations-report-before.json", before)
            _write_json(export_dir / "operations-report-after.json", after)
            _write_readme(export_dir, runbook)
            files = [_file_record(export_dir, export_dir / name) for name in ("runbook.json", "execution-report.json", "operations-report-before.json", "operations-report-after.json", "README.txt")]
            manifest = {
                "schema_version": RUNBOOK_EXPORT_SCHEMA_VERSION,
                "tool": {"name": "MusicForge Release Operations Runbook Export", "version": __version__},
                "release_id": release_id,
                "runbook_id": runbook_id,
                "generated_at": now,
                "stale": stale,
                "source_hash": runbook.get("source", {}).get("operations_source_hash"),
                "current_operations_source_hash": after.get("source_hash"),
                "runbook": {"path": "runbook.json", "integrity_hash": runbook.get("integrity_hash"), "runbook_hash": runbook_integrity_hash(runbook)},
                "execution_report": {"path": "execution-report.json", "integrity_hash": execution.get("integrity_hash"), "execution_hash": execution_report_integrity_hash(execution)},
                "operations_before": {"path": "operations-report-before.json", "integrity_hash": before.get("integrity_hash"), "report_hash": operations_report_integrity_hash(before) if isinstance(before, dict) and before else None},
                "operations_after": {"path": "operations-report-after.json", "integrity_hash": after.get("integrity_hash"), "report_hash": operations_report_integrity_hash(after)},
                "summary": runbook.get("summary", {}),
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": {"status": "passed"},
            }
            _write_json(export_dir / "runbook-manifest.json", sanitize_metadata(manifest, blocked_keys=RUNBOOK_BLOCKED_KEYS))
            self._append_event(release_id, runbook_id, "exported", {"stale": stale}, now=now)
            return manifest

    def build_zip(self, release_id: str, runbook_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            export_dir = self.export_dir(release_id, runbook_id).resolve()
            root = self.runbook_dir(release_id, runbook_id).resolve()
            zip_path = self.zip_path(release_id, runbook_id).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "runbook-manifest.json").exists():
                self.export_runbook(release_id, runbook_id, now=now)
            manifest = self.read_export_manifest(release_id, runbook_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            _write_json(export_dir / "runbook-manifest.json", manifest)
            entries = _zip_entries(export_dir)
            tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for resolved, entry in entries:
                        archive.write(resolved, entry)
                tmp_path.replace(zip_path)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise
            return {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}

    def read_export_manifest(self, release_id: str, runbook_id: str) -> DomainDocument:
        path = self.export_dir(release_id, runbook_id) / "runbook-manifest.json"
        if not path.exists():
            raise FileNotFoundError("Release Operations Runbook export has not been generated.")
        return sanitize_metadata(read_json(path), blocked_keys=RUNBOOK_BLOCKED_KEYS)

    def _reserve_runbook_id(self, release_id: str) -> str:
        root = self.runbooks_root(release_id)
        root.mkdir(parents=True, exist_ok=True)
        existing = []
        for child in root.iterdir():
            if child.is_dir() and child.name.startswith("orb-"):
                try:
                    existing.append(int(child.name.split("-")[-1]))
                except ValueError:
                    pass
        return f"orb-{(max(existing) if existing else 0) + 1:06d}"

    def _is_stale(self, runbook: ImplementationDocument) -> bool:
        current = self.operations_store.build_report(str(runbook.get("release_id") or ""), persist=False)
        return str(current.get("source_hash") or "") != str(runbook.get("source", {}).get("operations_source_hash") or "")

    def _mark_stale(self, release_id: str, runbook: ImplementationDocument, *, now: str | None = None) -> None:
        runbook["status"] = "stale"
        for item in runbook.get("items", []) if isinstance(runbook.get("items"), list) else []:
            if isinstance(item, dict) and item.get("status") in {"pending", "failed", "blocked"}:
                item["status"] = "stale"
        runbook["updated_at"] = now or now_iso()
        _write_json(self.runbook_path(release_id, str(runbook.get("runbook_id") or "")), _finalize_runbook(runbook))
        self._append_event(release_id, str(runbook.get("runbook_id") or ""), "stale_detected", {}, now=now)

    def _execute_item(self, release_id: str, runbook: ImplementationDocument, item: ImplementationDocument, *, now: str) -> None:
        item["status"] = "running"
        item["started_at"] = now
        item["attempt"] = int(item.get("attempt") or 0) + 1
        self._append_event(release_id, str(runbook.get("runbook_id")), "item_started", {"item_id": item.get("item_id"), "action_type": item.get("action_type")}, now=now)
        before = self._item_summary(release_id, item)
        try:
            artifact = self._perform_action(release_id, item)
            after = self._item_summary(release_id, item)
            item["status"] = "completed"
            item["completed_at"] = now_iso()
            item["result"] = {"status": "completed", "artifact_summary": artifact, "before_summary": before, "after_summary": after}
            item["error"] = None
            self._append_event(release_id, str(runbook.get("runbook_id")), "item_completed", {"item_id": item.get("item_id"), "action_type": item.get("action_type")})
        except Exception as exc:
            item["status"] = "blocked" if _signed_or_mutation_error(exc) else "failed"
            item["completed_at"] = now_iso()
            item["error"] = sanitize_sensitive_text(str(exc))[:800]
            item["result"] = {"status": item["status"], "before_summary": before}
            self._append_event(release_id, str(runbook.get("runbook_id")), "item_failed", {"item_id": item.get("item_id"), "error": item["error"]})

    def _perform_action(self, release_id: str, item: ImplementationDocument) -> ImplementationDocument:
        action = str(item.get("action_type") or "")
        entity_id = str(item.get("entity_id") or release_id)
        if action == "release.qa.refresh":
            release = self.release_store.get_release(release_id)
            report = self.release_store.write_qa(release_id, build_release_qa_report(release=release, release_store=self.release_store, project_store=self.release_store.project_store, options={}))
            self.release_store.update_qa_summary(release_id, release_qa_summary(report))
            return release_qa_summary(report)
        if action == "metadata.qa.refresh":
            release = self.release_store.get_release(release_id)
            metadata = read_release_metadata(self.release_store, release_id, default={})
            report = build_release_metadata_qa_report(release=release, metadata=metadata)
            from song_agent.domains.delivery.release_metadata import write_release_metadata_qa

            write_release_metadata_qa(self.release_store, release_id, report)
            return release_metadata_qa_summary(report)
        if action == "metadata.export":
            _ensure_release_export_mutable(self.release_store, release_id)
            report = read_release_metadata_qa(self.release_store, release_id, default={})
            manifest = export_release_metadata_files(release_store=self.release_store, release_id=release_id, qa_report=report)
            attach_metadata_export_to_manifest(self.release_store, release_id, manifest)
            return {"status": "exported", "file_count": len(manifest.get("files", [])) if isinstance(manifest.get("files"), list) else 0}
        if action == "release.export":
            release = self.release_store.get_release(release_id)
            _ensure_release_export_mutable(self.release_store, release_id, release=release)
            qa = self.release_store.read_qa(release_id, default={})
            manifest = build_release_export_bundle(release=release, release_store=self.release_store, project_store=self.release_store.project_store, qa_report=qa)
            self.release_store.update_export_summary(release_id, {"status": "exported", "file_count": manifest.get("summary", {}).get("file_count", 0)})
            return {"status": "exported", "file_count": manifest.get("summary", {}).get("file_count", 0)}
        if action == "release.zip":
            _ensure_release_export_mutable(self.release_store, release_id)
            return build_release_export_zip(self.release_store, release_id)
        if action == "release.verify":
            return verification_summary(verify_release_zip(self.release_store.zip_path(release_id)))
        if action.startswith("distribution."):
            target = self.distribution_store.get_target(release_id, entity_id)
            if action == "distribution.qa.refresh":
                from song_agent.domains.delivery.distribution_qa import build_distribution_qa_report, distribution_qa_summary

                report = self.distribution_store.write_qa(release_id, target.target_id, build_distribution_qa_report(store=self.distribution_store, release_id=release_id, target=target))
                self.distribution_store.update_qa_summary(release_id, target.target_id, distribution_qa_summary(report))
                return distribution_qa_summary(report)
            if action == "distribution.export":
                self.distribution_store.ensure_target_mutable(release_id, target)
                qa = self.distribution_store.read_qa(release_id, target.target_id, default={})
                manifest = build_distribution_export_package(store=self.distribution_store, release_id=release_id, target=target, qa_report=qa)
                return {"status": "exported", "package_id": manifest.get("package_id")}
            if action == "distribution.zip":
                self.distribution_store.ensure_target_mutable(release_id, target)
                return build_distribution_package_zip(self.distribution_store, release_id, target)
            if action == "distribution.verify":
                package_id = self.distribution_store.latest_package_id(target)
                if not package_id:
                    raise FileNotFoundError("Distribution export has not been generated.")
                return distribution_verification_summary(verify_distribution_package(self.distribution_store.package_zip_path(release_id, package_id)))
        if action.startswith("submission_evidence."):
            submission_id = entity_id
            if action == "submission_evidence.report.refresh":
                return submission_evidence_report_summary(self.submission_evidence_store.refresh_report(release_id, submission_id))
            if action == "submission_evidence.export":
                manifest = self.submission_evidence_store.export_evidence(release_id, submission_id)
                return {"status": "exported", "file_count": len(manifest.get("files", [])) if isinstance(manifest.get("files"), list) else 0}
            if action == "submission_evidence.zip":
                return self.submission_evidence_store.build_zip(release_id, submission_id)
            if action == "submission_evidence.verify":
                return submission_evidence_verification_summary(verify_submission_evidence_package(self.submission_evidence_store.package_zip_path(release_id, submission_id), require_submitted=True, require_accepted=True))
        if action.startswith("submission."):
            submission = self.submission_store.get_submission(release_id, entity_id)
            if action == "submission.qa.refresh":
                report = self.submission_store.write_qa(release_id, submission.submission_id, build_submission_qa_report(store=self.submission_store, release_id=release_id, submission=submission))
                self.submission_store.update_qa_summary(release_id, submission.submission_id, submission_qa_summary(report))
                return submission_qa_summary(report)
            if action == "submission.export":
                qa = self.submission_store.read_qa(release_id, submission.submission_id, default={})
                manifest = build_submission_export_bundle(store=self.submission_store, release_id=release_id, submission=submission, qa_report=qa)
                return {"status": "exported", "file_count": manifest.get("summary", {}).get("file_count", 0)}
            if action == "submission.zip":
                return build_submission_package_zip(self.submission_store, release_id, submission)
            if action == "submission.verify":
                return submission_verification_summary(verify_submission_package(self.submission_store.package_zip_path(release_id, submission.submission_id)))
        if action == "operations.refresh":
            return self.operations_store.refresh(release_id)
        if action == "operations.export":
            manifest = self.operations_store.export_operations(release_id)
            return {"status": "exported", "file_count": len(manifest.get("files", [])) if isinstance(manifest.get("files"), list) else 0}
        if action == "operations.zip":
            return self.operations_store.build_zip(release_id)
        if action == "operations.verify":
            return release_operations_verification_summary(verify_release_operations_package(self.operations_store.zip_path(release_id)))
        raise ReleaseOperationsRunbookStateError(f"Unsupported runbook action: {action}")

    def _item_summary(self, release_id: str, item: ImplementationDocument) -> ImplementationDocument:
        action = str(item.get("action_type") or "")
        entity_id = str(item.get("entity_id") or release_id)
        try:
            if action.startswith("distribution."):
                target = self.distribution_store.get_target(release_id, entity_id)
                return {"target_id": target.target_id, "status": target.status, "qa": target.latest_qa_summary, "export": target.latest_export_summary, "signoff": target.latest_signoff_summary}
            if action.startswith("submission_evidence."):
                return self.submission_evidence_store.overview(release_id, entity_id).get("summary", {})
            if action.startswith("submission."):
                batch = self.submission_store.get_submission(release_id, entity_id)
                return {"submission_id": batch.submission_id, "status": batch.status, "qa": batch.latest_qa_summary, "export": batch.latest_export_summary, "signoff": batch.latest_signoff_summary}
            if action.startswith("operations."):
                report = self.operations_store.read_report(release_id, default={})
                return {"status": report.get("status"), "current_stage": report.get("current_stage"), "source_hash": report.get("source_hash")}
            release = self.release_store.get_release(release_id)
            return {"release_id": release.release_id, "status": release.status, "qa": release.latest_qa_summary, "export": release.latest_export_summary, "signoff": release.latest_signoff_summary}
        except Exception:
            return {}

    def _append_event(self, release_id: str, runbook_id: str, event_type: str, summary: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.events_path(release_id, runbook_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        if path.exists():
            count = len(path.read_text(encoding="utf-8").splitlines())
        event = sanitize_metadata({"event_id": f"orbe-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "runbook_id": runbook_id, "summary": summary}, blocked_keys=RUNBOOK_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

_v142_ror_readiness.bind_globals(globals())
