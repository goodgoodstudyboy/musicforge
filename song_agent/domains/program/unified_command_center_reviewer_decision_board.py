# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path, document_or as _document_or

import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_evidence_review import UnifiedCommandCenterEvidenceReviewStore as UnifiedCommandCenterEvidenceReviewStore
from song_agent.domains.program.unified_command_center_evidence_review_verifier import verify_unified_command_center_evidence_review_acceptance_package as verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package as verify_unified_command_center_evidence_review_package
from song_agent.domains.program.unified_command_center_reviewer_decision_board_verifier import REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION, verify_unified_command_center_reviewer_decision_board_package as verify_unified_command_center_reviewer_decision_board_package, write_unified_command_center_reviewer_decision_board_verification_report as write_unified_command_center_reviewer_decision_board_verification_report


from song_agent.domains.program import v142_uccrdb_readiness as _v142_uccrdb_readiness
from song_agent.domains.program.v142_uccrdb_readiness import (
    UnifiedCommandCenterReviewerDecisionBoardError,
    UnifiedCommandCenterReviewerDecisionBoardNotFoundError,
    UnifiedCommandCenterReviewerDecisionBoardStateError,
    _accepted_evidence_item,
    _source_document,
    _response_rows,
    _roster_document,
    _response_index_document,
    _accepted_index_document,
    _finding_ledger_document,
    _finding_row,
    _conflict_report_document,
    _quorum_report_document,
    _decision_matrix_document,
    _decision_report_document,
    _checklist_document,
    _manifest_document,
    _reviewer_guide,
    _signoff_binding_summary,
    _policy,
    _history_state,
    _history_chain_ok,
    _gate_failed,
    _read_optional_json,
    _read_zip_json,
    _integrity_hash,
    _integrity_ok,
)
from song_agent.domains.program import v142_uccrdb_evidence as _v142_uccrdb_evidence
from song_agent.domains.program.v142_uccrdb_evidence import _sha256_path, _zip_manifest_hash, _path_or_none, _bounded, _safe_id







DEFAULT_POLICY = {
    "min_accepted_count": 2,
    "min_organization_count": 1,
    "required_roles": ["technical_reviewer", "release_owner"],
    "block_on_required_rejection": True,
    "block_on_any_rejection": False,
    "block_on_high_findings": True,
    "block_on_critical_findings": True,
}


class UnifiedCommandCenterReviewerDecisionBoardStore:
    def __init__(
        self,
        center_store: UnifiedCommandCenterStore | None = None,
        *,
        evidence_review_store: UnifiedCommandCenterEvidenceReviewStore | None = None,
    ) -> None:
        self.center_store = center_store or UnifiedCommandCenterStore()
        self.evidence_review_store = evidence_review_store or UnifiedCommandCenterEvidenceReviewStore(self.center_store)
        self.lock = threading.RLock()

    def boards_dir(self, center_id: str) -> Path:
        return self.center_store.center_dir(center_id) / "reviewer-decision-boards"

    def board_dir(self, center_id: str, board_id: str) -> Path:
        return self.boards_dir(center_id) / _safe_id(board_id)

    def export_dir(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "export"

    def local_paths_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "local-paths.json"

    def source_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "board-source.json"

    def roster_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "reviewer-roster.json"

    def response_index_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "response-index.json"

    def accepted_index_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "accepted-evidence-index.json"

    def finding_ledger_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "finding-ledger.json"

    def conflict_report_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "conflict-report.json"

    def quorum_report_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "quorum-report.json"

    def decision_matrix_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "decision-matrix.json"

    def decision_report_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "decision-report.json"

    def checklist_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "manual-checklist.json"

    def signoff_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "decision-signoff.json"

    def signoff_binding_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "signoff-binding-summary.json"

    def history_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "board-history.jsonl"

    def manifest_path(self, center_id: str, board_id: str) -> Path:
        return self.export_dir(center_id, board_id) / "manifest.json"

    def zip_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "reviewer-decision-board-archive.zip"

    def verification_report_path(self, center_id: str, board_id: str) -> Path:
        return self.board_dir(center_id, board_id) / "verification-report.json"

    def list_boards(self, center_id: str) -> list[DomainDocument]:
        if not self.boards_dir(center_id).exists():
            return []
        rows = []
        for path in sorted(self.boards_dir(center_id).glob("uccdb-*")):
            source = path / "board-source.json"
            if source.exists():
                rows.append(read_json(source))
        return rows

    def get_board(self, center_id: str, board_id: str) -> DomainDocument:
        if not self.source_path(center_id, board_id).exists():
            raise UnifiedCommandCenterReviewerDecisionBoardNotFoundError(f"Unified Command Center Reviewer Decision Board not found: {board_id}.")
        return {
            "source": read_json(self.source_path(center_id, board_id)),
            "reviewer_roster": _read_optional_json(self.roster_path(center_id, board_id)),
            "response_index": _read_optional_json(self.response_index_path(center_id, board_id)),
            "accepted_evidence_index": _read_optional_json(self.accepted_index_path(center_id, board_id)),
            "finding_ledger": _read_optional_json(self.finding_ledger_path(center_id, board_id)),
            "conflict_report": _read_optional_json(self.conflict_report_path(center_id, board_id)),
            "quorum_report": _read_optional_json(self.quorum_report_path(center_id, board_id)),
            "decision_matrix": _read_optional_json(self.decision_matrix_path(center_id, board_id)),
            "decision_report": _read_optional_json(self.decision_report_path(center_id, board_id)),
            "manual_checklist": _read_optional_json(self.checklist_path(center_id, board_id)),
            "decision_signoff": _read_optional_json(self.signoff_path(center_id, board_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(center_id, board_id)),
            "manifest": _read_optional_json(self.manifest_path(center_id, board_id)),
            "verification": _read_optional_json(self.verification_report_path(center_id, board_id)),
        }

    def create_board(self, center_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            board_id = str(payload.get("board_id") or self._next_board_id(center_id))
            if self.source_path(center_id, board_id).exists():
                raise UnifiedCommandCenterReviewerDecisionBoardStateError(f"Reviewer Decision Board already exists: {board_id}.")
            self.board_dir(center_id, board_id).mkdir(parents=True, exist_ok=True)
            paths = self._local_paths(center_id, board_id, payload, include_default_policy=True)
            docs = self._build_documents(center_id, board_id, paths)
            self._write_docs(center_id, board_id, docs)
            write_json(self.local_paths_path(center_id, board_id), paths)
            return docs

    def refresh_board(self, center_id: str, board_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self._ensure_unsigned(center_id, board_id)
            paths = self._merged_local_paths(center_id, board_id, payload)
            docs = self._build_documents(center_id, board_id, paths)
            self._write_docs(center_id, board_id, docs)
            write_json(self.local_paths_path(center_id, board_id), paths)
            return docs

    def signoff(self, center_id: str, board_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self._ensure_unsigned(center_id, board_id)
            if "policy" in payload:
                raise UnifiedCommandCenterReviewerDecisionBoardStateError("Reviewer Decision Board policy cannot be changed during signoff. Refresh the unsigned Board first.")
            paths = self._stored_local_paths(center_id, board_id)
            docs = self._build_documents(center_id, board_id, paths)
            decision = docs["decision_report"]
            if decision.get("status") != "ready_for_signoff":
                raise UnifiedCommandCenterReviewerDecisionBoardStateError("Reviewer Decision Board is not ready for signoff.")
            self._write_docs(center_id, board_id, docs)
            write_json(self.local_paths_path(center_id, board_id), paths)
            now = now_iso()
            signoff = sanitize_metadata(
                {
                    "schema_version": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_command_center_reviewer_decision_board_signoff",
                    "center_id": center_id,
                    "board_id": board_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "decision-board-chair", 120),
                    "role": _bounded(payload.get("role") or "decision_board_chair", 80),
                    "reason": _bounded(payload.get("reason") or "Reviewer Decision Board approved.", 1000),
                    "signed_at": now,
                    "source_hash": docs["source"].get("source_hash"),
                    "board_source_hash": docs["source"].get("integrity_hash"),
                    "reviewer_roster_hash": docs["reviewer_roster"].get("integrity_hash"),
                    "response_index_hash": docs["response_index"].get("integrity_hash"),
                    "accepted_evidence_index_hash": docs["accepted_evidence_index"].get("integrity_hash"),
                    "finding_ledger_hash": docs["finding_ledger"].get("integrity_hash"),
                    "conflict_report_hash": docs["conflict_report"].get("integrity_hash"),
                    "quorum_report_hash": docs["quorum_report"].get("integrity_hash"),
                    "decision_matrix_hash": docs["decision_matrix"].get("integrity_hash"),
                    "decision_report_hash": docs["decision_report"].get("integrity_hash"),
                    "manual_checklist_hash": docs["manual_checklist"].get("integrity_hash"),
                    "summary": docs["decision_report"].get("summary", {}),
                    "tool": {"name": "MusicForge Unified Command Center Reviewer Decision Board", "version": __version__},
                }
            )
            signoff["payload_hash"] = _integrity_hash(signoff)
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(center_id, board_id), signoff)
            event = self._append_history(
                center_id,
                board_id,
                {
                    "event_type": "ucc_reviewer_decision_board_signoff_created",
                    "created_at": now,
                    "center_id": center_id,
                    "board_id": board_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "decision_report_hash": signoff.get("decision_report_hash"),
                    "quorum_report_hash": signoff.get("quorum_report_hash"),
                    "accepted_evidence_index_hash": signoff.get("accepted_evidence_index_hash"),
                },
            )
            binding = _signoff_binding_summary(center_id, board_id, signoff, event)
            write_json(self.signoff_binding_path(center_id, board_id), binding)
            return signoff

    def export_archive(self, center_id: str, board_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            docs = self._signed_docs_for_export(center_id, board_id)
            export_dir = self.export_dir(center_id, board_id)
            export_dir.mkdir(parents=True, exist_ok=True)
            files = {
                "board-source.json": docs["source"],
                "reviewer-roster.json": docs["reviewer_roster"],
                "response-index.json": docs["response_index"],
                "accepted-evidence-index.json": docs["accepted_evidence_index"],
                "finding-ledger.json": docs["finding_ledger"],
                "conflict-report.json": docs["conflict_report"],
                "quorum-report.json": docs["quorum_report"],
                "decision-matrix.json": docs["decision_matrix"],
                "decision-report.json": docs["decision_report"],
                "manual-checklist.json": docs["manual_checklist"],
                "decision-signoff.json": docs["decision_signoff"],
                "signoff-binding-summary.json": docs["signoff_binding"],
            }
            for rel, doc in files.items():
                write_json(export_dir / rel, doc)
            (export_dir / "board-history.jsonl").write_text(self.history_path(center_id, board_id).read_text(encoding="utf-8") if self.history_path(center_id, board_id).exists() else "", encoding="utf-8")
            (export_dir / "reviewer-guide.md").write_text(_reviewer_guide(docs), encoding="utf-8")
            (export_dir / "README.txt").write_text("MusicForge Unified Command Center Reviewer Decision Board Archive\n", encoding="utf-8")
            manifest = _manifest_document(center_id, board_id, docs, export_dir)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": "signed", "export_dir": str(export_dir), "manifest_hash": manifest.get("integrity_hash")}

    def build_zip(self, center_id: str, board_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        with self.lock:
            self.export_archive(center_id, board_id, payload)
            zip_path = self.zip_path(center_id, board_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for rel in sorted(REQUIRED_ENTRIES):
                    archive.write(self.export_dir(center_id, board_id) / rel, rel)
            report = self.verify_archive(center_id, board_id, payload)
            return {"status": report.get("status"), "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "verification_report": str(self.verification_report_path(center_id, board_id))}

    def verify_archive(self, center_id: str, board_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        paths = self._merged_local_paths(center_id, board_id, payload)
        report = verify_unified_command_center_reviewer_decision_board_package(
            self.zip_path(center_id, board_id),
            strict=bool(payload.get("strict", True)),
            require_signed=bool(payload.get("require_signed", True)),
            require_quorum=bool(payload.get("require_quorum", True)),
            evidence_review_path=_path_or_none(paths.get("review_zip")),
            evidence_review_verification_report_path=_path_or_none(paths.get("review_verification_report")),
            accepted_evidence_paths=[_path_or_none(row.get("zip_path")) for row in paths.get("accepted_evidence", [])],
            accepted_evidence_verification_report_paths=[_path_or_none(row.get("verification_report_path")) for row in paths.get("accepted_evidence", [])],
            accepted_evidence_response_verification_report_paths=[_path_or_none(row.get("response_verification_report_path")) for row in paths.get("accepted_evidence", [])],
        )
        write_unified_command_center_reviewer_decision_board_verification_report(report, self.verification_report_path(center_id, board_id))
        return report

    def gate(
        self,
        center_id: str,
        *,
        required: bool = False,
        board_id: str | None = None,
        archive_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        require_signed: bool = True,
        require_quorum: bool = True,
        payload: DomainDocument | None = None,
    ) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        payload = payload or {}
        try:
            if board_id and not archive_zip_path:
                archive_zip_path = self.zip_path(center_id, board_id)
            if board_id and not verification_report_path:
                verification_report_path = self.verification_report_path(center_id, board_id)
            if not archive_zip_path or not verification_report_path:
                return _gate_failed("Unified Command Center Reviewer Decision Board archive evidence is missing.")
            paths = self._merged_local_paths(center_id, board_id, payload) if board_id else payload
            runtime = verify_unified_command_center_reviewer_decision_board_package(
                archive_zip_path,
                strict=True,
                require_signed=require_signed,
                require_quorum=require_quorum,
                evidence_review_path=_path_or_none(paths.get("review_zip")),
                evidence_review_verification_report_path=_path_or_none(paths.get("review_verification_report")),
                accepted_evidence_paths=[_path_or_none(row.get("zip_path")) for row in paths.get("accepted_evidence", [])],
                accepted_evidence_verification_report_paths=[_path_or_none(row.get("verification_report_path")) for row in paths.get("accepted_evidence", [])],
                accepted_evidence_response_verification_report_paths=[_path_or_none(row.get("response_verification_report_path")) for row in paths.get("accepted_evidence", [])],
            )
            external = read_json(Path(verification_report_path))
            if (
                external.get("status") != "passed"
                or runtime.get("status") != "passed"
                or external.get("zip_sha256") != runtime.get("zip_sha256")
                or external.get("manifest_hash") != runtime.get("manifest_hash")
            ):
                return _gate_failed("Unified Command Center Reviewer Decision Board verification failed.", verification=runtime)
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center Reviewer Decision Board gate passed.", "verification": runtime}
        except (OSError, ValueError, UnifiedCommandCenterReviewerDecisionBoardError) as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def _next_board_id(self, center_id: str) -> str:
        existing = []
        if self.boards_dir(center_id).exists():
            existing = [path.name for path in self.boards_dir(center_id).glob("uccdb-*")]
        index = len(existing) + 1
        while True:
            candidate = f"uccdb-{index:06d}"
            if not self.source_path(center_id, candidate).exists():
                return candidate
            index += 1

    def _local_paths(self, center_id: str, board_id: str, payload: ImplementationDocument, *, include_default_policy: bool = False) -> ImplementationDocument:
        review_id = str(payload.get("review_id") or "")
        if not review_id:
            reviews = self.evidence_review_store.list_reviews(center_id)
            review_id = str((reviews[-1] if reviews else {}).get("review_id") or "")
        accepted_rows = _as_list(payload.get("accepted_evidence"))
        normalized_accepted: list[ImplementationDocument] = []
        for row in accepted_rows:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("evidence_id") or "")
            normalized_accepted.append(
                {
                    "evidence_id": evidence_id,
                    "role": _bounded(row.get("role") or row.get("reviewer_role") or "", 80),
                    "organization": _bounded(row.get("organization") or "", 120),
                    "reviewer_id": _bounded(row.get("reviewer_id") or row.get("reviewer") or "", 120),
                    "zip_path": str(row.get("zip_path") or row.get("accepted_evidence_zip") or row.get("acceptance_zip") or (self.evidence_review_store.accepted_evidence_zip_path(center_id, review_id, evidence_id) if review_id and evidence_id else "")),
                    "verification_report_path": str(row.get("verification_report_path") or row.get("accepted_evidence_verification_report") or row.get("acceptance_verification_report") or (self.evidence_review_store.accepted_evidence_verification_report_path(center_id, review_id, evidence_id) if review_id and evidence_id else "")),
                    "response_verification_report_path": str(row.get("response_verification_report_path") or row.get("accepted_evidence_response_verification_report") or row.get("response_verification_report") or (self.evidence_review_store.accepted_evidence_dir(center_id, review_id, evidence_id) / "response-verification-summary.json" if review_id and evidence_id else "")),
                }
            )
        paths = {
            "board_id": board_id,
            "review_id": review_id,
            "review_zip": str(payload.get("review_zip") or payload.get("evidence_review_zip") or payload.get("unified_command_center_evidence_review") or (self.evidence_review_store.zip_path(center_id, review_id) if review_id else "")),
            "review_verification_report": str(payload.get("review_verification_report") or payload.get("evidence_review_verification_report") or (self.evidence_review_store.verification_report_path(center_id, review_id) if review_id else "")),
            "accepted_evidence": normalized_accepted,
            "responses": sanitize_metadata(_as_list(payload.get("responses"))),
            "findings": sanitize_metadata(_as_list(payload.get("findings"))),
        }
        if isinstance(payload.get("policy"), dict):
            paths["policy"] = _policy(payload["policy"])
        elif include_default_policy:
            paths["policy"] = _policy({})
        return paths

    def _merged_local_paths(self, center_id: str, board_id: str | None, payload: ImplementationDocument) -> ImplementationDocument:
        base: ImplementationDocument = {}
        if board_id and self.local_paths_path(center_id, board_id).exists():
            base = read_json(self.local_paths_path(center_id, board_id))
        incoming = self._local_paths(center_id, board_id or str(payload.get("board_id") or ""), payload) if payload else {}
        for key, value in incoming.items():
            if key == "policy":
                continue
            if value not in (None, "", [], {}):
                base[key] = value
        if "policy" in incoming:
            explicit_policy = _document_or(payload.get("policy"), incoming["policy"])
            base["policy"] = _policy({**(_as_document(base.get("policy"))), **explicit_policy})
        return base

    def _stored_local_paths(self, center_id: str, board_id: str) -> ImplementationDocument:
        path = self.local_paths_path(center_id, board_id)
        if not path.exists():
            raise UnifiedCommandCenterReviewerDecisionBoardNotFoundError(f"Unified Command Center Reviewer Decision Board not found: {board_id}.")
        return read_json(path)

    def _build_documents(self, center_id: str, board_id: str, paths: ImplementationDocument) -> ImplementationDocument:
        source = _source_document(center_id, board_id, paths)
        accepted_items = self._accepted_evidence_items(paths)
        response_rows = _response_rows(paths, accepted_items)
        roster = _roster_document(center_id, board_id, source, accepted_items, response_rows)
        response_index = _response_index_document(center_id, board_id, source, response_rows)
        accepted_index = _accepted_index_document(center_id, board_id, source, accepted_items)
        findings = _finding_ledger_document(center_id, board_id, source, response_rows, _as_list(paths.get("findings")))
        conflicts = _conflict_report_document(center_id, board_id, source, response_rows, findings, source.get("policy", {}))
        quorum = _quorum_report_document(center_id, board_id, source, accepted_items, response_rows)
        matrix = _decision_matrix_document(center_id, board_id, source, roster, response_index, quorum, conflicts)
        decision = _decision_report_document(center_id, board_id, source, quorum, conflicts, matrix)
        checklist = _checklist_document(center_id, board_id, source, decision)
        return {
            "source": source,
            "reviewer_roster": roster,
            "response_index": response_index,
            "accepted_evidence_index": accepted_index,
            "finding_ledger": findings,
            "conflict_report": conflicts,
            "quorum_report": quorum,
            "decision_matrix": matrix,
            "decision_report": decision,
            "manual_checklist": checklist,
        }

    def _accepted_evidence_items(self, paths: ImplementationDocument) -> list[ImplementationDocument]:
        items: list[ImplementationDocument] = []
        review_zip = paths.get("review_zip")
        review_report = paths.get("review_verification_report")
        for row in paths.get("accepted_evidence", []) if isinstance(paths.get("accepted_evidence"), list) else []:
            if not isinstance(row, dict):
                continue
            item = _accepted_evidence_item(row, review_zip, review_report)
            items.append(item)
        return items

    def _write_docs(self, center_id: str, board_id: str, docs: ImplementationDocument) -> None:
        write_json(self.source_path(center_id, board_id), docs["source"])
        write_json(self.roster_path(center_id, board_id), docs["reviewer_roster"])
        write_json(self.response_index_path(center_id, board_id), docs["response_index"])
        write_json(self.accepted_index_path(center_id, board_id), docs["accepted_evidence_index"])
        write_json(self.finding_ledger_path(center_id, board_id), docs["finding_ledger"])
        write_json(self.conflict_report_path(center_id, board_id), docs["conflict_report"])
        write_json(self.quorum_report_path(center_id, board_id), docs["quorum_report"])
        write_json(self.decision_matrix_path(center_id, board_id), docs["decision_matrix"])
        write_json(self.decision_report_path(center_id, board_id), docs["decision_report"])
        write_json(self.checklist_path(center_id, board_id), docs["manual_checklist"])

    def _signed_docs_for_export(self, center_id: str, board_id: str) -> ImplementationDocument:
        docs = self.get_board(center_id, board_id)
        signoff = docs["decision_signoff"]
        if not signoff:
            raise UnifiedCommandCenterReviewerDecisionBoardStateError("Reviewer Decision Board must be signed before archive export.")
        if not _integrity_ok(signoff):
            raise UnifiedCommandCenterReviewerDecisionBoardStateError("Reviewer Decision Board signoff integrity failed.")
        expected = {
            "board_source_hash": docs["source"].get("integrity_hash"),
            "reviewer_roster_hash": docs["reviewer_roster"].get("integrity_hash"),
            "response_index_hash": docs["response_index"].get("integrity_hash"),
            "accepted_evidence_index_hash": docs["accepted_evidence_index"].get("integrity_hash"),
            "finding_ledger_hash": docs["finding_ledger"].get("integrity_hash"),
            "conflict_report_hash": docs["conflict_report"].get("integrity_hash"),
            "quorum_report_hash": docs["quorum_report"].get("integrity_hash"),
            "decision_matrix_hash": docs["decision_matrix"].get("integrity_hash"),
            "decision_report_hash": docs["decision_report"].get("integrity_hash"),
            "manual_checklist_hash": docs["manual_checklist"].get("integrity_hash"),
        }
        mismatches = [key for key, value in expected.items() if signoff.get(key) != value]
        if mismatches:
            raise UnifiedCommandCenterReviewerDecisionBoardStateError(f"Reviewer Decision Board signed evidence changed: {', '.join(mismatches)}.")
        if not _history_chain_ok(self.history_path(center_id, board_id), signoff.get("integrity_hash")):
            raise UnifiedCommandCenterReviewerDecisionBoardStateError("Reviewer Decision Board signoff history integrity failed.")
        if not docs["signoff_binding"] or docs["signoff_binding"].get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedCommandCenterReviewerDecisionBoardStateError("Reviewer Decision Board signoff binding is missing or stale.")
        return docs

    def _ensure_unsigned(self, center_id: str, board_id: str) -> None:
        state = _history_state(self.history_path(center_id, board_id))
        if state.get("signed"):
            raise UnifiedCommandCenterReviewerDecisionBoardStateError("Signed Reviewer Decision Board cannot be modified without reset.")
        if self.signoff_path(center_id, board_id).exists():
            raise UnifiedCommandCenterReviewerDecisionBoardStateError("Reviewer Decision Board is signed.")

    def _append_history(self, center_id: str, board_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        path = self.history_path(center_id, board_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = None
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    previous = json.loads(line).get("event_hash")
        event = sanitize_metadata({**payload, "previous_event_hash": previous})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

_v142_uccrdb_readiness.bind_globals(globals())
_v142_uccrdb_evidence.bind_globals(globals())
