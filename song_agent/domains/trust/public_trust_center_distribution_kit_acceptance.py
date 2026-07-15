from __future__ import annotations

import base64
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
from song_agent.domains.trust.public_trust_center_distribution_kit import DISTRIBUTION_KIT_BLOCKED_KEYS, PublicTrustCenterDistributionKitStore, distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package, write_public_trust_center_distribution_kit_verification_report
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import ACCEPTANCE_BLOCKED_KEYS, ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE, accepted_evidence_hash, accepted_evidence_manifest_hash, verification_hash


DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION = 1
ACCEPTANCE_RESPONSE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_response"
ACCEPTANCE_TEMPLATE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_template"


ACCEPTANCE_ALLOWED_RESULTS = {"accepted", "needs_changes", "rejected"}



RESPONSE_RECORD_HASH_EXCLUDE_KEYS = {"integrity_hash", "imported_at"}
RESPONSE_PAYLOAD_HASH_EXCLUDE_KEYS = {"response_hash", "payload_hash", "integrity_hash"}
MAX_RESPONSE_BYTES = 512 * 1024


class PublicTrustCenterDistributionKitAcceptanceError(ValueError):
    pass


class PublicTrustCenterDistributionKitAcceptanceNotFoundError(PublicTrustCenterDistributionKitAcceptanceError):
    pass


class PublicTrustCenterDistributionKitAcceptanceStateError(PublicTrustCenterDistributionKitAcceptanceError):
    pass


class PublicTrustCenterDistributionKitAcceptanceStore:
    def __init__(self, *, distribution_kit_store: PublicTrustCenterDistributionKitStore) -> None:
        self.distribution_kit_store = distribution_kit_store
        self.lock = threading.RLock()

    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.distribution_kit_store.root_dir(center_id) / "acceptance"

    def template_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "response-template.json"

    def responses_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "responses"

    def response_dir(self, center_id: str, response_id: str) -> Path:
        return self.responses_dir(center_id) / _safe_id(response_id)

    def response_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-state.json"

    def original_response_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "original-response.json"

    def response_verification_report_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-verification-report.json"

    def response_binding_summary_path(self, center_id: str, response_id: str) -> Path:
        return self.response_dir(center_id, response_id) / "response-binding-summary.json"

    def change_request_dir(self, center_id: str) -> Path:
        return self.root_dir(center_id) / "change-request-drafts"

    def accepted_evidence_root(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "accepted-evidence"

    def evidence_dir(self, center_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_root(center_id) / _safe_id(evidence_id)

    def evidence_report_path(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "evidence-report.json"

    def evidence_export_dir(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "export"

    def evidence_zip_path(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "accepted-evidence.zip"

    def evidence_verification_report_path(self, center_id: str, evidence_id: str) -> Path:
        return self.evidence_dir(center_id, evidence_id) / "accepted-evidence-verification-report.json"

    def read_response(self, center_id: str, response_id: str) -> dict[str, Any]:
        path = self.response_path(center_id, response_id)
        if not path.exists():
            raise PublicTrustCenterDistributionKitAcceptanceNotFoundError(f"Distribution Kit acceptance response not found: {response_id}")
        return _read_json_default(path, default={})

    def list_responses(self, center_id: str = "ptc-default") -> list[dict[str, Any]]:
        root = self.responses_dir(center_id)
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("*/response-state.json")):
            value = _read_json_default(path, default={})
            if value:
                rows.append(response_summary(value))
        return rows

    def read_evidence(self, center_id: str, evidence_id: str | None = None, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if evidence_id:
            return _read_json_default(self.evidence_report_path(center_id, evidence_id), default=default)
        latest = self._latest_evidence_id(center_id)
        return _read_json_default(self.evidence_report_path(center_id, latest), default=default) if latest else dict(default or {})

    def create_response_template(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            del payload
            now = now or now_iso()
            binding = self._current_kit_binding(center_id, require_verified=True)
            template = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "template_type": ACCEPTANCE_TEMPLATE_TYPE,
                "center_id": center_id,
                "template_id": "ptcdka-template-" + stable_hash({"center_id": center_id, "kit_binding": binding})[:12],
                "created_at": now,
                "kit_binding": binding,
                "required_verification": {
                    "strict": True,
                    "deep": True,
                    "require_current": True,
                    "require_delivery_readiness": True,
                    "require_anchor_registry_current": True,
                    "require_anchor_published": True,
                    "require_anchor_not_revoked": True,
                    "require_anchor_transparency_current": True,
                    "require_anchor_checkpoint": True,
                },
                "response_template": response_template(center_id, binding),
            }
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.template_path(center_id), template)
            return _sanitize(template)

    def import_response(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            _reject_path_payload(payload)
            raw = _payload_bytes(payload, max_size=MAX_RESPONSE_BYTES)
            response_payload = _response_payload_from_bytes(raw)
            _require_response_binding(response_payload)
            external_id = str(response_payload.get("response_id") or "").strip()
            response_id = _safe_id(external_id) if external_id else _next_response_id(self.responses_dir(center_id))
            if not external_id:
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response_id is required.")
            binding = self._current_kit_binding(center_id, require_verified=True)
            payload_hash = response_payload_hash(response_payload)
            if response_payload.get("response_hash") and str(response_payload.get("response_hash")) != payload_hash:
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response_hash does not match payload.")
            verification = verify_response_document(response_payload, binding)
            stale = _response_binding_stale(response_payload, binding)
            status = _response_state_status(str(response_payload.get("result") or ""), stale, verification)
            record = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_RESPONSE_TYPE,
                "response_id": response_id,
                "external_response_id": external_id,
                "center_id": center_id,
                "imported_at": now,
                "reviewed_at": response_payload.get("reviewed_at"),
                "result": response_payload.get("result"),
                "status": status,
                "review_mode": response_payload.get("review_mode"),
                "source_hash": stable_hash(binding),
                "response_payload_hash": payload_hash,
                "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
                "kit_binding_status": "stale" if stale else "current",
                "verification_status": verification.get("status"),
                "accepted_evidence_id": None,
                "warnings": [],
                "kit_binding": _binding_from_response(response_payload),
                "response_payload": response_payload,
                "verification": verification,
                "redaction_summary": redaction_summary(response_payload),
            }
            record["integrity_hash"] = response_record_hash(record)
            response_dir = self.response_dir(center_id, response_id)
            response_dir.mkdir(parents=True, exist_ok=True)
            _write_json(self.original_response_path(center_id, response_id), response_payload)
            _write_json(self.response_verification_report_path(center_id, response_id), verification)
            _write_json(self.response_binding_summary_path(center_id, response_id), _response_binding_summary(record, binding))
            _write_json(self.response_path(center_id, response_id), record)
            _append_jsonl(response_dir / "events.jsonl", {"event_type": "response_imported", "created_at": now, "response_id": response_id, "status": status})
            if verification.get("status") == "failed":
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response verification failed.")
            return {"response": _sanitize(record), "verification": verification}

    def verify_response(self, center_id: str, response_id: str, *, now: str | None = None) -> dict[str, Any]:
        del now
        record = self.read_response(center_id, response_id)
        payload = record.get("response_payload") if isinstance(record.get("response_payload"), dict) else {}
        binding = self._current_kit_binding(center_id, require_verified=True)
        return verify_response_document(payload, binding)

    def response_is_stale(self, center_id: str, response: dict[str, Any]) -> bool:
        payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else {}
        try:
            binding = self._current_kit_binding(center_id, require_verified=True)
        except Exception:
            return True
        return _response_binding_stale(payload, binding)

    def refresh_accepted_evidence(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            response_id = str(payload.get("response_id") or "").strip() or self._latest_accepted_response_id(center_id)
            if not response_id:
                raise PublicTrustCenterDistributionKitAcceptanceStateError("No accepted Distribution Kit response is available.")
            response = self.read_response(center_id, response_id)
            verification = self.verify_response(center_id, response_id, now=now)
            if response.get("result") != "accepted" or response.get("review_mode") != "external_manual" or verification.get("status") != "passed" or self.response_is_stale(center_id, response):
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Only current, external_manual, accepted responses with passed verification can create accepted evidence.")
            binding = self._current_kit_binding(center_id, require_verified=True)
            source = self._evidence_source(center_id, response, verification, binding)
            public_response = _public_response(response)
            evidence_id = "ptcdkae-" + stable_hash({"center_id": center_id, "source": source})[:12]
            evidence = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE,
                "evidence_id": evidence_id,
                "center_id": center_id,
                "response_id": response_id,
                "created_at": now,
                "updated_at": now,
                "status": "current",
                "result": "accepted",
                "review_mode": "external_manual",
                "reviewer_summary": public_response.get("reviewer", {}),
                "kit_binding": binding,
                "source": source,
                "source_hash": stable_hash(source),
                "public_response": public_response,
                "warnings": [],
            }
            evidence["integrity_hash"] = accepted_evidence_hash(evidence)
            evidence_dir = self.evidence_dir(center_id, evidence_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            _write_json(self.evidence_report_path(center_id, evidence_id), evidence)
            return _sanitize(evidence)

    def export_accepted_evidence(self, center_id: str, response_id: str | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            evidence = self.refresh_accepted_evidence(center_id, {"response_id": response_id} if response_id else {}, now=now)
            self._ensure_evidence_exportable(center_id, evidence)
            evidence_id = str(evidence.get("evidence_id") or "")
            export_dir = self.evidence_export_dir(center_id, evidence_id).resolve()
            root = self.evidence_dir(center_id, evidence_id).resolve()
            _ensure_within(root, export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            source = evidence.get("source") if isinstance(evidence.get("source"), dict) else {}
            response_id = str(source.get("response_id") or evidence.get("response_id") or "")
            docs = _evidence_documents(
                evidence,
                response_verification_report=_read_json_default(self.response_verification_report_path(center_id, response_id), default={}),
                response_binding_summary=_read_json_default(self.response_binding_summary_path(center_id, response_id), default={}),
            )
            for name, doc in docs.items():
                if name.endswith(".json"):
                    _write_json(export_dir / name, doc)
                else:
                    _write_text(export_dir / name, str(doc))
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if _is_file(path) and path.name != "evidence-manifest.json"]
            manifest = {
                "schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION,
                "package_type": ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Distribution Kit Accepted Evidence", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": evidence.get("source_hash"),
                "evidence": {"evidence_id": evidence_id, "integrity_hash": evidence.get("integrity_hash"), "source_hash": evidence.get("source_hash")},
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "redaction_summary": redaction_summary(docs),
            }
            manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
            _write_json(export_dir / "evidence-manifest.json", manifest)
            return _sanitize(manifest)

    def build_accepted_evidence_zip(self, center_id: str, response_id: str | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            evidence = self.refresh_accepted_evidence(center_id, {"response_id": response_id} if response_id else {}, now=now)
            evidence_id = str(evidence.get("evidence_id") or "")
            export_dir = self.evidence_export_dir(center_id, evidence_id).resolve()
            root = self.evidence_dir(center_id, evidence_id).resolve()
            zip_path = self.evidence_zip_path(center_id, evidence_id).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "evidence-manifest.json").exists():
                self.export_accepted_evidence(center_id, response_id, now=now)
            manifest = read_json(export_dir / "evidence-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
            _write_json(export_dir / "evidence-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            return {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "evidence_id": evidence_id}

    def verify_accepted_evidence_zip(self, center_id: str, evidence_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package, write_public_trust_center_distribution_kit_accepted_evidence_verification_report

        payload = payload or {}
        evidence_id = evidence_id or self._latest_evidence_id(center_id)
        if not evidence_id:
            raise PublicTrustCenterDistributionKitAcceptanceNotFoundError("Accepted evidence not found.")
        report = verify_public_trust_center_distribution_kit_accepted_evidence_package(
            self.evidence_zip_path(center_id, evidence_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", False)),
            distribution_kit_path=self.distribution_kit_store.zip_path(center_id) if bool(payload.get("use_distribution_kit", True)) else None,
        )
        write_public_trust_center_distribution_kit_accepted_evidence_verification_report(report, self.evidence_verification_report_path(center_id, evidence_id))
        return report

    def create_change_request_draft(self, center_id: str, response_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            response = self.read_response(center_id, response_id)
            verification = self.verify_response(center_id, response_id, now=now)
            if response.get("result") not in {"needs_changes", "rejected"} or verification.get("status") == "failed" or self.response_is_stale(center_id, response):
                raise PublicTrustCenterDistributionKitAcceptanceStateError("Only current verified needs_changes/rejected Distribution Kit responses can create draft follow-up.")
            existing = self._find_change_request(center_id, response_id)
            if existing:
                return existing
            cr_id = _next_change_request_id(self.change_request_dir(center_id))
            response_payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else {}
            draft = {
                "draft_id": cr_id,
                "source": "distribution_kit_acceptance_response",
                "center_id": center_id,
                "response_id": response_id,
                "status": "draft",
                "result": response.get("result"),
                "reason": "External receiver requested Distribution Kit acceptance follow-up.",
                "findings": response_payload.get("findings") if isinstance(response_payload.get("findings"), list) else [],
                "created_at": now,
                "payload": sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BLOCKED_KEYS),
            }
            self.change_request_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.change_request_dir(center_id) / f"{cr_id}.json", draft)
            return _sanitize(draft)

    def list_change_requests(self, center_id: str = "ptc-default") -> list[dict[str, Any]]:
        root = self.change_request_dir(center_id)
        if not root.exists():
            return []
        return [_read_json_default(path, default={}) for path in sorted(root.glob("ptcdkcr-*.json"))]

    def summary(self, center_id: str = "ptc-default") -> dict[str, Any]:
        evidence = self.read_evidence(center_id, default={})
        return {
            "center_id": center_id,
            "response_count": len(self.list_responses(center_id)),
            "accepted_evidence_status": evidence.get("status") or "missing",
            "accepted_evidence_id": evidence.get("evidence_id"),
        }

    def _current_kit_binding(self, center_id: str, *, require_verified: bool) -> dict[str, Any]:
        zip_path = self.distribution_kit_store.zip_path(center_id)
        if not zip_path.exists() or not zip_path.is_file():
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit ZIP is missing.")
        report = self.distribution_kit_store.read_report(center_id, default={})
        manifest = _read_zip_json(zip_path, "distribution-kit-manifest.json")
        verification = _read_json_default(self.distribution_kit_store.verification_report_path(center_id), default={})
        if not verification or verification.get("zip_sha256") != _sha256(zip_path) or verification.get("manifest_hash") != manifest.get("integrity_hash"):
            verification = verify_public_trust_center_distribution_kit_package(zip_path, strict=True, deep=True, require_current=True, require_delivery_readiness=False)
            write_public_trust_center_distribution_kit_verification_report(verification, self.distribution_kit_store.verification_report_path(center_id))
        if require_verified and verification.get("status") != "passed":
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit verification must be passed before acceptance.")
        return _sanitize(
            {
                "distribution_kit_zip_sha256": _sha256(zip_path),
                "distribution_kit_zip_size_bytes": zip_path.stat().st_size,
                "distribution_kit_manifest_hash": manifest.get("integrity_hash"),
                "distribution_kit_report_hash": report.get("integrity_hash"),
                "distribution_kit_source_hash": report.get("source_hash"),
                "distribution_kit_verification_report_hash": verification_hash(verification),
                "distribution_kit_verification_status": verification.get("status"),
                "ptc_zip_sha256": (report.get("source") if isinstance(report.get("source"), dict) else {}).get("ptc_zip_sha256"),
                "anchor_registry_zip_sha256": (report.get("source") if isinstance(report.get("source"), dict) else {}).get("anchor_registry_zip_sha256"),
                "anchor_transparency_zip_sha256": (report.get("source") if isinstance(report.get("source"), dict) else {}).get("anchor_transparency_zip_sha256"),
                "checkpoint_hash": (report.get("source") if isinstance(report.get("source"), dict) else {}).get("checkpoint_hash"),
            }
        )

    def _evidence_source(self, center_id: str, response: dict[str, Any], verification: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
        response_id = str(response.get("response_id") or "")
        binding_summary = _read_json_default(self.response_binding_summary_path(center_id, response_id), default={})
        payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else {}
        return _sanitize(
            {
                "center_id": center_id,
                "response_id": response_id,
                "response_payload_hash": response.get("response_payload_hash"),
                "raw_response_sha256": response.get("raw_response_sha256"),
                "response_integrity_hash": response.get("integrity_hash"),
                "response_verification_hash": verification_hash(verification),
                "response_verification_status": verification.get("status"),
                "response_public_summary_hash": stable_hash(_public_response(response)),
                "binding_summary_hash": stable_hash(binding_summary),
                "distribution_kit_verification_report_hash": binding.get("distribution_kit_verification_report_hash"),
                "distribution_kit_zip_sha256": binding.get("distribution_kit_zip_sha256"),
                "distribution_kit_manifest_hash": binding.get("distribution_kit_manifest_hash"),
                "distribution_kit_report_hash": binding.get("distribution_kit_report_hash"),
                "distribution_kit_source_hash": binding.get("distribution_kit_source_hash"),
                "external_response_id": response.get("external_response_id"),
                "reviewed_at": payload.get("reviewed_at"),
            }
        )

    def _ensure_evidence_exportable(self, center_id: str, evidence: dict[str, Any]) -> None:
        if not evidence or evidence.get("status") != "current" or evidence.get("result") != "accepted":
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Accepted evidence is not current accepted evidence.")
        source = evidence.get("source") if isinstance(evidence.get("source"), dict) else {}
        response_id = str(source.get("response_id") or evidence.get("response_id") or "")
        response = self.read_response(center_id, response_id)
        verification = self.verify_response(center_id, response_id)
        binding = self._current_kit_binding(center_id, require_verified=True)
        current = self._evidence_source(center_id, response, verification, binding)
        if stable_hash(current) != str(evidence.get("source_hash") or ""):
            raise PublicTrustCenterDistributionKitAcceptanceStateError("Accepted evidence is stale.")

    def _latest_accepted_response_id(self, center_id: str) -> str:
        for item in reversed(self.list_responses(center_id)):
            if item.get("result") == "accepted" and item.get("verification_status") == "passed" and item.get("kit_binding_status") == "current":
                return str(item.get("response_id") or "")
        return ""

    def _latest_evidence_id(self, center_id: str) -> str:
        root = self.accepted_evidence_root(center_id)
        if not root.exists():
            return ""
        candidates: list[tuple[float, str]] = []
        for path in root.glob("*/evidence-report.json"):
            try:
                candidates.append((path.stat().st_mtime, path.parent.name))
            except OSError:
                continue
        return sorted(candidates)[-1][1] if candidates else ""

    def _find_change_request(self, center_id: str, response_id: str) -> dict[str, Any]:
        for item in self.list_change_requests(center_id):
            if item.get("response_id") == response_id:
                return item
        return {}


def response_template(center_id: str, binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_type": ACCEPTANCE_RESPONSE_TYPE,
        "response_id": "",
        "center_id": center_id,
        "result": "accepted",
        "review_mode": "external_manual",
        "reviewer": {"name": "", "organization": "", "role": ""},
        "reviewed_at": "",
        "verification": {"status": "passed", "tool": "verify-public-trust-center-distribution-kit-package", "tool_version": __version__, "command": "", "report_hash": binding.get("distribution_kit_verification_report_hash"), "summary": {}},
        "kit_binding": dict(binding),
        "findings": [],
        "comments": "",
    }


def verify_response_document(response: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(_check("ptcdka_response_type", response.get("response_type") == ACCEPTANCE_RESPONSE_TYPE, "Response type is valid."))
    response_id = str(response.get("response_id") or "")
    checks.append(_check("ptcdka_response_id", bool(response_id) and _safe_id(response_id) == response_id, "Response id is safe."))
    result = str(response.get("result") or "")
    checks.append(_check("ptcdka_response_result", result in ACCEPTANCE_ALLOWED_RESULTS, "Response result is allowed."))
    checks.append(_check("ptcdka_response_review_mode", response.get("review_mode") == "external_manual", "Response review mode is external_manual."))
    required = [
        "distribution_kit_zip_sha256",
        "distribution_kit_zip_size_bytes",
        "distribution_kit_manifest_hash",
        "distribution_kit_report_hash",
        "distribution_kit_source_hash",
        "distribution_kit_verification_report_hash",
    ]
    kit_binding = response.get("kit_binding") if isinstance(response.get("kit_binding"), dict) else {}
    missing = [key for key in required if not kit_binding.get(key)]
    checks.append(_check("ptcdka_response_required_binding", not missing, "Response Kit binding fields are present." if not missing else "Response Kit binding is missing: " + ", ".join(missing)))
    binding_ok = all(kit_binding.get(key) == binding.get(key) for key in required)
    checks.append(_check("ptcdka_response_kit_binding_current", binding_ok, "Response Kit binding matches current Distribution Kit."))
    verification = response.get("verification") if isinstance(response.get("verification"), dict) else {}
    checks.append(_check("ptcdka_response_external_verification_passed", result != "accepted" or verification.get("status") == "passed", "Accepted response has passed external verification."))
    checks.append(_check("ptcdka_response_hash", not response.get("response_hash") or response.get("response_hash") == response_payload_hash(response), "Response hash matches payload."))
    findings = _redaction_findings("response", json.dumps(response, ensure_ascii=False, sort_keys=True))
    checks.append({"scope": "response", "check_id": "ptcdka_response_redaction_scan", "status": "failed" if findings else "passed", "severity": "blocking", "message": f"Found {len(findings)} sensitive value(s)." if findings else "No sensitive values found."})
    blockers = [item for item in checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
    return _sanitize({"schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION, "package_kind": "distribution_kit_acceptance_response", "generated_at": now_iso(), "status": "failed" if blockers else "passed", "summary": {"result": result, "blocker_count": len(blockers)}, "checks": checks, "blockers": blockers})


def response_payload_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in RESPONSE_PAYLOAD_HASH_EXCLUDE_KEYS})


def response_record_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in RESPONSE_RECORD_HASH_EXCLUDE_KEYS})











def response_summary(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_id": response.get("response_id"),
        "external_response_id": response.get("external_response_id"),
        "result": response.get("result"),
        "status": response.get("status"),
        "verification_status": response.get("verification_status"),
        "kit_binding_status": response.get("kit_binding_status"),
        "accepted_evidence_id": response.get("accepted_evidence_id"),
        "imported_at": response.get("imported_at"),
    }


def accepted_evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    data = evidence if isinstance(evidence, dict) else {}
    reviewer = data.get("reviewer_summary") if isinstance(data.get("reviewer_summary"), dict) else {}
    return {"status": data.get("status") or "missing", "result": data.get("result") or "missing", "evidence_id": data.get("evidence_id"), "response_id": data.get("response_id"), "reviewer_name": reviewer.get("name"), "reviewer_organization": reviewer.get("organization")}


def redaction_summary(value: Any) -> dict[str, Any]:
    findings = _redaction_findings("payload", json.dumps(value, ensure_ascii=False, sort_keys=True))
    return {"status": "failed" if findings else "passed", "finding_count": len(findings)}


def _evidence_documents(evidence: dict[str, Any], *, response_verification_report: dict[str, Any] | None = None, response_binding_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    source = evidence.get("source") if isinstance(evidence.get("source"), dict) else {}
    public = evidence.get("public_response") if isinstance(evidence.get("public_response"), dict) else {}
    binding = evidence.get("kit_binding") if isinstance(evidence.get("kit_binding"), dict) else {}
    response_verification_report = response_verification_report if isinstance(response_verification_report, dict) else {}
    response_binding_summary = response_binding_summary if isinstance(response_binding_summary, dict) else {}
    response_verification = {
        "source_hash": evidence.get("source_hash"),
        "response_id": source.get("response_id"),
        "status": source.get("response_verification_status"),
        "response_payload_hash": source.get("response_payload_hash"),
        "response_integrity_hash": source.get("response_integrity_hash"),
        "verification_hash": source.get("response_verification_hash"),
    }
    response_verification_report_summary = _sanitize(
        {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "status": response_verification_report.get("status"),
            "response_payload_hash": source.get("response_payload_hash"),
            "raw_response_sha256": source.get("raw_response_sha256"),
            "response_public_summary_hash": source.get("response_public_summary_hash"),
            "response_verification_hash": verification_hash(response_verification_report),
            "check_count": len(response_verification_report.get("checks") if isinstance(response_verification_report.get("checks"), list) else []),
            "blocker_count": len(response_verification_report.get("blockers") if isinstance(response_verification_report.get("blockers"), list) else []),
        }
    )
    response_binding_proof = _sanitize(
        {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "binding_summary_hash": stable_hash(response_binding_summary),
            "response_payload_hash": source.get("response_payload_hash"),
            "raw_response_sha256": source.get("raw_response_sha256"),
            "response_public_summary_hash": source.get("response_public_summary_hash"),
            "kit_binding_status": response_binding_summary.get("kit_binding_status") or response_binding_summary.get("status"),
            "response_binding": response_binding_summary.get("response_binding") if isinstance(response_binding_summary.get("response_binding"), dict) else {},
            "current_binding": response_binding_summary.get("current_binding") if isinstance(response_binding_summary.get("current_binding"), dict) else {},
        }
    )
    return {
        "evidence-report.json": evidence,
        "original-response-public.json": public,
        "original-response-binding-summary.json": {"source_hash": evidence.get("source_hash"), **source, "public_response": public, "response_public_summary_hash": source.get("response_public_summary_hash"), **binding},
        "response-verification-summary.json": response_verification,
        "response-verification-report-summary.json": response_verification_report_summary,
        "original-response-binding-proof.json": response_binding_proof,
        "distribution-kit-verification-summary.json": {"source_hash": evidence.get("source_hash"), **binding},
        "README.txt": _evidence_readme(evidence),
        "VERIFY.txt": _evidence_verify_text(),
    }


def _public_response(response: dict[str, Any]) -> dict[str, Any]:
    payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else response
    reviewer = payload.get("reviewer") if isinstance(payload.get("reviewer"), dict) else {}
    public_findings = []
    for item in payload.get("findings", []) if isinstance(payload.get("findings"), list) else []:
        if isinstance(item, dict):
            public_findings.append({"severity": item.get("severity"), "code": item.get("code"), "public_message": sanitize_sensitive_text(str(item.get("public_message") or item.get("message") or ""))[:500]})
    return _sanitize(
        {
            "response_id": payload.get("response_id"),
            "result": payload.get("result"),
            "review_mode": payload.get("review_mode"),
            "reviewed_at": payload.get("reviewed_at"),
            "reviewer": {"name": reviewer.get("name"), "organization": reviewer.get("organization"), "role": reviewer.get("role")},
            "verification_status": (payload.get("verification") if isinstance(payload.get("verification"), dict) else {}).get("status"),
            "comments_excerpt": sanitize_sensitive_text(str(payload.get("comments") or ""))[:500],
            "findings": public_findings,
        }
    )


def _response_binding_summary(record: dict[str, Any], current_binding: dict[str, Any]) -> dict[str, Any]:
    return _sanitize({"response_id": record.get("response_id"), "status": record.get("status"), "kit_binding_status": record.get("kit_binding_status"), "response_binding": record.get("kit_binding"), "current_binding": current_binding, "response_payload_hash": record.get("response_payload_hash"), "response_integrity_hash": record.get("integrity_hash")})


def _response_state_status(result: str, stale: bool, verification: dict[str, Any]) -> str:
    if verification.get("status") == "failed":
        return "invalid"
    prefix = result if result in ACCEPTANCE_ALLOWED_RESULTS else "invalid"
    if prefix == "invalid":
        return "invalid"
    return prefix + ("_stale" if stale else "_current")


def _response_binding_stale(response: dict[str, Any], binding: dict[str, Any]) -> bool:
    response_binding = response.get("kit_binding") if isinstance(response.get("kit_binding"), dict) else {}
    keys = ["distribution_kit_zip_sha256", "distribution_kit_zip_size_bytes", "distribution_kit_manifest_hash", "distribution_kit_report_hash", "distribution_kit_source_hash", "distribution_kit_verification_report_hash"]
    return any(response_binding.get(key) != binding.get(key) for key in keys)


def _binding_from_response(response: dict[str, Any]) -> dict[str, Any]:
    return dict(response.get("kit_binding") if isinstance(response.get("kit_binding"), dict) else {})


def _require_response_binding(response: dict[str, Any]) -> None:
    if response.get("response_type") != ACCEPTANCE_RESPONSE_TYPE:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response_type is invalid.")
    required = ["distribution_kit_zip_sha256", "distribution_kit_zip_size_bytes", "distribution_kit_manifest_hash", "distribution_kit_report_hash", "distribution_kit_source_hash", "distribution_kit_verification_report_hash"]
    binding = response.get("kit_binding") if isinstance(response.get("kit_binding"), dict) else {}
    missing = [key for key in required if not binding.get(key)]
    if missing:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response is missing required Kit binding fields: " + ", ".join(missing))
    if response.get("result") not in ACCEPTANCE_ALLOWED_RESULTS:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response result is invalid.")
    if response.get("review_mode") != "external_manual":
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response review_mode must be external_manual.")


def _reject_path_payload(payload: dict[str, Any]) -> None:
    if any(payload.get(key) for key in ("source_path", "local_path", "file_path")):
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance import only accepts uploaded content; source_path/local_path/file_path are not allowed.")


def _payload_bytes(payload: dict[str, Any], *, max_size: int) -> bytes:
    if payload.get("content_base64"):
        try:
            raw = base64.b64decode(str(payload.get("content_base64")), validate=True)
        except Exception as exc:
            raise PublicTrustCenterDistributionKitAcceptanceStateError(f"Invalid content_base64: {exc}") from exc
    elif payload.get("data_base64"):
        try:
            raw = base64.b64decode(str(payload.get("data_base64")), validate=True)
        except Exception as exc:
            raise PublicTrustCenterDistributionKitAcceptanceStateError(f"Invalid data_base64: {exc}") from exc
    elif isinstance(payload.get("response"), dict):
        raw = json.dumps(payload.get("response"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    elif isinstance(payload.get("content"), dict):
        raw = json.dumps(payload.get("content"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    elif payload.get("content"):
        raw = str(payload.get("content")).encode("utf-8")
    else:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response content is required.")
    if len(raw) > max_size:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response content is too large.")
    return raw


def _response_payload_from_bytes(raw: bytes) -> dict[str, Any]:
    try:
        if raw[:4] == b"PK\x03\x04":
            import io

            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                names = archive.namelist()
                candidate = "acceptance-response.json" if "acceptance-response.json" in names else next((name for name in names if name.endswith(".json")), "")
                if not candidate:
                    raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response ZIP does not contain a JSON response.")
                raw = archive.read(candidate)
        value = json.loads(raw.decode("utf-8"))
    except PublicTrustCenterDistributionKitAcceptanceStateError:
        raise
    except Exception as exc:
        raise PublicTrustCenterDistributionKitAcceptanceStateError(f"Distribution Kit acceptance response could not be parsed: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response must be a JSON object.")
    return _sanitize(value)


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = json.loads(_read_text(path))
    except Exception:
        return dict(default or {})
    return _sanitize(value if isinstance(value, dict) else dict(default or {}))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(path, json.dumps(_sanitize(payload), ensure_ascii=False, indent=2) + "\n")
    return path


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        handle.write(text)


def _read_text(path: Path) -> str:
    with open(_fs_path(path), "r", encoding="utf-8") as handle:
        return handle.read()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if _is_file(path)]


def _is_file(path: Path) -> bool:
    try:
        return os.path.isfile(_fs_path(path))
    except OSError:
        return False


def _write_zip(zip_path: Path, export_dir: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(export_dir):
                archive.write(_fs_path(resolved), entry)
        os.replace(_fs_path(tmp_path), _fs_path(zip_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _sha256(path: Path) -> str | None:
    try:
        if not os.path.isfile(_fs_path(path)):
            return None
    except OSError:
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence_readme(evidence: dict[str, Any]) -> str:
    return sanitize_sensitive_text("\n".join(["MusicForge Distribution Kit Accepted Evidence", "", f"Center ID: {evidence.get('center_id')}", f"Evidence ID: {evidence.get('evidence_id')}", f"Status: {evidence.get('status')}", ""]))


def _evidence_verify_text() -> str:
    return "Verify this evidence:\npython -m song_agent.cli verify-public-trust-center-distribution-kit-accepted-evidence-package public-trust-center-distribution-kit-accepted-evidence.zip --strict --json\n"


def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Resolved path escapes Distribution Kit Acceptance root.")


def _fs_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "item")).strip(".-")
    return text or "item"


def _next_response_id(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    return f"ptcdkar-{len([path for path in root.iterdir() if path.is_dir()]) + 1:06d}"


def _next_change_request_id(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    return f"ptcdkcr-{len(list(root.glob('ptcdkcr-*.json'))) + 1:06d}"


def _check(check_id: str, ok: bool, message: str) -> dict[str, Any]:
    return {"scope": "response", "check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message}


def _redaction_findings(scope: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    sanitized = sanitize_sensitive_text(text)
    if sanitized != text:
        findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "local_path", "message": "Local path pattern found."})
    lowered = text.lower()
    for marker in ("github" + "key", "x-access-" + "token", "api_" + "key", "access_" + "token", "source_" + "path", "local_" + "path", "file_" + "path"):
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    return findings


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=ACCEPTANCE_BLOCKED_KEYS)
