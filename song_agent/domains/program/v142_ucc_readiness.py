# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, document_or as _document_or
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_verifier import COMPONENT_KEYS as COMPONENT_KEYS, RUNTIME_COMPONENT_KEYS as RUNTIME_COMPONENT_KEYS, UNIFIED_COMMAND_CENTER_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, verify_unified_command_center_component as verify_unified_command_center_component, verify_unified_command_center_package as verify_unified_command_center_package, write_unified_command_center_verification_report as write_unified_command_center_verification_report

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

blocker = _make_deferred_global('blocker')
check = _make_deferred_global('check')

def bind_globals(namespace: dict[str, object]) -> None:
    global blocker, check
    blocker = namespace.get('blocker', blocker)
    check = namespace.get('check', check)
    _bind_deferred_defaults(namespace)


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




def evidence_to_verifier_kwargs(evidence: DomainDocument) -> DomainDocument:
    mapping = {
        "release": ("release_zip_path", "release_verification_report_path"),
        "audio-command-center": ("release_audio_command_center_zip_path", "release_audio_command_center_verification_report_path"),
        "trust-operations-hub": ("trust_operations_hub_zip_path", "trust_operations_hub_verification_report_path"),
        "public-trust-center": ("public_trust_center_zip_path", "public_trust_center_verification_report_path"),
        "operations": ("release_operations_zip_path", "release_operations_verification_report_path"),
        "maintenance": ("maintenance_backup_zip_path", "maintenance_backup_verification_report_path"),
    }
    kwargs: DomainDocument = {}
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

def _requirements(*sources: DomainDocument) -> dict[str, bool]:
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

def _component_row(defn: dict[str, str], evidence: DomainDocument, requirements: dict[str, bool]) -> DomainDocument:
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

def _component_id(key: str, evidence: DomainDocument) -> str:
    if key == "audio-command-center":
        return str(evidence.get("primary_release_id") or "")
    if key == "trust-operations-hub":
        return str(evidence.get("hub_id") or "hub")
    if key == "public-trust-center":
        return str(evidence.get("center_id") or "ptc-default")
    return key

def _empty_fingerprint(key: str) -> DomainDocument:
    doc: object = {"component_key": key, "status": "not_configured", "items": [], "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _graph_node(row: DomainDocument) -> DomainDocument:
    return {"node_id": row["node_id"], "domain": row["domain"], "component_type": row["component_type"], "component_id": row.get("component_id"), "label": row["label"], "required": row["required"], "readiness": row["readiness"], "status": row["status"], "fingerprint": row.get("fingerprint", {})}

def _graph_edges(nodes: list[DomainDocument]) -> list[DomainDocument]:
    ids = {row["node_id"] for row in nodes}
    edges: list[DomainDocument] = []
    if "audio.audio-command-center" in ids and "release.release" in ids:
        edges.append({"from": "audio.audio-command-center", "to": "release.release", "relation": "supports_release_signoff"})
    if "public_trust.public-trust-center" in ids and "trust_operations.trust-operations-hub" in ids:
        edges.append({"from": "public_trust.public-trust-center", "to": "trust_operations.trust-operations-hub", "relation": "feeds_hub"})
    if "trust_operations.trust-operations-hub" in ids and "ga.ga-readiness" in ids:
        edges.append({"from": "trust_operations.trust-operations-hub", "to": "ga.ga-readiness", "relation": "supports_ga"})
    if "audio.audio-command-center" in ids and "ga.ga-readiness" in ids:
        edges.append({"from": "audio.audio-command-center", "to": "ga.ga-readiness", "relation": "supports_ga"})
    return edges

def _inventory_summary(rows: list[DomainDocument]) -> dict[str, int]:
    return {
        "total": len(rows),
        "ready": sum(1 for row in rows if row.get("readiness") == "ready"),
        "blocked": sum(1 for row in rows if row.get("required") and row.get("readiness") not in {"ready", "not_required"}),
        "missing": sum(1 for row in rows if row.get("readiness") == "missing"),
        "stale": sum(1 for row in rows if row.get("readiness") == "stale"),
        "manual_required": sum(1 for row in rows if row.get("readiness") == "manual_required"),
    }

def _readiness_matrix(center_id: str, source_hash: str, rows: list[DomainDocument], created_at: str) -> DomainDocument:
    domains: list[DomainDocument] = []
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

def _domain_status(rows: list[DomainDocument]) -> str:
    order = ["runtime_failed", "verification_failed", "stale", "blocked", "missing", "manual_required", "warning"]
    states = {str(row.get("readiness") or "") for row in rows}
    for item in order:
        if item in states:
            return item
    return "blocked"

def _gap_item(row: DomainDocument) -> DomainDocument:
    readiness = str(row.get("readiness") or "blocked")
    priority = {"runtime_failed": 10, "verification_failed": 20, "stale": 30, "missing": 40, "blocked": 50, "manual_required": 80, "warning": 90}.get(readiness, 60)
    item = {"gap_id": f"ucc-gap-{row.get('component_key')}", "priority": priority, "domain": row.get("domain"), "component_key": row.get("component_key"), "node_id": row.get("node_id"), "readiness": readiness, "title": f"Resolve {row.get('label')}", "reason": _message(row), "safe_action": _safe_action(row), "manual_action": None if _safe_action(row) else f"Complete manual remediation for {row.get('label')}.", "blocking": True}
    item["integrity_hash"] = _integrity_hash(item)
    return item

def _safe_action(row: DomainDocument) -> str | None:
    key = str(row.get("component_key") or "")
    if key in {"release", "audio-command-center", "trust-operations-hub", "public-trust-center", "distribution", "submission", "operations", "ga-readiness", "maintenance", "release-check"}:
        return f"{key}.verify"
    return None

def _message(row: DomainDocument) -> str:
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

def _runbook(center_id: str, source_hash: str, gaps: list[DomainDocument], created_at: str) -> DomainDocument:
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

def _runbook_result(center_id: str, source_hash: str | None, results: list[DomainDocument]) -> DomainDocument:
    doc = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_runbook_result", "center_id": center_id, "created_at": now_iso(), "source_hash": source_hash, "results": results, "summary": {"completed_count": sum(1 for row in results if row.get("status") == "completed"), "failed_count": sum(1 for row in results if row.get("status") == "failed"), "manual_required_count": sum(1 for row in results if row.get("status") == "manual_required"), "skipped_unsupported_count": sum(1 for row in results if row.get("status") == "skipped_unsupported")}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _verification_index(center_id: str, source_hash: str, rows: list[DomainDocument], created_at: str) -> DomainDocument:
    items = []
    for row in rows:
        fp = row.get("fingerprint") or {}
        items.append({"component_key": row.get("component_key"), "domain": row.get("domain"), "status": row.get("status"), "readiness": row.get("readiness"), "verification_report_hash": fp.get("verification_report_hash"), "runtime_status": fp.get("runtime_status"), "runtime_manifest_hash": fp.get("runtime_manifest_hash")})
    doc = {"schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_verification_index", "center_id": center_id, "created_at": created_at, "source_hash": source_hash, "items": items}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _report_summary(center: DomainDocument, rows: list[DomainDocument], readiness: DomainDocument) -> DomainDocument:
    required = [row for row in rows if row.get("required")]
    return {"overall_status": readiness.get("overall_status"), "release_count": len(center.get("release_ids", [])), "required_components": len(required), "ready_components": sum(1 for row in required if row.get("readiness") == "ready"), "blocked_components": sum(1 for row in required if row.get("readiness") not in {"ready", "manual_required"}), "manual_required_components": sum(1 for row in required if row.get("readiness") == "manual_required")}

def _sync_report_hashes(docs: DomainDocument) -> None:
    report = docs["report"]
    report["document_hashes"] = {"source": docs["source"].get("integrity_hash"), "evidence_graph": docs["graph"].get("integrity_hash"), "evidence_inventory": docs["inventory"].get("integrity_hash"), "readiness_matrix": docs["readiness"].get("integrity_hash"), "gap_plan": docs["gap_plan"].get("integrity_hash"), "safe_runbook": docs["runbook"].get("integrity_hash"), "runbook_result": docs["runbook_result"].get("integrity_hash"), "verification_index": docs["verification_index"].get("integrity_hash")}
    report["evidence_graph_hash"] = docs["graph"].get("integrity_hash")
    report["inventory_hash"] = docs["inventory"].get("integrity_hash")
    report["readiness_hash"] = docs["readiness"].get("integrity_hash")
    report["gap_plan_hash"] = docs["gap_plan"].get("integrity_hash")
    report["runbook_hash"] = docs["runbook"].get("integrity_hash")
    report["integrity_hash"] = _integrity_hash(report)

def _component_by_key(inventory: DomainDocument, key: str) -> DomainDocument:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return row
    return {"fingerprint": _empty_fingerprint(key)}

def _readme(report: DomainDocument) -> str:
    return "\n".join(["MusicForge Unified Command Center", "", f"Center: {report.get('center_id')}", f"Status: {report.get('status')}", "", "Verify this package with verify-unified-command-center-package and the referenced external evidence packages.", ""])

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

def _integrity_hash(payload: DomainDocument) -> str:
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

def _path_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item]
    return [value] if value else []

def _multi_component_result(key: str, paths: DomainDocument) -> DomainDocument:
    zips = _path_list(paths.get("zips") or paths.get("zip_paths") or paths.get("zip") or paths.get("zip_path"))
    reports = _path_list(paths.get("verification_reports") or paths.get("verification_report_paths") or paths.get("verification_report") or paths.get("verification_report_path"))
    checks: list[DomainDocument] = []
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

def _component_finish_for_store(key: str, fingerprint: DomainDocument, checks: list[DomainDocument]) -> DomainDocument:
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    fingerprint["integrity_hash"] = _integrity_hash(fingerprint)
    result = {"component_key": key, "status": "passed" if not blockers else "failed", "readiness": "ready" if not blockers else "missing" if any("required" in item or "exists" in item for item in blockers) else "stale" if any("binding" in item for item in blockers) else "verification_failed", "fingerprint": fingerprint, "checks": checks, "blockers": blockers}
    result["integrity_hash"] = _integrity_hash(result)
    return result

def _component_instance_id(key: str, component: DomainDocument, index: int) -> str:
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

def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}
