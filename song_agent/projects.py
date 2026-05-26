from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from song_agent.music_quality import analyze_song_quality
from song_agent.projectio import read_json, slugify, write_json
from song_agent.redaction import sanitize_metadata
from song_agent.schemas.song import SongPlan


PROJECT_ROOT = Path(".musicforge") / "projects"
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
    summary: dict[str, Any]
    input_payload: dict[str, Any]
    generation_mode: str
    pipeline_mode: str
    artifacts: dict[str, str]


@dataclass
class ProjectState:
    project_id: str
    name: str
    description: str = ""
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    hidden: bool = False
    selected_version_id: str | None = None
    final_version_id: str | None = None
    version_count: int = 0
    latest_version_id: str | None = None
    best_quality_version_id: str | None = None
    best_quality_score: int | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "hidden": self.hidden,
            "selected_version_id": self.selected_version_id,
            "final_version_id": self.final_version_id,
            "version_count": self.version_count,
            "latest_version_id": self.latest_version_id,
            "best_quality_version_id": self.best_quality_version_id,
            "best_quality_score": self.best_quality_score,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        created_at = str(data.get("created_at") or now_iso())
        status = str(data.get("status") or "active")
        if status not in PROJECT_STATUSES:
            status = "active"
        return cls(
            project_id=_validate_project_id(str(data.get("project_id") or "")),
            name=str(data.get("name") or data.get("project_id") or "Untitled Project"),
            description=str(data.get("description") or ""),
            status=status,
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
            hidden=bool(data.get("hidden", False)),
            selected_version_id=_optional_str(data.get("selected_version_id")),
            final_version_id=_optional_str(data.get("final_version_id")),
            version_count=int(data.get("version_count", 0) or 0),
            latest_version_id=_optional_str(data.get("latest_version_id")),
            best_quality_version_id=_optional_str(data.get("best_quality_version_id")),
            best_quality_score=_optional_int(data.get("best_quality_score")),
            tags=[str(tag) for tag in data.get("tags", []) if str(tag).strip()],
        )


@dataclass
class ProjectVersion:
    version_id: str
    project_id: str
    index: int
    name: str
    job_id: str
    output_dir: str
    status: str
    created_at: str
    updated_at: str
    request: dict[str, Any] = field(default_factory=dict)
    generation_mode: str = "local"
    pipeline_mode: str = "single"
    summary: dict[str, Any] = field(default_factory=dict)
    quality_score: int | None = None
    has_midi: bool = False
    has_audio: bool = False
    has_stems: bool = False
    has_stem_audio: bool = False
    note: str = ""
    pinned: bool = False
    missing_job: bool = False
    parent_version_id: str | None = None
    variant_type: str = "original"
    change_summary: str = ""
    quality_gate_status: str = "not_evaluated"
    quality_gate_score: int | None = None
    quality_gate_warnings: list[str] = field(default_factory=list)
    final_export_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "project_id": self.project_id,
            "index": self.index,
            "name": self.name,
            "job_id": self.job_id,
            "output_dir": self.output_dir,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request": self.request,
            "generation_mode": self.generation_mode,
            "pipeline_mode": self.pipeline_mode,
            "summary": self.summary,
            "quality_score": self.quality_score,
            "has_midi": self.has_midi,
            "has_audio": self.has_audio,
            "has_stems": self.has_stems,
            "has_stem_audio": self.has_stem_audio,
            "note": self.note,
            "pinned": self.pinned,
            "missing_job": self.missing_job,
            "parent_version_id": self.parent_version_id,
            "variant_type": self.variant_type,
            "change_summary": self.change_summary,
            "quality_gate_status": self.quality_gate_status,
            "quality_gate_score": self.quality_gate_score,
            "quality_gate_warnings": self.quality_gate_warnings,
            "final_export_path": self.final_export_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectVersion":
        created_at = str(data.get("created_at") or now_iso())
        version_id = _validate_version_id(str(data.get("version_id") or "v001"))
        status = str(data.get("status") or "queued")
        if status not in VERSION_STATUSES:
            status = "missing_job" if bool(data.get("missing_job", False)) else "queued"
        variant_type = str(data.get("variant_type") or "original")
        if variant_type not in VARIANT_TYPES:
            variant_type = "manual"
        quality_gate_status = str(data.get("quality_gate_status") or "not_evaluated")
        if quality_gate_status not in QUALITY_GATE_STATUSES:
            quality_gate_status = "not_evaluated"
        return cls(
            version_id=version_id,
            project_id=_validate_project_id(str(data.get("project_id") or "")),
            index=int(data.get("index", _version_index(version_id)) or _version_index(version_id)),
            name=str(data.get("name") or f"Version {_version_index(version_id)}"),
            job_id=str(data.get("job_id") or ""),
            output_dir=str(data.get("output_dir") or ""),
            status=status,
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
            request=dict(data.get("request") or {}),
            generation_mode=str(data.get("generation_mode") or "local"),
            pipeline_mode=str(data.get("pipeline_mode") or "single"),
            summary=dict(data.get("summary") or {}),
            quality_score=_optional_int(data.get("quality_score")),
            has_midi=bool(data.get("has_midi", False)),
            has_audio=bool(data.get("has_audio", False)),
            has_stems=bool(data.get("has_stems", False)),
            has_stem_audio=bool(data.get("has_stem_audio", False)),
            note=str(data.get("note") or ""),
            pinned=bool(data.get("pinned", False)),
            missing_job=bool(data.get("missing_job", status == "missing_job")),
            parent_version_id=_optional_version_id(data.get("parent_version_id")),
            variant_type=variant_type,
            change_summary=str(data.get("change_summary") or ""),
            quality_gate_status=quality_gate_status,
            quality_gate_score=_optional_int(data.get("quality_gate_score")),
            quality_gate_warnings=[str(warning) for warning in data.get("quality_gate_warnings", [])],
            final_export_path=_optional_str(data.get("final_export_path")),
        )


@dataclass
class ProjectDocument:
    state: ProjectState
    versions: list[ProjectVersion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.state.to_dict(),
            "versions": [version.to_dict() for version in self.versions],
        }


class ProjectStore:
    def __init__(self, root: Path | str = PROJECT_ROOT):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()

    def create_project(
        self,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> ProjectDocument:
        clean_name = _clean(name) or "Untitled Project"
        project_dir = self._reserve_project_dir(clean_name)
        now = now_iso()
        document = ProjectDocument(
            state=ProjectState(
                project_id=project_dir.name,
                name=clean_name,
                description=str(description or ""),
                created_at=now,
                updated_at=now,
                tags=[str(tag).strip() for tag in (tags or []) if str(tag).strip()],
            ),
            versions=[],
        )
        self.save_project(document)
        self.append_event(document.state.project_id, "project_created", {"name": clean_name})
        return document

    def list_projects(self, include_hidden: bool = False) -> list[ProjectDocument]:
        documents: list[ProjectDocument] = []
        for project_json in self.root.glob("*/project.json"):
            try:
                document = self.get_project(project_json.parent.name)
            except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError):
                continue
            if document.state.hidden and not include_hidden:
                continue
            documents.append(document)
        return sorted(documents, key=lambda document: document.state.updated_at, reverse=True)

    def get_project(self, project_id: str) -> ProjectDocument:
        with self.lock:
            project_dir = self.project_dir(project_id)
            project_json = project_dir / "project.json"
            versions_json = project_dir / "versions.json"
            if not project_json.exists():
                raise FileNotFoundError(project_id)
            state = ProjectState.from_dict(read_json(project_json))
            if versions_json.exists():
                versions_data = read_json(versions_json)
                raw_versions = versions_data.get("versions", versions_data) if isinstance(versions_data, dict) else versions_data
            else:
                raw_versions = []
            versions = [ProjectVersion.from_dict(version) for version in raw_versions]
            document = ProjectDocument(state=state, versions=versions)
            self.recalculate(document)
            return document

    def save_project(self, document: ProjectDocument) -> None:
        with self.lock:
            if document.state.status not in PROJECT_STATUSES:
                raise ValueError(f"Unsupported project status: {document.state.status}.")
            document.state.project_id = _validate_project_id(document.state.project_id)
            for version in document.versions:
                version.project_id = document.state.project_id
                _validate_version_id(version.version_id)
                if version.status not in VERSION_STATUSES:
                    raise ValueError(f"Unsupported project version status: {version.status}.")
            self.recalculate(document, touch=True)
            project_dir = self.project_dir(document.state.project_id)
            project_dir.mkdir(parents=True, exist_ok=True)
            write_json(project_dir / "project.json", document.state.to_dict())
            write_json(project_dir / "versions.json", {"versions": [version.to_dict() for version in document.versions]})

    def add_version_from_job(
        self,
        project_id: str,
        job: JobLike,
        name: str = "",
        note: str = "",
        parent_version_id: str | None = None,
        variant_type: str = "original",
        change_summary: str = "",
    ) -> ProjectDocument:
        document = self.get_project(project_id)
        if any(version.job_id == job.job_id for version in document.versions):
            raise ValueError("Job is already attached to this project.")
        if parent_version_id is not None:
            _find_version(document, parent_version_id)
        variant_type = _validate_variant_type(variant_type)
        index = max((version.index for version in document.versions), default=0) + 1
        version_id = f"v{index:03d}"
        version = ProjectVersion(
            version_id=version_id,
            project_id=document.state.project_id,
            index=index,
            name=_clean(name) or f"Version {index}",
            job_id=job.job_id,
            output_dir=job.output_dir,
            status=job.status if job.status in VERSION_STATUSES else "queued",
            created_at=job.created_at,
            updated_at=job.updated_at,
            request=dict(job.input_payload),
            generation_mode=job.generation_mode,
            pipeline_mode=job.pipeline_mode,
            summary=dict(job.summary),
            note=str(note or ""),
            parent_version_id=parent_version_id,
            variant_type=variant_type,
            change_summary=str(change_summary or ""),
        )
        self.refresh_version_from_job(version, job)
        document.versions.append(version)
        self.save_project(document)
        self.append_event(
            document.state.project_id,
            "version_added",
            {
                "version_id": version.version_id,
                "job_id": job.job_id,
                "parent_version_id": parent_version_id,
                "variant_type": variant_type,
            },
        )
        return self.get_project(project_id)

    def update_version_from_job(self, project_id: str, job: JobLike) -> ProjectDocument:
        document = self.get_project(project_id)
        for version in document.versions:
            if version.job_id == job.job_id:
                self.refresh_version_from_job(version, job)
                self.save_project(document)
                return self.get_project(project_id)
        raise FileNotFoundError(job.job_id)

    def update_version_quality_gate(
        self,
        project_id: str,
        version_id: str,
        result: Any,
    ) -> ProjectDocument:
        document = self.get_project(project_id)
        version = _find_version(document, version_id)
        version.quality_gate_status = str(result.status)
        version.quality_gate_score = result.score
        version.quality_gate_warnings = [str(warning) for warning in result.warnings]
        self.save_project(document)
        self.append_event(
            project_id,
            "quality_gate_evaluated",
            {
                "version_id": version.version_id,
                "status": version.quality_gate_status,
                "score": version.quality_gate_score,
            },
        )
        return self.get_project(project_id)

    def update_version_final_export(
        self,
        project_id: str,
        version_id: str,
        export_path: Path | str,
    ) -> ProjectDocument:
        document = self.get_project(project_id)
        version = _find_version(document, version_id)
        version.final_export_path = str(export_path)
        version.updated_at = now_iso()
        self.save_project(document)
        self.append_event(
            project_id,
            "final_export_created",
            {
                "version_id": version.version_id,
                "path": version.final_export_path,
            },
        )
        return self.get_project(project_id)

    def sync_project(self, project_id: str, job_lookup: Any) -> ProjectDocument:
        document = self.get_project(project_id)
        changed = False
        for version in document.versions:
            job = job_lookup(version.job_id)
            if job is None:
                if not version.missing_job or version.status != "missing_job":
                    version.missing_job = True
                    version.status = "missing_job"
                    version.updated_at = now_iso()
                    changed = True
                continue
            before = version.to_dict()
            self.refresh_version_from_job(version, job)
            if version.to_dict() != before:
                changed = True
        if changed:
            self.save_project(document)
            return self.get_project(project_id)
        return document

    def refresh_version_from_job(self, version: ProjectVersion, job: JobLike) -> ProjectVersion:
        version.job_id = job.job_id
        version.output_dir = job.output_dir
        version.status = job.status if job.status in VERSION_STATUSES else "queued"
        version.updated_at = job.updated_at
        version.request = dict(job.input_payload)
        version.generation_mode = job.generation_mode
        version.pipeline_mode = job.pipeline_mode
        version.summary = dict(job.summary)
        version.missing_job = False
        version.has_midi = _artifact_exists(job, "midi", Path(job.output_dir) / "renders" / "song.mid")
        version.has_audio = _artifact_exists(job, "audio", Path(job.output_dir) / "renders" / "song.wav")
        stems_dir = Path(job.output_dir) / "stems"
        manifest_path = stems_dir / "manifest.json"
        version.has_stems = manifest_path.exists()
        version.has_stem_audio = any((stems_dir / "audio").glob("*.wav")) if (stems_dir / "audio").exists() else False
        version.quality_score = quality_score_for_run(Path(job.output_dir))
        return version

    def set_selected_version(self, project_id: str, version_id: str) -> ProjectDocument:
        document = self.get_project(project_id)
        version = _find_version(document, version_id)
        document.state.selected_version_id = version.version_id
        self.save_project(document)
        self.append_event(project_id, "selected_version_set", {"version_id": version.version_id})
        return self.get_project(project_id)

    def set_final_version(self, project_id: str, version_id: str) -> ProjectDocument:
        document = self.get_project(project_id)
        version = _find_version(document, version_id)
        if version.status != "completed":
            raise ValueError("Only completed versions can be marked final.")
        document.state.final_version_id = version.version_id
        document.state.status = "finalized"
        self.save_project(document)
        self.append_event(project_id, "final_version_set", {"version_id": version.version_id})
        return self.get_project(project_id)

    def hide_project(self, project_id: str, hidden: bool) -> ProjectDocument:
        document = self.get_project(project_id)
        document.state.hidden = hidden
        self.save_project(document)
        self.append_event(project_id, "project_hidden" if hidden else "project_unhidden", {})
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> None:
        project_dir = self.project_dir(project_id)
        self.ensure_project_dir_is_safe(project_dir)
        if not project_dir.exists():
            raise FileNotFoundError(project_id)
        shutil.rmtree(project_dir)

    def export_project(self, project_id: str) -> dict[str, Any]:
        export = self.project_export_snapshot(project_id)
        write_json(self.project_dir(project_id) / "export.json", export)
        self.append_event(project_id, "project_exported", {"version_count": len(export.get("versions", []))})
        return export

    def project_export_snapshot(self, project_id: str) -> dict[str, Any]:
        document = self.get_project(project_id)
        return {
            "project": document.state.to_dict(),
            "versions": [self._export_version(version) for version in document.versions],
            "selected_version": _version_or_none(document, document.state.selected_version_id),
            "final_version": _version_or_none(document, document.state.final_version_id),
            "asset_refs": _collect_project_asset_refs(self.project_dir(project_id), document),
            "reference_refs": _collect_project_reference_refs(self.project_dir(project_id), document),
            "context_packs": _collect_project_context_packs(self.project_dir(project_id), document),
            "review_tasks": _collect_project_review_tasks(self.project_dir(project_id)),
            "review_sprints": _collect_project_review_sprints(self.project_dir(project_id)),
            "review_metrics_summary": _collect_project_review_metrics_summary(self.project_dir(project_id)),
            "acceptance_fix_sprint_summary": _collect_project_acceptance_fix_sprint_summary(document.state.project_id),
            "acceptance_fix_plan_summary": _collect_project_acceptance_fix_plan_summary(document.state.project_id),
            "acceptance_fix_plan_review_summary": _collect_project_acceptance_fix_plan_review_summary(document.state.project_id),
            "acceptance_kb_summary": _collect_project_acceptance_kb_summary(document.state.project_id),
            "planning_rule_simulation_summary": _collect_project_planning_rule_simulation_summary(document.state.project_id),
            "planning_rule_governance_summary": _collect_project_planning_rule_governance_summary(document.state.project_id),
            "planning_rule_impact_summary": _collect_project_planning_rule_impact_summary(document.state.project_id),
            "delivery_qa_summary": _collect_project_delivery_qa_summary(self.project_dir(project_id)),
            "delivery_signoff_summary": _collect_project_delivery_signoff_summary(self.project_dir(project_id)),
            "generated_at": now_iso(),
        }

    def diff_versions(self, project_id: str, left_id: str, right_id: str) -> dict[str, Any]:
        document = self.get_project(project_id)
        left = _find_version(document, left_id)
        right = _find_version(document, right_id)
        return {
            "project_id": document.state.project_id,
            "left": _version_ref(left),
            "right": _version_ref(right),
            "changed": {
                "request": _diff_dict(left.request, right.request),
                "summary": _diff_dict(left.summary, right.summary),
                "lineage": _diff_dict(_lineage_info(left), _lineage_info(right)),
                "edit": _diff_optional(_edit_info(left), _edit_info(right)),
                "sections": _diff_dict(_section_info(left), _section_info(right)),
                "tracks": _diff_dict(_track_info(left), _track_info(right)),
                "quality": _diff_dict({"overall": left.quality_score}, {"overall": right.quality_score}),
                "artifacts": _diff_dict(_artifact_flags(left), _artifact_flags(right)),
            },
        }

    def find_or_create_project(self, name: str) -> ProjectDocument:
        clean_name = _clean(name) or "Untitled Project"
        target_slug = slugify(clean_name)[:80]
        for document in self.list_projects(include_hidden=True):
            if document.state.project_id == target_slug or document.state.name.strip().lower() == clean_name.lower():
                return document
        return self.create_project(clean_name)

    def append_event(self, project_id: str, event_type: str, payload: dict[str, Any]) -> None:
        project_dir = self.project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": now_iso(),
            "type": event_type,
            "payload": payload,
        }
        with (project_dir / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_events(self, project_id: str) -> list[dict[str, Any]]:
        events_path = self.project_dir(project_id) / "events.jsonl"
        if not events_path.exists():
            return []
        events = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events

    def delivery_qa_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "delivery-qa.json"

    def read_delivery_qa(self, project_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.delivery_qa_path(project_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(path)
        data = read_json(path)
        return _sanitize_asset_metadata(data if isinstance(data, dict) else {})

    def write_delivery_qa(self, project_id: str, report: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        self.get_project(project_id)
        clean = _sanitize_asset_metadata(report if isinstance(report, dict) else {})
        if now:
            clean["created_at"] = clean.get("created_at") or now
        write_json(self.delivery_qa_path(project_id), clean)
        return clean

    def delivery_signoff_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "delivery-signoff.json"

    def delivery_signoff_history_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "delivery-signoff-history.jsonl"

    def read_delivery_signoff(self, project_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.delivery_signoff_path(project_id)
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(path)
        data = read_json(path)
        return _sanitize_asset_metadata(data if isinstance(data, dict) else {})

    def write_delivery_signoff(self, project_id: str, record: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        self.get_project(project_id)
        clean = _sanitize_asset_metadata(record if isinstance(record, dict) else {})
        if now:
            clean["signed_at"] = clean.get("signed_at") or now
        write_json(self.delivery_signoff_path(project_id), clean)
        return clean

    def reset_delivery_signoff(self, project_id: str, history_event: dict[str, Any]) -> dict[str, Any]:
        existing = self.read_delivery_signoff(project_id, default={})
        if not existing:
            raise FileNotFoundError("Delivery signoff does not exist.")
        event = _sanitize_asset_metadata(history_event if isinstance(history_event, dict) else {})
        history_path = self.delivery_signoff_history_path(project_id)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        signoff_path = self.delivery_signoff_path(project_id)
        if signoff_path.exists():
            signoff_path.unlink()
        return event

    def project_dir(self, project_id: str) -> Path:
        return self.root / _validate_project_id(project_id)

    def ensure_project_dir_is_safe(self, project_dir: Path) -> None:
        root = self.root.resolve()
        target = project_dir.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside the project root.") from exc

    def recalculate(self, document: ProjectDocument, *, touch: bool = False) -> None:
        document.versions.sort(key=lambda version: version.index)
        document.state.version_count = len(document.versions)
        document.state.latest_version_id = document.versions[-1].version_id if document.versions else None
        scored = [version for version in document.versions if version.quality_score is not None]
        best = max(scored, key=lambda version: int(version.quality_score or 0), default=None)
        document.state.best_quality_version_id = best.version_id if best else None
        document.state.best_quality_score = best.quality_score if best else None
        valid_version_ids = {version.version_id for version in document.versions}
        if document.state.selected_version_id not in valid_version_ids:
            document.state.selected_version_id = None
        if document.state.final_version_id not in valid_version_ids:
            document.state.final_version_id = None
        if touch:
            document.state.updated_at = now_iso()

    def _reserve_project_dir(self, name: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        base = (slugify(name) or "project")[:80].strip("-") or "project"
        for index in range(1, 1000):
            suffix = "" if index == 1 else f"-{index}"
            project_dir = self.root / f"{base}{suffix}"
            try:
                project_dir.mkdir(parents=True, exist_ok=False)
                return project_dir
            except FileExistsError:
                continue
        raise RuntimeError("Unable to allocate a unique project directory.")

    @staticmethod
    def _export_version(version: ProjectVersion) -> dict[str, Any]:
        output_dir = Path(version.output_dir) if version.output_dir else None
        return {
            **version.to_dict(),
            "song_plan": str(output_dir / "data" / "song-plan.json") if output_dir else None,
            "midi": str(output_dir / "renders" / "song.mid") if output_dir else None,
            "audio": str(output_dir / "renders" / "song.wav") if output_dir else None,
            "stem_manifest": str(output_dir / "stems" / "manifest.json") if output_dir else None,
            "edit": _edit_info(version),
            "mix": _mix_info(version),
        }


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
        return analyze_song_quality(plan).scores.overall
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


def _version_or_none(document: ProjectDocument, version_id: str | None) -> dict[str, Any] | None:
    if not version_id:
        return None
    try:
        return _find_version(document, version_id).to_dict()
    except FileNotFoundError:
        return None


def _version_ref(version: ProjectVersion) -> dict[str, Any]:
    return {
        "version_id": version.version_id,
        "job_id": version.job_id,
        "name": version.name,
        "status": version.status,
        "parent_version_id": version.parent_version_id,
        "variant_type": version.variant_type,
    }


def _lineage_info(version: ProjectVersion) -> dict[str, Any]:
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


def _edit_info(version: ProjectVersion) -> dict[str, Any] | None:
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
        "audition_summary": metadata.get("audition_summary") if isinstance(metadata.get("audition_summary"), dict) else {},
        "review_edit": metadata.get("review_edit") if isinstance(metadata.get("review_edit"), dict) else {},
        "review_summary": metadata.get("review_summary") if isinstance(metadata.get("review_summary"), dict) else {},
        "review_task": metadata.get("review_task") if isinstance(metadata.get("review_task"), dict) else {},
        "review_candidate": metadata.get("review_candidate") if isinstance(metadata.get("review_candidate"), dict) else {},
        "review_candidate_source": metadata.get("review_candidate_source") if isinstance(metadata.get("review_candidate_source"), dict) else {},
        "review_provider_patch": metadata.get("review_provider_patch") if isinstance(metadata.get("review_provider_patch"), dict) else {},
        "review_decision": metadata.get("review_decision") if isinstance(metadata.get("review_decision"), dict) else {},
        "review_sprint": metadata.get("review_sprint") if isinstance(metadata.get("review_sprint"), dict) else {},
        "review_sprint_recommendation": metadata.get("review_sprint_recommendation") if isinstance(metadata.get("review_sprint_recommendation"), dict) else {},
        "review_sprint_action_queue": metadata.get("review_sprint_action_queue") if isinstance(metadata.get("review_sprint_action_queue"), dict) else {},
        "review_judge": metadata.get("review_judge") if isinstance(metadata.get("review_judge"), dict) else {},
        "review_candidate_intents": metadata.get("review_candidate_intents") if isinstance(metadata.get("review_candidate_intents"), list) else [],
        "summary": metadata.get("summary") or {},
        "structure": metadata.get("structure") or {},
        "warnings": metadata.get("warnings") or [],
    }


def _mix_info(version: ProjectVersion) -> dict[str, Any]:
    run_dir = Path(version.output_dir)
    summary: dict[str, Any] = {}
    state_path = run_dir / "data" / "mix-state.json"
    patch_path = run_dir / "data" / "mix-patch.json"
    stem_health_path = run_dir / "stems" / "stem-health.json"
    if state_path.exists():
        try:
            from song_agent.mix_controls import mix_state_hash, mix_state_integrity_ok

            state = read_json(state_path)
            ok = mix_state_integrity_ok(state)
            summary["mix_state"] = {"exists": True, "integrity_ok": ok, "mix_state_hash": mix_state_hash(state) if ok else None}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            summary["mix_state"] = {"exists": True, "integrity_ok": False}
    if patch_path.exists():
        try:
            from song_agent.mix_controls import mix_patch_hash, mix_patch_integrity_ok

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
            from song_agent.stem_health import stem_health_integrity_ok, stem_health_summary

            report = read_json(stem_health_path)
            summary["stem_health"] = {**stem_health_summary(report), "integrity_ok": stem_health_integrity_ok(report)}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            summary["stem_health"] = {"status": "invalid", "integrity_ok": False}
    return summary


def _section_info(version: ProjectVersion) -> dict[str, dict[str, Any]]:
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


def _track_info(version: ProjectVersion) -> dict[str, dict[str, Any]]:
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


def _average_velocity(track: Any) -> float:
    if not track.notes:
        return 0.0
    return round(sum(note.velocity for note in track.notes) / len(track.notes), 2)


def _diff_dict(left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = sorted(set(left) | set(right))
    return {
        key: {"left": left.get(key), "right": right.get(key)}
        for key in keys
        if left.get(key) != right.get(key)
    }


def _diff_optional(left: Any, right: Any) -> dict[str, Any]:
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


def _optional_version_id(value: Any) -> str | None:
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


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def _collect_project_asset_refs(project_dir: Path, document: ProjectDocument) -> list[dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}

    def add_ref(ref: dict[str, Any], *, version_id: str | None = None, candidate_group_id: str | None = None) -> None:
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


def _collect_project_reference_refs(project_dir: Path, document: ProjectDocument) -> list[dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}

    def add_ref(ref: dict[str, Any], *, version_id: str | None = None, candidate_group_id: str | None = None, linked: bool = False) -> None:
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
            linked_project_ids = data.get("linked_project_ids") if isinstance(data, dict) else []
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


def _collect_project_context_packs(project_dir: Path, document: ProjectDocument) -> list[dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = {}

    def add_pack(data: dict[str, Any], *, version_id: str | None = None, candidate_group_id: str | None = None) -> None:
        pack_id = str(data.get("pack_id") or "").strip()
        if not pack_id:
            return
        record = packs.setdefault(
            pack_id,
            {
                "pack_id": pack_id,
                "name": str(data.get("name") or pack_id),
                "asset_count": len(data.get("asset_refs") or []) if isinstance(data.get("asset_refs"), list) else int(data.get("asset_count") or 0),
                "reference_count": len(data.get("reference_refs") or []) if isinstance(data.get("reference_refs"), list) else int(data.get("reference_count") or 0),
                "created_from": _sanitize_asset_metadata(data.get("created_from")) if isinstance(data.get("created_from"), dict) else {},
                "query": _sanitize_asset_metadata(data.get("query")) if isinstance(data.get("query"), dict) else {},
                "used_by_versions": [],
                "used_by_candidate_groups": [],
            },
        )
        if data.get("name") and record.get("name") == pack_id:
            record["name"] = str(data.get("name"))
        if version_id and version_id not in record["used_by_versions"]:
            record["used_by_versions"].append(version_id)
        if candidate_group_id and candidate_group_id not in record["used_by_candidate_groups"]:
            record["used_by_candidate_groups"].append(candidate_group_id)

    for version in document.versions:
        path = Path(version.output_dir) / "data" / "context-pack.json"
        if not path.exists():
            continue
        try:
            data = read_json(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            add_pack(data, version_id=version.version_id)

    candidate_root = project_dir / "candidate-groups"
    if candidate_root.exists():
        for group_json in candidate_root.glob("*/group.json"):
            try:
                data = read_json(group_json)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            source = data.get("source") if isinstance(data, dict) else None
            context_pack = source.get("context_pack") if isinstance(source, dict) else None
            if isinstance(context_pack, dict):
                add_pack(context_pack, candidate_group_id=str(data.get("group_id") or group_json.parent.name))

    return sorted((_sanitize_asset_metadata(record) for record in packs.values()), key=lambda item: item["pack_id"])


def _collect_project_review_tasks(project_dir: Path) -> list[dict[str, Any]]:
    from song_agent.prompt_templates import PromptTemplateStore
    from song_agent.review_judge import REVIEW_JUDGE_TEMPLATE_ID, judge_report_summary, mark_judge_report_stale, read_judge_report_with_stale
    from song_agent.review_tasks import ReviewTaskStore, review_candidate_source_breakdown, review_decision_summary, review_task_summary

    store = ReviewTaskStore(project_dir)
    template_store = PromptTemplateStore(project_dir.parent.parent / "prompt-templates.json")
    tasks = store.list_tasks(include_archived=True)
    summaries: list[dict[str, Any]] = []
    for task in tasks:
        selected = None
        if task.selected_candidate_id:
            try:
                selected = store.read_candidate(task.task_id, task.selected_candidate_id)
            except (OSError, ValueError, TypeError, FileNotFoundError):
                selected = None
        summary = review_task_summary(task, selected)
        candidates = store.list_candidates(task.task_id)
        try:
            decision_report = store.read_decision_report(task.task_id)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            decision_report = {}
        try:
            template_id = str((store.read_judge_report(task.task_id, default={}) or {}).get("template_id") or REVIEW_JUDGE_TEMPLATE_ID)
            template = template_store.get_template(template_id)
            parent_plan = _project_version_song_plan(project_dir, task.parent_version_id)
            judge_report = read_judge_report_with_stale(store, task, candidates=candidates, parent_plan=parent_plan, template=template)
        except (OSError, ValueError, TypeError, FileNotFoundError):
            try:
                raw_report = store.read_judge_report(task.task_id, default={})
            except (OSError, ValueError, TypeError, FileNotFoundError):
                raw_report = {}
            judge_report = mark_judge_report_stale(raw_report, stale=True) if raw_report else {}
        summary["candidate_count"] = int(task.counts.get("candidate_count") or 0)
        summary["ready_candidate_count"] = int(task.counts.get("ready_candidate_count") or 0)
        summary["provider_summary"] = review_candidate_source_breakdown(candidates)
        summary["decision_report"] = review_decision_summary(decision_report)
        summary["judge_summary"] = judge_report_summary(judge_report)
        summary["priority"] = task.priority
        summaries.append(_sanitize_asset_metadata(summary))
    return sorted(summaries, key=lambda item: str(item.get("task_id") or ""))


def _project_version_song_plan(project_dir: Path, version_id: str) -> Any:
    from song_agent.schemas.song import SongPlan

    versions_path = project_dir / "versions.json"
    data = read_json(versions_path)
    for version in data.get("versions", []) if isinstance(data, dict) else []:
        if isinstance(version, dict) and version.get("version_id") == version_id:
            return SongPlan.from_dict(read_json(Path(str(version.get("output_dir") or "")) / "data" / "song-plan.json"))
    raise FileNotFoundError(version_id)


def _collect_project_review_sprints(project_dir: Path) -> list[dict[str, Any]]:
    from song_agent.review_sprints import ReviewSprintStore, review_sprint_export_summary
    from song_agent.review_sprint_actions import ReviewSprintActionQueueStore, action_queue_collection_summary
    from song_agent.review_sprint_metrics import ReviewMetricsStore, sprint_metrics_summary
    from song_agent.review_sprint_closeout import closeout_report_summary, signoff_summary

    store = ReviewSprintStore(project_dir)
    metrics_store = ReviewMetricsStore(project_dir)
    sprints = store.list_sprints(include_archived=True)
    summaries = []
    for sprint in sprints:
        summary = store.read_summary(sprint.sprint_id, default={})
        conflict_report = store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = store.read_recommendation_report(sprint.sprint_id, default={})
        judge_summary = store.read_judge_summary(sprint.sprint_id, default={})
        queue_store = ReviewSprintActionQueueStore(store.sprint_dir(sprint.sprint_id))
        queue_summary = action_queue_collection_summary(queue_store.list_queues(include_archived=True))
        closeout_summary = closeout_report_summary(store.read_closeout_report(sprint.sprint_id, default={}))
        signoff = signoff_summary(store.read_signoff(sprint.sprint_id, default={}))
        payload = review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, queue_summary, judge_summary, closeout_summary, signoff)
        metrics_summary = sprint_metrics_summary(metrics_store.read_sprint_metrics(sprint.sprint_id, default={}))
        if metrics_summary:
            payload["metrics_summary"] = metrics_summary
        summaries.append(payload)
    return sorted((_sanitize_asset_metadata(item) for item in summaries), key=lambda item: str(item.get("sprint_id") or ""))


def _collect_project_review_metrics_summary(project_dir: Path) -> dict[str, Any]:
    from song_agent.review_sprint_metrics import ReviewMetricsStore, project_review_metrics_summary

    try:
        store = ReviewMetricsStore(project_dir)
        return _sanitize_asset_metadata(project_review_metrics_summary(store.read_project_metrics(default={})))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _collect_project_acceptance_fix_sprint_summary(project_id: str) -> dict[str, Any]:
    from song_agent.acceptance_fix_sprints import AcceptanceFixSprintStore, latest_fix_sprint_summary

    try:
        return _sanitize_asset_metadata(latest_fix_sprint_summary(AcceptanceFixSprintStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_acceptance_fix_plan_summary(project_id: str) -> dict[str, Any]:
    from song_agent.acceptance_fix_planning import AcceptanceFixPlanningStore, latest_fix_plan_summary

    try:
        return _sanitize_asset_metadata(latest_fix_plan_summary(AcceptanceFixPlanningStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_acceptance_fix_plan_review_summary(project_id: str) -> dict[str, Any]:
    from song_agent.acceptance_fix_plan_reviews import AcceptanceFixPlanReviewStore, latest_fix_plan_review_summary

    try:
        return _sanitize_asset_metadata(latest_fix_plan_review_summary(AcceptanceFixPlanReviewStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_acceptance_kb_summary(project_id: str) -> dict[str, Any]:
    from song_agent.acceptance_kb import AcceptanceKnowledgeBaseStore

    try:
        return _sanitize_asset_metadata(AcceptanceKnowledgeBaseStore().summary(project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_planning_rule_simulation_summary(project_id: str) -> dict[str, Any]:
    from song_agent.planning_rule_simulation import PlanningRuleSimulationStore, latest_planning_simulation_summary

    try:
        return _sanitize_asset_metadata(latest_planning_simulation_summary(PlanningRuleSimulationStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_planning_rule_governance_summary(project_id: str) -> dict[str, Any]:
    from song_agent.acceptance_fix_planning import AcceptanceFixPlanningStore
    from song_agent.planning_rule_governance import PlanningRuleGovernanceStore, active_governance_summary

    try:
        summary = _sanitize_asset_metadata(active_governance_summary(PlanningRuleGovernanceStore()))
        used: dict[str, int] = {}
        for plan in AcceptanceFixPlanningStore().list_plans(include_archived=False):
            matches_project = plan.scope.get("project_id") == project_id or any(str((item.get("target") if isinstance(item.get("target"), dict) else {}).get("project_id") or "") == project_id for item in plan.planned_items)
            if not matches_project:
                continue
            governance = plan.source.get("planning_rule_governance") if isinstance(plan.source.get("planning_rule_governance"), dict) else {}
            version_id = str(governance.get("planning_rule_version_id") or governance.get("version_id") or "legacy_default")
            used[version_id] = used.get(version_id, 0) + 1
        summary["used_rule_versions"] = [{"version_id": key, "plan_count": value} for key, value in sorted(used.items())]
        return summary
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_planning_rule_impact_summary(project_id: str) -> dict[str, Any]:
    from song_agent.planning_rule_impact import PlanningRuleImpactStore, latest_planning_rule_impact_summary

    try:
        return _sanitize_asset_metadata(latest_planning_rule_impact_summary(PlanningRuleImpactStore(), project_id=project_id))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "missing"}


def _collect_project_delivery_qa_summary(project_dir: Path) -> dict[str, Any]:
    from song_agent.delivery_qa import delivery_qa_summary

    try:
        return _sanitize_asset_metadata(delivery_qa_summary(read_json(project_dir / "delivery-qa.json")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _collect_project_delivery_signoff_summary(project_dir: Path) -> dict[str, Any]:
    from song_agent.delivery_qa import delivery_signoff_summary

    try:
        return _sanitize_asset_metadata(delivery_signoff_summary(read_json(project_dir / "delivery-signoff.json")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "not_signed"}


def _sanitize_asset_metadata(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=BLOCKED_ASSET_METADATA_KEYS)
