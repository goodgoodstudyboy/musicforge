# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, document_or as _document_or

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center_publication import PublicTrustCenterPublicationStore as PublicTrustCenterPublicationStore, publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_verifier import verify_public_trust_center_publication_mirror as verify_public_trust_center_publication_mirror, verify_public_trust_center_publication_package as verify_public_trust_center_publication_package
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE as PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE, PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE as PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE, PUBLICATION_MONITORING_HASH_EXCLUDE_KEYS as PUBLICATION_MONITORING_HASH_EXCLUDE_KEYS, PUBLICATION_MONITORING_PACKAGE_TYPE as PUBLICATION_MONITORING_PACKAGE_TYPE, PUBLICATION_MONITORING_SCHEMA_VERSION as PUBLICATION_MONITORING_SCHEMA_VERSION, PUBLICATION_MONITOR_RUN_PACKAGE_TYPE as PUBLICATION_MONITOR_RUN_PACKAGE_TYPE, PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE as PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE, monitoring_hash as monitoring_hash, monitoring_manifest_hash as monitoring_manifest_hash, verification_hash as verification_hash
from song_agent.domains.trust.v142_ptcpm_readiness import PublicTrustCenterPublicationMonitoringStoreReadinessMixin
from song_agent.domains.trust import v142_ptcpm_readiness as _v142_ptcpm_readiness
from song_agent.domains.trust.v142_ptcpm_evidence import PublicTrustCenterPublicationMonitoringStoreEvidenceMixin
from song_agent.domains.trust import v142_ptcpm_evidence as _v142_ptcpm_evidence




PUBLICATION_MONITOR_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitor"






PUBLICATION_MONITORING_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}
TERMINAL_INCIDENT_STATUSES = {"resolved", "waived"}
BLOCKING_DRIFT_SEVERITIES = {"critical", "high"}


class PublicTrustCenterPublicationMonitoringError(ValueError):
    pass


class PublicTrustCenterPublicationMonitoringNotFoundError(PublicTrustCenterPublicationMonitoringError):
    pass


class PublicTrustCenterPublicationMonitoringStateError(PublicTrustCenterPublicationMonitoringError):
    pass


class PublicTrustCenterPublicationMonitoringStore(PublicTrustCenterPublicationMonitoringStoreReadinessMixin, PublicTrustCenterPublicationMonitoringStoreEvidenceMixin):
    def __init__(self, *, publication_store: PublicTrustCenterPublicationStore) -> None:
        self.publication_store = publication_store
        self.lock = threading.RLock()


























































def monitoring_summary(run: DomainDocument) -> DomainDocument:
    summary = _as_document(run.get("summary"))
    return {"run_id": run.get("run_id"), "monitor_id": run.get("monitor_id"), "publication_id": run.get("publication_id"), "status": run.get("status"), **summary}


def _default_requirements() -> dict[str, bool]:
    return {
        "require_ready": True,
        "require_anchor_current": True,
        "require_acceptance_board_signoff": True,
        "require_no_revoked": True,
        "require_current": True,
        "require_no_open_critical_incidents": True,
        "require_mirror": True,
        "require_external_channel_state": True,
    }


def _default_drift_policy() -> dict[str, str]:
    return {
        "missing_file": "critical",
        "hash_mismatch": "critical",
        "extra_file": "high",
        "html_unsafe": "critical",
        "revoked": "critical",
        "superseded": "critical",
        "state_missing": "critical",
        "state_stale": "critical",
        "redaction": "critical",
    }


def _drift(drift_type: str, severity: str, message: str, evidence: ImplementationDocument | None = None) -> ImplementationDocument:
    return {"drift_id": "drift-" + stable_hash({"type": drift_type, "message": message, "evidence": evidence or {}})[:12], "drift_type": drift_type, "severity": severity, "message": message, "evidence": evidence or {}, "manual_action": {"status": "manual_required", "action_type": _manual_action_for_drift(drift_type)}}


def _manual_action_for_drift(drift_type: str) -> str:
    if drift_type in {"publication_revoked", "publication_superseded", "publication_missing_from_state"}:
        return "publish_replacement"
    if drift_type.startswith("mirror_"):
        return "refresh_or_recopy_mirror"
    return "investigate_publication_drift"


def _overall_severity(drifts: list[ImplementationDocument]) -> str:
    severities = [str(item.get("severity") or "") for item in drifts]
    if "critical" in severities:
        return "critical"
    if "high" in severities:
        return "high"
    if "warning" in severities:
        return "warning"
    return "none"


def _run_status(drift_report: ImplementationDocument, incident_report: ImplementationDocument) -> str:
    summary = _as_document(incident_report.get("summary"))
    if drift_report.get("status") == "failed" or int(summary.get("critical_count") or 0) > 0:
        return "failed"
    if drift_report.get("status") == "warning" or int(summary.get("open_count") or 0) > 0:
        return "warning"
    return "passed"


def _publication_state_row(channel_state: ImplementationDocument, publication_id: str) -> ImplementationDocument:
    for row in channel_state.get("publications", []) if isinstance(channel_state.get("publications"), list) else []:
        if isinstance(row, dict) and str(row.get("publication_id") or "") == str(publication_id):
            return row
    return {}


def _check_status_map(report: ImplementationDocument) -> dict[str, str]:
    return {str(item.get("check_id") or ""): str(item.get("status") or "") for item in report.get("checks", []) if isinstance(item, dict)}


def _event(event_type: str, payload: ImplementationDocument, previous_event_hash: str | None, now: str, prefix: str, index: int) -> ImplementationDocument:
    payload = sanitize_metadata(payload, blocked_keys=PUBLICATION_MONITORING_BLOCKED_KEYS)
    event = {
        "event_id": f"{prefix}-{index:06d}",
        "event_type": event_type,
        "created_at": now,
        "payload": payload,
        "payload_hash": stable_hash(payload),
        "previous_event_hash": previous_event_hash,
    }
    event["event_hash"] = stable_hash(event)
    return event


def _incident_from_events(center_id: str, channel_id: str, monitor_id: str, incident_id: str, events: list[ImplementationDocument]) -> ImplementationDocument:
    if not events:
        return {}
    opened = next((event for event in events if event.get("event_type") == "opened"), events[0])
    payload = _as_document(opened.get("payload"))
    status = "open"
    evidence = {
        "drift_report_hash": payload.get("drift_report_hash"),
        "probe_results_hash": payload.get("probe_results_hash"),
        "channel_state_latest_event_hash": payload.get("channel_state_latest_event_hash"),
    }
    latest_run_id = payload.get("run_id")
    for event in events:
        event_type = str(event.get("event_type") or "")
        epayload = _as_document(event.get("payload"))
        if epayload.get("run_id"):
            latest_run_id = epayload.get("run_id")
        if event_type in {"opened", "reopened"}:
            status = "open"
        elif event_type == "acknowledged":
            status = "open"
        elif event_type == "resolved":
            status = "resolved"
        elif event_type == "waived":
            status = "waived"
    issue_type = str(payload.get("issue_type") or "monitoring_drift")
    severity = str(payload.get("severity") or "critical")
    return {
        "schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION,
        "package_type": PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE,
        "incident_id": incident_id,
        "monitor_id": monitor_id,
        "center_id": center_id,
        "channel_id": channel_id,
        "first_run_id": payload.get("run_id"),
        "latest_run_id": latest_run_id,
        "publication_id": None,
        "status": status,
        "severity": severity,
        "issue_type": issue_type,
        "title": _incident_title(issue_type),
        "evidence": evidence,
        "manual_actions": [{"action_type": _manual_action_for_drift(issue_type), "status": "manual_required", "reason": _incident_title(issue_type)}],
    }


def _incident_title(issue_type: str) -> str:
    return {
        "publication_revoked": "Published snapshot has been revoked",
        "publication_superseded": "Published snapshot has been superseded",
        "mirror_file_missing": "Publication mirror is missing files",
        "mirror_file_hash_mismatch": "Publication mirror file hash mismatch",
        "mirror_extra_file": "Publication mirror contains unexpected files",
        "publication_zip_hash_mismatch": "Publication ZIP does not match channel state",
    }.get(issue_type, "Publication monitoring drift detected")


def _event_chain_valid(events: list[ImplementationDocument]) -> bool:
    previous: str | None = None
    for event in events:
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(_as_document(event.get("payload"))):
            return False
        expected = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event.get("event_hash") != expected:
            return False
        previous = str(event.get("event_hash") or "")
    return True


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:80] or "item"


def _next_id(root: Path, prefix: str) -> str:
    count = len(list(root.glob(f"{prefix}-*"))) if root.exists() else 0
    return f"{prefix}-{count + 1:06d}"


def _public_path_hint(value: Any) -> str | None:
    if not value:
        return None
    return Path(str(value)).name


def _write_json(path: Path, payload: ImplementationDocument) -> Path:
    _mkdir(path.parent)
    tmp_path = path.with_name(f".tmp-{os.getpid()}-{threading.get_ident()}.json")
    try:
        with open(_fs_path(tmp_path), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
        os.replace(_fs_path(tmp_path), _fs_path(path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return path


def _read_json_default(path: Path, *, default: ImplementationDocument | None = None) -> ImplementationDocument:
    if not os.path.exists(_fs_path(path)):
        return dict(default or {})
    try:
        with open(_fs_path(path), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return dict(default or {})
    return _document_or(value, dict(default or {}))


def _append_jsonl(path: Path, payload: ImplementationDocument) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[ImplementationDocument]) -> None:
    _mkdir(path.parent)
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_sanitize(row), ensure_ascii=False, sort_keys=True) + "\n")


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
    rows = [_file_record(export_dir, path) for path in _walk_files(export_dir) if path.relative_to(export_dir).as_posix() not in {"checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt", "monitoring-manifest.json"}]
    data = {"schema_version": PUBLICATION_MONITORING_SCHEMA_VERSION, "files": rows}
    data["integrity_hash"] = monitoring_hash(data)
    return data


def _write_sha256sums(export_dir: Path, checksum_json: ImplementationDocument) -> None:
    lines = [f"{item.get('sha256')}  {item.get('path')}" for item in checksum_json.get("files", []) if isinstance(item, dict)]
    (export_dir / "checksum" / "SHA256SUMS.txt").write_text(sanitize_sensitive_text("\n".join(lines) + "\n"), encoding="utf-8")


def _write_readme(export_dir: Path) -> None:
    text = "\n".join(
        [
            "MusicForge Public Trust Center Publication Monitoring",
            "",
            "This package contains a local publication monitoring run, drift report, incident summary, channel state snapshot, and verifier reports.",
            "Use verify-public-trust-center-publication-monitoring-package with --publication-channel-state for current revoke/supersede checks.",
            "",
        ]
    )
    (export_dir / "README.txt").write_text(sanitize_sensitive_text(text), encoding="utf-8")


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
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(root):
                with open(_fs_path(resolved), "rb") as handle:
                    archive.writestr(entry, handle.read())
        os.replace(_fs_path(tmp_path), _fs_path(zip_path))
    finally:
        if os.path.exists(_fs_path(tmp_path)):
            os.unlink(_fs_path(tmp_path))


def _safe_copy(source: Path, target: Path, root: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    _ensure_within(root.resolve(), target)
    if not os.path.isfile(_fs_path(source)) or os.path.islink(_fs_path(source)):
        raise PublicTrustCenterPublicationMonitoringStateError(f"Required monitoring source file is missing: {source.name}")
    _mkdir(target.parent)
    shutil.copyfile(_fs_path(source), _fs_path(target))


def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterPublicationMonitoringStateError("Resolved path escapes Public Trust Center publication monitoring root.")


def _mkdir(path: Path) -> None:
    os.makedirs(_fs_path(path), exist_ok=True)


def _sha256(path: Path) -> str | None:
    if not os.path.isfile(_fs_path(path)):
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sanitize(payload: Any) -> Any:
    return sanitize_metadata(payload, blocked_keys=PUBLICATION_MONITORING_BLOCKED_KEYS)


def _fs_path(path: Path) -> str:
    text = str(Path(path).resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _from_fs_path(value: str) -> Path:
    if os.name != "nt":
        return Path(value)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value.removeprefix("\\\\?\\UNC\\"))
    if value.startswith("\\\\?\\"):
        return Path(value.removeprefix("\\\\?\\"))
    return Path(value)

_v142_ptcpm_readiness.bind_globals(globals())
_v142_ptcpm_evidence.bind_globals(globals())
