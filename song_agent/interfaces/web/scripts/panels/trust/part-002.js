function wirePortfolioAuditActions(portfolioId) {
  const payload = () => ({
    strict: true,
    require_reviewer_packs: $("portfolio-audit-require-reviewer-packs").checked,
    require_audit: $("portfolio-audit-require-audit").checked,
    require_archive: $("portfolio-audit-require-archive").checked,
  });
  bindAction("portfolio-audit-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(portfolioAuditPayload()),
    });
    await loadPortfolioAudits();
  });
  bindAction("portfolio-audit-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/export`, { method: "POST" });
    await loadPortfolioAudits();
  });
  bindAction("portfolio-audit-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/export/zip`, { method: "POST" });
    await loadPortfolioAudits();
  });
  bindAction("portfolio-audit-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    await loadPortfolioAudits();
  });
  bindAction("portfolio-audit-archive", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/archive`, { method: "POST" });
    await loadPortfolioAudits();
  });
  bindAction("portfolio-governance-audit-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/refresh`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-audit-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-audit-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-audit-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, require_signed: true, require_archives: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-reviewer-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/refresh`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-reviewer-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-reviewer-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-reviewer-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, require_audit: true, require_signed: true, require_archives: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ require_reviewer_response: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-import-accepted", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/reviewer-responses/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer: { name: "Studio Reviewer" }, decision: "accepted", findings: [], notes: "Accepted in Studio." }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-signoff", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signed_by: "studio-user" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-cr", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/change-requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Final Board archive change requested." }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-reset", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/signoff/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Reset Final Board signoff after approved change.", change_request_id: "" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/archive/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/archive/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-final-board-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/archive/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, require_signed: true, require_reviewer_pack: true, require_audit: true, require_archives: true, require_reviewer_response: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-vault-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/refresh`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-vault-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-vault-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-vault-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, deep: true, require_final_board: true, require_reviewer_pack: true, require_audit: true, require_archives: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_vault: true, require_final_board: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-registry-register-current", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/register-current`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-registry-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-registry-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-registry-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-registry-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true, require_published: true, require_no_revoked_current: true, require_accepted_evidence: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  document.querySelectorAll(".portfolio-governance-attestation-registry-publish").forEach((button) => {
    button.addEventListener("click", async () => {
      const entryId = button.dataset.entryId;
      if (!entryId) return;
      await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/entries/${encodeURIComponent(entryId)}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: "public_summary", supersede_current: true }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-attestation-registry-revoke").forEach((button) => {
    button.addEventListener("click", async () => {
      const entryId = button.dataset.entryId;
      if (!entryId) return;
      const reason = prompt("Revocation reason");
      if (!reason) return;
      await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/entries/${encodeURIComponent(entryId)}/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: "public_summary", reason }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  bindAction("portfolio-governance-attestation-portal-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true, require_registry: true, require_attestation: true, require_accepted_evidence: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-review-refresh-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-review-export-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-review-zip-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-review-verify-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-review-import-response", async () => {
    const contentBase64 = prompt("Portal Review Response content_base64");
    if (!contentBase64) return;
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/responses/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", content_base64: contentBase64 }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-portal-review-create-change-request", async () => {
    const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review`);
    const responses = data.responses || [];
    const response = responses[responses.length - 1] || {};
    if (!response.response_id) return;
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/responses/${encodeURIComponent(response.response_id)}/create-change-request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ created_by: "studio" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-accepted-evidence-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-accepted-evidence-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-accepted-evidence-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-accepted-evidence-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-accepted-evidence-archive", async () => {
    const reason = prompt("Accepted Evidence archive reason");
    if (!reason) return;
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/archive`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", reason }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-refresh", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", require_accepted_evidence: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-export", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-zip", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-verify", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true, require_accepted_evidence: true, require_contiguous_chain: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-refresh-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-export-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-zip-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-verify-pack", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_transparency: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-import-response", async () => {
    const contentBase64 = prompt("Transparency Acknowledgement Response content_base64");
    if (!contentBase64) return;
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/responses/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", content_base64: contentBase64 }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-refresh-evidence", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-export-evidence", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-zip-evidence", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/zip`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-verify-evidence", async () => {
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary", strict: true, require_accepted: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("portfolio-governance-attestation-transparency-ack-create-change-request", async () => {
    const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement`);
    const responses = data.responses || [];
    const response = responses[responses.length - 1] || {};
    if (!response.response_id) return;
    await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/responses/${encodeURIComponent(response.response_id)}/create-change-request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "public_summary" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
}

function wirePublicTrustCenterActions(portfolioId) {
  const payload = () => ({
    center_id: "ptc-default",
    portfolio_ids: [portfolioId],
    include_all_releases: true,
    include_all_portfolios: false,
    include_delivery: true,
    include_distribution: true,
    include_submission: true,
    include_submission_evidence: true,
    include_operations: true,
    attestation_profile: "public_summary",
    require_registry_current: true,
    require_portal_current: true,
    require_transparency_current: true,
  });
  bindAction("public-trust-center-refresh", async () => {
    await api(`/api/public-trust-centers/ptc-default/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-export", async () => {
    await api(`/api/public-trust-centers/ptc-default/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-zip", async () => {
    await api(`/api/public-trust-centers/ptc-default/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-verify", async () => {
    await api(`/api/public-trust-centers/ptc-default/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, require_registry_current: true, require_portal_current: true, require_transparency_current: true, require_delivery_readiness: false, require_distribution_ready: false, require_submission_accepted: false, require_submission_evidence: false, require_operations_signed: false, require_operations_audit: false, require_operations_reviewer_pack: false, require_anchor_registry_current: true, require_anchor_published: true, require_anchor_not_revoked: true, require_anchor_transparency_current: true, require_anchor_checkpoint: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-archive", async () => {
    await api(`/api/public-trust-centers/ptc-default/archive`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-register", async () => {
    const registered = await api(`/api/public-trust-centers/ptc-default/anchor-registry/register-current`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Studio anchor registration" }),
    });
    const entryId = (registered.entry || {}).entry_id;
    if (entryId) {
      await api(`/api/public-trust-centers/ptc-default/anchor-registry/publish/${encodeURIComponent(entryId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Studio anchor publication" }),
      });
    }
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-export", async () => {
    await api(`/api/public-trust-centers/ptc-default/anchor-registry/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-zip", async () => {
    await api(`/api/public-trust-centers/ptc-default/anchor-registry/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-verify", async () => {
    await api(`/api/public-trust-centers/ptc-default/anchor-registry/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, require_current: true, require_anchor_published: true, require_anchor_not_revoked: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-transparency-refresh", async () => {
    await api(`/api/public-trust-centers/ptc-default/anchor-transparency/refresh`, { method: "POST" });
    await api(`/api/public-trust-centers/ptc-default/anchor-transparency/checkpoint/create`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-transparency-export", async () => {
    await api(`/api/public-trust-centers/ptc-default/anchor-transparency/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-transparency-zip", async () => {
    await api(`/api/public-trust-centers/ptc-default/anchor-transparency/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-anchor-transparency-verify", async () => {
    await api(`/api/public-trust-centers/ptc-default/anchor-transparency/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, use_checkpoint: true, use_anchor_registry: true, require_current_checkpoint: true, require_published_anchor: true, require_not_revoked: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-refresh", async () => {
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/refresh`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-export", async () => {
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-zip", async () => {
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-verify", async () => {
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, deep: true, require_current: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-acceptance-template", async () => {
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/template`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-accepted-evidence-export", async () => {
    const data = await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance`);
    const responses = data.responses || [];
    const response = responses[responses.length - 1] || {};
    if (!response.response_id) return;
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/responses/${encodeURIComponent(response.response_id)}/evidence/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-accepted-evidence-zip", async () => {
    const data = await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance`);
    const responses = data.responses || [];
    const response = responses[responses.length - 1] || {};
    if (!response.response_id) return;
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/responses/${encodeURIComponent(response.response_id)}/evidence/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-distribution-kit-accepted-evidence-verify", async () => {
    const data = await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance`);
    const responses = data.responses || [];
    const response = responses[responses.length - 1] || {};
    if (!response.response_id) return;
    await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/responses/${encodeURIComponent(response.response_id)}/evidence/verify`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-refresh", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/refresh`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-export", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-zip", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-verify", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, require_ready: true, require_quorum: true, require_no_conflicts: true, use_distribution_kit: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-signoff-draft", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "studio" }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-signoff", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signed_by: "Studio Reviewer", reason: "Acceptance Board quorum is ready for public release." }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-signoff-archive-export", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/export`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-signoff-archive-zip", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/zip`, { method: "POST" });
    await renderPortfolioAuditDetail(portfolioId);
  });
  bindAction("public-trust-center-acceptance-board-signoff-archive-verify", async () => {
    await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true }),
    });
    await renderPortfolioAuditDetail(portfolioId);
  });
}

function wirePortfolioGovernanceActions(portfolioId) {
  bindAction("portfolio-governance-create", async () => {
    const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-queues`, { method: "POST" });
    $("portfolio-governance-message").textContent = (data.queue || {}).existing ? "existing queue" : "created";
    await renderPortfolioAuditDetail(portfolioId);
  });
  document.querySelectorAll(".portfolio-governance-run-safe").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/run-safe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_portfolio_after_safe_actions: false }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-export").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/export`, { method: "POST" });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-zip").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/export/zip`, { method: "POST" });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-verify").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strict: true, require_manual_actions: true }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  async function manualAcknowledgements(queueId) {
    const data = await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/manual-actions`);
    return ((data.manual_action_list || {}).items || []).map((item) => ({
      item_id: item.item_id,
      action_type: item.action_type,
      resolution: "accepted_for_followup",
      owner: "developer",
      due_note: "next governance cycle",
    }));
  }
  document.querySelectorAll(".portfolio-governance-signoff").forEach((button) => {
    button.addEventListener("click", async () => {
      const queueId = button.dataset.queueId;
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/signoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signed_by: "studio-user", manual_acknowledgements: await manualAcknowledgements(queueId) }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-force-signoff").forEach((button) => {
    button.addEventListener("click", async () => {
      const queueId = button.dataset.queueId;
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/signoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signed_by: "studio-user", force: true, override_reason: "accepted residual governance follow-up", manual_acknowledgements: await manualAcknowledgements(queueId) }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-cr").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/change-requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Governance signoff reset requested from Studio", requested_by: "studio-user" }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-reset").forEach((button) => {
    button.addEventListener("click", async () => {
      const queueId = button.dataset.queueId;
      const changes = await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/change-requests`);
      const approved = ((changes.change_requests || []).find((item) => item.status === "approved") || {}).change_request_id || "";
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/signoff/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Reset with approved governance change", change_request_id: approved }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-archive-export").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/archive/export`, { method: "POST" });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-archive-zip").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/archive/zip`, { method: "POST" });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
  document.querySelectorAll(".portfolio-governance-archive-verify").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/archive/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strict: true, require_signed: true }),
      });
      await renderPortfolioAuditDetail(portfolioId);
    });
  });
}

Object.assign(globalThis, { wirePortfolioAuditActions, wirePublicTrustCenterActions, wirePortfolioGovernanceActions });

export { wirePortfolioAuditActions, wirePublicTrustCenterActions, wirePortfolioGovernanceActions };
