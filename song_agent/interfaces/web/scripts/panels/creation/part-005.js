function projectCompareResultHtml(compare) {
  const sectionRows = (compare.sections || []).map((row) => `
    <tr>
      <td>${escapeHtml(row.section)}</td>
      <td>${escapeHtml(row.changed ? "changed" : "-")}</td>
      <td class="wrap-cell">${escapeHtml(JSON.stringify(row.left || {}))}</td>
      <td class="wrap-cell">${escapeHtml(JSON.stringify(row.right || {}))}</td>
    </tr>
  `).join("");
  const trackRows = (compare.tracks || []).map((row) => `
    <tr>
      <td>${escapeHtml(row.track)}</td>
      <td>${escapeHtml(row.changed ? "changed" : "-")}</td>
      <td class="wrap-cell">${escapeHtml(JSON.stringify(row.left || {}))}</td>
      <td class="wrap-cell">${escapeHtml(JSON.stringify(row.right || {}))}</td>
    </tr>
  `).join("");
  return `
    <div class="summary-grid">
      ${metric("Recommendation", compare.summary.recommendation || "-")}
      ${metric("Quality Delta", compare.summary.quality_delta ?? "-")}
      ${metric("Section Changes", compare.summary.section_changes || 0)}
      ${metric("Track Changes", compare.summary.track_changes || 0)}
    </div>
    <div class="compare-grid">
      ${projectCompareSideHtml("Left", compare.left, (compare.artifacts || {}).left)}
      ${projectCompareSideHtml("Right", compare.right, (compare.artifacts || {}).right)}
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Section</th><th>Changed</th><th>Left</th><th>Right</th></tr></thead>
        <tbody>${sectionRows || "<tr><td colspan='4'>No section data.</td></tr>"}</tbody>
      </table>
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Track</th><th>Changed</th><th>Left</th><th>Right</th></tr></thead>
        <tbody>${trackRows || "<tr><td colspan='4'>No track data.</td></tr>"}</tbody>
      </table>
    </div>
  `;
}

function projectCompareSideHtml(label, version, artifacts) {
  if (!version) return `<div class="empty">${escapeHtml(label)}</div>`;
  return `
    <div>
      <div class="panel-title" style="padding:0 0 8px;border-bottom:0;">${escapeHtml(label)} ${escapeHtml(version.version_id)}</div>
      <div class="summary-grid">
        ${metric("Quality", (version.quality || {}).overall ?? "-")}
        ${metric("Gate", (version.gate || {}).status || "-")}
        ${metric("Variant", version.variant_type || "-")}
        ${metric("Preset", ((version.edit || {}).preset || {}).name || "-")}
      </div>
      <div class="actions">
        ${artifacts && artifacts.midi ? `<a class="button-link secondary" href="${escapeHtml(artifacts.midi)}">MIDI</a>` : ""}
        ${artifacts && artifacts.audio ? `<a class="button-link secondary" href="${escapeHtml(artifacts.audio)}">WAV</a>` : `<span class="message">WAV not rendered</span>`}
      </div>
      ${artifacts && artifacts.audio ? `<audio class="audio-player" controls src="${escapeHtml(artifacts.audio)}"></audio>` : ""}
    </div>
  `;
}

function projectVersionOptions(versions, selectedId) {
  return versions.map((version) => `
    <option value="${escapeHtml(version.version_id)}" ${version.version_id === selectedId ? "selected" : ""}>${escapeHtml(version.version_id)} · ${escapeHtml(version.name || version.job_id)}</option>
  `).join("");
}

function projectTabLabel(tab) {
  return {
    versions: "Versions",
    variation: "Variation",
    edit: "Edit",
    editor: "Editor",
    "review-workbench": "Review Workbench",
    "mix-board": "Mix Board",
    "review-sprints": "Review Sprints",
    candidates: "Candidates",
    "quality-gate": "Quality Gate",
    "final-export": "Final Export",
    compare: "Compare",
    references: "References",
    export: "Export JSON",
    events: "Events",
  }[tab] || tab;
}

async function renderJobAssets(job, target) {
  target.innerHTML = `
    <div class="grid2">
      <label>Asset Types
        <input id="job-asset-types" value="motif,chord_progression">
      </label>
      <label>Section
        <input id="job-asset-section" value="chorus">
      </label>
    </div>
    <div class="grid2">
      <label>Track
        <input id="job-asset-track" placeholder="melody, drums, bass">
      </label>
      <label>Tags
        <input id="job-asset-tags" placeholder="chorus, hook">
      </label>
    </div>
    <div class="actions">
      <button id="job-extract-asset" type="button">Extract Asset</button>
      <span id="job-asset-message" class="message"></span>
    </div>
  `;
  bindAction("job-extract-asset", async () => {
    const data = await api("/api/assets/extract/from-job", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: job.job_id,
        asset_types: $("job-asset-types").value.split(",").map((item) => item.trim()).filter(Boolean),
        section_name: $("job-asset-section").value.trim(),
        track_name: $("job-asset-track").value.trim(),
        tags: $("job-asset-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
      }),
    });
    $("job-asset-message").textContent = `saved ${data.count || 0}`;
    await loadAssets();
  });
}

Object.assign(globalThis, { projectCompareResultHtml, projectCompareSideHtml, projectVersionOptions, projectTabLabel, renderJobAssets });

export { projectCompareResultHtml, projectCompareSideHtml, projectVersionOptions, projectTabLabel, renderJobAssets };
