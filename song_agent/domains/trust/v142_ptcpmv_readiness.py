# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    raw_central_directory_entry_names as _raw_zip_entry_names,
)
import hashlib as hashlib
import json as json
import os as os
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_contracts import publication_channel_state_hash as publication_channel_state_hash
from song_agent.domains.trust.public_trust_center_publication_monitoring_contracts import PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE as PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE, PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE as PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE, PUBLICATION_MONITORING_PACKAGE_TYPE as PUBLICATION_MONITORING_PACKAGE_TYPE, PUBLICATION_MONITORING_SCHEMA_VERSION as PUBLICATION_MONITORING_SCHEMA_VERSION, PUBLICATION_MONITOR_RUN_PACKAGE_TYPE as PUBLICATION_MONITOR_RUN_PACKAGE_TYPE, PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE as PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE, monitoring_hash as monitoring_hash, monitoring_manifest_hash as monitoring_manifest_hash, verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
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

VERIFIER_BLOCKED_KEYS = _make_deferred_global('VERIFIER_BLOCKED_KEYS')
item = _make_deferred_global('item')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS, item, part
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    item = namespace.get('item', item)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


PUBLICATION_MONITORING_VERIFICATION_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitoring_verification"
PUBLICATION_MONITORING_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 256
DEFAULT_MAX_ENTRY_COUNT = 64
REQUIRED_ENTRIES = {
    "README.txt",
    "monitoring-manifest.json",
    "monitor-run.json",
    "probe-results.json",
    "drift-report.json",
    "incident-report.json",
    "incident-events.jsonl",
    "channel-state-snapshot.json",
    "file-index.json",
    "verification-reports/publication-verification-report.json",
    "verification-reports/mirror-verification-report.json",
    "checksum/SHA256SUMS.json",
    "checksum/SHA256SUMS.txt",
}




def _rebuild_incidents_from_events(events: list[DomainDocument], *, center_id: str, channel_id: str, monitor_id: str, publication_id: object) -> tuple[list[DomainDocument], dict[str, int], list[str]]:
    grouped: dict[str, list[DomainDocument]] = {}
    invalid: list[str] = []
    for event in events:
        incident_id = str(event.get("incident_id") or "")
        if not incident_id:
            invalid.append("<missing-incident-id>")
            continue
        grouped.setdefault(incident_id, []).append(event)
    rows: list[DomainDocument] = []
    for incident_id, incident_events in sorted(grouped.items()):
        ordered = sorted(incident_events, key=lambda item: int(item.get("sequence") or 0))
        if not _incident_event_chain_valid(ordered):
            invalid.append(incident_id)
        row = _incident_from_events(center_id, channel_id, monitor_id, incident_id, ordered)
        if row:
            row["publication_id"] = publication_id
            row["event_count"] = len(ordered)
            row["latest_event_hash"] = ordered[-1].get("event_hash") if ordered else None
            row["event_chain_valid"] = _incident_event_chain_valid(ordered)
            rows.append(row)
    summary = {
        "incident_count": len(rows),
        "open_count": sum(1 for item in rows if item.get("status") == "open"),
        "critical_count": sum(1 for item in rows if item.get("status") == "open" and item.get("severity") == "critical"),
        "waived_count": sum(1 for item in rows if item.get("status") == "waived"),
        "resolved_count": sum(1 for item in rows if item.get("status") == "resolved"),
    }
    return rows, summary, invalid

def _incident_from_events(center_id: str, channel_id: str, monitor_id: str, incident_id: str, events: list[DomainDocument]) -> DomainDocument:
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

def _incident_comparable(incident: DomainDocument) -> DomainDocument:
    return {key: incident.get(key) for key in (
        "schema_version",
        "package_type",
        "incident_id",
        "monitor_id",
        "center_id",
        "channel_id",
        "first_run_id",
        "latest_run_id",
        "publication_id",
        "status",
        "severity",
        "issue_type",
        "title",
        "evidence",
        "manual_actions",
        "event_count",
        "latest_event_hash",
        "event_chain_valid",
    )}

def _incident_title(issue_type: str) -> str:
    return {
        "publication_revoked": "Published snapshot has been revoked",
        "publication_superseded": "Published snapshot has been superseded",
        "mirror_file_missing": "Publication mirror is missing files",
        "mirror_file_hash_mismatch": "Publication mirror file hash mismatch",
        "mirror_extra_file": "Publication mirror contains unexpected files",
        "publication_zip_hash_mismatch": "Publication ZIP does not match channel state",
    }.get(issue_type, "Publication monitoring drift detected")

def _manual_action_for_drift(issue_type: str) -> str:
    if issue_type.startswith("mirror_"):
        return "refresh_publication_mirror"
    if issue_type.startswith("publication_"):
        return "review_publication_channel_state"
    return "investigate_publication_monitoring_drift"

def _incident_event_chain_valid(events: list[DomainDocument]) -> bool:
    previous: str | None = None
    for index, event in enumerate(events, start=1):
        if int(event.get("sequence") or 0) != index:
            return False
        if event.get("previous_event_hash") != previous:
            return False
        payload = _as_document(event.get("payload"))
        if event.get("payload_hash") != stable_hash(payload):
            return False
        expected = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event.get("event_hash") != expected:
            return False
        previous = str(event.get("event_hash") or "")
    return True

def _publication_state_row(channel_state: DomainDocument, publication_id: str) -> DomainDocument:
    for row in channel_state.get("publications", []) if isinstance(channel_state.get("publications"), list) else []:
        if isinstance(row, dict) and str(row.get("publication_id") or "") == str(publication_id):
            return row
    return {}

def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    return True

def _is_forbidden_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or "/.musicforge/" in lower

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _read_json_file(path: Path | None) -> DomainDocument:
    if path is None:
        return {}
    try:
        with open(_fs_path(Path(path)), "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return _as_document(value)

def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts

def _redaction_findings(name: str, text: str) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    for pattern in [*SENSITIVE_VALUE_PATTERNS, *LOCAL_PATH_VALUE_PATTERNS]:
        regex = pattern[0] if isinstance(pattern, tuple) else pattern
        if regex.search(text):
            findings.append({"path": name, "pattern": regex.pattern[:80]})
    return findings

def _blocked_key_findings(name: str, value: object) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "key": str(key)})
            findings.extend(_blocked_key_findings(name, nested))
    elif isinstance(value, list):
        for nested in value:
            findings.extend(_blocked_key_findings(name, nested))
    return findings

def _fs_path(path: Path) -> str:
    text = str(Path(path).resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text
