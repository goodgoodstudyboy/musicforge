async function api(path, options = {}) {
  if (authRequired && !accessToken && path !== "/api/info") {
    showAuthLock("");
    throw new Error("Unauthorized.");
  }
  const headers = new Headers(options.headers || {});
  if (authRequired && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const res = await fetch(path, { ...options, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (res.status === 401) {
    sessionStorage.removeItem("musicforge_access_token");
    accessToken = "";
    showAuthLock("Unauthorized.");
    throw new Error(data.error || res.statusText);
  }
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

async function init() {
  const info = await api("/api/info");
  authRequired = Boolean(info.auth_required);
  if (authRequired && !accessToken) {
    showAuthLock("");
    $("version").textContent = "v" + info.version;
    $("mode").textContent = info.mode;
    $("runs").textContent = info.runs_dir;
    return;
  }
  hideAuthLock();
  template = await api("/api/template");
  $("version").textContent = "v" + info.version;
  $("mode").textContent = info.mode;
  $("runs").textContent = info.runs_dir;
  fillPresets();
  fillForm(template.defaults);
  await loadProvider();
  await loadGaHealth();
  await loadMaintenanceStatus();
  await loadPromptTemplates();
  await loadEditorTemplates();
  await loadRenderer();
  await loadEditPresets();
  await loadAssets();
  await loadReferences();
  await loadContextPacks();
  await loadJobs();
  await loadProjects();
  await loadReleases();
  await loadPortfolioAudits();
  await loadAcceptanceReferenceData();
  await loadAcceptanceAnalytics();
  await loadAcceptanceFixSprints();
  await loadAcceptanceKb();
  await loadPlanningSimulations();
  await loadPlanningGovernance();
  await loadPlanningImpact();
  await loadAcceptanceSuites();
  await loadBatches();
  setInterval(() => {
    loadJobs();
    loadProjects();
    loadReleases();
    loadPortfolioAudits();
    loadAcceptanceAnalytics();
    loadAcceptanceFixSprints();
    loadAcceptanceKb();
    loadPlanningSimulations();
    loadPlanningGovernance();
    loadPlanningImpact();
    loadAcceptanceSuites();
    loadAssets();
    loadReferences();
    loadContextPacks();
    loadEditorTemplates();
    loadBatches();
  }, 2000);
  $("poll").textContent = "polling 2s";
}

function showAuthLock(message) {
  document.body.classList.add("locked");
  $("auth-message").textContent = message || "";
}

function hideAuthLock() {
  document.body.classList.remove("locked");
  $("auth-message").textContent = "";
}

function fillForm(data) {
  for (const [key, value] of Object.entries(data)) {
    const el = $(key);
    if (el) el.value = value ?? "";
  }
}

function formPayload() {
  const payload = {
    title: $("title").value.trim(),
    language: $("language").value.trim(),
    style: $("style").value.trim(),
    theme: $("theme").value.trim(),
    duration_seconds: Number($("duration_seconds").value),
    vocal_mode: $("vocal_mode").value,
    generation_mode: $("generation_mode").value,
    pipeline_mode: $("pipeline_mode").value,
  };
  if ($("tempo_bpm").value) payload.tempo_bpm = Number($("tempo_bpm").value);
  if ($("key").value.trim()) payload.key = $("key").value.trim();
  if ($("lyrics").value.trim()) payload.lyrics = $("lyrics").value;
  const refs = assetRefsPayload("song-asset-refs");
  if (refs.length) payload.asset_refs = refs;
  const referenceRefs = referenceRefsPayload("song-reference-refs");
  if (referenceRefs.length) payload.reference_refs = referenceRefs;
  const contextPackId = contextPackIdPayload("song-context-pack");
  if (contextPackId) payload.context_pack_id = contextPackId;
  return payload;
}

async function loadProvider() {
  const data = await api("/api/provider");
  applyProvider(data);
}

function applyProvider(data) {
  providerConfig = data.config;
  $("provider-status").textContent = data.configured ? "configured" : "not configured";
  $("provider-base-url").value = providerConfig.base_url || "";
  $("provider-wire-api").value = providerConfig.wire_api || "openai_chat_completions";
  $("provider-model").value = providerConfig.model || "";
  $("provider-light-model").value = providerConfig.light_model || "";
  $("provider-review-model").value = providerConfig.review_model || "";
  $("provider-timeout-seconds").value = providerConfig.timeout_seconds || 60;
  $("provider-max-retries").value = providerConfig.max_retries ?? 1;
  $("provider-max-output-tokens").value = providerConfig.max_output_tokens || 4000;
  $("provider-api-key").placeholder = providerConfig.api_key_set
    ? `saved: ${providerConfig.api_key_masked}`
    : "leave blank to save empty key";
}

function providerPayload() {
  return {
    base_url: $("provider-base-url").value.trim(),
    wire_api: $("provider-wire-api").value,
    api_key: $("provider-api-key").value,
    model: $("provider-model").value.trim(),
    light_model: $("provider-light-model").value.trim(),
    review_model: $("provider-review-model").value.trim(),
    timeout_seconds: Number($("provider-timeout-seconds").value || 60),
    max_retries: Number($("provider-max-retries").value || 0),
    max_output_tokens: Number($("provider-max-output-tokens").value || 4000),
  };
}

async function loadRenderer() {
  const data = await api("/api/renderer");
  applyRenderer(data);
}

function applyRenderer(data) {
  rendererConfig = data.config;
  $("renderer-status").textContent = data.configured ? "configured" : "missing";
  $("renderer-type").value = rendererConfig.renderer_type || "fluidsynth";
  $("renderer-fluidsynth-path").value = rendererConfig.fluidsynth_path || "fluidsynth";
  $("renderer-soundfont-path").value = rendererConfig.soundfont_path || "";
  $("renderer-sample-rate").value = rendererConfig.sample_rate || 44100;
  $("renderer-gain").value = rendererConfig.gain ?? 0.6;
  const exists = rendererConfig.soundfont_exists ? "soundfont exists" : "soundfont missing";
  $("renderer-message").textContent = rendererConfig.soundfont_path ? exists : "";
}

function rendererPayload() {
  return {
    renderer_type: $("renderer-type").value,
    fluidsynth_path: $("renderer-fluidsynth-path").value.trim(),
    soundfont_path: $("renderer-soundfont-path").value.trim(),
    sample_rate: Number($("renderer-sample-rate").value || 44100),
    gain: Number($("renderer-gain").value || 0.6),
  };
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
    reader.onerror = () => reject(reader.error || new Error("File read failed."));
    reader.readAsDataURL(file);
  });
}

function chordList(id) {
  return $(id).value.split(",").map((item) => item.trim()).filter(Boolean);
}

function setSelectValue(id, value) {
  const select = $(id);
  if (select && value != null) select.value = value;
}

function isDerivedSection(sectionId) {
  return String(sectionId || "").startsWith("derived-section-");
}

function isDerivedTrack(trackId) {
  return String(trackId || "").startsWith("derived-track-");
}

function isDerivedNote(noteId) {
  return String(noteId || "").startsWith("derived-note-");
}

function parseJsonField(id) {
  const raw = $(id).value.trim();
  if (!raw) return {};
  return JSON.parse(raw);
}

function actionQueueActionLabel(action) {
  return ({
    refresh_recommendations: "Recommendations",
    refresh_conflicts: "Conflicts",
    save_recommended_context_pack: "Context",
    generate_local_candidates: "Local",
    generate_provider_candidates: "Provider",
    refresh_judge_report: "Judge",
    refresh_decision_report: "Decision",
    inspect_conflict: "Inspect",
    manual_apply_candidate: "Manual Apply",
    manual_resolve_task: "Manual Resolve",
    manual_add_follow_up: "Manual Follow-up",
    skip_stale_task: "Blocked Stale",
    skip_archived_task: "Blocked Archived",
    no_action: "No Action",
  })[action] || action || "-";
}

function resolveOptionByRole(selectId, role, index) {
  if (!role) return "";
  const options = Array.from($(selectId).options).filter((option) => option.value && option.value.toLowerCase().includes(String(role).toLowerCase()));
  if (!options.length) return "";
  const targetIndex = Number(index || 0);
  return (options[targetIndex < 0 ? options.length - 1 : Math.min(targetIndex, options.length - 1)] || options[0]).value;
}

function finalExportManifestHtml(manifest) {
  const rows = (manifest.files || []).map((file) => `
    <tr>
      <td>${escapeHtml(file.kind)}</td>
      <td>${escapeHtml(file.path)}</td>
      <td>${file.exists ? "yes" : "-"}</td>
      <td>${escapeHtml(file.skipped || file.size_bytes || "-")}</td>
    </tr>
  `).join("");
  return `
    <div class="summary-grid">
      ${metric("Export Version", manifest.version_id || "-")}
      ${metric("Job", manifest.job_id || "-")}
      ${metric("Gate", (manifest.quality_gate || {}).status || "-")}
      ${metric("Generated", manifest.generated_at || "-")}
    </div>
    ${manifest.zip ? `<div class="summary-grid">
      ${metric("ZIP", manifest.zip.filename || "final-export.zip")}
      ${metric("ZIP Size", manifest.zip.size_bytes || 0)}
      ${metric("ZIP Entries", manifest.zip.entry_count || 0)}
      ${metric("ZIP SHA", (manifest.zip.sha256 || "").slice(0, 12))}
    </div>` : ""}
    <table>
      <thead><tr><th>Kind</th><th>Path</th><th>Exists</th><th>Info</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='4'>No files.</td></tr>"}</tbody>
    </table>
  `;
}

async function renderDetail(jobId) {
  const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
  const detail = $("detail");
  const summary = job.summary || {};
  const tabs = ["summary", "edit", "assets", "nodes", "timeline", "tracks", "stems", "quality", "validator", "json", "logs", "artifacts"];
  detail.innerHTML = `
    <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
      <span>${escapeHtml(job.title)}</span>
      <span class="status ${job.status}">${job.status}</span>
    </div>
    <div class="summary-grid">
      ${metric("Tempo", summary.tempo_bpm || "-")}
      ${metric("Key", summary.key || "-")}
      ${metric("Sections", summary.section_count || "-")}
      ${metric("Notes", summary.note_count || "-")}
    </div>
    <div class="summary-grid">
      ${metric("Attempt", job.attempt_count ?? 0)}
      ${metric("Retry Count", job.retry_count ?? 0)}
      ${metric("Heartbeat", job.heartbeat_at || "-")}
      ${metric("Stalled", job.stalled ? "yes" : "no")}
    </div>
    <div class="summary-grid">
      ${metric("Generation Mode", job.generation_mode || (job.provider_snapshot || {}).mode || "-")}
      ${metric("Pipeline Mode", job.pipeline_mode || "single")}
      ${metric("Step", job.step || "-")}
      ${metric("Updated", job.updated_at || "-")}
    </div>
    ${job.input_payload && job.input_payload.context_pack ? `
      <div class="summary-grid">
        ${metric("Context Pack", job.input_payload.context_pack.pack_id || "-")}
        ${metric("Context Name", job.input_payload.context_pack.name || "-")}
        ${metric("Context Assets", (job.input_payload.context_pack.asset_refs || []).length)}
        ${metric("Context References", (job.input_payload.context_pack.reference_refs || []).length)}
      </div>
    ` : ""}
    ${providerSnapshotHtml(job.provider_snapshot || {})}
    <div class="actions">
      ${actionButtons(job)}
      <span>${escapeHtml(job.output_dir)}</span>
    </div>
    ${audioControls(job)}
    ${job.error ? `<p class="error">${escapeHtml(job.error)}</p>` : ""}
    <div class="tabs">
      ${tabs.map(tab => `<button type="button" class="${activeTab === tab ? "active" : ""}" data-tab="${tab}">${tabLabel(tab)}</button>`).join("")}
    </div>
    <div id="tab-content"></div>
  `;
  detail.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", async () => {
      activeTab = button.dataset.tab;
      await renderDetail(job.job_id);
    });
  });
  wireJobActions(job);
  await renderTab(job);
}

async function renderTab(job) {
  const target = $("tab-content");
  if (activeTab === "summary") {
    target.innerHTML = `<pre>${escapeHtml(JSON.stringify(job, null, 2))}</pre>`;
  } else if (activeTab === "edit") {
    await renderEdit(job, target);
  } else if (activeTab === "assets") {
    await renderJobAssets(job, target);
  } else if (activeTab === "timeline") {
    await renderTimeline(job, target);
  } else if (activeTab === "nodes") {
    await renderNodes(job, target);
  } else if (activeTab === "tracks") {
    await renderTracks(job, target);
  } else if (activeTab === "stems") {
    await renderStems(job, target);
  } else if (activeTab === "quality") {
    await renderQuality(job, target);
  } else if (activeTab === "validator") {
    await renderValidator(job, target);
  } else if (activeTab === "logs") {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/events`);
    target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.events, null, 2))}</pre>`;
  } else if (activeTab === "json") {
    try {
      const plan = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/song-plan`);
      target.innerHTML = `<pre>${escapeHtml(JSON.stringify(plan, null, 2))}</pre>`;
    } catch (err) {
      target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
    }
  } else if (activeTab === "artifacts") {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/artifacts`);
    target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.artifacts, null, 2))}</pre>`;
  }
}

async function renderTimeline(job, target) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/timeline`);
    const view = data.view;
    const rows = view.sections.map((section) => `
      <tr>
        <td>${escapeHtml(section.name)}</td>
        <td>${escapeHtml(section.start_bar)}-${escapeHtml(section.end_bar)} (${escapeHtml(section.bars)})</td>
        <td>${escapeHtml(section.estimated_start_seconds)}s</td>
        <td>${escapeHtml(section.estimated_end_seconds)}s</td>
        <td>${escapeHtml(section.chords.join(" · "))}</td>
        <td>${escapeHtml(section.role || "-")}</td>
        <td>${escapeHtml(section.energy ?? 0)}</td>
        <td>${escapeHtml(section.tension ?? 0)}</td>
        <td>${escapeHtml(section.density ?? 0)}</td>
        <td>${section.hook ? "yes" : "-"}</td>
      </tr>
    `).join("");
    target.innerHTML = `
      ${runtimeHeader(view)}
      ${warnings(view.warnings)}
      <table>
        <thead><tr><th>Section</th><th>Bars</th><th>Start</th><th>End</th><th>Chords</th><th>Role</th><th>Energy</th><th>Tension</th><th>Density</th><th>Hook</th></tr></thead>
        <tbody>${rows || "<tr><td colspan='10'>No sections.</td></tr>"}</tbody>
      </table>
    `;
  } catch (err) {
    target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
  }
}

async function renderEdit(job, target) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/edit`);
    const edit = data.edit || {};
    const targetData = edit.target || {};
    target.innerHTML = `
      <div class="summary-grid">
        ${metric("Edit Type", edit.edit_type || "-")}
        ${metric("Parent Version", edit.parent_version_id || "-")}
        ${metric("Parent Job", edit.parent_job_id || "-")}
        ${metric("Strength", edit.strength ?? "-")}
      </div>
      <div class="summary-grid">
        ${metric("Section", targetData.section_name || "-")}
        ${metric("Track", targetData.track_name || "-")}
        ${metric("Field", targetData.field || "-")}
        ${metric("Provider Mode", edit.provider_mode || "-")}
      </div>
      <p>${escapeHtml(edit.instruction || "")}</p>
      <pre>${escapeHtml(JSON.stringify(edit, null, 2))}</pre>
    `;
  } catch (err) {
    target.innerHTML = `<div class="empty">No edit metadata for this job.</div>`;
  }
}

async function renderTracks(job, target) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/tracks`);
    const view = data.view;
    const rows = view.tracks.map((track) => `
      <tr>
        <td>${escapeHtml(track.name)}</td>
        <td>${escapeHtml(track.instrument)}</td>
        <td>${escapeHtml(track.note_count)}</td>
        <td>${escapeHtml(pitchRange(track))}</td>
        <td>${escapeHtml(track.end_beat_max ?? "-")}</td>
        <td>${escapeHtml(track.average_velocity ?? "-")}</td>
      </tr>
    `).join("");
    target.innerHTML = `
      <div class="summary-grid">
        ${metric("Tracks", view.track_count)}
        ${metric("Notes", view.note_count)}
        ${metric("Total Bars", view.total_bars)}
        ${metric("Density", view.tracks.length ? (view.tracks[0].density_notes_per_bar ?? "-") : "-")}
      </div>
      <table>
        <thead><tr><th>Track</th><th>Instrument</th><th>Notes</th><th>Pitch Range</th><th>End Beat</th><th>Avg Velocity</th></tr></thead>
        <tbody>${rows || "<tr><td colspan='6'>No tracks.</td></tr>"}</tbody>
      </table>
    `;
  } catch (err) {
    target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
  }
}

async function renderValidator(job, target) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/validator`);
    const view = data.view;
    const rows = view.checks.map((check) => `
      <tr><td>${escapeHtml(check.name)}</td><td>${escapeHtml(check.status)}</td></tr>
    `).join("");
    target.innerHTML = `
      <div class="summary-grid">
        ${metric("Status", view.status)}
        ${metric("Passed", view.passed ? "yes" : "no")}
      ${metric("Checks", view.check_count)}
      ${metric("MIDI Size", view.midi.size)}
      ${metric("Audio Size", view.audio ? view.audio.size_bytes : 0)}
    </div>
      ${warnings(view.warnings)}
      <table>
        <thead><tr><th>Check</th><th>Status</th></tr></thead>
        <tbody>${rows || "<tr><td colspan='2'>No checks.</td></tr>"}</tbody>
      </table>
    `;
  } catch (err) {
    target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
  }
}

function providerSnapshotHtml(snapshot) {
  if (!snapshot || !snapshot.mode) return "";
  return `
    <div class="summary-grid">
      ${metric("Generation Mode", snapshot.mode)}
      ${metric("Provider Model", snapshot.model || "-")}
      ${metric("Wire API", snapshot.wire_api || "-")}
      ${metric("API Key", snapshot.api_key_masked || (snapshot.api_key_set ? "set" : "-"))}
    </div>
  `;
}

function tabLabel(tab) {
  const labels = {
    summary: "Summary",
    edit: "Edit",
    assets: "Assets",
    nodes: "Nodes",
    timeline: "Timeline",
    tracks: "Tracks",
    stems: "Stems",
    quality: "Quality",
    validator: "Validator",
    json: "SongPlan JSON",
    logs: "Logs",
    artifacts: "Artifacts",
  };
  return labels[tab] || tab;
}

function actionButtons(job) {
  const id = encodeURIComponent(job.job_id);
  const canDownload = job.artifacts && job.artifacts.midi;
  const buttons = [];
  if (canDownload) buttons.push(`<a class="button-link" href="/api/jobs/${id}/midi">Download MIDI</a>`);
  if (job.status === "completed" && canDownload) {
    buttons.push(`<button class="secondary" id="render-audio" type="button">Render Audio</button>`);
  }
  if (job.artifacts && job.artifacts.audio) {
    buttons.push(`<a class="button-link secondary" href="/api/jobs/${id}/audio">Download WAV</a>`);
  }
  buttons.push(`<button class="secondary" id="open-folder" type="button">Open Folder</button>`);
  if (job.status === "running" || job.status === "queued") {
    buttons.push(`<button class="danger" id="cancel-job" type="button">Cancel</button>`);
  }
  if (job.status === "failed" || job.status === "stalled" || job.status === "interrupted") {
    buttons.push(`<button class="secondary" id="retry-job" type="button">Retry</button>`);
  }
  if (job.hidden) {
    buttons.push(`<button class="secondary" id="unhide-job" type="button">Unhide</button>`);
  } else {
    buttons.push(`<button class="secondary" id="hide-job" type="button">Hide</button>`);
  }
  if (job.status !== "running") {
    buttons.push(`<button class="danger" id="delete-job" type="button">Delete</button>`);
  }
  return buttons.join("");
}

function bindAction(id, fn) {
  const el = $(id);
  if (!el) return;
  el.addEventListener("click", async () => {
    try { await fn(); }
    catch (err) { alert(err.message); }
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function slugifyClient(value) {
  return String(value || "custom-edit")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64) || "custom-edit";
}

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

globalThis.$ = (id) => document.getElementById(id);

Object.assign(globalThis, { api, init, showAuthLock, hideAuthLock, fillForm, formPayload, loadProvider, applyProvider, providerPayload, loadRenderer, applyRenderer, rendererPayload, fileToBase64, chordList, setSelectValue, isDerivedSection, isDerivedTrack, isDerivedNote, parseJsonField, actionQueueActionLabel, resolveOptionByRole, finalExportManifestHtml, renderDetail, renderTab, renderTimeline, renderEdit, renderTracks, renderValidator, providerSnapshotHtml, tabLabel, actionButtons, bindAction, escapeHtml, slugifyClient, debounce, $ });

export { api, init, showAuthLock, hideAuthLock, fillForm, formPayload, loadProvider, applyProvider, providerPayload, loadRenderer, applyRenderer, rendererPayload, fileToBase64, chordList, setSelectValue, isDerivedSection, isDerivedTrack, isDerivedNote, parseJsonField, actionQueueActionLabel, resolveOptionByRole, finalExportManifestHtml, renderDetail, renderTab, renderTimeline, renderEdit, renderTracks, renderValidator, providerSnapshotHtml, tabLabel, actionButtons, bindAction, escapeHtml, slugifyClient, debounce, $ };
