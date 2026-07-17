from __future__ import annotations

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext

from typing import Any

from song_agent.application.interface_persistence import write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesRenderEditorPreviewAudio(QualityRouteContext):
    def _render_editor_preview_audio(self, project_id: str, preview_id: str) -> Any:
        store = _interfaces_api_runtime.EditorPreviewStore(self.project_store.project_dir(project_id))
        preview = store.read_preview(preview_id)
        preview_dir = store.preview_dir(preview_id)
        midi_path = preview_dir / "song.mid"
        try:
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
        except FileNotFoundError as exc:
            raise FileNotFoundError("Parent version not found.") from exc
        if preview.parent_job_id != parent_job.job_id:
            raise _interfaces_api_runtime.EditorPatchStaleError("Editor preview parent job does not match the current version.")
        if _interfaces_api_runtime.editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
            raise _interfaces_api_runtime.EditorPatchStaleError("Editor preview is stale because the parent song-plan.json has changed.")
        patch = store.read_patch(preview_id)
        result = _interfaces_api_runtime.apply_editor_patch(parent_plan, patch)
        result.plan.validate()
        write_interface_document(preview_dir / "song-plan.json", result.plan.to_dict())
        _interfaces_api_runtime.render_midi(result.plan, midi_path)
        report_path = preview_dir / "validator-report.json"
        report = _interfaces_api_runtime.read_json(report_path) if report_path.exists() else {}
        report.update(_interfaces_api_runtime._build_validator_report(preview_dir / "song-plan.json", midi_path))
        try:
            config, _sources = _interfaces_api_runtime.load_renderer_config()
            config.validate_ready_for_render()
            wav_path = _interfaces_api_runtime.render_audio(midi_path, preview_dir / "song.wav", config)
        except _interfaces_api_runtime.RendererError as exc:
            updated = store.update_preview_audio(
                preview_id,
                status="failed",
                audio_error=str(_interfaces_api_runtime.sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."),
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(project_id, "editor_preview_audio_failed", {"preview_id": preview_id, "error": updated.audio_error})
            raise
        updated = store.update_preview_audio(
            preview_id,
            status="completed",
            audio_url=f"/api/projects/{project_id}/editor-previews/{preview_id}/audio",
            audio_size_bytes=wav_path.stat().st_size,
            now=_interfaces_api_runtime._utc_now(),
        )
        report["audio"] = _interfaces_api_runtime._audio_report(wav_path)
        write_interface_document(report_path, report)
        self.project_store.append_event(project_id, "editor_preview_audio_rendered", {"preview_id": preview_id, "size_bytes": wav_path.stat().st_size})
        return updated
