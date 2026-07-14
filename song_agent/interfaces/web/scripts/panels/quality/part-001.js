function applyLibraryPreview(preview) {
  librarySelection = {
    asset_refs: (preview.asset_refs || []).slice(0, 5),
    reference_refs: (preview.reference_refs || []).slice(0, 5),
  };
  renderContextPackPreview();
}

async function previewSelectedContextPack() {
  const packId = $("context-pack-select").value;
  if (!packId) return;
  try {
    const data = await api(`/api/context-packs/${encodeURIComponent(packId)}/apply-preview`, { method: "POST" });
    $("context-pack-preview").textContent = JSON.stringify(data, null, 2);
    librarySelection = { asset_refs: data.asset_refs || [], reference_refs: data.reference_refs || [] };
  } catch (err) {
    $("context-pack-preview").textContent = err.message;
  }
}

function renderContextPackPreview() {
  $("context-pack-preview").textContent = JSON.stringify(librarySelection, null, 2);
}

async function loadAcceptanceSuites() {
  try {
    const data = await api("/api/acceptance/suites");
    acceptanceSuites = data.suites || [];
    if (selectedAcceptanceSuiteId && !acceptanceSuites.some((suite) => suite.suite_id === selectedAcceptanceSuiteId)) {
      selectedAcceptanceSuiteId = null;
      $("acceptance-detail").innerHTML = "<div class='empty'>Select or create an acceptance suite.</div>";
    }
    renderAcceptanceSuites();
    if (selectedAcceptanceSuiteId) await renderAcceptanceDetail(selectedAcceptanceSuiteId);
  } catch (err) {
    $("acceptance-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAcceptanceReferenceData() {
  try {
    const [profilesData, songbookData] = await Promise.all([
      api("/api/acceptance/profiles"),
      api("/api/acceptance/songbook"),
    ]);
    acceptanceProfiles = profilesData.profiles || [];
    acceptanceSongbook = songbookData.songbook || null;
    renderAcceptanceReferenceData();
  } catch (err) {
    $("acceptance-songbook").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadAcceptanceAnalytics() {
  try {
    const data = await api("/api/acceptance/analytics");
    acceptanceAnalytics = data.analytics || null;
  } catch (err) {
    acceptanceAnalytics = null;
  }
  renderAcceptanceAnalytics();
}

async function loadAcceptanceFixSprints() {
  try {
    const data = await api("/api/acceptance/fix-sprints");
    acceptanceFixSprints = data.fix_sprints || [];
  } catch (err) {
    acceptanceFixSprints = [];
  }
  renderAcceptanceFixSprints();
}

async function loadAcceptanceFixPlans() {
  try {
    const data = await api("/api/acceptance/fix-plans");
    acceptanceFixPlans = data.fix_plans || [];
  } catch (err) {
    acceptanceFixPlans = [];
  }
  renderAcceptanceFixPlans();
}

async function loadAcceptanceFixPlanReview(planId) {
  if (!planId) {
    acceptanceFixPlanReview = null;
    renderAcceptanceFixPlanReview();
    return;
  }
  try {
    const data = await api(`/api/acceptance/fix-plans/${encodeURIComponent(planId)}/outcome-review`);
    acceptanceFixPlanReview = data.outcome_review || null;
  } catch (err) {
    acceptanceFixPlanReview = null;
  }
  renderAcceptanceFixPlanReview();
}

async function loadPlanningSimulations() {
  try {
    const [rulesetsData, simulationsData] = await Promise.all([
      api("/api/acceptance/planning-rulesets"),
      api("/api/acceptance/planning-simulations"),
    ]);
    planningRuleSets = rulesetsData.rulesets || [];
    planningSimulations = simulationsData.simulations || [];
  } catch (err) {
    planningRuleSets = [];
    planningSimulations = [];
  }
  renderPlanningSimulations();
}

async function loadPlanningImpact() {
  try {
    const data = await api("/api/acceptance/planning-rule-impact/reports");
    planningImpactReports = data.reports || [];
    planningImpact = planningImpactReports[0] || null;
  } catch (err) {
    planningImpactReports = [];
    planningImpact = null;
  }
  renderPlanningImpact();
}

async function loadAcceptanceKb() {
  try {
    const data = await api("/api/acceptance/kb");
    acceptanceKb = data.knowledge_report || null;
  } catch (err) {
    acceptanceKb = null;
  }
  renderAcceptanceKb();
}

function renderAcceptanceSuites() {
  const list = $("acceptance-list");
  if (!acceptanceSuites.length) {
    list.innerHTML = "<div class='empty'>No acceptance suites yet.</div>";
    return;
  }
  const rows = acceptanceSuites.map((suite) => `
    <tr class="${suite.suite_id === selectedAcceptanceSuiteId ? "active" : ""}">
      <td><button class="secondary acceptance-open" data-suite-id="${escapeHtml(suite.suite_id)}" type="button">Open</button></td>
      <td>${escapeHtml(suite.name || suite.suite_id)}</td>
      <td><span class="status ${escapeHtml(suite.status || "")}">${escapeHtml(suite.status || "-")}</span></td>
      <td>${escapeHtml(suite.case_count || 0)}</td>
      <td>${escapeHtml(suite.accepted_count || 0)}</td>
      <td>${escapeHtml((suite.latest_report_summary || {}).status || "missing")}</td>
      <td>${escapeHtml((suite.latest_signoff_summary || {}).status || "not_signed")}</td>
    </tr>
  `).join("");
  list.innerHTML = `
    <table>
      <thead><tr><th></th><th>Name</th><th>Status</th><th>Cases</th><th>Accepted</th><th>Report</th><th>Signoff</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  list.querySelectorAll(".acceptance-open").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedAcceptanceSuiteId = button.dataset.suiteId;
      renderAcceptanceSuites();
      await renderAcceptanceDetail(selectedAcceptanceSuiteId);
    });
  });
}

function renderAcceptanceReferenceData() {
  if ($("acceptance-profile") && acceptanceProfiles.length) {
    const current = $("acceptance-profile").value || "developer_manual";
    $("acceptance-profile").innerHTML = acceptanceProfiles.map((profile) => {
      const id = profile.profile_id || "";
      return `<option value="${escapeHtml(id)}" ${id === current ? "selected" : ""}>${escapeHtml(id)}</option>`;
    }).join("");
  }
  const songs = (acceptanceSongbook || {}).songs || [];
  const songbook = $("acceptance-songbook");
  if (!songbook) return;
  if (!songs.length) {
    songbook.innerHTML = "<div class='empty'>No regression songs available.</div>";
    return;
  }
  songbook.innerHTML = `
    <table>
      <thead><tr><th>Song ID</th><th>Title</th><th>Style</th><th>Min</th></tr></thead>
      <tbody>${songs.slice(0, 12).map((song) => `
        <tr>
          <td>${escapeHtml(song.song_id || "-")}</td>
          <td>${escapeHtml(song.title || "-")}</td>
          <td>${escapeHtml(song.style || "-")}</td>
          <td>${escapeHtml(((song.expectations || {}).quality_min) || "-")}</td>
        </tr>
      `).join("")}</tbody>
    </table>
  `;
}

function acceptanceSongOptions() {
  const songs = (acceptanceSongbook || {}).songs || [];
  return songs.map((song) => `<option value="${escapeHtml(song.song_id)}">${escapeHtml(song.song_id)} · ${escapeHtml(song.title || "")}</option>`).join("");
}

function acceptanceSuiteOptions(selectedId = "") {
  return acceptanceSuites.map((suite) => {
    const summary = suite.latest_report_summary || {};
    const label = `${suite.name || suite.suite_id} · ${suite.profile_id || "-"} · ${summary.acceptance_status || summary.status || "missing"}`;
    return `<option value="${escapeHtml(suite.suite_id)}" ${suite.suite_id === selectedId ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
}

function renderAcceptanceAnalytics(report = acceptanceAnalytics) {
  const target = $("acceptance-analytics");
  if (!target) return;
  if (!report || !report.report_id) {
    target.innerHTML = "<div class='empty'>No acceptance analytics report yet.</div>";
    return;
  }
  const summary = report.summary || {};
  const heatmapRows = (report.songbook_heatmap || []).slice(0, 12).map((item) => `
    <tr>
      <td>${escapeHtml(item.song_id || "-")}</td>
      <td>${escapeHtml(item.status || "-")}</td>
      <td>${escapeHtml(item.case_count || 0)}</td>
      <td>${escapeHtml(item.manual_accepted_count || 0)}</td>
      <td>${escapeHtml(item.issue_count || 0)}</td>
      <td>${escapeHtml(item.average_rating ?? "-")}</td>
    </tr>
  `).join("");
  const issueRows = (report.issue_taxonomy || []).slice(0, 8).map((item) => `
    <tr>
      <td>${escapeHtml(item.issue_type || "-")}</td>
      <td>${escapeHtml(item.count || 0)}</td>
      <td>${escapeHtml(item.severity || "-")}</td>
      <td>${escapeHtml(item.example_excerpt || "")}</td>
    </tr>
  `).join("");
  const recommendationRows = (report.recommendations || []).slice(0, 8).map((item) => `
    <tr>
      <td>${escapeHtml(item.type || "-")}</td>
      <td>${escapeHtml(item.song_id || "-")}</td>
      <td>${escapeHtml(item.priority || "-")}</td>
      <td>${escapeHtml(item.reason || "")}</td>
      <td>${item.type === "create_review_task" ? `<button class="secondary acceptance-analytics-create-task" data-report-id="${escapeHtml(report.report_id)}" data-recommendation-id="${escapeHtml(item.recommendation_id)}" type="button">Create Task</button>` : "-"}</td>
    </tr>
  `).join("");
  target.innerHTML = `
    <div class="summary-grid">
      ${metric("Readiness", summary.readiness_status || "watch")}
      ${metric("Cases", summary.case_count || 0)}
      ${metric("Manual Accepted", summary.manual_accepted_count || 0)}
      ${metric("Needs Fix", summary.needs_fix_count || 0)}
      ${metric("Blocked", summary.blocked_count || 0)}
      ${metric("Stale", report.stale ? "yes" : "-")}
    </div>
    <div class="grid2">
      <label>Report ID <input id="acceptance-analytics-report-id" readonly value="${escapeHtml(report.report_id)}"></label>
      <label>Source Hash <input readonly value="${escapeHtml(report.source_hash || "")}"></label>
    </div>
    <div class="panel-title subhead"><span>Songbook Heatmap</span></div>
    <table>
      <thead><tr><th>Song ID</th><th>Status</th><th>Cases</th><th>Manual</th><th>Issues</th><th>Rating</th></tr></thead>
      <tbody>${heatmapRows || "<tr><td colspan='6'>No songbook metrics yet.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Issue Taxonomy</span></div>
    <table>
      <thead><tr><th>Issue</th><th>Count</th><th>Severity</th><th>Example</th></tr></thead>
      <tbody>${issueRows || "<tr><td colspan='4'>No issues detected.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Recommendations</span></div>
    <table>
      <thead><tr><th>Action</th><th>Song</th><th>Priority</th><th>Reason</th><th></th></tr></thead>
      <tbody>${recommendationRows || "<tr><td colspan='5'>No recommendations.</td></tr>"}</tbody>
    </table>
  `;
  document.querySelectorAll(".acceptance-analytics-create-task").forEach((button) => button.addEventListener("click", async () => {
    const data = await api(`/api/acceptance/analytics/reports/${encodeURIComponent(button.dataset.reportId)}/recommendations/${encodeURIComponent(button.dataset.recommendationId)}/create-review-task`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    $("acceptance-analytics-report-id").value = data.status || data.task_id || report.report_id;
  }));
}

function renderAcceptanceFixSprints() {
  const target = $("acceptance-fix-sprints");
  if (!target) return;
  if (!acceptanceFixSprints.length) {
    target.innerHTML = "<div class='empty'>No acceptance fix sprints yet.</div>";
    return;
  }
  const rows = acceptanceFixSprints.map((sprint) => {
    const counts = sprint.counts || {};
    const recheck = sprint.recheck || {};
    const delta = sprint.delta_summary || {};
    return `
      <tr>
        <td>${escapeHtml(sprint.fix_sprint_id)}</td>
        <td>${escapeHtml(sprint.name || "")}</td>
        <td>${escapeHtml(sprint.status || "-")}</td>
        <td>${escapeHtml(counts.item_count || 0)}</td>
        <td>${escapeHtml(counts.open_item_count || 0)}</td>
        <td>${escapeHtml(recheck.suite_id || "-")}</td>
        <td>${escapeHtml(delta.status || "-")}</td>
        <td class="actions">
          <button class="secondary acceptance-fix-tasks" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Create ReviewTasks</button>
          <button class="secondary acceptance-fix-recheck" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Create Recheck</button>
          <button class="secondary acceptance-fix-delta" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Delta</button>
          <button class="secondary acceptance-fix-close" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Close</button>
        </td>
      </tr>
    `;
  }).join("");
  target.innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Items</th><th>Open</th><th>Recheck</th><th>Delta</th><th>Actions</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  document.querySelectorAll(".acceptance-fix-tasks").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/create-review-tasks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    await loadAcceptanceFixSprints();
  }));
  document.querySelectorAll(".acceptance-fix-recheck").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/create-recheck-suite`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    await loadAcceptanceFixSprints();
    await loadAcceptanceSuites();
  }));
  document.querySelectorAll(".acceptance-fix-delta").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/delta/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    await loadAcceptanceFixSprints();
  }));
  document.querySelectorAll(".acceptance-fix-close").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/close`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    await loadAcceptanceFixSprints();
  }));
}

function renderAcceptanceFixPlans() {
  const target = $("acceptance-fix-plans");
  if (!target) return;
  if (!acceptanceFixPlans.length) {
    target.innerHTML = "<div class='empty'>No acceptance fix plans yet.</div>";
    return;
  }
  const rows = acceptanceFixPlans.map((plan) => {
    const summary = plan.summary || {};
    const execution = plan.execution || {};
    return `
      <tr>
        <td><button class="secondary acceptance-fix-plan-select" data-plan-id="${escapeHtml(plan.plan_id)}" type="button">Select</button></td>
        <td>${escapeHtml(plan.plan_id)}</td>
        <td>${escapeHtml(plan.status || "-")}</td>
        <td>${escapeHtml(summary.planned_item_count || 0)}</td>
        <td>${escapeHtml(summary.kb_match_count || 0)}</td>
        <td>${escapeHtml(summary.risk_warning_count || 0)}</td>
        <td>${escapeHtml(execution.created_fix_sprint_id || "-")}</td>
      </tr>
    `;
  }).join("");
  target.innerHTML = `
    <table>
      <thead><tr><th></th><th>Plan</th><th>Status</th><th>Items</th><th>KB Matches</th><th>Risks</th><th>Fix Sprint</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  document.querySelectorAll(".acceptance-fix-plan-select").forEach((button) => button.addEventListener("click", () => {
    $("acceptance-fix-plan-id").value = button.dataset.planId || "";
    loadAcceptanceFixPlanReview(button.dataset.planId || "");
  }));
}

function renderAcceptanceFixPlanReview() {
  const target = $("acceptance-fix-plan-review");
  if (!target) return;
  const review = acceptanceFixPlanReview || {};
  if (!review.review_id) {
    const status = review.status || "missing";
    target.innerHTML = `<div class="empty">Outcome Review ${escapeHtml(status)}.</div>`;
    return;
  }
  const summary = review.summary || {};
  const hints = (review.calibration_hints || []).slice(0, 5).map((hint) => `<li>${escapeHtml(hint.type || "hint")}: ${escapeHtml(hint.reason || "")}</li>`).join("");
  const items = (review.item_outcomes || []).slice(0, 8).map((item) => {
    const outcome = item.outcome || {};
    return `
      <tr>
        <td>${escapeHtml(item.planned_item_id || "-")}</td>
        <td>${escapeHtml(item.fix_item_id || "-")}</td>
        <td>${escapeHtml(item.planning_score ?? "-")}</td>
        <td>${escapeHtml(outcome.evidence_status || "-")}</td>
        <td>${escapeHtml(outcome.observed_effectiveness_score ?? "-")}</td>
      </tr>
    `;
  }).join("");
  target.innerHTML = `
    <div class="grid3">
      <div><b>Review</b><br>${escapeHtml(review.review_id)}</div>
      <div><b>Status</b><br>${escapeHtml(review.status || "-")}</div>
      <div><b>Plan Effectiveness</b><br>${escapeHtml(summary.plan_effectiveness_score ?? "-")}</div>
      <div><b>Ranking Alignment</b><br>${escapeHtml(summary.ranking_alignment_score ?? "-")}</div>
      <div><b>KB Helpfulness</b><br>${escapeHtml(summary.kb_evidence_helpfulness || "-")}</div>
      <div><b>Warnings</b><br>${escapeHtml(summary.warning_count || 0)}</div>
    </div>
    <table>
      <thead><tr><th>Planned Item</th><th>Fix Item</th><th>Score</th><th>Evidence</th><th>Effectiveness</th></tr></thead>
      <tbody>${items || "<tr><td colspan='5'>No item outcomes.</td></tr>"}</tbody>
    </table>
    ${hints ? `<ul>${hints}</ul>` : ""}
  `;
}

function renderPlanningSimulations() {
  const target = $("planning-rule-simulation");
  if (!target) return;
  const ruleset = planningRuleSets[0] || {};
  if (!planningSimulations.length) {
    target.innerHTML = `<div class="empty">Simulation only. Rule sets: ${escapeHtml(planningRuleSets.length)}. Latest rule set: ${escapeHtml(ruleset.ruleset_id || "-")}.</div>`;
    return;
  }
  const rows = planningSimulations.slice(0, 8).map((simulation) => {
    const summary = simulation.summary || {};
    return `
      <tr>
        <td>${escapeHtml(simulation.simulation_id || "-")}</td>
        <td>${escapeHtml(simulation.ruleset_id || "-")}</td>
        <td>${escapeHtml(simulation.status || "-")}</td>
        <td>${escapeHtml(summary.review_count || 0)}</td>
        <td>${escapeHtml(summary.alignment_delta ?? "-")}</td>
        <td>${escapeHtml(summary.recommendation || "-")}</td>
      </tr>
    `;
  }).join("");
  target.innerHTML = `
    <div class="grid3">
      <div><b>Mode</b><br>simulation only</div>
      <div><b>Rule Sets</b><br>${escapeHtml(planningRuleSets.length)}</div>
      <div><b>Simulations</b><br>${escapeHtml(planningSimulations.length)}</div>
    </div>
    <table>
      <thead><tr><th>Simulation</th><th>Rule Set</th><th>Status</th><th>Reviews</th><th>Delta</th><th>Recommendation</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderPlanningImpact() {
  const target = $("planning-rule-impact");
  if (!target) return;
  if (!planningImpact || !planningImpact.report_id) {
    target.innerHTML = "<div class='empty'>No planning rule impact report yet.</div>";
    return;
  }
  const summary = planningImpact.summary || {};
  const adoption = planningImpact.adoption || {};
  const risk = planningImpact.risk_drift || {};
  const rows = (planningImpact.version_metrics || []).slice(0, 8).map((item) => `
    <tr>
      <td>${escapeHtml(item.version_id || "-")}</td>
      <td>${escapeHtml(item.plan_count ?? 0)}</td>
      <td>${escapeHtml(item.review_count ?? 0)}</td>
      <td>${escapeHtml(item.average_plan_effectiveness_score ?? "-")}</td>
      <td>${escapeHtml(item.average_ranking_alignment_score ?? "-")}</td>
      <td>${escapeHtml(item.synthetic_only_rate ?? 0)}%</td>
      <td>${escapeHtml(item.waiver_rate ?? 0)}%</td>
      <td>${escapeHtml(item.force_close_rate ?? 0)}%</td>
    </tr>
  `).join("");
  target.innerHTML = `
    <div class="grid3">
      <div><b>Active Version</b><br>${escapeHtml(summary.active_version_id || "-")}</div>
      <div><b>Adoption Rate</b><br>${escapeHtml(adoption.active_adoption_rate ?? 0)}%</div>
      <div><b>Recommendation</b><br>${escapeHtml(summary.recommendation || "-")}</div>
    </div>
    <div class="grid3">
      <div><b>Plans</b><br>${escapeHtml(summary.observed_plan_count ?? 0)}</div>
      <div><b>Reviews</b><br>${escapeHtml(summary.observed_review_count ?? 0)}</div>
      <div><b>Rollback Recommended</b><br>${summary.rollback_recommended ? "yes" : "-"}</div>
    </div>
    <div class="grid3">
      <div><b>Manual Review</b><br>${escapeHtml(summary.manual_review_count ?? 0)}</div>
      <div><b>Synthetic Review</b><br>${escapeHtml(summary.synthetic_review_count ?? 0)}</div>
      <div><b>Risk Drift</b><br>${escapeHtml((risk.warnings || []).join(", ") || "-")}</div>
    </div>
    <table>
      <thead><tr><th>Version</th><th>Plans</th><th>Reviews</th><th>Effectiveness</th><th>Ranking</th><th>Synthetic</th><th>Waiver</th><th>Force</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='8'>No version metrics.</td></tr>"}</tbody>
    </table>
  `;
}

function renderAcceptanceKb(report = acceptanceKb) {
  const target = $("acceptance-kb");
  if (!target) return;
  if (!report || !report.report_id) {
    target.innerHTML = "<div class='empty'>No acceptance knowledge report yet.</div>";
    return;
  }
  const summary = report.summary || {};
  const issueRows = (report.issue_patterns || []).slice(0, 8).map((item) => `
    <tr>
      <td>${escapeHtml(item.issue_type || "-")}</td>
      <td>${escapeHtml(item.entry_count || 0)}</td>
      <td>${escapeHtml(item.effective_count || 0)}</td>
      <td>${escapeHtml(item.average_effectiveness_score ?? "-")}</td>
      <td>${escapeHtml(item.risk || "-")}</td>
    </tr>
  `).join("");
  const styleRows = (report.style_patterns || []).slice(0, 8).map((item) => `
    <tr>
      <td>${escapeHtml(item.style || "-")}</td>
      <td>${escapeHtml(item.entry_count || 0)}</td>
      <td>${escapeHtml((item.recurring_issues || []).join(", "))}</td>
      <td>${escapeHtml(item.average_effectiveness_score ?? "-")}</td>
      <td>${escapeHtml(item.stability_status || "-")}</td>
    </tr>
  `).join("");
  const entryRows = (report.recommendations || []).slice(0, 6).map((item) => `
    <tr>
      <td>${escapeHtml(item.type || "-")}</td>
      <td>${escapeHtml(item.issue_type || item.style || item.song_id || "-")}</td>
      <td>${escapeHtml(item.reason || "")}</td>
    </tr>
  `).join("");
  const rec = acceptanceKbRecommendation || {};
  target.innerHTML = `
    <div class="summary-grid">
      ${metric("Entries", summary.entry_count || 0)}
      ${metric("Effective", summary.effective_count || 0)}
      ${metric("Mixed", summary.mixed_count || 0)}
      ${metric("Ineffective", summary.ineffective_count || 0)}
      ${metric("Average", summary.average_effectiveness_score ?? "-")}
      ${metric("Stale", report.stale ? "yes" : "-")}
    </div>
    <div class="panel-title subhead"><span>Issue Patterns</span></div>
    <table>
      <thead><tr><th>Issue</th><th>Entries</th><th>Effective</th><th>Score</th><th>Risk</th></tr></thead>
      <tbody>${issueRows || "<tr><td colspan='5'>No issue patterns yet.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Style Patterns</span></div>
    <table>
      <thead><tr><th>Style</th><th>Entries</th><th>Recurring Issues</th><th>Score</th><th>Status</th></tr></thead>
      <tbody>${styleRows || "<tr><td colspan='5'>No style patterns yet.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Recommendation Panel</span></div>
    ${rec.status ? `<pre>${escapeHtml(JSON.stringify(rec, null, 2))}</pre>` : `<table><thead><tr><th>Type</th><th>Target</th><th>Reason</th></tr></thead><tbody>${entryRows || "<tr><td colspan='3'>No KB recommendations yet.</td></tr>"}</tbody></table>`}
  `;
}

function selectedAcceptanceSong() {
  const songId = $("acceptance-song-id")?.value || "";
  return ((acceptanceSongbook || {}).songs || []).find((song) => song.song_id === songId) || null;
}

async function renderAcceptanceDetail(suiteId) {
  const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}`);
  const suite = data.suite || {};
  const cases = data.cases || [];
  const report = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/report`).catch(() => ({ report: {}, summary: {} }));
  const signoff = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/signoff`).catch(() => ({ signoff: {}, summary: {} }));
  const humanPacks = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`).catch(() => ({ packs: [], summary: {} }));
  const humanImports = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/review-imports`).catch(() => ({ imports: [], summary: {} }));
  const analyticsData = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/analytics`).catch(() => ({ analytics: null, summary: {} }));
  const latestHumanPack = (humanPacks.packs || [])[0] || {};
  const latestHumanImport = (humanImports.imports || [])[0] || {};
  const caseRows = cases.map((item) => {
    const health = item.health_summary || {};
    const review = item.review_summary || {};
    return `
      <tr>
        <td>${escapeHtml(item.case_id)}</td>
        <td>${escapeHtml(item.song_id || "-")}</td>
        <td>${escapeHtml(item.name)}</td>
        <td><span class="status ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></td>
        <td>${escapeHtml(health.status || "missing")}</td>
        <td>${escapeHtml(health.audio_status || "-")}</td>
        <td>${escapeHtml(review.status || "missing")}</td>
        <td>${escapeHtml(review.rating ?? "-")}</td>
        <td>
          <button class="secondary acceptance-generate" data-case-id="${escapeHtml(item.case_id)}" type="button">Generate</button>
          <button class="secondary acceptance-health" data-case-id="${escapeHtml(item.case_id)}" type="button">Health</button>
          <a class="button-link secondary" href="/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(item.case_id)}/midi">MIDI</a>
        </td>
      </tr>
    `;
  }).join("");
  $("acceptance-detail").innerHTML = `
    <div class="panel-title subhead"><span>${escapeHtml(suite.name || suite.suite_id)}</span></div>
    <div class="quick-grid">
      ${metric("Status", suite.status || "-")}
      ${metric("Profile", suite.profile_id || "-")}
      ${metric("Songbook", suite.songbook_id || "-")}
      ${metric("Cases", suite.case_count || 0)}
      ${metric("Accepted", suite.accepted_count || 0)}
      ${metric("Report", (report.summary || {}).status || "missing")}
      ${metric("Acceptance", (report.summary || {}).acceptance_status || "missing")}
      ${metric("Signoff", (signoff.summary || {}).status || "not_signed")}
    </div>
    <div class="grid2">
      <label>Regression Song
        <select id="acceptance-song-id">${acceptanceSongOptions()}</select>
      </label>
      <label>Case Title <input id="acceptance-case-title" value="Acceptance Song"></label>
    </div>
    <div class="grid2">
      <label>Style <input id="acceptance-case-style" value="upbeat pop"></label>
      <label>Theme <input id="acceptance-case-theme" value="local acceptance review"></label>
    </div>
    <div class="actions">
      <button id="acceptance-add-case" type="button">Add Case</button>
      <button class="secondary" id="acceptance-build-report" type="button">Build Report</button>
      <button class="secondary" id="acceptance-refresh-suite-analytics" type="button">Refresh Analytics</button>
      <button class="secondary" id="acceptance-signoff" type="button">Signoff</button>
      <button class="secondary" id="acceptance-reset-signoff" type="button">Reset Signoff</button>
    </div>
    <div class="panel-title subhead"><span>Suite Analytics</span></div>
    <div class="quick-grid">
      ${metric("Readiness", (analyticsData.summary || {}).readiness_status || "missing")}
      ${metric("Top Issue", (((analyticsData.analytics || {}).issue_taxonomy || [])[0] || {}).issue_type || "-")}
      ${metric("Recommendations", ((analyticsData.analytics || {}).recommendations || []).length)}
      ${metric("Stale", (analyticsData.analytics || {}).stale ? "yes" : "-")}
    </div>
    <div class="panel-title subhead"><span>Acceptance Diff</span></div>
    <div class="grid2">
      <label>Baseline Suite
        <select id="acceptance-diff-suite"><option value="">select baseline</option>${acceptanceSuiteOptions()}</select>
      </label>
      <label>Diff Status
        <input id="acceptance-diff-status" readonly value="-">
      </label>
    </div>
    <div class="actions"><button class="secondary" id="acceptance-run-diff" type="button">Compare Suites</button></div>
    <pre id="acceptance-diff-result"></pre>
    <div class="panel-title subhead"><span>Human Review Pack</span></div>
    <div class="quick-grid">
      ${metric("Packs", (humanPacks.summary || {}).pack_count || 0)}
      ${metric("Latest Pack", latestHumanPack.pack_id || "-")}
      ${metric("Pack Status", latestHumanPack.status || "-")}
      ${metric("Latest Import", latestHumanImport.import_id || "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="acceptance-create-human-pack" type="button">Create Pack</button>
      <button class="secondary" id="acceptance-zip-human-pack" type="button" ${latestHumanPack.pack_id ? "" : "disabled"}>Build Pack ZIP</button>
      <button class="secondary" id="acceptance-verify-human-pack" type="button" ${latestHumanPack.pack_id ? "" : "disabled"}>Verify Pack</button>
      ${latestHumanPack.pack_id ? `<a class="button-link secondary" href="/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs/${encodeURIComponent(latestHumanPack.pack_id)}/zip">Download Pack</a>` : ""}
    </div>
    <label>Review Response JSON <textarea id="acceptance-human-review-response" placeholder="Paste exported human review response JSON here"></textarea></label>
    <div class="actions"><button class="secondary" id="acceptance-import-human-review" type="button">Import Response</button></div>
    <pre id="acceptance-human-review-result">${escapeHtml(JSON.stringify({ pack: latestHumanPack, import: latestHumanImport }, null, 2))}</pre>
    <div class="panel-title subhead"><span>Cases</span></div>
    <div class="table-wrap">
      ${caseRows ? `<table><thead><tr><th>ID</th><th>Song ID</th><th>Name</th><th>Status</th><th>Health</th><th>Audio</th><th>Review</th><th>Rating</th><th>Actions</th></tr></thead><tbody>${caseRows}</tbody></table>` : "<div class='empty'>No acceptance cases yet.</div>"}
    </div>
    <div class="panel-title subhead"><span>Listening Review</span></div>
    <div class="grid2">
      <label>Case ID <input id="acceptance-review-case-id" value="${escapeHtml((cases[0] || {}).case_id || "")}"></label>
      <label>Rating <input id="acceptance-review-rating" type="number" min="1" max="5" value="4"></label>
    </div>
    <div class="grid2">
      <label>Status
        <select id="acceptance-review-status"><option value="accepted">accepted</option><option value="needs_fix">needs_fix</option><option value="rejected">rejected</option><option value="waived">waived</option></select>
      </label>
      <label>Audio Mode <input id="acceptance-review-audio-mode" value="midi"></label>
    </div>
    <label style="display:flex;gap:8px;align-items:center;"><input id="acceptance-review-playback" type="checkbox" style="width:auto;"> Playback Confirmed</label>
    <label>Notes <textarea id="acceptance-review-notes">I listened to the generated MIDI and the structure is acceptable for this review.</textarea></label>
    <div class="actions"><button id="acceptance-save-review" type="button">Save Review</button></div>
    <pre>${escapeHtml(JSON.stringify(report.report || {}, null, 2))}</pre>
  `;
  wireAcceptanceActions(suiteId);
}

function wireAcceptanceActions(suiteId) {
  $("acceptance-song-id")?.addEventListener("change", () => {
    const song = selectedAcceptanceSong();
    if (!song) return;
    $("acceptance-case-title").value = song.title || "Acceptance Song";
    $("acceptance-case-style").value = song.style || "pop";
    $("acceptance-case-theme").value = song.theme || "acceptance review";
  });
  $("acceptance-add-case")?.addEventListener("click", async () => {
    const song = selectedAcceptanceSong();
    const request = song && song.request ? song.request : {
      title: $("acceptance-case-title").value.trim() || "Acceptance Song",
      language: "English",
      style: $("acceptance-case-style").value.trim() || "pop",
      theme: $("acceptance-case-theme").value.trim() || "acceptance review",
      duration_seconds: 90,
    };
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: (song && song.title) || $("acceptance-case-style").value.trim() || "acceptance case",
        source_type: song ? "regression_songbook" : "generated_request",
        song_id: song ? song.song_id : undefined,
        songbook_id: song ? (acceptanceSongbook || {}).songbook_id : undefined,
        songbook_version: song ? (acceptanceSongbook || {}).songbook_version : undefined,
        expectations: song ? (song.expectations || {}) : {},
        request,
      }),
    });
    await loadAcceptanceSuites();
  });
  document.querySelectorAll(".acceptance-generate").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(button.dataset.caseId)}/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ render_audio: "auto" }) });
    await loadAcceptanceSuites();
  }));
  document.querySelectorAll(".acceptance-health").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(button.dataset.caseId)}/health`, { method: "POST" });
    await loadAcceptanceSuites();
  }));
  $("acceptance-save-review")?.addEventListener("click", async () => {
    const caseId = $("acceptance-review-case-id").value.trim();
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(caseId)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rating: Number($("acceptance-review-rating").value || 4),
        status: $("acceptance-review-status").value,
        playback_confirmed: $("acceptance-review-playback").checked,
        audio_mode: $("acceptance-review-audio-mode").value.trim() || "midi",
        notes: $("acceptance-review-notes").value,
      }),
    });
    await loadAcceptanceSuites();
  });
  $("acceptance-build-report")?.addEventListener("click", async () => {
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/report`, { method: "POST" });
    await loadAcceptanceSuites();
  });
  $("acceptance-refresh-suite-analytics")?.addEventListener("click", async () => {
    const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/analytics/refresh`, { method: "POST" });
    acceptanceAnalytics = data.analytics || acceptanceAnalytics;
    renderAcceptanceAnalytics(acceptanceAnalytics);
    await loadAcceptanceSuites();
  });
  $("acceptance-run-diff")?.addEventListener("click", async () => {
    const otherSuiteId = $("acceptance-diff-suite").value;
    if (!otherSuiteId) return;
    const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/diff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ other_suite_id: otherSuiteId }),
    });
    $("acceptance-diff-status").value = (data.diff || {}).status || "-";
    $("acceptance-diff-result").textContent = JSON.stringify(data.diff || {}, null, 2);
  });
  $("acceptance-create-human-pack")?.addEventListener("click", async () => {
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    await loadAcceptanceSuites();
  });
  $("acceptance-zip-human-pack")?.addEventListener("click", async () => {
    const packId = ((await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`)).packs || [])[0]?.pack_id;
    if (!packId) return;
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs/${encodeURIComponent(packId)}/zip`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    await loadAcceptanceSuites();
  });
  $("acceptance-verify-human-pack")?.addEventListener("click", async () => {
    const packId = ((await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`)).packs || [])[0]?.pack_id;
    if (!packId) return;
    const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs/${encodeURIComponent(packId)}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true }) });
    $("acceptance-human-review-result").textContent = JSON.stringify(data.report || data, null, 2);
  });
  $("acceptance-import-human-review")?.addEventListener("click", async () => {
    const raw = $("acceptance-human-review-response").value.trim();
    if (!raw) return;
    const response = JSON.parse(raw);
    const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/review-imports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response }) });
    $("acceptance-human-review-result").textContent = JSON.stringify(data.import || data, null, 2);
    await loadAcceptanceSuites();
  });
  $("acceptance-signoff")?.addEventListener("click", async () => {
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/signoff`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ signed_by: "developer" }) });
    await loadAcceptanceSuites();
  });
  $("acceptance-reset-signoff")?.addEventListener("click", async () => {
    await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/signoff/reset`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason: "review update" }) });
    await loadAcceptanceSuites();
  });
}

Object.assign(globalThis, { applyLibraryPreview, previewSelectedContextPack, renderContextPackPreview, loadAcceptanceSuites, loadAcceptanceReferenceData, loadAcceptanceAnalytics, loadAcceptanceFixSprints, loadAcceptanceFixPlans, loadAcceptanceFixPlanReview, loadPlanningSimulations, loadPlanningImpact, loadAcceptanceKb, renderAcceptanceSuites, renderAcceptanceReferenceData, acceptanceSongOptions, acceptanceSuiteOptions, renderAcceptanceAnalytics, renderAcceptanceFixSprints, renderAcceptanceFixPlans, renderAcceptanceFixPlanReview, renderPlanningSimulations, renderPlanningImpact, renderAcceptanceKb, selectedAcceptanceSong, renderAcceptanceDetail, wireAcceptanceActions });

export { applyLibraryPreview, previewSelectedContextPack, renderContextPackPreview, loadAcceptanceSuites, loadAcceptanceReferenceData, loadAcceptanceAnalytics, loadAcceptanceFixSprints, loadAcceptanceFixPlans, loadAcceptanceFixPlanReview, loadPlanningSimulations, loadPlanningImpact, loadAcceptanceKb, renderAcceptanceSuites, renderAcceptanceReferenceData, acceptanceSongOptions, acceptanceSuiteOptions, renderAcceptanceAnalytics, renderAcceptanceFixSprints, renderAcceptanceFixPlans, renderAcceptanceFixPlanReview, renderPlanningSimulations, renderPlanningImpact, renderAcceptanceKb, selectedAcceptanceSong, renderAcceptanceDetail, wireAcceptanceActions };
