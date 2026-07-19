# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication import publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, HUB_EXPORT_ENTRIES as HUB_EXPORT_ENTRIES, TRUST_OPERATIONS_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_HUB_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_PACKAGE_TYPE, TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_SCHEMA_VERSION as TRUST_OPERATIONS_SCHEMA_VERSION, hub_hash as hub_hash, hub_manifest_hash as hub_manifest_hash

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

TRUST_OPERATIONS_BLOCKED_KEYS = _make_deferred_global('TRUST_OPERATIONS_BLOCKED_KEYS')
TrustOperationsHubError = _make_deferred_global('TrustOperationsHubError')
TrustOperationsHubNotFoundError = _make_deferred_global('TrustOperationsHubNotFoundError')
TrustOperationsHubStateError = _make_deferred_global('TrustOperationsHubStateError')
_action_type = _make_deferred_global('_action_type')
_append_jsonl = _make_deferred_global('_append_jsonl')
_delivery_action_type = _make_deferred_global('_delivery_action_type')
_delivery_component_id = _make_deferred_global('_delivery_component_id')
_delivery_evidence_from_verification = _make_deferred_global('_delivery_evidence_from_verification')
_delivery_evidence_summary = _make_deferred_global('_delivery_evidence_summary')
_evidence_from_verification = _make_deferred_global('_evidence_from_verification')
_paths = _make_deferred_global('_paths')
_read_json = _make_deferred_global('_read_json')
_read_json_default = _make_deferred_global('_read_json_default')
_read_jsonl = _make_deferred_global('_read_jsonl')
_read_required = _make_deferred_global('_read_required')
_readiness_row = _make_deferred_global('_readiness_row')
_readiness_summary = _make_deferred_global('_readiness_summary')
_requirement_for_component = _make_deferred_global('_requirement_for_component')
_status_from_verification_evidence = _make_deferred_global('_status_from_verification_evidence')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global TRUST_OPERATIONS_BLOCKED_KEYS, TrustOperationsHubError, TrustOperationsHubNotFoundError, TrustOperationsHubStateError, _action_type, _append_jsonl, _delivery_action_type, _delivery_component_id
    global _delivery_evidence_from_verification, _delivery_evidence_summary, _evidence_from_verification, _paths, _read_json, _read_json_default, _read_jsonl
    global _read_required, _readiness_row, _readiness_summary, _requirement_for_component, _status_from_verification_evidence, item
    TRUST_OPERATIONS_BLOCKED_KEYS = namespace.get('TRUST_OPERATIONS_BLOCKED_KEYS', TRUST_OPERATIONS_BLOCKED_KEYS)
    TrustOperationsHubError = namespace.get('TrustOperationsHubError', TrustOperationsHubError)
    TrustOperationsHubNotFoundError = namespace.get('TrustOperationsHubNotFoundError', TrustOperationsHubNotFoundError)
    TrustOperationsHubStateError = namespace.get('TrustOperationsHubStateError', TrustOperationsHubStateError)
    _action_type = namespace.get('_action_type', _action_type)
    _append_jsonl = namespace.get('_append_jsonl', _append_jsonl)
    _delivery_action_type = namespace.get('_delivery_action_type', _delivery_action_type)
    _delivery_component_id = namespace.get('_delivery_component_id', _delivery_component_id)
    _delivery_evidence_from_verification = namespace.get('_delivery_evidence_from_verification', _delivery_evidence_from_verification)
    _delivery_evidence_summary = namespace.get('_delivery_evidence_summary', _delivery_evidence_summary)
    _evidence_from_verification = namespace.get('_evidence_from_verification', _evidence_from_verification)
    _paths = namespace.get('_paths', _paths)
    _read_json = namespace.get('_read_json', _read_json)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_jsonl = namespace.get('_read_jsonl', _read_jsonl)
    _read_required = namespace.get('_read_required', _read_required)
    _readiness_row = namespace.get('_readiness_row', _readiness_row)
    _readiness_summary = namespace.get('_readiness_summary', _readiness_summary)
    _requirement_for_component = namespace.get('_requirement_for_component', _requirement_for_component)
    _status_from_verification_evidence = namespace.get('_status_from_verification_evidence', _status_from_verification_evidence)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


TRUST_OPERATIONS_HUB_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_report"
TRUST_OPERATIONS_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_readiness_matrix"
TRUST_OPERATIONS_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_blocker_register"
TRUST_OPERATIONS_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_manual_action_queue"
TRUST_OPERATIONS_EVIDENCE_BINDING_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_evidence_binding_index"
TRUST_OPERATIONS_VERIFICATION_SUMMARY_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_verification_summary_index"
TRUST_OPERATIONS_SOURCE_STATE_PACKAGE_TYPE = "musicforge_trust_operations_source_state"
TRUST_OPERATIONS_DELIVERY_EVIDENCE_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_evidence_index"
TRUST_OPERATIONS_DELIVERY_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_readiness_matrix"
TRUST_OPERATIONS_DELIVERY_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_delivery_blocker_register"
TRUST_OPERATIONS_DELIVERY_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_delivery_manual_action_queue"
TRUST_OPERATIONS_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_hub_change_request"




class TrustOperationsHubStoreEvidenceMixin:
    def _source_state(self, hub: DomainDocument, report_id: str, payload: DomainDocument) -> DomainDocument:
        states: list[DomainDocument] = []
        for state_path in _paths(payload.get("publication_channel_state_paths") or payload.get("publication_channel_state_path")):
            state = _read_json_default(state_path, default={})
            if not state:
                continue
            current = _as_document(state.get("current_publication"))
            states.append({"center_id": state.get("center_id"), "channel_id": state.get("channel_id"), "state_hash": publication_channel_state_hash(state), "latest_event_hash": state.get("latest_event_hash"), "current_publication_id": current.get("publication_id"), "current_status": current.get("status")})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_SOURCE_STATE_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "sources": {"publication_channel_states": states, "release_signoffs": [], "operations_signoffs": [], "acceptance_board_signoffs": []}}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _evidence_binding_index(self, hub: DomainDocument, report_id: str, payload: DomainDocument, source_state: DomainDocument) -> DomainDocument:
        rows: list[DomainDocument] = []
        for report_path in _paths(payload.get("public_trust_center_verification_paths") or payload.get("public_trust_center_verification_path")):
            report = _read_json_default(report_path, default={})
            rows.append(_evidence_from_verification("public_trust_center:ptc-default", "public_trust_center_verification", report, report_path))
        for report_path in _paths(payload.get("publication_monitoring_verification_paths") or payload.get("publication_monitoring_verification_path")):
            report = _read_json_default(report_path, default={})
            rows.append(_evidence_from_verification("publication-monitoring:public-release", "publication_monitoring_verification", report, report_path))
        for state in source_state.get("sources", {}).get("publication_channel_states", []) if isinstance(source_state.get("sources"), dict) else []:
            if isinstance(state, dict):
                rows.append({"evidence_id": "publication-channel-state:" + str(state.get("channel_id") or "unknown"), "component_type": "publication_channel_state", "package_type": "musicforge_public_trust_center_publication_channel_state", "zip_sha256": None, "manifest_hash": None, "verification_report_hash": None, "source_hash": state.get("state_hash"), "status": state.get("current_status") or "missing", "current_state_refs": {"publication_channel_state_hash": state.get("state_hash"), "latest_event_hash": state.get("latest_event_hash"), "current_publication_id": state.get("current_publication_id")}})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_EVIDENCE_BINDING_INDEX_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "evidence": rows, "summary": {"evidence_count": len(rows), "failed_count": sum(1 for row in rows if row.get("status") == "failed"), "stale_count": sum(1 for row in rows if row.get("status") == "stale")}}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _verification_summary_index(self, hub: DomainDocument, report_id: str, evidence_index: DomainDocument) -> DomainDocument:
        rows = []
        for evidence in evidence_index.get("evidence", []) if isinstance(evidence_index.get("evidence"), list) else []:
            if not isinstance(evidence, dict) or not evidence.get("verification_report_hash"):
                continue
            rows.append({"verification_id": evidence.get("evidence_id"), "component_type": evidence.get("component_type"), "status": evidence.get("status"), "verification_report_hash": evidence.get("verification_report_hash"), "package_zip_sha256": evidence.get("zip_sha256"), "manifest_hash": evidence.get("manifest_hash"), "required_by": [_requirement_for_component(str(evidence.get("component_type") or ""))]})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_VERIFICATION_SUMMARY_INDEX_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "verifications": rows, "summary": {"verification_count": len(rows), "passed_count": sum(1 for row in rows if row.get("status") == "passed"), "failed_count": sum(1 for row in rows if row.get("status") == "failed")}}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _readiness_matrix(self, hub: DomainDocument, report_id: str, evidence_index: DomainDocument, verification_index: DomainDocument, source_state: DomainDocument) -> DomainDocument:
        requirements = _as_document(hub.get("requirements"))
        rows: list[DomainDocument] = []
        by_type = {str(row.get("component_type") or ""): row for row in evidence_index.get("evidence", []) if isinstance(row, dict)}
        if requirements.get("require_public_trust_center_verified", True):
            rows.append(_readiness_row("public-trust-center:ptc-default", "public_trust_center", "public_trust_center_verified", by_type.get("public_trust_center_verification")))
        if requirements.get("require_publication_current", True):
            state_rows = source_state.get("sources", {}).get("publication_channel_states", []) if isinstance(source_state.get("sources"), dict) else []
            state = state_rows[0] if state_rows else {}
            status = "ready" if state and state.get("current_status") not in {"revoked", "superseded"} else "blocked"
            rows.append({"component_id": "publication-channel:" + str(state.get("channel_id") or "missing"), "component_type": "publication_channel", "requirement": "publication_current", "status": status, "severity": "blocking", "evidence_refs": ["publication-channel-state"], "summary": "Publication channel state is current." if status == "ready" else "Publication channel state is missing or revoked/superseded."})
        if requirements.get("require_publication_monitoring_clean", True):
            evidence = by_type.get("publication_monitoring_verification")
            rows.append(_readiness_row("publication-monitoring:public-release", "publication_monitoring", "publication_monitoring_clean", evidence))
            monitoring_summary = evidence.get("summary") if isinstance(evidence, dict) and isinstance(evidence.get("summary"), dict) else {}
            if requirements.get("require_no_open_critical_incidents", True) and evidence and _as_document(monitoring_summary).get("critical_incidents", 0):
                rows.append({"component_id": "publication-monitoring:public-release", "component_type": "publication_monitoring", "requirement": "no_open_critical_incidents", "status": "blocked", "severity": "blocking", "evidence_refs": ["publication-monitoring-verification"], "source_check_id": "ptcpm_require_no_open_critical_incidents", "summary": "Publication monitoring has open critical incidents."})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_READINESS_MATRIX_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "rows": rows, "summary": _readiness_summary(rows)}
        data["source"] = {"evidence_binding_index_hash": evidence_index.get("integrity_hash"), "verification_summary_index_hash": verification_index.get("integrity_hash"), "source_state_hash": source_state.get("integrity_hash")}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _blocker_register(self, hub: DomainDocument, report_id: str, readiness: DomainDocument) -> DomainDocument:
        blockers = []
        for index, row in enumerate([row for row in readiness.get("rows", []) if isinstance(row, dict) and row.get("status") in {"blocked", "stale", "missing", "not_configured"} and row.get("severity") == "blocking"], start=1):
            blockers.append({"blocker_id": f"hub-blocker-{index:06d}", "component_id": row.get("component_id"), "requirement": row.get("requirement"), "severity": "critical" if row.get("status") == "blocked" else "high", "status": "open", "source_check_id": row.get("source_check_id") or row.get("requirement"), "evidence_ref": (row.get("evidence_refs") or [None])[0], "manual_action_id": f"hub-action-{index:06d}", "message": row.get("summary")})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_BLOCKER_REGISTER_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "blockers": blockers, "summary": {"blocker_count": len(blockers), "critical_count": sum(1 for row in blockers if row.get("severity") == "critical"), "high_count": sum(1 for row in blockers if row.get("severity") == "high")}}
        data["source"] = {"readiness_matrix_hash": readiness.get("integrity_hash")}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _manual_action_queue(self, hub: DomainDocument, report_id: str, blocker_register: DomainDocument) -> DomainDocument:
        actions = []
        for blocker in blocker_register.get("blockers", []) if isinstance(blocker_register.get("blockers"), list) else []:
            if not isinstance(blocker, dict):
                continue
            actions.append({"action_id": blocker.get("manual_action_id"), "action_type": _action_type(str(blocker.get("requirement") or "")), "status": "manual_required", "component_id": blocker.get("component_id"), "reason": blocker.get("message"), "allowed_automation": False, "suggested_cli": "python -m song_agent.cli trust-operations-hub --refresh"})
        data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": TRUST_OPERATIONS_MANUAL_ACTION_QUEUE_PACKAGE_TYPE, "hub_id": hub.get("hub_id"), "report_id": report_id, "actions": actions, "summary": {"manual_required_count": len(actions), "safe_action_count": 0}}
        data["source"] = {"blocker_register_hash": blocker_register.get("integrity_hash")}
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_evidence_index(self, hub: DomainDocument, report_id: str, payload: DomainDocument) -> DomainDocument:
        rows: list[DomainDocument] = []
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            paths = _paths(payload.get(spec["payload_keys"]) or payload.get(spec["payload_key"]))
            for index, report_path in enumerate(paths, start=1):
                report = _read_json_default(report_path, default={})
                component_id = _delivery_component_id(spec, report, index)
                rows.append(_delivery_evidence_from_verification(component_id, spec["component_type"], spec["requirement"], report, report_path))
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_EVIDENCE_INDEX_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "evidence": sorted(rows, key=lambda row: (str(row.get("component_type") or ""), str(row.get("component_id") or ""))),
            "summary": _delivery_evidence_summary(rows),
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_readiness_matrix(self, hub: DomainDocument, report_id: str, delivery_evidence: DomainDocument) -> DomainDocument:
        requirements = _as_document(hub.get("requirements"))
        rows: list[DomainDocument] = []
        evidence_rows = [row for row in delivery_evidence.get("evidence", []) if isinstance(row, dict)]
        by_type: dict[str, list[DomainDocument]] = {}
        for row in evidence_rows:
            by_type.setdefault(str(row.get("component_type") or ""), []).append(row)
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            requirement = str(spec["requirement"])
            required = bool(requirements.get("require_" + requirement, False))
            typed_rows = by_type.get(str(spec["component_type"]), [])
            if not typed_rows:
                if not required:
                    continue
                rows.append(
                    {
                        "component_id": str(spec["component_id_prefix"]) + ":missing",
                        "component_type": spec["component_type"],
                        "requirement": requirement,
                        "status": "missing",
                        "severity": "blocking",
                        "evidence_refs": [],
                        "source_check_id": requirement,
                        "summary": f"{requirement} evidence is missing.",
                    }
                )
                continue
            for evidence in typed_rows:
                status = _status_from_verification_evidence(evidence)
                rows.append(
                    {
                        "component_id": evidence.get("component_id"),
                        "component_type": evidence.get("component_type"),
                        "requirement": requirement,
                        "status": status,
                        "severity": "blocking",
                        "evidence_refs": [str(evidence.get("evidence_id") or evidence.get("component_id") or "")],
                        "source_check_id": requirement,
                        "summary": f"{requirement} is {status}.",
                    }
                )
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_READINESS_MATRIX_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "rows": sorted(rows, key=lambda row: (str(row.get("component_type") or ""), str(row.get("component_id") or ""), str(row.get("requirement") or ""))),
            "summary": _readiness_summary(rows),
            "source": {"delivery_evidence_index_hash": delivery_evidence.get("integrity_hash")},
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_blocker_register(self, hub: DomainDocument, report_id: str, delivery_readiness: DomainDocument) -> DomainDocument:
        blockers = []
        for index, row in enumerate([row for row in delivery_readiness.get("rows", []) if isinstance(row, dict) and row.get("status") in {"blocked", "stale", "missing", "not_configured"} and row.get("severity") == "blocking"], start=1):
            blockers.append(
                {
                    "blocker_id": f"hub-delivery-blocker-{index:06d}",
                    "component_id": row.get("component_id"),
                    "requirement": row.get("requirement"),
                    "severity": "critical" if row.get("status") == "blocked" else "high",
                    "status": "open",
                    "source_check_id": row.get("source_check_id") or row.get("requirement"),
                    "evidence_ref": (row.get("evidence_refs") or [None])[0],
                    "manual_action_id": f"hub-delivery-action-{index:06d}",
                    "message": row.get("summary"),
                }
            )
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_BLOCKER_REGISTER_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "blockers": blockers,
            "summary": {"blocker_count": len(blockers), "critical_count": sum(1 for row in blockers if row.get("severity") == "critical"), "high_count": sum(1 for row in blockers if row.get("severity") == "high")},
            "source": {"delivery_readiness_matrix_hash": delivery_readiness.get("integrity_hash")},
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _delivery_manual_action_queue(self, hub: DomainDocument, report_id: str, delivery_blockers: DomainDocument) -> DomainDocument:
        actions = []
        for blocker in delivery_blockers.get("blockers", []) if isinstance(delivery_blockers.get("blockers"), list) else []:
            if not isinstance(blocker, dict):
                continue
            actions.append(
                {
                    "action_id": blocker.get("manual_action_id"),
                    "action_type": _delivery_action_type(str(blocker.get("requirement") or "")),
                    "status": "manual_required",
                    "component_id": blocker.get("component_id"),
                    "reason": blocker.get("message"),
                    "allowed_automation": False,
                    "suggested_cli": "python -m song_agent.cli trust-operations-hub --refresh --export --zip --verify",
                }
            )
        data = {
            "schema_version": TRUST_OPERATIONS_SCHEMA_VERSION,
            "package_type": TRUST_OPERATIONS_DELIVERY_MANUAL_ACTION_QUEUE_PACKAGE_TYPE,
            "hub_id": hub.get("hub_id"),
            "report_id": report_id,
            "actions": actions,
            "summary": {"manual_required_count": len(actions), "safe_action_count": 0},
            "source": {"delivery_blocker_register_hash": delivery_blockers.get("integrity_hash")},
        }
        data["integrity_hash"] = hub_hash(data)
        return data

    def _read_report_docs(self, hub_id: str, report_id: str) -> dict[str, DomainDocument]:
        docs = {
            "hub_report": _read_required(self.report_path(hub_id, report_id)),
            "readiness_matrix": _read_required(self.readiness_matrix_path(hub_id, report_id)),
            "blocker_register": _read_required(self.blocker_register_path(hub_id, report_id)),
            "manual_action_queue": _read_required(self.manual_action_queue_path(hub_id, report_id)),
            "evidence_binding_index": _read_required(self.evidence_binding_index_path(hub_id, report_id)),
            "verification_summary_index": _read_required(self.verification_summary_index_path(hub_id, report_id)),
            "source_state": _read_required(self.source_state_path(hub_id, report_id)),
            "delivery_evidence_index": _read_required(self.delivery_evidence_index_path(hub_id, report_id)),
            "delivery_readiness_matrix": _read_required(self.delivery_readiness_matrix_path(hub_id, report_id)),
            "delivery_blocker_register": _read_required(self.delivery_blocker_register_path(hub_id, report_id)),
            "delivery_manual_action_queue": _read_required(self.delivery_manual_action_queue_path(hub_id, report_id)),
        }
        return docs

    def _read_source_paths(self, hub_id: str, report_id: str) -> DomainDocument:
        return _read_json_default(self.source_paths_path(hub_id, report_id), default={})

    def _assert_report_docs_current(self, docs: dict[str, DomainDocument]) -> None:
        if docs["hub_report"].get("integrity_hash") != hub_hash(docs["hub_report"]):
            raise TrustOperationsHubStateError("Hub report integrity failed.")
        for key in ("readiness_matrix", "blocker_register", "manual_action_queue", "evidence_binding_index", "verification_summary_index", "source_state", "delivery_evidence_index", "delivery_readiness_matrix", "delivery_blocker_register", "delivery_manual_action_queue"):
            if docs[key].get("integrity_hash") != hub_hash(docs[key]):
                raise TrustOperationsHubStateError(f"{key} integrity failed.")
        source = _as_document(docs["hub_report"].get("source"))
        expected = {
            "readiness_matrix_hash": docs["readiness_matrix"].get("integrity_hash"),
            "blocker_register_hash": docs["blocker_register"].get("integrity_hash"),
            "manual_action_queue_hash": docs["manual_action_queue"].get("integrity_hash"),
            "evidence_binding_index_hash": docs["evidence_binding_index"].get("integrity_hash"),
            "verification_summary_index_hash": docs["verification_summary_index"].get("integrity_hash"),
            "source_state_hash": docs["source_state"].get("integrity_hash"),
            "delivery_evidence_index_hash": docs["delivery_evidence_index"].get("integrity_hash"),
            "delivery_readiness_matrix_hash": docs["delivery_readiness_matrix"].get("integrity_hash"),
            "delivery_blocker_register_hash": docs["delivery_blocker_register"].get("integrity_hash"),
            "delivery_manual_action_queue_hash": docs["delivery_manual_action_queue"].get("integrity_hash"),
        }
        for key, value in expected.items():
            if source.get(key) != value:
                raise TrustOperationsHubStateError("Hub report source references are stale.")

    def _assert_external_sources_current(self, docs: dict[str, DomainDocument], source_paths: DomainDocument) -> None:
        state_hashes = {
            str(item.get("state_hash") or "")
            for item in docs["source_state"].get("sources", {}).get("publication_channel_states", [])
            if isinstance(item, dict)
        }
        for state_path in _paths(source_paths.get("publication_channel_state_paths")):
            state = _read_json_default(state_path, default={})
            if not state:
                raise TrustOperationsHubStateError("Trust Operations Hub publication channel state is missing.")
            if publication_channel_state_hash(state) not in state_hashes:
                raise TrustOperationsHubStateError("Trust Operations Hub publication channel state changed. Refresh before export.")
            current = _as_document(state.get("current_publication"))
            if not current or current.get("status") in {"revoked", "superseded"}:
                raise TrustOperationsHubStateError("Trust Operations Hub publication channel is no longer current. Refresh before export.")
        evidence_rows = [row for row in docs["evidence_binding_index"].get("evidence", []) if isinstance(row, dict)]
        for component_type, key in (
            ("public_trust_center_verification", "public_trust_center_verification_paths"),
            ("publication_monitoring_verification", "publication_monitoring_verification_paths"),
        ):
            expected_rows = [row for row in evidence_rows if row.get("component_type") == component_type]
            expected_hashes = {str(row.get("verification_report_hash") or "") for row in expected_rows}
            for report_path in _paths(source_paths.get(key)):
                report = _read_json_default(report_path, default={})
                if verification_hash(report) not in expected_hashes:
                    raise TrustOperationsHubStateError("Trust Operations Hub external verification report changed. Refresh before export.")
        delivery_rows = [row for row in docs["delivery_evidence_index"].get("evidence", []) if isinstance(row, dict)]
        for spec in DELIVERY_VERIFICATION_COMPONENTS:
            expected_rows = [row for row in delivery_rows if row.get("component_type") == spec["component_type"]]
            expected_hashes = {str(row.get("verification_report_hash") or "") for row in expected_rows}
            for report_path in _paths(source_paths.get(spec["payload_keys"])):
                report = _read_json_default(report_path, default={})
                if verification_hash(report) not in expected_hashes:
                    raise TrustOperationsHubStateError("Trust Operations Hub delivery verification report changed. Refresh before export.")

    def _ensure_unsigned(self, hub_id: str) -> None:
        if self._signoff_state(hub_id)["status"] == "signed":
            raise TrustOperationsHubStateError("Signed Trust Operations Hub cannot be modified. Reset signoff with an approved change request first.")

    def _signoff_state(self, hub_id: str) -> DomainDocument:
        state: DomainDocument = {"status": "unsigned", "signoff_hash": None, "change_request_id": None}
        for row in _read_jsonl(self.signoff_history_path(hub_id)):
            event_type = str(row.get("event_type") or "")
            if event_type == "signed" and row.get("signoff_hash"):
                state = {"status": "signed", "signoff_hash": row.get("signoff_hash"), "report_id": row.get("report_id")}
            elif event_type == "reset" and state.get("status") == "signed":
                if row.get("signoff_hash") != state.get("signoff_hash"):
                    continue
                change_request_id = str(row.get("change_request_id") or "")
                try:
                    cr = self._read_change_request(hub_id, change_request_id)
                except TrustOperationsHubError:
                    continue
                if (
                    cr.get("status") == "applied"
                    and cr.get("applied_at")
                    and cr.get("applied_signoff_hash") == row.get("signoff_hash")
                    and cr.get("integrity_hash") == hub_hash(cr)
                    and cr.get("integrity_hash") == row.get("change_request_hash")
                ):
                    state = {"status": "reset", "signoff_hash": row.get("signoff_hash"), "change_request_id": change_request_id}
        if state.get("status") == "signed":
            signoff = _read_json_default(self.signoff_path(hub_id), default={})
            if signoff and signoff.get("integrity_hash") != state.get("signoff_hash"):
                state["signoff_file_status"] = "mismatch"
            elif signoff:
                state["signoff_file_status"] = "present"
            else:
                state["signoff_file_status"] = "missing"
        return state

    def _signoff_summary(self, hub_id: str) -> DomainDocument:
        signoff = _read_json_default(self.signoff_path(hub_id), default={})
        summary = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "package_type": "musicforge_trust_operations_hub_signoff_summary", "hub_id": hub_id, "status": signoff.get("status") or "unsigned", "signoff_hash": signoff.get("integrity_hash"), "report_id": signoff.get("report_id")}
        summary["integrity_hash"] = hub_hash(summary)
        return summary

    def _read_change_request(self, hub_id: str, change_request_id: str) -> DomainDocument:
        path = self.change_request_path(hub_id, change_request_id)
        if not path.exists():
            raise TrustOperationsHubNotFoundError("Trust Operations Hub change request not found.")
        return _read_json(path)

    def _append_event(self, hub_id: str, event_type: str, payload: DomainDocument, *, now: str) -> None:
        rows = _read_jsonl(self.events_path(hub_id))
        event = {"event_id": f"trust-hub-event-{len(rows) + 1:06d}", "event_type": event_type, "created_at": now, "payload": sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_BLOCKED_KEYS), "previous_event_hash": rows[-1].get("event_hash") if rows else None}
        event["payload_hash"] = stable_hash(event["payload"])
        event["event_hash"] = stable_hash(event)
        _append_jsonl(self.events_path(hub_id), event)
