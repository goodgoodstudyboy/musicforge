# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_report_integrity_ok as portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore as ReleasePortfolioGovernanceAuditStore, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore as ReleasePortfolioGovernanceReviewerPackStore, reviewer_report_integrity_hash as reviewer_report_integrity_hash, reviewer_report_integrity_ok as reviewer_report_integrity_ok, reviewer_pack_summary as reviewer_pack_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_final_board_contracts import FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS as FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS, FINAL_BOARD_BLOCKED_KEYS as FINAL_BOARD_BLOCKED_KEYS, FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS as FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS, FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS as FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS, FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS as FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS, FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS as FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS, final_board_archive_manifest_hash as final_board_archive_manifest_hash, final_board_change_request_hash as final_board_change_request_hash, final_board_change_request_integrity_ok as final_board_change_request_integrity_ok, final_board_report_integrity_hash as final_board_report_integrity_hash, final_board_response_integrity_hash as final_board_response_integrity_hash, final_board_signoff_hash as final_board_signoff_hash

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

ReleasePortfolioGovernanceFinalBoardStateError = _make_deferred_global('ReleasePortfolioGovernanceFinalBoardStateError')
_blocker = _make_deferred_global('_blocker')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_final_board_markdown = _make_deferred_global('_final_board_markdown')
_read_json_default = _make_deferred_global('_read_json_default')
_read_zip_json = _make_deferred_global('_read_zip_json')
_redaction_summary = _make_deferred_global('_redaction_summary')
_reviewer_response_bundle = _make_deferred_global('_reviewer_response_bundle')
_reviewer_response_markdown = _make_deferred_global('_reviewer_response_markdown')
_reviewer_response_status = _make_deferred_global('_reviewer_response_status')
_sha256 = _make_deferred_global('_sha256')
_verification_summary = _make_deferred_global('_verification_summary')
_warning = _make_deferred_global('_warning')
_write_json = _make_deferred_global('_write_json')
_write_readme = _make_deferred_global('_write_readme')
_zip_entries = _make_deferred_global('_zip_entries')
final_board_signoff_summary = _make_deferred_global('final_board_signoff_summary')
key = _make_deferred_global('key')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceFinalBoardStateError, _blocker, _ensure_within, _file_record, _final_board_markdown, _read_json_default, _read_zip_json
    global _redaction_summary, _reviewer_response_bundle, _reviewer_response_markdown, _reviewer_response_status, _sha256, _verification_summary, _warning, _write_json
    global _write_readme, _zip_entries, final_board_signoff_summary, key, value
    ReleasePortfolioGovernanceFinalBoardStateError = namespace.get('ReleasePortfolioGovernanceFinalBoardStateError', ReleasePortfolioGovernanceFinalBoardStateError)
    _blocker = namespace.get('_blocker', _blocker)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _final_board_markdown = namespace.get('_final_board_markdown', _final_board_markdown)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _redaction_summary = namespace.get('_redaction_summary', _redaction_summary)
    _reviewer_response_bundle = namespace.get('_reviewer_response_bundle', _reviewer_response_bundle)
    _reviewer_response_markdown = namespace.get('_reviewer_response_markdown', _reviewer_response_markdown)
    _reviewer_response_status = namespace.get('_reviewer_response_status', _reviewer_response_status)
    _sha256 = namespace.get('_sha256', _sha256)
    _verification_summary = namespace.get('_verification_summary', _verification_summary)
    _warning = namespace.get('_warning', _warning)
    _write_json = namespace.get('_write_json', _write_json)
    _write_readme = namespace.get('_write_readme', _write_readme)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    final_board_signoff_summary = namespace.get('final_board_signoff_summary', final_board_signoff_summary)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


FINAL_BOARD_SCHEMA_VERSION = 1
FINAL_BOARD_ARCHIVE_SCHEMA_VERSION = 1
FINAL_BOARD_CHANGE_REQUEST_SCHEMA_VERSION = 1
SIGNED_STATUSES = {"signed", "force_signed"}
RESPONSE_DECISIONS = {"accepted", "accepted_with_notes", "needs_changes", "rejected"}
RESPONSE_BLOCKED_KEYS = {"source_path", "local_path", "file_path", "raw_file", "token", "api_key", "access_token", "authorization", "secret"}




class ReleasePortfolioGovernanceFinalBoardStoreEvidenceMixin:
    def export_archive(self, portfolio_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            signoff = self.get_signoff(portfolio_id)
            summary = self.signoff_summary(portfolio_id, signoff=signoff)
            if summary.get("status") not in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive requires signed Final Board Signoff.")
            if not summary.get("integrity_ok") or summary.get("stale"):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Signoff is stale or integrity failed. Reset and sign again.")
            export_dir = self.export_dir(portfolio_id).resolve()
            root = self.root_dir(portfolio_id).resolve()
            _ensure_within(root, export_dir)
            if self._history_has_current_signoff_archive_event(portfolio_id, signoff, "archive_exported"):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive already exists for this signoff. Reset signoff before rebuilding archive evidence.")
            existing_manifest = _read_json_default(export_dir / "manifest.json", default={})
            if existing_manifest.get("final_board_signoff", {}).get("integrity_hash") == signoff.get("integrity_hash"):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive already exists for this signoff. Reset signoff before rebuilding archive evidence.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            report = self.read_report(portfolio_id, default={})
            responses = self.list_reviewer_responses(portfolio_id)
            change_requests = {"portfolio_id": portfolio_id, "items": self.list_change_requests(portfolio_id)}
            change_requests["payload_hash"] = stable_hash({key: value for key, value in change_requests.items() if key != "payload_hash"})
            history_text = self.history_path(portfolio_id).read_text(encoding="utf-8") if self.history_path(portfolio_id).exists() else ""
            reviewer_verification = _read_json_default(self.reviewer_pack_store.verification_report_path(portfolio_id), default={})
            audit_verification = _read_json_default(self.audit_store.verification_report_path(portfolio_id), default={})
            _write_json(export_dir / "final-board-report.json", report)
            _write_json(export_dir / "final-board-signoff.json", signoff)
            (export_dir / "final-board-history.jsonl").write_text(history_text, encoding="utf-8")
            _write_json(export_dir / "reviewer-response-summary.json", _reviewer_response_bundle(portfolio_id, responses, report.get("source", {})))
            _write_json(export_dir / "change-requests.json", change_requests)
            _write_json(export_dir / "governance-reviewer-pack-summary.json", {"summary": reviewer_pack_summary(self.reviewer_pack_store.read_report(portfolio_id, default={})), "verification": _verification_summary(reviewer_verification)})
            _write_json(export_dir / "governance-audit-summary.json", {"summary": audit_summary(self.audit_store.read_report(portfolio_id, default={})), "verification": _verification_summary(audit_verification)})
            _write_json(export_dir / "governance-archive-summary.json", self.audit_store.read_report(portfolio_id, default={}).get("archive_summary", {}))
            (export_dir / "final-board.md").write_text(_final_board_markdown(report, signoff), encoding="utf-8")
            (export_dir / "reviewer-response-summary.md").write_text(_reviewer_response_markdown(responses), encoding="utf-8")
            _write_readme(export_dir, report, signoff)
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            source = _as_document(report.get("source"))
            manifest = {
                "schema_version": FINAL_BOARD_ARCHIVE_SCHEMA_VERSION,
                "package_type": "release_portfolio_governance_final_board_archive",
                "tool": {"name": "MusicForge Release Portfolio Governance Final Board Archive", "version": __version__},
                "portfolio_id": portfolio_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "final_board_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "final_board_signoff": {"integrity_hash": signoff.get("integrity_hash"), "status": signoff.get("status")},
                "reviewer_pack_evidence": {
                    "verification_hash": source.get("governance_reviewer_pack_verification_hash"),
                    "zip_sha256": source.get("governance_reviewer_pack_zip_sha256"),
                    "manifest_hash": source.get("governance_reviewer_pack_manifest_hash"),
                },
                "audit_evidence": {
                    "verification_hash": source.get("governance_audit_verification_hash"),
                    "zip_sha256": source.get("governance_audit_zip_sha256"),
                    "manifest_hash": source.get("governance_audit_export_manifest_hash"),
                },
                "reviewer_response_summary": {"status": _reviewer_response_status(responses, source), "count": len(responses)},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"report": report, "signoff": signoff, "responses": responses, "change_requests": change_requests}),
            }
            manifest["integrity_hash"] = final_board_archive_manifest_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
            self._append_history(portfolio_id, "archive_exported", {"status": report.get("status"), "file_count": len(files), "signoff_id": signoff.get("signoff_id"), "signoff_integrity_hash": signoff.get("integrity_hash")}, now=now)
            return sanitize_metadata(manifest, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)

    def build_archive_zip(self, portfolio_id: str, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            signoff = self.signoff_summary(portfolio_id)
            if signoff.get("status") not in SIGNED_STATUSES:
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive ZIP requires signed Final Board Signoff.")
            current_signoff = self.read_signoff(portfolio_id, default={})
            if self._history_has_current_signoff_archive_event(portfolio_id, current_signoff, "archive_zip_built"):
                raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive ZIP already exists for this signoff. Reset signoff before rebuilding archive evidence.")
            export_dir = self.export_dir(portfolio_id).resolve()
            root = self.root_dir(portfolio_id).resolve()
            zip_path = self.archive_zip_path(portfolio_id).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "manifest.json").exists():
                self.export_archive(portfolio_id, now=now)
            if zip_path.exists():
                manifest = _read_zip_json(zip_path, "manifest.json")
                if manifest.get("final_board_signoff", {}).get("integrity_hash") == current_signoff.get("integrity_hash"):
                    raise ReleasePortfolioGovernanceFinalBoardStateError("Final Board Archive ZIP already exists for this signoff. Reset signoff before rebuilding archive evidence.")
            manifest = read_json(export_dir / "manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            manifest["integrity_hash"] = final_board_archive_manifest_hash(manifest)
            _write_json(export_dir / "manifest.json", manifest)
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
            self._append_history(portfolio_id, "archive_zip_built", {"sha256": info["sha256"], "entry_count": len(entries), "signoff_id": current_signoff.get("signoff_id"), "signoff_integrity_hash": current_signoff.get("integrity_hash")}, now=now)
            return sanitize_metadata(info, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)

    def signoff_summary(self, portfolio_id: str, *, signoff: DomainDocument | None = None) -> DomainDocument:
        data = _document_or(signoff, self.read_signoff(portfolio_id, default={}))
        stale = False
        if data and data.get("status") in SIGNED_STATUSES:
            try:
                report = self.read_report(portfolio_id, default={})
                source = _as_document(data.get("source"))
                stale = (
                    self.report_is_stale(portfolio_id, report)
                    or source.get("final_board_report_hash") != report.get("integrity_hash")
                    or source.get("reviewer_pack_verification_hash") != stable_hash(_read_json_default(self.reviewer_pack_store.verification_report_path(portfolio_id), default={}))
                    or source.get("governance_audit_verification_hash") != stable_hash(_read_json_default(self.audit_store.verification_report_path(portfolio_id), default={}))
                )
            except Exception:
                stale = True
        return final_board_signoff_summary(data, stale=stale)

    def summary(self, portfolio_id: str) -> DomainDocument:
        report = self.read_report(portfolio_id, default={})
        signoff = self.read_signoff(portfolio_id, default={})
        verification = _read_json_default(self.verification_report_path(portfolio_id), default={})
        return sanitize_metadata(
            {
                "status": final_board_signoff_summary(signoff).get("status") if signoff else report.get("status", "missing"),
                "report_status": report.get("status") if report else "missing",
                "signoff_status": final_board_signoff_summary(signoff).get("status"),
                "source_hash": report.get("source_hash"),
                "archive_zip_sha256": _sha256(self.archive_zip_path(portfolio_id)) if self.archive_zip_path(portfolio_id).exists() else None,
                "verification_status": verification.get("status") or "missing",
                "stale": self.report_is_stale(portfolio_id, report) if report else False,
            },
            blocked_keys=FINAL_BOARD_BLOCKED_KEYS,
        )

    def _final_board_findings(self, portfolio_id: str, source: DomainDocument, responses: list[DomainDocument], payload: DomainDocument) -> tuple[list[DomainDocument], list[DomainDocument], list[DomainDocument]]:
        blockers: list[DomainDocument] = []
        warnings: list[DomainDocument] = []
        gates: list[DomainDocument] = []

        def gate(gate_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            status = "passed" if passed else "warning" if warning else "failed"
            item = {"gate_id": gate_id, "status": status, "severity": "warning" if warning else "blocking", "message": message}
            gates.append(item)
            if not passed and warning:
                warnings.append(_warning(gate_id, message))
            elif not passed:
                blockers.append(_blocker(gate_id, message))

        gate("portfolio_exists", bool(source.get("portfolio_hash")), "Portfolio exists.")
        gate("portfolio_report_current", bool(source.get("portfolio_report_integrity_ok")) and not source.get("portfolio_report_stale"), "Portfolio Audit report is current.")
        gate("governance_audit_report_current", bool(source.get("governance_audit_report_integrity_ok")) and not source.get("governance_audit_report_stale") and source.get("governance_audit_report_status") != "failed", "Governance Audit report is current.")
        gate("governance_audit_ledger_chain", bool(source.get("governance_audit_ledger_integrity_ok")), "Governance Audit ledger chain is valid.")
        gate(
            "governance_audit_verification_current",
            source.get("governance_audit_verification_status") == "passed"
            and source.get("governance_audit_verification_zip_sha256") == source.get("governance_audit_zip_sha256")
            and source.get("governance_audit_verification_zip_size_bytes") == source.get("governance_audit_zip_size_bytes")
            and source.get("governance_audit_verification_manifest_hash") == source.get("governance_audit_export_manifest_hash"),
            "Governance Audit verification matches the current Audit ZIP and manifest.",
        )
        gate("governance_reviewer_pack_report_current", bool(source.get("governance_reviewer_report_integrity_ok")) and not source.get("governance_reviewer_report_stale") and source.get("governance_reviewer_report_status") != "failed", "Governance Reviewer Pack report is current.")
        gate(
            "governance_reviewer_pack_verification_current",
            source.get("governance_reviewer_pack_verification_status") == "passed"
            and source.get("governance_reviewer_pack_verification_zip_sha256") == source.get("governance_reviewer_pack_zip_sha256")
            and source.get("governance_reviewer_pack_verification_zip_size_bytes") == source.get("governance_reviewer_pack_zip_size_bytes"),
            "Governance Reviewer Pack verification matches the current Reviewer Pack ZIP.",
        )
        queue_count = int(source.get("queue_count") or 0)
        signed_count = int(source.get("signed_queue_count") or 0)
        archive_count = int(source.get("archive_verified_count") or 0)
        gate("signed_queue_coverage", queue_count > 0 and signed_count >= queue_count, "All Governance Queues are signed.")
        gate("archive_verification_coverage", signed_count > 0 and archive_count >= signed_count, "All signed Governance Queues have verified Archive evidence.")
        gate("reset_change_request_causality", int(source.get("reset_count") or 0) == 0 or int(source.get("applied_change_request_count") or 0) >= int(source.get("reset_count") or 0), "Reset entries are bound to applied Change Requests.")
        response_status = _reviewer_response_status(responses, source)
        gate("reviewer_response_closed", response_status not in {"needs_changes", "rejected", "stale", "invalid"}, "Reviewer responses are closed.")
        if bool(payload.get("require_reviewer_response", False)):
            gate("external_reviewer_response_required", response_status in {"accepted", "accepted_with_notes"}, "Accepted reviewer response is required.")
        force_count = int(source.get("force_signed_queue_count") or 0)
        if force_count:
            gate("no_force_signoff", False, "Force-signed Governance Queue is present.", warning=not bool(payload.get("require_no_force", False)))
        if _redaction_summary({"source": source, "responses": responses}).get("status") == "failed":
            gate("redaction_scan", False, "Final Board source contains sensitive values.")
        else:
            gate("redaction_scan", True, "No sensitive values found in Final Board source.")
        return blockers, warnings, gates

    def _reserve_report_id(self, portfolio_id: str) -> str:
        existing = self.read_report(portfolio_id, default={})
        if str(existing.get("report_id") or "").startswith("fgb-"):
            return str(existing.get("report_id"))
        return "fgb-000001"

    def _reserve_response_id(self, portfolio_id: str) -> str:
        root = self.responses_root(portfolio_id)
        root.mkdir(parents=True, exist_ok=True)
        nums: list[int] = []
        for path in root.glob("fbr-*.json"):
            try:
                nums.append(int(path.stem.split("-")[-1]))
            except ValueError:
                pass
        return f"fbr-{(max(nums) if nums else 0) + 1:06d}"

    def _reserve_signoff_id(self, portfolio_id: str) -> str:
        path = self.history_path(portfolio_id)
        used: list[int] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                signoff_id = str((_as_document(event.get("summary"))).get("signoff_id") or "")
                if signoff_id.startswith("fgs-"):
                    try:
                        used.append(int(signoff_id.split("-")[-1]))
                    except ValueError:
                        pass
        return f"fgs-{(max(used) if used else 0) + 1:06d}"

    def _reserve_change_request_id(self, portfolio_id: str) -> str:
        root = self.change_requests_root(portfolio_id)
        root.mkdir(parents=True, exist_ok=True)
        nums: list[int] = []
        for path in root.glob("fcr-*.json"):
            try:
                nums.append(int(path.stem.split("-")[-1]))
            except ValueError:
                pass
        return f"fcr-{(max(nums) if nums else 0) + 1:06d}"

    def _append_history(self, portfolio_id: str, event_type: str, summary: DomainDocument, *, now: str | None = None) -> None:
        path = self.history_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"fgbe-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "summary": summary}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _history_has_current_signoff_archive_event(self, portfolio_id: str, signoff: DomainDocument, event_type: str) -> bool:
        signoff_id = str(signoff.get("signoff_id") or "")
        signoff_hash = str(signoff.get("integrity_hash") or "")
        if not signoff_id and not signoff_hash:
            return False
        active_signoff_id: str | None = None
        active_signoff_hash: str | None = None
        path = self.history_path(portfolio_id)
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            summary = _as_document(event.get("summary"))
            event_name = str(event.get("type") or "")
            if event_name == "signed":
                active_signoff_id = str(summary.get("signoff_id") or "") or None
                active_signoff_hash = str(summary.get("signoff_integrity_hash") or "") or None
                continue
            if event_name == "reset":
                active_signoff_id = None
                active_signoff_hash = None
                continue
            if event_name != event_type:
                continue
            event_signoff_hash = str(summary.get("signoff_integrity_hash") or "")
            event_signoff_id = str(summary.get("signoff_id") or "")
            if signoff_hash and event_signoff_hash and event_signoff_hash == signoff_hash:
                return True
            if signoff_id and event_signoff_id and event_signoff_id == signoff_id:
                return True
            # v7.0.0 archive history entries did not record signoff hashes.
            # Bind those legacy entries to the latest signed event until reset.
            if not event_signoff_hash and not event_signoff_id:
                if signoff_id and active_signoff_id == signoff_id:
                    return True
                if signoff_hash and active_signoff_hash == signoff_hash:
                    return True
        return False

    def _append_change_event(self, portfolio_id: str, event_type: str, item: DomainDocument, *, now: str | None = None) -> None:
        path = self.change_request_events_path(portfolio_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"fcre-{count + 1:06d}", "at": now or now_iso(), "type": event_type, "change_request_id": item.get("change_request_id"), "status": item.get("status")}, blocked_keys=FINAL_BOARD_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
