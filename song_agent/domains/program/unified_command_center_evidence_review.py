from __future__ import annotations

import base64
import json
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.projects import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package, write_unified_command_center_archive_verification_report
from song_agent.domains.program.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore
from song_agent.domains.program.unified_command_center_continuous_review_verifier import verify_unified_command_center_continuous_review_package, write_unified_command_center_continuous_review_verification_report
from song_agent.domains.program.unified_command_center_drift_response import UnifiedCommandCenterDriftResponseStore
from song_agent.domains.program.unified_command_center_drift_response_verifier import verify_unified_command_center_drift_response_package, write_unified_command_center_drift_response_verification_report
from song_agent.domains.program.unified_command_center_evidence_review_verifier import ACCEPTANCE_REQUIRED_ENTRIES, REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package, write_unified_command_center_handoff_verification_report
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore
from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package, write_unified_command_center_verification_report


class UnifiedCommandCenterEvidenceReviewError(ValueError):
    pass


class UnifiedCommandCenterEvidenceReviewNotFoundError(UnifiedCommandCenterEvidenceReviewError):
    pass


class UnifiedCommandCenterEvidenceReviewStateError(UnifiedCommandCenterEvidenceReviewError):
    pass


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

    def list_reviews(self, center_id: str) -> list[dict[str, Any]]:
        if not self.reviews_dir(center_id).exists():
            return []
        rows = []
        for path in sorted(self.reviews_dir(center_id).glob("uccer-*")):
            source_path = path / "review-source.json"
            if source_path.exists():
                rows.append(read_json(source_path))
        return rows

    def get_review(self, center_id: str, review_id: str) -> dict[str, Any]:
        if not self.source_path(center_id, review_id).exists():
            raise UnifiedCommandCenterEvidenceReviewNotFoundError(f"Unified Command Center Evidence Review not found: {review_id}.")
        docs: dict[str, Any] = {
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

    def create_review(self, center_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def refresh_review(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def run_replay(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            local_paths = self._merged_local_paths(center_id, review_id, payload)
            docs = self._build_documents(center_id, review_id, local_paths, replay=True)
            self._write_docs(center_id, review_id, docs)
            write_json(self.local_paths_path(center_id, review_id), local_paths)
            return docs["replay_result"]

    def export_review(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def build_zip(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_zip(self, center_id: str, review_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def list_responses(self, center_id: str, review_id: str) -> list[dict[str, Any]]:
        if not self.response_dir(center_id, review_id).exists():
            return []
        return [read_json(path) for path in sorted(self.response_dir(center_id, review_id).glob("*.json"))]

    def import_response(self, center_id: str, review_id: str, payload: dict[str, Any]) -> dict[str, Any]:
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
            "reviewer": _public_reviewer(response.get("reviewer") if isinstance(response.get("reviewer"), dict) else {}),
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

    def create_acceptance_evidence(self, center_id: str, review_id: str, response_id: str) -> dict[str, Any]:
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

    def verify_acceptance_evidence(self, center_id: str, review_id: str, evidence_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

    def _local_paths(self, center_id: str, review_id: str, payload: dict[str, Any]) -> dict[str, Any]:
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

    def _merged_local_paths(self, center_id: str, review_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        if review_id and self.local_paths_path(center_id, review_id).exists():
            paths = read_json(self.local_paths_path(center_id, review_id))
            for key, value in self._local_paths(center_id, review_id, payload).items():
                if value:
                    paths[key] = value
            return paths
        return self._local_paths(center_id, review_id or str(payload.get("review_id") or ""), payload)

    def _build_documents(self, center_id: str, review_id: str, local_paths: dict[str, Any], *, replay: bool) -> dict[str, Any]:
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

    def _write_docs(self, center_id: str, review_id: str, docs: dict[str, Any]) -> None:
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

    def _verification_summaries(self, center_id: str, review_id: str, paths: dict[str, Any]) -> dict[str, dict[str, Any]]:
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

    def _proof_summaries(self, center_id: str, review_id: str, paths: dict[str, Any]) -> dict[str, dict[str, Any]]:
        del center_id, review_id
        return {
            "signoff-binding-summary.json": _summary_from_path(paths.get("signoff_binding"), "signoff-binding"),
            "change-request-binding-report.json": _summary_from_path(paths.get("drift_change_request_binding_report"), "cr-binding-report"),
        }

    def _ensure_not_stale(self, center_id: str, review_id: str, payload: dict[str, Any]) -> None:
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

    def _write_change_request_draft(self, center_id: str, review_id: str, response: dict[str, Any]) -> None:
        path = self.review_dir(center_id, review_id) / "change-request-drafts.json"
        doc = _read_optional_json(path) or {"package_type": "musicforge_unified_command_center_evidence_review_change_request_drafts", "items": []}
        for finding in response.get("findings", []):
            doc.setdefault("items", []).append({"draft_id": f"crdraft-{len(doc.get('items', [])) + 1:06d}", "response_id": response.get("response_id"), "severity": finding.get("severity"), "component": finding.get("component"), "message": finding.get("message"), "status": "draft"})
        doc["integrity_hash"] = _integrity_hash(doc)
        write_json(path, doc)


def _source_document(center_id: str, review_id: str, paths: dict[str, Any], created_at: str) -> dict[str, Any]:
    source = {
        "ucc_zip_sha256": _sha256_path(paths.get("ucc_zip")),
        "ucc_manifest_hash": _zip_manifest_hash(paths.get("ucc_zip")),
        "ucc_verification_hash": _integrity_from_path(paths.get("ucc_verification_report")),
        "archive_zip_sha256": _sha256_path(paths.get("archive_zip")),
        "archive_manifest_hash": _zip_manifest_hash(paths.get("archive_zip")),
        "archive_verification_hash": _integrity_from_path(paths.get("archive_verification_report")),
        "handoff_zip_sha256": _sha256_path(paths.get("handoff_zip")),
        "handoff_manifest_hash": _zip_manifest_hash(paths.get("handoff_zip")),
        "handoff_verification_hash": _integrity_from_path(paths.get("handoff_verification_report")),
        "continuous_review_zip_sha256": _sha256_path(paths.get("continuous_review_zip")),
        "continuous_review_manifest_hash": _zip_manifest_hash(paths.get("continuous_review_zip")),
        "continuous_review_verification_hash": _integrity_from_path(paths.get("continuous_review_verification_report")),
        "drift_response_zip_sha256": _sha256_path(paths.get("drift_response_zip")),
        "drift_response_manifest_hash": _zip_manifest_hash(paths.get("drift_response_zip")),
        "drift_response_verification_hash": _integrity_from_path(paths.get("drift_response_verification_report")),
        "cr_binding_report_hash": _integrity_from_path(paths.get("drift_change_request_binding_report")),
        "ga_report_hash": _integrity_from_path(paths.get("ga_readiness_report")),
        "release_check_report_hash": _integrity_from_path(paths.get("release_check_report")),
    }
    status = "draft"
    doc = {
        "schema_version": UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION,
        "package_type": "musicforge_unified_command_center_evidence_review_source",
        "center_id": center_id,
        "review_id": review_id,
        "created_at": created_at,
        "status": status,
        "source": source,
    }
    doc["source_hash"] = stable_hash(source)
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _evidence_index_document(center_id: str, review_id: str, source: dict[str, Any]) -> dict[str, Any]:
    source_map = source.get("source", {})
    items = []
    for component, prefix, required in (
        ("unified_command_center", "ucc", True),
        ("unified_command_center_archive", "archive", True),
        ("unified_command_center_handoff", "handoff", True),
        ("continuous_review", "continuous_review", True),
        ("drift_response", "drift_response", bool(source_map.get("drift_response_zip_sha256"))),
        ("ga_readiness", "ga", bool(source_map.get("ga_report_hash"))),
        ("release_check", "release_check", bool(source_map.get("release_check_report_hash"))),
    ):
        verification_hash = source_map.get(f"{prefix}_verification_hash") if prefix not in {"ga", "release_check"} else source_map.get(f"{prefix}_report_hash")
        status = "passed" if verification_hash else "missing"
        items.append({"component_type": component, "component_id": center_id if component.startswith("unified") else review_id, "role": "root" if component == "unified_command_center" else "supporting", "required": required, "verification_hash": verification_hash, "verification_status": status, "runtime_status": "pending", "external_report_required": required})
    summary = {"required_count": len([row for row in items if row.get("required")]), "passed_count": len([row for row in items if row.get("verification_status") == "passed"]), "failed_count": len([row for row in items if row.get("required") and row.get("verification_status") != "passed"]), "manual_review_count": 1}
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_index", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "items": items, "summary": summary}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _proof_index_document(center_id: str, review_id: str, source: dict[str, Any]) -> dict[str, Any]:
    source_map = source.get("source", {})
    proofs = []
    if source_map.get("cr_binding_report_hash"):
        proofs.append({"proof_type": "cr_binding_report", "component_type": "drift_response", "component_id": review_id, "proof_hash": source_map.get("cr_binding_report_hash")})
    if source_map.get("ucc_verification_hash"):
        proofs.append({"proof_type": "verification_report", "component_type": "unified_command_center", "component_id": center_id, "proof_hash": source_map.get("ucc_verification_hash")})
    if source_map.get("archive_verification_hash"):
        proofs.append({"proof_type": "verification_report", "component_type": "unified_command_center_archive", "component_id": center_id, "proof_hash": source_map.get("archive_verification_hash")})
    summary = {"proof_count": len(proofs), "cr_proof_present": bool(source_map.get("cr_binding_report_hash"))}
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_external_proof_index", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "proofs": proofs, "summary": summary}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _replay_plan_document(center_id: str, review_id: str, source: dict[str, Any]) -> dict[str, Any]:
    source_map = source.get("source", {})
    steps = [
        {"step_id": "verify_ucc", "order": 10, "command": "verify-unified-command-center-package", "required": True, "inputs": ["ucc_zip", "ucc_verification_report"], "expected_status": "passed"},
        {"step_id": "verify_archive", "order": 20, "command": "verify-unified-command-center-archive-package", "required": True, "inputs": ["archive_zip", "archive_verification_report"], "expected_status": "passed"},
        {"step_id": "verify_handoff", "order": 30, "command": "verify-unified-command-center-handoff-package", "required": True, "inputs": ["handoff_zip", "handoff_verification_report"], "expected_status": "passed"},
        {"step_id": "verify_continuous_review", "order": 40, "command": "verify-unified-command-center-continuous-review-package", "required": True, "inputs": ["continuous_review_zip", "continuous_review_verification_report"], "expected_status": "passed"},
    ]
    if source_map.get("drift_response_zip_sha256"):
        steps.append({"step_id": "verify_drift_response", "order": 50, "command": "verify-unified-command-center-drift-response-package", "required": True, "inputs": ["drift_response_zip", "drift_response_verification_report", "change_request_binding_report"], "expected_status": "passed"})
    steps.extend([
        {"step_id": "verify_ga_readiness", "order": 60, "command": "verify-ga-readiness-report", "required": bool(source_map.get("ga_report_hash")), "inputs": ["ga_readiness_report"], "expected_status": "passed"},
        {"step_id": "verify_release_check", "order": 70, "command": "release-check-report", "required": bool(source_map.get("release_check_report_hash")), "inputs": ["release_check_report"], "expected_status": "passed"},
        {"step_id": "manual_reviewer_narrative", "order": 80, "command": "manual-review", "required": False, "inputs": ["reviewer-guide.md"], "expected_status": "manual_review"},
    ])
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_replay_plan", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "steps": steps}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _empty_replay_document(center_id: str, review_id: str, source: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    steps = [{"step_id": row.get("step_id"), "status": "pending", "blockers": [], "verification_hash": None} for row in plan.get("steps", [])]
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_replay_result", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "status": "pending", "steps": steps, "summary": {"total": len(steps), "passed": 0, "failed": 0, "manual_review": 1}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _run_replay_document(center_id: str, review_id: str, source: dict[str, Any], plan: dict[str, Any], paths: dict[str, Any]) -> dict[str, Any]:
    steps = []
    for step in plan.get("steps", []):
        step_id = step.get("step_id")
        if step_id == "verify_ucc":
            report = verify_unified_command_center_package(paths.get("ucc_zip"), strict=True, release_check_report_path=paths.get("release_check_report"))
        elif step_id == "verify_archive":
            report = verify_unified_command_center_archive_package(paths.get("archive_zip"), strict=True, require_signed=True, require_current_ucc=True, command_center_zip_path=paths.get("ucc_zip"), command_center_verification_report_path=paths.get("ucc_verification_report"), signoff_binding_path=paths.get("signoff_binding"))
        elif step_id == "verify_handoff":
            report = verify_unified_command_center_handoff_package(paths.get("handoff_zip"), strict=True, require_archive=True, archive_zip_path=paths.get("archive_zip"), archive_verification_report_path=paths.get("archive_verification_report"))
        elif step_id == "verify_continuous_review":
            report = verify_unified_command_center_continuous_review_package(paths.get("continuous_review_zip"), strict=True, require_clear=False, require_recovery_drill=False, require_current_review=True, archive_zip_path=paths.get("archive_zip"), archive_verification_report_path=paths.get("archive_verification_report"), handoff_zip_path=paths.get("handoff_zip"), handoff_verification_report_path=paths.get("handoff_verification_report"), command_center_zip_path=paths.get("ucc_zip"), command_center_verification_report_path=paths.get("ucc_verification_report"), signoff_binding_path=paths.get("signoff_binding"))
        elif step_id == "verify_drift_response":
            report = verify_unified_command_center_drift_response_package(paths.get("drift_response_zip"), strict=True, require_closed=True, require_recheck_clear=True, require_current_review=True, source_review_zip_path=paths.get("source_review_zip") or paths.get("continuous_review_zip"), source_review_verification_report_path=paths.get("source_review_verification_report") or paths.get("continuous_review_verification_report"), recheck_review_zip_path=paths.get("recheck_review_zip") or paths.get("continuous_review_zip"), recheck_review_verification_report_path=paths.get("recheck_review_verification_report") or paths.get("continuous_review_verification_report"), change_request_binding_report_path=paths.get("drift_change_request_binding_report"), archive_zip_path=paths.get("archive_zip"), archive_verification_report_path=paths.get("archive_verification_report"), handoff_zip_path=paths.get("handoff_zip"), handoff_verification_report_path=paths.get("handoff_verification_report"), command_center_zip_path=paths.get("ucc_zip"), command_center_verification_report_path=paths.get("ucc_verification_report"), signoff_binding_path=paths.get("signoff_binding"))
        elif step_id == "verify_ga_readiness":
            report = _generic_report(paths.get("ga_readiness_report"))
        elif step_id == "verify_release_check":
            report = _release_check_result(paths.get("release_check_report"))
        else:
            report = {"status": "manual_review", "blockers": [], "integrity_hash": None}
        steps.append({"step_id": step_id, "status": report.get("status"), "blockers": report.get("blockers", []), "verification_hash": report.get("integrity_hash"), "duration_ms": 0})
    required_steps = {str(row.get("step_id")) for row in plan.get("steps", []) if isinstance(row, dict) and row.get("required")}
    failed = [row for row in steps if row.get("step_id") in required_steps and row.get("status") != "passed"]
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_replay_result", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "status": "failed" if failed else "passed", "steps": steps, "summary": {"total": len(steps), "passed": len([row for row in steps if row.get("status") == "passed"]), "failed": len(failed), "manual_review": len([row for row in steps if row.get("status") == "manual_review"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _narrative_document(center_id: str, review_id: str, source: dict[str, Any], replay_result: dict[str, Any]) -> dict[str, Any]:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_narrative", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "status": replay_result.get("status"), "summary": {"ucc_ready": bool(source.get("source", {}).get("ucc_verification_hash")), "archive_current": bool(source.get("source", {}).get("archive_verification_hash")), "handoff_current": bool(source.get("source", {}).get("handoff_verification_hash")), "drift_response_present": bool(source.get("source", {}).get("drift_response_verification_hash")), "manual_review_required": True}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _checklist_document(center_id: str, review_id: str, source: dict[str, Any]) -> dict[str, Any]:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_manual_checklist", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "items": [{"item_id": "manual-001", "label": "Reviewer confirms UCC evidence chain narrative.", "required": True, "status": "manual_required"}]}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(center_id: str, review_id: str, source: dict[str, Any], root: Path, entries: set[str], status: str, *, package_type: str = UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE, evidence_id: str | None = None) -> dict[str, Any]:
    files = []
    for rel in sorted(entries - {"manifest.json"}):
        path = root / rel
        files.append({"path": rel, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size if path.exists() else 0})
    manifest = {"package_type": package_type, "schema_version": UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION, "center_id": center_id, "review_id": review_id, "evidence_id": evidence_id, "source_hash": source.get("source_hash"), "files": files, "summary": {"replay_status": status, "required_evidence_status": status, "manual_review_required": True}, "source": {"review_source_hash": source.get("integrity_hash")}}
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _reviewer_guide(docs: dict[str, Any]) -> str:
    source = docs.get("source", {})
    replay = docs.get("replay_result", {})
    return sanitize_sensitive_text(
        "\n".join(
            [
                "# MusicForge Unified Command Center Evidence Review",
                "",
                f"Review: {source.get('review_id')}",
                f"Replay status: {replay.get('status')}",
                "Run the verifier with the external evidence arguments listed in the replay plan.",
                "Accepted review responses must bind the current review pack hash and replay result hash.",
            ]
        )
    )


def _review_verifier_kwargs(paths: dict[str, Any]) -> dict[str, Any]:
    return {
        "ucc_zip_path": _path_or_none(paths.get("ucc_zip")),
        "ucc_verification_report_path": _path_or_none(paths.get("ucc_verification_report")),
        "archive_zip_path": _path_or_none(paths.get("archive_zip")),
        "archive_verification_report_path": _path_or_none(paths.get("archive_verification_report")),
        "handoff_zip_path": _path_or_none(paths.get("handoff_zip")),
        "handoff_verification_report_path": _path_or_none(paths.get("handoff_verification_report")),
        "continuous_review_zip_path": _path_or_none(paths.get("continuous_review_zip")),
        "continuous_review_verification_report_path": _path_or_none(paths.get("continuous_review_verification_report")),
        "drift_response_zip_path": _path_or_none(paths.get("drift_response_zip")),
        "drift_response_verification_report_path": _path_or_none(paths.get("drift_response_verification_report")),
        "drift_change_request_binding_report_path": _path_or_none(paths.get("drift_change_request_binding_report")),
        "source_review_zip_path": _path_or_none(paths.get("source_review_zip")),
        "source_review_verification_report_path": _path_or_none(paths.get("source_review_verification_report")),
        "recheck_review_zip_path": _path_or_none(paths.get("recheck_review_zip")),
        "recheck_review_verification_report_path": _path_or_none(paths.get("recheck_review_verification_report")),
        "signoff_binding_path": _path_or_none(paths.get("signoff_binding")),
        "ga_readiness_report_path": _path_or_none(paths.get("ga_readiness_report")),
        "release_check_report_path": _path_or_none(paths.get("release_check_report")),
    }


def _summary_from_path(path: Any, label: str) -> dict[str, Any]:
    if not path or not Path(path).exists():
        doc = {"package_type": f"musicforge_{label}_summary", "status": "not_applicable", "label": label}
    else:
        source = read_json(Path(path))
        doc = {key: source.get(key) for key in ("package_type", "status", "zip_sha256", "zip_size_bytes", "manifest_hash", "integrity_hash") if key in source}
        doc["label"] = label
    doc["summary_hash"] = stable_hash(doc)
    return doc


def _generic_report(path: Any) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {"status": "not_applicable", "blockers": [], "integrity_hash": None}
    report = read_json(Path(path))
    status = str(report.get("status") or "")
    if report.get("ok") is True:
        status = "passed"
    if status in {"ready", "warning"}:
        status = "passed"
    return {"status": status or "failed", "blockers": report.get("blockers", []), "integrity_hash": _integrity_or_stable(report)}


def _release_check_result(path: Any) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {"status": "not_applicable", "blockers": [], "integrity_hash": None}
    report = read_json(Path(path))
    return {"status": "passed" if report.get("ok") is True else "failed", "blockers": [row.get("check_id") for row in report.get("results", []) if isinstance(row, dict) and not row.get("ok")], "integrity_hash": _integrity_or_stable(report)}


def _public_reviewer(reviewer: dict[str, Any]) -> dict[str, Any]:
    return {"name": sanitize_sensitive_text(str(reviewer.get("name") or "Reviewer"))[:120], "organization": sanitize_sensitive_text(str(reviewer.get("organization") or ""))[:120], "role": sanitize_sensitive_text(str(reviewer.get("role") or "reviewer"))[:80]}


def _findings(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    return [{"severity": sanitize_sensitive_text(str(row.get("severity") or "low"))[:40], "component": sanitize_sensitive_text(str(row.get("component") or ""))[:120], "message": sanitize_sensitive_text(str(row.get("message") or ""))[:1000]} for row in rows if isinstance(row, dict)]


def _public_response(response: dict[str, Any]) -> dict[str, Any]:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_response_public", "response_id": response.get("response_id"), "review_id": response.get("review_id"), "result": response.get("result"), "reviewer": response.get("reviewer"), "findings": response.get("findings", []), "signed_at": response.get("signed_at")}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _response_verification_summary(response: dict[str, Any], public_response: dict[str, Any]) -> dict[str, Any]:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_response_verification_summary", "response_id": response.get("response_id"), "status": response.get("status"), "result": response.get("result"), "response_payload_hash": response.get("payload_hash"), "response_integrity_hash": response.get("integrity_hash"), "response_public_hash": public_response.get("integrity_hash"), "bindings": response.get("bindings", {})}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _response_binding_summary(response: dict[str, Any]) -> dict[str, Any]:
    bindings = response.get("bindings", {})
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_response_binding_summary", "response_id": response.get("response_id"), "review_pack_zip_sha256": bindings.get("review_pack_zip_sha256"), "review_pack_manifest_hash": bindings.get("review_pack_manifest_hash"), "review_pack_source_hash": bindings.get("review_pack_source_hash"), "replay_result_hash": bindings.get("replay_result_hash"), "response_payload_hash": response.get("payload_hash")}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _read_optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _path_or_none(value: Any) -> Path | None:
    if not value:
        return None
    return Path(value)


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_from_path(path: Any) -> str | None:
    if not path or not Path(path).exists():
        return None
    data = read_json(Path(path))
    return data.get("integrity_hash") or stable_hash(data)


def _integrity_or_stable(payload: dict[str, Any]) -> str:
    return str(payload.get("integrity_hash") or stable_hash(payload))


def _sha256_path(path: Any) -> str | None:
    if not path:
        return None
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _zip_manifest_hash(path: Any) -> str | None:
    if not path or not Path(path).exists():
        return None
    try:
        with zipfile.ZipFile(Path(path)) as archive:
            return json.loads(archive.read("manifest.json").decode("utf-8")).get("integrity_hash")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return None


def _safe_id(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in {"-", "_"})[:80] or "item"
