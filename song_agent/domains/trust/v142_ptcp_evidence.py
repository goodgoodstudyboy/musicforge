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
from song_agent.domains.trust.public_trust_center import PublicTrustCenterStore as PublicTrustCenterStore
from song_agent.domains.trust.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore as PublicTrustCenterAcceptanceBoardStore
from song_agent.domains.trust.public_trust_center_acceptance_board import acceptance_board_verification_hash as acceptance_board_verification_hash
from song_agent.domains.trust.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package as verify_public_trust_center_acceptance_board_signoff_archive_package, write_public_trust_center_acceptance_board_signoff_archive_verification_report as write_public_trust_center_acceptance_board_signoff_archive_verification_report
from song_agent.domains.trust.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package as verify_public_trust_center_acceptance_board_package
from song_agent.domains.trust.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore as PublicTrustCenterAnchorRegistryStore
from song_agent.domains.trust.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package as verify_public_trust_center_anchor_registry_package, write_public_trust_center_anchor_registry_verification_report as write_public_trust_center_anchor_registry_verification_report
from song_agent.domains.trust.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore as PublicTrustCenterAnchorTransparencyStore
from song_agent.domains.trust.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package as verify_public_trust_center_anchor_transparency_package, write_public_trust_center_anchor_transparency_verification_report as write_public_trust_center_anchor_transparency_verification_report
from song_agent.domains.trust.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore as PublicTrustCenterDistributionKitStore
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore as PublicTrustCenterDistributionKitAcceptanceStore, verification_hash as accepted_evidence_verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package, write_public_trust_center_distribution_kit_accepted_evidence_verification_report as write_public_trust_center_distribution_kit_accepted_evidence_verification_report
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package, write_public_trust_center_distribution_kit_verification_report as write_public_trust_center_distribution_kit_verification_report
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package as verify_public_trust_center_package, write_public_trust_center_verification_report as write_public_trust_center_verification_report
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_publication_contracts import PUBLICATION_BLOCKED_KEYS as PUBLICATION_BLOCKED_KEYS, PUBLICATION_CHANNEL_STATE_HASH_EXCLUDE_KEYS as PUBLICATION_CHANNEL_STATE_HASH_EXCLUDE_KEYS, PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE as PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE, PUBLICATION_MANIFEST_HASH_EXCLUDE_KEYS as PUBLICATION_MANIFEST_HASH_EXCLUDE_KEYS, PUBLICATION_PACKAGE_TYPE as PUBLICATION_PACKAGE_TYPE, PUBLICATION_REPORT_HASH_EXCLUDE_KEYS as PUBLICATION_REPORT_HASH_EXCLUDE_KEYS, PUBLICATION_REQUIRED_PACKAGE_KEYS as PUBLICATION_REQUIRED_PACKAGE_KEYS, PUBLICATION_SIDECAR_HASH_EXCLUDE_KEYS as PUBLICATION_SIDECAR_HASH_EXCLUDE_KEYS, publication_channel_state_hash as publication_channel_state_hash, publication_manifest_hash as publication_manifest_hash, publication_report_hash as publication_report_hash, sidecar_hash as sidecar_hash

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

PublicTrustCenterPublicationStateError = _make_deferred_global('PublicTrustCenterPublicationStateError')
_expected_entries = _make_deferred_global('_expected_entries')
_publication_lifecycle_from_events = _make_deferred_global('_publication_lifecycle_from_events')
_publication_state_row = _make_deferred_global('_publication_state_row')
_read_json_default = _make_deferred_global('_read_json_default')
_read_jsonl = _make_deferred_global('_read_jsonl')
_sanitize = _make_deferred_global('_sanitize')
_write_json = _make_deferred_global('_write_json')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
publication_report_integrity_ok = _make_deferred_global('publication_report_integrity_ok')
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterPublicationStateError, _expected_entries, _publication_lifecycle_from_events, _publication_state_row, _read_json_default, _read_jsonl, _sanitize
    global _write_json, item, key, publication_report_integrity_ok, value
    PublicTrustCenterPublicationStateError = namespace.get('PublicTrustCenterPublicationStateError', PublicTrustCenterPublicationStateError)
    _expected_entries = namespace.get('_expected_entries', _expected_entries)
    _publication_lifecycle_from_events = namespace.get('_publication_lifecycle_from_events', _publication_lifecycle_from_events)
    _publication_state_row = namespace.get('_publication_state_row', _publication_state_row)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _read_jsonl = namespace.get('_read_jsonl', _read_jsonl)
    _sanitize = namespace.get('_sanitize', _sanitize)
    _write_json = namespace.get('_write_json', _write_json)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    publication_report_integrity_ok = namespace.get('publication_report_integrity_ok', publication_report_integrity_ok)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


PUBLICATION_SCHEMA_VERSION = 1
PUBLICATION_CHANNEL_PACKAGE_TYPE = "musicforge_public_trust_center_publication_channel"
PUBLICATION_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_publication_report"
PUBLICATION_CHANNEL_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PUBLICATION_ALLOWED_CHANNEL_TYPES = {"internal_preview", "partner_handoff", "public_release", "archive_mirror"}




class PublicTrustCenterPublicationStoreEvidenceMixin:
    def _verification_index(self, report: DomainDocument) -> DomainDocument:
        data = {"schema_version": PUBLICATION_SCHEMA_VERSION, "publication_id": report.get("publication_id"), "source_hash": report.get("source_hash"), "items": report.get("source", {}).get("verifications", [])}
        data["integrity_hash"] = sidecar_hash(data)
        return data

    def _mirror_policy(self, report: DomainDocument) -> DomainDocument:
        source = _as_document(report.get("source"))
        allowed = _expected_entries(source)
        data = {
            "schema_version": PUBLICATION_SCHEMA_VERSION,
            "publication_id": report.get("publication_id"),
            "channel_id": report.get("channel_id"),
            "source_hash": report.get("source_hash"),
            "allowed_entries": sorted(allowed),
            "allow_extra_files": False,
            "nested_zip_allowlist": sorted(path for path in allowed if path.lower().endswith(".zip")),
        }
        data["integrity_hash"] = sidecar_hash(data)
        return data

    def _findings(self, channel: DomainDocument, source: DomainDocument) -> tuple[list[DomainDocument], list[DomainDocument], list[DomainDocument]]:
        checks: list[DomainDocument] = []
        blockers: list[DomainDocument] = []
        warnings: list[DomainDocument] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if passed:
                return
            (warnings if warning else blockers).append({"check_id": check_id, "severity": row["severity"], "message": message})

        package_keys = {str(item.get("package_key") or "") for item in source.get("packages", []) if isinstance(item, dict)}
        verification_statuses = {str(item.get("verification_key") or ""): item.get("status") for item in source.get("verifications", []) if isinstance(item, dict)}
        missing = sorted(PUBLICATION_REQUIRED_PACKAGE_KEYS - package_keys)
        check("ptcpub_required_packages_present", not missing, "Required publication packages are present." if not missing else "Missing packages: " + ", ".join(missing))
        failed = sorted(key for key in PUBLICATION_REQUIRED_PACKAGE_KEYS if verification_statuses.get(key) != "passed")
        check("ptcpub_required_verifications_passed", not failed, "Required package verifications passed." if not failed else "Failed verifications: " + ", ".join(failed))
        check("ptcpub_acceptance_board_signoff_present", bool(source.get("acceptance_board_signoff_hash")), "Acceptance Board signoff is present.")
        if (_as_document(channel.get("policy"))).get("require_accepted_evidence", True):
            check("ptcpub_accepted_evidence_present", bool(source.get("accepted_evidence")), "Accepted Evidence is included.")
        return checks, blockers, warnings

    def _ensure_exportable(self, center_id: str, channel_id: str, publication_id: str, report: DomainDocument) -> None:
        if report.get("status") in {"revoked", "superseded"}:
            raise PublicTrustCenterPublicationStateError("Public Trust Center publication is not exportable after revoke/supersede.")
        if not publication_report_integrity_ok(report):
            raise PublicTrustCenterPublicationStateError("Public Trust Center publication report integrity failed.")
        channel = self.read_channel(center_id, channel_id)
        current = self._build_source(center_id, channel)
        if report.get("source") != current or report.get("source_hash") != stable_hash(current):
            raise PublicTrustCenterPublicationStateError("Public Trust Center publication report is stale. Refresh before export.")
        if report.get("status") == "failed":
            raise PublicTrustCenterPublicationStateError("Public Trust Center publication report is failed.")

    def _append_event(self, center_id: str, channel_id: str, event_type: str, payload: DomainDocument, *, now: str) -> None:
        path = self.events_path(center_id, channel_id)
        events = _read_jsonl(path)
        previous = events[-1].get("event_hash") if events else None
        clean = _sanitize(payload)
        event = {"schema_version": PUBLICATION_SCHEMA_VERSION, "event_id": f"ptc-pub-event-{len(events) + 1:06d}", "channel_id": channel_id, "event_type": event_type, "created_at": now, "payload": clean, "payload_hash": stable_hash(clean), "previous_event_hash": previous}
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        self._write_channel_state(center_id, channel_id, now=now)

    def _write_channel_state(self, center_id: str, channel_id: str, *, now: str) -> DomainDocument:
        events = _read_jsonl(self.events_path(center_id, channel_id))
        event_state = _publication_lifecycle_from_events(events)
        current = _read_json_default(self.current_publication_path(center_id, channel_id), default={})
        publications: list[DomainDocument] = []
        seen: set[str] = set()
        snapshots = self.snapshots_dir(center_id, channel_id)
        if snapshots.exists():
            for report_path in sorted(snapshots.glob("*/publication-report.json")):
                report = _read_json_default(report_path, default={})
                publication_id = str(report.get("publication_id") or report_path.parent.name)
                seen.add(publication_id)
                derived = event_state.get(publication_id, {})
                publications.append(_publication_state_row(publication_id, report, derived, current, report_path.parent))
        for publication_id, derived in sorted(event_state.items()):
            if publication_id in seen:
                continue
            publications.append(_publication_state_row(publication_id, {}, derived, current, None))
        state = {
            "schema_version": PUBLICATION_SCHEMA_VERSION,
            "package_type": PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE,
            "center_id": center_id,
            "channel_id": channel_id,
            "generated_at": now,
            "current_publication": current,
            "publications": sorted(publications, key=lambda item: str(item.get("publication_id") or "")),
            "events": events,
            "event_count": len(events),
            "latest_event_hash": events[-1].get("event_hash") if events else None,
        }
        state["integrity_hash"] = publication_channel_state_hash(state)
        _write_json(self.channel_state_path(center_id, channel_id), state)
        return state

    def _history_has_state_event(self, center_id: str, channel_id: str, report: DomainDocument, event_type: str) -> bool:
        for event in _read_jsonl(self.events_path(center_id, channel_id)):
            if event.get("event_type") != event_type:
                continue
            payload = _as_document(event.get("payload"))
            if payload.get("source_hash") == report.get("source_hash") and payload.get("publication_id") == report.get("publication_id"):
                return True
        return False
