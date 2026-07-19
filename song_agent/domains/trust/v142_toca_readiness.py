# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_text as _as_text
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_continuous_assurance_contracts import ASSURANCE_ARCHIVE_ENTRIES as ASSURANCE_ARCHIVE_ENTRIES, CORE_EVIDENCE_SPECS as CORE_EVIDENCE_SPECS, TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_ASSURANCE_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION, assurance_hash as assurance_hash, assurance_manifest_hash as assurance_manifest_hash

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

ch = _make_deferred_global('ch')
check = _make_deferred_global('check')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch, check
    ch = namespace.get('ch', ch)
    check = namespace.get('check', check)
    _bind_deferred_defaults(namespace)






class TrustOperationsAssuranceError(ValueError):
    pass

class TrustOperationsAssuranceNotFoundError(TrustOperationsAssuranceError):
    pass

class TrustOperationsAssuranceStateError(TrustOperationsAssuranceError):
    pass

def _default_policy(now: str | None = None) -> DomainDocument:
    now = now or _now()
    policy = {
        "schema_version": TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION,
        "package_type": TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE,
        "policy_id": "default",
        "name": "Default Trust Operations Continuous Assurance Policy",
        "updated_at": now,
        "requirements": {
            "require_hub": True,
            "require_control_signoff": True,
            "require_control": True,
            "require_incident": True,
            "require_knowledge": True,
            "require_delivery_ready": False,
            "require_no_open_blocking_incidents": True,
            "require_no_expired_control_exceptions": True,
            "require_regression_guards": True,
        },
        "freshness": {"max_age_days": 30},
        "scoring": {"base_score": 100, "blocking_penalty": 100, "warning_penalty": 5},
    }
    policy["integrity_hash"] = assurance_hash(policy)
    return policy

def _external_row(evidence_type: str, archive_path: Path | None, report_path: Path | None, manifest_entry: str, *, component_id: str) -> DomainDocument:
    report = _read_json_default(report_path, default={}) if report_path else {}
    manifest = _read_zip_json_optional(archive_path, manifest_entry) if archive_path and manifest_entry else {}
    zip_sha = _sha256(archive_path) if archive_path and archive_path.exists() else report.get("zip_sha256")
    zip_size = os.stat(_fs_path(archive_path)).st_size if archive_path and archive_path.exists() else report.get("zip_size_bytes")
    manifest_hash = manifest.get("integrity_hash") or report.get("manifest_hash")
    status = str(report.get("status") or "missing")
    row = {
        "evidence_type": evidence_type,
        "component_id": component_id,
        "package_type": report.get("package_type"),
        "status": status,
        "zip_sha256": zip_sha,
        "zip_size_bytes": zip_size,
        "manifest_hash": manifest_hash,
        "verification_report_hash": verification_hash(report) if report else None,
        "verification_status": status,
        "source_hash": report.get("source_hash"),
        "summary": _as_document(report.get("summary")),
        "_archive_path": str(archive_path) if archive_path else None,
        "_report_path": str(report_path) if report_path else None,
    }
    if report:
        if report.get("zip_sha256") != zip_sha:
            row["status"] = "failed"
            row["stale_reason"] = "zip_sha256_mismatch"
        if report.get("zip_size_bytes") not in {None, zip_size}:
            row["status"] = "failed"
            row["stale_reason"] = "zip_size_mismatch"
        if report.get("manifest_hash") not in {None, manifest_hash}:
            row["status"] = "failed"
            row["stale_reason"] = "manifest_hash_mismatch"
    return row

def _evidence_row_from_external(row: DomainDocument, *, required: bool) -> DomainDocument:
    return {
        "evidence_id": f"{row.get('evidence_type')}:{row.get('component_id')}",
        "evidence_type": row.get("evidence_type"),
        "component_id": row.get("component_id"),
        "required": required,
        "package_type": row.get("package_type"),
        "status": row.get("status"),
        "zip_sha256": row.get("zip_sha256"),
        "zip_size_bytes": row.get("zip_size_bytes"),
        "manifest_hash": row.get("manifest_hash"),
        "verification_report_hash": row.get("verification_report_hash"),
        "source_hash": row.get("source_hash"),
        "summary": _as_document(row.get("summary")),
    }

def _public_row(row: DomainDocument) -> DomainDocument:
    return {key: value for key, value in row.items() if not str(key).startswith("_")}

def _check(check_id: str, status: str, severity: str, message: str, *, evidence_ref: str | None = None, details: DomainDocument | None = None) -> DomainDocument:
    item: DomainDocument = {"check_id": check_id, "status": status, "severity": severity, "message": message}
    if evidence_ref:
        item["evidence_ref"] = evidence_ref
    if details:
        item["details"] = details
    item["integrity_hash"] = assurance_hash(item)
    return item

def _checks_summary(checks: list[DomainDocument]) -> DomainDocument:
    blocking_failed = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check.get("status") in {"failed", "warning"} and check.get("severity") != "blocking"]
    return {
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check.get("status") == "passed"),
        "blocking_failed_count": len(blocking_failed),
        "warning_count": len(warnings),
        "score": 0 if blocking_failed else max(0, 100 - 5 * len(warnings)),
    }

def _fingerprint_projection(row: DomainDocument) -> DomainDocument:
    return {key: row.get(key) for key in ("package_type", "status", "zip_sha256", "zip_size_bytes", "manifest_hash", "verification_report_hash", "source_hash")}

def _source_paths(payload: DomainDocument) -> DomainDocument:
    paths: DomainDocument = {}
    for spec in CORE_EVIDENCE_SPECS.values():
        archive_key = str(spec["archive_key"])
        report_key = str(spec["report_key"])
        paths[archive_key] = [str(path) for path in _paths(payload.get(archive_key))]
        paths[report_key] = [str(path) for path in _paths(payload.get(report_key))]
    for delivery_spec in DELIVERY_VERIFICATION_COMPONENTS:
        key = str(delivery_spec["payload_keys"])
        singular = str(delivery_spec["payload_key"])
        paths[key] = [str(path) for path in _paths(payload.get(key) or payload.get(singular))]
    return paths

def _verifier_kwargs_from_source_paths(source_paths: DomainDocument) -> DomainDocument:
    kwargs: DomainDocument = {}
    for spec in CORE_EVIDENCE_SPECS.values():
        archive_key = str(spec["archive_key"])
        report_key = str(spec["report_key"])
        kwargs[archive_key] = _first_path(source_paths.get(archive_key))
        kwargs[report_key] = _first_path(source_paths.get(report_key))
    for delivery_spec in DELIVERY_VERIFICATION_COMPONENTS:
        kwargs[str(delivery_spec["payload_keys"])] = _path_list(source_paths.get(str(delivery_spec["payload_keys"])))
    return kwargs

def _delivery_component_id(spec: DomainDocument, report: DomainDocument, index: int) -> str:
    summary = _as_document(report.get("summary"))
    for key in ("release_id", "target_id", "submission_id", "evidence_id", "operations_id", "package_id"):
        value = report.get(key) or summary.get(key)
        if value:
            return f"{spec['component_id_prefix']}:{_safe_id(str(value))}"
    return f"{spec['component_id_prefix']}:{index:03d}"

def _paths(value: object) -> list[Path]:
    if value is None or value == "":
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, (list, tuple)):
        return [Path(item) for item in value if item]
    return []

def _path_list(value: object) -> list[Path]:
    return _paths(value)

def _first_path(value: object) -> Path | None:
    values = _paths(value)
    return values[0] if values else None

def _read_json_required(path: Path, message: str) -> DomainDocument:
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise TrustOperationsAssuranceStateError(message) from exc

def _read_json_default(path: Path | None, *, default: DomainDocument) -> DomainDocument:
    try:
        if path is None or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)

def _read_zip_json_optional(zip_path: Path | None, entry: str) -> DomainDocument:
    if not zip_path:
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}

def _write_json(path: Path, payload: DomainDocument) -> Path:
    return write_json(path, _sanitize(payload))

def _write_internal_json(path: Path, payload: DomainDocument) -> Path:
    return write_json(path, payload)

def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text("MusicForge Trust Operations Continuous Assurance Archive\n\nThis package contains local continuous assurance evidence and external verification bindings.\n", encoding="utf-8")

def _file_record(root: Path, path: Path) -> DomainDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}

def _walk_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]

def _write_zip(zip_path: Path, root: Path) -> None:
    _mkdir(zip_path.parent)
    with zipfile.ZipFile(_fs_path(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)

def _sha256(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        digest = hashlib.sha256()
        with open(_fs_path(path), "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None

def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"

def _append_jsonl(path: Path, payload: DomainDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""

def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"

def _sanitize(value: object) -> DomainDocument:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS)

def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
