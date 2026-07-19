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

PublicTrustCenterAcceptanceBoardNotFoundError = _make_deferred_global('PublicTrustCenterAcceptanceBoardNotFoundError')
PublicTrustCenterAcceptanceBoardStateError = _make_deferred_global('PublicTrustCenterAcceptanceBoardStateError')
_accepted_evidence_index = _make_deferred_global('_accepted_evidence_index')
_append_jsonl = _make_deferred_global('_append_jsonl')
_critical_findings = _make_deferred_global('_critical_findings')
_distribution_kit_state = _make_deferred_global('_distribution_kit_state')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_fs_path = _make_deferred_global('_fs_path')
_is_file = _make_deferred_global('_is_file')
_participant_warnings = _make_deferred_global('_participant_warnings')
_public_response_from_record = _make_deferred_global('_public_response_from_record')
_read_json_default = _make_deferred_global('_read_json_default')
_read_text = _make_deferred_global('_read_text')
_read_zip_json = _make_deferred_global('_read_zip_json')
_response_index = _make_deferred_global('_response_index')
_sanitize = _make_deferred_global('_sanitize')
_sha256 = _make_deferred_global('_sha256')
_write_json = _make_deferred_global('_write_json')
_write_text = _make_deferred_global('_write_text')
_write_zip = _make_deferred_global('_write_zip')
_zip_entries = _make_deferred_global('_zip_entries')
acceptance_board_change_request_hash = _make_deferred_global('acceptance_board_change_request_hash')
entry = _make_deferred_global('entry')
redaction_summary = _make_deferred_global('redaction_summary')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterAcceptanceBoardNotFoundError, PublicTrustCenterAcceptanceBoardStateError, _accepted_evidence_index, _append_jsonl, _critical_findings, _distribution_kit_state, _ensure_within, _file_record
    global _fs_path, _is_file, _participant_warnings, _public_response_from_record, _read_json_default, _read_text, _read_zip_json
    global _response_index, _sanitize, _sha256, _write_json, _write_text, _write_zip, _zip_entries, acceptance_board_change_request_hash, entry
    global redaction_summary
    PublicTrustCenterAcceptanceBoardNotFoundError = namespace.get('PublicTrustCenterAcceptanceBoardNotFoundError', PublicTrustCenterAcceptanceBoardNotFoundError)
    PublicTrustCenterAcceptanceBoardStateError = namespace.get('PublicTrustCenterAcceptanceBoardStateError', PublicTrustCenterAcceptanceBoardStateError)
    _accepted_evidence_index = namespace.get('_accepted_evidence_index', _accepted_evidence_index)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _critical_findings = namespace.get('_critical_findings', _critical_findings)
    _distribution_kit_state = namespace.get('_distribution_kit_state', _distribution_kit_state)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _fs_path = namespace.get('_fs_path', _fs_path)
    _is_file = namespace.get('_is_file', _is_file)
    _participant_warnings = namespace.get('_participant_warnings', _participant_warnings)
    _public_response_from_record = namespace.get('_public_response_from_record', _public_response_from_record)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_text = namespace.get('_read_text', _read_text)
    _read_zip_json = namespace.get('_read_zip_json', _read_zip_json)
    _response_index = namespace.get('_response_index', _response_index)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _sha256 = namespace.get('_sha256', _sha256)
    _write_json = namespace.get('_write_json', _write_json)
    _write_text = namespace.get('_write_text', _write_text)
    _write_zip = namespace.get('_write_zip', _write_zip)
    _zip_entries = namespace.get('_zip_entries', _zip_entries)
    acceptance_board_change_request_hash = namespace.get('acceptance_board_change_request_hash', acceptance_board_change_request_hash)
    entry = namespace.get('entry', entry)
    redaction_summary = namespace.get('redaction_summary', redaction_summary)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_BOARD_SCHEMA_VERSION = 1
ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_policy"
ACCEPTANCE_BOARD_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_change_request"
ACCEPTANCE_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
DEFAULT_POLICY_ID = "ptcab-policy-default"




class PublicTrustCenterAcceptanceBoardStoreEvidenceMixin:
    def export_signoff_archive(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            del payload
            signoff = self.read_signoff(center_id, default={})
            self._ensure_signoff_current(center_id, signoff)
            self._ensure_archive_not_exported(center_id, str(signoff.get("integrity_hash") or ""))
            archive_dir = self.signoff_archive_dir(center_id).resolve()
            _ensure_within(self.signoff_dir(center_id).resolve(), archive_dir)
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            docs = self._signoff_archive_documents(center_id, signoff, now)
            for name, doc in docs.items():
                if name.endswith(".json"):
                    _write_json(archive_dir / name, _as_document(doc))
                else:
                    _write_text(archive_dir / name, str(doc))
            files = [_file_record(archive_dir, path) for path in sorted(archive_dir.rglob("*")) if _is_file(path) and path.name != "board-signoff-archive-manifest.json"]
            manifest = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Acceptance Board Signoff Archive", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": signoff.get("source_hash"),
                "signoff_hash": signoff.get("integrity_hash"),
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "redaction_summary": redaction_summary(docs),
            }
            manifest["integrity_hash"] = acceptance_board_signoff_archive_hash(manifest)
            _write_json(archive_dir / "board-signoff-archive-manifest.json", manifest)
            self._append_signoff_history(center_id, {"event_type": "board_signoff_archive_exported", "created_at": now, "signoff_hash": signoff.get("integrity_hash"), "manifest_hash": manifest["integrity_hash"]})
            return _sanitize(manifest)

    def build_signoff_archive_zip(self, center_id: str = "ptc-default", payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            del payload
            signoff = self.read_signoff(center_id, default={})
            self._ensure_signoff_current(center_id, signoff)
            signoff_hash = str(signoff.get("integrity_hash") or "")
            self._ensure_archive_not_zipped(center_id, signoff_hash)
            archive_dir = self.signoff_archive_dir(center_id).resolve()
            manifest_path = archive_dir / "board-signoff-archive-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if manifest.get("signoff_hash") != signoff_hash or manifest.get("source_hash") != signoff.get("source_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff archive export is stale. Re-export before ZIP.")
            zip_path = self.signoff_archive_zip_path(center_id).resolve()
            _ensure_within(self.signoff_dir(center_id).resolve(), zip_path)
            entries = _zip_entries(archive_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = acceptance_board_signoff_archive_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, archive_dir)
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "signoff_hash": signoff_hash}
            self._append_signoff_history(center_id, {"event_type": "board_signoff_archive_zip_built", "created_at": now, "signoff_hash": signoff_hash, "zip_sha256": info["sha256"]})
            return _sanitize(info)

    def verify_signoff_archive_zip(self, center_id: str = "ptc-default", payload: DomainDocument | None = None) -> DomainDocument:
        from song_agent.domains.trust.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package, write_public_trust_center_acceptance_board_signoff_archive_verification_report

        payload = payload or {}
        report = verify_public_trust_center_acceptance_board_signoff_archive_package(
            self.signoff_archive_zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current=bool(payload.get("require_current", True)),
            require_ready=bool(payload.get("require_ready", True)),
            board_zip_path=self.zip_path(center_id) if bool(payload.get("use_board_zip", True)) else None,
            board_verification_report_path=self.verification_report_path(center_id) if bool(payload.get("use_board_verification", True)) else None,
            distribution_kit_path=self.distribution_kit_store.zip_path(center_id) if bool(payload.get("use_distribution_kit", True)) else None,
            accepted_evidence_dir=self.acceptance_store.accepted_evidence_root(center_id) if bool(payload.get("use_accepted_evidence", True)) else None,
        )
        write_public_trust_center_acceptance_board_signoff_archive_verification_report(report, self.signoff_archive_verification_report_path(center_id))
        return report

    def summary(self, center_id: str = "ptc-default") -> DomainDocument:
        report = self.read_report(center_id, default={})
        summary = _as_document(report.get("summary"))
        signoff = self.read_signoff(center_id, default={})
        return {"center_id": center_id, "readiness": report.get("readiness") or "missing", "status": report.get("status") or "missing", "signoff_status": signoff.get("status") or "unsigned", **summary}

    def _build_source(self, center_id: str, policy: DomainDocument) -> tuple[DomainDocument, list[DomainDocument], DomainDocument, list[DomainDocument], list[DomainDocument]]:
        distribution_kit = _distribution_kit_state(self.distribution_kit_store, center_id)
        response_rows: list[DomainDocument] = []
        participants: list[DomainDocument] = []
        evidence_rows: list[DomainDocument] = []
        response_proofs: list[DomainDocument] = []
        evidence_summaries: list[DomainDocument] = []
        evidence_by_response = self._evidence_by_response(center_id)
        for item in self.acceptance_store.list_responses(center_id):
            response_id = str(item.get("response_id") or "")
            if not response_id:
                continue
            try:
                response = self.acceptance_store.read_response(center_id, response_id)
            except PublicTrustCenterDistributionKitAcceptanceError:
                continue
            public_response = _public_response_from_record(response)
            reviewer = _as_document(public_response.get("reviewer"))
            response_stale = self.acceptance_store.response_is_stale(center_id, response)
            verification = _read_json_default(self.acceptance_store.response_verification_report_path(center_id, response_id), default={})
            binding = _read_json_default(self.acceptance_store.response_binding_summary_path(center_id, response_id), default={})
            evidence = evidence_by_response.get(response_id, {})
            evidence_id = str(evidence.get("evidence_id") or "")
            evidence_current = False
            evidence_verification_status = "missing"
            evidence_verification_hash = None
            evidence_zip_sha = None
            if evidence_id:
                try:
                    self.acceptance_store._ensure_evidence_exportable(center_id, evidence)  # noqa: SLF001 - internal evidence freshness guard.
                    evidence_current = True
                except Exception:
                    evidence_current = False
                verification_report = _read_json_default(self.acceptance_store.evidence_verification_report_path(center_id, evidence_id), default={})
                if not verification_report or verification_report.get("zip_sha256") != _sha256(self.acceptance_store.evidence_zip_path(center_id, evidence_id)):
                    verification_report = verify_public_trust_center_distribution_kit_accepted_evidence_package(
                        self.acceptance_store.evidence_zip_path(center_id, evidence_id),
                        strict=True,
                        require_current=True,
                        distribution_kit_path=self.distribution_kit_store.zip_path(center_id),
                    )
                    write_public_trust_center_distribution_kit_accepted_evidence_verification_report(verification_report, self.acceptance_store.evidence_verification_report_path(center_id, evidence_id))
                evidence_verification_status = str(verification_report.get("status") or "missing")
                evidence_verification_hash = verification_hash(verification_report)
                evidence_zip_sha = verification_report.get("zip_sha256")
                evidence_rows.append(
                    {
                        "evidence_id": evidence_id,
                        "response_id": response_id,
                        "evidence_integrity_hash": evidence.get("integrity_hash"),
                        "evidence_source_hash": evidence.get("source_hash"),
                        "verification_status": evidence_verification_status,
                        "verification_report_hash": evidence_verification_hash,
                        "zip_sha256": evidence_zip_sha,
                        "current": evidence_current,
                    }
                )
                evidence_summaries.append(
                    {
                        "source_hash": evidence.get("source_hash"),
                        "evidence_id": evidence_id,
                        "response_id": response_id,
                        "summary": accepted_evidence_summary(evidence),
                        "evidence_integrity_hash": evidence.get("integrity_hash"),
                        "verification_status": evidence_verification_status,
                        "verification_report_hash": evidence_verification_hash,
                        "zip_sha256": evidence_zip_sha,
                    }
                )
            response_row = {
                "response_id": response_id,
                "result": response.get("result"),
                "review_mode": response.get("review_mode"),
                "status": response.get("status"),
                "response_payload_hash": response.get("response_payload_hash"),
                "raw_response_sha256": response.get("raw_response_sha256"),
                "binding_summary_hash": stable_hash(binding),
                "verification_hash": verification_hash(verification),
                "public_response_hash": stable_hash(public_response),
                "verification_status": response.get("verification_status"),
                "kit_binding_status": response.get("kit_binding_status"),
                "current": not response_stale,
            }
            response_rows.append(response_row)
            response_proofs.append(
                {
                    "response_id": response_id,
                    "binding_proof": {
                        "source_hash": None,
                        "response_id": response_id,
                        "binding_summary_hash": stable_hash(binding),
                        "response_payload_hash": response.get("response_payload_hash"),
                        "raw_response_sha256": response.get("raw_response_sha256"),
                        "response_public_summary_hash": stable_hash(public_response),
                        "public_response": public_response,
                        "kit_binding_status": response.get("kit_binding_status"),
                        "response_binding": _as_document(binding.get("response_binding")),
                        "current_binding": _as_document(binding.get("current_binding")),
                    },
                    "verification_summary": {
                        "source_hash": None,
                        "response_id": response_id,
                        "status": verification.get("status"),
                        "response_payload_hash": response.get("response_payload_hash"),
                        "raw_response_sha256": response.get("raw_response_sha256"),
                        "response_public_summary_hash": stable_hash(public_response),
                        "response_verification_hash": verification_hash(verification),
                        "check_count": len(_as_list(verification.get("checks"))),
                        "blocker_count": len(_as_list(verification.get("blockers"))),
                    },
                }
            )
            current = bool(response.get("result") == "accepted" and response.get("review_mode") == "external_manual" and not response_stale and evidence_current and evidence_verification_status == "passed" and response.get("verification_status") == "passed")
            participant = {
                "response_id": response_id,
                "evidence_id": evidence_id or None,
                "result": response.get("result"),
                "review_mode": response.get("review_mode"),
                "reviewer_name": reviewer.get("name"),
                "organization": reviewer.get("organization"),
                "role": reviewer.get("role"),
                "current": not response_stale,
                "evidence_current": evidence_current,
                "evidence_verification_status": evidence_verification_status,
                "counts_for_quorum": current,
                "critical_findings": _critical_findings(response),
                "warnings": _participant_warnings(response, response_stale, evidence_id, evidence_current, evidence_verification_status),
            }
            participants.append(participant)
        source = {
            "center_id": center_id,
            "distribution_kit": distribution_kit,
            "policy_hash": policy.get("integrity_hash"),
            "responses": response_rows,
            "accepted_evidence": evidence_rows,
        }
        return source, participants, _response_index(source, response_rows), _accepted_evidence_index(source, evidence_rows), response_proofs, evidence_summaries

    def _evidence_by_response(self, center_id: str) -> dict[str, DomainDocument]:
        root = self.acceptance_store.accepted_evidence_root(center_id)
        rows: dict[str, DomainDocument] = {}
        if not root.exists():
            return rows
        for path in sorted(root.glob("*/evidence-report.json")):
            evidence = _read_json_default(path, default={})
            response_id = str(evidence.get("response_id") or "")
            if response_id:
                rows[response_id] = evidence
        return rows

    def _ensure_exportable(self, center_id: str, report: DomainDocument) -> None:
        if not report:
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report is missing. Refresh before export.")
        policy = self.read_policy(center_id)
        current_source, _participants, _response_index, _evidence_index, _proofs, _summaries = self._build_source(center_id, policy)
        if stable_hash(current_source) != report.get("source_hash"):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report is stale. Refresh before export.")
        if report.get("integrity_hash") != acceptance_board_report_hash(report):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report integrity failed.")

    def _ensure_unsigned(self, center_id: str, action: str) -> None:
        signoff = self.read_signoff(center_id, default={})
        if signoff.get("status") == "signed":
            raise PublicTrustCenterAcceptanceBoardStateError(f"Acceptance Board is signed. Reset signoff with an approved Change Request before attempting to {action}.")

    def _ensure_board_package_current(self, center_id: str) -> None:
        report = self.read_report(center_id, default={})
        self._ensure_exportable(center_id, report)
        manifest = _read_json_default(self.export_dir(center_id) / "acceptance-board-manifest.json", default={})
        if manifest.get("source_hash") != report.get("source_hash") or manifest.get("integrity_hash") != acceptance_board_manifest_hash(manifest):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board export is stale. Re-export before signoff.")
        zip_path = self.zip_path(center_id)
        if not zip_path.exists() or not zip_path.is_file():
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board ZIP is missing. Build ZIP before signoff.")
        zip_manifest = _read_zip_json(zip_path, "acceptance-board-manifest.json")
        if zip_manifest.get("integrity_hash") != manifest.get("integrity_hash"):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board ZIP manifest does not match current export.")

    def _signoff_source(self, center_id: str, verification: DomainDocument) -> DomainDocument:
        board_zip = self.zip_path(center_id)
        board_manifest = _read_zip_json(board_zip, "acceptance-board-manifest.json")
        report = self.read_report(center_id, default={})
        policy = self.read_policy(center_id)
        summary = _as_document(report.get("summary"))
        participants = [item for item in (_as_list(report.get("participants"))) if isinstance(item, dict)]
        counted = [item for item in participants if item.get("counts_for_quorum")]
        accepted_rows = []
        for row in (_as_document(report.get("source"))).get("accepted_evidence", []):
            if isinstance(row, dict) and any(item.get("evidence_id") == row.get("evidence_id") for item in counted):
                accepted_rows.append(row)
        return _sanitize(
            {
                "center_id": center_id,
                "board": {
                    "zip_sha256": _sha256(board_zip),
                    "zip_size_bytes": board_zip.stat().st_size if board_zip.exists() else None,
                    "manifest_hash": board_manifest.get("integrity_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "source_hash": report.get("source_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "readiness": report.get("readiness"),
                    "status": report.get("status"),
                },
                "verification": {
                    "status": verification.get("status"),
                    "verification_report_hash": acceptance_board_verification_hash(verification),
                    "zip_sha256": verification.get("zip_sha256"),
                    "zip_size_bytes": verification.get("zip_size_bytes"),
                    "manifest_hash": verification.get("manifest_hash"),
                    "blocker_count": len(_as_list(verification.get("blockers"))),
                },
                "quorum": {
                    "requirements": _as_document(policy.get("requirements")),
                    "summary": summary,
                    "participant_count": len(counted),
                    "participants": [
                        {
                            "response_id": item.get("response_id"),
                            "evidence_id": item.get("evidence_id"),
                            "organization": item.get("organization"),
                            "role": item.get("role"),
                            "reviewer_name": item.get("reviewer_name"),
                        }
                        for item in counted
                    ],
                },
                "accepted_evidence": sorted(accepted_rows, key=lambda item: str(item.get("evidence_id") or "")),
                "distribution_kit": _as_document((_as_document(report.get("source"))).get("distribution_kit")),
            }
        )

    def _ensure_signoff_integrity(self, signoff: DomainDocument) -> None:
        if not signoff:
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff is missing.")
        if signoff.get("integrity_hash") != acceptance_board_signoff_hash(signoff):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff integrity failed.")
        if signoff.get("source_hash") != stable_hash(_as_document(signoff.get("source"))):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff source hash failed.")

    def _ensure_signoff_current(self, center_id: str, signoff: DomainDocument) -> None:
        self._ensure_signoff_integrity(signoff)
        current_verification = _read_json_default(self.verification_report_path(center_id), default={})
        source = self._signoff_source(center_id, current_verification)
        if stable_hash(source) != signoff.get("source_hash"):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff source is stale. Reset signoff before archiving.")

    def _append_signoff_history(self, center_id: str, payload: DomainDocument) -> None:
        _append_jsonl(self.signoff_history_path(center_id), payload)

    def _history_events(self, center_id: str) -> list[DomainDocument]:
        path = self.signoff_history_path(center_id)
        if not path.exists():
            return []
        events: list[DomainDocument] = []
        try:
            for line in _read_text(path).splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    events.append(_sanitize(item))
        except OSError:
            return []
        return events

    def _history_has_event(self, center_id: str, event_type: str, signoff_hash: str) -> bool:
        return any(item.get("event_type") == event_type and item.get("signoff_hash") == signoff_hash for item in self._history_events(center_id))

    def _ensure_archive_not_exported(self, center_id: str, signoff_hash: str) -> None:
        if self._history_has_event(center_id, "board_signoff_archive_exported", signoff_hash):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff archive was already exported for this signoff. Reset signoff before rebuilding archive.")

    def _ensure_archive_not_zipped(self, center_id: str, signoff_hash: str) -> None:
        if self._history_has_event(center_id, "board_signoff_archive_zip_built", signoff_hash):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff archive ZIP was already built for this signoff. Reset signoff before rebuilding archive ZIP.")

    def _read_change_request(self, center_id: str, change_request_id: str) -> DomainDocument:
        request = _read_json_default(self.change_request_path(center_id, change_request_id), default={})
        if not request:
            raise PublicTrustCenterAcceptanceBoardNotFoundError(f"Acceptance Board Change Request not found: {change_request_id}")
        return request

    def _ensure_change_request_integrity(self, request: DomainDocument) -> None:
        if request.get("integrity_hash") != acceptance_board_change_request_hash(request):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request integrity failed.")
