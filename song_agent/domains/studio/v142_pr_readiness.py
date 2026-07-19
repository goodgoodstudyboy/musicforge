# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Protocol as Protocol
from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, score_song_plan as score_song_plan
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan

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

ProjectDocument = _make_deferred_global('ProjectDocument')
ProjectVersion = _make_deferred_global('ProjectVersion')
_sanitize_asset_metadata = _make_deferred_global('_sanitize_asset_metadata')
item = _make_deferred_global('item')
key = _make_deferred_global('key')
note = _make_deferred_global('note')
section = _make_deferred_global('section')

def bind_globals(namespace: dict[str, object]) -> None:
    global ProjectDocument, ProjectVersion, _sanitize_asset_metadata, item, key, note, section
    ProjectDocument = namespace.get('ProjectDocument', ProjectDocument)
    ProjectVersion = namespace.get('ProjectVersion', ProjectVersion)
    _sanitize_asset_metadata = namespace.get('_sanitize_asset_metadata', _sanitize_asset_metadata)
    item = namespace.get('item', item)
    key = namespace.get('key', key)
    note = namespace.get('note', note)
    section = namespace.get('section', section)
    _bind_deferred_defaults(namespace)


PROJECT_STATUSES = {"active", "archived", "finalized"}
VARIANT_TYPES = {
    "original",
    "style_variation",
    "tempo_key_variation",
    "lyrics_variation",
    "arrangement_variation",
    "quality_repair",
    "manual",
    "section_edit",
    "track_edit",
    "lyrics_edit",
    "melody_edit",
    "arrangement_edit",
    "provider_edit",
    "manual_editor_edit",
    "mix_control_edit",
    "audio_revision_mix_edit",
}
QUALITY_GATE_STATUSES = {
    "not_evaluated",
    "passed",
    "warning",
    "failed",
    "missing_plan",
    "error",
}
VERSION_STATUSES = {
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
    "stalled",
    "missing_job",
}
BLOCKED_ASSET_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "raw_provider_response",
    "secret",
    "token",
}




class JobLike(Protocol):
    job_id: str
    title: str
    output_dir: str
    status: str
    created_at: str
    updated_at: str
    summary: DomainDocument
    input_payload: DomainDocument
    generation_mode: str
    pipeline_mode: str
    artifacts: dict[str, str]

class ProjectSummaryProvider(Protocol):
    def __call__(
        self,
        project_dir: Path,
        document: ProjectDocument,
    ) -> DomainDocument: ...

def _empty_project_summary(
    project_dir: Path,
    document: ProjectDocument,
) -> DomainDocument:
    return {}

def quality_score_for_run(run_dir: Path) -> int | None:
    plan_path = run_dir / "data" / "song-plan.json"
    if not plan_path.exists():
        return None
    try:
        plan = SongPlan.from_dict(read_json(plan_path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if plan.quality and plan.quality.scores:
        return plan.quality.scores.overall
    try:
        return score_song_plan(plan).overall
    except (ValueError, TypeError):
        return None

def now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()

def _artifact_exists(job: JobLike, artifact_key: str, fallback: Path) -> bool:
    artifact = job.artifacts.get(artifact_key)
    if artifact and Path(artifact).exists():
        return True
    return fallback.exists()

def _find_version(document: ProjectDocument, version_id: str) -> ProjectVersion:
    version_id = _validate_version_id(version_id)
    for version in document.versions:
        if version.version_id == version_id:
            return version
    raise FileNotFoundError(version_id)

def _version_or_none(document: ProjectDocument, version_id: str | None) -> DomainDocument | None:
    if not version_id:
        return None
    try:
        return _find_version(document, version_id).to_dict()
    except FileNotFoundError:
        return None

def _version_ref(version: ProjectVersion) -> DomainDocument:
    return {
        "version_id": version.version_id,
        "job_id": version.job_id,
        "name": version.name,
        "status": version.status,
        "parent_version_id": version.parent_version_id,
        "variant_type": version.variant_type,
    }

def _lineage_info(version: ProjectVersion) -> DomainDocument:
    return {
        "parent_version_id": version.parent_version_id,
        "variant_type": version.variant_type,
        "change_summary": version.change_summary,
    }

def _artifact_flags(version: ProjectVersion) -> dict[str, bool]:
    return {
        "midi": version.has_midi,
        "audio": version.has_audio,
        "stems": version.has_stems,
        "stem_audio": version.has_stem_audio,
    }

def _edit_info(version: ProjectVersion) -> DomainDocument | None:
    path = Path(version.output_dir) / "data" / "edit-metadata.json"
    if not path.exists():
        return None
    try:
        metadata = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return {
        "schema_version": metadata.get("schema_version"),
        "edit_source": metadata.get("edit_source"),
        "edit_type": metadata.get("edit_type"),
        "target": metadata.get("target") or {},
        "instruction": metadata.get("instruction") or "",
        "preserve": metadata.get("preserve") or [],
        "strength": metadata.get("strength"),
        "preview_id": metadata.get("preview_id"),
        "operation_count": metadata.get("operation_count"),
        "changed_sections": metadata.get("changed_sections") or [],
        "changed_tracks": metadata.get("changed_tracks") or [],
        "clip_inserts": metadata.get("clip_inserts") or [],
        "template_inserts": metadata.get("template_inserts") or [],
        "audition_summary": _as_document(metadata.get("audition_summary")),
        "review_edit": _as_document(metadata.get("review_edit")),
        "review_summary": _as_document(metadata.get("review_summary")),
        "review_task": _as_document(metadata.get("review_task")),
        "review_candidate": _as_document(metadata.get("review_candidate")),
        "review_candidate_source": _as_document(metadata.get("review_candidate_source")),
        "review_provider_patch": _as_document(metadata.get("review_provider_patch")),
        "review_decision": _as_document(metadata.get("review_decision")),
        "review_sprint": _as_document(metadata.get("review_sprint")),
        "review_sprint_recommendation": _as_document(metadata.get("review_sprint_recommendation")),
        "review_sprint_action_queue": _as_document(metadata.get("review_sprint_action_queue")),
        "review_judge": _as_document(metadata.get("review_judge")),
        "review_candidate_intents": _as_list(metadata.get("review_candidate_intents")),
        "summary": metadata.get("summary") or {},
        "structure": metadata.get("structure") or {},
        "warnings": metadata.get("warnings") or [],
    }

def _mix_info(version: ProjectVersion) -> DomainDocument:
    run_dir = Path(version.output_dir)
    summary: DomainDocument = {}
    state_path = run_dir / "data" / "mix-state.json"
    patch_path = run_dir / "data" / "mix-patch.json"
    stem_health_path = run_dir / "stems" / "stem-health.json"
    if state_path.exists():
        try:
            from song_agent.domains.quality.mix_controls import mix_state_hash, mix_state_integrity_ok

            state = read_json(state_path)
            ok = mix_state_integrity_ok(state)
            summary["mix_state"] = {"exists": True, "integrity_ok": ok, "mix_state_hash": mix_state_hash(state) if ok else None}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            summary["mix_state"] = {"exists": True, "integrity_ok": False}
    if patch_path.exists():
        try:
            from song_agent.domains.quality.mix_controls import mix_patch_hash, mix_patch_integrity_ok

            patch = read_json(patch_path)
            ok = mix_patch_integrity_ok(patch)
            summary["mix_patch"] = {
                "exists": True,
                "patch_id": patch.get("patch_id"),
                "operation_count": len(patch.get("operations", [])) if isinstance(patch.get("operations"), list) else 0,
                "integrity_ok": ok,
                "mix_patch_hash": mix_patch_hash(patch) if ok else None,
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            summary["mix_patch"] = {"exists": True, "integrity_ok": False}
    if stem_health_path.exists():
        try:
            from song_agent.domains.creation.stem_health import stem_health_integrity_ok, stem_health_summary

            report = read_json(stem_health_path)
            summary["stem_health"] = {**stem_health_summary(report), "integrity_ok": stem_health_integrity_ok(report)}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            summary["stem_health"] = {"status": "invalid", "integrity_ok": False}
    return summary

def _section_info(version: ProjectVersion) -> dict[str, DomainDocument]:
    plan = _version_song_plan(version)
    if plan is None:
        return {}
    return {
        section.name: {
            "chords": list(section.chords),
            "lyrics": section.lyrics,
        }
        for section in plan.sections
    }

def _track_info(version: ProjectVersion) -> dict[str, DomainDocument]:
    plan = _version_song_plan(version)
    if plan is None:
        return {}
    return {
        track.name: {
            "instrument": track.instrument,
            "note_count": len(track.notes),
            "average_velocity": _average_velocity(track),
        }
        for track in plan.tracks
    }

def _version_song_plan(version: ProjectVersion) -> SongPlan | None:
    path = Path(version.output_dir) / "data" / "song-plan.json"
    if not path.exists():
        return None
    try:
        return SongPlan.from_dict(read_json(path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None

def _average_velocity(track: object) -> float:
    if not track.notes:
        return 0.0
    return round(sum(note.velocity for note in track.notes) / len(track.notes), 2)

def _diff_dict(left: DomainDocument, right: DomainDocument) -> dict[str, DomainDocument]:
    keys = sorted(set(left) | set(right))
    return {
        key: {"left": left.get(key), "right": right.get(key)}
        for key in keys
        if left.get(key) != right.get(key)
    }

def _diff_optional(left: object, right: object) -> DomainDocument:
    if left == right:
        return {}
    return {"left": left, "right": right}

def _validate_project_id(project_id: str) -> str:
    project_id = _clean(project_id)
    if not project_id or slugify(project_id) != project_id:
        raise ValueError("Invalid project_id.")
    return project_id

def _validate_version_id(version_id: str) -> str:
    version_id = _clean(version_id)
    if len(version_id) < 4 or not version_id.startswith("v") or not version_id[1:].isdigit():
        raise ValueError("Invalid version_id.")
    return version_id

def _optional_version_id(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _validate_version_id(str(value))

def _validate_variant_type(value: str) -> str:
    value = _clean(value) or "original"
    if value not in VARIANT_TYPES:
        raise ValueError(f"variant_type must be one of: {', '.join(sorted(VARIANT_TYPES))}.")
    return value

def _version_index(version_id: str) -> int:
    return int(_validate_version_id(version_id)[1:])

def _clean(value: object) -> str:
    return str(value or "").strip()

def _optional_str(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)

def _optional_int(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)

def _collect_project_asset_refs(project_dir: Path, document: ProjectDocument) -> list[DomainDocument]:
    refs: dict[str, DomainDocument] = {}

    def add_ref(ref: DomainDocument, *, version_id: str | None = None, candidate_group_id: str | None = None) -> None:
        asset_id = str(ref.get("asset_id") or "").strip()
        if not asset_id:
            return
        content_summary = _sanitize_asset_metadata(ref.get("content_summary")) if isinstance(ref.get("content_summary"), dict) else {}
        source = _sanitize_asset_metadata(ref.get("source")) if isinstance(ref.get("source"), dict) else {}
        record = refs.setdefault(
            asset_id,
            {
                "asset_id": asset_id,
                "asset_type": str(ref.get("asset_type") or ""),
                "name": str(ref.get("name") or asset_id),
                "roles": [],
                "used_by_versions": [],
                "used_by_candidate_groups": [],
                "content_summary": content_summary,
                "source": source,
            },
        )
        if ref.get("asset_type") and not record.get("asset_type"):
            record["asset_type"] = str(ref.get("asset_type"))
        if ref.get("name") and record.get("name") == asset_id:
            record["name"] = str(ref.get("name"))
        role = str(ref.get("role") or "").strip()
        if role and role not in record["roles"]:
            record["roles"].append(role)
        if content_summary and not record.get("content_summary"):
            record["content_summary"] = content_summary
        if source and not record.get("source"):
            record["source"] = source
        if version_id and version_id not in record["used_by_versions"]:
            record["used_by_versions"].append(version_id)
        if candidate_group_id and candidate_group_id not in record["used_by_candidate_groups"]:
            record["used_by_candidate_groups"].append(candidate_group_id)

    for version in document.versions:
        path = Path(version.output_dir) / "data" / "asset-refs.json"
        if not path.exists():
            continue
        try:
            data = read_json(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        for ref in data.get("asset_refs", []) if isinstance(data, dict) else []:
            if isinstance(ref, dict):
                add_ref(ref, version_id=version.version_id)

    candidate_root = project_dir / "candidate-groups"
    if candidate_root.exists():
        for group_json in candidate_root.glob("*/group.json"):
            try:
                data = read_json(group_json)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            source = data.get("source") if isinstance(data, dict) else None
            if not isinstance(source, dict):
                continue
            for ref in source.get("asset_refs", []):
                if isinstance(ref, dict):
                    add_ref(ref, candidate_group_id=str(data.get("group_id") or group_json.parent.name))

    return sorted(refs.values(), key=lambda item: item["asset_id"])

def _collect_project_reference_refs(project_dir: Path, document: ProjectDocument) -> list[DomainDocument]:
    refs: dict[str, DomainDocument] = {}

    def add_ref(ref: DomainDocument, *, version_id: str | None = None, candidate_group_id: str | None = None, linked: bool = False) -> None:
        reference_id = str(ref.get("reference_id") or "").strip()
        if not reference_id:
            return
        metadata_summary = _sanitize_asset_metadata(ref.get("metadata_summary")) if isinstance(ref.get("metadata_summary"), dict) else {}
        record = refs.setdefault(
            reference_id,
            {
                "reference_id": reference_id,
                "reference_type": str(ref.get("reference_type") or ""),
                "title": str(ref.get("title") or reference_id),
                "roles": [],
                "used_by_versions": [],
                "used_by_candidate_groups": [],
                "linked_to_project": linked,
                "metadata_summary": metadata_summary,
                "analysis_summary": _sanitize_asset_metadata(ref.get("analysis_summary")) if isinstance(ref.get("analysis_summary"), dict) else {},
            },
        )
        if ref.get("reference_type") and not record.get("reference_type"):
            record["reference_type"] = str(ref.get("reference_type"))
        if ref.get("title") and record.get("title") == reference_id:
            record["title"] = str(ref.get("title"))
        role = str(ref.get("role") or "").strip()
        if role and role not in record["roles"]:
            record["roles"].append(role)
        if metadata_summary and not record.get("metadata_summary"):
            record["metadata_summary"] = metadata_summary
        analysis_summary = _sanitize_asset_metadata(ref.get("analysis_summary")) if isinstance(ref.get("analysis_summary"), dict) else {}
        if analysis_summary and not record.get("analysis_summary"):
            record["analysis_summary"] = analysis_summary
        if linked:
            record["linked_to_project"] = True
        if version_id and version_id not in record["used_by_versions"]:
            record["used_by_versions"].append(version_id)
        if candidate_group_id and candidate_group_id not in record["used_by_candidate_groups"]:
            record["used_by_candidate_groups"].append(candidate_group_id)

    reference_root = Path(".musicforge") / "references"
    if reference_root.exists():
        for path in reference_root.glob("*/reference.json"):
            try:
                data = read_json(path)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            linked_project_ids = _as_list(data.get("linked_project_ids")) if isinstance(data, dict) else []
            if document.state.project_id in linked_project_ids:
                add_ref(
                    {
                        "reference_id": data.get("reference_id"),
                        "reference_type": data.get("reference_type"),
                        "title": data.get("title"),
                        "metadata_summary": {
                            "description": data.get("description"),
                            "tags": data.get("tags"),
                            "tempo_bpm": data.get("tempo_bpm"),
                            "key": data.get("key"),
                            "meter": data.get("meter"),
                            "source_note": data.get("source_note"),
                            "license_note": data.get("license_note"),
                            "text_excerpt": data.get("text_excerpt"),
                        },
                    },
                    linked=True,
                )

    for version in document.versions:
        path = Path(version.output_dir) / "data" / "reference-refs.json"
        if not path.exists():
            continue
        try:
            data = read_json(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        for ref in data.get("reference_refs", []) if isinstance(data, dict) else []:
            if isinstance(ref, dict):
                add_ref(ref, version_id=version.version_id)

    candidate_root = project_dir / "candidate-groups"
    if candidate_root.exists():
        for group_json in candidate_root.glob("*/group.json"):
            try:
                data = read_json(group_json)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            source = data.get("source") if isinstance(data, dict) else None
            if not isinstance(source, dict):
                continue
            for ref in source.get("reference_refs", []):
                if isinstance(ref, dict):
                    add_ref(ref, candidate_group_id=str(data.get("group_id") or group_json.parent.name))

    return sorted(refs.values(), key=lambda item: item["reference_id"])
