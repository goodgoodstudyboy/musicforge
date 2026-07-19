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
from song_agent.domains.trust.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation as verify_release_portfolio_governance_attestation
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_contracts import ENTRY_STATUSES as ENTRY_STATUSES, REGISTRY_BLOCKED_KEYS as REGISTRY_BLOCKED_KEYS, REGISTRY_ENTRY_HASH_EXCLUDE_KEYS as REGISTRY_ENTRY_HASH_EXCLUDE_KEYS, REGISTRY_HASH_EXCLUDE_KEYS as REGISTRY_HASH_EXCLUDE_KEYS, REGISTRY_MANIFEST_HASH_EXCLUDE_KEYS as REGISTRY_MANIFEST_HASH_EXCLUDE_KEYS, REGISTRY_PACKAGE_TYPE as REGISTRY_PACKAGE_TYPE, REGISTRY_REPORT_HASH_EXCLUDE_KEYS as REGISTRY_REPORT_HASH_EXCLUDE_KEYS, _find_entry as _find_entry, registry_entry_hash as registry_entry_hash, registry_hash as registry_hash, registry_manifest_hash as registry_manifest_hash, registry_report_hash as registry_report_hash, registry_summary as registry_summary, registry_verification_summary as registry_verification_summary

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

ReleasePortfolioGovernanceAttestationRegistryNotFoundError = _make_deferred_global('ReleasePortfolioGovernanceAttestationRegistryNotFoundError')
ReleasePortfolioGovernanceAttestationRegistryStateError = _make_deferred_global('ReleasePortfolioGovernanceAttestationRegistryStateError')
item = _make_deferred_global('item')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceAttestationRegistryNotFoundError, ReleasePortfolioGovernanceAttestationRegistryStateError, item, key
    ReleasePortfolioGovernanceAttestationRegistryNotFoundError = namespace.get('ReleasePortfolioGovernanceAttestationRegistryNotFoundError', ReleasePortfolioGovernanceAttestationRegistryNotFoundError)
    ReleasePortfolioGovernanceAttestationRegistryStateError = namespace.get('ReleasePortfolioGovernanceAttestationRegistryStateError', ReleasePortfolioGovernanceAttestationRegistryStateError)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


REGISTRY_SCHEMA_VERSION = 1
REGISTRY_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_registry_report"




def build_package_index(registry: DomainDocument, report: DomainDocument, *, generated_at: str) -> DomainDocument:
    entries = _as_list(registry.get("entries"))
    items = [{"entry_id": item.get("entry_id"), "certificate_id": item.get("certificate_id"), "status": item.get("status"), **(_as_document(item.get("source")))} for item in entries if isinstance(item, dict)]
    data = {"schema_version": REGISTRY_SCHEMA_VERSION, "portfolio_id": registry.get("portfolio_id"), "generated_at": generated_at, "source_hash": report.get("source_hash"), "summary": {"entry_count": len(items)}, "items": items}
    data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
    return sanitize_metadata(data, blocked_keys=REGISTRY_BLOCKED_KEYS)

def build_chain_of_custody(history_path: Path, registry: DomainDocument, report: DomainDocument, *, generated_at: str) -> DomainDocument:
    events: list[DomainDocument] = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append({"event_id": event.get("event_id"), "at": event.get("at"), "type": event.get("type"), "summary_hash": stable_hash(_as_document(event.get("summary")))})
    data = {"schema_version": REGISTRY_SCHEMA_VERSION, "portfolio_id": registry.get("portfolio_id"), "generated_at": generated_at, "source_hash": report.get("source_hash"), "summary": {"event_count": len(events), "latest_event_type": events[-1].get("type") if events else None, "current_entry_id": registry.get("current_entry_id")}, "events": events}
    data["integrity_hash"] = stable_hash({key: value for key, value in data.items() if key != "integrity_hash"})
    return sanitize_metadata(data, blocked_keys=REGISTRY_BLOCKED_KEYS)

def _entry_source(zip_path: Path, manifest: DomainDocument, certificate: DomainDocument, report: DomainDocument, verification: DomainDocument) -> DomainDocument:
    source = _as_document(report.get("source"))
    evidence = _document_or(manifest.get("evidence_vault"), _as_document(certificate.get("evidence_vault")))
    return sanitize_metadata(
        {
            "portfolio_id": report.get("portfolio_id") or manifest.get("portfolio_id"),
            "attestation_zip_sha256": _sha256(zip_path),
            "attestation_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "attestation_manifest_hash": manifest.get("integrity_hash"),
            "attestation_verification_hash": stable_hash(verification),
            "attestation_verification_status": verification.get("status"),
            "evidence_vault_zip_sha256": evidence.get("zip_sha256") or source.get("evidence_vault_zip_sha256"),
            "evidence_vault_zip_size_bytes": evidence.get("zip_size_bytes") or source.get("evidence_vault_zip_size_bytes"),
            "evidence_vault_manifest_hash": evidence.get("manifest_hash") or source.get("evidence_vault_manifest_hash"),
            "evidence_vault_verification_hash": evidence.get("verification_hash") or source.get("evidence_vault_verification_hash"),
            "evidence_vault_deep_verification_status": evidence.get("deep_verification_status") or source.get("evidence_vault_deep_verification_status"),
            "final_board_signoff_hash": source.get("final_board_signoff_hash") or (_as_document(certificate.get("final_board"))).get("signoff_hash"),
        },
        blocked_keys=REGISTRY_BLOCKED_KEYS,
    )

def _state_triple(registry: DomainDocument) -> dict[str, str]:
    current = _find_entry(registry, str(registry.get("current_entry_id") or "")) if registry.get("current_entry_id") else {}
    return {"registry_hash": str(registry.get("integrity_hash") or ""), "current_entry_id": str(registry.get("current_entry_id") or ""), "current_entry_hash": str(current.get("integrity_hash") or "")}

def _manifest_state(manifest: DomainDocument) -> dict[str, str]:
    row = _as_document(manifest.get("registry"))
    external = _as_document(manifest.get("external_review"))
    external_verification = _as_document(manifest.get("external_review_verification"))
    return {"registry_hash": str(row.get("integrity_hash") or ""), "current_entry_id": str(row.get("current_entry_id") or ""), "current_entry_hash": str(row.get("current_entry_hash") or ""), "external_review_hash": stable_hash(external), "external_review_verification_hash": stable_hash(external_verification)}

def _find_entry_mut(registry: DomainDocument, entry_id: str) -> DomainDocument:
    entry = _find_entry(registry, entry_id)
    if not entry:
        raise ReleasePortfolioGovernanceAttestationRegistryNotFoundError("Public Attestation Registry entry not found.")
    return entry

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
    return write_json(path, sanitize_metadata(payload, blocked_keys=REGISTRY_BLOCKED_KEYS))

def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceAttestationRegistryStateError("Resolved path escapes Public Attestation Registry directory.") from exc

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}

def _write_readme(export_dir: Path, registry: DomainDocument, report: DomainDocument) -> None:
    (export_dir / "README.txt").write_text(
        "\n".join(
            [
                "MusicForge Release Portfolio Governance Attestation Registry",
                "",
                f"Portfolio ID: {registry.get('portfolio_id')}",
                f"Current entry: {registry.get('current_entry_id') or 'none'}",
                f"Report status: {report.get('status')}",
                "This package records public attestation lifecycle metadata only.",
                "It does not contain Public Attestation ZIP or Evidence Vault ZIP files.",
                "",
            ]
        ),
        encoding="utf-8",
    )

def _accepted_evidence_summary_for_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> DomainDocument:
    try:
        from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_public_summary_from_portfolio_dir

        return accepted_evidence_public_summary_from_portfolio_dir(portfolio_dir, profile=profile)
    except Exception:
        return {"status": "missing", "external_review_status": "missing"}

def _accepted_evidence_verification_summary_for_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> DomainDocument:
    try:
        from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_verification_summary_from_portfolio_dir

        return accepted_evidence_verification_summary_from_portfolio_dir(portfolio_dir, profile=profile)
    except Exception:
        return {
            "package_type": "release_portfolio_governance_attestation_accepted_evidence_verification_summary",
            "profile": profile,
            "accepted_evidence_status": "missing",
            "external_review_status": "missing",
            "accepted_evidence_verification_status": "missing",
        }

def _safe_text(value: object, limit: int = 160) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]
