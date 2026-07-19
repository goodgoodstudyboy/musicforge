# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import json as json
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
from song_agent.domains.program.unified_command_center_release_train_verifier import EXPECTED_EVIDENCE_PACKAGE_TYPES as EXPECTED_EVIDENCE_PACKAGE_TYPES, REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package, write_unified_command_center_release_train_verification_report as write_unified_command_center_release_train_verification_report
from song_agent.domains.program.v142_uccrt_readiness import UnifiedCommandCenterReleaseTrainStoreReadinessMixin
from song_agent.domains.program import v142_uccrt_readiness as _v142_uccrt_readiness
from song_agent.domains.program.v142_uccrt_evidence import UnifiedCommandCenterReleaseTrainStoreEvidenceMixin
from song_agent.domains.program import v142_uccrt_evidence as _v142_uccrt_evidence



DEFAULT_REQUIRED_EVIDENCE = [
    "ucc",
    "ucc_archive",
    "handoff",
    "continuous_review",
    "evidence_review",
    "reviewer_decision_board",
]


class UnifiedCommandCenterReleaseTrainError(ValueError):
    pass


class UnifiedCommandCenterReleaseTrainNotFoundError(UnifiedCommandCenterReleaseTrainError):
    pass


class UnifiedCommandCenterReleaseTrainStateError(UnifiedCommandCenterReleaseTrainError):
    pass


class UnifiedCommandCenterReleaseTrainStore(UnifiedCommandCenterReleaseTrainStoreReadinessMixin, UnifiedCommandCenterReleaseTrainStoreEvidenceMixin):
    def __init__(self, root: Path | str | None = None, *, release_store: ReleaseStore | None = None) -> None:
        self.release_store = release_store or ReleaseStore()
        self.root = Path(root) if root is not None else self.release_store.root.parent / "unified-command-trains"
        self.lock = threading.RLock()


















































def write_external_evidence_manifest(path: Path | str, *, train_id: str, items: list[DomainDocument]) -> DomainDocument:
    manifest = {
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "train_id": train_id,
        "created_at": now_iso(),
        "items": items,
        "summary": {"item_count": len(items)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    write_json(Path(path), manifest)
    return manifest


def _read_external_manifest(path: Any, payload: ImplementationDocument) -> ImplementationDocument:
    if path:
        return read_json(Path(path))
    rows = payload.get("external_evidence") or payload.get("external_evidence_items") or []
    manifest = {
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "train_id": payload.get("train_id"),
        "created_at": now_iso(),
        "items": rows,
        "summary": {"item_count": len(rows)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _build_evidence_rows(items_doc: ImplementationDocument, external_manifest: ImplementationDocument) -> tuple[list[ImplementationDocument], list[ImplementationDocument]]:
    external_by_key = {_evidence_key(row): row for row in external_manifest.get("items", []) if isinstance(row, dict)}
    evidence_rows: list[ImplementationDocument] = []
    item_rows: list[ImplementationDocument] = []
    for item in items_doc.get("items", []):
        required = _required_evidence(item.get("required_evidence"))
        blockers: list[str] = []
        passed_count = 0
        for evidence_type in required:
            key = _evidence_key({"item_id": item.get("item_id"), "center_id": item.get("center_id"), "evidence_type": evidence_type})
            external = external_by_key.get(key, {})
            evidence_row = _evidence_row(item, evidence_type, external)
            if evidence_row["status"] == "passed":
                passed_count += 1
            else:
                blockers.extend(evidence_row.get("blockers", []))
            evidence_rows.append(evidence_row)
        status = "ready" if passed_count == len(required) and not blockers else "blocked"
        item_rows.append({**item, "status": status, "required_evidence_count": len(required), "passed_evidence_count": passed_count, "blockers": sorted(set(blockers))})
    return evidence_rows, item_rows


def _evidence_row(item: ImplementationDocument, evidence_type: str, external: ImplementationDocument) -> ImplementationDocument:
    row: _InferenceType = {
        "item_id": item.get("item_id"),
        "center_id": item.get("center_id"),
        "evidence_type": evidence_type,
        "package_type": EXPECTED_EVIDENCE_PACKAGE_TYPES.get(evidence_type),
        "zip_sha256": None,
        "zip_size_bytes": None,
        "manifest_hash": None,
        "verification_report_hash": None,
        "verification_status": "missing",
        "status": "missing",
        "blockers": [],
    }
    zip_path = Path(str(external.get("zip_path") or ""))
    report_path = Path(str(external.get("verification_report_path") or ""))
    if not zip_path.exists() or not report_path.exists():
        row["blockers"].append("external_evidence_missing")
        return row
    try:
        report = read_json(report_path)
        row.update(
            {
                "zip_sha256": _sha256_path(zip_path),
                "zip_size_bytes": zip_path.stat().st_size,
                "manifest_hash": _zip_manifest_hash(zip_path),
                "verification_report_hash": _integrity_hash(report),
                "verification_status": report.get("status"),
            }
        )
        expected_type = EXPECTED_EVIDENCE_PACKAGE_TYPES.get(evidence_type)
        if report.get("package_type") != expected_type:
            row["blockers"].append("wrong_package_type")
        if not _integrity_ok(report):
            row["blockers"].append("verification_integrity_failed")
        if report.get("status") != "passed":
            row["blockers"].append("verification_not_passed")
        if row["zip_sha256"] != (report.get("zip_sha256") or report.get("summary", {}).get("zip_sha256")):
            row["blockers"].append("zip_sha256_mismatch")
        if row["manifest_hash"] != (report.get("manifest_hash") or report.get("summary", {}).get("manifest_hash")):
            row["blockers"].append("manifest_hash_mismatch")
    except Exception as exc:
        row["blockers"].append(sanitize_sensitive_text(str(exc)))
    row["status"] = "passed" if not row["blockers"] else "failed"
    return sanitize_metadata(row)


def _inventory_document(train_id: str, source_hash: str, evidence_rows: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_release_train_evidence_inventory",
            "train_id": train_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "items": evidence_rows,
            "summary": {
                "evidence_count": len(evidence_rows),
                "passed_count": sum(1 for row in evidence_rows if row.get("status") == "passed"),
                "failed_count": sum(1 for row in evidence_rows if row.get("status") != "passed"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readiness_document(train_id: str, source_hash: str, items: list[ImplementationDocument], evidence_rows: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    overall = "go" if items and all(row.get("status") == "ready" for row in items) else "no_go"
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_release_train_readiness_matrix",
            "train_id": train_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "overall_status": overall,
            "items": items,
            "summary": {
                "item_count": len(items),
                "ready_count": sum(1 for row in items if row.get("status") == "ready"),
                "blocked_count": sum(1 for row in items if row.get("status") != "ready"),
                "evidence_count": len(evidence_rows),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _dependency_document(train_id: str, source_hash: str, items: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    item_status = {str(row.get("item_id")): str(row.get("status")) for row in items}
    edges = []
    for item in items:
        for dependency in item.get("depends_on", []):
            edges.append({"from_item_id": dependency, "to_item_id": item.get("item_id")})
    cycle = _has_cycle(edges)
    blocked = [edge for edge in edges if item_status.get(str(edge.get("from_item_id"))) != "ready"]
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_release_train_dependency_graph",
            "train_id": train_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "nodes": [{"item_id": row.get("item_id"), "center_id": row.get("center_id"), "status": row.get("status")} for row in items],
            "edges": edges,
            "summary": {"cycle_detected": cycle, "blocked_dependency_count": len(blocked), "blocked_dependencies": blocked},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _wave_document(train_id: str, source_hash: str, items: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    waves: dict[str, list[str]] = {}
    for row in items:
        waves.setdefault(str(row.get("wave") or 1), []).append(str(row.get("item_id")))
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_wave_plan", "train_id": train_id, "created_at": created_at, "source_hash": source_hash, "waves": waves, "summary": {"wave_count": len(waves)}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _go_no_go_report(train_id: str, source_hash: str, train: ImplementationDocument, readiness: ImplementationDocument, dependency: ImplementationDocument, inventory: ImplementationDocument, created_at: str) -> ImplementationDocument:
    blockers = []
    if readiness.get("overall_status") != "go":
        blockers.append("readiness:no_go")
    if dependency.get("summary", {}).get("cycle_detected"):
        blockers.append("dependency:cycle")
    if int(dependency.get("summary", {}).get("blocked_dependency_count") or 0):
        blockers.append("dependency:blocked")
    status = "go" if not blockers else "no_go"
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_go_no_go_report", "train_id": train_id, "created_at": created_at, "source_hash": source_hash, "status": status, "blockers": blockers, "summary": {"train_name": train.get("name"), "item_count": readiness.get("summary", {}).get("item_count"), "evidence_failed_count": inventory.get("summary", {}).get("failed_count"), "dependency_blocker_count": dependency.get("summary", {}).get("blocked_dependency_count")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _runbook_document(train_id: str, source_hash: str, readiness: ImplementationDocument, report: ImplementationDocument, created_at: str) -> ImplementationDocument:
    items = [{"item_id": "train-refresh", "action": "release_train.refresh", "safe": True, "status": "pending"}]
    for row in readiness.get("items", []):
        if row.get("status") != "ready":
            items.append({"item_id": f"manual-{row.get('item_id')}", "action": "ucc.remediate", "safe": False, "status": "manual_required", "center_id": row.get("center_id")})
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_safe_runbook", "train_id": train_id, "created_at": created_at, "source_hash": source_hash, "items": items, "summary": {"action_count": len(items), "safe_action_count": sum(1 for item in items if item.get("safe")), "manual_action_count": sum(1 for item in items if not item.get("safe")), "go_no_go_status": report.get("status")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _runbook_result(train_id: str, source_hash: str | None, results: list[ImplementationDocument]) -> ImplementationDocument:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_release_train_safe_runbook_result", "train_id": train_id, "created_at": now_iso(), "source_hash": source_hash, "results": results, "summary": {"completed_count": sum(1 for row in results if row.get("status") == "completed"), "failed_count": sum(1 for row in results if row.get("status") == "failed"), "manual_required_count": sum(1 for row in results if row.get("status") == "manual_required"), "skipped_unsupported_count": sum(1 for row in results if row.get("status") == "skipped_unsupported")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(train_id: str, docs: ImplementationDocument, files: list[ImplementationDocument]) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_SCHEMA_VERSION,
            "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_PACKAGE_TYPE,
            "train_id": train_id,
            "created_at": now_iso(),
            "source_hash": docs["source"].get("source_hash"),
            "source": {
                "train_hash": docs["train"].get("integrity_hash"),
                "source_hash": docs["source"].get("integrity_hash"),
                "items_hash": docs["items"].get("integrity_hash"),
                "evidence_inventory_hash": docs["inventory"].get("integrity_hash"),
                "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
                "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
                "wave_plan_hash": docs["wave"].get("integrity_hash"),
                "go_no_go_report_hash": docs["report"].get("integrity_hash"),
                "safe_runbook_hash": docs["runbook"].get("integrity_hash"),
                "safe_runbook_result_hash": docs["runbook_result"].get("integrity_hash"),
                "train_signoff_hash": docs["signoff"].get("integrity_hash"),
                "train_signoff_binding_hash": docs["signoff_binding"].get("integrity_hash"),
            },
            "summary": docs["report"].get("summary", {}),
            "files": sorted(files, key=lambda row: row.get("path") or ""),
            "zip": {},
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _reviewer_guide(docs: ImplementationDocument) -> str:
    return "\n".join(["# MusicForge UCC Release Train", "", f"Train: {docs['train'].get('train_id')}", f"Status: {docs['report'].get('status')}", "", "Verify with verify-unified-command-center-release-train-package and the external evidence manifest.", ""])


def _readme(docs: ImplementationDocument) -> str:
    return "\n".join(["MusicForge Unified Command Center Release Train", "", f"Train: {docs['train'].get('train_id')}", f"Go/No-Go: {docs['report'].get('status')}", ""])


def _required_evidence(value: Any) -> list[str]:
    if not value:
        return list(DEFAULT_REQUIRED_EVIDENCE)
    rows = [str(item) for item in value if str(item)] if isinstance(value, list) else [str(value)]
    return [item for item in rows if item in EXPECTED_EVIDENCE_PACKAGE_TYPES]


def _evidence_key(row: ImplementationDocument) -> str:
    return "|".join(str(row.get(key) or "") for key in ("item_id", "center_id", "evidence_type"))


def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]


def _gate_failed(message: str, **extra: Any) -> ImplementationDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}


def _file_record(path: Path, rel: str) -> ImplementationDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


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


def _zip_manifest_hash(path: Path | str) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            return manifest.get("integrity_hash")
    except Exception:
        return None


def _has_cycle(edges: list[ImplementationDocument]) -> bool:
    graph: dict[str, list[str]] = {}
    for row in edges:
        source = str(row.get("from_item_id") or "")
        target = str(row.get("to_item_id") or "")
        if not source or not target:
            continue
        graph.setdefault(source, []).append(target)
        graph.setdefault(target, graph.get(target, []))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(graph))

_v142_uccrt_readiness.bind_globals(globals())
_v142_uccrt_evidence.bind_globals(globals())
