from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

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
from song_agent.domains.trust.public_trust_center_distribution_kit import distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance import ACCEPTANCE_BLOCKED_KEYS as ACCEPTANCE_BLOCKED_KEYS, PublicTrustCenterDistributionKitAcceptanceError as PublicTrustCenterDistributionKitAcceptanceError, PublicTrustCenterDistributionKitAcceptanceStore as PublicTrustCenterDistributionKitAcceptanceStore, accepted_evidence_hash as accepted_evidence_hash, accepted_evidence_summary as accepted_evidence_summary, verification_hash as verification_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package as verify_public_trust_center_distribution_kit_accepted_evidence_package, write_public_trust_center_distribution_kit_accepted_evidence_verification_report as write_public_trust_center_distribution_kit_accepted_evidence_verification_report
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_acceptance_board_contracts import ACCEPTANCE_BOARD_BLOCKED_KEYS as ACCEPTANCE_BOARD_BLOCKED_KEYS, ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE as ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE, ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_PACKAGE_TYPE as ACCEPTANCE_BOARD_PACKAGE_TYPE, ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE, ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS as ACCEPTANCE_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS, ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE as ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE, SIGNOFF_ARCHIVE_ENTRIES as SIGNOFF_ARCHIVE_ENTRIES, acceptance_board_conflict_hash as acceptance_board_conflict_hash, acceptance_board_manifest_hash as acceptance_board_manifest_hash, acceptance_board_policy_hash as acceptance_board_policy_hash, acceptance_board_report_hash as acceptance_board_report_hash, acceptance_board_signoff_archive_hash as acceptance_board_signoff_archive_hash, acceptance_board_signoff_hash as acceptance_board_signoff_hash, acceptance_board_verification_hash as acceptance_board_verification_hash, sidecar_hash as sidecar_hash


ACCEPTANCE_BOARD_SCHEMA_VERSION = 1



ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_policy"

ACCEPTANCE_BOARD_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_change_request"






ACCEPTANCE_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}



DEFAULT_POLICY_ID = "ptcab-policy-default"



class PublicTrustCenterAcceptanceBoardError(ValueError):
    pass


class PublicTrustCenterAcceptanceBoardNotFoundError(PublicTrustCenterAcceptanceBoardError):
    pass


class PublicTrustCenterAcceptanceBoardStateError(PublicTrustCenterAcceptanceBoardError):
    pass


class PublicTrustCenterAcceptanceBoardStore:
    def __init__(self, *, acceptance_store: PublicTrustCenterDistributionKitAcceptanceStore) -> None:
        self.acceptance_store = acceptance_store
        self.distribution_kit_store = acceptance_store.distribution_kit_store
        self.lock = threading.RLock()

    def root_dir(self, center_id: str = "ptc-default") -> Path:
        return self.distribution_kit_store.root_dir(center_id).parent / "acceptance-board"

    def policy_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "board-policy.json"

    def report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "board-report.json"

    def conflict_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "conflict-report.json"

    def signoff_draft_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "board-signoff-draft.json"

    def events_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "events.jsonl"

    def export_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "export"

    def zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "public-trust-center-acceptance-board.zip"

    def verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "acceptance-board-verification-report.json"

    def signoff_dir(self, center_id: str = "ptc-default") -> Path:
        return self.root_dir(center_id) / "signoff"

    def signoff_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-signoff.json"

    def signoff_history_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-signoff-history.jsonl"

    def change_requests_dir(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-change-requests"

    def change_request_path(self, center_id: str, change_request_id: str) -> Path:
        return self.change_requests_dir(center_id) / f"{_safe_id(change_request_id)}.json"

    def signoff_archive_dir(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "archive"

    def signoff_archive_zip_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "public-trust-center-acceptance-board-signoff-archive.zip"

    def signoff_archive_verification_report_path(self, center_id: str = "ptc-default") -> Path:
        return self.signoff_dir(center_id) / "board-signoff-archive-verification-report.json"

    def read_policy(self, center_id: str = "ptc-default") -> dict[str, Any]:
        policy = _read_json_default(self.policy_path(center_id), default={})
        if policy:
            return policy
        return _default_policy(center_id, now_iso())

    def save_policy(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(center_id, "change Acceptance Board policy")
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            current = self.read_policy(center_id)
            requirements = _normalize_requirements(payload.get("requirements") if isinstance(payload.get("requirements"), dict) else payload)
            policy = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE,
                "policy_id": str(payload.get("policy_id") or current.get("policy_id") or DEFAULT_POLICY_ID),
                "center_id": center_id,
                "created_at": current.get("created_at") or now,
                "updated_at": now,
                "status": "active",
                "requirements": requirements,
                "role_rules": _role_rules(requirements),
            }
            policy["integrity_hash"] = acceptance_board_policy_hash(policy)
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.policy_path(center_id), policy)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_policy_saved", "created_at": now, "policy_hash": policy["integrity_hash"]})
            return _sanitize(policy)

    def read_report(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.report_path(center_id), default=default)

    def read_conflict_report(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.conflict_report_path(center_id), default=default)

    def refresh_report(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(center_id, "refresh Acceptance Board report")
            now = now or now_iso()
            payload = payload or {}
            if payload.get("policy"):
                self.save_policy(center_id, payload.get("policy") if isinstance(payload.get("policy"), dict) else {}, now=now)
            policy = self.read_policy(center_id)
            source, participants, response_index, evidence_index, response_proofs, evidence_summaries = self._build_source(center_id, policy)
            checks, conflicts = _evaluate_board(policy, participants)
            blockers = [item for item in checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
            warnings = [item for item in checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
            readiness = _readiness(policy, participants, blockers, conflicts)
            summary = _board_summary(policy, participants, checks, conflicts)
            source_hash = stable_hash(source)
            report = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "readiness": readiness,
                "policy": {"policy_id": policy.get("policy_id"), "policy_hash": policy.get("integrity_hash")},
                "source": source,
                "source_hash": source_hash,
                "summary": summary,
                "participants": participants,
                "checks": checks,
                "warnings": warnings,
            }
            report["integrity_hash"] = acceptance_board_report_hash(report)
            conflict_report = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE,
                "center_id": center_id,
                "created_at": now,
                "source_hash": source_hash,
                "status": "failed" if any(item.get("severity") == "blocking" for item in conflicts) else "passed",
                "conflicts": conflicts,
            }
            conflict_report["integrity_hash"] = acceptance_board_conflict_hash(conflict_report)
            self.root_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.report_path(center_id), report)
            _write_json(self.conflict_report_path(center_id), conflict_report)
            self._write_cached_sidecars(center_id, source_hash, response_index, evidence_index, response_proofs, evidence_summaries)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_refreshed", "created_at": now, "source_hash": source_hash, "readiness": readiness})
            return _sanitize(report)

    def export_board(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(center_id, "export Acceptance Board")
            now = now or now_iso()
            del payload
            report = self.read_report(center_id, default={})
            self._ensure_exportable(center_id, report)
            source_hash = str(report.get("source_hash") or "")
            policy = self.read_policy(center_id)
            conflict = self.read_conflict_report(center_id, default={})
            sidecars = self._sidecars_for_export(center_id, source_hash)
            export_dir = self.export_dir(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), export_dir)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            (export_dir / "evidence").mkdir(parents=True, exist_ok=True)
            (export_dir / "response-proofs").mkdir(parents=True, exist_ok=True)
            docs: dict[str, Any] = {
                "board-report.json": report,
                "board-policy.json": policy,
                "conflict-report.json": conflict,
                "board-summary.json": sidecars["board_summary"],
                "accepted-evidence-index.json": sidecars["accepted_evidence_index"],
                "response-index.json": sidecars["response_index"],
                "quorum-evidence.json": sidecars["quorum_evidence"],
                "README.txt": _readme(report),
                "VERIFY.txt": _verify_text(),
            }
            for name, doc in docs.items():
                if name.endswith(".json"):
                    _write_json(export_dir / name, doc)
                else:
                    _write_text(export_dir / name, str(doc))
            for item in sidecars["evidence_summaries"]:
                _write_json(export_dir / "evidence" / f"{_safe_id(str(item.get('evidence_id') or 'evidence'))}-summary.json", item)
            for proof in sidecars["response_proofs"]:
                response_id = _safe_id(str(proof.get("response_id") or "response"))
                _write_json(export_dir / "response-proofs" / f"{response_id}-binding-proof.json", proof.get("binding_proof") if isinstance(proof.get("binding_proof"), dict) else {})
                _write_json(export_dir / "response-proofs" / f"{response_id}-verification-summary.json", proof.get("verification_summary") if isinstance(proof.get("verification_summary"), dict) else {})
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if _is_file(path) and path.name != "acceptance-board-manifest.json"]
            manifest = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Acceptance Board", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": source_hash,
                "board_report": {"integrity_hash": report.get("integrity_hash"), "source_hash": source_hash},
                "policy": {"integrity_hash": policy.get("integrity_hash")},
                "conflict_report": {"integrity_hash": conflict.get("integrity_hash"), "source_hash": source_hash},
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "redaction_summary": redaction_summary(docs),
            }
            manifest["integrity_hash"] = acceptance_board_manifest_hash(manifest)
            _write_json(export_dir / "acceptance-board-manifest.json", manifest)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_exported", "created_at": now, "source_hash": source_hash, "manifest_hash": manifest["integrity_hash"]})
            return _sanitize(manifest)

    def build_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(center_id, "build Acceptance Board ZIP")
            now = now or now_iso()
            del payload
            report = self.read_report(center_id, default={})
            self._ensure_exportable(center_id, report)
            export_dir = self.export_dir(center_id).resolve()
            manifest = _read_json_default(export_dir / "acceptance-board-manifest.json", default={})
            if manifest.get("source_hash") != report.get("source_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board export is stale. Re-export before ZIP.")
            zip_path = self.zip_path(center_id).resolve()
            _ensure_within(self.root_dir(center_id).resolve(), zip_path)
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = acceptance_board_manifest_hash(manifest)
            _write_json(export_dir / "acceptance-board-manifest.json", manifest)
            _write_zip(zip_path, export_dir)
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries)}
            _append_jsonl(self.events_path(center_id), {"event_type": "board_zip_built", "created_at": now, "source_hash": report.get("source_hash"), "zip_sha256": info["sha256"]})
            return _sanitize(info)

    def verify_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package, write_public_trust_center_acceptance_board_verification_report

        payload = payload or {}
        report = verify_public_trust_center_acceptance_board_package(
            self.zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_ready=bool(payload.get("require_ready", False)),
            require_quorum=bool(payload.get("require_quorum", False)),
            require_no_conflicts=bool(payload.get("require_no_conflicts", False)),
            min_accepted_count=int(payload.get("min_accepted_count") or 0),
            min_accepted_organizations=int(payload.get("min_accepted_organizations") or 0),
            required_roles=[str(item) for item in payload.get("required_roles", [])] if isinstance(payload.get("required_roles"), list) else [],
            distribution_kit_path=self.distribution_kit_store.zip_path(center_id) if bool(payload.get("use_distribution_kit", True)) else None,
            accepted_evidence_dir=self.acceptance_store.accepted_evidence_root(center_id) if bool(payload.get("use_accepted_evidence", True)) else None,
        )
        write_public_trust_center_acceptance_board_verification_report(report, self.verification_report_path(center_id))
        return report

    def create_signoff_draft(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(center_id, "create Acceptance Board signoff draft")
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            report = self.read_report(center_id, default={})
            if not report:
                report = self.refresh_report(center_id, now=now)
            draft = {
                "draft_id": "ptcab-signoff-draft-000001",
                "center_id": center_id,
                "created_at": now,
                "status": "draft",
                "board_report_hash": report.get("integrity_hash"),
                "board_source_hash": report.get("source_hash"),
                "readiness": report.get("readiness"),
                "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {},
                "payload": payload,
            }
            _write_json(self.signoff_draft_path(center_id), draft)
            _append_jsonl(self.events_path(center_id), {"event_type": "board_signoff_draft_created", "created_at": now, "source_hash": report.get("source_hash")})
            return _sanitize(draft)

    def read_signoff(self, center_id: str = "ptc-default", *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.signoff_path(center_id), default=default)

    def signoff(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            self._ensure_unsigned(center_id, "sign Acceptance Board")
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            self._ensure_board_package_current(center_id)
            policy = self.read_policy(center_id)
            requirements = policy.get("requirements") if isinstance(policy.get("requirements"), dict) else {}
            verification = self.verify_zip(
                center_id,
                {
                    "strict": True,
                    "require_ready": True,
                    "require_quorum": True,
                    "require_no_conflicts": True,
                    "min_accepted_count": int(requirements.get("min_accepted_count") or 0),
                    "min_accepted_organizations": int(requirements.get("min_accepted_organizations") or 0),
                    "required_roles": requirements.get("required_roles") if isinstance(requirements.get("required_roles"), list) else [],
                    "use_distribution_kit": True,
                    "use_accepted_evidence": True,
                },
            )
            if verification.get("status") != "passed":
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board verification must pass before signoff.")
            report = self.read_report(center_id, default={})
            if report.get("readiness") != "ready" or report.get("status") != "passed":
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board must be ready before signoff.")
            source = self._signoff_source(center_id, verification)
            signoff_sequence = 1 + len([item for item in self._history_events(center_id) if item.get("event_type") == "board_signoff_signed"])
            signoff = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_SIGNOFF_PACKAGE_TYPE,
                "signoff_id": "ptcabs-" + stable_hash({"center_id": center_id, "source": source, "sequence": signoff_sequence})[:12],
                "signoff_sequence": signoff_sequence,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "signed",
                "signed_by": str(payload.get("signed_by") or "MusicForge Operator")[:120],
                "reason": sanitize_sensitive_text(str(payload.get("reason") or "Acceptance Board ready for public release.")[:1000]),
                "source": source,
                "source_hash": stable_hash(source),
                "board": source.get("board"),
                "verification": source.get("verification"),
                "quorum": source.get("quorum"),
                "accepted_evidence": source.get("accepted_evidence"),
                "distribution_kit": source.get("distribution_kit"),
                "warnings": [],
            }
            signoff["integrity_hash"] = acceptance_board_signoff_hash(signoff)
            self.signoff_dir(center_id).mkdir(parents=True, exist_ok=True)
            _write_json(self.signoff_path(center_id), signoff)
            self._append_signoff_history(center_id, {"event_type": "board_signoff_signed", "created_at": now, "signoff_hash": signoff["integrity_hash"], "source_hash": signoff["source_hash"]})
            _append_jsonl(self.events_path(center_id), {"event_type": "board_signoff_signed", "created_at": now, "signoff_hash": signoff["integrity_hash"], "source_hash": signoff["source_hash"]})
            return _sanitize(signoff)

    def create_change_request(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            reason = sanitize_sensitive_text(str(payload.get("reason") or "").strip())
            if len(reason) < 12:
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request reason must be at least 12 characters.")
            change_request_id = _next_change_request_id(self.change_requests_dir(center_id))
            current_signoff = self.read_signoff(center_id, default={})
            request = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_CHANGE_REQUEST_PACKAGE_TYPE,
                "change_request_id": change_request_id,
                "center_id": center_id,
                "created_at": now,
                "updated_at": now,
                "status": "draft",
                "reason": reason[:1000],
                "requested_by": str(payload.get("requested_by") or "MusicForge Operator")[:120],
                "target_signoff_hash": current_signoff.get("integrity_hash"),
                "applied_at": None,
                "applied_signoff_hash": None,
            }
            request["integrity_hash"] = acceptance_board_change_request_hash(request)
            _write_json(self.change_request_path(center_id, change_request_id), request)
            self._append_signoff_history(center_id, {"event_type": "board_change_request_created", "created_at": now, "change_request_id": change_request_id, "target_signoff_hash": request.get("target_signoff_hash")})
            return _sanitize(request)

    def approve_change_request(self, center_id: str, change_request_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            request = self._read_change_request(center_id, change_request_id)
            self._ensure_change_request_integrity(request)
            if request.get("status") not in {"draft", "submitted"}:
                raise PublicTrustCenterAcceptanceBoardStateError("Only draft/submitted Acceptance Board Change Requests can be approved.")
            request.update(
                {
                    "updated_at": now,
                    "status": "approved",
                    "approved_by": str(payload.get("approved_by") or "MusicForge Operator")[:120],
                    "approval_reason": sanitize_sensitive_text(str(payload.get("approval_reason") or payload.get("reason") or "Approved Acceptance Board signoff reset.")[:1000]),
                }
            )
            request["integrity_hash"] = acceptance_board_change_request_hash(request)
            _write_json(self.change_request_path(center_id, change_request_id), request)
            self._append_signoff_history(center_id, {"event_type": "board_change_request_approved", "created_at": now, "change_request_id": change_request_id})
            return _sanitize(request)

    def reset_signoff(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = sanitize_metadata(payload or {}, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
            change_request_id = str(payload.get("change_request_id") or "").strip()
            if not change_request_id:
                raise PublicTrustCenterAcceptanceBoardStateError("Approved Acceptance Board Change Request is required to reset signoff.")
            signoff = self.read_signoff(center_id, default={})
            if not signoff:
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff is missing.")
            self._ensure_signoff_integrity(signoff)
            request = self._read_change_request(center_id, change_request_id)
            self._ensure_change_request_integrity(request)
            if request.get("status") != "approved":
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request must be approved before reset.")
            if request.get("applied_at") or request.get("applied_signoff_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request has already been applied.")
            target_hash = request.get("target_signoff_hash")
            if target_hash and target_hash != signoff.get("integrity_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request does not target the current signoff.")
            request.update({"updated_at": now, "status": "applied", "applied_at": now, "applied_signoff_hash": signoff.get("integrity_hash")})
            request["integrity_hash"] = acceptance_board_change_request_hash(request)
            _write_json(self.change_request_path(center_id, change_request_id), request)
            reset_record = {
                "event_type": "board_signoff_reset",
                "created_at": now,
                "change_request_id": change_request_id,
                "signoff_hash": signoff.get("integrity_hash"),
                "reset_reason": sanitize_sensitive_text(str(payload.get("reason") or request.get("reason") or "")[:1000]),
                "reset_hash": stable_hash({"signoff_hash": signoff.get("integrity_hash"), "change_request_id": change_request_id, "request_hash": request.get("integrity_hash")}),
            }
            self._append_signoff_history(center_id, reset_record)
            try:
                self.signoff_path(center_id).unlink()
            except FileNotFoundError:
                pass
            _append_jsonl(self.events_path(center_id), reset_record)
            return {"status": "reset", "center_id": center_id, "change_request": _sanitize(request), "previous_signoff_hash": signoff.get("integrity_hash"), "reset_hash": reset_record["reset_hash"]}

    def export_signoff_archive(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            signoff = self.read_signoff(center_id, default={})
            self._ensure_signoff_current(center_id, signoff)
            self._ensure_archive_not_exported(center_id, str(signoff.get("integrity_hash") or ""))
            archive_dir = self.signoff_archive_dir(center_id).resolve()
            _ensure_within(self.signoff_dir(center_id).resolve(), archive_dir)
            if archive_dir.exists():
                shutil.rmtree(archive_dir)
            archive_dir.mkdir(parents=True, exist_ok=True)
            docs = self._signoff_archive_documents(center_id, signoff, now)
            for name, doc in docs.items():
                if name.endswith(".json"):
                    _write_json(archive_dir / name, doc if isinstance(doc, dict) else {})
                else:
                    _write_text(archive_dir / name, str(doc))
            files = [_file_record(archive_dir, path) for path in sorted(archive_dir.rglob("*")) if _is_file(path) and path.name != "board-signoff-archive-manifest.json"]
            manifest = {
                "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
                "package_type": ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Trust Center Acceptance Board Signoff Archive", "version": __version__},
                "center_id": center_id,
                "created_at": now,
                "source_hash": signoff.get("source_hash"),
                "signoff_hash": signoff.get("integrity_hash"),
                "files": sorted(files, key=lambda item: str(item.get("path") or "")),
                "zip": {},
                "redaction_summary": redaction_summary(docs),
            }
            manifest["integrity_hash"] = acceptance_board_signoff_archive_hash(manifest)
            _write_json(archive_dir / "board-signoff-archive-manifest.json", manifest)
            self._append_signoff_history(center_id, {"event_type": "board_signoff_archive_exported", "created_at": now, "signoff_hash": signoff.get("integrity_hash"), "manifest_hash": manifest["integrity_hash"]})
            return _sanitize(manifest)

    def build_signoff_archive_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            del payload
            signoff = self.read_signoff(center_id, default={})
            self._ensure_signoff_current(center_id, signoff)
            signoff_hash = str(signoff.get("integrity_hash") or "")
            self._ensure_archive_not_zipped(center_id, signoff_hash)
            archive_dir = self.signoff_archive_dir(center_id).resolve()
            manifest_path = archive_dir / "board-signoff-archive-manifest.json"
            manifest = _read_json_default(manifest_path, default={})
            if manifest.get("signoff_hash") != signoff_hash or manifest.get("source_hash") != signoff.get("source_hash"):
                raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff archive export is stale. Re-export before ZIP.")
            zip_path = self.signoff_archive_zip_path(center_id).resolve()
            _ensure_within(self.signoff_dir(center_id).resolve(), zip_path)
            entries = _zip_entries(archive_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(os.stat(_fs_path(path)).st_size for path, _entry in entries)}
            manifest["integrity_hash"] = acceptance_board_signoff_archive_hash(manifest)
            _write_json(manifest_path, manifest)
            _write_zip(zip_path, archive_dir)
            info = {"created_at": now, "filename": zip_path.name, "size_bytes": os.stat(_fs_path(zip_path)).st_size, "sha256": _sha256(zip_path), "entry_count": len(entries), "signoff_hash": signoff_hash}
            self._append_signoff_history(center_id, {"event_type": "board_signoff_archive_zip_built", "created_at": now, "signoff_hash": signoff_hash, "zip_sha256": info["sha256"]})
            return _sanitize(info)

    def verify_signoff_archive_zip(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from song_agent.domains.trust.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package, write_public_trust_center_acceptance_board_signoff_archive_verification_report

        payload = payload or {}
        report = verify_public_trust_center_acceptance_board_signoff_archive_package(
            self.signoff_archive_zip_path(center_id),
            strict=bool(payload.get("strict", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_current=bool(payload.get("require_current", True)),
            require_ready=bool(payload.get("require_ready", True)),
            board_zip_path=self.zip_path(center_id) if bool(payload.get("use_board_zip", True)) else None,
            board_verification_report_path=self.verification_report_path(center_id) if bool(payload.get("use_board_verification", True)) else None,
            distribution_kit_path=self.distribution_kit_store.zip_path(center_id) if bool(payload.get("use_distribution_kit", True)) else None,
            accepted_evidence_dir=self.acceptance_store.accepted_evidence_root(center_id) if bool(payload.get("use_accepted_evidence", True)) else None,
        )
        write_public_trust_center_acceptance_board_signoff_archive_verification_report(report, self.signoff_archive_verification_report_path(center_id))
        return report

    def summary(self, center_id: str = "ptc-default") -> dict[str, Any]:
        report = self.read_report(center_id, default={})
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        signoff = self.read_signoff(center_id, default={})
        return {"center_id": center_id, "readiness": report.get("readiness") or "missing", "status": report.get("status") or "missing", "signoff_status": signoff.get("status") or "unsigned", **summary}

    def _build_source(self, center_id: str, policy: ImplementationDocument) -> tuple[ImplementationDocument, list[ImplementationDocument], ImplementationDocument, ImplementationDocument, list[ImplementationDocument], list[ImplementationDocument]]:
        distribution_kit = _distribution_kit_state(self.distribution_kit_store, center_id)
        response_rows: list[dict[str, Any]] = []
        participants: list[dict[str, Any]] = []
        evidence_rows: list[dict[str, Any]] = []
        response_proofs: list[dict[str, Any]] = []
        evidence_summaries: list[dict[str, Any]] = []
        evidence_by_response = self._evidence_by_response(center_id)
        for item in self.acceptance_store.list_responses(center_id):
            response_id = str(item.get("response_id") or "")
            if not response_id:
                continue
            try:
                response = self.acceptance_store.read_response(center_id, response_id)
            except PublicTrustCenterDistributionKitAcceptanceError:
                continue
            public_response = _public_response_from_record(response)
            reviewer = public_response.get("reviewer") if isinstance(public_response.get("reviewer"), dict) else {}
            response_stale = self.acceptance_store.response_is_stale(center_id, response)
            verification = _read_json_default(self.acceptance_store.response_verification_report_path(center_id, response_id), default={})
            binding = _read_json_default(self.acceptance_store.response_binding_summary_path(center_id, response_id), default={})
            evidence = evidence_by_response.get(response_id, {})
            evidence_id = str(evidence.get("evidence_id") or "")
            evidence_current = False
            evidence_verification_status = "missing"
            evidence_verification_hash = None
            evidence_zip_sha = None
            if evidence_id:
                try:
                    self.acceptance_store._ensure_evidence_exportable(center_id, evidence)  # noqa: SLF001 - internal evidence freshness guard.
                    evidence_current = True
                except Exception:
                    evidence_current = False
                verification_report = _read_json_default(self.acceptance_store.evidence_verification_report_path(center_id, evidence_id), default={})
                if not verification_report or verification_report.get("zip_sha256") != _sha256(self.acceptance_store.evidence_zip_path(center_id, evidence_id)):
                    verification_report = verify_public_trust_center_distribution_kit_accepted_evidence_package(
                        self.acceptance_store.evidence_zip_path(center_id, evidence_id),
                        strict=True,
                        require_current=True,
                        distribution_kit_path=self.distribution_kit_store.zip_path(center_id),
                    )
                    write_public_trust_center_distribution_kit_accepted_evidence_verification_report(verification_report, self.acceptance_store.evidence_verification_report_path(center_id, evidence_id))
                evidence_verification_status = str(verification_report.get("status") or "missing")
                evidence_verification_hash = verification_hash(verification_report)
                evidence_zip_sha = verification_report.get("zip_sha256")
                evidence_rows.append(
                    {
                        "evidence_id": evidence_id,
                        "response_id": response_id,
                        "evidence_integrity_hash": evidence.get("integrity_hash"),
                        "evidence_source_hash": evidence.get("source_hash"),
                        "verification_status": evidence_verification_status,
                        "verification_report_hash": evidence_verification_hash,
                        "zip_sha256": evidence_zip_sha,
                        "current": evidence_current,
                    }
                )
                evidence_summaries.append(
                    {
                        "source_hash": evidence.get("source_hash"),
                        "evidence_id": evidence_id,
                        "response_id": response_id,
                        "summary": accepted_evidence_summary(evidence),
                        "evidence_integrity_hash": evidence.get("integrity_hash"),
                        "verification_status": evidence_verification_status,
                        "verification_report_hash": evidence_verification_hash,
                        "zip_sha256": evidence_zip_sha,
                    }
                )
            response_row = {
                "response_id": response_id,
                "result": response.get("result"),
                "review_mode": response.get("review_mode"),
                "status": response.get("status"),
                "response_payload_hash": response.get("response_payload_hash"),
                "raw_response_sha256": response.get("raw_response_sha256"),
                "binding_summary_hash": stable_hash(binding),
                "verification_hash": verification_hash(verification),
                "public_response_hash": stable_hash(public_response),
                "verification_status": response.get("verification_status"),
                "kit_binding_status": response.get("kit_binding_status"),
                "current": not response_stale,
            }
            response_rows.append(response_row)
            response_proofs.append(
                {
                    "response_id": response_id,
                    "binding_proof": {
                        "source_hash": None,
                        "response_id": response_id,
                        "binding_summary_hash": stable_hash(binding),
                        "response_payload_hash": response.get("response_payload_hash"),
                        "raw_response_sha256": response.get("raw_response_sha256"),
                        "response_public_summary_hash": stable_hash(public_response),
                        "public_response": public_response,
                        "kit_binding_status": response.get("kit_binding_status"),
                        "response_binding": binding.get("response_binding") if isinstance(binding.get("response_binding"), dict) else {},
                        "current_binding": binding.get("current_binding") if isinstance(binding.get("current_binding"), dict) else {},
                    },
                    "verification_summary": {
                        "source_hash": None,
                        "response_id": response_id,
                        "status": verification.get("status"),
                        "response_payload_hash": response.get("response_payload_hash"),
                        "raw_response_sha256": response.get("raw_response_sha256"),
                        "response_public_summary_hash": stable_hash(public_response),
                        "response_verification_hash": verification_hash(verification),
                        "check_count": len(verification.get("checks") if isinstance(verification.get("checks"), list) else []),
                        "blocker_count": len(verification.get("blockers") if isinstance(verification.get("blockers"), list) else []),
                    },
                }
            )
            current = bool(response.get("result") == "accepted" and response.get("review_mode") == "external_manual" and not response_stale and evidence_current and evidence_verification_status == "passed" and response.get("verification_status") == "passed")
            participant = {
                "response_id": response_id,
                "evidence_id": evidence_id or None,
                "result": response.get("result"),
                "review_mode": response.get("review_mode"),
                "reviewer_name": reviewer.get("name"),
                "organization": reviewer.get("organization"),
                "role": reviewer.get("role"),
                "current": not response_stale,
                "evidence_current": evidence_current,
                "evidence_verification_status": evidence_verification_status,
                "counts_for_quorum": current,
                "critical_findings": _critical_findings(response),
                "warnings": _participant_warnings(response, response_stale, evidence_id, evidence_current, evidence_verification_status),
            }
            participants.append(participant)
        source = {
            "center_id": center_id,
            "distribution_kit": distribution_kit,
            "policy_hash": policy.get("integrity_hash"),
            "responses": response_rows,
            "accepted_evidence": evidence_rows,
        }
        return source, participants, _response_index(source, response_rows), _accepted_evidence_index(source, evidence_rows), response_proofs, evidence_summaries

    def _evidence_by_response(self, center_id: str) -> dict[str, ImplementationDocument]:
        root = self.acceptance_store.accepted_evidence_root(center_id)
        rows: dict[str, dict[str, Any]] = {}
        if not root.exists():
            return rows
        for path in sorted(root.glob("*/evidence-report.json")):
            evidence = _read_json_default(path, default={})
            response_id = str(evidence.get("response_id") or "")
            if response_id:
                rows[response_id] = evidence
        return rows

    def _ensure_exportable(self, center_id: str, report: ImplementationDocument) -> None:
        if not report:
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report is missing. Refresh before export.")
        policy = self.read_policy(center_id)
        current_source, _participants, _response_index, _evidence_index, _proofs, _summaries = self._build_source(center_id, policy)
        if stable_hash(current_source) != report.get("source_hash"):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report is stale. Refresh before export.")
        if report.get("integrity_hash") != acceptance_board_report_hash(report):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report integrity failed.")

    def _ensure_unsigned(self, center_id: str, action: str) -> None:
        signoff = self.read_signoff(center_id, default={})
        if signoff.get("status") == "signed":
            raise PublicTrustCenterAcceptanceBoardStateError(f"Acceptance Board is signed. Reset signoff with an approved Change Request before attempting to {action}.")

    def _ensure_board_package_current(self, center_id: str) -> None:
        report = self.read_report(center_id, default={})
        self._ensure_exportable(center_id, report)
        manifest = _read_json_default(self.export_dir(center_id) / "acceptance-board-manifest.json", default={})
        if manifest.get("source_hash") != report.get("source_hash") or manifest.get("integrity_hash") != acceptance_board_manifest_hash(manifest):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board export is stale. Re-export before signoff.")
        zip_path = self.zip_path(center_id)
        if not zip_path.exists() or not zip_path.is_file():
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board ZIP is missing. Build ZIP before signoff.")
        zip_manifest = _read_zip_json(zip_path, "acceptance-board-manifest.json")
        if zip_manifest.get("integrity_hash") != manifest.get("integrity_hash"):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board ZIP manifest does not match current export.")

    def _signoff_source(self, center_id: str, verification: ImplementationDocument) -> ImplementationDocument:
        board_zip = self.zip_path(center_id)
        board_manifest = _read_zip_json(board_zip, "acceptance-board-manifest.json")
        report = self.read_report(center_id, default={})
        policy = self.read_policy(center_id)
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        participants = [item for item in (report.get("participants") if isinstance(report.get("participants"), list) else []) if isinstance(item, dict)]
        counted = [item for item in participants if item.get("counts_for_quorum")]
        accepted_rows = []
        for row in (report.get("source") if isinstance(report.get("source"), dict) else {}).get("accepted_evidence", []):
            if isinstance(row, dict) and any(item.get("evidence_id") == row.get("evidence_id") for item in counted):
                accepted_rows.append(row)
        return _sanitize(
            {
                "center_id": center_id,
                "board": {
                    "zip_sha256": _sha256(board_zip),
                    "zip_size_bytes": board_zip.stat().st_size if board_zip.exists() else None,
                    "manifest_hash": board_manifest.get("integrity_hash"),
                    "report_hash": report.get("integrity_hash"),
                    "source_hash": report.get("source_hash"),
                    "policy_hash": policy.get("integrity_hash"),
                    "readiness": report.get("readiness"),
                    "status": report.get("status"),
                },
                "verification": {
                    "status": verification.get("status"),
                    "verification_report_hash": acceptance_board_verification_hash(verification),
                    "zip_sha256": verification.get("zip_sha256"),
                    "zip_size_bytes": verification.get("zip_size_bytes"),
                    "manifest_hash": verification.get("manifest_hash"),
                    "blocker_count": len(verification.get("blockers") if isinstance(verification.get("blockers"), list) else []),
                },
                "quorum": {
                    "requirements": policy.get("requirements") if isinstance(policy.get("requirements"), dict) else {},
                    "summary": summary,
                    "participant_count": len(counted),
                    "participants": [
                        {
                            "response_id": item.get("response_id"),
                            "evidence_id": item.get("evidence_id"),
                            "organization": item.get("organization"),
                            "role": item.get("role"),
                            "reviewer_name": item.get("reviewer_name"),
                        }
                        for item in counted
                    ],
                },
                "accepted_evidence": sorted(accepted_rows, key=lambda item: str(item.get("evidence_id") or "")),
                "distribution_kit": (report.get("source") if isinstance(report.get("source"), dict) else {}).get("distribution_kit") if isinstance((report.get("source") if isinstance(report.get("source"), dict) else {}).get("distribution_kit"), dict) else {},
            }
        )

    def _ensure_signoff_integrity(self, signoff: ImplementationDocument) -> None:
        if not signoff:
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff is missing.")
        if signoff.get("integrity_hash") != acceptance_board_signoff_hash(signoff):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff integrity failed.")
        if signoff.get("source_hash") != stable_hash(signoff.get("source") if isinstance(signoff.get("source"), dict) else {}):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff source hash failed.")

    def _ensure_signoff_current(self, center_id: str, signoff: ImplementationDocument) -> None:
        self._ensure_signoff_integrity(signoff)
        current_verification = _read_json_default(self.verification_report_path(center_id), default={})
        source = self._signoff_source(center_id, current_verification)
        if stable_hash(source) != signoff.get("source_hash"):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff source is stale. Reset signoff before archiving.")

    def _append_signoff_history(self, center_id: str, payload: ImplementationDocument) -> None:
        _append_jsonl(self.signoff_history_path(center_id), payload)

    def _history_events(self, center_id: str) -> list[ImplementationDocument]:
        path = self.signoff_history_path(center_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            for line in _read_text(path).splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    events.append(_sanitize(item))
        except OSError:
            return []
        return events

    def _history_has_event(self, center_id: str, event_type: str, signoff_hash: str) -> bool:
        return any(item.get("event_type") == event_type and item.get("signoff_hash") == signoff_hash for item in self._history_events(center_id))

    def _ensure_archive_not_exported(self, center_id: str, signoff_hash: str) -> None:
        if self._history_has_event(center_id, "board_signoff_archive_exported", signoff_hash):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff archive was already exported for this signoff. Reset signoff before rebuilding archive.")

    def _ensure_archive_not_zipped(self, center_id: str, signoff_hash: str) -> None:
        if self._history_has_event(center_id, "board_signoff_archive_zip_built", signoff_hash):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board signoff archive ZIP was already built for this signoff. Reset signoff before rebuilding archive ZIP.")

    def _read_change_request(self, center_id: str, change_request_id: str) -> ImplementationDocument:
        request = _read_json_default(self.change_request_path(center_id, change_request_id), default={})
        if not request:
            raise PublicTrustCenterAcceptanceBoardNotFoundError(f"Acceptance Board Change Request not found: {change_request_id}")
        return request

    def _ensure_change_request_integrity(self, request: ImplementationDocument) -> None:
        if request.get("integrity_hash") != acceptance_board_change_request_hash(request):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board Change Request integrity failed.")

    def _signoff_archive_documents(self, center_id: str, signoff: ImplementationDocument, now: str) -> ImplementationDocument:
        source = signoff.get("source") if isinstance(signoff.get("source"), dict) else {}
        verification = _read_json_default(self.verification_report_path(center_id), default={})
        board_fingerprint = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "source_hash": signoff.get("source_hash"),
            "board": source.get("board") if isinstance(source.get("board"), dict) else {},
            "verification": source.get("verification") if isinstance(source.get("verification"), dict) else {},
        }
        board_fingerprint["integrity_hash"] = sidecar_hash(board_fingerprint)
        verification_summary = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "source_hash": signoff.get("source_hash"),
            "status": verification.get("status"),
            "verification_report_hash": acceptance_board_verification_hash(verification),
            "zip_sha256": verification.get("zip_sha256"),
            "zip_size_bytes": verification.get("zip_size_bytes"),
            "manifest_hash": verification.get("manifest_hash"),
            "summary": verification.get("summary") if isinstance(verification.get("summary"), dict) else {},
        }
        verification_summary["integrity_hash"] = sidecar_hash(verification_summary)
        quorum = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "quorum": source.get("quorum") if isinstance(source.get("quorum"), dict) else {}}
        quorum["integrity_hash"] = sidecar_hash(quorum)
        accepted_index = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "items": source.get("accepted_evidence") if isinstance(source.get("accepted_evidence"), list) else []}
        accepted_index["integrity_hash"] = sidecar_hash(accepted_index)
        accepted_verification = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "source_hash": signoff.get("source_hash"),
            "items": [
                {
                    "evidence_id": item.get("evidence_id"),
                    "response_id": item.get("response_id"),
                    "verification_status": item.get("verification_status"),
                    "verification_report_hash": item.get("verification_report_hash"),
                    "zip_sha256": item.get("zip_sha256"),
                }
                for item in accepted_index["items"]
                if isinstance(item, dict)
            ],
        }
        accepted_verification["integrity_hash"] = sidecar_hash(accepted_verification)
        distribution = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "distribution_kit": source.get("distribution_kit") if isinstance(source.get("distribution_kit"), dict) else {}}
        distribution["integrity_hash"] = sidecar_hash(distribution)
        latest_cr = _latest_applied_change_request(self.change_requests_dir(center_id), signoff.get("integrity_hash"))
        change = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "latest_applied_change_request": latest_cr}
        change["integrity_hash"] = sidecar_hash(change)
        chain = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": signoff.get("source_hash"), "events": self._history_events(center_id)}
        chain["integrity_hash"] = sidecar_hash(chain)
        report = {
            "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
            "package_type": ACCEPTANCE_BOARD_SIGNOFF_ARCHIVE_REPORT_PACKAGE_TYPE,
            "center_id": center_id,
            "created_at": now,
            "status": "passed",
            "source_hash": signoff.get("source_hash"),
            "signoff_hash": signoff.get("integrity_hash"),
            "summary": {
                "signoff_status": signoff.get("status"),
                "board_readiness": (source.get("board") if isinstance(source.get("board"), dict) else {}).get("readiness"),
                "verification_status": (source.get("verification") if isinstance(source.get("verification"), dict) else {}).get("status"),
                "accepted_evidence_count": len(accepted_index["items"]),
            },
            "warnings": [],
        }
        report["integrity_hash"] = acceptance_board_signoff_archive_hash(report)
        return {
            "board-signoff-archive-report.json": report,
            "board-signoff.json": signoff,
            "board-verification-summary.json": verification_summary,
            "board-fingerprint-summary.json": board_fingerprint,
            "quorum-fingerprint-summary.json": quorum,
            "accepted-evidence-fingerprint-index.json": accepted_index,
            "accepted-evidence-verification-index.json": accepted_verification,
            "distribution-kit-fingerprint-summary.json": distribution,
            "change-request-summary.json": change,
            "chain-of-custody.json": chain,
            "README.txt": _signoff_archive_readme(signoff),
            "VERIFY.txt": _signoff_archive_verify_text(),
        }

    def _write_cached_sidecars(self, center_id: str, source_hash: str, response_index: ImplementationDocument, evidence_index: ImplementationDocument, response_proofs: list[ImplementationDocument], evidence_summaries: list[ImplementationDocument]) -> None:
        cache_dir = self._cache_dir(center_id, source_hash)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        _mkdir(cache_dir / "response-proofs")
        _mkdir(cache_dir / "evidence")
        _write_json(cache_dir / "response-index.json", response_index)
        _write_json(cache_dir / "accepted-evidence-index.json", evidence_index)
        for proof in response_proofs:
            response_id = _safe_id(str(proof.get("response_id") or "response"))
            binding = proof.get("binding_proof") if isinstance(proof.get("binding_proof"), dict) else {}
            verification = proof.get("verification_summary") if isinstance(proof.get("verification_summary"), dict) else {}
            binding["source_hash"] = source_hash
            verification["source_hash"] = source_hash
            _write_json(cache_dir / "response-proofs" / f"{response_id}-binding-proof.json", binding)
            _write_json(cache_dir / "response-proofs" / f"{response_id}-verification-summary.json", verification)
        for item in evidence_summaries:
            item["source_hash"] = source_hash
            _write_json(cache_dir / "evidence" / f"{_safe_id(str(item.get('evidence_id') or 'evidence'))}-summary.json", item)

    def _sidecars_for_export(self, center_id: str, source_hash: str) -> ImplementationDocument:
        report = self.read_report(center_id, default={})
        cache_dir = self._cache_dir(center_id, source_hash)
        response_index = _read_json_default(cache_dir / "response-index.json", default={})
        evidence_index = _read_json_default(cache_dir / "accepted-evidence-index.json", default={})
        response_proofs: list[dict[str, Any]] = []
        for item in sorted(cache_dir.glob("response-proofs/*-binding-proof.json")):
            response_id = item.name[: -len("-binding-proof.json")]
            response_proofs.append({"response_id": response_id, "binding_proof": _read_json_default(item, default={}), "verification_summary": _read_json_default(cache_dir / "response-proofs" / f"{response_id}-verification-summary.json", default={})})
        evidence_summaries = [_read_json_default(path, default={}) for path in sorted((cache_dir / "evidence").glob("*-summary.json"))]
        board_summary = {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": source_hash, "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {}, "readiness": report.get("readiness"), "status": report.get("status")}
        board_summary["integrity_hash"] = sidecar_hash(board_summary)
        quorum = _quorum_evidence(report)
        quorum["integrity_hash"] = sidecar_hash(quorum)
        response_index["integrity_hash"] = sidecar_hash(response_index)
        evidence_index["integrity_hash"] = sidecar_hash(evidence_index)
        return {"board_summary": board_summary, "response_index": response_index, "accepted_evidence_index": evidence_index, "quorum_evidence": quorum, "response_proofs": response_proofs, "evidence_summaries": evidence_summaries}

    def _cache_dir(self, center_id: str, source_hash: str) -> Path:
        return self.root_dir(center_id) / "cache" / _safe_id(str(source_hash or "missing")[:16])

















def acceptance_board_change_request_hash(change_request: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (change_request or {}).items() if key not in ACCEPTANCE_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS})











def redaction_summary(value: Any) -> dict[str, Any]:
    findings = _redaction_findings("payload", json.dumps(value, ensure_ascii=False, sort_keys=True))
    return {"status": "failed" if findings else "passed", "finding_count": len(findings)}


def _default_policy(center_id: str, now: str) -> ImplementationDocument:
    policy = {
        "schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION,
        "package_type": ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE,
        "policy_id": DEFAULT_POLICY_ID,
        "center_id": center_id,
        "created_at": now,
        "updated_at": now,
        "status": "active",
        "requirements": _normalize_requirements({}),
        "role_rules": [],
    }
    policy["integrity_hash"] = acceptance_board_policy_hash(policy)
    return policy


def _normalize_requirements(payload: ImplementationDocument) -> ImplementationDocument:
    payload = payload if isinstance(payload, dict) else {}
    roles = []
    for role in payload.get("required_roles", []) if isinstance(payload.get("required_roles"), list) else []:
        safe = _safe_id(str(role or "")).lower()
        if safe and safe not in roles:
            roles.append(safe)
    return {
        "min_accepted_count": max(1, min(50, int(payload.get("min_accepted_count") or 1))),
        "min_accepted_organizations": max(0, min(50, int(payload.get("min_accepted_organizations") or 1))),
        "required_roles": roles,
        "allow_needs_changes": bool(payload.get("allow_needs_changes", False)),
        "allow_rejected": bool(payload.get("allow_rejected", False)),
        "block_on_critical_findings": bool(payload.get("block_on_critical_findings", True)),
        "require_current_distribution_kit": bool(payload.get("require_current_distribution_kit", True)),
        "require_current_accepted_evidence": bool(payload.get("require_current_accepted_evidence", True)),
    }


def _role_rules(requirements: ImplementationDocument) -> list[ImplementationDocument]:
    return [{"role": role, "min_accepted_count": 1} for role in requirements.get("required_roles", []) if role]


def _distribution_kit_state(distribution_kit_store: Any, center_id: str) -> ImplementationDocument:
    zip_path = distribution_kit_store.zip_path(center_id)
    report = distribution_kit_store.read_report(center_id, default={})
    verification = _read_json_default(distribution_kit_store.verification_report_path(center_id), default={})
    manifest = _read_zip_json(zip_path, "distribution-kit-manifest.json")
    return _sanitize(
        {
            "zip_sha256": _sha256(zip_path),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
            "manifest_hash": manifest.get("integrity_hash"),
            "report_hash": report.get("integrity_hash"),
            "source_hash": report.get("source_hash"),
            "verification_report_hash": verification_hash(verification),
            "verification_status": verification.get("status"),
        }
    )


def _public_response_from_record(response: ImplementationDocument) -> ImplementationDocument:
    payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else {}
    reviewer = payload.get("reviewer") if isinstance(payload.get("reviewer"), dict) else {}
    findings = []
    for item in payload.get("findings", []) if isinstance(payload.get("findings"), list) else []:
        if isinstance(item, dict):
            findings.append({"severity": item.get("severity"), "code": item.get("code"), "public_message": sanitize_sensitive_text(str(item.get("public_message") or item.get("message") or ""))[:500]})
    return _sanitize({"response_id": payload.get("response_id"), "result": payload.get("result"), "review_mode": payload.get("review_mode"), "reviewed_at": payload.get("reviewed_at"), "reviewer": {"name": reviewer.get("name"), "organization": reviewer.get("organization"), "role": reviewer.get("role")}, "verification_status": (payload.get("verification") if isinstance(payload.get("verification"), dict) else {}).get("status"), "comments_excerpt": sanitize_sensitive_text(str(payload.get("comments") or ""))[:500], "findings": findings})


def _critical_findings(response: ImplementationDocument) -> list[ImplementationDocument]:
    payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else {}
    return [item for item in payload.get("findings", []) if isinstance(item, dict) and str(item.get("severity") or "").lower() == "critical"]


def _participant_warnings(response: ImplementationDocument, response_stale: bool, evidence_id: str, evidence_current: bool, evidence_verification_status: str) -> list[str]:
    warnings: list[str] = []
    if response_stale:
        warnings.append("response_stale")
    if response.get("verification_status") != "passed":
        warnings.append("response_verification_not_passed")
    if response.get("review_mode") != "external_manual":
        warnings.append("review_mode_not_external_manual")
    if not evidence_id:
        warnings.append("accepted_evidence_missing")
    elif not evidence_current:
        warnings.append("accepted_evidence_stale")
    if evidence_id and evidence_verification_status != "passed":
        warnings.append("accepted_evidence_verification_not_passed")
    return warnings


def _evaluate_board(policy: ImplementationDocument, participants: list[ImplementationDocument]) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
    requirements = policy.get("requirements") if isinstance(policy.get("requirements"), dict) else {}
    counted = [item for item in participants if item.get("counts_for_quorum")]
    organizations = {str(item.get("organization") or "").strip().lower() for item in counted if str(item.get("organization") or "").strip()}
    roles = {str(item.get("role") or "").strip().lower() for item in counted if str(item.get("role") or "").strip()}
    needs_changes = [item for item in participants if item.get("current") and item.get("result") == "needs_changes"]
    rejected = [item for item in participants if item.get("current") and item.get("result") == "rejected"]
    critical = [item for item in participants if item.get("current") and item.get("critical_findings")]
    stale = [item for item in participants if item.get("warnings")]
    required_roles = [str(role).lower() for role in requirements.get("required_roles", [])]
    missing_roles = [role for role in required_roles if role not in roles]
    checks = [
        _check("ptcab_quorum", len(counted) >= int(requirements.get("min_accepted_count") or 1), f"Accepted quorum {len(counted)}/{requirements.get('min_accepted_count')}."),
        _check("ptcab_organization_quorum", len(organizations) >= int(requirements.get("min_accepted_organizations") or 0), f"Accepted organization quorum {len(organizations)}/{requirements.get('min_accepted_organizations')}."),
        _check("ptcab_required_roles", not missing_roles, "Required roles satisfied." if not missing_roles else "Missing required roles: " + ", ".join(missing_roles)),
        _check("ptcab_needs_changes_allowed", bool(requirements.get("allow_needs_changes", False)) or not needs_changes, "Needs changes responses are allowed or absent."),
        _check("ptcab_rejected_allowed", bool(requirements.get("allow_rejected", False)) or not rejected, "Rejected responses are allowed or absent."),
        _check("ptcab_no_critical_findings", not bool(requirements.get("block_on_critical_findings", True)) or not critical, "No blocking critical findings."),
        _check("ptcab_no_stale_participants", not stale, "No stale or incomplete participants."),
    ]
    conflicts: list[dict[str, Any]] = []
    if missing_roles:
        conflicts.append(_conflict("missing_required_role", "blocking", [], "Missing required roles: " + ", ".join(missing_roles)))
    if needs_changes and not bool(requirements.get("allow_needs_changes", False)):
        conflicts.append(_conflict("accepted_and_needs_changes", "blocking", [str(item.get("response_id") or "") for item in needs_changes], "At least one current needs_changes response exists."))
    if rejected and not bool(requirements.get("allow_rejected", False)):
        conflicts.append(_conflict("accepted_and_rejected", "blocking", [str(item.get("response_id") or "") for item in rejected], "At least one current rejected response exists."))
    if critical and bool(requirements.get("block_on_critical_findings", True)):
        conflicts.append(_conflict("critical_finding", "blocking", [str(item.get("response_id") or "") for item in critical], "At least one current critical finding exists."))
    for item in stale:
        for warning in item.get("warnings", []):
            conflicts.append(_conflict(warning if warning in {"response_stale", "accepted_evidence_stale"} else "stale_evidence", "warning", [str(item.get("response_id") or "")], f"Participant has warning: {warning}"))
    for index, item in enumerate(conflicts, start=1):
        item["conflict_id"] = f"ptcabc-{index:06d}"
    return checks, conflicts


def _readiness(policy: ImplementationDocument, participants: list[ImplementationDocument], blockers: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> str:
    if blockers or any(item.get("severity") == "blocking" for item in conflicts):
        if any(item.get("result") == "rejected" and item.get("current") for item in participants) and not bool((policy.get("requirements") or {}).get("allow_rejected", False)):
            return "rejected"
        if any(item.get("result") == "needs_changes" and item.get("current") for item in participants) and not bool((policy.get("requirements") or {}).get("allow_needs_changes", False)):
            return "needs_changes"
        if any("stale" in ",".join(item.get("warnings", [])) for item in participants):
            return "stale"
        if any("accepted_evidence_missing" in item.get("warnings", []) for item in participants):
            return "missing_evidence"
        return "blocked"
    return "ready"


def _board_summary(policy: ImplementationDocument, participants: list[ImplementationDocument], checks: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    counted = [item for item in participants if item.get("counts_for_quorum")]
    organizations = {str(item.get("organization") or "").strip().lower() for item in counted if str(item.get("organization") or "").strip()}
    return {
        "accepted_count": len(counted),
        "accepted_organization_count": len(organizations),
        "needs_changes_count": len([item for item in participants if item.get("current") and item.get("result") == "needs_changes"]),
        "rejected_count": len([item for item in participants if item.get("current") and item.get("result") == "rejected"]),
        "stale_count": len([item for item in participants if item.get("warnings")]),
        "required_roles_status": _check_status(checks, "ptcab_required_roles"),
        "quorum_status": _check_status(checks, "ptcab_quorum"),
        "conflict_status": "failed" if any(item.get("severity") == "blocking" for item in conflicts) else "passed",
        "policy_hash": policy.get("integrity_hash"),
    }


def _response_index(source: ImplementationDocument, rows: list[ImplementationDocument]) -> ImplementationDocument:
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": stable_hash(source), "items": rows}


def _accepted_evidence_index(source: ImplementationDocument, rows: list[ImplementationDocument]) -> ImplementationDocument:
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": stable_hash(source), "items": rows}


def _quorum_evidence(report: ImplementationDocument) -> ImplementationDocument:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    policy = report.get("policy") if isinstance(report.get("policy"), dict) else {}
    participants = report.get("participants") if isinstance(report.get("participants"), list) else []
    counted = [str(item.get("response_id") or "") for item in participants if isinstance(item, dict) and item.get("counts_for_quorum")]
    roles = {str(item.get("role") or "").lower(): "passed" for item in participants if isinstance(item, dict) and item.get("counts_for_quorum") and item.get("role")}
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": report.get("source_hash"), "policy_hash": policy.get("policy_hash"), "decision": {"readiness": report.get("readiness"), "quorum_status": summary.get("quorum_status"), "required_roles_status": summary.get("required_roles_status"), "conflict_status": summary.get("conflict_status")}, "counted_response_ids": counted, "required_roles": roles}


def _check_status(checks: list[ImplementationDocument], check_id: str) -> str:
    for item in checks:
        if item.get("check_id") == check_id:
            return "passed" if item.get("status") == "passed" else "failed"
    return "missing"


def _check(check_id: str, ok: bool, message: str) -> ImplementationDocument:
    return {"scope": "board", "check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message}


def _conflict(conflict_type: str, severity: str, participants: list[str], message: str) -> ImplementationDocument:
    return {"conflict_id": "", "type": conflict_type, "severity": severity, "participants": [item for item in participants if item], "message": message}


def _readme(report: ImplementationDocument) -> str:
    return sanitize_sensitive_text("\n".join(["MusicForge Public Trust Center Acceptance Board", "", f"Center ID: {report.get('center_id')}", f"Readiness: {report.get('readiness')}", f"Status: {report.get('status')}", ""]))


def _verify_text() -> str:
    return "Verify this board package:\npython -m song_agent.cli verify-public-trust-center-acceptance-board-package public-trust-center-acceptance-board.zip --strict --require-ready --json\n"


def _signoff_archive_readme(signoff: ImplementationDocument) -> str:
    return sanitize_sensitive_text(
        "\n".join(
            [
                "MusicForge Public Trust Center Acceptance Board Signoff Archive",
                "",
                f"Center ID: {signoff.get('center_id')}",
                f"Signoff ID: {signoff.get('signoff_id')}",
                f"Status: {signoff.get('status')}",
                "",
            ]
        )
    )


def _signoff_archive_verify_text() -> str:
    return "Verify this signoff archive:\npython -m song_agent.cli verify-public-trust-center-acceptance-board-signoff-archive-package public-trust-center-acceptance-board-signoff-archive.zip --strict --require-signed --json\n"


def _read_zip_json(zip_path: Path, entry: str) -> ImplementationDocument:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = json.loads(_read_text(path))
    except Exception:
        return dict(default or {})
    return _sanitize(value if isinstance(value, dict) else dict(default or {}))


def _next_change_request_id(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    max_index = 0
    for path in root.glob("bcr-*.json"):
        stem = path.stem
        try:
            max_index = max(max_index, int(stem.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"bcr-{max_index + 1:06d}"


def _latest_applied_change_request(root: Path, signoff_hash: Any) -> ImplementationDocument | None:
    if not root.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        item = _read_json_default(path, default={})
        if item.get("status") == "applied" and item.get("applied_signoff_hash") == signoff_hash:
            rows.append(item)
    if not rows:
        return None
    latest = rows[-1]
    return {
        "change_request_id": latest.get("change_request_id"),
        "status": latest.get("status"),
        "applied_at": latest.get("applied_at"),
        "integrity_hash": latest.get("integrity_hash"),
    }


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, _sanitize(payload))
    return path


def _write_text(path: Path, text: str) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        handle.write(text)


def _read_text(path: Path) -> str:
    with open(_fs_path(path), "r", encoding="utf-8") as handle:
        return handle.read()


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


def _file_record(root: Path, path: Path) -> ImplementationDocument:
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


def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterAcceptanceBoardStateError("Resolved path escapes Acceptance Board root.")


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


def _redaction_findings(scope: str, text: str) -> list[ImplementationDocument]:
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
    return sanitize_metadata(payload, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
