# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, document_or as _document_or

import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_verifier import COMPONENT_KEYS as COMPONENT_KEYS, RUNTIME_COMPONENT_KEYS as RUNTIME_COMPONENT_KEYS, UNIFIED_COMMAND_CENTER_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, verify_unified_command_center_component as verify_unified_command_center_component, verify_unified_command_center_package as verify_unified_command_center_package, write_unified_command_center_verification_report as write_unified_command_center_verification_report


UNIFIED_COMMAND_CENTER_REPORT_PACKAGE_TYPE = "musicforge_unified_command_center_report"

COMPONENT_DEFS: tuple[dict[str, str], ...] = (
    {"key": "release", "domain": "release", "label": "Release Delivery", "component_type": "release"},
    {"key": "audio-command-center", "domain": "audio", "label": "Release Audio Command Center", "component_type": "release_audio_command_center"},
    {"key": "trust-operations-hub", "domain": "trust_operations", "label": "Trust Operations Hub", "component_type": "trust_operations_hub"},
    {"key": "public-trust-center", "domain": "public_trust", "label": "Public Trust Center", "component_type": "public_trust_center"},
    {"key": "distribution", "domain": "distribution", "label": "Distribution Readiness", "component_type": "distribution"},
    {"key": "submission", "domain": "submission", "label": "Submission Readiness", "component_type": "submission"},
    {"key": "operations", "domain": "operations", "label": "Release Operations", "component_type": "release_operations"},
    {"key": "maintenance", "domain": "maintenance", "label": "LTS Maintenance", "component_type": "maintenance_backup"},
    {"key": "ga-readiness", "domain": "ga", "label": "GA Readiness", "component_type": "ga_readiness"},
    {"key": "release-check", "domain": "release_check", "label": "Release Check", "component_type": "release_check"},
)

DEFAULT_REQUIREMENTS = {
    "release": False,
    "audio-command-center": True,
    "trust-operations-hub": True,
    "public-trust-center": True,
    "distribution": False,
    "submission": False,
    "operations": False,
    "maintenance": False,
    "ga-readiness": True,
    "release-check": True,
}


class UnifiedCommandCenterError(ValueError):
    pass


class UnifiedCommandCenterNotFoundError(UnifiedCommandCenterError):
    pass


class UnifiedCommandCenterStateError(UnifiedCommandCenterError):
    pass


class UnifiedCommandCenterStore:
    def __init__(self, root: Path | str | None = None, *, release_store: ReleaseStore | None = None) -> None:
        self.release_store = release_store or ReleaseStore()
        self.root = Path(root) if root is not None else self.release_store.root.parent / "unified-command-centers"
        self.lock = threading.RLock()

    def center_dir(self, center_id: str) -> Path:
        return self.root / center_id

    def export_dir(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "export"

    def zip_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "musicforge-unified-command-center.zip"

    def verification_report_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "verification-report.json"

    def center_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "center.json"

    def source_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "source.json"

    def report_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "command-center-report.json"

    def graph_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "evidence-graph.json"

    def inventory_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "evidence-inventory.json"

    def readiness_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "readiness-matrix.json"

    def gap_plan_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "gap-plan.json"

    def runbook_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "safe-runbook.json"

    def runbook_result_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "runbook-result.json"

    def verification_index_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "verification-index.json"

    def create(self, payload: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            payload = payload or {}
            center_id = str(payload.get("center_id") or self._next_center_id())
            if self.center_path(center_id).exists():
                raise UnifiedCommandCenterStateError(f"Unified Command Center already exists: {center_id}")
            now = now_iso()
            center = {
                "schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION,
                "package_type": "musicforge_unified_command_center_record",
                "center_id": center_id,
                "name": sanitize_sensitive_text(str(payload.get("name") or "MusicForge Unified Command Center")),
                "scope": str(payload.get("scope") or "workspace"),
                "profile": str(payload.get("profile") or "ga"),
                "primary_release_id": str(payload.get("primary_release_id") or ""),
                "release_ids": [str(item) for item in payload.get("release_ids", []) if str(item)],
                "requirements": _requirements(_document_or(payload.get("requirements"), payload)),
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "latest_report_id": None,
                "source_hash": None,
            }
            center["integrity_hash"] = _integrity_hash(center)
            self.center_dir(center_id).mkdir(parents=True, exist_ok=True)
            write_json(self.center_path(center_id), center)
            return center

    def list_centers(self) -> list[DomainDocument]:
        if not self.root.exists():
            return []
        centers: list[ImplementationDocument] = []
        for path in sorted(self.root.glob("ucc-*")):
            center_path = path / "center.json"
            if center_path.exists():
                centers.append(read_json(center_path))
        return centers

    def read_center(self, center_id: str) -> DomainDocument:
        if not self.center_path(center_id).exists():
            raise UnifiedCommandCenterNotFoundError(f"Unified Command Center not found: {center_id}")
        return read_json(self.center_path(center_id))

    def read_report(self, center_id: str) -> DomainDocument:
        if not self.report_path(center_id).exists():
            raise UnifiedCommandCenterNotFoundError(f"Unified Command Center report not found: {center_id}")
        return read_json(self.report_path(center_id))

    def refresh(self, center_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            self.ensure_mutable(center_id)
            docs = self._build_documents(center_id, evidence or {})
            self._write_docs(center_id, docs)
            return docs["report"]

    def create_runbook(self, center_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            self.ensure_mutable(center_id)
            docs = self._ensure_docs(center_id, evidence or {})
            return docs["runbook"]

    def run_safe(self, center_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            self.ensure_mutable(center_id)
            docs = self._ensure_docs(center_id, evidence or {})
            current_source_hash = self._build_documents(center_id, evidence or {})["source"]["source_hash"]
            if current_source_hash != docs["source"].get("source_hash"):
                raise UnifiedCommandCenterStateError("Unified Command Center source is stale. Refresh before running safe actions.")
            results: list[ImplementationDocument] = []
            for item in docs["runbook"].get("items", []):
                if not isinstance(item, dict):
                    continue
                action = str(item.get("action") or "")
                item_id = str(item.get("item_id") or "")
                if not item.get("safe"):
                    results.append({"item_id": item_id, "action": action, "status": "manual_required", "reason": "Action requires human decision."})
                    continue
                try:
                    if action == "unified_command_center.refresh":
                        docs = self._build_documents(center_id, evidence or {})
                        self._write_docs(center_id, docs)
                        results.append({"item_id": item_id, "action": action, "status": "completed"})
                    elif action == "unified_command_center.export":
                        exported = self.export_package(center_id, evidence or {})
                        results.append({"item_id": item_id, "action": action, "status": "completed", "export_status": exported.get("status")})
                    elif action == "unified_command_center.zip":
                        zipped = self.build_zip(center_id, evidence or {})
                        results.append({"item_id": item_id, "action": action, "status": "completed", "zip_sha256": zipped.get("zip_sha256")})
                    elif action == "unified_command_center.verify":
                        verified = self.verify_zip(center_id, evidence=evidence or {}, strict=True)
                        results.append({"item_id": item_id, "action": action, "status": "completed" if verified.get("status") != "failed" else "failed", "verification_status": verified.get("status")})
                    else:
                        results.append({"item_id": item_id, "action": action, "status": "skipped_unsupported", "reason": "This safe action must be executed by its owning module."})
                except Exception as exc:
                    results.append({"item_id": item_id, "action": action, "status": "failed", "reason": sanitize_sensitive_text(str(exc))})
            result_doc = _runbook_result(center_id, docs["source"].get("source_hash"), results)
            write_json(self.runbook_result_path(center_id), result_doc)
            return result_doc

    def export_package(self, center_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            self.ensure_mutable(center_id)
            docs = self._ensure_docs(center_id, evidence or {})
            current_source_hash = self._build_documents(center_id, evidence or {})["source"]["source_hash"]
            if current_source_hash != docs["source"].get("source_hash"):
                raise UnifiedCommandCenterStateError("Unified Command Center source is stale. Refresh before export.")
            self._write_docs(center_id, docs)
            _sync_report_hashes(docs)
            export_dir = self.export_dir(center_id)
            if export_dir.exists():
                shutil.rmtree(export_dir)
            export_dir.mkdir(parents=True, exist_ok=True)
            for rel, key in (
                ("source.json", "source"),
                ("command-center-report.json", "report"),
                ("evidence-graph.json", "graph"),
                ("evidence-inventory.json", "inventory"),
                ("readiness-matrix.json", "readiness"),
                ("gap-plan.json", "gap_plan"),
                ("safe-runbook.json", "runbook"),
                ("runbook-result.json", "runbook_result"),
                ("verification-index.json", "verification_index"),
            ):
                write_json(export_dir / rel, docs[key])
            (export_dir / "README.txt").write_text(_readme(docs["report"]), encoding="utf-8")
            (export_dir / "component-fingerprints").mkdir(parents=True, exist_ok=True)
            for key in COMPONENT_KEYS:
                component = _component_by_key(docs["inventory"], key)
                write_json(export_dir / "component-fingerprints" / f"{key}.json", component.get("fingerprint") or _empty_fingerprint(key))
            manifest = self._build_manifest(center_id, export_dir, docs)
            write_json(export_dir / "manifest.json", manifest)
            return {"status": docs["report"].get("status"), "center_id": center_id, "export_dir": str(export_dir), "manifest": manifest}

    def build_zip(self, center_id: str, evidence: DomainDocument | None = None) -> DomainDocument:
        with self.lock:
            self.ensure_mutable(center_id)
            exported = self.export_package(center_id, evidence or {})
            export_dir = Path(exported["export_dir"])
            zip_path = self.zip_path(center_id)
            if zip_path.exists():
                zip_path.unlink()
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            with zipfile.ZipFile(zip_path) as archive:
                entries = sorted(info.filename for info in archive.infolist())
            manifest = read_json(export_dir / "manifest.json")
            manifest["zip"] = {"filename": zip_path.name, "sha256": _sha256_path(zip_path), "size_bytes": zip_path.stat().st_size, "entry_count": len(entries), "entries": entries}
            manifest["files"] = [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"]
            manifest["integrity_hash"] = _integrity_hash(manifest)
            write_json(export_dir / "manifest.json", manifest)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(export_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(export_dir).as_posix())
            return {"status": exported["status"], "center_id": center_id, "zip_path": str(zip_path), "zip_sha256": _sha256_path(zip_path), "manifest": manifest}

    def verify_zip(self, center_id: str, *, evidence: DomainDocument | None = None, strict: bool = True, require_ready: bool = False) -> DomainDocument:
        report = verify_unified_command_center_package(self.zip_path(center_id), strict=strict, require_ready=require_ready, **evidence_to_verifier_kwargs(evidence or {}))
        write_unified_command_center_verification_report(report, self.verification_report_path(center_id))
        return report

    def gate(self, center_id: str, *, required: bool, command_center_zip_path: Path | str | None = None, command_center_verification_report_path: Path | str | None = None, evidence: DomainDocument | None = None) -> DomainDocument:
        if not required:
            return {"status": "not_required", "hard_block": False}
        zip_path = Path(command_center_zip_path) if command_center_zip_path else self.zip_path(center_id)
        report_path = Path(command_center_verification_report_path) if command_center_verification_report_path else self.verification_report_path(center_id)
        if not zip_path.exists():
            return _gate_failed("Unified Command Center ZIP is missing.")
        if not report_path.exists():
            return _gate_failed("Unified Command Center verification report is missing.")
        try:
            external_report = read_json(report_path)
            runtime = verify_unified_command_center_package(zip_path, strict=True, require_ready=True, **evidence_to_verifier_kwargs(evidence or {}))
            if external_report.get("integrity_hash") != _integrity_hash(external_report):
                return _gate_failed("Unified Command Center verification integrity failed.", verification=external_report)
            if external_report.get("status") != "passed" or runtime.get("status") != "passed":
                return _gate_failed("Unified Command Center verification failed.", verification=runtime)
            if external_report.get("zip_sha256") != _sha256_path(zip_path) or external_report.get("manifest_hash") != runtime.get("manifest_hash"):
                return _gate_failed("Unified Command Center verification does not match current ZIP.", verification=runtime)
            return {"status": "passed", "hard_block": False, "message": "Unified Command Center gate passed.", "zip_sha256": runtime.get("zip_sha256"), "manifest_hash": runtime.get("manifest_hash"), "verification_hash": external_report.get("integrity_hash"), "summary": runtime.get("summary", {})}
        except Exception as exc:
            return _gate_failed(sanitize_sensitive_text(str(exc)))

    def signoff_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "signoff.json"

    def signoff_history_path(self, center_id: str) -> Path:
        return self.center_dir(center_id) / "signoff-history.jsonl"

    def latest_signoff_state(self, center_id: str) -> DomainDocument:
        latest: ImplementationDocument | None = None
        for event in self.read_signoff_history(center_id):
            event_type = str(event.get("event_type") or "")
            if event_type == "ucc_signoff_created":
                latest = {"status": "signed", "signoff_hash": event.get("signoff_hash"), "event": event}
            elif event_type == "ucc_signoff_reset":
                latest = {"status": "reset", "previous_signoff_hash": event.get("previous_signoff_hash"), "event": event}
        if latest:
            return latest
        if self.signoff_path(center_id).exists():
            signoff = read_json(self.signoff_path(center_id))
            if signoff.get("status") == "signed":
                return {"status": "signed", "signoff_hash": signoff.get("integrity_hash"), "event": {}}
        return {"status": "unsigned"}

    def read_signoff_history(self, center_id: str) -> list[DomainDocument]:
        path = self.signoff_history_path(center_id)
        if not path.exists():
            return []
        rows: list[ImplementationDocument] = []
        import json

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def ensure_mutable(self, center_id: str) -> None:
        state = self.latest_signoff_state(center_id)
        if state.get("status") == "signed":
            raise UnifiedCommandCenterStateError("Unified Command Center is signed. Reset signoff with an approved Change Request before modifying it.")

    def _next_center_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        existing = []
        for path in self.root.glob("ucc-*"):
            try:
                existing.append(int(path.name.split("-")[-1]))
            except ValueError:
                continue
        return f"ucc-{(max(existing) + 1) if existing else 1:06d}"

    def _ensure_docs(self, center_id: str, evidence: ImplementationDocument) -> ImplementationDocument:
        if not self.report_path(center_id).exists():
            return self._build_documents(center_id, evidence)
        return {
            "source": read_json(self.source_path(center_id)),
            "report": read_json(self.report_path(center_id)),
            "graph": read_json(self.graph_path(center_id)),
            "inventory": read_json(self.inventory_path(center_id)),
            "readiness": read_json(self.readiness_path(center_id)),
            "gap_plan": read_json(self.gap_plan_path(center_id)),
            "runbook": read_json(self.runbook_path(center_id)),
            "runbook_result": read_json(self.runbook_result_path(center_id)) if self.runbook_result_path(center_id).exists() else _runbook_result(center_id, None, []),
            "verification_index": read_json(self.verification_index_path(center_id)),
        }

    def _write_docs(self, center_id: str, docs: dict[str, ImplementationDocument]) -> None:
        center = self.read_center(center_id)
        center["status"] = docs["report"].get("status")
        center["updated_at"] = now_iso()
        center["latest_report_id"] = docs["report"].get("report_id")
        center["source_hash"] = docs["source"].get("source_hash")
        center["integrity_hash"] = _integrity_hash(center)
        self.center_dir(center_id).mkdir(parents=True, exist_ok=True)
        write_json(self.center_path(center_id), center)
        write_json(self.source_path(center_id), docs["source"])
        write_json(self.report_path(center_id), docs["report"])
        write_json(self.graph_path(center_id), docs["graph"])
        write_json(self.inventory_path(center_id), docs["inventory"])
        write_json(self.readiness_path(center_id), docs["readiness"])
        write_json(self.gap_plan_path(center_id), docs["gap_plan"])
        write_json(self.runbook_path(center_id), docs["runbook"])
        write_json(self.verification_index_path(center_id), docs["verification_index"])
        if not self.runbook_result_path(center_id).exists():
            write_json(self.runbook_result_path(center_id), docs["runbook_result"])

    def _build_documents(self, center_id: str, evidence: ImplementationDocument) -> dict[str, ImplementationDocument]:
        center = self.read_center(center_id)
        requirements = _requirements(center.get("requirements", {}), _as_document(evidence.get("requirements")))
        component_rows = [_component_row(defn, evidence, requirements) for defn in COMPONENT_DEFS]
        now = now_iso()
        source = {
            "schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_source",
            "center_id": center_id,
            "requirements": requirements,
            "release_ids": center.get("release_ids", []),
            "primary_release_id": center.get("primary_release_id"),
            "component_fingerprints": {row["component_key"]: row.get("fingerprint") for row in component_rows},
            "tool": {"name": "MusicForge Unified Command Center", "version": __version__},
        }
        source["source_hash"] = stable_hash({key: value for key, value in source.items() if key != "source_hash"})
        source["integrity_hash"] = _integrity_hash(source)
        nodes = [_graph_node(row) for row in component_rows]
        graph = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_evidence_graph", "center_id": center_id, "created_at": now, "source_hash": source["source_hash"], "nodes": nodes, "edges": _graph_edges(nodes)}
        graph["graph_hash"] = stable_hash({"nodes": graph["nodes"], "edges": graph["edges"]})
        graph["integrity_hash"] = _integrity_hash(graph)
        inventory = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_evidence_inventory", "center_id": center_id, "generated_at": now, "source_hash": source["source_hash"], "components": component_rows, "summary": _inventory_summary(component_rows)}
        inventory["integrity_hash"] = _integrity_hash(inventory)
        readiness = _readiness_matrix(center_id, source["source_hash"], component_rows, now)
        gaps = sorted([_gap_item(row) for row in component_rows if row.get("required") and row.get("readiness") != "ready"], key=lambda row: (int(row.get("priority") or 999), str(row.get("component_key") or "")))
        gap_plan = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_gap_plan", "center_id": center_id, "created_at": now, "source_hash": source["source_hash"], "items": gaps, "summary": {"action_count": len(gaps), "safe_action_count": sum(1 for row in gaps if row.get("safe_action")), "manual_action_count": sum(1 for row in gaps if row.get("manual_action")), "blocking_action_count": sum(1 for row in gaps if row.get("blocking"))}}
        gap_plan["integrity_hash"] = _integrity_hash(gap_plan)
        runbook = _runbook(center_id, source["source_hash"], gaps, now)
        runbook_result = _runbook_result(center_id, source["source_hash"], [])
        verification_index = _verification_index(center_id, source["source_hash"], component_rows, now)
        report = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": UNIFIED_COMMAND_CENTER_REPORT_PACKAGE_TYPE, "report_id": f"uccr-{now.replace(':', '').replace('-', '').replace('.', '')}", "center_id": center_id, "generated_at": now, "status": readiness["overall_status"], "source_hash": source["source_hash"], "summary": _report_summary(center, component_rows, readiness), "domain_summary": {row["domain"]: row for row in readiness["domains"]}, "top_blockers": gaps[:10], "next_actions": gaps[:10], "document_hashes": {}, "warnings": []}
        docs = {"source": source, "report": report, "graph": graph, "inventory": inventory, "readiness": readiness, "gap_plan": gap_plan, "runbook": runbook, "runbook_result": runbook_result, "verification_index": verification_index}
        _sync_report_hashes(docs)
        return docs

    def _build_manifest(self, center_id: str, export_dir: Path, docs: ImplementationDocument) -> ImplementationDocument:
        manifest = {
            "schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION,
            "package_type": UNIFIED_COMMAND_CENTER_PACKAGE_TYPE,
            "center_id": center_id,
            "report_id": docs["report"].get("report_id"),
            "source_hash": docs["source"].get("source_hash"),
            "status": docs["report"].get("status"),
            "report_hash": docs["report"].get("integrity_hash"),
            "sidecars": {
                "source_hash": docs["source"].get("source_hash"),
                "source_doc_hash": docs["source"].get("integrity_hash"),
                "evidence_graph_hash": docs["graph"].get("integrity_hash"),
                "inventory_hash": docs["inventory"].get("integrity_hash"),
                "readiness_hash": docs["readiness"].get("integrity_hash"),
                "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
                "runbook_hash": docs["runbook"].get("integrity_hash"),
                "runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
                "verification_index_hash": docs["verification_index"].get("integrity_hash"),
            },
            "tool": {"name": "MusicForge Unified Command Center", "version": __version__},
            "component_keys": list(COMPONENT_KEYS),
            "files": [_file_record(path, path.relative_to(export_dir).as_posix()) for path in sorted(export_dir.rglob("*")) if path.is_file() and path.name != "manifest.json"],
        }
        manifest["integrity_hash"] = _integrity_hash(manifest)
        return manifest


from song_agent.domains.program import v142_ucc_readiness as _v142_ucc_readiness
from song_agent.domains.program.v142_ucc_readiness import (
    evidence_to_verifier_kwargs,
    _requirements,
    _component_row,
    _component_id,
    _empty_fingerprint,
    _graph_node,
    _graph_edges,
    _inventory_summary,
    _readiness_matrix,
    _domain_status,
    _gap_item,
    _safe_action,
    _message,
    _runbook,
    _runbook_result,
    _verification_index,
    _report_summary,
    _sync_report_hashes,
    _component_by_key,
    _readme,
    _gate_failed,
    _integrity_hash,
    _sha256_path,
    _path_list,
    _multi_component_result,
    _component_finish_for_store,
    _component_instance_id,
    _safe_component_id,
    _file_record,
)

_v142_ucc_readiness.bind_globals(globals())
