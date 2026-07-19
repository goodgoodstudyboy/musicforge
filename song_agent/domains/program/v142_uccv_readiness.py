# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.trust.ga_readiness_contracts import GA_READINESS_PACKAGE_TYPE as GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION as GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok as ga_readiness_integrity_ok
from song_agent.domains.creation.lts_backup_verifier import verify_maintenance_backup_zip as verify_maintenance_backup_zip
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_verifier import verify_public_trust_center_package as verify_public_trust_center_package
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.distribution_verifier import verify_distribution_package as verify_distribution_package
from song_agent.domains.quality.release_audio_command_center import evidence_to_verifier_kwargs as audio_command_center_evidence_to_kwargs
from song_agent.domains.quality.release_audio_command_center_verifier import verify_release_audio_command_center_package as verify_release_audio_command_center_package
from song_agent.domains.trust.release_operations_verifier import verify_release_operations_package as verify_release_operations_package
from song_agent.domains.delivery.release_verifier import verify_release_zip as verify_release_zip
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.delivery.submission_verifier import verify_submission_package as verify_submission_package
from song_agent.domains.trust.trust_operations_hub_verifier import verify_trust_operations_hub_package as verify_trust_operations_hub_package

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

GA_SENSITIVE_RE = _make_deferred_global('GA_SENSITIVE_RE')
check = _make_deferred_global('check')
part = _make_deferred_global('part')
pattern = _make_deferred_global('pattern')
val = _make_deferred_global('val')
verify_unified_command_center_component = _make_deferred_global('verify_unified_command_center_component')

def bind_globals(namespace: dict[str, object]) -> None:
    global GA_SENSITIVE_RE, check, part, pattern, val, verify_unified_command_center_component
    GA_SENSITIVE_RE = namespace.get('GA_SENSITIVE_RE', GA_SENSITIVE_RE)
    check = namespace.get('check', check)
    part = namespace.get('part', part)
    pattern = namespace.get('pattern', pattern)
    val = namespace.get('val', val)
    verify_unified_command_center_component = namespace.get('verify_unified_command_center_component', verify_unified_command_center_component)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_PACKAGE_TYPE = "musicforge_unified_command_center"
UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_verification"
UNIFIED_COMMAND_CENTER_SCHEMA_VERSION = 1
COMPONENT_KEYS = (
    "release",
    "audio-command-center",
    "trust-operations-hub",
    "public-trust-center",
    "distribution",
    "submission",
    "operations",
    "maintenance",
    "ga-readiness",
    "release-check",
)
RUNTIME_COMPONENT_KEYS = {
    "release",
    "audio-command-center",
    "trust-operations-hub",
    "public-trust-center",
    "distribution",
    "submission",
    "operations",
    "maintenance",
    "ga-readiness",
    "release-check",
}
EXPECTED_VERIFICATION_PACKAGE_TYPES: dict[str, set[str]] = {
    "release": {"musicforge_release_verification"},
    "distribution": {"musicforge_distribution_verification"},
    "submission": {"musicforge_submission_verification"},
    "operations": {"musicforge_release_operations_verification"},
    "maintenance": {"musicforge_lts_maintenance_backup_verification_report"},
    "audio-command-center": {"release_audio_command_center_verification"},
    "trust-operations-hub": {"musicforge_trust_operations_hub_verification"},
}
REQUIRED_ENTRIES = {
    "README.txt",
    "manifest.json",
    "source.json",
    "command-center-report.json",
    "evidence-graph.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "gap-plan.json",
    "safe-runbook.json",
    "runbook-result.json",
    "verification-index.json",
    *{f"component-fingerprints/{key}.json" for key in COMPONENT_KEYS},
}
SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]




def _verify_ga_readiness_report_core(report_path: Path) -> DomainDocument:
    try:
        report = read_json(report_path)
    except Exception as exc:
        return {
            "package_type": "musicforge_ga_readiness_verification_report",
            "status": "failed",
            "blockers": ["ga_readiness_report_readable"],
            "warnings": [],
            "details": {"error": sanitize_sensitive_text(str(exc))},
        }

    status = str(report.get("status") or "unknown")
    checks = [
        _check("ga_readiness_package_type", report.get("package_type") == GA_READINESS_PACKAGE_TYPE, "GA readiness report package type is valid."),
        _check("ga_readiness_schema_version", report.get("schema_version") == GA_READINESS_SCHEMA_VERSION, "GA readiness report schema version is supported."),
        _check("ga_readiness_integrity", ga_readiness_integrity_ok(report), "GA readiness report integrity hash matches."),
        _check("ga_readiness_status_allowed", status in {"ready", "warning"}, f"GA readiness status is {status}.", blocking=status == "blocked"),
        _check("ga_readiness_redaction", not GA_SENSITIVE_RE.search(json.dumps(report, ensure_ascii=False)), "GA readiness report contains no obvious sensitive values."),
    ]
    blockers = [row["check_id"] for row in checks if row.get("status") == "failed" and row.get("blocking", True)]
    warnings = [row["check_id"] for row in checks if row.get("status") == "failed" and not row.get("blocking", True)]
    return {
        "package_type": "musicforge_ga_readiness_verification_report",
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }

def _release_check_component(report_path: Path | str | None) -> DomainDocument:
    checks: list[DomainDocument] = []
    fingerprint: object = {"component_key": "release-check", "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    if not report_path:
        checks.append(_check("ucc_release-check_report_required", False, "release-check JSON report is required."))
        return _component_finish("release-check", fingerprint, checks)
    try:
        report = read_json(Path(report_path))
    except Exception as exc:
        checks.append(_check("ucc_release-check_report_readable", False, "release-check report is readable.", {"error": sanitize_sensitive_text(str(exc))}))
        return _component_finish("release-check", fingerprint, checks)
    failed = [str(item.get("check_id") or "") for item in report.get("results", []) if isinstance(item, dict) and item.get("status") == "failed"]
    ok = bool(report.get("ok")) and not failed
    fingerprint.update({"verification_report_hash": stable_hash(report), "verification_status": "passed" if ok else "failed", "runtime_status": "passed" if ok else "failed", "runtime_failed_count": len(failed), "runtime_blockers": failed})
    checks.append(_check("ucc_release-check_status", ok, "release-check report is passed.", {"failed": failed[:10]}))
    return _component_finish("release-check", fingerprint, checks, runtime_report=report, external_report=report)

def _generic_report_component(key: str, report_path: Path | str | None) -> DomainDocument:
    checks: list[DomainDocument] = []
    fingerprint: object = {"component_key": key, "zip_sha256": None, "zip_size_bytes": None, "manifest_hash": None, "verification_report_hash": None, "verification_status": None, "runtime_status": None, "runtime_manifest_hash": None, "runtime_failed_count": 0, "runtime_blockers": []}
    if not report_path:
        checks.append(_check(f"ucc_{key}_report_required", False, f"{key} verification report is required."))
        return _component_finish(key, fingerprint, checks)
    try:
        report = read_json(Path(report_path))
    except Exception as exc:
        checks.append(_check(f"ucc_{key}_report_readable", False, f"{key} verification report is readable.", {"error": sanitize_sensitive_text(str(exc))}))
        return _component_finish(key, fingerprint, checks)
    blockers = [str(item) for item in report.get("blockers", [])]
    status = str(report.get("status") or "unknown")
    fingerprint.update({"verification_report_hash": _report_integrity_hash(report), "verification_status": status, "runtime_status": status, "manifest_hash": _report_manifest_hash(report), "runtime_manifest_hash": _report_manifest_hash(report), "runtime_failed_count": len(blockers), "runtime_blockers": blockers})
    if report.get("integrity_hash"):
        checks.append(_check(f"ucc_{key}_report_integrity", _report_integrity_ok(report), f"{key} verification report integrity hash is valid."))
    checks.append(_check(f"ucc_{key}_status", status == "passed", f"{key} verification status is passed.", {"status": status}))
    return _component_finish(key, fingerprint, checks, runtime_report=report, external_report=report)

def _component_finish(key: str, fingerprint: DomainDocument, checks: list[DomainDocument], *, runtime_report: DomainDocument | None = None, external_report: DomainDocument | None = None) -> DomainDocument:
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    public_fingerprint = _public_fingerprint(fingerprint)
    public_fingerprint["integrity_hash"] = _integrity_hash(public_fingerprint)
    result = {
        "component_key": key,
        "status": "passed" if not blockers else "failed",
        "readiness": "ready" if not blockers else _readiness_from_checks(checks),
        "fingerprint": public_fingerprint,
        "checks": checks,
        "blockers": blockers,
        "runtime_report": _public_report(runtime_report or {}),
        "external_report": _public_report(external_report or {}),
    }
    result["integrity_hash"] = _integrity_hash(result)
    return result

def _external_component_checks(key: str, fingerprint: DomainDocument, *, external: dict[str, DomainDocument], audio_evidence: DomainDocument, trust_evidence: DomainDocument, public_trust_evidence: DomainDocument, require_component: bool) -> list[DomainDocument]:
    if key in {"distribution", "submission"}:
        return _external_multi_component_checks(key, fingerprint, external=external, require_component=require_component)
    ext = external.get(key, {})
    if not require_component and not any(ext.values()):
        return []
    runtime = verify_unified_command_center_component(
        key,
        zip_path=ext.get("zip"),
        verification_report_path=ext.get("verification_report"),
        report_path=ext.get("report"),
        audio_evidence=audio_evidence,
        trust_evidence=trust_evidence,
        public_trust_evidence=public_trust_evidence,
    )
    current = _as_document(runtime.get("fingerprint"))
    return list(runtime.get("checks") or []) + [
        _check(
            f"ucc_{key}_fingerprint_binding",
            (
                fingerprint.get("zip_sha256") == current.get("zip_sha256")
                and fingerprint.get("zip_size_bytes") == current.get("zip_size_bytes")
                and fingerprint.get("manifest_hash") == current.get("manifest_hash")
                and fingerprint.get("verification_report_hash") == current.get("verification_report_hash")
                and fingerprint.get("verification_status") == current.get("verification_status")
                and fingerprint.get("runtime_status") == current.get("runtime_status")
                and fingerprint.get("runtime_manifest_hash") == current.get("runtime_manifest_hash")
                and int(fingerprint.get("runtime_failed_count") or 0) == int(current.get("runtime_failed_count") or 0)
                and sorted(str(item) for item in fingerprint.get("runtime_blockers", []) if str(item)) == sorted(str(item) for item in current.get("runtime_blockers", []) if str(item))
            ),
            f"{key} fingerprint matches current external evidence.",
            {"expected": current},
        )
    ]

def _external_multi_component_checks(key: str, fingerprint: DomainDocument, *, external: dict[str, DomainDocument], require_component: bool) -> list[DomainDocument]:
    ext = external.get(key, {})
    zip_paths = [Path(item) for item in ext.get("zips", []) if item]
    report_paths = [Path(item) for item in ext.get("verification_reports", []) if item]
    checks: list[DomainDocument] = []
    if require_component and (not zip_paths or not report_paths):
        checks.append(_check(f"ucc_{key}_external_required", False, f"{key} external ZIP and verification report lists are required."))
        return checks
    if not require_component and not zip_paths and not report_paths:
        return checks
    checks.append(_check(f"ucc_{key}_external_pair_count", len(zip_paths) == len(report_paths), f"{key} external ZIP/report counts match.", {"zip_count": len(zip_paths), "report_count": len(report_paths)}))
    if len(zip_paths) != len(report_paths):
        return checks
    runtime_items: list[DomainDocument] = []
    for index, (zip_path, report_path) in enumerate(zip(zip_paths, report_paths), start=1):
        runtime = verify_unified_command_center_component(key, zip_path=zip_path, verification_report_path=report_path)
        current = _as_document(runtime.get("fingerprint"))
        component_id = _component_id_from_report(key, current.get("external_report") or {}, index)
        # current may not include public reports; fall back to runtime report embedded by component result.
        external_report = _as_document(runtime.get("external_report"))
        runtime_report = _as_document(runtime.get("runtime_report"))
        component_id = _component_id_from_report(key, external_report or runtime_report, index)
        item = {
            "component_id": component_id,
            "zip_sha256": current.get("zip_sha256"),
            "zip_size_bytes": current.get("zip_size_bytes"),
            "manifest_hash": current.get("manifest_hash"),
            "verification_report_hash": current.get("verification_report_hash"),
            "verification_status": current.get("verification_status"),
            "runtime_status": current.get("runtime_status"),
            "runtime_manifest_hash": current.get("runtime_manifest_hash"),
            "runtime_failed_count": current.get("runtime_failed_count"),
            "runtime_blockers": current.get("runtime_blockers", []),
        }
        runtime_items.append(item)
        checks.extend(list(runtime.get("checks") or []))
    expected_items = _fingerprint_items(fingerprint)
    checks.append(_check(f"ucc_{key}_fingerprint_binding", _semantic_hash(expected_items) == _semantic_hash(runtime_items), f"{key} multi-instance fingerprints match current external evidence.", {"expected": expected_items, "current": runtime_items}))
    return checks

def _document_binding_checks(manifest: DomainDocument, source: DomainDocument, report: DomainDocument, graph: DomainDocument, inventory: DomainDocument, readiness: DomainDocument, gap_plan: DomainDocument, runbook: DomainDocument, runbook_result: DomainDocument, verification_index: DomainDocument, fingerprints: dict[str, DomainDocument], *, require_ready: bool) -> list[DomainDocument]:
    source_hash = report.get("source_hash")
    doc_hashes = _as_document(report.get("document_hashes"))
    checks = [
        _check("ucc_source_hash_binding", bool(source_hash) and source.get("source_hash") == source_hash and graph.get("source_hash") == source_hash and inventory.get("source_hash") == source_hash and readiness.get("source_hash") == source_hash and gap_plan.get("source_hash") == source_hash and runbook.get("source_hash") == source_hash and runbook_result.get("source_hash") == source_hash, "All documents bind the same source hash."),
        _check("ucc_report_document_hashes", doc_hashes.get("source") == source.get("integrity_hash") and doc_hashes.get("evidence_graph") == graph.get("integrity_hash") and doc_hashes.get("evidence_inventory") == inventory.get("integrity_hash") and doc_hashes.get("readiness_matrix") == readiness.get("integrity_hash") and doc_hashes.get("gap_plan") == gap_plan.get("integrity_hash") and doc_hashes.get("safe_runbook") == runbook.get("integrity_hash") and doc_hashes.get("runbook_result") == runbook_result.get("integrity_hash") and doc_hashes.get("verification_index") == verification_index.get("integrity_hash"), "Report binds all Unified Command Center documents."),
        _check("ucc_manifest_document_hashes", manifest.get("report_hash") == report.get("integrity_hash") and manifest.get("source_hash") == source_hash and (manifest.get("sidecars") or {}).get("evidence_graph_hash") == graph.get("integrity_hash") and (manifest.get("sidecars") or {}).get("inventory_hash") == inventory.get("integrity_hash") and (manifest.get("sidecars") or {}).get("readiness_hash") == readiness.get("integrity_hash") and (manifest.get("sidecars") or {}).get("gap_plan_hash") == gap_plan.get("integrity_hash") and (manifest.get("sidecars") or {}).get("runbook_hash") == runbook.get("integrity_hash"), "Manifest binds all Unified documents."),
    ]
    components = {str(row.get("component_key")): row for row in inventory.get("components", []) if isinstance(row, dict)}
    graph_nodes = {str(row.get("node_id")): row for row in graph.get("nodes", []) if isinstance(row, dict)}
    for key in COMPONENT_KEYS:
        component = components.get(key, {})
        checks.append(_check(f"ucc_{key}_inventory_fingerprint_binding", _semantic_hash(component.get("fingerprint") or {}) == _semantic_hash(fingerprints[key]), f"{key} inventory fingerprint matches sidecar."))
        node = graph_nodes.get(str(component.get("node_id") or ""))
        checks.append(_check(f"ucc_{key}_graph_inventory_binding", bool(node) and _as_document(node).get("readiness") == component.get("readiness") and _semantic_hash(_as_document(node).get("fingerprint") or {}) == _semantic_hash(component.get("fingerprint") or {}), f"{key} graph node matches inventory."))
    required_blocked = [row.get("component_key") for row in inventory.get("components", []) if isinstance(row, dict) and row.get("required") and row.get("readiness") != "ready"]
    gap_component_keys = sorted(str(row.get("component_key")) for row in gap_plan.get("items", []) if isinstance(row, dict))
    checks.append(_check("ucc_readiness_gap_semantics", sorted(str(item) for item in required_blocked) == gap_component_keys, "Gap plan matches blocked required inventory components.", {"blocked": required_blocked, "gaps": gap_component_keys}))
    overall_ready = not required_blocked and readiness.get("overall_status") == "ready" and report.get("status") == "ready"
    if require_ready:
        checks.append(_check("ucc_require_ready", overall_ready, "Unified Command Center is ready.", {"blocked": required_blocked}))
    return checks

def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, names: set[str]) -> list[DomainDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective = names - {"manifest.json"}
    expected = REQUIRED_ENTRIES - {"manifest.json"}
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        data = archive.read(path)
        info = archive.getinfo(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("ucc_manifest_integrity_hash", _integrity_ok(manifest), "Manifest integrity hash is valid."),
        _check("ucc_manifest_declares_files", declared == effective, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective), "undeclared": sorted(effective - declared)}),
        _check("ucc_manifest_fixed_files", declared == expected, "Manifest files match fixed Unified Command Center structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
        _check("ucc_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
        _check("ucc_manifest_zip_entries_reference_only", True, "manifest.zip.entries is not used as an allow-list."),
    ]

def _finish(checks: list[DomainDocument], summary: DomainDocument, *extra: DomainDocument) -> DomainDocument:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_SCHEMA_VERSION,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {**summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report

def _check(check_id: str, passed: bool, message: str, details: DomainDocument | None = None, *, blocking: bool = True) -> DomainDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}

def _external_paths(**kwargs: object) -> dict[str, DomainDocument]:
    return {
        "audio-command-center": {"zip": kwargs.get("release_audio_command_center_zip_path"), "verification_report": kwargs.get("release_audio_command_center_verification_report_path")},
        "trust-operations-hub": {"zip": kwargs.get("trust_operations_hub_zip_path"), "verification_report": kwargs.get("trust_operations_hub_verification_report_path")},
        "public-trust-center": {"zip": kwargs.get("public_trust_center_zip_path"), "verification_report": kwargs.get("public_trust_center_verification_report_path")},
        "maintenance": {"zip": kwargs.get("maintenance_backup_zip_path"), "verification_report": kwargs.get("maintenance_backup_verification_report_path")},
        "ga-readiness": {"report": kwargs.get("ga_readiness_report_path"), "verification_report": kwargs.get("ga_readiness_verification_report_path")},
        "release-check": {"report": kwargs.get("release_check_report_path")},
        "release": {"zip": kwargs.get("release_zip_path"), "verification_report": kwargs.get("release_verification_report_path")},
        "distribution": {"zips": _path_list(kwargs.get("distribution_zip_paths")), "verification_reports": _path_list(kwargs.get("distribution_verification_report_paths"))},
        "submission": {"zips": _path_list(kwargs.get("submission_zip_paths")), "verification_reports": _path_list(kwargs.get("submission_verification_report_paths"))},
        "operations": {"zip": kwargs.get("release_operations_zip_path"), "verification_report": kwargs.get("release_operations_verification_report_path")},
    }

def _public_report(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    public = {
        "package_type": report.get("package_type"),
        "status": report.get("status"),
        "zip_sha256": report.get("zip_sha256") or summary.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes") or summary.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash") or summary.get("manifest_hash"),
        "blockers": report.get("blockers", []),
        "summary": {key: value for key, value in summary.items() if key not in {"zip_path", "path"}},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    data = json.loads(archive.read(name).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data

def _component_status(inventory: DomainDocument, key: str) -> str:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return str(row.get("readiness") or row.get("status") or "")
    return ""

def _component_required(inventory: DomainDocument, key: str) -> bool:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return bool(row.get("required"))
    return False

def _component_forced(
    key: str,
    *,
    require_audio_ready: bool,
    require_trust_ready: bool,
    require_public_trust_ready: bool,
    require_release_ready: bool,
    require_distribution_ready: bool,
    require_submission_ready: bool,
    require_operations_ready: bool,
    require_maintenance_ready: bool,
    require_ga_ready: bool,
) -> bool:
    return (
        (key == "audio-command-center" and require_audio_ready)
        or (key == "trust-operations-hub" and require_trust_ready)
        or (key == "public-trust-center" and require_public_trust_ready)
        or (key == "release" and require_release_ready)
        or (key == "distribution" and require_distribution_ready)
        or (key == "submission" and require_submission_ready)
        or (key == "operations" and require_operations_ready)
        or (key == "maintenance" and require_maintenance_ready)
        or (key == "ga-readiness" and require_ga_ready)
    )

def _domain_requirement_check(readiness: DomainDocument, domain: str, check_id: str) -> DomainDocument:
    for row in readiness.get("domains", []):
        if isinstance(row, dict) and row.get("domain") == domain:
            return _check(check_id, row.get("status") == "ready", f"{domain} readiness is ready.", {"status": row.get("status")})
    return _check(check_id, False, f"{domain} readiness row is missing.")

def _readiness_from_checks(checks: list[DomainDocument]) -> str:
    failed = [str(check.get("check_id") or "") for check in checks if check.get("status") == "failed"]
    if any("required" in item or "exists" in item for item in failed):
        return "missing"
    if any("integrity" in item or "external_status" in item for item in failed):
        return "verification_failed"
    if any("binding" in item for item in failed):
        return "stale"
    if any("runtime_status" in item for item in failed):
        return "runtime_failed"
    return "blocked"

def _path_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item]
    return [value] if value else []

def _report_integrity_hash(report: DomainDocument) -> str:
    return str(report.get("integrity_hash") or stable_hash(report))

def _package_type_matches(key: str, report: DomainDocument) -> bool:
    expected = EXPECTED_VERIFICATION_PACKAGE_TYPES.get(key)
    if not expected:
        return True
    return str(report.get("package_type") or "") in expected

def _report_integrity_ok(report: DomainDocument) -> bool:
    if not report:
        return False
    if report.get("integrity_hash"):
        return report.get("integrity_hash") == _integrity_hash(report)
    return True

def _report_zip_sha256(report: DomainDocument) -> str | None:
    summary = _as_document(report.get("summary"))
    input_doc = _as_document(report.get("input"))
    return report.get("zip_sha256") or summary.get("zip_sha256") or input_doc.get("sha256")

def _report_zip_size(report: DomainDocument) -> int | None:
    summary = _as_document(report.get("summary"))
    input_doc = _as_document(report.get("input"))
    value = report.get("zip_size_bytes") or summary.get("zip_size_bytes") or input_doc.get("size_bytes")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def _report_manifest_hash(report: DomainDocument) -> str | None:
    summary = _as_document(report.get("summary"))
    return report.get("manifest_hash") or summary.get("manifest_hash")

def _manifest_binding_matches(report: DomainDocument, runtime_manifest_hash: str | None) -> bool:
    expected = _report_manifest_hash(report)
    if expected:
        return expected == runtime_manifest_hash
    # Older verifiers did not persist manifest_hash. In that case ZIP sha/runtime status
    # are still checked, and manifest binding is not claimed as independent evidence.
    return True

def _component_id_from_report(key: str, report: DomainDocument, index: int) -> str:
    summary = _as_document(report.get("summary"))
    prefix = {"distribution": "distribution", "submission": "submission"}.get(key, key)
    for field in ("release_id", "target_id", "submission_id", "package_id"):
        value = report.get(field) or summary.get(field)
        if value:
            return f"{prefix}:{_safe_component_id(str(value))}"
    return f"{prefix}:{index:03d}"

def _safe_component_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip()).strip("-") or "unknown"

def _fingerprint_items(fingerprint: DomainDocument) -> list[DomainDocument]:
    items = _as_list(fingerprint.get("items"))
    return sorted([_public_fingerprint(item) for item in items if isinstance(item, dict)], key=lambda item: str(item.get("component_id") or ""))

def _public_fingerprint(value: DomainDocument) -> DomainDocument:
    return {key: val for key, val in value.items() if not str(key).startswith("_")}

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _semantic_hash(value: object) -> str:
    def scrub(item: object) -> object:
        if isinstance(item, dict):
            return {key: scrub(val) for key, val in sorted(item.items()) if key not in {"created_at", "updated_at", "generated_at", "integrity_hash"}}
        if isinstance(item, list):
            return [scrub(val) for val in item]
        return item

    return stable_hash(scrub(value))

def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    path = Path(name)
    if path.is_absolute():
        return False
    parts = name.split("/")
    return all(part and part not in {".", ".."} and ":" not in part for part in parts)

def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> DomainDocument:
    offenders: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            offenders.append(name)
    return _check("ucc_redaction_scan", not offenders, "Package contains no obvious secrets or local workspace paths.", {"offenders": offenders})

def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
