from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

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
from song_agent.domains.program.unified_command_center_evidence_review import UnifiedCommandCenterEvidenceReviewStore
from song_agent.domains.program.unified_command_center_evidence_review_verifier import verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package
from song_agent.domains.program.unified_command_center_reviewer_decision_board_verifier import REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION, verify_unified_command_center_reviewer_decision_board_package, write_unified_command_center_reviewer_decision_board_verification_report


class UnifiedCommandCenterReviewerDecisionBoardError(ValueError):
    pass


class UnifiedCommandCenterReviewerDecisionBoardNotFoundError(UnifiedCommandCenterReviewerDecisionBoardError):
    pass


class UnifiedCommandCenterReviewerDecisionBoardStateError(UnifiedCommandCenterReviewerDecisionBoardError):
    pass


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

    def list_boards(self, center_id: str) -> list[dict[str, Any]]:
        if not self.boards_dir(center_id).exists():
            return []
        rows = []
        for path in sorted(self.boards_dir(center_id).glob("uccdb-*")):
            source = path / "board-source.json"
            if source.exists():
                rows.append(read_json(source))
        return rows

    def get_board(self, center_id: str, board_id: str) -> dict[str, Any]:
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

    def create_board(self, center_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def refresh_board(self, center_id: str, board_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self._ensure_unsigned(center_id, board_id)
            paths = self._merged_local_paths(center_id, board_id, payload)
            docs = self._build_documents(center_id, board_id, paths)
            self._write_docs(center_id, board_id, docs)
            write_json(self.local_paths_path(center_id, board_id), paths)
            return docs

    def signoff(self, center_id: str, board_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def export_archive(self, center_id: str, board_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def build_zip(self, center_id: str, board_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_archive(self, center_id: str, board_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        accepted_rows = payload.get("accepted_evidence") if isinstance(payload.get("accepted_evidence"), list) else []
        normalized_accepted: list[dict[str, Any]] = []
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
            "responses": sanitize_metadata(payload.get("responses") if isinstance(payload.get("responses"), list) else []),
            "findings": sanitize_metadata(payload.get("findings") if isinstance(payload.get("findings"), list) else []),
        }
        if isinstance(payload.get("policy"), dict):
            paths["policy"] = _policy(payload["policy"])
        elif include_default_policy:
            paths["policy"] = _policy({})
        return paths

    def _merged_local_paths(self, center_id: str, board_id: str | None, payload: ImplementationDocument) -> ImplementationDocument:
        base: dict[str, Any] = {}
        if board_id and self.local_paths_path(center_id, board_id).exists():
            base = read_json(self.local_paths_path(center_id, board_id))
        incoming = self._local_paths(center_id, board_id or str(payload.get("board_id") or ""), payload) if payload else {}
        for key, value in incoming.items():
            if key == "policy":
                continue
            if value not in (None, "", [], {}):
                base[key] = value
        if "policy" in incoming:
            explicit_policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else incoming["policy"]
            base["policy"] = _policy({**(base.get("policy") if isinstance(base.get("policy"), dict) else {}), **explicit_policy})
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
        findings = _finding_ledger_document(center_id, board_id, source, response_rows, paths.get("findings") if isinstance(paths.get("findings"), list) else [])
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
        items: list[dict[str, Any]] = []
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


def _accepted_evidence_item(row: ImplementationDocument, review_zip: Any, review_report: Any) -> ImplementationDocument:
    zip_path = _path_or_none(row.get("zip_path"))
    verification_report_path = _path_or_none(row.get("verification_report_path"))
    response_report_path = _path_or_none(row.get("response_verification_report_path"))
    runtime: dict[str, Any] = {}
    external: dict[str, Any] = {}
    response_summary: dict[str, Any] = {}
    public_response: dict[str, Any] = {}
    blockers: list[str] = []
    if not zip_path or not zip_path.exists():
        blockers.append("accepted_evidence_zip_missing")
    if not verification_report_path or not verification_report_path.exists():
        blockers.append("accepted_evidence_verification_missing")
    if not response_report_path or not response_report_path.exists():
        blockers.append("accepted_evidence_response_verification_missing")
    if not blockers:
        runtime = verify_unified_command_center_evidence_review_acceptance_package(
            zip_path,
            strict=True,
            require_accepted=True,
            review_pack_path=review_zip,
            review_pack_verification_report_path=review_report,
            response_verification_report_path=response_report_path,
        )
        external = read_json(verification_report_path)
        response_summary = read_json(response_report_path)
        public_response = _read_zip_json(zip_path, "original-response-public.json")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            blockers.append("accepted_evidence_verification_failed")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            blockers.append("accepted_evidence_verification_stale")
    reviewer = public_response.get("reviewer") if isinstance(public_response.get("reviewer"), dict) else {}
    role = _bounded(reviewer.get("role") or "reviewer", 80)
    organization = _bounded(reviewer.get("organization") or "", 120)
    reviewer_name = _bounded(reviewer.get("name") or "Reviewer", 120)
    hint_role = _bounded(row.get("role") or "", 80)
    hint_organization = _bounded(row.get("organization") or "", 120)
    hint_reviewer = _bounded(row.get("reviewer_id") or "", 120)
    if public_response:
        if hint_role and hint_role != role:
            blockers.append("accepted_evidence_role_mismatch")
        if hint_organization and hint_organization != organization:
            blockers.append("accepted_evidence_organization_mismatch")
        if hint_reviewer and hint_reviewer != reviewer_name:
            blockers.append("accepted_evidence_reviewer_mismatch")
    item = {
        "evidence_id": str(row.get("evidence_id") or runtime.get("summary", {}).get("evidence_id") or ""),
        "response_id": str(public_response.get("response_id") or response_summary.get("response_id") or ""),
        "result": public_response.get("result") or runtime.get("summary", {}).get("result"),
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "reviewer": {
            "name": reviewer_name,
            "organization": organization,
            "role": role,
        },
        "payload_hints": {
            "reviewer": hint_reviewer,
            "organization": hint_organization,
            "role": hint_role,
        },
        "role": role,
        "organization": organization,
        "zip_sha256": runtime.get("zip_sha256") or _sha256_path(zip_path),
        "zip_size_bytes": runtime.get("zip_size_bytes") or (zip_path.stat().st_size if zip_path and zip_path.exists() else None),
        "manifest_hash": runtime.get("manifest_hash"),
        "acceptance_verification_hash": external.get("integrity_hash"),
        "response_verification_hash": response_summary.get("integrity_hash"),
        "response_public_hash": public_response.get("integrity_hash"),
        "review_pack_zip_sha256": (public_response.get("bindings") or {}).get("review_pack_zip_sha256") or _read_zip_json(zip_path, "acceptance-report.json").get("review_pack_zip_sha256") if zip_path and zip_path.exists() else None,
        "findings": public_response.get("findings", []) if isinstance(public_response.get("findings"), list) else [],
    }
    item["item_hash"] = stable_hash(item)
    return item


def _source_document(center_id: str, board_id: str, paths: ImplementationDocument) -> ImplementationDocument:
    review_zip = _path_or_none(paths.get("review_zip"))
    review_verification_report = _path_or_none(paths.get("review_verification_report"))
    review_verification = read_json(review_verification_report) if review_verification_report and review_verification_report.exists() else {}
    runtime = verify_unified_command_center_evidence_review_package(review_zip, strict=False, require_replay_passed=False) if review_zip and review_zip.exists() else {}
    policy = _policy(paths.get("policy") if isinstance(paths.get("policy"), dict) else {})
    source = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_reviewer_decision_board_source",
            "center_id": center_id,
            "board_id": board_id,
            "review_id": paths.get("review_id"),
            "created_at": now_iso(),
            "status": "draft",
            "policy": policy,
            "evidence_review": {
                "zip_sha256": runtime.get("zip_sha256") or _sha256_path(review_zip),
                "zip_size_bytes": runtime.get("zip_size_bytes") or (review_zip.stat().st_size if review_zip and review_zip.exists() else None),
                "manifest_hash": runtime.get("manifest_hash") or _zip_manifest_hash(review_zip),
                "verification_hash": review_verification.get("integrity_hash"),
                "verification_status": review_verification.get("status"),
                "runtime_status": runtime.get("status"),
            },
        }
    )
    source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash", "created_at"}})
    source["integrity_hash"] = _integrity_hash(source)
    return source


def _response_rows(paths: ImplementationDocument, accepted_items: list[ImplementationDocument]) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    for item in accepted_items:
        rows.append(
            {
                "response_id": item.get("response_id"),
                "result": item.get("result"),
                "status": item.get("status"),
                "reviewer": item.get("reviewer"),
                "role": item.get("role"),
                "organization": item.get("organization"),
                "accepted_evidence_id": item.get("evidence_id"),
                "accepted_evidence_hash": item.get("item_hash"),
                "findings": item.get("findings", []),
            }
        )
    for row in paths.get("responses", []) if isinstance(paths.get("responses"), list) else []:
        if not isinstance(row, dict):
            continue
        reviewer = row.get("reviewer") if isinstance(row.get("reviewer"), dict) else {}
        rows.append(
            sanitize_metadata(
                {
                    "response_id": _bounded(row.get("response_id") or row.get("id") or f"manual-{len(rows) + 1:03d}", 120),
                    "result": _bounded(row.get("result") or "needs_changes", 40),
                    "status": _bounded(row.get("status") or "current", 40),
                    "reviewer": {
                        "name": _bounded(reviewer.get("name") or row.get("reviewer_name") or "Reviewer", 120),
                        "organization": _bounded(reviewer.get("organization") or row.get("organization") or "", 120),
                        "role": _bounded(reviewer.get("role") or row.get("role") or "reviewer", 80),
                    },
                    "role": _bounded(row.get("role") or reviewer.get("role") or "reviewer", 80),
                    "organization": _bounded(row.get("organization") or reviewer.get("organization") or "", 120),
                    "accepted_evidence_id": row.get("accepted_evidence_id"),
                    "findings": row.get("findings") if isinstance(row.get("findings"), list) else [],
                }
            )
        )
    return rows


def _roster_document(center_id: str, board_id: str, source: ImplementationDocument, accepted_items: list[ImplementationDocument], responses: list[ImplementationDocument]) -> ImplementationDocument:
    reviewers: dict[str, dict[str, Any]] = {}
    for row in responses:
        reviewer = row.get("reviewer") if isinstance(row.get("reviewer"), dict) else {}
        key = str(row.get("response_id") or reviewer.get("name") or len(reviewers))
        reviewers[key] = {
            "reviewer_id": key,
            "name": reviewer.get("name"),
            "organization": row.get("organization") or reviewer.get("organization"),
            "role": row.get("role") or reviewer.get("role"),
            "result": row.get("result"),
            "accepted_evidence_id": row.get("accepted_evidence_id"),
        }
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_roster", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "reviewers": list(reviewers.values()), "summary": {"reviewer_count": len(reviewers), "accepted_reviewer_count": len([item for item in accepted_items if item.get("status") == "passed"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _response_index_document(center_id: str, board_id: str, source: ImplementationDocument, responses: list[ImplementationDocument]) -> ImplementationDocument:
    items = []
    for row in responses:
        entry = dict(row)
        entry["response_hash"] = stable_hash(entry)
        items.append(entry)
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_response_index", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "responses": items, "summary": {"response_count": len(items), "accepted_count": len([row for row in items if row.get("result") == "accepted"]), "needs_changes_count": len([row for row in items if row.get("result") == "needs_changes"]), "rejected_count": len([row for row in items if row.get("result") == "rejected"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _accepted_index_document(center_id: str, board_id: str, source: ImplementationDocument, accepted_items: list[ImplementationDocument]) -> ImplementationDocument:
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_accepted_evidence_index", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "items": accepted_items, "summary": {"accepted_evidence_count": len(accepted_items), "passed_count": len([row for row in accepted_items if row.get("status") == "passed"]), "failed_count": len([row for row in accepted_items if row.get("status") != "passed"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _finding_ledger_document(center_id: str, board_id: str, source: ImplementationDocument, responses: list[ImplementationDocument], extra_findings: list[Any]) -> ImplementationDocument:
    findings: list[dict[str, Any]] = []
    index = 1
    for row in responses:
        for finding in row.get("findings", []) if isinstance(row.get("findings"), list) else []:
            if isinstance(finding, dict):
                findings.append(_finding_row(index, row, finding))
                index += 1
    for finding in extra_findings:
        if isinstance(finding, dict):
            findings.append(_finding_row(index, {}, finding))
            index += 1
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_finding_ledger", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "findings": findings, "summary": {"finding_count": len(findings), "high_count": len([row for row in findings if row.get("severity") == "high"]), "critical_count": len([row for row in findings if row.get("severity") == "critical"]), "open_high_or_critical_count": len([row for row in findings if row.get("status") == "open" and row.get("severity") in {"high", "critical"}])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _finding_row(index: int, response: ImplementationDocument, finding: ImplementationDocument) -> ImplementationDocument:
    row = sanitize_metadata(
        {
            "finding_id": _bounded(finding.get("finding_id") or f"finding-{index:03d}", 80),
            "response_id": response.get("response_id"),
            "role": response.get("role"),
            "severity": _bounded(finding.get("severity") or "low", 40).lower(),
            "component": _bounded(finding.get("component") or "", 120),
            "message": _bounded(finding.get("message") or finding.get("summary") or "", 1000),
            "status": _bounded(finding.get("status") or "open", 40).lower(),
        }
    )
    row["finding_hash"] = stable_hash(row)
    return row


def _conflict_report_document(center_id: str, board_id: str, source: ImplementationDocument, responses: list[ImplementationDocument], findings: ImplementationDocument, policy: ImplementationDocument) -> ImplementationDocument:
    required_roles = set(policy.get("required_roles") or [])
    rejected_required = [row for row in responses if row.get("result") == "rejected" and row.get("role") in required_roles]
    rejected_any = [row for row in responses if row.get("result") == "rejected"]
    open_high = [row for row in findings.get("findings", []) if row.get("status") == "open" and row.get("severity") == "high"]
    open_critical = [row for row in findings.get("findings", []) if row.get("status") == "open" and row.get("severity") == "critical"]
    blockers: list[str] = []
    if policy.get("block_on_required_rejection") and rejected_required:
        blockers.append("required_reviewer_rejected")
    if policy.get("block_on_any_rejection") and rejected_any:
        blockers.append("reviewer_rejected")
    if policy.get("block_on_high_findings") and open_high:
        blockers.append("open_high_finding")
    if policy.get("block_on_critical_findings") and open_critical:
        blockers.append("open_critical_finding")
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_conflict_report", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "status": "failed" if blockers else "passed", "blockers": blockers, "summary": {"rejected_required_count": len(rejected_required), "rejected_count": len(rejected_any), "open_high_count": len(open_high), "open_critical_count": len(open_critical)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _quorum_report_document(center_id: str, board_id: str, source: ImplementationDocument, accepted_items: list[ImplementationDocument], responses: list[ImplementationDocument]) -> ImplementationDocument:
    policy = source.get("policy", {})
    passed = [row for row in accepted_items if row.get("status") == "passed" and row.get("result") == "accepted"]
    roles = {str(row.get("role") or "") for row in passed}
    organizations = {str(row.get("organization") or "") for row in passed if row.get("organization")}
    evidence_ids = [str(row.get("evidence_id") or "") for row in passed]
    duplicates = sorted({item for item in evidence_ids if item and evidence_ids.count(item) > 1})
    required_roles = set(policy.get("required_roles") or [])
    missing_roles = sorted(required_roles - roles)
    blockers: list[str] = []
    if len(passed) < int(policy.get("min_accepted_count") or 0):
        blockers.append("min_accepted_count")
    if len(organizations) < int(policy.get("min_organization_count") or 0):
        blockers.append("min_organization_count")
    if missing_roles:
        blockers.append("required_roles")
    if duplicates:
        blockers.append("duplicate_accepted_evidence")
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_quorum_report", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "status": "failed" if blockers else "passed", "blockers": blockers, "summary": {"accepted_count": len(passed), "organization_count": len(organizations), "roles": sorted(roles), "required_roles": sorted(required_roles), "missing_roles": missing_roles, "duplicate_evidence_ids": duplicates}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _decision_matrix_document(center_id: str, board_id: str, source: ImplementationDocument, roster: ImplementationDocument, response_index: ImplementationDocument, quorum: ImplementationDocument, conflicts: ImplementationDocument) -> ImplementationDocument:
    roles = sorted(set((source.get("policy", {}).get("required_roles") or []) + [row.get("role") for row in roster.get("reviewers", []) if row.get("role")]))
    rows = []
    responses = response_index.get("responses", [])
    for role in roles:
        role_responses = [row for row in responses if row.get("role") == role]
        accepted = len([row for row in role_responses if row.get("result") == "accepted"])
        rejected = len([row for row in role_responses if row.get("result") == "rejected"])
        needs_changes = len([row for row in role_responses if row.get("result") == "needs_changes"])
        status = "accepted" if accepted else "rejected" if rejected else "needs_changes" if needs_changes else "missing"
        rows.append({"role": role, "status": status, "accepted_count": accepted, "needs_changes_count": needs_changes, "rejected_count": rejected})
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_decision_matrix", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "rows": rows, "summary": {"quorum_status": quorum.get("status"), "conflict_status": conflicts.get("status"), "role_count": len(rows)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _decision_report_document(center_id: str, board_id: str, source: ImplementationDocument, quorum: ImplementationDocument, conflicts: ImplementationDocument, matrix: ImplementationDocument) -> ImplementationDocument:
    blockers = []
    if quorum.get("status") != "passed":
        blockers.extend([f"quorum:{item}" for item in quorum.get("blockers", [])])
    if conflicts.get("status") != "passed":
        blockers.extend([f"conflict:{item}" for item in conflicts.get("blockers", [])])
    status = "ready_for_signoff" if not blockers else "blocked"
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_decision_report", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "status": status, "blockers": blockers, "summary": {"quorum_status": quorum.get("status"), "conflict_status": conflicts.get("status"), "accepted_count": quorum.get("summary", {}).get("accepted_count"), "missing_roles": quorum.get("summary", {}).get("missing_roles", [])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _checklist_document(center_id: str, board_id: str, source: ImplementationDocument, decision: ImplementationDocument) -> ImplementationDocument:
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_manual_checklist", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "items": [{"item_id": "manual-001", "label": "Decision Board chair confirms reviewer quorum and open findings.", "required": True, "status": "passed" if decision.get("status") == "ready_for_signoff" else "blocked"}]}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(center_id: str, board_id: str, docs: ImplementationDocument, export_dir: Path) -> ImplementationDocument:
    files = []
    for rel in sorted(REQUIRED_ENTRIES - {"manifest.json"}):
        path = export_dir / rel
        files.append({"path": rel, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size if path.exists() else 0})
    manifest = {
        "schema_version": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE,
        "center_id": center_id,
        "board_id": board_id,
        "created_at": now_iso(),
        "source_hash": docs["source"].get("source_hash"),
        "files": files,
        "source": {
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
            "decision_signoff_hash": docs["decision_signoff"].get("integrity_hash"),
            "signoff_binding_hash": docs["signoff_binding"].get("integrity_hash"),
        },
        "summary": docs["decision_report"].get("summary", {}),
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _reviewer_guide(docs: ImplementationDocument) -> str:
    source = docs.get("source", {})
    decision = docs.get("decision_report", {})
    return sanitize_sensitive_text(
        "\n".join(
            [
                "# MusicForge Unified Command Center Reviewer Decision Board",
                "",
                f"Board: {source.get('board_id')}",
                f"Decision status: {decision.get('status')}",
                "Verify this archive with the Evidence Review Pack and every accepted evidence ZIP/report.",
            ]
        )
    )


def _signoff_binding_summary(center_id: str, board_id: str, signoff: ImplementationDocument, event: ImplementationDocument) -> ImplementationDocument:
    doc = {
        "package_type": "musicforge_unified_command_center_reviewer_decision_board_signoff_binding_summary",
        "center_id": center_id,
        "board_id": board_id,
        "status": signoff.get("status"),
        "signed_by": signoff.get("signed_by"),
        "role": signoff.get("role"),
        "signed_at": signoff.get("signed_at"),
        "signoff_hash": signoff.get("integrity_hash"),
        "signoff_payload_hash": signoff.get("payload_hash"),
        "history_event_hash": event.get("event_hash"),
        "decision_report_hash": signoff.get("decision_report_hash"),
        "quorum_report_hash": signoff.get("quorum_report_hash"),
        "accepted_evidence_index_hash": signoff.get("accepted_evidence_index_hash"),
    }
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _policy(value: ImplementationDocument) -> ImplementationDocument:
    policy = dict(DEFAULT_POLICY)
    for key in DEFAULT_POLICY:
        if key in value:
            policy[key] = value[key]
    policy["min_accepted_count"] = int(policy.get("min_accepted_count") or 0)
    policy["min_organization_count"] = int(policy.get("min_organization_count") or 0)
    policy["required_roles"] = [_bounded(role, 80) for role in (policy.get("required_roles") or [])]
    for key in ("block_on_required_rejection", "block_on_any_rejection", "block_on_high_findings", "block_on_critical_findings"):
        policy[key] = bool(policy.get(key))
    return policy


def _history_state(path: Path) -> ImplementationDocument:
    signed = False
    latest_signoff_hash = None
    if not path.exists():
        return {"signed": False, "latest_signoff_hash": None}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event_type") == "ucc_reviewer_decision_board_signoff_created":
            signed = True
            latest_signoff_hash = event.get("signoff_hash")
        elif event.get("event_type") == "ucc_reviewer_decision_board_signoff_reset":
            signed = False
            latest_signoff_hash = None
    return {"signed": signed, "latest_signoff_hash": latest_signoff_hash}


def _history_chain_ok(path: Path, signoff_hash: str | None) -> bool:
    if not path.exists():
        return False
    previous = None
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        expected_payload = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event.get("previous_event_hash") != previous or event.get("payload_hash") != expected_payload or event.get("event_hash") != expected_event:
            return False
        if event.get("event_type") == "ucc_reviewer_decision_board_signoff_created" and event.get("signoff_hash") == signoff_hash:
            found = True
        previous = event.get("event_hash")
    return found


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _read_optional_json(path: Path) -> ImplementationDocument:
    return read_json(path) if path.exists() else {}


def _read_zip_json(path: Path | None, rel: str) -> ImplementationDocument:
    if not path or not path.exists():
        return {}
    try:
        with zipfile.ZipFile(path) as archive:
            return json.loads(archive.read(rel).decode("utf-8"))
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return {}


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _sha256_path(path: Path | str | None) -> str | None:
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


def _zip_manifest_hash(path: Path | str | None) -> str | None:
    if not path:
        return None
    try:
        with zipfile.ZipFile(Path(path)) as archive:
            return json.loads(archive.read("manifest.json").decode("utf-8")).get("integrity_hash")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return None


def _path_or_none(value: Any) -> Path | None:
    if not value:
        return None
    return Path(value)


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _safe_id(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in {"-", "_"})[:80] or "item"
