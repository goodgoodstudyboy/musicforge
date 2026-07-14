async function loadReleases() {
  try {
    const data = await api(includeHiddenReleases ? "/api/releases?include_hidden=1" : "/api/releases");
    releases = data.releases || [];
    if (selectedReleaseId && !releases.some((release) => release.release_id === selectedReleaseId)) {
      selectedReleaseId = null;
      $("release-detail").innerHTML = "<div class='empty'>Select or create a release.</div>";
    }
    renderReleases();
    if (selectedReleaseId) await renderReleaseDetail(selectedReleaseId);
  } catch (err) {
    $("release-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

function releasePayload() {
  return {
    name: $("release-name").value.trim() || "Untitled Release",
    release_type: $("release-type").value || "demo_pack",
    primary_artist: $("release-primary-artist").value.trim(),
    catalog_id: $("release-catalog-id").value.trim(),
    language: $("release-language").value.trim(),
    notes: $("release-notes").value.trim(),
  };
}

function renderReleases() {
  const list = $("release-list");
  if (!releases.length) {
    list.innerHTML = "<div class='empty'>No releases yet.</div>";
    return;
  }
  const rows = releases.map((release) => `
    <tr class="${release.release_id === selectedReleaseId ? "active" : ""}">
      <td><button class="secondary release-open" data-release-id="${escapeHtml(release.release_id)}" type="button">Open</button></td>
      <td>${escapeHtml(release.name || release.release_id)}</td>
      <td>${escapeHtml(release.release_type || "-")}</td>
      <td><span class="status ${escapeHtml(release.status || "")}">${escapeHtml(release.status || "-")}</span></td>
      <td>${escapeHtml(release.track_count || 0)}</td>
      <td>${escapeHtml((release.qa_summary || {}).status || "missing")}</td>
      <td>${escapeHtml((release.signoff_summary || {}).status || "not_signed")}</td>
    </tr>
  `).join("");
  list.innerHTML = `
    <table>
      <thead><tr><th></th><th>Name</th><th>Type</th><th>Status</th><th>Tracks</th><th>QA</th><th>Signoff</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  list.querySelectorAll(".release-open").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedReleaseId = button.dataset.releaseId;
      renderReleases();
      await renderReleaseDetail(selectedReleaseId);
    });
  });
}

async function renderReleaseDetail(releaseId) {
  const data = await api(`/api/releases/${encodeURIComponent(releaseId)}`);
  const release = data.release;
  const summary = data.summary || {};
  let qaData = { summary: release.qa_summary || {}, release_qa: { checks: [], track_checks: [] } };
  let exportData = { summary: release.export_summary || {}, manifest: {} };
  let signoffData = { summary: release.signoff_summary || {}, signoff: {} };
  let metadataData = { summary: {}, metadata: {}, metadata_qa: { checks: [], track_checks: [] } };
  let audioReviewData = { summary: {}, reviews: [] };
  let audioRevisionData = { summary: {}, sessions: [] };
  let masteringData = { summary: {}, analysis: {}, plan: {}, candidates: [], selected_candidate: {} };
  let encodedAudioData = { summary: {}, profiles: [] };
  let formatDecisionData = { sessions: [], active_session: {} };
  let rightsData = { report: {}, parties: [] };
  let distributionData = { summary: {}, targets: [], artwork: [] };
  let submissionData = { summary: {}, submissions: [] };
  let operationsData = { summary: {}, report: {} };
  let operationsReviewerData = { summary: {}, report: {}, retrospective_summary: {} };
  let releaseAnalyticsData = { summary: {}, analytics: null };
  try { qaData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/qa`); } catch (err) {}
  try { exportData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/export`); } catch (err) {}
  try { signoffData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/signoff`); } catch (err) {}
  try { audioReviewData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews`); } catch (err) {}
  try {
    audioRevisionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions`);
    const firstRevisionSession = ((audioRevisionData.sessions || [])[0] || {}).session_id;
    if (firstRevisionSession) {
      audioRevisionData.detail = await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(firstRevisionSession)}`);
    }
  } catch (err) {}
  try { masteringData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering`); } catch (err) {}
  try { encodedAudioData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio`); } catch (err) {}
  try { formatDecisionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions`); } catch (err) {}
  try { rightsData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/rights`); } catch (err) {}
  try {
    metadataData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata`);
    const metadataQa = await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata/qa`);
    metadataData.metadata_qa = metadataQa.metadata_qa || {};
    metadataData.qa_summary = metadataQa.summary || {};
  } catch (err) {}
  try {
    distributionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution`);
    const artworkData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/artwork`);
    distributionData.artwork = artworkData.artwork || [];
    const templateData = await api(`/api/distribution/template-packs`);
    distributionData.template_packs = templateData.template_packs || distributionData.template_packs || [];
  } catch (err) {}
  try { submissionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions`); } catch (err) {}
  try {
    operationsData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations`);
    const runbookData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks`);
    operationsData.runbooks = runbookData.runbooks || [];
    const auditData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/audit`);
    operationsData.audit = auditData || {};
    operationsReviewerData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack`);
  } catch (err) {}
  try { releaseAnalyticsData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/acceptance-analytics`); } catch (err) {}
  const target = $("release-detail");
  target.innerHTML = `
    <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
      <span>Release Workspace · ${escapeHtml(release.name || release.release_id)}</span>
      <span class="status ${escapeHtml(release.status || "")}">${escapeHtml(release.status || "-")}</span>
    </div>
    <div class="summary-grid">
      ${metric("Release", release.release_id)}
      ${metric("Type", release.release_type || "-")}
      ${metric("Tracks", summary.track_count || 0)}
      ${metric("Artist", release.primary_artist || "-")}
    </div>
    <div class="summary-grid">
      ${metric("Release QA", (qaData.summary || {}).status || "missing")}
      ${metric("Release Export", (exportData.summary || {}).status || ((exportData.manifest || {}).schema_version ? "built" : "missing"))}
      ${metric("Release ZIP", ((exportData.manifest || {}).zip || {}).filename || "-")}
      ${metric("Release Signoff", (signoffData.summary || {}).status || "not_signed")}
    </div>
    <div class="grid2">
      <label>Add Project
        <select id="release-add-project">${releaseProjectOptions()}</select>
      </label>
      <label>Track Title
        <input id="release-add-title" placeholder="optional title override">
      </label>
    </div>
    <div class="actions">
      ${releaseActionButtons(release, signoffData.summary || {})}
      <span id="release-action-message" class="message"></span>
    </div>
    ${releaseTrackTable(release)}
    ${releaseMetadataHtml(metadataData, release)}
    ${releaseAudioReviewHtml(audioReviewData, release)}
    ${releaseAudioRevisionHtml(audioRevisionData, release)}
    ${releaseMasteringHtml(masteringData, release)}
    ${releaseEncodedAudioHtml(encodedAudioData, release)}
    ${releaseFormatDecisionHtml(formatDecisionData, release)}
    ${releaseRightsClearanceHtml(rightsData, release)}
    ${releaseOperationsHtml(operationsData, operationsReviewerData, release)}
    ${releaseDistributionHtml(distributionData, release)}
    ${releaseSubmissionsHtml(submissionData, distributionData, release)}
    ${releaseAcceptanceAnalyticsHtml(releaseAnalyticsData, release)}
    ${releaseQaHtml(qaData)}
    ${releaseExportHtml(exportData, release)}
    ${releaseSignoffHtml(signoffData)}
  `;
  wireReleaseActions(release);
}

function releaseProjectOptions() {
  return projects.map((project) => `<option value="${escapeHtml(project.project_id)}">${escapeHtml(project.name)} · ${escapeHtml(project.final_version_id || "-")}</option>`).join("");
}

function releaseActionButtons(release, signoffSummary) {
  const signed = ["signed", "force_signed"].includes(signoffSummary.status);
  return `
    <button id="release-add-track" type="button" ${signed || !projects.length ? "disabled" : ""}>Add Track</button>
    <button class="secondary" id="release-init-metadata" type="button" ${signed ? "disabled" : ""}>Initialize Metadata</button>
    <button class="secondary" id="release-refresh-metadata-qa" type="button">Refresh Metadata QA</button>
    <button class="secondary" id="release-export-metadata" type="button">Export Metadata</button>
    <button class="secondary" id="release-refresh-qa" type="button">Refresh Release QA</button>
    <button class="secondary" id="release-refresh-audio-qa" type="button">Refresh Release Audio QA</button>
    <button class="secondary" id="release-build-export" type="button" ${signed ? "disabled" : ""}>Build Release Export</button>
    <button class="secondary" id="release-build-zip" type="button">Build Release ZIP</button>
    <button id="release-signoff" type="button" ${signed ? "disabled" : ""}>Sign Release</button>
    <button class="danger" id="release-force-signoff" type="button" ${signed ? "disabled" : ""}>Force Sign</button>
    <button class="danger" id="release-reset-signoff" type="button" ${signed ? "" : "disabled"}>Reset Signoff</button>
    <button class="secondary" id="release-hide" type="button">${release.hidden ? "Unhide" : "Hide"}</button>
    <button class="secondary" id="release-archive" type="button">Archive</button>
    ${release.export_summary && release.export_summary.zip_filename ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/export.zip">Download Release ZIP</a>` : ""}
  `;
}

function releaseTrackTable(release) {
  const rows = (release.tracks || []).map((track) => `
    <tr>
      <td>${escapeHtml(track.disc_number || 1)}.${escapeHtml(track.track_number || 0)}</td>
      <td>${escapeHtml(track.title || "-")}</td>
      <td>${escapeHtml(track.project_id)}</td>
      <td>${escapeHtml(track.version_id || "-")}</td>
      <td>${escapeHtml(track.delivery_qa_status || "-")}</td>
      <td>${escapeHtml(track.delivery_signoff_status || "-")}</td>
      <td>
        <button class="secondary release-track-refresh" data-track-id="${escapeHtml(track.track_id)}" type="button">Refresh</button>
        <button class="danger release-track-remove" data-track-id="${escapeHtml(track.track_id)}" type="button">Remove</button>
      </td>
    </tr>
  `).join("");
  return `
    <div class="panel-title subhead"><span>Tracklist</span></div>
    <table>
      <thead><tr><th>#</th><th>Title</th><th>Project</th><th>Version</th><th>Delivery QA</th><th>Signoff</th><th>Actions</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='7'>No tracks yet.</td></tr>"}</tbody>
    </table>
  `;
}

function releaseQaHtml(qaData) {
  const summary = (qaData && qaData.summary) || {};
  const report = (qaData && qaData.release_qa) || {};
  return `
    <div class="panel-title subhead"><span>Release QA</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.status || "-")}
      ${metric("Blockers", summary.blocker_count || 0)}
      ${metric("Warnings", summary.warning_count || 0)}
      ${metric("Tracks", summary.track_count || 0)}
    </div>
    ${deliveryChecksHtml([...(report.checks || []), ...(report.track_checks || [])])}
  `;
}

function releaseMetadataHtml(metadataData, release) {
  const metadata = (metadataData && metadataData.metadata) || {};
  const summary = (metadataData && metadataData.summary) || {};
  const qaSummary = (metadataData && metadataData.qa_summary) || {};
  const releaseMeta = metadata.release || {};
  const rows = (metadata.tracks || []).map((track) => `
    <tr>
      <td>${escapeHtml(track.track_number || "-")}</td>
      <td>${escapeHtml(track.title || "-")}</td>
      <td>${escapeHtml(track.display_artist || "-")}</td>
      <td>${escapeHtml(track.isrc || "-")}</td>
      <td>${track.explicit ? "yes" : "-"}</td>
      <td>${track.instrumental ? "yes" : "-"}</td>
      <td>${track.confirmed ? "yes" : "-"}</td>
    </tr>
  `).join("");
  return `
    <div class="panel-title subhead"><span>Release Metadata</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.exists ? "ready" : "missing")}
      ${metric("Metadata QA", qaSummary.status || summary.qa_status || "missing")}
      ${metric("Title", releaseMeta.title || release.name || "-")}
      ${metric("UPC", releaseMeta.upc || "-")}
    </div>
    <div class="grid2">
      <label>Release Title
        <input id="release-metadata-title" value="${escapeHtml(releaseMeta.title || release.name || "")}">
      </label>
      <label>UPC
        <input id="release-metadata-upc" value="${escapeHtml(releaseMeta.upc || "")}">
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="release-save-metadata" type="button" ${metadata.schema_version ? "" : "disabled"}>Save Metadata</button>
      ${summary.exists ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/metadata/platform.csv">Platform CSV</a>` : ""}
      ${summary.exists ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/metadata/credits.csv">Credits CSV</a>` : ""}
    </div>
    <table>
      <thead><tr><th>#</th><th>Title</th><th>Artist</th><th>ISRC</th><th>Explicit</th><th>Instrumental</th><th>Confirmed</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='7'>Initialize metadata to edit release and track fields.</td></tr>"}</tbody>
    </table>
    ${deliveryChecksHtml([...((metadataData.metadata_qa || {}).checks || []), ...((metadataData.metadata_qa || {}).track_checks || [])])}
  `;
}

function releaseFormatDecisionHtml(formatDecisionData, release) {
  const sessions = (formatDecisionData && formatDecisionData.sessions) || [];
  const active = (formatDecisionData && formatDecisionData.active_session) || {};
  const latest = sessions[0] || {};
  return `
    <div class="panel-title subhead"><span>Format Decision Workbench</span></div>
    <div class="summary-grid">
      ${metric("Sessions", sessions.length || 0)}
      ${metric("Active", active.session_id || "-")}
      ${metric("Latest", latest.session_id || "-")}
      ${metric("Status", latest.status || "missing")}
    </div>
    <div class="grid2">
      <label>Candidate Profiles
        <input id="release-format-decision-profiles" value="mp3_320,flac_lossless">
      </label>
      <label>Selected Profiles
        <input id="release-format-decision-selected" value="mp3_320">
      </label>
      <label>Archive Profiles
        <input id="release-format-decision-archive" value="flac_lossless">
      </label>
      <label>Rejected Profiles
        <input id="release-format-decision-rejected" value="">
      </label>
    </div>
    <label>Decision Reason
      <textarea id="release-format-decision-reason" rows="2"></textarea>
    </label>
    <div class="actions">
      <button class="secondary" id="release-create-format-decision" type="button">Create Format Decision</button>
    </div>
  `;
}

function releaseRightsClearanceHtml(rightsData, release) {
  const report = (rightsData && rightsData.report) || {};
  const parties = (rightsData && rightsData.parties) || [];
  const rows = (report.tracks || []).map((track) => `
    <tr>
      <td>${escapeHtml(track.track_id || "-")}</td>
      <td><span class="status ${escapeHtml(track.status || "")}">${escapeHtml(track.status || "-")}</span></td>
      <td>${escapeHtml(track.manual_clearance_status || "-")}</td>
      <td>${escapeHtml((track.failures || []).join(", ") || "-")}</td>
    </tr>
  `).join("");
  const trackOptions = (release.tracks || []).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(`${track.track_number || ""} ${track.title || track.track_id}`)}</option>`).join("");
  const partyOptions = parties.map((party) => `<option value="${escapeHtml(party.party_id || "")}">${escapeHtml(party.public_credit_name || party.display_name || party.party_id)}</option>`).join("");
  return `
    <div class="panel-title subhead"><span>Rights Clearance</span></div>
    <div class="summary-grid">
      ${metric("Status", report.status || "missing")}
      ${metric("Tracks", report.track_count || 0)}
      ${metric("Manual Cleared", report.manual_cleared_track_count || 0)}
      ${metric("Parties", parties.length || 0)}
    </div>
    <div class="grid2">
      <label>Party Name
        <input id="rights-party-name" value="MusicForge">
      </label>
      <label>Public Credit
        <input id="rights-party-credit" value="MusicForge">
      </label>
      <label>Track
        <select id="rights-track-id">${trackOptions}</select>
      </label>
      <label>Contributor
        <select id="rights-party-id">${partyOptions}</select>
      </label>
      <label>Role
        <select id="rights-contributor-role"><option value="composer">composer</option><option value="lyricist">lyricist</option><option value="producer">producer</option><option value="performer">performer</option></select>
      </label>
      <label>Share
        <input id="rights-contributor-share" type="number" value="100" min="0" max="100">
      </label>
    </div>
    <label>Attestation
      <textarea id="rights-attestation" rows="2">Original composition rights confirmed.</textarea>
    </label>
    <div class="actions">
      <button class="secondary" id="rights-create-party" type="button">Create Party</button>
      <button class="secondary" id="rights-save-track" type="button">Save Track Rights</button>
      <button class="secondary" id="rights-review-track" type="button">Accept Rights</button>
      <button class="secondary" id="rights-refresh-report" type="button">Refresh Rights Report</button>
    </div>
    <table>
      <thead><tr><th>Track</th><th>Status</th><th>Manual</th><th>Failures</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='4'>No rights report yet.</td></tr>"}</tbody>
    </table>
  `;
}

function releaseOperationsHtml(operationsData, reviewerPackData, release) {
  const summary = (operationsData && operationsData.summary) || {};
  const report = (operationsData && operationsData.report) || {};
  const progress = report.stage_progress || {};
  const manifest = operationsData.manifest || {};
  const zip = operationsData.zip || manifest.zip || {};
  const runbooks = operationsData.runbooks || [];
  const activeRunbook = runbooks[0] || {};
  const runbookSummary = activeRunbook.summary || {};
  const audit = operationsData.audit || {};
  const auditSummary = audit.summary || {};
  const reviewerSummary = (reviewerPackData && reviewerPackData.summary) || {};
  const reviewerReport = (reviewerPackData && reviewerPackData.report) || {};
  const retrospectiveSummary = (reviewerPackData && reviewerPackData.retrospective_summary) || {};
  const reviewerFindings = (reviewerReport.warnings || []).slice(0, 5).map((item) => `
    <tr><td>${escapeHtml(item.check_id || "-")}</td><td>${escapeHtml(item.message || "-")}</td></tr>
  `).join("");
  const stageRows = (report.stage_statuses || []).map((stage) => `
    <tr>
      <td>${escapeHtml(stage.stage || "-")}</td>
      <td><span class="status ${escapeHtml(stage.status || "")}">${escapeHtml(stage.status || "-")}</span></td>
      <td>${escapeHtml(stage.blocker_count || 0)}</td>
      <td>${escapeHtml(stage.warning_count || 0)}</td>
    </tr>
  `).join("");
  const actionRows = (report.next_actions || []).slice(0, 8).map((action) => `
    <tr>
      <td>${escapeHtml(action.label || action.action_type || "-")}</td>
      <td>${escapeHtml(action.entity_id || "-")}</td>
      <td>${escapeHtml((action.blocked_by || []).join(", ") || "-")}</td>
      <td>${escapeHtml((action.unblocks || []).join(", ") || "-")}</td>
    </tr>
  `).join("");
  const runbookOptions = runbooks.map((runbook) => `<option value="${escapeHtml(runbook.runbook_id || "")}">${escapeHtml(runbook.runbook_id || "-")} · ${escapeHtml(runbook.status || "-")}</option>`).join("");
  const runbookRows = runbooks.slice(0, 8).map((runbook) => {
    const itemSummary = runbook.summary || {};
    return `
      <tr>
        <td>${escapeHtml(runbook.runbook_id || "-")}</td>
        <td><span class="status ${escapeHtml(runbook.status || "")}">${escapeHtml(runbook.status || "-")}</span></td>
        <td>${escapeHtml(itemSummary.safe_count || 0)}</td>
        <td>${escapeHtml(itemSummary.manual_required_count || 0)}</td>
        <td>${escapeHtml(itemSummary.failed_count || 0)}</td>
      </tr>
    `;
  }).join("");
  const operationsSignoff = report.operations_signoff || (summary.operations_signoff || {});
  return `
    <div class="panel-title subhead"><span>Release Operations</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.status || report.status || "missing")}
      ${metric("Stage", summary.current_stage || report.current_stage || "draft")}
      ${metric("Next", summary.next_stage || report.next_stage || "-")}
      ${metric("Progress", `${progress.completed_count || 0}/${progress.total_count || 0}`)}
      ${metric("Blockers", summary.blocker_count || 0)}
      ${metric("Warnings", summary.warning_count || 0)}
      ${metric("Stale", operationsData.stale ? "yes" : "-")}
      ${metric("Integrity", operationsData.integrity_ok === false ? "failed" : "ok")}
    </div>
    <div class="actions">
      <button class="secondary" id="release-operations-refresh" type="button">Refresh Operations</button>
      <button class="secondary" id="release-operations-export" type="button">Export Operations</button>
      <button class="secondary" id="release-operations-zip" type="button">Build Operations ZIP</button>
      <button class="secondary" id="release-operations-verify" type="button">Verify Operations ZIP</button>
      ${(zip.filename || (manifest.zip || {}).filename) ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/export.zip">Download Operations ZIP</a>` : ""}
    </div>
    <table>
      <thead><tr><th>Stage</th><th>Status</th><th>Blockers</th><th>Warnings</th></tr></thead>
      <tbody>${stageRows || "<tr><td colspan='4'>No Operations report yet.</td></tr>"}</tbody>
    </table>
    <table>
      <thead><tr><th>Next Action</th><th>Entity</th><th>Blocked By</th><th>Unblocks</th></tr></thead>
      <tbody>${actionRows || "<tr><td colspan='4'>No pending Operations actions.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Release Operations Runbook</span></div>
    <div class="summary-grid">
      ${metric("Runbook", activeRunbook.runbook_id || "missing")}
      ${metric("Status", activeRunbook.status || "-")}
      ${metric("Safe Actions", runbookSummary.safe_count || 0)}
      ${metric("Manual Required", runbookSummary.manual_required_count || 0)}
      ${metric("Failed", runbookSummary.failed_count || 0)}
    </div>
    <div class="actions">
      <select id="release-runbook-id">${runbookOptions || "<option value=''>No runbook</option>"}</select>
      <button class="secondary" id="release-runbook-create" type="button">Create Runbook</button>
      <button class="secondary" id="release-runbook-run-safe" type="button">Run Safe Actions</button>
      <button class="secondary" id="release-runbook-refresh-stale" type="button">Refresh Runbook Stale</button>
      <button class="secondary" id="release-runbook-export" type="button">Export Runbook</button>
      <button class="secondary" id="release-runbook-zip" type="button">Build Runbook ZIP</button>
      <button class="secondary" id="release-runbook-verify" type="button">Verify Runbook ZIP</button>
      ${activeRunbook.runbook_id ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks/${encodeURIComponent(activeRunbook.runbook_id)}/export.zip">Download Runbook ZIP</a>` : ""}
    </div>
    <table>
      <thead><tr><th>Runbook</th><th>Status</th><th>Safe</th><th>Manual Required</th><th>Failed</th></tr></thead>
      <tbody>${runbookRows || "<tr><td colspan='5'>No Operations Runbooks yet.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Release Operations Signoff</span></div>
    <div class="summary-grid">
      ${metric("Signoff", operationsSignoff.status || "not_signed")}
      ${metric("Signed By", operationsSignoff.signed_by || "-")}
      ${metric("Stale", operationsSignoff.stale ? "yes" : "-")}
      ${metric("Integrity", operationsSignoff.integrity_ok === false ? "failed" : "ok")}
    </div>
    <div class="grid2">
      <label>Operations Signed By <input id="release-operations-signed-by" value="local-user"></label>
      <label>Operations Reset Reason <input id="release-operations-reset-reason" value="Approved operations evidence change"></label>
      <label>Change Request Reason <input id="release-operations-change-reason" value="Refresh archived operations evidence after approved change"></label>
      <label>Change Request Scope <input id="release-operations-change-scope" value="operations,release_export"></label>
      <label>Change Request ID <input id="release-operations-change-id" placeholder="ocr-000001"></label>
    </div>
    <div class="actions">
      <button class="secondary" id="release-operations-sign" type="button">Sign Operations</button>
      <button class="secondary" id="release-operations-archive-export" type="button">Export Archive</button>
      <button class="secondary" id="release-operations-archive-zip" type="button">Build Archive ZIP</button>
      <button class="secondary" id="release-operations-archive-verify" type="button">Verify Archive ZIP</button>
      <button class="secondary" id="release-operations-change-create" type="button">Create Change Request</button>
      <button class="danger" id="release-operations-reset-signoff" type="button">Reset Operations Signoff</button>
      <a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/archive.zip">Download Archive ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Release Operations Audit Ledger</span></div>
    <div class="summary-grid">
      ${metric("Audit", auditSummary.status || "missing")}
      ${metric("Entries", auditSummary.entry_count || 0)}
      ${metric("Blockers", auditSummary.blocker_count || 0)}
      ${metric("Warnings", auditSummary.warning_count || 0)}
      ${metric("Integrity", auditSummary.integrity_ok === false ? "failed" : "ok")}
    </div>
    <div class="actions">
      <button class="secondary" id="release-operations-audit-refresh" type="button">Refresh Audit Ledger</button>
      <button class="secondary" id="release-operations-audit-export" type="button">Export Audit Package</button>
      <button class="secondary" id="release-operations-audit-zip" type="button">Build Audit ZIP</button>
      <button class="secondary" id="release-operations-audit-verify" type="button">Verify Audit ZIP</button>
      <a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/audit.zip">Download Audit ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Reviewer Pack</span></div>
    <div class="summary-grid">
      ${metric("Reviewer", reviewerSummary.status || "missing")}
      ${metric("Readiness", reviewerSummary.readiness || "-")}
      ${metric("Audit", reviewerSummary.audit_status || "-")}
      ${metric("Archive", reviewerSummary.archive_verified ? "verified" : "-")}
      ${metric("Warnings", reviewerSummary.warning_count || 0)}
      ${metric("Retrospective", retrospectiveSummary.status || "missing")}
    </div>
    <div class="actions">
      <button class="secondary" id="release-reviewer-pack-refresh" type="button">Refresh Reviewer Report</button>
      <button class="secondary" id="release-reviewer-pack-export" type="button">Export Reviewer Pack</button>
      <button class="secondary" id="release-reviewer-pack-zip" type="button">Build Reviewer ZIP</button>
      <button class="secondary" id="release-reviewer-pack-verify" type="button">Verify Reviewer ZIP</button>
      <a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack.zip">Download Reviewer ZIP</a>
    </div>
    <table>
      <thead><tr><th>Risk hotspots</th><th>Reviewer note</th></tr></thead>
      <tbody>${reviewerFindings || "<tr><td colspan='2'>No Reviewer Pack warnings.</td></tr>"}</tbody>
    </table>
  `;
}

function releaseExportHtml(exportData, release) {
  const manifest = (exportData && exportData.manifest) || {};
  const zip = manifest.zip || {};
  const rows = (manifest.files || []).slice(0, 80).map((file) => `
    <tr><td>${escapeHtml(file.kind || "-")}</td><td>${escapeHtml(file.path || "-")}</td><td>${escapeHtml(file.size_bytes || 0)}</td></tr>
  `).join("");
  return `
    <div class="panel-title subhead"><span>Release Export</span></div>
    <div class="summary-grid">
      ${metric("Status", (exportData.summary || {}).status || (manifest.schema_version ? "built" : "missing"))}
      ${metric("Files", (manifest.summary || {}).file_count || 0)}
      ${metric("Tracks", (manifest.summary || {}).track_count || (release.tracks || []).length)}
      ${metric("ZIP", zip.filename || "-")}
    </div>
    <table>
      <thead><tr><th>Kind</th><th>Path</th><th>Size</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='3'>No release export yet.</td></tr>"}</tbody>
    </table>
  `;
}

function releaseAcceptanceAnalyticsHtml(analyticsData, release) {
  const summary = (analyticsData && analyticsData.summary) || {};
  const report = (analyticsData && analyticsData.analytics) || {};
  return `
    <div class="panel-title subhead"><span>Acceptance Analytics</span></div>
    <div class="summary-grid">
      ${metric("Readiness", summary.readiness_status || "missing")}
      ${metric("Cases", summary.case_count || 0)}
      ${metric("Needs Fix", summary.needs_fix_count || 0)}
      ${metric("Blocked", summary.blocked_count || 0)}
      ${metric("Report", report.report_id || "-")}
      ${metric("Stale", report.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="release-refresh-acceptance-analytics" type="button">Refresh Acceptance Analytics</button>
    </div>
  `;
}

function releaseSignoffHtml(signoffData) {
  const summary = (signoffData && signoffData.summary) || {};
  const signoff = (signoffData && signoffData.signoff) || {};
  const gate = summary.acceptance_gate || signoff.acceptance_gate || {};
  const analyticsGate = gate.acceptance_analytics || {};
  return `
    <div class="panel-title subhead"><span>Release Signoff</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.status || "not_signed")}
      ${metric("Signed At", summary.signed_at || "-")}
      ${metric("Signed By", summary.signed_by || "-")}
      ${metric("Forced", summary.forced ? "yes" : "-")}
      ${metric("Acceptance Gate", gate.status || "-")}
      ${metric("Acceptance Suite", gate.suite_id || "-")}
      ${metric("Analytics", analyticsGate.readiness_status || "-")}
    </div>
    <div class="grid2">
      <label>Signed By
        <input id="release-signed-by" value="${escapeHtml(signoff.signed_by || "local-user")}">
      </label>
      <label>Acceptance Suite
        <select id="release-acceptance-suite">
          <option value="">none</option>
          ${acceptanceSuiteOptions((gate || {}).suite_id || "")}
        </select>
      </label>
    </div>
    <div class="grid2">
      <label>Reset Reason
        <input id="release-reset-reason" placeholder="Reason required before reset">
      </label>
      <label>Gate Status
        <input value="${escapeHtml(gate.acceptance_status || "-")}" readonly>
      </label>
    </div>
    <label>Notes
      <textarea id="release-signoff-notes" rows="2">${escapeHtml(signoff.notes || "")}</textarea>
    </label>
    <label>Override Reason
      <textarea id="release-override-reason" rows="2" placeholder="Required for force sign"></textarea>
    </label>
    <label class="inline">
      <input id="release-require-per-track-audio-review" type="checkbox">
      Require per-track audio review
    </label>
    <label class="inline">
      <input id="release-require-stem-audio-health" type="checkbox">
      Require stem audio health
    </label>
    <label class="inline">
      <input id="release-require-current-mix-state" type="checkbox">
      Require current mix state
    </label>
    <label class="inline">
      <input id="release-require-audio-revision-closeout" type="checkbox">
      Require audio revision closeout
    </label>
    <label class="inline">
      <input id="release-require-mastering-qa" type="checkbox">
      Require mastering QA
    </label>
    <label class="inline">
      <input id="release-require-encoded-audio" type="checkbox">
      Require encoded audio
    </label>
    <label class="inline">
      <input id="release-require-encoded-audio-review" type="checkbox">
      Require encoded audio review
    </label>
    <label class="inline">
      <input id="release-require-format-decision" type="checkbox">
      Require format decision
    </label>
    <label class="inline">
      <input id="release-require-rights-clearance" type="checkbox">
      Require rights clearance
    </label>
    <label>Required Audio Formats
      <input id="release-required-audio-formats" value="mp3_320">
    </label>
  `;
}

function releaseSignoffPayload(force) {
  return {
    force,
    signed_by: $("release-signed-by").value.trim() || "local-user",
    notes: $("release-signoff-notes").value.trim(),
    override_reason: $("release-override-reason").value.trim(),
    acceptance_suite_id: $("release-acceptance-suite").value,
    require_per_track_audio_review: $("release-require-per-track-audio-review")?.checked || false,
    require_stem_audio_health: $("release-require-stem-audio-health")?.checked || false,
    require_current_mix_state: $("release-require-current-mix-state")?.checked || false,
    require_audio_revision_closeout: $("release-require-audio-revision-closeout")?.checked || false,
    require_mastering_qa: $("release-require-mastering-qa")?.checked || false,
    require_encoded_audio: $("release-require-encoded-audio")?.checked || false,
    require_encoded_audio_review: $("release-require-encoded-audio-review")?.checked || false,
    require_format_decision: $("release-require-format-decision")?.checked || false,
    require_rights_clearance: $("release-require-rights-clearance")?.checked || false,
    required_audio_format_profiles: ($("release-required-audio-formats")?.value || "").split(",").map((item) => item.trim()).filter(Boolean),
    mastering_profile_id: $("release-mastering-profile")?.value || "",
  };
}

Object.assign(globalThis, { loadReleases, releasePayload, renderReleases, renderReleaseDetail, releaseProjectOptions, releaseActionButtons, releaseTrackTable, releaseQaHtml, releaseMetadataHtml, releaseFormatDecisionHtml, releaseRightsClearanceHtml, releaseOperationsHtml, releaseExportHtml, releaseAcceptanceAnalyticsHtml, releaseSignoffHtml, releaseSignoffPayload });

export { loadReleases, releasePayload, renderReleases, renderReleaseDetail, releaseProjectOptions, releaseActionButtons, releaseTrackTable, releaseQaHtml, releaseMetadataHtml, releaseFormatDecisionHtml, releaseRightsClearanceHtml, releaseOperationsHtml, releaseExportHtml, releaseAcceptanceAnalyticsHtml, releaseSignoffHtml, releaseSignoffPayload };
