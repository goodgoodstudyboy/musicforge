# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, list_or as _list_or

import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub import DELIVERY_VERIFICATION_COMPONENTS as DELIVERY_VERIFICATION_COMPONENTS, TrustOperationsHubStore as TrustOperationsHubStore, hub_hash as hub_hash
from song_agent.domains.trust.trust_operations_hub_incidents_contracts import INCIDENT_EXPORT_ENTRIES as INCIDENT_EXPORT_ENTRIES, TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE as TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION as TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION, incident_hash as incident_hash, incident_manifest_hash as incident_manifest_hash
from song_agent.domains.trust.v142_tohi_readiness import TrustOperationsIncidentStoreReadinessMixin
from song_agent.domains.trust import v142_tohi_readiness as _v142_tohi_readiness
from song_agent.domains.trust.v142_tohi_evidence import TrustOperationsIncidentStoreEvidenceMixin
from song_agent.domains.trust import v142_tohi_evidence as _v142_tohi_evidence





TRUST_OPERATIONS_INCIDENT_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_report"


TRUST_OPERATIONS_INCIDENT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}
EVIDENCE_PACKAGE_TYPES = {
    "release_verification": "musicforge_release_verification",
    "distribution_verification": "musicforge_distribution_verification",
    "submission_verification": "musicforge_submission_verification",
    "submission_evidence_verification": "musicforge_submission_evidence_verification",
    "release_operations_verification": "musicforge_release_operations_verification",
    "publication_monitoring_verification": "musicforge_public_trust_center_publication_monitoring_verification",
}



BLOCKING_STATUSES = {"open", "triaged", "in_progress", "waiting_verification", "verified"}
SAFE_REMEDIATION_ACTIONS = {
    "refresh_hub_report",
    "export_hub",
    "zip_hub",
    "verify_hub",
    "create_hub_runbook",
    "run_hub_safe_actions",
    "verify_release_package",
    "verify_distribution_package",
    "verify_submission_package",
    "verify_submission_evidence_package",
    "verify_release_operations_package",
    "manual_required",
}
FORBIDDEN_REMEDIATION_ACTIONS = {
    "signoff",
    "reset_signoff",
    "approve_change_request",
    "submit",
    "mark_accepted",
    "provider_call",
    "upload_file",
    "manual_review",
    "delete_artifact",
    "force_close",
}


class TrustOperationsIncidentError(ValueError):
    pass


class TrustOperationsIncidentNotFoundError(TrustOperationsIncidentError):
    pass


class TrustOperationsIncidentStateError(TrustOperationsIncidentError):
    pass


class TrustOperationsIncidentStore(TrustOperationsIncidentStoreReadinessMixin, TrustOperationsIncidentStoreEvidenceMixin):
    def __init__(
        self,
        root: Path | str = Path(".musicforge") / "trust-operations-incidents",
        *,
        hub_store: TrustOperationsHubStore | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.hub_store = hub_store or TrustOperationsHubStore()
        self.lock = threading.RLock()
























































def _default_plan_steps(incident: ImplementationDocument) -> list[ImplementationDocument]:
    component_type = str(incident.get("detected_from", {}).get("component_type") or "")
    action = {
        "release_verification": "verify_release_package",
        "distribution_verification": "verify_distribution_package",
        "submission_verification": "verify_submission_package",
        "submission_evidence_verification": "verify_submission_evidence_package",
        "release_operations_verification": "verify_release_operations_package",
    }.get(component_type, "manual_required")
    return [
        {"action_type": "manual_required", "title": "Review and repair the underlying Trust Operations blocker."},
        {"action_type": action, "title": f"Verify {component_type or 'component'} evidence."},
    ]


def _board_summary(incidents: list[ImplementationDocument]) -> ImplementationDocument:
    open_rows = [item for item in incidents if item.get("status") in BLOCKING_STATUSES]
    blocking_open = [item for item in open_rows if item.get("blocking")]
    critical = [item for item in open_rows if item.get("severity") == "critical"]
    high = [item for item in open_rows if item.get("severity") == "high"]
    stale = [item for item in incidents if item.get("stale")]
    return {
        "total_incidents": len(incidents),
        "open_count": len(open_rows),
        "closed_count": sum(1 for item in incidents if item.get("status") == "closed"),
        "critical_count": len(critical),
        "high_count": len(high),
        "blocking_open_count": len(blocking_open),
        "stale_count": len(stale),
        "ready_for_hub_signoff": len(open_rows) == 0 and len(stale) == 0,
    }


def _evidence_summary(index: ImplementationDocument) -> dict[str, int]:
    rows = _as_list(index.get("evidence"))
    return {
        "evidence_count": len(rows),
        "passed_count": sum(1 for row in rows if isinstance(row, dict) and _evidence_binding_valid(row) and row.get("status") == "passed"),
        "failed_count": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "failed"),
        "invalid_count": sum(1 for row in rows if isinstance(row, dict) and row.get("status") == "passed" and not _evidence_binding_valid(row)),
    }


def _expected_evidence_rows_for_component(docs: dict[str, ImplementationDocument], component_type: str) -> list[ImplementationDocument]:
    delivery_types = {str(spec.get("component_type") or "") for spec in DELIVERY_VERIFICATION_COMPONENTS}
    if component_type in delivery_types:
        source = _as_document(docs.get("delivery_evidence_index"))
    else:
        source = _as_document(docs.get("evidence_binding_index"))
    return [row for row in source.get("evidence", []) if isinstance(row, dict) and row.get("component_type") == component_type]


def _binding_for_expected_row(expected: ImplementationDocument, report: ImplementationDocument) -> ImplementationDocument:
    expected_component_id = str(expected.get("component_id") or expected.get("evidence_id") or expected.get("component_type") or "")
    expected_component_type = str(expected.get("component_type") or "")
    report_hash = verification_hash(report)
    checks = [
        _binding_check("known_package_type", report.get("package_type"), EVIDENCE_PACKAGE_TYPES.get(expected_component_type)) if EVIDENCE_PACKAGE_TYPES.get(expected_component_type) else {"name": "known_package_type", "status": "passed", "actual": report.get("package_type"), "expected": report.get("package_type")},
        _binding_check("package_type", report.get("package_type"), expected.get("package_type")),
        _binding_check("status", report.get("status") or "missing", expected.get("status") or "missing"),
        _binding_check("verification_report_hash", report_hash, expected.get("verification_report_hash")),
        _binding_check("zip_sha256", report.get("zip_sha256"), expected.get("zip_sha256")),
        _binding_check("manifest_hash", report.get("manifest_hash"), expected.get("manifest_hash")),
        _binding_check("source_hash", report.get("source_hash"), expected.get("source_hash")),
    ]
    if expected.get("zip_size_bytes") is not None or report.get("zip_size_bytes") is not None:
        checks.append(_binding_check("zip_size_bytes", report.get("zip_size_bytes"), expected.get("zip_size_bytes")))
    passed = all(check["status"] == "passed" for check in checks)
    return {
        "binding_status": "passed" if passed else "failed",
        "binding_checks": checks,
        "component_type": expected_component_type,
        "component_id": expected_component_id,
        "expected_evidence_id": expected.get("evidence_id"),
        "expected_component_id": expected_component_id,
        "expected_component_type": expected_component_type,
        "expected_package_type": expected.get("package_type"),
        "expected_verification_report_hash": expected.get("verification_report_hash"),
        "expected_zip_sha256": expected.get("zip_sha256"),
        "expected_zip_size_bytes": expected.get("zip_size_bytes"),
        "expected_manifest_hash": expected.get("manifest_hash"),
        "expected_source_hash": expected.get("source_hash"),
        "expected_status": expected.get("status"),
    }


def _binding_check(name: str, actual: Any, expected: Any) -> ImplementationDocument:
    return {"name": name, "status": "passed" if actual == expected else "failed", "actual": actual, "expected": expected}


def _failed_binding(component_type: str, component_id: str, reason: str) -> ImplementationDocument:
    return {
        "binding_status": "failed",
        "binding_checks": [{"name": reason, "status": "failed", "actual": component_id, "expected": component_type}],
        "component_type": component_type,
        "component_id": component_id,
    }


def _is_generic_component_id(component_id: str) -> bool:
    return component_id.endswith(":coverage") or component_id.endswith(":verification") or component_id.endswith(":missing")


def _evidence_binding_valid(evidence: ImplementationDocument) -> bool:
    if evidence.get("status") != "passed":
        return False
    if evidence.get("binding_status") != "passed":
        return False
    if evidence.get("package_type") != evidence.get("expected_package_type"):
        return False
    if evidence.get("component_type") != evidence.get("expected_component_type"):
        return False
    if evidence.get("component_id") != evidence.get("expected_component_id"):
        return False
    if evidence.get("verification_report_hash") != evidence.get("expected_verification_report_hash"):
        return False
    for key in ("zip_sha256", "zip_size_bytes", "manifest_hash", "source_hash"):
        expected_key = "expected_" + key
        if evidence.get(expected_key) is not None and evidence.get(key) != evidence.get(expected_key):
            return False
    checks = _as_list(evidence.get("binding_checks"))
    return bool(checks) and all(isinstance(check, dict) and check.get("status") == "passed" for check in checks)


def _valid_passed_evidence_for_incident(index: ImplementationDocument, incident: ImplementationDocument) -> list[ImplementationDocument]:
    detected = _as_document(incident.get("detected_from"))
    incident_component_type = str(detected.get("component_type") or "")
    incident_component_id = str(detected.get("component_id") or "")
    rows = []
    for row in index.get("evidence", []) if isinstance(index.get("evidence"), list) else []:
        if not isinstance(row, dict) or not _evidence_binding_valid(row):
            continue
        if incident_component_type and row.get("component_type") != incident_component_type:
            continue
        if incident_component_id and not _is_generic_component_id(incident_component_id) and row.get("component_id") != incident_component_id:
            continue
        rows.append(row)
    return rows


def _category(requirement: str, source_type: str) -> str:
    if source_type.endswith("delivery"):
        if requirement.endswith("_verified"):
            return "delivery_verification_missing"
        return "delivery_blocker"
    if "monitoring" in requirement:
        return "publication_monitoring_incident"
    return "hub_blocker"


def _component_type_from_component_id(component_id: str) -> str:
    prefix = str(component_id).split(":", 1)[0]
    return {
        "release": "release_verification",
        "distribution": "distribution_verification",
        "submission": "submission_verification",
        "submission-evidence": "submission_evidence_verification",
        "release-operations": "release_operations_verification",
        "publication-monitoring": "publication_monitoring_verification",
    }.get(prefix, prefix)


def _component_type_from_check_id(check_id: str) -> str:
    for marker, component_type in (
        ("release_verification", "release_verification"),
        ("distribution_verification", "distribution_verification"),
        ("submission_evidence_verification", "submission_evidence_verification"),
        ("submission_verification", "submission_verification"),
        ("release_operations_verification", "release_operations_verification"),
        ("monitoring", "publication_monitoring_verification"),
    ):
        if marker in check_id:
            return component_type
    return "trust_operations_hub"


def _component_id_from_check_id(component_type: str, check_id: str) -> str:
    prefix = {
        "release_verification": "release",
        "distribution_verification": "distribution",
        "submission_verification": "submission",
        "submission_evidence_verification": "submission-evidence",
        "release_operations_verification": "release-operations",
        "publication_monitoring_verification": "publication-monitoring",
    }.get(component_type, "hub")
    if check_id.endswith("_component_coverage"):
        return f"{prefix}:coverage"
    match = re.search(r"_(release|distribution|submission|submission_evidence|release_operations)_([A-Za-z0-9_]+)_hash$", check_id)
    if match:
        return f"{prefix}:{match.group(2).replace('_', '-')}"
    return f"{prefix}:verification"


def _contains_sensitive_value(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    markers = (
        "sk-",
        "bearer ",
        "github" + "_pat_",
        "x-access" + "-token",
        "github" + "key",
        "c:" + "\\users\\",
        "\\\\",
    )
    return any(marker in lowered for marker in markers)


def _write_readme(export_dir: Path) -> None:
    (export_dir / "README.txt").write_text(
        "MusicForge Trust Operations Incident Board\n\nThis package contains local incident response and remediation closeout evidence for Trust Operations Hub blockers.\n",
        encoding="utf-8",
    )


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


def _file_record(root: Path, path: Path) -> ImplementationDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}


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


def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in _walk_files(root)]


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


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:100] or "item"


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
    return sanitize_metadata(payload, blocked_keys=TRUST_OPERATIONS_INCIDENT_BLOCKED_KEYS)


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)

_v142_tohi_readiness.bind_globals(globals())
_v142_tohi_evidence.bind_globals(globals())
