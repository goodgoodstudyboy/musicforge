# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.release_audio_command_center_verifier import RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE as RELEASE_AUDIO_COMMAND_CENTER_PACKAGE_TYPE, verify_release_audio_command_center_component as verify_release_audio_command_center_component, verify_release_audio_command_center_package as verify_release_audio_command_center_package, write_release_audio_command_center_verification_report as write_release_audio_command_center_verification_report
from song_agent.domains.quality.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStore as ReleaseAudioQualityActionQueueSignoffStore
from song_agent.domains.quality.release_audio_quality_actions import ReleaseAudioQualityActionQueueStore as ReleaseAudioQualityActionQueueStore
from song_agent.domains.quality.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore as ReleaseAudioQualityObservatoryStore
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

value = _make_deferred_global('value')

def bind_globals(namespace: dict[str, object]) -> None:
    global value
    value = namespace.get('value', value)
    _bind_deferred_defaults(namespace)


RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION = 1
RELEASE_AUDIO_COMMAND_CENTER_REPORT_PACKAGE_TYPE = "release_audio_command_center_report"
COMPONENTS: tuple[dict[str, str], ...] = (
    {"key": "certification", "label": "Release Audio Certification", "artifact": "release_audio_certification"},
    {"key": "timeline", "label": "Release Audio Timeline", "artifact": "release_audio_timeline"},
    {"key": "regression", "label": "Release Audio Regression Guard", "artifact": "release_audio_regression"},
    {"key": "baseline_governance", "label": "Release Audio Baseline Governance", "artifact": "release_audio_baseline_governance"},
    {"key": "regression_response", "label": "Release Audio Regression Response", "artifact": "release_audio_regression_response"},
    {"key": "observatory", "label": "Release Audio Quality Observatory", "artifact": "release_audio_quality_observatory"},
    {"key": "action_queue", "label": "Release Audio Quality Action Queue", "artifact": "release_audio_quality_action_queue"},
    {"key": "action_queue_signoff", "label": "Release Audio Quality Action Queue Signoff", "artifact": "release_audio_quality_action_queue_signoff"},
)




def _component_row(component: dict[str, str], evidence: DomainDocument, *, verifier_kwargs: DomainDocument) -> DomainDocument:
    key = component["key"]
    paths = _as_document(evidence.get(key))
    mapping = {
        "certification": ("certification_zip_path", "certification_verification_report_path"),
        "timeline": ("timeline_zip_path", "timeline_verification_report_path"),
        "regression": ("regression_zip_path", "regression_verification_report_path"),
        "baseline_governance": ("baseline_registry_zip_path", "baseline_registry_verification_report_path"),
        "regression_response": ("regression_response_zip_path", "regression_response_verification_report_path"),
        "observatory": ("observatory_zip_path", "observatory_verification_report_path"),
        "action_queue": ("action_queue_zip_path", "action_queue_verification_report_path"),
        "action_queue_signoff": ("action_queue_signoff_archive_path", "action_queue_signoff_verification_report_path"),
    }
    zip_arg, report_arg = mapping[key]
    zip_path = paths.get("zip") or paths.get("zip_path") or verifier_kwargs.get(zip_arg)
    report_path = paths.get("verification_report") or paths.get("verification_report_path") or verifier_kwargs.get(report_arg)
    status = "missing"
    readiness = "missing"
    message = "Evidence ZIP or verification report is missing."
    fingerprint: object = {
        "component_key": key,
        "artifact_type": component["artifact"],
        "zip_sha256": None,
        "zip_size_bytes": None,
        "manifest_hash": None,
        "verification_report_hash": None,
        "verification_status": None,
        "runtime_verification_status": None,
        "runtime_manifest_hash": None,
        "runtime_failed_count": 0,
        "runtime_blockers": [],
    }
    verification_summary: DomainDocument = {"component_key": key, "status": "missing"}
    runtime_summary: DomainDocument = {"component_key": key, "status": "missing", "blockers": []}
    if zip_path and report_path:
        runtime = verify_release_audio_command_center_component(key, zip_path, report_path, **verifier_kwargs)
        fingerprint.update(runtime.get("fingerprint") or {})
        fingerprint["artifact_type"] = component["artifact"]
        external_report = _as_document(runtime.get("external_report"))
        verification_summary = _public_verification_summary(key, external_report) if external_report else verification_summary
        runtime_summary = {
            "component_key": key,
            "status": runtime.get("status"),
            "readiness": runtime.get("readiness"),
            "blockers": runtime.get("blockers", []),
            "runtime_report": runtime.get("runtime_report", {}),
        }
        runtime_summary["integrity_hash"] = _integrity_hash(runtime_summary)
        if runtime.get("status") == "passed":
            status = "ready"
            readiness = "ready"
            message = "Evidence is current and runtime verification passed."
        else:
            status = "blocked"
            readiness = str(runtime.get("readiness") or "blocked")
            message = _message_for_readiness(readiness, component["label"])
    fingerprint["integrity_hash"] = _integrity_hash(fingerprint)
    if "integrity_hash" not in verification_summary:
        verification_summary["integrity_hash"] = _integrity_hash(verification_summary)
    return sanitize_metadata(
        {
            "component_key": key,
            "artifact_type": component["artifact"],
            "label": component["label"],
            "status": status,
            "readiness": readiness,
            "message": message,
            "fingerprint": fingerprint,
            "verification_summary": verification_summary,
            "runtime_summary": runtime_summary,
        }
    )

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
        "summary": {key: value for key, value in summary.items() if key not in {"zip_path"}},
    }
    public["integrity_hash"] = _integrity_hash(public)
    return sanitize_metadata(public)

def _sync_report_document_hashes(docs: DomainDocument) -> None:
    report = _as_document(docs.get("report"))
    report["document_hashes"] = {
        "command_center": docs.get("command_center", {}).get("integrity_hash"),
        "evidence_inventory": docs.get("inventory", {}).get("integrity_hash"),
        "readiness_matrix": docs.get("readiness", {}).get("integrity_hash"),
        "gap_plan": docs.get("gap_plan", {}).get("integrity_hash"),
        "runbook": docs.get("runbook", {}).get("integrity_hash"),
        "runbook_results": docs.get("runbook_results", {}).get("integrity_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)

def _readiness_row(row: DomainDocument) -> DomainDocument:
    status = "ready" if row.get("status") == "ready" else str(row.get("readiness") or "blocked") if row.get("required") else "not_required"
    return {
        "component_key": row.get("component_key"),
        "artifact_type": row.get("artifact_type"),
        "label": row.get("label"),
        "required": bool(row.get("required")),
        "readiness": status,
        "message": row.get("message"),
        "verification_status": (row.get("fingerprint") or {}).get("verification_status"),
        "runtime_verification_status": (row.get("fingerprint") or {}).get("runtime_verification_status"),
        "runtime_blockers": (row.get("fingerprint") or {}).get("runtime_blockers", []),
        "next_action": "none" if status == "ready" else f"refresh_or_verify_{row.get('component_key')}",
    }

def _gap_row(row: DomainDocument) -> DomainDocument:
    priority = {
        "runtime_failed": 10,
        "stale": 20,
        "verification_failed": 30,
        "missing": 40,
        "manual_required": 50,
        "blocked": 60,
    }.get(str(row.get("readiness") or ""), 90)
    gap = {
        "gap_id": f"acc-gap-{row.get('component_key')}",
        "component_key": row.get("component_key"),
        "severity": "blocking",
        "priority": priority,
        "readiness": row.get("readiness"),
        "reason": row.get("message") or "Required evidence is not ready.",
        "recommended_action": _recommended_action_for_readiness(row),
    }
    gap["integrity_hash"] = _integrity_hash(gap)
    return gap

def _message_for_readiness(readiness: str, label: str) -> str:
    if readiness == "missing":
        return f"{label} ZIP or verification report is missing."
    if readiness == "stale":
        return f"{label} verification report does not match current evidence."
    if readiness == "verification_failed":
        return f"{label} verification report is failed or invalid."
    if readiness == "runtime_failed":
        return f"{label} runtime verification failed."
    if readiness == "manual_required":
        return f"{label} requires manual follow-up."
    return f"{label} is blocked."

def _recommended_action_for_readiness(row: DomainDocument) -> str:
    readiness = str(row.get("readiness") or "")
    key = str(row.get("component_key") or "component")
    if readiness == "runtime_failed":
        return f"rerun_runtime_verifier_for_{key}"
    if readiness == "stale":
        return f"rebuild_and_reverify_{key}"
    if readiness == "verification_failed":
        return f"inspect_verification_report_for_{key}"
    if readiness == "missing":
        return f"generate_and_verify_{key}"
    if readiness == "manual_required":
        return f"complete_manual_action_for_{key}"
    return row.get("next_action") or f"refresh_or_verify_{key}"

def _build_runbook(release_id: str, source_hash: str, gaps: list[DomainDocument], created_at: str) -> DomainDocument:
    actions = [
        {"item_id": "acc-safe-001", "action_type": "refresh_command_center", "execution_mode": "safe_auto", "requires_manual": False},
        {"item_id": "acc-safe-002", "action_type": "export_command_center", "execution_mode": "safe_auto", "requires_manual": False},
        {"item_id": "acc-safe-003", "action_type": "build_command_center_zip", "execution_mode": "safe_auto", "requires_manual": False},
        {"item_id": "acc-safe-004", "action_type": "verify_command_center_zip", "execution_mode": "safe_auto", "requires_manual": False},
    ]
    for index, gap in enumerate(gaps, start=1):
        actions.append(
            {
                "item_id": f"acc-manual-{index:03d}",
                "action_type": str(gap.get("recommended_action") or "resolve_gap"),
                "execution_mode": "manual_required",
                "requires_manual": True,
                "source_gap_id": gap.get("gap_id"),
            }
        )
    runbook = {
        "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
        "package_type": "release_audio_command_center_runbook",
        "release_id": release_id,
        "created_at": created_at,
        "source_hash": source_hash,
        "actions": actions,
        "summary": {
            "action_count": len(actions),
            "safe_action_count": sum(1 for row in actions if row.get("execution_mode") == "safe_auto"),
            "manual_required_count": sum(1 for row in actions if row.get("execution_mode") == "manual_required"),
        },
    }
    runbook["integrity_hash"] = _integrity_hash(runbook)
    return runbook

def _empty_runbook_results(release_id: str, *, source_hash: str | None = None) -> DomainDocument:
    doc = {
        "schema_version": RELEASE_AUDIO_COMMAND_CENTER_SCHEMA_VERSION,
        "package_type": "release_audio_command_center_runbook_results",
        "release_id": release_id,
        "created_at": now_iso(),
        "source_hash": source_hash,
        "results": [],
        "summary": {"completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0},
    }
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _readme(report: DomainDocument) -> str:
    return "\n".join(
        [
            "MusicForge Release Audio Command Center",
            "",
            f"Release: {report.get('release_id')}",
            f"Status: {report.get('status')}",
            f"Readiness: {report.get('readiness')}",
            "",
            "This package summarizes audio release evidence. Verify it with verify-release-audio-command-center-package and external evidence ZIP/report files.",
            "",
        ]
    )

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}
