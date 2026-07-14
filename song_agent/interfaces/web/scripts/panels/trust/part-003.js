function renderPlanningGovernance() {
  const target = $("planning-rule-governance");
  if (!target) return;
  const summary = (planningGovernance || {}).summary || {};
  const active = (planningGovernance || {}).active || {};
  const promotionRows = planningPromotions.slice(0, 8).map((promotion) => {
    const evidence = promotion.evidence || {};
    return `
      <tr>
        <td>${escapeHtml(promotion.promotion_id || "-")}</td>
        <td>${escapeHtml(promotion.status || "-")}</td>
        <td>${escapeHtml(promotion.ruleset_id || "-")}</td>
        <td>${escapeHtml(promotion.simulation_id || "-")}</td>
        <td>${escapeHtml(evidence.recommendation || "-")}</td>
        <td>${escapeHtml(evidence.alignment_delta ?? "-")}</td>
      </tr>
    `;
  }).join("");
  const versionRows = planningVersions.slice(0, 6).map((version) => `
    <tr>
      <td>${escapeHtml(version.version_id || "-")}</td>
      <td>${escapeHtml(version.status || "-")}</td>
      <td>${escapeHtml(version.ruleset_id || "-")}</td>
      <td>${escapeHtml((version.promoted_from || {}).simulation_id || "-")}</td>
    </tr>
  `).join("");
  target.innerHTML = `
    <div class="grid3">
      <div><b>Active Version</b><br>${escapeHtml(summary.active_version_id || active.active_version_id || "-")}</div>
      <div><b>Ruleset</b><br>${escapeHtml(summary.ruleset_id || "-")}</div>
      <div><b>Evidence</b><br>${escapeHtml(summary.evidence_stale ? "stale" : summary.status || "missing")}</div>
    </div>
    <table>
      <thead><tr><th>Promotion</th><th>Status</th><th>Rule Set</th><th>Simulation</th><th>Recommendation</th><th>Delta</th></tr></thead>
      <tbody>${promotionRows || "<tr><td colspan='6'>No promotions.</td></tr>"}</tbody>
    </table>
    <table>
      <thead><tr><th>Version</th><th>Status</th><th>Rule Set</th><th>Simulation</th></tr></thead>
      <tbody>${versionRows || "<tr><td colspan='4'>No versions.</td></tr>"}</tbody>
    </table>
  `;
}

Object.assign(globalThis, { renderPlanningGovernance });

export { renderPlanningGovernance };
