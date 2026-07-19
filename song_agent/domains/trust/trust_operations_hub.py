# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication import publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub_contracts import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, HUB_EXPORT_ENTRIES as HUB_EXPORT_ENTRIES, TRUST_OPERATIONS_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_HUB_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_PACKAGE_TYPE, TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_HUB_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_SCHEMA_VERSION as TRUST_OPERATIONS_SCHEMA_VERSION, hub_hash as hub_hash, hub_manifest_hash as hub_manifest_hash
from song_agent.domains.trust.v142_toh_readiness import TrustOperationsHubStoreReadinessMixin
from song_agent.domains.trust import v142_toh_readiness as _v142_toh_readiness
from song_agent.domains.trust.v142_toh_evidence import TrustOperationsHubStoreEvidenceMixin
from song_agent.domains.trust import v142_toh_evidence as _v142_toh_evidence





TRUST_OPERATIONS_HUB_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_report"
TRUST_OPERATIONS_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_readiness_matrix"
TRUST_OPERATIONS_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_blocker_register"
TRUST_OPERATIONS_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_manual_action_queue"
TRUST_OPERATIONS_EVIDENCE_BINDING_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_evidence_binding_index"
TRUST_OPERATIONS_VERIFICATION_SUMMARY_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_verification_summary_index"
TRUST_OPERATIONS_SOURCE_STATE_PACKAGE_TYPE = "musicforge_trust_operations_source_state"
TRUST_OPERATIONS_DELIVERY_EVIDENCE_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_evidence_index"
TRUST_OPERATIONS_DELIVERY_READINESS_MATRIX_PACKAGE_TYPE = "musicforge_trust_operations_delivery_readiness_matrix"
TRUST_OPERATIONS_DELIVERY_BLOCKER_REGISTER_PACKAGE_TYPE = "musicforge_trust_operations_delivery_blocker_register"
TRUST_OPERATIONS_DELIVERY_MANUAL_ACTION_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_delivery_manual_action_queue"

TRUST_OPERATIONS_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_hub_change_request"
TRUST_OPERATIONS_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}







class TrustOperationsHubError(ValueError):
    pass


class TrustOperationsHubNotFoundError(TrustOperationsHubError):
    pass


class TrustOperationsHubStateError(TrustOperationsHubError):
    pass


class TrustOperationsHubStore(TrustOperationsHubStoreReadinessMixin, TrustOperationsHubStoreEvidenceMixin):
    def __init__(self, root: Path | str = Path(".musicforge") / "trust-operations") -> None:
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
































































def _default_requirements() -> dict[str, bool]:
    return {
        "require_public_trust_center_verified": True,
        "require_publication_current": True,
        "require_publication_monitoring_clean": True,
        "require_no_open_critical_incidents": True,
        "require_release_verified": False,
        "require_distribution_verified": False,
        "require_submission_verified": False,
        "require_submission_evidence_verified": False,
        "require_release_operations_verified": False,
    }


def _scope(payload: ImplementationDocument) -> ImplementationDocument:
    return {"release_ids": _list(payload.get("release_ids") or payload.get("release_id")), "project_ids": _list(payload.get("project_ids") or payload.get("project_id")), "public_trust_center_ids": _list(payload.get("public_trust_center_ids") or payload.get("public_trust_center_id") or "ptc-default"), "publication_channel_ids": _list(payload.get("publication_channel_ids") or payload.get("publication_channel_id") or "public-release")}


def _source_paths(payload: ImplementationDocument) -> ImplementationDocument:
    paths = {
        "publication_channel_state_paths": [str(path) for path in _paths(payload.get("publication_channel_state_paths") or payload.get("publication_channel_state_path"))],
        "public_trust_center_verification_paths": [str(path) for path in _paths(payload.get("public_trust_center_verification_paths") or payload.get("public_trust_center_verification_path"))],
        "publication_monitoring_verification_paths": [str(path) for path in _paths(payload.get("publication_monitoring_verification_paths") or payload.get("publication_monitoring_verification_path"))],
    }
    for spec in DELIVERY_VERIFICATION_COMPONENTS:
        paths[str(spec["payload_keys"])] = [str(path) for path in _paths(payload.get(spec["payload_keys"]) or payload.get(spec["payload_key"]))]
    return paths


def _evidence_from_verification(evidence_id: str, component_type: str, report: ImplementationDocument, path: Path) -> ImplementationDocument:
    return {"evidence_id": evidence_id, "component_type": component_type, "path_hint": str(path.name), "package_type": report.get("package_type"), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash"), "verification_report_hash": verification_hash(report), "source_hash": report.get("source_hash"), "status": report.get("status") or "missing", "summary": _as_document(report.get("summary")), "current_state_refs": {"publication_channel_state_hash": report.get("channel_state_hash")}}


def _delivery_component_id(spec: dict[str, str], report: ImplementationDocument, index: int) -> str:
    summary = _as_document(report.get("summary"))
    for key in ("release_id", "target_id", "submission_id", "evidence_id", "operations_id", "package_id"):
        value = report.get(key) or summary.get(key)
        if value:
            return f"{spec['component_id_prefix']}:{_safe_id(str(value))}"
    return f"{spec['component_id_prefix']}:{index:03d}"


def _delivery_evidence_from_verification(component_id: str, component_type: str, requirement: str, report: ImplementationDocument, path: Path) -> ImplementationDocument:
    return {
        "evidence_id": component_id + ":verification",
        "component_id": component_id,
        "component_type": component_type,
        "requirement": requirement,
        "path_hint": str(path.name),
        "package_type": report.get("package_type"),
        "zip_sha256": report.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash"),
        "verification_report_hash": verification_hash(report),
        "source_hash": report.get("source_hash"),
        "status": report.get("status") or "missing",
        "summary": _as_document(report.get("summary")),
    }


def _delivery_evidence_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "evidence_count": len(rows),
        "passed_count": sum(1 for row in rows if row.get("status") == "passed"),
        "failed_count": sum(1 for row in rows if row.get("status") == "failed"),
        "stale_count": sum(1 for row in rows if row.get("status") == "stale"),
        "missing_count": sum(1 for row in rows if not row.get("status") or row.get("status") == "missing"),
    }


def _status_from_verification_evidence(evidence: ImplementationDocument) -> str:
    status = str(evidence.get("status") or "")
    if status == "passed":
        return "ready"
    if status == "failed":
        return "blocked"
    if status == "stale":
        return "stale"
    return "missing"


def _readiness_row(component_id: str, component_type: str, requirement: str, evidence: ImplementationDocument | None) -> ImplementationDocument:
    if not evidence:
        return {"component_id": component_id, "component_type": component_type, "requirement": requirement, "status": "missing", "severity": "blocking", "evidence_refs": [], "summary": f"{requirement} evidence is missing."}
    status = "ready" if evidence.get("status") == "passed" else "blocked" if evidence.get("status") == "failed" else "stale" if evidence.get("status") == "stale" else "missing"
    return {"component_id": component_id, "component_type": component_type, "requirement": requirement, "status": status, "severity": "blocking", "evidence_refs": [str(evidence.get("evidence_id") or component_type)], "summary": f"{requirement} is {status}.", "source_check_id": requirement}


def _readiness_summary(rows: list[ImplementationDocument]) -> dict[str, int]:
    return {"row_count": len(rows), "ready_count": sum(1 for row in rows if row.get("status") == "ready"), "blocked_count": sum(1 for row in rows if row.get("status") == "blocked"), "warning_count": sum(1 for row in rows if row.get("status") == "warning"), "stale_count": sum(1 for row in rows if row.get("status") == "stale"), "missing_count": sum(1 for row in rows if row.get("status") in {"missing", "not_configured"})}


def _combine_readiness_summaries(*summaries: ImplementationDocument) -> dict[str, int]:
    keys = ("row_count", "ready_count", "blocked_count", "warning_count", "stale_count", "missing_count")
    return {key: sum(int(summary.get(key) or 0) for summary in summaries if isinstance(summary, dict)) for key in keys}


def _requirement_for_component(component_type: str) -> str:
    return {"public_trust_center_verification": "public_trust_center_verified", "publication_monitoring_verification": "publication_monitoring_clean"}.get(component_type, component_type)


def _action_type(requirement: str) -> str:
    if "incident" in requirement or "monitoring" in requirement:
        return "resolve_publication_monitoring_incident"
    if "publication" in requirement:
        return "refresh_publication_channel"
    return "review_trust_operations_evidence"


def _delivery_action_type(requirement: str) -> str:
    return {
        "release_verified": "verify_release_package",
        "distribution_verified": "verify_distribution_package",
        "submission_verified": "verify_submission_package",
        "submission_evidence_verified": "verify_submission_evidence_package",
        "release_operations_verified": "verify_release_operations_package",
    }.get(requirement, "review_delivery_evidence")


def _paths(value: Any) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, list):
        return [Path(item) for item in value if item]
    return []


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def _read_required(path: Path) -> ImplementationDocument:
    if not path.exists():
        raise TrustOperationsHubNotFoundError(f"Trust Operations Hub artifact missing: {path.name}")
    return _read_json(path)


def _read_json(path: Path) -> ImplementationDocument:
    return read_json(path)


def _read_json_default(path: Path, *, default: ImplementationDocument) -> ImplementationDocument:
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    return write_json(path, _sanitize(payload))


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[ImplementationDocument]:
    if not path.exists():
        return []
    rows: list[ImplementationDocument] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _checksum_json(export_dir: Path) -> ImplementationDocument:
    rows = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.relative_to(export_dir).as_posix() not in {"checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt", "trust-operations-hub-manifest.json"}]
    data = {"schema_version": TRUST_OPERATIONS_SCHEMA_VERSION, "files": rows}
    data["integrity_hash"] = hub_hash(data)
    return data


def _write_sha256sums(export_dir: Path, checksum_json: ImplementationDocument) -> None:
    lines = [f"{item.get('sha256')}  {item.get('path')}" for item in checksum_json.get("files", []) if isinstance(item, dict)]
    (export_dir / "checksum" / "SHA256SUMS.txt").write_text(sanitize_sensitive_text("\n".join(lines) + "\n"), encoding="utf-8")


def _write_readme(export_dir: Path) -> None:
    (export_dir / "README.txt").write_text("MusicForge Trust Operations Hub\n\nThis package contains a local cross-link trust operations readiness report and evidence binding indexes.\n", encoding="utf-8")


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


def _walk_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    root = root.resolve()
    for dirpath, _dirnames, filenames in os.walk(_fs_path(root)):
        current = _from_fs_path(str(dirpath))
        for filename in filenames:
            path = current / filename
            if os.path.isfile(_fs_path(path)) and not os.path.islink(_fs_path(path)):
                rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(root).as_posix())


def _write_zip(zip_path: Path, root: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.tmp")
    _mkdir(zip_path.parent)
    if tmp_path.exists():
        tmp_path.unlink()
    with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, entry in _zip_entries(root):
            archive.write(_fs_path(path), entry)
    tmp_path.replace(zip_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:100] or "item"


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


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


def _from_fs_path(value: str) -> Path:
    if os.name == "nt" and value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    if os.name == "nt" and value.startswith("\\\\?\\"):
        return Path(value[4:])
    return Path(value)


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_BLOCKED_KEYS)


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)

_v142_toh_readiness.bind_globals(globals())
_v142_toh_evidence.bind_globals(globals())
