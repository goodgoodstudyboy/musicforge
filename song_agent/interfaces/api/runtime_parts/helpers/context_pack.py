from __future__ import annotations

from song_agent.platform.contracts import JsonDocument, as_list as _as_list

from song_agent.interfaces.bootstrap.api.core import unquote

def _match_context_pack_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/context-packs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        pack_id, tail = rest.split("/", 1)
        return unquote(pack_id), "/" + tail
    return unquote(rest), ""

def _match_project_variation_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "variation":
        return unquote(parts[1])
    return None

def _match_project_editor_state_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-state":
        return unquote(parts[1])
    return None

def _match_project_editor_view_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-view":
        return unquote(parts[1])
    return None

def _match_project_editor_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-draft":
        return unquote(parts[1])
    return None

def _match_project_editor_clips_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-clips":
        return unquote(parts[1])
    return None

def _match_project_editor_clip_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-clip-draft":
        return unquote(parts[1])
    return None

def _match_project_section_template_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "section-templates":
        return unquote(parts[1])
    return None

def _match_project_track_template_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "track-templates":
        return unquote(parts[1])
    return None

def _match_project_editor_template_mapping_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-template-mapping":
        return unquote(parts[1])
    return None

def _match_project_editor_multitrack_clip_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-multitrack-clip-draft":
        return unquote(parts[1])
    return None

def _match_project_editor_preview_create_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-preview":
        return unquote(parts[1])
    return None

def _match_project_version_audio_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] in {"audio", "render-audio"}:
        return unquote(parts[1]), parts[2]
    return None

def _match_project_mix_tail(tail: str) -> tuple[str, str, str | None] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "mix-state":
        return unquote(parts[1]), "mix-state", None
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-state" and parts[3] == "reset":
        return unquote(parts[1]), "mix-state-reset", None
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "mix-preview":
        return unquote(parts[1]), "mix-preview-create", None
    if len(parts) == 5 and parts[0] == "versions" and parts[2] == "mix-preview":
        action = parts[4]
        if action in {"midi", "audio", "render-audio", "apply", "delete"}:
            return unquote(parts[1]), f"mix-preview-{action}", unquote(parts[3])
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-previews":
        return unquote(parts[1]), "mix-preview-detail", unquote(parts[3])
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-stems" and parts[3] == "render":
        return unquote(parts[1]), "mix-stems-render", None
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-stems" and parts[3] == "health":
        return unquote(parts[1]), "mix-stems-health", None
    return None

def _match_project_editor_preview_root_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 1 and parts[0] == "editor-previews":
        return "list"
    if len(parts) == 2 and parts[0] == "editor-previews" and parts[1] == "cleanup":
        return "cleanup"
    return None

def _match_project_editor_auditions_root_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] == "auditions":
        return unquote(parts[1])
    return None

def _match_project_editor_audition_reviews_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] == "audition-reviews":
        return unquote(parts[1])
    return None

def _match_project_editor_audition_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "editor-previews" and parts[2] == "auditions":
        return unquote(parts[1]), unquote(parts[3]), "detail"
    if len(parts) == 5 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] in {
        "midi",
        "audio",
        "render-audio",
        "review",
        "markers",
        "create-asset",
        "review-edit-preview",
        "review-edit",
        "provider-review-edit-preview",
        "create-context-pack",
        "review-task",
        "delete",
    }:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_editor_audition_marker_tail(tail: str) -> tuple[str, str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 6 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] == "markers":
        return unquote(parts[1]), unquote(parts[3]), unquote(parts[5]), "update"
    if len(parts) == 7 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] == "markers" and parts[6] == "delete":
        return unquote(parts[1]), unquote(parts[3]), unquote(parts[5]), "delete"
    return None

def _match_project_editor_preview_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "editor-previews":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] in {"patch", "song-plan", "midi", "audio", "render-audio", "delete", "apply"}:
        return unquote(parts[1]), parts[2]
    return None

def _match_project_edit_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] in {"edit", "edit-targets"}:
        return unquote(parts[1]), parts[2]
    return None

def _match_project_edit_preview_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "edit-preview":
        return unquote(parts[1]), "", "create"
    if len(parts) == 5 and parts[0] == "versions" and parts[2] == "edit-preview" and parts[4] in {"apply", "delete"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_edit_candidates_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "edit-candidates":
        return unquote(parts[1]), "create"
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "edit-candidates" and parts[3] == "ab":
        return unquote(parts[1]), "ab"
    return None

def _match_project_candidate_group_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "candidate-groups":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] in {"apply", "delete"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] in {"render-midi", "render-audio"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] == "usage":
        return unquote(parts[1]), "usage"
    return None

def _match_project_candidate_artifact_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 5 and parts[0] == "candidate-groups" and parts[2] == "candidates" and parts[4] in {"midi", "audio", "render-midi", "render-audio"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_review_task_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "review-tasks":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "review-tasks" and parts[2] in {"candidates", "provider-candidates", "decision-report", "judge-report", "resolve", "needs-more-work", "archive"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 4 and parts[0] == "review-tasks" and parts[2] == "decision-report" and parts[3] == "refresh":
        return unquote(parts[1]), "decision-report-refresh"
    if len(parts) == 4 and parts[0] == "review-tasks" and parts[2] == "judge-report" and parts[3] == "refresh":
        return unquote(parts[1]), "judge-report-refresh"
    return None

def _match_project_review_sprint_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "review-sprints":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "review-sprints" and parts[2] in {"refresh", "close", "archive", "tasks", "generate-local-candidates", "generate-provider-candidates", "conflicts", "recommendations", "metrics", "judge-summary", "closeout", "signoff"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "tasks" and parts[3] in {"remove", "reorder"}:
        return unquote(parts[1]), f"tasks-{parts[3]}"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "conflicts" and parts[3] == "refresh":
        return unquote(parts[1]), "conflicts-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "recommendations" and parts[3] == "refresh":
        return unquote(parts[1]), "recommendations-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "metrics" and parts[3] == "refresh":
        return unquote(parts[1]), "metrics-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "judge-summary" and parts[3] == "refresh":
        return unquote(parts[1]), "judge-summary-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "closeout" and parts[3] == "refresh":
        return unquote(parts[1]), "closeout-refresh"
    if len(parts) == 5 and parts[0] == "review-sprints" and parts[2] == "recommendations" and parts[4] == "context-pack":
        return unquote(parts[1]), f"recommendation-context-pack:{unquote(parts[3])}"
    if len(parts) == 3 and parts[0] == "review-sprints" and parts[2] == "action-queues":
        return unquote(parts[1]), "action-queues"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "action-queues":
        return unquote(parts[1]), f"action-queue:{unquote(parts[3])}:detail"
    if len(parts) == 5 and parts[0] == "review-sprints" and parts[2] == "action-queues" and parts[4] in {"run", "archive"}:
        return unquote(parts[1]), f"action-queue:{unquote(parts[3])}:{parts[4]}"
    return None

def _recommendation_action_for_task(report: JsonDocument, task_id: str) -> JsonDocument:
    actions = report.get("recommended_actions") if isinstance(report, dict) else []
    for action in _as_list(actions):
        if isinstance(action, dict) and action.get("task_id") == task_id:
            return action
    return {}

def _context_ref_count(preview: object) -> int:
    if not isinstance(preview, dict):
        return 0
    return len(preview.get("asset_refs") or []) + len(preview.get("reference_refs") or [])

def _match_project_review_task_candidate_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 5 and parts[0] == "review-tasks" and parts[2] == "candidates" and parts[4] in {"midi", "audio", "render-midi", "render-audio", "apply"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_prompt_ab_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 1 and parts[0] == "prompt-ab":
        return "", "list"
    if len(parts) == 2 and parts[0] == "prompt-ab":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "prompt-ab" and parts[2] == "delete":
        return unquote(parts[1]), "delete"
    return None

def _match_project_evaluate_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "evaluate":
        return unquote(parts[1])
    return None

__all__ = ['_context_ref_count', '_match_context_pack_route', '_match_project_candidate_artifact_tail', '_match_project_candidate_group_tail', '_match_project_edit_candidates_tail', '_match_project_edit_preview_tail', '_match_project_edit_tail', '_match_project_editor_audition_marker_tail', '_match_project_editor_audition_reviews_tail', '_match_project_editor_audition_tail', '_match_project_editor_auditions_root_tail', '_match_project_editor_clip_draft_tail', '_match_project_editor_clips_tail', '_match_project_editor_draft_tail', '_match_project_editor_multitrack_clip_draft_tail', '_match_project_editor_preview_create_tail', '_match_project_editor_preview_root_tail', '_match_project_editor_preview_tail', '_match_project_editor_state_tail', '_match_project_editor_template_mapping_tail', '_match_project_editor_view_tail', '_match_project_evaluate_tail', '_match_project_mix_tail', '_match_project_prompt_ab_tail', '_match_project_review_sprint_tail', '_match_project_review_task_candidate_tail', '_match_project_review_task_tail', '_match_project_section_template_tail', '_match_project_track_template_tail', '_match_project_variation_tail', '_match_project_version_audio_tail', '_recommendation_action_for_task']
