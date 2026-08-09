from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from song_agent.application.jobs.model import JobState
from song_agent.application.jobs.ports import BatchRunnerPort, BatchStorePort, JobRuntimePort
from song_agent.domains.creation.edit_presets import EditPresetStore
from song_agent.domains.creation.edits import EditedSongPlanResult
from song_agent.domains.creation.provider_contracts import ProviderConfig
from song_agent.domains.creation.renderers.audio import RendererConfig
from song_agent.domains.creation.schemas.song import SongPlan
from song_agent.domains.quality.audio_profiles import AudioProfileStore, RendererProfile
from song_agent.domains.quality.candidate_groups import CandidateGroup, CandidateGroupStore
from song_agent.domains.quality.mix_controls import MixControlStore
from song_agent.domains.quality.mix_render import MixRenderStore
from song_agent.domains.quality.review_edits import ReviewEditIntent
from song_agent.domains.quality.review_sprint_actions import ReviewSprintActionQueueStore, SprintActionItem
from song_agent.domains.quality.review_sprints import ReviewSprint, ReviewSprintStore
from song_agent.domains.quality.review_tasks import ReviewCandidate, ReviewTask, ReviewTaskStore
from song_agent.domains.studio.assets import AssetStore, CreativeAsset
from song_agent.domains.studio.context_packs import ContextPackStore
from song_agent.domains.studio.editor_audition import EditorAuditionManifest, EditorAuditionStore
from song_agent.domains.studio.editor_templates import EditorTemplateStore
from song_agent.domains.studio.library_index import LibraryIndexStore
from song_agent.domains.studio.project_quality import QualityGateResult
from song_agent.domains.studio.project_repository import ProjectDocument, ProjectVersion
from song_agent.domains.studio.projectio import ProjectPaths
from song_agent.domains.studio.projects import ProjectStore
from song_agent.domains.studio.prompt_templates import PromptTemplate, PromptTemplateStore
from song_agent.domains.studio.references import ReferenceStore
from song_agent.domains.studio.song_editor import EditorPatch, EditorPatchResult, EditorPreview, EditorPreviewStore
from song_agent.platform.contracts.documents import JsonDocument

__all__ = (
    "CreativeAsset",
    "EditorAuditionManifest",
    "EditorAuditionStore",
    "EditorPatch",
    "EditorPatchResult",
    "EditorPreviewStore",
    "MixControlStore",
    "MixRenderStore",
    "ProjectPaths",
    "PromptTemplate",
    "ProviderConfig",
    "RendererConfig",
    "SprintActionItem",
)

class CreationServerPort(Protocol):
    @property
    def audio_profile_store(self) -> AudioProfileStore: ...

    @property
    def asset_store(self) -> AssetStore: ...
    @property
    def batch_runner(self) -> BatchRunnerPort: ...
    @property
    def batch_store(self) -> BatchStorePort: ...
    @property
    def context_pack_store(self) -> ContextPackStore: ...

    @property
    def editor_template_store(self) -> EditorTemplateStore: ...
    @property
    def library_index_store(self) -> LibraryIndexStore: ...
    @property
    def project_store(self) -> ProjectStore: ...
    @property
    def prompt_template_store(self) -> PromptTemplateStore: ...

    @property
    def reference_store(self) -> ReferenceStore: ...


class _CreationRouteContextTyping(CreationServerPort, Protocol):
    """Typed cross-route members supplied by API composition."""

    def _apply_review_task_candidate(
        self,
        project_id: str,
        task_store: ReviewTaskStore,
        task: ReviewTask,
        candidate: ReviewCandidate,
        parent: ProjectVersion,
        parent_job: JobState,
        parent_plan: SongPlan,
        payload: JsonDocument,
    ) -> tuple[ReviewTask, ReviewCandidate, ProjectVersion, JobState, EditedSongPlanResult]: ...

    def _content_length_within(self, limit: int) -> bool: ...

    def _create_project_candidate_group(
        self,
        project_id: str,
        version_id: str,
        payload: JsonDocument,
        *,
        mark_asset_usage: bool = True,
    ) -> CandidateGroup: ...

    def _create_review_edit_job(
        self,
        *,
        project_id: str,
        parent: ProjectVersion,
        parent_job: JobState,
        parent_plan: SongPlan,
        review_edit: ReviewEditIntent,
        result: EditedSongPlanResult,
        payload: JsonDocument,
    ) -> JobState: ...

    def _create_review_task_follow_up(
        self,
        project_id: str,
        task_store: ReviewTaskStore,
        task: ReviewTask,
        payload: JsonDocument,
    ) -> tuple[ReviewTask, ReviewTask]: ...

    def _evaluate_project_version(self, project_id: str, version: ProjectVersion) -> QualityGateResult: ...

    def _expand_context_pack_payload(self, payload: JsonDocument) -> JsonDocument: ...

    def _generate_review_sprint_local_candidates(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        payload: JsonDocument,
    ) -> JsonDocument: ...

    def _generate_review_sprint_provider_candidates(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        payload: JsonDocument,
    ) -> JsonDocument: ...

    def _get_or_refresh_delivery_qa(self, project_id: str, *, refresh: bool) -> JsonDocument: ...

    def _get_or_refresh_project_review_metrics(self, project_id: str, *, refresh: bool) -> JsonDocument: ...

    def _get_or_refresh_sprint_closeout(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        *,
        refresh: bool,
    ) -> JsonDocument: ...

    def _get_or_refresh_sprint_judge_summary(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        *,
        refresh: bool,
    ) -> JsonDocument: ...

    def _get_or_refresh_sprint_metrics(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        *,
        refresh: bool,
    ) -> JsonDocument: ...

    def _handle_audition_context_pack(
        self,
        project_id: str,
        preview_id: str,
        audition_id: str,
        payload: JsonDocument,
    ) -> None: ...

    def _handle_project_editor_audition_next_action(
        self,
        method: str,
        project_id: str,
        preview_id: str,
        audition_id: str,
        action: str,
    ) -> None: ...

    def _handle_project_version_audio_route(
        self, method: str, project_id: str, version_id: str, action: str
    ) -> None: ...

    def _handle_project_acceptance_analytics(self, method: str, project_id: str) -> None: ...

    def _handle_project_acceptance_analytics_refresh(self, method: str, project_id: str) -> None: ...

    def _set_final_version_with_gate(
        self,
        project_id: str,
        version_id: str,
        *,
        force: bool,
    ) -> tuple[ProjectDocument, QualityGateResult]: ...

    def _handle_project_release_targets(self, method: str, project_id: str) -> None: ...

    def _handle_project_add_to_release(self, method: str, project_id: str) -> None: ...

    def _handle_project_review_task_create(
        self,
        method: str,
        project_id: str,
        preview_id: str,
        audition_id: str,
    ) -> None: ...

    def _handle_provider_review_edit_preview(
        self,
        project_id: str,
        parent: ProjectVersion,
        parent_job: JobState,
        parent_plan: SongPlan,
        review_edit: ReviewEditIntent,
        payload: JsonDocument,
    ) -> None: ...

    def _job_audio_artifact_stale_reasons(self, job: JobState) -> list[str]: ...

    def _merge_editor_patch_metadata(
        self,
        left: JsonDocument | None,
        right: JsonDocument | None,
    ) -> JsonDocument: ...

    def _optional_json_body(self) -> JsonDocument: ...

    def _project_candidate_group_or_conflict(
        self,
        project_id: str,
        group_store: CandidateGroupStore,
        group_id: str,
    ) -> CandidateGroup | None: ...

    def _project_edit_parent(self, project_id: str, version_id: str) -> tuple[ProjectDocument, ProjectVersion, JobState, SongPlan]: ...

    def _read_json_body(self) -> JsonDocument: ...

    def _read_review_task_judge_report(
        self,
        project_id: str,
        task_store: ReviewTaskStore,
        task: ReviewTask,
        candidates: list[ReviewCandidate] | None = None,
        *,
        parent_plan: SongPlan | None = None,
    ) -> JsonDocument: ...

    def _refresh_review_sprint_judge_reports(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        payload: JsonDocument | None = None,
    ) -> JsonDocument: ...

    def _refresh_review_sprint_recommendations(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
    ) -> JsonDocument: ...

    def _refresh_review_sprint_state(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
    ) -> tuple[ReviewSprint, JsonDocument]: ...

    def _refresh_review_task_judge_report(
        self,
        project_id: str,
        task_store: ReviewTaskStore,
        task: ReviewTask,
        payload: JsonDocument | None = None,
    ) -> JsonDocument: ...

    def _render_editor_preview_audio(self, project_id: str, preview_id: str) -> EditorPreview: ...

    def _renderer_profile_from_payload(self, payload: JsonDocument | None) -> RendererProfile | None: ...

    def _review_sprint_ordered_task_ids(self, sprint: ReviewSprint) -> list[str]: ...

    def _review_sprint_parent_plan_hashes(
        self,
        project_id: str,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
    ) -> dict[str, str]: ...

    def _review_sprint_public_payload(self, sprint_store: ReviewSprintStore, sprint: ReviewSprint) -> JsonDocument: ...

    def _review_sprint_response(
        self,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        *,
        include_events: bool = False,
    ) -> JsonDocument: ...

    def _rollback_prompt_ab_groups(self, project_id: str, group_ids: list[str]) -> None: ...

    def _run_review_sprint_action_queue(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        queue_store: ReviewSprintActionQueueStore,
        queue_id: str,
        payload: JsonDocument,
    ) -> JsonDocument: ...

    def _save_review_sprint_recommendation_context_pack(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: ReviewSprint,
        task_id: str,
        payload: JsonDocument,
    ) -> JsonDocument: ...

    def _send_error(self, status: HTTPStatus, message: str) -> None: ...

    def _send_file(self, path: Path, content_type: str | None = None, *, filename: str | None = None) -> None: ...

    def _send_json(self, data: JsonDocument, status: HTTPStatus = HTTPStatus.OK) -> None: ...

    def _send_node_retry(self, method: str, job: JobState, tail: str) -> None: ...

    def _send_node_route(self, method: str, job: JobState, tail: str) -> None: ...

    def _send_nodes_list(self, job: JobState) -> None: ...

    def _send_runtime_view(self, job: JobState, view_name: str) -> None: ...

    def _send_stem_file(self, job: JobState, tail: str) -> None: ...

    edit_preset_store: EditPresetStore
    path: str
    server: CreationServerPort
    store: JobRuntimePort


if TYPE_CHECKING:
    CreationRouteContext = _CreationRouteContextTyping
else:

    class CreationRouteContext:
        """Runtime marker for Creation route mixins."""
