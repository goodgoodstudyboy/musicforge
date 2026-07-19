# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path
import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_archive_verifier import UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_archive_package as verify_unified_command_center_archive_package
from song_agent.domains.program.unified_command_center_continuous_review_verifier import UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_continuous_review_package as verify_unified_command_center_continuous_review_package
from song_agent.domains.program.unified_command_center_drift_response_verifier import UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_drift_response_package as verify_unified_command_center_drift_response_package
from song_agent.domains.program.unified_command_center_handoff_verifier import UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package
from song_agent.domains.program.unified_command_center_verifier import UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_package as verify_unified_command_center_package

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
value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global check, key, value
    check = namespace.get('check', check)
    key = namespace.get('key', key)
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_evidence_review_acceptance_verification"
UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION = 1
REQUIRED_ENTRIES = {
    "manifest.json",
    "review-source.json",
    "evidence-index.json",
    "external-proof-index.json",
    "replay-plan.json",
    "replay-result.json",
    "evidence-narrative.json",
    "manual-checklist.json",
    "reviewer-guide.md",
    "README.txt",
    "verification-summaries/ucc.json",
    "verification-summaries/ucc-archive.json",
    "verification-summaries/ucc-handoff.json",
    "verification-summaries/continuous-review.json",
    "verification-summaries/drift-response.json",
    "verification-summaries/ga-readiness.json",
    "verification-summaries/release-check.json",
    "proof-summaries/signoff-binding-summary.json",
    "proof-summaries/change-request-binding-report.json",
}
ACCEPTANCE_REQUIRED_ENTRIES = {
    "manifest.json",
    "acceptance-report.json",
    "original-response-public.json",
    "response-verification-summary.json",
    "original-response-binding-summary.json",
    "README.txt",
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




def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> DomainDocument:
    hits: list[str] = []
    for name in names:
        try:
            data = archive.read(name)
        except (KeyError, OSError):
            continue
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                hits.append(name)
                break
    return _check("ucc_review_redaction_scan", not hits, "No sensitive strings appear in the package.", {"entries": sorted(set(hits))})

def _finish(
    checks: list[DomainDocument],
    summary: DomainDocument,
    extra: DomainDocument | None = None,
    *,
    package_type: str = UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE,
) -> DomainDocument:
    if extra is not None:
        checks.append(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") != "blocking"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "package_type": package_type,
        "schema_version": UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION,
        "status": status,
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report

def _check(check_id: str, passed: bool, message: str, detail: DomainDocument | None = None, *, severity: str = "blocking") -> DomainDocument:
    return {
        "check_id": check_id,
        "status": "passed" if passed else "failed",
        "severity": severity,
        "message": message,
        "detail": detail or {},
    }

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    return json.loads(archive.read(name).decode("utf-8"))

def _read_json_file(path: Path | str) -> DomainDocument:
    return read_json(Path(path))

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)

def _integrity_or_stable(payload: DomainDocument) -> str:
    return str(payload.get("integrity_hash") or stable_hash(payload))

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

def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()

def _zip_manifest_hash(zip_path: Path | str | None) -> str | None:
    if not zip_path:
        return None
    try:
        with zipfile.ZipFile(zip_path) as archive:
            return _read_json_entry(archive, "manifest.json").get("integrity_hash")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return None

def _is_safe_entry(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized != name:
        return False
    if not normalized or normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        return False
    if re.match(r"^[A-Za-z]:", normalized):
        return False
    lower = normalized.lower()
    if lower.startswith(".musicforge/") or "/.musicforge/" in lower:
        return False
    return True
