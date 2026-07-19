# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path

import base64 as base64
import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package as verify_unified_command_center_archive_package, write_unified_command_center_archive_verification_report as write_unified_command_center_archive_verification_report
from song_agent.domains.program.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore as UnifiedCommandCenterContinuousReviewStore
from song_agent.domains.program.unified_command_center_continuous_review_verifier import verify_unified_command_center_continuous_review_package as verify_unified_command_center_continuous_review_package, write_unified_command_center_continuous_review_verification_report as write_unified_command_center_continuous_review_verification_report
from song_agent.domains.program.unified_command_center_drift_response import UnifiedCommandCenterDriftResponseStore as UnifiedCommandCenterDriftResponseStore
from song_agent.domains.program.unified_command_center_drift_response_verifier import verify_unified_command_center_drift_response_package as verify_unified_command_center_drift_response_package, write_unified_command_center_drift_response_verification_report as write_unified_command_center_drift_response_verification_report
from song_agent.domains.program.unified_command_center_evidence_review_verifier import ACCEPTANCE_REQUIRED_ENTRIES as ACCEPTANCE_REQUIRED_ENTRIES, REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION, verify_unified_command_center_evidence_review_acceptance_package as verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package as verify_unified_command_center_evidence_review_package, write_unified_command_center_evidence_review_acceptance_verification_report as write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report as write_unified_command_center_evidence_review_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore as UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package, write_unified_command_center_handoff_verification_report as write_unified_command_center_handoff_verification_report
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore as UnifiedCommandCenterSignoffStore
from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package as verify_unified_command_center_package, write_unified_command_center_verification_report as write_unified_command_center_verification_report


from song_agent.domains.program import v142_uccer_readiness as _v142_uccer_readiness
from song_agent.domains.program.v142_uccer_readiness import (
    UnifiedCommandCenterEvidenceReviewError,
    UnifiedCommandCenterEvidenceReviewNotFoundError,
    UnifiedCommandCenterEvidenceReviewStateError,
    _source_document,
    _evidence_index_document,
    _proof_index_document,
    _replay_plan_document,
    _empty_replay_document,
    _run_replay_document,
    _narrative_document,
    _checklist_document,
    _manifest_document,
    _reviewer_guide,
    _review_verifier_kwargs,
    _summary_from_path,
    _generic_report,
    _release_check_result,
    _public_reviewer,
    _findings,
    _public_response,
    _response_verification_summary,
    _response_binding_summary,
    _read_optional_json,
    _path_or_none,
    _integrity_hash,
    _integrity_from_path,
    _integrity_or_stable,
    _sha256_path,
    _zip_manifest_hash,
    _safe_id,
)







class UnifiedCommandCenterEvidenceReviewStore:
    def __init__(
        self,
        center_store: UnifiedCommandCenterStore | None = None,
        *,
        signoff_store: UnifiedCommandCenterSignoffStore | None = None,
        handoff_store: UnifiedCommandCenterHandoffStore | None = None,
        review_store: UnifiedCommandCenterContinuousReviewStore | None = None,
        drift_response_store: UnifiedCommandCenterDriftResponseStore | None = None,
    ) -> None:
        self.center_store = center_store or UnifiedCommandCenterStore()
        self.signoff_store = signoff_store or UnifiedCommandCenterSignoffStore(self.center_store)
        self.handoff_store = handoff_store or UnifiedCommandCenterHandoffStore(self.signoff_store)
        self.review_store = review_store or UnifiedCommandCenterContinuousReviewStore(self.center_store, signoff_store=self.signoff_store, handoff_store=self.handoff_store)
        self.drift_response_store = drift_response_store or UnifiedCommandCenterDriftResponseStore(self.center_store, signoff_store=self.signoff_store, handoff_store=self.handoff_store, review_store=self.review_store)
        self.lock = threading.RLock()

    def reviews_dir(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "evidence-reviews"

    def review_dir(self, center_id: str, review_id: str) -> Path:
        return self.reviews_dir(center_id) / _safe_id(review_id)

    def export_dir(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "export"

    def local_paths_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "local-paths.json"

    def source_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "review-source.json"

    def evidence_index_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "evidence-index.json"

    def proof_index_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "external-proof-index.json"

    def replay_plan_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "replay-plan.json"

    def replay_result_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "replay-result.json"

    def narrative_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "evidence-narrative.json"

    def checklist_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "manual-checklist.json"

    def guide_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "reviewer-guide.md"

    def manifest_path(self, center_id: str, review_id: str) -> Path:
        return self.export_dir(center_id, review_id) / "manifest.json"

    def zip_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "evidence-review.zip"

    def verification_report_path(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "verification-report.json"

    def response_dir(self, center_id: str, review_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "review-responses"

    def accepted_evidence_dir(self, center_id: str, review_id: str, evidence_id: str) -> Path:
        return self.review_dir(center_id, review_id) / "accepted-evidence" / _safe_id(evidence_id)

    def accepted_evidence_zip_path(self, center_id: str, review_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(center_id, review_id, evidence_id) / "evidence-acceptance.zip"

    def accepted_evidence_verification_report_path(self, center_id: str, review_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(center_id, review_id, evidence_id) / "acceptance-verification-report.json"

    def list_reviews(self, center_id: str) -> list[DomainDocument]:
        if not self.reviews_dir(center_id).exists():
            return []
        rows = []
        for path in sorted(self.reviews_dir(center_id).glob("uccer-*")):
            source_path = path / "review-source.json"
            if source_path.exists():
                rows.append(read_json(source_path))
        return rows

    def get_review(self, center_id: str, review_id: str) -> DomainDocument:
        if not self.source_path(center_id, review_id).exists():
            raise UnifiedCommandCenterEvidenceReviewNotFoundError(f"Unified Command Center Evidence Review not found: {review_id}.")
        docs: ImplementationDocument = {
            "source": read_json(self.source_path(center_id, review_id)),
            "evidence_index": _read_optional_json(self.evidence_index_path(center_id, review_id)),
            "external_proof_index": _read_optional_json(self.proof_index_path(center_id, review_id)),
            "replay_plan": _read_optional_json(self.replay_plan_path(center_id, review_id)),
            "replay_result": _read_optional_json(self.replay_result_path(center_id, review_id)),
            "evidence_narrative": _read_optional_json(self.narrative_path(center_id, review_id)),
            "manual_checklist": _read_optional_json(self.checklist_path(center_id, review_id)),
            "verification": _read_optional_json(self.verification_report_path(center_id, review_id)),
            "manifest": _read_optional_json(self.manifest_path(center_id, review_id)),
            "responses": self.list_responses(center_id, review_id),
        }
        return docs

    def create_review(self, center_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            review_id = str(payload.get("review_id") or self._next_review_id(center_id))
            if self.source_path(center_id, review_id).exists():
                raise UnifiedCommandCenterEvidenceReviewStateError(f"Evidence Review already exists: {review_id}.")
            self.review_dir(center_id, review_id).mkdir(parents=True, exist_ok=True)
            local_paths = self._local_paths(center_id, review_id, payload)
            docs = self._build_documents(center_id, review_id, local_paths, replay=False)
            self._write_docs(center_id, review_id, docs)
            write_json(self.local_paths_path(center_id, review_id), local_paths)
            return docs

    def refresh_review(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            current = self.get_review(center_id, review_id)["source"]
            if current.get("status") in {"accepted", "archived"}:
                raise UnifiedCommandCenterEvidenceReviewStateError("Accepted Evidence Review cannot be refreshed.")
            local_paths = self._merged_local_paths(center_id, review_id, payload)
            docs = self._build_documents(center_id, review_id, local_paths, replay=False)
            self._write_docs(center_id, review_id, docs)
            write_json(self.local_paths_path(center_id, review_id), local_paths)
            return docs

    def run_replay(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            local_paths = self._merged_local_paths(center_id, review_id, payload)
            docs = self._build_documents(center_id, review_id, local_paths, replay=True)
            self._write_docs(center_id, review_id, docs)
            write_json(self.local_paths_path(center_id, review_id), local_paths)
            return docs["replay_result"]

    def export_review(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self._ensure_not_stale(center_id, review_id, payload)
            docs = self.get_review(center_id, review_id)
            if docs["replay_result"].get("status") != "passed":
                raise UnifiedCommandCenterEvidenceReviewStateError("Evidence Review replay must pass before export.")
            export_dir = self.export_dir(center_id, review_id)
            export_dir.mkdir(parents=True, exist_ok=True)
            files = {
                "review-source.json": docs["source"],
                "evidence-index.json": docs["evidence_index"],
                "external-proof-index.json": docs["external_proof_index"],
                "replay-plan.json": docs["replay_plan"],
                "replay-result.json": docs["replay_result"],
                "evidence-narrative.json": docs["evidence_narrative"],
                "manual-checklist.json": docs["manual_checklist"],
            }
            summaries = self._verification_summaries(center_id, review_id, self._merged_local_paths(center_id, review_id, payload))
            proofs = self._proof_summaries(center_id, review_id, self._merged_local_paths(center_id, review_id, payload))
            for rel, doc in files.items():
                write_json(export_dir / rel, doc)
            for rel, doc in summaries.items():
                write_json(export_dir / "verification-summaries" / rel, doc)
            for rel, doc in proofs.items():
                write_json(export_dir / "proof-summaries" / rel, doc)
            (export_dir / "reviewer-guide.md").write_text(_reviewer_guide(docs), encoding="utf-8")
            (export_dir / "README.txt").write_text("MusicForge Unified Command Center Evidence Review Pack\n", encoding="utf-8")
            manifest = _manifest_document(center_id, review_id, docs["source"], export_dir, REQUIRED_ENTRIES, docs["replay_result"].get("status"))
            manifest.setdefault("source", {}).update(
                {
                    "evidence_index_hash": docs["evidence_index"].get("integrity_hash"),
                    "external_proof_index_hash": docs["external_proof_index"].get("integrity_hash"),
                    "replay_plan_hash": docs["replay_plan"].get("integrity_hash"),
                    "replay_result_hash": docs["replay_result"].get("integrity_hash"),
                }
            )
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["replay_result"].get("status"), "export_dir": str(export_dir), "manifest_hash": manifest.get("integrity_hash")}

    def build_zip(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.export_review(center_id, review_id, payload)
            zip_path = self.zip_path(center_id, review_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for rel in sorted(REQUIRED_ENTRIES):
                    archive.write(self.export_dir(center_id, review_id) / rel, rel)
            report = self.verify_zip(center_id, review_id, payload)
            return {"status": report.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "verification_report": str(self.verification_report_path(center_id, review_id))}

    def verify_zip(self, center_id: str, review_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        local_paths = self._merged_local_paths(center_id, review_id, payload)
        report = verify_unified_command_center_evidence_review_package(
            self.zip_path(center_id, review_id),
            strict=bool(payload.get("strict", True)),
            require_replay_passed=bool(payload.get("require_replay_passed", True)),
            **_review_verifier_kwargs(local_paths),
        )
        write_unified_command_center_evidence_review_verification_report(report, self.verification_report_path(center_id, review_id))
        return report

    def list_responses(self, center_id: str, review_id: str) -> list[DomainDocument]:
        if not self.response_dir(center_id, review_id).exists():
            return []
        return [read_json(path) for path in sorted(self.response_dir(center_id, review_id).glob("*.json"))]

    def import_response(self, center_id: str, review_id: str, payload: DomainDocument) -> DomainDocument:
        if any(key in payload for key in {"source_path", "local_path", "file_path"}):
            raise UnifiedCommandCenterEvidenceReviewStateError("Review response import does not accept local file paths.")
        response = payload.get("response") if isinstance(payload.get("response"), dict) else None
        if response is None and payload.get("response_base64"):
            response = json.loads(base64.b64decode(str(payload["response_base64"])).decode("utf-8"))
        if response is None:
            response = payload
        response = sanitize_metadata(response)
        required = ["review_pack_id", "review_pack_zip_sha256", "review_pack_manifest_hash", "review_pack_source_hash", "replay_result_hash", "result"]
        missing = [key for key in required if not response.get(key)]
        if missing:
            raise UnifiedCommandCenterEvidenceReviewStateError(f"Review response missing required binding fields: {', '.join(missing)}.")
        source = self.get_review(center_id, review_id)["source"]
        replay = read_json(self.replay_result_path(center_id, review_id))
        manifest = read_json(self.manifest_path(center_id, review_id)) if self.manifest_path(center_id, review_id).exists() else {}
        expected = {
            "review_pack_id": review_id,
            "review_pack_zip_sha256": _sha256_path(self.zip_path(center_id, review_id)),
            "review_pack_manifest_hash": manifest.get("integrity_hash"),
            "review_pack_source_hash": source.get("source_hash"),
            "replay_result_hash": replay.get("integrity_hash"),
        }
        status = "current" if all(response.get(key) == value for key, value in expected.items()) else "stale"
        response_id = str(response.get("response_id") or self._next_response_id(center_id, review_id))
        result = str(response.get("result"))
        response_doc = {
            "schema_version": UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_evidence_review_response",
            "center_id": center_id,
            "review_id": review_id,
            "response_id": response_id,
            "status": status,
            "result": result,
            "reviewer": _public_reviewer(_as_document(response.get("reviewer"))),
            "findings": _findings(response.get("findings")),
            "signed_at": sanitize_sensitive_text(str(response.get("signed_at") or now_iso())),
            "bindings": expected,
            "payload": response,
        }
        response_doc["payload_hash"] = stable_hash(response)
        response_doc["integrity_hash"] = _integrity_hash(response_doc)
        self.response_dir(center_id, review_id).mkdir(parents=True, exist_ok=True)
        write_json(self.response_dir(center_id, review_id) / f"{response_id}.json", response_doc)
        if result in {"needs_changes", "rejected"}:
            self._write_change_request_draft(center_id, review_id, response_doc)
        return response_doc

    def create_acceptance_evidence(self, center_id: str, review_id: str, response_id: str) -> DomainDocument:
        response_path = self.response_dir(center_id, review_id) / f"{_safe_id(response_id)}.json"
        if not response_path.exists():
            raise UnifiedCommandCenterEvidenceReviewNotFoundError(f"Review response not found: {response_id}.")
        response = read_json(response_path)
        if response.get("result") != "accepted" or response.get("status") != "current":
            raise UnifiedCommandCenterEvidenceReviewStateError("Only current accepted review responses can create acceptance evidence.")
        self._ensure_not_stale(center_id, review_id, {})
        evidence_id = self._next_evidence_id(center_id, review_id)
        evidence_dir = self.accepted_evidence_dir(center_id, review_id, evidence_id)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        public_response = _public_response(response)
        response_verification = _response_verification_summary(response, public_response)
        binding_summary = _response_binding_summary(response)
        report = {
            "schema_version": UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_evidence_review_acceptance_report",
            "center_id": center_id,
            "review_id": review_id,
            "response_id": response_id,
            "evidence_id": evidence_id,
            "result": "accepted",
            "created_at": now_iso(),
            "review_pack_zip_sha256": response.get("bindings", {}).get("review_pack_zip_sha256"),
            "review_pack_manifest_hash": response.get("bindings", {}).get("review_pack_manifest_hash"),
            "review_pack_source_hash": response.get("bindings", {}).get("review_pack_source_hash"),
            "response_public_hash": public_response.get("integrity_hash"),
            "response_payload_hash": response.get("payload_hash"),
            "reviewer": public_response.get("reviewer"),
        }
        report["integrity_hash"] = _integrity_hash(report)
        for rel, doc in (
            ("acceptance-report.json", report),
            ("original-response-public.json", public_response),
            ("response-verification-summary.json", response_verification),
            ("original-response-binding-summary.json", binding_summary),
        ):
            write_json(evidence_dir / rel, doc)
        (evidence_dir / "README.txt").write_text("MusicForge Evidence Review Acceptance Evidence\n", encoding="utf-8")
        manifest = _manifest_document(center_id, review_id, {"source_hash": response.get("bindings", {}).get("review_pack_source_hash"), "integrity_hash": report.get("integrity_hash")}, evidence_dir, ACCEPTANCE_REQUIRED_ENTRIES, "accepted", package_type=UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE, evidence_id=evidence_id)
        manifest.setdefault("source", {})["acceptance_report_hash"] = report.get("integrity_hash")
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(evidence_dir / "manifest.json", manifest)
        zip_path = self.accepted_evidence_zip_path(center_id, review_id, evidence_id)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for rel in sorted(ACCEPTANCE_REQUIRED_ENTRIES):
                archive.write(evidence_dir / rel, rel)
        verification = self.verify_acceptance_evidence(center_id, review_id, evidence_id)
        return {"status": verification.get("status"), "evidence_id": evidence_id, "zip_path": str(zip_path), "verification_report": str(self.accepted_evidence_verification_report_path(center_id, review_id, evidence_id))}

    def verify_acceptance_evidence(self, center_id: str, review_id: str, evidence_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        response_verification = self.accepted_evidence_dir(center_id, review_id, evidence_id) / "response-verification-summary.json"
        report = verify_unified_command_center_evidence_review_acceptance_package(
            self.accepted_evidence_zip_path(center_id, review_id, evidence_id),
            strict=bool(payload.get("strict", True)),
            require_accepted=bool(payload.get("require_accepted", True)),
            review_pack_path=payload.get("review_pack") or self.zip_path(center_id, review_id),
            review_pack_verification_report_path=payload.get("review_pack_verification_report") or self.verification_report_path(center_id, review_id),
            response_verification_report_path=payload.get("response_verification_report") or response_verification,
        )
        write_unified_command_center_evidence_review_acceptance_verification_report(report, self.accepted_evidence_verification_report_path(center_id, review_id, evidence_id))
        return report

    def gate(
        self,
        center_id: str,
        *,
        required: bool = False,
        review_id: str | None = None,
        review_zip_path: Path | str | None = None,
        review_verification_report_path: Path | str | None = None,
        require_accepted: bool = False,
        acceptance_zip_path: Path | str | None = None,
        acceptance_verification_report_path: Path | str | None = None,
        acceptance_response_verification_report_path: Path | str | None = None,
        payload: DomainDocument | None = None,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        payload = payload or {}
        try:
            if review_id and not review_zip_path:
                review_zip_path = self.zip_path(center_id, review_id)
            if review_id and not review_verification_report_path:
                review_verification_report_path = self.verification_report_path(center_id, review_id)
            if not review_zip_path or not review_verification_report_path:
                return {"status": "failed", "hard_block": True, "message": "Unified Command Center Evidence Review evidence is missing."}
            verification = read_json(Path(review_verification_report_path))
            runtime = verify_unified_command_center_evidence_review_package(review_zip_path, strict=True, require_replay_passed=True, **_review_verifier_kwargs(self._merged_local_paths(center_id, review_id, payload) if review_id else payload))
            if verification.get("status") != "passed" or runtime.get("status") != "passed":
                return {"status": "failed", "hard_block": True, "message": "Unified Command Center Evidence Review verification failed.", "verification": runtime}
            if require_accepted:
                if not acceptance_zip_path or not acceptance_verification_report_path or not acceptance_response_verification_report_path:
                    return {"status": "failed", "hard_block": True, "message": "Evidence Review accepted response evidence is missing."}
                runtime_accepted = verify_unified_command_center_evidence_review_acceptance_package(
                    acceptance_zip_path,
                    strict=True,
                    require_accepted=True,
                    review_pack_path=review_zip_path,
                    review_pack_verification_report_path=review_verification_report_path,
                    response_verification_report_path=acceptance_response_verification_report_path,
                )
                accepted = read_json(Path(acceptance_verification_report_path))
                if (
                    accepted.get("status") != "passed"
                    or runtime_accepted.get("status") != "passed"
                    or accepted.get("zip_sha256") != runtime_accepted.get("zip_sha256")
                    or accepted.get("manifest_hash") != runtime_accepted.get("manifest_hash")
                ):
                    return {"status": "failed", "hard_block": True, "message": "Evidence Review acceptance evidence verification failed.", "verification": runtime_accepted}
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Evidence Review gate passed."}
        except (OSError, ValueError, UnifiedCommandCenterEvidenceReviewError) as exc:
            return {"status": "failed", "hard_block": True, "message": sanitize_sensitive_text(str(exc))}

    def _local_paths(self, center_id: str, review_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        continuous_review_id = str(payload.get("continuous_review_id") or payload.get("source_review_id") or "")
        if not continuous_review_id:
            reviews = self.review_store.list_reviews(center_id)
            continuous_review_id = str((reviews[-1] if reviews else {}).get("review_id") or "")
        drift_response_id = str(payload.get("drift_response_id") or payload.get("response_id") or "")
        if not drift_response_id:
            responses = self.drift_response_store.list_responses(center_id)
            drift_response_id = str((responses[-1] if responses else {}).get("response_id") or "")
        recheck_review_id = str(payload.get("recheck_review_id") or "")
        if drift_response_id:
            recheck_doc = _read_optional_json(self.drift_response_store.recheck_path(center_id, drift_response_id))
            recheck_review_id = recheck_review_id or str((recheck_doc.get("review") or {}).get("review_id") or "")
        paths = {
            "review_id": review_id,
            "ucc_zip": str(payload.get("ucc_zip") or payload.get("unified_command_center") or payload.get("unified_command_center_zip") or self.center_store.zip_path(center_id)),
            "ucc_verification_report": str(payload.get("ucc_verification_report") or payload.get("unified_command_center_verification_report") or self.center_store.verification_report_path(center_id)),
            "archive_zip": str(payload.get("archive_zip") or payload.get("archive") or payload.get("unified_command_center_archive") or payload.get("unified_command_center_archive_zip") or self.signoff_store.archive_zip_path(center_id)),
            "archive_verification_report": str(payload.get("archive_verification_report") or self.signoff_store.archive_verification_report_path(center_id)),
            "handoff_zip": str(payload.get("handoff_zip") or payload.get("handoff") or payload.get("unified_command_center_handoff") or payload.get("unified_command_center_handoff_zip") or self.handoff_store.zip_path(center_id)),
            "handoff_verification_report": str(payload.get("handoff_verification_report") or self.handoff_store.verification_report_path(center_id)),
            "signoff_binding": str(payload.get("signoff_binding") or self.signoff_store.signoff_binding_path(center_id)),
            "continuous_review_id": continuous_review_id,
            "continuous_review_zip": str(payload.get("continuous_review_zip") or payload.get("continuous_review") or (self.review_store.zip_path(center_id, continuous_review_id) if continuous_review_id else "")),
            "continuous_review_verification_report": str(payload.get("continuous_review_verification_report") or (self.review_store.verification_report_path(center_id, continuous_review_id) if continuous_review_id else "")),
            "drift_response_id": drift_response_id,
            "drift_response_zip": str(payload.get("drift_response_zip") or payload.get("drift_response") or (self.drift_response_store.zip_path(center_id, drift_response_id) if drift_response_id else "")),
            "drift_response_verification_report": str(payload.get("drift_response_verification_report") or (self.drift_response_store.verification_report_path(center_id, drift_response_id) if drift_response_id else "")),
            "drift_change_request_binding_report": str(payload.get("drift_change_request_binding_report") or payload.get("change_request_binding_report") or (self.drift_response_store.cr_binding_report_path(center_id, drift_response_id) if drift_response_id else "")),
            "source_review_zip": str(payload.get("source_review_zip") or payload.get("source_review") or (self.review_store.zip_path(center_id, continuous_review_id) if continuous_review_id else "")),
            "source_review_verification_report": str(payload.get("source_review_verification_report") or (self.review_store.verification_report_path(center_id, continuous_review_id) if continuous_review_id else "")),
            "recheck_review_id": recheck_review_id,
            "recheck_review_zip": str(payload.get("recheck_review_zip") or payload.get("recheck_review") or (self.review_store.zip_path(center_id, recheck_review_id) if recheck_review_id else "")),
            "recheck_review_verification_report": str(payload.get("recheck_review_verification_report") or (self.review_store.verification_report_path(center_id, recheck_review_id) if recheck_review_id else "")),
            "ga_readiness_report": str(payload.get("ga_readiness_report") or ""),
            "release_check_report": str(payload.get("release_check_report") or ""),
        }
        return paths

    def _merged_local_paths(self, center_id: str, review_id: str | None, payload: ImplementationDocument) -> ImplementationDocument:
        if review_id and self.local_paths_path(center_id, review_id).exists():
            paths = read_json(self.local_paths_path(center_id, review_id))
            for key, value in self._local_paths(center_id, review_id, payload).items():
                if value:
                    paths[key] = value
            return paths
        return self._local_paths(center_id, review_id or str(payload.get("review_id") or ""), payload)

    def _build_documents(self, center_id: str, review_id: str, local_paths: ImplementationDocument, *, replay: bool) -> ImplementationDocument:
        now = now_iso()
        source = _source_document(center_id, review_id, local_paths, now)
        evidence_index = _evidence_index_document(center_id, review_id, source)
        proof_index = _proof_index_document(center_id, review_id, source)
        replay_plan = _replay_plan_document(center_id, review_id, source)
        replay_result = _run_replay_document(center_id, review_id, source, replay_plan, local_paths) if replay else _empty_replay_document(center_id, review_id, source, replay_plan)
        narrative = _narrative_document(center_id, review_id, source, replay_result)
        checklist = _checklist_document(center_id, review_id, source)
        return {
            "source": source,
            "evidence_index": evidence_index,
            "external_proof_index": proof_index,
            "replay_plan": replay_plan,
            "replay_result": replay_result,
            "evidence_narrative": narrative,
            "manual_checklist": checklist,
        }

    def _write_docs(self, center_id: str, review_id: str, docs: ImplementationDocument) -> None:
        for key, path in (
            ("source", self.source_path(center_id, review_id)),
            ("evidence_index", self.evidence_index_path(center_id, review_id)),
            ("external_proof_index", self.proof_index_path(center_id, review_id)),
            ("replay_plan", self.replay_plan_path(center_id, review_id)),
            ("replay_result", self.replay_result_path(center_id, review_id)),
            ("evidence_narrative", self.narrative_path(center_id, review_id)),
            ("manual_checklist", self.checklist_path(center_id, review_id)),
        ):
            write_json(path, docs[key])
        self.guide_path(center_id, review_id).write_text(_reviewer_guide(docs), encoding="utf-8")

    def _verification_summaries(self, center_id: str, review_id: str, paths: ImplementationDocument) -> dict[str, ImplementationDocument]:
        del center_id, review_id
        return {
            "ucc.json": _summary_from_path(paths.get("ucc_verification_report"), "ucc"),
            "ucc-archive.json": _summary_from_path(paths.get("archive_verification_report"), "ucc-archive"),
            "ucc-handoff.json": _summary_from_path(paths.get("handoff_verification_report"), "ucc-handoff"),
            "continuous-review.json": _summary_from_path(paths.get("continuous_review_verification_report"), "continuous-review"),
            "drift-response.json": _summary_from_path(paths.get("drift_response_verification_report"), "drift-response"),
            "ga-readiness.json": _summary_from_path(paths.get("ga_readiness_report"), "ga-readiness"),
            "release-check.json": _summary_from_path(paths.get("release_check_report"), "release-check"),
        }

    def _proof_summaries(self, center_id: str, review_id: str, paths: ImplementationDocument) -> dict[str, ImplementationDocument]:
        del center_id, review_id
        return {
            "signoff-binding-summary.json": _summary_from_path(paths.get("signoff_binding"), "signoff-binding"),
            "change-request-binding-report.json": _summary_from_path(paths.get("drift_change_request_binding_report"), "cr-binding-report"),
        }

    def _ensure_not_stale(self, center_id: str, review_id: str, payload: ImplementationDocument) -> None:
        current = self.get_review(center_id, review_id)["source"]
        paths = self._merged_local_paths(center_id, review_id, payload)
        rebuilt = _source_document(center_id, review_id, paths, str(current.get("created_at") or now_iso()))
        if rebuilt.get("source_hash") != current.get("source_hash"):
            raise UnifiedCommandCenterEvidenceReviewStateError("Evidence Review source is stale. Refresh and replay before export.")

    def _next_review_id(self, center_id: str) -> str:
        existing = [path.name for path in self.reviews_dir(center_id).glob("uccer-*")] if self.reviews_dir(center_id).exists() else []
        return f"uccer-{len(existing) + 1:06d}"

    def _next_response_id(self, center_id: str, review_id: str) -> str:
        existing = list(self.response_dir(center_id, review_id).glob("*.json")) if self.response_dir(center_id, review_id).exists() else []
        return f"uccerr-{len(existing) + 1:06d}"

    def _next_evidence_id(self, center_id: str, review_id: str) -> str:
        root = self.review_dir(center_id, review_id) / "accepted-evidence"
        existing = [path.name for path in root.glob("uccera-*")] if root.exists() else []
        return f"uccera-{len(existing) + 1:06d}"

    def _write_change_request_draft(self, center_id: str, review_id: str, response: ImplementationDocument) -> None:
        path = self.review_dir(center_id, review_id) / "change-request-drafts.json"
        doc = _read_optional_json(path) or {"package_type": "musicforge_unified_command_center_evidence_review_change_request_drafts", "items": []}
        for finding in response.get("findings", []):
            doc.setdefault("items", []).append({"draft_id": f"crdraft-{len(doc.get('items', [])) + 1:06d}", "response_id": response.get("response_id"), "severity": finding.get("severity"), "component": finding.get("component"), "message": finding.get("message"), "status": "draft"})
        doc["integrity_hash"] = _integrity_hash(doc)
        write_json(path, doc)

_v142_uccer_readiness.bind_globals(globals())
