from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, document_or as _document_or

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

    def create(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def list_centers(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        centers: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("ucc-*")):
            center_path = path / "center.json"
            if center_path.exists():
                centers.append(read_json(center_path))
        return centers

    def read_center(self, center_id: str) -> dict[str, Any]:
        if not self.center_path(center_id).exists():
            raise UnifiedCommandCenterNotFoundError(f"Unified Command Center not found: {center_id}")
        return read_json(self.center_path(center_id))

    def read_report(self, center_id: str) -> dict[str, Any]:
        if not self.report_path(center_id).exists():
            raise UnifiedCommandCenterNotFoundError(f"Unified Command Center report not found: {center_id}")
        return read_json(self.report_path(center_id))

    def refresh(self, center_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            self.ensure_mutable(center_id)
            docs = self._build_documents(center_id, evidence or {})
            self._write_docs(center_id, docs)
            return docs["report"]

    def create_runbook(self, center_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            self.ensure_mutable(center_id)
            docs = self._ensure_docs(center_id, evidence or {})
            return docs["runbook"]

    def run_safe(self, center_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.lock:
            self.ensure_mutable(center_id)
            docs = self._ensure_docs(center_id, evidence or {})
            current_source_hash = self._build_documents(center_id, evidence or {})["source"]["source_hash"]
            if current_source_hash != docs["source"].get("source_hash"):
                raise UnifiedCommandCenterStateError("Unified Command Center source is stale. Refresh before running safe actions.")
            results: list[dict[str, Any]] = []
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

    def export_package(self, center_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def build_zip(self, center_id: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def verify_zip(self, center_id: str, *, evidence: dict[str, Any] | None = None, strict: bool = True, require_ready: bool = False) -> dict[str, Any]:
        report = verify_unified_command_center_package(self.zip_path(center_id), strict=strict, require_ready=require_ready, **evidence_to_verifier_kwargs(evidence or {}))
        write_unified_command_center_verification_report(report, self.verification_report_path(center_id))
        return report

    def gate(self, center_id: str, *, required: bool, command_center_zip_path: Path | str | None = None, command_center_verification_report_path: Path | str | None = None, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def latest_signoff_state(self, center_id: str) -> dict[str, Any]:
        latest: dict[str, Any] | None = None
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

    def read_signoff_history(self, center_id: str) -> list[dict[str, Any]]:
        path = self.signoff_history_path(center_id)
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
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


def evidence_to_verifier_kwargs(evidence: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "release": ("release_zip_path", "release_verification_report_path"),
        "audio-command-center": ("release_audio_command_center_zip_path", "release_audio_command_center_verification_report_path"),
        "trust-operations-hub": ("trust_operations_hub_zip_path", "trust_operations_hub_verification_report_path"),
        "public-trust-center": ("public_trust_center_zip_path", "public_trust_center_verification_report_path"),
        "operations": ("release_operations_zip_path", "release_operations_verification_report_path"),
        "maintenance": ("maintenance_backup_zip_path", "maintenance_backup_verification_report_path"),
    }
    kwargs: dict[str, Any] = {}
    for key, (zip_arg, report_arg) in mapping.items():
        paths = _as_document(evidence.get(key))
        zip_value = paths.get("zip") or paths.get("zip_path") or evidence.get(zip_arg) or evidence.get(zip_arg.replace("_path", ""))
        report_value = paths.get("verification_report") or paths.get("verification_report_path") or evidence.get(report_arg) or evidence.get(report_arg.replace("_path", ""))
        if zip_value:
            kwargs[zip_arg] = zip_value
        if report_value:
            kwargs[report_arg] = report_value
    for key, zip_arg, report_arg in (
        ("distribution", "distribution_zip_paths", "distribution_verification_report_paths"),
        ("submission", "submission_zip_paths", "submission_verification_report_paths"),
    ):
        paths = _as_document(evidence.get(key))
        zips = _path_list(paths.get("zips") or paths.get("zip_paths") or paths.get("zip") or evidence.get(zip_arg))
        reports = _path_list(paths.get("verification_reports") or paths.get("verification_report_paths") or paths.get("verification_report") or evidence.get(report_arg))
        if zips:
            kwargs[zip_arg] = zips
        if reports:
            kwargs[report_arg] = reports
    ga = _as_document(evidence.get("ga-readiness"))
    if ga.get("report") or evidence.get("ga_readiness_report_path"):
        kwargs["ga_readiness_report_path"] = ga.get("report") or evidence.get("ga_readiness_report_path")
    if ga.get("verification_report") or evidence.get("ga_readiness_verification_report_path"):
        kwargs["ga_readiness_verification_report_path"] = ga.get("verification_report") or evidence.get("ga_readiness_verification_report_path")
    release_check = _as_document(evidence.get("release-check"))
    if release_check.get("report") or evidence.get("release_check_report_path"):
        kwargs["release_check_report_path"] = release_check.get("report") or evidence.get("release_check_report_path")
    if isinstance(evidence.get("audio_evidence"), dict):
        kwargs["audio_evidence"] = evidence["audio_evidence"]
    if isinstance(evidence.get("trust_evidence"), dict):
        kwargs["trust_evidence"] = evidence["trust_evidence"]
    if isinstance(evidence.get("public_trust_evidence"), dict):
        kwargs["public_trust_evidence"] = evidence["public_trust_evidence"]
    return kwargs


def _requirements(*sources: ImplementationDocument) -> dict[str, bool]:
    result = dict(DEFAULT_REQUIREMENTS)
    aliases = {
        "require_audio_command_center": "audio-command-center",
        "require_trust_operations_hub": "trust-operations-hub",
        "require_public_trust_center": "public-trust-center",
        "require_maintenance_backup": "maintenance",
        "require_ga_readiness": "ga-readiness",
        "require_release_check": "release-check",
        "require_release_ready": "release",
        "require_distribution_ready": "distribution",
        "require_submission_accepted": "submission",
        "require_submission_ready": "submission",
        "require_operations_signed": "operations",
        "require_operations_ready": "operations",
    }
    for source in sources:
        for key, value in source.items():
            if key in result:
                result[key] = bool(value)
            elif key in aliases:
                result[aliases[key]] = bool(value)
    return result


def _component_row(defn: dict[str, str], evidence: ImplementationDocument, requirements: dict[str, bool]) -> ImplementationDocument:
    key = defn["key"]
    required = bool(requirements.get(key, False))
    paths = _as_document(evidence.get(key))
    if key in {"distribution", "submission"}:
        component = _multi_component_result(key, paths)
    else:
        component = verify_unified_command_center_component(
            key,
            zip_path=paths.get("zip") or paths.get("zip_path"),
            verification_report_path=paths.get("verification_report") or paths.get("verification_report_path"),
            report_path=paths.get("report") or paths.get("report_path"),
            audio_evidence=_as_document(evidence.get("audio_evidence")),
            trust_evidence=_as_document(evidence.get("trust_evidence")),
            public_trust_evidence=_as_document(evidence.get("public_trust_evidence")),
        )
    readiness = component.get("readiness") if required else "not_required" if component.get("readiness") == "missing" else component.get("readiness")
    return sanitize_metadata(
        {
            "node_id": f"{defn['domain']}.{key}",
            "domain": defn["domain"],
            "component_key": key,
            "component_type": defn["component_type"],
            "component_id": _component_id(key, evidence),
            "label": defn["label"],
            "required": required,
            "readiness": readiness,
            "status": component.get("status"),
            "zip_present": bool(paths.get("zip") or paths.get("zip_path") or paths.get("zips") or paths.get("zip_paths")),
            "verification_report_present": bool(paths.get("verification_report") or paths.get("verification_report_path") or paths.get("verification_reports") or paths.get("verification_report_paths") or paths.get("report") or paths.get("report_path")),
            "runtime_status": (component.get("fingerprint") or {}).get("runtime_status"),
            "runtime_blockers": (component.get("fingerprint") or {}).get("runtime_blockers", []),
            "runtime_manifest_hash": (component.get("fingerprint") or {}).get("runtime_manifest_hash"),
            "fingerprint": component.get("fingerprint") or _empty_fingerprint(key),
            "checks": component.get("checks", []),
            "blockers": component.get("blockers", []),
            "last_checked_at": now_iso(),
        }
    )


def _component_id(key: str, evidence: ImplementationDocument) -> str:
    if key == "audio-command-center":
        return str(evidence.get("primary_release_id") or "")
    if key == "trust-operations-hub":
        return str(evidence.get("hub_id") or "hub")
    if key == "public-trust-center":
        return str(evidence.get("center_id") or "ptc-default")
    return key


def _empty_fingerprint(key: str) -> ImplementationDocument:
    doc: _InferenceType = {"component_key": key, "status": "not_configured", "items": [], "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _graph_node(row: ImplementationDocument) -> ImplementationDocument:
    return {"node_id": row["node_id"], "domain": row["domain"], "component_type": row["component_type"], "component_id": row.get("component_id"), "label": row["label"], "required": row["required"], "readiness": row["readiness"], "status": row["status"], "fingerprint": row.get("fingerprint", {})}


def _graph_edges(nodes: list[ImplementationDocument]) -> list[ImplementationDocument]:
    ids = {row["node_id"] for row in nodes}
    edges: list[dict[str, Any]] = []
    if "audio.audio-command-center" in ids and "release.release" in ids:
        edges.append({"from": "audio.audio-command-center", "to": "release.release", "relation": "supports_release_signoff"})
    if "public_trust.public-trust-center" in ids and "trust_operations.trust-operations-hub" in ids:
        edges.append({"from": "public_trust.public-trust-center", "to": "trust_operations.trust-operations-hub", "relation": "feeds_hub"})
    if "trust_operations.trust-operations-hub" in ids and "ga.ga-readiness" in ids:
        edges.append({"from": "trust_operations.trust-operations-hub", "to": "ga.ga-readiness", "relation": "supports_ga"})
    if "audio.audio-command-center" in ids and "ga.ga-readiness" in ids:
        edges.append({"from": "audio.audio-command-center", "to": "ga.ga-readiness", "relation": "supports_ga"})
    return edges


def _inventory_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "total": len(rows),
        "ready": sum(1 for row in rows if row.get("readiness") == "ready"),
        "blocked": sum(1 for row in rows if row.get("required") and row.get("readiness") not in {"ready", "not_required"}),
        "missing": sum(1 for row in rows if row.get("readiness") == "missing"),
        "stale": sum(1 for row in rows if row.get("readiness") == "stale"),
        "manual_required": sum(1 for row in rows if row.get("readiness") == "manual_required"),
    }


def _readiness_matrix(center_id: str, source_hash: str, rows: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    domains: list[dict[str, Any]] = []
    for domain in sorted({str(row.get("domain")) for row in rows}):
        domain_rows = [row for row in rows if row.get("domain") == domain]
        required_rows = [row for row in domain_rows if row.get("required")]
        blocked_rows = [row for row in required_rows if row.get("readiness") != "ready"]
        status = "not_required" if not required_rows else "ready" if not blocked_rows else _domain_status(blocked_rows)
        domains.append(
            {
                "domain": domain,
                "status": status,
                "required": bool(required_rows),
                "ready_count": sum(1 for row in required_rows if row.get("readiness") == "ready"),
                "blocked_count": len(blocked_rows),
                "manual_required_count": sum(1 for row in required_rows if row.get("readiness") == "manual_required"),
                "top_blockers": [{"node_id": row.get("node_id"), "reason": _message(row)} for row in blocked_rows[:5]],
            }
        )
    required_blocked = [row for row in rows if row.get("required") and row.get("readiness") != "ready"]
    overall = "ready" if not required_blocked else "warning" if all(row.get("readiness") == "manual_required" for row in required_blocked) else "blocked"
    matrix = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_readiness_matrix", "center_id": center_id, "created_at": created_at, "source_hash": source_hash, "overall_status": overall, "overall_score": max(0, 100 - len(required_blocked) * 10), "domains": domains, "release_gates": {"release_signoff_ready": overall == "ready", "ga_ready": overall == "ready", "external_handoff_ready": overall == "ready"}}
    matrix["integrity_hash"] = _integrity_hash(matrix)
    return matrix


def _domain_status(rows: list[ImplementationDocument]) -> str:
    order = ["runtime_failed", "verification_failed", "stale", "blocked", "missing", "manual_required", "warning"]
    states = {str(row.get("readiness") or "") for row in rows}
    for item in order:
        if item in states:
            return item
    return "blocked"


def _gap_item(row: ImplementationDocument) -> ImplementationDocument:
    readiness = str(row.get("readiness") or "blocked")
    priority = {"runtime_failed": 10, "verification_failed": 20, "stale": 30, "missing": 40, "blocked": 50, "manual_required": 80, "warning": 90}.get(readiness, 60)
    item = {"gap_id": f"ucc-gap-{row.get('component_key')}", "priority": priority, "domain": row.get("domain"), "component_key": row.get("component_key"), "node_id": row.get("node_id"), "readiness": readiness, "title": f"Resolve {row.get('label')}", "reason": _message(row), "safe_action": _safe_action(row), "manual_action": None if _safe_action(row) else f"Complete manual remediation for {row.get('label')}.", "blocking": True}
    item["integrity_hash"] = _integrity_hash(item)
    return item


def _safe_action(row: ImplementationDocument) -> str | None:
    key = str(row.get("component_key") or "")
    if key in {"release", "audio-command-center", "trust-operations-hub", "public-trust-center", "distribution", "submission", "operations", "ga-readiness", "maintenance", "release-check"}:
        return f"{key}.verify"
    return None


def _message(row: ImplementationDocument) -> str:
    readiness = str(row.get("readiness") or "")
    label = str(row.get("label") or row.get("component_key") or "component")
    if readiness == "missing":
        return f"{label} evidence is missing."
    if readiness == "stale":
        return f"{label} verification is stale."
    if readiness == "verification_failed":
        return f"{label} verification failed."
    if readiness == "runtime_failed":
        return f"{label} runtime verification failed."
    if readiness == "manual_required":
        return f"{label} requires manual action."
    if readiness == "not_required":
        return f"{label} is not required."
    return f"{label} is blocked."


def _runbook(center_id: str, source_hash: str, gaps: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    items = [
        {"item_id": "ucc-safe-001", "action": "unified_command_center.refresh", "safe": True, "status": "pending"},
        {"item_id": "ucc-safe-002", "action": "unified_command_center.export", "safe": True, "status": "pending"},
        {"item_id": "ucc-safe-003", "action": "unified_command_center.zip", "safe": True, "status": "pending"},
        {"item_id": "ucc-safe-004", "action": "unified_command_center.verify", "safe": True, "status": "pending"},
    ]
    for index, gap in enumerate(gaps, start=1):
        items.append({"item_id": f"ucc-manual-{index:03d}", "action": gap.get("manual_action") or gap.get("safe_action") or "resolve_gap", "safe": False if gap.get("manual_action") else True, "status": "manual_required" if gap.get("manual_action") else "pending", "source_gap_id": gap.get("gap_id")})
    doc = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_safe_runbook", "center_id": center_id, "runbook_id": f"ucc-runbook-{center_id}", "created_at": created_at, "source_hash": source_hash, "items": items, "summary": {"action_count": len(items), "safe_action_count": sum(1 for item in items if item.get("safe")), "manual_action_count": sum(1 for item in items if not item.get("safe"))}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _runbook_result(center_id: str, source_hash: str | None, results: list[ImplementationDocument]) -> ImplementationDocument:
    doc = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_runbook_result", "center_id": center_id, "created_at": now_iso(), "source_hash": source_hash, "results": results, "summary": {"completed_count": sum(1 for row in results if row.get("status") == "completed"), "failed_count": sum(1 for row in results if row.get("status") == "failed"), "manual_required_count": sum(1 for row in results if row.get("status") == "manual_required"), "skipped_unsupported_count": sum(1 for row in results if row.get("status") == "skipped_unsupported")}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _verification_index(center_id: str, source_hash: str, rows: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    items = []
    for row in rows:
        fp = row.get("fingerprint") or {}
        items.append({"component_key": row.get("component_key"), "domain": row.get("domain"), "status": row.get("status"), "readiness": row.get("readiness"), "verification_report_hash": fp.get("verification_report_hash"), "runtime_status": fp.get("runtime_status"), "runtime_manifest_hash": fp.get("runtime_manifest_hash")})
    doc = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_verification_index", "center_id": center_id, "created_at": created_at, "source_hash": source_hash, "items": items}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _report_summary(center: ImplementationDocument, rows: list[ImplementationDocument], readiness: ImplementationDocument) -> ImplementationDocument:
    required = [row for row in rows if row.get("required")]
    return {"overall_status": readiness.get("overall_status"), "release_count": len(center.get("release_ids", [])), "required_components": len(required), "ready_components": sum(1 for row in required if row.get("readiness") == "ready"), "blocked_components": sum(1 for row in required if row.get("readiness") not in {"ready", "manual_required"}), "manual_required_components": sum(1 for row in required if row.get("readiness") == "manual_required")}


def _sync_report_hashes(docs: ImplementationDocument) -> None:
    report = docs["report"]
    report["document_hashes"] = {"source": docs["source"].get("integrity_hash"), "evidence_graph": docs["graph"].get("integrity_hash"), "evidence_inventory": docs["inventory"].get("integrity_hash"), "readiness_matrix": docs["readiness"].get("integrity_hash"), "gap_plan": docs["gap_plan"].get("integrity_hash"), "safe_runbook": docs["runbook"].get("integrity_hash"), "runbook_result": docs["runbook_result"].get("integrity_hash"), "verification_index": docs["verification_index"].get("integrity_hash")}
    report["evidence_graph_hash"] = docs["graph"].get("integrity_hash")
    report["inventory_hash"] = docs["inventory"].get("integrity_hash")
    report["readiness_hash"] = docs["readiness"].get("integrity_hash")
    report["gap_plan_hash"] = docs["gap_plan"].get("integrity_hash")
    report["runbook_hash"] = docs["runbook"].get("integrity_hash")
    report["integrity_hash"] = _integrity_hash(report)


def _component_by_key(inventory: ImplementationDocument, key: str) -> ImplementationDocument:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return row
    return {"fingerprint": _empty_fingerprint(key)}


def _readme(report: ImplementationDocument) -> str:
    return "\n".join(["MusicForge Unified Command Center", "", f"Center: {report.get('center_id')}", f"Status: {report.get('status')}", "", "Verify this package with verify-unified-command-center-package and the referenced external evidence packages.", ""])


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item]
    return [value] if value else []


def _multi_component_result(key: str, paths: ImplementationDocument) -> ImplementationDocument:
    zips = _path_list(paths.get("zips") or paths.get("zip_paths") or paths.get("zip") or paths.get("zip_path"))
    reports = _path_list(paths.get("verification_reports") or paths.get("verification_report_paths") or paths.get("verification_report") or paths.get("verification_report_path"))
    checks: list[dict[str, Any]] = []
    fingerprint = _empty_fingerprint(key)
    fingerprint["items"] = []
    if not zips and not reports:
        component = verify_unified_command_center_component(key)
        return component
    if len(zips) != len(reports):
        checks.append({"check_id": f"ucc_{key}_external_pair_count", "status": "failed", "message": f"{key} ZIP/report counts match.", "details": {"zip_count": len(zips), "report_count": len(reports)}, "blocking": True})
        return _component_finish_for_store(key, fingerprint, checks)
    for index, (zip_path, report_path) in enumerate(zip(zips, reports), start=1):
        component = verify_unified_command_center_component(key, zip_path=zip_path, verification_report_path=report_path)
        fp = _as_document(component.get("fingerprint"))
        component_id = _component_instance_id(key, component, index)
        fingerprint["items"].append(
            {
                "component_id": component_id,
                "zip_sha256": fp.get("zip_sha256"),
                "zip_size_bytes": fp.get("zip_size_bytes"),
                "manifest_hash": fp.get("manifest_hash"),
                "verification_report_hash": fp.get("verification_report_hash"),
                "verification_status": fp.get("verification_status"),
                "runtime_status": fp.get("runtime_status"),
                "runtime_manifest_hash": fp.get("runtime_manifest_hash"),
                "runtime_failed_count": fp.get("runtime_failed_count"),
                "runtime_blockers": fp.get("runtime_blockers", []),
            }
        )
        checks.extend(component.get("checks") or [])
    fingerprint["items"] = sorted(fingerprint["items"], key=lambda item: str(item.get("component_id") or ""))
    fingerprint["item_count"] = len(fingerprint["items"])
    fingerprint["verification_status"] = "passed" if all(item.get("verification_status") == "passed" for item in fingerprint["items"]) else "failed"
    fingerprint["runtime_status"] = "passed" if all(item.get("runtime_status") == "passed" for item in fingerprint["items"]) else "failed"
    fingerprint["runtime_failed_count"] = sum(int(item.get("runtime_failed_count") or 0) for item in fingerprint["items"])
    fingerprint["runtime_blockers"] = [blocker for item in fingerprint["items"] for blocker in item.get("runtime_blockers", [])]
    fingerprint["integrity_hash"] = _integrity_hash(fingerprint)
    return _component_finish_for_store(key, fingerprint, checks)


def _component_finish_for_store(key: str, fingerprint: ImplementationDocument, checks: list[ImplementationDocument]) -> ImplementationDocument:
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    fingerprint["integrity_hash"] = _integrity_hash(fingerprint)
    result = {"component_key": key, "status": "passed" if not blockers else "failed", "readiness": "ready" if not blockers else "missing" if any("required" in item or "exists" in item for item in blockers) else "stale" if any("binding" in item for item in blockers) else "verification_failed", "fingerprint": fingerprint, "checks": checks, "blockers": blockers}
    result["integrity_hash"] = _integrity_hash(result)
    return result


def _component_instance_id(key: str, component: ImplementationDocument, index: int) -> str:
    for report_key in ("external_report", "runtime_report"):
        report = _as_document(component.get(report_key))
        summary = _as_document(report.get("summary"))
        prefix = {"distribution": "distribution", "submission": "submission"}.get(key, key)
        for field in ("release_id", "target_id", "submission_id", "package_id"):
            value = report.get(field) or summary.get(field)
            if value:
                return f"{prefix}:{_safe_component_id(str(value))}"
    return f"{key}:{index:03d}"


def _safe_component_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip()).strip("-") or "unknown"


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}
