from __future__ import annotations

import json
import shutil
import threading
import zipfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.platform.lifecycle import HistoryChain
from song_agent.platform.persistence import WorkspaceLock
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import ReleaseStore, stable_hash
from song_agent.unified_release_program_verifier import (
    UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE,
    UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
    verify_unified_release_program_package,
    write_unified_release_program_verification_report,
)
from song_agent.unified_command_center_release_train_handoff_verifier import (
    UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    verify_unified_command_center_release_train_handoff_package,
)


DEFAULT_POLICY = {
    "require_all_required_trains_ready": True,
    "require_no_dependency_cycle": True,
    "require_no_critical_risk": True,
    "require_external_handoff_acceptance": False,
    "allow_advisory_warnings": True,
    "allow_optional_defer": True,
    "required_program_roles": ["release_owner"],
}


class UnifiedReleaseProgramError(ValueError):
    pass


class UnifiedReleaseProgramNotFoundError(UnifiedReleaseProgramError):
    pass


class UnifiedReleaseProgramStateError(UnifiedReleaseProgramError):
    pass


class UnifiedReleaseProgramStore:
    def __init__(self, root: Path | str | None = None, *, release_store: ReleaseStore | None = None) -> None:
        self.release_store = release_store or ReleaseStore()
        self.root = Path(root) if root is not None else self.release_store.root.parent / "unified-release-programs"
        self.lock = WorkspaceLock(self.root.parent, operation="program-workflow-write")

    def program_dir(self, program_id: str) -> Path:
        return self.root / _safe_id(program_id)

    def program_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program.json"

    def source_inputs_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "source-inputs.json"

    def items_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "train-items.json"

    def external_manifest_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "external-evidence-manifest.json"

    def dependency_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "dependency-graph.json"

    def readiness_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "readiness-matrix.json"

    def risk_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "risk-register.json"

    def exception_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "exception-register.json"

    def gap_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "gap-plan.json"

    def report_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-report.json"

    def history_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-history.jsonl"

    def signoff_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-signoff.json"

    def signoff_binding_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "program-signoff-binding-summary.json"

    def export_dir(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "export"

    def manifest_path(self, program_id: str) -> Path:
        return self.export_dir(program_id) / "manifest.json"

    def zip_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "unified-release-program.zip"

    def verification_report_path(self, program_id: str) -> Path:
        return self.program_dir(program_id) / "unified-release-program-verification-report.json"

    def create_program(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            program_id = _safe_id(str(payload.get("program_id") or self._next_program_id()))
            if self.program_path(program_id).exists():
                raise UnifiedReleaseProgramStateError(f"Unified Release Program already exists: {program_id}")
            now = now_iso()
            program = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_record",
                    "program_id": program_id,
                    "name": _bounded(payload.get("name") or "Unified Release Program", 200),
                    "status": "draft",
                    "created_at": now,
                    "updated_at": now,
                    "policy": _policy(payload.get("policy")),
                    "summary": {},
                }
            )
            program["integrity_hash"] = _integrity_hash(program)
            self.program_dir(program_id).mkdir(parents=True, exist_ok=True)
            write_json(self.program_path(program_id), program)
            self._write_items(program_id, [])
            self._write_exception_register(program_id, [])
            if payload.get("items"):
                for item in payload.get("items") or []:
                    self.add_train_item(program_id, dict(item))
            return self.read_program(program_id)

    def list_programs(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        rows = []
        for path in sorted(self.root.glob("urp-*")):
            program_path = path / "program.json"
            if program_path.exists():
                rows.append(read_json(program_path))
        return rows

    def read_program(self, program_id: str) -> dict[str, Any]:
        if not self.program_path(program_id).exists():
            raise UnifiedReleaseProgramNotFoundError(f"Unified Release Program not found: {program_id}")
        return read_json(self.program_path(program_id))

    def get_program(self, program_id: str) -> dict[str, Any]:
        return {
            "program": self.read_program(program_id),
            "items": _read_optional_json(self.items_path(program_id)),
            "external_evidence_manifest": _read_optional_json(self.external_manifest_path(program_id)),
            "dependency_graph": _read_optional_json(self.dependency_path(program_id)),
            "readiness_matrix": _read_optional_json(self.readiness_path(program_id)),
            "risk_register": _read_optional_json(self.risk_path(program_id)),
            "exception_register": _read_optional_json(self.exception_path(program_id)),
            "gap_plan": _read_optional_json(self.gap_path(program_id)),
            "report": _read_optional_json(self.report_path(program_id)),
            "signoff": _read_optional_json(self.signoff_path(program_id)),
            "signoff_binding": _read_optional_json(self.signoff_binding_path(program_id)),
            "verification": _read_optional_json(self.verification_report_path(program_id)),
        }

    def add_train_item(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.ensure_unsigned(program_id)
            program = self.read_program(program_id)
            items_doc = self._read_items(program_id)
            rows = list(items_doc.get("items") or [])
            item_id = _safe_id(str(payload.get("item_id") or f"train-{len(rows) + 1:03d}"))
            train_id = _safe_id(str(payload.get("train_id") or ""))
            handoff_id = _safe_id(str(payload.get("handoff_id") or ""))
            if not train_id or not handoff_id:
                raise UnifiedReleaseProgramStateError("train_id and handoff_id are required.")
            if any(row.get("item_id") == item_id for row in rows):
                raise UnifiedReleaseProgramStateError(f"Duplicate Program item_id: {item_id}")
            if not bool(payload.get("allow_duplicate_train")) and any(row.get("train_id") == train_id and row.get("handoff_id") == handoff_id for row in rows):
                raise UnifiedReleaseProgramStateError("Duplicate train_id + handoff_id requires allow_duplicate_train=true.")
            item_type = str(payload.get("type") or payload.get("item_type") or "required")
            if item_type not in {"required", "optional", "advisory", "deferred"}:
                raise UnifiedReleaseProgramStateError("Program item type must be required, optional, advisory, or deferred.")
            external = payload.get("external_evidence") if isinstance(payload.get("external_evidence"), dict) else {}
            row = sanitize_metadata(
                {
                    "item_id": item_id,
                    "train_id": train_id,
                    "handoff_id": handoff_id,
                    "label": _bounded(payload.get("label") or train_id, 200),
                    "type": item_type,
                    "lane": _bounded(payload.get("lane") or "release", 80),
                    "wave": _bounded(payload.get("wave") or f"wave-{len(rows) + 1}", 80),
                    "depends_on": [_safe_id(str(item)) for item in payload.get("depends_on", []) if str(item)],
                    "expected_status": _bounded(payload.get("expected_status") or "signed", 80),
                    "defer_reason": _bounded(payload.get("defer_reason") or "", 500),
                    "external_evidence": {
                        "handoff_zip": str(payload.get("handoff_zip") or external.get("handoff_zip") or external.get("handoff_zip_path") or ""),
                        "handoff_verification_report": str(payload.get("handoff_verification_report") or external.get("handoff_verification_report") or external.get("handoff_verification_report_path") or ""),
                        "handoff_signoff_binding": str(payload.get("handoff_signoff_binding") or external.get("handoff_signoff_binding") or external.get("handoff_signoff_binding_path") or ""),
                        "accepted_evidence_dir": str(payload.get("accepted_evidence_dir") or external.get("accepted_evidence_dir") or ""),
                    },
                    "status": "pending",
                }
            )
            rows.append(row)
            self._write_items(program_id, rows)
            program["updated_at"] = now_iso()
            program["integrity_hash"] = _integrity_hash(program)
            write_json(self.program_path(program_id), program)
            return row

    def remove_train_item(self, program_id: str, item_id: str) -> dict[str, Any]:
        with self.lock:
            self.ensure_unsigned(program_id)
            rows = [row for row in self._read_items(program_id).get("items", []) if row.get("item_id") != item_id]
            self._write_items(program_id, rows)
            return self._read_items(program_id)

    def approve_exception(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.ensure_unsigned(program_id)
            register = self._read_exceptions(program_id)
            rows = list(register.get("exceptions") or [])
            exception = sanitize_metadata(
                {
                    "exception_id": _safe_id(str(payload.get("exception_id") or f"ex-{len(rows) + 1:06d}")),
                    "item_id": _safe_id(str(payload.get("item_id") or "")),
                    "type": _bounded(payload.get("type") or "waive_warning", 80),
                    "severity": _bounded(payload.get("severity") or "medium", 80),
                    "reason": _bounded(payload.get("reason") or "", 1000),
                    "approved_by": _bounded(payload.get("approved_by") or "program-owner", 120),
                    "created_at": now_iso(),
                    "status": "approved",
                }
            )
            exception["integrity_hash"] = _integrity_hash(exception)
            rows.append(exception)
            self._write_exception_register(program_id, rows)
            return exception

    def refresh_report(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            inputs = _merge_inputs(_read_optional_json(self.source_inputs_path(program_id)), _source_inputs(payload))
            docs = self._build_documents(program_id, inputs)
            self._write_docs(program_id, docs)
            write_json(self.source_inputs_path(program_id), inputs)
            program = docs["program"]
            program["status"] = "ready" if docs["report"].get("status") == "ready" else "blocked"
            program["summary"] = docs["report"].get("summary", {})
            program["source_hash"] = docs["report"].get("source_hash")
            program["updated_at"] = now_iso()
            program["integrity_hash"] = _integrity_hash(program)
            write_json(self.program_path(program_id), program)
            return docs["report"]

    def signoff(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        with self.lock:
            self.ensure_unsigned(program_id)
            docs = self._build_documents(program_id, _merge_inputs(_read_optional_json(self.source_inputs_path(program_id)), _source_inputs(payload)))
            if docs["report"].get("status") != "ready":
                self._write_docs(program_id, docs)
                raise UnifiedReleaseProgramStateError("Unified Release Program must be ready before signoff.")
            role = _bounded(payload.get("role") or "release_owner", 80)
            required_roles = set(docs["program"].get("policy", {}).get("required_program_roles") or ["release_owner"])
            if role not in required_roles:
                raise UnifiedReleaseProgramStateError("Program signer role is not allowed by policy.")
            self._write_docs(program_id, docs)
            now = now_iso()
            signoff = sanitize_metadata(
                {
                    "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                    "package_type": "musicforge_unified_release_program_signoff",
                    "program_id": program_id,
                    "status": "signed",
                    "signed_by": _bounded(payload.get("signed_by") or "program-owner", 120),
                    "role": role,
                    "reason": _bounded(payload.get("reason") or "Unified Release Program approved for final delivery.", 1000),
                    "signed_at": now,
                    "source_hash": docs["report"].get("source_hash"),
                    "program_report_hash": docs["report"].get("integrity_hash"),
                    "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                    "train_items_hash": docs["items"].get("integrity_hash"),
                    "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                    "risk_register_hash": docs["risk"].get("integrity_hash"),
                    "exception_register_hash": docs["exceptions"].get("integrity_hash"),
                    "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                    "tool": {"name": "MusicForge Unified Release Program Signoff", "version": __version__},
                }
            )
            signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
            signoff["integrity_hash"] = _integrity_hash(signoff)
            write_json(self.signoff_path(program_id), signoff)
            event = self._append_history(
                program_id,
                {
                    "event_type": "unified_release_program_signoff_created",
                    "created_at": now,
                    "program_id": program_id,
                    "signed_by": signoff.get("signed_by"),
                    "role": signoff.get("role"),
                    "reason": signoff.get("reason"),
                    "signoff_hash": signoff.get("integrity_hash"),
                    "signoff_payload_hash": signoff.get("payload_hash"),
                    "source_hash": signoff.get("source_hash"),
                    "program_report_hash": signoff.get("program_report_hash"),
                },
            )
            write_json(self.signoff_binding_path(program_id), self._signoff_binding_summary(program_id, signoff, event, docs))
            program = docs["program"]
            program["status"] = "signed"
            program["signed_at"] = now
            program["signoff_hash"] = signoff.get("integrity_hash")
            program["updated_at"] = now
            program["integrity_hash"] = _integrity_hash(program)
            write_json(self.program_path(program_id), program)
            return signoff

    def export_program(self, program_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._docs_for_export(program_id)
            export_dir = self.export_dir(program_id)
            if docs.get("signoff"):
                signoff_hash = str(docs["signoff"].get("integrity_hash") or "")
                if self._exported_for_signoff(program_id, signoff_hash):
                    if self.manifest_path(program_id).exists():
                        return read_json(self.manifest_path(program_id))
                    raise UnifiedReleaseProgramStateError("Program export was already created for this signoff. Create a new Program for changes.")
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            files: list[dict[str, Any]] = []

            def write_entry(rel: str, payload_doc: dict[str, Any] | str) -> None:
                path = export_dir / rel
                if isinstance(payload_doc, str):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(payload_doc, encoding="utf-8")
                else:
                    write_json(path, payload_doc)
                files.append(_file_record(path, rel))

            write_entry("program-report.json", docs["report"])
            write_entry("train-items.json", docs["items"])
            write_entry("external-evidence-manifest.json", docs["external_manifest"])
            write_entry("dependency-graph.json", docs["dependency"])
            write_entry("readiness-matrix.json", docs["readiness"])
            write_entry("risk-register.json", docs["risk"])
            write_entry("exception-register.json", docs["exceptions"])
            write_entry("gap-plan.json", docs["gap_plan"])
            write_entry("recipient-guide.md", _recipient_guide(docs))
            write_entry("program-history.jsonl", _history_text(self.read_history(program_id)))
            if docs.get("signoff"):
                write_entry("program-signoff.json", docs["signoff"])
                write_entry("program-signoff-binding-summary.json", docs["signoff_binding"])
            write_entry("README.txt", "MusicForge Unified Release Program Board\n")
            file_index = _file_index(program_id, files)
            write_entry("file-index.json", file_index)
            manifest = _manifest_document(program_id, docs, files, file_index)
            write_json(self.manifest_path(program_id), manifest)
            if docs.get("signoff"):
                self._append_history(program_id, {"event_type": "unified_release_program_exported", "created_at": now_iso(), "program_id": program_id, "signoff_hash": docs["signoff"].get("integrity_hash"), "program_manifest_hash": manifest.get("integrity_hash")})
            return manifest

    def build_zip(self, program_id: str) -> dict[str, Any]:
        with self.lock:
            docs = self._docs_for_export(program_id)
            if docs.get("signoff"):
                signoff_hash = str(docs["signoff"].get("integrity_hash") or "")
                if self._built_for_signoff(program_id, signoff_hash):
                    raise UnifiedReleaseProgramStateError("Program ZIP already exists for this signoff. Create a new Program for changes.")
            if not self.manifest_path(program_id).exists():
                self.export_program(program_id)
            else:
                self._assert_export_current(program_id)
            export_dir = self.export_dir(program_id)
            zip_path = self.zip_path(program_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(self.manifest_path(program_id))
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path != zip_path and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(self.manifest_path(program_id), manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file() and path != zip_path:
                        archive.write(path, path.relative_to(export_dir).as_posix())
            final_sha = _sha256_path(zip_path)
            if docs.get("signoff"):
                self._append_history(program_id, {"event_type": "unified_release_program_zip_built", "created_at": now_iso(), "program_id": program_id, "signoff_hash": docs["signoff"].get("integrity_hash"), "program_zip_sha256": final_sha, "program_manifest_hash": manifest.get("integrity_hash")})
            return {"status": "passed", "program_id": program_id, "zip_path": str(zip_path), "zip_sha256": final_sha, "manifest": manifest}

    def verify_package(self, program_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        report = verify_unified_release_program_package(
            self.zip_path(program_id),
            strict=bool(payload.get("strict", True)),
            require_current=bool(payload.get("require_current", True)),
            require_signed=bool(payload.get("require_signed", False)),
            external_evidence_manifest_path=payload.get("external_evidence_manifest") or payload.get("external_evidence_manifest_path") or self.external_manifest_path(program_id),
            program_signoff_binding_path=payload.get("program_signoff_binding") or payload.get("program_signoff_binding_path") or self.signoff_binding_path(program_id),
        )
        write_unified_release_program_verification_report(report, self.verification_report_path(program_id))
        return report

    def gate(
        self,
        *,
        required: bool = True,
        program_zip_path: Path | str | None = None,
        verification_report_path: Path | str | None = None,
        external_evidence_manifest_path: Path | str | None = None,
        program_signoff_binding_path: Path | str | None = None,
    ) -> dict[str, Any]:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(program_zip_path) if program_zip_path else None
        verification_path = Path(verification_report_path) if verification_report_path else None
        if not zip_path or not zip_path.exists():
            return _gate_failed("Unified Release Program ZIP is missing.")
        if not verification_path or not verification_path.exists():
            return _gate_failed("Unified Release Program verification report is missing.")
        try:
            external = read_json(verification_path)
            runtime = verify_unified_release_program_package(
                zip_path,
                strict=True,
                require_current=True,
                require_signed=True,
                external_evidence_manifest_path=external_evidence_manifest_path,
                program_signoff_binding_path=program_signoff_binding_path,
            )
            if not _integrity_ok(external):
                return _gate_failed("Unified Release Program verification integrity failed.")
            if external.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Release Program verification failed.", verification=runtime)
            if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Release Program verification does not match current ZIP.")
            return {"status": "passed", "hard_block": False, "message": "Unified Release Program gate passed.", "program_zip_sha256": runtime.get("zip_sha256"), "verification_hash": external.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def ensure_unsigned(self, program_id: str) -> None:
        state = self.latest_signoff_state(program_id)
        if state.get("status") == "signed":
            raise UnifiedReleaseProgramStateError("Unified Release Program is signed. Create a new Program for changes.")

    def latest_signoff_state(self, program_id: str) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
        for event in self.read_history(program_id):
            if event.get("event_type") == "unified_release_program_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event.get("event_type") == "unified_release_program_signoff_reset":
                previous_hash = event.get("previous_signoff_hash")
                if latest and (not previous_hash or latest.get("signoff_hash") == previous_hash):
                    latest = {"status": "reset", "previous_signoff_hash": previous_hash, "event": event}
        if latest:
            return latest
        if self.signoff_path(program_id).exists():
            signoff = read_json(self.signoff_path(program_id))
            if signoff.get("status") == "signed":
                return {"status": "signed", "signoff_hash": signoff.get("integrity_hash"), "event": {}}
        return {"status": "unsigned"}

    def read_history(self, program_id: str) -> list[dict[str, Any]]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).read()

    def _build_documents(self, program_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        program = self.read_program(program_id)
        items_doc = self._read_items(program_id)
        runtime_external_manifest = _external_manifest(program_id, items_doc, inputs)
        exceptions = self._read_exceptions(program_id)
        item_rows = _item_rows(program, items_doc, runtime_external_manifest)
        external_manifest = _public_external_manifest(program_id, item_rows)
        now = now_iso()
        source = sanitize_metadata(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_source",
                "program_id": program_id,
                "created_at": now,
                "program_hash": program.get("integrity_hash"),
                "train_items_hash": items_doc.get("integrity_hash"),
                "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
                "exception_register_hash": exceptions.get("integrity_hash"),
                "train_handoff_fingerprints": [row.get("fingerprint", {}) | {"item_id": row.get("item_id"), "train_id": row.get("train_id"), "handoff_id": row.get("handoff_id")} for row in item_rows],
            }
        )
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash"}})
        source["integrity_hash"] = _integrity_hash(source)
        dependency = _dependency_graph(program_id, source["source_hash"], item_rows, now)
        readiness = _readiness_matrix(program_id, source["source_hash"], item_rows, dependency, program, now)
        risk = _risk_register(program_id, source["source_hash"], readiness, dependency, item_rows, now)
        gap = _gap_plan(program_id, source["source_hash"], readiness, risk, now)
        report = _program_report(program_id, source["source_hash"], program, items_doc, external_manifest, dependency, readiness, risk, exceptions, gap, now)
        return {"program": program, "source": source, "items": _items_document(program_id, item_rows), "external_manifest": external_manifest, "dependency": dependency, "readiness": readiness, "risk": risk, "exceptions": exceptions, "gap_plan": gap, "report": report}

    def _write_docs(self, program_id: str, docs: dict[str, Any]) -> None:
        for key, path in (
            ("items", self.items_path(program_id)),
            ("external_manifest", self.external_manifest_path(program_id)),
            ("dependency", self.dependency_path(program_id)),
            ("readiness", self.readiness_path(program_id)),
            ("risk", self.risk_path(program_id)),
            ("exceptions", self.exception_path(program_id)),
            ("gap_plan", self.gap_path(program_id)),
            ("report", self.report_path(program_id)),
        ):
            write_json(path, docs[key])

    def _read_items(self, program_id: str) -> dict[str, Any]:
        if not self.items_path(program_id).exists():
            self._write_items(program_id, [])
        return read_json(self.items_path(program_id))

    def _write_items(self, program_id: str, rows: list[dict[str, Any]]) -> None:
        doc = _items_document(program_id, rows)
        write_json(self.items_path(program_id), doc)

    def _read_exceptions(self, program_id: str) -> dict[str, Any]:
        if not self.exception_path(program_id).exists():
            self._write_exception_register(program_id, [])
        return read_json(self.exception_path(program_id))

    def _write_exception_register(self, program_id: str, rows: list[dict[str, Any]]) -> None:
        doc = sanitize_metadata(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_exception_register",
                "program_id": program_id,
                "exceptions": rows,
                "summary": {"approved": sum(1 for row in rows if row.get("status") == "approved"), "blocking_unapproved": sum(1 for row in rows if row.get("status") not in {"approved", "rejected"})},
            }
        )
        doc["integrity_hash"] = _integrity_hash(doc)
        write_json(self.exception_path(program_id), doc)

    def _docs_for_export(self, program_id: str) -> dict[str, Any]:
        if self.report_path(program_id).exists():
            docs = {
                "program": self.read_program(program_id),
                "items": read_json(self.items_path(program_id)),
                "external_manifest": read_json(self.external_manifest_path(program_id)),
                "dependency": read_json(self.dependency_path(program_id)),
                "readiness": read_json(self.readiness_path(program_id)),
                "risk": read_json(self.risk_path(program_id)),
                "exceptions": read_json(self.exception_path(program_id)),
                "gap_plan": read_json(self.gap_path(program_id)),
                "report": read_json(self.report_path(program_id)),
            }
        else:
            docs = self._build_documents(program_id, _read_optional_json(self.source_inputs_path(program_id)))
            self._write_docs(program_id, docs)
        state = self.latest_signoff_state(program_id)
        if state.get("status") == "signed":
            if not self.signoff_path(program_id).exists():
                raise UnifiedReleaseProgramStateError("Program signoff file is missing but history shows a signed state.")
            signoff = read_json(self.signoff_path(program_id))
            if not _integrity_ok(signoff) or signoff.get("status") != "signed":
                raise UnifiedReleaseProgramStateError("Program signoff integrity failed.")
            if state.get("signoff_hash") and state.get("signoff_hash") != signoff.get("integrity_hash"):
                raise UnifiedReleaseProgramStateError("Program signoff file does not match latest signed history state.")
            binding = self._read_signoff_binding(program_id, signoff)
            checks = {
                "program_report_hash": docs["report"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                "train_items_hash": docs["items"].get("integrity_hash"),
                "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                "risk_register_hash": docs["risk"].get("integrity_hash"),
                "exception_register_hash": docs["exceptions"].get("integrity_hash"),
                "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
            }
            for key, value in checks.items():
                if signoff.get(key) != value:
                    raise UnifiedReleaseProgramStateError("Program signed documents no longer match signoff.")
            docs["signoff"] = signoff
            docs["signoff_binding"] = binding
        return docs

    def _read_signoff_binding(self, program_id: str, signoff: dict[str, Any]) -> dict[str, Any]:
        path = self.signoff_binding_path(program_id)
        if not path.exists():
            raise UnifiedReleaseProgramStateError("Program signoff binding summary is missing.")
        binding = read_json(path)
        if not _integrity_ok(binding):
            raise UnifiedReleaseProgramStateError("Program signoff binding integrity failed.")
        if binding.get("signoff_hash") != signoff.get("integrity_hash"):
            raise UnifiedReleaseProgramStateError("Program signoff binding does not match current signoff.")
        return binding

    def _assert_export_current(self, program_id: str) -> None:
        manifest = read_json(self.manifest_path(program_id))
        docs = self._docs_for_export(program_id)
        expected_source = _manifest_source(docs)
        if manifest.get("source") != expected_source:
            raise UnifiedReleaseProgramStateError("Program export is stale. Rebuild export before ZIP.")

    def _append_history(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return HistoryChain(self.history_path(program_id), sanitizer=sanitize_metadata).append(payload)

    def _signoff_binding_summary(self, program_id: str, signoff: dict[str, Any], event: dict[str, Any], docs: dict[str, Any]) -> dict[str, Any]:
        binding = sanitize_metadata(
            {
                "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
                "package_type": "musicforge_unified_release_program_signoff_binding_summary",
                "program_id": program_id,
                "created_at": now_iso(),
                "signed_by": signoff.get("signed_by"),
                "role": signoff.get("role"),
                "reason": signoff.get("reason"),
                "signed_at": signoff.get("signed_at"),
                "signoff_hash": signoff.get("integrity_hash"),
                "signoff_payload_hash": signoff.get("payload_hash"),
                "latest_history_event_hash": event.get("event_hash"),
                "history_event_payload_hash": event.get("payload_hash"),
                "program_report_hash": docs["report"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                "train_items_hash": docs["items"].get("integrity_hash"),
                "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                "risk_register_hash": docs["risk"].get("integrity_hash"),
                "exception_register_hash": docs["exceptions"].get("integrity_hash"),
                "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
                "train_handoff_fingerprints": [
                    {
                        "item_id": row.get("item_id"),
                        "train_id": row.get("train_id"),
                        "handoff_id": row.get("handoff_id"),
                        **(row.get("fingerprint") if isinstance(row.get("fingerprint"), dict) else {}),
                    }
                    for row in docs["items"].get("items", [])
                ],
            }
        )
        binding["integrity_hash"] = _integrity_hash(binding)
        return binding

    def _exported_for_signoff(self, program_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "unified_release_program_exported" and event.get("signoff_hash") == signoff_hash for event in self.read_history(program_id))

    def _built_for_signoff(self, program_id: str, signoff_hash: str) -> bool:
        return any(event.get("event_type") == "unified_release_program_zip_built" and event.get("signoff_hash") == signoff_hash for event in self.read_history(program_id))

    def _next_program_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        max_seen = 0
        for path in self.root.glob("urp-*/program.json"):
            try:
                max_seen = max(max_seen, int(path.parent.name.split("-")[-1]))
            except ValueError:
                continue
        return f"urp-{max_seen + 1:06d}"


def write_external_evidence_manifest(path: Path | str, *, program_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = _external_manifest_from_rows(program_id, items)
    write_json(Path(path), manifest)
    return manifest


def _external_manifest(program_id: str, items_doc: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    path = inputs.get("external_evidence_manifest") or inputs.get("external_evidence_manifest_path")
    if path:
        return read_json(Path(path))
    rows = inputs.get("external_evidence") or inputs.get("external_evidence_items")
    if rows is None:
        rows = []
        for item in items_doc.get("items", []):
            external = item.get("external_evidence") if isinstance(item.get("external_evidence"), dict) else {}
            rows.append(
                {
                    "item_id": item.get("item_id"),
                    "train_id": item.get("train_id"),
                    "handoff_id": item.get("handoff_id"),
                    "evidence_type": "release_train_handoff",
                    **external,
                }
            )
    return _external_manifest_from_rows(program_id, rows)


def _external_manifest_from_rows(program_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    for row in rows:
        normalized_row = {
            "item_id": _safe_id(str(row.get("item_id") or "")),
            "train_id": _safe_id(str(row.get("train_id") or "")),
            "handoff_id": _safe_id(str(row.get("handoff_id") or "")),
            "evidence_type": "release_train_handoff",
            "handoff_zip": str(row.get("handoff_zip") or row.get("handoff_zip_path") or ""),
            "handoff_verification_report": str(row.get("handoff_verification_report") or row.get("handoff_verification_report_path") or ""),
            "handoff_signoff_binding": str(row.get("handoff_signoff_binding") or row.get("handoff_signoff_binding_path") or ""),
            "accepted_evidence_dir": str(row.get("accepted_evidence_dir") or ""),
            "handoff_zip_sha256": row.get("handoff_zip_sha256"),
            "handoff_manifest_hash": row.get("handoff_manifest_hash"),
            "handoff_verification_report_hash": row.get("handoff_verification_report_hash"),
            "handoff_signoff_binding_hash": row.get("handoff_signoff_binding_hash"),
        }
        normalized_row.update(_fingerprint_from_external_row(normalized_row))
        normalized.append(normalized_row)
    manifest = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": program_id,
        "created_at": now_iso(),
        "items": normalized,
        "summary": {"item_count": len(normalized)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _public_external_manifest(program_id: str, item_rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    for row in item_rows:
        fingerprint = row.get("fingerprint") if isinstance(row.get("fingerprint"), dict) else {}
        normalized.append(
            {
                "item_id": row.get("item_id"),
                "train_id": row.get("train_id"),
                "handoff_id": row.get("handoff_id"),
                "evidence_type": "release_train_handoff",
                "handoff_zip_sha256": fingerprint.get("handoff_zip_sha256"),
                "handoff_zip_size_bytes": fingerprint.get("handoff_zip_size_bytes"),
                "handoff_manifest_hash": fingerprint.get("handoff_manifest_hash"),
                "handoff_verification_report_hash": fingerprint.get("handoff_verification_report_hash"),
                "handoff_signoff_binding_hash": fingerprint.get("handoff_signoff_binding_hash"),
                "handoff_status": fingerprint.get("handoff_status"),
            }
        )
    manifest = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": program_id,
        "created_at": now_iso(),
        "items": normalized,
        "summary": {"item_count": len(normalized)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _fingerprint_from_external_row(row: dict[str, Any]) -> dict[str, Any]:
    fingerprint: dict[str, Any] = {}
    zip_path = Path(str(row.get("handoff_zip") or ""))
    report_path = Path(str(row.get("handoff_verification_report") or ""))
    binding_path = Path(str(row.get("handoff_signoff_binding") or ""))
    if zip_path.exists() and zip_path.is_file() and not row.get("handoff_zip_sha256"):
        fingerprint["handoff_zip_sha256"] = _sha256_path(zip_path)
        fingerprint["handoff_zip_size_bytes"] = zip_path.stat().st_size
    if report_path.exists() and report_path.is_file():
        try:
            report = read_json(report_path)
            if not row.get("handoff_manifest_hash"):
                fingerprint["handoff_manifest_hash"] = _verification_manifest_hash(report)
            if not row.get("handoff_verification_report_hash"):
                fingerprint["handoff_verification_report_hash"] = _integrity_hash(report)
        except Exception:
            pass
    if binding_path.exists() and binding_path.is_file() and not row.get("handoff_signoff_binding_hash"):
        fingerprint["handoff_signoff_binding_hash"] = _sha256_or_integrity(binding_path)
    return {key: value for key, value in fingerprint.items() if value not in (None, "")}


def _item_rows(program: dict[str, Any], items_doc: dict[str, Any], external_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    external_by_key = {_item_key(row): row for row in external_manifest.get("items", []) if isinstance(row, dict)}
    require_accepted = bool(program.get("policy", {}).get("require_external_handoff_acceptance"))
    rows = []
    for item in items_doc.get("items", []):
        external = external_by_key.get(_item_key(item), {})
        runtime = _runtime_handoff(item, external, require_accepted=require_accepted)
        row = sanitize_metadata({**item, "require_accepted": require_accepted, "runtime": runtime, "fingerprint": runtime.get("fingerprint", {}), "status": "ready" if runtime.get("status") == "passed" else "blocked", "blockers": runtime.get("blockers", [])})
        rows.append(row)
    return rows


def _runtime_handoff(item: dict[str, Any], external: dict[str, Any], *, require_accepted: bool) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "missing", "blockers": [], "fingerprint": {}}
    zip_path = Path(str(external.get("handoff_zip") or external.get("handoff_zip_path") or ""))
    report_path = Path(str(external.get("handoff_verification_report") or external.get("handoff_verification_report_path") or ""))
    binding_path = Path(str(external.get("handoff_signoff_binding") or external.get("handoff_signoff_binding_path") or ""))
    accepted_raw = external.get("accepted_evidence_dir")
    accepted_dir = Path(str(accepted_raw)) if accepted_raw else None
    if not zip_path.exists() or not report_path.exists() or not binding_path.exists():
        result["blockers"].append("handoff_external_evidence_missing")
        return result
    try:
        external_report = read_json(report_path)
        runtime = verify_unified_command_center_release_train_handoff_package(
            zip_path,
            strict=True,
            require_signed=True,
            require_accepted=require_accepted,
            handoff_signoff_binding_path=binding_path,
            accepted_evidence_dir=accepted_dir,
        )
        runtime_zip_sha256 = _verification_zip_sha256(runtime)
        runtime_manifest_hash = _verification_manifest_hash(runtime)
        external_zip_sha256 = _verification_zip_sha256(external_report)
        external_manifest_hash = _verification_manifest_hash(external_report)
        fingerprint = {
            "handoff_zip_sha256": _sha256_path(zip_path),
            "handoff_zip_size_bytes": zip_path.stat().st_size,
            "handoff_manifest_hash": runtime_manifest_hash,
            "handoff_verification_report_hash": _integrity_hash(external_report),
            "handoff_signoff_binding_hash": _sha256_or_integrity(binding_path),
            "handoff_status": runtime.get("status"),
        }
        result["fingerprint"] = fingerprint
        if external_report.get("package_type") != UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE:
            result["blockers"].append("handoff_verification_wrong_package_type")
        if not _integrity_ok(external_report):
            result["blockers"].append("handoff_verification_integrity_failed")
        if external_report.get("status") != "passed" or runtime.get("status") != "passed":
            result["blockers"].append("handoff_verification_not_passed")
        if external_zip_sha256 != runtime_zip_sha256 or runtime_zip_sha256 != fingerprint["handoff_zip_sha256"]:
            result["blockers"].append("handoff_zip_sha256_mismatch")
        if external_manifest_hash != runtime_manifest_hash:
            result["blockers"].append("handoff_manifest_hash_mismatch")
        result["runtime_blockers"] = runtime.get("blockers", [])
    except Exception as exc:
        result["blockers"].append(sanitize_sensitive_text(str(exc)))
    result["status"] = "passed" if not result["blockers"] else "failed"
    return sanitize_metadata(result)


def _items_document(program_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_train_items",
            "program_id": program_id,
            "items": rows,
            "summary": {
                "item_count": len(rows),
                "ready_count": sum(1 for row in rows if row.get("status") == "ready"),
                "blocked_count": sum(1 for row in rows if row.get("status") == "blocked"),
                "required_count": sum(1 for row in rows if row.get("type") == "required"),
                "deferred_count": sum(1 for row in rows if row.get("type") == "deferred"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _dependency_graph(program_id: str, source_hash: str, items: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    nodes = [{"item_id": row.get("item_id"), "type": row.get("type"), "lane": row.get("lane"), "wave": row.get("wave"), "status": row.get("status")} for row in items]
    edges = []
    item_ids = {str(row.get("item_id")) for row in items}
    for row in items:
        for dep in row.get("depends_on", []) or []:
            if dep:
                edges.append({"from": dep, "to": row.get("item_id"), "reason": "Program dependency"})
    cycle = _has_cycle([str(row.get("from") or "") for row in edges], [str(row.get("to") or "") for row in edges])
    blocked = [edge for edge in edges if edge.get("from") not in item_ids or next((row for row in items if row.get("item_id") == edge.get("from")), {}).get("status") != "ready"]
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_dependency_graph",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "nodes": nodes,
            "edges": edges,
            "summary": {"has_cycle": cycle, "blocked_dependency_count": len(blocked), "ordered_items": _topological_order(nodes, edges) if not cycle else []},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readiness_matrix(program_id: str, source_hash: str, items: list[dict[str, Any]], dependency: dict[str, Any], program: dict[str, Any], created_at: str) -> dict[str, Any]:
    rows = []
    critical_failed = 0
    warning_count = 0
    required_ready_count = sum(1 for item in items if item.get("type") == "required" and item.get("status") == "ready")
    for item in items:
        severity = "critical" if item.get("type") == "required" else "warning"
        status = "passed" if item.get("status") == "ready" else "failed" if severity == "critical" else "warning"
        if status == "failed":
            critical_failed += 1
        if status == "warning":
            warning_count += 1
        rows.append({"check_id": f"{item.get('item_id')}.current_handoff_verified", "item_id": item.get("item_id"), "train_id": item.get("train_id"), "handoff_id": item.get("handoff_id"), "status": status, "severity": severity, "item_type": item.get("type"), "blockers": item.get("blockers", [])})
    if dependency.get("summary", {}).get("has_cycle"):
        critical_failed += 1
        rows.append({"check_id": "dependency_graph_acyclic", "status": "failed", "severity": "critical"})
    else:
        rows.append({"check_id": "dependency_graph_acyclic", "status": "passed", "severity": "critical"})
    blocked_deps = int(dependency.get("summary", {}).get("blocked_dependency_count") or 0)
    if blocked_deps:
        critical_failed += blocked_deps
        rows.append({"check_id": "dependency_graph_blocked", "status": "failed", "severity": "critical", "blocked_dependency_count": blocked_deps})
    if required_ready_count == 0:
        critical_failed += 1
        rows.append(
            {
                "check_id": "program_has_verified_required_handoff",
                "status": "failed",
                "severity": "critical",
                "required_ready_count": required_ready_count,
                "message": "Program signoff requires at least one required train with a current verified Handoff.",
            }
        )
    else:
        rows.append({"check_id": "program_has_verified_required_handoff", "status": "passed", "severity": "critical", "required_ready_count": required_ready_count})
    status = "ready" if critical_failed == 0 else "blocked"
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_readiness_matrix",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "rows": rows,
            "summary": {"status": status, "critical_failed": critical_failed, "warning_count": warning_count, "manual_required": 0, "required_ready_count": required_ready_count},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _risk_register(program_id: str, source_hash: str, readiness: dict[str, Any], dependency: dict[str, Any], items: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    risks = []
    for row in readiness.get("rows", []):
        if row.get("status") == "passed":
            continue
        risks.append({"risk_id": f"risk-{len(risks) + 1:03d}", "severity": "critical" if row.get("severity") == "critical" else "medium", "category": "verification", "item_id": row.get("item_id"), "message": f"{row.get('check_id')} is {row.get('status')}", "recommended_action": "refresh train handoff verification"})
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_risk_register",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "risks": risks,
            "summary": {
                "critical": sum(1 for row in risks if row.get("severity") == "critical"),
                "high": sum(1 for row in risks if row.get("severity") == "high"),
                "medium": sum(1 for row in risks if row.get("severity") == "medium"),
                "low": sum(1 for row in risks if row.get("severity") == "low"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _gap_plan(program_id: str, source_hash: str, readiness: dict[str, Any], risk: dict[str, Any], created_at: str) -> dict[str, Any]:
    actions = [{"action_id": f"gap-{index + 1:03d}", "source_check_id": row.get("check_id"), "status": "manual_required", "recommended_action": "Resolve Program blocker and refresh Program."} for index, row in enumerate(readiness.get("rows", [])) if row.get("status") in {"failed", "warning"}]
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_gap_plan",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "actions": actions,
            "summary": {"action_count": len(actions), "manual_required": len(actions)},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _program_report(program_id: str, source_hash: str, program: dict[str, Any], items: dict[str, Any], external_manifest: dict[str, Any], dependency: dict[str, Any], readiness: dict[str, Any], risk: dict[str, Any], exceptions: dict[str, Any], gap: dict[str, Any], created_at: str) -> dict[str, Any]:
    status = "ready" if readiness.get("summary", {}).get("status") == "ready" else "blocked"
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_report",
            "program_id": program_id,
            "created_at": created_at,
            "status": status,
            "source_hash": source_hash,
            "summary": {
                "train_count": items.get("summary", {}).get("item_count", 0),
                "ready_count": items.get("summary", {}).get("ready_count", 0),
                "blocked_count": items.get("summary", {}).get("blocked_count", 0),
                "deferred_count": items.get("summary", {}).get("deferred_count", 0),
                "dependency_cycle": bool(dependency.get("summary", {}).get("has_cycle")),
                "readiness": readiness.get("summary", {}).get("status"),
                "risk_count": len(risk.get("risks", [])),
            },
            "source": {
                "train_items_hash": items.get("integrity_hash"),
                "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
                "dependency_graph_hash": dependency.get("integrity_hash"),
                "readiness_matrix_hash": readiness.get("integrity_hash"),
                "risk_register_hash": risk.get("integrity_hash"),
                "exception_register_hash": exceptions.get("integrity_hash"),
                "gap_plan_hash": gap.get("integrity_hash"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(program_id: str, docs: dict[str, Any], files: list[dict[str, Any]], file_index: dict[str, Any]) -> dict[str, Any]:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source_hash": docs["report"].get("source_hash"),
            "source": _manifest_source(docs),
            "files": [row for row in files if row.get("path") != "manifest.json"],
            "file_index_hash": file_index.get("integrity_hash"),
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _manifest_source(docs: dict[str, Any]) -> dict[str, Any]:
    source = {
        "program_report_hash": docs["report"].get("integrity_hash"),
        "train_items_hash": docs["items"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "risk_register_hash": docs["risk"].get("integrity_hash"),
        "exception_register_hash": docs["exceptions"].get("integrity_hash"),
        "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
    }
    if docs.get("signoff"):
        source["program_signoff_hash"] = docs["signoff"].get("integrity_hash")
    if docs.get("signoff_binding"):
        source["program_signoff_binding_hash"] = docs["signoff_binding"].get("integrity_hash")
    return source


def _file_index(program_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    doc = {"schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_file_index", "program_id": program_id, "files": [row for row in files if row.get("path") != "file-index.json"], "summary": {"file_count": len(files)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _file_record(path: Path, rel: str) -> dict[str, Any]:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _recipient_guide(docs: dict[str, Any]) -> str:
    return f"# Unified Release Program\n\nProgram: {docs['report'].get('program_id')}\nStatus: {docs['report'].get('status')}\n"


def _read_optional_json(path: Path) -> dict[str, Any]:
    if path.exists():
        return read_json(path)
    return {}


def _source_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _json_safe_input(value)
        for key, value in payload.items()
        if key in {"external_evidence_manifest", "external_evidence_manifest_path", "external_evidence", "external_evidence_items"}
    }


def _merge_inputs(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    merged.update({key: value for key, value in incoming.items() if value not in (None, "", [])})
    return merged


def _json_safe_input(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe_input(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_input(item) for item in value]
    return value


def _policy(payload: Any) -> dict[str, Any]:
    data = dict(DEFAULT_POLICY)
    if isinstance(payload, dict):
        for key in data:
            if key in payload:
                data[key] = payload[key]
    data["required_program_roles"] = [str(role) for role in data.get("required_program_roles") or ["release_owner"]]
    return data


def _safe_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return safe.strip("-")[:120]


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _integrity_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: dict[str, Any]) -> bool:
    return bool(doc.get("integrity_hash")) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_or_integrity(path: Path) -> str:
    try:
        doc = read_json(path)
        if isinstance(doc, dict) and doc.get("integrity_hash"):
            return str(doc.get("integrity_hash"))
    except Exception:
        pass
    return _sha256_path(path)


def _verification_zip_sha256(report: dict[str, Any]) -> str | None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return report.get("zip_sha256") or summary.get("zip_sha256")


def _verification_manifest_hash(report: dict[str, Any]) -> str | None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return report.get("manifest_hash") or summary.get("manifest_hash")


def _item_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(key) or "") for key in ("item_id", "train_id", "handoff_id"))


def _history_text(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)


def _gate_failed(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _has_cycle(from_nodes: list[str], to_nodes: list[str]) -> bool:
    graph: dict[str, list[str]] = {}
    for source, target in zip(from_nodes, to_nodes):
        if source and target:
            graph.setdefault(source, []).append(target)
            graph.setdefault(target, [])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(graph))


def _topological_order(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    remaining = {str(row.get("item_id")) for row in nodes}
    incoming = {node: 0 for node in remaining}
    outgoing: dict[str, list[str]] = {node: [] for node in remaining}
    for edge in edges:
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source in remaining and target in remaining:
            incoming[target] += 1
            outgoing[source].append(target)
    order = []
    ready = sorted(node for node, count in incoming.items() if count == 0)
    while ready:
        node = ready.pop(0)
        order.append(node)
        remaining.discard(node)
        for nxt in outgoing.get(node, []):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    return order
