# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS
from song_agent.domains.trust.trust_operations_final_readiness_contracts import FINAL_READINESS_EXPORT_ENTRIES as FINAL_READINESS_EXPORT_ENTRIES, FINAL_READINESS_SINGLE_SPECS as FINAL_READINESS_SINGLE_SPECS, TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS as TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS, TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE as TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE, TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION as TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION, final_readiness_hash as final_readiness_hash, final_readiness_history_event_hash as final_readiness_history_event_hash, final_readiness_history_event_payload_hash as final_readiness_history_event_payload_hash, final_readiness_history_hash as final_readiness_history_hash, final_readiness_manifest_hash as final_readiness_manifest_hash
from song_agent.domains.trust.v142_tofr_readiness import TrustOperationsFinalReadinessStoreReadinessMixin
from song_agent.domains.trust import v142_tofr_readiness as _v142_tofr_readiness
from song_agent.domains.trust.v142_tofr_evidence import TrustOperationsFinalReadinessStoreEvidenceMixin
from song_agent.domains.trust import v142_tofr_evidence as _v142_tofr_evidence








TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_final_handoff_change_request"










class TrustOperationsFinalReadinessError(ValueError):
    pass


class TrustOperationsFinalReadinessNotFoundError(TrustOperationsFinalReadinessError):
    pass


class TrustOperationsFinalReadinessStateError(TrustOperationsFinalReadinessError):
    pass


class TrustOperationsFinalReadinessStore(TrustOperationsFinalReadinessStoreReadinessMixin, TrustOperationsFinalReadinessStoreEvidenceMixin):
    def __init__(self, root: Path | str = Path(".musicforge") / "trust-operations" / "final-readiness") -> None:
        self.root = Path(root).resolve()
        self.lock = threading.RLock()




























































def _verifier_payload(payload: ImplementationDocument) -> ImplementationDocument:
    return {
        "hub_package_path": payload.get("hub_package_path"),
        "hub_verification_report_path": payload.get("hub_verification_report_path"),
        "release_verification_paths": payload.get("release_verification_paths") or ([payload["release_verification_path"]] if payload.get("release_verification_path") else []),
        "distribution_verification_paths": payload.get("distribution_verification_paths") or ([payload["distribution_verification_path"]] if payload.get("distribution_verification_path") else []),
        "submission_verification_paths": payload.get("submission_verification_paths") or ([payload["submission_verification_path"]] if payload.get("submission_verification_path") else []),
        "submission_evidence_verification_paths": payload.get("submission_evidence_verification_paths") or ([payload["submission_evidence_verification_path"]] if payload.get("submission_evidence_verification_path") else []),
        "release_operations_verification_paths": payload.get("release_operations_verification_paths") or ([payload["release_operations_verification_path"]] if payload.get("release_operations_verification_path") else []),
        "incident_board_package_path": payload.get("incident_board_package_path"),
        "incident_board_verification_report_path": payload.get("incident_board_verification_report_path"),
        "incident_knowledge_package_path": payload.get("incident_knowledge_package_path"),
        "incident_knowledge_verification_report_path": payload.get("incident_knowledge_verification_report_path"),
        "control_assessment_package_path": payload.get("control_assessment_package_path") or payload.get("control_package_path") or payload.get("trust_control_package_path"),
        "control_verification_report_path": payload.get("control_verification_report_path") or payload.get("trust_control_verification_report_path"),
        "control_signoff_archive_path": payload.get("control_signoff_archive_path") or payload.get("trust_control_signoff_archive_path"),
        "control_signoff_verification_report_path": payload.get("control_signoff_verification_report_path") or payload.get("trust_control_signoff_verification_report_path"),
        "continuous_assurance_archive_path": payload.get("continuous_assurance_archive_path") or payload.get("assurance_archive_path"),
        "continuous_assurance_verification_report_path": payload.get("continuous_assurance_verification_report_path") or payload.get("assurance_verification_report_path"),
        "assurance_watch_package_path": payload.get("assurance_watch_package_path") or payload.get("watch_package_path"),
        "assurance_watch_verification_report_path": payload.get("assurance_watch_verification_report_path") or payload.get("watch_verification_report_path"),
        "assurance_watch_signoff_archive_path": payload.get("assurance_watch_signoff_archive_path"),
        "assurance_watch_signoff_verification_report_path": payload.get("assurance_watch_signoff_verification_report_path"),
    }


def _row_from_verification_report(
    component_type: str,
    component_id: str,
    report: ImplementationDocument,
    package_path: Path | None,
    *,
    required: bool,
    manifest_hash: Any | None = None,
    expected_verification_package_type: str | None = None,
    require_package: bool = False,
) -> ImplementationDocument:
    package_sha = _sha256(package_path) if package_path else report.get("zip_sha256")
    package_size = os.stat(_fs_path(package_path)).st_size if package_path and package_path.exists() else report.get("zip_size_bytes")
    report_hash = verification_hash(report) if report else None
    mismatch_reasons: list[str] = []
    if not report:
        status = "missing"
    elif require_package and (package_path is None or not package_path.exists()):
        status = "missing"
        mismatch_reasons.append("package_missing")
    elif expected_verification_package_type and report.get("package_type") != expected_verification_package_type:
        status = "failed"
        mismatch_reasons.append("verification_package_type")
    elif report.get("status") != "passed":
        status = "failed"
        mismatch_reasons.append("verification_status")
    else:
        status = "passed"
    if report and package_path is not None and package_path.exists():
        if report.get("zip_sha256") and report.get("zip_sha256") != package_sha:
            status = "stale"
            mismatch_reasons.append("zip_sha256")
        if report.get("zip_size_bytes") and report.get("zip_size_bytes") != package_size:
            status = "stale"
            mismatch_reasons.append("zip_size_bytes")
        if report.get("manifest_hash") and manifest_hash and report.get("manifest_hash") != manifest_hash:
            status = "stale"
            mismatch_reasons.append("manifest_hash")
    return {
        "evidence_id": f"{component_type}:{component_id}",
        "component_type": component_type,
        "component_id": component_id,
        "required": required,
        "status": status,
        "package_type": report.get("package_type") if report else None,
        "package_sha256": package_sha,
        "package_size_bytes": package_size,
        "manifest_hash": manifest_hash or report.get("manifest_hash"),
        "verification_package_type": report.get("package_type") if report else None,
        "verification_report_hash": report_hash,
        "verification_status": report.get("status") if report else None,
        "blocker_count": len(_as_list(report.get("blockers"))),
        "mismatch_reasons": sorted(set(mismatch_reasons)),
    }


def _payload_paths(payload: ImplementationDocument, plural_key: str, singular_key: str) -> list[Path]:
    values = payload.get(plural_key)
    paths: list[Path] = []
    if isinstance(values, (list, tuple)):
        paths.extend(path for item in values if (path := _path_or_none(item)) is not None)
    elif values:
        path = _path_or_none(values)
        if path is not None:
            paths.append(path)
    if payload.get(singular_key):
        path = _path_or_none(payload.get(singular_key))
        if path is not None:
            paths.append(path)
    return paths


def _component_id_from_report(report: ImplementationDocument, prefix: str, index: int) -> str:
    summary = _as_document(report.get("summary"))
    for key in ("component_id", "target_id", "submission_id", "release_id", "operations_id", "package_id"):
        if report.get(key):
            return _safe_id(str(report.get(key)))
        if summary.get(key):
            return _safe_id(str(summary.get(key)))
    return f"{prefix}-{index + 1:03d}"


def _path_or_none(value: Any) -> Path | None:
    if not value:
        return None
    return Path(value)


def _blocker(code: str, message: str) -> ImplementationDocument:
    item = {"code": code, "message": message, "severity": "blocking"}
    item["integrity_hash"] = stable_hash(item)
    return item


def _read_json_default(path: Path | None, *, default: ImplementationDocument) -> ImplementationDocument:
    try:
        if path is None or not path.exists():
            return dict(default)
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default)


def _read_zip_json(zip_path: Path | None, entry: str) -> ImplementationDocument:
    if not zip_path or not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(_fs_path(zip_path), "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
            return _as_document(value)
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    _mkdir(path.parent)
    return write_json(path, _sanitize(payload))


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _write_readme(root: Path) -> None:
    (root / "README.txt").write_text(
        "MusicForge Trust Operations Final Readiness Handoff Pack\n"
        "This package contains final signed Trust Operations readiness evidence summaries.\n",
        encoding="utf-8",
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _file_record(root: Path, path: Path) -> ImplementationDocument:
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
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _next_id(root: Path, prefix: str) -> str:
    _mkdir(root)
    indexes: list[int] = []
    for path in root.iterdir():
        name = path.stem if path.is_file() else path.name
        if not name.startswith(prefix + "-"):
            continue
        try:
            indexes.append(int(name.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}-{(max(indexes) if indexes else 0) + 1:06d}"


def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sanitize(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fs_path(path: Path) -> str:
    return str(path)

_v142_tofr_readiness.bind_globals(globals())
_v142_tofr_evidence.bind_globals(globals())
