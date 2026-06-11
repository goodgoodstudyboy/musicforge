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
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.release_portfolio_governance_attestation_portal_review import (
    ReleasePortfolioGovernanceAttestationPortalReviewStore,
    response_summary,
    verification_hash as review_verification_hash,
)
from song_agent.releases import stable_hash


ACCEPTED_EVIDENCE_SCHEMA_VERSION = 1
ACCEPTED_EVIDENCE_PACKAGE_TYPE = "release_portfolio_governance_attestation_accepted_evidence"
ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_accepted_evidence_report"
ACCEPTED_EVIDENCE_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}
ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}
ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}
ACCEPTED_EVIDENCE_STATUSES = {"current", "stale", "failed", "archived"}


class ReleasePortfolioGovernanceAttestationAcceptedEvidenceError(ValueError):
    pass


class ReleasePortfolioGovernanceAttestationAcceptedEvidenceNotFoundError(ReleasePortfolioGovernanceAttestationAcceptedEvidenceError):
    pass


class ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError(ReleasePortfolioGovernanceAttestationAcceptedEvidenceError):
    pass


class ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore:
    def __init__(self, *, review_store: ReleasePortfolioGovernanceAttestationPortalReviewStore) -> None:
        self.review_store = review_store
        self.lock = threading.RLock()

    def root_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        root = self.review_store.portal_store.attestation_store.portfolio_store.portfolio_dir(portfolio_id) / "governance-attestation-accepted-evidence"
        if profile == "public_summary":
            return root
        return root / "profiles" / _safe_profile(profile)

    def evidence_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "accepted-evidence.json"

    def history_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "accepted-evidence-history.jsonl"

    def verification_report_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "accepted-evidence-verification-report.json"

    def export_dir(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "accepted-evidence-export"

    def zip_path(self, portfolio_id: str, profile: str = "public_summary") -> Path:
        return self.root_dir(portfolio_id, profile) / "governance-attestation-accepted-evidence.zip"

    def read_evidence(self, portfolio_id: str, *, profile: str = "public_summary", default: dict[str, Any] | None = None) -> dict[str, Any]:
        return _read_json_default(self.evidence_path(portfolio_id, profile), default=default)

    def read_export_manifest(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        path = self.export_dir(portfolio_id, profile) / "accepted-evidence-manifest.json"
        if not path.exists():
            raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceNotFoundError("Accepted Evidence export has not been generated.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)

    def refresh_evidence(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            payload = payload or {}
            profile = str(payload.get("profile") or "public_summary")
            response_id = str(payload.get("response_id") or "").strip() or self._latest_current_accepted_response_id(portfolio_id, profile)
            if not response_id:
                raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("No current accepted Portal Review Response is available.")
            response = self.review_store.get_response(portfolio_id, response_id, profile=profile)
            pack = self.review_store.read_pack(portfolio_id, profile=profile, default={})
            verification = self.review_store.verify_response(portfolio_id, response_id, profile=profile, now=now)
            source = self.build_source(portfolio_id, response_id, profile=profile, response=response, pack=pack, verification=verification)
            blockers, warnings, checks = self._findings(source, response, pack, verification)
            if blockers:
                detail = str(blockers[0].get("message") or "Accepted Evidence has blockers.")
                raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError(detail)
            response_public = _response_public_summary(response)
            public = _public_summary(source, response_public, "accepted")
            evidence = {
                "schema_version": ACCEPTED_EVIDENCE_SCHEMA_VERSION,
                "package_type": ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                "accepted_evidence_id": _evidence_id(portfolio_id, profile, source),
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "status": "current",
                "source": source,
                "source_hash": stable_hash(source),
                "response_summary": response_public,
                "public_summary": public,
                "checks": checks,
                "blockers": blockers,
                "warnings": warnings,
                "created_at": now,
                "updated_at": now,
            }
            evidence["integrity_hash"] = accepted_evidence_hash(evidence)
            self.root_dir(portfolio_id, profile).mkdir(parents=True, exist_ok=True)
            _write_json(self.evidence_path(portfolio_id, profile), evidence)
            self._append_history(portfolio_id, profile, "accepted_evidence_refreshed", {"accepted_evidence_id": evidence["accepted_evidence_id"], "source_hash": evidence["source_hash"], "response_id": response_id}, now=now)
            return sanitize_metadata(evidence, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)

    def build_source(
        self,
        portfolio_id: str,
        response_id: str,
        *,
        profile: str = "public_summary",
        response: dict[str, Any] | None = None,
        pack: dict[str, Any] | None = None,
        verification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = response if isinstance(response, dict) else self.review_store.get_response(portfolio_id, response_id, profile=profile)
        pack = pack if isinstance(pack, dict) else self.review_store.read_pack(portfolio_id, profile=profile, default={})
        verification = verification if isinstance(verification, dict) else self.review_store.verify_response(portfolio_id, response_id, profile=profile)
        pack_source = pack.get("source") if isinstance(pack.get("source"), dict) else {}
        source = {
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "response_id": response.get("response_id"),
            "response_decision": response.get("decision"),
            "response_status": response.get("status"),
            "response_payload_hash": response.get("payload_hash"),
            "response_integrity_hash": response.get("integrity_hash"),
            "response_verification_status": verification.get("status"),
            "response_verification_hash": review_verification_hash(verification),
            "review_pack_id": pack.get("review_pack_id"),
            "review_pack_source_hash": pack.get("source_hash"),
            "response_review_pack_id": response.get("review_pack_id"),
            "response_review_pack_source_hash": response.get("review_pack_source_hash"),
            "review_pack_stale": self.review_store.pack_is_stale(portfolio_id, pack, profile=profile) if pack else True,
            "portal_zip_sha256": pack_source.get("portal_zip_sha256"),
            "portal_zip_size_bytes": pack_source.get("portal_zip_size_bytes"),
            "portal_manifest_hash": pack_source.get("portal_manifest_hash"),
            "portal_verification_hash": pack_source.get("portal_verification_hash"),
            "portal_verification_status": pack_source.get("portal_verification_status"),
            "portal_source_hash": pack_source.get("portal_source_hash"),
            "registry_zip_sha256": pack_source.get("registry_zip_sha256"),
            "registry_manifest_hash": pack_source.get("registry_manifest_hash"),
            "registry_verification_hash": pack_source.get("registry_verification_hash"),
            "registry_verification_status": pack_source.get("registry_verification_status"),
            "registry_current_entry_id": pack_source.get("registry_current_entry_id"),
            "registry_current_entry_hash": pack_source.get("registry_current_entry_hash"),
            "current_certificate_id": pack_source.get("current_certificate_id"),
            "current_attestation_zip_sha256": pack_source.get("current_attestation_zip_sha256"),
            "current_attestation_manifest_hash": pack_source.get("current_attestation_manifest_hash"),
            "current_attestation_verification_hash": pack_source.get("current_attestation_verification_hash"),
            "current_attestation_verification_status": pack_source.get("current_attestation_verification_status"),
            "evidence_vault_zip_sha256": pack_source.get("evidence_vault_zip_sha256"),
            "evidence_vault_manifest_hash": pack_source.get("evidence_vault_manifest_hash"),
            "evidence_vault_verification_hash": pack_source.get("evidence_vault_verification_hash"),
            "evidence_vault_deep_verification_status": pack_source.get("evidence_vault_deep_verification_status"),
            "final_board_signoff_hash": pack_source.get("final_board_signoff_hash"),
        }
        return sanitize_metadata(source, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)

    def evidence_is_stale(self, portfolio_id: str, evidence: dict[str, Any] | None = None, *, profile: str = "public_summary") -> bool:
        data = evidence if isinstance(evidence, dict) else self.read_evidence(portfolio_id, profile=profile, default={})
        if not data:
            return False
        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        response_id = str(source.get("response_id") or "")
        if not response_id:
            return True
        try:
            current = self.build_source(portfolio_id, response_id, profile=str(data.get("attestation_profile") or profile))
        except Exception:
            return True
        return _source_stale_hash(current) != _source_stale_hash(source)

    def export_evidence(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            evidence = self.read_evidence(portfolio_id, profile=profile, default={})
            if not evidence:
                evidence = self.refresh_evidence(portfolio_id, payload, now=now)
            self._ensure_exportable(portfolio_id, evidence, profile=profile)
            state = _state_tuple(evidence)
            if self._history_has_state_event(portfolio_id, profile, state, "accepted_evidence_exported"):
                raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence export already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            existing_manifest = _read_json_default(export_dir / "accepted-evidence-manifest.json", default={})
            if _manifest_state(existing_manifest) == state:
                raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence export already exists for this source state.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            (export_dir / "data").mkdir(parents=True, exist_ok=True)
            data_docs = _data_documents(evidence)
            _write_json(export_dir / "accepted-evidence-report.json", evidence)
            _write_json(export_dir / "accepted-evidence-summary.json", _accepted_evidence_public_document(evidence))
            for name, doc in data_docs.items():
                _write_json(export_dir / "data" / name, doc)
            (export_dir / "README.txt").write_text(_readme(evidence), encoding="utf-8")
            files = [_file_record(export_dir, path) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "accepted-evidence-manifest.json"]
            manifest = {
                "schema_version": ACCEPTED_EVIDENCE_SCHEMA_VERSION,
                "package_type": ACCEPTED_EVIDENCE_PACKAGE_TYPE,
                "tool": {"name": "MusicForge Public Attestation Accepted Evidence", "version": __version__},
                "portfolio_id": portfolio_id,
                "attestation_profile": profile,
                "created_at": now,
                "source_hash": evidence.get("source_hash"),
                "accepted_evidence": {
                    "accepted_evidence_id": evidence.get("accepted_evidence_id"),
                    "integrity_hash": evidence.get("integrity_hash"),
                    "source_hash": evidence.get("source_hash"),
                    "status": evidence.get("status"),
                },
                "public_summary": evidence.get("public_summary") if isinstance(evidence.get("public_summary"), dict) else {},
                "files": sorted(files, key=lambda item: item["path"]),
                "zip": {},
                "redaction_summary": _redaction_summary({"evidence": evidence, "data": data_docs}),
            }
            manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
            _write_json(export_dir / "accepted-evidence-manifest.json", manifest)
            self._append_history(portfolio_id, profile, "accepted_evidence_exported", {**state, "manifest_hash": manifest["integrity_hash"]}, now=now)
            return sanitize_metadata(manifest, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)

    def build_zip(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            evidence = self.read_evidence(portfolio_id, profile=profile, default={})
            if not evidence:
                evidence = self.refresh_evidence(portfolio_id, payload, now=now)
            self._ensure_exportable(portfolio_id, evidence, profile=profile)
            state = _state_tuple(evidence)
            if self._history_has_state_event(portfolio_id, profile, state, "accepted_evidence_zip_built"):
                raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence ZIP already exists for this source state.")
            export_dir = self.export_dir(portfolio_id, profile).resolve()
            root = self.root_dir(portfolio_id, profile).resolve()
            zip_path = self.zip_path(portfolio_id, profile).resolve()
            _ensure_within(root, export_dir)
            _ensure_within(root, zip_path)
            if not (export_dir / "accepted-evidence-manifest.json").exists():
                if self._history_has_state_event(portfolio_id, profile, state, "accepted_evidence_exported"):
                    raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence export already exists for this source state.")
                self.export_evidence(portfolio_id, {"profile": profile}, now=now)
            manifest = read_json(export_dir / "accepted-evidence-manifest.json")
            entries = _zip_entries(export_dir)
            manifest["zip"] = {"created_at": now, "filename": zip_path.name, "entry_count": len(entries), "entries": [entry for _path, entry in entries], "total_uncompressed_size_bytes": sum(path.stat().st_size for path, _entry in entries)}
            manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
            _write_json(export_dir / "accepted-evidence-manifest.json", manifest)
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
            info = {"created_at": now, "filename": zip_path.name, "path": zip_path.name, "size_bytes": zip_path.stat().st_size, "sha256": _sha256(zip_path), "entry_count": len(entries)}
            self._append_history(portfolio_id, profile, "accepted_evidence_zip_built", {**state, "zip_sha256": info["sha256"]}, now=now)
            return sanitize_metadata(info, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)

    def verify_evidence(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        from song_agent.release_portfolio_governance_attestation_accepted_evidence_verifier import verify_release_portfolio_governance_attestation_accepted_evidence, write_release_portfolio_governance_attestation_accepted_evidence_verification_report

        profile = str((payload or {}).get("profile") or "public_summary")
        report = verify_release_portfolio_governance_attestation_accepted_evidence(
            self.zip_path(portfolio_id, profile),
            strict=bool((payload or {}).get("strict", False)),
            require_current=bool((payload or {}).get("require_current", False)),
            now=now,
        )
        write_release_portfolio_governance_attestation_accepted_evidence_verification_report(report, self.verification_report_path(portfolio_id, profile))
        return report

    def archive_evidence(self, portfolio_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            profile = str((payload or {}).get("profile") or "public_summary")
            reason = sanitize_sensitive_text(str((payload or {}).get("reason") or "").strip())
            if len(reason) < 8:
                raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("reason must be at least 8 characters.")
            evidence = self.read_evidence(portfolio_id, profile=profile, default={})
            if not evidence:
                raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceNotFoundError("Accepted Evidence does not exist.")
            evidence["status"] = "archived"
            evidence["archived_at"] = now
            evidence["archive_reason"] = reason[:1000]
            evidence["updated_at"] = now
            evidence["integrity_hash"] = accepted_evidence_hash(evidence)
            _write_json(self.evidence_path(portfolio_id, profile), evidence)
            self._append_history(portfolio_id, profile, "accepted_evidence_archived", {"accepted_evidence_id": evidence.get("accepted_evidence_id"), "reason_hash": stable_hash(reason)}, now=now)
            return sanitize_metadata(evidence, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)

    def summary(self, portfolio_id: str, *, profile: str = "public_summary") -> dict[str, Any]:
        evidence = self.read_evidence(portfolio_id, profile=profile, default={})
        if not evidence:
            return {"status": "missing", "external_review_status": "missing", "profile": profile}
        summary = accepted_evidence_summary(evidence)
        summary["stale"] = self.evidence_is_stale(portfolio_id, evidence, profile=profile)
        return sanitize_metadata(summary, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)

    def _latest_current_accepted_response_id(self, portfolio_id: str, profile: str) -> str:
        root = self.review_store.responses_dir(portfolio_id, profile)
        if not root.exists():
            return ""
        rows: list[dict[str, Any]] = []
        for path in sorted(root.glob("aprr-*.json")):
            value = _read_json_default(path, default={})
            if value.get("decision") == "accepted" and value.get("status") == "accepted":
                rows.append(value)
        for response in reversed(rows):
            try:
                verification = self.review_store.verify_response(portfolio_id, str(response.get("response_id") or ""), profile=profile)
            except Exception:
                continue
            pack = self.review_store.read_pack(portfolio_id, profile=profile, default={})
            if verification.get("status") == "passed" and response.get("review_pack_source_hash") == pack.get("source_hash"):
                return str(response.get("response_id") or "")
        return ""

    def _findings(self, source: dict[str, Any], response: dict[str, Any], pack: dict[str, Any], verification: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        checks: list[dict[str, Any]] = []

        def check(check_id: str, passed: bool, message: str, *, warning: bool = False) -> None:
            row = {"check_id": check_id, "status": "passed" if passed else "warning" if warning else "failed", "severity": "warning" if warning else "blocking", "message": message}
            checks.append(row)

        check("accepted_evidence_decision_accepted", response.get("decision") == "accepted", "Portal Review Response decision must be accepted.")
        check("accepted_evidence_response_status_current", response.get("status") == "accepted", "Portal Review Response status must be accepted/current.")
        check("accepted_evidence_response_verification_passed", verification.get("status") == "passed", "Portal Review Response verification must be passed.")
        check("accepted_evidence_review_pack_source_current", response.get("review_pack_source_hash") == pack.get("source_hash") and bool(pack.get("source_hash")), "Response must bind to the current Review Pack source hash.")
        check("accepted_evidence_review_pack_not_stale", not bool(source.get("review_pack_stale")), "Review Pack source must not be stale.")
        check("accepted_evidence_portal_verified", source.get("portal_verification_status") == "passed", "Portal verification must be passed.")
        check("accepted_evidence_registry_verified", source.get("registry_verification_status") == "passed", "Registry verification must be passed.")
        check("accepted_evidence_attestation_verified", source.get("current_attestation_verification_status") == "passed", "Public Attestation verification must be passed.")
        check("accepted_evidence_current_entry", bool(source.get("registry_current_entry_id")), "Current Registry entry is required.")
        check("accepted_evidence_redaction", _redaction_summary({"source": source, "response_summary": _response_public_summary(response)}).get("status") == "passed", "Accepted Evidence public summary must pass redaction scan.")
        blockers = [item for item in checks if item["status"] == "failed" and item["severity"] == "blocking"]
        warnings = [item for item in checks if item["status"] == "warning"]
        return blockers, warnings, checks

    def _ensure_exportable(self, portfolio_id: str, evidence: dict[str, Any], *, profile: str) -> None:
        if not accepted_evidence_integrity_ok(evidence):
            raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence integrity failed.")
        if evidence.get("status") != "current":
            raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence must be current before export.")
        if self.evidence_is_stale(portfolio_id, evidence, profile=profile):
            raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence source is stale. Refresh accepted evidence before export.")
        if (evidence.get("public_summary") if isinstance(evidence.get("public_summary"), dict) else {}).get("external_review_status") != "accepted":
            raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Accepted Evidence public summary is not accepted.")

    def _append_history(self, portfolio_id: str, profile: str, event_type: str, summary: dict[str, Any], *, now: str) -> None:
        path = self.history_path(portfolio_id, profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now, "event_type": event_type, **summary}, ensure_ascii=False, sort_keys=True) + "\n")

    def _history_has_state_event(self, portfolio_id: str, profile: str, state: dict[str, str], event_type: str) -> bool:
        path = self.history_path(portfolio_id, profile)
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


def accepted_evidence_hash(evidence: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (evidence or {}).items() if key not in ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS})


def accepted_evidence_integrity_ok(evidence: dict[str, Any] | None) -> bool:
    data = evidence if isinstance(evidence, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == accepted_evidence_hash(data)


def accepted_evidence_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS})


def accepted_evidence_manifest_integrity_ok(manifest: dict[str, Any] | None) -> bool:
    data = manifest if isinstance(manifest, dict) else {}
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == accepted_evidence_manifest_hash(data)


def accepted_evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    data = evidence if isinstance(evidence, dict) else {}
    public = data.get("public_summary") if isinstance(data.get("public_summary"), dict) else {}
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "external_review_status": public.get("external_review_status") or data.get("status") or "missing",
            "accepted_evidence_id": data.get("accepted_evidence_id"),
            "response_id": source.get("response_id") or public.get("response_id"),
            "reviewer_label": public.get("reviewer_label"),
            "reviewed_at": public.get("accepted_at") or public.get("reviewed_at"),
            "verification_status": source.get("response_verification_status"),
            "source_hash": data.get("source_hash"),
            "current_entry_id": source.get("registry_current_entry_id"),
            "current_certificate_id": source.get("current_certificate_id"),
            "stale": data.get("status") == "stale",
        },
        blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS,
    )


def accepted_evidence_public_summary_from_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    root = portfolio_dir / "governance-attestation-accepted-evidence"
    if profile != "public_summary":
        root = root / "profiles" / _safe_profile(profile)
    evidence = _read_json_default(root / "accepted-evidence.json", default={})
    if not evidence:
        return _missing_public_summary()
    if not accepted_evidence_integrity_ok(evidence):
        summary = accepted_evidence_summary(evidence)
        summary["status"] = "failed"
        summary["external_review_status"] = "failed"
        summary.setdefault("accepted_evidence_verification_status", "missing")
        summary.setdefault("accepted_evidence_verification_report_hash", None)
        return summary
    summary = accepted_evidence_summary(evidence)
    verification = _read_json_default(root / "accepted-evidence-verification-report.json", default={})
    verification_status = verification.get("status") or "missing"
    zip_path = root / "governance-attestation-accepted-evidence.zip"
    manifest = _read_json_default(root / "accepted-evidence-export" / "accepted-evidence-manifest.json", default={})
    current_zip_sha256 = _sha256(zip_path)
    current_manifest_hash = manifest.get("integrity_hash") if isinstance(manifest, dict) else None
    if verification_status == "passed" and (
        not current_zip_sha256
        or verification.get("zip_sha256") != current_zip_sha256
        or not current_manifest_hash
        or verification.get("manifest_hash") != current_manifest_hash
    ):
        verification_status = "failed"
    summary["accepted_evidence_verification_status"] = verification_status
    summary["accepted_evidence_zip_sha256"] = verification.get("zip_sha256")
    summary["accepted_evidence_zip_size_bytes"] = verification.get("zip_size_bytes")
    summary["accepted_evidence_manifest_hash"] = verification.get("manifest_hash")
    summary["accepted_evidence_verification_report_hash"] = stable_hash(verification) if verification else None
    return sanitize_metadata(summary, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS)


def _missing_public_summary() -> dict[str, Any]:
    return {
        "status": "missing",
        "external_review_status": "missing",
        "accepted_evidence_id": None,
        "response_id": None,
        "reviewer_label": None,
        "reviewed_at": None,
        "verification_status": None,
        "source_hash": None,
        "current_entry_id": None,
        "current_certificate_id": None,
        "accepted_evidence_verification_status": "missing",
        "accepted_evidence_zip_sha256": None,
        "accepted_evidence_zip_size_bytes": None,
        "accepted_evidence_manifest_hash": None,
        "accepted_evidence_verification_report_hash": None,
    }


def accepted_evidence_verification_summary_from_portfolio_dir(portfolio_dir: Path, *, profile: str = "public_summary") -> dict[str, Any]:
    root = portfolio_dir / "governance-attestation-accepted-evidence"
    if profile != "public_summary":
        root = root / "profiles" / _safe_profile(profile)
    evidence = _read_json_default(root / "accepted-evidence.json", default={})
    verification = _read_json_default(root / "accepted-evidence-verification-report.json", default={})
    manifest = _read_json_default(root / "accepted-evidence-export" / "accepted-evidence-manifest.json", default={})
    public_summary = accepted_evidence_summary(evidence) if evidence else {"status": "missing", "external_review_status": "missing"}
    zip_path = root / "governance-attestation-accepted-evidence.zip"
    current_zip_sha256 = _sha256(zip_path)
    current_manifest_hash = manifest.get("integrity_hash") if isinstance(manifest, dict) else None
    verification_status = verification.get("status") or "missing"
    if verification_status == "passed" and (
        not current_zip_sha256
        or verification.get("zip_sha256") != current_zip_sha256
        or not current_manifest_hash
        or verification.get("manifest_hash") != current_manifest_hash
    ):
        verification_status = "failed"
    return sanitize_metadata(
        {
            "package_type": "release_portfolio_governance_attestation_accepted_evidence_verification_summary",
            "profile": profile,
            "accepted_evidence_id": evidence.get("accepted_evidence_id"),
            "accepted_evidence_source_hash": evidence.get("source_hash"),
            "accepted_evidence_status": public_summary.get("status"),
            "external_review_status": public_summary.get("external_review_status"),
            "response_id": public_summary.get("response_id"),
            "current_entry_id": public_summary.get("current_entry_id"),
            "current_certificate_id": public_summary.get("current_certificate_id"),
            "accepted_evidence_verification_status": verification_status,
            "accepted_evidence_zip_sha256": verification.get("zip_sha256"),
            "accepted_evidence_zip_size_bytes": verification.get("zip_size_bytes"),
            "accepted_evidence_manifest_hash": verification.get("manifest_hash"),
            "accepted_evidence_verification_report_hash": stable_hash(verification) if verification else None,
            "current_zip_sha256": current_zip_sha256,
            "current_manifest_hash": current_manifest_hash,
        },
        blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS,
    )


def _accepted_evidence_public_document(evidence: dict[str, Any]) -> dict[str, Any]:
    return {"source_hash": evidence.get("source_hash"), "summary": accepted_evidence_summary(evidence), "public_summary": evidence.get("public_summary")}


def _response_public_summary(response: dict[str, Any]) -> dict[str, Any]:
    reviewer = response.get("reviewer") if isinstance(response.get("reviewer"), dict) else {}
    findings = response.get("findings") if isinstance(response.get("findings"), list) else []
    high = 0
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").lower()
        if severity in {"high", "critical"}:
            high += 1
    return sanitize_metadata(
        {
            "response_id": response.get("response_id"),
            "decision": response.get("decision"),
            "status": response.get("status"),
            "reviewer_label": reviewer.get("organization") or reviewer.get("name") or "external_reviewer",
            "reviewer_organization": reviewer.get("organization"),
            "reviewed_at": response.get("reviewed_at"),
            "rating": response.get("rating"),
            "finding_count": len(findings),
            "high_finding_count": high,
            "payload_hash": response.get("payload_hash"),
        },
        blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS,
    )


def _public_summary(source: dict[str, Any], response_public: dict[str, Any], status: str) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "external_review_status": status,
            "accepted_at": response_public.get("reviewed_at"),
            "reviewed_at": response_public.get("reviewed_at"),
            "reviewer_label": response_public.get("reviewer_label"),
            "response_id": response_public.get("response_id"),
            "current_certificate_id": source.get("current_certificate_id"),
            "registry_current_entry_id": source.get("registry_current_entry_id"),
            "verification_status": source.get("response_verification_status"),
            "reviewed_portal_zip_sha256": source.get("portal_zip_sha256"),
            "portal_source_hash": source.get("portal_source_hash"),
        },
        blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS,
    )


def _data_documents(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source = evidence.get("source") if isinstance(evidence.get("source"), dict) else {}
    public = evidence.get("public_summary") if isinstance(evidence.get("public_summary"), dict) else {}
    return {
        "response-verification-summary.json": {"source_hash": evidence.get("source_hash"), "response_id": source.get("response_id"), "decision": source.get("response_decision"), "response_status": source.get("response_status"), "verification_status": source.get("response_verification_status"), "verification_hash": source.get("response_verification_hash"), "payload_hash": source.get("response_payload_hash"), "integrity_hash": source.get("response_integrity_hash")},
        "review-pack-source-summary.json": {"source_hash": evidence.get("source_hash"), "review_pack_id": source.get("review_pack_id"), "review_pack_source_hash": source.get("review_pack_source_hash"), "response_review_pack_id": source.get("response_review_pack_id"), "response_review_pack_source_hash": source.get("response_review_pack_source_hash"), "review_pack_stale": source.get("review_pack_stale")},
        "portal-binding-summary.json": {"source_hash": evidence.get("source_hash"), "portal_zip_sha256": source.get("portal_zip_sha256"), "portal_zip_size_bytes": source.get("portal_zip_size_bytes"), "portal_manifest_hash": source.get("portal_manifest_hash"), "portal_verification_hash": source.get("portal_verification_hash"), "portal_verification_status": source.get("portal_verification_status"), "portal_source_hash": source.get("portal_source_hash")},
        "registry-binding-summary.json": {"source_hash": evidence.get("source_hash"), "registry_zip_sha256": source.get("registry_zip_sha256"), "registry_manifest_hash": source.get("registry_manifest_hash"), "registry_verification_hash": source.get("registry_verification_hash"), "registry_verification_status": source.get("registry_verification_status"), "current_entry_id": source.get("registry_current_entry_id"), "current_entry_hash": source.get("registry_current_entry_hash")},
        "attestation-binding-summary.json": {"source_hash": evidence.get("source_hash"), "current_certificate_id": source.get("current_certificate_id"), "attestation_zip_sha256": source.get("current_attestation_zip_sha256"), "attestation_manifest_hash": source.get("current_attestation_manifest_hash"), "attestation_verification_hash": source.get("current_attestation_verification_hash"), "attestation_verification_status": source.get("current_attestation_verification_status"), "evidence_vault_zip_sha256": source.get("evidence_vault_zip_sha256"), "evidence_vault_manifest_hash": source.get("evidence_vault_manifest_hash"), "evidence_vault_verification_hash": source.get("evidence_vault_verification_hash"), "evidence_vault_deep_verification_status": source.get("evidence_vault_deep_verification_status"), "final_board_signoff_hash": source.get("final_board_signoff_hash")},
        "external-review-public-summary.json": {"source_hash": evidence.get("source_hash"), **public},
    }


def _state_tuple(evidence: dict[str, Any]) -> dict[str, str]:
    return {"source_hash": str(evidence.get("source_hash") or ""), "accepted_evidence_id": str(evidence.get("accepted_evidence_id") or ""), "integrity_hash": str(evidence.get("integrity_hash") or "")}


def _manifest_state(manifest: dict[str, Any]) -> dict[str, str]:
    row = manifest.get("accepted_evidence") if isinstance(manifest.get("accepted_evidence"), dict) else {}
    return {"source_hash": str(manifest.get("source_hash") or ""), "accepted_evidence_id": str(row.get("accepted_evidence_id") or ""), "integrity_hash": str(row.get("integrity_hash") or "")}


def _source_stale_hash(source: dict[str, Any]) -> str:
    # Avoid the public-summary portal rebuild cycle: accepted evidence binds the
    # reviewed portal source and package verification status, not a later portal
    # ZIP that only adds this public summary.
    ignored = {"portal_zip_sha256", "portal_zip_size_bytes", "portal_manifest_hash", "portal_verification_hash"}
    return stable_hash({key: value for key, value in (source or {}).items() if key not in ignored})


def _evidence_id(portfolio_id: str, profile: str, source: dict[str, Any]) -> str:
    return f"apae-{stable_hash({'portfolio_id': portfolio_id, 'profile': profile, 'source': source})[:12]}"


def _readme(evidence: dict[str, Any]) -> str:
    public = evidence.get("public_summary") if isinstance(evidence.get("public_summary"), dict) else {}
    return "\n".join(
        [
            "MusicForge Public Attestation Accepted Evidence",
            "",
            f"Portfolio ID: {evidence.get('portfolio_id')}",
            f"Accepted Evidence ID: {evidence.get('accepted_evidence_id')}",
            f"External review status: {public.get('external_review_status') or evidence.get('status')}",
            "This package contains public-safe accepted review evidence summaries only.",
            "It does not contain the full response, notes, attachments, Portal ZIP, Registry ZIP, Attestation ZIP, or Evidence Vault ZIP.",
            "",
        ]
    )


def _file_record(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if path.is_file()]


def _read_json_default(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return value if isinstance(value, dict) else dict(default or {})


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_json(path, sanitize_metadata(payload, blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS))


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
        raise ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError("Resolved path escapes Accepted Evidence directory.") from exc


def _redaction_summary(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    matches = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            matches.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if matches else "passed", "matches": matches[:20]}


def _safe_profile(profile: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(profile or "public_summary"))[:80] or "public_summary"
