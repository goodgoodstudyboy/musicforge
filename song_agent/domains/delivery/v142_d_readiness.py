# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS, get_distribution_profile as get_distribution_profile, merge_profile_options as merge_profile_options
from song_agent.domains.delivery.distribution_templates import TemplatePackStore as TemplatePackStore, template_rules as template_rules, template_summary as template_summary
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
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

DistributionStore = _make_deferred_global('DistributionStore')
DistributionTarget = _make_deferred_global('DistributionTarget')
DistributionValidationError = _make_deferred_global('DistributionValidationError')
ch = _make_deferred_global('ch')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global DistributionStore, DistributionTarget, DistributionValidationError, ch, item
    DistributionStore = namespace.get('DistributionStore', DistributionStore)
    DistributionTarget = namespace.get('DistributionTarget', DistributionTarget)
    DistributionValidationError = namespace.get('DistributionValidationError', DistributionValidationError)
    ch = namespace.get('ch', ch)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_ROOT_NAME = "distribution"
DISTRIBUTION_TARGET_SCHEMA_VERSION = 1
DISTRIBUTION_TARGET_STATUSES = {"draft", "qa_failed", "qa_warning", "qa_passed", "exported", "signed", "archived"}
SIGNED_DISTRIBUTION_STATUSES = {"signed", "force_signed"}




def distribution_target_summary(target: DistributionTarget | DomainDocument | None) -> DomainDocument:
    data = target.to_dict() if isinstance(target, DistributionTarget) else _as_document(target)
    return sanitize_metadata(
        {
            "target_id": data.get("target_id"),
            "release_id": data.get("release_id"),
            "profile_id": data.get("profile_id"),
            "template_pack_id": data.get("template_pack_id"),
            "template_hash": data.get("template_hash"),
            "template_source": data.get("template_source"),
            "name": data.get("name"),
            "status": data.get("status") or "missing",
            "qa_status": (data.get("latest_qa_summary") or {}).get("status") if isinstance(data.get("latest_qa_summary"), dict) else None,
            "export_status": (data.get("latest_export_summary") or {}).get("status") if isinstance(data.get("latest_export_summary"), dict) else None,
            "package_id": (data.get("latest_export_summary") or {}).get("package_id") if isinstance(data.get("latest_export_summary"), dict) else None,
            "signoff_status": (data.get("latest_signoff_summary") or {}).get("status") if isinstance(data.get("latest_signoff_summary"), dict) else None,
            "updated_at": data.get("updated_at"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def distribution_signoff_summary(record: DomainDocument | None) -> DomainDocument:
    data = _as_document(record)
    return sanitize_metadata(
        {
            "status": data.get("status") or "not_signed",
            "release_id": data.get("release_id"),
            "target_id": data.get("target_id"),
            "package_id": data.get("package_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "qa_source_hash": data.get("qa_source_hash"),
            "export_manifest_hash": data.get("export_manifest_hash"),
            "forced": bool(data.get("forced", False)),
            "encoded_audio_acceptance": _as_document(data.get("encoded_audio_acceptance")),
            "format_decision": _as_document(data.get("format_decision")),
            "rights_clearance": _as_document(data.get("rights_clearance")),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def build_distribution_signoff_record(
    *,
    release_id: str,
    target: DistributionTarget,
    package_id: str,
    qa_report: DomainDocument,
    payload: DomainDocument | None = None,
    export_manifest: DomainDocument | None = None,
    now: str | None = None,
) -> DomainDocument:
    now = now or now_iso()
    payload = payload or {}
    force = bool(payload.get("force", False))
    if force and not str(payload.get("override_reason") or "").strip():
        raise ValueError("override_reason is required when force=true.")
    blockers = qa_report.get("blockers", []) if isinstance(qa_report.get("blockers"), list) else []
    warnings = qa_report.get("warnings", []) if isinstance(qa_report.get("warnings"), list) else []
    if not force and (qa_report.get("status") not in {"passed", "warning"} or blockers):
        raise ValueError("Distribution QA does not allow signoff.")
    record = {
        "schema_version": 1,
        "release_id": release_id,
        "target_id": target.target_id,
        "package_id": package_id,
        "profile_id": target.profile_id,
        "status": "force_signed" if force else "signed",
        "signed_at": now,
        "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
        "qa_source_hash": qa_report.get("source_hash"),
        "distribution_source_hash": qa_report.get("source_hash"),
        "export_manifest_hash": stable_hash(export_manifest) if isinstance(export_manifest, dict) and export_manifest else None,
        "forced": force,
        "override_reason": _safe_text(payload.get("override_reason"), 500) if force else None,
        "acknowledged_blockers": blockers if force else [],
        "acknowledged_warnings": warnings,
        "encoded_audio_acceptance": _as_document(payload.get("encoded_audio_acceptance")),
        "format_decision": _as_document(payload.get("format_decision")),
        "rights_clearance": _as_document(payload.get("rights_clearance")),
        "notes": _safe_text(payload.get("notes"), 2000),
    }
    return sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def distribution_signoff_history_event(record: DomainDocument, *, reason: str, now: str | None = None) -> DomainDocument:
    return sanitize_metadata(
        {
            "timestamp": now or now_iso(),
            "event": "distribution_signoff_reset",
            "reason": sanitize_sensitive_text(str(reason or ""))[:500],
            "previous_summary": distribution_signoff_summary(record),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def remove_distribution_dir(store: DistributionStore, release_id: str) -> None:
    path = store.distribution_dir(release_id)
    root = store.release_store.release_dir(release_id).resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise DistributionValidationError("Refusing to operate outside release distribution boundaries.") from exc
    if path.exists():
        shutil.rmtree(path)

def _stale_summary(summary: DomainDocument | None, reason: str) -> DomainDocument:
    data = dict(summary or {})
    if data:
        data["stale"] = True
        data["status"] = "stale"
        data["stale_reason"] = reason
    return sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _safe_id(value: object, *, default: str) -> str:
    text = str(value or default).strip().lower().replace(" ", "_")
    if not text:
        return default
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in text):
        raise DistributionValidationError("Identifier contains unsupported characters.")
    return text[:80]

def _optional_id(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in text):
        raise DistributionValidationError("Identifier contains unsupported characters.")
    return text[:80]

def _optional_text(value: object, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None

def _merge_target_options(profile: DomainDocument, rules: DomainDocument, overrides: DomainDocument | None = None) -> DomainDocument:
    base = merge_profile_options(profile, rules)
    overrides = _as_document(overrides)
    allowed = set(base) | {"artwork_id", "submission_note"}
    for key, value in overrides.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            base[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            base[key] = value
    return sanitize_metadata(base, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def _validate_target_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("target-") or not text.removeprefix("target-").isdigit():
        raise DistributionValidationError("Invalid distribution target id.")
    return text

def _validate_package_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("package-") or not text.removeprefix("package-").isdigit():
        raise DistributionValidationError("Invalid distribution package id.")
    return text
