async function loadPortfolioAudits() {
  try {
    const data = await api(includeArchivedPortfolioAudits ? "/api/release-portfolio-audits?include_archived=1" : "/api/release-portfolio-audits");
    portfolioAudits = data.portfolios || [];
    if (selectedPortfolioAuditId && !portfolioAudits.some((portfolio) => portfolio.portfolio_id === selectedPortfolioAuditId)) {
      selectedPortfolioAuditId = null;
      $("portfolio-audit-detail").innerHTML = "<div class='empty'>Select or create a Portfolio Audit.</div>";
    }
    renderPortfolioAudits();
    if (selectedPortfolioAuditId) await renderPortfolioAuditDetail(selectedPortfolioAuditId);
  } catch (err) {
    $("portfolio-audit-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

async function loadPlanningGovernance() {
  try {
    const [activeData, promotionsData, versionsData] = await Promise.all([
      api("/api/acceptance/planning-rule-governance/active"),
      api("/api/acceptance/planning-rule-governance/promotions"),
      api("/api/acceptance/planning-rule-governance/versions"),
    ]);
    planningGovernance = activeData || null;
    planningPromotions = promotionsData.promotions || [];
    planningVersions = versionsData.versions || [];
  } catch (err) {
    planningGovernance = null;
    planningPromotions = [];
    planningVersions = [];
  }
  renderPlanningGovernance();
}

function portfolioAuditPayload() {
  const releaseIds = $("portfolio-audit-release-ids").value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
  const payload = {
    name: $("portfolio-audit-name").value.trim() || "Release Portfolio Audit",
    release_ids: releaseIds,
    include_hidden: $("portfolio-audit-include-hidden-releases").checked,
    include_archived: $("portfolio-audit-include-archived-releases").checked,
    require_reviewer_packs: $("portfolio-audit-require-reviewer-packs").checked,
    require_audit: $("portfolio-audit-require-audit").checked,
    require_archive: $("portfolio-audit-require-archive").checked,
  };
  const maxReleases = Number($("portfolio-audit-max-releases").value || 0);
  if (maxReleases > 0) payload.max_releases = maxReleases;
  return payload;
}

function renderPortfolioAudits() {
  const list = $("portfolio-audit-list");
  if (!portfolioAudits.length) {
    list.innerHTML = "<div class='empty'>No Portfolio Audits yet.</div>";
    return;
  }
  const rows = portfolioAudits.map((portfolio) => `
    <tr class="${portfolio.portfolio_id === selectedPortfolioAuditId ? "active" : ""}">
      <td><button class="secondary portfolio-audit-open" data-portfolio-id="${escapeHtml(portfolio.portfolio_id)}" type="button">Open</button></td>
      <td>${escapeHtml(portfolio.name || portfolio.portfolio_id)}</td>
      <td><span class="status ${escapeHtml(portfolio.status || "")}">${escapeHtml(portfolio.status || "-")}</span></td>
      <td>${escapeHtml(portfolio.source_hash ? "current" : "draft")}</td>
      <td>${escapeHtml(portfolio.latest_export_manifest_hash ? "built" : "missing")}</td>
    </tr>
  `).join("");
  list.innerHTML = `
    <table>
      <thead><tr><th></th><th>Name</th><th>Status</th><th>Source</th><th>Export</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  list.querySelectorAll(".portfolio-audit-open").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedPortfolioAuditId = button.dataset.portfolioId;
      renderPortfolioAudits();
      await renderPortfolioAuditDetail(selectedPortfolioAuditId);
    });
  });
}

async function renderPortfolioAuditDetail(portfolioId) {
  const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}`);
  const portfolio = data.portfolio || {};
  let reportData = { report: data.report || {}, summary: data.summary || {} };
  let trendData = { trend_report: {}, summary: {} };
  let riskData = { risk_register: {}, summary: {} };
  try { reportData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/report`); } catch (err) {}
  try { trendData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/trends`); } catch (err) {}
  try { riskData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/risks`); } catch (err) {}
  let governanceData = { queues: [], summary: {} };
  try { governanceData = await api(`/api/release-portfolio-governance-queues?portfolio_id=${encodeURIComponent(portfolioId)}`); } catch (err) {}
  let governanceAuditData = { report: {}, summary: {} };
  try { governanceAuditData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit`); } catch (err) {}
  let governanceReviewerData = { report: {}, summary: {} };
  try { governanceReviewerData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack`); } catch (err) {}
  let governanceFinalBoardData = { report: {}, summary: {}, signoff_summary: {} };
  try { governanceFinalBoardData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board`); } catch (err) {}
  let governanceEvidenceVaultData = { report: {}, summary: {} };
  try { governanceEvidenceVaultData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault`); } catch (err) {}
  let governanceAttestationData = { report: {}, summary: {}, certificate: {} };
  try { governanceAttestationData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation`); } catch (err) {}
  let governanceAttestationRegistryData = { registry: {}, report: {}, summary: {} };
  try { governanceAttestationRegistryData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry`); } catch (err) {}
  let governanceAttestationPortalData = { report: {}, summary: {} };
  try { governanceAttestationPortalData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal`); } catch (err) {}
  let governanceAttestationPortalReviewData = { review_pack: {}, summary: {}, responses: [] };
  try { governanceAttestationPortalReviewData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review`); } catch (err) {}
  let governanceAttestationAcceptedEvidenceData = { accepted_evidence: {}, summary: {}, verification: {} };
  try { governanceAttestationAcceptedEvidenceData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence`); } catch (err) {}
  let governanceAttestationTransparencyData = { feed: {}, summary: {}, verification: {} };
  try { governanceAttestationTransparencyData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency`); } catch (err) {}
  let governanceAttestationTransparencyAcknowledgementData = { pack: {}, summary: {}, evidence_summary: {}, responses: [] };
  try { governanceAttestationTransparencyAcknowledgementData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement`); } catch (err) {}
  const report = reportData.report || {};
  const summary = report.summary || reportData.summary || {};
  const governanceAuditSummary = governanceAuditData.summary || {};
  const governanceReviewerSummary = governanceReviewerData.summary || {};
  const governanceFinalBoardSummary = governanceFinalBoardData.summary || {};
  const governanceFinalBoardSignoff = governanceFinalBoardData.signoff_summary || {};
  const governanceEvidenceVaultSummary = governanceEvidenceVaultData.summary || {};
  const governanceAttestationSummary = governanceAttestationData.summary || {};
  const governanceAttestationCertificate = governanceAttestationData.certificate || {};
  const governanceAttestationRegistrySummary = governanceAttestationRegistryData.summary || {};
  const governanceAttestationRegistry = governanceAttestationRegistryData.registry || {};
  const governanceAttestationPortalSummary = governanceAttestationPortalData.summary || {};
  const governanceAttestationPortalReviewSummary = governanceAttestationPortalReviewData.summary || {};
  const governanceAttestationPortalReviewResponses = governanceAttestationPortalReviewData.responses || [];
  const governanceAttestationAcceptedEvidenceSummary = governanceAttestationAcceptedEvidenceData.summary || {};
  const governanceAttestationTransparencySummary = governanceAttestationTransparencyData.summary || {};
  const governanceAttestationTransparencyAcknowledgementSummary = governanceAttestationTransparencyAcknowledgementData.summary || {};
  const governanceAttestationTransparencyAcknowledgementEvidenceSummary = governanceAttestationTransparencyAcknowledgementData.evidence_summary || {};
  const governanceAttestationTransparencyAcknowledgementResponses = governanceAttestationTransparencyAcknowledgementData.responses || [];
  const governanceAttestationRegistryRows = (governanceAttestationRegistry.entries || []).slice(-6).reverse().map((entry) => `
    <tr>
      <td>${escapeHtml(entry.entry_id || "-")}</td>
      <td><span class="status ${escapeHtml(entry.status || "")}">${escapeHtml(entry.status || "-")}</span></td>
      <td>${escapeHtml(entry.certificate_id || "-")}</td>
      <td>${escapeHtml(((entry.source || {}).attestation_zip_sha256 || "").slice(0, 12) || "-")}</td>
      <td>
        <button class="secondary portfolio-governance-attestation-registry-publish" data-entry-id="${escapeHtml(entry.entry_id || "")}" type="button">Publish</button>
        <button class="secondary portfolio-governance-attestation-registry-revoke" data-entry-id="${escapeHtml(entry.entry_id || "")}" type="button">Revoke</button>
      </td>
    </tr>
  `).join("");
  const score = report.risk_score || {};
  const stale = Boolean(reportData.stale || (reportData.summary || {}).stale || (data.summary || {}).stale);
  const trend = trendData.trend_report || {};
  const risks = riskData.risk_register || {};
  const selection = portfolio.selection || {};
  const releaseRows = (report.release_readiness_ranking || []).map((item) => `
    <tr>
      <td>${escapeHtml(item.release_id || "-")}</td>
      <td>${escapeHtml(item.release_name || "-")}</td>
      <td><span class="status ${escapeHtml(item.readiness_status || "")}">${escapeHtml(item.readiness_status || "-")}</span></td>
      <td>${escapeHtml(item.coverage_score ?? "-")}</td>
      <td>${escapeHtml(item.risk_score ?? "-")}</td>
      <td>${escapeHtml(item.recommendation || "-")}</td>
    </tr>
  `).join("");
  const riskRows = (risks.risks || []).slice(0, 12).map((risk) => `
    <tr>
      <td>${escapeHtml(risk.severity || "-")}</td>
      <td>${escapeHtml(risk.category || "-")}</td>
      <td class="wrap-cell">${escapeHtml(risk.title || "-")}</td>
      <td>${escapeHtml((risk.release_ids || []).join(", ") || "-")}</td>
    </tr>
  `).join("");
  const recommendationRows = (report.recommendations || []).slice(0, 12).map((item) => `
    <tr>
      <td>${escapeHtml(item.severity || "-")}</td>
      <td>${escapeHtml(item.category || "-")}</td>
      <td class="wrap-cell">${escapeHtml(item.reason || "-")}</td>
      <td class="wrap-cell">${escapeHtml(item.suggested_action || "-")}</td>
    </tr>
  `).join("");
  const trendRows = (trend.trend_findings || []).slice(0, 12).map((item) => `
    <tr>
      <td>${escapeHtml(item.category || "-")}</td>
      <td>${escapeHtml(item.status || "-")}</td>
      <td class="wrap-cell">${escapeHtml(item.message || item.title || "-")}</td>
    </tr>
  `).join("");
  const governanceQueues = governanceData.queues || [];
  const governanceRows = governanceQueues.slice(0, 8).map((queue) => {
    const execution = queue.execution || {};
    return `
      <tr>
        <td>${escapeHtml(queue.queue_id || "-")}</td>
        <td><span class="status ${escapeHtml(queue.status || "")}">${escapeHtml(queue.status || "-")}</span></td>
        <td>${escapeHtml(execution.total_items ?? "-")}</td>
        <td>${escapeHtml(execution.safe_action_count ?? "-")}</td>
        <td>${escapeHtml(execution.manual_required_count ?? "-")}</td>
        <td>${execution.post_portfolio_refresh_required ? "yes" : "-"}</td>
        <td>
          <button class="secondary portfolio-governance-run-safe" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Run Safe</button>
          <button class="secondary portfolio-governance-export" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Export</button>
          <button class="secondary portfolio-governance-zip" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">ZIP</button>
          <button class="secondary portfolio-governance-verify" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Verify</button>
          <a class="button-link secondary" href="/api/release-portfolio-governance-queues/${encodeURIComponent(queue.queue_id)}/download">Download</a>
          <button class="secondary portfolio-governance-signoff" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Signoff</button>
          <button class="secondary portfolio-governance-force-signoff" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Force Signoff</button>
          <button class="secondary portfolio-governance-cr" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">New Change Request</button>
          <button class="secondary portfolio-governance-reset" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Reset Signoff</button>
          <button class="secondary portfolio-governance-archive-export" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Archive Export</button>
          <button class="secondary portfolio-governance-archive-zip" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Archive ZIP</button>
          <button class="secondary portfolio-governance-archive-verify" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Archive Verify</button>
          <a class="button-link secondary" href="/api/release-portfolio-governance-queues/${encodeURIComponent(queue.queue_id)}/archive.zip">Archive Download</a>
        </td>
      </tr>
    `;
  }).join("");
  $("portfolio-audit-detail").innerHTML = `
    <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
      <span>Release Portfolio Audit · ${escapeHtml(portfolio.name || portfolio.portfolio_id)}</span>
      <span class="status ${escapeHtml(report.status || portfolio.status || "")}">${escapeHtml(report.status || portfolio.status || "draft")}</span>
    </div>
    <div class="summary-grid">
      ${metric("Portfolio", portfolio.portfolio_id || "-")}
      ${metric("Releases", summary.release_count || 0)}
      ${metric("Risk Score", score.score ?? "-")}
      ${metric("Risk Status", score.status || "-")}
      ${metric("Blockers", summary.blocker_count || 0)}
      ${metric("Warnings", summary.warning_count || 0)}
      ${metric("Stale", stale ? "yes" : "-")}
      ${metric("Reviewer Packs", selection.require_reviewer_packs ? "required" : "optional")}
      ${metric("Archive", selection.require_archive ? "required" : "optional")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-audit-refresh" type="button">Refresh Portfolio Audit</button>
      <button class="secondary" id="portfolio-audit-export" type="button">Export Portfolio Audit</button>
      <button class="secondary" id="portfolio-audit-zip" type="button">Build Portfolio ZIP</button>
      <button class="secondary" id="portfolio-audit-verify" type="button">Verify Portfolio ZIP</button>
      <button class="danger" id="portfolio-audit-archive" type="button">Archive Portfolio Audit</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/download">Download Portfolio ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Release Readiness Ranking</span></div>
    <table>
      <thead><tr><th>Release</th><th>Name</th><th>Readiness</th><th>Coverage</th><th>Risk</th><th>Recommendation</th></tr></thead>
      <tbody>${releaseRows || "<tr><td colspan='6'>Refresh Portfolio Audit to build release ranking.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Portfolio Risk Register</span></div>
    <table>
      <thead><tr><th>Severity</th><th>Category</th><th>Risk</th><th>Releases</th></tr></thead>
      <tbody>${riskRows || "<tr><td colspan='4'>No portfolio risks.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Deterministic Recommendations</span></div>
    <table>
      <thead><tr><th>Severity</th><th>Category</th><th>Reason</th><th>Action</th></tr></thead>
      <tbody>${recommendationRows || "<tr><td colspan='4'>No portfolio recommendations.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Portfolio Trend Report</span></div>
    <table>
      <thead><tr><th>Category</th><th>Status</th><th>Finding</th></tr></thead>
      <tbody>${trendRows || "<tr><td colspan='3'>No trend findings.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Portfolio Governance Queue</span></div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-create" type="button">Create Governance Queue</button>
      <span id="portfolio-governance-message" class="message"></span>
    </div>
    <table>
      <thead><tr><th>Queue</th><th>Status</th><th>Items</th><th>Safe</th><th>Manual</th><th>Refresh Needed</th><th>Safe Actions</th></tr></thead>
      <tbody>${governanceRows || "<tr><td colspan='7'>No Governance Queues yet.</td></tr>"}</tbody>
    </table>
    <div class="panel-title subhead"><span>Governance Closeout</span></div>
    <div class="summary-grid">
      ${metric("Signoff", "queue-level")}
      ${metric("Archive", "verifiable")}
      ${metric("Change Control", "approved CR required")}
    </div>
    <div class="panel-title subhead"><span>Portfolio Governance Audit Ledger</span></div>
    <div class="summary-grid">
      ${metric("Audit", governanceAuditSummary.status || "missing")}
      ${metric("Entries", governanceAuditSummary.entry_count || 0)}
      ${metric("Signed Queues", governanceAuditSummary.signed_queue_count || 0)}
      ${metric("Archive Verified", governanceAuditSummary.archive_verified_count || 0)}
      ${metric("Blockers", governanceAuditSummary.blocker_count || 0)}
      ${metric("Warnings", governanceAuditSummary.warning_count || 0)}
      ${metric("Stale", governanceAuditSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-audit-refresh" type="button">Refresh Governance Audit</button>
      <button class="secondary" id="portfolio-governance-audit-export" type="button">Export Governance Audit</button>
      <button class="secondary" id="portfolio-governance-audit-zip" type="button">Build Governance Audit ZIP</button>
      <button class="secondary" id="portfolio-governance-audit-verify" type="button">Verify Governance Audit ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-audit.zip">Download Governance Audit ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Portfolio Governance Reviewer Pack</span></div>
    <div class="summary-grid">
      ${metric("Reviewer Pack", governanceReviewerSummary.status || "missing")}
      ${metric("Audit", governanceReviewerSummary.audit_status || "-")}
      ${metric("Audit Verified", governanceReviewerSummary.audit_package_verification_status || "-")}
      ${metric("Queues", governanceReviewerSummary.queue_count || 0)}
      ${metric("Signed Queues", governanceReviewerSummary.signed_queue_count || 0)}
      ${metric("Archive Verified", governanceReviewerSummary.archive_verified_count || 0)}
      ${metric("Blockers", governanceReviewerSummary.blocker_count || 0)}
      ${metric("Warnings", governanceReviewerSummary.warning_count || 0)}
      ${metric("Stale", governanceReviewerSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-reviewer-refresh" type="button">Refresh Governance Reviewer Pack</button>
      <button class="secondary" id="portfolio-governance-reviewer-export" type="button">Export Governance Reviewer Pack</button>
      <button class="secondary" id="portfolio-governance-reviewer-zip" type="button">Build Governance Reviewer ZIP</button>
      <button class="secondary" id="portfolio-governance-reviewer-verify" type="button">Verify Governance Reviewer ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-reviewer-pack.zip">Download Governance Reviewer ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Portfolio Governance Final Board</span></div>
    <div class="summary-grid">
      ${metric("Final Board", governanceFinalBoardSummary.status || "missing")}
      ${metric("Signoff", governanceFinalBoardSignoff.status || "-")}
      ${metric("Reviewer Response", governanceFinalBoardSummary.reviewer_response_status || "-")}
      ${metric("Reviewer Pack", governanceFinalBoardSummary.reviewer_pack_verification_status || "-")}
      ${metric("Audit", governanceFinalBoardSummary.audit_verification_status || "-")}
      ${metric("Archive Verified", governanceFinalBoardSummary.archive_verified_count || 0)}
      ${metric("Blockers", governanceFinalBoardSummary.blocker_count || 0)}
      ${metric("Warnings", governanceFinalBoardSummary.warning_count || 0)}
      ${metric("Stale", governanceFinalBoardSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-final-board-refresh" type="button">Refresh Final Board</button>
      <button class="secondary" id="portfolio-governance-final-board-import-accepted" type="button">Import Accepted Response</button>
      <button class="secondary" id="portfolio-governance-final-board-signoff" type="button">Final Board Signoff</button>
      <button class="secondary" id="portfolio-governance-final-board-cr" type="button">New Final Board Change Request</button>
      <button class="secondary" id="portfolio-governance-final-board-reset" type="button">Reset Final Board Signoff</button>
      <button class="secondary" id="portfolio-governance-final-board-export" type="button">Export Final Board Archive</button>
      <button class="secondary" id="portfolio-governance-final-board-zip" type="button">Build Final Board ZIP</button>
      <button class="secondary" id="portfolio-governance-final-board-verify" type="button">Verify Final Board ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-final-board.zip">Download Final Board ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Governance Evidence Vault</span></div>
    <div class="summary-grid">
      ${metric("Evidence Vault", governanceEvidenceVaultSummary.status || "missing")}
      ${metric("Nested Required", governanceEvidenceVaultSummary.required_package_count || 0)}
      ${metric("Nested Current", governanceEvidenceVaultSummary.current_required_package_count || 0)}
      ${metric("Archives", governanceEvidenceVaultSummary.archive_package_count || 0)}
      ${metric("Queues", governanceEvidenceVaultSummary.queue_package_count || 0)}
      ${metric("Verification", governanceEvidenceVaultSummary.verification_status || "-")}
      ${metric("Deep Verify", governanceEvidenceVaultSummary.deep_verification_status || "-")}
      ${metric("Blockers", governanceEvidenceVaultSummary.blocker_count || 0)}
      ${metric("Warnings", governanceEvidenceVaultSummary.warning_count || 0)}
      ${metric("Stale", governanceEvidenceVaultSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-vault-refresh" type="button">Refresh Evidence Vault</button>
      <button class="secondary" id="portfolio-governance-vault-export" type="button">Export Evidence Vault</button>
      <button class="secondary" id="portfolio-governance-vault-zip" type="button">Build Evidence Vault ZIP</button>
      <button class="secondary" id="portfolio-governance-vault-verify" type="button">Verify Evidence Vault ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-evidence-vault.zip">Download Evidence Vault ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Governance Public Attestation</span></div>
    <div class="summary-grid">
      ${metric("Public Attestation", governanceAttestationSummary.status || "missing")}
      ${metric("Profile", governanceAttestationSummary.profile || "public_summary")}
      ${metric("Certificate", governanceAttestationSummary.certificate_id || governanceAttestationCertificate.certificate_id || "-")}
      ${metric("Vault Verify", governanceAttestationSummary.vault_verification_status || governanceAttestationSummary.verification_status || "-")}
      ${metric("Deep Verify", governanceAttestationSummary.deep_verification_status || "-")}
      ${metric("Signed Queues", governanceAttestationSummary.signed_queue_count || 0)}
      ${metric("Blockers", governanceAttestationSummary.blocker_count || 0)}
      ${metric("Warnings", governanceAttestationSummary.warning_count || 0)}
      ${metric("Stale", governanceAttestationSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-attestation-refresh" type="button">Refresh Public Attestation</button>
      <button class="secondary" id="portfolio-governance-attestation-export" type="button">Export Public Attestation</button>
      <button class="secondary" id="portfolio-governance-attestation-zip" type="button">Build Public Attestation ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-verify" type="button">Verify Public Attestation ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation.zip">Download Public Attestation ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Governance Attestation Registry</span></div>
    <div class="summary-grid">
      ${metric("Registry", governanceAttestationRegistrySummary.status || "missing")}
      ${metric("Current Entry", governanceAttestationRegistrySummary.current_entry_id || "-")}
      ${metric("Entries", governanceAttestationRegistrySummary.entry_count || 0)}
      ${metric("Published", governanceAttestationRegistrySummary.published_count || 0)}
      ${metric("Revoked", governanceAttestationRegistrySummary.revoked_count || 0)}
      ${metric("Superseded", governanceAttestationRegistrySummary.superseded_count || 0)}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-attestation-registry-register-current" type="button">Register Current Attestation</button>
      <button class="secondary" id="portfolio-governance-attestation-registry-refresh" type="button">Refresh Registry Report</button>
      <button class="secondary" id="portfolio-governance-attestation-registry-export" type="button">Export Registry</button>
      <button class="secondary" id="portfolio-governance-attestation-registry-zip" type="button">Build Registry ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-registry-verify" type="button">Verify Registry ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-registry.zip">Download Registry ZIP</a>
    </div>
    <table class="compact-table">
      <thead><tr><th>Entry</th><th>Status</th><th>Certificate</th><th>ZIP SHA</th><th>Actions</th></tr></thead>
      <tbody>${governanceAttestationRegistryRows || '<tr><td colspan="5">No registry entries.</td></tr>'}</tbody>
    </table>
    <div class="panel-title subhead"><span>Governance Attestation Portal Snapshot</span></div>
    <div class="summary-grid">
      ${metric("Portal", governanceAttestationPortalSummary.status || "missing")}
      ${metric("Current Entry", governanceAttestationPortalSummary.current_entry_id || "-")}
      ${metric("Current Certificate", governanceAttestationPortalSummary.current_certificate_id || "-")}
      ${metric("Registry", governanceAttestationPortalSummary.registry_status || "-")}
      ${metric("Attestation", governanceAttestationPortalSummary.attestation_status || "-")}
      ${metric("Blockers", governanceAttestationPortalSummary.blocker_count || 0)}
      ${metric("Warnings", governanceAttestationPortalSummary.warning_count || 0)}
      ${metric("Stale", governanceAttestationPortalSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-attestation-portal-refresh" type="button">Refresh Portal</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-export" type="button">Export Portal</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-zip" type="button">Build Portal ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-verify" type="button">Verify Portal ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-portal.zip">Download Portal ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Portal Review Response</span></div>
    <div class="summary-grid">
      ${metric("Review Pack", governanceAttestationPortalReviewSummary.status || "missing")}
      ${metric("Pack ID", governanceAttestationPortalReviewSummary.review_pack_id || "-")}
      ${metric("Current Entry", governanceAttestationPortalReviewSummary.current_entry_id || "-")}
      ${metric("Responses", governanceAttestationPortalReviewResponses.length || 0)}
      ${metric("Stale", governanceAttestationPortalReviewSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-attestation-portal-review-refresh-pack" type="button">Refresh Review Pack</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-review-export-pack" type="button">Export Review Pack</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-review-zip-pack" type="button">Build Review Pack ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-review-verify-pack" type="button">Verify Review Pack</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-review-import-response" type="button">Import Response</button>
      <button class="secondary" id="portfolio-governance-attestation-portal-review-create-change-request" type="button">Create Change Request</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-portal-review-pack.zip">Download Review Pack ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Accepted Evidence</span></div>
    <div class="summary-grid">
      ${metric("Evidence", governanceAttestationAcceptedEvidenceSummary.status || "missing")}
      ${metric("External Review", governanceAttestationAcceptedEvidenceSummary.external_review_status || "-")}
      ${metric("Accepted Evidence", governanceAttestationAcceptedEvidenceSummary.accepted_evidence_id || "-")}
      ${metric("Response", governanceAttestationAcceptedEvidenceSummary.response_id || "-")}
      ${metric("Verification", governanceAttestationAcceptedEvidenceSummary.accepted_evidence_verification_status || governanceAttestationAcceptedEvidenceSummary.verification_status || "-")}
      ${metric("Stale", governanceAttestationAcceptedEvidenceSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-refresh" type="button">Refresh Accepted Evidence</button>
      <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-export" type="button">Export Accepted Evidence</button>
      <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-zip" type="button">Build Accepted Evidence ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-verify" type="button">Verify Accepted Evidence ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-archive" type="button">Archive Accepted Evidence</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-accepted-evidence.zip">Download Accepted Evidence ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Transparency Feed</span></div>
    <div class="summary-grid">
      ${metric("Feed", governanceAttestationTransparencySummary.status || "missing")}
      ${metric("Current Entry", governanceAttestationTransparencySummary.current_entry_id || "-")}
      ${metric("External Review", governanceAttestationTransparencySummary.external_review_status || "-")}
      ${metric("Events", governanceAttestationTransparencySummary.event_count ?? 0)}
      ${metric("Notices", governanceAttestationTransparencySummary.notice_count ?? 0)}
      ${metric("Verification", governanceAttestationTransparencySummary.verification_status || "-")}
      ${metric("Stale", governanceAttestationTransparencySummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-attestation-transparency-refresh" type="button">Refresh Transparency</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-export" type="button">Export Transparency</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-zip" type="button">Build Transparency ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-verify" type="button">Verify Transparency ZIP</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-transparency.zip">Download Transparency ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Transparency Acknowledgement</span></div>
    <div class="summary-grid">
      ${metric("Pack", governanceAttestationTransparencyAcknowledgementSummary.status || "missing")}
      ${metric("Pack ID", governanceAttestationTransparencyAcknowledgementSummary.pack_id || "-")}
      ${metric("Responses", governanceAttestationTransparencyAcknowledgementResponses.length || 0)}
      ${metric("Evidence", governanceAttestationTransparencyAcknowledgementEvidenceSummary.status || "missing")}
      ${metric("External Review", governanceAttestationTransparencyAcknowledgementEvidenceSummary.external_review_status || "-")}
      ${metric("Acknowledgement", governanceAttestationTransparencyAcknowledgementEvidenceSummary.acknowledgement_id || "-")}
      ${metric("Stale", governanceAttestationTransparencyAcknowledgementSummary.stale || governanceAttestationTransparencyAcknowledgementEvidenceSummary.stale ? "yes" : "-")}
    </div>
    <div class="actions">
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-refresh-pack" type="button">Refresh Ack Pack</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-export-pack" type="button">Export Ack Pack</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-zip-pack" type="button">Build Ack Pack ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-verify-pack" type="button">Verify Ack Pack</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-import-response" type="button">Import Ack Response</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-refresh-evidence" type="button">Refresh Ack Evidence</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-export-evidence" type="button">Export Ack Evidence</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-zip-evidence" type="button">Build Ack Evidence ZIP</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-verify-evidence" type="button">Verify Ack Evidence</button>
      <button class="secondary" id="portfolio-governance-attestation-transparency-ack-create-change-request" type="button">Create Ack Change Request</button>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-transparency-acknowledgement-pack.zip">Download Ack Pack ZIP</a>
      <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-transparency-acknowledgement-evidence.zip">Download Ack Evidence ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Public Trust Center</span></div>
    <div class="summary-grid">
      ${metric("Delivery", "Release / Distribution / Submission / Operations")}
      ${metric("Requirement", "Current public proof + delivery sidecars")}
    </div>
    <div class="actions">
      <button class="secondary" id="public-trust-center-refresh" type="button">Refresh Trust Center</button>
      <button class="secondary" id="public-trust-center-export" type="button">Export Trust Center</button>
      <button class="secondary" id="public-trust-center-zip" type="button">Build Trust Center ZIP</button>
      <button class="secondary" id="public-trust-center-verify" type="button">Verify Trust Center ZIP</button>
      <button class="secondary" id="public-trust-center-archive" type="button">Archive Trust Center</button>
      <a class="button-link secondary" href="/api/public-trust-centers/ptc-default.zip">Download Trust Center ZIP</a>
      <button class="secondary" id="public-trust-center-anchor-register" type="button">Register Anchor</button>
      <button class="secondary" id="public-trust-center-anchor-export" type="button">Export Anchor Registry</button>
      <button class="secondary" id="public-trust-center-anchor-zip" type="button">Build Anchor Registry ZIP</button>
      <button class="secondary" id="public-trust-center-anchor-verify" type="button">Verify Anchor Registry</button>
      <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/anchor-registry/download">Download Anchor Registry ZIP</a>
      <button class="secondary" id="public-trust-center-anchor-transparency-refresh" type="button">Refresh Anchor Transparency</button>
      <button class="secondary" id="public-trust-center-anchor-transparency-export" type="button">Export Anchor Transparency</button>
      <button class="secondary" id="public-trust-center-anchor-transparency-zip" type="button">Build Anchor Transparency ZIP</button>
      <button class="secondary" id="public-trust-center-anchor-transparency-verify" type="button">Verify Anchor Transparency</button>
      <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/anchor-transparency/download">Download Anchor Transparency ZIP</a>
      <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/anchor-transparency/checkpoint">Download Anchor Checkpoint</a>
      <button class="secondary" id="public-trust-center-distribution-kit-refresh" type="button">Refresh Distribution Kit</button>
      <button class="secondary" id="public-trust-center-distribution-kit-export" type="button">Export Distribution Kit</button>
      <button class="secondary" id="public-trust-center-distribution-kit-zip" type="button">Build Distribution Kit ZIP</button>
      <button class="secondary" id="public-trust-center-distribution-kit-verify" type="button">Verify Distribution Kit</button>
      <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/distribution-kit/download">Download Distribution Kit ZIP</a>
      <button class="secondary" id="public-trust-center-distribution-kit-acceptance-template" type="button">Create Kit Acceptance Template</button>
      <button class="secondary" id="public-trust-center-distribution-kit-accepted-evidence-export" type="button">Export Kit Accepted Evidence</button>
      <button class="secondary" id="public-trust-center-distribution-kit-accepted-evidence-zip" type="button">Build Kit Accepted Evidence ZIP</button>
      <button class="secondary" id="public-trust-center-distribution-kit-accepted-evidence-verify" type="button">Verify Kit Accepted Evidence</button>
      <button class="secondary" id="public-trust-center-acceptance-board-refresh" type="button">Refresh Acceptance Board</button>
      <button class="secondary" id="public-trust-center-acceptance-board-export" type="button">Export Acceptance Board</button>
      <button class="secondary" id="public-trust-center-acceptance-board-zip" type="button">Build Acceptance Board ZIP</button>
      <button class="secondary" id="public-trust-center-acceptance-board-verify" type="button">Verify Acceptance Board</button>
      <button class="secondary" id="public-trust-center-acceptance-board-signoff-draft" type="button">Create Board Signoff Draft</button>
      <button class="secondary" id="public-trust-center-acceptance-board-signoff" type="button">Sign Acceptance Board</button>
      <button class="secondary" id="public-trust-center-acceptance-board-signoff-archive-export" type="button">Export Board Signoff Archive</button>
      <button class="secondary" id="public-trust-center-acceptance-board-signoff-archive-zip" type="button">Build Board Signoff Archive ZIP</button>
      <button class="secondary" id="public-trust-center-acceptance-board-signoff-archive-verify" type="button">Verify Board Signoff Archive</button>
      <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/acceptance-board/download">Download Acceptance Board ZIP</a>
      <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/download">Download Board Signoff Archive ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Trust Operations Hub</span></div>
    <div class="summary-grid">
      ${metric("Scope", "Release / Distribution / Submission / Operations / PTC / Publication")}
      ${metric("Evidence", "Readiness matrix + blocker register + verification index")}
    </div>
    <div class="actions">
      <button class="secondary" id="trust-operations-hub-refresh" type="button">Refresh Hub</button>
      <button class="secondary" id="trust-operations-hub-export" type="button">Export Hub</button>
      <button class="secondary" id="trust-operations-hub-zip" type="button">Build Hub ZIP</button>
      <button class="secondary" id="trust-operations-hub-verify" type="button">Verify Hub ZIP</button>
      <button class="secondary" id="trust-operations-hub-signoff" type="button">Sign Hub</button>
      <button class="secondary" id="trust-operations-hub-change-request" type="button">Create Hub Change Request</button>
      <button class="secondary" id="trust-operations-hub-reset" type="button">Reset Hub Signoff</button>
      <a class="button-link secondary" href="/api/trust-operations/hubs/default.zip">Download Hub ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Trust Operations Runbook</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-runbook-create" type="button">Create Runbook</button>
      <button class="secondary" id="trust-operations-runbook-run-safe" type="button">Run Safe Actions</button>
      <button class="secondary" id="trust-operations-runbook-export" type="button">Export Runbook</button>
      <button class="secondary" id="trust-operations-runbook-zip" type="button">Build Runbook ZIP</button>
      <button class="secondary" id="trust-operations-runbook-verify" type="button">Verify Runbook</button>
    </div>
    <div class="panel-title subhead"><span>Trust Operations Incidents</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-incidents-refresh" type="button">Refresh Incidents</button>
      <button class="secondary" id="trust-operations-incidents-triage" type="button">Triage Incident</button>
      <button class="secondary" id="trust-operations-incidents-plan" type="button">Create Remediation Plan</button>
      <button class="secondary" id="trust-operations-incidents-evidence" type="button">Add Evidence</button>
      <button class="secondary" id="trust-operations-incidents-close" type="button">Close Incident</button>
      <button class="secondary" id="trust-operations-incidents-export" type="button">Export Incident Board</button>
      <button class="secondary" id="trust-operations-incidents-zip" type="button">Build Incident ZIP</button>
      <button class="secondary" id="trust-operations-incidents-verify" type="button">Verify Incident ZIP</button>
    </div>
    <div class="panel-title subhead"><span>Trust Operations Knowledge</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-knowledge-refresh" type="button">Refresh Knowledge</button>
      <button class="secondary" id="trust-operations-knowledge-create-guard" type="button">Create Regression Guard</button>
      <button class="secondary" id="trust-operations-knowledge-run-guards" type="button">Run Regression Guards</button>
      <button class="secondary" id="trust-operations-knowledge-recurrence" type="button">Refresh Recurrence</button>
      <button class="secondary" id="trust-operations-knowledge-export" type="button">Export Knowledge</button>
      <button class="secondary" id="trust-operations-knowledge-zip" type="button">Build Knowledge ZIP</button>
      <button class="secondary" id="trust-operations-knowledge-verify" type="button">Verify Knowledge ZIP</button>
      <a class="button-link secondary" href="/api/trust-operations/hubs/default/knowledge.zip">Download Knowledge ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Trust Operations Controls</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-controls-refresh" type="button">Refresh Control Catalog</button>
      <button class="secondary" id="trust-operations-controls-policy" type="button">Create Control Policy</button>
      <button class="secondary" id="trust-operations-controls-assess" type="button">Assess Controls</button>
      <button class="secondary" id="trust-operations-controls-export" type="button">Export Controls</button>
      <button class="secondary" id="trust-operations-controls-zip" type="button">Build Controls ZIP</button>
      <button class="secondary" id="trust-operations-controls-verify" type="button">Verify Controls ZIP</button>
      <a class="button-link secondary" href="/api/trust-operations/hubs/default/controls/toc-assess-000001.zip">Download Controls ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Trust Control Signoff</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-control-signoff-sign" type="button">Sign Controls</button>
      <button class="secondary" id="trust-operations-control-signoff-exception" type="button">Request Exception</button>
      <button class="secondary" id="trust-operations-control-signoff-cr" type="button">Create Change Request</button>
      <button class="secondary" id="trust-operations-control-signoff-reset" type="button">Reset Control Signoff</button>
      <button class="secondary" id="trust-operations-control-signoff-export" type="button">Export Signoff Archive</button>
      <button class="secondary" id="trust-operations-control-signoff-zip" type="button">Build Signoff ZIP</button>
      <button class="secondary" id="trust-operations-control-signoff-verify" type="button">Verify Signoff ZIP</button>
      <a class="button-link secondary" href="/api/trust-operations/control-signoff/default/download">Download Control Signoff ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Continuous Assurance</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-assurance-refresh" type="button">Refresh Assurance</button>
      <button class="secondary" id="trust-operations-assurance-export" type="button">Export Assurance</button>
      <button class="secondary" id="trust-operations-assurance-zip" type="button">Build Assurance ZIP</button>
      <button class="secondary" id="trust-operations-assurance-verify" type="button">Verify Assurance</button>
      <a class="button-link secondary" href="/api/trust-operations/assurance/runs/toa-000001/download">Download Assurance ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Assurance Watch</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-assurance-watch-schedule" type="button">Update Schedule</button>
      <button class="secondary" id="trust-operations-assurance-watch-refresh" type="button">Refresh Watch Queue</button>
      <button class="secondary" id="trust-operations-assurance-watch-export" type="button">Export Watch Archive</button>
      <button class="secondary" id="trust-operations-assurance-watch-zip" type="button">Build Watch ZIP</button>
      <button class="secondary" id="trust-operations-assurance-watch-verify" type="button">Verify Watch ZIP</button>
      <a class="button-link secondary" href="/api/trust-operations/assurance-watch/queues/toawq-000001/download">Download Watch ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Assurance Watch Signoff</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-assurance-watch-signoff-closeout" type="button">Refresh Watch Closeout</button>
      <button class="secondary" id="trust-operations-assurance-watch-signoff-sign" type="button">Sign Watch Closeout</button>
      <button class="secondary" id="trust-operations-assurance-watch-signoff-cr" type="button">Create Watch Change Request</button>
      <button class="secondary" id="trust-operations-assurance-watch-signoff-reset" type="button">Reset Watch Signoff</button>
      <button class="secondary" id="trust-operations-assurance-watch-signoff-export" type="button">Export Watch Signoff Archive</button>
      <button class="secondary" id="trust-operations-assurance-watch-signoff-zip" type="button">Build Watch Signoff ZIP</button>
      <button class="secondary" id="trust-operations-assurance-watch-signoff-verify" type="button">Verify Watch Signoff ZIP</button>
      <a class="button-link secondary" href="/api/trust-operations/assurance-watch/signoffs/toawq-000001/download">Download Watch Signoff ZIP</a>
    </div>
    <div class="panel-title subhead"><span>Final Readiness Handoff</span></div>
    <div class="actions">
      <button class="secondary" id="trust-operations-final-readiness-refresh" type="button">Refresh Final Readiness</button>
      <button class="secondary" id="trust-operations-final-readiness-certificate" type="button">Create Certificate</button>
      <button class="secondary" id="trust-operations-final-readiness-sign" type="button">Sign Final Handoff</button>
      <button class="secondary" id="trust-operations-final-readiness-cr" type="button">Create Final Change Request</button>
      <button class="secondary" id="trust-operations-final-readiness-reset" type="button">Reset Final Handoff</button>
      <button class="secondary" id="trust-operations-final-readiness-export" type="button">Export Final Handoff</button>
      <button class="secondary" id="trust-operations-final-readiness-zip" type="button">Build Final Handoff ZIP</button>
      <button class="secondary" id="trust-operations-final-readiness-verify" type="button">Verify Final Handoff ZIP</button>
      <a class="button-link secondary" href="/api/trust-operations/final-readiness/download">Download Final Handoff ZIP</a>
    </div>
  `;
  wirePortfolioAuditActions(portfolio.portfolio_id);
  wirePortfolioGovernanceActions(portfolio.portfolio_id);
  wirePublicTrustCenterActions(portfolio.portfolio_id);
}

Object.assign(globalThis, { loadPortfolioAudits, loadPlanningGovernance, portfolioAuditPayload, renderPortfolioAudits, renderPortfolioAuditDetail });

export { loadPortfolioAudits, loadPlanningGovernance, portfolioAuditPayload, renderPortfolioAudits, renderPortfolioAuditDetail };
