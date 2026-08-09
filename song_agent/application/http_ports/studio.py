from __future__ import annotations

from http import HTTPStatus
from http.client import HTTPMessage
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Protocol

from song_agent.application.jobs.model import JobState
from song_agent.application.jobs.ports import JobRuntimePort
from song_agent.platform.auth import AuthConfig
from song_agent.domains.creation.edit_presets import EditPresetStore
from song_agent.domains.creation.edits import EditedSongPlanResult
from song_agent.domains.creation.schemas.song import SongPlan
from song_agent.domains.quality.review_sprint_actions import ReviewSprintActionQueueStore, SprintActionItem, SprintActionQueue
from song_agent.domains.quality.review_sprints import ReviewSprint, ReviewSprintStore
from song_agent.domains.quality.review_tasks import ReviewCandidate, ReviewTask, ReviewTaskStore
from song_agent.domains.quality.human_review_pack import HumanReviewPackStore
from song_agent.domains.studio.assets import AssetStore
from song_agent.domains.studio.library_index import LibraryIndexStore
from song_agent.domains.studio.project_quality import QualityGateResult
from song_agent.domains.studio.project_repository import ProjectDocument, ProjectVersion
from song_agent.domains.studio.projects import ProjectStore
from song_agent.domains.studio.prompt_templates import PromptTemplateStore
from song_agent.domains.studio.references import ReferenceStore
from song_agent.domains.studio.song_editor import EditorPreview
from song_agent.platform.contracts.documents import JsonDocument

__all__ = (
    "EditedSongPlanResult",
    "EditorPreview",
    "ReviewSprintActionQueueStore",
    "SprintActionQueue",
)

class StudioRouteRegistryPort(Protocol):
    def dispatch(self, port: object, method: str, path: str, parsed: object) -> bool: ...


class StudioServerPort(Protocol):
    @property
    def auth_config(self) -> AuthConfig: ...

    @property
    def edit_preset_store(self) -> EditPresetStore: ...

    @property
    def human_review_pack_store(self) -> HumanReviewPackStore: ...

    @property
    def job_store(self) -> JobRuntimePort: ...


class _StudioRouteContextTyping(StudioServerPort, Protocol):
    """Typed cross-route members supplied by API composition."""

    headers: HTTPMessage
    path: str
    rfile: BinaryIO
    route_registry: StudioRouteRegistryPort
    wfile: BinaryIO

    def _evaluate_project_version(self, project_id: str, version: ProjectVersion) -> QualityGateResult: ...

    def _execute_queue_context_pack_action(
        self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: ReviewSprint, item: SprintActionItem
    ) -> JsonDocument: ...

    def _generate_review_task_provider_candidates_for_queue(
        self, project_id: str, task_store: ReviewTaskStore, task: ReviewTask, payload: JsonDocument
    ) -> JsonDocument: ...

    def _get_or_refresh_sprint_judge_summary(
        self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: ReviewSprint, *, refresh: bool
    ) -> JsonDocument: ...

    def _get_or_refresh_sprint_metrics(
        self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: ReviewSprint, *, refresh: bool
    ) -> JsonDocument: ...

    def _handle_request(self, method: str) -> None: ...

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

    def _refresh_review_sprint_recommendations(
        self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: ReviewSprint
    ) -> JsonDocument: ...

    def _refresh_review_sprint_state(
        self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: ReviewSprint
    ) -> tuple[ReviewSprint, JsonDocument]: ...

    def _refresh_review_task_judge_report(
        self, project_id: str, task_store: ReviewTaskStore, task: ReviewTask, payload: JsonDocument | None = None
    ) -> JsonDocument: ...

    def _review_sprint_action_queue_summary_for_task(self, project_id: str, task_id: str) -> JsonDocument: ...

    def _review_sprint_membership_summary(self, project_id: str, task_id: str) -> JsonDocument: ...

    def _review_sprint_ordered_task_ids(self, sprint: ReviewSprint) -> list[str]: ...

    def _review_sprint_parent_plan_hashes(self, project_id: str, task_store: ReviewTaskStore, sprint: ReviewSprint) -> dict[str, str]: ...

    def _review_sprint_recommendation_summary_for_task(self, project_id: str, task_id: str) -> JsonDocument: ...

    def _review_sprint_response(
        self, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: ReviewSprint, *, include_events: bool = False
    ) -> JsonDocument: ...

    def _review_sprint_task_items(self, task_store: ReviewTaskStore, sprint: ReviewSprint) -> list[JsonDocument]: ...

    def _send_error(self, status: HTTPStatus, message: str) -> None: ...

    def _send_file(self, path: Path, content_type: str | None = None, *, filename: str | None = None) -> None: ...

    def _send_json(self, data: JsonDocument, status: HTTPStatus = HTTPStatus.OK) -> None: ...

    @property
    def asset_store(self) -> AssetStore: ...

    def end_headers(self) -> None: ...

    @property
    def library_index_store(self) -> LibraryIndexStore: ...

    @property
    def project_store(self) -> ProjectStore: ...

    @property
    def prompt_template_store(self) -> PromptTemplateStore: ...

    @property
    def reference_store(self) -> ReferenceStore: ...

    def send_header(self, keyword: str, value: str) -> None: ...

    def send_response(self, code: int, message: str | None = None) -> None: ...

    server: StudioServerPort

    @property
    def store(self) -> JobRuntimePort: ...


if TYPE_CHECKING:
    StudioRouteContext = _StudioRouteContextTyping
else:

    class StudioRouteContext:
        """Runtime marker for Studio route mixins."""
