# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import html as html
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
from song_agent.domains.trust.attestation_store_ports import AttestationRegistryStorePort as AttestationRegistryStorePort
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_contracts import registry_summary as registry_summary
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry as verify_release_portfolio_governance_attestation_registry
from song_agent.domains.trust.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation as verify_release_portfolio_governance_attestation
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_contracts import PORTAL_BLOCKED_KEYS as PORTAL_BLOCKED_KEYS, PORTAL_MANIFEST_HASH_EXCLUDE_KEYS as PORTAL_MANIFEST_HASH_EXCLUDE_KEYS, PORTAL_PACKAGE_TYPE as PORTAL_PACKAGE_TYPE, PORTAL_PAGES as PORTAL_PAGES, PORTAL_REPORT_HASH_EXCLUDE_KEYS as PORTAL_REPORT_HASH_EXCLUDE_KEYS, portal_manifest_hash as portal_manifest_hash, portal_report_hash as portal_report_hash, portal_summary as portal_summary, portal_verification_summary as portal_verification_summary

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

ReleasePortfolioGovernanceAttestationPortalStateError = _make_deferred_global('ReleasePortfolioGovernanceAttestationPortalStateError')
ch = _make_deferred_global('ch')
key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceAttestationPortalStateError, ch, key
    ReleasePortfolioGovernanceAttestationPortalStateError = namespace.get('ReleasePortfolioGovernanceAttestationPortalStateError', ReleasePortfolioGovernanceAttestationPortalStateError)
    ch = namespace.get('ch', ch)
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)


PORTAL_SCHEMA_VERSION = 1
PORTAL_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_portal_report"




def _html_pages(report: DomainDocument, data_docs: dict[str, DomainDocument], *, external_review: DomainDocument | None = None) -> dict[str, str]:
    source = _as_document(report.get("source"))
    summary = _as_document(report.get("summary"))
    external = _as_document(external_review)
    base = _html_shell
    hashes = {
        "Registry ZIP": source.get("registry_zip_sha256"),
        "Current Attestation ZIP": source.get("current_attestation_zip_sha256"),
        "Evidence Vault ZIP": source.get("evidence_vault_zip_sha256"),
        "Final Board Signoff": source.get("final_board_signoff_hash"),
    }
    index_body = [
        "<h1>MusicForge Release Portfolio Governance Public Attestation Portal</h1>",
        _kv("Portfolio ID", source.get("portfolio_id")),
        _kv("Current certificate", source.get("current_certificate_id")),
        _kv("Current entry", source.get("registry_current_entry_id")),
        _kv("Registry status", source.get("registry_verification_status")),
        _kv("Attestation status", source.get("attestation_verification_status")),
        _kv("External Review", _external_review_label(external)),
        _kv("Published / revoked / superseded", f"{source.get('published_count', 0)} / {source.get('revoked_count', 0)} / {source.get('superseded_count', 0)}"),
        _hash_table(hashes),
        _links(),
    ]
    current_body = [
        "<h1>Current Public Attestation</h1>",
        _kv("Certificate ID", source.get("current_certificate_id")),
        _kv("Entry ID", source.get("registry_current_entry_id")),
        _kv("Attestation profile", source.get("attestation_profile")),
        _kv("Attestation verification", source.get("attestation_verification_status")),
        _kv("Evidence Vault deep verification", source.get("evidence_vault_deep_verification_status")),
        _kv("External Review", _external_review_label(external)),
        _kv("Final Board signoff hash", source.get("final_board_signoff_hash")),
        "<p>This page is a summary. Run verifier for evidence validation.</p>",
        _links(),
    ]
    registry_body = [
        "<h1>Registry Lifecycle Summary</h1>",
        _kv("Current entry", summary.get("current_entry_id")),
        _kv("Current certificate", summary.get("current_certificate_id")),
        _kv("Published count", summary.get("published_count")),
        _kv("Revoked count", summary.get("revoked_count")),
        _kv("Superseded count", summary.get("superseded_count")),
        _links(),
    ]
    revocations_body = [
        "<h1>Revocations and Supersedes</h1>",
        _kv("Revoked entries", source.get("revoked_count", 0)),
        _kv("Superseded entries", source.get("superseded_count", 0)),
        "<p>Detailed lifecycle evidence is available in the Attestation Registry package.</p>",
        _links(),
    ]
    verify_body = [
        "<h1>Offline Verification</h1>",
        "<pre>python -m song_agent.cli verify-release-portfolio-governance-attestation-portal governance-attestation-portal.zip --strict --require-current --json</pre>",
        "<p>This Portal ZIP contains summaries only. Full deep audit requires the Evidence Vault ZIP.</p>",
        '<p><a href="data/verification-commands.json">verification-commands.json</a></p>',
        _links(),
    ]
    pages = {
        "index.html": base("index.html", "Overview", "".join(index_body), report),
        "current.html": base("current.html", "Current", "".join(current_body), report),
        "registry.html": base("registry.html", "Registry", "".join(registry_body), report),
        "revocations.html": base("revocations.html", "Revocations", "".join(revocations_body), report),
        "verify.html": base("verify.html", "Verify", "".join(verify_body), report),
    }
    del data_docs
    return pages

def _html_shell(page: str, title: str, body: str, report: DomainDocument) -> str:
    source_hash = html.escape(str(report.get("source_hash") or ""))
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)} - MusicForge Attestation Portal</title>\n"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.45;color:#17202a;background:#fff}nav a{margin-right:1rem}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:.35rem .55rem}code,pre{background:#f4f4f4;padding:.2rem .35rem}</style>\n"
        "</head>\n"
        f'<body data-source-hash="{source_hash}" data-page="{html.escape(page)}">\n'
        f"<nav>{_links()}</nav>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )

def _links() -> str:
    return '<a href="index.html">Overview</a><a href="current.html">Current</a><a href="registry.html">Registry</a><a href="revocations.html">Revocations</a><a href="verify.html">Verify</a>'

def _kv(label: str, value: object) -> str:
    return f"<p><strong>{html.escape(label)}:</strong> {html.escape(str(value if value is not None else 'missing'))}</p>"

def _hash_table(rows: DomainDocument) -> str:
    body = "".join(f"<tr><th>{html.escape(str(key))}</th><td><code>{html.escape(str(value or 'missing')[:16])}</code></td></tr>" for key, value in rows.items())
    return f"<table>{body}</table>"

def _external_review_label(external: DomainDocument) -> str:
    status = str(external.get("external_review_status") or external.get("status") or "missing")
    if status == "accepted":
        reviewer = str(external.get("reviewer_label") or "external reviewer")
        reviewed_at = str(external.get("reviewed_at") or "")
        return f"Accepted by {reviewer}" + (f" at {reviewed_at}" if reviewed_at else "")
    if status == "stale":
        return "Stale evidence"
    return status

def _registry_manifest_row(source: DomainDocument) -> DomainDocument:
    return {
        "zip_sha256": source.get("registry_zip_sha256"),
        "zip_size_bytes": source.get("registry_zip_size_bytes"),
        "manifest_hash": source.get("registry_manifest_hash"),
        "verification_hash": source.get("registry_verification_hash"),
        "verification_status": source.get("registry_verification_status"),
        "current_entry_id": source.get("registry_current_entry_id"),
        "current_entry_hash": source.get("registry_current_entry_hash"),
    }

def _attestation_manifest_row(source: DomainDocument) -> DomainDocument:
    return {
        "certificate_id": source.get("current_certificate_id"),
        "zip_sha256": source.get("current_attestation_zip_sha256"),
        "zip_size_bytes": source.get("current_attestation_zip_size_bytes"),
        "manifest_hash": source.get("current_attestation_manifest_hash"),
        "verification_hash": source.get("current_attestation_verification_hash"),
        "verification_status": source.get("attestation_verification_status"),
    }

def _state_triple(report: DomainDocument) -> dict[str, str]:
    source = _as_document(report.get("source"))
    return {"source_hash": str(report.get("source_hash") or ""), "current_entry_hash": str(source.get("registry_current_entry_hash") or ""), "registry_zip_sha256": str(source.get("registry_zip_sha256") or "")}

def _manifest_state(manifest: DomainDocument) -> dict[str, str]:
    registry = _as_document(manifest.get("registry"))
    external = _as_document(manifest.get("external_review"))
    external_verification = _as_document(manifest.get("external_review_verification"))
    return {"source_hash": str(manifest.get("source_hash") or ""), "current_entry_hash": str(registry.get("current_entry_hash") or ""), "registry_zip_sha256": str(registry.get("zip_sha256") or ""), "external_review_hash": stable_hash(external), "external_review_verification_hash": stable_hash(external_verification)}

def _page_record(root: Path, path: str, source_hash: object) -> DomainDocument:
    resolved = root / path
    return {"path": path, "content_hash": _sha256(resolved), "source_hash": source_hash}

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
    return write_json(path, sanitize_metadata(payload, blocked_keys=PORTAL_BLOCKED_KEYS))

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
        raise ReleasePortfolioGovernanceAttestationPortalStateError("Resolved path escapes Attestation Portal directory.") from exc

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}

def _write_readme(export_dir: Path, report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    (export_dir / "README.txt").write_text(
        "\n".join(
            [
                "MusicForge Release Portfolio Governance Attestation Portal Snapshot",
                "",
                f"Portfolio ID: {report.get('portfolio_id')}",
                f"Current entry: {summary.get('current_entry_id') or 'none'}",
                f"Current certificate: {summary.get('current_certificate_id') or 'none'}",
                "This static portal is offline and does not publish anything to the internet.",
                "Run verify-release-portfolio-governance-attestation-portal before relying on it.",
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

def _find_entry(registry: DomainDocument, entry_id: str) -> DomainDocument:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}

def _safe_profile(profile: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(profile or "public_summary"))[:80]

def _verification_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})
