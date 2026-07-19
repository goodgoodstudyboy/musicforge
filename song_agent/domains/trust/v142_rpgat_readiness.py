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
from song_agent.domains.trust.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore as ReleasePortfolioGovernanceAttestationStore
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore as ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore, accepted_evidence_summary as accepted_evidence_summary
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_public_summary_from_portfolio_dir as accepted_evidence_public_summary_from_portfolio_dir, accepted_evidence_verification_summary_from_portfolio_dir as accepted_evidence_verification_summary_from_portfolio_dir
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_verifier import verify_release_portfolio_governance_attestation_accepted_evidence as verify_release_portfolio_governance_attestation_accepted_evidence
from song_agent.domains.trust.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore as ReleasePortfolioGovernanceAttestationPortalStore
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal as verify_release_portfolio_governance_attestation_portal
from song_agent.domains.trust.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore as ReleasePortfolioGovernanceAttestationRegistryStore, registry_summary as registry_summary
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry as verify_release_portfolio_governance_attestation_registry
from song_agent.domains.trust.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation as verify_release_portfolio_governance_attestation
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_contracts import TRANSPARENCY_BLOCKED_KEYS as TRANSPARENCY_BLOCKED_KEYS, TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS as TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS, TRANSPARENCY_FEED_HASH_EXCLUDE_KEYS as TRANSPARENCY_FEED_HASH_EXCLUDE_KEYS, TRANSPARENCY_FEED_PACKAGE_TYPE as TRANSPARENCY_FEED_PACKAGE_TYPE, TRANSPARENCY_MANIFEST_HASH_EXCLUDE_KEYS as TRANSPARENCY_MANIFEST_HASH_EXCLUDE_KEYS, TRANSPARENCY_NOTICE_HASH_EXCLUDE_KEYS as TRANSPARENCY_NOTICE_HASH_EXCLUDE_KEYS, TRANSPARENCY_PACKAGE_TYPE as TRANSPARENCY_PACKAGE_TYPE, TRANSPARENCY_REPORT_PACKAGE_TYPE as TRANSPARENCY_REPORT_PACKAGE_TYPE, _accepted_evidence_current as _accepted_evidence_current, _build_events as _build_events, _build_notices as _build_notices, transparency_event_hash as transparency_event_hash, transparency_feed_hash as transparency_feed_hash, transparency_manifest_hash as transparency_manifest_hash, transparency_notice_hash as transparency_notice_hash, transparency_summary as transparency_summary

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
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch, key
    ch = namespace.get('ch', ch)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


TRANSPARENCY_SCHEMA_VERSION = 1
TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}




class ReleasePortfolioGovernanceAttestationTransparencyError(ValueError):
    pass

class ReleasePortfolioGovernanceAttestationTransparencyNotFoundError(ReleasePortfolioGovernanceAttestationTransparencyError):
    pass

class ReleasePortfolioGovernanceAttestationTransparencyStateError(ReleasePortfolioGovernanceAttestationTransparencyError):
    pass

def transparency_feed_integrity_ok(feed: DomainDocument | None) -> bool:
    data = _as_document(feed)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_feed_hash(data)

def transparency_report_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS})

def transparency_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_report_hash(data)

def transparency_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_manifest_hash(data)

def transparency_notice_integrity_ok(notice: DomainDocument | None) -> bool:
    data = _as_document(notice)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_notice_hash(data)

def _report_from_feed(feed: DomainDocument, *, now: str) -> DomainDocument:
    source = {
        "feed_hash": feed.get("integrity_hash"),
        "feed_source_hash": feed.get("source_hash"),
        "public_state_hash": (_as_document(feed.get("source"))).get("public_state_hash"),
        "registry_manifest_hash": (_as_document(feed.get("source"))).get("registry_manifest_hash"),
        "portal_manifest_hash": (_as_document(feed.get("source"))).get("portal_manifest_hash"),
        "accepted_evidence_manifest_hash": (_as_document(feed.get("source"))).get("accepted_evidence_manifest_hash"),
    }
    report = {
        "schema_version": TRANSPARENCY_SCHEMA_VERSION,
        "package_type": TRANSPARENCY_REPORT_PACKAGE_TYPE,
        "portfolio_id": feed.get("portfolio_id"),
        "attestation_profile": feed.get("attestation_profile"),
        "generated_at": now,
        "status": "failed" if feed.get("status") == "failed" else "warning" if feed.get("status") == "warning" else "passed",
        "readiness": feed.get("readiness"),
        "source": source,
        "source_hash": stable_hash(source),
        "summary": _as_document(feed.get("summary")),
        "checks": _as_list(feed.get("checks")),
        "blockers": _as_list(feed.get("blockers")),
        "warnings": _as_list(feed.get("warnings")),
    }
    report["integrity_hash"] = transparency_report_hash(report)
    return sanitize_metadata(report, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

def _feed_summary(public_state: DomainDocument, events: list[DomainDocument], notices: list[DomainDocument], blockers: list[DomainDocument], warnings: list[DomainDocument]) -> DomainDocument:
    registry = _as_document(public_state.get("registry"))
    accepted = _as_document(public_state.get("accepted_evidence"))
    return sanitize_metadata(
        {
            "event_count": len(events),
            "notice_count": len(notices),
            "current_entry_id": registry.get("current_entry_id"),
            "current_certificate_id": registry.get("current_certificate_id"),
            "external_review_status": accepted.get("external_review_status") or "missing",
            "latest_notice_type": notices[-1].get("notice_type") if notices else None,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        blocked_keys=TRANSPARENCY_BLOCKED_KEYS,
    )

def _data_documents(feed: DomainDocument) -> dict[str, DomainDocument]:
    state = _as_document(feed.get("current_public_state"))
    source = _as_document(feed.get("source"))
    registry = _as_document(state.get("registry"))
    portal = _as_document(state.get("portal"))
    attestation = _as_document(state.get("public_attestation"))
    accepted = _as_document(state.get("accepted_evidence"))
    docs = {
        "current-public-state.json": {"source_hash": feed.get("source_hash"), "public_state_hash": source.get("public_state_hash"), "current_public_state": state},
        "package-fingerprints.json": {"source_hash": feed.get("source_hash"), **source},
        "registry-binding-summary.json": {"source_hash": feed.get("source_hash"), **registry},
        "portal-binding-summary.json": {"source_hash": feed.get("source_hash"), **portal},
        "attestation-binding-summary.json": {"source_hash": feed.get("source_hash"), **attestation},
    }
    if accepted:
        docs["accepted-evidence-binding-summary.json"] = {"feed_source_hash": feed.get("source_hash"), **accepted}
    return sanitize_metadata(docs, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

def _state_tuple(feed: DomainDocument) -> dict[str, str]:
    return {"source_hash": str(feed.get("source_hash") or ""), "integrity_hash": str(feed.get("integrity_hash") or "")}

def _manifest_state(manifest: DomainDocument) -> dict[str, str]:
    feed_row = _as_document(manifest.get("feed"))
    return {"source_hash": str(manifest.get("source_hash") or ""), "integrity_hash": str(feed_row.get("integrity_hash") or "")}

def _event_chain_valid(events: list[DomainDocument]) -> bool:
    previous = ""
    seen: set[str] = set()
    for event in events:
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in seen:
            return False
        seen.add(event_id)
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("event_hash") != transparency_event_hash(event):
            return False
        previous = str(event.get("event_hash") or "")
    return True

def _readme(feed: DomainDocument) -> str:
    summary = _as_document(feed.get("summary"))
    return "\n".join(
        [
            "MusicForge Release Portfolio Governance Attestation Transparency Feed",
            "",
            f"Portfolio ID: {feed.get('portfolio_id')}",
            f"Profile: {feed.get('attestation_profile')}",
            f"Status: {feed.get('status')}",
            f"Events: {summary.get('event_count', 0)}",
            f"Notices: {summary.get('notice_count', 0)}",
            "This package contains public-safe transparency summaries only.",
            "It does not contain nested Registry, Portal, Public Attestation, Evidence Vault, or Accepted Evidence ZIP files.",
            "",
        ]
    )

def _find_entry(registry: DomainDocument, entry_id: str) -> DomainDocument:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}

def _file_record(root: Path, path: Path) -> DomainDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]

def _read_json_default(path: Path, *, default: DomainDocument | None = None) -> DomainDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except Exception:
        return {}

def _write_json(path: Path, payload: DomainDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(payload, blocked_keys=TRANSPARENCY_BLOCKED_KEYS))

def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _verification_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Resolved path escapes Attestation Transparency directory.") from exc

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}

def _safe_profile(profile: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(profile or "public_summary"))[:80] or "public_summary"
