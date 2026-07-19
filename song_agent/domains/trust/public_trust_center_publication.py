# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

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



PUBLICATION_SCHEMA_VERSION = 1
PUBLICATION_CHANNEL_PACKAGE_TYPE = "musicforge_public_trust_center_publication_channel"

PUBLICATION_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_publication_report"



PUBLICATION_CHANNEL_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}



PUBLICATION_ALLOWED_CHANNEL_TYPES = {"internal_preview", "partner_handoff", "public_release", "archive_mirror"}



class PublicTrustCenterPublicationError(ValueError):
    pass


class PublicTrustCenterPublicationNotFoundError(PublicTrustCenterPublicationError):
    pass


class PublicTrustCenterPublicationStateError(PublicTrustCenterPublicationError):
    pass


class PublicTrustCenterPublicationStore(PublicTrustCenterPublicationStoreReadinessMixin, PublicTrustCenterPublicationStoreEvidenceMixin):
    def __init__(
        self,
        *,
        trust_center_store: PublicTrustCenterStore,
        distribution_kit_store: PublicTrustCenterDistributionKitStore,
        anchor_registry_store: PublicTrustCenterAnchorRegistryStore,
        anchor_transparency_store: PublicTrustCenterAnchorTransparencyStore,
        acceptance_store: PublicTrustCenterDistributionKitAcceptanceStore,
        acceptance_board_store: PublicTrustCenterAcceptanceBoardStore,
    ) -> None:
        self.trust_center_store = trust_center_store
        self.distribution_kit_store = distribution_kit_store
        self.anchor_registry_store = anchor_registry_store
        self.anchor_transparency_store = anchor_transparency_store
        self.acceptance_store = acceptance_store
        self.acceptance_board_store = acceptance_board_store
        self.lock = threading.RLock()










































def publication_channel_hash(channel: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (channel or {}).items() if key not in PUBLICATION_CHANNEL_HASH_EXCLUDE_KEYS})








def publication_report_integrity_ok(report: DomainDocument) -> bool:
    return bool(report) and str(report.get("integrity_hash") or "") == publication_report_hash(report)








def _publication_lifecycle_from_events(events: list[ImplementationDocument]) -> dict[str, ImplementationDocument]:
    rows: dict[str, ImplementationDocument] = {}
    for event in events:
        payload = _as_document(event.get("payload"))
        publication_id = str(payload.get("publication_id") or "")
        if not publication_id:
            continue
        row = rows.setdefault(publication_id, {"publication_id": publication_id, "status_from_events": "unknown", "events": []})
        row["events"].append({"event_id": event.get("event_id"), "event_type": event.get("event_type"), "event_hash": event.get("event_hash"), "created_at": event.get("created_at")})
        row["latest_event_hash"] = event.get("event_hash")
        row["latest_event_type"] = event.get("event_type")
        event_type = str(event.get("event_type") or "")
        if event_type in {"publication_refreshed", "publication_exported", "publication_zip_built", "publication_verified", "publication_mirror_verified"} and row.get("status_from_events") not in {"revoked", "superseded"}:
            row["status_from_events"] = "published"
        elif event_type == "publication_revoked":
            row["status_from_events"] = "revoked"
            row["revoked_at"] = event.get("created_at")
            row["revocation_event_hash"] = event.get("event_hash")
        elif event_type == "publication_superseded":
            row["status_from_events"] = "superseded"
            row["superseded_at"] = event.get("created_at")
            row["superseded_by_publication_id"] = payload.get("replacement_publication_id")
            row["supersede_event_hash"] = event.get("event_hash")
    return rows


def _publication_state_row(publication_id: str, report: ImplementationDocument, derived: ImplementationDocument, current: ImplementationDocument, snapshot_root: Path | None) -> ImplementationDocument:
    snapshot = report.get("status") if report else None
    status = str(derived.get("status_from_events") or snapshot or "missing")
    if snapshot in {"revoked", "superseded"}:
        status = str(snapshot)
    row = {
        "publication_id": publication_id,
        "status": status,
        "report_status": snapshot,
        "source_hash": report.get("source_hash"),
        "report_hash": report.get("integrity_hash"),
        "manifest_hash": None,
        "zip_sha256": None,
        "zip_size_bytes": None,
        "current": current.get("publication_id") == publication_id and current.get("status") != "revoked",
        "latest_event_hash": derived.get("latest_event_hash"),
        "latest_event_type": derived.get("latest_event_type"),
        "superseded_by_publication_id": report.get("superseded_by_publication_id") or derived.get("superseded_by_publication_id"),
        "revoked_at": derived.get("revoked_at"),
        "superseded_at": derived.get("superseded_at"),
        "revocation_event_hash": derived.get("revocation_event_hash"),
        "supersede_event_hash": derived.get("supersede_event_hash"),
        "event_hashes": [str(item.get("event_hash") or "") for item in derived.get("events", []) if isinstance(item, dict) and item.get("event_hash")],
    }
    if report and snapshot_root is not None:
        export_manifest = _read_json_default(snapshot_root / "export" / "publication-manifest.json", default={})
        zip_path = snapshot_root / "public-trust-center-publication.zip"
        row["manifest_hash"] = export_manifest.get("integrity_hash")
        row["zip_sha256"] = _sha256(zip_path)
        row["zip_size_bytes"] = os.stat(_fs_path(zip_path)).st_size if os.path.isfile(_fs_path(zip_path)) else None
    return _sanitize(row)


def publication_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return {"publication_id": report.get("publication_id"), "channel_id": report.get("channel_id"), "status": report.get("status") or "missing", "ready_for_publication": summary.get("ready_for_publication"), "source_hash": report.get("source_hash")}


def _default_policy(channel_type: str) -> dict[str, bool]:
    if channel_type == "internal_preview":
        return {
            "require_ptc_current": True,
            "require_distribution_kit_current": False,
            "require_anchor_registry_current": False,
            "require_anchor_transparency_current": False,
            "require_acceptance_board_signoff": False,
            "require_accepted_evidence": False,
            "allow_preview_status": True,
            "allow_revoked_anchor": False,
            "allow_stale_packages": False,
        }
    return {
        "require_ptc_current": True,
        "require_distribution_kit_current": True,
        "require_anchor_registry_current": True,
        "require_anchor_transparency_current": True,
        "require_acceptance_board_signoff": True,
        "require_accepted_evidence": True,
        "allow_preview_status": False,
        "allow_revoked_anchor": False,
        "allow_stale_packages": False,
    }


def _package_row(key: str, path: str, zip_path: Path, verification_path: Path | None = None) -> ImplementationDocument:
    manifest_hash = _manifest_hash_for_package(key, zip_path)
    verification = _read_json_default(verification_path or Path(), default={})
    return {"package_key": key, "path": path, "required": True, "sha256": _sha256(zip_path), "size_bytes": os.stat(_fs_path(zip_path)).st_size if zip_path.exists() else None, "manifest_hash": manifest_hash, "verification_report_hash": _verification_hash(verification), "status": verification.get("status")}


def _verification_row(key: str, path: str, verification_path: Path) -> ImplementationDocument:
    verification = _read_json_default(verification_path, default={})
    return {"verification_key": key, "path": path, "status": verification.get("status"), "zip_sha256": verification.get("zip_sha256"), "manifest_hash": verification.get("manifest_hash"), "report_hash": _verification_hash(verification)}


def _accepted_package_rows(center_id: str, acceptance_store: PublicTrustCenterDistributionKitAcceptanceStore) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    root = acceptance_store.accepted_evidence_root(center_id)
    if not root.exists():
        return rows
    for evidence_zip in sorted(root.rglob("accepted-evidence.zip")):
        evidence = _read_zip_json(evidence_zip, "evidence-report.json")
        evidence_id = str(evidence.get("evidence_id") or evidence_zip.parent.name)
        verification_path = acceptance_store.evidence_verification_report_path(center_id, evidence_id)
        verification = _read_json_default(verification_path, default={})
        rows.append({"package_key": f"accepted_evidence:{evidence_id}", "path": f"accepted-evidence/{_safe_id(evidence_id)}/accepted-evidence.zip", "required": True, "sha256": _sha256(evidence_zip), "size_bytes": os.stat(_fs_path(evidence_zip)).st_size if evidence_zip.exists() else None, "manifest_hash": _read_zip_json(evidence_zip, "evidence-manifest.json").get("integrity_hash"), "verification_report_hash": accepted_evidence_verification_hash(verification), "status": verification.get("status"), "response_id": evidence.get("response_id"), "evidence_id": evidence_id})
    return rows


def _accepted_verification_rows(center_id: str, acceptance_store: PublicTrustCenterDistributionKitAcceptanceStore) -> list[ImplementationDocument]:
    rows: list[ImplementationDocument] = []
    root = acceptance_store.accepted_evidence_root(center_id)
    if not root.exists():
        return rows
    for evidence_zip in sorted(root.rglob("accepted-evidence.zip")):
        evidence = _read_zip_json(evidence_zip, "evidence-report.json")
        evidence_id = str(evidence.get("evidence_id") or evidence_zip.parent.name)
        verification_path = acceptance_store.evidence_verification_report_path(center_id, evidence_id)
        verification = _read_json_default(verification_path, default={})
        rows.append({"verification_key": f"accepted_evidence:{evidence_id}", "path": f"accepted-evidence/{_safe_id(evidence_id)}/accepted-evidence-verification-report.json", "status": verification.get("status"), "zip_sha256": verification.get("zip_sha256"), "manifest_hash": verification.get("manifest_hash"), "report_hash": accepted_evidence_verification_hash(verification), "evidence_id": evidence_id})
    return rows


def _path_for_package(center_id: str, key: Any, store: PublicTrustCenterPublicationStore) -> Path:
    key = str(key or "")
    if key == "public_trust_center":
        return store.trust_center_store.zip_path(center_id)
    if key == "distribution_kit":
        return store.distribution_kit_store.zip_path(center_id)
    if key == "anchor_registry":
        return store.anchor_registry_store.zip_path(center_id)
    if key == "anchor_transparency":
        return store.anchor_transparency_store.zip_path(center_id)
    if key == "acceptance_board":
        return store.acceptance_board_store.zip_path(center_id)
    if key == "acceptance_board_signoff_archive":
        return store.acceptance_board_store.signoff_archive_zip_path(center_id)
    if key.startswith("accepted_evidence:"):
        evidence_id = key.split(":", 1)[1]
        return store.acceptance_store.evidence_zip_path(center_id, evidence_id)
    raise PublicTrustCenterPublicationStateError(f"Unknown publication package key: {key}")


def _path_for_verification(center_id: str, key: Any, store: PublicTrustCenterPublicationStore) -> Path:
    key = str(key or "")
    if key == "public_trust_center":
        return store.trust_center_store.verification_report_path(center_id)
    if key == "distribution_kit":
        return store.distribution_kit_store.verification_report_path(center_id)
    if key == "anchor_registry":
        return store.anchor_registry_store.verification_report_path(center_id)
    if key == "anchor_transparency":
        return store.anchor_transparency_store.verification_report_path(center_id)
    if key == "acceptance_board":
        return store.acceptance_board_store.verification_report_path(center_id)
    if key == "acceptance_board_signoff_archive":
        return store.acceptance_board_store.signoff_archive_verification_report_path(center_id)
    if key.startswith("accepted_evidence:"):
        evidence_id = key.split(":", 1)[1]
        return store.acceptance_store.evidence_verification_report_path(center_id, evidence_id)
    raise PublicTrustCenterPublicationStateError(f"Unknown publication verification key: {key}")


def _manifest_hash_for_package(key: str, zip_path: Path) -> Any:
    entry = {
        "public_trust_center": "trust-center-manifest.json",
        "distribution_kit": "distribution-kit-manifest.json",
        "anchor_registry": "anchor-registry-manifest.json",
        "anchor_transparency": "anchor-transparency-manifest.json",
        "acceptance_board": "acceptance-board-manifest.json",
        "acceptance_board_signoff_archive": "board-signoff-archive-manifest.json",
    }.get(key)
    if key.startswith("accepted_evidence:"):
        entry = "evidence-manifest.json"
    return _read_zip_json(zip_path, entry).get("integrity_hash") if entry else None


def _expected_entries(source: ImplementationDocument) -> set[str]:
    entries = {
        "README.txt",
        "publication-manifest.json",
        "publication-report.json",
        "package-index.json",
        "verification-index.json",
        "mirror-policy.json",
        "checksum/SHA256SUMS.txt",
        "checksum/SHA256SUMS.json",
        "site/index.html",
        "site/trust-center.html",
        "site/packages.html",
        "site/verification.html",
        "anchors/ptc-anchor-checkpoint-current.json",
        "anchors/public-trust-center.delivery-anchor.json",
    }
    for item in source.get("packages", []) if isinstance(source.get("packages"), list) else []:
        if isinstance(item, dict) and item.get("path"):
            entries.add(str(item["path"]))
    for item in source.get("verifications", []) if isinstance(source.get("verifications"), list) else []:
        if isinstance(item, dict) and item.get("path"):
            entries.add(str(item["path"]))
    return entries


def _checksum_json(export_dir: Path) -> ImplementationDocument:
    rows = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.relative_to(export_dir).as_posix() not in {"checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt", "publication-manifest.json"}]
    data = {"schema_version": PUBLICATION_SCHEMA_VERSION, "files": rows}
    data["integrity_hash"] = sidecar_hash(data)
    return data


def _write_sha256sums(export_dir: Path, checksum_json: ImplementationDocument) -> None:
    lines = [f"{item.get('sha256')}  {item.get('path')}" for item in checksum_json.get("files", []) if isinstance(item, dict)]
    (export_dir / "checksum" / "SHA256SUMS.txt").write_text(sanitize_sensitive_text("\n".join(lines) + "\n"), encoding="utf-8")


def _write_readme(export_dir: Path) -> None:
    text = "\n".join(
        [
            "MusicForge Public Trust Center Publication",
            "",
            "This local publication snapshot contains the Public Trust Center packages, verification reports, checksums, and static HTML pages.",
            "Run verify-public-trust-center-publication-package with --strict --deep before relying on it.",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")


def _write_html_pages(export_dir: Path, report: ImplementationDocument) -> None:
    summary = _as_document(report.get("summary"))
    body = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>MusicForge Public Trust Center Publication</title>"
        "<style>body{font-family:Arial,sans-serif;margin:2rem;line-height:1.45}code{background:#f4f4f4;padding:.1rem .25rem}</style></head>"
        "<body><h1>MusicForge Public Trust Center Publication</h1>"
        f"<p>Publication: <code>{_html(report.get('publication_id'))}</code></p>"
        f"<p>Status: <code>{_html(report.get('status'))}</code></p>"
        f"<p>Packages: <code>{_html(summary.get('package_count'))}</code></p>"
        "<p><a href=\"packages.html\">Packages</a> | <a href=\"verification.html\">Verification</a> | <a href=\"trust-center.html\">Trust Center</a></p>"
        "</body></html>"
    )
    for name in ("index.html", "trust-center.html", "packages.html", "verification.html"):
        (export_dir / "site" / name).write_text(sanitize_sensitive_text(body), encoding="utf-8")


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    root = root.resolve()
    for dirpath, _dirnames, filenames in os.walk(_fs_path(root)):
        current = _from_fs_path(str(dirpath))
        for filename in filenames:
            path = current / filename
            if not os.path.islink(_fs_path(path)):
                rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(root).as_posix())


def _write_zip(zip_path: Path, root: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(root):
                with open(_fs_path(resolved), "rb") as handle:
                    archive.writestr(entry, handle.read())
        tmp_path.replace(zip_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _safe_copy(source: Path, target: Path, root: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    _ensure_within(root.resolve(), target)
    if not source.exists() or not source.is_file() or source.is_symlink():
        raise PublicTrustCenterPublicationStateError(f"Required publication source file is missing: {source.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_fs_path(source), _fs_path(target))


def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterPublicationStateError("Resolved path escapes Public Trust Center publication root.")


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    return write_json(path, _sanitize(payload))


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    if not path.exists():
        return []
    rows: list[ImplementationDocument] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _read_zip_json(zip_path: Path, entry: str | None) -> ImplementationDocument:
    if not zip_path.exists() or not entry:
        return {}
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            return json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}


def _sha256(path: Path) -> str | None:
    if not os.path.isfile(_fs_path(path)):
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verification_hash(report: ImplementationDocument) -> str | None:
    if not report:
        return None
    if report.get("package_kind") == "public_trust_center_acceptance_board":
        return acceptance_board_verification_hash(report)
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})


def _is_file(path: Path) -> bool:
    return os.path.isfile(_fs_path(path)) and not os.path.islink(_fs_path(path))


def _fs_path(path: Path) -> str:
    text = str(Path(path).resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _from_fs_path(value: str) -> Path:
    if os.name != "nt":
        return Path(value)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value.removeprefix("\\\\?\\UNC\\"))
    if value.startswith("\\\\?\\"):
        return Path(value.removeprefix("\\\\?\\"))
    return Path(value)


from song_agent.domains.trust import v142_ptcp_readiness_2 as _v142_ptcp_readiness_2
from song_agent.domains.trust.v142_ptcp_readiness_2 import _safe_id as _safe_id, _next_channel_id as _next_channel_id, _next_publication_id as _next_publication_id, _sanitize as _sanitize, _html as _html










_v142_ptcp_readiness.bind_globals(globals())
_v142_ptcp_evidence.bind_globals(globals())

_v142_ptcp_readiness_2.bind_globals(globals())
