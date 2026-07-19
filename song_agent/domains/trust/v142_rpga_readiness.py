# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
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
from song_agent.domains.trust.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore as ReleasePortfolioGovernanceEvidenceVaultStore, evidence_vault_manifest_integrity_ok as evidence_vault_manifest_integrity_ok, evidence_vault_report_integrity_hash as evidence_vault_report_integrity_hash, evidence_vault_report_integrity_ok as evidence_vault_report_integrity_ok, evidence_vault_verification_summary as evidence_vault_verification_summary
from song_agent.domains.trust.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore as ReleasePortfolioGovernanceFinalBoardStore, final_board_report_integrity_hash as final_board_report_integrity_hash, final_board_report_integrity_ok as final_board_report_integrity_ok, final_board_signoff_hash as final_board_signoff_hash, final_board_signoff_integrity_ok as final_board_signoff_integrity_ok
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_contracts import ATTESTATION_BLOCKED_KEYS as ATTESTATION_BLOCKED_KEYS, ATTESTATION_CERTIFICATE_HASH_EXCLUDE_KEYS as ATTESTATION_CERTIFICATE_HASH_EXCLUDE_KEYS, ATTESTATION_CERTIFICATE_TYPE as ATTESTATION_CERTIFICATE_TYPE, ATTESTATION_MANIFEST_HASH_EXCLUDE_KEYS as ATTESTATION_MANIFEST_HASH_EXCLUDE_KEYS, ATTESTATION_PACKAGE_TYPE as ATTESTATION_PACKAGE_TYPE, ATTESTATION_REPORT_HASH_EXCLUDE_KEYS as ATTESTATION_REPORT_HASH_EXCLUDE_KEYS, attestation_certificate_hash as attestation_certificate_hash, attestation_manifest_hash as attestation_manifest_hash, attestation_report_integrity_hash as attestation_report_integrity_hash, attestation_verification_summary as attestation_verification_summary

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

ReleasePortfolioGovernanceAttestationError = _make_deferred_global('ReleasePortfolioGovernanceAttestationError')
ReleasePortfolioGovernanceAttestationStateError = _make_deferred_global('ReleasePortfolioGovernanceAttestationStateError')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceAttestationError, ReleasePortfolioGovernanceAttestationStateError
    ReleasePortfolioGovernanceAttestationError = namespace.get('ReleasePortfolioGovernanceAttestationError', ReleasePortfolioGovernanceAttestationError)
    ReleasePortfolioGovernanceAttestationStateError = namespace.get('ReleasePortfolioGovernanceAttestationStateError', ReleasePortfolioGovernanceAttestationStateError)
    _bind_deferred_defaults(namespace)


ATTESTATION_SCHEMA_VERSION = 1
ATTESTATION_EXPORT_SCHEMA_VERSION = 1
ATTESTATION_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_report"
SIGNED_STATUSES = {"signed", "force_signed"}
ATTESTATION_PROFILES = {"public_summary", "partner_due_diligence", "internal_public_preview"}




def _certificate_markdown(certificate: DomainDocument) -> str:
    final_board = _as_document(certificate.get("final_board"))
    vault = _as_document(certificate.get("evidence_vault"))
    coverage = _as_document(certificate.get("coverage"))
    return "\n".join(
        [
            "# MusicForge Portfolio Governance Public Attestation",
            "",
            f"Certificate ID: `{certificate.get('certificate_id')}`",
            f"Portfolio ID: `{certificate.get('portfolio_id')}`",
            f"Governance status: `{certificate.get('governance_status')}`",
            f"Final Board signoff status: `{final_board.get('signoff_status')}`",
            f"Final Board signoff hash: `{final_board.get('signoff_hash')}`",
            f"Evidence Vault ZIP SHA-256: `{vault.get('zip_sha256')}`",
            f"Evidence Vault verification: `{vault.get('verification_status')}` / deep `{vault.get('deep_verification_status')}`",
            f"Signed governance queues: `{coverage.get('signed_queue_count')}`",
            f"Force-signed governance queues: `{coverage.get('force_signed_queue_count')}`",
            "",
            "This public attestation contains hash fingerprints and summary evidence only. Request the full Evidence Vault for deep nested package verification.",
            "",
        ]
    )

def _certificate_html(certificate: DomainDocument) -> str:
    text = _certificate_markdown(certificate)
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><title>MusicForge Public Attestation</title></head><body><pre>{escaped}</pre></body></html>"

def _write_readme(export_dir: Path, certificate: DomainDocument) -> None:
    (export_dir / "README.txt").write_text(
        "\n".join(
            [
                "MusicForge Release Portfolio Governance Public Attestation",
                "",
                f"Certificate ID: {certificate.get('certificate_id')}",
                "This package contains public summary evidence only.",
                "It does not contain Evidence Vault nested ZIP packages.",
                "Verify it with: python -m song_agent.cli verify-release-portfolio-governance-attestation portfolio-governance-public-attestation.zip --strict --require-vault --require-final-board --json",
                "",
            ]
        ),
        encoding="utf-8",
    )

def _file_record(root: Path, path: Path) -> DomainDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rows.append((path.resolve(), path.relative_to(root).as_posix()))
    return rows

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    if not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            return json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}

def _read_json_default(path: Path, *, default: DomainDocument | None = None) -> DomainDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))

def _write_json(path: Path, payload: DomainDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, payload)

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
        raise ReleasePortfolioGovernanceAttestationStateError("Resolved path escapes Public Attestation directory.") from exc

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}

def _blocker(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}

def _warning(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}

def _validate_profile(profile: str) -> str:
    value = str(profile or "public_summary").strip()
    if value not in ATTESTATION_PROFILES:
        raise ReleasePortfolioGovernanceAttestationError(f"Unsupported attestation profile: {value}")
    return value
