$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  accessToken = $("auth-token").value.trim();
  sessionStorage.setItem("musicforge_access_token", accessToken);
  $("auth-token").value = "";
  try {
    await init();
  } catch (err) {
    showAuthLock(err.message);
  }
});




























































$("song-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const job = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formPayload()),
    });
    selectedJobId = job.job_id;
    activeTab = "summary";
    await loadJobs();
  } catch (err) {
    alert(err.message);
  }
});
$("reset-form").addEventListener("click", () => fillForm(template.defaults));
$("song-suggest-context").addEventListener("click", async () => {
  try {
    const data = await api("/api/library/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: "song_request",
        goal: "generate",
        song_request: formPayload(),
      }),
    });
    applyLibraryPreview(data.recommendation.context_pack_preview || {});
    renderLibraryResults([...(data.recommendation.asset_results || []), ...(data.recommendation.reference_results || [])]);
    $("song-context-suggestion").textContent = "context suggested";
  } catch (err) {
    $("song-context-suggestion").textContent = err.message;
  }
});
$("refresh").addEventListener("click", loadJobs);
$("include-hidden").addEventListener("change", async () => {
  includeHidden = $("include-hidden").checked;
  await loadJobs();
});
$("refresh-projects").addEventListener("click", loadProjects);
$("include-hidden-projects").addEventListener("change", async () => {
  includeHiddenProjects = $("include-hidden-projects").checked;
  await loadProjects();
});
["project-search", "project-status-filter", "project-variant-filter"].forEach((id) => {
  $(id).addEventListener("change", loadProjects);
});
$("project-search").addEventListener("input", debounce(loadProjects, 250));
$("clear-project-filters").addEventListener("click", async () => {
  $("project-search").value = "";
  $("project-status-filter").value = "";
  $("project-variant-filter").value = "";
  $("include-hidden-projects").checked = false;
  includeHiddenProjects = false;
  await loadProjects();
});
$("project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectPayload()),
    });
    selectedProjectId = data.project.project_id;
    activeProjectTab = "versions";
    $("project-message").textContent = "created";
    await loadProjects();
  } catch (err) {
    $("project-message").textContent = err.message;
  }
});
$("refresh-releases").addEventListener("click", loadReleases);
$("include-hidden-releases").addEventListener("change", async () => {
  includeHiddenReleases = $("include-hidden-releases").checked;
  await loadReleases();
});
$("release-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/releases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(releasePayload()),
    });
    selectedReleaseId = data.release.release_id;
    $("release-message").textContent = "created";
    await loadReleases();
  } catch (err) {
    $("release-message").textContent = err.message;
  }
});
$("refresh-portfolio-audits").addEventListener("click", loadPortfolioAudits);
$("include-archived-portfolio-audits").addEventListener("change", async () => {
  includeArchivedPortfolioAudits = $("include-archived-portfolio-audits").checked;
  await loadPortfolioAudits();
});
$("portfolio-audit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/release-portfolio-audits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(portfolioAuditPayload()),
    });
    selectedPortfolioAuditId = (data.portfolio || {}).portfolio_id || null;
    $("portfolio-audit-message").textContent = "created";
    await loadPortfolioAudits();
  } catch (err) {
    $("portfolio-audit-message").textContent = err.message;
  }
});
$("refresh-acceptance").addEventListener("click", loadAcceptanceSuites);
$("acceptance-refresh-analytics").addEventListener("click", async () => {
  try {
    const data = await api("/api/acceptance/analytics/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: "global" }) });
    acceptanceAnalytics = data.analytics || null;
    renderAcceptanceAnalytics();
  } catch (err) {
    $("acceptance-analytics").innerHTML = `<div class="empty">${escapeHtml(err.message)}</div>`;
  }
});
$("acceptance-refresh-fix-sprints").addEventListener("click", loadAcceptanceFixSprints);
$("acceptance-fix-plan-refresh").addEventListener("click", loadAcceptanceFixPlans);
$("acceptance-fix-plan-create").addEventListener("click", async () => {
  try {
    if (!acceptanceAnalytics || !acceptanceAnalytics.report_id) throw new Error("Refresh Acceptance Analytics first.");
    const data = await api("/api/acceptance/fix-plans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        analytics_report_id: acceptanceAnalytics.report_id,
        kb_report_id: (acceptanceKb || {}).report_id || null,
        max_items: Number($("acceptance-fix-plan-max-items").value || 20),
        include_hidden_kb: $("acceptance-fix-plan-hidden").checked,
      }),
    });
    $("acceptance-fix-plan-id").value = (data.fix_plan || {}).plan_id || "";
    await loadAcceptanceFixPlans();
  } catch (err) {
    $("acceptance-fix-plans").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("acceptance-fix-plan-create-sprint").addEventListener("click", async () => {
  try {
    const planId = $("acceptance-fix-plan-id").value.trim() || ((acceptanceFixPlans[0] || {}).plan_id || "");
    if (!planId) throw new Error("Create or select a Fix Plan first.");
    await api(`/api/acceptance/fix-plans/${encodeURIComponent(planId)}/create-fix-sprint`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Knowledge-assisted Fix Sprint" }) });
    await loadAcceptanceFixPlans();
    await loadAcceptanceFixSprints();
  } catch (err) {
    $("acceptance-fix-plans").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("acceptance-fix-plan-review-refresh").addEventListener("click", async () => {
  try {
    const planId = $("acceptance-fix-plan-id").value.trim() || ((acceptanceFixPlans[0] || {}).plan_id || "");
    if (!planId) throw new Error("Select a Fix Plan first.");
    const data = await api(`/api/acceptance/fix-plans/${encodeURIComponent(planId)}/outcome-review/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    acceptanceFixPlanReview = data.outcome_review || null;
    renderAcceptanceFixPlanReview();
  } catch (err) {
    $("acceptance-fix-plan-review").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("planning-ruleset-create").addEventListener("click", async () => {
  try {
    await api("/api/acceptance/planning-rulesets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ template: $("planning-ruleset-template").value }),
    });
    await loadPlanningSimulations();
  } catch (err) {
    $("planning-rule-simulation").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("planning-simulation-run").addEventListener("click", async () => {
  try {
    const ruleset = planningRuleSets[0];
    if (!ruleset) throw new Error("Create a Planning Rule Set first.");
    const reviewId = (acceptanceFixPlanReview || {}).review_id;
    if (!reviewId) throw new Error("Refresh an Outcome Review first.");
    await api("/api/acceptance/planning-simulations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ruleset_id: ruleset.ruleset_id, review_ids: [reviewId], include_warning_reviews: true }),
    });
    await loadPlanningSimulations();
  } catch (err) {
    $("planning-rule-simulation").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("planning-simulation-refresh").addEventListener("click", loadPlanningSimulations);
$("planning-governance-refresh").addEventListener("click", loadPlanningGovernance);
$("planning-impact-refresh").addEventListener("click", async () => {
  try {
    const data = await api("/api/acceptance/planning-rule-impact/reports", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: { type: "global" }, include_legacy: true, include_superseded: true }) });
    planningImpact = data.impact_report || null;
    await loadPlanningImpact();
  } catch (err) {
    $("planning-rule-impact").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("planning-governance-create").addEventListener("click", async () => {
  try {
    const simulation = planningSimulations[0];
    if (!simulation) throw new Error("Run a Planning Rule Simulation first.");
    await api("/api/acceptance/planning-rule-governance/promotions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ruleset_id: simulation.ruleset_id, simulation_id: simulation.simulation_id, note: "Studio promotion request" }),
    });
    await loadPlanningGovernance();
  } catch (err) {
    $("planning-rule-governance").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("planning-governance-approve").addEventListener("click", async () => {
  try {
    const promotion = planningPromotions.find((item) => item.status === "pending") || planningPromotions[0];
    if (!promotion) throw new Error("Create a Planning Rule Promotion first.");
    await api(`/api/acceptance/planning-rule-governance/promotions/${encodeURIComponent(promotion.promotion_id)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved_by: "studio", approval_note: "Approved in Studio" }),
    });
    await loadPlanningGovernance();
  } catch (err) {
    $("planning-rule-governance").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("planning-governance-promote").addEventListener("click", async () => {
  try {
    const promotion = planningPromotions.find((item) => item.status === "approved") || planningPromotions[0];
    if (!promotion) throw new Error("Approve a Planning Rule Promotion first.");
    await api(`/api/acceptance/planning-rule-governance/promotions/${encodeURIComponent(promotion.promotion_id)}/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ promoted_by: "studio" }),
    });
    await loadPlanningGovernance();
  } catch (err) {
    $("planning-rule-governance").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("acceptance-kb-refresh").addEventListener("click", async () => {
  try {
    const data = await api("/api/acceptance/kb/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: "global" }) });
    acceptanceKb = data.knowledge_report || null;
    acceptanceKbRecommendation = null;
    renderAcceptanceKb();
  } catch (err) {
    $("acceptance-kb").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("acceptance-kb-recommend").addEventListener("click", async () => {
  try {
    const payload = {
      issue_types: [$("acceptance-kb-issue-type").value.trim()].filter(Boolean),
      style: $("acceptance-kb-style").value.trim(),
      song_id: $("acceptance-kb-song-id").value.trim(),
    };
    const data = await api("/api/acceptance/kb/recommend", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    acceptanceKbRecommendation = data.recommendation || null;
    renderAcceptanceKb();
  } catch (err) {
    $("acceptance-kb").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("acceptance-create-fix-sprint").addEventListener("click", async () => {
  try {
    if (!acceptanceAnalytics || !acceptanceAnalytics.report_id) throw new Error("Refresh Acceptance Analytics first.");
    await api("/api/acceptance/fix-sprints", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analytics_report_id: acceptanceAnalytics.report_id, name: "Acceptance-driven Fix Sprint" }),
    });
    await loadAcceptanceFixSprints();
  } catch (err) {
    $("acceptance-fix-sprints").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
});
$("acceptance-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/acceptance/suites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("acceptance-name").value.trim() || "Music Acceptance Suite",
        mode: $("acceptance-mode").value,
        profile_id: $("acceptance-profile").value,
        min_rating: Number($("acceptance-min-rating").value || 3),
      }),
    });
    selectedAcceptanceSuiteId = data.suite.suite_id;
    $("acceptance-message").textContent = "created";
    await loadAcceptanceSuites();
  } catch (err) {
    $("acceptance-message").textContent = err.message;
  }
});
$("refresh-assets").addEventListener("click", loadAssets);
$("include-hidden-assets").addEventListener("change", async () => {
  includeHiddenAssets = $("include-hidden-assets").checked;
  await loadAssets();
});
["asset-type-filter", "asset-favorite-filter"].forEach((id) => {
  $(id).addEventListener("change", loadAssets);
});
["asset-search", "asset-tag-filter"].forEach((id) => {
  $(id).addEventListener("input", debounce(loadAssets, 250));
});
$("refresh-references").addEventListener("click", loadReferences);
$("include-hidden-references").addEventListener("change", async () => {
  includeHiddenReferences = $("include-hidden-references").checked;
  await loadReferences();
});
["reference-type-filter", "reference-favorite-filter"].forEach((id) => {
  $(id).addEventListener("change", loadReferences);
});
["reference-search", "reference-tag-filter"].forEach((id) => {
  $(id).addEventListener("input", debounce(loadReferences, 250));
});
$("library-search").addEventListener("click", searchLibrary);
$("library-recommend").addEventListener("click", recommendLibrary);
$("library-rebuild").addEventListener("click", rebuildLibrary);
$("context-pack-refresh").addEventListener("click", loadContextPacks);
$("context-pack-save-selection").addEventListener("click", saveSelectedContextPack);
$("context-pack-apply-preview").addEventListener("click", previewSelectedContextPack);
$("context-pack-select").addEventListener("change", () => {
  $("song-context-pack").value = $("context-pack-select").value;
});
$("editor-template-refresh").addEventListener("click", loadEditorTemplates);
$("reference-import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = await referenceImportPayload();
    const data = await api("/api/references/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    selectedReferenceId = data.reference.reference_id;
    $("reference-message").textContent = data.duplicate ? "duplicate" : "imported";
    $("reference-file").value = "";
    await loadReferences();
  } catch (err) {
    $("reference-message").textContent = err.message;
  }
});
$("refresh-batches").addEventListener("click", loadBatches);
$("include-hidden-batches").addEventListener("change", async () => {
  includeHiddenBatches = $("include-hidden-batches").checked;
  await loadBatches();
});
$("batch-csv-file").addEventListener("change", async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  $("batch-csv-text").value = await file.text();
});
$("batch-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/batches/import-csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(batchPayload()),
    });
    selectedBatchId = data.batch.batch_id;
    $("batch-message").textContent = "imported";
    await loadBatches();
  } catch (err) {
    $("batch-message").textContent = err.message;
  }
});
$("provider-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/provider", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(providerPayload()),
    });
    applyProvider(data);
    $("provider-message").textContent = "saved";
    $("provider-api-key").value = "";
  } catch (err) {
    $("provider-message").textContent = err.message;
  }
});
$("provider-reset").addEventListener("click", async () => {
  if (!confirm("Reset provider settings?")) return;
  try {
    await api("/api/provider/reset", { method: "POST" });
    await loadProvider();
    $("provider-message").textContent = "reset";
  } catch (err) {
    $("provider-message").textContent = err.message;
  }
});
$("provider-test").addEventListener("click", async () => {
  try {
    const data = await api("/api/provider/test", { method: "POST" });
    $("provider-message").textContent = data.message || "test ok";
  } catch (err) {
    $("provider-message").textContent = err.message;
  }
});
$("prompt-template-select").addEventListener("change", () => {
  applyPromptTemplateSelection();
});
$("prompt-template-save").addEventListener("click", async () => {
  const templateId = $("prompt-template-select").value || "provider-edit-intent";
  try {
    await api(`/api/prompt-templates/${encodeURIComponent(templateId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        system_prompt: $("prompt-template-system").value,
        user_prompt: $("prompt-template-user").value,
      }),
    });
    $("prompt-template-message").textContent = "saved";
    await loadPromptTemplates();
  } catch (err) {
    $("prompt-template-message").textContent = err.message;
  }
});
$("prompt-template-reset").addEventListener("click", async () => {
  const templateId = $("prompt-template-select").value || "provider-edit-intent";
  try {
    await api(`/api/prompt-templates/${encodeURIComponent(templateId)}/reset`, { method: "POST" });
    $("prompt-template-message").textContent = "reset";
    await loadPromptTemplates();
  } catch (err) {
    $("prompt-template-message").textContent = err.message;
  }
});
$("renderer-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/api/renderer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rendererPayload()),
    });
    applyRenderer(data);
    $("renderer-message").textContent = "saved";
  } catch (err) {
    $("renderer-message").textContent = err.message;
  }
});
$("renderer-reset").addEventListener("click", async () => {
  if (!confirm("Reset renderer settings?")) return;
  try {
    await api("/api/renderer/reset", { method: "POST" });
    await loadRenderer();
    $("renderer-message").textContent = "reset";
  } catch (err) {
    $("renderer-message").textContent = err.message;
  }
});
$("renderer-test").addEventListener("click", async () => {
  try {
    const data = await api("/api/renderer/test", { method: "POST" });
    $("renderer-message").textContent = data.message || "test ok";
  } catch (err) {
    $("renderer-message").textContent = err.message;
  }
});
$("audio-lab-detect").addEventListener("click", async () => {
  await showAudioLabResult("/api/audio-lab/environment/detect", { method: "POST" });
});
$("audio-lab-test-profile").addEventListener("click", async () => {
  await showAudioLabResult("/api/audio-lab/environment/test-profile", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile_id: "default" }) });
});
$("audio-lab-smoke").addEventListener("click", async () => {
  await showAudioLabResult("/api/audio-lab/smoke-runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cases: 1, render_audio: "auto" }) });
});
$("audio-lab-session-create").addEventListener("click", async () => {
  $("audio-lab-summary").textContent = "Create a session from a smoke run via /api/audio-lab/listening-sessions.";
});
$("audio-lab-compare-create").addEventListener("click", async () => {
  $("audio-lab-summary").textContent = "Create A/B comparisons via /api/audio-lab/comparisons.";
});
$("audio-fix-sprint-list").addEventListener("click", async () => {
  await showAudioFixSprintResult("/api/audio-fix-sprints", { method: "GET" });
});
$("audio-fix-sprint-create").addEventListener("click", async () => {
  const sessionId = $("audio-fix-sprint-session-id").value.trim();
  if (!sessionId) {
    $("audio-fix-sprint-status").textContent = "missing session";
    return;
  }
  await showAudioFixSprintResult("/api/audio-fix-sprints", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ from_session: sessionId }) });
});
$("audio-campaign-list").addEventListener("click", async () => {
  await showAudioCampaignResult("/api/audio-campaigns", { method: "GET" });
});
$("audio-campaign-create").addEventListener("click", async () => {
  const sessionId = $("audio-campaign-session-id").value.trim();
  if (!sessionId) {
    $("audio-campaign-status").textContent = "missing session";
    return;
  }
  await showAudioCampaignResult("/api/audio-campaigns", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ from_session: sessionId }) });
});
$("audio-campaign-plan-release").addEventListener("click", async () => {
  const releaseId = $("audio-campaign-release-id").value.trim();
  if (!releaseId) {
    $("audio-campaign-status").textContent = "missing release";
    return;
  }
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-plan/refresh`, { method: "POST" });
});
$("audio-campaign-preflight-release").addEventListener("click", async () => {
  const releaseId = $("audio-campaign-release-id").value.trim();
  if (!releaseId) {
    $("audio-campaign-status").textContent = "missing release";
    return;
  }
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-plan/preflight`, { method: "POST" });
});
$("audio-campaign-create-from-release").addEventListener("click", async () => {
  const releaseId = $("audio-campaign-release-id").value.trim();
  if (!releaseId) {
    $("audio-campaign-status").textContent = "missing release";
    return;
  }
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-plan/create`, { method: "POST" });
});
$("audio-campaign-release-status").addEventListener("click", async () => {
  const releaseId = $("audio-campaign-release-id").value.trim();
  if (!releaseId) {
    $("audio-campaign-status").textContent = "missing release";
    return;
  }
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-plan/status`, { method: "GET" });
});
$("audio-campaign-release-link").addEventListener("click", async () => {
  const releaseId = $("audio-campaign-release-id").value.trim();
  const campaignId = $("audio-campaign-id").value.trim();
  if (!releaseId || !campaignId) {
    $("audio-campaign-status").textContent = "missing release or campaign";
    return;
  }
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-plan/link`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ campaign_id: campaignId }) });
});
$("audio-campaign-governance").addEventListener("click", async () => {
  const campaignId = $("audio-campaign-id").value.trim();
  if (!campaignId) {
    $("audio-campaign-status").textContent = "missing campaign";
    return;
  }
  await showAudioCampaignResult(`/api/audio-campaigns/${encodeURIComponent(campaignId)}/governance`, { method: "POST" });
});
$("audio-campaign-archive-zip").addEventListener("click", async () => {
  const campaignId = $("audio-campaign-id").value.trim();
  if (!campaignId) {
    $("audio-campaign-status").textContent = "missing campaign";
    return;
  }
  await showAudioCampaignResult(`/api/audio-campaigns/${encodeURIComponent(campaignId)}/archive/zip`, { method: "POST" });
});
$("audio-campaign-verify-archive").addEventListener("click", async () => {
  const campaignId = $("audio-campaign-id").value.trim();
  if (!campaignId) {
    $("audio-campaign-status").textContent = "missing campaign";
    return;
  }
  await showAudioCampaignResult(`/api/audio-campaigns/${encodeURIComponent(campaignId)}/archive/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true }) });
});








$("audio-campaign-remediation-plan").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-remediation/refresh`, { method: "POST" });
});
$("audio-campaign-remediation-run-safe").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-remediation/run-safe`, { method: "POST" });
});
$("audio-campaign-remediation-closeout").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-remediation/closeout`, { method: "POST" });
});
$("audio-campaign-remediation-zip").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-remediation/zip`, { method: "POST" });
});
$("audio-campaign-remediation-verify").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-campaign-remediation/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_passed: true }) });
});
$("release-audio-certification-refresh").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-certification/refresh`, { method: "POST" });
});
$("release-audio-certification-signoff").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-certification/signoff`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ signed_by: "studio-user", role: "developer" }) });
});
$("release-audio-certification-zip").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-certification/zip`, { method: "POST" });
});
$("release-audio-certification-verify").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-certification/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_passed: true, require_signed: true, require_real_audio: true, require_manual_review: true, require_remediation_when_needed: true }) });
});
$("release-audio-timeline-refresh").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-timelines/refresh`, { method: "POST" });
});
$("release-audio-timeline-signoff").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  const refreshed = await api(`/api/releases/${encodeURIComponent(releaseId)}/audio-timelines/refresh`, { method: "POST" });
  const timelineId = refreshed.timeline_id || (refreshed.report && refreshed.report.timeline_id);
  if (!timelineId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-timelines/${encodeURIComponent(timelineId)}/signoff`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ signed_by: "studio-user", role: "developer" }) });
});
$("release-audio-timeline-zip").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  const current = await api(`/api/releases/${encodeURIComponent(releaseId)}/audio-timelines/current`);
  const timelineId = current.timeline_id || (current.report && current.report.timeline_id);
  if (!timelineId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-timelines/${encodeURIComponent(timelineId)}/zip`, { method: "POST" });
});
$("release-audio-timeline-verify").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  const current = await api(`/api/releases/${encodeURIComponent(releaseId)}/audio-timelines/current`);
  const timelineId = current.timeline_id || (current.report && current.report.timeline_id);
  if (!timelineId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-timelines/${encodeURIComponent(timelineId)}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_passed: true, require_signed: true, require_real_audio: true, require_manual_review: true, require_current_certification: true }) });
});
$("release-audio-regression-status").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression`);
});
$("release-audio-regression-refresh").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression/refresh`, { method: "POST" });
});
$("release-audio-regression-signoff").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression/signoff`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ signed_by: "studio-user", role: "developer" }) });
});
$("release-audio-regression-zip").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression/zip`, { method: "POST" });
});
$("release-audio-regression-verify").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_passed: true, require_signed: true, require_current: true, require_baseline_current: true }) });
});
$("release-audio-baseline-list").addEventListener("click", async () => {
  await showAudioCampaignResult(`/api/audio-baselines`);
});
$("release-audio-regression-response-create").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression-response/create`, { method: "POST" });
});
$("release-audio-regression-response-run-safe").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression-response/run-safe`, { method: "POST" });
});
$("release-audio-regression-response-signoff").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression-response/signoff`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ signed_by: "studio-user", role: "developer" }) });
});
$("release-audio-regression-response-verify").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-regression-response/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_closed: true, require_signed: true, require_regression_current: true }) });
});
$("release-audio-quality-observatory-list").addEventListener("click", async () => {
  await showAudioCampaignResult(`/api/audio-quality-observatories`);
});
$("release-audio-quality-observatory-create").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  const body = releaseId ? { release_ids: [releaseId] } : {};
  await showAudioCampaignResult(`/api/audio-quality-observatories`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
});
$("release-audio-quality-observatory-refresh").addEventListener("click", async () => {
  const id = prompt("Observatory id", "aqo-000001");
  if (!id) return;
  await showAudioCampaignResult(`/api/audio-quality-observatories/${encodeURIComponent(id)}/refresh`, { method: "POST" });
});
$("release-audio-quality-observatory-verify").addEventListener("click", async () => {
  const id = prompt("Observatory id", "aqo-000001");
  if (!id) return;
  await showAudioCampaignResult(`/api/audio-quality-observatories/${encodeURIComponent(id)}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_current_evidence: true, require_no_critical_risk: true }) });
});
$("release-audio-quality-action-list").addEventListener("click", async () => {
  await showAudioCampaignResult(`/api/audio-quality-actions`);
});
$("release-audio-quality-action-create").addEventListener("click", async () => {
  const id = prompt("Observatory id", "aqo-000001");
  if (!id) return;
  await showAudioCampaignResult(`/api/audio-quality-actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observatory_id: id }) });
});
$("release-audio-quality-action-run-safe").addEventListener("click", async () => {
  const id = prompt("Action queue id", "aqa-000001");
  if (!id) return;
  await showAudioCampaignResult(`/api/audio-quality-actions/${encodeURIComponent(id)}/run-safe`, { method: "POST" });
});
$("release-audio-quality-action-verify").addEventListener("click", async () => {
  const id = prompt("Action queue id", "aqa-000001");
  if (!id) return;
  await showAudioCampaignResult(`/api/audio-quality-actions/${encodeURIComponent(id)}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_current_observatory: true }) });
});
$("release-audio-command-center-refresh").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-command-center/refresh`, { method: "POST" });
});
$("release-audio-command-center-runbook").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-command-center/runbook`, { method: "POST" });
});
$("release-audio-command-center-run-safe").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-command-center/run-safe`, { method: "POST" });
});
$("release-audio-command-center-zip").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-command-center/zip`, { method: "POST" });
});
$("release-audio-command-center-verify").addEventListener("click", async () => {
  const releaseId = audioCampaignReleaseId();
  if (!releaseId) return;
  await showAudioCampaignResult(`/api/releases/${encodeURIComponent(releaseId)}/audio-command-center/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true, require_ready: true }) });
});
