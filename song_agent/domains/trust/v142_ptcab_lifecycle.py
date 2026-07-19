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

_latest_applied_change_request = _make_deferred_global('_latest_applied_change_request')
_mkdir = _make_deferred_global('_mkdir')
_quorum_evidence = _make_deferred_global('_quorum_evidence')
_read_json_default = _make_deferred_global('_read_json_default')
_safe_id = _make_deferred_global('_safe_id')
_signoff_archive_readme = _make_deferred_global('_signoff_archive_readme')
_signoff_archive_verify_text = _make_deferred_global('_signoff_archive_verify_text')
_write_json = _make_deferred_global('_write_json')
path = _make_deferred_global('path')

def bind_globals(namespace: dict[str, object]) -> None:
    global _latest_applied_change_request, _mkdir, _quorum_evidence, _read_json_default, _safe_id, _signoff_archive_readme, _signoff_archive_verify_text
    global _write_json, path
    _latest_applied_change_request = namespace.get('_latest_applied_change_request', _latest_applied_change_request)
    _mkdir = namespace.get('_mkdir', _mkdir)
    _quorum_evidence = namespace.get('_quorum_evidence', _quorum_evidence)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _signoff_archive_readme = namespace.get('_signoff_archive_readme', _signoff_archive_readme)
    _signoff_archive_verify_text = namespace.get('_signoff_archive_verify_text', _signoff_archive_verify_text)
    _write_json = namespace.get('_write_json', _write_json)
    path = namespace.get('path', path)
    _bind_deferred_defaults(namespace)


ACCEPTANCE_BOARD_SCHEMA_VERSION = 1
ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_policy"
ACCEPTANCE_BOARD_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_change_request"
ACCEPTANCE_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
DEFAULT_POLICY_ID = "ptcab-policy-default"




class PublicTrustCenterAcceptanceBoardStoreLifecycleMixin:
    def _signoff_archive_documents(self, center_id: str, signoff: DomainDocument, now: str) -> DomainDocument:
        source = _as_document(signoff.get("source"))
        verification = _read_json_default(self.verification_report_path(center_id), default={})
        board_fingerprint = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "source_hash": signoff.get("source_hash"),
            "board": _as_document(source.get("board")),
            "verification": _as_document(source.get("verification")),
        }
        board_fingerprint["integrity_hash"] = sidecar_hash(board_fingerprint)
        verification_summary = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "source_hash": signoff.get("source_hash"),
            "status": verification.get("status"),
            "verification_report_hash": acceptance_board_verification_hash(verification),
            "zip_sha256": verification.get("zip_sha256"),
            "zip_size_bytes": verification.get("zip_size_bytes"),
            "manifest_hash": verification.get("manifest_hash"),
            "summary": _as_document(verification.get("summary")),
        }
        verification_summary["integrity_hash"] = sidecar_hash(verification_summary)
        quorum = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "quorum": _as_document(source.get("quorum"))}
        quorum["integrity_hash"] = sidecar_hash(quorum)
        accepted_index = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "items": _as_list(source.get("accepted_evidence"))}
        accepted_index["integrity_hash"] = sidecar_hash(accepted_index)
        accepted_verification = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "source_hash": signoff.get("source_hash"),
            "items": [
                {
                    "evidence_id": item.get("evidence_id"),
                    "response_id": item.get("response_id"),
                    "verification_status": item.get("verification_status"),
                    "verification_report_hash": item.get("verification_report_hash"),
                    "zip_sha256": item.get("zip_sha256"),
                }
                for item in _as_list(accepted_index["items"])
                if isinstance(item, dict)
            ],
        }
        accepted_verification["integrity_hash"] = sidecar_hash(accepted_verification)
        distribution = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "distribution_kit": _as_document(source.get("distribution_kit"))}
        distribution["integrity_hash"] = sidecar_hash(distribution)
        latest_cr = _latest_applied_change_request(self.change_requests_dir(center_id), signoff.get("integrity_hash"))
        change = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "latest_applied_change_request": latest_cr}
        change["integrity_hash"] = sidecar_hash(change)
        chain = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "events": self._history_events(center_id)}
        chain["integrity_hash"] = sidecar_hash(chain)
        report: object = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "package_type": ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE,
            "center_id": center_id,
            "created_at": now,
            "status": "passed",
            "source_hash": signoff.get("source_hash"),
            "signoff_hash": signoff.get("integrity_hash"),
            "summary": {
                "signoff_status": signoff.get("status"),
                "board_readiness": (_as_document(source.get("board"))).get("readiness"),
                "verification_status": (_as_document(source.get("verification"))).get("status"),
                "accepted_evidence_count": len(_as_list(accepted_index.get("items"))),
            },
            "warnings": [],
        }
        report["integrity_hash"] = acceptance_board_signoff_archive_hash(report)
        return {
            "board-signoff-archive-report.json": report,
            "board-signoff.json": signoff,
            "board-verification-summary.json": verification_summary,
            "board-fingerprint-summary.json": board_fingerprint,
            "quorum-fingerprint-summary.json": quorum,
            "accepted-evidence-fingerprint-index.json": accepted_index,
            "accepted-evidence-verification-index.json": accepted_verification,
            "distribution-kit-fingerprint-summary.json": distribution,
            "change-request-summary.json": change,
            "chain-of-custody.json": chain,
            "README.txt": _signoff_archive_readme(signoff),
            "VERIFY.txt": _signoff_archive_verify_text(),
        }

    def _write_cached_sidecars(self, center_id: str, source_hash: str, response_index: DomainDocument, evidence_index: DomainDocument, response_proofs: list[DomainDocument], evidence_summaries: list[DomainDocument]) -> None:
        cache_dir = self._cache_dir(center_id, source_hash)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        _mkdir(cache_dir / "response-proofs")
        _mkdir(cache_dir / "evidence")
        _write_json(cache_dir / "response-index.json", response_index)
        _write_json(cache_dir / "accepted-evidence-index.json", evidence_index)
        for proof in response_proofs:
            response_id = _safe_id(str(proof.get("response_id") or "response"))
            binding = _as_document(proof.get("binding_proof"))
            verification = _as_document(proof.get("verification_summary"))
            binding["source_hash"] = source_hash
            verification["source_hash"] = source_hash
            _write_json(cache_dir / "response-proofs" / f"{response_id}-binding-proof.json", binding)
            _write_json(cache_dir / "response-proofs" / f"{response_id}-verification-summary.json", verification)
        for item in evidence_summaries:
            item["source_hash"] = source_hash
            _write_json(cache_dir / "evidence" / f"{_safe_id(str(item.get('evidence_id') or 'evidence'))}-summary.json", item)

    def _sidecars_for_export(self, center_id: str, source_hash: str) -> DomainDocument:
        report = self.read_report(center_id, default={})
        cache_dir = self._cache_dir(center_id, source_hash)
        response_index = _read_json_default(cache_dir / "response-index.json", default={})
        evidence_index = _read_json_default(cache_dir / "accepted-evidence-index.json", default={})
        response_proofs: list[DomainDocument] = []
        for item in sorted(cache_dir.glob("response-proofs/*-binding-proof.json")):
            response_id = item.name[: -len("-binding-proof.json")]
            response_proofs.append({"response_id": response_id, "binding_proof": _read_json_default(item, default={}), "verification_summary": _read_json_default(cache_dir / "response-proofs" / f"{response_id}-verification-summary.json", default={})})
        evidence_summaries = [_read_json_default(path, default={}) for path in sorted((cache_dir / "evidence").glob("*-summary.json"))]
        board_summary = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": source_hash, "summary": _as_document(report.get("summary")), "readiness": report.get("readiness"), "status": report.get("status")}
        board_summary["integrity_hash"] = sidecar_hash(board_summary)
        quorum = _quorum_evidence(report)
        quorum["integrity_hash"] = sidecar_hash(quorum)
        response_index["integrity_hash"] = sidecar_hash(response_index)
        evidence_index["integrity_hash"] = sidecar_hash(evidence_index)
        return {"board_summary": board_summary, "response_index": response_index, "accepted_evidence_index": evidence_index, "quorum_evidence": quorum, "response_proofs": response_proofs, "evidence_summaries": evidence_summaries}

    def _cache_dir(self, center_id: str, source_hash: str) -> Path:
        return self.root_dir(center_id) / "cache" / _safe_id(str(source_hash or "missing")[:16])
