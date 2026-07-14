function renderProjectEditorState() {
  const target = $("project-editor-state");
  if (!target || !projectEditorState) return;
  const view = currentProjectEditorView();
  const viewSections = view.sections || [];
  const viewTracks = view.tracks || [];
  if (!viewSections.some((section) => section.section_id === projectEditorSelectedSectionId)) {
    projectEditorSelectedSectionId = (viewSections[0] || {}).section_id || projectEditorSelectedSectionId;
  }
  const sectionOptions = viewSections.map((section) => {
    const derived = isDerivedSection(section.section_id);
    const label = `${section.name} · bar ${section.start_bar}${derived ? " · draft" : ""}`;
    return `<option value="${escapeHtml(section.section_id)}"${derived ? " disabled" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
  const afterSectionOptions = `<option value="">start/end</option>${viewSections.filter((section) => !isDerivedSection(section.section_id)).map((section) => `<option value="${escapeHtml(section.section_id)}">${escapeHtml(section.name)} · bar ${escapeHtml(section.start_bar)}</option>`).join("")}`;
  const trackOptions = viewTracks.map((track) => {
    const derived = isDerivedTrack(track.track_id);
    const label = `${track.name} · ${track.note_count || 0}${derived ? " · draft" : ""}`;
    return `<option value="${escapeHtml(track.track_id)}"${derived ? " disabled" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
  const selectedTrack = viewTracks.find((track) => track.track_id === projectEditorSelectedTrackId) || viewTracks[0] || { notes: [] };
  projectEditorSelectedTrackId = selectedTrack.track_id || projectEditorSelectedTrackId;
  const clipOptions = projectEditorClipOptions();
  const templateOptions = projectEditorTemplateOptions();
  target.innerHTML = `
    <div class="summary-grid">
      ${metric("Title", projectEditorState.song.title)}
      ${metric("Tempo", projectEditorState.song.tempo_bpm)}
      ${metric("Key", projectEditorState.song.key)}
      ${metric("Base Hash", projectEditorState.base_plan_hash.slice(0, 12))}
    </div>
    <div class="editor-workbench">
      <section>
        <h3>Arranger Timeline</h3>
        <div id="project-editor-arranger" class="editor-arranger">
          <div id="project-editor-section-ruler" class="arranger-ruler">
            <strong>Bars</strong>
            ${projectEditorBarRuler(view)}
          </div>
          <div class="arranger-ruler">
            <strong>Sections</strong>
            <div class="section-row">${projectEditorSectionBlocks(view)}</div>
          </div>
          ${projectEditorTrackOverview(view)}
        </div>
      </section>
      <div class="editor-split">
        <section>
          <h3>Tracks</h3>
          <div class="track-list">${projectEditorTrackButtons(view)}</div>
        </section>
        <section>
          <h3>Piano Roll</h3>
          <div id="project-editor-piano-roll" class="editor-piano-roll">
            ${projectEditorPianoRoll(view)}
          </div>
        </section>
      </div>
      <section id="project-editor-note-inspector" class="editor-inspector">
        <h3>Inspector</h3>
        <div class="summary-grid">
          ${metric("Selected Section", projectEditorSelectedSectionId || "-")}
          ${metric("Selected Track", projectEditorSelectedTrackId || "-")}
          ${metric("Selected Note", projectEditorSelectedNoteId || "-")}
          ${metric("Patch Ops", projectEditorPatch.length)}
        </div>
        <div class="actions">
          <button class="secondary" id="project-editor-section-move-left" type="button">Move Section Left</button>
          <button class="secondary" id="project-editor-section-move-right" type="button">Move Section Right</button>
          <button class="secondary" id="project-editor-section-shorten" type="button">Shorten</button>
          <button class="secondary" id="project-editor-section-lengthen" type="button">Lengthen</button>
          <button class="secondary" id="project-editor-nudge-left" type="button">Nudge Left</button>
          <button class="secondary" id="project-editor-nudge-right" type="button">Nudge Right</button>
          <button class="secondary" id="project-editor-pitch-up" type="button">Pitch Up</button>
          <button class="secondary" id="project-editor-pitch-down" type="button">Pitch Down</button>
        </div>
      </section>
    </div>
    <section id="project-editor-clip-browser">
      <h3>Clip Browser</h3>
      <div class="grid2">
        <label>Clip
          <select id="project-editor-clip-select">${clipOptions}</select>
        </label>
        <label>Insert Mode
          <select id="project-editor-clip-mode">
            <option value="overlay">overlay</option>
            <option value="replace_range">replace_range</option>
          </select>
        </label>
      </div>
      <div class="grid2">
        <label>Start Beat <input id="project-editor-clip-start" type="number" step="0.125" value="${escapeHtml((viewSections.find((section) => section.section_id === projectEditorSelectedSectionId) || {}).start_beat ?? 0)}"></label>
        <label>Transpose <input id="project-editor-clip-transpose" type="number" min="-24" max="24" value="0"></label>
      </div>
      <div class="grid2">
        <label>Velocity Scale <input id="project-editor-clip-velocity" type="number" min="0.25" max="2" step="0.05" value="1"></label>
        <label>Quantize
          <select id="project-editor-clip-quantize">
            <option value="">none</option>
            <option value="1/16">1/16</option>
            <option value="1/8">1/8</option>
            <option value="1/4">1/4</option>
          </select>
        </label>
      </div>
      <div class="actions">
        <button class="secondary" id="project-editor-clip-draft" type="button" ${clipOptions ? "" : "disabled"}>Draft Insert Clip</button>
      </div>
      <div class="empty small">${escapeHtml(projectEditorClipSummaryText())}</div>
    </section>
    <section id="project-editor-template-browser">
      <h3>Template Browser</h3>
      <div class="grid2">
        <label>Section Template
          <select id="project-editor-template-select">${templateOptions}</select>
        </label>
        <label>Start Beat <input id="project-editor-template-start" type="number" step="0.125" value="${escapeHtml((viewSections.find((section) => section.section_id === projectEditorSelectedSectionId) || {}).start_beat ?? 0)}"></label>
      </div>
      <div class="grid2">
        <label>Insert Mode
          <select id="project-editor-template-mode">
            <option value="overlay">overlay</option>
            <option value="replace_range">replace_range</option>
          </select>
        </label>
        <label>Transpose <input id="project-editor-template-transpose" type="number" min="-24" max="24" value="0"></label>
      </div>
      <div class="grid2">
        <label>Velocity Scale <input id="project-editor-template-velocity" type="number" min="0.25" max="2" step="0.05" value="1"></label>
        <label>Quantize
          <select id="project-editor-template-quantize">
            <option value="">none</option>
            <option value="1/16">1/16</option>
            <option value="1/8">1/8</option>
            <option value="1/4">1/4</option>
          </select>
        </label>
      </div>
      <div id="project-editor-template-mapping" class="table-wrap"><div class="empty small">${escapeHtml(projectEditorTemplateSummaryText())}</div></div>
      <div class="actions">
        <button class="secondary" id="project-editor-template-map" type="button" ${templateOptions ? "" : "disabled"}>Suggest Mapping</button>
        <button class="secondary" id="project-editor-template-draft" type="button" ${templateOptions ? "" : "disabled"}>Draft Insert Template</button>
      </div>
    </section>
    <div class="grid2">
      <section>
        <h3>Sections</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Bars</th><th>Chords</th><th>Lyrics</th></tr></thead>
            <tbody>${projectEditorState.sections.map((section) => `<tr><td>${escapeHtml(section.name)}</td><td>${escapeHtml(section.start_bar)}+${escapeHtml(section.bars)}</td><td>${escapeHtml(section.chords.join(" · "))}</td><td>${escapeHtml((section.lyrics || "").slice(0, 80))}</td></tr>`).join("")}</tbody>
          </table>
        </div>
      </section>
      <section>
        <h3>Tracks</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Instrument</th><th>Notes</th><th>Range</th></tr></thead>
            <tbody>${projectEditorState.tracks.map((track) => `<tr><td>${escapeHtml(track.name)}</td><td>${escapeHtml(track.instrument)}</td><td>${escapeHtml(track.note_count)}</td><td>${escapeHtml(track.pitch_min ?? "-")}..${escapeHtml(track.pitch_max ?? "-")}</td></tr>`).join("")}</tbody>
          </table>
        </div>
      </section>
    </div>
    <div class="grid2">
      <section>
        <h3>Section Fields</h3>
        <label>Section <select id="project-editor-section">${sectionOptions}</select></label>
        <label>Chords <input id="project-editor-chords" placeholder="Cmaj7, G7, Am7, Fmaj7"></label>
        <label>Lyrics <textarea id="project-editor-lyrics"></textarea></label>
        <div class="actions">
          <button class="secondary" id="project-editor-add-chords" type="button">Set Chords</button>
          <button class="secondary" id="project-editor-add-lyrics" type="button">Set Lyrics</button>
          <button class="secondary" id="project-editor-save-section-template" type="button">Save Section Template</button>
        </div>
      </section>
      <section>
        <h3>Track Fields</h3>
        <label>Track <select id="project-editor-track">${trackOptions}</select></label>
        <label>Instrument <input id="project-editor-instrument" placeholder="warm lead synth"></label>
        <div class="actions">
          <button class="secondary" id="project-editor-add-instrument" type="button">Set Instrument</button>
          <button class="secondary" id="project-editor-save-track-template" type="button">Save Track Template</button>
        </div>
      </section>
    </div>
    <div class="grid2">
      <section>
        <h3>Section Structure</h3>
        <label>Name <input id="project-editor-section-name" placeholder="bridge"></label>
        <label>After <select id="project-editor-after-section">${afterSectionOptions}</select></label>
        <label>Bars <input id="project-editor-section-bars" type="number" min="1" max="64" value="4"></label>
        <label>Chords <input id="project-editor-section-structure-chords" placeholder="Fmaj7, G7"></label>
        <label>Note Policy
          <select id="project-editor-section-note-policy">
            <option value="delete">delete</option>
            <option value="shift_left">shift_left</option>
            <option value="crop">crop</option>
            <option value="shift_tail">shift_tail</option>
          </select>
        </label>
        <div class="actions">
          <button class="secondary" id="project-editor-add-section-op" type="button">Add Section</button>
          <button class="secondary" id="project-editor-duplicate-section-op" type="button">Duplicate Section</button>
          <button class="secondary" id="project-editor-delete-section-op" type="button">Delete Section</button>
          <button class="secondary" id="project-editor-resize-section-op" type="button">Resize Section</button>
          <button class="secondary" id="project-editor-move-section-op" type="button">Move Section</button>
        </div>
      </section>
      <section>
        <h3>Track Structure</h3>
        <label>Name <input id="project-editor-track-name" placeholder="counter melody"></label>
        <label>Instrument <input id="project-editor-track-structure-instrument" placeholder="warm pad"></label>
        <label>Transpose <input id="project-editor-track-transpose" type="number" min="-24" max="24" value="0"></label>
        <div class="actions">
          <button class="secondary" id="project-editor-add-track-op" type="button">Add Track</button>
          <button class="secondary" id="project-editor-duplicate-track-op" type="button">Duplicate Track</button>
          <button class="secondary" id="project-editor-delete-track-op" type="button">Delete Track</button>
          <button class="secondary" id="project-editor-rename-track-op" type="button">Rename Track</button>
        </div>
      </section>
    </div>
    <section>
      <h3>Notes</h3>
      <div class="grid2">
        <label>Note <select id="project-editor-note"></select></label>
        <label>Patch <input id="project-editor-note-patch" placeholder='{"pitch":67,"velocity":96}'></label>
      </div>
      <div class="grid2">
        <label>Add Note <input id="project-editor-add-note-json" placeholder='{"pitch":64,"start_beat":4,"duration_beats":1,"velocity":90}'></label>
        <label>Batch Range <input id="project-editor-range-json" placeholder='{"start_beat":0,"end_beat":16}'></label>
      </div>
      <div class="grid2">
        <label>Transpose Semitones <input id="project-editor-transpose" type="number" min="-24" max="24" value="0"></label>
        <label>Velocity Factor <input id="project-editor-velocity-factor" type="number" min="0.25" max="2" step="0.05" value="1"></label>
      </div>
      <div class="actions">
        <button class="secondary" id="project-editor-add-note" type="button">Add Note</button>
        <button class="secondary" id="project-editor-update-note" type="button">Update Note</button>
        <button class="secondary" id="project-editor-delete-note" type="button">Delete Note</button>
        <button class="secondary" id="project-editor-transpose-range" type="button">Transpose Range</button>
        <button class="secondary" id="project-editor-velocity-range" type="button">Scale Velocity</button>
      </div>
    </section>
    <section>
      <h3>Patch Queue</h3>
      <div id="project-editor-patch-queue" class="patch-queue"></div>
      <h3>Patch Summary</h3>
      <pre id="project-editor-patch-json"></pre>
    </section>
  `;
  setSelectValue("project-editor-section", projectEditorSelectedSectionId);
  setSelectValue("project-editor-track", projectEditorSelectedTrackId);
  renderProjectEditorNoteOptions();
  setSelectValue("project-editor-note", projectEditorSelectedNoteId);
  $("project-editor-track").addEventListener("change", renderProjectEditorNoteOptions);
  $("project-editor-section").addEventListener("change", () => { projectEditorSelectedSectionId = $("project-editor-section").value; });
  $("project-editor-track").addEventListener("change", () => {
    projectEditorSelectedTrackId = $("project-editor-track").value;
    projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
    renderProjectEditorState();
  });
  $("project-editor-note").addEventListener("change", () => { projectEditorSelectedNoteId = $("project-editor-note").value; fillSelectedProjectEditorNotePatch(); });
  const clipSelect = $("project-editor-clip-select");
  if (clipSelect) {
    clipSelect.value = String(projectEditorSelectedClipIndex || 0);
    clipSelect.addEventListener("change", () => {
      projectEditorSelectedClipIndex = Number(clipSelect.value || 0);
      renderProjectEditorState();
    });
  }
  const templateSelect = $("project-editor-template-select");
  if (templateSelect) {
    templateSelect.value = String(projectEditorSelectedTemplateIndex || 0);
    templateSelect.addEventListener("change", async () => {
      projectEditorSelectedTemplateIndex = Number(templateSelect.value || 0);
      projectEditorTemplateMapping = null;
      renderProjectEditorTemplateMapping();
    });
  }
  target.querySelectorAll("[data-editor-section-id]").forEach((button) => {
    button.addEventListener("click", () => {
      projectEditorSelectedSectionId = button.dataset.editorSectionId;
      setSelectValue("project-editor-section", projectEditorSelectedSectionId);
      renderProjectEditorState();
    });
  });
  target.querySelectorAll("[data-editor-track-id]").forEach((button) => {
    button.addEventListener("click", () => {
      projectEditorSelectedTrackId = button.dataset.editorTrackId;
      projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
      renderProjectEditorState();
    });
  });
  target.querySelectorAll("[data-editor-note-id]").forEach((button) => {
    button.addEventListener("click", () => {
      projectEditorSelectedTrackId = button.dataset.editorTrackId;
      projectEditorSelectedNoteId = button.dataset.editorNoteId;
      renderProjectEditorState();
    });
  });
  bindAction("project-editor-add-chords", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "set_section_chords", section_id: $("project-editor-section").value, chords: $("project-editor-chords").value.split(",").map((item) => item.trim()).filter(Boolean) }); });
  bindAction("project-editor-add-lyrics", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "set_section_lyrics", section_id: $("project-editor-section").value, lyrics: $("project-editor-lyrics").value }); });
  bindAction("project-editor-add-instrument", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "set_track_instrument", track_id: $("project-editor-track").value, instrument: $("project-editor-instrument").value.trim() }); });
  bindAction("project-editor-save-section-template", () => saveProjectEditorSectionTemplate());
  bindAction("project-editor-save-track-template", () => saveProjectEditorTrackTemplate());
  bindAction("project-editor-add-section-op", () => addProjectEditorOperation({ op: "add_section", after_section_id: $("project-editor-after-section").value, name: $("project-editor-section-name").value.trim(), bars: Number($("project-editor-section-bars").value || 4), chords: chordList("project-editor-section-structure-chords") }));
  bindAction("project-editor-duplicate-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "duplicate_section", section_id: $("project-editor-section").value, after_section_id: $("project-editor-after-section").value, name: $("project-editor-section-name").value.trim(), copy_notes: true }); });
  bindAction("project-editor-delete-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "delete_section", section_id: $("project-editor-section").value, note_policy: $("project-editor-section-note-policy").value === "shift_left" ? "shift_left" : "delete" }); });
  bindAction("project-editor-resize-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "resize_section", section_id: $("project-editor-section").value, bars: Number($("project-editor-section-bars").value || 4), note_policy: $("project-editor-section-note-policy").value === "crop" ? "crop" : "shift_tail" }); });
  bindAction("project-editor-move-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "move_section", section_id: $("project-editor-section").value, after_section_id: $("project-editor-after-section").value, move_notes: true }); });
  bindAction("project-editor-add-track-op", () => addProjectEditorOperation({ op: "add_track", name: $("project-editor-track-name").value.trim(), instrument: $("project-editor-track-structure-instrument").value.trim() }));
  bindAction("project-editor-duplicate-track-op", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "duplicate_track", track_id: $("project-editor-track").value, name: $("project-editor-track-name").value.trim(), instrument: $("project-editor-track-structure-instrument").value.trim(), transpose: Number($("project-editor-track-transpose").value || 0) }); });
  bindAction("project-editor-delete-track-op", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "delete_track", track_id: $("project-editor-track").value }); });
  bindAction("project-editor-rename-track-op", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "rename_track", track_id: $("project-editor-track").value, name: $("project-editor-track-name").value.trim() }); });
  bindAction("project-editor-add-note", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "add_note", track_id: $("project-editor-track").value, note: parseJsonField("project-editor-add-note-json") }); });
  bindAction("project-editor-update-note", () => { if (!isDerivedTrack($("project-editor-track").value) && !isDerivedNote($("project-editor-note").value)) addProjectEditorOperation({ op: "update_note", track_id: $("project-editor-track").value, note_id: $("project-editor-note").value, patch: parseJsonField("project-editor-note-patch") }); });
  bindAction("project-editor-delete-note", () => { if (!isDerivedTrack($("project-editor-track").value) && !isDerivedNote($("project-editor-note").value)) addProjectEditorOperation({ op: "delete_notes", track_id: $("project-editor-track").value, note_ids: [$("project-editor-note").value] }); });
  bindAction("project-editor-nudge-left", () => addSelectedProjectEditorNoteOperation({ op: "move_notes", delta_beats: -0.25 }));
  bindAction("project-editor-nudge-right", () => addSelectedProjectEditorNoteOperation({ op: "move_notes", delta_beats: 0.25 }));
  bindAction("project-editor-pitch-up", () => addSelectedProjectEditorNoteOperation({ op: "transpose_notes", semitones: 1 }));
  bindAction("project-editor-pitch-down", () => addSelectedProjectEditorNoteOperation({ op: "transpose_notes", semitones: -1 }));
  bindAction("project-editor-section-move-left", () => addProjectEditorSectionMove(-1));
  bindAction("project-editor-section-move-right", () => addProjectEditorSectionMove(1));
  bindAction("project-editor-section-shorten", () => addProjectEditorSectionResize(-1));
  bindAction("project-editor-section-lengthen", () => addProjectEditorSectionResize(1));
  bindAction("project-editor-transpose-range", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "transpose_notes", track_id: $("project-editor-track").value, range: parseJsonField("project-editor-range-json"), semitones: Number($("project-editor-transpose").value || 0) }); });
  bindAction("project-editor-velocity-range", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "scale_velocity", track_id: $("project-editor-track").value, range: parseJsonField("project-editor-range-json"), factor: Number($("project-editor-velocity-factor").value || 1) }); });
  bindAction("project-editor-clip-draft", () => draftInsertProjectEditorClip());
  bindAction("project-editor-template-map", () => loadProjectEditorTemplateMapping());
  bindAction("project-editor-template-draft", () => draftInsertProjectEditorTemplate());
  renderProjectEditorTemplateMapping();
  renderProjectEditorDraft();
}

function projectEditorFlattenedClips() {
  return (((projectEditorClips || {}).clips) || []).filter((clip) => clip && clip.clip_ref);
}

function projectEditorSectionTemplates() {
  return (((editorTemplates || {}).section_templates) || []).filter((template) => template && !template.hidden && template.template_id);
}

function projectEditorClipOptions() {
  const clips = projectEditorFlattenedClips();
  return clips.map((clip, index) => `<option value="${escapeHtml(index)}">${escapeHtml(clip.title || clip.source_id)} · ${escapeHtml(clip.source_type)} · ${escapeHtml(clip.note_count || 0)} notes</option>`).join("");
}

function projectEditorTemplateOptions() {
  const templates = projectEditorSectionTemplates();
  return templates.map((template, index) => `<option value="${escapeHtml(index)}">${escapeHtml(template.name || template.template_id)} · ${escapeHtml(((template.clip || {}).lane_count) || 0)} lanes · ${escapeHtml(((template.clip || {}).note_count) || 0)} notes</option>`).join("");
}

function projectEditorClipSummaryText() {
  const clip = projectEditorFlattenedClips()[projectEditorSelectedClipIndex || 0];
  if (!clip) return "No reusable clips are available yet.";
  return `${clip.source_type} · ${clip.kind || "clip"} · ${clip.duration_beats || 0} beats · ${clip.note_count || 0} notes`;
}

function projectEditorTemplateSummaryText() {
  const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
  if (!template) return "No section templates are available yet.";
  const clip = template.clip || {};
  return `${template.template_id} · ${clip.lane_count || 0} lanes · ${clip.note_count || 0} notes`;
}

function projectEditorPatchMetadata() {
  const inserts = [];
  const templateInserts = [];
  const seen = new Set();
  const seenTemplates = new Set();
  for (const operation of projectEditorPatch) {
    const groupId = operation && operation.clip_group_id;
    const insert = groupId ? projectEditorClipInsertMap[groupId] : null;
    if (!insert || !groupId || seen.has(groupId)) continue;
    seen.add(groupId);
    inserts.push(insert);
  }
  for (const operation of projectEditorPatch) {
    const groupId = operation && operation.template_group_id;
    const insert = groupId ? projectEditorTemplateInsertMap[groupId] : null;
    if (!insert || !groupId || seenTemplates.has(groupId)) continue;
    seenTemplates.add(groupId);
    templateInserts.push(insert);
  }
  const metadata = {};
  if (inserts.length) metadata.clip_inserts = inserts;
  if (templateInserts.length) metadata.template_inserts = templateInserts;
  return metadata;
}

async function draftInsertProjectEditorClip() {
  if (!projectEditorState || !projectEditorSelectedTrackId || isDerivedTrack(projectEditorSelectedTrackId)) return;
  const clips = projectEditorFlattenedClips();
  const clip = clips[projectEditorSelectedClipIndex || 0];
  if (!clip) return;
  const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/editor-clip-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_view: true,
      include_diff: true,
      clip_ref: clip.clip_ref,
      current_patch: projectEditorPatch.length ? {
        schema_version: 1,
        base_plan_hash: projectEditorState.base_plan_hash,
        label: $("project-editor-label").value.trim(),
        operations: projectEditorPatch,
        metadata: projectEditorPatchMetadata(),
      } : null,
      target: {
        track_id: projectEditorSelectedTrackId,
        section_id: projectEditorSelectedSectionId,
        start_beat: Number($("project-editor-clip-start").value || 0),
      },
      options: {
        mode: $("project-editor-clip-mode").value,
        transpose: Number($("project-editor-clip-transpose").value || 0),
        velocity_scale: Number($("project-editor-clip-velocity").value || 1),
        quantize_grid: $("project-editor-clip-quantize").value || null,
      },
    }),
  });
  const clipInsert = ((((data.patch || {}).metadata || {}).clip_inserts) || [])[0] || null;
  if (clipInsert && clipInsert.clip_group_id) projectEditorClipInsertMap[clipInsert.clip_group_id] = clipInsert;
  projectEditorPatch.push(...((data.patch || {}).operations || []));
  projectEditorRedo = [];
  projectEditorPreview = null;
  projectEditorDraft = data;
  projectEditorView = data.draft_view || data.view || projectEditorView;
  renderProjectEditorState();
  const result = $("project-editor-preview-result");
  if (result) {
    result.innerHTML = `
      <div class="summary-grid">
        ${metric("Clip", (data.clip_summary || {}).title || "-")}
        ${metric("Ops Added", ((data.patch || {}).operations || []).length)}
        ${metric("Notes", (data.clip_summary || {}).note_count ?? "-")}
        ${metric("Validator", (data.validator || {}).status || "-")}
      </div>
      <pre>${escapeHtml(JSON.stringify({ clip_summary: data.clip_summary, warnings: data.warnings, diff: data.diff }, null, 2))}</pre>
    `;
  }
}

async function saveProjectEditorSectionTemplate() {
  if (!projectEditorState || !projectEditorSelectedSectionId || isDerivedSection(projectEditorSelectedSectionId)) return;
  try {
    const section = (currentProjectEditorView().sections || []).find((item) => item.section_id === projectEditorSelectedSectionId) || {};
    const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/section-templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        section_id: projectEditorSelectedSectionId,
        name: `${section.name || projectEditorSelectedSectionId} Template`,
        tags: ["editor", "section"],
      }),
    });
    $("project-editor-message").textContent = `saved ${data.template.template_id}`;
    await loadEditorTemplates();
    renderProjectEditorState();
  } catch (err) {
    $("project-editor-message").textContent = err.message;
  }
}

async function saveProjectEditorTrackTemplate() {
  if (!projectEditorState || !projectEditorSelectedTrackId || isDerivedTrack(projectEditorSelectedTrackId)) return;
  try {
    const track = (currentProjectEditorView().tracks || []).find((item) => item.track_id === projectEditorSelectedTrackId) || {};
    const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/track-templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        track_id: projectEditorSelectedTrackId,
        name: `${track.name || projectEditorSelectedTrackId} Template`,
        tags: ["editor", "track"],
      }),
    });
    $("project-editor-message").textContent = `saved ${data.template.template_id}`;
    await loadEditorTemplates();
    renderProjectEditorState();
  } catch (err) {
    $("project-editor-message").textContent = err.message;
  }
}

async function loadProjectEditorTemplateMapping() {
  if (!projectEditorState) return;
  const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
  if (!template) return;
  try {
    projectEditorTemplateMapping = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/editor-template-mapping`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_ref: { source_type: "section_template", template_id: template.template_id } }),
    });
    renderProjectEditorTemplateMapping();
  } catch (err) {
    $("project-editor-message").textContent = err.message;
  }
}

function renderProjectEditorTemplateMapping() {
  const target = $("project-editor-template-mapping");
  if (!target) return;
  const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
  if (!template) {
    target.innerHTML = `<div class="empty small">No section templates are available yet.</div>`;
    return;
  }
  const suggestions = (projectEditorTemplateMapping || {}).suggestions || [];
  if (!suggestions.length) {
    target.innerHTML = `<div class="empty small">${escapeHtml(projectEditorTemplateSummaryText())}</div>`;
    return;
  }
  const trackOptions = (currentProjectEditorView().tracks || []).filter((track) => !isDerivedTrack(track.track_id)).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.name)} · ${escapeHtml(track.track_id)}</option>`).join("");
  target.innerHTML = `
    <table>
      <thead><tr><th>Lane</th><th>Role</th><th>Notes</th><th>Target Track</th><th>Mode</th></tr></thead>
      <tbody>
        ${suggestions.map((item) => `
          <tr data-template-lane-id="${escapeHtml(item.lane_id)}">
            <td>${escapeHtml(item.lane_name || item.lane_id)}</td>
            <td>${escapeHtml(item.lane_role || "-")}</td>
            <td>${escapeHtml(item.note_count || 0)}</td>
            <td><select data-template-target-track>${trackOptions}</select></td>
            <td>
              <select data-template-mode>
                <option value="overlay">overlay</option>
                <option value="replace_range">replace_range</option>
                <option value="skip">skip</option>
              </select>
            </td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  target.querySelectorAll("[data-template-lane-id]").forEach((row) => {
    const item = suggestions.find((suggestion) => suggestion.lane_id === row.dataset.templateLaneId) || {};
    const select = row.querySelector("[data-template-target-track]");
    const mode = row.querySelector("[data-template-mode]");
    if (select && item.suggested_track_id) select.value = item.suggested_track_id;
    if (mode && !item.suggested_track_id) mode.value = "skip";
  });
}

function projectEditorTemplateLaneMappings() {
  const table = $("project-editor-template-mapping");
  if (!table) return [];
  return Array.from(table.querySelectorAll("[data-template-lane-id]")).map((row) => ({
    lane_id: row.dataset.templateLaneId,
    target_track_id: (row.querySelector("[data-template-target-track]") || {}).value || "",
    mode: (row.querySelector("[data-template-mode]") || {}).value || "overlay",
  }));
}

async function draftInsertProjectEditorTemplate() {
  if (!projectEditorState) return;
  const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
  if (!template) return;
  if (!projectEditorTemplateMapping) {
    await loadProjectEditorTemplateMapping();
  }
  const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/editor-multitrack-clip-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_view: true,
      include_diff: true,
      source_ref: { source_type: "section_template", template_id: template.template_id },
      current_patch: projectEditorPatch.length ? {
        schema_version: 1,
        base_plan_hash: projectEditorState.base_plan_hash,
        label: $("project-editor-label").value.trim(),
        operations: projectEditorPatch,
        metadata: projectEditorPatchMetadata(),
      } : null,
      target: {
        section_id: projectEditorSelectedSectionId,
        start_beat: Number($("project-editor-template-start").value || 0),
      },
      lane_mappings: projectEditorTemplateLaneMappings(),
      options: {
        mode: $("project-editor-template-mode").value,
        transpose: Number($("project-editor-template-transpose").value || 0),
        velocity_scale: Number($("project-editor-template-velocity").value || 1),
        quantize_grid: $("project-editor-template-quantize").value || null,
      },
    }),
  });
  const templateInsert = ((((data.patch || {}).metadata || {}).template_inserts) || [])[0] || null;
  if (templateInsert && templateInsert.template_group_id) projectEditorTemplateInsertMap[templateInsert.template_group_id] = templateInsert;
  projectEditorPatch.push(...((data.patch || {}).operations || []));
  projectEditorRedo = [];
  projectEditorPreview = null;
  projectEditorDraft = data;
  projectEditorView = data.draft_view || data.view || projectEditorView;
  renderProjectEditorState();
  const result = $("project-editor-preview-result");
  if (result) {
    result.innerHTML = `
      <div class="summary-grid">
        ${metric("Template", (data.template_summary || {}).title || "-")}
        ${metric("Ops Added", ((data.patch || {}).operations || []).length)}
        ${metric("Lanes", (data.template_summary || {}).lane_count ?? "-")}
        ${metric("Validator", (data.validator || {}).status || "-")}
      </div>
      <pre>${escapeHtml(JSON.stringify({ template_summary: data.template_summary, warnings: data.warnings, diff: data.diff }, null, 2))}</pre>
    `;
  }
}

function renderProjectEditorNoteOptions() {
  const select = $("project-editor-note");
  if (!select) return;
  const trackId = $("project-editor-track") ? $("project-editor-track").value : projectEditorSelectedTrackId;
  const track = (projectEditorViewTrackWithNotes(trackId) || { notes: [] });
  select.innerHTML = (track.notes || []).slice(0, 256).map((note) => `<option value="${escapeHtml(note.note_id)}">${escapeHtml(note.pitch)} @ ${escapeHtml(note.start_beat)}</option>`).join("");
  if (!projectEditorSelectedNoteId || !(track.notes || []).some((note) => note.note_id === projectEditorSelectedNoteId)) {
    projectEditorSelectedNoteId = ((track.notes || [])[0] || {}).note_id || null;
  }
  setSelectValue("project-editor-note", projectEditorSelectedNoteId);
  fillSelectedProjectEditorNotePatch();
}

function addProjectEditorOperation(operation) {
  projectEditorPatch.push(operation);
  projectEditorRedo = [];
  projectEditorPreview = null;
  projectEditorDraft = null;
  renderProjectEditorDraft();
}

function addSelectedProjectEditorNoteOperation(operation) {
  if (!projectEditorSelectedTrackId || !projectEditorSelectedNoteId || isDerivedTrack(projectEditorSelectedTrackId) || isDerivedNote(projectEditorSelectedNoteId)) return;
  addProjectEditorOperation({ ...operation, track_id: projectEditorSelectedTrackId, note_ids: [projectEditorSelectedNoteId] });
}

function addProjectEditorSectionMove(delta) {
  const sections = (projectEditorView || projectEditorState || { sections: [] }).sections || [];
  const index = sections.findIndex((section) => section.section_id === projectEditorSelectedSectionId);
  if (index < 0) return;
  if (String(projectEditorSelectedSectionId || "").startsWith("derived-section-")) return;
  if (delta < 0 && index === 0) return;
  if (delta > 0 && index >= sections.length - 1) return;
  const targetIndex = delta < 0 ? index - 2 : index + 1;
  const after = targetIndex >= 0 ? sections[targetIndex].section_id : "";
  if (after && isDerivedSection(after)) return;
  addProjectEditorOperation({ op: "move_section", section_id: projectEditorSelectedSectionId, after_section_id: after, move_notes: true });
}

function addProjectEditorSectionResize(delta) {
  const section = ((projectEditorView || projectEditorState || { sections: [] }).sections || []).find((item) => item.section_id === projectEditorSelectedSectionId);
  if (!section) return;
  if (String(section.section_id || "").startsWith("derived-section-")) return;
  addProjectEditorOperation({ op: "resize_section", section_id: section.section_id, bars: Math.max(1, Number(section.bars || 1) + delta), note_policy: delta < 0 ? "crop" : "shift_tail" });
}

function renderProjectEditorDraft() {
  const pre = $("project-editor-patch-json");
  if (pre) pre.textContent = projectEditorPatch.map(describeProjectEditorOperation).join("\\n") + "\\n\\n" + JSON.stringify({ operations: projectEditorPatch }, null, 2);
  const queue = $("project-editor-patch-queue");
  if (queue) queue.innerHTML = projectEditorPatch.length ? projectEditorPatch.map((operation, index) => `
    <div class="patch-queue-row">
      <span>${escapeHtml(index + 1)}. ${escapeHtml(describeProjectEditorOperation(operation))}</span>
      <button class="secondary" data-editor-remove-op="${escapeHtml(index)}" type="button">Remove</button>
    </div>
  `).join("") : "<div class='empty'>Patch queue is empty.</div>";
  if (queue) queue.querySelectorAll("[data-editor-remove-op]").forEach((button) => {
    button.addEventListener("click", () => {
      projectEditorPatch.splice(Number(button.dataset.editorRemoveOp), 1);
      projectEditorPreview = null;
      projectEditorDraft = null;
      renderProjectEditorDraft();
    });
  });
  const preview = $("project-editor-preview");
  if (preview) preview.disabled = !projectEditorState || projectEditorPatch.length === 0;
  const draftRefresh = $("project-editor-draft-refresh");
  if (draftRefresh) draftRefresh.disabled = !projectEditorState || projectEditorPatch.length === 0;
  const undo = $("project-editor-undo");
  if (undo) undo.disabled = projectEditorPatch.length === 0;
  const redo = $("project-editor-redo");
  if (redo) redo.disabled = projectEditorRedo.length === 0;
  const apply = $("project-editor-apply");
  if (apply) apply.disabled = !projectEditorPreview;
  const result = $("project-editor-preview-result");
  if (result && !projectEditorPreview && !projectEditorDraft) result.innerHTML = "<div class='empty'>Preview result will appear here.</div>";
}

function projectEditorAuditionTrackOptions() {
  const view = currentProjectEditorView();
  return (view.tracks || []).filter((track) => !isDerivedTrack(track.track_id)).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.name)} · ${escapeHtml(track.track_id)}</option>`).join("");
}

function projectEditorAuditionListHtml() {
  if (!projectEditorAuditions.length) return "<div class='empty small'>No auditions.</div>";
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Audition</th><th>Source</th><th>Range</th><th>Track mode</th><th>Notes</th><th>Review</th><th>WAV</th><th>Actions</th></tr></thead>
        <tbody>${projectEditorAuditions.map((audition) => `
          <tr>
            <td>${escapeHtml(audition.audition_id)}</td>
            <td>${escapeHtml(audition.source)}</td>
            <td>${escapeHtml((audition.range || {}).mode || "-")}</td>
            <td>${escapeHtml(audition.track_mode)}</td>
            <td>${escapeHtml(audition.note_count || 0)}</td>
            <td>
              <div class="compact-form">
                <input data-editor-audition-rating="${escapeHtml(audition.audition_id)}" type="number" min="0" max="5" value="${escapeHtml(((audition.review || {}).rating) || 0)}">
                <select data-editor-audition-status="${escapeHtml(audition.audition_id)}">
                  ${["unreviewed", "keep", "maybe", "needs_fix", "reject"].map((status) => `<option value="${status}" ${((audition.review || {}).status || "unreviewed") === status ? "selected" : ""}>${status}</option>`).join("")}
                </select>
                <label class="inline-check"><input data-editor-audition-favorite="${escapeHtml(audition.audition_id)}" type="checkbox" ${((audition.review || {}).favorite) ? "checked" : ""}> Fav</label>
                <input data-editor-audition-notes="${escapeHtml(audition.audition_id)}" value="${escapeHtml((audition.review || {}).notes || "")}" placeholder="review notes">
                <input data-editor-audition-tags="${escapeHtml(audition.audition_id)}" value="${escapeHtml(((audition.review || {}).tags || []).join(", "))}" placeholder="tags">
                <button class="secondary" data-editor-audition-review="${escapeHtml(audition.audition_id)}" type="button">Save Review</button>
                <div class="actions">
                  <input data-editor-audition-marker-beat="${escapeHtml(audition.audition_id)}" type="number" step="0.125" value="0" title="Marker beat">
                  <select data-editor-audition-marker-kind="${escapeHtml(audition.audition_id)}">
                    ${["hook", "drop", "issue", "keep", "fix", "note"].map((kind) => `<option value="${kind}">${kind}</option>`).join("")}
                  </select>
                  <input data-editor-audition-marker-label="${escapeHtml(audition.audition_id)}" placeholder="marker label">
                  <button class="secondary" data-editor-audition-marker-add="${escapeHtml(audition.audition_id)}" type="button">Add Marker</button>
                </div>
                <div class="empty small">${escapeHtml(((audition.review || {}).markers || []).map((marker) => `${marker.kind}@${marker.beat}`).join(" · ") || "No markers")}</div>
              </div>
            </td>
            <td>${escapeHtml(((audition.audio || {}).status) || "not_started")}</td>
            <td>
              ${(audition.midi || {}).url ? `<a class="button-link secondary" href="${escapeHtml(audition.midi.url)}">MIDI</a>` : ""}
              <button class="secondary" data-editor-audition-render="${escapeHtml(audition.audition_id)}" type="button">Render Audition WAV</button>
              ${(audition.audio || {}).status === "completed" && (audition.audio || {}).url ? `<audio class="inline-audio" controls src="${escapeHtml(audition.audio.url)}"></audio>` : ""}
              <button class="secondary" data-editor-audition-create-asset="${escapeHtml(audition.audition_id)}" type="button">Save Audition Asset</button>
              <button class="secondary" data-editor-audition-preview-edit="${escapeHtml(audition.audition_id)}" type="button">Preview Edit</button>
              <button class="secondary" data-editor-audition-create-edit="${escapeHtml(audition.audition_id)}" type="button">Create Local Edit</button>
              <button class="secondary" data-editor-audition-provider-preview="${escapeHtml(audition.audition_id)}" type="button">Provider Preview</button>
              <button class="secondary" data-editor-audition-create-review-task="${escapeHtml(audition.audition_id)}" type="button">Create Review Task</button>
              <button class="secondary" data-editor-audition-create-context="${escapeHtml(audition.audition_id)}" type="button">Create Context Pack</button>
              <button class="secondary" data-editor-audition-delete="${escapeHtml(audition.audition_id)}" type="button">Delete</button>
            </td>
          </tr>
        `).join("")}</tbody>
      </table>
    </div>
    <div id="project-editor-review-edit-result"><div class="empty small">Review Edit result will appear here.</div></div>
  `;
}

Object.assign(globalThis, { renderProjectEditorState, projectEditorFlattenedClips, projectEditorSectionTemplates, projectEditorClipOptions, projectEditorTemplateOptions, projectEditorClipSummaryText, projectEditorTemplateSummaryText, projectEditorPatchMetadata, draftInsertProjectEditorClip, saveProjectEditorSectionTemplate, saveProjectEditorTrackTemplate, loadProjectEditorTemplateMapping, renderProjectEditorTemplateMapping, projectEditorTemplateLaneMappings, draftInsertProjectEditorTemplate, renderProjectEditorNoteOptions, addProjectEditorOperation, addSelectedProjectEditorNoteOperation, addProjectEditorSectionMove, addProjectEditorSectionResize, renderProjectEditorDraft, projectEditorAuditionTrackOptions, projectEditorAuditionListHtml });

export { renderProjectEditorState, projectEditorFlattenedClips, projectEditorSectionTemplates, projectEditorClipOptions, projectEditorTemplateOptions, projectEditorClipSummaryText, projectEditorTemplateSummaryText, projectEditorPatchMetadata, draftInsertProjectEditorClip, saveProjectEditorSectionTemplate, saveProjectEditorTrackTemplate, loadProjectEditorTemplateMapping, renderProjectEditorTemplateMapping, projectEditorTemplateLaneMappings, draftInsertProjectEditorTemplate, renderProjectEditorNoteOptions, addProjectEditorOperation, addSelectedProjectEditorNoteOperation, addProjectEditorSectionMove, addProjectEditorSectionResize, renderProjectEditorDraft, projectEditorAuditionTrackOptions, projectEditorAuditionListHtml };
