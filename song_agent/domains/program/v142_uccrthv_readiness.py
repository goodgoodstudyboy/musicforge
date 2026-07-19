# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.persistence.file_artifacts import read_json_document as read_json, write_json_atomic as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package as verify_unified_command_center_release_train_change_control_package
from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import verify_unified_command_center_release_train_lifecycle_package as verify_unified_command_center_release_train_lifecycle_package
from song_agent.domains.program.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package as verify_unified_command_center_release_train_package

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

check = _make_deferred_global('check')
key = _make_deferred_global('key')
line = _make_deferred_global('line')

def bind_globals(namespace: dict[str, object]) -> None:
    global check, key, line
    check = namespace.get('check', check)
    key = namespace.get('key', key)
    line = namespace.get('line', line)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_handoff"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_release_train_handoff_verification"
UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION = 1
BASE_REQUIRED_ENTRIES = {
    "manifest.json",
    "file-index.json",
    "README.txt",
    "handoff-report.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "recipient-guide.md",
    "gap-plan.json",
    "external-evidence-manifest.json",
    "response-summary.json",
    "accepted-evidence-summary.json",
    "handoff-history.jsonl",
}
SIGNED_ENTRIES = {"handoff-signoff.json", "handoff-signoff-binding-summary.json"}
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




def _document_binding_checks(manifest: DomainDocument, file_index: DomainDocument, report: DomainDocument, inventory: DomainDocument, readiness: DomainDocument, gap_plan: DomainDocument, external_manifest: DomainDocument, response_summary: DomainDocument, accepted_summary: DomainDocument, signoff: DomainDocument, binding: DomainDocument) -> list[DomainDocument]:
    source_hash = report.get("source_hash")
    manifest_source = _as_document(manifest.get("source"))
    checks = [
        _check("ucc_train_handoff_source_hash_consistent", manifest.get("source_hash") == source_hash == inventory.get("source_hash") == readiness.get("source_hash"), "Source hash is consistent across handoff documents."),
        _check("ucc_train_handoff_manifest_file_index_binding", manifest_source.get("file_index_hash") == file_index.get("integrity_hash"), "Manifest binds file index."),
        _check("ucc_train_handoff_manifest_report_binding", manifest_source.get("handoff_report_hash") == report.get("integrity_hash"), "Manifest binds handoff report."),
        _check("ucc_train_handoff_manifest_inventory_binding", manifest_source.get("evidence_inventory_hash") == inventory.get("integrity_hash"), "Manifest binds evidence inventory."),
        _check("ucc_train_handoff_manifest_readiness_binding", manifest_source.get("readiness_matrix_hash") == readiness.get("integrity_hash"), "Manifest binds readiness matrix."),
        _check("ucc_train_handoff_manifest_gap_plan_binding", manifest_source.get("gap_plan_hash") == gap_plan.get("integrity_hash"), "Manifest binds gap plan."),
        _check("ucc_train_handoff_manifest_external_manifest_binding", manifest_source.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash"), "Manifest binds external evidence manifest."),
        _check("ucc_train_handoff_manifest_response_summary_binding", manifest_source.get("response_summary_hash") == response_summary.get("integrity_hash"), "Manifest binds response summary."),
        _check("ucc_train_handoff_manifest_accepted_summary_binding", manifest_source.get("accepted_evidence_summary_hash") == accepted_summary.get("integrity_hash"), "Manifest binds accepted evidence summary."),
    ]
    if signoff:
        checks.append(_check("ucc_train_handoff_manifest_signoff_binding", manifest_source.get("handoff_signoff_hash") == signoff.get("integrity_hash"), "Manifest binds handoff signoff."))
    if binding:
        checks.append(_check("ucc_train_handoff_manifest_signoff_sidecar_binding", manifest_source.get("handoff_signoff_binding_hash") == binding.get("integrity_hash"), "Manifest binds signoff binding sidecar."))
    return checks

def _signoff_binding_checks(binding: DomainDocument, signoff: DomainDocument, history: list[DomainDocument], report: DomainDocument, inventory: DomainDocument, readiness: DomainDocument, external_manifest: DomainDocument, accepted_summary: DomainDocument, *, require: bool) -> list[DomainDocument]:
    if not signoff and not binding:
        return [_check("ucc_train_handoff_signoff_required", not require, "Handoff signoff is present when required.")]
    checks = [_check("ucc_train_handoff_signoff_binding_present", bool(binding), "Signoff binding summary is present.")]
    latest_event = history[-1] if history else {}
    checks.extend(
        [
            _check("ucc_train_handoff_signoff_hash", binding.get("signoff_hash") == signoff.get("integrity_hash"), "Binding signoff hash matches signoff."),
            _check("ucc_train_handoff_signoff_signed_by", binding.get("signed_by") == signoff.get("signed_by"), "Binding signed_by matches signoff."),
            _check("ucc_train_handoff_signoff_role", binding.get("role") == signoff.get("role"), "Binding role matches signoff."),
            _check("ucc_train_handoff_signoff_reason", binding.get("reason") == signoff.get("reason"), "Binding reason matches signoff."),
            _check("ucc_train_handoff_signoff_signed_at", binding.get("signed_at") == signoff.get("signed_at"), "Binding signed_at matches signoff."),
            _check("ucc_train_handoff_signoff_history_event", binding.get("latest_history_event_hash") == latest_event.get("event_hash"), "Binding matches latest history event."),
            _check("ucc_train_handoff_signoff_report_hash", binding.get("handoff_report_hash") == report.get("integrity_hash") == signoff.get("handoff_report_hash"), "Binding report hash matches signoff and report."),
            _check("ucc_train_handoff_signoff_inventory_hash", binding.get("evidence_inventory_hash") == inventory.get("integrity_hash") == signoff.get("evidence_inventory_hash"), "Binding inventory hash matches signoff and inventory."),
            _check("ucc_train_handoff_signoff_readiness_hash", binding.get("readiness_matrix_hash") == readiness.get("integrity_hash") == signoff.get("readiness_matrix_hash"), "Binding readiness hash matches signoff and readiness."),
            _check("ucc_train_handoff_signoff_external_manifest_hash", binding.get("external_evidence_manifest_hash") == external_manifest.get("integrity_hash"), "Binding external evidence manifest hash matches."),
            _check("ucc_train_handoff_signoff_accepted_summary_hash", binding.get("accepted_evidence_summary_hash") == accepted_summary.get("integrity_hash") == signoff.get("accepted_evidence_summary_hash"), "Binding accepted evidence summary hash matches."),
        ]
    )
    return checks

def _external_signoff_binding_checks(path: Path | str | None, binding: DomainDocument, signoff: DomainDocument, history: list[DomainDocument], report: DomainDocument, inventory: DomainDocument, readiness: DomainDocument, external_manifest: DomainDocument, accepted_summary: DomainDocument, *, require: bool) -> list[DomainDocument]:
    if not path:
        if require:
            return [_check("ucc_train_handoff_external_signoff_binding_required", False, "External handoff signoff binding proof is required.")]
        return []
    binding_path = Path(path)
    checks = [_check("ucc_train_handoff_external_signoff_binding_exists", binding_path.exists() and binding_path.is_file(), "External handoff signoff binding proof exists.")]
    if not binding_path.exists() or not binding_path.is_file():
        return checks
    external = read_json(binding_path)
    checks.extend(
        [
            _check("ucc_train_handoff_external_signoff_binding_integrity", _integrity_ok(external), "External handoff signoff binding integrity hash is valid."),
            _check("ucc_train_handoff_external_signoff_binding_hash", external.get("integrity_hash") == binding.get("integrity_hash"), "External handoff signoff binding matches archive binding."),
        ]
    )
    checks.extend(_signoff_binding_checks(external, signoff, history, report, inventory, readiness, external_manifest, accepted_summary, require=require))
    return checks

def _history_checks(history: list[DomainDocument], signoff: DomainDocument) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    previous = ""
    for index, event in enumerate(history):
        payload_hash = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        checks.append(_check(f"ucc_train_handoff_history_{index:03d}_payload_hash", event.get("payload_hash") == payload_hash, "History event payload hash is valid."))
        checks.append(_check(f"ucc_train_handoff_history_{index:03d}_event_hash", event.get("event_hash") == event_hash, "History event hash is valid."))
        checks.append(_check(f"ucc_train_handoff_history_{index:03d}_chain", str(event.get("previous_event_hash") or "") == previous, "History hash chain is contiguous."))
        previous = str(event.get("event_hash") or "")
    if signoff:
        signoff_events = [row for row in history if row.get("event_type") == "release_train_handoff_signoff_created"]
        event = signoff_events[-1] if signoff_events else {}
        checks.extend(
            [
                _check("ucc_train_handoff_history_has_signoff_event", bool(event), "History contains handoff signoff event."),
                _check("ucc_train_handoff_history_signoff_hash", event.get("signoff_hash") == signoff.get("integrity_hash"), "History signoff event hash matches signoff."),
                _check("ucc_train_handoff_history_signed_by", event.get("signed_by") == signoff.get("signed_by"), "History signoff event signer matches signoff."),
            ]
        )
    return checks

def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, names: set[str], expected_entries: set[str]) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    paths = {str(row.get("path") or "") for row in files}
    expected_file_paths = expected_entries - {"manifest.json"}
    checks.append(_check("ucc_train_handoff_manifest_files_exact", paths == expected_file_paths, "Manifest files match fixed allow-list.", {"missing": sorted(expected_file_paths - paths), "extra": sorted(paths - expected_file_paths)}))
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in names:
            checks.append(_check(f"ucc_train_handoff_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP.", {"path": rel}))
            continue
        data = archive.read(rel)
        checks.append(_check(f"ucc_train_handoff_manifest_file_{_safe_check_key(rel)}_hash", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry.", {"path": rel}))
    return checks

def _file_index_checks(file_index: DomainDocument, expected_file_paths: set[str]) -> list[DomainDocument]:
    rows = [row for row in file_index.get("files", []) if isinstance(row, dict)]
    paths = {str(row.get("path") or "") for row in rows}
    return [
        _check("ucc_train_handoff_file_index_package_type", file_index.get("package_type") == "musicforge_release_train_handoff_file_index", "File index package type is valid."),
        _check("ucc_train_handoff_file_index_files_exact", paths == expected_file_paths, "File index files match fixed allow-list.", {"missing": sorted(expected_file_paths - paths), "extra": sorted(paths - expected_file_paths)}),
    ]

def _finish(checks: list[DomainDocument], summary: DomainDocument, first_check: DomainDocument | None = None) -> DomainDocument:
    if first_check is not None:
        checks.append(first_check)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") != "blocking"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "schema_version": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE,
        "status": status,
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report

def write_unified_command_center_release_train_handoff_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)

def unified_command_center_release_train_handoff_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1

def _check(check_id: str, passed: bool, message: str, details: DomainDocument | None = None, *, severity: str = "blocking") -> DomainDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message, "details": details or {}}

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    return json.loads(archive.read(name).decode("utf-8"))

def _read_optional_json(path: Path) -> DomainDocument:
    return read_json(path) if path.exists() else {}

def _parse_jsonl(text: str) -> list[DomainDocument]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]

def _integrity_hash(doc: DomainDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})

def _integrity_ok(doc: DomainDocument) -> bool:
    return bool(doc.get("integrity_hash")) and doc.get("integrity_hash") == _integrity_hash(doc)

def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()

def _is_safe_entry(name: str) -> bool:
    if "\\" in name or name.startswith("/") or name.startswith("../") or "/../" in name or name.endswith("/.."):
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    return bool(name) and not Path(name).is_absolute()

def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> DomainDocument:
    offenders = []
    for name in names:
        lowered = name.lower()
        if not lowered.endswith((".json", ".txt", ".md", ".html")):
            continue
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                offenders.append(name)
                break
    return _check("ucc_train_handoff_redaction_scan", not offenders, "Handoff package contains no obvious secrets or local paths.", {"offenders": sorted(set(offenders))})

def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"

def _report_manifest_hash(report: DomainDocument) -> str | None:
    return report.get("manifest_hash") or report.get("summary", {}).get("manifest_hash")
