function assetContentSummary(asset) {
  const content = asset.content || {};
  return {
    note_count: Array.isArray(content.notes) ? content.notes.length : 0,
    chord_count: Array.isArray(content.chords) ? content.chords.length : 0,
    section_name: content.section_name || "",
    track_name: content.track_name || "",
  };
}

function renderProjects() {
  const list = $("project-list");
  if (!projects.length) {
    list.innerHTML = "<div class='empty'>No projects yet.</div>";
    return;
  }
  const rows = projects.map((project) => `
    <tr class="${project.project_id === selectedProjectId ? "active" : ""}">
      <td><button class="secondary project-open" data-project-id="${escapeHtml(project.project_id)}" type="button">Open</button></td>
      <td>${escapeHtml(project.name)}</td>
      <td><span class="status ${project.status}">${escapeHtml(project.status)}</span></td>
      <td>${escapeHtml(project.version_count || 0)}</td>
      <td>${escapeHtml(project.selected_version_id || "-")}</td>
      <td>${escapeHtml(project.final_version_id || "-")}</td>
      <td>${escapeHtml(project.best_quality_score ?? "-")}</td>
    </tr>
  `).join("");
  list.innerHTML = `
    <table>
      <thead><tr><th></th><th>Name</th><th>Status</th><th>Versions</th><th>Selected</th><th>Final</th><th>Best Quality</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  list.querySelectorAll(".project-open").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedProjectId = button.dataset.projectId;
      activeProjectTab = "versions";
      renderProjects();
      await renderProjectDetail(selectedProjectId);
    });
  });
}

async function renderProjectDetail(projectId) {
  const data = await api(`/api/projects/${encodeURIComponent(projectId)}`);
  const project = data.project;
  const versions = data.versions || [];
  const tabs = ["versions", "variation", "edit", "editor", "mix-board", "review-workbench", "review-sprints", "candidates", "quality-gate", "final-export", "references", "compare", "export", "events"];
  const target = $("project-detail");
  target.innerHTML = `
    <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
      <span>${escapeHtml(project.name)}</span>
      <span class="status ${project.status}">${escapeHtml(project.status)}</span>
    </div>
    <div class="summary-grid">
      ${metric("Versions", project.version_count || 0)}
      ${metric("Selected", project.selected_version_id || "-")}
      ${metric("Final", project.final_version_id || "-")}
      ${metric("Best Quality", project.best_quality_score ?? "-")}
    </div>
    <div class="actions">
      ${projectActionButtons(project)}
      <span>${escapeHtml(project.project_id)}</span>
    </div>
    <div class="grid2">
      <label>New Version Name
        <input id="project-version-name" value="Version ${(versions.length || 0) + 1}">
      </label>
      <label>Add Existing Job ID
        <input id="project-existing-job-id" placeholder="job-id">
      </label>
    </div>
    <label>Version Note
      <input id="project-version-note" placeholder="short note">
    </label>
    <label>Asset References
      <div id="project-version-asset-refs" class="asset-ref-list"></div>
    </label>
    <label>Reference Materials
      <div id="project-version-reference-refs" class="reference-ref-list"></div>
    </label>
    <label>Context Pack
      <select id="project-version-context-pack" class="context-pack-select"><option value="">none</option></select>
    </label>
    <div class="actions">
      <button id="project-new-version" type="button">New Version</button>
      <button class="secondary" id="project-add-job" type="button">Add Existing Job</button>
    </div>
    <div class="tabs">
      ${tabs.map(tab => `<button type="button" class="${activeProjectTab === tab ? "active" : ""}" data-project-tab="${tab}">${projectTabLabel(tab)}</button>`).join("")}
    </div>
    <div id="project-tab-content"></div>
  `;
  target.querySelectorAll("[data-project-tab]").forEach((button) => {
    button.addEventListener("click", async () => {
      activeProjectTab = button.dataset.projectTab;
      await renderProjectDetail(project.project_id);
    });
  });
  wireProjectActions(project, versions);
  renderAssetSelectors();
  renderReferenceSelectors();
  renderContextPackSelectors();
  await renderProjectTab(project, versions);
}

function projectActionButtons(project) {
  const buttons = [];
  buttons.push(`<a class="button-link secondary" href="/api/projects/${encodeURIComponent(project.project_id)}/export">Export</a>`);
  if (project.hidden) {
    buttons.push(`<button class="secondary" id="unhide-project" type="button">Unhide</button>`);
  } else {
    buttons.push(`<button class="secondary" id="hide-project" type="button">Hide</button>`);
  }
  buttons.push(`<button class="danger" id="delete-project" type="button">Delete Project</button>`);
  return buttons.join("");
}

function wireProjectActions(project, versions) {
  const id = encodeURIComponent(project.project_id);
  bindAction("project-new-version", async () => {
    await api(`/api/projects/${id}/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request: formPayload(),
        name: $("project-version-name").value.trim(),
        note: $("project-version-note").value.trim(),
        generation_mode: $("generation_mode").value,
        pipeline_mode: $("pipeline_mode").value,
        asset_refs: assetRefsPayload("project-version-asset-refs"),
        reference_refs: referenceRefsPayload("project-version-reference-refs"),
        context_pack_id: contextPackIdPayload("project-version-context-pack"),
      }),
    });
    await loadJobs();
    await loadProjects();
  });
  bindAction("project-add-job", async () => {
    await api(`/api/projects/${id}/versions/from-job`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: $("project-existing-job-id").value.trim(),
        name: $("project-version-name").value.trim(),
        note: $("project-version-note").value.trim(),
      }),
    });
    await loadProjects();
  });
  bindAction("hide-project", async () => {
    await api(`/api/projects/${id}/hide`, { method: "POST" });
    await loadProjects();
  });
  bindAction("unhide-project", async () => {
    await api(`/api/projects/${id}/unhide`, { method: "POST" });
    await loadProjects();
  });
  bindAction("delete-project", async () => {
    if (!confirm("Delete this project metadata? Job runs stay in runs/.")) return;
    await api(`/api/projects/${id}/delete`, { method: "POST" });
    selectedProjectId = null;
    await loadProjects();
  });
  $("project-tab-content").addEventListener("click", async (event) => {
    const target = event.target;
    if (!target.dataset) return;
    if (target.dataset.projectJobId) {
      selectedJobId = target.dataset.projectJobId;
      activeTab = "summary";
      await loadJobs();
      return;
    }
    if (target.dataset.projectSelectVersion) {
      await api(`/api/projects/${id}/selected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version_id: target.dataset.projectSelectVersion }),
      });
      await loadProjects();
      return;
    }
    if (target.dataset.projectVariationVersion) {
      projectVariationParentId = target.dataset.projectVariationVersion;
      activeProjectTab = "variation";
      await renderProjectDetail(project.project_id);
      return;
    }
    if (target.dataset.projectEditVersion) {
      projectEditParentId = target.dataset.projectEditVersion;
      activeProjectTab = "edit";
      await renderProjectDetail(project.project_id);
      return;
    }
    if (target.dataset.projectEditorVersion) {
      projectEditorParentId = target.dataset.projectEditorVersion;
      activeProjectTab = "editor";
      await renderProjectDetail(project.project_id);
      return;
    }
    if (target.dataset.projectEvaluateVersion) {
      await api(`/api/projects/${id}/versions/${encodeURIComponent(target.dataset.projectEvaluateVersion)}/evaluate`, { method: "POST" });
      await loadProjects();
      return;
    }
    if (target.dataset.projectExportVersion) {
      await api(`/api/projects/${id}/final-export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version_id: target.dataset.projectExportVersion }),
      });
      activeProjectTab = "final-export";
      await loadProjects();
      return;
    }
    if (target.dataset.projectFinalVersion) {
      await api(`/api/projects/${id}/final`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version_id: target.dataset.projectFinalVersion }),
      });
      await loadProjects();
      return;
    }
    if (target.dataset.projectExtractVersion) {
      await api("/api/assets/extract/from-project-version", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: project.project_id,
          version_id: target.dataset.projectExtractVersion,
          asset_types: [target.dataset.assetType || "motif"],
          section_name: "chorus",
          tags: ["studio"],
          favorite: true,
        }),
      });
      await loadAssets();
    }
  });
}

async function renderProjectTab(project, versions) {
  const target = $("project-tab-content");
  if (activeProjectTab === "versions") {
    target.innerHTML = projectVersionsTable(project, versions);
  } else if (activeProjectTab === "variation") {
    target.innerHTML = projectVariationControls(project, versions);
    renderAssetSelectors();
    renderContextPackSelectors();
    bindAction("project-create-variation", async () => {
      const parentId = $("project-variation-parent").value;
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parentId)}/variation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(projectVariationPayload()),
      });
      projectVariationParentId = null;
      activeProjectTab = "versions";
      await loadJobs();
      await loadProjects();
    });
  } else if (activeProjectTab === "edit") {
    await renderProjectEdit(project, versions, target);
  } else if (activeProjectTab === "editor") {
    await renderProjectEditor(project, versions, target);
  } else if (activeProjectTab === "mix-board") {
    await renderProjectMixBoard(project, versions, target);
  } else if (activeProjectTab === "review-workbench") {
    await renderProjectReviewWorkbench(project, versions, target);
  } else if (activeProjectTab === "review-sprints") {
    await renderProjectReviewSprints(project, versions, target);
  } else if (activeProjectTab === "candidates") {
    await renderProjectCandidates(project, versions, target);
  } else if (activeProjectTab === "quality-gate") {
    await renderProjectQualityGate(project, versions, target);
  } else if (activeProjectTab === "final-export") {
    await renderProjectFinalExport(project, versions, target);
  } else if (activeProjectTab === "references") {
    await renderProjectReferences(project, target);
  } else if (activeProjectTab === "compare") {
    target.innerHTML = projectCompareControls(versions);
    bindAction("project-compare", async () => {
      const left = $("project-diff-left").value;
      const right = $("project-diff-right").value;
      const compare = await api(`/api/projects/${encodeURIComponent(project.project_id)}/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`);
      $("project-diff-result").innerHTML = projectCompareResultHtml(compare);
    });
  } else if (activeProjectTab === "export") {
    try {
      const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/export`);
      target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
    } catch (err) {
      target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
    }
  } else if (activeProjectTab === "events") {
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/events`);
    target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.events, null, 2))}</pre>`;
  }
}

async function renderProjectMixBoard(project, versions, target) {
  const versionId = (project.selected_version_id || project.final_version_id || (versions[versions.length - 1] || {}).version_id || "").trim();
  let stateData = {};
  let stemHealth = {};
  if (versionId) {
    try { stateData = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(versionId)}/mix-state`); } catch (err) { stateData = { error: err.message }; }
    try { stemHealth = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(versionId)}/mix-stems/health`); } catch (err) { stemHealth = { summary: { status: "missing" } }; }
  }
  const state = stateData.mix_state || {};
  const tracks = state.tracks || [];
  const selectedOptions = versions.map((version) => `<option value="${escapeHtml(version.version_id)}" ${version.version_id === versionId ? "selected" : ""}>${escapeHtml(version.version_id)} · ${escapeHtml(version.name || version.job_id)}</option>`).join("");
  target.innerHTML = `
    <div class="panel-title subhead"><span>Mix Board</span></div>
    <div class="summary-grid">
      ${metric("Version", versionId || "-")}
      ${metric("Mix State", stateData.summary ? "ready" : (stateData.error || "missing"))}
      ${metric("Stem Health", (stemHealth.summary || {}).status || "missing")}
      ${metric("Tracks", tracks.length || 0)}
    </div>
    <div class="grid2">
      <label>Version
        <select id="mix-board-version">${selectedOptions}</select>
      </label>
      <label>Patch Label
        <input id="mix-patch-label" value="Mix Board preview">
      </label>
    </div>
    <div class="grid2">
      <label>Track
        <select id="mix-track-id">${tracks.map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.track_id)} · ${escapeHtml(track.name)}</option>`).join("")}</select>
      </label>
      <label>Volume dB
        <input id="mix-track-volume" type="number" min="-36" max="12" step="0.5" value="-2">
      </label>
    </div>
    <div class="grid2">
      <label>Pan
        <input id="mix-track-pan" type="number" min="-100" max="100" step="1" value="0">
      </label>
      <label>Velocity Scale
        <input id="mix-track-velocity" type="number" min="0" max="2" step="0.05" value="1">
      </label>
    </div>
    <div class="actions">
      <label class="inline"><input id="mix-track-mute" type="checkbox"> Mute</label>
      <label class="inline"><input id="mix-track-solo" type="checkbox"> Solo</label>
      <button class="secondary" id="mix-preview-create" type="button">Create Preview</button>
      <button class="secondary" id="mix-stems-render" type="button">Render Stems</button>
      <button class="secondary" id="mix-state-reset" type="button">Reset Mix State</button>
    </div>
    <pre id="mix-board-result">${escapeHtml(JSON.stringify({ mix_state: state, stem_health: stemHealth.summary || {} }, null, 2))}</pre>
  `;
  $("mix-board-version")?.addEventListener("change", async () => {
    await renderProjectMixBoard(project, versions, target);
  });
  bindAction("mix-preview-create", async () => {
    const selectedVersion = $("mix-board-version").value;
    const operations = [
      { op: "set_track_volume", track_id: $("mix-track-id").value, volume_db: Number($("mix-track-volume").value || 0) },
      { op: "set_track_pan", track_id: $("mix-track-id").value, pan: Number($("mix-track-pan").value || 0) },
      { op: "set_track_velocity_scale", track_id: $("mix-track-id").value, velocity_scale: Number($("mix-track-velocity").value || 1) },
    ];
    if ($("mix-track-mute").checked) operations.push({ op: "set_track_mute", track_id: $("mix-track-id").value, mute: true });
    if ($("mix-track-solo").checked) operations.push({ op: "set_track_solo", track_id: $("mix-track-id").value, solo: true });
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(selectedVersion)}/mix-preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: $("mix-patch-label").value.trim(), operations }),
    });
    $("mix-board-result").textContent = JSON.stringify(data, null, 2);
  });
  bindAction("mix-stems-render", async () => {
    const selectedVersion = $("mix-board-version").value;
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(selectedVersion)}/mix-stems/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ require_wav: false }),
    });
    $("mix-board-result").textContent = JSON.stringify(data.summary || data, null, 2);
  });
  bindAction("mix-state-reset", async () => {
    const selectedVersion = $("mix-board-version").value;
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(selectedVersion)}/mix-state/reset`, { method: "POST" });
    $("mix-board-result").textContent = JSON.stringify(data.mix_state || data, null, 2);
  });
}

function projectVersionsTable(project, versions) {
  const rows = versions.map((version) => `
    <tr>
      <td>${escapeHtml(version.version_id)}${project.selected_version_id === version.version_id ? " selected" : ""}${project.final_version_id === version.version_id ? " final" : ""}</td>
      <td>${escapeHtml(version.name || "-")}</td>
      <td><button class="secondary" data-project-job-id="${escapeHtml(version.job_id)}" type="button">${escapeHtml(version.job_id)}</button></td>
      <td><span class="status ${version.status}">${escapeHtml(version.status)}</span></td>
      <td>${escapeHtml(version.quality_score ?? "-")}</td>
      <td>${escapeHtml(version.parent_version_id || "-")}</td>
      <td>${escapeHtml(version.variant_type || "original")}</td>
      <td><span class="status ${version.quality_gate_status || "not_evaluated"}">${escapeHtml(version.quality_gate_status || "not_evaluated")}</span> ${escapeHtml(version.quality_gate_score ?? "")}</td>
      <td>${version.final_export_path ? "yes" : "-"}</td>
      <td>${escapeHtml(version.request.tempo_bpm || "-")}</td>
      <td>${escapeHtml(version.request.key || "-")}</td>
      <td>${version.has_midi ? "yes" : "-"}</td>
      <td>${version.has_audio ? "yes" : "-"}</td>
      <td>${version.has_stems ? "yes" : "-"}</td>
      <td>${version.has_stem_audio ? "yes" : "-"}</td>
      <td>${escapeHtml(version.note || "-")}</td>
      <td>
        <div class="actions">
          <button class="secondary" data-project-select-version="${escapeHtml(version.version_id)}" type="button">Set Selected</button>
          <button class="secondary" data-project-final-version="${escapeHtml(version.version_id)}" type="button">Set Final</button>
          <button class="secondary" data-project-variation-version="${escapeHtml(version.version_id)}" type="button">Create Variation</button>
          <button class="secondary" data-project-edit-version="${escapeHtml(version.version_id)}" type="button">Edit Version</button>
          <button class="secondary" data-project-editor-version="${escapeHtml(version.version_id)}" type="button">Open Editor</button>
          <button class="secondary" data-project-evaluate-version="${escapeHtml(version.version_id)}" type="button">Evaluate Gate</button>
          <button class="secondary" data-project-export-version="${escapeHtml(version.version_id)}" type="button">Export Final</button>
          <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="motif" type="button">Save Motif</button>
          <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="chord_progression" type="button">Save Chords</button>
          <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="drum_pattern" type="button">Save Drums</button>
          <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="bass_pattern" type="button">Save Bass</button>
        </div>
      </td>
    </tr>
  `).join("");
  return `
    <table>
      <thead><tr><th>Version</th><th>Name</th><th>Job</th><th>Status</th><th>Quality</th><th>Parent</th><th>Variant Type</th><th>Gate</th><th>Final Export</th><th>Tempo</th><th>Key</th><th>MIDI</th><th>WAV</th><th>Stems</th><th>Stem WAV</th><th>Note</th><th>Actions</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='17'>No versions yet.</td></tr>"}</tbody>
    </table>
  `;
}

function projectVariationControls(project, versions) {
  const parentId = projectVariationParentId || project.selected_version_id || project.final_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
  const parent = versions.find((version) => version.version_id === parentId) || versions[0] || null;
  const options = projectVersionOptions(versions, parentId);
  return `
    <div class="grid2">
      <label>Parent Version
        <select id="project-variation-parent">${options}</select>
      </label>
      <label>Variant Type
        <select id="project-variation-type">
          <option value="style_variation">style_variation</option>
          <option value="tempo_key_variation">tempo_key_variation</option>
          <option value="lyrics_variation">lyrics_variation</option>
          <option value="arrangement_variation">arrangement_variation</option>
          <option value="quality_repair">quality_repair</option>
          <option value="manual">manual</option>
        </select>
      </label>
    </div>
    <div class="grid2">
      <label>Name
        <input id="project-variation-name" value="Variation ${(versions.length || 0) + 1}">
      </label>
      <label>Change Summary
        <input id="project-variation-summary" placeholder="short change summary">
      </label>
    </div>
    <div class="grid2">
      <label>Generation Mode
        <select id="project-variation-generation-mode">
          <option value="">inherit</option>
          <option value="local">local</option>
          <option value="provider">provider</option>
        </select>
      </label>
      <label>Pipeline Mode
        <select id="project-variation-pipeline-mode">
          <option value="">inherit</option>
          <option value="single">single</option>
          <option value="multinode">multinode</option>
        </select>
      </label>
    </div>
    <div class="grid2">
      <label>Style Patch
        <textarea id="project-variation-style"></textarea>
      </label>
      <label>Theme Patch
        <textarea id="project-variation-theme"></textarea>
      </label>
    </div>
    <div class="grid2">
      <label>Tempo BPM
        <input id="project-variation-tempo" type="number" min="40" max="240">
      </label>
      <label>Key
        <input id="project-variation-key">
      </label>
    </div>
    <div class="grid2">
      <label>Duration Seconds
        <input id="project-variation-duration" type="number" min="30" max="600">
      </label>
      <label>Lyrics Patch
        <textarea id="project-variation-lyrics"></textarea>
      </label>
    </div>
    <label>Asset References
      <div id="project-variation-asset-refs" class="asset-ref-list"></div>
    </label>
    <label>Reference Materials
      <div id="project-variation-reference-refs" class="reference-ref-list"></div>
    </label>
    <label>Context Pack
      <select id="project-variation-context-pack" class="context-pack-select"><option value="">none</option></select>
    </label>
    <div class="actions">
      <button id="project-create-variation" type="button" ${parent ? "" : "disabled"}>Create Variation</button>
      <span id="project-variation-message" class="message"></span>
    </div>
    <pre>${escapeHtml(JSON.stringify(parent ? parent.request : {}, null, 2))}</pre>
  `;
}

function projectVariationPayload() {
  const requestPatch = {};
  const textFields = [
    ["style", "project-variation-style"],
    ["theme", "project-variation-theme"],
    ["key", "project-variation-key"],
    ["lyrics", "project-variation-lyrics"],
  ];
  textFields.forEach(([field, id]) => {
    const value = $(id).value;
    if (value.trim()) requestPatch[field] = field === "lyrics" ? value : value.trim();
  });
  if ($("project-variation-tempo").value) requestPatch.tempo_bpm = Number($("project-variation-tempo").value);
  if ($("project-variation-duration").value) requestPatch.duration_seconds = Number($("project-variation-duration").value);
  const payload = {
    variant_type: $("project-variation-type").value,
    name: $("project-variation-name").value.trim(),
    change_summary: $("project-variation-summary").value.trim(),
    request_patch: requestPatch,
  };
  const refs = assetRefsPayload("project-variation-asset-refs");
  if (refs.length) payload.asset_refs = refs;
  const referenceRefs = referenceRefsPayload("project-variation-reference-refs");
  if (referenceRefs.length) payload.reference_refs = referenceRefs;
  const contextPackId = contextPackIdPayload("project-variation-context-pack");
  if (contextPackId) payload.context_pack_id = contextPackId;
  if ($("project-variation-generation-mode").value) payload.generation_mode = $("project-variation-generation-mode").value;
  if ($("project-variation-pipeline-mode").value) payload.pipeline_mode = $("project-variation-pipeline-mode").value;
  return payload;
}

async function renderProjectEditor(project, versions, target) {
  const parentId = projectEditorParentId || project.selected_version_id || project.final_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
  target.innerHTML = projectEditorShell(versions, parentId);
  const parentSelect = $("project-editor-parent");
  if (parentSelect) {
    parentSelect.addEventListener("change", async () => {
      projectEditorParentId = parentSelect.value;
      projectEditorState = null;
      projectEditorView = null;
      projectEditorPatch = [];
      projectEditorRedo = [];
      projectEditorDraft = null;
      projectEditorClips = null;
      projectEditorClipInsertMap = {};
      projectEditorTemplateInsertMap = {};
      projectEditorTemplateMapping = null;
      projectEditorSelectedClipIndex = 0;
      projectEditorSelectedTemplateIndex = 0;
      projectEditorPreview = null;
      projectEditorAuditions = [];
      await renderProjectEditor(project, versions, target);
    });
  }
  bindAction("project-editor-load-history", async () => {
    await loadProjectEditorPreviewHistory(project.project_id);
  });
  bindAction("project-editor-cleanup-history", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/editor-previews/cleanup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delete_unapplied_older_than_days: 7, keep_latest: 20 }),
    });
    await loadProjectEditorPreviewHistory(project.project_id);
  });
  bindAction("project-editor-load", async () => {
    await loadProjectEditorState(project.project_id, $("project-editor-parent").value);
  });
  bindAction("project-editor-clear", () => {
    projectEditorPatch = [];
    projectEditorRedo = [];
    projectEditorDraft = null;
    projectEditorClips = null;
    projectEditorClipInsertMap = {};
    projectEditorTemplateInsertMap = {};
    projectEditorTemplateMapping = null;
    projectEditorSelectedClipIndex = 0;
    projectEditorSelectedTemplateIndex = 0;
    projectEditorPreview = null;
    projectEditorAuditions = [];
    renderProjectEditorDraft();
    renderProjectEditorState();
  });
  bindAction("project-editor-undo", () => {
    const op = projectEditorPatch.pop();
    if (op) projectEditorRedo.push(op);
    projectEditorPreview = null;
    renderProjectEditorDraft();
  });
  bindAction("project-editor-redo", () => {
    const op = projectEditorRedo.pop();
    if (op) projectEditorPatch.push(op);
    projectEditorPreview = null;
    renderProjectEditorDraft();
  });
  bindAction("project-editor-draft-refresh", async () => {
    await refreshProjectEditorDraft(project.project_id, $("project-editor-parent").value);
  });
  bindAction("project-editor-preview", async () => {
    if (!projectEditorState) await loadProjectEditorState(project.project_id, $("project-editor-parent").value);
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent($("project-editor-parent").value)}/editor-preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patch: {
          schema_version: 1,
          base_plan_hash: projectEditorState.base_plan_hash,
          label: $("project-editor-label").value.trim(),
          operations: projectEditorPatch,
          metadata: projectEditorPatchMetadata(),
        },
        render_midi: true,
      }),
    });
    projectEditorPreview = data.preview;
    renderProjectEditorPreview();
  });
  bindAction("project-editor-apply", async () => {
    if (!projectEditorPreview) return;
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        version_name: $("project-editor-version-name").value.trim(),
        version_note: $("project-editor-version-note").value.trim(),
        change_summary: $("project-editor-label").value.trim(),
      }),
    });
    projectEditorParentId = null;
    projectEditorState = null;
    projectEditorView = null;
    projectEditorPatch = [];
    projectEditorRedo = [];
    projectEditorDraft = null;
    projectEditorClips = null;
    projectEditorClipInsertMap = {};
    projectEditorTemplateInsertMap = {};
    projectEditorTemplateMapping = null;
    projectEditorSelectedClipIndex = 0;
    projectEditorSelectedTemplateIndex = 0;
    projectEditorPreview = null;
    projectEditorAuditions = [];
    activeProjectTab = "versions";
    await loadJobs();
    await loadProjects();
  });
  if (parentId) await loadProjectEditorState(project.project_id, parentId);
  await loadProjectEditorPreviewHistory(project.project_id);
}

function projectEditorShell(versions, parentId) {
  return `
    <div class="grid2">
      <label>Parent Version
        <select id="project-editor-parent">${projectVersionOptions(versions, parentId)}</select>
      </label>
      <label>Patch Label
        <input id="project-editor-label" value="Manual editor patch">
      </label>
    </div>
    <div class="grid2">
      <label>New Version Name
        <input id="project-editor-version-name" value="Editor Version ${(versions.length || 0) + 1}">
      </label>
      <label>Version Note
        <input id="project-editor-version-note" placeholder="manual visual editor patch">
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="project-editor-load" type="button" ${parentId ? "" : "disabled"}>Open</button>
      <button class="secondary" id="project-editor-draft-refresh" type="button" disabled>Draft Refresh</button>
      <button class="secondary" id="project-editor-undo" type="button" disabled>Undo</button>
      <button class="secondary" id="project-editor-redo" type="button" disabled>Redo</button>
      <button class="secondary" id="project-editor-clear" type="button">Clear Patch</button>
      <button id="project-editor-preview" type="button" disabled>Preview</button>
      <button id="project-editor-apply" type="button" disabled>Apply as Version</button>
      <button class="secondary" id="project-editor-load-history" type="button">Preview History</button>
      <button class="secondary" id="project-editor-cleanup-history" type="button">Cleanup Previews</button>
      <span id="project-editor-message" class="message"></span>
    </div>
    <div id="project-editor-state"><div class="empty">Select a version to open the editor.</div></div>
    <div id="project-editor-preview-result"><div class="empty">Preview result will appear here.</div></div>
    <div id="project-editor-history"><div class="empty">Preview history will appear here.</div></div>
  `;
}

async function loadProjectEditorState(projectId, versionId) {
  if (!versionId) return;
  projectEditorState = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-state`);
  const viewData = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-view`);
  projectEditorClips = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-clips`);
  projectEditorView = viewData.view;
  projectEditorPatch = [];
  projectEditorRedo = [];
  projectEditorDraft = null;
  projectEditorPreview = null;
  projectEditorClipInsertMap = {};
  projectEditorTemplateInsertMap = {};
  projectEditorTemplateMapping = null;
  projectEditorSelectedClipIndex = 0;
  projectEditorSelectedTemplateIndex = 0;
  projectEditorSelectedSectionId = (projectEditorState.sections[0] || {}).section_id || null;
  projectEditorSelectedTrackId = (projectEditorState.tracks[0] || {}).track_id || null;
  projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
  projectEditorAuditions = [];
  renderProjectEditorState();
  renderProjectEditorDraft();
}

Object.assign(globalThis, { assetContentSummary, renderProjects, renderProjectDetail, projectActionButtons, wireProjectActions, renderProjectTab, renderProjectMixBoard, projectVersionsTable, projectVariationControls, projectVariationPayload, renderProjectEditor, projectEditorShell, loadProjectEditorState });

export { assetContentSummary, renderProjects, renderProjectDetail, projectActionButtons, wireProjectActions, renderProjectTab, renderProjectMixBoard, projectVersionsTable, projectVariationControls, projectVariationPayload, renderProjectEditor, projectEditorShell, loadProjectEditorState };
