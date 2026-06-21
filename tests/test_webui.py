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


def test_webui_contains_acceptance_workspace():
    html = panel_html()

    assert "Acceptance" in html
    assert 'id="acceptance-form"' in html
    assert 'id="acceptance-profile"' in html
    assert 'id="acceptance-songbook"' in html
    assert 'id="acceptance-song-id"' in html
    assert 'id="acceptance-list"' in html
    assert 'id="acceptance-detail"' in html
    assert "/api/acceptance/suites" in html
    assert "/api/acceptance/profiles" in html
    assert "/api/acceptance/songbook" in html
    assert "Regression Songbook" in html
    assert "release_candidate" in html
    assert "song_id" in html
    assert "Acceptance Diff" in html
    assert 'id="acceptance-diff-suite"' in html
    assert "Human Review Pack" in html
    assert 'id="acceptance-human-review-response"' in html
    assert "Acceptance Analytics" in html
    assert 'id="acceptance-analytics"' in html
    assert 'id="acceptance-refresh-analytics"' in html
    assert "Acceptance Fix Sprints" in html
    assert 'id="acceptance-fix-sprints"' in html
    assert 'id="acceptance-create-fix-sprint"' in html
    assert "Fix Planning" in html
    assert 'id="acceptance-fix-plans"' in html
    assert 'id="acceptance-fix-plan-create"' in html
    assert 'id="acceptance-fix-plan-create-sprint"' in html
    assert "Fix Plan Outcome Review" in html
    assert "Refresh Outcome Review" in html
    assert 'id="acceptance-fix-plan-review"' in html
    assert "/outcome-review/refresh" in html
    assert "Plan Effectiveness" in html
    assert "Knowledge Base" in html
    assert 'id="acceptance-kb"' in html
    assert 'id="acceptance-kb-refresh"' in html
    assert 'id="acceptance-kb-recommend"' in html
    assert "Issue Patterns" in html
    assert "Style Patterns" in html
    assert "Recommendation Panel" in html
    assert "/api/acceptance/fix-sprints" in html
    assert "/api/acceptance/fix-plans" in html
    assert "/api/acceptance/analytics" in html
    assert "/api/acceptance/kb" in html
    assert "/analytics/refresh" in html
    assert "Songbook Heatmap" in html
    assert "Issue Taxonomy" in html
    assert "Recommendations" in html
    assert "create-review-task" in html
    assert "/human-review-packs" in html
    assert "/review-imports" in html
    assert "/diff" in html
    assert "/cases/${encodeURIComponent" in html
    assert "/report" in html
    assert "/signoff" in html


def test_webui_contains_encoded_audio_acceptance_controls():
    html = panel_html()

    assert 'id="release-require-encoded-audio-review"' in html
    assert "Require encoded audio review" in html
    assert 'id="release-require-format-decision"' in html
    assert "Require format decision" in html
    assert 'id="release-require-rights-clearance"' in html
    assert "Require rights clearance" in html
    assert "Rights Clearance" in html
    assert "/rights/parties" in html
    assert "/rights/refresh" in html
    assert "/rights/tracks/${encodeURIComponent" in html
    assert "Format Decision Workbench" in html
    assert "/format-decisions" in html
    assert "Release Operations" in html
    assert 'id="release-operations-refresh"' in html
    assert 'id="release-operations-export"' in html
    assert 'id="release-operations-zip"' in html
    assert 'id="release-operations-verify"' in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/operations" in html
    assert "/operations/refresh" in html
    assert "/operations/export/zip" in html
    assert "/operations/verify" in html
    assert "Release Operations Runbook" in html
    assert 'id="release-runbook-create"' in html
    assert 'id="release-runbook-run-safe"' in html
    assert 'id="release-runbook-refresh-stale"' in html
    assert 'id="release-runbook-export"' in html
    assert 'id="release-runbook-zip"' in html
    assert 'id="release-runbook-verify"' in html
    assert "/operations/runbooks" in html
    assert "/run-safe" in html
    assert "Release Operations Signoff" in html
    assert 'id="release-operations-sign"' in html
    assert 'id="release-operations-archive-export"' in html
    assert 'id="release-operations-archive-zip"' in html
    assert 'id="release-operations-archive-verify"' in html
    assert 'id="release-operations-change-create"' in html
    assert 'id="release-operations-reset-signoff"' in html
    assert "/operations/signoff" in html
    assert "/operations/signoff/reset" in html
    assert "/operations/archive/export" in html
    assert "/operations/archive/export/zip" in html
    assert "/operations/archive/verify" in html
    assert "/operations/archive.zip" in html
    assert "/operations/change-requests" in html
    assert "Release Operations Audit Ledger" in html
    assert 'id="release-operations-audit-refresh"' in html
    assert 'id="release-operations-audit-export"' in html
    assert 'id="release-operations-audit-zip"' in html
    assert 'id="release-operations-audit-verify"' in html
    assert "/operations/audit/refresh" in html
    assert "/operations/audit/export" in html
    assert "/operations/audit/export/zip" in html
    assert "/operations/audit/verify" in html
    assert "/operations/audit.zip" in html
    assert "Reviewer Pack" in html
    assert "Refresh Reviewer Report" in html
    assert "Verify Reviewer ZIP" in html
    assert "Retrospective" in html
    assert "Risk hotspots" in html
    assert 'id="release-reviewer-pack-refresh"' in html
    assert 'id="release-reviewer-pack-export"' in html
    assert 'id="release-reviewer-pack-zip"' in html
    assert 'id="release-reviewer-pack-verify"' in html
    assert "/operations/reviewer-pack" in html
    assert "/operations/reviewer-pack/verify" in html
    assert "/operations/reviewer-pack.zip" in html
    assert "Portfolio Audit" in html
    assert 'id="portfolio-audit-list"' in html
    assert 'id="portfolio-audit-detail"' in html
    assert 'id="portfolio-audit-form"' in html
    assert 'id="portfolio-audit-name"' in html
    assert 'id="portfolio-audit-release-ids"' in html
    assert 'id="portfolio-audit-require-reviewer-packs"' in html
    assert 'id="portfolio-audit-require-audit"' in html
    assert 'id="portfolio-audit-require-archive"' in html
    assert 'id="portfolio-audit-refresh"' in html
    assert 'id="portfolio-audit-export"' in html
    assert 'id="portfolio-audit-zip"' in html
    assert 'id="portfolio-audit-verify"' in html
    assert "Release Readiness Ranking" in html
    assert "Portfolio Risk Register" in html
    assert "Deterministic Recommendations" in html
    assert "Portfolio Governance Queue" in html
    assert 'id="portfolio-governance-create"' in html
    assert "portfolio-governance-run-safe" in html
    assert "portfolio-governance-export" in html
    assert "portfolio-governance-zip" in html
    assert "portfolio-governance-verify" in html
    assert "Governance Closeout" in html
    assert "portfolio-governance-signoff" in html
    assert "portfolio-governance-force-signoff" in html
    assert "portfolio-governance-cr" in html
    assert "portfolio-governance-reset" in html
    assert "portfolio-governance-archive-export" in html
    assert "portfolio-governance-archive-zip" in html
    assert "portfolio-governance-archive-verify" in html
    assert "Portfolio Governance Audit Ledger" in html
    assert 'id="portfolio-governance-audit-refresh"' in html
    assert 'id="portfolio-governance-audit-export"' in html
    assert 'id="portfolio-governance-audit-zip"' in html
    assert 'id="portfolio-governance-audit-verify"' in html
    assert "/governance-audit.zip" in html
    assert "Portfolio Governance Reviewer Pack" in html
    assert 'id="portfolio-governance-reviewer-refresh"' in html
    assert 'id="portfolio-governance-reviewer-export"' in html
    assert 'id="portfolio-governance-reviewer-zip"' in html
    assert 'id="portfolio-governance-reviewer-verify"' in html
    assert "/governance-reviewer-pack" in html
    assert "/governance-reviewer-pack.zip" in html
    assert "Portfolio Governance Final Board" in html
    assert 'id="portfolio-governance-final-board-refresh"' in html
    assert 'id="portfolio-governance-final-board-import-accepted"' in html
    assert 'id="portfolio-governance-final-board-signoff"' in html
    assert 'id="portfolio-governance-final-board-cr"' in html
    assert 'id="portfolio-governance-final-board-reset"' in html
    assert 'id="portfolio-governance-final-board-export"' in html
    assert 'id="portfolio-governance-final-board-zip"' in html
    assert 'id="portfolio-governance-final-board-verify"' in html
    assert "/governance-final-board" in html
    assert "/governance-final-board.zip" in html
    assert "Governance Evidence Vault" in html
    assert 'id="portfolio-governance-vault-refresh"' in html
    assert 'id="portfolio-governance-vault-export"' in html
    assert 'id="portfolio-governance-vault-zip"' in html
    assert 'id="portfolio-governance-vault-verify"' in html
    assert "/governance-evidence-vault" in html
    assert "/governance-evidence-vault.zip" in html
    assert "Governance Public Attestation" in html
    assert 'id="portfolio-governance-attestation-refresh"' in html
    assert 'id="portfolio-governance-attestation-export"' in html
    assert 'id="portfolio-governance-attestation-zip"' in html
    assert 'id="portfolio-governance-attestation-verify"' in html
    assert "/governance-attestation" in html
    assert "/governance-attestation.zip" in html
    assert "Governance Attestation Registry" in html
    assert 'id="portfolio-governance-attestation-registry-register-current"' in html
    assert 'id="portfolio-governance-attestation-registry-refresh"' in html
    assert 'id="portfolio-governance-attestation-registry-export"' in html
    assert 'id="portfolio-governance-attestation-registry-zip"' in html
    assert 'id="portfolio-governance-attestation-registry-verify"' in html
    assert "/governance-attestation-registry" in html
    assert "/governance-attestation-registry.zip" in html
    assert "Governance Attestation Portal Snapshot" in html
    assert 'id="portfolio-governance-attestation-portal-refresh"' in html
    assert 'id="portfolio-governance-attestation-portal-export"' in html
    assert 'id="portfolio-governance-attestation-portal-zip"' in html
    assert 'id="portfolio-governance-attestation-portal-verify"' in html
    assert "/governance-attestation-portal" in html
    assert "/governance-attestation-portal.zip" in html
    assert "Portal Review Response" in html
    assert 'id="portfolio-governance-attestation-portal-review-refresh-pack"' in html
    assert 'id="portfolio-governance-attestation-portal-review-export-pack"' in html
    assert 'id="portfolio-governance-attestation-portal-review-zip-pack"' in html
    assert 'id="portfolio-governance-attestation-portal-review-verify-pack"' in html
    assert 'id="portfolio-governance-attestation-portal-review-import-response"' in html
    assert 'id="portfolio-governance-attestation-portal-review-create-change-request"' in html
    assert "/governance-attestation-portal-review" in html
    assert "/governance-attestation-portal-review-pack.zip" in html
    assert "Accepted Evidence" in html
    assert 'id="portfolio-governance-attestation-accepted-evidence-refresh"' in html
    assert 'id="portfolio-governance-attestation-accepted-evidence-export"' in html
    assert 'id="portfolio-governance-attestation-accepted-evidence-zip"' in html
    assert 'id="portfolio-governance-attestation-accepted-evidence-verify"' in html
    assert 'id="portfolio-governance-attestation-accepted-evidence-archive"' in html
    assert "/governance-attestation-accepted-evidence" in html
    assert "/governance-attestation-accepted-evidence.zip" in html
    assert "Transparency Feed" in html
    assert 'id="portfolio-governance-attestation-transparency-refresh"' in html
    assert 'id="portfolio-governance-attestation-transparency-export"' in html
    assert 'id="portfolio-governance-attestation-transparency-zip"' in html
    assert 'id="portfolio-governance-attestation-transparency-verify"' in html
    assert "/governance-attestation-transparency" in html
    assert "/governance-attestation-transparency.zip" in html
    assert "Transparency Acknowledgement" in html
    assert 'id="portfolio-governance-attestation-transparency-ack-refresh-pack"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-export-pack"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-zip-pack"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-verify-pack"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-import-response"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-refresh-evidence"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-export-evidence"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-zip-evidence"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-verify-evidence"' in html
    assert 'id="portfolio-governance-attestation-transparency-ack-create-change-request"' in html
    assert "/governance-attestation-transparency-acknowledgement" in html
    assert "/governance-attestation-transparency-acknowledgement-pack.zip" in html
    assert "/governance-attestation-transparency-acknowledgement-evidence.zip" in html
    assert "/api/release-portfolio-audits" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/refresh" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/export/zip" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/archive/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/responses/import" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/verify" in html
    assert "/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/verify" in html
    assert "Public Trust Center" in html
    assert "Trust Operations Hub" in html
    assert 'id="trust-operations-hub-refresh"' in html
    assert 'id="trust-operations-hub-export"' in html
    assert 'id="trust-operations-hub-zip"' in html
    assert 'id="trust-operations-hub-verify"' in html
    assert 'id="trust-operations-hub-signoff"' in html
    assert 'id="trust-operations-hub-change-request"' in html
    assert 'id="trust-operations-hub-reset"' in html
    assert "/api/trust-operations/hubs/default.zip" in html
    assert "Trust Operations Runbook" in html
    assert 'id="trust-operations-runbook-create"' in html
    assert 'id="trust-operations-runbook-run-safe"' in html
    assert 'id="trust-operations-runbook-export"' in html
    assert 'id="trust-operations-runbook-zip"' in html
    assert 'id="trust-operations-runbook-verify"' in html
    assert "Trust Operations Incidents" in html
    assert "Trust Operations Knowledge" in html
    assert 'id="trust-operations-knowledge-refresh"' in html
    assert 'id="trust-operations-knowledge-create-guard"' in html
    assert 'id="trust-operations-knowledge-run-guards"' in html
    assert 'id="trust-operations-knowledge-export"' in html
    assert 'id="trust-operations-knowledge-verify"' in html
    assert "Trust Operations Controls" in html
    assert 'id="trust-operations-controls-refresh"' in html
    assert 'id="trust-operations-controls-policy"' in html
    assert 'id="trust-operations-controls-assess"' in html
    assert 'id="trust-operations-controls-export"' in html
    assert 'id="trust-operations-controls-zip"' in html
    assert 'id="trust-operations-controls-verify"' in html
    assert "Trust Control Signoff" in html
    assert 'id="trust-operations-control-signoff-sign"' in html
    assert 'id="trust-operations-control-signoff-exception"' in html
    assert 'id="trust-operations-control-signoff-cr"' in html
    assert 'id="trust-operations-control-signoff-reset"' in html
    assert 'id="trust-operations-control-signoff-export"' in html
    assert 'id="trust-operations-control-signoff-zip"' in html
    assert 'id="trust-operations-control-signoff-verify"' in html
    assert "/api/trust-operations/control-signoff/default/download" in html
    assert 'id="trust-operations-incidents-refresh"' in html
    assert 'id="trust-operations-incidents-triage"' in html
    assert 'id="trust-operations-incidents-plan"' in html
    assert 'id="trust-operations-incidents-evidence"' in html
    assert 'id="trust-operations-incidents-close"' in html
    assert 'id="trust-operations-incidents-export"' in html
    assert 'id="trust-operations-incidents-zip"' in html
    assert 'id="trust-operations-incidents-verify"' in html
    assert 'id="public-trust-center-refresh"' in html
    assert 'id="public-trust-center-export"' in html
    assert 'id="public-trust-center-zip"' in html
    assert 'id="public-trust-center-verify"' in html
    assert 'id="public-trust-center-archive"' in html
    assert 'id="public-trust-center-anchor-register"' in html
    assert 'id="public-trust-center-anchor-export"' in html
    assert 'id="public-trust-center-anchor-zip"' in html
    assert 'id="public-trust-center-anchor-verify"' in html
    assert 'id="public-trust-center-distribution-kit-refresh"' in html
    assert 'id="public-trust-center-distribution-kit-export"' in html
    assert 'id="public-trust-center-distribution-kit-zip"' in html
    assert 'id="public-trust-center-distribution-kit-verify"' in html
    assert 'id="public-trust-center-distribution-kit-acceptance-template"' in html
    assert 'id="public-trust-center-distribution-kit-accepted-evidence-export"' in html
    assert 'id="public-trust-center-distribution-kit-accepted-evidence-zip"' in html
    assert 'id="public-trust-center-distribution-kit-accepted-evidence-verify"' in html
    assert 'id="public-trust-center-acceptance-board-refresh"' in html
    assert 'id="public-trust-center-acceptance-board-export"' in html
    assert 'id="public-trust-center-acceptance-board-zip"' in html
    assert 'id="public-trust-center-acceptance-board-verify"' in html
    assert 'id="public-trust-center-acceptance-board-signoff-draft"' in html
    assert "/api/public-trust-centers/ptc-default.zip" in html
    assert "/api/public-trust-centers/ptc-default/anchor-registry/download" in html
    assert "/api/public-trust-centers/ptc-default/distribution-kit/download" in html
    assert "/api/public-trust-centers/ptc-default/acceptance-board/download" in html
    assert "/api/public-trust-centers/ptc-default/refresh" in html
    assert "/api/public-trust-centers/ptc-default/verify" in html
    assert "/api/public-trust-centers/ptc-default/distribution-kit/verify" in html
    assert "/api/public-trust-centers/ptc-default/acceptance-board/verify" in html
    assert "/api/release-portfolio-governance-queues" in html
    assert "/governance-queues" in html
    assert "/run-safe" in html
    assert "/signoff/reset" in html
    assert "/change-requests" in html
    assert "/archive/export" in html
    assert "/archive/zip" in html
    assert "/archive/verify" in html
    assert "/archive.zip" in html
    assert 'id="release-refresh-encoded-audio-health"' in html
    assert "/encoded-audio/health" in html
    assert "/encoded-audio/acceptance/refresh" in html


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
    assert "Delivery QA" in html
    assert "Refresh Delivery QA" in html
    assert "Sign Delivery" in html
    assert "Force Sign" in html
    assert "Reset Signoff" in html
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
    assert "/editor-clips" in html
    assert "/editor-clip-draft" in html
    assert "/api/editor-templates" in html
    assert "/section-templates" in html
    assert "/track-templates" in html
    assert "/editor-template-mapping" in html
    assert "/editor-multitrack-clip-draft" in html
    assert "/editor-preview" in html
    assert "/editor-previews/" in html
    assert "/auditions" in html
    assert "/versions/${encodeURIComponent(parentVersion)}/render-audio" in html
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
    assert "/api/projects/${encodeURIComponent(project.project_id)}/delivery-qa" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/delivery-qa/refresh" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff/reset" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/release-targets" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/add-to-release" in html
    assert "/api/projects/${id}/selected" in html
    assert "/api/projects/${id}/final" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/compare" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/export" in html
    assert "/api/projects/${encodeURIComponent(project.project_id)}/events" in html
    assert "/api/projects/${id}/hide" in html
    assert "/api/projects/${id}/unhide" in html
    assert "/api/projects/${id}/delete" in html


def test_webui_contains_release_workspace_controls():
    html = panel_html()

    assert "Release Workspace" in html
    assert "Release QA" in html
    assert "Release Export" in html
    assert "Release Signoff" in html
    assert "Audio Lab" in html
    assert "Release Audio QA" in html
    assert "Audio Review Board" in html
    assert "Tracklist" in html
    assert "Add to Release" in html
    assert "/api/releases" in html
    assert "/api/releases?include_hidden=1" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/tracks" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/tracks/${encodeURIComponent(button.dataset.trackId)}/refresh" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/tracks/${encodeURIComponent(button.dataset.trackId)}/remove" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/qa" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/qa/refresh" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/audio-qa" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews/refresh-summary" in html
    assert "/mix-patch-draft" in html
    assert 'id="release-require-per-track-audio-review"' in html
    assert 'id="release-require-stem-audio-health"' in html
    assert 'id="release-require-current-mix-state"' in html
    assert "Audio Revision Workbench" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions" in html
    assert "/candidates/generate" in html
    assert 'id="release-audio-revision-session"' in html
    assert 'id="release-generate-audio-revision-candidates"' in html
    assert 'id="release-apply-audio-revision-candidate"' in html
    assert 'id="release-require-audio-revision-closeout"' in html
    assert "Mastering QA" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/mastering" in html
    assert "/mastering/analyze" in html
    assert "/mastering/plan" in html
    assert "/mastering/candidates" in html
    assert 'id="release-mastering-profile"' in html
    assert 'id="release-render-mastering-candidate"' in html
    assert 'id="release-require-mastering-qa"' in html
    assert "Encoded Audio Formats" in html
    assert 'id="release-save-encoded-audio-config"' not in html
    assert "Fake Runner" not in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio" in html
    assert "/encoded-audio/render" in html
    assert "/encoded-audio/verify" in html
    assert "/encoded-audio/reset" in html
    assert 'id="release-require-encoded-audio"' in html
    assert 'id="release-required-audio-formats"' in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/metadata" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/metadata/init" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/metadata/qa" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/metadata/qa/refresh" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/metadata/export" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/metadata/platform.csv" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/metadata/credits.csv" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/export" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/export/zip" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/export.zip" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/signoff" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/signoff/reset" in html
    assert 'id="release-acceptance-suite"' in html
    assert "acceptance_suite_id" in html
    assert "Acceptance Gate" in html
    assert "Refresh Acceptance Analytics" in html
    assert "/acceptance-analytics" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/${release.hidden ? \"unhide\" : \"hide\"}" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/archive" in html
    assert "Distribution Prep" in html
    assert "Platform Template Packs" in html
    assert 'id="distribution-template-packs"' in html
    assert 'id="distribution-template-pack"' in html
    assert 'id="distribution-primary-audio-format"' in html
    assert 'id="distribution-audio-format-profiles"' in html
    assert 'id="distribution-create-template"' in html
    assert 'id="distribution-clone-template"' in html
    assert "/api/distribution/template-packs" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/artwork" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/artwork/import" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/qa/refresh" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/export" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/export/zip" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(target.target_id)}/export.zip" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/verify" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/layout" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/signoff" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/checklist" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/checklist/items/explicit-confirmed" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/signoff/reset" in html
    assert 'id="distribution-layout-preview"' in html
    assert 'id="distribution-layout-file-tree"' in html
    assert 'id="release-submissions"' in html
    assert 'id="submission-create"' in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/qa/refresh" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/export" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/export/zip" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/verify" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/signoff" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/report/refresh" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/export" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/export/zip" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/verify" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/signoff" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/signoff/reset" in html
    assert "/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}/items/${encodeURIComponent(itemId)}/record-submission" in html
    assert 'id="submission-evidence"' in html
    assert "upload to platform" not in html.lower()
    assert "credential" not in html.lower()


def test_webui_contains_interactive_editor_controls():
    html = panel_html()

    assert 'id="project-editor-arranger"' in html
    assert 'id="project-editor-section-ruler"' in html
    assert "project-editor-section-block" in html
    assert 'id="project-editor-piano-roll"' in html
    assert "project-editor-note-rect" in html
    assert 'id="project-editor-note-inspector"' in html
    assert 'id="project-editor-patch-queue"' in html
    assert 'id="project-editor-draft-refresh"' in html
    assert 'id="project-editor-undo"' in html
    assert 'id="project-editor-redo"' in html
    assert 'id="project-editor-nudge-left"' in html
    assert 'id="project-editor-nudge-right"' in html
    assert 'id="project-editor-pitch-up"' in html
    assert 'id="project-editor-pitch-down"' in html
    assert "/editor-view" in html
    assert "/editor-draft" in html
    assert "refreshProjectEditorDraft" in html
    assert "projectEditorRedo" in html
    assert "projectEditorClipInsertMap" in html
    assert "Clip Browser" in html
    assert 'id="project-editor-clip-browser"' in html
    assert "Draft Insert Clip" in html
    assert "Editor Templates" in html
    assert "Template Browser" in html
    assert 'id="project-editor-template-browser"' in html
    assert "Draft Insert Template" in html
    assert "Save Section Template" in html
    assert "Save Track Template" in html
    assert "projectEditorTemplateInsertMap" in html
    assert "Render Preview Audio" in html
    assert "Render Parent Audio" in html
    assert "A/B Parent" in html
    assert "A/B Preview" in html
    assert "Audition Review Board" in html
    assert "Track mode" in html
    assert "Create Audition" in html
    assert "Render Audition WAV" in html
    assert "Save Review" in html
    assert "Add Marker" in html
    assert "Save Audition Asset" in html
    assert "Preview Edit" in html
    assert "Create Local Edit" in html
    assert "Provider Preview" in html
    assert "Create Context Pack" in html
    assert "Create Review Task" in html
    assert "Review Workbench" in html
    assert "Review Sprints" in html
    assert "Generate Local Candidates" in html
    assert "Generate Provider Candidates" in html
    assert "Create Review Sprint" in html
    assert "Refresh Review Sprints" in html
    assert "Generate Sprint Local" in html
    assert "Generate Sprint Provider" in html
    assert "Refresh Conflicts" in html
    assert "Recommendations" in html
    assert "Refresh Recommendations" in html
    assert "Recommended Action" in html
    assert "Save Context Pack" in html
    assert "Applying candidates still requires manual confirmation." in html
    assert "Action Queue" in html
    assert "Create Queue from Recommendations" in html
    assert "Select Safe Actions" in html
    assert "Run Selected Safe Actions" in html
    assert "Allow provider actions" in html
    assert "Dashboard" in html
    assert "Refresh Metrics" in html
    assert "Readiness" in html
    assert "Provider Tokens" in html
    assert "Quality Delta" in html
    assert "manual required" in html
    assert "/action-queues" in html
    assert "/action-queues/${encodeURIComponent(button.dataset.queueId)}/run" in html
    assert "/action-queues/${encodeURIComponent(button.dataset.queueId)}/archive" in html
    assert "Close Sprint" in html
    assert "Add to Sprint" in html
    assert "Decision Report" in html
    assert "Refresh Decision Report" in html
    assert "Judge Report" in html
    assert "Refresh Judge Report" in html
    assert "Judge reports are advisory. Applying a candidate remains manual." in html
    assert "Candidate</th><th>Overall</th><th>Fit</th><th>Precision</th><th>Musicality</th><th>Novelty</th><th>Risk</th><th>Confidence" in html
    assert "Judge Summary" in html
    assert "Refresh Sprint Judge" in html
    assert "Judged Tasks" in html
    assert "Judge Tokens" in html
    assert "Closeout" in html
    assert "Refresh Closeout" in html
    assert "Force Close" in html
    assert "Signoff" in html
    assert "Close Allowed" in html
    assert "refresh_judge_report" in html
    assert "provider-review-judge" in html
    assert "provider-review-candidates" in html
    assert "Refresh Review Tasks" in html
    assert "Resolve Task" in html
    assert "Needs More Work" in html
    assert "Archive Task" in html
    assert "Review Edit result" in html
    assert "/audition-reviews" in html
    assert "/review-edit-preview" in html
    assert "/provider-review-edit-preview" in html
    assert "/review-task" in html
    assert "/review-tasks?include_archived=1" in html
    assert "/review-tasks/${encodeURIComponent(task.task_id)}" in html
    assert "/review-sprints?include_archived=1" in html
    assert "/review-sprints/${encodeURIComponent(button.dataset.reviewSprintProvider)}/generate-provider-candidates" in html
    assert "/review-sprints/${encodeURIComponent(button.dataset.reviewSprintLocal)}/generate-local-candidates" in html
    assert "/review-sprints/${encodeURIComponent(button.dataset.reviewSprintConflicts)}/conflicts/refresh" in html
    assert "/review-sprints/${encodeURIComponent(button.dataset.reviewSprintRecommendations)}/recommendations/refresh" in html
    assert "/review-sprints/${encodeURIComponent(sprint.sprint_id)}/metrics" in html
    assert "/review-sprints/${encodeURIComponent(button.dataset.reviewSprintMetrics)}/metrics/refresh" in html
    assert "/review-tasks/${encodeURIComponent(button.dataset.reviewJudgeRefresh)}/judge-report/refresh" in html
    assert "/review-sprints/${encodeURIComponent(sprint.sprint_id)}/judge-summary" in html
    assert "/review-sprints/${encodeURIComponent(button.dataset.reviewSprintJudge)}/judge-summary/refresh" in html
    assert "/review-sprints/${encodeURIComponent(sprint.sprint_id)}/closeout" in html
    assert "/review-sprints/${encodeURIComponent(sprint.sprint_id)}/signoff" in html
    assert "/review-sprints/${encodeURIComponent(button.dataset.reviewSprintCloseout)}/closeout/refresh" in html
    assert "/review-metrics" in html
    assert "/recommendations/${encodeURIComponent(button.dataset.taskId)}/context-pack" in html
    assert "/provider-candidates" in html
    assert "/decision-report/refresh" in html
    assert "/candidates/${encodeURIComponent(button.dataset.candidateId)}/apply" in html
    assert "/needs-more-work" in html
    assert "/resolve" in html
    assert "/archive" in html
    assert "/create-context-pack" in html
    assert "/create-asset" in html


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


def test_webui_contains_mix_board_controls():
    html = panel_html()

    assert "Mix Board" in html
    assert "/mix-state" in html
    assert "/mix-preview" in html
    assert "/mix-stems/render" in html
    assert "Volume dB" in html
    assert "Pan" in html


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
