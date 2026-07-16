from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore, accepted_evidence_summary
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_read_model import accepted_evidence_public_summary_from_portfolio_dir, accepted_evidence_verification_summary_from_portfolio_dir
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence_verifier import verify_release_portfolio_governance_attestation_accepted_evidence
from song_agent.domains.trust.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal
from song_agent.domains.trust.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore, registry_summary
from song_agent.domains.trust.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry
from song_agent.domains.trust.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_contracts import TRANSPARENCY_BLOCKED_KEYS, TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS, TRANSPARENCY_FEED_HASH_EXCLUDE_KEYS, TRANSPARENCY_FEED_PACKAGE_TYPE, TRANSPARENCY_MANIFEST_HASH_EXCLUDE_KEYS, TRANSPARENCY_NOTICE_HASH_EXCLUDE_KEYS, TRANSPARENCY_PACKAGE_TYPE, TRANSPARENCY_REPORT_PACKAGE_TYPE, _accepted_evidence_current, _build_events, _build_notices, transparency_event_hash, transparency_feed_hash, transparency_manifest_hash, transparency_notice_hash, transparency_summary


TRANSPARENCY_SCHEMA_VERSION = 1





TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}





class ReleasePortfolioGovernanceAttestationTransparencyError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyNotFoundError(ReleasePortfolioGovernanceAttestationTransparencyError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyStateError(ReleasePortfolioGovernanceAttestationTransparencyError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyStore:
    def __init__(
        self,
        *,
        attestation_store: ReleasePortfolioGovernanceAttestationStore,
        registry_store: ReleasePortfolioGovernanceAttestationRegistryStore,
        portal_store: ReleasePortfolioGovernanceAttestationPortalStore,
        accepted_evidence_store: ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore,
    ) -> None:
        self.attestation_store = attestation_store
        self.registry_store = registry_store
        self.portal_store = portal_store
        self.accepted_evidence_store = accepted_evidence_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        root = self.attestation_store.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation-transparency"
        if str(profile or "public_summary") == "public_summary":
            return root
        return root / "profiles" / _safe_profile(profile)

    def feed_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "transparency-feed.json"

    def report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "transparency-report.json"

    def history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "transparency-history.jsonl"

    def notices_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "notices"

    def verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "transparency-verification-report.json"

    def export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "transparency-export"

    def zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "governance-attestation-transparency.zip"

    def read_feed(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.feed_path(portfolio_id, profile), default=default)

    def read_report(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(portfolio_id, profile), default=default)

    def read_export_manifest(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        path = self.export_dir(portfolio_id, profile) / "transparency-manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceAttestationTransparencyNotFoundError("Attestation Transparency export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

    def refresh_feed(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            require_accepted = bool(payload.get("require_accepted_evidence", False))
            previous = self.read_feed(portfolio_id, profile=profile, default={})
            public_state = self.build_public_state(portfolio_id, profile=profile)
            source = self.build_source(portfolio_id, public_state=public_state, profile=profile)
            events = _build_events(portfolio_id, profile, public_state, source, now=now)
            notices = _build_notices(portfolio_id, profile, public_state, source, events, previous, now=now)
            blockers, warnings, checks = self._findings(public_state, source, events, notices, require_accepted=require_accepted)
            summary = _feed_summary(public_state, events, notices, blockers, warnings)
            feed = {
                "schema_version": TRANSPARENCY_SCHEMA_VERSION,
                "package_type": TRANSPARENCY_FEED_PACKAGE_TYPE,
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "status": "failed" if blockers else "warning" if warnings else "current",
                "readiness": "blocked" if blockers else "ready",
                "generated_at": now,
                "source": source,
                "source_hash": stable_hash(source),
                "current_public_state": public_state,
                "events": events,
                "notices": notices,
                "summary": summary,
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            feed["integrity_hash"] = transparency_feed_hash(feed)
            report = _report_from_feed(feed, now=now)
            self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            self.notices_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.feed_path(portfolio_id, profile), feed)
            _write_json(self.report_path(portfolio_id, profile), report)
            for notice in notices:
                _write_json(self.notices_dir(portfolio_id, profile) / f"{notice.get('notice_id')}.json", notice)
            self._append_history(portfolio_id, profile, "transparency_feed_refreshed", {"source_hash": feed["source_hash"], "integrity_hash": feed["integrity_hash"], "status": feed["status"]}, now=now)
            return sanitize_metadata(feed, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

    def build_public_state(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        self.attestation_store.portfolio_store.get_portfolio(portfolio_id)
        registry_zip = self.registry_store.zip_path(portfolio_id, profile)
        registry_verification = verify_release_portfolio_governance_attestation_registry(
            registry_zip,
            strict=True,
            require_current=False,
            require_published=False,
            require_no_revoked_current=False,
            require_accepted_evidence=False,
        )
        registry_manifest = _read_zip_json(registry_zip, "manifest.json")
        registry_doc = _read_zip_json(registry_zip, "registry.json")
        registry_counts = registry_summary(registry_doc)
        current_id = str(registry_doc.get("current_entry_id") or "")
        current_entry = _find_entry(registry_doc, current_id) if current_id else {}
        current_source = current_entry.get("source") if isinstance(current_entry.get("source"), dict) else {}

        attestation_zip = self.attestation_store.zip_path(portfolio_id, profile)
        attestation_verification = verify_release_portfolio_governance_attestation(attestation_zip, strict=True, require_vault=True, require_final_board=True)
        attestation_manifest = _read_zip_json(attestation_zip, "manifest.json")

        portal_zip = self.portal_store.zip_path(portfolio_id, profile)
        portal_verification = verify_release_portfolio_governance_attestation_portal(
            portal_zip,
            strict=True,
            require_current=False,
            require_registry=False,
            require_attestation=False,
            require_accepted_evidence=False,
        )
        portal_manifest = _read_zip_json(portal_zip, "portal-manifest.json")
        portal_report = _read_zip_json(portal_zip, "portal-report.json")
        portal_source = portal_report.get("source") if isinstance(portal_report.get("source"), dict) else {}

        portfolio_dir = self.attestation_store.portfolio_store.portfolio_dir(portfolio_id)
        accepted_public = accepted_evidence_public_summary_from_portfolio_dir(portfolio_dir, profile=profile)
        accepted_verification_summary = accepted_evidence_verification_summary_from_portfolio_dir(portfolio_dir, profile=profile)
        accepted_evidence = self.accepted_evidence_store.read_evidence(portfolio_id, profile=profile, default={})
        accepted_zip = self.accepted_evidence_store.zip_path(portfolio_id, profile)
        accepted_verification = {}
        if accepted_zip.exists():
            accepted_verification = verify_release_portfolio_governance_attestation_accepted_evidence(accepted_zip, strict=True, require_current=False)

        state = {
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "registry": {
                "status": registry_doc.get("status") or "missing",
                "current_entry_id": current_id or None,
                "current_entry_status": current_entry.get("status") if current_entry else "missing",
                "current_entry_hash": current_entry.get("integrity_hash") if current_entry else None,
                "current_certificate_id": current_entry.get("certificate_id") if current_entry else None,
                "published_count": registry_counts.get("published_count", 0),
                "revoked_count": registry_counts.get("revoked_count", 0),
                "superseded_count": registry_counts.get("superseded_count", 0),
                "registry_zip_sha256": _sha256(registry_zip),
                "registry_zip_size_bytes": registry_zip.stat().st_size if registry_zip.exists() else None,
                "registry_manifest_hash": registry_manifest.get("integrity_hash"),
                "registry_verification_status": registry_verification.get("status") or "missing",
                "registry_verification_hash": _verification_hash(registry_verification) if registry_verification else None,
            },
            "public_attestation": {
                "certificate_id": current_entry.get("certificate_id") if current_entry else None,
                "attestation_zip_sha256": _sha256(attestation_zip),
                "attestation_zip_size_bytes": attestation_zip.stat().st_size if attestation_zip.exists() else None,
                "attestation_manifest_hash": attestation_manifest.get("integrity_hash"),
                "attestation_verification_status": attestation_verification.get("status") or "missing",
                "attestation_verification_hash": _verification_hash(attestation_verification) if attestation_verification else None,
                "current_entry_attestation_zip_sha256": current_source.get("attestation_zip_sha256") if current_entry else None,
                "current_entry_attestation_manifest_hash": current_source.get("attestation_manifest_hash") if current_entry else None,
            },
            "portal": {
                "portal_zip_sha256": _sha256(portal_zip),
                "portal_zip_size_bytes": portal_zip.stat().st_size if portal_zip.exists() else None,
                "portal_manifest_hash": portal_manifest.get("integrity_hash"),
                "portal_source_hash": portal_report.get("source_hash"),
                "portal_verification_status": portal_verification.get("status") or "missing",
                "portal_verification_hash": _verification_hash(portal_verification) if portal_verification else None,
                "portal_registry_zip_sha256": portal_source.get("registry_zip_sha256"),
                "portal_current_attestation_zip_sha256": portal_source.get("current_attestation_zip_sha256"),
            },
            "accepted_evidence": {
                "status": accepted_public.get("status") or "missing",
                "external_review_status": accepted_public.get("external_review_status") or "missing",
                "accepted_evidence_id": accepted_public.get("accepted_evidence_id"),
                "response_id": accepted_public.get("response_id"),
                "reviewer_label": accepted_public.get("reviewer_label"),
                "reviewed_at": accepted_public.get("reviewed_at"),
                "source_hash": accepted_public.get("source_hash"),
                "accepted_evidence_integrity_hash": accepted_evidence.get("integrity_hash") if accepted_evidence else None,
                "accepted_evidence_zip_sha256": accepted_verification_summary.get("accepted_evidence_zip_sha256"),
                "accepted_evidence_zip_size_bytes": accepted_verification_summary.get("accepted_evidence_zip_size_bytes"),
                "accepted_evidence_manifest_hash": accepted_verification_summary.get("accepted_evidence_manifest_hash"),
                "accepted_evidence_verification_status": accepted_verification_summary.get("accepted_evidence_verification_status") or "missing",
                "accepted_evidence_verification_report_hash": accepted_verification_summary.get("accepted_evidence_verification_report_hash"),
                "accepted_evidence_verification_hash": _verification_hash(accepted_verification) if accepted_verification else None,
                "current_entry_id": accepted_public.get("current_entry_id"),
                "current_certificate_id": accepted_public.get("current_certificate_id"),
            },
            "evidence_vault": {
                "zip_sha256": current_source.get("evidence_vault_zip_sha256") if current_entry else None,
                "manifest_hash": current_source.get("evidence_vault_manifest_hash") if current_entry else None,
                "verification_hash": current_source.get("evidence_vault_verification_hash") if current_entry else None,
                "deep_verification_status": current_source.get("evidence_vault_deep_verification_status") if current_entry else "missing",
            },
            "final_board": {"signoff_hash": current_source.get("final_board_signoff_hash") if current_entry else None},
        }
        return sanitize_metadata(state, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

    def build_source(self, portfolio_id: str, *, public_state: dict[str, Any] | None = None, profile: str = "public_summary") -> dict[str, Any]:
        state = public_state if isinstance(public_state, dict) else self.build_public_state(portfolio_id, profile=profile)
        registry = state.get("registry") if isinstance(state.get("registry"), dict) else {}
        attestation = state.get("public_attestation") if isinstance(state.get("public_attestation"), dict) else {}
        portal = state.get("portal") if isinstance(state.get("portal"), dict) else {}
        accepted = state.get("accepted_evidence") if isinstance(state.get("accepted_evidence"), dict) else {}
        source = {
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "public_state_hash": stable_hash(state),
            "registry_verification_status": registry.get("registry_verification_status"),
            "registry_zip_sha256": registry.get("registry_zip_sha256"),
            "registry_manifest_hash": registry.get("registry_manifest_hash"),
            "registry_verification_hash": registry.get("registry_verification_hash"),
            "registry_current_entry_id": registry.get("current_entry_id"),
            "registry_current_entry_status": registry.get("current_entry_status"),
            "registry_current_entry_hash": registry.get("current_entry_hash"),
            "current_certificate_id": registry.get("current_certificate_id"),
            "attestation_verification_status": attestation.get("attestation_verification_status"),
            "attestation_zip_sha256": attestation.get("attestation_zip_sha256"),
            "attestation_manifest_hash": attestation.get("attestation_manifest_hash"),
            "attestation_verification_hash": attestation.get("attestation_verification_hash"),
            "portal_verification_status": portal.get("portal_verification_status"),
            "portal_zip_sha256": portal.get("portal_zip_sha256"),
            "portal_manifest_hash": portal.get("portal_manifest_hash"),
            "portal_verification_hash": portal.get("portal_verification_hash"),
            "accepted_evidence_status": accepted.get("status"),
            "accepted_evidence_external_review_status": accepted.get("external_review_status"),
            "accepted_evidence_id": accepted.get("accepted_evidence_id"),
            "accepted_evidence_source_hash": accepted.get("source_hash"),
            "accepted_evidence_integrity_hash": accepted.get("accepted_evidence_integrity_hash"),
            "accepted_evidence_zip_sha256": accepted.get("accepted_evidence_zip_sha256"),
            "accepted_evidence_manifest_hash": accepted.get("accepted_evidence_manifest_hash"),
            "accepted_evidence_verification_status": accepted.get("accepted_evidence_verification_status"),
            "accepted_evidence_verification_hash": accepted.get("accepted_evidence_verification_hash"),
            "accepted_evidence_verification_report_hash": accepted.get("accepted_evidence_verification_report_hash"),
        }
        return sanitize_metadata(source, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

    def feed_is_stale(self, portfolio_id: str, feed: dict[str, Any] | None = None, *, profile: str = "public_summary") -> bool:
        data = feed if isinstance(feed, dict) else self.read_feed(portfolio_id, profile=profile, default={})
        if not data:
            return False
        try:
            source = self.build_source(portfolio_id, profile=str(data.get("attestation_profile") or profile))
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_transparency(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            feed = self.read_feed(portfolio_id, profile=profile, default={}) or self.refresh_feed(portfolio_id, payload, now=now)
            report = self.read_report(portfolio_id, profile=profile, default={})
            self._ensure_exportable(portfolio_id, feed, report, profile=profile)
            state = _state_tuple(feed)
            if self._history_has_state_event(portfolio_id, profile, state, "transparency_exported"):
                raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency export already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "transparency-manifest.json", default={})
            if _manifest_state(existing_manifest) == state:
                raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency export already exists for this source state.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            (export_dir / "notices").mkdir(parents=True, exist_ok=True)
            _write_json(export_dir / "transparency-feed.json", feed)
            _write_json(export_dir / "transparency-report.json", report)
            data_docs = _data_documents(feed)
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            for notice in feed.get("notices", []) if isinstance(feed.get("notices"), list) else []:
                if isinstance(notice, dict):
                    _write_json(export_dir / "notices" / f"{notice.get('notice_id')}.json", notice)
            (export_dir / "README.txt").write_text(_readme(feed), encoding="utf-8")
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "transparency-manifest.json"]
            public_state = feed.get("current_public_state") if isinstance(feed.get("current_public_state"), dict) else {}
            registry = public_state.get("registry") if isinstance(public_state.get("registry"), dict) else {}
            manifest = {
                "schema_version": TRANSPARENCY_SCHEMA_VERSION,
                "package_type": TRANSPARENCY_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Release Portfolio Governance Attestation Transparency", "version": __version__},
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "created_at": now,
                "source_hash": feed.get("source_hash"),
                "feed": {
                    "integrity_hash": feed.get("integrity_hash"),
                    "source_hash": feed.get("source_hash"),
                    "event_count": len(feed.get("events") if isinstance(feed.get("events"), list) else []),
                    "notice_count": len(feed.get("notices") if isinstance(feed.get("notices"), list) else []),
                },
                "report": {"integrity_hash": report.get("integrity_hash"), "source_hash": report.get("source_hash")},
                "current_public_state": {
                    "public_state_hash": feed.get("source", {}).get("public_state_hash") if isinstance(feed.get("source"), dict) else None,
                    "current_entry_id": registry.get("current_entry_id"),
                    "current_certificate_id": registry.get("current_certificate_id"),
                },
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"feed": feed, "report": report, "data": data_docs}),
            }
            manifest["integrity_hash"] = transparency_manifest_hash(manifest)
            _write_json(export_dir / "transparency-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "transparency_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            feed = self.read_feed(portfolio_id, profile=profile, default={})
            report = self.read_report(portfolio_id, profile=profile, default={})
            self._ensure_exportable(portfolio_id, feed, report, profile=profile)
            state = _state_tuple(feed)
            if self._history_has_state_event(portfolio_id, profile, state, "transparency_zip_built"):
                raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency ZIP already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "transparency-manifest.json").exists():
                if self._history_has_state_event(portfolio_id, profile, state, "transparency_exported"):
                    raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency export already exists for this source state.")
                self.export_transparency(portfolio_id, payload, now=now)
            if zip_path.exists():
                manifest_in_zip = _read_zip_json(zip_path, "transparency-manifest.json")
                if _manifest_state(manifest_in_zip) == state:
                    raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency ZIP already exists for this source state.")
            manifest = read_json(export_dir / "transparency-manifest.json")
            if _manifest_state(manifest) != state:
                raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency export is stale. Re-export before ZIP.")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = transparency_manifest_hash(manifest)
            _write_json(export_dir / "transparency-manifest.json", manifest)
            entries = _zip_entries(export_dir)
            tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for resolved, entry in entries:
                        archive.write(resolved, entry)
                tmp_path.replace(zip_path)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "entries": [entry for _path, entry in entries]}
            self._append_history(portfolio_id, profile, "transparency_zip_built", {**state, "sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

    def verify_transparency(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency, write_release_portfolio_governance_attestation_transparency_verification_report

        payload = payload or {}
        profile = str(payload.get("profile") or "public_summary")
        report = verify_release_portfolio_governance_attestation_transparency(
            self.zip_path(portfolio_id, profile),
            strict=bool(payload.get("strict", False)),
            require_current=bool(payload.get("require_current", False)),
            require_accepted_evidence=bool(payload.get("require_accepted_evidence", False)),
            require_no_revoked_current=bool(payload.get("require_no_revoked_current", False)),
            require_contiguous_chain=bool(payload.get("require_contiguous_chain", False)),
            now=now,
        )
        write_release_portfolio_governance_attestation_transparency_verification_report(report, self.verification_report_path(portfolio_id, profile))
        return report

    def list_notices(self, portfolio_id: str, *, profile: str = "public_summary") -> list[dict[str, Any]]:
        feed = self.read_feed(portfolio_id, profile=profile, default={})
        notices = feed.get("notices") if isinstance(feed.get("notices"), list) else []
        return [sanitize_metadata(item, blocked_keys=TRANSPARENCY_BLOCKED_KEYS) for item in notices if isinstance(item, dict)]

    def get_notice(self, portfolio_id: str, notice_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        for notice in self.list_notices(portfolio_id, profile=profile):
            if notice.get("notice_id") == notice_id:
                return notice
        raise ReleasePortfolioGovernanceAttestationTransparencyNotFoundError("Attestation Transparency notice not found.")

    def summary(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        feed = self.read_feed(portfolio_id, profile=profile, default={})
        report = self.read_report(portfolio_id, profile=profile, default={})
        verification = _read_json_default(self.verification_report_path(portfolio_id, profile), default={})
        summary = transparency_summary(feed)
        summary["report_status"] = report.get("status") or "missing"
        summary["verification_status"] = verification.get("status") or "missing"
        if feed:
            summary["stale"] = self.feed_is_stale(portfolio_id, feed, profile=profile)
        return sanitize_metadata(summary, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)

    def _findings(
        self,
        public_state: ImplementationDocument,
        source: ImplementationDocument,
        events: list[ImplementationDocument],
        notices: list[ImplementationDocument],
        *,
        require_accepted: bool,
    ) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)
            if not passed:
                (warnings if warning else blockers).append({"check_id": check_id, "severity": row["severity"], "message": message})

        check("registry_verification_passed", source.get("registry_verification_status") == "passed", "Registry verification is passed.")
        check("registry_current_published", source.get("registry_current_entry_id") and source.get("registry_current_entry_status") == "published", "Registry current entry is published.")
        check("attestation_verification_passed", source.get("attestation_verification_status") == "passed", "Public Attestation verification is passed.")
        check("portal_verification_passed", source.get("portal_verification_status") == "passed", "Portal verification is passed.")
        check("event_chain_valid", _event_chain_valid(events), "Transparency event chain is contiguous.")
        check("notices_valid", all(transparency_notice_integrity_ok(item) for item in notices), "Transparency notices have valid integrity.")
        if require_accepted:
            check("accepted_evidence_required", _accepted_evidence_current(source), "Accepted Evidence is current and verified.")
        else:
            check("accepted_evidence_optional", _accepted_evidence_current(source) or source.get("accepted_evidence_status") in {"missing", None}, "Accepted Evidence is current or absent.", warning=not _accepted_evidence_current(source))
        check("redaction_scan", _redaction_summary({"public_state": public_state, "source": source, "events": events, "notices": notices}).get("status") == "passed", "Transparency feed contains no sensitive values.")
        return blockers, warnings, checks

    def _ensure_exportable(self, portfolio_id: str, feed: ImplementationDocument, report: ImplementationDocument, *, profile: str) -> None:
        if not transparency_feed_integrity_ok(feed):
            raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency Feed integrity failed.")
        if not transparency_report_integrity_ok(report):
            raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency Report integrity failed.")
        if self.feed_is_stale(portfolio_id, feed, profile=profile):
            raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency Feed is stale. Refresh before export.")
        if feed.get("status") == "failed" or report.get("status") == "failed":
            raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency Feed is failed.")
        if report.get("source", {}).get("feed_hash") != feed.get("integrity_hash"):
            raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Attestation Transparency Report does not match Feed.")

    def _history_has_state_event(self, portfolio_id: str, profile: str, state: dict[str, str], event_type: str) -> bool:
        path = self.history_path(portfolio_id, profile)
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or str(event.get("type") or "") != event_type:
                continue
            summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
            if all(str(summary.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: ImplementationDocument, *, now: str) -> None:
        path = self.history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"atttrans-history-{count + 1:06d}", "at": now, "type": event_type, "summary": summary}, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")





def transparency_feed_integrity_ok(feed: dict[str, Any] | None) -> bool:
    data = feed if isinstance(feed, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_feed_hash(data)


def transparency_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS})


def transparency_report_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_report_hash(data)





def transparency_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_manifest_hash(data)








def transparency_notice_integrity_ok(notice: dict[str, Any] | None) -> bool:
    data = notice if isinstance(notice, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == transparency_notice_hash(data)





def _report_from_feed(feed: ImplementationDocument, *, now: str) -> ImplementationDocument:
    source = {
        "feed_hash": feed.get("integrity_hash"),
        "feed_source_hash": feed.get("source_hash"),
        "public_state_hash": (feed.get("source") if isinstance(feed.get("source"), dict) else {}).get("public_state_hash"),
        "registry_manifest_hash": (feed.get("source") if isinstance(feed.get("source"), dict) else {}).get("registry_manifest_hash"),
        "portal_manifest_hash": (feed.get("source") if isinstance(feed.get("source"), dict) else {}).get("portal_manifest_hash"),
        "accepted_evidence_manifest_hash": (feed.get("source") if isinstance(feed.get("source"), dict) else {}).get("accepted_evidence_manifest_hash"),
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
        "summary": feed.get("summary") if isinstance(feed.get("summary"), dict) else {},
        "checks": feed.get("checks") if isinstance(feed.get("checks"), list) else [],
        "blockers": feed.get("blockers") if isinstance(feed.get("blockers"), list) else [],
        "warnings": feed.get("warnings") if isinstance(feed.get("warnings"), list) else [],
    }
    report["integrity_hash"] = transparency_report_hash(report)
    return sanitize_metadata(report, blocked_keys=TRANSPARENCY_BLOCKED_KEYS)


def _feed_summary(public_state: ImplementationDocument, events: list[ImplementationDocument], notices: list[ImplementationDocument], blockers: list[ImplementationDocument], warnings: list[ImplementationDocument]) -> ImplementationDocument:
    registry = public_state.get("registry") if isinstance(public_state.get("registry"), dict) else {}
    accepted = public_state.get("accepted_evidence") if isinstance(public_state.get("accepted_evidence"), dict) else {}
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








def _data_documents(feed: ImplementationDocument) -> dict[str, ImplementationDocument]:
    state = feed.get("current_public_state") if isinstance(feed.get("current_public_state"), dict) else {}
    source = feed.get("source") if isinstance(feed.get("source"), dict) else {}
    registry = state.get("registry") if isinstance(state.get("registry"), dict) else {}
    portal = state.get("portal") if isinstance(state.get("portal"), dict) else {}
    attestation = state.get("public_attestation") if isinstance(state.get("public_attestation"), dict) else {}
    accepted = state.get("accepted_evidence") if isinstance(state.get("accepted_evidence"), dict) else {}
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


def _state_tuple(feed: ImplementationDocument) -> dict[str, str]:
    return {"source_hash": str(feed.get("source_hash") or ""), "integrity_hash": str(feed.get("integrity_hash") or "")}


def _manifest_state(manifest: ImplementationDocument) -> dict[str, str]:
    feed_row = manifest.get("feed") if isinstance(manifest.get("feed"), dict) else {}
    return {"source_hash": str(manifest.get("source_hash") or ""), "integrity_hash": str(feed_row.get("integrity_hash") or "")}


def _event_chain_valid(events: list[ImplementationDocument]) -> bool:
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





def _readme(feed: ImplementationDocument) -> str:
    summary = feed.get("summary") if isinstance(feed.get("summary"), dict) else {}
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


def _find_entry(registry: ImplementationDocument, entry_id: str) -> ImplementationDocument:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
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


def _verification_hash(report: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceAttestationTransparencyStateError("Resolved path escapes Attestation Transparency directory.") from exc


def _redaction_summary(value: Any) -> ImplementationDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}


def _safe_profile(profile: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(profile or "public_summary"))[:80] or "public_summary"
