from __future__ import annotations

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
from song_agent.domains.trust.release_portfolio_governance import PORTFOLIO_GOVERNANCE_BLOCKED_KEYS, ReleasePortfolioGovernanceStore, action_plan_integrity_ok, execution_report_integrity_ok, governance_manifest_integrity_hash, governance_manifest_integrity_ok, manual_action_list_integrity_ok, queue_integrity_ok, queue_summary
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_portfolio_governance_signoff_contracts import ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS, CHANGE_REQUEST_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS, SIGNOFF_HASH_EXCLUDE_KEYS, governance_archive_manifest_hash, governance_change_request_hash, governance_change_request_integrity_ok, governance_signoff_hash


PORTFOLIO_GOVERNANCE_SIGNOFF_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_ARCHIVE_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_CHANGE_REQUEST_SCHEMA_VERSION = 1




SIGNED_STATUSES = {"signed", "force_signed"}
ACK_RESOLUTIONS = {"accepted_for_followup", "waived", "already_handled"}


class ReleasePortfolioGovernanceSignoffError(ValueError):
    pass


class ReleasePortfolioGovernanceSignoffNotFoundError(ReleasePortfolioGovernanceSignoffError):
    pass


class ReleasePortfolioGovernanceSignoffStateError(ReleasePortfolioGovernanceSignoffError):
    pass


class ReleasePortfolioGovernanceSignoffStore:
    def __init__(self, *, governance_store: ReleasePortfolioGovernanceStore) -> None:
        self.governance_store = governance_store
        self.lock = threading.RLock()

    def queue_dir(self, queue_id: str) -> Path:
        return self.governance_store.queue_dir(queue_id)

    def signoff_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "signoff.json"

    def history_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "signoff-history.jsonl"

    def change_requests_root(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "change-requests"

    def change_request_path(self, queue_id: str, change_request_id: str) -> Path:
        return self.change_requests_root(queue_id) / f"{_validate_change_request_id(change_request_id)}.json"

    def change_request_events_path(self, queue_id: str) -> Path:
        return self.change_requests_root(queue_id) / "pgcr-events.jsonl"

    def archive_export_dir(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "governance-archive"

    def archive_zip_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "governance-archive.zip"

    def archive_verification_report_path(self, queue_id: str) -> Path:
        return self.queue_dir(queue_id) / "governance-archive-verification-report.json"

    def read_signoff(self, queue_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.signoff_path(queue_id)
        if not path.exists():
            return default if default is not None else {}
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def get_signoff(self, queue_id: str) -> dict[str, Any]:
        signoff = self.read_signoff(queue_id, default={})
        if not signoff:
            raise ReleasePortfolioGovernanceSignoffNotFoundError("Release Portfolio Governance Signoff does not exist.")
        return signoff

    def signoff_summary(self, queue_id: str, *, signoff: dict[str, Any] | None = None) -> dict[str, Any]:
        signoff = signoff if signoff is not None else self.read_signoff(queue_id, default={})
        current_source_hash = None
        stale = False
        if signoff:
            try:
                queue = self.governance_store.get_queue(queue_id)
                current = self.governance_store._current_source(str(queue.get("portfolio_id") or ""))  # noqa: SLF001
                current_source_hash = stable_hash(current)
                source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
                stale = bool(source.get("current_source_hash") and current_source_hash and str(source.get("current_source_hash")) != current_source_hash)
            except Exception:
                stale = False
        return governance_signoff_summary(signoff, current_source_hash=current_source_hash, stale=stale)

    def gate(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        now = now or now_iso()
        force = bool(payload.get("force", False))
        override_reason = sanitize_sensitive_text(str(payload.get("override_reason") or "").strip())
        requirements = _requirements(payload)
        manual_acknowledgements = _manual_acknowledgements(payload.get("manual_acknowledgements"))
        queue = self.governance_store.get_queue(queue_id)
        plan = self.governance_store.read_action_plan(queue_id, default={})
        execution = self.governance_store.read_execution_report(queue_id, default={})
        manual = self.governance_store.read_manual_action_list(queue_id, default={})
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        queue_ok = queue_integrity_ok(queue)
        plan_ok = action_plan_integrity_ok(plan)
        execution_ok = execution_report_integrity_ok(execution)
        manual_ok = manual_action_list_integrity_ok(manual)
        _maybe_block(blockers, "queue_integrity", not queue_ok, "Governance Queue integrity failed.")
        _maybe_block(blockers, "action_plan_integrity", not plan_ok, "Governance Action Plan integrity failed.")
        _maybe_block(blockers, "execution_report_integrity", not execution_ok, "Governance Execution Report integrity failed.")
        _maybe_block(blockers, "manual_action_list_integrity", not manual_ok, "Governance Manual Action List integrity failed.")

        source_state = self._source_state(queue, execution)
        _maybe_block(blockers, "queue_source_current", not source_state.get("current_or_documented"), "Portfolio Governance Queue source is stale. Refresh Portfolio Audit and create a new queue.")

        export_manifest = self._read_export_manifest(queue_id, blockers)
        zip_info = self._zip_evidence(queue_id, queue, blockers)
        verification = self._read_queue_verification(queue_id, zip_info, export_manifest, blockers, warnings)

        summary = execution.get("summary") if isinstance(execution.get("summary"), dict) else {}
        failed = int(summary.get("failed") or 0)
        blocked = int(summary.get("blocked") or 0)
        manual_required = int(summary.get("manual_required") or 0)
        if failed:
            blockers.append(_blocker("failed_safe_actions", "Governance Queue has failed safe actions."))
        if blocked:
            blockers.append(_blocker("blocked_actions", "Governance Queue has blocked actions."))

        manual_ids = _manual_required_ids(plan)
        acknowledged_ids = {str(item.get("item_id") or "") for item in manual_acknowledgements if str(item.get("item_id") or "")}
        missing_ack = sorted(manual_ids - acknowledged_ids)
        if requirements["require_manual_acknowledgement"] and missing_ack:
            item = _blocker("manual_acknowledgement_missing", "Manual-required governance actions need acknowledgement: " + ", ".join(missing_ack[:8]))
            if force:
                warnings.append({**item, "severity": "warning"})
            else:
                blockers.append(item)
        if force and not override_reason:
            blockers.append(_blocker("override_reason_missing", "override_reason is required for force Portfolio Governance Signoff."))

        signable = not blockers and (not warnings or force)
        status = "passed" if not blockers and not warnings else "warning" if signable else "failed"
        gate = {
            "schema_version": PORTFOLIO_GOVERNANCE_SIGNOFF_SCHEMA_VERSION,
            "queue_id": queue_id,
            "portfolio_id": queue.get("portfolio_id"),
            "generated_at": now,
            "status": status,
            "signable": signable,
            "force": force,
            "hard_blocked": bool(blockers),
            "requirements": requirements,
            "source": source_state,
            "evidence": {
                "queue_integrity_hash": queue.get("integrity_hash"),
                "action_plan_integrity_hash": plan.get("integrity_hash"),
                "execution_report_integrity_hash": execution.get("integrity_hash"),
                "manual_action_list_integrity_hash": manual.get("integrity_hash"),
                "queue_export_manifest_hash": export_manifest.get("integrity_hash"),
                "queue_zip_sha256": zip_info.get("sha256"),
                "queue_zip_size_bytes": zip_info.get("size_bytes"),
                "queue_verification_report_hash": stable_hash(verification) if verification else None,
            },
            "summary": {
                **queue_summary(queue, execution),
                "manual_acknowledgement_count": len(manual_acknowledgements),
                "missing_acknowledgement_count": len(missing_ack),
            },
            "manual_acknowledgements": manual_acknowledgements,
            "blockers": blockers,
            "warnings": warnings,
        }
        gate["source_hash"] = stable_hash({"source": gate["source"], "evidence": gate["evidence"], "summary": gate["summary"], "requirements": requirements})
        return sanitize_metadata(gate, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def signoff(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            existing = self.read_signoff(queue_id, default={})
            if governance_signoff_summary(existing).get("status") in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceSignoffStateError("Portfolio Governance Queue is already signed off. Reset Governance Signoff before signing again.")
            gate = self.gate(queue_id, payload, now=now)
            if not gate.get("signable"):
                blockers = gate.get("blockers") if isinstance(gate.get("blockers"), list) else []
                detail = str((blockers[0] if blockers and isinstance(blockers[0], dict) else {}).get("message") or "Portfolio Governance Signoff gate failed.")
                raise ReleasePortfolioGovernanceSignoffStateError(f"Portfolio Governance Signoff gate failed: {detail}")
            force = bool(payload.get("force", False))
            status = "force_signed" if force and gate.get("status") != "passed" else "signed"
            signoff = {
                "schema_version": PORTFOLIO_GOVERNANCE_SIGNOFF_SCHEMA_VERSION,
                "signoff_id": self._reserve_signoff_id(queue_id),
                "queue_id": queue_id,
                "portfolio_id": gate.get("portfolio_id"),
                "status": status,
                "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
                "signed_at": now,
                "force": status == "force_signed",
                "override_reason": sanitize_sensitive_text(str(payload.get("override_reason") or "").strip()) or None,
                "requirements": gate.get("requirements", {}),
                "source": gate.get("source", {}),
                "evidence": gate.get("evidence", {}),
                "summary": gate.get("summary", {}),
                "manual_acknowledgements": gate.get("manual_acknowledgements", []),
                "checks": {"blockers": gate.get("blockers", []), "warnings": gate.get("warnings", [])},
                "gate_hash": gate.get("source_hash"),
            }
            signoff["integrity_hash"] = governance_signoff_hash(signoff)
            self.queue_dir(queue_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.signoff_path(queue_id), signoff)
            self._append_history(queue_id, "signed", {"status": status, "signoff_id": signoff["signoff_id"], "signed_by": signoff.get("signed_by")}, now=now)
            self.governance_store._append_event(queue_id, "governance_signoff_signed", {"status": status, "signoff_id": signoff["signoff_id"]}, now=now)  # noqa: SLF001
            return signoff

    def reset_signoff(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
        if len(reason) < 8:
            raise ReleasePortfolioGovernanceSignoffStateError("reason must be at least 8 characters.")
        change_request_id = str(payload.get("change_request_id") or "").strip()
        if not change_request_id:
            raise ReleasePortfolioGovernanceSignoffStateError("Approved Portfolio Governance Change Request is required before reset.")
        with self.lock:
            request = self.get_change_request(queue_id, change_request_id)
            if not governance_change_request_integrity_ok(request):
                raise ReleasePortfolioGovernanceSignoffStateError("Portfolio Governance Change Request integrity failed.")
            if request.get("status") != "approved":
                raise ReleasePortfolioGovernanceSignoffStateError("Portfolio Governance Change Request must be approved before reset.")
            now = now or now_iso()
            existing = self.read_signoff(queue_id, default={})
            reset = {
                "schema_version": PORTFOLIO_GOVERNANCE_SIGNOFF_SCHEMA_VERSION,
                "queue_id": queue_id,
                "portfolio_id": existing.get("portfolio_id") or self.governance_store.get_queue(queue_id).get("portfolio_id"),
                "status": "reset",
                "reset_at": now,
                "reset_by": _safe_text(payload.get("reset_by"), 120) or "local-user",
                "reason": reason,
                "change_request_id": change_request_id,
                "previous_status": existing.get("status") if existing else "not_signed",
                "previous_integrity_hash": existing.get("integrity_hash") if existing else None,
            }
            reset["integrity_hash"] = governance_signoff_hash(reset)
            _write_json(self.signoff_path(queue_id), reset)
            request["status"] = "applied"
            request["updated_at"] = now
            request["application"] = {"applied_at": now, "applied_by": reset["reset_by"], "applied_signoff_reset_hash": reset["integrity_hash"]}
            request["integrity_hash"] = governance_change_request_hash(request)
            _write_json(self.change_request_path(queue_id, change_request_id), request)
            self._append_change_event(queue_id, "applied", request, now=now)
            self._append_history(queue_id, "reset", {"change_request_id": change_request_id, "reason": reason, "reset_hash": reset["integrity_hash"]}, now=now)
            self.governance_store._append_event(queue_id, "governance_signoff_reset", {"change_request_id": change_request_id, "reset_hash": reset["integrity_hash"]}, now=now)  # noqa: SLF001
            return reset

    def export_archive(self, queue_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            signoff = self.get_signoff(queue_id)
            summary = self.signoff_summary(queue_id, signoff=signoff)
            if summary.get("status") not in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceSignoffStateError("Governance Archive requires signed Portfolio Governance Signoff.")
            if not summary.get("integrity_ok") or summary.get("stale"):
                raise ReleasePortfolioGovernanceSignoffStateError("Portfolio Governance Signoff is stale or integrity failed. Reset and sign again.")
            queue = self.governance_store.get_queue(queue_id)
            plan = self.governance_store.read_action_plan(queue_id, default={})
            execution = self.governance_store.read_execution_report(queue_id, default={})
            manual = self.governance_store.read_manual_action_list(queue_id, default={})
            verification = _read_json_default(self.governance_store.verification_report_path(queue_id), default={})
            change_requests = {"queue_id": queue_id, "items": self.list_change_requests(queue_id), "summary": self.change_request_summary(queue_id)}
            change_requests["payload_hash"] = stable_hash(change_requests)
            before = {"queue_id": queue_id, "portfolio_id": queue.get("portfolio_id"), "source": queue.get("source"), "source_hash": queue.get("source_hash")}
            after = {"queue_id": queue_id, "portfolio_id": queue.get("portfolio_id"), "source": self.governance_store._current_source(str(queue.get("portfolio_id") or ""))}  # noqa: SLF001
            after["source_hash"] = stable_hash(after.get("source", {}))
            export_dir = self.archive_export_dir(queue_id).resolve()
            queue_dir = self.queue_dir(queue_id).resolve()
            _ensure_within(queue_dir, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            _write_json(export_dir / "queue.json", queue)
            _write_json(export_dir / "action-plan.json", plan)
            _write_json(export_dir / "execution-report.json", execution)
            _write_json(export_dir / "manual-action-list.json", manual)
            _write_json(export_dir / "queue-verification-report.json", verification)
            _write_json(export_dir / "governance-signoff.json", signoff)
            _write_json(export_dir / "change-requests.json", change_requests)
            _write_json(export_dir / "portfolio-before-summary.json", before)
            _write_json(export_dir / "portfolio-after-summary.json", after)
            _write_closeout(export_dir, signoff, execution, change_requests)
            _write_readme(export_dir, signoff)
            names = [
                "queue.json",
                "action-plan.json",
                "execution-report.json",
                "manual-action-list.json",
                "queue-verification-report.json",
                "governance-signoff.json",
                "change-requests.json",
                "portfolio-before-summary.json",
                "portfolio-after-summary.json",
                "GOVERNANCE_CLOSEOUT.md",
                "README.txt",
            ]
            files = [_file_record(export_dir, export_dir / name) for name in names]
            manifest = {
                "schema_version": PORTFOLIO_GOVERNANCE_ARCHIVE_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_archive",
                "tool": {"name": "MusicForge Release Portfolio Governance Archive", "version": __version__},
                "queue_id": queue_id,
                "portfolio_id": queue.get("portfolio_id"),
                "signoff_id": signoff.get("signoff_id"),
                "created_at": now,
                "source_hash": signoff.get("source", {}).get("current_source_hash") if isinstance(signoff.get("source"), dict) else None,
                "summary": summary,
                "sidecars": {
                    "queue": {"payload_hash": queue.get("integrity_hash")},
                    "action_plan": {"payload_hash": plan.get("integrity_hash")},
                    "execution_report": {"payload_hash": execution.get("integrity_hash")},
                    "manual_action_list": {"payload_hash": manual.get("integrity_hash")},
                    "queue_verification_report": {"payload_hash": stable_hash(verification)},
                    "governance_signoff": {"payload_hash": signoff.get("integrity_hash")},
                    "change_requests": {"payload_hash": change_requests.get("payload_hash")},
                },
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
            }
            manifest["integrity_hash"] = governance_archive_manifest_hash(manifest)
            write_json(export_dir / "manifest.json", sanitize_metadata(manifest, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS))
            self.governance_store._append_event(queue_id, "governance_archive_exported", {"status": summary.get("status")}, now=now)  # noqa: SLF001
            return sanitize_metadata(manifest, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def build_archive_zip(self, queue_id: str, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            export_dir = self.archive_export_dir(queue_id).resolve()
            queue_dir = self.queue_dir(queue_id).resolve()
            zip_path = self.archive_zip_path(queue_id).resolve()
            _ensure_within(queue_dir, export_dir)
            _ensure_within(queue_dir, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_archive(queue_id, now=now)
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = governance_archive_manifest_hash(manifest)
            write_json(export_dir / "manifest.json", sanitize_metadata(manifest, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS))
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
            return sanitize_metadata(info, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def read_archive_manifest(self, queue_id: str) -> dict[str, Any]:
        path = self.archive_export_dir(queue_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceSignoffNotFoundError("Portfolio Governance Archive export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def archive_summary(self, queue_id: str) -> dict[str, Any]:
        manifest = self.read_archive_manifest(queue_id) if (self.archive_export_dir(queue_id) / "manifest.json").exists() else {}
        verification = _read_json_default(self.archive_verification_report_path(queue_id), default={})
        zip_path = self.archive_zip_path(queue_id)
        return sanitize_metadata(
            {
                "status": manifest.get("summary", {}).get("status") if isinstance(manifest.get("summary"), dict) else "missing",
                "queue_id": queue_id,
                "signoff_id": manifest.get("signoff_id"),
                "manifest_hash": manifest.get("integrity_hash"),
                "zip_exists": zip_path.exists(),
                "zip_sha256": _sha256(zip_path) if zip_path.exists() else None,
                "verification_status": verification.get("status") or "missing",
            },
            blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS,
        )

    def list_change_requests(self, queue_id: str, *, include_archived: bool = True) -> list[dict[str, Any]]:
        root = self.change_requests_root(queue_id)
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("pgcr-*.json")) if root.exists() else []:
            try:
                item = sanitize_metadata(read_json(path), blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)
            except Exception:
                continue
            if not include_archived and item.get("status") == "archived":
                continue
            rows.append(item)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("requested_at") or ""), reverse=True)

    def get_change_request(self, queue_id: str, change_request_id: str) -> dict[str, Any]:
        path = self.change_request_path(queue_id, change_request_id)
        if not path.exists():
            raise ReleasePortfolioGovernanceSignoffNotFoundError("Portfolio Governance Change Request does not exist.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def create_change_request(self, queue_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
        if len(reason) < 8:
            raise ReleasePortfolioGovernanceSignoffStateError("Change Request reason must be at least 8 characters.")
        with self.lock:
            now = now or now_iso()
            queue = self.governance_store.get_queue(queue_id)
            signoff = self.read_signoff(queue_id, default={})
            change_request_id = self._reserve_change_request_id(queue_id)
            item = {
                "schema_version": PORTFOLIO_GOVERNANCE_CHANGE_REQUEST_SCHEMA_VERSION,
                "change_request_id": change_request_id,
                "queue_id": queue_id,
                "portfolio_id": queue.get("portfolio_id"),
                "type": _safe_text(payload.get("type"), 80) or "reset_signoff",
                "status": "requested",
                "requested_by": _safe_text(payload.get("requested_by") or payload.get("created_by"), 120) or "local-user",
                "requested_at": now,
                "updated_at": now,
                "reason": reason,
                "impact": {"affected_signoff_id": signoff.get("signoff_id"), "affected_queue_id": queue_id},
                "approval": {"approved_by": None, "approved_at": None, "approval_note": None},
                "application": {"applied_at": None, "applied_by": None, "applied_signoff_reset_hash": None},
                "source": {"signoff_hash": signoff.get("integrity_hash"), "queue_hash": queue.get("integrity_hash")},
            }
            item["payload_hash"] = stable_hash({key: value for key, value in item.items() if key not in {"payload_hash", "integrity_hash", "updated_at"}})
            item["integrity_hash"] = governance_change_request_hash(item)
            self.change_requests_root(queue_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.change_request_path(queue_id, change_request_id), item)
            self._append_change_event(queue_id, "created", item, now=now)
            return item

    def update_change_request_status(self, queue_id: str, change_request_id: str, action: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            item = self.get_change_request(queue_id, change_request_id)
            current = str(item.get("status") or "")
            if not governance_change_request_integrity_ok(item):
                raise ReleasePortfolioGovernanceSignoffStateError("Portfolio Governance Change Request integrity failed.")
            if action == "approve":
                if current != "requested":
                    raise ReleasePortfolioGovernanceSignoffStateError("Only requested Change Requests can be approved.")
                approved_by = _safe_text(payload.get("approved_by") or payload.get("reviewed_by"), 120)
                if not approved_by:
                    raise ReleasePortfolioGovernanceSignoffStateError("approved_by is required.")
                item["status"] = "approved"
                item["approval"] = {"approved_by": approved_by, "approved_at": now, "approval_note": sanitize_sensitive_text(str(payload.get("approval_note") or payload.get("notes") or "").strip()) or None}
            elif action == "reject":
                if current != "requested":
                    raise ReleasePortfolioGovernanceSignoffStateError("Only requested Change Requests can be rejected.")
                reason = sanitize_sensitive_text(str(payload.get("reason") or payload.get("notes") or "").strip())
                if len(reason) < 8:
                    raise ReleasePortfolioGovernanceSignoffStateError("Rejection reason must be at least 8 characters.")
                item["status"] = "rejected"
                item["approval"] = {"approved_by": None, "approved_at": None, "approval_note": reason}
            elif action == "archive":
                if current not in {"rejected", "applied"}:
                    raise ReleasePortfolioGovernanceSignoffStateError("Only rejected or applied Change Requests can be archived.")
                item["status"] = "archived"
            else:
                raise ReleasePortfolioGovernanceSignoffStateError("Unknown Change Request action.")
            item["updated_at"] = now
            item["integrity_hash"] = governance_change_request_hash(item)
            _write_json(self.change_request_path(queue_id, change_request_id), item)
            self._append_change_event(queue_id, action, item, now=now)
            return item

    def change_request_summary(self, queue_id: str) -> dict[str, Any]:
        rows = self.list_change_requests(queue_id)
        counts: dict[str, int] = {}
        for item in rows:
            counts[str(item.get("status") or "unknown")] = counts.get(str(item.get("status") or "unknown"), 0) + 1
        latest = rows[0] if rows else {}
        summary = {"queue_id": queue_id, "count": len(rows), "status_counts": counts, "latest_change_request_id": latest.get("change_request_id"), "approved_count": counts.get("approved", 0)}
        summary["summary_hash"] = stable_hash(summary)
        return sanitize_metadata(summary, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def _source_state(self, queue: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
        current = self.governance_store._current_source(str(queue.get("portfolio_id") or ""))  # noqa: SLF001
        current_hash = stable_hash(current)
        post = execution.get("post_conditions") if isinstance(execution.get("post_conditions"), dict) else {}
        queue_source_hash = str(queue.get("source_hash") or "")
        source_current = not bool(current.get("stale")) and current_hash == queue_source_hash
        documented_run_drift = (
            execution_report_integrity_ok(execution)
            and str(execution.get("integrity_hash") or "") == str(queue.get("latest_execution_report_hash") or "")
            and str(post.get("pre_source_hash") or "") == queue_source_hash
            and str(post.get("post_source_hash") or "") == current_hash
            and bool(post.get("portfolio_refresh_required"))
        )
        return sanitize_metadata(
            {
                "queue_source_hash": queue_source_hash,
                "current_source_hash": current_hash,
                "documented_run_drift": documented_run_drift,
                "post_portfolio_refresh_required": bool(post.get("portfolio_refresh_required", False)),
                "post_portfolio_report_hash": post.get("post_portfolio_report_hash"),
                "current_source_stale": bool(current.get("stale")),
                "current_or_documented": bool(source_current or documented_run_drift),
            },
            blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS,
        )

    def _read_export_manifest(self, queue_id: str, blockers: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            manifest = self.governance_store.read_export_manifest(queue_id)
        except Exception:
            blockers.append(_blocker("queue_export_missing", "Governance Queue export manifest is missing."))
            return {}
        if not governance_manifest_integrity_ok(manifest):
            blockers.append(_blocker("queue_export_manifest_integrity", "Governance Queue export manifest integrity failed."))
        return manifest

    def _zip_evidence(self, queue_id: str, queue: dict[str, Any], blockers: list[dict[str, Any]]) -> dict[str, Any]:
        zip_path = self.governance_store.zip_path(queue_id)
        if not zip_path.exists():
            blockers.append(_blocker("queue_zip_missing", "Governance Queue ZIP is missing."))
            return {}
        sha = _sha256(zip_path)
        if queue.get("latest_zip_sha256") and str(queue.get("latest_zip_sha256")) != sha:
            blockers.append(_blocker("queue_zip_sha256", "Governance Queue ZIP sha256 does not match queue evidence."))
        return {"filename": zip_path.name, "sha256": sha, "size_bytes": zip_path.stat().st_size}

    def _read_queue_verification(self, queue_id: str, zip_info: dict[str, Any], export_manifest: dict[str, Any], blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
        path = self.governance_store.verification_report_path(queue_id)
        if not path.exists():
            blockers.append(_blocker("queue_verification_missing", "Governance Queue verification report is missing."))
            return {}
        report = _read_json_default(path, default={})
        status = str(report.get("status") or "")
        if status == "failed":
            blockers.append(_blocker("queue_verification_failed", "Governance Queue verification report failed."))
        elif status == "warning":
            warnings.append(_warning("queue_verification_warning", "Governance Queue verification report has warnings."))
        elif status != "passed":
            blockers.append(_blocker("queue_verification_status", f"Governance Queue verification status is {status or 'missing'}."))
        expected_zip_sha = str(zip_info.get("sha256") or "")
        report_zip_sha = str(report.get("zip_sha256") or (report.get("zip") if isinstance(report.get("zip"), dict) else {}).get("sha256") or "")
        if not report_zip_sha:
            blockers.append(_blocker("queue_verification_zip_sha256_missing", "Governance Queue verification report does not record the verified ZIP sha256. Re-run queue verification."))
        elif expected_zip_sha and report_zip_sha != expected_zip_sha:
            blockers.append(_blocker("queue_verification_zip_sha256", "Governance Queue verification report does not match the current Governance Queue ZIP. Re-run queue verification."))
        expected_zip_size = zip_info.get("size_bytes")
        report_zip_size = report.get("zip_size_bytes")
        if report_zip_size is None and isinstance(report.get("zip"), dict):
            report_zip_size = report["zip"].get("size_bytes")
        if report_zip_size is None:
            blockers.append(_blocker("queue_verification_zip_size_missing", "Governance Queue verification report does not record the verified ZIP size. Re-run queue verification."))
        elif expected_zip_size is not None and int(report_zip_size or 0) != int(expected_zip_size or 0):
            blockers.append(_blocker("queue_verification_zip_size", "Governance Queue verification report does not match the current Governance Queue ZIP size. Re-run queue verification."))
        expected_manifest_hash = str(export_manifest.get("integrity_hash") or "")
        report_manifest_hash = str(report.get("manifest_hash") or "")
        if not report_manifest_hash:
            blockers.append(_blocker("queue_verification_manifest_hash_missing", "Governance Queue verification report does not record the verified export manifest hash. Re-run queue verification."))
        elif expected_manifest_hash and report_manifest_hash != expected_manifest_hash:
            blockers.append(_blocker("queue_verification_manifest_hash", "Governance Queue verification report does not match the current Governance Queue export manifest. Re-run queue verification."))
        return report

    def _reserve_signoff_id(self, queue_id: str) -> str:
        used: set[int] = set()
        existing = self.read_signoff(queue_id, default={})
        if str(existing.get("signoff_id") or "").startswith("pgs-"):
            try:
                used.add(int(str(existing.get("signoff_id")).split("-")[-1]))
            except ValueError:
                pass
        path = self.history_path(queue_id)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                signoff_id = str((event.get("summary") if isinstance(event.get("summary"), dict) else {}).get("signoff_id") or "")
                if signoff_id.startswith("pgs-"):
                    try:
                        used.add(int(signoff_id.split("-")[-1]))
                    except ValueError:
                        pass
        return f"pgs-{(max(used) if used else 0) + 1:06d}"

    def _reserve_change_request_id(self, queue_id: str) -> str:
        root = self.change_requests_root(queue_id)
        root.mkdir(parents=True, exist_ok=True)
        existing: list[int] = []
        for path in root.glob("pgcr-*.json"):
            try:
                existing.append(int(path.stem.split("-")[-1]))
            except ValueError:
                pass
        return f"pgcr-{(max(existing) if existing else 0) + 1:06d}"

    def _append_history(self, queue_id: str, event_type: str, summary: dict[str, Any], *, now: str | None = None) -> None:
        path = self.history_path(queue_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"pgse-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _append_change_event(self, queue_id: str, event_type: str, item: dict[str, Any], *, now: str | None = None) -> None:
        path = self.change_request_events_path(queue_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"pgcre-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "change_request_id": item.get("change_request_id"), "status": item.get("status")}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")





def governance_signoff_integrity_ok(signoff: dict[str, Any] | None) -> bool:
    data = signoff if isinstance(signoff, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == governance_signoff_hash(data)


def governance_signoff_summary(signoff: dict[str, Any] | None, *, current_source_hash: str | None = None, stale: bool = False) -> dict[str, Any]:
    data = signoff if isinstance(signoff, dict) else {}
    if not data:
        return {"status": "not_signed", "integrity_ok": False, "stale": False}
    integrity_ok = governance_signoff_integrity_ok(data)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "queue_id": data.get("queue_id"),
            "portfolio_id": data.get("portfolio_id"),
            "signoff_id": data.get("signoff_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "force": bool(data.get("force")),
            "integrity_hash": data.get("integrity_hash"),
            "integrity_ok": integrity_ok,
            "payload_hash_ok": integrity_ok,
            "stale": stale,
            "current_source_hash": current_source_hash,
            "safe_completed": data.get("summary", {}).get("safe_completed") if isinstance(data.get("summary"), dict) else None,
            "manual_required": data.get("summary", {}).get("manual_required") if isinstance(data.get("summary"), dict) else None,
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS,
    )











def governance_archive_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == governance_archive_manifest_hash(data)


def _requirements(payload: dict[str, Any]) -> dict[str, bool]:
    raw = payload.get("requirements") if isinstance(payload.get("requirements"), dict) else {}
    return {
        "require_queue_verified": bool(raw.get("require_queue_verified", True)),
        "require_no_failed_actions": bool(raw.get("require_no_failed_actions", True)),
        "require_manual_acknowledgement": bool(raw.get("require_manual_acknowledgement", True)),
        "require_after_refresh_when_needed": bool(raw.get("require_after_refresh_when_needed", True)),
        "require_current_source": bool(raw.get("require_current_source", True)),
    }


def _manual_acknowledgements(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if not isinstance(item, dict):
            continue
        resolution = _safe_text(item.get("resolution"), 80)
        if resolution not in ACK_RESOLUTIONS:
            resolution = "accepted_for_followup"
        rows.append(
            {
                "item_id": _safe_text(item.get("item_id"), 80),
                "action_type": _safe_text(item.get("action_type"), 120),
                "resolution": resolution,
                "owner": _safe_text(item.get("owner"), 120) or "local-user",
                "due_note": sanitize_sensitive_text(str(item.get("due_note") or "").strip())[:200],
                "note": sanitize_sensitive_text(str(item.get("note") or "").strip())[:500],
            }
        )
    return rows


def _manual_required_ids(plan: dict[str, Any]) -> set[str]:
    return {str(item.get("item_id") or "") for item in plan.get("items", []) if isinstance(item, dict) and item.get("status") == "manual_required" and str(item.get("item_id") or "")}


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default if default is not None else {}
    value = read_json(path)
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)


def _write_json(path: Path, value: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS))


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    rel = _validate_relative_path(path.resolve().relative_to(root.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        resolved = path.resolve()
        _ensure_within(root.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(root.resolve()).as_posix())
        if entry in seen:
            raise ReleasePortfolioGovernanceSignoffStateError(f"Duplicate Governance Archive ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceSignoffStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceSignoffStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceSignoffStateError(f"Unsafe relative path: {value}.")
    return text


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceSignoffStateError("Refusing to operate outside Portfolio Governance Queue boundaries.") from exc


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
    if not text.startswith("pgcr-") or not text.replace("pgcr-", "", 1).isdigit():
        raise ReleasePortfolioGovernanceSignoffNotFoundError("Invalid Portfolio Governance Change Request id.")
    return text


def _maybe_block(blockers: list[dict[str, Any]], check_id: str, condition: bool, message: str) -> None:
    if condition:
        blockers.append(_blocker(check_id, message))


def _blocker(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "blocking", "message": message}


def _warning(check_id: str, message: str) -> dict[str, Any]:
    return {"check_id": check_id, "severity": "warning", "message": message}


def _write_closeout(export_dir: Path, signoff: dict[str, Any], execution: dict[str, Any], change_requests: dict[str, Any]) -> None:
    summary = execution.get("summary") if isinstance(execution.get("summary"), dict) else {}
    lines = [
        "MusicForge Portfolio Governance Closeout",
        "",
        f"Queue ID: {signoff.get('queue_id')}",
        f"Signoff Status: {signoff.get('status')}",
        f"Signed By: {signoff.get('signed_by') or '-'}",
        f"Signed At: {signoff.get('signed_at') or '-'}",
        f"Safe Completed: {summary.get('safe_completed', 0)}",
        f"Manual Required: {summary.get('manual_required', 0)}",
        f"Change Requests: {change_requests.get('summary', {}).get('count', 0) if isinstance(change_requests.get('summary'), dict) else 0}",
        "",
        "This package contains governance evidence only. It does not include credentials, provider secrets, audio assets, or platform account data.",
    ]
    (export_dir / "GOVERNANCE_CLOSEOUT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(export_dir: Path, signoff: dict[str, Any]) -> None:
    text = "\n".join(
        [
            "MusicForge Release Portfolio Governance Archive",
            "",
            f"Queue ID: {signoff.get('queue_id')}",
            f"Signoff Status: {signoff.get('status')}",
            "Verify with: python -m song_agent.cli verify-release-portfolio-governance-archive-package governance-archive.zip --strict --require-signed --json",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(text, encoding="utf-8")
