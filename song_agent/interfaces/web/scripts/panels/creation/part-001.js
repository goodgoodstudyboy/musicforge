function fillPresets() {
  const select = $("preset");
  select.innerHTML = "<option value=''>Default</option>";
  template.presets.forEach((preset, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = preset.name;
    select.appendChild(option);
  });
  select.addEventListener("change", () => {
    const value = select.value;
    if (value === "") {
      fillForm(template.defaults);
    } else {
      fillForm({ ...template.defaults, ...template.presets[Number(value)] });
    }
  });
}

async function loadEditPresets() {
  const data = await api("/api/edit-presets");
  editPresets = data.presets || [];
}

async function loadPromptTemplates() {
  const data = await api("/api/prompt-templates");
  promptTemplates = data.templates || [];
  const select = $("prompt-template-select");
  select.innerHTML = promptTemplates.map((template) => `<option value="${escapeHtml(template.template_id)}">${escapeHtml(template.name)}${template.overridden ? " · override" : ""}</option>`).join("");
  if (!select.value && promptTemplates.some((template) => template.template_id === "provider-edit-intent")) {
    select.value = "provider-edit-intent";
  }
  $("prompt-template-status").textContent = `${data.override_count || 0} overrides`;
  applyPromptTemplateSelection();
}

function applyPromptTemplateSelection() {
  const template = promptTemplates.find((item) => item.template_id === $("prompt-template-select").value) || promptTemplates[0];
  if (!template) return;
  $("prompt-template-system").value = template.system_prompt || "";
  $("prompt-template-user").value = template.user_prompt || "";
}

async function loadEditorTemplates() {
  editorTemplates = await api("/api/editor-templates");
  const sections = (editorTemplates.section_templates || []).filter((template) => !template.hidden);
  const tracks = (editorTemplates.track_templates || []).filter((template) => !template.hidden);
  const total = sections.length + tracks.length;
  $("editor-template-status").textContent = `${total} templates`;
  const target = $("editor-template-list");
  if (!total) {
    target.innerHTML = `<div class="empty">No editor templates saved yet.</div>`;
    return;
  }
  target.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Type</th><th>Lanes</th><th>Notes</th><th>Updated</th></tr></thead>
      <tbody>
        ${sections.map((template) => `<tr><td>${escapeHtml(template.name)}</td><td>section</td><td>${escapeHtml(((template.clip || {}).lane_count) || 0)}</td><td>${escapeHtml(((template.clip || {}).note_count) || 0)}</td><td>${escapeHtml(template.updated_at || "-")}</td></tr>`).join("")}
        ${tracks.map((template) => `<tr><td>${escapeHtml(template.name)}</td><td>track</td><td>1</td><td>${escapeHtml(template.default_note_count || 0)}</td><td>${escapeHtml(template.updated_at || "-")}</td></tr>`).join("")}
      </tbody>
    </table>
  `;
}

function projectPayload() {
  return {
    name: $("project-name").value.trim() || $("title").value.trim() || "Untitled Project",
    description: $("project-description").value.trim(),
    tags: $("project-tags").value
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean),
  };
}

async function loadContextPacks() {
  try {
    const data = await api("/api/context-packs");
    contextPacks = data.context_packs || [];
    renderContextPacks();
    renderContextPackSelectors();
  } catch (err) {
    $("context-pack-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

async function rebuildLibrary() {
  const data = await api("/api/library/rebuild", { method: "POST" });
  $("library-message").textContent = `${data.index.item_count} indexed`;
}

async function searchLibrary() {
  const payload = librarySearchPayload();
  const data = await api("/api/library/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  renderLibraryResults(data.results || []);
  $("library-message").textContent = `${data.total || 0} results`;
}

async function recommendLibrary() {
  const data = await api("/api/library/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source: "song_request",
      goal: "generate",
      song_request: formPayload(),
      limit: 10,
    }),
  });
  const recommendation = data.recommendation || {};
  applyLibraryPreview(recommendation.context_pack_preview || {});
  renderLibraryResults([...(recommendation.asset_results || []), ...(recommendation.reference_results || [])]);
  $("library-message").textContent = "recommended";
}

function librarySearchPayload() {
  const payload = {
    query: $("library-query").value.trim(),
    include_stale: $("library-include-stale").checked,
    include_hidden: $("library-include-hidden").checked,
    limit: 30,
  };
  if ($("library-kind").value) payload.item_kinds = [$("library-kind").value];
  if ($("library-role").value.trim()) payload.roles = $("library-role").value.split(",").map((item) => item.trim()).filter(Boolean);
  if ($("library-tempo").value) payload.tempo_bpm = Number($("library-tempo").value);
  if ($("library-key").value.trim()) payload.key = $("library-key").value.trim();
  return payload;
}

function renderLibraryResults(results) {
  const target = $("library-results");
  if (!results.length) {
    target.innerHTML = "<div class='empty'>No library results.</div>";
    return;
  }
  target.innerHTML = results.map((result) => `
    <div class="library-result">
      <h4>${escapeHtml(result.title)} <span class="status">${escapeHtml(result.item_kind)} · ${escapeHtml(result.item_type)}</span></h4>
      <div class="summary-grid">
        ${metric("Score", result.score ?? "-")}
        ${metric("Key", result.key || "-")}
        ${metric("Tempo", result.tempo_bpm || "-")}
        ${metric("Uses", result.usage_count || 0)}
      </div>
      <div class="actions">
        <button class="secondary" data-library-add="${escapeHtml(result.item_id)}" data-kind="${escapeHtml(result.item_kind)}" data-source-id="${escapeHtml(result.source_id)}" data-role="${escapeHtml(((result.features || {}).roles || ["reference"])[0] || "reference")}" type="button">Add to Context</button>
      </div>
      <pre>${escapeHtml(JSON.stringify({ tags: result.tags || [], reasons: result.score_breakdown || [], summary: result.summary || {} }, null, 2))}</pre>
    </div>
  `).join("");
  target.querySelectorAll("[data-library-add]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.kind === "asset") {
        upsertContextRef(librarySelection.asset_refs, "asset_id", { asset_id: button.dataset.sourceId, role: button.dataset.role, strength: 0.8 });
      } else {
        upsertContextRef(librarySelection.reference_refs, "reference_id", { reference_id: button.dataset.sourceId, role: button.dataset.role, strength: 0.6 });
      }
      renderContextPackPreview();
    });
  });
}

function upsertContextRef(list, key, item) {
  if (list.some((ref) => ref[key] === item[key])) return;
  if (list.length >= 5) return;
  list.push(item);
}

async function saveSelectedContextPack() {
  try {
    const pack = await api("/api/context-packs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("context-pack-name").value.trim() || "Studio Context",
        created_from: { source: "studio", goal: "generate" },
        query: librarySearchPayload(),
        asset_refs: librarySelection.asset_refs,
        reference_refs: librarySelection.reference_refs,
        selection: { mode: "manual", selected_by: "user" },
      }),
    });
    $("context-pack-message").textContent = "saved";
    $("context-pack-select").value = pack.context_pack.pack_id;
    await loadContextPacks();
  } catch (err) {
    $("context-pack-message").textContent = err.message;
  }
}

function renderContextPacks() {
  const target = $("context-pack-list");
  if (!contextPacks.length) {
    target.innerHTML = "<div class='empty'>No context packs yet.</div>";
    return;
  }
  target.innerHTML = `
    <table><thead><tr><th>Pack</th><th>Assets</th><th>References</th><th>Updated</th></tr></thead><tbody>
      ${contextPacks.map((pack) => `<tr><td>${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</td><td>${escapeHtml((pack.asset_refs || []).length)}</td><td>${escapeHtml((pack.reference_refs || []).length)}</td><td>${escapeHtml(pack.updated_at || "-")}</td></tr>`).join("")}
    </tbody></table>
  `;
}

function renderContextPackSelectors() {
  document.querySelectorAll(".context-pack-select").forEach((select) => {
    const selected = select.value;
    select.innerHTML = `<option value="">none</option>${contextPacks.map((pack) => `<option value="${escapeHtml(pack.pack_id)}">${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</option>`).join("")}`;
    select.value = selected;
  });
  if ($("context-pack-select")) {
    const selected = $("context-pack-select").value;
    $("context-pack-select").innerHTML = `<option value="">none</option>${contextPacks.map((pack) => `<option value="${escapeHtml(pack.pack_id)}">${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</option>`).join("")}`;
    $("context-pack-select").value = selected;
  }
  if ($("song-context-pack")) {
    const selected = $("song-context-pack").value;
    $("song-context-pack").innerHTML = `<option value="">none</option>${contextPacks.map((pack) => `<option value="${escapeHtml(pack.pack_id)}">${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</option>`).join("")}`;
    $("song-context-pack").value = selected;
  }
}

function contextPackIdPayload(selectId) {
  const select = $(selectId);
  return select && select.value ? select.value : "";
}

async function loadProjects() {
  try {
    const params = new URLSearchParams();
    if (includeHiddenProjects) params.set("include_hidden", "1");
    if ($("project-search").value.trim()) params.set("q", $("project-search").value.trim());
    if ($("project-status-filter").value) params.set("status", $("project-status-filter").value);
    if ($("project-variant-filter").value) params.set("variant_type", $("project-variant-filter").value);
    const data = await api(`/api/projects${params.toString() ? "?" + params.toString() : ""}`);
    projects = data.projects;
    if (selectedProjectId && !projects.some((project) => project.project_id === selectedProjectId)) {
      selectedProjectId = null;
      $("project-detail").innerHTML = "<div class='empty'>Select or create a project.</div>";
    }
    renderProjects();
    if (selectedProjectId) await renderProjectDetail(selectedProjectId);
  } catch (err) {
    $("project-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAssets() {
  try {
    const params = new URLSearchParams();
    if (includeHiddenAssets) params.set("include_hidden", "1");
    if ($("asset-search").value.trim()) params.set("q", $("asset-search").value.trim());
    if ($("asset-type-filter").value) params.set("type", $("asset-type-filter").value);
    if ($("asset-tag-filter").value.trim()) params.set("tag", $("asset-tag-filter").value.trim());
    if ($("asset-favorite-filter").value) params.set("favorite", $("asset-favorite-filter").value);
    const data = await api(`/api/assets${params.toString() ? "?" + params.toString() : ""}`);
    assets = data.assets || [];
    if (selectedAssetId && !assets.some((asset) => asset.asset_id === selectedAssetId)) {
      selectedAssetId = null;
      $("asset-detail").innerHTML = "<div class='empty'>Select an asset.</div>";
    }
    renderAssets();
    renderAssetSelectors();
    if (selectedAssetId) await renderAssetDetail(selectedAssetId);
  } catch (err) {
    $("asset-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadReferences() {
  try {
    const params = new URLSearchParams();
    if (includeHiddenReferences) params.set("include_hidden", "1");
    if ($("reference-search").value.trim()) params.set("q", $("reference-search").value.trim());
    if ($("reference-type-filter").value) params.set("type", $("reference-type-filter").value);
    if ($("reference-tag-filter").value.trim()) params.set("tag", $("reference-tag-filter").value.trim());
    if ($("reference-favorite-filter").value) params.set("favorite", $("reference-favorite-filter").value);
    const data = await api(`/api/references${params.toString() ? "?" + params.toString() : ""}`);
    references = data.references || [];
    if (selectedReferenceId && !references.some((reference) => reference.reference_id === selectedReferenceId)) {
      selectedReferenceId = null;
      $("reference-detail").innerHTML = "<div class='empty'>Select a reference.</div>";
    }
    renderReferences();
    renderReferenceSelectors();
    if (selectedReferenceId) await renderReferenceDetail(selectedReferenceId);
  } catch (err) {
    $("reference-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

function renderReferences() {
  const list = $("reference-list");
  if (!references.length) {
    list.innerHTML = "<div class='empty'>No references yet.</div>";
    renderReferenceSelectors();
    return;
  }
  const rows = references.map((reference) => `
    <tr>
      <td><button class="secondary reference-open" data-reference-id="${escapeHtml(reference.reference_id)}" type="button">Open</button></td>
      <td>${escapeHtml(reference.title)}</td>
      <td>${escapeHtml(reference.reference_type)}</td>
      <td>${escapeHtml((reference.tags || []).join(", "))}</td>
      <td>${escapeHtml(reference.size_bytes || 0)}</td>
      <td>${escapeHtml(reference.usage_count || 0)}</td>
      <td>${reference.favorite ? "yes" : "-"}</td>
    </tr>
  `).join("");
  list.innerHTML = `
    <table>
      <thead><tr><th></th><th>Title</th><th>Type</th><th>Tags</th><th>Bytes</th><th>Uses</th><th>Favorite</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  list.querySelectorAll(".reference-open").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedReferenceId = button.dataset.referenceId;
      await renderReferenceDetail(selectedReferenceId);
    });
  });
}

async function renderReferenceDetail(referenceId) {
  const data = await api(`/api/references/${encodeURIComponent(referenceId)}`);
  const reference = data.reference;
  let analysis = { status: "not_loaded", summary: {} };
  let sliceManifest = { status: "not_loaded", slices: [] };
  try {
    analysis = (await api(`/api/references/${encodeURIComponent(referenceId)}/analysis`)).analysis || analysis;
  } catch (err) {
    analysis = { status: "error", error: err.message, summary: {} };
  }
  if (reference.reference_type === "midi") {
    try {
      sliceManifest = (await api(`/api/references/${encodeURIComponent(referenceId)}/slices`)).manifest || sliceManifest;
    } catch (err) {
      sliceManifest = { status: "error", error: err.message, slices: [] };
    }
  }
  $("reference-detail").innerHTML = `
    <div class="summary-grid">
      ${metric("Reference", reference.reference_id)}
      ${metric("Type", reference.reference_type)}
      ${metric("Size", reference.size_bytes || 0)}
      ${metric("Uses", reference.usage_count || 0)}
      ${metric("Key", reference.key || "-")}
      ${metric("Tempo", reference.tempo_bpm || "-")}
      ${metric("Projects", (reference.linked_project_ids || []).length)}
      ${metric("Assets", (reference.derived_asset_ids || []).length)}
    </div>
    <div class="grid2">
      <label>Title
        <input id="reference-edit-title" value="${escapeHtml(reference.title)}">
      </label>
      <label>Tags
        <input id="reference-edit-tags" value="${escapeHtml((reference.tags || []).join(", "))}">
      </label>
    </div>
    <label>Description
      <textarea id="reference-edit-description">${escapeHtml(reference.description || "")}</textarea>
    </label>
    <div class="actions">
      <button id="reference-save" type="button">Save Metadata</button>
      <a class="button-link secondary" href="${escapeHtml(reference.file_url)}">Download Original</a>
      ${reference.reference_type !== "audio_wav" ? `<button class="secondary" id="reference-create-asset" type="button">Create Asset</button>` : ""}
      ${selectedProjectId ? `<button class="secondary" id="reference-link-project" type="button">Link Project</button><button class="secondary" id="reference-unlink-project" type="button">Unlink Project</button>` : ""}
      ${reference.hidden ? `<button class="secondary" id="reference-unhide" type="button">Unhide Reference</button>` : `<button class="secondary" id="reference-hide" type="button">Hide Reference</button>`}
      ${reference.favorite ? `<button class="secondary" id="reference-unfavorite" type="button">Unfavorite</button>` : `<button class="secondary" id="reference-favorite" type="button">Favorite</button>`}
      <button class="danger" id="reference-delete" type="button">Delete Reference</button>
    </div>
    <div class="panel-title subhead"><span>Analysis</span></div>
    <div class="summary-grid">
      ${metric("Analysis", analysis.status || "-")}
      ${metric("Slices", (sliceManifest.slices || []).length)}
      ${metric("Stale", analysis.stale ? "yes" : "-")}
      ${metric("Warnings", (analysis.warnings || []).length)}
    </div>
    <div class="actions">
      <button class="secondary" id="reference-analyze" type="button">Analyze Reference</button>
      ${reference.reference_type === "midi" ? `<button class="secondary" id="reference-generate-slices" type="button">Generate MIDI Slices</button>` : ""}
    </div>
    ${referenceAnalysisHtml(reference, analysis, sliceManifest)}
    <pre>${escapeHtml(JSON.stringify({ summary: referenceSummary(reference), linked_project_ids: reference.linked_project_ids, derived_asset_ids: reference.derived_asset_ids }, null, 2))}</pre>
  `;
  bindAction("reference-save", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: $("reference-edit-title").value.trim(),
        description: $("reference-edit-description").value,
        tags: $("reference-edit-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
      }),
    });
    await loadReferences();
  });
  bindAction("reference-create-asset", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/create-asset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_type: defaultAssetTypeForReference(reference.reference_type) }),
    });
    await loadAssets();
    await loadReferences();
  });
  bindAction("reference-analyze", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/analyze`, { method: "POST" });
    await renderReferenceDetail(reference.reference_id);
  });
  bindAction("reference-generate-slices", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices`, { method: "POST" });
    await renderReferenceDetail(reference.reference_id);
  });
  $("reference-detail").querySelectorAll("[data-render-reference-slice-midi]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices/${encodeURIComponent(button.dataset.sliceId)}/render-midi`, { method: "POST" });
      await renderReferenceDetail(reference.reference_id);
    });
  });
  $("reference-detail").querySelectorAll("[data-render-reference-slice-audio]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices/${encodeURIComponent(button.dataset.sliceId)}/render-audio`, { method: "POST" });
      await renderReferenceDetail(reference.reference_id);
    });
  });
  $("reference-detail").querySelectorAll("[data-create-reference-slice-asset]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices/${encodeURIComponent(button.dataset.sliceId)}/create-asset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: `${reference.title} ${button.dataset.sliceId}` }),
      });
      await loadAssets();
      await loadReferences();
    });
  });
  bindAction("reference-link-project", async () => {
    if (!selectedProjectId) return;
    await api(`/api/projects/${encodeURIComponent(selectedProjectId)}/references/link`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reference_id: reference.reference_id }),
    });
    await loadReferences();
    await loadProjects();
  });
  bindAction("reference-unlink-project", async () => {
    if (!selectedProjectId) return;
    await api(`/api/projects/${encodeURIComponent(selectedProjectId)}/references/unlink`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reference_id: reference.reference_id }),
    });
    await loadReferences();
    await loadProjects();
  });
  bindAction("reference-hide", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/hide`, { method: "POST" });
    await loadReferences();
  });
  bindAction("reference-unhide", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/unhide`, { method: "POST" });
    await loadReferences();
  });
  bindAction("reference-favorite", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/favorite`, { method: "POST" });
    await loadReferences();
  });
  bindAction("reference-unfavorite", async () => {
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/unfavorite`, { method: "POST" });
    await loadReferences();
  });
  bindAction("reference-delete", async () => {
    if (!confirm("Delete this reference?")) return;
    await api(`/api/references/${encodeURIComponent(reference.reference_id)}/delete`, { method: "POST" });
    selectedReferenceId = null;
    await loadReferences();
  });
}

function referenceAnalysisHtml(reference, analysis, sliceManifest) {
  const summary = analysis.summary || {};
  let body = "";
  if (reference.reference_type === "audio_wav" && analysis.status === "completed") {
    const envelope = summary.envelope || [];
    body = `
      <div class="summary-grid">
        ${metric("Duration", summary.duration_seconds ?? "-")}
        ${metric("Sample Rate", summary.sample_rate ?? "-")}
        ${metric("Channels", summary.channels ?? "-")}
        ${metric("Peak / RMS", `${summary.peak ?? "-"} / ${summary.rms ?? "-"}`)}
      </div>
      <div class="waveform">${envelope.map((point) => `<span style="height:${Math.max(2, Math.round((Number(point.peak) || 0) * 44))}px"></span>`).join("")}</div>
    `;
  } else if (reference.reference_type === "midi" && analysis.status === "completed") {
    const tracks = summary.track_summaries || [];
    body = `
      <div class="summary-grid">
        ${metric("Format", summary.format ?? "-")}
        ${metric("PPQ", summary.ppq ?? "-")}
        ${metric("Tempo", summary.tempo_bpm ?? "-")}
        ${metric("Notes", summary.note_count ?? "-")}
      </div>
      <div class="table-scroll">
        <table><thead><tr><th>Track</th><th>Role</th><th>Notes</th><th>Pitch</th></tr></thead><tbody>
          ${tracks.map((track) => `<tr><td>${escapeHtml(track.track_index)}</td><td>${escapeHtml(track.likely_role || "-")}</td><td>${escapeHtml(track.note_count || 0)}</td><td>${escapeHtml(track.pitch_min ?? "-")} - ${escapeHtml(track.pitch_max ?? "-")}</td></tr>`).join("") || `<tr><td colspan="4">No MIDI tracks.</td></tr>`}
        </tbody></table>
      </div>
      ${referenceSlicesHtml(reference, sliceManifest)}
    `;
  } else if ((reference.reference_type === "lyrics_text" || reference.reference_type === "style_note") && analysis.status === "completed") {
    body = `
      <div class="summary-grid">
        ${metric("Characters", summary.character_count ?? "-")}
        ${metric("Lines", summary.line_count ?? "-")}
        ${metric("Words", summary.word_count ?? "-")}
        ${metric("Language", summary.language_hint || "-")}
      </div>
      <pre>${escapeHtml(JSON.stringify({ keywords: summary.keywords || [], safe_excerpt: summary.safe_excerpt || "" }, null, 2))}</pre>
    `;
  } else {
    body = `<div class="empty">${escapeHtml(analysis.error || "Analysis is not available yet.")}</div>`;
  }
  return body;
}

function referenceSlicesHtml(reference, sliceManifest) {
  const slices = sliceManifest.slices || [];
  if (!slices.length) return `<div class="empty">No MIDI slices yet.</div>`;
  return `
    <div class="table-scroll">
      <table><thead><tr><th>Slice</th><th>Type</th><th>Start</th><th>Beats</th><th>Notes</th><th>Actions</th></tr></thead><tbody>
        ${slices.map((slice) => `
          <tr>
            <td>${escapeHtml(slice.slice_id)}</td>
            <td>${escapeHtml(slice.slice_type)}</td>
            <td>${escapeHtml(slice.start_beat)}</td>
            <td>${escapeHtml(slice.duration_beats)}</td>
            <td>${escapeHtml(slice.note_count)}</td>
            <td>
              <button class="secondary" data-render-reference-slice-midi data-slice-id="${escapeHtml(slice.slice_id)}" type="button">Render MIDI</button>
              ${slice.midi_url ? `<a class="button-link secondary" href="${escapeHtml(slice.midi_url)}">Download MIDI</a>` : ""}
              <button class="secondary" data-render-reference-slice-audio data-slice-id="${escapeHtml(slice.slice_id)}" type="button">Render WAV</button>
              ${slice.audio_url ? `<a class="button-link secondary" href="${escapeHtml(slice.audio_url)}">Download WAV</a><audio controls src="${escapeHtml(slice.audio_url)}"></audio>` : ""}
              <button class="secondary" data-create-reference-slice-asset data-slice-id="${escapeHtml(slice.slice_id)}" type="button">Create Asset</button>
            </td>
          </tr>
        `).join("")}
      </tbody></table>
    </div>
  `;
}

function renderReferenceSelectors() {
  document.querySelectorAll(".reference-ref-list").forEach((container) => {
    const previous = new Map(Array.from(container.querySelectorAll("input[type='checkbox']")).map((input) => [input.value, input.checked]));
    const strengths = new Map(Array.from(container.querySelectorAll("input[type='number']")).map((input) => [input.dataset.referenceId, input.value]));
    container.innerHTML = references.slice(0, 60).map((reference) => `
      <label class="asset-ref-row">
        <input type="checkbox" value="${escapeHtml(reference.reference_id)}" ${previous.get(reference.reference_id) ? "checked" : ""}>
        <span>${escapeHtml(reference.reference_type)} · ${escapeHtml(reference.title)}</span>
        <input type="number" data-reference-id="${escapeHtml(reference.reference_id)}" min="0" max="1" step="0.1" value="${escapeHtml(strengths.get(reference.reference_id) || "0.7")}">
      </label>
    `).join("") || "<div class='empty'>No references available.</div>";
  });
}

function referenceRefsPayload(containerId) {
  const container = $(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll("input[type='checkbox']:checked")).slice(0, 5).map((checkbox) => {
    const reference = references.find((item) => item.reference_id === checkbox.value) || {};
    const strengthInput = container.querySelector(`input[type='number'][data-reference-id="${CSS.escape(checkbox.value)}"]`);
    return {
      reference_id: checkbox.value,
      role: defaultReferenceRole(reference.reference_type),
      strength: Number((strengthInput && strengthInput.value) || 0.7),
    };
  });
}

async function referenceImportPayload() {
  const file = $("reference-file").files && $("reference-file").files[0];
  if (!file) throw new Error("Choose a reference file.");
  return {
    reference_type: $("reference-type").value,
    filename: file.name,
    title: $("reference-title").value.trim() || file.name,
    tags: $("reference-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
    content_base64: await fileToBase64(file),
  };
}

function defaultReferenceRole(referenceType) {
  return {
    audio_wav: "reference_audio",
    midi: "reference_midi",
    lyrics_text: "reference_lyrics",
    style_note: "reference_style",
  }[referenceType] || "reference";
}

function defaultAssetTypeForReference(referenceType) {
  return {
    midi: "motif",
    lyrics_text: "lyric_hook",
    style_note: "section_template",
  }[referenceType] || "lyric_hook";
}

function referenceSummary(reference) {
  return {
    description: reference.description,
    tags: reference.tags || [],
    text_excerpt: reference.text_excerpt,
    source_note: reference.source_note,
    license_note: reference.license_note,
  };
}

function renderAssets() {
  const list = $("asset-list");
  if (!assets.length) {
    list.innerHTML = "<div class='empty'>No assets yet.</div>";
    renderAssetSelectors();
    return;
  }
  const rows = assets.map((asset) => `
    <tr>
      <td><button class="secondary asset-open" data-asset-id="${escapeHtml(asset.asset_id)}" type="button">Open</button></td>
      <td>${escapeHtml(asset.name)}</td>
      <td>${escapeHtml(asset.asset_type)}</td>
      <td>${escapeHtml((asset.tags || []).join(", "))}</td>
      <td>${escapeHtml(asset.quality_score ?? "-")}</td>
      <td>${escapeHtml(asset.usage_count || 0)}</td>
      <td>${asset.favorite ? "yes" : "-"}</td>
    </tr>
  `).join("");
  list.innerHTML = `
    <table>
      <thead><tr><th></th><th>Name</th><th>Type</th><th>Tags</th><th>Quality</th><th>Uses</th><th>Favorite</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  list.querySelectorAll(".asset-open").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedAssetId = button.dataset.assetId;
      await renderAssetDetail(selectedAssetId);
    });
  });
}

async function renderAssetDetail(assetId) {
  const data = await api(`/api/assets/${encodeURIComponent(assetId)}`);
  const asset = data.asset;
  const preview = asset.preview || {};
  $("asset-detail").innerHTML = `
    <div class="summary-grid">
      ${metric("Asset", asset.asset_id)}
      ${metric("Type", asset.asset_type)}
      ${metric("Quality", asset.quality_score ?? "-")}
      ${metric("Uses", asset.usage_count || 0)}
      ${metric("Key", asset.key || "-")}
      ${metric("Tempo", asset.tempo_bpm || "-")}
      ${metric("MIDI", preview.midi_status || "not_started")}
      ${metric("WAV", preview.audio_status || "not_started")}
    </div>
    <div class="grid2">
      <label>Name
        <input id="asset-name" value="${escapeHtml(asset.name)}">
      </label>
      <label>Tags
        <input id="asset-tags" value="${escapeHtml((asset.tags || []).join(", "))}">
      </label>
    </div>
    <label>Description
      <textarea id="asset-description">${escapeHtml(asset.description || "")}</textarea>
    </label>
    <div class="actions">
      <button id="asset-save" type="button">Save Metadata</button>
      <button class="secondary" id="asset-render-midi" type="button">Render Asset MIDI</button>
      <button class="secondary" id="asset-render-audio" type="button">Render Asset Audio</button>
      ${preview.midi_url ? `<a class="button-link secondary" href="${escapeHtml(preview.midi_url)}">Download Asset MIDI</a>` : ""}
      ${preview.audio_url ? `<a class="button-link secondary" href="${escapeHtml(preview.audio_url)}">Download Asset WAV</a>` : ""}
      ${asset.hidden ? `<button class="secondary" id="asset-unhide" type="button">Unhide Asset</button>` : `<button class="secondary" id="asset-hide" type="button">Hide Asset</button>`}
      ${asset.favorite ? `<button class="secondary" id="asset-unfavorite" type="button">Unfavorite</button>` : `<button class="secondary" id="asset-favorite" type="button">Favorite</button>`}
      <button class="danger" id="asset-delete" type="button">Delete Asset</button>
    </div>
    ${preview.audio_url ? `<audio class="audio-player" controls src="${escapeHtml(preview.audio_url)}"></audio>` : ""}
    <pre>${escapeHtml(JSON.stringify({ source: asset.source, content_summary: assetContentSummary(asset), content: asset.content }, null, 2))}</pre>
  `;
  bindAction("asset-save", async () => {
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("asset-name").value.trim(),
        description: $("asset-description").value,
        tags: $("asset-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
      }),
    });
    await loadAssets();
  });
  bindAction("asset-render-midi", async () => {
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/render-midi`, { method: "POST" });
    await loadAssets();
  });
  bindAction("asset-render-audio", async () => {
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/render-audio`, { method: "POST" });
    await loadAssets();
  });
  bindAction("asset-hide", async () => {
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/hide`, { method: "POST" });
    await loadAssets();
  });
  bindAction("asset-unhide", async () => {
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/unhide`, { method: "POST" });
    await loadAssets();
  });
  bindAction("asset-favorite", async () => {
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/favorite`, { method: "POST" });
    await loadAssets();
  });
  bindAction("asset-unfavorite", async () => {
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/unfavorite`, { method: "POST" });
    await loadAssets();
  });
  bindAction("asset-delete", async () => {
    if (!confirm("Delete this asset?")) return;
    await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/delete`, { method: "POST" });
    selectedAssetId = null;
    await loadAssets();
  });
}

function renderAssetSelectors() {
  document.querySelectorAll(".asset-ref-list").forEach((container) => {
    const previous = new Map(Array.from(container.querySelectorAll("input[type='checkbox']")).map((input) => [input.value, input.checked]));
    const strengths = new Map(Array.from(container.querySelectorAll("input[type='number']")).map((input) => [input.dataset.assetId, input.value]));
    container.innerHTML = assets.slice(0, 60).map((asset) => `
      <label class="asset-ref-row">
        <input type="checkbox" value="${escapeHtml(asset.asset_id)}" ${previous.get(asset.asset_id) ? "checked" : ""}>
        <span>${escapeHtml(asset.asset_type)} · ${escapeHtml(asset.name)}</span>
        <input type="number" data-asset-id="${escapeHtml(asset.asset_id)}" min="0" max="1" step="0.1" value="${escapeHtml(strengths.get(asset.asset_id) || "0.7")}">
      </label>
    `).join("") || "<div class='empty'>No assets available.</div>";
  });
}

function assetRefsPayload(containerId) {
  const container = $(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll("input[type='checkbox']:checked")).slice(0, 5).map((checkbox) => {
    const asset = assets.find((item) => item.asset_id === checkbox.value) || {};
    const strengthInput = container.querySelector(`input[type='number'][data-asset-id="${CSS.escape(checkbox.value)}"]`);
    return {
      asset_id: checkbox.value,
      role: defaultAssetRole(asset.asset_type),
      strength: Number((strengthInput && strengthInput.value) || 0.7),
    };
  });
}

function defaultAssetRole(assetType) {
  return {
    motif: "motif_reference",
    chord_progression: "chord_reference",
    drum_pattern: "drum_reference",
    bass_pattern: "bass_reference",
  }[assetType] || "reference";
}

Object.assign(globalThis, { fillPresets, loadEditPresets, loadPromptTemplates, applyPromptTemplateSelection, loadEditorTemplates, projectPayload, loadContextPacks, rebuildLibrary, searchLibrary, recommendLibrary, librarySearchPayload, renderLibraryResults, upsertContextRef, saveSelectedContextPack, renderContextPacks, renderContextPackSelectors, contextPackIdPayload, loadProjects, loadAssets, loadReferences, renderReferences, renderReferenceDetail, referenceAnalysisHtml, referenceSlicesHtml, renderReferenceSelectors, referenceRefsPayload, referenceImportPayload, defaultReferenceRole, defaultAssetTypeForReference, referenceSummary, renderAssets, renderAssetDetail, renderAssetSelectors, assetRefsPayload, defaultAssetRole });

export { fillPresets, loadEditPresets, loadPromptTemplates, applyPromptTemplateSelection, loadEditorTemplates, projectPayload, loadContextPacks, rebuildLibrary, searchLibrary, recommendLibrary, librarySearchPayload, renderLibraryResults, upsertContextRef, saveSelectedContextPack, renderContextPacks, renderContextPackSelectors, contextPackIdPayload, loadProjects, loadAssets, loadReferences, renderReferences, renderReferenceDetail, referenceAnalysisHtml, referenceSlicesHtml, renderReferenceSelectors, referenceRefsPayload, referenceImportPayload, defaultReferenceRole, defaultAssetTypeForReference, referenceSummary, renderAssets, renderAssetDetail, renderAssetSelectors, assetRefsPayload, defaultAssetRole };
