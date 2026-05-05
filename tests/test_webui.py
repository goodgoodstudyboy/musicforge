from song_agent.webui import panel_html


def test_webui_contains_music_fields():
    html = panel_html()

    assert "MusicForge Studio" in html
    assert "Provider Settings" in html
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
    assert "Validator" in html
    assert "SongPlan JSON" in html
    assert "Section</th><th>Bars</th><th>Start</th><th>End</th><th>Chords" in html
    assert "Track</th><th>Instrument</th><th>Notes</th><th>Pitch Range" in html
    assert "Check</th><th>Status" in html
    assert "Node</th><th>Status</th><th>Provider" in html


def test_webui_calls_runtime_view_apis():
    html = panel_html()

    assert "/timeline" in html
    assert "/nodes" in html
    assert "/tracks" in html
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
    assert "Export" in html


def test_webui_calls_batch_apis():
    html = panel_html()

    assert "/api/batches/import-csv" in html
    assert "/api/batches?include_hidden=1" in html
    assert "/api/batches/${encodeURIComponent(batchId)}" in html
    assert "/api/batches/${id}/launch" in html
    assert "/api/batches/${id}/pause" in html
    assert "/api/batches/${id}/resume" in html
    assert "/api/batches/${id}/retry-failed" in html
    assert "/api/batches/${id}/export" in html
    assert "/api/batches/${id}/open-folder" in html
    assert "/api/batches/${id}/delete" in html
