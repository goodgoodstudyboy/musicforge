# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_governance import PORTFOLIO_GOVERNANCE_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_BLOCKED_KEYS, ReleasePortfolioGovernanceStore as ReleasePortfolioGovernanceStore, action_plan_integrity_ok as action_plan_integrity_ok, execution_report_integrity_ok as execution_report_integrity_ok, governance_manifest_integrity_hash as governance_manifest_integrity_hash, governance_manifest_integrity_ok as governance_manifest_integrity_ok, manual_action_list_integrity_ok as manual_action_list_integrity_ok, queue_integrity_ok as queue_integrity_ok, queue_summary as queue_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_signoff_contracts import ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS as ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS, CHANGE_REQUEST_HASH_EXCLUDE_KEYS as CHANGE_REQUEST_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS, SIGNOFF_HASH_EXCLUDE_KEYS as SIGNOFF_HASH_EXCLUDE_KEYS, governance_archive_manifest_hash as governance_archive_manifest_hash, governance_change_request_hash as governance_change_request_hash, governance_change_request_integrity_ok as governance_change_request_integrity_ok, governance_signoff_hash as governance_signoff_hash

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

ReleasePortfolioGovernanceSignoffStateError = _make_deferred_global('ReleasePortfolioGovernanceSignoffStateError')
_blocker = _make_deferred_global('_blocker')
_read_json_default = _make_deferred_global('_read_json_default')
_safe_text = _make_deferred_global('_safe_text')
_sha256 = _make_deferred_global('_sha256')
_warning = _make_deferred_global('_warning')
_write_json = _make_deferred_global('_write_json')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceSignoffStateError, _blocker, _read_json_default, _safe_text, _sha256, _warning, _write_json
    ReleasePortfolioGovernanceSignoffStateError = namespace.get('ReleasePortfolioGovernanceSignoffStateError', ReleasePortfolioGovernanceSignoffStateError)
    _blocker = namespace.get('_blocker', _blocker)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _sha256 = namespace.get('_sha256', _sha256)
    _warning = namespace.get('_warning', _warning)
    _write_json = namespace.get('_write_json', _write_json)
    _bind_deferred_defaults(namespace)


PORTFOLIO_GOVERNANCE_SIGNOFF_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_ARCHIVE_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_CHANGE_REQUEST_SCHEMA_VERSION = 1
SIGNED_STATUSES = {"signed", "force_signed"}
ACK_RESOLUTIONS = {"accepted_for_followup", "waived", "already_handled"}




class ReleasePortfolioGovernanceSignoffStoreEvidenceMixin:
    def update_change_request_status(self, queue_id: str, change_request_id: str, action: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def change_request_summary(self, queue_id: str) -> DomainDocument:
        rows = self.list_change_requests(queue_id)
        counts: dict[str, int] = {}
        for item in rows:
            counts[str(item.get("status") or "unknown")] = counts.get(str(item.get("status") or "unknown"), 0) + 1
        latest = rows[0] if rows else {}
        summary = {"queue_id": queue_id, "count": len(rows), "status_counts": counts, "latest_change_request_id": latest.get("change_request_id"), "approved_count": counts.get("approved", 0)}
        summary["summary_hash"] = stable_hash(summary)
        return sanitize_metadata(summary, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def _source_state(self, queue: DomainDocument, execution: DomainDocument) -> DomainDocument:
        current = self.governance_store._current_source(str(queue.get("portfolio_id") or ""))  # noqa: SLF001
        current_hash = stable_hash(current)
        post = _as_document(execution.get("post_conditions"))
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

    def _read_export_manifest(self, queue_id: str, blockers: list[DomainDocument]) -> DomainDocument:
        try:
            manifest = self.governance_store.read_export_manifest(queue_id)
        except Exception:
            blockers.append(_blocker("queue_export_missing", "Governance Queue export manifest is missing."))
            return {}
        if not governance_manifest_integrity_ok(manifest):
            blockers.append(_blocker("queue_export_manifest_integrity", "Governance Queue export manifest integrity failed."))
        return manifest

    def _zip_evidence(self, queue_id: str, queue: DomainDocument, blockers: list[DomainDocument]) -> DomainDocument:
        zip_path = self.governance_store.zip_path(queue_id)
        if not zip_path.exists():
            blockers.append(_blocker("queue_zip_missing", "Governance Queue ZIP is missing."))
            return {}
        sha = _sha256(zip_path)
        if queue.get("latest_zip_sha256") and str(queue.get("latest_zip_sha256")) != sha:
            blockers.append(_blocker("queue_zip_sha256", "Governance Queue ZIP sha256 does not match queue evidence."))
        return {"filename": zip_path.name, "sha256": sha, "size_bytes": zip_path.stat().st_size}

    def _read_queue_verification(self, queue_id: str, zip_info: DomainDocument, export_manifest: DomainDocument, blockers: list[DomainDocument], warnings: list[DomainDocument]) -> DomainDocument:
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
        report_zip_sha = str(report.get("zip_sha256") or (_as_document(report.get("zip"))).get("sha256") or "")
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
                signoff_id = str((_as_document(event.get("summary"))).get("signoff_id") or "")
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

    def _append_history(self, queue_id: str, event_type: str, summary: DomainDocument, *, now: str | None = None) -> None:
        path = self.history_path(queue_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"pgse-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _append_change_event(self, queue_id: str, event_type: str, item: DomainDocument, *, now: str | None = None) -> None:
        path = self.change_request_events_path(queue_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"pgcre-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "change_request_id": item.get("change_request_id"), "status": item.get("status")}, blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
