from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.public_trust_center_distribution_kit import distribution_kit_manifest_hash
from song_agent.public_trust_center_distribution_kit_acceptance import (
    ACCEPTANCE_BLOCKED_KEYS,
    PublicTrustCenterDistributionKitAcceptanceError,
    PublicTrustCenterDistributionKitAcceptanceStore,
    accepted_evidence_hash,
    accepted_evidence_summary,
    verification_hash,
)
from song_agent.public_trust_center_distribution_kit_acceptance_verifier import (
    verify_public_trust_center_distribution_kit_accepted_evidence_package,
    write_public_trust_center_distribution_kit_accepted_evidence_verification_report,
)
from song_agent.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.releases import stable_hash


ACCEPTANCE_BOARD_SCHEMA_VERSION = 1
ACCEPTANCE_BOARD_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board"
ACCEPTANCE_BOARD_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_report"
ACCEPTANCE_BOARD_CONFLICT_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_conflict_report"
ACCEPTANCE_BOARD_POLICY_PACKAGE_TYPE = "musicforge_public_trust_center_acceptance_board_policy"
ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}
ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS = {"integrity_hash"}
ACCEPTANCE_BOARD_BLOCKED_KEYS = ACCEPTANCE_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"})
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

    def read_policy(self, center_id: str = "ptc-default") -> dict[str, Any]:
        policy = _read_json_default(self.policy_path(center_id), default={})
        if policy:
            return policy
        return _default_policy(center_id, now_iso())

    def save_policy(self, center_id: str = "ptc-default", payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
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
        from song_agent.public_trust_center_acceptance_board_verifier import (
            verify_public_trust_center_acceptance_board_package,
            write_public_trust_center_acceptance_board_verification_report,
        )

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

    def summary(self, center_id: str = "ptc-default") -> dict[str, Any]:
        report = self.read_report(center_id, default={})
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        return {"center_id": center_id, "readiness": report.get("readiness") or "missing", "status": report.get("status") or "missing", **summary}

    def _build_source(self, center_id: str, policy: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
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

    def _evidence_by_response(self, center_id: str) -> dict[str, dict[str, Any]]:
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

    def _ensure_exportable(self, center_id: str, report: dict[str, Any]) -> None:
        if not report:
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report is missing. Refresh before export.")
        policy = self.read_policy(center_id)
        current_source, _participants, _response_index, _evidence_index, _proofs, _summaries = self._build_source(center_id, policy)
        if stable_hash(current_source) != report.get("source_hash"):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report is stale. Refresh before export.")
        if report.get("integrity_hash") != acceptance_board_report_hash(report):
            raise PublicTrustCenterAcceptanceBoardStateError("Acceptance Board report integrity failed.")

    def _write_cached_sidecars(self, center_id: str, source_hash: str, response_index: dict[str, Any], evidence_index: dict[str, Any], response_proofs: list[dict[str, Any]], evidence_summaries: list[dict[str, Any]]) -> None:
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

    def _sidecars_for_export(self, center_id: str, source_hash: str) -> dict[str, Any]:
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


def acceptance_board_policy_hash(policy: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (policy or {}).items() if key not in ACCEPTANCE_BOARD_POLICY_HASH_EXCLUDE_KEYS})


def acceptance_board_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS})


def acceptance_board_conflict_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in ACCEPTANCE_BOARD_REPORT_HASH_EXCLUDE_KEYS})


def acceptance_board_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ACCEPTANCE_BOARD_MANIFEST_HASH_EXCLUDE_KEYS})


def sidecar_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (payload or {}).items() if key not in ACCEPTANCE_BOARD_SIDECAR_HASH_EXCLUDE_KEYS})


def redaction_summary(value: Any) -> dict[str, Any]:
    findings = _redaction_findings("payload", json.dumps(value, ensure_ascii=False, sort_keys=True))
    return {"status": "failed" if findings else "passed", "finding_count": len(findings)}


def _default_policy(center_id: str, now: str) -> dict[str, Any]:
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


def _normalize_requirements(payload: dict[str, Any]) -> dict[str, Any]:
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


def _role_rules(requirements: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"role": role, "min_accepted_count": 1} for role in requirements.get("required_roles", []) if role]


def _distribution_kit_state(distribution_kit_store: Any, center_id: str) -> dict[str, Any]:
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


def _public_response_from_record(response: dict[str, Any]) -> dict[str, Any]:
    payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else {}
    reviewer = payload.get("reviewer") if isinstance(payload.get("reviewer"), dict) else {}
    findings = []
    for item in payload.get("findings", []) if isinstance(payload.get("findings"), list) else []:
        if isinstance(item, dict):
            findings.append({"severity": item.get("severity"), "code": item.get("code"), "public_message": sanitize_sensitive_text(str(item.get("public_message") or item.get("message") or ""))[:500]})
    return _sanitize({"response_id": payload.get("response_id"), "result": payload.get("result"), "review_mode": payload.get("review_mode"), "reviewed_at": payload.get("reviewed_at"), "reviewer": {"name": reviewer.get("name"), "organization": reviewer.get("organization"), "role": reviewer.get("role")}, "verification_status": (payload.get("verification") if isinstance(payload.get("verification"), dict) else {}).get("status"), "comments_excerpt": sanitize_sensitive_text(str(payload.get("comments") or ""))[:500], "findings": findings})


def _critical_findings(response: dict[str, Any]) -> list[dict[str, Any]]:
    payload = response.get("response_payload") if isinstance(response.get("response_payload"), dict) else {}
    return [item for item in payload.get("findings", []) if isinstance(item, dict) and str(item.get("severity") or "").lower() == "critical"]


def _participant_warnings(response: dict[str, Any], response_stale: bool, evidence_id: str, evidence_current: bool, evidence_verification_status: str) -> list[str]:
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


def _evaluate_board(policy: dict[str, Any], participants: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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


def _readiness(policy: dict[str, Any], participants: list[dict[str, Any]], blockers: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> str:
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


def _board_summary(policy: dict[str, Any], participants: list[dict[str, Any]], checks: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> dict[str, Any]:
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


def _response_index(source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": stable_hash(source), "items": rows}


def _accepted_evidence_index(source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": stable_hash(source), "items": rows}


def _quorum_evidence(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    policy = report.get("policy") if isinstance(report.get("policy"), dict) else {}
    participants = report.get("participants") if isinstance(report.get("participants"), list) else []
    counted = [str(item.get("response_id") or "") for item in participants if isinstance(item, dict) and item.get("counts_for_quorum")]
    roles = {str(item.get("role") or "").lower(): "passed" for item in participants if isinstance(item, dict) and item.get("counts_for_quorum") and item.get("role")}
    return {"schema_version": ACCEPTANCE_BOARD_SCHEMA_VERSION, "source_hash": report.get("source_hash"), "policy_hash": policy.get("policy_hash"), "decision": {"readiness": report.get("readiness"), "quorum_status": summary.get("quorum_status"), "required_roles_status": summary.get("required_roles_status"), "conflict_status": summary.get("conflict_status")}, "counted_response_ids": counted, "required_roles": roles}


def _check_status(checks: list[dict[str, Any]], check_id: str) -> str:
    for item in checks:
        if item.get("check_id") == check_id:
            return "passed" if item.get("status") == "passed" else "failed"
    return "missing"


def _check(check_id: str, ok: bool, message: str) -> dict[str, Any]:
    return {"scope": "board", "check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message}


def _conflict(conflict_type: str, severity: str, participants: list[str], message: str) -> dict[str, Any]:
    return {"conflict_id": "", "type": conflict_type, "severity": severity, "participants": [item for item in participants if item], "message": message}


def _readme(report: dict[str, Any]) -> str:
    return sanitize_sensitive_text("\n".join(["MusicForge Public Trust Center Acceptance Board", "", f"Center ID: {report.get('center_id')}", f"Readiness: {report.get('readiness')}", f"Status: {report.get('status')}", ""]))


def _verify_text() -> str:
    return "Verify this board package:\npython -m song_agent.cli verify-public-trust-center-acceptance-board-package public-trust-center-acceptance-board.zip --strict --require-ready --json\n"


def _read_zip_json(zip_path: Path, entry: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
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
    write_json(path, _sanitize(payload))
    return path


def _write_text(path: Path, text: str) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        handle.write(text)


def _read_text(path: Path) -> str:
    with open(_fs_path(path), "r", encoding="utf-8") as handle:
        return handle.read()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


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
    return sanitize_metadata(payload, blocked_keys=ACCEPTANCE_BOARD_BLOCKED_KEYS)
