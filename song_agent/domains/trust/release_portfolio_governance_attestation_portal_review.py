# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

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
from song_agent.domains.trust.attestation_store_ports import AttestationPortalStorePort as AttestationPortalStorePort
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_contracts import portal_summary as portal_summary, portal_verification_summary as portal_verification_summary
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal as verify_release_portfolio_governance_attestation_portal, write_release_portfolio_governance_attestation_portal_verification_report as write_release_portfolio_governance_attestation_portal_verification_report
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_review_contracts import PORTAL_REVIEW_BLOCKED_KEYS as PORTAL_REVIEW_BLOCKED_KEYS, PORTAL_REVIEW_MANIFEST_HASH_EXCLUDE_KEYS as PORTAL_REVIEW_MANIFEST_HASH_EXCLUDE_KEYS, PORTAL_REVIEW_PACK_HASH_EXCLUDE_KEYS as PORTAL_REVIEW_PACK_HASH_EXCLUDE_KEYS, PORTAL_REVIEW_PACK_PACKAGE_TYPE as PORTAL_REVIEW_PACK_PACKAGE_TYPE, PORTAL_REVIEW_RESPONSE_HASH_FIELDS as PORTAL_REVIEW_RESPONSE_HASH_FIELDS, PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE as PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE, response_integrity_hash as response_integrity_hash, response_payload_hash as response_payload_hash, response_summary as response_summary, review_manifest_hash as review_manifest_hash, review_pack_hash as review_pack_hash, review_pack_summary as review_pack_summary, verification_hash as verification_hash


PORTAL_REVIEW_SCHEMA_VERSION = 1








class ReleasePortfolioGovernanceAttestationPortalReviewError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationPortalReviewNotFoundError(ReleasePortfolioGovernanceAttestationPortalReviewError):
    pass


class ReleasePortfolioGovernanceAttestationPortalReviewStateError(ReleasePortfolioGovernanceAttestationPortalReviewError):
    pass


class ReleasePortfolioGovernanceAttestationPortalReviewStore:
    def __init__(self, *, portal_store: AttestationPortalStorePort) -> None:
        self.portal_store = portal_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        root = self.portal_store.attestation_store.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation-portal-review"
        if profile == "public_summary":
            return root
        return root / "profiles" / _safe_profile(profile)

    def pack_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "review-pack.json"

    def pack_history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "review-pack-history.jsonl"

    def pack_verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "review-pack-verification-report.json"

    def export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "review-pack-export"

    def pack_zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "governance-attestation-portal-review-pack.zip"

    def responses_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "responses"

    def response_path(self, portfolio_id: str, response_id: str, profile: str = "public_summary") -> Path:
        return self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}.json"

    def response_zip_path(self, portfolio_id: str, response_id: str, profile: str = "public_summary") -> Path:
        return self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}.zip"

    def response_verification_report_path(self, portfolio_id: str, response_id: str, profile: str = "public_summary") -> Path:
        return self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}-verification-report.json"

    def change_requests_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "change-request-drafts"

    def read_pack(self, portfolio_id: str, *, profile: str = "public_summary", default: DomainDocument | None = None) -> DomainDocument:
        return _read_json_default(self.pack_path(portfolio_id, profile), default=default)

    def refresh_pack(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            reviewer_instructions = str((payload or {}).get("reviewer_instructions") or "").strip()
            source = self.build_source(portfolio_id, profile=profile)
            blockers, warnings, checks = self._pack_findings(source)
            pack = {
                "schema_version": PORTAL_REVIEW_SCHEMA_VERSION,
                "package_type": PORTAL_REVIEW_PACK_PACKAGE_TYPE,
                "review_pack_id": _pack_id(portfolio_id, profile, source),
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "ready",
                "source": source,
                "source_hash": stable_hash(source),
                "reviewer_instructions": reviewer_instructions,
                "summary": _pack_summary(source, blockers, warnings),
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
            }
            pack["integrity_hash"] = review_pack_hash(pack)
            self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.pack_path(portfolio_id, profile), pack)
            self._append_history(portfolio_id, profile, "review_pack_refreshed", {"review_pack_id": pack["review_pack_id"], "source_hash": pack["source_hash"], "status": pack["status"]}, now=now)
            return sanitize_metadata(pack, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def build_source(self, portfolio_id: str, *, profile: str = "public_summary") -> DomainDocument:
        self.portal_store.attestation_store.portfolio_store.get_portfolio(portfolio_id)
        portal_zip = self.portal_store.zip_path(portfolio_id, profile)
        portal_verification = verify_release_portfolio_governance_attestation_portal(
            portal_zip,
            strict=True,
            require_current=True,
            require_registry=True,
            require_attestation=True,
        )
        write_release_portfolio_governance_attestation_portal_verification_report(
            portal_verification,
            self.portal_store.verification_report_path(portfolio_id, profile),
        )
        portal_report = self.portal_store.read_report(portfolio_id, profile=profile, default={})
        portal_source = _as_document(portal_report.get("source"))
        portal_manifest = _read_json_default(self.portal_store.export_dir(portfolio_id, profile) / "portal-manifest.json", default={})
        source = {
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "portal_zip_sha256": _sha256(portal_zip),
            "portal_zip_size_bytes": portal_zip.stat().st_size if portal_zip.exists() and portal_zip.is_file() else None,
            "portal_manifest_hash": portal_manifest.get("integrity_hash") or portal_verification.get("manifest_hash"),
            "portal_verification_hash": verification_hash(portal_verification),
            "portal_verification_status": portal_verification.get("status") or "missing",
            "portal_source_hash": portal_report.get("source_hash"),
            "registry_zip_sha256": portal_source.get("registry_zip_sha256"),
            "registry_manifest_hash": portal_source.get("registry_manifest_hash"),
            "registry_verification_hash": portal_source.get("registry_verification_hash"),
            "registry_verification_status": portal_source.get("registry_verification_status"),
            "registry_current_entry_id": portal_source.get("registry_current_entry_id"),
            "registry_current_entry_hash": portal_source.get("registry_current_entry_hash"),
            "current_certificate_id": portal_source.get("current_certificate_id"),
            "current_attestation_zip_sha256": portal_source.get("current_attestation_zip_sha256"),
            "current_attestation_manifest_hash": portal_source.get("current_attestation_manifest_hash"),
            "current_attestation_verification_hash": portal_source.get("current_attestation_verification_hash"),
            "current_attestation_verification_status": portal_source.get("current_attestation_verification_status") or portal_source.get("attestation_verification_status"),
            "evidence_vault_zip_sha256": portal_source.get("evidence_vault_zip_sha256"),
            "evidence_vault_manifest_hash": portal_source.get("evidence_vault_manifest_hash"),
            "evidence_vault_verification_hash": portal_source.get("evidence_vault_verification_hash"),
            "evidence_vault_deep_verification_status": portal_source.get("evidence_vault_deep_verification_status"),
            "final_board_signoff_hash": portal_source.get("final_board_signoff_hash"),
        }
        return sanitize_metadata(source, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def pack_is_stale(self, portfolio_id: str, pack: DomainDocument | None = None, *, profile: str = "public_summary") -> bool:
        data = _document_or(pack, self.read_pack(portfolio_id, profile=profile, default={}))
        if not data:
            return False
        try:
            source = self.build_source(portfolio_id, profile=str(data.get("attestation_profile") or profile))
        except Exception:
            return True
        return stable_hash(source) != str(data.get("source_hash") or "")

    def export_pack(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            pack = self.read_pack(portfolio_id, profile=profile, default={}) or self.refresh_pack(portfolio_id, {"profile": profile}, now=now)
            if self.pack_is_stale(portfolio_id, pack, profile=profile):
                raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Pack source is stale. Refresh the pack before export.")
            if pack.get("status") == "failed":
                raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Pack has blockers and cannot be exported.")
            state = _state_tuple(pack)
            if self._history_has_state_event(portfolio_id, profile, state, "review_pack_exported"):
                raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Pack export already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            _write_json(export_dir / "review-pack.json", pack)
            data_docs = _pack_data_documents(pack)
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            (export_dir / "reviewer-guide.md").write_text(_reviewer_guide(pack), encoding="utf-8")
            form = _response_form(pack)
            _write_json(export_dir / "portal-review-form.json", form)
            (export_dir / "portal-review-form.md").write_text(_response_form_markdown(pack), encoding="utf-8")
            (export_dir / "README.txt").write_text(_pack_readme(pack), encoding="utf-8")
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "review-pack-manifest.json"]
            manifest = {
                "schema_version": PORTAL_REVIEW_SCHEMA_VERSION,
                "package_type": PORTAL_REVIEW_PACK_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Portal Review Pack", "version": __version__},
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "created_at": now,
                "review_pack": {"review_pack_id": pack.get("review_pack_id"), "integrity_hash": pack.get("integrity_hash"), "source_hash": pack.get("source_hash")},
                "source_hash": pack.get("source_hash"),
                "portal": _portal_binding(_as_document(pack.get("source"))),
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": redaction_summary({"pack": pack, "data": data_docs, "form": form}),
            }
            manifest["integrity_hash"] = review_manifest_hash(manifest)
            _write_json(export_dir / "review-pack-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "review_pack_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def build_pack_zip(self, portfolio_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            pack = self.read_pack(portfolio_id, profile=profile, default={})
            if not pack:
                pack = self.refresh_pack(portfolio_id, {"profile": profile}, now=now)
            if self.pack_is_stale(portfolio_id, pack, profile=profile):
                raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Pack source is stale. Refresh the pack before ZIP.")
            state = _state_tuple(pack)
            if self._history_has_state_event(portfolio_id, profile, state, "review_pack_zip_built"):
                raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Pack ZIP already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.pack_zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "review-pack-manifest.json").exists():
                self.export_pack(portfolio_id, {"profile": profile}, now=now)
            manifest = read_json(export_dir / "review-pack-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {
                "created_at": now,
                "filename": zip_path.name,
                "entry_count": len(entries),
                "entries": [entry for _path, entry in entries],
                "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries),
            }
            manifest["integrity_hash"] = review_manifest_hash(manifest)
            _write_json(export_dir / "review-pack-manifest.json", manifest)
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
            info = {"filename": zip_path.name, "path": zip_path.name, "sha256": _sha256(zip_path), "size_bytes": zip_path.stat().st_size, "created_at": now}
            self._append_history(portfolio_id, profile, "review_pack_zip_built", {**state, "zip_sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def import_response(self, portfolio_id: str, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
        with self.lock:
            now = now or now_iso()
            if "source_path" in payload:
                raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Response import only accepts uploaded content; source_path is not allowed.")
            profile = str(payload.get("profile") or "public_summary")
            pack = self.read_pack(portfolio_id, profile=profile, default={})
            if not pack:
                raise ReleasePortfolioGovernanceAttestationPortalReviewNotFoundError("Portal Review Pack does not exist.")
            response = self._decode_response_payload(payload)
            self._ensure_external_response_source_binding(response, pack)
            response.setdefault("schema_version", PORTAL_REVIEW_SCHEMA_VERSION)
            response.setdefault("package_type", PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE)
            response.setdefault("response_id", self._next_response_id(portfolio_id, profile))
            response.setdefault("portfolio_id", portfolio_id)
            response.setdefault("attestation_profile", profile)
            response.setdefault("imported_at", now)
            response["status"] = _response_status(response, pack)
            response["payload_hash"] = response_payload_hash(response)
            response["integrity_hash"] = response_integrity_hash(response)
            self.responses_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.response_path(portfolio_id, response["response_id"], profile), response)
            report = self.verify_response(portfolio_id, response["response_id"], profile=profile, now=now)
            result = {"response": response, "verification": report, "summary": response_summary(response)}
            return sanitize_metadata(result, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def _ensure_external_response_source_binding(self, response: ImplementationDocument, pack: ImplementationDocument) -> None:
        review_pack_id = str(response.get("review_pack_id") or "").strip()
        review_pack_source_hash = str(response.get("review_pack_source_hash") or "").strip()
        if not review_pack_id:
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Response must include review_pack_id from the exported Review Pack.")
        if not review_pack_source_hash:
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Response must include review_pack_source_hash from the exported Review Pack.")
        if review_pack_id != str(pack.get("review_pack_id") or ""):
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Response review_pack_id does not match the current Review Pack.")

    def build_response_zip(self, portfolio_id: str, response: DomainDocument, *, profile: str = "public_summary", now: str | None = None) -> Path:
        now = now or now_iso()
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        if not pack:
            raise ReleasePortfolioGovernanceAttestationPortalReviewNotFoundError("Portal Review Pack does not exist.")
        response = dict(response)
        response.setdefault("schema_version", PORTAL_REVIEW_SCHEMA_VERSION)
        response.setdefault("package_type", PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE)
        response.setdefault("response_id", self._next_response_id(portfolio_id, profile))
        response.setdefault("portfolio_id", portfolio_id)
        response.setdefault("attestation_profile", profile)
        response.setdefault("review_pack_id", pack.get("review_pack_id"))
        response.setdefault("review_pack_source_hash", pack.get("source_hash"))
        response.setdefault("reviewed_at", now)
        response["status"] = _response_status(response, pack)
        response["payload_hash"] = response_payload_hash(response)
        response["integrity_hash"] = response_integrity_hash(response)
        response_id = str(response["response_id"])
        work_dir = self.responses_dir(portfolio_id, profile) / f"{_safe_id(response_id)}-export"
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "data").mkdir(parents=True, exist_ok=True)
        _write_json(work_dir / "review-response.json", response)
        (work_dir / "review-response.md").write_text(_response_markdown(response), encoding="utf-8")
        _write_json(work_dir / "data" / "review-pack-source.json", {"source_hash": pack.get("source_hash"), "source": pack.get("source"), "review_pack_id": pack.get("review_pack_id")})
        _write_json(work_dir / "data" / "portal-binding-summary.json", _portal_binding(_as_document(pack.get("source"))))
        (work_dir / "README.txt").write_text("MusicForge Portal Review Response. Verify before import.\n", encoding="utf-8")
        files = [_file_record(work_dir, path) for path in sorted(work_dir.rglob("*")) if path.is_file() and path.name != "response-manifest.json"]
        manifest = {
            "schema_version": PORTAL_REVIEW_SCHEMA_VERSION,
            "package_type": PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE,
            "created_at": now,
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "response_id": response_id,
            "review_pack_id": pack.get("review_pack_id"),
            "review_pack_source_hash": pack.get("source_hash"),
            "payload_hash": response.get("payload_hash"),
            "source_hash": pack.get("source_hash"),
            "portal": _portal_binding(_as_document(pack.get("source"))),
            "files": sorted(files, key=lambda item: item["path"]),
            "zip": {},
        }
        manifest["integrity_hash"] = review_manifest_hash(manifest)
        _write_json(work_dir / "response-manifest.json", manifest)
        zip_path = self.response_zip_path(portfolio_id, response_id, profile)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(work_dir):
                archive.write(resolved, entry)
        return zip_path

    def list_responses(self, portfolio_id: str, *, profile: str = "public_summary") -> list[DomainDocument]:
        root = self.responses_dir(portfolio_id, profile)
        if not root.exists():
            return []
        rows: list[ImplementationDocument] = []
        for path in sorted(root.glob("aprr-*.json")):
            value = _read_json_default(path, default={})
            if value:
                rows.append(response_summary(value))
        return rows

    def get_response(self, portfolio_id: str, response_id: str, *, profile: str = "public_summary") -> DomainDocument:
        value = _read_json_default(self.response_path(portfolio_id, response_id, profile), default={})
        if not value:
            raise ReleasePortfolioGovernanceAttestationPortalReviewNotFoundError("Portal Review Response not found.")
        return sanitize_metadata(value, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def verify_response(self, portfolio_id: str, response_id: str, *, profile: str = "public_summary", now: str | None = None) -> DomainDocument:
        from song_agent.domains.trust.release_portfolio_governance_attestation_portal_review_verifier import verify_response_document

        response = self.get_response(portfolio_id, response_id, profile=profile)
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        report = verify_response_document(response, pack, now=now)
        _write_json(self.response_verification_report_path(portfolio_id, response_id, profile), report)
        return sanitize_metadata(report, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def create_change_request(self, portfolio_id: str, response_id: str, payload: DomainDocument | None = None, *, profile: str = "public_summary", now: str | None = None) -> DomainDocument:
        now = now or now_iso()
        response = self.get_response(portfolio_id, response_id, profile=profile)
        pack = self.read_pack(portfolio_id, profile=profile, default={})
        if response.get("decision") not in {"needs_changes", "rejected"}:
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Only needs_changes or rejected responses can create a Change Request draft.")
        if response.get("review_pack_source_hash") != pack.get("source_hash") or response.get("status") == "stale":
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Response source is stale. Refresh review pack and import a current response.")
        report = self.verify_response(portfolio_id, response_id, profile=profile, now=now)
        if report.get("status") == "failed":
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Response verification failed.")
        existing = self._find_change_request_for_response(portfolio_id, response_id, profile)
        if existing:
            return sanitize_metadata({"change_request": existing, "existing": True}, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)
        root = self.change_requests_dir(portfolio_id, profile)
        root.mkdir(parents=True, exist_ok=True)
        change_request_id = f"apcr-{len(list(root.glob('apcr-*.json'))) + 1:06d}"
        request = {
            "schema_version": PORTAL_REVIEW_SCHEMA_VERSION,
            "change_request_id": change_request_id,
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "status": "draft",
            "created_at": now,
            "created_by": str((payload or {}).get("created_by") or response.get("reviewer", {}).get("name") or "external_reviewer"),
            "source_type": "portal_review_response",
            "source_response_id": response_id,
            "review_pack_source_hash": response.get("review_pack_source_hash"),
            "decision": response.get("decision"),
            "reason": str((payload or {}).get("reason") or response.get("notes") or "External portal review requested changes.")[:2000],
            "findings": _as_list(response.get("findings")),
        }
        request["integrity_hash"] = stable_hash({key: value for key, value in request.items() if key != "integrity_hash"})
        _write_json(root / f"{change_request_id}.json", request)
        return sanitize_metadata({"change_request": request, "existing": False}, blocked_keys=PORTAL_REVIEW_BLOCKED_KEYS)

    def _decode_response_payload(self, payload: ImplementationDocument) -> ImplementationDocument:
        if isinstance(payload.get("response"), dict):
            return dict(payload["response"])
        encoded = str(payload.get("content_base64") or payload.get("data_base64") or "")
        if not encoded:
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("Portal Review Response import requires content_base64.")
        try:
            data = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError("content_base64 is not valid base64.") from exc
        try:
            return _response_from_bytes(data)
        except Exception as exc:
            raise ReleasePortfolioGovernanceAttestationPortalReviewStateError(f"Portal Review Response payload could not be parsed: {exc}") from exc

    def _next_response_id(self, portfolio_id: str, profile: str) -> str:
        root = self.responses_dir(portfolio_id, profile)
        count = len(list(root.glob("aprr-*.json"))) if root.exists() else 0
        return f"aprr-{count + 1:06d}"

    def _find_change_request_for_response(self, portfolio_id: str, response_id: str, profile: str) -> ImplementationDocument:
        root = self.change_requests_dir(portfolio_id, profile)
        if not root.exists():
            return {}
        for path in sorted(root.glob("apcr-*.json")):
            value = _read_json_default(path, default={})
            if value.get("source_response_id") == response_id:
                return value
        return {}

    def _pack_findings(self, source: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument], list[ImplementationDocument]]:
        checks: list[ImplementationDocument] = []

        def add(check_id: str, ok: bool, message: str) -> None:
            checks.append({"check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message})

        add("portal_review_pack_portal_verified", source.get("portal_verification_status") == "passed", "Portal ZIP verification must be passed.")
        add("portal_review_pack_registry_verified", source.get("registry_verification_status") == "passed", "Registry evidence must be verified.")
        add("portal_review_pack_attestation_verified", source.get("current_attestation_verification_status") == "passed", "Public Attestation evidence must be verified.")
        add("portal_review_pack_current_entry", bool(source.get("registry_current_entry_id")), "Current registry entry is required.")
        blockers = [item for item in checks if item["status"] == "failed"]
        warnings: list[ImplementationDocument] = []
        return blockers, warnings, checks

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, payload: ImplementationDocument, *, now: str | None = None) -> None:
        path = self.pack_history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now or now_iso(), "event_type": event_type, **payload}, ensure_ascii=False, sort_keys=True) + "\n")

    def _history_has_state_event(self, portfolio_id: str, profile: str, state: dict[str, str], event_type: str) -> bool:
        path = self.pack_history_path(portfolio_id, profile)
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") == event_type and all(str(event.get(key) or "") == value for key, value in state.items()):
                return True
        return False





from song_agent.domains.trust import v142_rpgapr_readiness as _v142_rpgapr_readiness
from song_agent.domains.trust.v142_rpgapr_readiness import (
    review_pack_integrity_ok,
    _response_status,
    _has_unresolved_high_findings,
    _response_from_bytes,
    _pack_id,
    _pack_summary,
    _pack_data_documents,
    _response_schema,
    _response_form,
    _portal_binding,
    _reviewer_guide,
    _response_form_markdown,
    _pack_readme,
    _response_markdown,
    redaction_summary,
    _state_tuple,
    _file_record,
    _zip_entries,
    _read_json_default,
    _write_json,
    _sha256,
    _ensure_within,
    _safe_profile,
    _safe_id,
)

_v142_rpgapr_readiness.bind_globals(globals())
