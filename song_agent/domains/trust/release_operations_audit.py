from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.trust.release_operations import ReleaseOperationsStore, operations_report_integrity_hash, operations_report_integrity_ok
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore, runbook_integrity_hash, runbook_integrity_ok, runbook_summary
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore, operations_archive_manifest_hash, operations_archive_manifest_integrity_ok, operations_change_request_hash, operations_change_request_integrity_ok, operations_signoff_hash, operations_signoff_integrity_ok, operations_signoff_summary
from song_agent.domains.delivery.releases import ReleaseStore, stable_hash
from song_agent.domains.trust.release_operations_audit_contracts import AUDIT_ENTRY_HASH_EXCLUDE_KEYS, AUDIT_MANIFEST_HASH_EXCLUDE_KEYS, AUDIT_REPORT_HASH_EXCLUDE_KEYS, OPERATIONS_AUDIT_BLOCKED_KEYS, _entry_hash_payload, audit_entry_hash, audit_ledger_hash, audit_ledger_integrity_ok, audit_manifest_integrity_hash, audit_report_integrity_hash


OPERATIONS_AUDIT_SCHEMA_VERSION = 1
OPERATIONS_AUDIT_EXPORT_SCHEMA_VERSION = 1





DOMAIN_PRIORITY = {
    "release": 10,
    "release_export": 20,
    "metadata": 30,
    "audio": 40,
    "rights": 50,
    "format_decision": 60,
    "distribution": 70,
    "submission": 80,
    "submission_evidence": 90,
    "operations_report": 100,
    "operations_runbook": 110,
    "operations_signoff": 120,
    "operations_change_request": 130,
    "operations_archive": 140,
    "operations_audit": 150,
}


class ReleaseOperationsAuditError(ValueError):
    pass


class ReleaseOperationsAuditNotFoundError(ReleaseOperationsAuditError):
    pass


class ReleaseOperationsAuditStateError(ReleaseOperationsAuditError):
    pass


class ReleaseOperationsAuditStore:
    def __init__(
        self,
        *,
        operations_store: ReleaseOperationsStore,
        runbook_store: ReleaseOperationsRunbookStore,
        signoff_store: ReleaseOperationsSignoffStore,
        release_store: ReleaseStore | None = None,
    ) -> None:
        self.operations_store = operations_store
        self.runbook_store = runbook_store
        self.signoff_store = signoff_store
        self.release_store = release_store or operations_store.release_store
        self.lock = threading.RLock()

    def audit_dir(self, release_id: str) -> Path:
        return self.operations_store.operations_dir(release_id) / "audit"

    def report_path(self, release_id: str) -> Path:
        return self.audit_dir(release_id) / "operations-audit-report.json"

    def ledger_path(self, release_id: str) -> Path:
        return self.audit_dir(release_id) / "operations-audit-ledger.jsonl"

    def events_path(self, release_id: str) -> Path:
        return self.audit_dir(release_id) / "operations-audit-events.jsonl"

    def export_dir(self, release_id: str) -> Path:
        return self.audit_dir(release_id) / "audit-export"

    def zip_path(self, release_id: str) -> Path:
        return self.audit_dir(release_id) / "operations-audit.zip"

    def verification_report_path(self, release_id: str) -> Path:
        return self.audit_dir(release_id) / "operations-audit-verification-report.json"

    def read_report(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.report_path(release_id)
        if not path.exists():
            return default if default is not None else {}
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)

    def read_ledger(self, release_id: str) -> list[dict[str, Any]]:
        path = self.ledger_path(release_id)
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
                rows.append(sanitize_metadata(value, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS))
        return rows

    def refresh(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            entries, source = self.build_ledger_entries(release_id)
            ledger_hash = audit_ledger_hash(entries)
            blockers, warnings = self._audit_findings(release_id, entries)
            report = {
                "schema_version": OPERATIONS_AUDIT_SCHEMA_VERSION,
                "release_id": release_id,
                "generated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": "blocked" if blockers else "archivable",
                "source_hash": stable_hash(source),
                "ledger_hash": ledger_hash,
                "summary": {
                    "entry_count": len(entries),
                    "domain_count": len({str(item.get("domain") or "") for item in entries}),
                    "critical_milestone_count": sum(1 for item in entries if item.get("risk") in {"manual_required", "change_control", "external_state"}),
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                    "change_request_count": sum(1 for item in entries if item.get("domain") == "operations_change_request"),
                    "applied_change_request_count": sum(1 for item in entries if item.get("event_type") == "operations_change_request_applied"),
                    "signed_mutation_count": sum(1 for item in entries if item.get("risk") == "signed_mutation"),
                },
                "stage_timeline": _stage_timeline(entries),
                "critical_milestones": _critical_milestones(entries),
                "change_control": _change_control_summary(entries),
                "package_verifiers": _package_verifier_summary(entries),
                "coverage": _coverage(entries),
                "blockers": blockers,
                "warnings": warnings,
            }
            report["integrity_hash"] = audit_report_integrity_hash(report)
            report = sanitize_metadata(report, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)
            root = self.audit_dir(release_id)
            root.mkdir(parents=True, exist_ok=True)
            write_json(self.report_path(release_id), report)
            _write_ledger(self.ledger_path(release_id), entries)
            self._append_event(release_id, "refreshed", {"status": report.get("status"), "entry_count": len(entries)}, now=now)
            return report

    def build_ledger_entries(self, release_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        release = self.release_store.get_release(release_id)
        rows: list[dict[str, Any]] = []
        source: dict[str, Any] = {"release_id": release_id, "sources": []}
        release_dict = release.to_dict()
        rows.append(_entry_seed(release_id, release_dict.get("created_at"), "release", "release_document_current", "local-user", "read_only", "refresh", "release", release_id, release_dict, source_hash=stable_hash(release_dict)))
        source["sources"].append({"type": "release", "hash": stable_hash(release_dict)})
        reset_hash_by_change_request_id = _reset_hash_by_change_request_id(self.signoff_store, release_id)
        for event in self.release_store.read_events(release_id):
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("type") or "unknown")
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            change_request_id = str(payload.get("change_request_id") or "")
            reset_payload_hash = payload.get("payload_hash") or reset_hash_by_change_request_id.get(change_request_id)
            if event_type == "operations_signoff_reset":
                rows.append(
                    _entry_seed(
                        release_id,
                        event.get("at") or event.get("timestamp"),
                        "release",
                        "release_event_operations_signoff_reset",
                        "local-user",
                        "change_control",
                        "reset",
                        "release_event",
                        str(event.get("event_id") or event_type),
                        event,
                        payload_hash=reset_payload_hash,
                        causal_refs=[{"type": "change_request", "id": change_request_id}] if change_request_id else [],
                    )
                )
            else:
                rows.append(_entry_seed(release_id, event.get("at") or event.get("timestamp"), "release", f"release_event_{_slug(event_type)}", "local-user", "read_only", "external_record", "release_event", str(event.get("event_id") or ""), event))

        operations_report = self.operations_store.read_report(release_id, default={})
        if operations_report:
            integrity_ok = operations_report_integrity_ok(operations_report)
            rows.append(
                _entry_seed(
                    release_id,
                    operations_report.get("generated_at"),
                    "operations_report",
                    "operations_report_refreshed",
                    "local-user",
                    "read_only",
                    "refresh",
                    "operations_report",
                    str(operations_report.get("report_id") or "operations-report"),
                    operations_report,
                    source_hash=operations_report.get("source_hash"),
                    integrity_ok=integrity_ok,
                    stale=bool(operations_report.get("stale")),
                )
            )
            source["sources"].append({"type": "operations_report", "hash": operations_report_integrity_hash(operations_report), "source_hash": operations_report.get("source_hash")})
            export_manifest = _read_optional_json(self.operations_store.export_dir(release_id) / "operations-manifest.json")
            if export_manifest:
                rows.append(_entry_seed(release_id, export_manifest.get("generated_at"), "operations_report", "operations_export_created", "local-user", "auto_safe", "export", "operations_export", "operations-manifest", export_manifest, source_hash=export_manifest.get("source_hash")))
            operations_verification = _read_optional_json(self.operations_store.operations_dir(release_id) / "operations-verification-report.json")
            if operations_verification:
                rows.append(_entry_seed(release_id, operations_verification.get("generated_at"), "operations_report", "operations_package_verified", "local-user", "auto_safe", "verify", "operations_verifier", "operations-verification-report", operations_verification, source_hash=operations_report.get("source_hash")))

        latest_runbook = _latest_runbook(self.runbook_store, release_id)
        if latest_runbook:
            rows.append(_entry_seed(release_id, latest_runbook.get("updated_at") or latest_runbook.get("created_at"), "operations_runbook", "operations_runbook_current", latest_runbook.get("created_by"), "auto_safe", "refresh", "runbook", latest_runbook.get("runbook_id"), latest_runbook, source_hash=(latest_runbook.get("source") or {}).get("operations_source_hash"), integrity_ok=runbook_integrity_ok(latest_runbook), stale=latest_runbook.get("status") == "stale"))
            runbook_events_path = self.runbook_store.events_path(release_id, str(latest_runbook.get("runbook_id") or ""))
            for event in _read_jsonl(runbook_events_path):
                rows.append(_entry_seed(release_id, event.get("at"), "operations_runbook", f"operations_runbook_{_slug(event.get('type') or 'event')}", "local-user", "auto_safe", "refresh", "runbook_event", str(event.get("event_id") or ""), event))
            execution = _read_optional_json(self.runbook_store.execution_report_path(release_id, str(latest_runbook.get("runbook_id") or "")))
            if execution:
                rows.append(_entry_seed(release_id, execution.get("generated_at"), "operations_runbook", "operations_runbook_execution_report", "local-user", "auto_safe", "verify", "runbook_execution", latest_runbook.get("runbook_id"), execution))

        signoff = self.signoff_store.read_signoff(release_id, default={})
        if signoff:
            event_type = "operations_signoff_reset" if signoff.get("status") == "reset" else "operations_signoff_signed"
            risk = "change_control" if signoff.get("status") == "reset" else "manual_required"
            rows.append(
                _entry_seed(
                    release_id,
                    signoff.get("reset_at") or signoff.get("signed_at"),
                    "operations_signoff",
                    event_type,
                    signoff.get("signed_by") or "local-user",
                    risk,
                    "reset" if signoff.get("status") == "reset" else "signoff",
                    "operations_signoff",
                    signoff.get("status"),
                    signoff,
                    source_hash=signoff.get("source_hash"),
                    payload_hash=signoff.get("payload_hash") or operations_signoff_hash(signoff),
                    integrity_ok=operations_signoff_integrity_ok(signoff),
                    causal_refs=[{"type": "change_request", "id": signoff.get("change_request_id")}] if signoff.get("status") == "reset" and signoff.get("change_request_id") else [],
                )
            )
        for event in _read_jsonl(self.signoff_store.history_path(release_id)):
            event_type = f"operations_signoff_history_{_slug(event.get('type') or 'event')}"
            summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
            change_request_id = str(summary.get("change_request_id") or "")
            reset_payload_hash = summary.get("payload_hash") or reset_hash_by_change_request_id.get(change_request_id)
            rows.append(
                _entry_seed(
                    release_id,
                    event.get("at"),
                    "operations_signoff",
                    event_type,
                    "local-user",
                    "change_control" if event.get("type") == "reset" else "manual_required",
                    "reset" if event.get("type") == "reset" else "signoff",
                    "operations_signoff_history",
                    str(event.get("event_id") or ""),
                    event,
                    payload_hash=reset_payload_hash if event.get("type") == "reset" else None,
                    causal_refs=[{"type": "change_request", "id": change_request_id}] if change_request_id else [],
                )
            )

        change_requests = self.signoff_store.list_change_requests(release_id)
        for request in sorted(change_requests, key=lambda item: str(item.get("created_at") or "")):
            status = str(request.get("status") or "unknown")
            event_type = f"operations_change_request_{_slug(status)}"
            rows.append(_entry_seed(release_id, request.get("updated_at") or request.get("created_at"), "operations_change_request", event_type, request.get("created_by"), "change_control", "change_request", "change_request", request.get("change_request_id"), request, source_hash=(request.get("source") or {}).get("release_source_hash"), integrity_ok=operations_change_request_integrity_ok(request), causal_refs=[{"type": "operations_signoff_reset", "payload_hash": request.get("applied_signoff_reset_hash")}] if status == "applied" else []))
        for event in _read_jsonl(self.signoff_store.change_request_events_path(release_id)):
            rows.append(_entry_seed(release_id, event.get("at"), "operations_change_request", f"operations_change_request_event_{_slug(event.get('type') or 'event')}", "local-user", "change_control", "change_request", "change_request_event", str(event.get("event_id") or ""), event))

        archive_manifest = _read_optional_json(self.signoff_store.archive_export_dir(release_id) / "operations-archive-manifest.json")
        if archive_manifest:
            rows.append(_entry_seed(release_id, archive_manifest.get("generated_at"), "operations_archive", "operations_archive_exported", "local-user", "auto_safe", "archive", "operations_archive", "operations-archive-manifest", archive_manifest, source_hash=archive_manifest.get("source_hash"), integrity_ok=operations_archive_manifest_integrity_ok(archive_manifest)))
            source["sources"].append({"type": "operations_archive", "hash": operations_archive_manifest_hash(archive_manifest), "source_hash": archive_manifest.get("source_hash")})
        archive_verification = _read_optional_json(self.signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
        if archive_verification:
            rows.append(_entry_seed(release_id, archive_verification.get("generated_at"), "operations_archive", "operations_archive_verified", "local-user", "auto_safe", "verify", "operations_archive_verifier", "operations-archive-verification-report", archive_verification, integrity_ok=archive_verification.get("status") != "failed"))

        if operations_report:
            for domain, item in _verifier_entries_from_operations_report(release_id, operations_report):
                rows.append(item)

        rows = _finalize_entries(rows)
        _bind_change_request_causal_refs(rows)
        source["ledger_input_hash"] = stable_hash([_entry_hash_payload(item) for item in rows])
        return rows, source

    def entries(self, release_id: str, *, domain: str | None = None, risk: str | None = None, event_type: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.read_ledger(release_id)
        if domain:
            rows = [item for item in rows if item.get("domain") == domain]
        if risk:
            rows = [item for item in rows if item.get("risk") == risk]
        if event_type:
            rows = [item for item in rows if item.get("event_type") == event_type]
        return rows[: max(1, min(1000, int(limit or 200)))]

    def graph(self, release_id: str) -> dict[str, Any]:
        rows = self.read_ledger(release_id)
        nodes = []
        edges = []
        for item in rows:
            source_ref = item.get("source_ref") if isinstance(item.get("source_ref"), dict) else {}
            evidence_ref = item.get("evidence_ref") if isinstance(item.get("evidence_ref"), dict) else {}
            node_id = str(source_ref.get("source_id") or item.get("entry_id"))
            nodes.append({"id": node_id, "type": source_ref.get("source_type") or item.get("domain"), "status": "passed" if evidence_ref.get("integrity_ok", True) else "failed", "hash": evidence_ref.get("payload_hash")})
            if item.get("previous_hash"):
                edges.append({"from": str(item.get("previous_hash")), "to": str(item.get("entry_hash")), "type": "hash_chain"})
            for causal in item.get("causal_refs", []) if isinstance(item.get("causal_refs"), list) else []:
                if isinstance(causal, dict):
                    edges.append({"from": str(causal.get("id") or causal.get("payload_hash") or ""), "to": str(item.get("entry_id")), "type": "causal"})
        return sanitize_metadata({"nodes": nodes[:500], "edges": edges[:1000]}, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)

    def export_audit(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            report = self.read_report(release_id, default={}) or self.refresh(release_id, now=now)
            entries = self.read_ledger(release_id)
            if not audit_report_integrity_ok(report):
                raise ReleaseOperationsAuditStateError("Operations Audit Report integrity failed. Refresh audit before export.")
            export_dir = self.export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            ledger_text = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in entries)
            (export_dir / "operations-audit-ledger.jsonl").write_text(ledger_text, encoding="utf-8")
            _write_json(export_dir / "operations-audit-report.json", report)
            _write_json(export_dir / "operations-report-summary.json", _operations_report_summary(self.operations_store.read_report(release_id, default={})))
            _write_json(export_dir / "operations-signoff-summary.json", operations_signoff_summary(self.signoff_store.read_signoff(release_id, default={}), current_report=self.operations_store.build_report(release_id, persist=False)))
            _write_json(export_dir / "latest-runbook-summary.json", runbook_summary(_latest_runbook(self.runbook_store, release_id)) if _latest_runbook(self.runbook_store, release_id) else {"status": "missing"})
            _write_json(export_dir / "change-request-ledger.json", {"change_requests": self.signoff_store.list_change_requests(release_id), "summary": self.signoff_store.change_request_summary(release_id)})
            _write_json(export_dir / "package-verifier-ledger.json", _package_verifier_summary(entries))
            _write_audit_readme(export_dir, report)
            files = [_file_record(export_dir, export_dir / name) for name in ("operations-audit-report.json", "operations-audit-ledger.jsonl", "operations-report-summary.json", "operations-signoff-summary.json", "latest-runbook-summary.json", "change-request-ledger.json", "package-verifier-ledger.json", "README.txt")]
            manifest = {
                "schema_version": OPERATIONS_AUDIT_EXPORT_SCHEMA_VERSION,
                "tool": {"name": "MusicForge Release Operations Audit", "version": __version__},
                "release_id": release_id,
                "generated_at": now,
                "app_version": __version__,
                "source_hash": report.get("source_hash"),
                "ledger_hash": report.get("ledger_hash"),
                "summary": {"status": report.get("status"), "entry_count": len(entries), "blocker_count": report.get("summary", {}).get("blocker_count") if isinstance(report.get("summary"), dict) else 0, "warning_count": report.get("summary", {}).get("warning_count") if isinstance(report.get("summary"), dict) else 0},
                "audit_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash"), "ledger_hash": report.get("ledger_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "entries": entries}),
            }
            manifest["integrity_hash"] = audit_manifest_integrity_hash(manifest)
            _write_json(export_dir / "operations-audit-manifest.json", manifest)
            self._append_event(release_id, "exported", {"status": report.get("status")}, now=now)
            return sanitize_metadata(manifest, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)

    def build_zip(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            export_dir = self.export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            zip_path = self.zip_path(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            _ensure_within(release_dir, zip_path)
            if not (export_dir / "operations-audit-manifest.json").exists():
                self.export_audit(release_id, now=now)
            manifest = read_json(export_dir / "operations-audit-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = audit_manifest_integrity_hash(manifest)
            _write_json(export_dir / "operations-audit-manifest.json", manifest)
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
            return sanitize_metadata({"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)

    def read_export_manifest(self, release_id: str) -> dict[str, Any]:
        path = self.export_dir(release_id) / "operations-audit-manifest.json"
        if not path.exists():
            raise FileNotFoundError("Operations Audit export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)

    def summary(self, release_id: str) -> dict[str, Any]:
        report = self.read_report(release_id, default={})
        if not report:
            return {"status": "missing", "entry_count": 0, "integrity_ok": False}
        return audit_summary(report)

    def _audit_findings(self, release_id: str, entries: list[ImplementationDocument]) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        if not audit_ledger_integrity_ok(entries):
            blockers.append(_blocker("audit_ledger_chain", "Operations Audit ledger hash chain failed."))
        if not any(item.get("event_type") == "operations_report_refreshed" for item in entries):
            warnings.append(_warning("operations_report_missing", "Operations Report is missing from Audit Ledger."))
        signoff = self.signoff_store.read_signoff(release_id, default={})
        if signoff and not any(item.get("event_type") in {"operations_signoff_signed", "operations_signoff_reset"} for item in entries):
            blockers.append(_blocker("operations_signoff_missing", "Operations Signoff exists but is missing from Audit Ledger."))
        if signoff and not operations_signoff_integrity_ok(signoff):
            blockers.append(_blocker("operations_signoff_integrity", "Operations Signoff payload hash failed."))
        if signoff.get("status") == "reset":
            change_request_id = str(signoff.get("change_request_id") or "")
            request = self.signoff_store.get_change_request(release_id, change_request_id) if change_request_id else {}
            if not change_request_id:
                blockers.append(_blocker("operations_reset_change_request_missing", "Operations Signoff reset is missing Change Request id."))
            elif not request or request.get("status") != "applied":
                blockers.append(_blocker("operations_reset_change_request_not_applied", "Operations Signoff reset requires applied Change Request evidence."))
            elif not operations_change_request_integrity_ok(request):
                blockers.append(_blocker("operations_change_request_integrity", "Operations Change Request integrity failed."))
            elif str(request.get("applied_signoff_reset_hash") or "") != str(signoff.get("payload_hash") or ""):
                blockers.append(_blocker("operations_reset_change_request_hash", "Applied Change Request reset hash does not match reset signoff hash."))
        archive_manifest = _read_optional_json(self.signoff_store.archive_export_dir(release_id) / "operations-archive-manifest.json")
        if archive_manifest and not operations_archive_manifest_integrity_ok(archive_manifest):
            blockers.append(_blocker("operations_archive_manifest_integrity", "Operations Archive manifest integrity failed."))
        archive_verification = _read_optional_json(self.signoff_store.operations_dir(release_id) / "operations-archive-verification-report.json")
        if archive_manifest and not archive_verification:
            blockers.append(_blocker("operations_archive_verifier_missing", "Operations Archive export exists but verification report is missing."))
        if archive_verification and archive_verification.get("status") == "failed":
            blockers.append(_blocker("operations_archive_verifier", "Operations Archive verifier failed."))
        report = self.operations_store.read_report(release_id, default={})
        if report and not operations_report_integrity_ok(report):
            blockers.append(_blocker("operations_report_integrity", "Operations Report integrity failed."))
        for request in self.signoff_store.list_change_requests(release_id):
            if not operations_change_request_integrity_ok(request):
                blockers.append(_blocker("operations_change_request_integrity", f"Operations Change Request {request.get('change_request_id')} integrity failed."))
        if _redaction_summary({"entries": entries}).get("status") == "failed":
            blockers.append(_blocker("operations_audit_redaction", "Operations Audit contains sensitive values."))
        return blockers, warnings

    def _append_event(self, release_id: str, event_type: str, summary: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.events_path(release_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"olaevt-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")








def audit_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == audit_report_integrity_hash(data)





def audit_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == audit_manifest_integrity_hash(data)








def audit_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status") or "missing",
            "readiness": report.get("readiness"),
            "entry_count": summary.get("entry_count", 0),
            "ledger_hash": report.get("ledger_hash"),
            "source_hash": report.get("source_hash"),
            "integrity_ok": audit_report_integrity_ok(report),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "change_request_count": summary.get("change_request_count", 0),
            "applied_change_request_count": summary.get("applied_change_request_count", 0),
        },
        blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS,
    )


def _entry_seed(
    release_id: str,
    occurred_at: Any,
    domain: str,
    event_type: str,
    actor: Any,
    risk: str,
    mutation_kind: str,
    source_type: str,
    source_id: Any,
    payload: Any,
    *,
    source_hash: Any = None,
    payload_hash: Any = None,
    integrity_ok: bool = True,
    stale: bool = False,
    causal_refs: list[ImplementationDocument] | None = None,
) -> ImplementationDocument:
    payload_hash = str(payload_hash or stable_hash(payload))
    return {
        "schema_version": OPERATIONS_AUDIT_SCHEMA_VERSION,
        "entry_id": "",
        "release_id": release_id,
        "sequence": 0,
        "occurred_at": _safe_time(occurred_at),
        "domain": domain,
        "event_type": _safe_event_type(event_type),
        "actor": _safe_text(actor, 120) or "unknown",
        "risk": risk,
        "mutation_kind": mutation_kind,
        "source_ref": {"source_type": source_type, "source_id": str(source_id or source_type), "path_hint": _path_hint(source_type), "payload_hash": payload_hash},
        "evidence_ref": {"artifact_type": "json", "artifact_id": str(source_id or source_type), "payload_hash": payload_hash, "source_hash": source_hash, "integrity_ok": bool(integrity_ok), "stale": bool(stale)},
        "causal_refs": causal_refs or [],
        "warnings": [] if occurred_at else [{"check_id": "occurred_at_missing", "message": "Source event time is missing."}],
        "previous_hash": None,
        "entry_hash": "",
    }


def _finalize_entries(rows: list[ImplementationDocument]) -> list[ImplementationDocument]:
    sorted_rows = sorted(rows, key=lambda item: (_safe_time(item.get("occurred_at")), DOMAIN_PRIORITY.get(str(item.get("domain")), 999), str(item.get("event_type") or ""), str((item.get("source_ref") or {}).get("source_id") or ""), str((item.get("source_ref") or {}).get("payload_hash") or "")))
    previous: str | None = None
    result: list[dict[str, Any]] = []
    for index, item in enumerate(sorted_rows, start=1):
        entry = dict(item)
        entry["entry_id"] = f"olae-{index:06d}"
        entry["sequence"] = index
        entry["previous_hash"] = previous
        entry["entry_hash"] = audit_entry_hash(entry)
        previous = entry["entry_hash"]
        result.append(sanitize_metadata(entry, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS))
    return result


def _bind_change_request_causal_refs(entries: list[ImplementationDocument]) -> None:
    reset_event_types = {
        "operations_signoff_reset",
        "operations_signoff_history_reset",
        "release_event_operations_signoff_reset",
    }
    applied_by_id: dict[str, dict[str, Any]] = {}
    applied_by_reset_hash: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.get("event_type") != "operations_change_request_applied":
            continue
        source_ref = entry.get("source_ref") if isinstance(entry.get("source_ref"), dict) else {}
        change_request_id = str(source_ref.get("source_id") or "")
        if change_request_id:
            applied_by_id[change_request_id] = entry
        for ref in entry.get("causal_refs", []) if isinstance(entry.get("causal_refs"), list) else []:
            if isinstance(ref, dict) and ref.get("payload_hash"):
                applied_by_reset_hash[str(ref.get("payload_hash"))] = entry
    changed = False
    for entry in entries:
        if entry.get("event_type") not in reset_event_types:
            continue
        reset_hash = str((entry.get("evidence_ref") or {}).get("payload_hash") or "")
        refs = entry.get("causal_refs") if isinstance(entry.get("causal_refs"), list) else []
        change_request_id = ""
        for ref in refs:
            if isinstance(ref, dict) and ref.get("type") == "change_request" and ref.get("id"):
                change_request_id = str(ref.get("id"))
                break
        applied = applied_by_id.get(change_request_id) or applied_by_reset_hash.get(reset_hash)
        if not applied:
            continue
        entry["causal_refs"] = [
            {
                "type": "change_request",
                "id": change_request_id or (applied.get("source_ref") or {}).get("source_id"),
                "entry_id": applied.get("entry_id"),
                "payload_hash": (applied.get("evidence_ref") or {}).get("payload_hash"),
            }
        ]
        changed = True
    if changed:
        previous: str | None = None
        for entry in entries:
            entry["previous_hash"] = previous
            entry["entry_hash"] = audit_entry_hash(entry)
            previous = entry["entry_hash"]





def _write_ledger(path: Path, entries: list[ImplementationDocument]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in entries), encoding="utf-8")
    return path


def _latest_runbook(runbook_store: ReleaseOperationsRunbookStore, release_id: str) -> ImplementationDocument:
    rows = runbook_store.list_runbooks(release_id, include_archived=True)
    return rows[0] if rows else {}


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)


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
            rows.append(sanitize_metadata(value, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS))
    return rows


def _reset_hash_by_change_request_id(signoff_store: ReleaseOperationsSignoffStore, release_id: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for request in signoff_store.list_change_requests(release_id):
        if not isinstance(request, dict) or request.get("status") != "applied":
            continue
        change_request_id = str(request.get("change_request_id") or "")
        reset_hash = str(request.get("applied_signoff_reset_hash") or "")
        if change_request_id and reset_hash:
            result[change_request_id] = reset_hash
    return result


def _verifier_entries_from_operations_report(release_id: str, report: ImplementationDocument) -> list[tuple[str, ImplementationDocument]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    verifiers = report.get("verifier_summaries") if isinstance(report.get("verifier_summaries"), dict) else {}
    for key, value in verifiers.items():
        if isinstance(value, dict):
            rows.append((str(key), _entry_seed(release_id, report.get("generated_at"), "operations_report", f"package_verifier_{_slug(key)}", "local-user", "auto_safe", "verify", "package_verifier", key, value, source_hash=report.get("source_hash"), integrity_ok=value.get("status") != "failed")))
        elif isinstance(value, list):
            for index, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    rows.append((str(key), _entry_seed(release_id, report.get("generated_at"), "operations_report", f"package_verifier_{_slug(key)}", "local-user", "auto_safe", "verify", "package_verifier", f"{key}-{index}", item, source_hash=report.get("source_hash"), integrity_ok=item.get("status") != "failed")))
    return rows


def _stage_timeline(entries: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [{"entry_id": item.get("entry_id"), "occurred_at": item.get("occurred_at"), "domain": item.get("domain"), "event_type": item.get("event_type"), "risk": item.get("risk")} for item in entries if item.get("domain") in {"operations_report", "operations_runbook", "operations_signoff", "operations_archive"}]


def _critical_milestones(entries: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [{"entry_id": item.get("entry_id"), "event_type": item.get("event_type"), "risk": item.get("risk"), "payload_hash": (item.get("evidence_ref") or {}).get("payload_hash")} for item in entries if item.get("risk") in {"manual_required", "change_control", "external_state"}]


def _change_control_summary(entries: list[ImplementationDocument]) -> ImplementationDocument:
    change_entries = [item for item in entries if item.get("domain") == "operations_change_request"]
    return {"count": len(change_entries), "applied_count": sum(1 for item in change_entries if item.get("event_type") == "operations_change_request_applied"), "entries": change_entries[:50]}


def _package_verifier_summary(entries: list[ImplementationDocument]) -> ImplementationDocument:
    rows = [item for item in entries if str(item.get("event_type") or "").startswith("package_verifier_") or str(item.get("event_type") or "").endswith("_verified")]
    failed = [item for item in rows if (item.get("evidence_ref") or {}).get("integrity_ok") is False]
    return {"count": len(rows), "failed_count": len(failed), "entries": rows[:80]}


def _coverage(entries: list[ImplementationDocument]) -> ImplementationDocument:
    domains = sorted({str(item.get("domain") or "") for item in entries})
    required = ["release", "operations_report", "operations_runbook", "operations_signoff", "operations_archive", "operations_change_request"]
    return {"domains": domains, "missing_required": [item for item in required if item not in domains]}


def _operations_report_summary(report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {"status": report.get("status") or "missing", "current_stage": report.get("current_stage"), "source_hash": report.get("source_hash"), "integrity_hash": report.get("integrity_hash"), "entry_summary": summary}


def _write_audit_readme(export_dir: Path, report: ImplementationDocument) -> None:
    lines = [
        "MusicForge Release Operations Audit Package",
        "",
        f"Release ID: {report.get('release_id')}",
        f"Audit Status: {report.get('status')}",
        f"Ledger Hash: {report.get('ledger_hash') or '-'}",
        "",
        "This package contains summary audit evidence only. It does not include audio, artwork, credentials, or platform account data.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, data: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS))


def _file_record(export_dir: Path, path: Path) -> ImplementationDocument:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
        if entry in seen:
            raise ReleaseOperationsAuditStateError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleaseOperationsAuditStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleaseOperationsAuditStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleaseOperationsAuditStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseOperationsAuditStateError("Refusing to operate outside release operations audit boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS

    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _safe_time(value: Any) -> str:
    text = str(value or "").strip()
    return text or "1970-01-01T00:00:00+00:00"


def _safe_event_type(value: Any) -> str:
    return _slug(str(value or "unknown")) or "unknown"


def _slug(value: Any) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch == "_").strip("_")


def _path_hint(source_type: str) -> str:
    mapping = {
        "operations_report": "operations/operations-report.json",
        "operations_export": "operations/operations-export/operations-manifest.json",
        "operations_signoff": "operations/operations-signoff.json",
        "operations_archive": "operations/archive-export/operations-archive-manifest.json",
        "runbook": "operations/runbooks/<runbook-id>/runbook.json",
        "change_request": "operations/change-requests/<change-request-id>.json",
    }
    return mapping.get(source_type, source_type)


def _blocker(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}
