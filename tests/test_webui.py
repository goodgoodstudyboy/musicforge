from song_agent.webui import panel_html


def test_webui_contains_music_fields():
    html = panel_html()

    assert "MusicForge Studio" in html
    assert "Provider Settings" in html
    assert "Prompt Templates" in html
    assert 'id="provider-base-url"' in html
    assert 'id="provider-api-key"' in html
    assert 'id="provider-model"' in html
    assert 'id="generation_mode"' in html
    assert 'id="pipeline_mode"' in html
    assert 'id="title"' in html
    assert 'id="style"' in html
    assert 'id="theme"' in html
    assert 'id="tempo_bpm"' in html
    assert 'id="job-list"' in html
    assert "Download MIDI" in html
    assert 'id="include-hidden"' in html


def test_webui_contains_runtime_tabs():
    html = panel_html()

    assert "Timeline" in html
    assert "Nodes" in html
    assert "Tracks" in html
    assert "Stems" in html
    assert "Quality" in html
    assert "Validator" in html
    assert "SongPlan JSON" in html
    assert "Section</th><th>Bars</th><th>Start</th><th>End</th><th>Chords" in html
    assert "Energy</th><th>Tension</th><th>Density" in html
    assert "Track</th><th>Instrument</th><th>Notes</th><th>Pitch Range" in html
    assert "Check</th><th>Status" in html
    assert "Node</th><th>Status</th><th>Provider" in html
    assert "Stem</th><th>Role</th><th>Instrument</th><th>Notes" in html
    assert "Quality view will be available after the song plan is generated." in html
    assert "Warning</th>" in html
    assert "Critic Passed" in html


def test_webui_calls_runtime_view_apis():
    html = panel_html()

    assert "/timeline" in html
    assert "/nodes" in html
    assert "/tracks" in html
    assert "/stems" in html
    assert "/quality" in html
    assert "/validator" in html


def test_webui_calls_nodes_api():
    html = panel_html()

    assert "renderNodes" in html
    assert "/nodes/${encodeURIComponent(nodeName)}" in html
    assert "Retry node" in html
    assert "/dependencies" in html
    assert "node-retry" in html


def test_webui_contains_job_action_buttons_and_calls():
    html = panel_html()

    assert "Open Folder" in html
    assert "Hide" in html
    assert "Unhide" in html
    assert "Delete" in html
    assert "Cancel" in html
    assert "Retry" in html
    assert "/hide" in html
    assert "/unhide" in html
    assert "/delete" in html
    assert "/cancel" in html
    assert "/retry" in html
    assert "/api/jobs?include_hidden=1" in html


def test_webui_displays_heartbeat_and_attempts():
    html = panel_html()

    assert "Attempt" in html
    assert "Retry Count" in html
    assert "Heartbeat" in html
    assert "Stalled" in html


def test_webui_contains_provider_form_calls():
    html = panel_html()

    assert "/api/provider" in html
    assert "/api/provider/reset" in html
    assert "providerPayload" in html
    assert "api_key_masked" in html
    assert "/api/provider/test" in html
    assert "providerSnapshotHtml" in html
    assert "/api/prompt-templates" in html
    assert "prompt-template-system" in html
    assert "Save Template Override" in html


def test_webui_contains_renderer_settings():
    html = panel_html()

    assert "Renderer Settings" in html
    assert 'id="renderer-form"' in html
    assert 'id="renderer-fluidsynth-path"' in html
    assert 'id="renderer-soundfont-path"' in html
    assert 'id="renderer-sample-rate"' in html
    assert 'id="renderer-gain"' in html
    assert "Test renderer" in html
    assert "/api/renderer" in html
    assert "/api/renderer/reset" in html
    assert "/api/renderer/test" in html
    assert "rendererPayload" in html


def test_webui_contains_audio_render_controls():
    html = panel_html()

    assert "Render Audio" in html
    assert "Download WAV" in html
    assert "<audio" in html
    assert "controls src=\"/api/jobs/${encodeURIComponent(job.job_id)}/audio\"" in html
    assert "/render-audio" in html
    assert "/audio" in html


def test_webui_contains_stem_controls():
    html = panel_html()

    assert "Render Stems" in html
    assert "Render Stem Audio" in html
    assert "Download MIDI" in html
    assert "Download WAV" in html
    assert "Solo" in html
    assert "Mute" in html
    assert "Stems have not been rendered yet." in html
    assert "SongPlan is not available yet." in html
    assert "/render-stems" in html
    assert "/render-stem-audio" in html
    assert "soloStem" in html
    assert "muteStem" in html


def test_webui_contains_access_token_prompt():
    html = panel_html()

    assert "Access token" in html
    assert 'id="auth-form"' in html
    assert 'id="auth-token"' in html
    assert "Unlock" in html
    assert "sessionStorage" in html
    assert "musicforge_access_token" in html
    assert "localStorage" not in html


def test_webui_fetch_injects_bearer_and_handles_401():
    html = panel_html()

    assert 'headers.set("Authorization", `Bearer ${accessToken}`)' in html
    assert "res.status === 401" in html
    assert 'sessionStorage.removeItem("musicforge_access_token")' in html
    assert "showAuthLock" in html
    assert "auth_required" in html


def test_webui_contains_batch_tab_controls():
    html = panel_html()

    assert "Batch" in html
    assert 'id="batch-form"' in html
    assert 'id="batch-csv-file"' in html
    assert 'id="batch-csv-text"' in html
    assert 'id="batch-generation-mode"' in html
    assert 'id="batch-pipeline-mode"' in html
    assert 'id="batch-max-concurrency"' in html
    assert "Import" in html
    assert "Launch" in html
    assert "Pause" in html
    assert "Resume" in html
    assert "Retry Failed" in html
    assert "Render Audio" in html
    assert "Render Failed Audio" in html
    assert "Render Stems" in html
    assert "Render Stem Audio" in html
    assert "Render Failed Stems" in html
    assert "Render Failed Stem Audio" in html
    assert "Export" in html


def test_webui_contains_project_workspace_controls():
    html = panel_html()

    assert "Projects" in html
    assert "Project Detail" in html
    assert 'id="project-form"' in html
    assert 'id="project-name"' in html
    assert 'id="project-description"' in html
    assert 'id="project-tags"' in html
    assert 'id="project-list"' in html
    assert 'id="project-detail"' in html
    assert "New Project" in html
    assert "New Version" in html
    assert "Add Existing Job" in html
    assert "Set Selected" in html
    assert "Set Final" in html
    assert "Create Variation" in html
    assert "Edit Version" in html
    assert "Create Edit Version" in html
    assert "Generate Preview" in html
    assert "Apply Preview" in html
    assert "Candidates" in html
    assert "Candidate Count" in html
    assert "Generate Candidates" in html
    assert "Generate Prompt A/B" in html
    assert "Provider Calls" in html
    assert "Render Group MIDI" in html
    assert "Render Group Audio" in html
    assert "Render MIDI" in html
    assert "Download MIDI" in html
    assert "Render Audio" in html
    assert "Download WAV" in html
    assert "Apply Candidate" in html
    assert "Delete Candidate Group" in html
    assert "Edit Preset" in html
    assert "Apply Preset" in html
    assert "Save Current As Preset" in html
    assert "Evaluate Gate" in html
    assert "Quality Gate" in html
    assert "Final Export" in html
    assert "Generate Final Export" in html
    assert "Build ZIP" in html
    assert "Download ZIP" in html
    assert 'id="project-search"' in html
    assert 'id="project-status-filter"' in html
    assert 'id="project-variant-filter"' in html
    assert "Compare" in html
    assert "Export JSON" in html
    assert "Delete Project" in html


def test_webui_contains_assets_workspace_controls():
    html = panel_html()

    assert "Assets" in html
    assert 'id="asset-search"' in html
    assert 'id="asset-type-filter"' in html
    assert 'id="asset-list"' in html
    assert 'id="asset-detail"' in html
    assert "Render Asset MIDI" in html
    assert "Render Asset Audio" in html
    assert "Download Asset MIDI" in html
    assert "Download Asset WAV" in html
    assert "Extract Asset" in html
    assert "Save Motif" in html
    assert "Save Chords" in html
    assert "Save Drums" in html
    assert "Save Bass" in html
    assert "Save as Asset" in html
    assert "Asset References" in html
    assert "asset-ref-list" in html
    assert "<audio" in html


def test_webui_contains_reference_workspace_controls():
    html = panel_html()

    assert "References" in html
    assert 'id="reference-import-form"' in html
    assert 'id="reference-type"' in html
    assert 'id="reference-file"' in html
    assert 'id="reference-search"' in html
    assert 'id="reference-type-filter"' in html
    assert 'id="reference-list"' in html
    assert 'id="reference-detail"' in html
    assert "Import Reference" in html
    assert "Download Original" in html
    assert "Create Asset" in html
    assert "Analysis" in html
    assert "Analyze Reference" in html
    assert "Generate MIDI Slices" in html
    assert "Render MIDI" in html
    assert "Render WAV" in html
    assert "Create Asset" in html
    assert ".waveform" in html
    assert "Reference Materials" in html
    assert "reference-ref-list" in html
    assert "Include Reference Summaries" in html


def test_webui_calls_asset_apis():
    html = panel_html()

    assert "/api/assets" in html
    assert "/api/assets/extract/from-job" in html
    assert "/api/assets/extract/from-project-version" in html
    assert "/api/assets/extract/from-candidate" in html
    assert "/api/assets/${encodeURIComponent(assetId)}" in html
    assert "/render-midi" in html
    assert "/render-audio" in html
    assert "/midi" in html
    assert "/audio" in html
    assert "/favorite" in html
    assert "/unfavorite" in html
    assert "/hide" in html
    assert "/unhide" in html
    assert "/delete" in html
    assert "assetRefsPayload" in html
    assert "asset_refs" in html


def test_webui_calls_reference_apis():
    html = panel_html()

    assert "/api/references" in html
    assert "/api/references/import" in html
    assert "/api/references/${encodeURIComponent(referenceId)}" in html
    assert "/api/references/${encodeURIComponent(referenceId)}/analysis" in html
    assert "/api/references/${encodeURIComponent(reference.reference_id)}/analyze" in html
    assert "/api/references/${encodeURIComponent(reference.reference_id)}/slices" in html
    assert "/slices/${encodeURIComponent(button.dataset.sliceId)}/render-midi" in html
    assert "/slices/${encodeURIComponent(button.dataset.sliceId)}/render-audio" in html
    assert "/slices/${encodeURIComponent(button.dataset.sliceId)}/create-asset" in html
    assert "file_url" in html
    assert "/create-asset" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/references" in html
    assert "/references/link" in html
    assert "/references/unlink" in html
    assert "referenceRefsPayload" in html
    assert "reference_refs" in html
    assert "fileToBase64" in html


def test_webui_calls_library_context_pack_apis():
    html = panel_html()

    assert "Library" in html
    assert "/api/library/index" in html or "/api/library/rebuild" in html
    assert "/api/library/search" in html
    assert "/api/library/recommend" in html
    assert "/api/context-packs" in html
    assert "/api/context-packs/${encodeURIComponent(packId)}/apply-preview" in html
    assert "context_pack_id" in html
    assert "context-pack-select" in html
    assert "song-suggest-context" in html
    assert "score_breakdown" in html


def test_webui_calls_project_apis():
    html = panel_html()

    assert "/api/projects" in html
    assert "include_hidden" in html
    assert "URLSearchParams" in html
    assert 'params.set("q"' in html
    assert "/api/projects/${encodeURIComponent(projectId)}" in html
    assert "/api/projects/${id}/versions" in html
    assert "/api/projects/${id}/versions/from-job" in html
    assert "/versions/${encodeURIComponent(parentId)}/variation" in html
    assert "/versions/${encodeURIComponent(parent)}/edit" in html
    assert "/edit-preview" in html
    assert "/editor-state" in html
    assert "/editor-preview" in html
    assert "/editor-previews/" in html
    assert "Open Editor" in html
    assert "project-editor-preview" in html
    assert "Add Section" in html
    assert "Duplicate Section" in html
    assert "Delete Section" in html
    assert "Resize Section" in html
    assert "Move Section" in html
    assert "Add Track" in html
    assert "Duplicate Track" in html
    assert "Delete Track" in html
    assert "Rename Track" in html
    assert "Preview History" in html
    assert "/editor-previews/cleanup" in html
    assert "describeProjectEditorOperation" in html
    assert "/edit-candidates" in html
    assert "/edit-candidates/ab" in html
    assert "/candidate-groups" in html
    assert "/usage/provider" in html
    assert "/prompt-ab" in html
    assert "/render-midi" in html
    assert "/render-audio" in html
    assert "/midi" in html
    assert "/audio" in html
    assert "/apply" in html
    assert "/edit-targets" in html
    assert "/api/edit-presets" in html
    assert "projectEditPresetPayload" in html
    assert "/api/jobs/${encodeURIComponent(job.job_id)}/edit" in html
    assert "/versions/${encodeURIComponent(target.dataset.projectEvaluateVersion)}/evaluate" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/quality-gate" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/quality-gate/evaluate-all" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/final-export" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/final-export/zip" in html
    assert "/final-export.zip" in html
    assert "/api/projects/${id}/selected" in html
    assert "/api/projects/${id}/final" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/compare" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/export" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/events" in html
    assert "/api/projects/${id}/hide" in html
    assert "/api/projects/${id}/unhide" in html
    assert "/api/projects/${id}/delete" in html


def test_webui_compare_layout_is_responsive():
    html = panel_html()

    assert ".compare-grid" in html
    assert ".table-scroll" in html
    assert "wrap-cell" in html
    assert "WAV not rendered" in html


def test_webui_candidate_review_layout_is_responsive():
    html = panel_html()

    assert ".candidate-grid" in html
    assert ".candidate-group" in html
    assert ".candidate-card" in html
    assert ".candidate-grid { grid-template-columns: 1fr; }" in html


def test_webui_calls_batch_apis():
    html = panel_html()

    assert "/api/batches/import-csv" in html
    assert "/api/batches?include_hidden=1" in html
    assert "/api/batches/${encodeURIComponent(batchId)}" in html
    assert "/api/batches/${id}/launch" in html
    assert "/api/batches/${id}/pause" in html
    assert "/api/batches/${id}/resume" in html
    assert "/api/batches/${id}/retry-failed" in html
    assert "/api/batches/${id}/render-audio" in html
    assert "/api/batches/${id}/render-failed-audio" in html
    assert "/api/batches/${id}/render-stems" in html
    assert "/api/batches/${id}/render-stem-audio" in html
    assert "/api/batches/${id}/render-failed-stems" in html
    assert "/api/batches/${id}/render-failed-stem-audio" in html
    assert "/api/batches/${id}/export" in html
    assert "/api/batches/${id}/open-folder" in html
    assert "/api/batches/${id}/delete" in html
