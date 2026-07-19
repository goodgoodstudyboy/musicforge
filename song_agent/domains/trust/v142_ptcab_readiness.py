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
from song_agent.domains.trust.public_trust_center_distribution_kit import distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance import ACCEPTANCE_BLOCKED_KEYS as ACCEPTANCE_BLOCKED_KEYS, PublicTrustCenterDistributionKitAcceptanceError as PublicTrustCenterDistributionKitAcceptanceError, PublicTrustCenterDistributionKitAcceptanceStore as PublicTrustCenterDistributionKitAcceptanceStore, accepted_evidence_hash as accepted_evidence_hash, accepted_evidence_summary as accepted_evidence_summary, verification_hash as verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package, write_public_trust_center_distribution_kit_accepted_evidence_verification_report as write_public_trust_center_distribution_kit_accepted_evidence_verification_report
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import ACCEPTANCE_BOARD_BLOCKED_KEYS as ACCEPTANCE_BOARD_BLOCKED_KEYS, ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE as ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE, ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_PACKAGE_TYPE as ACCEPTANCE_BOARD_PACKAGE_TYPE, ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE, SIGNOFF_ARCHIVE_ENTRIES as SIGNOFF_ARCHIVE_ENTRIES, acceptance_board_conflict_hash as acceptance_board_conflict_hash, acceptance_board_manifest_hash as acceptance_board_manifest_hash, acceptance_board_policy_hash as acceptance_board_policy_hash, acceptance_board_report_hash as acceptance_board_report_hash, acceptance_board_signoff_archive_hash as acceptance_board_signoff_archive_hash, acceptance_board_signoff_hash as acceptance_board_signoff_hash, acceptance_board_verification_hash as acceptance_board_verification_hash, sidecar_hash as sidecar_hash

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

PublicTrustCenterAcceptanceBoardStateError = _make_deferred_global('PublicTrustCenterAcceptanceBoardStateError')
_append_jsonl = _make_deferred_global('_append_jsonl')
_board_summary = _make_deferred_global('_board_summary')
_default_policy = _make_deferred_global('_default_policy')
_ensure_within = _make_deferred_global('_ensure_within')
_evaluate_board = _make_deferred_global('_evaluate_board')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_is_file = _make_deferred_global('_is_file')
_next_change_request_id = _make_deferred_global('_next_change_request_id')
_normalize_requirements = _make_deferred_global('_normalize_requirements')
_read_json_default = _make_deferred_global('_read_json_default')
_readiness = _make_deferred_global('_readiness')
_readme = _make_deferred_global('_readme')
_role_rules = _make_deferred_global('_role_rules')
_safe_id = _make_deferred_global('_safe_id')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_verify_text = _make_deferred_global('_verify_text')
_write_json = _make_deferred_global('_write_json')
_write_text = _make_deferred_global('_write_text')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
acceptance_board_change_request_hash = _make_deferred_global('acceptance_board_change_request_hash')
entry = _make_deferred_global('entry')
path = _make_deferred_global('path')
redaction_summary = _make_deferred_global('redaction_summary')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterAcceptanceBoardStateError, _append_jsonl, _board_summary, _default_policy, _ensure_within, _evaluate_board, _file_record, _fs_path
    global _is_file, _next_change_request_id, _normalize_requirements, _read_json_default, _readiness, _readme, _role_rules
    global _safe_id, _sanitize, _sha256, _verify_text, _write_json, _write_text, _write_zip, _zip_entries
    global acceptance_board_change_request_hash, entry, path, redaction_summary
    PublicTrustCenterAcceptanceBoardStateError = namespace.get('PublicTrustCenterAcceptanceBoardStateError', PublicTrustCenterAcceptanceBoardStateError)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _board_summary = namespace.get('_board_summary', _board_summary)
    _default_policy = namespace.get('_default_policy', _default_policy)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _evaluate_board = namespace.get('_evaluate_board', _evaluate_board)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _is_file = namespace.get('_is_file', _is_file)
    _next_change_request_id = namespace.get('_next_change_request_id', _next_change_request_id)
    _normalize_requirements = namespace.get('_normalize_requirements', _normalize_requirements)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _readiness = namespace.get('_readiness', _readiness)
    _readme = namespace.get('_readme', _readme)
    _role_rules = namespace.get('_role_rules', _role_rules)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _verify_text = namespace.get('_verify_text', _verify_text)
    _write_json = namespace.get('_write_json', _write_json)
    _write_text = namespace.get('_write_text', _write_text)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    acceptance_board_change_request_hash = namespace.get('acceptance_board_change_request_hash', acceptance_board_change_request_hash)
    entry = namespace.get('entry', entry)
    path = namespace.get('path', path)
    redaction_summary = namespace.get('redaction_summary', redaction_summary)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_BOARD_SCHEMA_VERSION = 1
ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_policy"
ACCEPTANCE_BOARD_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_change_request"
ACCEPTANCE_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
DEFAULT_POLICY_ID = "ptcab-policy-default"




class PublicTrustCenterAcceptanceBoardStoreReadinessMixin:
    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.distribution_kit_store.root_dir(center_id).parent / "acceptance-board"

    def policy_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "board-policy.json"

    def report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "board-report.json"

    def conflict_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "conflict-report.json"

    def signoff_draft_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "board-signoff-draft.json"

    def events_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "events.jsonl"

    def export_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "export"

    def zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "public-trust-center-acceptance-board.zip"

    def verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "acceptance-board-verification-report.json"

    def signoff_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "signoff"

    def signoff_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-signoff.json"

    def signoff_history_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-signoff-history.jsonl"

    def change_requests_dir(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-change-requests"

    def change_request_path(self, center_id: str, change_request_id: str) -> Path:
        return self.change_requests_dir(center_id) / f"{_safe_id(change_request_id)}.json"

    def signoff_archive_dir(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "archive"

    def signoff_archive_zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "public-trust-center-acceptance-board-signoff-archive.zip"

    def signoff_archive_verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-signoff-archive-verification-report.json"

    def read_policy(self, center_id: str = "ptc-default") -> DomainDocument:
        policy = _read_json_default(self.policy_path(center_id), default={})
        if policy:
            return policy
        return _default_policy(center_id, now_iso())

    def save_policy(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            self._ensure_unsigned(center_id, "change Acceptance Board policy")
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            current = self.read_policy(center_id)
            requirements = _normalize_requirements(_document_or(payload.get("requirements"), payload))
            policy = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE,
                "policy_id": str(payload.get("policy_id") or current.get("policy_id") or DEFAULT_POLICY_ID),
                "center_id": center_id,
                "created_at": current.get("created_at") or now,
                "updated_at": now,
                "status": "active",
                "requirements": requirements,
                "role_rules": _role_rules(requirements),
            }
            policy["integrity_hash"] = acceptance_board_policy_hash(policy)
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.policy_path(center_id), policy)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_policy_saved", "created_at": now, "policy_hash": policy["integrity_hash"]})
            return _sanitize(policy)

    def read_report(self, center_id: str = "ptc-default", *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.report_path(center_id), default=default)

    def read_conflict_report(self, center_id: str = "ptc-default", *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.conflict_report_path(center_id), default=default)

    def refresh_report(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            self._ensure_unsigned(center_id, "refresh Acceptance Board report")
            now = now or now_iso()
            payload = payload or {}
            if payload.get("policy"):
                self.save_policy(center_id, _as_document(payload.get("policy")), now=now)
            policy = self.read_policy(center_id)
            source, participants, response_index, evidence_index, response_proofs, evidence_summaries = self._build_source(center_id, policy)
            checks, conflicts = _evaluate_board(policy, participants)
            blockers = [item for item in checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
            warnings = [item for item in checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
            readiness = _readiness(policy, participants, blockers, conflicts)
            summary = _board_summary(policy, participants, checks, conflicts)
            source_hash = stable_hash(source)
            report = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": readiness,
                "policy": {"policy_id": policy.get("policy_id"), "policy_hash": policy.get("integrity_hash")},
                "source": source,
                "source_hash": source_hash,
                "summary": summary,
                "participants": participants,
                "checks": checks,
                "warnings": warnings,
            }
            report["integrity_hash"] = acceptance_board_report_hash(report)
            conflict_report = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE,
                "center_id": center_id,
                "created_at": now,
                "source_hash": source_hash,
                "status": "failed" if any(item.get("severity") == "blocking" for item in conflicts) else "passed",
                "conflicts": conflicts,
            }
            conflict_report["integrity_hash"] = acceptance_board_conflict_hash(conflict_report)
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id), report)
            _write_json(self.conflict_report_path(center_id), conflict_report)
            self._write_cached_sidecars(center_id, source_hash, response_index, evidence_index, response_proofs, evidence_summaries)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_refreshed", "created_at": now, "source_hash": source_hash, "readiness": readiness})
            return _sanitize(report)

    def export_board(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            self._ensure_unsigned(center_id, "export Acceptance Board")
            now = now or now_iso()
            del payload
            report = self.read_report(center_id, default={})
            self._ensure_exportable(center_id, report)
            source_hash = str(report.get("source_hash") or "")
            policy = self.read_policy(center_id)
            conflict = self.read_conflict_report(center_id, default={})
            sidecars = self._sidecars_for_export(center_id, source_hash)
            export_dir = self.export_dir(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            (export_dir / "evidence").mkdir(parents=True, exist_ok=True)
            (export_dir / "response-proofs").mkdir(parents=True, exist_ok=True)
            docs: DomainDocument = {
                "board-report.json": report,
                "board-policy.json": policy,
                "conflict-report.json": conflict,
                "board-summary.json": sidecars["board_summary"],
                "accepted-evidence-index.json": sidecars["accepted_evidence_index"],
                "response-index.json": sidecars["response_index"],
                "quorum-evidence.json": sidecars["quorum_evidence"],
                "README.txt": _readme(report),
                "VERIFY.txt": _verify_text(),
            }
            for name, doc in docs.items():
                if name.endswith(".json"):
                    _write_json(export_dir / name, doc)
                else:
                    _write_text(export_dir / name, str(doc))
            for item in sidecars["evidence_summaries"]:
                _write_json(export_dir / "evidence" / f"{_safe_id(str(item.get('evidence_id') or 'evidence'))}-summary.json", item)
            for proof in sidecars["response_proofs"]:
                response_id = _safe_id(str(proof.get("response_id") or "response"))
                _write_json(export_dir / "response-proofs" / f"{response_id}-binding-proof.json", _as_document(proof.get("binding_proof")))
                _write_json(export_dir / "response-proofs" / f"{response_id}-verification-summary.json", _as_document(proof.get("verification_summary")))
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if _is_file(path) and path.name != "acceptance-board-manifest.json"]
            manifest = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Acceptance Board", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": source_hash,
                "board_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": source_hash},
                "policy": {"integrity_hash": policy.get("integrity_hash")},
                "conflict_report": {"integrity_hash": conflict.get("integrity_hash"), "source_hash": source_hash},
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "redaction_summary": redaction_summary(docs),
            }
            manifest["integrity_hash"] = acceptance_board_manifest_hash(manifest)
            _write_json(export_dir / "acceptance-board-manifest.json", manifest)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_exported", "created_at": now, "source_hash": source_hash, "manifest_hash": manifest["integrity_hash"]})
            return _sanitize(manifest)

    def build_zip(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            self._ensure_unsigned(center_id, "build Acceptance Board ZIP")
            now = now or now_iso()
            del payload
            report = self.read_report(center_id, default={})
            self._ensure_exportable(center_id, report)
            export_dir = self.export_dir(center_id).resolve()
            manifest = _read_json_default(export_dir / "acceptance-board-manifest.json", default={})
            if manifest.get("source_hash") != report.get("source_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board export is stale. Re-export before ZIP.")
            zip_path = self.zip_path(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = acceptance_board_manifest_hash(manifest)
            _write_json(export_dir / "acceptance-board-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries)}
            _append_jsonl(self.events_path(center_id), {"event_type": "board_zip_built", "created_at": now, "source_hash": report.get("source_hash"), "zip_sha256": info["sha256"]})
            return _sanitize(info)

    def verify_zip(self, center_id: str = "ptc-default", payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package, write_public_trust_center_acceptance_board_verification_report

        payload = payload or {}
        report = verify_public_trust_center_acceptance_board_package(
            self.zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_ready=bool(payload.get("require_ready", False)),
            require_quorum=bool(payload.get("require_quorum", False)),
            require_no_conflicts=bool(payload.get("require_no_conflicts", False)),
            min_accepted_count=int(payload.get("min_accepted_count") or 0),
            min_accepted_organizations=int(payload.get("min_accepted_organizations") or 0),
            required_roles=[str(item) for item in payload.get("required_roles", [])] if isinstance(payload.get("required_roles"), list) else [],
            distribution_kit_path=self.distribution_kit_store.zip_path(center_id) if bool(payload.get("use_distribution_kit", True)) else None,
            accepted_evidence_dir=self.acceptance_store.accepted_evidence_root(center_id) if bool(payload.get("use_accepted_evidence", True)) else None,
        )
        write_public_trust_center_acceptance_board_verification_report(report, self.verification_report_path(center_id))
        return report

    def create_signoff_draft(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            self._ensure_unsigned(center_id, "create Acceptance Board signoff draft")
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            report = self.read_report(center_id, default={})
            if not report:
                report = self.refresh_report(center_id, now=now)
            draft = {
                "draft_id": "ptcab-signoff-draft-000001",
                "center_id": center_id,
                "created_at": now,
                "status": "draft",
                "board_report_hash": report.get("integrity_hash"),
                "board_source_hash": report.get("source_hash"),
                "readiness": report.get("readiness"),
                "summary": _as_document(report.get("summary")),
                "payload": payload,
            }
            _write_json(self.signoff_draft_path(center_id), draft)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_signoff_draft_created", "created_at": now, "source_hash": report.get("source_hash")})
            return _sanitize(draft)

    def read_signoff(self, center_id: str = "ptc-default", *, default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.signoff_path(center_id), default=default)

    def signoff(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            self._ensure_unsigned(center_id, "sign Acceptance Board")
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            self._ensure_board_package_current(center_id)
            policy = self.read_policy(center_id)
            requirements = _as_document(policy.get("requirements"))
            verification = self.verify_zip(
                center_id,
                {
                    "strict": True,
                    "require_ready": True,
                    "require_quorum": True,
                    "require_no_conflicts": True,
                    "min_accepted_count": int(requirements.get("min_accepted_count") or 0),
                    "min_accepted_organizations": int(requirements.get("min_accepted_organizations") or 0),
                    "required_roles": _as_list(requirements.get("required_roles")),
                    "use_distribution_kit": True,
                    "use_accepted_evidence": True,
                },
            )
            if verification.get("status") != "passed":
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board verification must pass before signoff.")
            report = self.read_report(center_id, default={})
            if report.get("readiness") != "ready" or report.get("status") != "passed":
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board must be ready before signoff.")
            source = self._signoff_source(center_id, verification)
            signoff_sequence = 1 + len([item for item in self._history_events(center_id) if item.get("event_type") == "board_signoff_signed"])
            signoff: object = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE,
                "signoff_id": "ptcabs-" + stable_hash({"center_id": center_id, "source": source, "sequence": signoff_sequence})[:12],
                "signoff_sequence": signoff_sequence,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "signed",
                "signed_by": str(payload.get("signed_by") or "MusicForge Operator")[:120],
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Acceptance Board ready for public release.")[:1000]),
                "source": source,
                "source_hash": stable_hash(source),
                "board": source.get("board"),
                "verification": source.get("verification"),
                "quorum": source.get("quorum"),
                "accepted_evidence": source.get("accepted_evidence"),
                "distribution_kit": source.get("distribution_kit"),
                "warnings": [],
            }
            signoff["integrity_hash"] = acceptance_board_signoff_hash(signoff)
            self.signoff_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.signoff_path(center_id), signoff)
            self._append_signoff_history(center_id, {"event_type": "board_signoff_signed", "created_at": now, "signoff_hash": signoff["integrity_hash"], "source_hash": signoff["source_hash"]})
            _append_jsonl(self.events_path(center_id), {"event_type": "board_signoff_signed", "created_at": now, "signoff_hash": signoff["integrity_hash"], "source_hash": signoff["source_hash"]})
            return _sanitize(signoff)

    def create_change_request(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 12:
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request reason must be at least 12 characters.")
            change_request_id = _next_change_request_id(self.change_requests_dir(center_id))
            current_signoff = self.read_signoff(center_id, default={})
            request = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_CHANGE_REQUEST_PACKAGE_TYPE,
                "change_request_id": change_request_id,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "draft",
                "reason": reason[:1000],
                "requested_by": str(payload.get("requested_by") or "MusicForge Operator")[:120],
                "target_signoff_hash": current_signoff.get("integrity_hash"),
                "applied_at": None,
                "applied_signoff_hash": None,
            }
            request["integrity_hash"] = acceptance_board_change_request_hash(request)
            _write_json(self.change_request_path(center_id, change_request_id), request)
            self._append_signoff_history(center_id, {"event_type": "board_change_request_created", "created_at": now, "change_request_id": change_request_id, "target_signoff_hash": request.get("target_signoff_hash")})
            return _sanitize(request)

    def approve_change_request(self, center_id: str, change_request_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            request = self._read_change_request(center_id, change_request_id)
            self._ensure_change_request_integrity(request)
            if request.get("status") not in {"draft", "submitted"}:
                raise PublicTrustCenterAcceptanceBoardStateError("Only draft/submitted Acceptance Board Change Requests can be approved.")
            request.update(
                {
                    "updated_at": now,
                    "status": "approved",
                    "approved_by": str(payload.get("approved_by") or "MusicForge Operator")[:120],
                    "approval_reason": sanitize_sensitive_text(str(payload.get("approval_reason") or payload.get("reason") or "Approved Acceptance Board signoff reset.")[:1000]),
                }
            )
            request["integrity_hash"] = acceptance_board_change_request_hash(request)
            _write_json(self.change_request_path(center_id, change_request_id), request)
            self._append_signoff_history(center_id, {"event_type": "board_change_request_approved", "created_at": now, "change_request_id": change_request_id})
            return _sanitize(request)

    def reset_signoff(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            change_request_id = str(payload.get("change_request_id") or "").strip()
            if not change_request_id:
                raise PublicTrustCenterAcceptanceBoardStateError("Approved Acceptance Board Change Request is required to reset signoff.")
            signoff = self.read_signoff(center_id, default={})
            if not signoff:
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff is missing.")
            self._ensure_signoff_integrity(signoff)
            request = self._read_change_request(center_id, change_request_id)
            self._ensure_change_request_integrity(request)
            if request.get("status") != "approved":
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request must be approved before reset.")
            if request.get("applied_at") or request.get("applied_signoff_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request has already been applied.")
            target_hash = request.get("target_signoff_hash")
            if target_hash and target_hash != signoff.get("integrity_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request does not target the current signoff.")
            request.update({"updated_at": now, "status": "applied", "applied_at": now, "applied_signoff_hash": signoff.get("integrity_hash")})
            request["integrity_hash"] = acceptance_board_change_request_hash(request)
            _write_json(self.change_request_path(center_id, change_request_id), request)
            reset_record = {
                "event_type": "board_signoff_reset",
                "created_at": now,
                "change_request_id": change_request_id,
                "signoff_hash": signoff.get("integrity_hash"),
                "reset_reason": sanitize_sensitive_text(str(payload.get("reason") or request.get("reason") or "")[:1000]),
                "reset_hash": stable_hash({"signoff_hash": signoff.get("integrity_hash"), "change_request_id": change_request_id, "request_hash": request.get("integrity_hash")}),
            }
            self._append_signoff_history(center_id, reset_record)
            try:
                self.signoff_path(center_id).unlink()
            except FileNotFoundError:
                pass
            _append_jsonl(self.events_path(center_id), reset_record)
            return {"status": "reset", "center_id": center_id, "change_request": _sanitize(request), "previous_signoff_hash": signoff.get("integrity_hash"), "reset_hash": reset_record["reset_hash"]}
