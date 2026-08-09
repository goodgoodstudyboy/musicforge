from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list, _document_or

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


class PublicTrustCenterPublicationStore:
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

    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.trust_center_store.center_dir(center_id) / "publications"

    def channels_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "channels"

    def channel_dir(self, center_id: str, channel_id: str) -> Path:
        return self.channels_dir(center_id) / _safe_id(channel_id)

    def channel_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "channel.json"

    def events_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "events.jsonl"

    def current_publication_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "current-publication.json"

    def channel_state_path(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "publication-channel-state.json"

    def snapshots_dir(self, center_id: str, channel_id: str) -> Path:
        return self.channel_dir(center_id, channel_id) / "snapshots"

    def snapshot_dir(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshots_dir(center_id, channel_id) / _safe_id(publication_id)

    def report_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "publication-report.json"

    def export_dir(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "export"

    def zip_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "public-trust-center-publication.zip"

    def verification_report_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "publication-verification-report.json"

    def mirror_verification_report_path(self, center_id: str, channel_id: str, publication_id: str) -> Path:
        return self.snapshot_dir(center_id, channel_id, publication_id) / "publication-mirror-verification-report.json"

    def create_channel(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            channel_id = _safe_id(str(payload.get("channel_id") or _next_channel_id(self.channels_dir(center_id))))
            channel_type = str(payload.get("channel_type") or "public_release")
            if channel_type not in PUBLICATION_ALLOWED_CHANNEL_TYPES:
                raise PublicTrustCenterPublicationStateError("Invalid Public Trust Center publication channel_type.")
            policy = _default_policy(channel_type)
            if isinstance(payload.get("policy"), dict):
                policy.update({key: bool(value) for key, value in payload["policy"].items() if key in policy})
            channel = {
                "schema_version": PUBLICATION_SCHEMA_VERSION,
                "package_type": PUBLICATION_CHANNEL_PACKAGE_TYPE,
                "channel_id": channel_id,
                "center_id": center_id,
                "name": sanitize_sensitive_text(str(payload.get("name") or "Public Trust Center Release Channel")[:160]),
                "channel_type": channel_type,
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "description": sanitize_sensitive_text(str(payload.get("description") or "")[:1000]),
                "policy": policy,
                "site_options": {
                    "include_html": bool((_as_document(payload.get("site_options"))).get("include_html", True)),
                    "include_checksums": True,
                    "include_readme": True,
                    "include_verification_commands": True,
                },
            }
            channel["integrity_hash"] = publication_channel_hash(channel)
            self.channel_dir(center_id, channel_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.channel_path(center_id, channel_id), channel)
            self._append_event(center_id, channel_id, "channel_created", {"channel_hash": channel["integrity_hash"]}, now=now)
            return _sanitize(channel)

    def read_channel(self, center_id: str, channel_id: str) -> dict[str, Any]:
        value = _read_json_default(self.channel_path(center_id, channel_id), default={})
        if not value:
            raise PublicTrustCenterPublicationNotFoundError("Public Trust Center publication channel not found.")
        return value

    def list_channels(self, center_id: str | None = None, include_inactive: bool = False) -> list[dict[str, Any]]:
        roots = [self.channels_dir(center_id)] if center_id else sorted(path / "publications" / "channels" for path in self.trust_center_store.root.glob("*") if path.is_dir())
        rows: list[dict[str, Any]] = []
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*/channel.json")):
                channel = _read_json_default(path, default={})
                if not channel:
                    continue
                if not include_inactive and channel.get("status") != "active":
                    continue
                rows.append(_sanitize(channel))
        return rows

    def refresh_publication(self, center_id: str, channel_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            channel = self.read_channel(center_id, channel_id)
            publication_id = _safe_id(str(payload.get("publication_id") or _next_publication_id(self.snapshots_dir(center_id, channel_id))))
            self._refresh_underlying_verifications(center_id)
            source = self._build_source(center_id, channel)
            checks, blockers, warnings = self._findings(channel, source)
            report = {
                "schema_version": PUBLICATION_SCHEMA_VERSION,
                "package_type": PUBLICATION_REPORT_PACKAGE_TYPE,
                "publication_id": publication_id,
                "channel_id": channel_id,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "ready",
                "source": source,
                "summary": {
                    "package_count": len(_as_list(source.get("packages"))),
                    "verification_report_count": len(_as_list(source.get("verifications"))),
                    "accepted_evidence_count": len(_as_list(source.get("accepted_evidence"))),
                    "all_required_packages_current": not blockers,
                    "ready_for_publication": not blockers,
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                },
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            report["source_hash"] = stable_hash(source)
            report["integrity_hash"] = publication_report_hash(report)
            self.snapshot_dir(center_id, channel_id, publication_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id, channel_id, publication_id), report)
            _write_json(self.current_publication_path(center_id, channel_id), {"publication_id": publication_id, "source_hash": report["source_hash"], "report_hash": report["integrity_hash"], "updated_at": now})
            self._append_event(center_id, channel_id, "publication_refreshed", {"publication_id": publication_id, "source_hash": report["source_hash"], "report_hash": report["integrity_hash"]}, now=now)
            return _sanitize(report)

    def export_publication(self, center_id: str, channel_id: str, publication_id: str | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            publication_id = publication_id or self._current_publication_id(center_id, channel_id)
            report = self._read_report(center_id, channel_id, publication_id)
            self._ensure_exportable(center_id, channel_id, publication_id, report)
            if self._history_has_state_event(center_id, channel_id, report, "publication_exported"):
                raise PublicTrustCenterPublicationStateError("Public Trust Center publication export already exists for this source state.")
            export_dir = self.export_dir(center_id, channel_id, publication_id).resolve()
            _ensure_within(self.snapshot_dir(center_id, channel_id, publication_id).resolve(), export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            for relative in ("packages", "accepted-evidence", "verification-reports", "anchors", "checksum", "site"):
                (export_dir / relative).mkdir(parents=True, exist_ok=True)
            copied_paths = self._copy_source_files(center_id, report, export_dir)
            _write_json(export_dir / "publication-report.json", report)
            package_index = self._package_index(report)
            verification_index = self._verification_index(report)
            mirror_policy = self._mirror_policy(report)
            _write_json(export_dir / "package-index.json", package_index)
            _write_json(export_dir / "verification-index.json", verification_index)
            _write_json(export_dir / "mirror-policy.json", mirror_policy)
            _write_readme(export_dir)
            _write_html_pages(export_dir, report)
            checksum_json = _checksum_json(export_dir)
            _write_json(export_dir / "checksum" / "SHA256SUMS.json", checksum_json)
            _write_sha256sums(export_dir, checksum_json)
            files = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.name != "publication-manifest.json"]
            manifest = {
                "schema_version": PUBLICATION_SCHEMA_VERSION,
                "package_type": PUBLICATION_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Publication", "version": __version__},
                "publication_id": publication_id,
                "channel_id": channel_id,
                "center_id": center_id,
                "created_at": now,
                "source_hash": report.get("source_hash"),
                "report_hash": report.get("integrity_hash"),
                "package_index_hash": package_index.get("integrity_hash"),
                "verification_index_hash": verification_index.get("integrity_hash"),
                "mirror_policy_hash": mirror_policy.get("integrity_hash"),
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "copied_paths": sorted(copied_paths),
            }
            manifest["integrity_hash"] = publication_manifest_hash(manifest)
            _write_json(export_dir / "publication-manifest.json", manifest)
            self._append_event(center_id, channel_id, "publication_exported", {"publication_id": publication_id, "source_hash": report.get("source_hash"), "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(manifest)

    def build_publication_zip(self, center_id: str, channel_id: str, publication_id: str | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            publication_id = publication_id or self._current_publication_id(center_id, channel_id)
            report = self._read_report(center_id, channel_id, publication_id)
            self._ensure_exportable(center_id, channel_id, publication_id, report)
            if self._history_has_state_event(center_id, channel_id, report, "publication_zip_built"):
                raise PublicTrustCenterPublicationStateError("Public Trust Center publication ZIP already exists for this source state.")
            export_dir = self.export_dir(center_id, channel_id, publication_id).resolve()
            manifest_path = export_dir / "publication-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if manifest.get("source_hash") != report.get("source_hash") or manifest.get("report_hash") != report.get("integrity_hash"):
                raise PublicTrustCenterPublicationStateError("Public Trust Center publication export is stale. Re-export before ZIP.")
            zip_path = self.zip_path(center_id, channel_id, publication_id).resolve()
            _ensure_within(self.snapshot_dir(center_id, channel_id, publication_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = publication_manifest_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "publication_id": publication_id}
            self._append_event(center_id, channel_id, "publication_zip_built", {"publication_id": publication_id, "source_hash": report.get("source_hash"), "zip_sha256": info["sha256"], "manifest_hash": manifest["integrity_hash"]}, now=now)
            return _sanitize(info)

    def verify_publication_zip(self, center_id: str, channel_id: str, publication_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.public_trust_center_publication_verifier import verify_public_trust_center_publication_package, write_public_trust_center_publication_verification_report

        payload = payload or {}
        publication_id = publication_id or self._current_publication_id(center_id, channel_id)
        report = verify_public_trust_center_publication_package(
            self.zip_path(center_id, channel_id, publication_id),
            strict=bool(payload.get("strict", True)),
            deep=bool(payload.get("deep", True)),
            require_ready=bool(payload.get("require_ready", True)),
            require_acceptance_board_signoff=bool(payload.get("require_acceptance_board_signoff", True)),
            require_anchor_current=bool(payload.get("require_anchor_current", True)),
            require_no_revoked=bool(payload.get("require_no_revoked", False)),
            publication_channel_state_path=payload.get("publication_channel_state_path") or self.channel_state_path(center_id, channel_id),
        )
        write_public_trust_center_publication_verification_report(report, self.verification_report_path(center_id, channel_id, publication_id))
        self._append_event(center_id, channel_id, "publication_verified", {"publication_id": publication_id, "verification_status": report.get("status"), "verification_hash": _verification_hash(report)}, now=now_iso())
        return report

    def verify_mirror_directory(self, center_id: str, channel_id: str, publication_id: str, mirror_dir: Path | str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.public_trust_center_publication_verifier import verify_public_trust_center_publication_mirror, write_public_trust_center_publication_verification_report

        payload = payload or {}
        report = verify_public_trust_center_publication_mirror(
            Path(mirror_dir),
            strict=bool(payload.get("strict", True)),
            require_ready=bool(payload.get("require_ready", True)),
            require_acceptance_board_signoff=bool(payload.get("require_acceptance_board_signoff", True)),
            require_anchor_current=bool(payload.get("require_anchor_current", True)),
            require_no_revoked=bool(payload.get("require_no_revoked", False)),
            publication_channel_state_path=payload.get("publication_channel_state_path") or self.channel_state_path(center_id, channel_id),
        )
        write_public_trust_center_publication_verification_report(report, self.mirror_verification_report_path(center_id, channel_id, publication_id))
        self._append_event(center_id, channel_id, "publication_mirror_verified", {"publication_id": publication_id, "verification_status": report.get("status"), "verification_hash": _verification_hash(report)}, now=now_iso())
        return report

    def revoke_publication(self, center_id: str, channel_id: str, publication_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=PUBLICATION_BLOCKED_KEYS)
            report = self._read_report(center_id, channel_id, publication_id)
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 8:
                raise PublicTrustCenterPublicationStateError("Publication revoke reason must be at least 8 characters.")
            report["updated_at"] = now
            report["status"] = "revoked"
            report.setdefault("revocation", {})["reason"] = reason[:1000]
            report["integrity_hash"] = publication_report_hash(report)
            _write_json(self.report_path(center_id, channel_id, publication_id), report)
            current = _read_json_default(self.current_publication_path(center_id, channel_id), default={})
            if current.get("publication_id") == publication_id:
                current["status"] = "revoked"
                current["updated_at"] = now
                _write_json(self.current_publication_path(center_id, channel_id), current)
            self._append_event(center_id, channel_id, "publication_revoked", {"publication_id": publication_id, "reason_hash": stable_hash(reason), "source_hash": report.get("source_hash")}, now=now)
            return _sanitize(report)

    def supersede_publication(self, center_id: str, channel_id: str, publication_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            old = self._read_report(center_id, channel_id, publication_id)
            replacement = self.refresh_publication(center_id, channel_id, payload or {}, now=now)
            old["updated_at"] = now
            old["status"] = "superseded"
            old["superseded_by_publication_id"] = replacement.get("publication_id")
            old["integrity_hash"] = publication_report_hash(old)
            _write_json(self.report_path(center_id, channel_id, publication_id), old)
            self._append_event(center_id, channel_id, "publication_superseded", {"publication_id": publication_id, "replacement_publication_id": replacement.get("publication_id"), "source_hash": old.get("source_hash")}, now=now)
            return {"old_publication": _sanitize(old), "new_publication": replacement}

    def _current_publication_id(self, center_id: str, channel_id: str) -> str:
        current = _read_json_default(self.current_publication_path(center_id, channel_id), default={})
        publication_id = str(current.get("publication_id") or "")
        if not publication_id:
            raise PublicTrustCenterPublicationNotFoundError("Current Public Trust Center publication is missing.")
        return publication_id

    def _read_report(self, center_id: str, channel_id: str, publication_id: str) -> ImplementationDocument:
        report = _read_json_default(self.report_path(center_id, channel_id, publication_id), default={})
        if not report:
            raise PublicTrustCenterPublicationNotFoundError("Public Trust Center publication report is missing.")
        return report

    def _build_source(self, center_id: str, channel: ImplementationDocument) -> ImplementationDocument:
        package_rows = self._package_rows(center_id)
        verification_rows = self._verification_rows(center_id)
        accepted_rows = self._accepted_evidence_rows(center_id)
        signoff = self.acceptance_board_store.read_signoff(center_id, default={})
        source = {
            "center_id": center_id,
            "channel_id": channel.get("channel_id"),
            "channel_hash": channel.get("integrity_hash"),
            "channel_type": channel.get("channel_type"),
            "policy": _as_document(channel.get("policy")),
            "packages": package_rows,
            "verifications": verification_rows,
            "accepted_evidence": accepted_rows,
            "accepted_evidence_index_hash": stable_hash(accepted_rows),
            "acceptance_board_signoff_hash": signoff.get("integrity_hash"),
            "acceptance_board_signoff_source_hash": signoff.get("source_hash"),
        }
        return _sanitize(source)

    def _refresh_underlying_verifications(self, center_id: str) -> None:
        if not self.acceptance_board_store.verification_report_path(center_id).exists():
            self.acceptance_board_store.verify_zip(center_id, {"strict": True, "require_ready": True, "require_quorum": True, "require_no_conflicts": True, "use_distribution_kit": True, "use_accepted_evidence": True})
        if not self.acceptance_board_store.signoff_archive_verification_report_path(center_id).exists():
            self.acceptance_board_store.verify_signoff_archive_zip(center_id, {"strict": True, "require_signed": True, "require_current": True, "require_ready": True, "use_board_zip": True, "use_board_verification": True, "use_distribution_kit": True, "use_accepted_evidence": True})
        for evidence_zip in sorted(self.acceptance_store.accepted_evidence_root(center_id).rglob("accepted-evidence.zip")):
            evidence = _read_zip_json(evidence_zip, "evidence-report.json")
            evidence_id = str(evidence.get("evidence_id") or evidence_zip.parent.name)
            if not self.acceptance_store.evidence_verification_report_path(center_id, evidence_id).exists():
                self.acceptance_store.verify_accepted_evidence_zip(center_id, evidence_id, {"strict": True, "require_current": True, "use_distribution_kit": True})
        write_public_trust_center_verification_report(
            verify_public_trust_center_package(
                self.trust_center_store.zip_path(center_id),
                strict=True,
                require_delivery_readiness=False,
                delivery_anchor_path=self.trust_center_store.delivery_anchor_path(center_id),
                anchor_registry_path=self.anchor_registry_store.zip_path(center_id),
                anchor_transparency_path=self.anchor_transparency_store.zip_path(center_id),
                anchor_checkpoint_path=self.anchor_transparency_store.current_checkpoint_path(center_id),
                require_anchor_registry_current=True,
                require_anchor_published=True,
                require_anchor_not_revoked=True,
                require_anchor_transparency_current=True,
                require_anchor_checkpoint=True,
                require_acceptance_board_signoff=True,
                acceptance_board_signoff_archive_path=self.acceptance_board_store.signoff_archive_zip_path(center_id),
                acceptance_board_path=self.acceptance_board_store.zip_path(center_id),
                acceptance_board_verification_report_path=self.acceptance_board_store.verification_report_path(center_id),
                distribution_kit_path=self.distribution_kit_store.zip_path(center_id),
                accepted_evidence_dir=self.acceptance_store.accepted_evidence_root(center_id),
            ),
            self.trust_center_store.verification_report_path(center_id),
        )
        self.distribution_kit_store.verify_zip(center_id, {"strict": True, "deep": True, "require_current": True, "require_delivery_readiness": False, "require_acceptance_board_signoff": True, "acceptance_board_signoff_archive_path": self.acceptance_board_store.signoff_archive_zip_path(center_id), "acceptance_board_path": self.acceptance_board_store.zip_path(center_id), "acceptance_board_verification_report_path": self.acceptance_board_store.verification_report_path(center_id), "accepted_evidence_dir": self.acceptance_store.accepted_evidence_root(center_id)})
        registry_verification = verify_public_trust_center_anchor_registry_package(self.anchor_registry_store.zip_path(center_id), strict=True, require_current=True, require_anchor_published=True, require_anchor_not_revoked=True)
        write_public_trust_center_anchor_registry_verification_report(registry_verification, self.anchor_registry_store.verification_report_path(center_id))
        transparency_verification = verify_public_trust_center_anchor_transparency_package(self.anchor_transparency_store.zip_path(center_id), strict=True, checkpoint_path=self.anchor_transparency_store.current_checkpoint_path(center_id), anchor_registry_path=self.anchor_registry_store.zip_path(center_id), require_current_checkpoint=True, require_published_anchor=True, require_not_revoked=True)
        write_public_trust_center_anchor_transparency_verification_report(transparency_verification, self.anchor_transparency_store.verification_report_path(center_id))

    def _package_rows(self, center_id: str) -> list[ImplementationDocument]:
        rows = [
            _package_row("public_trust_center", "packages/public-trust-center.zip", self.trust_center_store.zip_path(center_id), self.trust_center_store.verification_report_path(center_id)),
            _package_row("distribution_kit", "packages/public-trust-center-distribution-kit.zip", self.distribution_kit_store.zip_path(center_id), self.distribution_kit_store.verification_report_path(center_id)),
            _package_row("anchor_registry", "packages/public-trust-center-anchor-registry.zip", self.anchor_registry_store.zip_path(center_id), self.anchor_registry_store.verification_report_path(center_id)),
            _package_row("anchor_transparency", "packages/public-trust-center-anchor-transparency.zip", self.anchor_transparency_store.zip_path(center_id), self.anchor_transparency_store.verification_report_path(center_id)),
            _package_row("acceptance_board", "packages/public-trust-center-acceptance-board.zip", self.acceptance_board_store.zip_path(center_id), self.acceptance_board_store.verification_report_path(center_id)),
            _package_row("acceptance_board_signoff_archive", "packages/public-trust-center-acceptance-board-signoff-archive.zip", self.acceptance_board_store.signoff_archive_zip_path(center_id), self.acceptance_board_store.signoff_archive_verification_report_path(center_id)),
        ]
        rows.extend(_accepted_package_rows(center_id, self.acceptance_store))
        return rows

    def _verification_rows(self, center_id: str) -> list[ImplementationDocument]:
        rows = [
            _verification_row("public_trust_center", "verification-reports/public-trust-center-verification-report.json", self.trust_center_store.verification_report_path(center_id)),
            _verification_row("distribution_kit", "verification-reports/distribution-kit-verification-report.json", self.distribution_kit_store.verification_report_path(center_id)),
            _verification_row("anchor_registry", "verification-reports/anchor-registry-verification-report.json", self.anchor_registry_store.verification_report_path(center_id)),
            _verification_row("anchor_transparency", "verification-reports/anchor-transparency-verification-report.json", self.anchor_transparency_store.verification_report_path(center_id)),
            _verification_row("acceptance_board", "verification-reports/acceptance-board-verification-report.json", self.acceptance_board_store.verification_report_path(center_id)),
            _verification_row("acceptance_board_signoff_archive", "verification-reports/acceptance-board-signoff-archive-verification-report.json", self.acceptance_board_store.signoff_archive_verification_report_path(center_id)),
        ]
        rows.extend(_accepted_verification_rows(center_id, self.acceptance_store))
        return rows

    def _accepted_evidence_rows(self, center_id: str) -> list[ImplementationDocument]:
        rows: list[dict[str, Any]] = []
        root = self.acceptance_store.accepted_evidence_root(center_id)
        if not root.exists():
            return rows
        for evidence_zip in sorted(root.rglob("accepted-evidence.zip")):
            evidence = _read_zip_json(evidence_zip, "evidence-report.json")
            evidence_id = str(evidence.get("evidence_id") or evidence_zip.parent.name)
            verification_path = self.acceptance_store.evidence_verification_report_path(center_id, evidence_id)
            verification = _read_json_default(verification_path, default={})
            rows.append({"evidence_id": evidence_id, "response_id": evidence.get("response_id"), "zip_sha256": _sha256(evidence_zip), "manifest_hash": _read_zip_json(evidence_zip, "evidence-manifest.json").get("integrity_hash"), "verification_status": verification.get("status"), "verification_hash": _verification_hash(verification)})
        return rows

    def _copy_source_files(self, center_id: str, report: ImplementationDocument, export_dir: Path) -> list[str]:
        copied: list[str] = []
        for item in report.get("source", {}).get("packages", []):
            if not isinstance(item, dict):
                continue
            source = _path_for_package(center_id, item.get("package_key"), self)
            target = export_dir / str(item.get("path") or "")
            _safe_copy(source, target, export_dir)
            copied.append(str(item.get("path") or ""))
        for item in report.get("source", {}).get("verifications", []):
            if not isinstance(item, dict):
                continue
            source = _path_for_verification(center_id, item.get("verification_key"), self)
            target = export_dir / str(item.get("path") or "")
            _safe_copy(source, target, export_dir)
            copied.append(str(item.get("path") or ""))
        checkpoint = self.anchor_transparency_store.current_checkpoint_path(center_id)
        _safe_copy(checkpoint, export_dir / "anchors/ptc-anchor-checkpoint-current.json", export_dir)
        copied.append("anchors/ptc-anchor-checkpoint-current.json")
        delivery_anchor = self.trust_center_store.delivery_anchor_path(center_id)
        _safe_copy(delivery_anchor, export_dir / "anchors/public-trust-center.delivery-anchor.json", export_dir)
        copied.append("anchors/public-trust-center.delivery-anchor.json")
        return copied

    def _package_index(self, report: ImplementationDocument) -> ImplementationDocument:
        rows = []
        verification_by_key = {str(item.get("verification_key") or ""): item for item in report.get("source", {}).get("verifications", []) if isinstance(item, dict)}
        for item in report.get("source", {}).get("packages", []):
            if not isinstance(item, dict):
                continue
            verification = verification_by_key.get(str(item.get("package_key") or "")) or {}
            rows.append({**item, "verification_report_path": verification.get("path"), "verification_report_hash": verification.get("report_hash"), "status": verification.get("status")})
        data = {"schema_version": PUBLICATION_SCHEMA_VERSION, "publication_id": report.get("publication_id"), "source_hash": report.get("source_hash"), "items": rows}
        data["integrity_hash"] = sidecar_hash(data)
        return data

    def _verification_index(self, report: ImplementationDocument) -> ImplementationDocument:
        data = {"schema_version": PUBLICATION_SCHEMA_VERSION, "publication_id": report.get("publication_id"), "source_hash": report.get("source_hash"), "items": report.get("source", {}).get("verifications", [])}
        data["integrity_hash"] = sidecar_hash(data)
        return data

    def _mirror_policy(self, report: ImplementationDocument) -> ImplementationDocument:
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

    def _findings(self, channel: ImplementationDocument, source: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        checks: list[dict[str, Any]] = []
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

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

    def _ensure_exportable(self, center_id: str, channel_id: str, publication_id: str, report: ImplementationDocument) -> None:
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

    def _append_event(self, center_id: str, channel_id: str, event_type: str, payload: ImplementationDocument, *, now: str) -> None:
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

    def _write_channel_state(self, center_id: str, channel_id: str, *, now: str) -> ImplementationDocument:
        events = _read_jsonl(self.events_path(center_id, channel_id))
        event_state = _publication_lifecycle_from_events(events)
        current = _read_json_default(self.current_publication_path(center_id, channel_id), default={})
        publications: list[dict[str, Any]] = []
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

    def _history_has_state_event(self, center_id: str, channel_id: str, report: ImplementationDocument, event_type: str) -> bool:
        for event in _read_jsonl(self.events_path(center_id, channel_id)):
            if event.get("event_type") != event_type:
                continue
            payload = _as_document(event.get("payload"))
            if payload.get("source_hash") == report.get("source_hash") and payload.get("publication_id") == report.get("publication_id"):
                return True
        return False


def publication_channel_hash(channel: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (channel or {}).items() if key not in PUBLICATION_CHANNEL_HASH_EXCLUDE_KEYS})








def publication_report_integrity_ok(report: dict[str, Any]) -> bool:
    return bool(report) and str(report.get("integrity_hash") or "") == publication_report_hash(report)








def _publication_lifecycle_from_events(events: list[ImplementationDocument]) -> dict[str, ImplementationDocument]:
    rows: dict[str, dict[str, Any]] = {}
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


def publication_summary(report: dict[str, Any]) -> dict[str, Any]:
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
    rows: list[dict[str, Any]] = []
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
    rows: list[dict[str, Any]] = []
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
    rows: list[dict[str, Any]] = []
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


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=PUBLICATION_BLOCKED_KEYS)


def _html(value: Any) -> str:
    import html

    return html.escape(str(value or ""))
