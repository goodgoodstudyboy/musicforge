from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.domains.program.ports import ProgramReleaseStore as ProgramReleaseStore
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore as UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_handoff_verifier import ACCEPTED_EVIDENCE_REQUIRED_ENTRIES as ACCEPTED_EVIDENCE_REQUIRED_ENTRIES, UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE, verify_unified_release_program_accepted_evidence_package as verify_unified_release_program_accepted_evidence_package, verify_unified_release_program_handoff_package as verify_unified_release_program_handoff_package, verify_unified_release_program_review_pack_package as verify_unified_release_program_review_pack_package, write_unified_release_program_accepted_evidence_verification_report as write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_handoff_verification_report as write_unified_release_program_handoff_verification_report, write_unified_release_program_review_pack_verification_report as write_unified_release_program_review_pack_verification_report
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_package as verify_unified_release_program_package


DEFAULT_BOARD_POLICY = {
    "minimum_acceptances": 1,
    "minimum_organizations": 1,
    "required_roles": ["release_owner"],
    "block_on_rejected": True,
    "block_on_needs_changes": True,
    "block_on_critical_finding": True,
}


class UnifiedReleaseProgramHandoffError(ValueError):
    pass


class UnifiedReleaseProgramHandoffNotFoundError(UnifiedReleaseProgramHandoffError):
    pass


class UnifiedReleaseProgramHandoffStateError(UnifiedReleaseProgramHandoffError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramHandoffStateError)


class UnifiedReleaseProgramHandoffStore:
    def __init__(self, program_store: UnifiedReleaseProgramStore | None = None, *, release_store: ProgramReleaseStore | None = None) -> None:
        self.program_store = program_store or UnifiedReleaseProgramStore(release_store=release_store)
        self.lock = WorkspaceLock(self.program_store.root.parent, operation="program-workflow-write")

    def handoff_dir(self, program_id: str) -> Path:
        return self.program_store.program_dir(program_id) / "handoff"

    def report_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "handoff-report.json"

    def inventory_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "evidence-inventory.json"

    def guide_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "recipient-guide.md"

    def external_manifest_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "external-evidence-manifest.json"

    def runtime_external_manifest_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "runtime-external-evidence-manifest.json"

    def decision_board_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "decision-board.json"

    def conflict_report_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "conflict-report.json"

    def accepted_index_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "accepted-evidence-index.json"

    def readiness_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "handoff-readiness-matrix.json"

    def gap_path(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "handoff-gap-plan.json"

    def review_pack_dir(self, program_id: str, review_pack_id: str) -> Path:
        return self.handoff_dir(program_id) / "review-packs" / _safe_id(review_pack_id)

    def review_pack_zip_path(self, program_id: str, review_pack_id: str) -> Path:
        return self.review_pack_dir(program_id, review_pack_id) / "review-pack.zip"

    def review_pack_verification_report_path(self, program_id: str, review_pack_id: str) -> Path:
        return self.review_pack_dir(program_id, review_pack_id) / "review-pack-verification-report.json"

    def response_dir(self, program_id: str, response_id: str) -> Path:
        return self.handoff_dir(program_id) / "responses" / _safe_id(response_id)

    def response_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response.json"

    def response_verification_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response-verification-report.json"

    def response_binding_path(self, program_id: str, response_id: str) -> Path:
        return self.response_dir(program_id, response_id) / "response-binding-summary.json"

    def accepted_evidence_dir(self, program_id: str, evidence_id: str) -> Path:
        return self.handoff_dir(program_id) / "accepted-evidence" / _safe_id(evidence_id)

    def accepted_evidence_zip_path(self, program_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence.zip"

    def accepted_evidence_verification_report_path(self, program_id: str, evidence_id: str) -> Path:
        return self.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence-verification-report.json"

    def signoff_dir(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "signoff"

    def signoff_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "program-handoff-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "program-handoff-signoff-binding-summary.json"

    def history_path(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "program-handoff-history.jsonl"

    def frozen_dir(self, program_id: str) -> Path:
        return self.signoff_dir(program_id) / "frozen"

    def archive_dir(self, program_id: str) -> Path:
        return self.handoff_dir(program_id) / "archive"

    def archive_export_dir(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "export"

    def archive_manifest_path(self, program_id: str) -> Path:
        return self.archive_export_dir(program_id) / "manifest.json"

    def archive_zip_path(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "program-handoff-archive.zip"

    def archive_verification_report_path(self, program_id: str) -> Path:
        return self.archive_dir(program_id) / "program-handoff-archive-verification-report.json"

    def get_handoff(self, program_id: str) -> dict[str, Any]:
        return {
            "report": _read_optional_json(self.report_path(program_id)),
            "evidence_inventory": _read_optional_json(self.inventory_path(program_id)),
            "external_evidence_manifest": _read_optional_json(self.external_manifest_path(program_id)),
            "runtime_external_evidence_manifest": _read_optional_json(self.runtime_external_manifest_path(program_id)),
            "decision_board": _read_optional_json(self.decision_board_path(program_id)),
            "conflict_report": _read_optional_json(self.conflict_report_path(program_id)),
            "accepted_evidence_index": _read_optional_json(self.accepted_index_path(program_id)),
            "readiness_matrix": _read_optional_json(self.readiness_path(program_id)),
            "gap_plan": _read_optional_json(self.gap_path(program_id)),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "verification": _read_optional_json(self.archive_verification_report_path(program_id)),
        }

    def refresh_handoff(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._build_documents(program_id, payload, write_external=True)
            self._write_live_docs(program_id, docs)
            return docs["report"]

    def export_review_pack(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._ensure_live_docs(program_id, payload)
            review_pack_id = _safe_id(str(payload.get("review_pack_id") or self._next_review_pack_id(program_id)))
            pack_dir = self.review_pack_dir(program_id, review_pack_id)
            export_dir = pack_dir / "export"
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            now = now_iso()
            source_hash = stable_hash(
                {
                    "handoff_report_hash": docs["report"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "review_pack_id": review_pack_id,
                }
            )
            report = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_review_pack_report",
                    "program_id": program_id,
                    "handoff_id": docs["report"].get("handoff_id"),
                    "review_pack_id": review_pack_id,
                    "audience": _bounded(payload.get("audience") or "release_owner", 80),
                    "status": "ready",
                    "source_hash": source_hash,
                    "created_at": now,
                    "summary": docs["report"].get("summary", {}),
                }
            )
            binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_review_pack_binding_summary",
                    "program_id": program_id,
                    "handoff_id": report.get("handoff_id"),
                    "review_pack_id": review_pack_id,
                    "source_hash": source_hash,
                    "handoff_report_hash": docs["report"].get("integrity_hash"),
                    "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                }
            )
            template = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_reviewer_form_template",
                    "required_fields": [
                        "review_pack_id",
                        "review_pack_source_hash",
                        "review_pack_zip_sha256",
                        "review_pack_manifest_hash",
                        "program_id",
                        "handoff_id",
                        "reviewer_id",
                        "reviewer_role",
                        "organization",
                        "decision",
                        "payload_hash",
                    ],
                }
            )
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, value: dict[str, Any] | str) -> None:
                path = export_dir / rel
                if isinstance(value, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            write_entry("review-pack-report.json", report)
            write_entry("review-pack-binding-summary.json", binding)
            write_entry("recipient-guide.md", docs["guide"])
            write_entry("data/handoff-summary.json", _public_handoff_summary(docs))
            write_entry("data/evidence-inventory-public.json", _public_inventory(docs["inventory"]))
            write_entry("data/risk-summary-public.json", _risk_summary(docs))
            write_entry("data/reviewer-form-template.json", template)
            write_entry("README.txt", "MusicForge Unified Release Program Review Pack\n")
            manifest = _package_manifest(UNIFIED_RELEASE_PROGRAM_REVIEW_PACK_PACKAGE_TYPE, program_id, report.get("handoff_id"), files, {"review_pack_report_hash": report.get("integrity_hash"), "review_pack_binding_hash": binding.get("integrity_hash")})
            write_json(export_dir / "manifest.json", manifest)
            write_json(pack_dir / "review-pack-report.json", report)
            write_json(pack_dir / "review-pack-binding-summary.json", binding)
            return {"status": "ready", "review_pack_id": review_pack_id, "manifest": manifest, "review_pack_report": report, "binding": binding}

    def build_review_pack_zip(self, program_id: str, review_pack_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            review_pack_id = _safe_id(str(review_pack_id or payload.get("review_pack_id") or ""))
            if not review_pack_id:
                created = self.export_review_pack(program_id, payload)
                review_pack_id = str(created["review_pack_id"])
            pack_dir = self.review_pack_dir(program_id, review_pack_id)
            export_dir = pack_dir / "export"
            if not (export_dir / "manifest.json").exists():
                self.export_review_pack(program_id, {**payload, "review_pack_id": review_pack_id})
            return self._build_zip(export_dir, self.review_pack_zip_path(program_id, review_pack_id), "review_pack")

    def verify_review_pack_zip(self, program_id: str, review_pack_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        review_pack_id = _safe_id(str(review_pack_id or payload.get("review_pack_id") or ""))
        zip_path = payload.get("review_pack_zip") or payload.get("zip_path") or self.review_pack_zip_path(program_id, review_pack_id)
        report = verify_unified_release_program_review_pack_package(zip_path, strict=bool(payload.get("strict", True)))
        if review_pack_id:
            write_unified_release_program_review_pack_verification_report(report, self.review_pack_verification_report_path(program_id, review_pack_id))
        return report

    def import_response(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        if payload.get("response_json"):
            payload.update(read_json(Path(payload["response_json"])))
        for forbidden in ("source_path", "local_path", "file_path"):
            if payload.get(forbidden):
                raise UnifiedReleaseProgramHandoffStateError(f"{forbidden} is not allowed for reviewer response import.")
        with self.lock:
            self.ensure_unsigned(program_id)
            required = [
                "review_pack_id",
                "review_pack_source_hash",
                "review_pack_zip_sha256",
                "review_pack_manifest_hash",
                "program_id",
                "handoff_id",
                "reviewer_id",
                "reviewer_role",
                "organization",
                "decision",
                "payload_hash",
            ]
            missing = [field for field in required if not payload.get(field)]
            if missing:
                raise UnifiedReleaseProgramHandoffStateError(f"Reviewer response missing binding fields: {', '.join(missing)}")
            if str(payload.get("program_id")) != program_id:
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response program_id does not match.")
            expected_hash = _response_payload_hash(payload)
            if payload.get("payload_hash") != expected_hash:
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response payload_hash is invalid.")
            review_pack_id = _safe_id(str(payload.get("review_pack_id")))
            pack_report_path = self.review_pack_dir(program_id, review_pack_id) / "review-pack-report.json"
            binding_path = self.review_pack_dir(program_id, review_pack_id) / "review-pack-binding-summary.json"
            if not pack_report_path.exists() or not binding_path.exists():
                raise UnifiedReleaseProgramHandoffNotFoundError(f"Review Pack not found: {review_pack_id}")
            pack_report = read_json(pack_report_path)
            pack_binding = read_json(binding_path)
            zip_path = self.review_pack_zip_path(program_id, review_pack_id)
            if payload.get("review_pack_source_hash") != pack_report.get("source_hash"):
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response review_pack_source_hash does not match current Review Pack.")
            if not zip_path.exists() or payload.get("review_pack_zip_sha256") != _sha256_path(zip_path):
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response review_pack_zip_sha256 does not match current Review Pack ZIP.")
            manifest_hash = _manifest_hash_from_zip(zip_path)
            if payload.get("review_pack_manifest_hash") != manifest_hash:
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response review_pack_manifest_hash does not match current Review Pack manifest.")
            response_id = _safe_id(str(payload.get("response_id") or self._next_response_id(program_id)))
            response = sanitize_metadata({**payload, "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "response_type": "musicforge_unified_release_program_review_response", "response_id": response_id, "status": "imported", "imported_at": now_iso()})
            response["integrity_hash"] = _integrity_hash(response)
            public = _response_public_projection(response)
            response_dir = self.response_dir(program_id, response_id)
            response_dir.mkdir(parents=True, exist_ok=True)
            write_json(self.response_path(program_id, response_id), response)
            verification = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": UNIFIED_RELEASE_PROGRAM_RESPONSE_VERIFICATION_PACKAGE_TYPE,
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "response_id": response_id,
                    "status": "passed",
                    "response_payload_hash": response.get("payload_hash"),
                    "response_integrity_hash": response.get("integrity_hash"),
                    "response_public_summary_hash": stable_hash(public),
                    "review_pack_source_hash": response.get("review_pack_source_hash"),
                    "review_pack_zip_sha256": response.get("review_pack_zip_sha256"),
                    "review_pack_manifest_hash": response.get("review_pack_manifest_hash"),
                }
            )
            binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_response_binding_summary",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "response_id": response_id,
                    "review_pack_id": response.get("review_pack_id"),
                    "review_pack_source_hash": response.get("review_pack_source_hash"),
                    "review_pack_zip_sha256": response.get("review_pack_zip_sha256"),
                    "review_pack_manifest_hash": response.get("review_pack_manifest_hash"),
                    "reviewer_id": response.get("reviewer_id"),
                    "reviewer_role": response.get("reviewer_role"),
                    "organization": response.get("organization"),
                    "decision": response.get("decision"),
                    "response_payload_hash": response.get("payload_hash"),
                    "response_integrity_hash": response.get("integrity_hash"),
                    "review_pack_binding_hash": pack_binding.get("integrity_hash"),
                }
            )
            write_json(self.response_verification_path(program_id, response_id), verification)
            write_json(self.response_binding_path(program_id, response_id), binding)
            (response_dir / "response-raw-sha256.txt").write_text(str(response.get("payload_hash")), encoding="utf-8")
            return {"status": "imported", "response": response, "verification": verification, "binding": binding}

    def create_accepted_evidence(self, program_id: str, response_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            self.ensure_unsigned(program_id)
            response_id = _safe_id(response_id)
            response = read_json(self.response_path(program_id, response_id))
            if response.get("decision") not in {"accepted", "accepted_with_notes"}:
                raise UnifiedReleaseProgramHandoffStateError("Only accepted reviewer responses can create accepted evidence.")
            verification = read_json(self.response_verification_path(program_id, response_id))
            binding = read_json(self.response_binding_path(program_id, response_id))
            if verification.get("status") != "passed" or not _integrity_ok(verification) or not _integrity_ok(binding):
                raise UnifiedReleaseProgramHandoffStateError("Reviewer response verification or binding failed.")
            evidence_id = _safe_id(str(response.get("evidence_id") or self._next_evidence_id(program_id)))
            evidence_dir = self.accepted_evidence_dir(program_id, evidence_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            public_response = _with_integrity(_response_public_projection(response))
            verification_summary = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_response_verification_summary",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "response_id": response_id,
                    "status": verification.get("status"),
                    "response_payload_hash": verification.get("response_payload_hash"),
                    "response_verification_hash": verification.get("integrity_hash"),
                    "response_public_summary_hash": verification.get("response_public_summary_hash"),
                }
            )
            report = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_accepted_evidence_report",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "decision": response.get("decision"),
                    "reviewer": {
                        "reviewer_id": response.get("reviewer_id"),
                        "role": binding.get("reviewer_role"),
                        "organization": binding.get("organization"),
                    },
                    "source": {
                        "response_payload_hash": binding.get("response_payload_hash"),
                        "response_verification_hash": verification.get("integrity_hash"),
                        "response_binding_hash": binding.get("integrity_hash"),
                        "review_pack_source_hash": binding.get("review_pack_source_hash"),
                    },
                    "public_summary": {"accepted": True, "role": binding.get("reviewer_role"), "organization": binding.get("organization")},
                    "status": "accepted",
                }
            )
            evidence_binding = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_accepted_evidence_binding_summary",
                    "program_id": program_id,
                    "handoff_id": response.get("handoff_id"),
                    "evidence_id": evidence_id,
                    "response_id": response_id,
                    "accepted_evidence_report_hash": report.get("integrity_hash"),
                    "response_verification_hash": verification.get("integrity_hash"),
                    "response_binding_hash": binding.get("integrity_hash"),
                    "reviewer_role": binding.get("reviewer_role"),
                    "organization": binding.get("organization"),
                    "decision": binding.get("decision"),
                }
            )
            write_json(evidence_dir / "original-response-public.json", public_response)
            write_json(evidence_dir / "response-verification-summary.json", verification_summary)
            write_json(evidence_dir / "response-binding-summary.json", binding)
            write_json(evidence_dir / "accepted-evidence-report.json", report)
            write_json(evidence_dir / "accepted-evidence-binding-summary.json", evidence_binding)
            self.build_accepted_evidence_zip(program_id, evidence_id)
            self.verify_accepted_evidence_zip(program_id, evidence_id)
            self.refresh_decision_board(program_id, {})
            return {"status": "accepted", "evidence": report, "binding": evidence_binding}

    def build_accepted_evidence_zip(self, program_id: str, evidence_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        evidence_id = _safe_id(evidence_id)
        evidence_dir = self.accepted_evidence_dir(program_id, evidence_id)
        export_dir = evidence_dir / "export"
        if export_dir.exists():
            shutil.rmtree(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        files: list[dict[str, Any]] = []

        def copy_entry(rel: str) -> None:
            source = evidence_dir / rel
            dest = export_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            files.append(_file_record(dest, rel))

        for rel in sorted(ACCEPTED_EVIDENCE_REQUIRED_ENTRIES - {"manifest.json", "README.txt"}):
            copy_entry(rel)
        readme = export_dir / "README.txt"
        readme.write_text("MusicForge Unified Release Program Accepted Evidence\n", encoding="utf-8")
        files.append(_file_record(readme, "README.txt"))
        report = read_json(evidence_dir / "accepted-evidence-report.json")
        manifest = _package_manifest(UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE, program_id, report.get("handoff_id"), files, {"accepted_evidence_report_hash": report.get("integrity_hash")})
        write_json(export_dir / "manifest.json", manifest)
        return self._build_zip(export_dir, self.accepted_evidence_zip_path(program_id, evidence_id), "accepted_evidence")

    def verify_accepted_evidence_zip(self, program_id: str, evidence_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        evidence_id = _safe_id(evidence_id)
        report_doc = read_json(self.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence-report.json")
        response_id = str(report_doc.get("response_id"))
        report = verify_unified_release_program_accepted_evidence_package(
            payload.get("accepted_evidence_zip") or self.accepted_evidence_zip_path(program_id, evidence_id),
            strict=bool(payload.get("strict", True)),
            require_accepted=bool(payload.get("require_accepted", True)),
            response_verification_report_path=payload.get("response_verification_report") or self.response_verification_path(program_id, response_id),
            response_binding_summary_path=payload.get("response_binding_summary") or self.response_binding_path(program_id, response_id),
        )
        write_unified_release_program_accepted_evidence_verification_report(report, self.accepted_evidence_verification_report_path(program_id, evidence_id))
        return report

    def refresh_decision_board(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            policy = _board_policy(payload.get("policy") if "policy" in payload else (_read_optional_json(self.decision_board_path(program_id)).get("policy") or None))
            participants, conflicts = self._accepted_participants(program_id)
            conflicts.extend(self._response_decision_conflicts(program_id, policy))
            readiness = _decision_readiness(policy, participants, conflicts)
            board = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_decision_board",
                    "program_id": program_id,
                    "handoff_id": self._handoff_id(program_id, payload),
                    "board_id": _safe_id(str(payload.get("board_id") or "urpdb-000001")),
                    "policy": policy,
                    "participants": participants,
                    "conflicts": conflicts,
                    "readiness": readiness,
                    "status": readiness.get("status"),
                }
            )
            conflict_report = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_conflict_report", "program_id": program_id, "handoff_id": board.get("handoff_id"), "conflicts": conflicts, "summary": {"conflict_count": len(conflicts)}})
            accepted_index = self._accepted_index_document(program_id, participants)
            readiness_doc = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_readiness_matrix", "program_id": program_id, "handoff_id": board.get("handoff_id"), "rows": _readiness_rows(readiness), "summary": readiness})
            gap = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_gap_plan", "program_id": program_id, "handoff_id": board.get("handoff_id"), "items": _gap_items(readiness), "summary": {"gap_count": len(_gap_items(readiness))}})
            write_json(self.decision_board_path(program_id), board)
            write_json(self.conflict_report_path(program_id), conflict_report)
            write_json(self.accepted_index_path(program_id), accepted_index)
            write_json(self.readiness_path(program_id), readiness_doc)
            write_json(self.gap_path(program_id), gap)
            if self.report_path(program_id).exists():
                report = read_json(self.report_path(program_id))
                report["summary"] = {**(report.get("summary") or {}), "quorum_status": readiness.get("status"), "accepted_response_count": len(participants), "missing_roles": readiness.get("missing_roles", [])}
                report["status"] = "ready_for_signoff" if readiness.get("status") == "ready_for_signoff" and not report.get("blockers") else report.get("status")
                report["integrity_hash"] = _integrity_hash(report)
                write_json(self.report_path(program_id), report)
            return board

    def signoff_handoff(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            if not self.report_path(program_id).exists():
                self.refresh_handoff(program_id, payload)
            board = self.refresh_decision_board(program_id, {})
            if board.get("status") != "ready_for_signoff":
                raise UnifiedReleaseProgramHandoffStateError("Program Handoff Decision Board is not ready for signoff.")
            docs = self._docs_for_signoff(program_id)
            now = now_iso()
            docs["report"]["status"] = "signed"
            docs["report"]["signed_at"] = now
            docs["report"]["integrity_hash"] = _integrity_hash(docs["report"])
            role = _bounded(payload.get("role") or "release_owner", 80)
            allowed_roles = set((board.get("policy") or {}).get("required_roles") or ["release_owner"])
            if role not in allowed_roles:
                raise UnifiedReleaseProgramHandoffStateError("Program Handoff signer role is not allowed by policy.")
            signoff = _with_integrity(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_handoff_signoff",
                    "program_id": program_id,
                    "handoff_id": docs["report"].get("handoff_id"),
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "program-handoff-chair", 120),
                    "role": role,
                    "reason": _bounded(payload.get("reason") or "Unified Release Program final handoff accepted.", 1000),
                    "signed_at": now,
                    "source_hash": docs["report"].get("source_hash"),
                    "handoff_report_hash": docs["report"].get("integrity_hash"),
                    "decision_board_hash": docs["decision"].get("integrity_hash"),
                    "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "tool": {"name": "MusicForge Unified Release Program Final Handoff", "version": __version__},
                }
            )
            signoff = SignoffService.seal(signoff)
            self.signoff_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.signoff_path(program_id), signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "unified_release_program_handoff_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "handoff_id": signoff.get("handoff_id"),
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "source_hash": signoff.get("source_hash"),
                    "handoff_report_hash": signoff.get("handoff_report_hash"),
                    "decision_board_hash": signoff.get("decision_board_hash"),
                },
            )
            binding = self._signoff_binding(signoff, event, docs)
            write_json(self.signoff_binding_path(program_id), binding)
            self._write_frozen(program_id, docs)
            write_json(self.report_path(program_id), docs["report"])
            return signoff

    def export_handoff_archive(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            docs = self._archive_documents(program_id)
            export_dir = self.archive_export_dir(program_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, value: dict[str, Any] | str) -> None:
                path = export_dir / rel
                if isinstance(value, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value, encoding="utf-8")
                else:
                    write_json(path, value)
                files.append(_file_record(path, rel))

            write_entry("program-handoff-report.json", docs["report"])
            write_entry("evidence-inventory.json", docs["inventory"])
            write_entry("recipient-guide.md", docs["guide"])
            write_entry("decision-board.json", docs["decision"])
            write_entry("conflict-report.json", docs["conflicts"])
            write_entry("accepted-evidence-index.json", docs["accepted_index"])
            write_entry("handoff-readiness-matrix.json", docs["readiness"])
            write_entry("handoff-gap-plan.json", docs["gap"])
            write_entry("external-evidence-manifest.json", docs["external_manifest"])
            write_entry("program-handoff-signoff.json", docs["signoff"])
            write_entry("program-handoff-signoff-binding-summary.json", docs["binding"])
            write_entry("program-handoff-history.jsonl", _history_text(self.read_history(program_id)))
            write_entry("verification-summaries/program-verification-summary.json", docs["program_summary"])
            write_entry("verification-summaries/operations-verification-summary.json", docs["operations_summary"])
            write_entry("verification-summaries/accepted-evidence-verification-summaries.json", docs["accepted_summary"])
            write_entry("README.txt", "MusicForge Unified Release Program Final Handoff Archive\n")
            manifest = _package_manifest(UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE, program_id, docs["report"].get("handoff_id"), files, _archive_source(docs))
            write_json(self.archive_manifest_path(program_id), manifest)
            return manifest

    def build_handoff_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del payload
        with self.lock:
            self.export_handoff_archive(program_id)
            return self._build_zip(self.archive_export_dir(program_id), self.archive_zip_path(program_id), "handoff_archive")

    def verify_handoff_archive_zip(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = verify_unified_release_program_handoff_package(
            payload.get("handoff_zip") or payload.get("handoff_archive_zip") or self.archive_zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", True)),
            require_accepted=bool(payload.get("require_accepted", True)),
            require_signed=bool(payload.get("require_signed", True)),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or self.runtime_external_manifest_path(program_id),
            handoff_signoff_binding_path=payload.get("handoff_signoff_binding") or self.signoff_binding_path(program_id),
        )
        write_unified_release_program_handoff_verification_report(report, self.archive_verification_report_path(program_id))
        return report

    def gate(self, program_id: str, *, required: bool = False, handoff_archive_zip_path: Path | str | None = None, handoff_archive_verification_report_path: Path | str | None = None, **payload: Any) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(handoff_archive_zip_path) if handoff_archive_zip_path else self.archive_zip_path(program_id)
        report_path = Path(handoff_archive_verification_report_path) if handoff_archive_verification_report_path else self.archive_verification_report_path(program_id)
        if not zip_path.exists():
            return _gate_failed("Unified Release Program Final Handoff Archive ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Release Program Final Handoff verification report is missing.")
        try:
            external = read_json(report_path)
            runtime = verify_unified_release_program_handoff_package(
                zip_path,
                strict=True,
                require_current=True,
                require_accepted=True,
                require_signed=True,
                external_evidence_manifest_path=payload.get("external_evidence_manifest") or self.runtime_external_manifest_path(program_id),
                handoff_signoff_binding_path=payload.get("handoff_signoff_binding") or self.signoff_binding_path(program_id),
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Release Program Final Handoff verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Release Program Final Handoff verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Release Program Final Handoff verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Release Program Final Handoff gate passed.", "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def ensure_unsigned(self, program_id: str) -> None:
        if self.latest_signoff_state(program_id).get("status") == "signed":
            raise UnifiedReleaseProgramHandoffStateError("Unified Release Program Final Handoff is signed. Create a new handoff for changes.")

    def latest_signoff_state(self, program_id: str) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "unified_release_program_handoff_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
        if latest:
            return latest
        if self.signoff_path(program_id).exists():
            signoff = read_json(self.signoff_path(program_id))
            if signoff.get("status") == "signed":
                return {"status": "signed", "signoff_hash": signoff.get("integrity_hash"), "event": {}}
        return {"status": "unsigned"}

    def read_history(self, program_id: str) -> list[dict[str, Any]]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()

    def _build_documents(self, program_id: str, payload: ImplementationDocument, *, write_external: bool) -> ImplementationDocument:
        handoff_id = self._handoff_id(program_id, payload)
        runtime_external_manifest = self._external_manifest(program_id, handoff_id, payload)
        external_manifest = _public_external_manifest(runtime_external_manifest)
        if write_external:
            write_json(self.runtime_external_manifest_path(program_id), runtime_external_manifest)
            write_json(self.external_manifest_path(program_id), external_manifest)
        program_state = self._current_program_state(runtime_external_manifest)
        operations_state = self._current_operations_state(runtime_external_manifest)
        checks = list(program_state.get("checks", [])) + list(operations_state.get("checks", []))
        blockers = [row["check_id"] for row in checks if row.get("status") == "failed"]
        participants, conflicts = self._accepted_participants(program_id)
        decision = _read_optional_json(self.decision_board_path(program_id))
        policy = _board_policy(decision.get("policy") if decision else DEFAULT_BOARD_POLICY)
        conflicts.extend(self._response_decision_conflicts(program_id, policy))
        accepted_index = self._accepted_index_document(program_id, participants)
        if not decision:
            decision = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_decision_board", "program_id": program_id, "handoff_id": handoff_id, "board_id": "urpdb-000001", "policy": policy, "participants": participants, "conflicts": conflicts, "readiness": _decision_readiness(policy, participants, conflicts), "status": "pending"})
        else:
            decision = {**decision, "participants": participants, "conflicts": conflicts, "readiness": _decision_readiness(policy, participants, conflicts), "status": _decision_readiness(policy, participants, conflicts).get("status"), "integrity_hash": None}
            decision["integrity_hash"] = _integrity_hash(decision)
        inventory = self._evidence_inventory(program_id, handoff_id, program_state, operations_state, participants)
        now = now_iso()
        source = {
            "program": _source_without_checks(program_state),
            "operations": _source_without_checks(operations_state),
            "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
            "accepted_evidence_index_hash": accepted_index.get("integrity_hash"),
        }
        source_hash = stable_hash(source)
        readiness_summary = _decision_readiness(policy, participants, conflicts)
        status = "ready_for_signoff" if not blockers and readiness_summary.get("status") == "ready_for_signoff" else "ready_for_review" if not blockers else "blocked"
        report = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_handoff_report",
                "program_id": program_id,
                "handoff_id": handoff_id,
                "status": status,
                "created_at": now,
                "source": source,
                "source_hash": source_hash,
                "summary": {
                    "accepted_response_count": len(participants),
                    "required_role_count": len((decision.get("policy") or DEFAULT_BOARD_POLICY).get("required_roles") or []),
                    "quorum_status": readiness_summary.get("status"),
                    "open_blocker_count": len(blockers),
                    "risk_level": "low" if not blockers else "critical",
                    **inventory.get("summary", {}),
                },
                "warnings": [],
                "blockers": blockers,
            }
        )
        conflict_report = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_conflict_report", "program_id": program_id, "handoff_id": handoff_id, "conflicts": conflicts, "summary": {"conflict_count": len(conflicts)}})
        readiness = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_readiness_matrix", "program_id": program_id, "handoff_id": handoff_id, "rows": _readiness_rows(readiness_summary), "summary": readiness_summary})
        gap = _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_gap_plan", "program_id": program_id, "handoff_id": handoff_id, "items": _gap_items(readiness_summary) + [{"check_id": row["check_id"], "status": "manual_required"} for row in checks if row.get("status") == "failed"], "summary": {"gap_count": len(_gap_items(readiness_summary)) + len(blockers)}})
        return {"report": report, "inventory": inventory, "guide": _recipient_guide(report, inventory), "external_manifest": external_manifest, "runtime_external_manifest": runtime_external_manifest, "decision": decision, "conflicts": conflict_report, "accepted_index": accepted_index, "readiness": readiness, "gap": gap, "program_state": program_state, "operations_state": operations_state}

    def _write_live_docs(self, program_id: str, docs: ImplementationDocument) -> None:
        self.handoff_dir(program_id).mkdir(parents=True, exist_ok=True)
        write_json(self.report_path(program_id), docs["report"])
        write_json(self.inventory_path(program_id), docs["inventory"])
        self.guide_path(program_id).write_text(docs["guide"], encoding="utf-8")
        write_json(self.external_manifest_path(program_id), docs["external_manifest"])
        if docs.get("runtime_external_manifest"):
            write_json(self.runtime_external_manifest_path(program_id), docs["runtime_external_manifest"])
        write_json(self.decision_board_path(program_id), docs["decision"])
        write_json(self.conflict_report_path(program_id), docs["conflicts"])
        write_json(self.accepted_index_path(program_id), docs["accepted_index"])
        write_json(self.readiness_path(program_id), docs["readiness"])
        write_json(self.gap_path(program_id), docs["gap"])

    def _ensure_live_docs(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        if not self.report_path(program_id).exists():
            docs = self._build_documents(program_id, payload, write_external=True)
            self._write_live_docs(program_id, docs)
            return docs
        return {
            "report": read_json(self.report_path(program_id)),
            "inventory": read_json(self.inventory_path(program_id)),
            "guide": self.guide_path(program_id).read_text(encoding="utf-8") if self.guide_path(program_id).exists() else "",
            "external_manifest": read_json(self.external_manifest_path(program_id)),
            "runtime_external_manifest": _read_optional_json(self.runtime_external_manifest_path(program_id)),
            "decision": _read_optional_json(self.decision_board_path(program_id)),
            "conflicts": _read_optional_json(self.conflict_report_path(program_id)),
            "accepted_index": _read_optional_json(self.accepted_index_path(program_id)),
            "readiness": _read_optional_json(self.readiness_path(program_id)),
            "gap": _read_optional_json(self.gap_path(program_id)),
        }

    def _docs_for_signoff(self, program_id: str) -> ImplementationDocument:
        docs = self._ensure_live_docs(program_id, {})
        for key, path in (("report", self.report_path(program_id)), ("inventory", self.inventory_path(program_id)), ("decision", self.decision_board_path(program_id)), ("accepted_index", self.accepted_index_path(program_id)), ("external_manifest", self.external_manifest_path(program_id))):
            doc = read_json(path)
            if not _integrity_ok(doc):
                raise UnifiedReleaseProgramHandoffStateError(f"Program Handoff {key} integrity failed.")
            docs[key] = doc
        if docs["report"].get("blockers"):
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff report has blockers.")
        return docs

    def _archive_documents(self, program_id: str) -> ImplementationDocument:
        if self.latest_signoff_state(program_id).get("status") != "signed":
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff must be signed before archive export.")
        signoff = read_json(self.signoff_path(program_id))
        binding = read_json(self.signoff_binding_path(program_id))
        if not _integrity_ok(signoff) or not _integrity_ok(binding):
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff signoff integrity failed.")
        if binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramHandoffStateError("Program Handoff signoff binding does not match signoff.")
        frozen = self.frozen_dir(program_id)
        docs = {
            "report": read_json(frozen / "program-handoff-report.json"),
            "inventory": read_json(frozen / "evidence-inventory.json"),
            "guide": (frozen / "recipient-guide.md").read_text(encoding="utf-8"),
            "decision": read_json(frozen / "decision-board.json"),
            "conflicts": read_json(frozen / "conflict-report.json"),
            "accepted_index": read_json(frozen / "accepted-evidence-index.json"),
            "readiness": read_json(frozen / "handoff-readiness-matrix.json"),
            "gap": read_json(frozen / "handoff-gap-plan.json"),
            "external_manifest": read_json(frozen / "external-evidence-manifest.json"),
            "signoff": signoff,
            "binding": binding,
        }
        expected = {
            "handoff_report_hash": docs["report"].get("integrity_hash"),
            "decision_board_hash": docs["decision"].get("integrity_hash"),
            "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
            "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        }
        for key, value in expected.items():
            if signoff.get(key) != value or binding.get(key) != value:
                raise UnifiedReleaseProgramHandoffStateError("Program Handoff frozen docs do not match signoff.")
        runtime_external_manifest = _read_optional_json(self.runtime_external_manifest_path(program_id)) or docs["external_manifest"]
        docs["program_summary"] = _verification_summary_from_state("program", self._current_program_state(runtime_external_manifest))
        docs["operations_summary"] = _verification_summary_from_state("operations", self._current_operations_state(runtime_external_manifest))
        docs["accepted_summary"] = self._accepted_verification_summary(runtime_external_manifest)
        return docs

    def _write_frozen(self, program_id: str, docs: ImplementationDocument) -> None:
        frozen = self.frozen_dir(program_id)
        if frozen.exists():
            shutil.rmtree(frozen)
        frozen.mkdir(parents=True, exist_ok=True)
        write_json(frozen / "program-handoff-report.json", docs["report"])
        write_json(frozen / "evidence-inventory.json", docs["inventory"])
        (frozen / "recipient-guide.md").write_text(docs["guide"], encoding="utf-8")
        write_json(frozen / "decision-board.json", docs["decision"])
        write_json(frozen / "conflict-report.json", docs["conflicts"])
        write_json(frozen / "accepted-evidence-index.json", docs["accepted_index"])
        write_json(frozen / "handoff-readiness-matrix.json", docs["readiness"])
        write_json(frozen / "handoff-gap-plan.json", docs["gap"])
        write_json(frozen / "external-evidence-manifest.json", docs["external_manifest"])

    def _external_manifest(self, program_id: str, handoff_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        path = payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path")
        if path:
            return read_json(Path(path))
        if self.runtime_external_manifest_path(program_id).exists():
            return read_json(self.runtime_external_manifest_path(program_id))
        if self.external_manifest_path(program_id).exists():
            return read_json(self.external_manifest_path(program_id))
        rows = payload.get("external_evidence") or payload.get("items") or []
        return _external_manifest_from_rows(program_id, handoff_id, rows)

    def _current_program_state(self, external_manifest: ImplementationDocument) -> ImplementationDocument:
        row = _manifest_row(external_manifest, "unified_release_program")
        checks: list[dict[str, Any]] = []
        if not row:
            return {"status": "missing", "checks": [_check("program_evidence_required", False, "Program evidence is required.")]}
        zip_path = Path(str(row.get("program_zip") or ""))
        report_path = Path(str(row.get("program_verification_report") or ""))
        binding_path = Path(str(row.get("program_signoff_binding") or ""))
        evidence_path = Path(str(row.get("program_external_evidence_manifest") or row.get("external_evidence_manifest") or ""))
        checks.extend(_path_checks("program", {"zip": zip_path, "verification": report_path, "binding": binding_path, "external_manifest": evidence_path}))
        if any(item["status"] == "failed" for item in checks):
            return {"status": "missing", "checks": checks}
        external = read_json(report_path)
        runtime = verify_unified_release_program_package(zip_path, strict=True, require_current=True, require_signed=True, external_evidence_manifest_path=evidence_path, program_signoff_binding_path=binding_path)
        checks.extend(
            [
                _check("program_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, "Program verification package type is valid."),
                _check("program_verification_integrity", _integrity_ok(external), "Program verification integrity is valid."),
                _check("program_runtime_passed", runtime.get("status") == "passed", "Program runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
                _check("program_external_passed", external.get("status") == "passed", "Program external verification passed."),
                _check("program_zip_sha256_current", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Program ZIP hash is current."),
                _check("program_manifest_hash_current", external.get("manifest_hash") == runtime.get("manifest_hash"), "Program manifest hash is current."),
            ]
        )
        return {
            "status": "ready" if not [item for item in checks if item.get("status") == "failed"] else "failed",
            "checks": checks,
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_hash": _integrity_hash(external),
            "verification_status": external.get("status"),
            "runtime_status": runtime.get("status"),
            "signoff_binding_hash": _integrity_hash(read_json(binding_path)),
            "external_evidence_manifest_hash": _integrity_hash(read_json(evidence_path)),
        }

    def _current_operations_state(self, external_manifest: ImplementationDocument) -> ImplementationDocument:
        row = _manifest_row(external_manifest, "unified_release_program_operations")
        program_row = _manifest_row(external_manifest, "unified_release_program") or {}
        checks: list[dict[str, Any]] = []
        if not row:
            return {"status": "missing", "checks": [_check("operations_evidence_required", False, "Program Operations evidence is required.")]}
        zip_path = Path(str(row.get("operations_zip") or row.get("operations_archive_zip") or ""))
        report_path = Path(str(row.get("operations_verification_report") or row.get("operations_archive_verification_report") or ""))
        program_zip = Path(str(row.get("program_zip") or program_row.get("program_zip") or ""))
        program_report = Path(str(row.get("program_verification_report") or program_row.get("program_verification_report") or ""))
        program_binding = Path(str(row.get("program_signoff_binding") or program_row.get("program_signoff_binding") or ""))
        program_external = Path(str(row.get("program_external_evidence_manifest") or row.get("external_evidence_manifest") or program_row.get("program_external_evidence_manifest") or program_row.get("external_evidence_manifest") or ""))
        checks.extend(_path_checks("operations", {"zip": zip_path, "verification": report_path, "program_zip": program_zip, "program_verification": program_report, "program_binding": program_binding, "program_external_manifest": program_external}))
        if any(item["status"] == "failed" for item in checks):
            return {"status": "missing", "checks": checks}
        external = read_json(report_path)
        runtime = verify_unified_release_program_operations_package(zip_path, strict=True, require_current=True, require_signed_program=True, require_continuous_review_clear=True, require_lifecycle_audit=True, program_zip_path=program_zip, program_verification_report_path=program_report, program_signoff_binding_path=program_binding, external_evidence_manifest_path=program_external)
        checks.extend(
            [
                _check("operations_verification_package_type", external.get("package_type") == UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, "Operations verification package type is valid."),
                _check("operations_verification_integrity", _integrity_ok(external), "Operations verification integrity is valid."),
                _check("operations_runtime_passed", runtime.get("status") == "passed", "Operations runtime verification passed.", {"blockers": runtime.get("blockers", [])}),
                _check("operations_external_passed", external.get("status") == "passed", "Operations external verification passed."),
                _check("operations_zip_sha256_current", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Operations ZIP hash is current."),
                _check("operations_manifest_hash_current", external.get("manifest_hash") == runtime.get("manifest_hash"), "Operations manifest hash is current."),
            ]
        )
        return {
            "status": "ready" if not [item for item in checks if item.get("status") == "failed"] else "failed",
            "checks": checks,
            "zip_sha256": _sha256_path(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "manifest_hash": runtime.get("manifest_hash"),
            "verification_hash": _integrity_hash(external),
            "verification_status": external.get("status"),
            "runtime_status": runtime.get("status"),
        }

    def _evidence_inventory(self, program_id: str, handoff_id: str, program_state: ImplementationDocument, operations_state: ImplementationDocument, participants: list[ImplementationDocument]) -> ImplementationDocument:
        items = [
            {"item_id": "evi-program-current", "evidence_type": "unified_release_program", "component_id": program_id, **_source_without_checks(program_state)},
            {"item_id": "evi-program-operations", "evidence_type": "unified_release_program_operations", "component_id": program_id, **_source_without_checks(operations_state)},
        ]
        for participant in participants:
            items.append({"item_id": f"evi-{participant.get('accepted_evidence_id')}", "evidence_type": "program_accepted_evidence", "component_id": handoff_id, "status": "ready", "evidence_id": participant.get("accepted_evidence_id"), "role": participant.get("role"), "organization": participant.get("organization"), "decision": participant.get("decision")})
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_handoff_evidence_inventory",
                "program_id": program_id,
                "handoff_id": handoff_id,
                "items": items,
                "summary": {
                    "ready_count": sum(1 for row in items if row.get("status") == "ready"),
                    "failed_count": sum(1 for row in items if row.get("status") == "failed"),
                    "missing_count": sum(1 for row in items if row.get("status") == "missing"),
                    "accepted_evidence_count": len(participants),
                },
            }
        )

    def _accepted_participants(self, program_id: str) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
        base = self.handoff_dir(program_id) / "accepted-evidence"
        participants: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        if not base.exists():
            return participants, conflicts
        for report_path in sorted(base.glob("*/accepted-evidence-report.json")):
            evidence_dir = report_path.parent
            report = read_json(report_path)
            binding_path = evidence_dir / "response-binding-summary.json"
            verification_summary_path = evidence_dir / "response-verification-summary.json"
            evidence_binding_path = evidence_dir / "accepted-evidence-binding-summary.json"
            if not binding_path.exists() or not verification_summary_path.exists() or not evidence_binding_path.exists():
                conflicts.append({"evidence_id": report.get("evidence_id"), "reason": "missing_response_proof"})
                continue
            binding = read_json(binding_path)
            verification_summary = read_json(verification_summary_path)
            evidence_binding = read_json(evidence_binding_path)
            if not (_integrity_ok(report) and _integrity_ok(binding) and _integrity_ok(verification_summary) and _integrity_ok(evidence_binding)):
                conflicts.append({"evidence_id": report.get("evidence_id"), "reason": "integrity_failed"})
                continue
            role = binding.get("reviewer_role")
            organization = binding.get("organization")
            decision = binding.get("decision")
            if role != (report.get("reviewer") or {}).get("role") or organization != (report.get("reviewer") or {}).get("organization") or decision != report.get("decision"):
                conflicts.append({"evidence_id": report.get("evidence_id"), "reason": "accepted_evidence_role_mismatch"})
                continue
            participants.append(
                {
                    "reviewer_id": binding.get("reviewer_id"),
                    "role": role,
                    "organization": organization,
                    "decision": decision,
                    "accepted_evidence_id": report.get("evidence_id"),
                    "response_id": report.get("response_id"),
                    "source_verified": True,
                    "accepted_evidence_zip_sha256": _sha256_path(self.accepted_evidence_zip_path(program_id, str(report.get("evidence_id")))),
                    "accepted_evidence_verification_hash": _integrity_hash(_read_optional_json(self.accepted_evidence_verification_report_path(program_id, str(report.get("evidence_id"))))),
                }
            )
        return participants, conflicts

    def _response_decision_conflicts(self, program_id: str, policy: ImplementationDocument) -> list[ImplementationDocument]:
        base = self.handoff_dir(program_id) / "responses"
        conflicts: list[dict[str, Any]] = []
        if not base.exists():
            return conflicts
        for response_path in sorted(base.glob("*/response.json")):
            try:
                response = read_json(response_path)
            except Exception as exc:
                conflicts.append({"response_id": response_path.parent.name, "reason": "response_unreadable", "message": sanitize_sensitive_text(str(exc))})
                continue
            response_id = str(response.get("response_id") or response_path.parent.name)
            decision = str(response.get("decision") or "")
            base_row = {
                "response_id": response_id,
                "reviewer_id": response.get("reviewer_id"),
                "role": response.get("reviewer_role"),
                "organization": response.get("organization"),
                "decision": decision,
            }
            if not _integrity_ok(response):
                conflicts.append({**base_row, "reason": "response_integrity_failed"})
                continue
            verification = _read_optional_json(self.response_verification_path(program_id, response_id))
            binding = _read_optional_json(self.response_binding_path(program_id, response_id))
            if not verification or not binding or not _integrity_ok(verification) or not _integrity_ok(binding):
                conflicts.append({**base_row, "reason": "response_binding_failed"})
                continue
            if binding.get("decision") != decision or binding.get("reviewer_role") != response.get("reviewer_role") or binding.get("organization") != response.get("organization"):
                conflicts.append({**base_row, "reason": "response_binding_mismatch"})
                continue
            if decision == "rejected" and policy.get("block_on_rejected", True):
                conflicts.append({**base_row, "reason": "rejected_response_present"})
            if decision == "needs_changes" and policy.get("block_on_needs_changes", True):
                conflicts.append({**base_row, "reason": "needs_changes_response_present"})
            if policy.get("block_on_critical_finding", True):
                findings = response.get("findings") if isinstance(response.get("findings"), list) else []
                if any(str(row.get("severity") or "").lower() == "critical" for row in findings if isinstance(row, dict)):
                    conflicts.append({**base_row, "reason": "critical_finding_present"})
        return conflicts

    def _accepted_index_document(self, program_id: str, participants: list[ImplementationDocument]) -> ImplementationDocument:
        handoff_id = self._handoff_id(program_id, {})
        return _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_accepted_evidence_index",
                "program_id": program_id,
                "handoff_id": handoff_id,
                "items": [
                    {
                        "evidence_id": row.get("accepted_evidence_id"),
                        "response_id": row.get("response_id"),
                        "role": row.get("role"),
                        "organization": row.get("organization"),
                        "decision": row.get("decision"),
                        "accepted_evidence_zip_sha256": row.get("accepted_evidence_zip_sha256"),
                        "accepted_evidence_verification_hash": row.get("accepted_evidence_verification_hash"),
                    }
                    for row in participants
                ],
                "summary": {"accepted_count": len(participants)},
            }
        )

    def _accepted_verification_summary(self, external_manifest: ImplementationDocument) -> ImplementationDocument:
        rows = [row for row in external_manifest.get("items", []) if row.get("evidence_type") == "program_accepted_evidence"]
        summaries = []
        for row in rows:
            report_path = Path(str(row.get("accepted_evidence_verification_report") or row.get("verification_report_path") or ""))
            if report_path.exists():
                report = read_json(report_path)
                summaries.append({"evidence_id": row.get("evidence_id"), "status": report.get("status"), "verification_hash": _integrity_hash(report), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash")})
        return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_accepted_evidence_verification_summaries", "summaries": summaries, "summary": {"accepted_count": len(summaries)}})

    def _signoff_binding(self, signoff: ImplementationDocument, event: ImplementationDocument, docs: ImplementationDocument) -> ImplementationDocument:
        binding = _with_integrity(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_handoff_signoff_binding_summary",
                "program_id": signoff.get("program_id"),
                "handoff_id": signoff.get("handoff_id"),
                "created_at": now_iso(),
                "signed_by": signoff.get("signed_by"),
                "role": signoff.get("role"),
                "reason": signoff.get("reason"),
                "signed_at": signoff.get("signed_at"),
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "latest_history_event_hash": event.get("event_hash"),
                "history_event_payload_hash": event.get("payload_hash"),
                "handoff_report_hash": docs["report"].get("integrity_hash"),
                "decision_board_hash": docs["decision"].get("integrity_hash"),
                "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
                "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                "source_hash": docs["report"].get("source_hash"),
            }
        )
        return binding

    def _append_history(self, program_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _handoff_id(self, program_id: str, payload: ImplementationDocument) -> str:
        if payload.get("handoff_id"):
            return _safe_id(str(payload["handoff_id"]))
        if self.report_path(program_id).exists():
            return _safe_id(str(read_json(self.report_path(program_id)).get("handoff_id") or "uph-000001"))
        return "uph-000001"

    def _next_review_pack_id(self, program_id: str) -> str:
        base = self.handoff_dir(program_id) / "review-packs"
        base.mkdir(parents=True, exist_ok=True)
        return f"urprp-{len(list(base.glob('urprp-*'))) + 1:06d}"

    def _next_response_id(self, program_id: str) -> str:
        base = self.handoff_dir(program_id) / "responses"
        base.mkdir(parents=True, exist_ok=True)
        return f"urpresp-{len(list(base.glob('urpresp-*'))) + 1:06d}"

    def _next_evidence_id(self, program_id: str) -> str:
        base = self.handoff_dir(program_id) / "accepted-evidence"
        base.mkdir(parents=True, exist_ok=True)
        return f"urpae-{len(list(base.glob('urpae-*'))) + 1:06d}"

    def _build_zip(self, export_dir: Path, zip_path: Path, label: str) -> ImplementationDocument:
        if not (export_dir / "manifest.json").exists():
            raise UnifiedReleaseProgramHandoffStateError(f"{label} export manifest is missing.")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        if zip_path.exists():
            zip_path.unlink()
        ArchiveBuilder.build_directory_zip(export_dir, zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            entries = sorted(info.filename for info in archive.infolist())
        manifest = read_json(export_dir / "manifest.json")
        manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
        manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
        manifest["integrity_hash"] = _integrity_hash(manifest)
        write_json(export_dir / "manifest.json", manifest)
        zip_path.unlink(missing_ok=True)
        ArchiveBuilder.build_directory_zip(export_dir, zip_path)
        return {"status": "passed", "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}


def write_handoff_external_evidence_manifest(path: Path | str, *, program_id: str, handoff_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = _external_manifest_from_rows(program_id, handoff_id, items)
    write_json(Path(path), manifest)
    return manifest


def _external_manifest_from_rows(program_id: str, handoff_id: str, rows: list[ImplementationDocument]) -> ImplementationDocument:
    normalized = []
    for row in rows:
        evidence_type = str(row.get("evidence_type") or "")
        normalized_row = {"evidence_id": _safe_id(str(row.get("evidence_id") or evidence_type or "evidence")), "evidence_type": evidence_type, "component_id": str(row.get("component_id") or row.get("program_id") or program_id)}
        for key, value in row.items():
            if key not in normalized_row and value is not None:
                normalized_row[key] = str(value) if isinstance(value, Path) else value
        normalized.append(normalized_row)
    manifest = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": program_id,
        "handoff_id": handoff_id,
        "created_at": now_iso(),
        "items": normalized,
        "summary": {"item_count": len(normalized)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _public_external_manifest(manifest: ImplementationDocument) -> ImplementationDocument:
    public_items = []
    allowed_exact = {
        "evidence_id",
        "evidence_type",
        "component_id",
        "program_id",
        "handoff_id",
        "response_id",
        "role",
        "organization",
        "decision",
    }
    allowed_suffixes = ("_hash", "_sha256", "_size_bytes", "_status")
    for row in manifest.get("items", []):
        if not isinstance(row, dict):
            continue
        public_row = {}
        for key, value in row.items():
            if key in allowed_exact or key.endswith(allowed_suffixes):
                public_row[key] = value
        if "evidence_id" not in public_row and row.get("evidence_id"):
            public_row["evidence_id"] = row.get("evidence_id")
        if "evidence_type" not in public_row and row.get("evidence_type"):
            public_row["evidence_type"] = row.get("evidence_type")
        if "component_id" not in public_row and row.get("component_id"):
            public_row["component_id"] = row.get("component_id")
        public_items.append(public_row)
    public = {
        "schema_version": manifest.get("schema_version") or UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
        "package_type": manifest.get("package_type") or UNIFIED_RELEASE_PROGRAM_HANDOFF_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": manifest.get("program_id"),
        "handoff_id": manifest.get("handoff_id"),
        "created_at": manifest.get("created_at"),
        "items": public_items,
        "summary": {"item_count": len(public_items)},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public


def _manifest_row(manifest: ImplementationDocument, evidence_type: str) -> ImplementationDocument | None:
    return next((row for row in manifest.get("items", []) if row.get("evidence_type") == evidence_type), None)


def _package_manifest(package_type: str, program_id: str, handoff_id: str, files: list[ImplementationDocument], source: ImplementationDocument) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
            "package_type": package_type,
            "program_id": program_id,
            "handoff_id": handoff_id,
            "created_at": now_iso(),
            "source": source,
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _archive_source(docs: ImplementationDocument) -> ImplementationDocument:
    return {
        "handoff_report_hash": docs["report"].get("integrity_hash"),
        "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
        "decision_board_hash": docs["decision"].get("integrity_hash"),
        "conflict_report_hash": docs["conflicts"].get("integrity_hash"),
        "accepted_evidence_index_hash": docs["accepted_index"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "gap_plan_hash": docs["gap"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "handoff_signoff_hash": docs["signoff"].get("integrity_hash"),
        "handoff_signoff_binding_hash": docs["binding"].get("integrity_hash"),
        "program_verification_summary_hash": docs["program_summary"].get("integrity_hash"),
        "operations_verification_summary_hash": docs["operations_summary"].get("integrity_hash"),
        "accepted_evidence_verification_summary_hash": docs["accepted_summary"].get("integrity_hash"),
    }


def _verification_summary_from_state(kind: str, state: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
            "package_type": f"musicforge_unified_release_program_handoff_{kind}_verification_summary",
            "status": state.get("status"),
            "zip_sha256": state.get("zip_sha256"),
            "zip_size_bytes": state.get("zip_size_bytes"),
            "manifest_hash": state.get("manifest_hash"),
            "verification_hash": state.get("verification_hash"),
            "verification_status": state.get("verification_status"),
            "runtime_status": state.get("runtime_status"),
        }
    )


def _decision_readiness(policy: ImplementationDocument, participants: list[ImplementationDocument], conflicts: list[ImplementationDocument]) -> ImplementationDocument:
    accepted = [row for row in participants if row.get("decision") in {"accepted", "accepted_with_notes"}]
    roles = {row.get("role") for row in accepted}
    orgs = {row.get("organization") for row in accepted}
    required_roles = set(policy.get("required_roles") or [])
    minimum_acceptances = int(policy.get("minimum_acceptances") or 1)
    minimum_orgs = int(policy.get("minimum_organizations") or 1)
    missing_roles = sorted(required_roles - roles)
    blockers = []
    if len(accepted) < minimum_acceptances:
        blockers.append("minimum_acceptances")
    if len(orgs) < minimum_orgs:
        blockers.append("minimum_organizations")
    if missing_roles:
        blockers.append("required_roles")
    if conflicts:
        blockers.append("accepted_evidence_conflicts")
    return {"status": "blocked" if blockers else "ready_for_signoff", "accepted_count": len(accepted), "organization_count": len(orgs), "missing_roles": missing_roles, "blockers": blockers}


def _board_policy(value: Any) -> ImplementationDocument:
    raw = value if isinstance(value, dict) else {}
    return {
        "minimum_acceptances": int(raw.get("minimum_acceptances") or DEFAULT_BOARD_POLICY["minimum_acceptances"]),
        "minimum_organizations": int(raw.get("minimum_organizations") or DEFAULT_BOARD_POLICY["minimum_organizations"]),
        "required_roles": [_bounded(role, 80) for role in raw.get("required_roles", DEFAULT_BOARD_POLICY["required_roles"])],
        "block_on_rejected": bool(raw.get("block_on_rejected", DEFAULT_BOARD_POLICY["block_on_rejected"])),
        "block_on_needs_changes": bool(raw.get("block_on_needs_changes", DEFAULT_BOARD_POLICY["block_on_needs_changes"])),
        "block_on_critical_finding": bool(raw.get("block_on_critical_finding", DEFAULT_BOARD_POLICY["block_on_critical_finding"])),
    }


def _readiness_rows(readiness: ImplementationDocument) -> list[ImplementationDocument]:
    blockers = set(readiness.get("blockers") or [])
    return [
        {"check_id": "minimum_acceptances", "status": "failed" if "minimum_acceptances" in blockers else "passed"},
        {"check_id": "minimum_organizations", "status": "failed" if "minimum_organizations" in blockers else "passed"},
        {"check_id": "required_roles", "status": "failed" if "required_roles" in blockers else "passed", "missing_roles": readiness.get("missing_roles", [])},
        {"check_id": "accepted_evidence_conflicts", "status": "failed" if "accepted_evidence_conflicts" in blockers else "passed"},
    ]


def _gap_items(readiness: ImplementationDocument) -> list[ImplementationDocument]:
    return [{"gap_id": f"gap-{index + 1:03d}", "source": blocker, "status": "manual_required"} for index, blocker in enumerate(readiness.get("blockers") or [])]


def _response_payload_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key not in {"payload_hash", "integrity_hash", "response_id", "status", "imported_at"}})


def _response_public_projection(response: ImplementationDocument) -> ImplementationDocument:
    return {
        "schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION,
        "package_type": "musicforge_unified_release_program_review_response_public_projection",
        "program_id": response.get("program_id"),
        "handoff_id": response.get("handoff_id"),
        "review_pack_id": response.get("review_pack_id"),
        "response_id": response.get("response_id"),
        "reviewer_id": response.get("reviewer_id"),
        "reviewer_name": _bounded(response.get("reviewer_name") or response.get("reviewer_id"), 120),
        "reviewer_role": response.get("reviewer_role"),
        "organization": response.get("organization"),
        "decision": response.get("decision"),
        "notes": _bounded(response.get("notes") or "", 1000),
    }


def _public_handoff_summary(docs: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_public_summary", "program_id": docs["report"].get("program_id"), "handoff_id": docs["report"].get("handoff_id"), "status": docs["report"].get("status"), "summary": docs["report"].get("summary", {})})


def _public_inventory(inventory: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_public_inventory", "items": inventory.get("items", []), "summary": inventory.get("summary", {})})


def _risk_summary(docs: ImplementationDocument) -> ImplementationDocument:
    return _with_integrity({"schema_version": UNIFIED_RELEASE_PROGRAM_HANDOFF_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_handoff_risk_summary", "risk_level": docs["report"].get("summary", {}).get("risk_level"), "blockers": docs["report"].get("blockers", [])})


def _recipient_guide(report: ImplementationDocument, inventory: ImplementationDocument) -> str:
    return "\n".join(
        [
            "# MusicForge Unified Release Program Final Handoff",
            "",
            f"Program: {report.get('program_id')}",
            f"Handoff: {report.get('handoff_id')}",
            f"Status: {report.get('status')}",
            f"Ready evidence: {inventory.get('summary', {}).get('ready_count', 0)}",
            "",
        ]
    )


def _source_without_checks(state: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in state.items() if key != "checks"}


def _path_checks(prefix: str, paths: dict[str, Path]) -> list[ImplementationDocument]:
    return [_check(f"{prefix}_{key}_exists", path.exists() and path.is_file(), f"{key} exists.", {"path": str(path)}) for key, path in paths.items()]


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}}


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _history_text(rows: list[ImplementationDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _with_integrity(doc: ImplementationDocument) -> ImplementationDocument:
    return SignoffService.seal(sanitize_metadata(doc), payload_hash=False)


def _integrity_hash(doc: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: ImplementationDocument) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _manifest_hash_from_zip(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        return manifest.get("integrity_hash")
    except Exception:
        return None


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    return read_json(path)


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "")).strip("-")[:140]


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]
