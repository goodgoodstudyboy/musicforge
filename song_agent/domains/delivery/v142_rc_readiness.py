# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_float as _as_float, as_list as _as_list, document_or as _document_or
import json as json
import re as re
from pathlib import Path as Path
from song_agent.domains.studio.assets import AssetStore as AssetStore
from song_agent.domains.studio.context_packs import ContextPackStore as ContextPackStore
from song_agent.domains.studio.library_index import asset_source_hash as asset_source_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.studio.references import ReferenceStore as ReferenceStore
from song_agent.domains.delivery.release_metadata import read_release_metadata as read_release_metadata
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

RIGHTS_BLOCKED_KEYS = _make_deferred_global('RIGHTS_BLOCKED_KEYS')
SOURCE_COVERAGE_SAFE_STATUSES = _make_deferred_global('SOURCE_COVERAGE_SAFE_STATUSES')
_context_pack_required_source = _make_deferred_global('_context_pack_required_source')
_list = _make_deferred_global('_list')
_looks_like_local_path = _make_deferred_global('_looks_like_local_path')
_metadata_credit_names = _make_deferred_global('_metadata_credit_names')
_metadata_required_source = _make_deferred_global('_metadata_required_source')
_norm_name = _make_deferred_global('_norm_name')
_normalize_required_source = _make_deferred_global('_normalize_required_source')
_read_json_default = _make_deferred_global('_read_json_default')
_safe_id = _make_deferred_global('_safe_id')
_text = _make_deferred_global('_text')
_used_by_version = _make_deferred_global('_used_by_version')
name = _make_deferred_global('name')
rights_track_integrity_ok = _make_deferred_global('rights_track_integrity_ok')

def bind_globals(namespace: dict[str, object]) -> None:
    global RIGHTS_BLOCKED_KEYS, SOURCE_COVERAGE_SAFE_STATUSES, _context_pack_required_source, _list, _looks_like_local_path, _metadata_credit_names, _metadata_required_source
    global _norm_name, _normalize_required_source, _read_json_default, _safe_id, _text, _used_by_version, name, rights_track_integrity_ok
    RIGHTS_BLOCKED_KEYS = namespace.get('RIGHTS_BLOCKED_KEYS', RIGHTS_BLOCKED_KEYS)
    SOURCE_COVERAGE_SAFE_STATUSES = namespace.get('SOURCE_COVERAGE_SAFE_STATUSES', SOURCE_COVERAGE_SAFE_STATUSES)
    _context_pack_required_source = namespace.get('_context_pack_required_source', _context_pack_required_source)
    _list = namespace.get('_list', _list)
    _looks_like_local_path = namespace.get('_looks_like_local_path', _looks_like_local_path)
    _metadata_credit_names = namespace.get('_metadata_credit_names', _metadata_credit_names)
    _metadata_required_source = namespace.get('_metadata_required_source', _metadata_required_source)
    _norm_name = namespace.get('_norm_name', _norm_name)
    _normalize_required_source = namespace.get('_normalize_required_source', _normalize_required_source)
    _read_json_default = namespace.get('_read_json_default', _read_json_default)
    _safe_id = namespace.get('_safe_id', _safe_id)
    _text = namespace.get('_text', _text)
    _used_by_version = namespace.get('_used_by_version', _used_by_version)
    name = namespace.get('name', name)
    rights_track_integrity_ok = namespace.get('rights_track_integrity_ok', rights_track_integrity_ok)
    _bind_deferred_defaults(namespace)


RIGHTS_SCHEMA_VERSION = 1
RIGHTS_REPORT_INTEGRITY_EXCLUDE = {"integrity_hash", "integrity_ok", "stale", "stale_reasons", "current_source_hash"}
RIGHTS_TRACK_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons"}
RIGHTS_SUMMARY_INTEGRITY_EXCLUDE = {"summary_hash"}
CONTRIBUTOR_ROLES_REQUIRING_SPLITS = {"composer", "lyricist"}
SOURCE_BLOCKING_STATUSES = {"uncleared", "blocked", "unknown", "pending"}
SOURCE_SAFE_STATUSES = {"cleared", "waived", "owned", "public_domain", "original"}




def rights_report_source_hash(release: DomainDocument, metadata: DomainDocument, rows: list[DomainDocument], parties: list[DomainDocument]) -> str:
    return stable_hash(
        sanitize_metadata(
            {
                "release": {
                    "release_id": release.get("release_id"),
                    "name": release.get("name"),
                    "primary_artist": release.get("primary_artist"),
                    "tracks": [
                        {
                            "track_id": track.get("track_id"),
                            "disc_number": track.get("disc_number"),
                            "track_number": track.get("track_number"),
                            "title": track.get("title"),
                            "artist": track.get("artist"),
                            "project_id": track.get("project_id"),
                            "version_id": track.get("version_id"),
                        }
                        for track in release.get("tracks", [])
                        if isinstance(track, dict)
                    ],
                },
                "metadata_hash": stable_hash(metadata or {}),
                "track_rows": [{key: row.get(key) for key in ("track_id", "status", "source_hash", "rights_track_hash")} for row in rows],
                "parties_hash": stable_hash({"parties": parties}),
            },
            blocked_keys=RIGHTS_BLOCKED_KEYS,
        )
    )

def rights_report_integrity_hash(report: DomainDocument) -> str:
    payload = {key: value for key, value in report.items() if key not in RIGHTS_REPORT_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=RIGHTS_BLOCKED_KEYS))

def rights_report_integrity_ok(report: DomainDocument) -> bool:
    expected = str((report or {}).get("integrity_hash") or "")
    return bool(expected) and expected == rights_report_integrity_hash(report)

def rights_summary_hash(summary: DomainDocument) -> str:
    payload = {key: value for key, value in summary.items() if key not in RIGHTS_SUMMARY_INTEGRITY_EXCLUDE}
    return stable_hash(sanitize_metadata(payload, blocked_keys=RIGHTS_BLOCKED_KEYS))

def rights_summary_integrity_ok(summary: DomainDocument) -> bool:
    expected = str((summary or {}).get("summary_hash") or "")
    return bool(expected) and expected == rights_summary_hash(summary)

def rights_export_summary(report: DomainDocument, *, exported_tracks: list[DomainDocument]) -> DomainDocument:
    summary = {
        "schema_version": RIGHTS_SCHEMA_VERSION,
        "status": report.get("status") or "missing",
        "summary_path": "rights/summary.json",
        "report_path": "rights/report.json",
        "report_hash": report.get("integrity_hash"),
        "source_hash": report.get("source_hash"),
        "track_count": report.get("track_count", 0),
        "manual_cleared_track_count": report.get("manual_cleared_track_count", 0),
        "failed_track_count": report.get("failed_track_count", 0),
        "warning_track_count": report.get("warning_track_count", 0),
        "tracks": exported_tracks,
    }
    summary["summary_hash"] = rights_summary_hash(summary)
    return sanitize_metadata(summary, blocked_keys=RIGHTS_BLOCKED_KEYS)

def rights_redaction_findings(value: object, *, path: str = "rights") -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in RIGHTS_BLOCKED_KEYS:
                findings.append({"path": path, "kind": "blocked_key", "key": str(key)})
            findings.extend(rights_redaction_findings(item, path=f"{path}.{key}"))
        return findings
    if isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(rights_redaction_findings(item, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, str):
        for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                findings.append({"path": path, "kind": "sensitive_value"})
        if _looks_like_local_path(value):
            findings.append({"path": path, "kind": "local_path_value"})
    return findings

def verify_release_rights_package_evidence(
    *,
    manifest_summary: DomainDocument,
    summary: DomainDocument,
    report: DomainDocument,
    tracks: dict[str, DomainDocument],
    required: bool,
) -> list[str]:
    failures: list[str] = []
    if required and not manifest_summary:
        failures.append("manifest_rights_missing")
        return failures
    if not summary:
        failures.append("summary_missing")
        return failures
    if str(manifest_summary.get("summary_hash") or "") != str(summary.get("summary_hash") or ""):
        failures.append("summary_hash")
    if not rights_summary_integrity_ok(summary):
        failures.append("summary_integrity")
    if not report:
        failures.append("report_missing")
    else:
        if str(summary.get("report_hash") or "") != str(report.get("integrity_hash") or ""):
            failures.append("report_hash")
        if not rights_report_integrity_ok(report):
            failures.append("report_integrity")
        if required and report.get("status") != "passed":
            failures.append(f"report_status:{report.get('status')}")
    for row in summary.get("tracks", []) if isinstance(summary.get("tracks"), list) else []:
        if not isinstance(row, dict):
            continue
        track_id = str(row.get("track_id") or "")
        record = tracks.get(track_id)
        if not record:
            failures.append(f"{track_id}:track_record_missing")
            continue
        if str(row.get("payload_hash") or "") != str(record.get("integrity_hash") or ""):
            failures.append(f"{track_id}:track_hash")
        if not rights_track_integrity_ok(record):
            failures.append(f"{track_id}:track_integrity")
    if required and not summary.get("tracks"):
        failures.append("track_records_missing")
    if rights_redaction_findings({"summary": summary, "report": report, "tracks": list(tracks.values())}):
        failures.append("redaction")
    return sorted(set(failures))

def verify_rights_summary_evidence(*, manifest_summary: DomainDocument, summary: DomainDocument, required: bool) -> list[str]:
    failures: list[str] = []
    if required and not manifest_summary:
        failures.append("manifest_rights_missing")
        return failures
    if not summary:
        failures.append("summary_missing")
        return failures
    if str(manifest_summary.get("summary_hash") or "") != str(summary.get("summary_hash") or ""):
        failures.append("summary_hash")
    if not rights_summary_integrity_ok(summary):
        failures.append("summary_integrity")
    if required and summary.get("status") != "passed":
        failures.append(f"summary_status:{summary.get('status')}")
    if rights_redaction_findings(summary):
        failures.append("redaction")
    return sorted(set(failures))

def required_source_usages_for_track(
    track: object,
    *,
    release_store: ReleaseStore,
    asset_store: AssetStore,
    reference_store: ReferenceStore,
    context_pack_store: ContextPackStore,
) -> list[DomainDocument]:
    project_id = str(getattr(track, "project_id", "") or "")
    version_id = str(getattr(track, "version_id", "") or "")
    sources: dict[str, DomainDocument] = {}

    def add(source: DomainDocument) -> None:
        normalized = _normalize_required_source(source)
        key = _source_coverage_key(normalized)
        if not key:
            return
        existing = sources.get(key)
        if existing:
            merged_detected = sorted(set(_list(existing.get("detected_in")) + _list(normalized.get("detected_in"))))
            existing["detected_in"] = merged_detected
            existing.setdefault("name", normalized.get("name"))
            if existing.get("source_status") == "current" and normalized.get("source_status") != "current":
                existing["source_status"] = normalized.get("source_status")
                existing["stale_reasons"] = sorted(set(_list(existing.get("stale_reasons")) + _list(normalized.get("stale_reasons"))))
            return
        sources[key] = normalized

    project_export = _project_export_snapshot(release_store, project_id)
    final_manifest = _final_export_manifest(release_store, project_id)
    version = _project_version(release_store, project_id, version_id)
    version_run_dir = Path(getattr(version, "output_dir", "") or "") if version is not None else None

    for ref in _list(final_manifest.get("asset_refs")):
        if isinstance(ref, dict):
            add(_asset_required_source(ref, asset_store=asset_store, detected_in="final_export.asset_refs", version_id=version_id))
    for ref in _list(final_manifest.get("reference_refs")):
        if isinstance(ref, dict):
            add(_reference_required_source(ref, reference_store=reference_store, detected_in="final_export.reference_refs", version_id=version_id))
    context_pack = _as_document(final_manifest.get("context_pack"))
    if context_pack and context_pack.get("pack_id"):
        add(_context_pack_required_source(context_pack, context_pack_store=context_pack_store, detected_in="final_export.context_pack", version_id=version_id))
    edit = _as_document(final_manifest.get("edit"))
    for item in _list(edit.get("clip_inserts")):
        if isinstance(item, dict):
            add(_metadata_required_source(item, source_type="editor_clip", detected_in="final_export.edit.clip_inserts", version_id=version_id))
    for item in _list(edit.get("template_inserts")):
        if isinstance(item, dict):
            add(_metadata_required_source(item, source_type="template", detected_in="final_export.edit.template_inserts", version_id=version_id))
    for key in ("review_provider_patch", "review_candidate_source", "review_candidate", "review_judge"):
        value = edit.get(key)
        if isinstance(value, dict) and value:
            add(_metadata_required_source(value, source_type="provider_provenance", detected_in=f"final_export.edit.{key}", version_id=version_id))

    for ref in _list(project_export.get("asset_refs")):
        if isinstance(ref, dict) and _used_by_version(ref, version_id):
            add(_asset_required_source(ref, asset_store=asset_store, detected_in="project_export.asset_refs", version_id=version_id))
    for ref in _list(project_export.get("reference_refs")):
        if isinstance(ref, dict) and (_used_by_version(ref, version_id) or ref.get("linked_to_project")):
            add(_reference_required_source(ref, reference_store=reference_store, detected_in="project_export.reference_refs", version_id=version_id))
    for pack in _list(project_export.get("context_packs")):
        if isinstance(pack, dict) and _used_by_version(pack, version_id):
            add(_context_pack_required_source(pack, context_pack_store=context_pack_store, detected_in="project_export.context_packs", version_id=version_id))
    for exported_version in _list(project_export.get("versions")):
        if not isinstance(exported_version, dict) or str(exported_version.get("version_id") or "") != version_id:
            continue
        exported_edit = _as_document(exported_version.get("edit"))
        for item in _list(exported_edit.get("clip_inserts")):
            if isinstance(item, dict):
                add(_metadata_required_source(item, source_type="editor_clip", detected_in="project_export.version.edit.clip_inserts", version_id=version_id))
        for item in _list(exported_edit.get("template_inserts")):
            if isinstance(item, dict):
                add(_metadata_required_source(item, source_type="template", detected_in="project_export.version.edit.template_inserts", version_id=version_id))
        for key in ("review_provider_patch", "review_candidate_source", "review_candidate", "review_judge"):
            value = exported_edit.get(key)
            if isinstance(value, dict) and value:
                add(_metadata_required_source(value, source_type="provider_provenance", detected_in=f"project_export.version.edit.{key}", version_id=version_id))

    if version_run_dir is not None:
        data_dir = version_run_dir / "data"
        asset_snapshot = _read_json_default(data_dir / "asset-refs.json", {})
        for ref in _list(asset_snapshot.get("asset_refs")):
            if isinstance(ref, dict):
                add(_asset_required_source(ref, asset_store=asset_store, detected_in="job_artifacts.asset_refs", version_id=version_id))
        reference_snapshot = _read_json_default(data_dir / "reference-refs.json", {})
        for ref in _list(reference_snapshot.get("reference_refs")):
            if isinstance(ref, dict):
                add(_reference_required_source(ref, reference_store=reference_store, detected_in="job_artifacts.reference_refs", version_id=version_id))
        context_snapshot = _read_json_default(data_dir / "context-pack.json", {})
        if context_snapshot.get("pack_id"):
            add(_context_pack_required_source(context_snapshot, context_pack_store=context_pack_store, detected_in="job_artifacts.context_pack", version_id=version_id))
        edit_snapshot = _read_json_default(data_dir / "edit-metadata.json", {})
        for item in _list(edit_snapshot.get("clip_inserts")):
            if isinstance(item, dict):
                add(_metadata_required_source(item, source_type="editor_clip", detected_in="job_artifacts.edit.clip_inserts", version_id=version_id))
        for item in _list(edit_snapshot.get("template_inserts")):
            if isinstance(item, dict):
                add(_metadata_required_source(item, source_type="template", detected_in="job_artifacts.edit.template_inserts", version_id=version_id))
        for key in ("provider_patch", "review_provider_patch", "review_candidate_source", "review_candidate", "review_judge"):
            value = edit_snapshot.get(key)
            if isinstance(value, dict) and value:
                add(_metadata_required_source(value, source_type="provider_provenance", detected_in=f"job_artifacts.edit.{key}", version_id=version_id))

    return [sources[key] for key in sorted(sources)]

def _evaluate_track(record: DomainDocument, *, party_map: dict[str, DomainDocument], metadata_track: DomainDocument) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    contributors = [item for item in _list(record.get("contributors")) if isinstance(item, dict)]
    if not contributors:
        failures.append("contributors_missing")
    for contributor in contributors:
        party_id = str(contributor.get("party_id") or "")
        if not party_id or party_id not in party_map:
            failures.append(f"party_missing:{party_id or 'missing'}")
        if not _text(contributor.get("role"), 80):
            failures.append("contributor_role_missing")
    roles = {str(item.get("role") or "").lower() for item in contributors}
    if "composer" not in roles:
        failures.append("composer_missing")
    instrumental = bool(record.get("instrumental", metadata_track.get("instrumental", False)))
    lyrics = _text(metadata_track.get("lyrics"), 200000)
    if lyrics and not instrumental and "lyricist" not in roles:
        failures.append("lyricist_missing_for_lyrics")
    for role in CONTRIBUTOR_ROLES_REQUIRING_SPLITS:
        role_rows = [item for item in contributors if str(item.get("role") or "").lower() == role]
        if not role_rows:
            continue
        total = sum(float(item.get("share") or item.get("split_percent") or 0) for item in role_rows)
        if abs(total - 100.0) > 0.01:
            failures.append(f"{role}_split_not_100")
    metadata_credits = _metadata_credit_names(metadata_track)
    if metadata_credits and not bool(record.get("metadata_credits_waived", False)):
        rights_names = {_norm_name(party_map.get(str(item.get("party_id") or ""), {}).get("public_credit_name") or party_map.get(str(item.get("party_id") or ""), {}).get("display_name")) for item in contributors}
        for role, names in metadata_credits.items():
            if role in {"composer", "lyricist"}:
                missing = sorted(name for name in names if name and name not in rights_names)
                if missing:
                    failures.append(f"metadata_credit_missing_in_rights:{role}")
    for source in _list(record.get("source_usages")):
        if not isinstance(source, dict):
            continue
        status = str(source.get("status") or "unknown").lower()
        risk = str(source.get("risk_level") or source.get("risk") or "medium").lower()
        if status in SOURCE_BLOCKING_STATUSES and risk in {"medium", "high", "critical"}:
            failures.append(f"source_uncleared:{source.get('source_id') or source.get('name') or 'source'}")
        if status not in SOURCE_SAFE_STATUSES and status not in SOURCE_BLOCKING_STATUSES:
            warnings.append(f"source_unknown_status:{status}")
    declared_sources = _declared_source_coverage(record.get("source_usages"))
    for required in _list(record.get("required_source_usages")):
        if not isinstance(required, dict):
            continue
        source_id = str(required.get("source_id") or "").strip()
        source_type = str(required.get("source_type") or "source").strip().lower()
        source_status = str(required.get("source_status") or "current").strip().lower()
        key = _source_coverage_key(required)
        declared = declared_sources.get(key)
        if source_status in {"missing", "hidden", "stale", "blocked"}:
            failures.append(f"required_source_{source_status}:{source_id or source_type}")
        if not declared:
            failures.append(f"required_source_missing:{source_type}:{source_id or 'source'}")
            continue
        declared_status = str(declared.get("status") or "unknown").strip().lower()
        if declared_status not in SOURCE_COVERAGE_SAFE_STATUSES:
            failures.append(f"required_source_uncleared:{source_type}:{source_id or 'source'}")
    manual = _as_document(record.get("manual_clearance"))
    if manual.get("status") not in {"accepted", "waived"}:
        failures.append("manual_clearance_missing")
    if manual.get("review_mode") != "manual":
        failures.append("manual_clearance_not_manual")
    if not _text(manual.get("confirmed_by"), 160):
        failures.append("manual_clearance_reviewer_missing")
    if manual.get("status") == "waived" and not _text(manual.get("waiver_reason"), 1000):
        failures.append("waiver_reason_missing")
    return failures, warnings

def _declared_source_coverage(sources: object) -> dict[str, DomainDocument]:
    coverage: dict[str, DomainDocument] = {}
    for source in _list(sources):
        if not isinstance(source, dict):
            continue
        key = _source_coverage_key(source)
        if key:
            coverage[key] = source
    return coverage

def _source_coverage_key(source: DomainDocument) -> str:
    source_id = str(source.get("source_id") or "").strip().lower()
    source_type = str(source.get("source_type") or source.get("type") or "").strip().lower()
    if not source_id:
        return ""
    return f"{source_type}:{source_id}"

def _project_export_snapshot(release_store: ReleaseStore, project_id: str) -> DomainDocument:
    if not project_id:
        return {}
    try:
        return release_store.project_store.project_export_snapshot(project_id)
    except (OSError, ValueError, TypeError, FileNotFoundError):
        return {}

def _final_export_manifest(release_store: ReleaseStore, project_id: str) -> DomainDocument:
    if not project_id:
        return {}
    try:
        project_dir = release_store.project_store.project_dir(project_id)
        path = project_dir / "final-export" / "manifest.json"
        if path.exists():
            data = read_json(path)
            return _as_document(data)
    except (OSError, ValueError, TypeError, FileNotFoundError):
        return {}
    return {}

def _project_version(release_store: ReleaseStore, project_id: str, version_id: str) -> object | None:
    if not project_id or not version_id:
        return None
    try:
        document = release_store.project_store.get_project(project_id)
    except (OSError, ValueError, TypeError, FileNotFoundError):
        return None
    return next((version for version in document.versions if getattr(version, "version_id", "") == version_id), None)

def _asset_required_source(ref: DomainDocument, *, asset_store: AssetStore, detected_in: str, version_id: str) -> DomainDocument:
    asset_id = _safe_id(str(ref.get("asset_id") or ""), "asset")
    status = "current"
    stale_reasons: list[str] = []
    current_hash = ""
    try:
        asset = asset_store.read_asset(asset_id)
        current_hash = asset_source_hash(asset)
        if asset.hidden:
            status = "hidden"
            stale_reasons.append("asset_hidden")
        snapshot_hash = str(ref.get("source_hash") or "")
        if snapshot_hash and snapshot_hash != current_hash:
            status = "stale"
            stale_reasons.append("asset_source_hash_changed")
    except (OSError, ValueError, TypeError, FileNotFoundError):
        status = "missing"
        stale_reasons.append("asset_missing")
    return {
        "source_id": asset_id,
        "source_type": "asset",
        "name": _text(ref.get("name") or asset_id, 180),
        "role": _text(ref.get("role") or ",".join(str(item) for item in _list(ref.get("roles")) if str(item).strip()), 120),
        "source_status": status,
        "source_hash": current_hash or str(ref.get("source_hash") or ""),
        "detected_in": [detected_in],
        "used_by_versions": sorted(set([version_id, *[str(item) for item in _list(ref.get("used_by_versions")) if str(item).strip()]])),
        "stale_reasons": stale_reasons,
    }

def _reference_required_source(ref: DomainDocument, *, reference_store: ReferenceStore, detected_in: str, version_id: str) -> DomainDocument:
    reference_id = _safe_id(str(ref.get("reference_id") or ""), "ref")
    status = "current"
    stale_reasons: list[str] = []
    current_hash = ""
    try:
        reference = reference_store.read_reference(reference_id)
        current_hash = reference.sha256
        if reference.hidden:
            status = "hidden"
            stale_reasons.append("reference_hidden")
        snapshot_hash = str(ref.get("source_hash") or ref.get("sha256") or "")
        if snapshot_hash and snapshot_hash != current_hash:
            status = "stale"
            stale_reasons.append("reference_sha256_changed")
    except (OSError, ValueError, TypeError, FileNotFoundError):
        status = "missing"
        stale_reasons.append("reference_missing")
    return {
        "source_id": reference_id,
        "source_type": "reference",
        "name": _text(ref.get("title") or ref.get("name") or reference_id, 180),
        "role": _text(ref.get("role") or ",".join(str(item) for item in _list(ref.get("roles")) if str(item).strip()), 120),
        "source_status": status,
        "source_hash": current_hash or str(ref.get("source_hash") or ref.get("sha256") or ""),
        "detected_in": [detected_in],
        "used_by_versions": sorted(set([version_id, *[str(item) for item in _list(ref.get("used_by_versions")) if str(item).strip()]])),
        "stale_reasons": stale_reasons,
    }
