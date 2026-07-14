async function showAudioLabResult(path, options) {
  try {
    const data = await api(path, options);
    $("audio-lab-status").textContent = (data.summary && data.summary.status) || (data.environment && data.environment.status) || (data.smoke_run && data.smoke_run.status) || "ok";
    $("audio-lab-summary").textContent = JSON.stringify(data.summary || data.environment || data, null, 2);
  } catch (err) {
    $("audio-lab-status").textContent = "error";
    $("audio-lab-summary").textContent = err.message;
  }
}

async function showAudioFixSprintResult(path, options) {
  try {
    const data = await api(path, options);
    $("audio-fix-sprint-status").textContent = (data.summary && data.summary.status) || (data.sprint && data.sprint.status) || "ok";
    $("audio-fix-sprint-summary").textContent = JSON.stringify(data.summary || data.sprint || data, null, 2);
  } catch (err) {
    $("audio-fix-sprint-status").textContent = "error";
    $("audio-fix-sprint-summary").textContent = err.message;
  }
}

async function showAudioCampaignResult(path, options) {
  try {
    const data = await api(path, options);
    $("audio-campaign-status").textContent = (data.summary && data.summary.status) || (data.campaign && data.campaign.status) || "ok";
    $("audio-campaign-summary").textContent = JSON.stringify(data.summary || data.campaign || data, null, 2);
  } catch (err) {
    $("audio-campaign-status").textContent = "error";
    $("audio-campaign-summary").textContent = err.message;
  }
}

function releaseAudioReviewHtml(audioReviewData, release) {
  const summary = (audioReviewData && audioReviewData.summary) || {};
  const reviews = (audioReviewData && audioReviewData.reviews) || [];
  const rows = (release.tracks || []).map((track) => {
    const review = reviews.find((item) => item.track_id === track.track_id && item.status === "accepted" && item.review_mode === "manual" && !item.stale) || reviews.find((item) => item.track_id === track.track_id) || {};
    return `
      <tr>
        <td>${escapeHtml(track.track_number || "-")}</td>
        <td>${escapeHtml(track.title || "-")}</td>
        <td>${escapeHtml(track.track_id || "-")}</td>
        <td>${escapeHtml(review.status || "missing")}</td>
        <td>${escapeHtml(review.review_mode || "-")}</td>
        <td>${escapeHtml(review.rating || "-")}</td>
        <td>${review.stale ? "yes" : "-"}</td>
        <td>${escapeHtml(((review.markers || []).length) || 0)}</td>
      </tr>
    `;
  }).join("");
  return `
    <div class="panel-title subhead"><span>Audio Review Board</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.status || "missing")}
      ${metric("Manual Accepted", summary.manual_accepted_track_count || 0)}
      ${metric("Missing", (summary.missing_track_ids || []).length)}
      ${metric("Stale", summary.stale_review_count || 0)}
    </div>
    <div class="grid2">
      <label>Review Track
        <select id="release-audio-review-track">${(release.tracks || []).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.track_number || "-")}. ${escapeHtml(track.title || track.track_id)}</option>`).join("")}</select>
      </label>
      <label>Reviewer
        <input id="release-audio-reviewer" value="local-user">
      </label>
    </div>
    <div class="grid2">
      <label>Status
        <select id="release-audio-review-status"><option value="accepted">accepted</option><option value="needs_fix">needs_fix</option><option value="rejected">rejected</option><option value="waived">waived</option></select>
      </label>
      <label>Rating
        <input id="release-audio-review-rating" type="number" min="0" max="5" value="4">
      </label>
    </div>
    <label>Notes
      <textarea id="release-audio-review-notes" rows="2"></textarea>
    </label>
    <div class="actions">
      <button class="secondary" id="release-refresh-audio-review-summary" type="button">Refresh Audio Review Summary</button>
      <button class="secondary" id="release-add-audio-review" type="button">Add Track Review</button>
      <button class="secondary release-marker-mix-patch-draft" data-endpoint="/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews/{review_id}/markers/{marker_id}/mix-patch-draft" type="button" disabled>Create Mix Patch Draft</button>
    </div>
    <table>
      <thead><tr><th>#</th><th>Title</th><th>Track</th><th>Review</th><th>Mode</th><th>Rating</th><th>Stale</th><th>Markers</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='8'>No release tracks yet.</td></tr>"}</tbody>
    </table>
  `;
}

function releaseAudioRevisionHtml(audioRevisionData, release) {
  const summary = (audioRevisionData && audioRevisionData.summary) || {};
  const sessions = (audioRevisionData && audioRevisionData.sessions) || [];
  const detail = (audioRevisionData && audioRevisionData.detail) || {};
  const issues = detail.issues || [];
  const candidates = detail.candidates || [];
  const latest = sessions[0] || {};
  const sessionId = latest.session_id || "";
  const rows = sessions.map((session) => `
    <tr>
      <td>${escapeHtml(session.session_id || "-")}</td>
      <td>${escapeHtml(session.status || "-")}</td>
      <td>${escapeHtml(session.issue_count || 0)}</td>
      <td>${escapeHtml(session.open_issue_count || 0)}</td>
      <td>${escapeHtml(session.applied_candidate_count || 0)}</td>
      <td>${session.stale ? "yes" : "-"}</td>
    </tr>
  `).join("");
  const issueRows = issues.map((issue) => `
    <tr>
      <td>${escapeHtml(issue.issue_id || "-")}</td>
      <td><span class="status ${escapeHtml(issue.status || "")}">${escapeHtml(issue.status || "-")}</span></td>
      <td>${escapeHtml(issue.track_id || "-")}</td>
      <td>${escapeHtml(issue.category || "-")}</td>
      <td>${escapeHtml(issue.severity || "-")}</td>
      <td>${escapeHtml(issue.selected_candidate_id || "-")}</td>
      <td>${escapeHtml(issue.applied_version_id || "-")}</td>
    </tr>
  `).join("");
  const candidateRows = candidates.map((candidate) => {
    const candidateId = candidate.candidate_id || "";
    const previewBase = `/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/candidates/${encodeURIComponent(candidateId)}`;
    return `
      <tr>
        <td>${escapeHtml(candidateId || "-")}</td>
        <td><span class="status ${escapeHtml(candidate.status || "")}">${escapeHtml(candidate.status || "-")}</span></td>
        <td>${candidate.selected ? "yes" : "-"}</td>
        <td>${escapeHtml(candidate.score || 0)}</td>
        <td>${escapeHtml((candidate.review || {}).status || "-")}</td>
        <td>${escapeHtml(candidate.applied_version_id || "-")}</td>
        <td>${candidateId ? `<a href="${previewBase}/midi" target="_blank" rel="noreferrer">MIDI</a> · <a href="${previewBase}/audio" target="_blank" rel="noreferrer">WAV</a>` : "-"}</td>
      </tr>
    `;
  }).join("");
  const issueControl = issues.length
    ? `<select id="release-audio-revision-issue">${issues.map((issue) => `<option value="${escapeHtml(issue.issue_id || "")}">${escapeHtml(issue.issue_id || "-")} · ${escapeHtml(issue.status || "-")} · ${escapeHtml(issue.severity || "-")}</option>`).join("")}</select>`
    : `<input id="release-audio-revision-issue" placeholder="ari-000001">`;
  const candidateControl = candidates.length
    ? `<select id="release-audio-revision-candidate">${candidates.map((candidate) => `<option value="${escapeHtml(candidate.candidate_id || "")}">${escapeHtml(candidate.candidate_id || "-")} · ${escapeHtml(candidate.status || "-")}${candidate.selected ? " · selected" : ""}</option>`).join("")}</select>`
    : `<input id="release-audio-revision-candidate" placeholder="arc-000001">`;
  return `
    <div class="panel-title subhead"><span>Audio Revision Workbench</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.status || "missing")}
      ${metric("Sessions", summary.session_count || sessions.length || 0)}
      ${metric("Open Issues", summary.open_issue_count || 0)}
      ${metric("Rechecked", summary.rechecked_issue_count || 0)}
    </div>
    <div class="grid2">
      <label>Session
        <select id="release-audio-revision-session">${sessions.map((session) => `<option value="${escapeHtml(session.session_id || "")}">${escapeHtml(session.session_id || "-")} · ${escapeHtml(session.status || "-")}</option>`).join("")}</select>
      </label>
      <label>Issue
        ${issueControl}
      </label>
    </div>
    <div class="grid2">
      <label>Candidate
        ${candidateControl}
      </label>
      <label>Session Title
        <input id="release-audio-revision-title" value="Audio revision pass">
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="release-create-audio-revision" type="button">Create Revision Session</button>
      <button class="secondary" id="release-generate-audio-revision-candidates" type="button" ${sessionId ? "" : "disabled"}>Generate Candidates</button>
      <button class="secondary" id="release-review-audio-revision-candidate" type="button" ${sessionId ? "" : "disabled"}>Accept Candidate</button>
      <button class="secondary" id="release-select-audio-revision-candidate" type="button" ${sessionId ? "" : "disabled"}>Select Candidate</button>
      <button class="secondary" id="release-apply-audio-revision-candidate" type="button" ${sessionId ? "" : "disabled"}>Apply Candidate</button>
      <button class="secondary" id="release-refresh-audio-revision" type="button" ${sessionId ? "" : "disabled"}>Refresh Recheck</button>
      <button class="secondary" id="release-close-audio-revision" type="button" ${sessionId ? "" : "disabled"}>Close Session</button>
    </div>
    <table>
      <thead><tr><th>Issue</th><th>Status</th><th>Track</th><th>Category</th><th>Severity</th><th>Selected Candidate</th><th>Applied Version</th></tr></thead>
      <tbody>${issueRows || "<tr><td colspan='7'>No audio revision issues yet.</td></tr>"}</tbody>
    </table>
    <table>
      <thead><tr><th>Candidate</th><th>Status</th><th>Selected</th><th>Score</th><th>Review</th><th>Applied Version</th><th>A/B Preview</th></tr></thead>
      <tbody>${candidateRows || "<tr><td colspan='7'>No audio revision candidates yet.</td></tr>"}</tbody>
    </table>
    <table>
      <thead><tr><th>Session</th><th>Status</th><th>Issues</th><th>Open</th><th>Applied</th><th>Stale</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='6'>No audio revision sessions yet.</td></tr>"}</tbody>
    </table>
  `;
}

function releaseMasteringHtml(masteringData, release) {
  const summary = (masteringData && masteringData.summary) || {};
  const analysis = (masteringData && masteringData.analysis) || {};
  const plan = (masteringData && masteringData.plan) || {};
  const candidates = (masteringData && masteringData.candidates) || [];
  const selectedId = ((masteringData && masteringData.selected_candidate) || {}).candidate_id || "";
  const candidateOptions = candidates.map((candidate) => `<option value="${escapeHtml(candidate.candidate_id || "")}" ${candidate.candidate_id === selectedId ? "selected" : ""}>${escapeHtml(candidate.candidate_id || "-")} · ${escapeHtml(candidate.status || "-")}${candidate.selected ? " · selected" : ""}</option>`).join("");
  const rows = (analysis.tracks || []).map((track) => `
    <tr>
      <td>${escapeHtml(track.track_id || "-")}</td>
      <td><span class="status ${escapeHtml(track.status || "")}">${escapeHtml(track.status || "-")}</span></td>
      <td>${escapeHtml(((track.metrics || {}).loudness_proxy_db ?? "-"))}</td>
      <td>${escapeHtml(((track.metrics || {}).peak_dbfs ?? "-"))}</td>
      <td>${escapeHtml(((track.metrics || {}).clipping_ratio ?? "-"))}</td>
      <td>${escapeHtml(((track.metrics || {}).leading_silence_seconds ?? "-"))}</td>
      <td>${escapeHtml(((track.metrics || {}).trailing_silence_seconds ?? "-"))}</td>
    </tr>
  `).join("");
  return `
    <div class="panel-title subhead"><span>Mastering QA</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.status || "missing")}
      ${metric("Profile", summary.profile_id || "demo_review")}
      ${metric("Avg Loudness", summary.average_loudness_proxy_db ?? "-")}
      ${metric("Max Delta", summary.max_track_loudness_delta_db ?? "-")}
      ${metric("Candidate", summary.selected_candidate_id || "-")}
      ${metric("Actions", (plan.summary || {}).action_count || 0)}
    </div>
    <div class="grid2">
      <label>Mastering Profile
        <select id="release-mastering-profile">
          <option value="demo_review">demo_review</option>
          <option value="streaming_balanced">streaming_balanced</option>
          <option value="album_consistency">album_consistency</option>
          <option value="podcast_music_bed">podcast_music_bed</option>
        </select>
      </label>
      <label>Candidate
        <select id="release-mastering-candidate">${candidateOptions || "<option value=''>none</option>"}</select>
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="release-mastering-analyze" type="button">Analyze Mastering</button>
      <button class="secondary" id="release-mastering-plan" type="button">Create Mastering Plan</button>
      <button class="secondary" id="release-render-mastering-candidate" type="button">Render Mastered Candidate</button>
      <button class="secondary" id="release-mastering-review" type="button">Accept Mastered Candidate</button>
      <button class="secondary" id="release-mastering-select" type="button">Select Mastered Candidate</button>
      <button class="secondary" id="release-mastering-reset" type="button">Reset Mastering</button>
    </div>
    <table>
      <thead><tr><th>Track</th><th>Status</th><th>Loudness Proxy</th><th>Peak dBFS</th><th>Clip</th><th>Lead Silence</th><th>Tail Silence</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='7'>No mastering analysis yet.</td></tr>"}</tbody>
    </table>
  `;
}

function releaseEncodedAudioHtml(encodedAudioData, release) {
  const summary = (encodedAudioData && encodedAudioData.summary) || {};
  const profiles = (encodedAudioData && encodedAudioData.profiles) || [];
  const profileRows = profiles.map((profile) => `
    <tr>
      <td>${escapeHtml(profile.profile_id || "-")}</td>
      <td><span class="status ${escapeHtml(profile.status || "")}">${escapeHtml(profile.status || "-")}</span></td>
      <td>${escapeHtml(profile.format || "-")}</td>
      <td>${escapeHtml(profile.extension || "-")}</td>
      <td>${escapeHtml(profile.completed_count || 0)}/${escapeHtml(profile.track_count || 0)}</td>
      <td>${profile.current === false ? "stale" : "current"}</td>
    </tr>
  `).join("");
  return `
    <div class="panel-title subhead"><span>Encoded Audio Formats</span></div>
    <div class="summary-grid">
      ${metric("Status", summary.status || "missing")}
      ${metric("Profiles", summary.profile_count || 0)}
      ${metric("Completed", (summary.completed_profiles || []).length || 0)}
      ${metric("Failed", (summary.failed_profiles || []).length || 0)}
    </div>
    <div class="grid2">
      <label>Format Profiles
        <input id="release-encoded-audio-profiles" value="mp3_320,flac_lossless">
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="release-render-encoded-audio" type="button">Render Encoded Audio</button>
      <button class="secondary" id="release-verify-encoded-audio" type="button">Verify Encoded Audio</button>
      <button class="secondary" id="release-refresh-encoded-audio-health" type="button">Refresh Encoded Health</button>
      <button class="secondary" id="release-reset-encoded-audio" type="button">Reset Encoded Audio</button>
    </div>
    <table>
      <thead><tr><th>Profile</th><th>Status</th><th>Format</th><th>Ext</th><th>Tracks</th><th>Current</th></tr></thead>
      <tbody>${profileRows || "<tr><td colspan='6'>No encoded audio profiles yet.</td></tr>"}</tbody>
    </table>
  `;
}

function bindProjectEditorPreviewAudioControls() {
  bindAction("project-editor-render-preview-audio", async () => {
    const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/render-audio`, { method: "POST" });
    projectEditorPreview = data.preview;
    renderProjectEditorPreview();
  });
  bindAction("project-editor-render-parent-audio", async () => {
    const parentVersion = $("project-editor-parent") ? $("project-editor-parent").value : projectEditorParentId;
    await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(parentVersion)}/render-audio`, { method: "POST" });
    renderProjectEditorPreview();
  });
  const parentAudio = $("project-editor-audio-parent");
  const previewAudio = $("project-editor-audio-preview");
  if (parentAudio && previewAudio) {
    parentAudio.addEventListener("play", () => previewAudio.pause());
    previewAudio.addEventListener("play", () => parentAudio.pause());
  }
}

async function renderStems(job, target) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/stems`);
    const manifest = data.manifest || {};
    const stems = manifest.stems || [];
    const rows = stems.map((stem) => `
      <tr data-stem-id="${escapeHtml(stem.stem_id)}">
        <td>${escapeHtml(stem.stem_id)}</td>
        <td>${escapeHtml(stem.role || "-")}</td>
        <td>${escapeHtml(stem.instrument || "-")}</td>
        <td>${escapeHtml(stem.note_count ?? 0)}</td>
        <td>${escapeHtml(stem.duration_beats ?? 0)}</td>
        <td>${stem.midi_exists ? `<a href="/api/jobs/${encodeURIComponent(job.job_id)}/stems/${encodeURIComponent(stem.stem_id)}/midi">Download MIDI</a>` : "-"}</td>
        <td><span class="status ${stem.audio_status || "not_started"}">${escapeHtml(stem.audio_status || "not_started")}</span></td>
        <td>${escapeHtml(stem.audio_error || "-")}</td>
        <td>
          <div class="actions">
            <button class="secondary render-stem-audio" data-stem-id="${escapeHtml(stem.stem_id)}" type="button">Render Audio</button>
            ${stem.audio_exists ? `<a class="button-link secondary" href="/api/jobs/${encodeURIComponent(job.job_id)}/stems/${encodeURIComponent(stem.stem_id)}/audio">Download WAV</a>` : ""}
            <button class="secondary stem-solo" data-stem-id="${escapeHtml(stem.stem_id)}" type="button">Solo</button>
            <button class="secondary stem-mute" data-stem-id="${escapeHtml(stem.stem_id)}" type="button">Mute</button>
          </div>
          ${stem.audio_exists ? `<audio class="audio-player stem-audio" data-stem-id="${escapeHtml(stem.stem_id)}" controls src="/api/jobs/${encodeURIComponent(job.job_id)}/stems/${encodeURIComponent(stem.stem_id)}/audio"></audio>` : ""}
        </td>
      </tr>
    `).join("");
    target.innerHTML = `
      <div class="actions">
        <button id="render-stems" type="button">Render Stems</button>
        <button class="secondary" id="render-stem-audio" type="button">Render Stem Audio</button>
        <button class="secondary" id="refresh-stems" type="button">Refresh</button>
      </div>
      ${stems.length && data.status === "not_started" ? `<div class="empty">Stems have not been rendered yet.</div>` : ""}
      <table>
        <thead><tr><th>Stem</th><th>Role</th><th>Instrument</th><th>Notes</th><th>Duration</th><th>MIDI</th><th>WAV</th><th>Error</th><th>Actions</th></tr></thead>
        <tbody>${rows || "<tr><td colspan='9'>Stems have not been rendered yet.</td></tr>"}</tbody>
      </table>
    `;
    bindAction("render-stems", async () => {
      await api(`/api/jobs/${encodeURIComponent(job.job_id)}/render-stems`, { method: "POST" });
      await renderStems(job, target);
    });
    bindAction("render-stem-audio", async () => {
      await api(`/api/jobs/${encodeURIComponent(job.job_id)}/render-stem-audio`, { method: "POST" });
      await renderStems(job, target);
    });
    bindAction("refresh-stems", async () => {
      await renderStems(job, target);
    });
    target.querySelectorAll(".render-stem-audio").forEach((button) => {
      button.addEventListener("click", async () => {
        await api(`/api/jobs/${encodeURIComponent(job.job_id)}/render-stem-audio`, {
          method: "POST",
          body: JSON.stringify({ stem_ids: [button.dataset.stemId] }),
        });
        await renderStems(job, target);
      });
    });
    target.querySelectorAll(".stem-solo").forEach((button) => {
      button.addEventListener("click", () => soloStem(target, button.dataset.stemId));
    });
    target.querySelectorAll(".stem-mute").forEach((button) => {
      button.addEventListener("click", () => muteStem(target, button.dataset.stemId));
    });
  } catch (err) {
    if (String(err.message || "").includes("song-plan.json is not available")) {
      target.innerHTML = `<div class="empty">SongPlan is not available yet.</div>`;
      return;
    }
    target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
  }
}

function pitchRange(track) {
  if (track.pitch_min == null || track.pitch_max == null) return "-";
  return `${track.pitch_min}-${track.pitch_max}`;
}

function audioControls(job) {
  if (!job.artifacts || !job.artifacts.audio) return "";
  return `
    <audio class="audio-player" controls src="/api/jobs/${encodeURIComponent(job.job_id)}/audio"></audio>
  `;
}

function soloStem(target, stemId) {
  target.querySelectorAll(".stem-audio").forEach((audio) => {
    if (audio.dataset.stemId === stemId) {
      audio.muted = false;
      audio.play().catch(() => {});
    } else {
      audio.pause();
      audio.currentTime = 0;
    }
  });
}

function muteStem(target, stemId) {
  target.querySelectorAll(".stem-audio").forEach((audio) => {
    if (audio.dataset.stemId === stemId) {
      audio.pause();
      audio.muted = true;
    }
  });
}

globalThis.audioCampaignReleaseId = () => {
  const releaseId = $("audio-campaign-release-id").value.trim();
  if (!releaseId) {
    $("audio-campaign-status").textContent = "missing release";
    return "";
  }
  return releaseId;
};

Object.assign(globalThis, { showAudioLabResult, showAudioFixSprintResult, showAudioCampaignResult, releaseAudioReviewHtml, releaseAudioRevisionHtml, releaseMasteringHtml, releaseEncodedAudioHtml, bindProjectEditorPreviewAudioControls, renderStems, pitchRange, audioControls, soloStem, muteStem, audioCampaignReleaseId });

export { showAudioLabResult, showAudioFixSprintResult, showAudioCampaignResult, releaseAudioReviewHtml, releaseAudioRevisionHtml, releaseMasteringHtml, releaseEncodedAudioHtml, bindProjectEditorPreviewAudioControls, renderStems, pitchRange, audioControls, soloStem, muteStem, audioCampaignReleaseId };
