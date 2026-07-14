function bindProjectEditorAuditionControls() {
  bindAction("project-editor-refresh-auditions", async () => {
    await loadProjectEditorAuditions();
    renderProjectEditorPreview();
  });
  bindAction("project-editor-filter-favorites", async () => {
    await loadProjectEditorAuditions({ favorite: true, sort: "rating" });
    renderProjectEditorPreview();
  });
  bindAction("project-editor-create-audition", async () => {
    const rangeMode = $("project-editor-audition-range").value;
    const range = { mode: rangeMode };
    if (rangeMode === "section") range.section_id = projectEditorSelectedSectionId;
    if (rangeMode === "custom") {
      range.start_beat = Number($("project-editor-audition-start").value || 0);
      range.end_beat = Number($("project-editor-audition-end").value || 0);
    }
    const trackMode = $("project-editor-audition-track-mode").value;
    const trackIds = trackMode === "all" ? [] : [$("project-editor-audition-track").value];
    const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: $("project-editor-audition-source").value,
        range,
        track_mode: trackMode,
        track_ids: trackIds,
      }),
    });
    projectEditorAuditions = [data.audition, ...projectEditorAuditions.filter((item) => item.audition_id !== data.audition.audition_id)];
    renderProjectEditorPreview();
  });
  document.querySelectorAll("[data-editor-audition-render]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(button.dataset.editorAuditionRender)}/render-audio`, { method: "POST" });
      await loadProjectEditorAuditions();
      renderProjectEditorPreview();
    });
  });
  document.querySelectorAll("[data-editor-audition-review]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionReview;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating: Number((document.querySelector(`[data-editor-audition-rating="${CSS.escape(id)}"]`) || {}).value || 0),
          status: (document.querySelector(`[data-editor-audition-status="${CSS.escape(id)}"]`) || {}).value || "unreviewed",
          favorite: Boolean((document.querySelector(`[data-editor-audition-favorite="${CSS.escape(id)}"]`) || {}).checked),
          notes: (document.querySelector(`[data-editor-audition-notes="${CSS.escape(id)}"]`) || {}).value || "",
          tags: ((document.querySelector(`[data-editor-audition-tags="${CSS.escape(id)}"]`) || {}).value || "").split(",").map((item) => item.trim()).filter(Boolean),
        }),
      });
      projectEditorAuditions = projectEditorAuditions.map((item) => item.audition_id === id ? data.audition : item);
      renderProjectEditorPreview();
    });
  });
  document.querySelectorAll("[data-editor-audition-marker-add]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionMarkerAdd;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/markers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          beat: Number((document.querySelector(`[data-editor-audition-marker-beat="${CSS.escape(id)}"]`) || {}).value || 0),
          kind: (document.querySelector(`[data-editor-audition-marker-kind="${CSS.escape(id)}"]`) || {}).value || "note",
          label: (document.querySelector(`[data-editor-audition-marker-label="${CSS.escape(id)}"]`) || {}).value || "",
        }),
      });
      projectEditorAuditions = projectEditorAuditions.map((item) => item.audition_id === id ? data.audition : item);
      renderProjectEditorPreview();
    });
  });
  document.querySelectorAll("[data-editor-audition-create-asset]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionCreateAsset;
      await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/create-asset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_type: "motif", name: `${id} motif`, tags: ["audition"] }),
      });
      await loadAssets();
      await loadProjectEditorAuditions();
      renderProjectEditorPreview();
    });
  });
  document.querySelectorAll("[data-editor-audition-preview-edit]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionPreviewEdit;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review-edit-preview`, { method: "POST" });
      const result = $("project-editor-review-edit-result");
      if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ review_edit: data.review_edit, summary: data.summary, validator: data.validator }, null, 2))}</pre>`;
    });
  });
  document.querySelectorAll("[data-editor-audition-create-edit]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionCreateEdit;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review-edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version_name: `${id} Review Edit`, version_note: "Created from audition review" }),
      });
      const result = $("project-editor-review-edit-result");
      if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ version: data.version, job: data.job, review_edit: data.review_edit }, null, 2))}</pre>`;
      await loadProjects();
    });
  });
  document.querySelectorAll("[data-editor-audition-provider-preview]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionProviderPreview;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/provider-review-edit-preview`, { method: "POST" });
      providerEditPreview = data.preview;
      const result = $("project-editor-review-edit-result");
      if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ preview: data.preview, patch: data.patch, review_edit: data.review_edit }, null, 2))}</pre>`;
    });
  });
  document.querySelectorAll("[data-editor-audition-create-review-task]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionCreateReviewTask;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review-task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const result = $("project-editor-review-edit-result");
      if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ task: data.task }, null, 2))}</pre>`;
      activeProjectTab = "review-workbench";
      await loadProjects();
    });
  });
  document.querySelectorAll("[data-editor-audition-create-context]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.editorAuditionCreateContext;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/create-context-pack`, { method: "POST" });
      await loadContextPacks();
      const result = $("project-editor-review-edit-result");
      if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ context_pack: data.context_pack }, null, 2))}</pre>`;
    });
  });
  document.querySelectorAll("[data-editor-audition-delete]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(button.dataset.editorAuditionDelete)}/delete`, { method: "POST" });
      projectEditorAuditions = projectEditorAuditions.filter((item) => item.audition_id !== button.dataset.editorAuditionDelete);
      renderProjectEditorPreview();
    });
  });
}

async function loadProjectEditorAuditions(filters = {}) {
  if (!projectEditorPreview || !projectEditorState) return;
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => params.set(key, value));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/audition-reviews${suffix}`);
  projectEditorAuditions = data.auditions || [];
}

async function refreshProjectEditorDraft(projectId, versionId) {
  if (!projectEditorState || !projectEditorPatch.length) return;
  const data = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_view: true,
      include_diff: true,
      patch: {
        schema_version: 1,
        base_plan_hash: projectEditorState.base_plan_hash,
        label: $("project-editor-label").value.trim(),
        operations: projectEditorPatch,
        metadata: projectEditorPatchMetadata(),
      },
    }),
  });
  projectEditorDraft = data;
  projectEditorView = data.view;
  const track = projectEditorViewTrackWithNotes(projectEditorSelectedTrackId);
  if (!track || !(track.notes || []).some((note) => note.note_id === projectEditorSelectedNoteId)) {
    projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
  }
  renderProjectEditorState();
  const result = $("project-editor-preview-result");
  if (result) {
    result.innerHTML = `
      <div class="summary-grid">
        ${metric("Draft Ops", data.operation_count)}
        ${metric("Sections", (data.summary.changed_sections || []).join(", ") || "-")}
        ${metric("Tracks", (data.summary.changed_tracks || []).join(", ") || "-")}
        ${metric("Validator", (data.validator || {}).status || "-")}
      </div>
      <pre>${escapeHtml(JSON.stringify({ summary: data.summary, diff: data.diff }, null, 2))}</pre>
    `;
  }
}

function currentProjectEditorView() {
  return projectEditorView || {
    song: { ...(projectEditorState.song || {}), total_beats: (projectEditorState.song.total_bars || 1) * (projectEditorState.song.beats_per_bar || 4) },
    sections: projectEditorState.sections || [],
    tracks: (projectEditorState.tracks || []).map((track) => {
      const copy = { ...track };
      delete copy.notes;
      return copy;
    }),
    lanes: (projectEditorState.tracks || []).map((track) => ({ track_id: track.track_id, notes: track.notes || [] })),
    pitch_range: { min: 36, max: 84 },
  };
}

function projectEditorViewTrackWithNotes(trackId) {
  const view = currentProjectEditorView();
  const track = (view.tracks || []).find((item) => item.track_id === trackId) || (view.tracks || [])[0] || null;
  if (!track) return null;
  const lane = (view.lanes || []).find((item) => item.track_id === track.track_id) || { notes: [] };
  return { ...track, notes: lane.notes || [] };
}

function firstProjectEditorNoteId(trackId) {
  const track = projectEditorViewTrackWithNotes(trackId);
  return ((track && track.notes) || [])[0]?.note_id || null;
}

function fillSelectedProjectEditorNotePatch() {
  const input = $("project-editor-note-patch");
  if (!input) return;
  const track = projectEditorViewTrackWithNotes(projectEditorSelectedTrackId);
  const note = ((track && track.notes) || []).find((item) => item.note_id === projectEditorSelectedNoteId);
  if (note) {
    input.value = JSON.stringify({ pitch: note.pitch, start_beat: note.start_beat, duration_beats: note.duration_beats, velocity: note.velocity });
  }
}

function projectEditorBarRuler(view) {
  const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
  const beatsPerBar = Math.max(1, Number((view.song || {}).beats_per_bar || 4));
  const totalBars = Math.max(1, Number((view.song || {}).total_bars || Math.ceil(totalBeats / beatsPerBar)));
  return `<div class="bar-ruler">${Array.from({ length: totalBars }, (_, index) => {
    const left = (index * beatsPerBar / totalBeats) * 100;
    return `<span class="bar-tick" style="left:${left}%">${index + 1}</span>`;
  }).join("")}</div>`;
}

function projectEditorSectionBlocks(view) {
  const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
  return (view.sections || []).map((section) => {
    const left = (Number(section.start_beat || 0) / totalBeats) * 100;
    const width = Math.max(2, ((Number(section.end_beat || 0) - Number(section.start_beat || 0)) / totalBeats) * 100);
    const selected = section.section_id === projectEditorSelectedSectionId ? " selected" : "";
    return `<button class="project-editor-section-block${selected}" data-editor-section-id="${escapeHtml(section.section_id)}" style="left:${left}%;width:${width}%;" type="button">${escapeHtml(section.name)} · ${escapeHtml(section.bars)} bars</button>`;
  }).join("");
}

function projectEditorTrackOverview(view) {
  const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
  return (view.tracks || []).map((track) => {
    const lane = (view.lanes || []).find((item) => item.track_id === track.track_id) || { notes: [] };
    const notes = (lane.notes || []).slice(0, 180).map((note) => {
      const left = (Number(note.start_beat || 0) / totalBeats) * 100;
      const width = Math.max(0.6, (Number(note.duration_beats || 0.25) / totalBeats) * 100);
      return `<span class="lane-note" style="left:${left}%;width:${width}%"></span>`;
    }).join("");
    return `<div class="track-lane"><button class="secondary" data-editor-track-id="${escapeHtml(track.track_id)}" type="button">${escapeHtml(track.name)}</button><div class="lane-notes">${notes}</div></div>`;
  }).join("");
}

function projectEditorTrackButtons(view) {
  return (view.tracks || []).map((track) => {
    const active = track.track_id === projectEditorSelectedTrackId ? " active" : "";
    return `<button class="${active}" data-editor-track-id="${escapeHtml(track.track_id)}" type="button">${escapeHtml(track.name)} · ${escapeHtml(track.note_count || 0)}</button>`;
  }).join("") || "<div class='empty'>No tracks.</div>";
}

function projectEditorPianoRoll(view) {
  const track = projectEditorViewTrackWithNotes(projectEditorSelectedTrackId);
  if (!track) return "<div class='empty'>Select a track.</div>";
  const notes = track.notes || [];
  const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
  const pitchMin = Math.max(0, Number((view.pitch_range || {}).min ?? 36));
  const pitchMax = Math.min(127, Number((view.pitch_range || {}).max ?? 84));
  const pitchSpan = Math.max(1, pitchMax - pitchMin + 1);
  const labels = [];
  for (let pitch = pitchMax; pitch >= pitchMin; pitch -= 12) {
    const top = ((pitchMax - pitch) / pitchSpan) * 100;
    labels.push(`<span class="pitch-label" style="top:${top}%">${pitch}</span>`);
  }
  const rects = notes.slice(0, 1200).map((note) => {
    const left = Math.max(0, (Number(note.start_beat || 0) / totalBeats) * 100);
    const width = Math.max(0.8, (Number(note.duration_beats || 0.25) / totalBeats) * 100);
    const top = Math.max(0, Math.min(96, ((pitchMax - Number(note.pitch || pitchMin)) / pitchSpan) * 100));
    const selected = note.note_id === projectEditorSelectedNoteId ? " selected" : "";
    const derived = isDerivedNote(note.note_id) ? " derived" : "";
    return `<button class="project-editor-note-rect${selected}${derived}" data-editor-track-id="${escapeHtml(track.track_id)}" data-editor-note-id="${escapeHtml(note.note_id)}" style="left:${left}%;top:${top}%;width:${width}%;" type="button">${escapeHtml(note.pitch)}</button>`;
  }).join("");
  return `<div class="piano-grid">${labels.join("")}${rects || "<div class='empty'>No notes in this track.</div>"}</div>`;
}

function describeProjectEditorOperation(operation) {
  const op = operation.op || "operation";
  if (operation.template_group_id) return `template ${operation.template_group_id}: ${op} ${operation.track_id || operation.section_id || ""}`.trim();
  if (operation.clip_group_id) return `clip ${operation.clip_group_id}: ${op} ${operation.track_id || operation.section_id || ""}`.trim();
  if (op === "add_section") return `add_section: ${operation.name || "section"} after ${operation.after_section_id || "end"}`;
  if (op === "duplicate_section") return `duplicate_section: ${operation.section_id || "section"} -> ${operation.name || "copy"}`;
  if (op === "delete_section") return `delete_section: ${operation.section_id || "section"}`;
  if (op === "resize_section") return `resize_section: ${operation.section_id || "section"} -> ${operation.bars || "?"} bars`;
  if (op === "move_section") return `move_section: ${operation.section_id || "section"} after ${operation.after_section_id || "start"}`;
  if (op === "add_track") return `add_track: ${operation.name || "track"}`;
  if (op === "duplicate_track") return `duplicate_track: ${operation.track_id || "track"} -> ${operation.name || "copy"}`;
  if (op === "delete_track") return `delete_track: ${operation.track_id || "track"}`;
  if (op === "rename_track") return `rename_track: ${operation.track_id || "track"} -> ${operation.name || "track"}`;
  return `${op}: ${operation.section_id || operation.track_id || ""}`.trim();
}

async function renderProjectEdit(project, versions, target) {
  const parentId = projectEditParentId || project.selected_version_id || project.final_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
  let targets = { sections: [], tracks: [], supported_edit_types: [] };
  let preview = "";
  if (parentId) {
    try {
      targets = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parentId)}/edit-targets`);
      preview = JSON.stringify(targets, null, 2);
    } catch (err) {
      preview = err.message;
    }
  }
  target.innerHTML = projectEditControls(project, versions, parentId, targets, preview);
  renderAssetSelectors();
  renderReferenceSelectors();
  renderContextPackSelectors();
  const parentSelect = $("project-edit-parent");
  if (parentSelect) {
    parentSelect.addEventListener("change", async () => {
      projectEditParentId = parentSelect.value;
      await renderProjectEdit(project, versions, target);
    });
  }
  bindAction("project-create-edit", async () => {
    const parent = $("project-edit-parent").value;
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectEditPayload()),
    });
    projectEditParentId = null;
    activeProjectTab = "versions";
    await loadJobs();
    await loadProjects();
  });
  bindAction("project-provider-preview", async () => {
    const parent = $("project-edit-parent").value;
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit-preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectProviderPreviewPayload()),
    });
    providerEditPreview = data.preview;
    $("project-provider-preview-result").innerHTML = providerPreviewHtml(data.preview, data.patch);
  });
  bindAction("project-provider-apply-preview", async () => {
    if (!providerEditPreview) return;
    const parent = $("project-edit-parent").value;
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit-preview/${encodeURIComponent(providerEditPreview.preview_id)}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("project-edit-name").value.trim(),
        change_summary: $("project-edit-summary").value.trim(),
      }),
    });
    providerEditPreview = null;
    activeProjectTab = "versions";
    await loadJobs();
    await loadProjects();
  });
  bindAction("project-apply-preset", async () => {
    applyEditPresetToForm();
  });
  bindAction("project-save-edit-preset", async () => {
    const presetId = slugifyClient($("project-edit-preset-id").value || $("project-edit-name").value || "custom-edit");
    await api("/api/edit-presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectEditPresetPayload(presetId)),
    });
    await loadEditPresets();
    await renderProjectEdit(project, versions, target);
  });
}

function projectEditControls(project, versions, parentId, targets, preview) {
  const sectionOptions = (targets.sections || []).map((section) => `<option value="${escapeHtml(section.name)}">${escapeHtml(section.name)} · ${escapeHtml(section.bars)} bars</option>`).join("");
  const trackOptions = (targets.tracks || []).map((track) => `<option value="${escapeHtml(track.name)}">${escapeHtml(track.name)} · ${escapeHtml(track.instrument)} · ${escapeHtml(track.note_count)} notes</option>`).join("");
  const editTypeOptions = (targets.supported_edit_types || ["section_energy", "section_harmony", "track_density", "lyrics_rewrite", "melody_variation", "arrangement_variation"]).map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`).join("");
  const presetOptions = editPresets.map((preset) => `<option value="${escapeHtml(preset.preset_id)}">${escapeHtml(preset.name)}${preset.built_in ? " · built-in" : ""}</option>`).join("");
  return `
    <div class="grid2">
      <label>Edit Preset
        <select id="project-edit-preset"><option value="">none</option>${presetOptions}</select>
      </label>
      <label>Preset ID
        <input id="project-edit-preset-id" placeholder="custom-edit-preset">
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="project-apply-preset" type="button">Apply Preset</button>
      <button class="secondary" id="project-save-edit-preset" type="button">Save Current As Preset</button>
      <span id="project-preset-message" class="message"></span>
    </div>
    <div class="grid2">
      <label>Parent Version
        <select id="project-edit-parent">${projectVersionOptions(versions, parentId)}</select>
      </label>
      <label>Edit Type
        <select id="project-edit-type">${editTypeOptions}</select>
      </label>
    </div>
    <div class="grid2">
      <label>Section
        <select id="project-edit-section"><option value="">none</option>${sectionOptions}</select>
      </label>
      <label>Track
        <select id="project-edit-track"><option value="">none</option>${trackOptions}</select>
      </label>
    </div>
    <div class="grid2">
      <label>Field
        <select id="project-edit-field">
          <option value="">none</option>
          <option value="lyrics">lyrics</option>
          <option value="chords">chords</option>
          <option value="notes">notes</option>
          <option value="instrument">instrument</option>
        </select>
      </label>
      <label>Strength
        <input id="project-edit-strength" type="number" min="1" max="10" value="6">
      </label>
    </div>
    <div class="grid2">
      <label>Name
        <input id="project-edit-name" value="Edit ${(versions.length || 0) + 1}">
      </label>
      <label>Change Summary
        <input id="project-edit-summary" placeholder="short edit summary">
      </label>
    </div>
    <label>Instruction
      <textarea id="project-edit-instruction" placeholder="Make the chorus more energetic while keeping tempo and key."></textarea>
    </label>
    <div class="grid2">
      <label>Payload Lyrics
        <textarea id="project-edit-lyrics" placeholder="lyrics_rewrite text"></textarea>
      </label>
      <label>Payload Chords
        <input id="project-edit-chords" placeholder="Cmaj7, Am7, Fmaj7, G7">
      </label>
    </div>
    <div class="grid2">
      <label>Payload Instrument
        <input id="project-edit-instrument" placeholder="alternate instrument">
      </label>
      <label>Provider Mode
        <select id="project-edit-provider-mode">
          <option value="local">local</option>
          <option value="provider">provider</option>
        </select>
      </label>
    </div>
    <div class="actions">
      ${["tempo", "key", "structure", "lyrics", "harmony", "melody", "arrangement"].map((item) => `<label><input class="project-edit-preserve" type="checkbox" value="${item}" ${["tempo", "key", "structure"].includes(item) ? "checked" : ""}> ${item}</label>`).join("")}
    </div>
    <label>Asset References
      <div id="project-edit-asset-refs" class="asset-ref-list"></div>
    </label>
    <label>Reference Materials
      <div id="project-edit-reference-refs" class="reference-ref-list"></div>
    </label>
    <label>Context Pack
      <select id="project-edit-context-pack" class="context-pack-select"><option value="">none</option></select>
    </label>
    <div class="actions">
      <button id="project-create-edit" type="button" ${parentId ? "" : "disabled"}>Create Edit Version</button>
      <button class="secondary" id="project-provider-preview" type="button" ${parentId ? "" : "disabled"}>Generate Preview</button>
      <button class="secondary" id="project-provider-apply-preview" type="button">Apply Preview</button>
      <span id="project-edit-message" class="message"></span>
    </div>
    <div id="project-provider-preview-result"><div class="empty">Provider edit preview will appear here.</div></div>
    <pre>${escapeHtml(preview || "{}")}</pre>
  `;
}

function projectEditPayload() {
  const target = {};
  if ($("project-edit-section").value) target.section_name = $("project-edit-section").value;
  if ($("project-edit-track").value) target.track_name = $("project-edit-track").value;
  if ($("project-edit-field").value) target.field = $("project-edit-field").value;
  const payload = {};
  if ($("project-edit-lyrics").value.trim()) payload.lyrics = $("project-edit-lyrics").value;
  if ($("project-edit-chords").value.trim()) payload.chords = $("project-edit-chords").value.split(",").map((item) => item.trim()).filter(Boolean);
  if ($("project-edit-instrument").value.trim()) payload.instrument = $("project-edit-instrument").value.trim();
  const presetId = $("project-edit-preset") ? $("project-edit-preset").value : "";
  const data = {
    edit_type: $("project-edit-type").value,
    target,
    instruction: $("project-edit-instruction").value.trim(),
    preserve: Array.from(document.querySelectorAll(".project-edit-preserve:checked")).map((item) => item.value),
    strength: Number($("project-edit-strength").value || 5),
    provider_mode: $("project-edit-provider-mode").value,
    payload,
    name: $("project-edit-name").value.trim(),
    change_summary: $("project-edit-summary").value.trim(),
  };
  if (presetId) data.preset_id = presetId;
  const refs = assetRefsPayload("project-edit-asset-refs");
  if (refs.length) data.asset_refs = refs;
  const referenceRefs = referenceRefsPayload("project-edit-reference-refs");
  if (referenceRefs.length) data.reference_refs = referenceRefs;
  const contextPackId = contextPackIdPayload("project-edit-context-pack");
  if (contextPackId) data.context_pack_id = contextPackId;
  return data;
}

function projectPromptABHtml(experiments) {
  if (!experiments || !experiments.length) return `<div class="empty">Prompt A/B experiments will appear here.</div>`;
  return `
    <table>
      <thead><tr><th>A/B</th><th>Templates</th><th>Groups</th><th>Status</th></tr></thead>
      <tbody>
        ${experiments.map((experiment) => `
          <tr>
            <td>${escapeHtml(experiment.ab_id)}</td>
            <td>${escapeHtml((experiment.template_ids || []).join(" / "))}</td>
            <td>${escapeHtml((experiment.group_ids || []).join(", "))}</td>
            <td>${escapeHtml(experiment.status || "-")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function applyEditPresetToForm() {
  const preset = editPresets.find((item) => item.preset_id === $("project-edit-preset").value);
  if (!preset) return;
  $("project-edit-type").value = preset.edit_type;
  $("project-edit-strength").value = Math.max(1, Math.min(10, Math.round(Number(preset.strength || 0.5) * 10)));
  $("project-edit-instruction").value = preset.description || "";
  if (preset.target_defaults) {
    if (preset.target_defaults.field) $("project-edit-field").value = preset.target_defaults.field;
    const sectionName = resolveOptionByRole("project-edit-section", preset.target_defaults.section_role, preset.target_defaults.section_index);
    if (preset.target_defaults.section_name || sectionName) $("project-edit-section").value = preset.target_defaults.section_name || sectionName;
    const trackName = resolveOptionByRole("project-edit-track", preset.target_defaults.track_role, 0);
    if (preset.target_defaults.track_name || trackName) $("project-edit-track").value = preset.target_defaults.track_name || trackName;
  }
  if (preset.payload) {
    $("project-edit-lyrics").value = preset.payload.lyrics || "";
    $("project-edit-chords").value = Array.isArray(preset.payload.chords) ? preset.payload.chords.join(", ") : "";
    $("project-edit-instrument").value = preset.payload.instrument || "";
  }
  document.querySelectorAll(".project-edit-preserve").forEach((checkbox) => {
    checkbox.checked = (preset.preserve || []).includes(checkbox.value);
  });
  $("project-preset-message").textContent = preset.name;
}

function projectEditPresetPayload(presetId) {
  const payload = projectEditPayload();
  return {
    preset_id: presetId,
    name: $("project-edit-name").value.trim() || presetId,
    description: $("project-edit-instruction").value.trim(),
    edit_type: payload.edit_type,
    strength: Math.max(0, Math.min(1, Number(payload.strength || 5) / 10)),
    target_defaults: payload.target,
    payload: payload.payload,
    preserve: payload.preserve,
    tags: ["studio"],
  };
}

async function renderProjectFinalExport(project, versions, target) {
  let manifest = null;
  let deliveryQa = null;
  let deliverySignoff = { summary: { status: "not_signed" } };
  let message = "No final export yet.";
  try {
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/final-export`);
    manifest = data.final_export;
  } catch (err) {
    message = err.message;
  }
  try {
    deliveryQa = await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-qa`);
  } catch (err) {
    deliveryQa = { summary: { status: "not_ready", readiness: "needs_export", handoff_allowed: false }, delivery_qa: { checks: [], artifact_integrity: { files: [] }, zip: {} }, error: err.message };
  }
  try {
    deliverySignoff = await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff`);
  } catch (err) {
    deliverySignoff = { summary: { status: "not_signed" }, signoff: {}, error: err.message };
  }
  let releaseTargets = { releases: [] };
  try {
    releaseTargets = await api(`/api/projects/${encodeURIComponent(project.project_id)}/release-targets`);
  } catch (err) {
    releaseTargets = { releases: [], error: err.message };
  }
  const selectedId = project.final_version_id || project.selected_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
  const selected = versions.find((version) => version.version_id === selectedId) || versions[0] || {};
  target.innerHTML = `
    <div class="summary-grid">
      ${metric("Final", project.final_version_id || "-")}
      ${metric("Gate", selected.quality_gate_status || "not_evaluated")}
      ${metric("MIDI", selected.has_midi ? "yes" : "-")}
      ${metric("WAV", selected.has_audio ? "yes" : "-")}
    </div>
    <div class="summary-grid">
      ${metric("Stems", selected.has_stems ? "yes" : "-")}
      ${metric("Stem WAV", selected.has_stem_audio ? "yes" : "-")}
      ${metric("Quality", selected.quality_score ?? "-")}
      ${metric("Final Export", selected.final_export_path || "-")}
    </div>
    <div class="grid2">
      <label>Version
        <select id="project-final-export-version">${projectVersionOptions(versions, selectedId)}</select>
      </label>
      <label>Force Gate Override
        <select id="project-final-export-force">
          <option value="false">false</option>
          <option value="true">true</option>
        </select>
      </label>
    </div>
    <div class="actions">
      <label><input id="project-final-export-audio" type="checkbox" checked> Include Audio</label>
      <label><input id="project-final-export-stems" type="checkbox" checked> Include Stems</label>
      <label><input id="project-final-export-stem-audio" type="checkbox" checked> Include Stem Audio</label>
      <label><input id="project-final-export-references" type="checkbox" checked> Include Reference Summaries</label>
    </div>
    <div class="actions">
      <button id="project-generate-final-export" type="button" ${versions.length ? "" : "disabled"}>Generate Final Export</button>
      <button class="secondary" id="project-build-final-export-zip" type="button" ${manifest ? "" : "disabled"}>Build ZIP</button>
      <button class="secondary" id="project-refresh-final-export" type="button">Refresh</button>
      <a class="button-link secondary" href="/api/projects/${encodeURIComponent(project.project_id)}/export">Export JSON</a>
      ${manifest && manifest.zip ? `<a class="button-link secondary" href="/api/projects/${encodeURIComponent(project.project_id)}/final-export.zip">Download ZIP</a>` : ""}
      <span id="project-final-export-message" class="message"></span>
    </div>
    ${manifest ? finalExportManifestHtml(manifest) : `<div class="empty">${escapeHtml(message)}</div>`}
    ${deliveryQaHtml(deliveryQa, deliverySignoff)}
    ${projectAddToReleaseHtml(releaseTargets)}
  `;
  bindAction("project-generate-final-export", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/final-export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectFinalExportPayload()),
    });
    await loadProjects();
  });
  bindAction("project-refresh-final-export", async () => {
    await renderProjectFinalExport(project, versions, target);
  });
  bindAction("project-build-final-export-zip", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/final-export/zip`, { method: "POST" });
    await renderProjectFinalExport(project, versions, target);
  });
  bindAction("project-refresh-delivery-qa", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-qa/refresh`, { method: "POST" });
    await renderProjectFinalExport(project, versions, target);
  });
  bindAction("project-sign-delivery", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(deliverySignoffPayload(false)),
    });
    await renderProjectFinalExport(project, versions, target);
  });
  bindAction("project-force-sign-delivery", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(deliverySignoffPayload(true)),
    });
    await renderProjectFinalExport(project, versions, target);
  });
  bindAction("project-reset-delivery-signoff", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: $("project-delivery-reset-reason").value.trim() }),
    });
    await renderProjectFinalExport(project, versions, target);
  });
  bindAction("project-add-to-release", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/add-to-release`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        release_id: $("project-release-target").value,
        title: $("project-release-track-title").value.trim(),
      }),
    });
    await loadReleases();
    await renderProjectFinalExport(project, versions, target);
  });
}

function projectFinalExportPayload() {
  return {
    version_id: $("project-final-export-version").value,
    include_audio: $("project-final-export-audio").checked,
    include_stems: $("project-final-export-stems").checked,
    include_stem_audio: $("project-final-export-stem-audio").checked,
    include_reference_refs: $("project-final-export-references").checked,
    force: $("project-final-export-force").value === "true",
  };
}

async function renderProjectReferences(project, target) {
  try {
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/references`);
    const rows = (data.references || []).map((reference) => `
      <tr>
        <td>${escapeHtml(reference.reference_id)}</td>
        <td>${escapeHtml(reference.title)}</td>
        <td>${escapeHtml(reference.reference_type)}</td>
        <td>${escapeHtml((reference.tags || []).join(", "))}</td>
        <td>${escapeHtml(reference.usage_count || 0)}</td>
        <td><button class="secondary project-reference-unlink" data-reference-id="${escapeHtml(reference.reference_id)}" type="button">Unlink</button></td>
      </tr>
    `).join("");
    target.innerHTML = `
      <label>Link Reference
        <div id="project-link-reference-refs" class="reference-ref-list"></div>
      </label>
      <div class="actions">
        <button id="project-link-selected-reference" type="button">Link Selected Reference</button>
      </div>
      <table>
        <thead><tr><th>Reference</th><th>Title</th><th>Type</th><th>Tags</th><th>Uses</th><th></th></tr></thead>
        <tbody>${rows || "<tr><td colspan='6'>No linked references.</td></tr>"}</tbody>
      </table>
    `;
    renderReferenceSelectors();
    bindAction("project-link-selected-reference", async () => {
      const refs = referenceRefsPayload("project-link-reference-refs");
      for (const ref of refs) {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/references/link`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference_id: ref.reference_id }),
        });
      }
      await loadReferences();
      await renderProjectReferences(project, target);
    });
    target.querySelectorAll(".project-reference-unlink").forEach((button) => {
      button.addEventListener("click", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/references/unlink`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference_id: button.dataset.referenceId }),
        });
        await loadReferences();
        await renderProjectReferences(project, target);
      });
    });
  } catch (err) {
    target.innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

function projectCompareControls(versions) {
  const options = versions.map((version) => `<option value="${escapeHtml(version.version_id)}">${escapeHtml(version.version_id)} · ${escapeHtml(version.name || version.job_id)}</option>`).join("");
  return `
    <div class="grid2">
      <label>Left
        <select id="project-diff-left">${options}</select>
      </label>
      <label>Right
        <select id="project-diff-right">${options}</select>
      </label>
    </div>
    <div class="actions"><button id="project-compare" type="button">Compare</button></div>
    <div id="project-diff-result"><div class="empty">Choose two versions to compare.</div></div>
  `;
}

Object.assign(globalThis, { bindProjectEditorAuditionControls, loadProjectEditorAuditions, refreshProjectEditorDraft, currentProjectEditorView, projectEditorViewTrackWithNotes, firstProjectEditorNoteId, fillSelectedProjectEditorNotePatch, projectEditorBarRuler, projectEditorSectionBlocks, projectEditorTrackOverview, projectEditorTrackButtons, projectEditorPianoRoll, describeProjectEditorOperation, renderProjectEdit, projectEditControls, projectEditPayload, projectPromptABHtml, applyEditPresetToForm, projectEditPresetPayload, renderProjectFinalExport, projectFinalExportPayload, renderProjectReferences, projectCompareControls });

export { bindProjectEditorAuditionControls, loadProjectEditorAuditions, refreshProjectEditorDraft, currentProjectEditorView, projectEditorViewTrackWithNotes, firstProjectEditorNoteId, fillSelectedProjectEditorNotePatch, projectEditorBarRuler, projectEditorSectionBlocks, projectEditorTrackOverview, projectEditorTrackButtons, projectEditorPianoRoll, describeProjectEditorOperation, renderProjectEdit, projectEditControls, projectEditPayload, projectPromptABHtml, applyEditPresetToForm, projectEditPresetPayload, renderProjectFinalExport, projectFinalExportPayload, renderProjectReferences, projectCompareControls };
