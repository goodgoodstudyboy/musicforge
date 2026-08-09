from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list, _document_or

import base64 as base64
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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore as ReleasePortfolioGovernanceAttestationTransparencyStore
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency as verify_release_portfolio_governance_attestation_transparency, write_release_portfolio_governance_attestation_transparency_verification_report as write_release_portfolio_governance_attestation_transparency_verification_report
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement_contracts import ACK_BLOCKED_KEYS as ACK_BLOCKED_KEYS, ACK_EVIDENCE_HASH_EXCLUDE_KEYS as ACK_EVIDENCE_HASH_EXCLUDE_KEYS, ACK_EVIDENCE_PACKAGE_TYPE as ACK_EVIDENCE_PACKAGE_TYPE, ACK_MANIFEST_HASH_EXCLUDE_KEYS as ACK_MANIFEST_HASH_EXCLUDE_KEYS, ACK_PACK_HASH_EXCLUDE_KEYS as ACK_PACK_HASH_EXCLUDE_KEYS, ACK_PACK_PACKAGE_TYPE as ACK_PACK_PACKAGE_TYPE, ACK_RESPONSE_PACKAGE_TYPE as ACK_RESPONSE_PACKAGE_TYPE, ACK_SCHEMA_VERSION as ACK_SCHEMA_VERSION, ack_evidence_hash as ack_evidence_hash, ack_manifest_hash as ack_manifest_hash, ack_pack_hash as ack_pack_hash, acknowledgement_summary as acknowledgement_summary, response_template as response_template









ACK_RESPONSE_HASH_FIELDS = (
    "response_id",
    "review_pack_id",
    "review_pack_source_hash",
    "portfolio_id",
    "profile",
    "transparency_zip_sha256",
    "transparency_manifest_hash",
    "transparency_feed_source_hash",
    "reviewer",
    "review_status",
    "reviewed_notice_ids",
    "reviewed_event_ids",
    "comments",
    "concerns",
    "submitted_at",
)

ACK_ALLOWED_RESPONSE_STATUSES = {"accepted", "needs_changes", "rejected"}


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError):
    pass


class ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore:
    def __init__(self, *, transparency_store: ReleasePortfolioGovernanceAttestationTransparencyStore) -> None:
        self.transparency_store = transparency_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        root = self.transparency_store.attestation_store.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation-transparency-ack"
        if str(profile or "public_summary") == "public_summary":
            return root
        return root / "profiles" / _safe_profile(profile)

    def pack_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack.json"

    def pack_history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "acknowledgement-pack-history.jsonl"

    def pack_export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack-export"

    def pack_zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack.zip"

    def pack_verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-pack-verification-report.json"

    def responses_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "responses"

    def response_path(self, portfolio_id: str, response_id: str, profile: str = "public_summary") -> Path:
        return self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}.json"

    def response_verification_report_path(self, portfolio_id: str, response_id: str, profile: str = "public_summary") -> Path:
        return self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}-verification-report.json"

    def evidence_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence.json"

    def evidence_export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence-export"

    def evidence_zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence.zip"

    def evidence_verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "ack-evidence-verification-report.json"

    def change_requests_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "change-request-drafts"

    def read_pack(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.pack_path(portfolio_id, profile), default=default)

    def read_response(self, portfolio_id: str, response_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        path = self.response_path(portfolio_id, response_id, profile)
        if not path.exists():
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError(f"Acknowledgement response not found: {response_id}")
        return sanitize_metadata(read_json(path), blocked_keys=ACK_BLOCKED_KEYS)

    def list_responses(self, portfolio_id: str, *, profile: str = "public_summary") -> list[dict[str, Any]]:
        root = self.responses_dir(portfolio_id, profile)
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("att-trans-ack-response-*.json")):
            value = _read_json_default(path, default={})
            if value:
                rows.append(response_summary(value))
        return rows

    def read_evidence(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.evidence_path(portfolio_id, profile), default=default)

    def refresh_pack(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            require_verified = bool((payload or {}).get("require_transparency_verified", True))
            source = self.build_pack_source(portfolio_id, profile=profile)
            blockers, warnings, checks = self._pack_findings(source, require_verified=require_verified)
            feed = self.transparency_store.read_feed(portfolio_id, profile=profile, default={})
            pack = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_PACK_PACKAGE_TYPE,
                "pack_id": _pack_id(portfolio_id, profile, source),
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "ready",
                "source": source,
                "source_hash": stable_hash(source),
                "summary": {
                    "event_count": len(feed.get("events", []) if isinstance(feed.get("events"), list) else []),
                    "notice_count": len(feed.get("notices", []) if isinstance(feed.get("notices"), list) else []),
                    "latest_notice_type": (_as_document(feed.get("summary"))).get("latest_notice_type"),
                    "requires_response": True,
                },
                "response_requirements": {
                    "allowed_status": sorted(ACK_ALLOWED_RESPONSE_STATUSES),
                    "required_fields": [
                        "review_pack_id",
                        "review_pack_source_hash",
                        "transparency_zip_sha256",
                        "transparency_manifest_hash",
                        "transparency_feed_source_hash",
                        "reviewer",
                        "review_status",
                        "reviewed_notice_ids",
                    ],
                },
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            pack["integrity_hash"] = ack_pack_hash(pack)
            self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.pack_path(portfolio_id, profile), pack)
            self._append_history(portfolio_id, profile, "ack_pack_refreshed", {"pack_id": pack["pack_id"], "source_hash": pack["source_hash"], "status": pack["status"]}, now=now)
            return sanitize_metadata(pack, blocked_keys=ACK_BLOCKED_KEYS)

    def build_pack_source(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        self.transparency_store.attestation_store.portfolio_store.get_portfolio(portfolio_id)
        zip_path = self.transparency_store.zip_path(portfolio_id, profile)
        verification = verify_release_portfolio_governance_attestation_transparency(
            zip_path,
            strict=True,
            require_current=True,
            require_accepted_evidence=False,
            require_contiguous_chain=True,
        )
        write_release_portfolio_governance_attestation_transparency_verification_report(verification, self.transparency_store.verification_report_path(portfolio_id, profile))
        feed = self.transparency_store.read_feed(portfolio_id, profile=profile, default={})
        manifest = _read_json_default(self.transparency_store.export_dir(portfolio_id, profile) / "transparency-manifest.json", default={})
        checks = {str(item.get("check_id")): item.get("status") for item in verification.get("checks", []) if isinstance(item, dict)}
        source = {
            "portfolio_id": portfolio_id,
            "profile": profile,
            "transparency_zip_sha256": _sha256(zip_path),
            "transparency_zip_size_bytes": zip_path.stat().st_size if zip_path.exists() and zip_path.is_file() else None,
            "transparency_manifest_hash": manifest.get("integrity_hash") or verification.get("manifest_hash"),
            "transparency_feed_source_hash": feed.get("source_hash"),
            "transparency_feed_integrity_hash": feed.get("integrity_hash"),
            "transparency_verification_status": verification.get("status") or "missing",
            "transparency_verification_hash": verification_hash(verification),
            "transparency_event_semantics_status": checks.get("transparency_event_semantics_match"),
            "transparency_notice_semantics_status": checks.get("transparency_notice_semantics_match"),
            "current_public_state_hash": (_as_document(feed.get("source"))).get("public_state_hash"),
            "current_entry_id": (_as_document(feed.get("summary"))).get("current_entry_id"),
            "current_certificate_id": (_as_document(feed.get("summary"))).get("current_certificate_id"),
            "portal_manifest_hash": (_as_document(feed.get("source"))).get("portal_manifest_hash"),
            "accepted_evidence_manifest_hash": (_as_document(feed.get("source"))).get("accepted_evidence_manifest_hash"),
            "event_ids": [str(item.get("event_id")) for item in feed.get("events", []) if isinstance(item, dict) and item.get("event_id")],
            "notice_ids": [str(item.get("notice_id")) for item in feed.get("notices", []) if isinstance(item, dict) and item.get("notice_id")],
            "warning_notice_ids": [str(item.get("notice_id")) for item in feed.get("notices", []) if isinstance(item, dict) and item.get("notice_id") and item.get("severity") in {"warning", "critical"}],
        }
        return sanitize_metadata(source, blocked_keys=ACK_BLOCKED_KEYS)

    def pack_is_stale(self, portfolio_id: str, pack: dict[str, Any] | None = None, *, profile: str = "public_summary") -> bool:
        data = _document_or(pack, self.read_pack(portfolio_id, profile=profile, default={}))
        if not data:
            return False
        try:
            source = self.build_pack_source(portfolio_id, profile=str(data.get("profile") or profile))
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_pack(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            pack = self.read_pack(portfolio_id, profile=profile, default={}) or self.refresh_pack(portfolio_id, {"profile": profile}, now=now)
            if self.pack_is_stale(portfolio_id, pack, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack source is stale. Refresh the pack before export.")
            if pack.get("status") == "failed":
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack has blockers and cannot be exported.")
            state = _state_tuple(pack)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_pack_exported"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack export already exists for this source state.")
            export_dir = self.pack_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            (export_dir / "forms").mkdir(parents=True, exist_ok=True)
            data_docs = _pack_data_documents(pack, self.transparency_store.read_feed(portfolio_id, profile=profile, default={}))
            _write_json(export_dir / "transparency-acknowledgement-pack.json", pack)
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            template = response_template(pack)
            _write_json(export_dir / "forms" / "response-template.json", template)
            _write_json(export_dir / "forms" / "response-schema.json", _response_schema(pack))
            (export_dir / "README.txt").write_text(_pack_readme(pack), encoding="utf-8")
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "acknowledgement-pack-manifest.json"]
            manifest = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_PACK_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Transparency Acknowledgement Pack", "version": __version__},
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "source_hash": pack.get("source_hash"),
                "pack": {"pack_id": pack.get("pack_id"), "integrity_hash": pack.get("integrity_hash"), "source_hash": pack.get("source_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": redaction_summary({"pack": pack, "data": data_docs, "template": template}),
            }
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-pack-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "ack_pack_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=ACK_BLOCKED_KEYS)

    def build_pack_zip(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            pack = self.read_pack(portfolio_id, profile=profile, default={}) or self.refresh_pack(portfolio_id, {"profile": profile}, now=now)
            if self.pack_is_stale(portfolio_id, pack, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack source is stale. Refresh the pack before ZIP.")
            state = _state_tuple(pack)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_pack_zip_built"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack ZIP already exists for this source state.")
            export_dir = self.pack_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.pack_zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "acknowledgement-pack-manifest.json").exists():
                self.export_pack(portfolio_id, {"profile": profile}, now=now)
            manifest = read_json(export_dir / "acknowledgement-pack-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-pack-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "path": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries)}
            self._append_history(portfolio_id, profile, "ack_pack_zip_built", {**state, "zip_sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=ACK_BLOCKED_KEYS)

    def import_response(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            if any(payload.get(key) for key in ("source_path", "local_path", "file_path")):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response import only accepts uploaded content; source_path/local_path/file_path are not allowed.")
            raw = _payload_bytes(payload, max_size=1024 * 1024)
            response_payload = _response_payload_from_bytes(raw)
            pack = self.read_pack(portfolio_id, profile=profile, default={})
            if not pack:
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Transparency Acknowledgement Pack is missing.")
            _require_response_source_binding(response_payload)
            imported_id = _next_id(self.responses_dir(portfolio_id, profile), "att-trans-ack-response")
            external_id = str(response_payload.get("response_id") or "").strip()
            response_hash_value = response_payload_hash(response_payload)
            if response_payload.get("response_hash") and response_payload.get("response_hash") != response_hash_value:
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response_hash does not match payload.")
            verification = verify_response_document(response_payload, pack, now=now)
            stale = _response_stale(response_payload, pack)
            record = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_RESPONSE_PACKAGE_TYPE,
                "response_id": imported_id,
                "external_response_id": external_id or imported_id,
                "portfolio_id": portfolio_id,
                "profile": profile,
                "imported_at": now,
                "status": response_payload.get("review_status"),
                "verification_status": verification.get("status"),
                "stale": stale,
                "source": {
                    "review_pack_id": response_payload.get("review_pack_id"),
                    "review_pack_source_hash": response_payload.get("review_pack_source_hash"),
                    "transparency_zip_sha256": response_payload.get("transparency_zip_sha256"),
                    "transparency_manifest_hash": response_payload.get("transparency_manifest_hash"),
                    "transparency_feed_source_hash": response_payload.get("transparency_feed_source_hash"),
                },
                "response_payload": response_payload,
                "payload_hash": response_hash_value,
                "verification": verification,
                "redaction_summary": redaction_summary(response_payload),
            }
            record["integrity_hash"] = response_record_hash(record)
            self.responses_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.response_path(portfolio_id, imported_id, profile), record)
            _write_json(self.response_verification_report_path(portfolio_id, imported_id, profile), verification)
            self._append_history(portfolio_id, profile, "ack_response_imported", {"response_id": imported_id, "external_response_id": external_id, "status": record["status"], "verification_status": record["verification_status"], "stale": stale}, now=now)
            if verification.get("status") == "failed":
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response verification failed.")
            return {"response": sanitize_metadata(record, blocked_keys=ACK_BLOCKED_KEYS), "verification": verification}

    def verify_response(self, portfolio_id: str, response_id: str, *, profile: str = "public_summary", now: str | None = None) -> dict[str, Any]:
        record = self.read_response(portfolio_id, response_id, profile=profile)
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        payload = _as_document(record.get("response_payload"))
        return verify_response_document(payload, pack, now=now)

    def response_is_stale(self, portfolio_id: str, response: dict[str, Any], *, profile: str = "public_summary") -> bool:
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        payload = _as_document(response.get("response_payload"))
        return not pack or _response_stale(payload, pack) or self.pack_is_stale(portfolio_id, pack, profile=profile)

    def refresh_evidence(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            response_id = str(payload.get("response_id") or "").strip() or self._latest_accepted_response_id(portfolio_id, profile)
            if not response_id:
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("No accepted acknowledgement response is available.")
            response = self.read_response(portfolio_id, response_id, profile=profile)
            verification = self.verify_response(portfolio_id, response_id, profile=profile, now=now)
            if response.get("status") != "accepted" or verification.get("status") == "failed" or self.response_is_stale(portfolio_id, response, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Only accepted, verified, non-stale acknowledgement responses can create evidence.")
            source = self.build_evidence_source(portfolio_id, response_id, profile=profile, response=response, verification=verification)
            public = _evidence_public_summary(response)
            evidence = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_EVIDENCE_PACKAGE_TYPE,
                "acknowledgement_id": _evidence_id(portfolio_id, profile, source),
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "updated_at": now,
                "status": "current",
                "external_review_status": "accepted",
                "source": source,
                "source_hash": stable_hash(source),
                "public_summary": public,
            }
            evidence["integrity_hash"] = ack_evidence_hash(evidence)
            _write_json(self.evidence_path(portfolio_id, profile), evidence)
            self._append_history(portfolio_id, profile, "ack_evidence_refreshed", {"acknowledgement_id": evidence["acknowledgement_id"], "source_hash": evidence["source_hash"], "response_id": response_id}, now=now)
            return sanitize_metadata(evidence, blocked_keys=ACK_BLOCKED_KEYS)

    def build_evidence_source(
        self,
        portfolio_id: str,
        response_id: str,
        *,
        profile: str = "public_summary",
        response: dict[str, Any] | None = None,
        verification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = _document_or(response, self.read_response(portfolio_id, response_id, profile=profile))
        verification = _document_or(verification, self.verify_response(portfolio_id, response_id, profile=profile))
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        src = _as_document(response.get("source"))
        return sanitize_metadata(
            {
                "portfolio_id": portfolio_id,
                "profile": profile,
                "response_id": response.get("response_id"),
                "response_integrity_hash": response.get("integrity_hash"),
                "response_payload_hash": response.get("payload_hash"),
                "response_status": response.get("status"),
                "response_verification_status": verification.get("status"),
                "response_verification_hash": verification_hash(verification),
                "review_pack_id": pack.get("pack_id"),
                "review_pack_source_hash": pack.get("source_hash"),
                "response_review_pack_id": src.get("review_pack_id"),
                "response_review_pack_source_hash": src.get("review_pack_source_hash"),
                "transparency_zip_sha256": src.get("transparency_zip_sha256"),
                "transparency_manifest_hash": src.get("transparency_manifest_hash"),
                "transparency_feed_source_hash": src.get("transparency_feed_source_hash"),
                "response_public_summary_hash": stable_hash(_evidence_public_summary(response)),
            },
            blocked_keys=ACK_BLOCKED_KEYS,
        )

    def evidence_is_stale(self, portfolio_id: str, evidence: dict[str, Any] | None = None, *, profile: str = "public_summary") -> bool:
        data = _document_or(evidence, self.read_evidence(portfolio_id, profile=profile, default={}))
        if not data:
            return False
        source = _as_document(data.get("source"))
        response_id = str(source.get("response_id") or "")
        if not response_id:
            return True
        try:
            current = self.build_evidence_source(portfolio_id, response_id, profile=str(data.get("profile") or profile))
        except Exception:
            return True
        return stable_hash(current) != str(data.get("source_hash") or "")

    def export_evidence(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            evidence = self.read_evidence(portfolio_id, profile=profile, default={}) or self.refresh_evidence(portfolio_id, payload, now=now)
            self._ensure_evidence_exportable(portfolio_id, evidence, profile=profile)
            state = _state_tuple(evidence)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_evidence_exported"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence export already exists for this source state.")
            export_dir = self.evidence_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            data_docs = _evidence_data_documents(evidence)
            _write_json(export_dir / "acknowledgement-evidence.json", evidence)
            _write_json(export_dir / "acknowledgement-evidence-summary.json", {"summary": acknowledgement_summary(evidence), "public_summary": evidence.get("public_summary")})
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            (export_dir / "README.txt").write_text(_evidence_readme(evidence), encoding="utf-8")
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "acknowledgement-evidence-manifest.json"]
            manifest = {
                "schema_version": ACK_SCHEMA_VERSION,
                "package_type": ACK_EVIDENCE_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Transparency Acknowledgement Evidence", "version": __version__},
                "portfolio_id": portfolio_id,
                "profile": profile,
                "created_at": now,
                "source_hash": evidence.get("source_hash"),
                "acknowledgement": {"acknowledgement_id": evidence.get("acknowledgement_id"), "integrity_hash": evidence.get("integrity_hash"), "source_hash": evidence.get("source_hash")},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": redaction_summary({"evidence": evidence, "data": data_docs}),
            }
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-evidence-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "ack_evidence_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=ACK_BLOCKED_KEYS)

    def build_evidence_zip(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            evidence = self.read_evidence(portfolio_id, profile=profile, default={}) or self.refresh_evidence(portfolio_id, payload, now=now)
            self._ensure_evidence_exportable(portfolio_id, evidence, profile=profile)
            state = _state_tuple(evidence)
            if self._history_has_state_event(portfolio_id, profile, state, "ack_evidence_zip_built"):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence ZIP already exists for this source state.")
            export_dir = self.evidence_export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.evidence_zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "acknowledgement-evidence-manifest.json").exists():
                self.export_evidence(portfolio_id, {"profile": profile}, now=now)
            manifest = read_json(export_dir / "acknowledgement-evidence-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = ack_manifest_hash(manifest)
            _write_json(export_dir / "acknowledgement-evidence-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "path": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries)}
            self._append_history(portfolio_id, profile, "ack_evidence_zip_built", {**state, "zip_sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=ACK_BLOCKED_KEYS)

    def create_change_request(self, portfolio_id: str, response_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            response = self.read_response(portfolio_id, response_id, profile=profile)
            verification = self.verify_response(portfolio_id, response_id, profile=profile, now=now)
            if response.get("status") not in {"needs_changes", "rejected"} or verification.get("status") == "failed" or self.response_is_stale(portfolio_id, response, profile=profile):
                raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Only verified non-stale needs_changes/rejected acknowledgement responses can create Change Request drafts.")
            existing = self._find_change_request(portfolio_id, response_id, profile=profile)
            if existing:
                return existing
            cr_id = _next_id(self.change_requests_dir(portfolio_id, profile), "att-trans-ack-cr")
            response_payload = _as_document(response.get("response_payload"))
            cr = {
                "change_request_id": cr_id,
                "source": "transparency_acknowledgement_response",
                "response_id": response_id,
                "status": "draft",
                "reason": "External reviewer requested Transparency acknowledgement follow-up.",
                "requested_actions": _change_request_actions(response_payload),
                "created_at": now,
            }
            self.change_requests_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.change_requests_dir(portfolio_id, profile) / f"{cr_id}.json", cr)
            return sanitize_metadata(cr, blocked_keys=ACK_BLOCKED_KEYS)

    def list_change_requests(self, portfolio_id: str, *, profile: str = "public_summary") -> list[dict[str, Any]]:
        root = self.change_requests_dir(portfolio_id, profile)
        if not root.exists():
            return []
        return [_read_json_default(path, default={}) for path in sorted(root.glob("att-trans-ack-cr-*.json"))]

    def _pack_findings(self, source: ImplementationDocument, *, require_verified: bool) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        checks: list[dict[str, Any]] = []
        checks.append(_check("transparency_zip_exists", bool(source.get("transparency_zip_sha256")), "Transparency ZIP exists."))
        checks.append(_check("transparency_verification_passed", source.get("transparency_verification_status") == "passed", "Transparency verification is passed."))
        checks.append(_check("transparency_event_semantics_passed", source.get("transparency_event_semantics_status") == "passed", "Transparency event semantics passed."))
        checks.append(_check("transparency_notice_semantics_passed", source.get("transparency_notice_semantics_status") == "passed", "Transparency notice semantics passed."))
        blockers = [item for item in checks if item["status"] == "failed" and (require_verified or item["check_id"] == "transparency_zip_exists")]
        warnings = [item for item in checks if item["status"] == "failed" and item not in blockers]
        return blockers, warnings, checks

    def _ensure_evidence_exportable(self, portfolio_id: str, evidence: ImplementationDocument, *, profile: str) -> None:
        if not evidence:
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence is missing.")
        if self.evidence_is_stale(portfolio_id, evidence, profile=profile):
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence is stale.")
        if evidence.get("status") != "current" or evidence.get("external_review_status") != "accepted":
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement Evidence is not current accepted evidence.")

    def _latest_accepted_response_id(self, portfolio_id: str, profile: str) -> str:
        for item in reversed(self.list_responses(portfolio_id, profile=profile)):
            if item.get("status") == "accepted" and item.get("verification_status") == "passed" and not item.get("stale"):
                return str(item.get("response_id") or "")
        return ""

    def _find_change_request(self, portfolio_id: str, response_id: str, *, profile: str) -> ImplementationDocument:
        for item in self.list_change_requests(portfolio_id, profile=profile):
            if item.get("response_id") == response_id:
                return sanitize_metadata(item, blocked_keys=ACK_BLOCKED_KEYS)
        return {}

    def _history_has_state_event(self, portfolio_id: str, profile: str, state: dict[str, str], event_type: str) -> bool:
        path = self.pack_history_path(portfolio_id, profile)
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") != event_type:
                continue
            summary = _as_document(event.get("summary"))
            if all(str(summary.get(key) or "") == str(value or "") for key, value in state.items()):
                return True
        return False

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: ImplementationDocument, *, now: str) -> None:
        path = self.pack_history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0
        event = sanitize_metadata({"event_id": f"att-trans-ack-history-{count + 1:06d}", "at": now, "type": event_type, "summary": summary}, blocked_keys=ACK_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")








def response_payload_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: (response or {}).get(key) for key in ACK_RESPONSE_HASH_FIELDS})


def response_record_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in {"integrity_hash", "imported_at"}})








def response_summary(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_id": response.get("response_id"),
        "external_response_id": response.get("external_response_id"),
        "status": response.get("status"),
        "verification_status": response.get("verification_status"),
        "stale": bool(response.get("stale")),
        "imported_at": response.get("imported_at"),
    }





def verify_response_document(response: dict[str, Any], pack: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    del now
    checks: list[dict[str, Any]] = []
    required = ["review_pack_id", "review_pack_source_hash", "transparency_zip_sha256", "transparency_manifest_hash", "transparency_feed_source_hash"]
    missing = [key for key in required if not response.get(key)]
    checks.append(_check("ack_response_required_source_binding", not missing, "Response source binding fields are present." if not missing else "Missing response source binding: " + ", ".join(missing)))
    status = str(response.get("review_status") or "")
    checks.append(_check("ack_response_status_allowed", status in ACK_ALLOWED_RESPONSE_STATUSES, "Response status is allowed."))
    source = _as_document(pack.get("source"))
    checks.append(_check("ack_response_pack_binding", response.get("review_pack_id") == pack.get("pack_id") and response.get("review_pack_source_hash") == pack.get("source_hash"), "Response binds to the acknowledgement pack."))
    checks.append(
        _check(
            "ack_response_transparency_binding",
            response.get("transparency_zip_sha256") == source.get("transparency_zip_sha256")
            and response.get("transparency_manifest_hash") == source.get("transparency_manifest_hash")
            and response.get("transparency_feed_source_hash") == source.get("transparency_feed_source_hash"),
            "Response binds to current Transparency package.",
        )
    )
    notice_ids = set(str(item) for item in source.get("notice_ids", []) if item)
    event_ids = set(str(item) for item in source.get("event_ids", []) if item)
    reviewed_notices = set(str(item) for item in response.get("reviewed_notice_ids", []) if item) if isinstance(response.get("reviewed_notice_ids"), list) else set()
    reviewed_events = set(str(item) for item in response.get("reviewed_event_ids", []) if item) if isinstance(response.get("reviewed_event_ids"), list) else set()
    checks.append(_check("ack_response_notice_subset", reviewed_notices.issubset(notice_ids), "Reviewed notices belong to pack."))
    checks.append(_check("ack_response_event_subset", reviewed_events.issubset(event_ids), "Reviewed events belong to pack."))
    warning_notices = set(str(item) for item in source.get("warning_notice_ids", []) if item)
    checks.append(_check("ack_response_warning_notices_reviewed", status != "accepted" or warning_notices.issubset(reviewed_notices), "Accepted response reviewed all warning notices."))
    concerns = _as_list(response.get("concerns"))
    checks.append(_check("ack_response_concerns_required", status == "accepted" or bool(concerns), "Needs changes/rejected response includes concerns."))
    expected_hash = response_payload_hash(response)
    checks.append(_check("ack_response_payload_hash", not response.get("response_hash") or response.get("response_hash") == expected_hash, "Response hash matches payload."))
    findings = _redaction_findings("response", json.dumps(response, ensure_ascii=False))
    checks.append({"scope": "response", "check_id": "ack_response_redaction_scan", "status": "failed" if findings else "passed", "severity": "blocking", "message": f"Found {len(findings)} sensitive issue(s)." if findings else "No sensitive values found."})
    blockers = [item for item in checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
    return sanitize_metadata(
        {
            "schema_version": ACK_SCHEMA_VERSION,
            "package_kind": "acknowledgement_response",
            "generated_at": now_iso(),
            "status": "failed" if blockers else "passed",
            "summary": {"review_status": status, "blocker_count": len(blockers)},
            "checks": checks,
            "blockers": blockers,
        },
        blocked_keys=ACK_BLOCKED_KEYS,
    )


def verification_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})


def redaction_summary(value: Any) -> dict[str, Any]:
    findings = _redaction_findings("payload", json.dumps(value, ensure_ascii=False, sort_keys=True))
    return {"status": "failed" if findings else "passed", "finding_count": len(findings)}


def _pack_id(portfolio_id: str, profile: str, source: ImplementationDocument) -> str:
    return "att-trans-ack-pack-" + stable_hash({"portfolio_id": portfolio_id, "profile": profile, "source": source})[:12]


def _evidence_id(portfolio_id: str, profile: str, source: ImplementationDocument) -> str:
    return "att-trans-ack-" + stable_hash({"portfolio_id": portfolio_id, "profile": profile, "source": source})[:12]


def _pack_data_documents(pack: ImplementationDocument, feed: ImplementationDocument) -> ImplementationDocument:
    source = _as_document(pack.get("source"))
    events = _as_list(feed.get("events"))
    notices = _as_list(feed.get("notices"))
    return sanitize_metadata(
        {
            "transparency-verification-summary.json": {"source_hash": pack.get("source_hash"), "status": source.get("transparency_verification_status"), "verification_hash": source.get("transparency_verification_hash"), "event_semantics": source.get("transparency_event_semantics_status"), "notice_semantics": source.get("transparency_notice_semantics_status")},
            "transparency-feed-summary.json": {"source_hash": pack.get("source_hash"), "feed_source_hash": source.get("transparency_feed_source_hash"), "event_count": len(events), "notice_count": len(notices)},
            "current-public-state-summary.json": {"source_hash": pack.get("source_hash"), "current_public_state_hash": source.get("current_public_state_hash"), "current_entry_id": source.get("current_entry_id"), "current_certificate_id": source.get("current_certificate_id")},
            "events-summary.json": {"source_hash": pack.get("source_hash"), "events": [{"event_id": item.get("event_id"), "event_type": item.get("event_type"), "severity": item.get("severity")} for item in events if isinstance(item, dict)]},
            "notices-summary.json": {"source_hash": pack.get("source_hash"), "notices": [{"notice_id": item.get("notice_id"), "notice_type": item.get("notice_type"), "severity": item.get("severity")} for item in notices if isinstance(item, dict)]},
            "package-fingerprints.json": {"source_hash": pack.get("source_hash"), **source},
        },
        blocked_keys=ACK_BLOCKED_KEYS,
    )


def _evidence_data_documents(evidence: ImplementationDocument) -> ImplementationDocument:
    source = _as_document(evidence.get("source"))
    public = _as_document(evidence.get("public_summary"))
    return {
        "response-binding-summary.json": {"source_hash": evidence.get("source_hash"), **source},
        "response-verification-summary.json": {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "status": source.get("response_verification_status"),
            "verification_hash": source.get("response_verification_hash"),
            "response_payload_hash": source.get("response_payload_hash"),
            "response_integrity_hash": source.get("response_integrity_hash"),
            "review_pack_id": source.get("review_pack_id"),
            "review_pack_source_hash": source.get("review_pack_source_hash"),
            "transparency_zip_sha256": source.get("transparency_zip_sha256"),
            "transparency_manifest_hash": source.get("transparency_manifest_hash"),
            "transparency_feed_source_hash": source.get("transparency_feed_source_hash"),
        },
        "original-response-binding-summary.json": {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "response_payload_hash": source.get("response_payload_hash"),
            "response_integrity_hash": source.get("response_integrity_hash"),
            "review_pack_id": source.get("response_review_pack_id"),
            "review_pack_source_hash": source.get("response_review_pack_source_hash"),
            "transparency_zip_sha256": source.get("transparency_zip_sha256"),
            "transparency_manifest_hash": source.get("transparency_manifest_hash"),
            "transparency_feed_source_hash": source.get("transparency_feed_source_hash"),
            "public_summary": public,
            "response_public_summary_hash": source.get("response_public_summary_hash"),
        },
        "public-summary.json": {"source_hash": evidence.get("source_hash"), "public_summary": public},
    }


def _response_schema(pack: ImplementationDocument) -> ImplementationDocument:
    return {"package_type": ACK_RESPONSE_PACKAGE_TYPE, "required": pack.get("response_requirements", {}).get("required_fields", []), "allowed_status": sorted(ACK_ALLOWED_RESPONSE_STATUSES)}


def _evidence_public_summary(response: ImplementationDocument) -> ImplementationDocument:
    payload = _as_document(response.get("response_payload"))
    reviewer = _as_document(payload.get("reviewer"))
    return {
        "reviewer_name": reviewer.get("name"),
        "reviewer_organization": reviewer.get("organization"),
        "reviewed_notice_count": len(payload.get("reviewed_notice_ids", []) if isinstance(payload.get("reviewed_notice_ids"), list) else []),
        "reviewed_event_count": len(payload.get("reviewed_event_ids", []) if isinstance(payload.get("reviewed_event_ids"), list) else []),
        "accepted_at": payload.get("submitted_at"),
    }


def _response_payload_from_bytes(raw: bytes) -> ImplementationDocument:
    try:
        if raw[:4] == b"PK\x03\x04":
            import io

            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                if "acknowledgement-response.json" in archive.namelist():
                    raw = archive.read("acknowledgement-response.json")
                elif "review-response.json" in archive.namelist():
                    raw = archive.read("review-response.json")
                else:
                    json_entries = [name for name in archive.namelist() if name.endswith(".json")]
                    if not json_entries:
                        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response ZIP does not contain a JSON response.")
                    raw = archive.read(json_entries[0])
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Acknowledgement response could not be parsed: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response must be a JSON object.")
    return sanitize_metadata(value, blocked_keys=ACK_BLOCKED_KEYS)


def _require_response_source_binding(response: ImplementationDocument) -> None:
    required = ["review_pack_id", "review_pack_source_hash", "transparency_zip_sha256", "transparency_manifest_hash", "transparency_feed_source_hash"]
    missing = [key for key in required if not response.get(key)]
    if missing:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response is missing required source binding fields: " + ", ".join(missing))
    if response.get("package_type") != ACK_RESPONSE_PACKAGE_TYPE:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response package_type is invalid.")
    if response.get("review_status") not in ACK_ALLOWED_RESPONSE_STATUSES:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response review_status is invalid.")


def _response_stale(response: ImplementationDocument, pack: ImplementationDocument) -> bool:
    source = _as_document(pack.get("source"))
    return not (
        response.get("review_pack_id") == pack.get("pack_id")
        and response.get("review_pack_source_hash") == pack.get("source_hash")
        and response.get("transparency_zip_sha256") == source.get("transparency_zip_sha256")
        and response.get("transparency_manifest_hash") == source.get("transparency_manifest_hash")
        and response.get("transparency_feed_source_hash") == source.get("transparency_feed_source_hash")
    )


def _change_request_actions(response: ImplementationDocument) -> list[ImplementationDocument]:
    concerns = _as_list(response.get("concerns"))
    actions: list[dict[str, Any]] = []
    for concern in concerns:
        if isinstance(concern, dict):
            actions.append({"action_type": "review_transparency_acknowledgement_concern", "notice_id": concern.get("notice_id"), "event_id": concern.get("event_id"), "severity": concern.get("severity") or "warning"})
    return actions or [{"action_type": "review_transparency_acknowledgement_response", "severity": "warning"}]


def _payload_bytes(payload: ImplementationDocument, *, max_size: int) -> bytes:
    if payload.get("content_base64"):
        try:
            raw = base64.b64decode(str(payload.get("content_base64")), validate=True)
        except Exception as exc:
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Invalid content_base64: {exc}") from exc
    elif payload.get("data_base64"):
        try:
            raw = base64.b64decode(str(payload.get("data_base64")), validate=True)
        except Exception as exc:
            raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Invalid data_base64: {exc}") from exc
    elif payload.get("content"):
        raw = json.dumps(payload.get("content"), ensure_ascii=False).encode("utf-8") if isinstance(payload.get("content"), dict) else str(payload.get("content")).encode("utf-8")
    else:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response content is required.")
    if len(raw) > max_size:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError("Acknowledgement response content is too large.")
    return raw


def _pack_readme(pack: ImplementationDocument) -> str:
    return "\n".join(["MusicForge Transparency Acknowledgement Pack", "", f"Portfolio ID: {pack.get('portfolio_id')}", f"Pack ID: {pack.get('pack_id')}", f"Status: {pack.get('status')}", ""])


def _evidence_readme(evidence: ImplementationDocument) -> str:
    return "\n".join(["MusicForge Transparency Acknowledgement Evidence", "", f"Portfolio ID: {evidence.get('portfolio_id')}", f"Acknowledgement ID: {evidence.get('acknowledgement_id')}", f"Status: {evidence.get('status')}", ""])


def _check(check_id: str, ok: bool, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message if ok else message.replace(" is ", " is not ")}


def _state_tuple(doc: ImplementationDocument) -> dict[str, str]:
    return {"source_hash": str(doc.get("source_hash") or ""), "integrity_hash": str(doc.get("integrity_hash") or "")}


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except Exception:
        return dict(default or {})
    return sanitize_metadata(_as_document(value), blocked_keys=ACK_BLOCKED_KEYS)


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    return write_json(path, sanitize_metadata(payload, blocked_keys=ACK_BLOCKED_KEYS))


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    rel = path.relative_to(root).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            entries.append((path, path.relative_to(root).as_posix()))
    return entries


def _write_zip(zip_path: Path, export_dir: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(export_dir):
                archive.write(resolved, entry)
        tmp_path.replace(zip_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_within(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if root_resolved != target_resolved and root_resolved not in target_resolved.parents:
        raise ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError(f"Path escapes acknowledgement root: {target}")


def _safe_profile(value: str) -> str:
    return _safe_id(value or "public_summary")


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "item")).strip(".-")
    return text or "item"


def _next_id(root: Path, prefix: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    max_seen = 0
    for path in root.glob(f"{prefix}-*.json"):
        try:
            max_seen = max(max_seen, int(path.stem.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{max_seen + 1:06d}"


def _redaction_findings(scope: str, text: str) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    sanitized = sanitize_sensitive_text(text)
    if sanitized != text:
        findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    lowered = text.lower()
    blocked_markers = (
        "github" + "key",
        "x-access-" + "token",
        "api_" + "key",
        "access_" + "token",
        "tok" + "en",
        "sec" + "ret",
        "pass" + "word",
        "source_" + "path",
        "local_" + "path",
        "file_" + "path",
    )
    for marker in blocked_markers:
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    return findings
