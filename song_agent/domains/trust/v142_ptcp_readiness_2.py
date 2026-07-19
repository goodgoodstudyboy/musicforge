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
from song_agent.domains.trust.v142_ptcp_readiness import PublicTrustCenterPublicationStoreReadinessMixin
from song_agent.domains.trust import v142_ptcp_readiness as _v142_ptcp_readiness
from song_agent.domains.trust.v142_ptcp_evidence import PublicTrustCenterPublicationStoreEvidenceMixin
from song_agent.domains.trust import v142_ptcp_evidence as _v142_ptcp_evidence

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

ch = _make_deferred_global('ch')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch, part
    ch = namespace.get('ch', ch)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


PUBLICATION_SCHEMA_VERSION = 1
PUBLICATION_CHANNEL_PACKAGE_TYPE = "musicforge_public_trust_center_publication_channel"
PUBLICATION_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_publication_report"
PUBLICATION_CHANNEL_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
PUBLICATION_ALLOWED_CHANNEL_TYPES = {"internal_preview", "partner_handoff", "public_release", "archive_mirror"}




def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:80] or "item"

def _next_channel_id(root: Path) -> str:
    count = len(list(root.glob("ptc-channel-*"))) if root.exists() else 0
    return f"ptc-channel-{count + 1:06d}"

def _next_publication_id(root: Path) -> str:
    count = len(list(root.glob("ptc-pub-*"))) if root.exists() else 0
    return f"ptc-pub-{count + 1:06d}"

def _sanitize(payload: object) -> DomainDocument:
    return sanitize_metadata(payload, blocked_keys=PUBLICATION_BLOCKED_KEYS)

def _html(value: object) -> str:
    import html

    return html.escape(str(value or ""))
