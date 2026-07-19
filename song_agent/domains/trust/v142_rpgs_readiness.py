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

ReleasePortfolioGovernanceSignoffNotFoundError = _make_deferred_global('ReleasePortfolioGovernanceSignoffNotFoundError')
ReleasePortfolioGovernanceSignoffStateError = _make_deferred_global('ReleasePortfolioGovernanceSignoffStateError')
_blocker = _make_deferred_global('_blocker')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_manual_acknowledgements = _make_deferred_global('_manual_acknowledgements')
_manual_required_ids = _make_deferred_global('_manual_required_ids')
_maybe_block = _make_deferred_global('_maybe_block')
_read_json_default = _make_deferred_global('_read_json_default')
_requirements = _make_deferred_global('_requirements')
_safe_text = _make_deferred_global('_safe_text')
_sha256 = _make_deferred_global('_sha256')
_validate_change_request_id = _make_deferred_global('_validate_change_request_id')
_write_closeout = _make_deferred_global('_write_closeout')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_zip_entries = _make_deferred_global('_zip_entries')
governance_signoff_summary = _make_deferred_global('governance_signoff_summary')
key = _make_deferred_global('key')
name = _make_deferred_global('name')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceSignoffNotFoundError, ReleasePortfolioGovernanceSignoffStateError, _blocker, _ensure_within, _file_record, _manual_acknowledgements, _manual_required_ids
    global _maybe_block, _read_json_default, _requirements, _safe_text, _sha256, _validate_change_request_id, _write_closeout, _write_json
    global _write_readme, _zip_entries, governance_signoff_summary, key, name
    ReleasePortfolioGovernanceSignoffNotFoundError = namespace.get('ReleasePortfolioGovernanceSignoffNotFoundError', ReleasePortfolioGovernanceSignoffNotFoundError)
    ReleasePortfolioGovernanceSignoffStateError = namespace.get('ReleasePortfolioGovernanceSignoffStateError', ReleasePortfolioGovernanceSignoffStateError)
    _blocker = namespace.get('_blocker', _blocker)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _manual_acknowledgements = namespace.get('_manual_acknowledgements', _manual_acknowledgements)
    _manual_required_ids = namespace.get('_manual_required_ids', _manual_required_ids)
    _maybe_block = namespace.get('_maybe_block', _maybe_block)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _requirements = namespace.get('_requirements', _requirements)
    _safe_text = namespace.get('_safe_text', _safe_text)
    _sha256 = namespace.get('_sha256', _sha256)
    _validate_change_request_id = namespace.get('_validate_change_request_id', _validate_change_request_id)
    _write_closeout = namespace.get('_write_closeout', _write_closeout)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    governance_signoff_summary = namespace.get('governance_signoff_summary', governance_signoff_summary)
    key = namespace.get('key', key)
    name = namespace.get('name', name)
    _bind_deferred_defaults(namespace)


PORTFOLIO_GOVERNANCE_SIGNOFF_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_ARCHIVE_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_CHANGE_REQUEST_SCHEMA_VERSION = 1
SIGNED_STATUSES = {"signed", "force_signed"}
ACK_RESOLUTIONS = {"accepted_for_followup", "waived", "already_handled"}




class ReleasePortfolioGovernanceSignoffStoreReadinessMixin:
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

    def read_signoff(self, queue_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
        path = self.signoff_path(queue_id)
        if not path.exists():
            return default if default is not None else {}
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def get_signoff(self, queue_id: str) -> DomainDocument:
        signoff = self.read_signoff(queue_id, default={})
        if not signoff:
            raise ReleasePortfolioGovernanceSignoffNotFoundError("Release Portfolio Governance Signoff does not exist.")
        return signoff

    def signoff_summary(self, queue_id: str, *, signoff: DomainDocument | None = None) -> DomainDocument:
        signoff = signoff if signoff is not None else self.read_signoff(queue_id, default={})
        current_source_hash = None
        stale = False
        if signoff:
            try:
                queue = self.governance_store.get_queue(queue_id)
                current = self.governance_store._current_source(str(queue.get("portfolio_id") or ""))  # noqa: SLF001
                current_source_hash = stable_hash(current)
                source = _as_document(signoff.get("source"))
                stale = bool(source.get("current_source_hash") and current_source_hash and str(source.get("current_source_hash")) != current_source_hash)
            except Exception:
                stale = False
        return governance_signoff_summary(signoff, current_source_hash=current_source_hash, stale=stale)

    def gate(self, queue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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
        blockers: list[DomainDocument] = []
        warnings: list[DomainDocument] = []

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

        summary = _as_document(execution.get("summary"))
        failed = int(summary.get("failed") or 0)
        blocked = int(summary.get("blocked") or 0)
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

    def signoff(self, queue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            now = now or now_iso()
            existing = self.read_signoff(queue_id, default={})
            if governance_signoff_summary(existing).get("status") in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceSignoffStateError("Portfolio Governance Queue is already signed off. Reset Governance Signoff before signing again.")
            gate = self.gate(queue_id, payload, now=now)
            if not gate.get("signable"):
                blockers = _as_list(gate.get("blockers"))
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

    def reset_signoff(self, queue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def export_archive(self, queue_id: str, *, now: str | None = None) -> DomainDocument:
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

    def build_archive_zip(self, queue_id: str, *, now: str | None = None) -> DomainDocument:
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

    def read_archive_manifest(self, queue_id: str) -> DomainDocument:
        path = self.archive_export_dir(queue_id) / "manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceSignoffNotFoundError("Portfolio Governance Archive export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def archive_summary(self, queue_id: str) -> DomainDocument:
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

    def list_change_requests(self, queue_id: str, *, include_archived: bool = True) -> list[DomainDocument]:
        root = self.change_requests_root(queue_id)
        rows: list[DomainDocument] = []
        for path in sorted(root.glob("pgcr-*.json")) if root.exists() else []:
            try:
                item = sanitize_metadata(read_json(path), blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)
            except Exception:
                continue
            if not include_archived and item.get("status") == "archived":
                continue
            rows.append(item)
        return sorted(rows, key=lambda item: str(item.get("updated_at") or item.get("requested_at") or ""), reverse=True)

    def get_change_request(self, queue_id: str, change_request_id: str) -> DomainDocument:
        path = self.change_request_path(queue_id, change_request_id)
        if not path.exists():
            raise ReleasePortfolioGovernanceSignoffNotFoundError("Portfolio Governance Change Request does not exist.")
        value = read_json(path)
        return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS)

    def create_change_request(self, queue_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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
