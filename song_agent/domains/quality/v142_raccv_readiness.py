# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.quality.release_audio_baseline_governance_verifier import verify_release_audio_baseline_registry_package as verify_release_audio_baseline_registry_package
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_quality_action_signoff_verifier import verify_release_audio_quality_action_queue_signoff_archive_package as verify_release_audio_quality_action_queue_signoff_archive_package
from song_agent.domains.quality.release_audio_quality_actions_verifier import verify_release_audio_quality_action_queue_package as verify_release_audio_quality_action_queue_package
from song_agent.domains.quality.release_audio_quality_observatory_verifier import verify_release_audio_quality_observatory_package as verify_release_audio_quality_observatory_package
from song_agent.domains.quality.release_audio_regression_response_verifier import verify_release_audio_regression_response_package as verify_release_audio_regression_response_package
from song_agent.domains.quality.release_audio_regression_verifier import verify_release_audio_regression_package as verify_release_audio_regression_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package as verify_release_audio_timeline_package
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash

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
part = _make_deferred_global('part')
pattern = _make_deferred_global('pattern')
val = _make_deferred_global('val')

def bind_globals(namespace: dict[str, object]) -> None:
    global check, part, pattern, val
    check = namespace.get('check', check)
    part = namespace.get('part', part)
    pattern = namespace.get('pattern', pattern)
    val = namespace.get('val', val)
    _bind_deferred_defaults(namespace)


RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE = "release_audio_command_center"
RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE = "release_audio_command_center_verification"
RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION = 1
COMPONENT_KEYS = (
    "certification",
    "timeline",
    "regression",
    "baseline_governance",
    "regression_response",
    "observatory",
    "action_queue",
    "action_queue_signoff",
)
REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "command-center.json",
    "command-center-report.json",
    "evidence-inventory.json",
    "readiness-matrix.json",
    "gap-plan.json",
    "runbook.json",
    "runbook-results.json",
    *{f"evidence-fingerprints/{key}.json" for key in COMPONENT_KEYS},
    *{f"verification-summaries/{key}-verification.json" for key in COMPONENT_KEYS},
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




def _manifest_checks(archive: zipfile.ZipFile, manifest: DomainDocument, names: set[str]) -> list[DomainDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    mismatches = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = archive.getinfo(path)
        data = archive.read(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("release_audio_command_center_manifest_integrity_hash", _integrity_ok(manifest), "Manifest integrity hash is valid."),
        _check("release_audio_command_center_manifest_declares_files", declared == effective_names, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective_names), "undeclared": sorted(effective_names - declared)}),
        _check("release_audio_command_center_manifest_fixed_files", declared == expected_files, "Manifest files match fixed Command Center structure.", {"extra": sorted(declared - expected_files), "missing": sorted(expected_files - declared)}),
        _check("release_audio_command_center_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
        _check("release_audio_command_center_manifest_zip_entries_untrusted", True, "manifest.zip.entries is not used as an allow-list."),
    ]

def _finish(checks: list[DomainDocument], summary: DomainDocument, *extra: DomainDocument) -> DomainDocument:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    public_summary = {key: value for key, value in summary.items() if key != "zip_path"}
    report = {
        "package_type": RELEASE_AUDIO_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {**public_summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
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

def _component_required(inventory: DomainDocument, key: str) -> bool:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return bool(row.get("required"))
    return False

def _component_status(inventory: DomainDocument, key: str) -> str:
    for row in inventory.get("components", []):
        if isinstance(row, dict) and row.get("component_key") == key:
            return str(row.get("status") or "")
    return ""

def _public_verification_summary(component_key: str, report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    public = {
        "component_key": component_key,
        "package_type": report.get("package_type"),
        "status": report.get("status"),
        "zip_sha256": report.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash"),
        "original_integrity_hash": report.get("integrity_hash"),
        "summary": {key: value for key, value in summary.items() if key != "zip_path"},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return public

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    data = json.loads(archive.read(name).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data

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
    return _check("release_audio_command_center_redaction", not offenders, "Package contains no obvious secrets or local workspace paths.", {"offenders": offenders})

def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()

def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
