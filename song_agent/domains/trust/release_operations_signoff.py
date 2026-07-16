from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_operations import OPERATIONS_BLOCKED_KEYS as OPERATIONS_BLOCKED_KEYS, ReleaseOperationsStore as ReleaseOperationsStore, operations_report_integrity_hash as operations_report_integrity_hash, operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore as ReleaseOperationsRunbookStore, runbook_integrity_hash as runbook_integrity_hash, runbook_integrity_ok as runbook_integrity_ok, runbook_summary as runbook_summary
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.release_operations_signoff_contracts import OPERATIONS_ARCHIVE_HASH_EXCLUDE_KEYS as OPERATIONS_ARCHIVE_HASH_EXCLUDE_KEYS, OPERATIONS_CHANGE_REQUEST_HASH_EXCLUDE_KEYS as OPERATIONS_CHANGE_REQUEST_HASH_EXCLUDE_KEYS, OPERATIONS_SIGNOFF_BLOCKED_KEYS as OPERATIONS_SIGNOFF_BLOCKED_KEYS, OPERATIONS_SIGNOFF_HASH_EXCLUDE_KEYS as OPERATIONS_SIGNOFF_HASH_EXCLUDE_KEYS, operations_archive_manifest_hash as operations_archive_manifest_hash, operations_change_request_hash as operations_change_request_hash, operations_change_request_integrity_ok as operations_change_request_integrity_ok, operations_signoff_hash as operations_signoff_hash


OPERATIONS_SIGNOFF_SCHEMA_VERSION = 1
OPERATIONS_ARCHIVE_SCHEMA_VERSION = 1
OPERATIONS_CHANGE_REQUEST_SCHEMA_VERSION = 1






class ReleaseOperationsSignoffError(ValueError):
    pass


class ReleaseOperationsSignoffNotFoundError(ReleaseOperationsSignoffError):
    pass


class ReleaseOperationsSignoffStateError(ReleaseOperationsSignoffError):
    pass


class ReleaseOperationsSignoffStore:
    def __init__(
        self,
        *,
        operations_store: ReleaseOperationsStore,
        runbook_store: ReleaseOperationsRunbookStore,
        release_store: ReleaseStore | None = None,
    ) -> None:
        self.operations_store = operations_store
        self.runbook_store = runbook_store
        self.release_store = release_store or operations_store.release_store
        self.lock = threading.RLock()

    def operations_dir(self, release_id: str) -> Path:
        return self.operations_store.operations_dir(release_id)

    def signoff_path(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "operations-signoff.json"

    def history_path(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "operations-signoff-history.jsonl"

    def change_requests_root(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "change-requests"

    def change_request_path(self, release_id: str, change_request_id: str) -> Path:
        return self.change_requests_root(release_id) / f"{_validate_change_request_id(change_request_id)}.json"

    def change_request_events_path(self, release_id: str) -> Path:
        return self.change_requests_root(release_id) / "ocr-events.jsonl"

    def archive_export_dir(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "archive-export"

    def archive_zip_path(self, release_id: str) -> Path:
        return self.operations_dir(release_id) / "operations-archive.zip"

    def read_signoff(self, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.signoff_path(release_id)
        if not path.exists():
            return default if default is not None else {}
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

    def get_signoff(self, release_id: str) -> dict[str, Any]:
        signoff = self.read_signoff(release_id, default={})
        if not signoff:
            raise ReleaseOperationsSignoffNotFoundError("Release Operations Signoff does not exist.")
        return signoff

    def signoff_summary(self, release_id: str, *, signoff: dict[str, Any] | None = None) -> dict[str, Any]:
        signoff = signoff if signoff is not None else self.read_signoff(release_id, default={})
        return operations_signoff_summary(signoff, current_report=self.operations_store.build_report(release_id, persist=False) if signoff else None)

    def gate(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        now = now or now_iso()
        report = self.operations_store.read_report(release_id, default={}) or self.operations_store.refresh(release_id, now=now)
        current = self.operations_store.build_report(release_id, persist=False, now=now)
        runbook = _latest_runbook(self.runbook_store, release_id)
        package_ledger = self.package_ledger(release_id, current_report=current)
        verifier_summary = _verifier_summary_from_report(current)
        change_summary = self.change_request_summary(release_id)
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        force = bool(payload.get("force", False))
        override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "").strip())
        report_stale = str(report.get("source_hash") or "") != str(current.get("source_hash") or "")
        report_integrity_ok = operations_report_integrity_ok(report)
        current_integrity_ok = operations_report_integrity_ok(current)
        redaction_ok = current.get("redaction_summary", {}).get("status") != "failed"

        _maybe_block(blockers, "operations_report_integrity", not report_integrity_ok or not current_integrity_ok, "Operations Report integrity failed. Refresh Operations before signoff.")
        _maybe_block(blockers, "operations_report_stale", report_stale, "Operations Report is stale. Refresh Operations before signoff.")
        _maybe_block(blockers, "operations_redaction", not redaction_ok, "Operations Report redaction scan failed.")
        _maybe_block(blockers, "operations_accepted_stage", current.get("current_stage") != "accepted", "Operations current_stage must be accepted before Operations Signoff.")

        summary = current.get("summary") if isinstance(current.get("summary"), dict) else {}
        blocker_count = int(summary.get("blocker_count") or 0)
        warning_count = int(summary.get("warning_count") or 0)
        _maybe_block(blockers, "operations_blockers", blocker_count > 0, "Operations Report still has blockers.")
        if warning_count:
            warnings.append(_warning("operations_warnings", f"Operations Report has {warning_count} warning(s)."))

        runbook_gate = _runbook_gate(runbook, current)
        if runbook_gate.get("status") == "failed":
            blockers.append(_blocker("runbook", str(runbook_gate.get("message") or "Release Operations Runbook gate failed.")))
        elif runbook_gate.get("status") == "warning":
            warnings.append(_warning("runbook", str(runbook_gate.get("message") or "Release Operations Runbook has warnings.")))

        failed_verifiers = _failed_verifier_summaries(verifier_summary)
        _maybe_block(blockers, "package_verifiers", bool(failed_verifiers), "One or more package verifiers failed.")
        if _missing_submission_evidence(current):
            blockers.append(_blocker("submission_evidence_missing", "Submission Evidence accepted records are incomplete."))
        if not _package_ledger_complete(package_ledger):
            blockers.append(_blocker("package_ledger_incomplete", "Operations package ledger has missing required packages."))

        if force and not override_reason:
            blockers.append(_blocker("override_reason_missing", "override_reason is required for force Operations Signoff."))

        force_blocked = list(blockers)
        signable = not blockers and (not warnings or force)
        status = "passed" if not blockers and not warnings else "warning" if signable else "failed"
        return sanitize_metadata(
            {
                "status": status,
                "signable": signable,
                "force": force,
                "hard_blocked": bool(force_blocked),
                "blockers": blockers,
                "warnings": warnings,
                "operations_report": _report_reference(current),
                "stored_operations_report": _report_reference(report),
                "report_stale": report_stale,
                "runbook": runbook_gate,
                "package_ledger": package_ledger,
                "verifier_summary": verifier_summary,
                "change_request_summary": change_summary,
                "source_hash": stable_hash({"operations_report": _report_reference(current), "runbook": runbook_gate, "package_ledger": package_ledger, "verifier_summary": verifier_summary, "change_request_summary": change_summary}),
            },
            blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS,
        )

    def signoff(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            existing = self.read_signoff(release_id, default={})
            if operations_signoff_summary(existing).get("status") in {"signed", "force_signed"}:
                raise ReleaseOperationsSignoffStateError("Release Operations are already signed off. Reset Operations Signoff before signing again.")
            gate = self.gate(release_id, payload, now=now)
            if not gate.get("signable"):
                raise ReleaseOperationsSignoffStateError("Release Operations Signoff gate failed.")
            force = bool(payload.get("force", False))
            status = "force_signed" if force and gate.get("status") != "passed" else "signed"
            signoff = {
                "schema_version": OPERATIONS_SIGNOFF_SCHEMA_VERSION,
                "release_id": release_id,
                "status": status,
                "signed_at": now,
                "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
                "force": status == "force_signed",
                "override_reason": sanitize_sensitive_text(str(payload.get("override_reason") or "").strip()) or None,
                "operations_report": gate.get("operations_report", {}),
                "runbook": gate.get("runbook", {}),
                "package_ledger_hash": stable_hash(gate.get("package_ledger", {})),
                "verifier_summary_hash": stable_hash(gate.get("verifier_summary", {})),
                "change_request_summary_hash": stable_hash(gate.get("change_request_summary", {})),
                "source_hash": gate.get("operations_report", {}).get("source_hash") if isinstance(gate.get("operations_report"), dict) else None,
                "evidence_hash": gate.get("source_hash"),
                "gate": gate,
                "export_manifest_hash": None,
            }
            signoff["payload_hash"] = operations_signoff_hash(signoff)
            self.operations_dir(release_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.signoff_path(release_id), signoff)
            self._append_history(release_id, "signed", {"status": status, "signed_by": signoff.get("signed_by")}, now=now)
            self.release_store.append_event(release_id, "operations_signoff_signed", {"status": status})
            self.operations_store.refresh(release_id, now=now)
            return signoff

    def reset_signoff(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
        if len(reason) < 8:
            raise ReleaseOperationsSignoffStateError("reason must be at least 8 characters.")
        change_request_id = str(payload.get("change_request_id") or "").strip()
        if not change_request_id:
            raise ReleaseOperationsSignoffStateError("Approved Operations Change Request is required before reset.")
        with self.lock:
            request = self.get_change_request(release_id, change_request_id)
            if not operations_change_request_integrity_ok(request):
                raise ReleaseOperationsSignoffStateError("Operations Change Request integrity failed.")
            if request.get("status") != "approved":
                raise ReleaseOperationsSignoffStateError("Operations Change Request must be approved before reset.")
            now = now or now_iso()
            existing = self.read_signoff(release_id, default={})
            reset = {
                "schema_version": OPERATIONS_SIGNOFF_SCHEMA_VERSION,
                "release_id": release_id,
                "status": "reset",
                "reset_at": now,
                "reason": reason,
                "change_request_id": change_request_id,
                "previous_status": existing.get("status") if existing else "not_signed",
                "previous_payload_hash": existing.get("payload_hash") if existing else None,
            }
            reset["payload_hash"] = operations_signoff_hash(reset)
            self.operations_dir(release_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.signoff_path(release_id), reset)
            request["status"] = "applied"
            request["updated_at"] = now
            request["applied_at"] = now
            request["applied_signoff_reset_hash"] = reset["payload_hash"]
            request["integrity_hash"] = operations_change_request_hash(request)
            _write_json(self.change_request_path(release_id, change_request_id), request)
            self._append_change_event(release_id, "applied", request, now=now)
            reset_summary = {
                "reason": reason,
                "change_request_id": change_request_id,
                "payload_hash": reset["payload_hash"],
                "previous_payload_hash": reset.get("previous_payload_hash"),
            }
            self._append_history(release_id, "reset", reset_summary, now=now)
            self.release_store.append_event(release_id, "operations_signoff_reset", reset_summary)
            self.operations_store.refresh(release_id, now=now)
            return reset

    def package_ledger(self, release_id: str, *, current_report: dict[str, Any] | None = None) -> dict[str, Any]:
        report = current_report or self.operations_store.build_report(release_id, persist=False)
        packages = report.get("package_summaries") if isinstance(report.get("package_summaries"), dict) else {}
        release_zip = packages.get("release_zip") if isinstance(packages.get("release_zip"), dict) else {}
        distribution = packages.get("distribution_packages") if isinstance(packages.get("distribution_packages"), list) else []
        submission = packages.get("submission_packages") if isinstance(packages.get("submission_packages"), list) else []
        evidence = packages.get("submission_evidence_packages") if isinstance(packages.get("submission_evidence_packages"), list) else []
        ledger = {
            "release_id": release_id,
            "generated_at": now_iso(),
            "release_zip": release_zip,
            "distribution_packages": distribution,
            "submission_packages": submission,
            "submission_evidence_packages": evidence,
            "summary": {
                "release_zip_exists": bool(release_zip.get("exists")),
                "distribution_count": len(distribution),
                "submission_count": len(submission),
                "submission_evidence_count": len(evidence),
                "missing_count": _missing_package_count(packages),
            },
        }
        ledger["ledger_hash"] = stable_hash({key: value for key, value in ledger.items() if key != "ledger_hash"})
        return sanitize_metadata(ledger, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

    def export_archive(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            signoff = self.get_signoff(release_id)
            summary = operations_signoff_summary(signoff, current_report=self.operations_store.build_report(release_id, persist=False))
            if summary.get("status") not in {"signed", "force_signed"}:
                raise ReleaseOperationsSignoffStateError("Operations Archive requires signed Operations Signoff.")
            if not summary.get("payload_hash_ok") or summary.get("stale"):
                raise ReleaseOperationsSignoffStateError("Operations Signoff is stale or integrity failed. Reset and sign again.")
            report = self.operations_store.read_report(release_id, default={}) or self.operations_store.refresh(release_id, now=now)
            latest_runbook = _latest_runbook(self.runbook_store, release_id)
            latest_runbook_summary = runbook_summary(latest_runbook) if latest_runbook else {"status": "missing"}
            verifier_summaries = report.get("verifier_summaries") if isinstance(report.get("verifier_summaries"), dict) else {}
            package_ledger = self.package_ledger(release_id, current_report=report)
            change_summary = self.change_request_summary(release_id)
            export_dir = self.archive_export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            _write_json(export_dir / "operations-signoff.json", signoff)
            _write_json(export_dir / "operations-report.json", report)
            _write_json(export_dir / "latest-runbook-summary.json", latest_runbook_summary)
            _write_json(export_dir / "verifier-summaries.json", verifier_summaries)
            _write_json(export_dir / "package-ledger.json", package_ledger)
            _write_json(export_dir / "change-request-summary.json", change_summary)
            _write_archive_readme(export_dir, signoff, report)
            files = [_file_record(export_dir, export_dir / name) for name in ("operations-signoff.json", "operations-report.json", "latest-runbook-summary.json", "verifier-summaries.json", "package-ledger.json", "change-request-summary.json", "README.txt")]
            manifest = {
                "schema_version": OPERATIONS_ARCHIVE_SCHEMA_VERSION,
                "tool": {"name": "MusicForge Release Operations Archive", "version": __version__},
                "release_id": release_id,
                "generated_at": now,
                "source_hash": signoff.get("source_hash"),
                "operations_signoff": {"path": "operations-signoff.json", "payload_hash": signoff.get("payload_hash"), "payload_hash_actual": operations_signoff_hash(signoff)},
                "operations_report": {"path": "operations-report.json", "integrity_hash": report.get("integrity_hash"), "report_hash": operations_report_integrity_hash(report)},
                "latest_runbook": {"path": "latest-runbook-summary.json", "runbook_id": latest_runbook_summary.get("runbook_id"), "runbook_hash": runbook_integrity_hash(latest_runbook) if latest_runbook else None},
                "package_ledger": {"path": "package-ledger.json", "ledger_hash": package_ledger.get("ledger_hash")},
                "verifier_summaries": {"path": "verifier-summaries.json", "summary_hash": stable_hash(verifier_summaries)},
                "change_request_summary": {"path": "change-request-summary.json", "summary_hash": stable_hash(change_summary)},
                "summary": operations_signoff_summary(signoff, current_report=report),
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"signoff": signoff, "report": report, "runbook": latest_runbook_summary, "ledger": package_ledger, "change_requests": change_summary}),
            }
            manifest["integrity_hash"] = operations_archive_manifest_hash(manifest)
            _write_json(export_dir / "operations-archive-manifest.json", manifest)
            self.release_store.append_event(release_id, "operations_archive_exported", {"status": summary.get("status")})
            return sanitize_metadata(manifest, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

    def build_archive_zip(self, release_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            export_dir = self.archive_export_dir(release_id).resolve()
            release_dir = self.release_store.release_dir(release_id).resolve()
            zip_path = self.archive_zip_path(release_id).resolve()
            _ensure_within(release_dir, export_dir)
            _ensure_within(release_dir, zip_path)
            if not (export_dir / "operations-archive-manifest.json").exists():
                self.export_archive(release_id, now=now)
            manifest = read_json(export_dir / "operations-archive-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = operations_archive_manifest_hash(manifest)
            _write_json(export_dir / "operations-archive-manifest.json", manifest)
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
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            return sanitize_metadata(info, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

    def read_archive_manifest(self, release_id: str) -> dict[str, Any]:
        path = self.archive_export_dir(release_id) / "operations-archive-manifest.json"
        if not path.exists():
            raise FileNotFoundError("Operations Archive export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

    def list_change_requests(self, release_id: str, *, include_cancelled: bool = True) -> list[dict[str, Any]]:
        root = self.change_requests_root(release_id)
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("ocr-*.json")) if root.exists() else []:
            try:
                item = sanitize_metadata(read_json(path), blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)
            except Exception:
                continue
            if not include_cancelled and item.get("status") == "cancelled":
                continue
            rows.append(item)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)

    def get_change_request(self, release_id: str, change_request_id: str) -> dict[str, Any]:
        path = self.change_request_path(release_id, change_request_id)
        if not path.exists():
            raise ReleaseOperationsSignoffNotFoundError("Operations Change Request does not exist.")
        return sanitize_metadata(read_json(path), blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

    def create_change_request(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
        if len(reason) < 8:
            raise ReleaseOperationsSignoffStateError("Change Request reason must be at least 8 characters.")
        scope = payload.get("scope") if isinstance(payload.get("scope"), list) else []
        clean_scope = sorted({_safe_text(item, 80) for item in scope if _safe_text(item, 80)})
        if not clean_scope:
            raise ReleaseOperationsSignoffStateError("Change Request scope is required.")
        with self.lock:
            now = now or now_iso()
            change_request_id = self._reserve_change_request_id(release_id)
            signoff = self.read_signoff(release_id, default={})
            release = self.release_store.get_release(release_id)
            item = {
                "schema_version": OPERATIONS_CHANGE_REQUEST_SCHEMA_VERSION,
                "change_request_id": change_request_id,
                "release_id": release_id,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "created_by": _safe_text(payload.get("created_by"), 120) or "local-user",
                "reason": reason,
                "scope": clean_scope,
                "impact": _change_request_impact(clean_scope),
                "approval": {"approved_by": None, "approved_at": None, "notes": None},
                "source": {"operations_signoff_hash": signoff.get("payload_hash"), "release_source_hash": stable_hash(release.to_dict())},
            }
            item["integrity_hash"] = operations_change_request_hash(item)
            self.change_requests_root(release_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.change_request_path(release_id, change_request_id), item)
            self._append_change_event(release_id, "created", item, now=now)
            return item

    def update_change_request_status(self, release_id: str, change_request_id: str, action: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            item = self.get_change_request(release_id, change_request_id)
            current = str(item.get("status") or "")
            if not operations_change_request_integrity_ok(item):
                raise ReleaseOperationsSignoffStateError("Operations Change Request integrity failed.")
            if action == "submit":
                if current != "draft":
                    raise ReleaseOperationsSignoffStateError("Only draft Change Requests can be submitted.")
                item["status"] = "submitted"
            elif action == "approve":
                if current not in {"draft", "submitted"}:
                    raise ReleaseOperationsSignoffStateError("Only draft or submitted Change Requests can be approved.")
                approver = _safe_text(payload.get("approved_by"), 120) or _safe_text(payload.get("reviewed_by"), 120)
                notes = sanitize_sensitive_text(str(payload.get("notes") or "").strip())
                if not approver:
                    raise ReleaseOperationsSignoffStateError("approved_by is required.")
                item["status"] = "approved"
                item["approval"] = {"approved_by": approver, "approved_at": now, "notes": notes or None}
            elif action == "reject":
                if current not in {"draft", "submitted"}:
                    raise ReleaseOperationsSignoffStateError("Only draft or submitted Change Requests can be rejected.")
                reason = sanitize_sensitive_text(str(payload.get("reason") or payload.get("notes") or "").strip())
                if len(reason) < 8:
                    raise ReleaseOperationsSignoffStateError("Rejection reason must be at least 8 characters.")
                item["status"] = "rejected"
                item["approval"] = {"approved_by": None, "approved_at": None, "notes": reason}
            elif action == "cancel":
                if current in {"approved", "applied"}:
                    raise ReleaseOperationsSignoffStateError("Approved or applied Change Requests cannot be cancelled.")
                item["status"] = "cancelled"
            else:
                raise ReleaseOperationsSignoffStateError("Unknown Change Request action.")
            item["updated_at"] = now
            item["integrity_hash"] = operations_change_request_hash(item)
            _write_json(self.change_request_path(release_id, change_request_id), item)
            self._append_change_event(release_id, action, item, now=now)
            return item

    def change_request_summary(self, release_id: str) -> dict[str, Any]:
        rows = self.list_change_requests(release_id)
        counts: dict[str, int] = {}
        for item in rows:
            counts[str(item.get("status") or "unknown")] = counts.get(str(item.get("status") or "unknown"), 0) + 1
        latest = rows[0] if rows else {}
        summary = {"count": len(rows), "status_counts": counts, "latest_change_request_id": latest.get("change_request_id"), "approved_count": counts.get("approved", 0)}
        summary["summary_hash"] = stable_hash(summary)
        return sanitize_metadata(summary, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

    def _reserve_change_request_id(self, release_id: str) -> str:
        root = self.change_requests_root(release_id)
        root.mkdir(parents=True, exist_ok=True)
        existing: list[int] = []
        for path in root.glob("ocr-*.json"):
            try:
                existing.append(int(path.stem.split("-")[-1]))
            except ValueError:
                pass
        return f"ocr-{(max(existing) if existing else 0) + 1:06d}"

    def _append_history(self, release_id: str, event_type: str, summary: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.history_path(release_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        if path.exists():
            count = len(path.read_text(encoding="utf-8").splitlines())
        event = sanitize_metadata({"event_id": f"opse-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _append_change_event(self, release_id: str, event_type: str, item: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.change_request_events_path(release_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        if path.exists():
            count = len(path.read_text(encoding="utf-8").splitlines())
        event = sanitize_metadata({"event_id": f"ocre-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "change_request_id": item.get("change_request_id"), "status": item.get("status")}, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")





def operations_signoff_integrity_ok(signoff: dict[str, Any] | None) -> bool:
    data = signoff if isinstance(signoff, dict) else {}
    return bool(data.get("payload_hash")) and str(data.get("payload_hash")) == operations_signoff_hash(data)


def operations_signoff_summary(signoff: dict[str, Any] | None, *, current_report: dict[str, Any] | None = None) -> dict[str, Any]:
    data = signoff if isinstance(signoff, dict) else {}
    if not data:
        return {"status": "not_signed", "integrity_ok": False, "payload_hash_ok": False, "stale": False}
    payload_hash_ok = operations_signoff_integrity_ok(data)
    current_source_hash = current_report.get("source_hash") if isinstance(current_report, dict) else None
    stale = bool(current_source_hash and data.get("source_hash") and str(current_source_hash) != str(data.get("source_hash")))
    gate = data.get("gate") if isinstance(data.get("gate"), dict) else {}
    operations_report = data.get("operations_report") if isinstance(data.get("operations_report"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_id": data.get("release_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "force": bool(data.get("force")),
            "payload_hash": data.get("payload_hash"),
            "payload_hash_ok": payload_hash_ok,
            "integrity_ok": payload_hash_ok,
            "stale": stale,
            "source_hash": data.get("source_hash"),
            "current_source_hash": current_source_hash,
            "operations_report_id": operations_report.get("report_id"),
            "current_stage": operations_report.get("current_stage"),
            "blocker_count": len(gate.get("blockers", [])) if isinstance(gate.get("blockers"), list) else 0,
            "warning_count": len(gate.get("warnings", [])) if isinstance(gate.get("warnings"), list) else 0,
        },
        blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS,
    )











def operations_archive_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == operations_archive_manifest_hash(data)


def _latest_runbook(runbook_store: ReleaseOperationsRunbookStore, release_id: str) -> ImplementationDocument:
    rows = runbook_store.list_runbooks(release_id, include_archived=True)
    return rows[0] if rows else {}


def _runbook_gate(runbook: ImplementationDocument, current_report: ImplementationDocument) -> ImplementationDocument:
    if not runbook:
        return {"status": "warning", "message": "No Release Operations Runbook exists.", "runbook_id": None}
    summary = runbook_summary(runbook)
    source = runbook.get("source") if isinstance(runbook.get("source"), dict) else {}
    stale = str(source.get("operations_source_hash") or "") != str(current_report.get("source_hash") or "")
    failed_safe_count = sum(1 for item in runbook.get("items", []) if isinstance(item, dict) and item.get("risk") == "auto_safe" and item.get("status") == "failed")
    pending_safe_count = sum(1 for item in runbook.get("items", []) if isinstance(item, dict) and item.get("risk") == "auto_safe" and item.get("status") in {"pending", "running"})
    integrity_ok = runbook_integrity_ok(runbook)
    status = "failed" if stale or failed_safe_count or pending_safe_count or not integrity_ok else "passed" if runbook.get("status") in {"completed", "blocked"} else "warning"
    message = "Runbook evidence is current."
    if stale:
        message = "Release Operations Runbook is stale."
    elif not integrity_ok:
        message = "Release Operations Runbook integrity failed."
    elif failed_safe_count:
        message = "Release Operations Runbook has failed auto-safe items."
    elif pending_safe_count:
        message = "Release Operations Runbook still has pending auto-safe items."
    return sanitize_metadata({**summary, "status": status, "stale": stale, "integrity_ok": integrity_ok, "failed_safe_count": failed_safe_count, "pending_safe_count": pending_safe_count, "message": message}, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)


def _verifier_summary_from_report(report: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(report.get("verifier_summaries") if isinstance(report.get("verifier_summaries"), dict) else {}, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)


def _failed_verifier_summaries(value: Any) -> list[ImplementationDocument]:
    failed: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                if item.get("status") not in {"passed", "warning", "missing"}:
                    failed.append({"scope": key, **item})
            elif isinstance(item, list):
                failed.extend(_failed_verifier_summaries(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("status") not in {"passed", "warning", "missing"}:
                failed.append(item)
            elif isinstance(item, (list, dict)):
                failed.extend(_failed_verifier_summaries(item))
    return failed


def _missing_submission_evidence(report: ImplementationDocument) -> bool:
    domain = report.get("domains", {}).get("submission_evidence") if isinstance(report.get("domains"), dict) else {}
    if not isinstance(domain, dict) or not domain.get("required"):
        return False
    summary = domain.get("summary") if isinstance(domain.get("summary"), dict) else {}
    return int(summary.get("accepted_count") or 0) <= 0 or domain.get("status") not in {"passed", "warning"}


def _package_ledger_complete(ledger: ImplementationDocument) -> bool:
    summary = ledger.get("summary") if isinstance(ledger.get("summary"), dict) else {}
    return bool(summary.get("release_zip_exists")) and int(summary.get("missing_count") or 0) == 0


def _missing_package_count(packages: ImplementationDocument) -> int:
    missing = 0
    release_zip = packages.get("release_zip") if isinstance(packages.get("release_zip"), dict) else {}
    if not release_zip.get("exists"):
        missing += 1
    for key in ("distribution_packages", "submission_packages", "submission_evidence_packages"):
        for item in packages.get(key, []) if isinstance(packages.get(key), list) else []:
            if isinstance(item, dict) and not item.get("exists"):
                missing += 1
    return missing


def _change_request_impact(scope: list[str]) -> dict[str, bool]:
    values = set(scope)
    return {
        "requires_release_signoff_reset": bool(values & {"metadata", "release_export", "release", "audio", "rights", "format_decision"}),
        "requires_distribution_signoff_reset": bool(values & {"distribution", "release_export", "audio", "rights", "format_decision"}),
        "requires_submission_signoff_reset": bool(values & {"submission", "distribution", "release_export"}),
        "requires_operations_signoff_reset": True,
    }


def _report_reference(report: ImplementationDocument) -> ImplementationDocument:
    return {"report_id": report.get("report_id"), "status": report.get("status"), "current_stage": report.get("current_stage"), "source_hash": report.get("source_hash"), "integrity_hash": report.get("integrity_hash"), "blocker_count": report.get("summary", {}).get("blocker_count") if isinstance(report.get("summary"), dict) else None, "warning_count": report.get("summary", {}).get("warning_count") if isinstance(report.get("summary"), dict) else None}


def _maybe_block(blockers: list[ImplementationDocument], check_id: str, condition: bool, message: str) -> None:
    if condition:
        blockers.append(_blocker(check_id, message))


def _blocker(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS

    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}


def _write_archive_readme(export_dir: Path, signoff: ImplementationDocument, report: ImplementationDocument) -> None:
    lines = [
        "MusicForge Release Operations Archive",
        "",
        f"Release ID: {signoff.get('release_id')}",
        f"Signoff Status: {signoff.get('status')}",
        f"Signed At: {signoff.get('signed_at') or '-'}",
        f"Current Stage: {report.get('current_stage') or '-'}",
        "",
        "This archive contains summary evidence only. It does not include audio, artwork, package ZIPs, credentials, or platform account data.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, data: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS))


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
            raise ReleaseOperationsSignoffStateError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleaseOperationsSignoffStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleaseOperationsSignoffStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleaseOperationsSignoffStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseOperationsSignoffStateError("Refusing to operate outside release operations boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _validate_change_request_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("ocr-") or not text.replace("ocr-", "", 1).isdigit():
        raise ReleaseOperationsSignoffNotFoundError("Invalid Operations Change Request id.")
    return text
