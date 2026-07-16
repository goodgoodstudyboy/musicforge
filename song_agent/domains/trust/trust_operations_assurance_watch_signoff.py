from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib as hashlib
import json as json
import os as os
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
from song_agent.domains.trust.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore as TrustOperationsAssuranceWatchStore
from song_agent.domains.trust.trust_operations_continuous_assurance import TrustOperationsAssuranceStore as TrustOperationsAssuranceStore
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_assurance_watch_signoff_contracts import ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES as ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES, TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION, TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE, watch_signoff_hash as watch_signoff_hash, watch_signoff_history_event_hash as watch_signoff_history_event_hash, watch_signoff_history_event_payload_hash as watch_signoff_history_event_payload_hash, watch_signoff_manifest_hash as watch_signoff_manifest_hash







TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_change_request"








class TrustOperationsAssuranceWatchSignoffError(ValueError):
    pass


class TrustOperationsAssuranceWatchSignoffNotFoundError(TrustOperationsAssuranceWatchSignoffError):
    pass


class TrustOperationsAssuranceWatchSignoffStateError(TrustOperationsAssuranceWatchSignoffError):
    pass


class TrustOperationsAssuranceWatchSignoffStore:
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations" / "assurance-watch-signoffs",
        *,
        watch_store: TrustOperationsAssuranceWatchStore | None = None,
        assurance_store: TrustOperationsAssuranceStore | None = None,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.assurance_store = assurance_store or TrustOperationsAssuranceStore(hub_store=self.hub_store)
        self.watch_store = watch_store or TrustOperationsAssuranceWatchStore(hub_store=self.hub_store, assurance_store=self.assurance_store)
        self.lock = threading.RLock()

    def queue_dir(self, queue_id: str) -> Path:
        return self.root / _safe_id(queue_id)

    def closeout_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "watch-closeout.json"

    def signoff_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "watch-signoff.json"

    def history_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "watch-signoff-history.jsonl"

    def change_requests_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "change-requests"

    def change_request_path(self, queue_id: str, change_request_id: str) -> Path:
        return self.change_requests_dir(queue_id) / (_safe_id(change_request_id) + ".json")

    def archive_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "archive"

    def archive_zip_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "trust-operations-assurance-watch-signoff.zip"

    def verification_report_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "trust-operations-assurance-watch-signoff-verification-report.json"

    def read_closeout(self, queue_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = _read_json_default(self.closeout_path(queue_id), default=default or {})
        if not value and default is None:
            raise TrustOperationsAssuranceWatchSignoffNotFoundError("Assurance Watch closeout not found.")
        return value

    def read_signoff(self, queue_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = _read_json_default(self.signoff_path(queue_id), default=default or {})
        if not value and default is None:
            raise TrustOperationsAssuranceWatchSignoffNotFoundError("Assurance Watch signoff not found.")
        return value

    def list_change_requests(self, queue_id: str) -> list[dict[str, Any]]:
        root = self.change_requests_dir(queue_id)
        if not root.exists():
            return []
        return [_sanitize(row) for row in (_read_json_default(path, default={}) for path in sorted(root.glob("*.json"))) if row]

    def summary(self, queue_id: str) -> dict[str, Any]:
        state = self._signoff_state(queue_id)
        return {
            "queue_id": queue_id,
            "status": state.get("status") or "unsigned",
            "closeout": self.read_closeout(queue_id, default={}),
            "signoff": self.read_signoff(queue_id, default={}),
            "change_requests": self.list_change_requests(queue_id),
            "verification": _read_json_default(self.verification_report_path(queue_id), default={}),
        }

    def refresh_closeout(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(queue_id, "refresh closeout")
            source, watch_report, hub_report, assurance_report = self._closeout_source(queue_id, payload)
            blockers = self._closeout_blockers(source, watch_report, hub_report, assurance_report)
            queue = self.watch_store.read_queue(queue_id)
            action_pack = _read_json_default(self.watch_store.action_pack_path(queue_id), default={})
            queue_summary = queue.get("summary") if isinstance(queue.get("summary"), dict) else {}
            action_summary = action_pack.get("summary") if isinstance(action_pack.get("summary"), dict) else {}
            summary = {
                "total_watch_items": int(queue_summary.get("hub_count") or len(queue.get("rows", []) if isinstance(queue.get("rows"), list) else [])),
                "passed_watch_items": int(queue_summary.get("clear_count") or 0),
                "failed_watch_items": int(queue_summary.get("failed_count") or 0),
                "manual_required_items": int(action_summary.get("manual_required_count") or queue_summary.get("manual_action_count") or 0),
                "overdue_items": int(queue_summary.get("overdue_count") or 0),
                "blocking_drift_count": int(queue_summary.get("blocking_action_count") or action_summary.get("blocking_count") or 0),
                "watch_clear": queue.get("status") == "clear" and watch_report.get("clear") is True,
                "ready_for_signoff": not blockers,
            }
            closeout_id = _safe_id(str(payload.get("closeout_id") or _next_id(self.queue_dir(queue_id), "awco")))
            closeout = {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE,
                "closeout_id": closeout_id,
                "queue_id": queue_id,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "passed",
                "source": source,
                "summary": summary,
                "blockers": blockers,
                "warnings": [],
                "manual_actions": list(action_pack.get("actions", []) if isinstance(action_pack.get("actions"), list) else []),
            }
            closeout["integrity_hash"] = watch_signoff_hash(closeout)
            _write_json(self.closeout_path(queue_id), closeout)
            self._append_history(queue_id, {"event_type": "watch_closeout_refreshed", "created_at": now, "queue_id": queue_id, "closeout_hash": closeout["integrity_hash"], "status": closeout["status"]})
            return _sanitize(closeout)

    def sign(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            self._ensure_unsigned(queue_id, "sign watch closeout")
            closeout = self.read_closeout(queue_id)
            if closeout.get("integrity_hash") != watch_signoff_hash(closeout):
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch closeout integrity failed.")
            if closeout.get("status") != "passed":
                raise TrustOperationsAssuranceWatchSignoffStateError("Only passed Assurance Watch closeouts can be signed.")
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsAssuranceWatchSignoffStateError("Signoff reason must be at least 8 characters.")
            signed_by = sanitize_sensitive_text(str(payload.get("signed_by") or "local-reviewer")[:120])
            role = sanitize_sensitive_text(str(payload.get("role") or "owner")[:80])
            signoff_id = _safe_id(str(payload.get("signoff_id") or _next_id(self.queue_dir(queue_id), "awsg")))
            source = {
                "closeout_integrity_hash": closeout.get("integrity_hash"),
                "queue_source_hash": closeout.get("source", {}).get("queue_source_hash") if isinstance(closeout.get("source"), dict) else None,
                "watch_zip_sha256": closeout.get("source", {}).get("watch_zip_sha256") if isinstance(closeout.get("source"), dict) else None,
                "watch_manifest_hash": closeout.get("source", {}).get("watch_manifest_hash") if isinstance(closeout.get("source"), dict) else None,
                "watch_verification_report_hash": closeout.get("source", {}).get("watch_verification_report_hash") if isinstance(closeout.get("source"), dict) else None,
                "hub_zip_sha256": closeout.get("source", {}).get("hub_zip_sha256") if isinstance(closeout.get("source"), dict) else None,
                "hub_manifest_hash": closeout.get("source", {}).get("hub_manifest_hash") if isinstance(closeout.get("source"), dict) else None,
                "hub_verification_report_hash": closeout.get("source", {}).get("hub_verification_report_hash") if isinstance(closeout.get("source"), dict) else None,
                "continuous_assurance_report_hash": closeout.get("source", {}).get("continuous_assurance_report_hash") if isinstance(closeout.get("source"), dict) else None,
            }
            decision = {"approved": True, "force": False, "exceptions": []}
            payload_hash = stable_hash({"queue_id": queue_id, "closeout_id": closeout.get("closeout_id"), "signed_by": signed_by, "role": role, "reason": reason, "source": source, "decision": decision})
            signoff = {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE,
                "signoff_id": signoff_id,
                "queue_id": queue_id,
                "closeout_id": closeout.get("closeout_id"),
                "status": "signed",
                "signed_at": now,
                "signed_by": signed_by,
                "role": role,
                "reason": reason,
                "source": source,
                "decision": decision,
                "payload_hash": payload_hash,
            }
            signoff["integrity_hash"] = watch_signoff_hash(signoff)
            _write_json(self.signoff_path(queue_id), signoff)
            self._append_history(
                queue_id,
                {
                    "event_type": "watch_signoff_created",
                    "created_at": now,
                    "queue_id": queue_id,
                    "signoff_id": signoff_id,
                    "signoff_hash": signoff["integrity_hash"],
                    "closeout_hash": closeout.get("integrity_hash"),
                    "signed_by": signed_by,
                    "role": role,
                    "reason": reason,
                    "signoff_payload_hash": signoff.get("payload_hash"),
                },
            )
            return _sanitize(signoff)

    def create_change_request(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise TrustOperationsAssuranceWatchSignoffStateError("Change request reason must be at least 8 characters.")
            state = self._signoff_state(queue_id)
            cr_id = _safe_id(str(payload.get("change_request_id") or _next_id(self.change_requests_dir(queue_id), "awcr")))
            cr = {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUEST_PACKAGE_TYPE,
                "change_request_id": cr_id,
                "queue_id": queue_id,
                "status": "draft",
                "created_at": now,
                "created_by": sanitize_sensitive_text(str(payload.get("created_by") or "local-operator")[:120]),
                "reason": reason,
                "source": {"current_signoff_hash": state.get("signoff_hash")},
                "approval": None,
                "applied": {"applied_at": None, "applied_signoff_reset_hash": None},
            }
            cr["integrity_hash"] = watch_signoff_hash(cr)
            _write_json(self.change_request_path(queue_id, cr_id), cr)
            self._append_history(queue_id, {"event_type": "watch_change_request_created", "created_at": now, "queue_id": queue_id, "change_request_id": cr_id, "change_request_hash": cr["integrity_hash"]})
            return _sanitize(cr)

    def approve_change_request(self, queue_id: str, change_request_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            cr = self._read_change_request(queue_id, change_request_id)
            self._ensure_change_request_integrity(cr)
            if cr.get("status") != "draft":
                raise TrustOperationsAssuranceWatchSignoffStateError("Only draft Assurance Watch signoff change requests can be approved.")
            cr["status"] = "approved"
            cr["approval"] = {
                "approved_at": now,
                "approved_by": sanitize_sensitive_text(str(payload.get("approved_by") or "local-reviewer")[:120]),
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Assurance Watch signoff reset approved.")[:500]),
            }
            cr["integrity_hash"] = watch_signoff_hash(cr)
            _write_json(self.change_request_path(queue_id, change_request_id), cr)
            self._append_history(queue_id, {"event_type": "watch_change_request_approved", "created_at": now, "queue_id": queue_id, "change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]})
            return _sanitize(cr)

    def reset_signoff(self, queue_id: str, change_request_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            state = self._signoff_state(queue_id)
            if state.get("status") != "signed":
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff is not signed.")
            cr = self._read_change_request(queue_id, change_request_id)
            self._ensure_change_request_integrity(cr)
            applied = cr.get("applied") if isinstance(cr.get("applied"), dict) else {}
            if cr.get("status") != "approved" or applied.get("applied_at"):
                raise TrustOperationsAssuranceWatchSignoffStateError("Approved unused Assurance Watch change request is required.")
            source = cr.get("source") if isinstance(cr.get("source"), dict) else {}
            if source.get("current_signoff_hash") and source.get("current_signoff_hash") != state.get("signoff_hash"):
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch change request does not target the current signoff.")
            applied["applied_at"] = now
            applied["applied_signoff_reset_hash"] = state.get("signoff_hash")
            cr["applied"] = applied
            cr["status"] = "applied"
            cr["integrity_hash"] = watch_signoff_hash(cr)
            _write_json(self.change_request_path(queue_id, change_request_id), cr)
            self._append_history(queue_id, {"event_type": "watch_signoff_reset", "created_at": now, "queue_id": queue_id, "signoff_hash": state.get("signoff_hash"), "change_request_id": change_request_id, "change_request_hash": cr["integrity_hash"]})
            if self.signoff_path(queue_id).exists():
                os.remove(_fs_path(self.signoff_path(queue_id)))
            return {"status": "reset", "change_request": _sanitize(cr)}

    def export_archive(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            payload = payload or {}
            signoff = self.read_signoff(queue_id, default={})
            if not signoff and self._signoff_state(queue_id).get("status") == "signed":
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff is signed but watch-signoff.json is missing. Reset with an approved Change Request before archiving.")
            if not signoff:
                raise TrustOperationsAssuranceWatchSignoffNotFoundError("Assurance Watch signoff not found.")
            self._ensure_signoff_current(queue_id, signoff, payload)
            self._ensure_archive_not_exported(queue_id, str(signoff.get("integrity_hash") or ""))
            export_dir = self.archive_dir(queue_id)
            if export_dir.exists():
                shutil.rmtree(_fs_path(export_dir), ignore_errors=True)
            _mkdir(export_dir)
            closeout = self.read_closeout(queue_id)
            queue_summary = self._watch_queue_summary(queue_id, signoff)
            action_summary = self._drift_action_pack_summary(queue_id, signoff)
            external_summary = self._external_summary(signoff)
            change_requests_doc = self._change_requests_doc(queue_id, signoff)
            _write_readme(export_dir)
            _write_json(export_dir / "watch-closeout.json", closeout)
            _write_json(export_dir / "watch-signoff.json", signoff)
            _write_json(export_dir / "watch-queue-summary.json", queue_summary)
            _write_json(export_dir / "drift-action-pack-summary.json", action_summary)
            _write_json(export_dir / "external-verification-summary.json", external_summary)
            _write_json(export_dir / "change-requests.json", change_requests_doc)
            (export_dir / "watch-signoff-history.jsonl").write_text(_read_text(self.history_path(queue_id)), encoding="utf-8")
            manifest = {
                "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Trust Operations Assurance Watch Signoff", "version": __version__},
                "queue_id": queue_id,
                "generated_at": now,
                "source": {
                    "closeout_hash": closeout.get("integrity_hash"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "queue_summary_hash": queue_summary.get("integrity_hash"),
                    "drift_action_pack_summary_hash": action_summary.get("integrity_hash"),
                    "external_verification_summary_hash": external_summary.get("integrity_hash"),
                    "change_requests_hash": change_requests_doc.get("integrity_hash"),
                    "history_hash": _history_hash(self._history_events(queue_id)),
                    **(signoff.get("source") if isinstance(signoff.get("source"), dict) else {}),
                },
                "summary": {"status": signoff.get("status"), "watch_clear": True, "blocking_drift_count": closeout.get("summary", {}).get("blocking_drift_count") if isinstance(closeout.get("summary"), dict) else None},
                "files": sorted([_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "trust-operations-assurance-watch-signoff-manifest.json"], key=lambda item: str(item.get("path") or "")),
                "zip": {},
            }
            manifest["integrity_hash"] = watch_signoff_manifest_hash(manifest)
            _write_json(export_dir / "trust-operations-assurance-watch-signoff-manifest.json", manifest)
            self._append_history(queue_id, {"event_type": "watch_signoff_archive_exported", "created_at": now, "queue_id": queue_id, "signoff_hash": signoff.get("integrity_hash"), "manifest_hash": manifest["integrity_hash"]})
            return _sanitize(manifest)

    def build_archive_zip(self, queue_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or _now()
            signoff = self.read_signoff(queue_id, default={})
            if not signoff and self._signoff_state(queue_id).get("status") == "signed":
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff is signed but watch-signoff.json is missing. Reset with an approved Change Request before rebuilding archive ZIP.")
            if not signoff:
                raise TrustOperationsAssuranceWatchSignoffNotFoundError("Assurance Watch signoff not found.")
            self._ensure_archive_not_zipped(queue_id, str(signoff.get("integrity_hash") or ""))
            export_dir = self.archive_dir(queue_id)
            manifest_path = export_dir / "trust-operations-assurance-watch-signoff-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if not manifest:
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff archive export is missing.")
            if manifest.get("source", {}).get("signoff_hash") != signoff.get("integrity_hash"):
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff archive export is stale.")
            zip_path = self.archive_zip_path(queue_id)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = watch_signoff_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"zip_path": str(zip_path), "filename": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size, "manifest_hash": manifest["integrity_hash"], "signoff_hash": signoff.get("integrity_hash")}
            self._append_history(queue_id, {"event_type": "watch_signoff_archive_zip_built", "created_at": now, "queue_id": queue_id, "signoff_hash": signoff.get("integrity_hash"), "zip_sha256": info["sha256"], "manifest_hash": info["manifest_hash"]})
            return _sanitize(info)

    def verify_archive_zip(self, queue_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.trust_operations_assurance_watch_signoff_verifier import verify_trust_operations_assurance_watch_signoff_archive_package

        payload = payload or {}
        report = verify_trust_operations_assurance_watch_signoff_archive_package(
            self.archive_zip_path(queue_id),
            strict=bool(payload.get("strict", False)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current=bool(payload.get("require_current", True)),
            watch_package_path=payload.get("watch_package_path") or payload.get("assurance_watch_package_path") or self.watch_store.watch_zip_path(queue_id),
            watch_verification_report_path=payload.get("watch_verification_report_path") or payload.get("assurance_watch_verification_report_path") or self.watch_store.verification_report_path(queue_id),
            hub_package_path=payload.get("hub_package_path"),
            hub_verification_report_path=payload.get("hub_verification_report_path"),
            continuous_assurance_report_path=payload.get("continuous_assurance_report_path") or payload.get("assurance_verification_report_path"),
        )
        _write_json(self.verification_report_path(queue_id), report)
        return report

    def _closeout_source(self, queue_id: str, payload: ImplementationDocument) -> tuple[ImplementationDocument, ImplementationDocument, ImplementationDocument, ImplementationDocument]:
        watch_zip = Path(payload.get("watch_package_path") or payload.get("assurance_watch_package_path") or self.watch_store.watch_zip_path(queue_id))
        watch_report_path = Path(payload.get("watch_verification_report_path") or payload.get("assurance_watch_verification_report_path") or self.watch_store.verification_report_path(queue_id))
        watch_report = _read_json_required(watch_report_path, "Assurance Watch verification report is required.")
        watch_manifest = _read_zip_json(watch_zip, "trust-operations-assurance-watch-manifest.json")
        hub_report_path = Path(payload.get("hub_verification_report_path") or "")
        hub_report = _read_json_required(hub_report_path, "Hub verification report is required.") if str(hub_report_path) else {}
        assurance_report_path = Path(payload.get("continuous_assurance_report_path") or payload.get("assurance_verification_report_path") or "")
        assurance_report = _read_json_required(assurance_report_path, "Continuous Assurance verification report is required.") if str(assurance_report_path) else {}
        hub_zip = Path(payload.get("hub_package_path") or "") if payload.get("hub_package_path") else None
        hub_manifest = _read_zip_json(hub_zip, "trust-operations-hub-manifest.json") if hub_zip else {}
        source = {
            "queue_id": queue_id,
            "queue_source_hash": watch_report.get("source_hash"),
            "watch_zip_sha256": _sha256(watch_zip),
            "watch_zip_size_bytes": os.stat(_fs_path(watch_zip)).st_size if watch_zip.exists() else None,
            "watch_manifest_hash": watch_manifest.get("integrity_hash"),
            "watch_verification_report_hash": verification_hash(watch_report),
            "watch_verification_status": watch_report.get("status"),
            "watch_clear": watch_report.get("clear"),
            "watch_overdue_count": int(watch_report.get("overdue_count") or 0),
            "watch_blocking_action_count": int(watch_report.get("blocking_action_count") or 0),
            "hub_zip_sha256": _sha256(hub_zip) if hub_zip else watch_report.get("hub_zip_sha256"),
            "hub_manifest_hash": hub_manifest.get("integrity_hash") or hub_report.get("manifest_hash"),
            "hub_verification_report_hash": verification_hash(hub_report) if hub_report else _first_hash(watch_report.get("hub_verification_report_hashes")),
            "hub_verification_status": hub_report.get("status") if hub_report else None,
            "continuous_assurance_report_hash": verification_hash(assurance_report) if assurance_report else _first_hash(watch_report.get("assurance_verification_report_hashes")),
            "continuous_assurance_status": assurance_report.get("status") if assurance_report else None,
        }
        return source, watch_report, hub_report, assurance_report

    def _closeout_blockers(self, source: ImplementationDocument, watch_report: ImplementationDocument, hub_report: ImplementationDocument, assurance_report: ImplementationDocument) -> list[ImplementationDocument]:
        blockers: list[dict[str, Any]] = []
        if watch_report.get("package_type") != "musicforge_trust_operations_assurance_watch_verification":
            blockers.append(_blocker("watch_verification_package_type", "Assurance Watch verification report package_type is invalid."))
        if watch_report.get("status") != "passed":
            blockers.append(_blocker("watch_verification_failed", "Assurance Watch verification report is not passed."))
        if source.get("watch_zip_sha256") != watch_report.get("zip_sha256") or source.get("watch_zip_size_bytes") != watch_report.get("zip_size_bytes") or source.get("watch_manifest_hash") != watch_report.get("manifest_hash"):
            blockers.append(_blocker("watch_verification_stale", "Assurance Watch verification report does not bind the current Watch ZIP."))
        if watch_report.get("clear") is not True or int(watch_report.get("overdue_count") or 0) != 0 or int(watch_report.get("blocking_action_count") or 0) != 0:
            blockers.append(_blocker("watch_not_clear", "Assurance Watch queue is not clear."))
        if hub_report:
            if hub_report.get("status") != "passed":
                blockers.append(_blocker("hub_verification_failed", "Hub verification report is not passed."))
            if verification_hash(hub_report) not in {str(item) for item in watch_report.get("hub_verification_report_hashes", []) if item}:
                blockers.append(_blocker("hub_verification_not_bound", "Assurance Watch verification does not bind the current Hub verification report."))
        if assurance_report:
            if assurance_report.get("status") != "passed":
                blockers.append(_blocker("continuous_assurance_failed", "Continuous Assurance verification report is not passed."))
            if verification_hash(assurance_report) not in {str(item) for item in watch_report.get("assurance_verification_report_hashes", []) if item}:
                blockers.append(_blocker("continuous_assurance_not_bound", "Assurance Watch verification does not bind the Continuous Assurance verification report."))
        return blockers

    def _ensure_signoff_current(self, queue_id: str, signoff: ImplementationDocument, payload: ImplementationDocument) -> None:
        if signoff.get("integrity_hash") != watch_signoff_hash(signoff):
            raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff integrity failed.")
        current_source, _watch_report, _hub_report, _assurance_report = self._closeout_source(queue_id, payload)
        signoff_source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
        for key in ("watch_zip_sha256", "watch_manifest_hash", "watch_verification_report_hash", "hub_zip_sha256", "hub_manifest_hash", "hub_verification_report_hash", "continuous_assurance_report_hash"):
            if signoff_source.get(key) != current_source.get(key):
                raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff source is stale. Reset before archiving.")

    def _archive_report(self, queue_id: str, signoff: ImplementationDocument, closeout: ImplementationDocument, now: str) -> ImplementationDocument:
        report = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE,
            "queue_id": queue_id,
            "created_at": now,
            "status": "passed",
            "signoff_hash": signoff.get("integrity_hash"),
            "closeout_hash": closeout.get("integrity_hash"),
            "source_hash": stable_hash(signoff.get("source") if isinstance(signoff.get("source"), dict) else {}),
            "summary": closeout.get("summary") if isinstance(closeout.get("summary"), dict) else {},
            "warnings": [],
        }
        report["integrity_hash"] = watch_signoff_hash(report)
        return report

    def _source_summary(self, signoff: ImplementationDocument) -> ImplementationDocument:
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE,
            "queue_id": signoff.get("queue_id"),
            "source_hash": stable_hash(signoff.get("source") if isinstance(signoff.get("source"), dict) else {}),
            "source": signoff.get("source") if isinstance(signoff.get("source"), dict) else {},
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _watch_queue_summary(self, queue_id: str, signoff: ImplementationDocument) -> ImplementationDocument:
        queue = self.watch_store.read_queue(queue_id)
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_assurance_watch_queue_summary",
            "queue_id": queue_id,
            "signoff_hash": signoff.get("integrity_hash"),
            "queue_hash": queue.get("integrity_hash"),
            "source_hash": queue.get("source_hash"),
            "status": queue.get("status"),
            "summary": queue.get("summary") if isinstance(queue.get("summary"), dict) else {},
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _drift_action_pack_summary(self, queue_id: str, signoff: ImplementationDocument) -> ImplementationDocument:
        action_pack = _read_json_default(self.watch_store.action_pack_path(queue_id), default={})
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_assurance_watch_drift_action_pack_summary",
            "queue_id": queue_id,
            "signoff_hash": signoff.get("integrity_hash"),
            "action_pack_hash": action_pack.get("integrity_hash"),
            "status": action_pack.get("status"),
            "summary": action_pack.get("summary") if isinstance(action_pack.get("summary"), dict) else {},
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _external_summary(self, signoff: ImplementationDocument) -> ImplementationDocument:
        source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": "musicforge_trust_operations_assurance_watch_signoff_external_verification_summary",
            "queue_id": signoff.get("queue_id"),
            "signoff_hash": signoff.get("integrity_hash"),
            "source": source,
            "items": [
                {"component_type": "assurance_watch", "zip_sha256": source.get("watch_zip_sha256"), "manifest_hash": source.get("watch_manifest_hash"), "verification_report_hash": source.get("watch_verification_report_hash"), "status": "passed"},
                {"component_type": "hub", "zip_sha256": source.get("hub_zip_sha256"), "manifest_hash": source.get("hub_manifest_hash"), "verification_report_hash": source.get("hub_verification_report_hash"), "status": "passed"},
                {"component_type": "continuous_assurance", "verification_report_hash": source.get("continuous_assurance_report_hash"), "status": "passed"},
            ],
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _change_requests_doc(self, queue_id: str, signoff: ImplementationDocument) -> ImplementationDocument:
        rows = self.list_change_requests(queue_id)
        doc = {
            "schema_version": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE,
            "queue_id": queue_id,
            "signoff_hash": signoff.get("integrity_hash"),
            "change_requests": rows,
            "summary": {"change_request_count": len(rows), "applied_count": sum(1 for item in rows if item.get("status") == "applied")},
        }
        doc["integrity_hash"] = watch_signoff_hash(doc)
        return doc

    def _read_change_request(self, queue_id: str, change_request_id: str) -> ImplementationDocument:
        request = _read_json_default(self.change_request_path(queue_id, change_request_id), default={})
        if not request:
            raise TrustOperationsAssuranceWatchSignoffNotFoundError(f"Assurance Watch change request not found: {change_request_id}")
        return request

    def _ensure_change_request_integrity(self, request: ImplementationDocument) -> None:
        if request.get("integrity_hash") != watch_signoff_hash(request):
            raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch change request integrity failed.")

    def _history_events(self, queue_id: str) -> list[ImplementationDocument]:
        path = self.history_path(queue_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in _read_text(path).splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(_sanitize(item))
        return rows

    def _signoff_state(self, queue_id: str) -> ImplementationDocument:
        active_hash: str | None = None
        active_id: str | None = None
        for event in self._history_events(queue_id):
            event_type = event.get("event_type")
            signoff_hash = str(event.get("signoff_hash") or "")
            if event_type == "watch_signoff_created" and signoff_hash:
                active_hash = signoff_hash
                active_id = str(event.get("signoff_id") or "")
            elif event_type == "watch_signoff_reset" and signoff_hash and signoff_hash == active_hash:
                active_hash = None
                active_id = None
        return {"status": "signed" if active_hash else "unsigned", "signoff_hash": active_hash, "signoff_id": active_id}

    def _ensure_unsigned(self, queue_id: str, action: str) -> None:
        if self._signoff_state(queue_id).get("status") == "signed":
            raise TrustOperationsAssuranceWatchSignoffStateError(f"Assurance Watch signoff is signed. Reset with an approved Change Request before attempting to {action}.")

    def _history_has_event(self, queue_id: str, event_type: str, signoff_hash: str) -> bool:
        return any(item.get("event_type") == event_type and item.get("signoff_hash") == signoff_hash for item in self._history_events(queue_id))

    def _ensure_archive_not_exported(self, queue_id: str, signoff_hash: str) -> None:
        if self._history_has_event(queue_id, "watch_signoff_archive_exported", signoff_hash):
            raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff archive was already exported for this signoff. Reset before rebuilding archive.")

    def _ensure_archive_not_zipped(self, queue_id: str, signoff_hash: str) -> None:
        if self._history_has_event(queue_id, "watch_signoff_archive_zip_built", signoff_hash):
            raise TrustOperationsAssuranceWatchSignoffStateError("Assurance Watch signoff archive ZIP was already built for this signoff. Reset before rebuilding archive ZIP.")

    def _append_history(self, queue_id: str, payload: ImplementationDocument) -> None:
        events = self._history_events(queue_id)
        event = _sanitize(payload)
        event["previous_event_hash"] = events[-1].get("event_hash") if events else None
        event["payload_hash"] = watch_signoff_history_event_payload_hash(event)
        event["event_hash"] = watch_signoff_history_event_hash(event)
        _append_jsonl(self.history_path(queue_id), event)














def _history_hash(events: list[ImplementationDocument]) -> str:
    return stable_hash({"events": events})


def _blocker(code: str, message: str) -> ImplementationDocument:
    item = {"code": code, "message": message, "severity": "blocking"}
    item["integrity_hash"] = stable_hash(item)
    return item


def _read_json_required(path: Path, message: str) -> ImplementationDocument:
    if not path.exists():
        raise TrustOperationsAssuranceWatchSignoffStateError(message)
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TrustOperationsAssuranceWatchSignoffStateError(message) from exc


def _read_zip_json(zip_path: Path | None, entry: str) -> ImplementationDocument:
    if not zip_path:
        raise TrustOperationsAssuranceWatchSignoffStateError(f"Required ZIP entry is missing or invalid: {entry}")
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrustOperationsAssuranceWatchSignoffStateError(f"Required ZIP entry is missing or invalid: {entry}") from exc


def _read_json_default(path: Path, *, default: ImplementationDocument) -> ImplementationDocument:
    try:
        if not path or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    _mkdir(path.parent)
    return write_json(path, _sanitize(payload))


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text(
        "MusicForge Trust Operations Assurance Watch Signoff Archive\n"
        "This package contains signed local continuous assurance watch closeout evidence.\n",
        encoding="utf-8",
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _write_zip(zip_path: Path, root: Path) -> None:
    _mkdir(zip_path.parent)
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_hash(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if item:
                return str(item)
    if value:
        return str(value)
    return None


def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes: list[int] = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"


def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
