function wireReleaseActions(release) {
  bindAction("release-add-track", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/tracks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: $("release-add-project").value, title: $("release-add-title").value.trim() }),
    });
    await loadReleases();
  });
  bindAction("release-init-metadata", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata/init`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-save-metadata", async () => {
    const metadata = await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata`);
    const payload = metadata.metadata || {};
    payload.release = payload.release || {};
    payload.release.title = $("release-metadata-title").value.trim();
    payload.release.upc = $("release-metadata-upc").value.trim();
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadReleases();
  });
  bindAction("release-refresh-metadata-qa", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata/qa/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-export-metadata", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata/export`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-refresh-qa", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/qa/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-refresh-audio-qa", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-qa`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ require_audio: true }) });
    await loadReleases();
  });
  bindAction("release-refresh-audio-review-summary", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews/refresh-summary`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-add-audio-review", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        track_id: $("release-audio-review-track").value,
        status: $("release-audio-review-status").value,
        review_mode: "manual",
        reviewer: { name: $("release-audio-reviewer").value.trim() || "local-user" },
        rating: Number($("release-audio-review-rating").value || 0),
        playback_confirmed: true,
        notes: $("release-audio-review-notes").value,
      }),
    });
    await loadReleases();
  });
  bindAction("release-create-audio-revision", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: $("release-audio-revision-title").value.trim() || "Audio revision pass" }),
    });
    await loadReleases();
  });
  bindAction("release-generate-audio-revision-candidates", async () => {
    const sessionId = $("release-audio-revision-session").value;
    const issueId = $("release-audio-revision-issue").value.trim();
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/issues/${encodeURIComponent(issueId)}/candidates/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_candidates: 3 }),
    });
    await loadReleases();
  });
  bindAction("release-review-audio-revision-candidate", async () => {
    const sessionId = $("release-audio-revision-session").value;
    const candidateId = $("release-audio-revision-candidate").value.trim();
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/candidates/${encodeURIComponent(candidateId)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "accepted", review_mode: "manual", rating: 4, playback_confirmed: true }),
    });
    await loadReleases();
  });
  bindAction("release-select-audio-revision-candidate", async () => {
    const sessionId = $("release-audio-revision-session").value;
    const candidateId = $("release-audio-revision-candidate").value.trim();
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/candidates/${encodeURIComponent(candidateId)}/select`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-apply-audio-revision-candidate", async () => {
    const sessionId = $("release-audio-revision-session").value;
    const candidateId = $("release-audio-revision-candidate").value.trim();
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/candidates/${encodeURIComponent(candidateId)}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version_name: "Audio Revision Applied" }),
    });
    await loadReleases();
  });
  bindAction("release-refresh-audio-revision", async () => {
    const sessionId = $("release-audio-revision-session").value;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-close-audio-revision", async () => {
    const sessionId = $("release-audio-revision-session").value;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/close`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-mastering-analyze", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: $("release-mastering-profile").value || "demo_review" }),
    });
    await loadReleases();
  });
  bindAction("release-mastering-plan", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering/plan`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-render-mastering-candidate", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering/candidates`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-mastering-review", async () => {
    const candidateId = $("release-mastering-candidate").value;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering/candidates/${encodeURIComponent(candidateId)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "accepted", review_mode: "manual", rating: 4, playback_confirmed: true }),
    });
    await loadReleases();
  });
  bindAction("release-mastering-select", async () => {
    const candidateId = $("release-mastering-candidate").value;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering/candidates/${encodeURIComponent(candidateId)}/select`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-mastering-reset", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Studio mastering reset" }),
    });
    await loadReleases();
  });
  bindAction("release-render-encoded-audio", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_ids: $("release-encoded-audio-profiles").value.split(",").map((item) => item.trim()).filter(Boolean) }),
    });
    await loadReleases();
  });
  bindAction("release-verify-encoded-audio", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ require_encoded_audio: true, required_audio_format_profiles: $("release-encoded-audio-profiles").value.split(",").map((item) => item.trim()).filter(Boolean) }),
    });
    await loadReleases();
  });
  bindAction("release-refresh-encoded-audio-health", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio/health`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_ids: $("release-encoded-audio-profiles").value.split(",").map((item) => item.trim()).filter(Boolean) }),
    });
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio/acceptance/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_ids: $("release-encoded-audio-profiles").value.split(",").map((item) => item.trim()).filter(Boolean) }),
    });
    await loadReleases();
  });
  bindAction("release-reset-encoded-audio", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Studio encoded audio reset" }),
    });
    await loadReleases();
  });
  bindAction("release-create-format-decision", async () => {
    const profileList = $("release-format-decision-profiles").value.split(",").map((item) => item.trim()).filter(Boolean);
    const created = await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profiles: profileList }),
    });
    const sessionId = (created.session || {}).session_id;
    if (sessionId) {
      await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions/${encodeURIComponent(sessionId)}/matrix`, { method: "POST" });
      await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions/${encodeURIComponent(sessionId)}/recommend`, { method: "POST" });
      await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions/${encodeURIComponent(sessionId)}/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_profiles: $("release-format-decision-selected").value.split(",").map((item) => item.trim()).filter(Boolean),
          archive_profiles: $("release-format-decision-archive").value.split(",").map((item) => item.trim()).filter(Boolean),
          rejected_profiles: $("release-format-decision-rejected").value.split(",").map((item) => item.trim()).filter(Boolean),
          reason: $("release-format-decision-reason").value.trim(),
        }),
      });
      await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions/${encodeURIComponent(sessionId)}/report`, { method: "POST" });
      await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions/${encodeURIComponent(sessionId)}/activate`, { method: "POST" });
    }
    await loadReleases();
  });
  bindAction("rights-create-party", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/rights/parties`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: $("rights-party-name").value.trim(), public_credit_name: $("rights-party-credit").value.trim() }),
    });
    await loadReleases();
  });
  bindAction("rights-save-track", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/rights/tracks/${encodeURIComponent($("rights-track-id").value)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instrumental: true,
        contributors: [{ party_id: $("rights-party-id").value, role: $("rights-contributor-role").value, share: Number($("rights-contributor-share").value || 100) }],
        source_usages: [{ source_id: "original-1", name: "Original composition", status: "original", risk_level: "low" }],
      }),
    });
    await loadReleases();
  });
  bindAction("rights-review-track", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/rights/tracks/${encodeURIComponent($("rights-track-id").value)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "accepted", review_mode: "manual", confirmed_by: "local-user", attestation: $("rights-attestation").value.trim() }),
    });
    await loadReleases();
  });
  bindAction("rights-refresh-report", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/rights/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-refresh", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-export", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/export`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-zip", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/export/zip`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-verify", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ require_submission_evidence: true }),
    });
    await loadReleases();
  });
  const selectedRunbookId = () => {
    const value = ($("release-runbook-id") || {}).value || "";
    if (!value) throw new Error("Select a Release Operations Runbook first.");
    return value;
  };
  bindAction("release-runbook-create", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-runbook-run-safe", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks/${encodeURIComponent(selectedRunbookId())}/run-safe`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-runbook-refresh-stale", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks/${encodeURIComponent(selectedRunbookId())}/refresh-stale`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-runbook-export", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks/${encodeURIComponent(selectedRunbookId())}/export`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-runbook-zip", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks/${encodeURIComponent(selectedRunbookId())}/export/zip`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-runbook-verify", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks/${encodeURIComponent(selectedRunbookId())}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ require_current: true }),
    });
    await loadReleases();
  });
  bindAction("release-operations-sign", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signed_by: ($("release-operations-signed-by") || {}).value || "local-user" }),
    });
    await loadReleases();
  });
  bindAction("release-operations-archive-export", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/archive/export`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-archive-zip", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/archive/export/zip`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-archive-verify", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/archive/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ require_signed: true }),
    });
    await loadReleases();
  });
  bindAction("release-operations-change-create", async () => {
    const scope = (($("release-operations-change-scope") || {}).value || "operations").split(",").map((item) => item.trim()).filter(Boolean);
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/change-requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: ($("release-operations-change-reason") || {}).value || "Approved operations evidence change", scope, created_by: "local-user" }),
    });
    await loadReleases();
  });
  bindAction("release-operations-reset-signoff", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/signoff/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: ($("release-operations-reset-reason") || {}).value || "Approved operations evidence change", change_request_id: (($("release-operations-change-id") || {}).value || "").trim() || null }),
    });
    await loadReleases();
  });
  bindAction("release-operations-audit-refresh", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/audit/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-audit-export", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/audit/export`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-audit-zip", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/audit/export/zip`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-operations-audit-verify", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/audit/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ require_current: true, require_signed: true, require_archive: true }),
    });
    await loadReleases();
  });
  bindAction("release-reviewer-pack-refresh", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-reviewer-pack-export", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack/export`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-reviewer-pack-zip", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack/export/zip`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-reviewer-pack-verify", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strict: true, require_audit: true, require_signed: true, require_archive: true }),
    });
    await loadReleases();
  });
  bindAction("release-build-export", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/export`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-build-zip", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/export/zip`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-refresh-acceptance-analytics", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/acceptance-analytics/refresh`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-signoff", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(releaseSignoffPayload(false)),
    });
    await loadReleases();
  });
  bindAction("release-force-signoff", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(releaseSignoffPayload(true)),
    });
    await loadReleases();
  });
  bindAction("release-reset-signoff", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/signoff/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: $("release-reset-reason").value.trim() }),
    });
    await loadReleases();
  });
  bindAction("release-hide", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/${release.hidden ? "unhide" : "hide"}`, { method: "POST" });
    await loadReleases();
  });
  bindAction("release-archive", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/archive`, { method: "POST" });
    await loadReleases();
  });
  wireReleaseDistributionActions(release);
  wireReleaseSubmissionActions(release);
  document.querySelectorAll(".release-track-refresh").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/releases/${encodeURIComponent(release.release_id)}/tracks/${encodeURIComponent(button.dataset.trackId)}/refresh`, { method: "POST" });
      await loadReleases();
    });
  });
  document.querySelectorAll(".release-track-remove").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/releases/${encodeURIComponent(release.release_id)}/tracks/${encodeURIComponent(button.dataset.trackId)}/remove`, { method: "POST" });
      await loadReleases();
    });
  });
}

function releaseDistributionHtml(distributionData, release) {
  const targets = distributionData.targets || [];
  const artwork = distributionData.artwork || [];
  const templatePacks = distributionData.template_packs || [];
  const templateOptions = templatePacks.map((template) => `<option value="${escapeHtml(template.template_pack_id)}">${escapeHtml(template.name || template.slug)} · ${escapeHtml(template.source || "local")}</option>`).join("");
  const rows = targets.map((target) => `
    <tr>
      <td>${escapeHtml(target.name || target.target_id)}</td>
      <td>${escapeHtml(target.profile_id || "-")}</td>
      <td>${escapeHtml(target.template_pack_id || "-")}</td>
      <td>${escapeHtml(target.status || "-")}</td>
      <td>${escapeHtml(((target.latest_qa_summary || {}).status) || "-")}</td>
      <td>${escapeHtml(((target.latest_export_summary || {}).package_id) || "-")}</td>
      <td>${escapeHtml(((target.latest_signoff_summary || {}).status) || "not_signed")}</td>
      <td>
        <button class="secondary distribution-qa" data-target-id="${escapeHtml(target.target_id)}" type="button">QA</button>
        <button class="secondary distribution-export" data-target-id="${escapeHtml(target.target_id)}" type="button">Export</button>
        <button class="secondary distribution-zip" data-target-id="${escapeHtml(target.target_id)}" type="button">ZIP</button>
        <button class="secondary distribution-verify" data-target-id="${escapeHtml(target.target_id)}" type="button">Verify</button>
        <button class="secondary distribution-layout-preview" data-target-id="${escapeHtml(target.target_id)}" type="button">Layout</button>
        <button class="secondary distribution-sign" data-target-id="${escapeHtml(target.target_id)}" type="button">Sign</button>
        <button class="secondary distribution-checklist-init" data-target-id="${escapeHtml(target.target_id)}" type="button">Checklist</button>
        <button class="secondary distribution-checklist-done" data-target-id="${escapeHtml(target.target_id)}" type="button">Done</button>
        <button class="danger distribution-reset" data-target-id="${escapeHtml(target.target_id)}" type="button">Reset</button>
        ${((target.latest_export_summary || {}).package_id) ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(target.target_id)}/export.zip">Download</a>` : ""}
      </td>
    </tr>
  `).join("");
  return `
    <div class="panel-title subhead"><span>Distribution Prep</span></div>
    <div class="summary-grid">
      ${metric("Targets", targets.length)}
      ${metric("Latest", (distributionData.summary || {}).latest_status || "missing")}
      ${metric("Artwork", artwork.length)}
      ${metric("Signed", (distributionData.summary || {}).signed_target_count || 0)}
      ${metric("Templates", templatePacks.length)}
    </div>
    <div class="panel-title subhead"><span>Platform Template Packs</span></div>
    <div id="distribution-template-packs" class="grid2">
      <label>Template Slug <input id="distribution-template-slug" value="custom-local-template"></label>
      <label>Template Name <input id="distribution-template-name" value="Custom Local Template"></label>
    </div>
    <div class="actions">
      <button class="secondary" id="distribution-create-template" type="button">Create Template</button>
      <button class="secondary" id="distribution-clone-template" type="button">Clone Template</button>
    </div>
    <div class="grid2">
      <label>Profile
        <select id="distribution-profile">
          <option value="demo_pitch">Demo Pitch</option>
          <option value="generic_dsp">Generic DSP</option>
          <option value="internal_archive">Internal Archive</option>
        </select>
      </label>
      <label>Target Name
        <input id="distribution-target-name" value="Distribution Package">
      </label>
    </div>
    <label>Template Pack
      <select id="distribution-template-pack">
        <option value="">No Template</option>
        ${templateOptions}
      </select>
    </label>
    <div class="grid2">
      <label>Primary Audio Format
        <select id="distribution-primary-audio-format">
          <option value="wav_master">WAV Master</option>
          <option value="mp3_320">MP3 320</option>
          <option value="flac_lossless">FLAC Lossless</option>
          <option value="aac_256">AAC 256</option>
        </select>
      </label>
      <label>Audio Format Profiles
        <input id="distribution-audio-format-profiles" value="wav_master">
      </label>
    </div>
    <div class="grid2">
      <label>Artwork Filename
        <input id="distribution-artwork-filename" value="cover.png">
      </label>
      <label>Artwork Base64
        <input id="distribution-artwork-base64" placeholder="PNG/JPEG base64">
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="distribution-create-target" type="button">Create Target</button>
      <button class="secondary" id="distribution-import-artwork" type="button">Import Artwork</button>
    </div>
    <table>
      <thead><tr><th>Name</th><th>Profile</th><th>Template</th><th>Status</th><th>QA</th><th>Package</th><th>Signoff</th><th>Actions</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='8'>No distribution targets yet.</td></tr>"}</tbody>
    </table>
    <div id="distribution-layout-preview" class="panel">
      <div class="panel-title subhead"><span>Layout Preview</span></div>
      <div id="distribution-layout-summary" class="muted">Select a target to preview package paths.</div>
      <pre id="distribution-layout-file-tree"></pre>
      <div id="distribution-layout-entries"></div>
    </div>
  `;
}

function wireReleaseDistributionActions(release) {
  bindAction("distribution-create-template", async () => {
    await api(`/api/distribution/template-packs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: $("distribution-template-slug").value.trim(),
        name: $("distribution-template-name").value.trim(),
        rules: { require_artwork: true, require_upc: false, require_isrc: false, csv_formula_escape: true },
        metadata_mapping: { platform_csv: [{ column: "Title", source: "track.title", required: true }] },
        checklist: [{ item_id: "explicit-confirmed", label: "Explicit flag checked", required: true }]
      }),
    });
    await loadReleases();
  });
  bindAction("distribution-clone-template", async () => {
    const selected = $("distribution-template-pack").value || "tpl-generic-dsp-basic";
    await api(`/api/distribution/template-packs/${encodeURIComponent(selected)}/clone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: `${$("distribution-template-slug").value.trim() || "custom-local-template"}-copy` }),
    });
    await loadReleases();
  });
  bindAction("distribution-create-target", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: $("distribution-profile").value,
        template_pack_id: $("distribution-template-pack").value,
        name: $("distribution-target-name").value.trim(),
        options: {
          require_encoded_audio: $("distribution-primary-audio-format").value !== "wav_master",
          primary_audio_format: $("distribution-primary-audio-format").value,
          audio_format_profiles: $("distribution-audio-format-profiles").value.split(",").map((item) => item.trim()).filter(Boolean),
        },
      }),
    });
    await loadReleases();
  });
  bindAction("distribution-import-artwork", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/artwork/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: $("distribution-artwork-filename").value.trim(), content_base64: $("distribution-artwork-base64").value.trim() }),
    });
    await loadReleases();
  });
  document.querySelectorAll(".distribution-qa").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/qa/refresh`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".distribution-export").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/export`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".distribution-zip").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/export/zip`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".distribution-verify").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/verify`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".distribution-layout-preview").forEach((button) => button.addEventListener("click", async () => {
    const data = await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/layout`);
    const layout = data.layout || {};
    const summary = layout.summary || {};
    const entries = layout.entries || [];
    $("distribution-layout-summary").textContent = `status=${summary.status || "-"} audio=${summary.audio_count || 0} lyrics=${summary.lyrics_count || 0} artwork=${summary.artwork_count || 0} collisions=${summary.collision_count || 0}`;
    $("distribution-layout-file-tree").textContent = entries.map((entry) => entry.path || "").filter(Boolean).sort().join("\\n");
    $("distribution-layout-entries").innerHTML = `<table><thead><tr><th>Kind</th><th>Track</th><th>Path</th><th>Status</th></tr></thead><tbody>${entries.map((entry) => `<tr><td>${escapeHtml(entry.kind || "")}</td><td>${escapeHtml(entry.track_id || "-")}</td><td>${escapeHtml(entry.path || "")}</td><td>${escapeHtml(entry.status || "")}</td></tr>`).join("")}</tbody></table>`;
  }));
  document.querySelectorAll(".distribution-sign").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signed_by: "local-user" }),
    });
    await loadReleases();
  }));
  document.querySelectorAll(".distribution-checklist-init").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/checklist`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".distribution-checklist-done").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/checklist/items/explicit-confirmed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "done", note: "Checked locally" }),
    });
    await loadReleases();
  }));
  document.querySelectorAll(".distribution-reset").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/targets/${encodeURIComponent(button.dataset.targetId)}/signoff/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "Distribution package rebuild" }),
    });
    await loadReleases();
  }));
}

function releaseSubmissionsHtml(submissionData, distributionData, release) {
  const submissions = submissionData.submissions || [];
  const signedTargets = (distributionData.targets || []).filter((target) => target.status === "signed" || ((target.latest_signoff_summary || {}).status === "signed"));
  const targetOptions = signedTargets.map((target) => `<option value="${escapeHtml(target.target_id)}">${escapeHtml(target.name || target.target_id)} · ${escapeHtml(target.profile_id || "")}</option>`).join("");
  const rows = submissions.map((submission) => {
    const signoff = submission.latest_signoff_summary || {};
    const exportSummary = submission.latest_export_summary || {};
    const evidenceSummary = submission.latest_evidence_summary || {};
    return `
      <tr>
        <td>${escapeHtml(submission.submission_id)}</td>
        <td>${escapeHtml(submission.name || "")}</td>
        <td>${escapeHtml(submission.status || "")}</td>
        <td>${escapeHtml((submission.items || []).length)}</td>
        <td>${escapeHtml(signoff.status || "not_signed")}</td>
        <td>${escapeHtml(evidenceSummary.status || "not_started")} / ${escapeHtml(evidenceSummary.signoff_status || "not_signed")}</td>
        <td>
          <button class="secondary submission-refresh" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Refresh</button>
          <button class="secondary submission-qa" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">QA</button>
          <button class="secondary submission-export" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Export</button>
          <button class="secondary submission-zip" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">ZIP</button>
          <button class="secondary submission-verify" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Verify</button>
          <button class="secondary submission-sign" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Sign</button>
          <button class="secondary submission-evidence-report" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Evidence Report</button>
          <button class="secondary submission-evidence-export" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Evidence Export</button>
          <button class="secondary submission-evidence-zip" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Evidence ZIP</button>
          <button class="secondary submission-evidence-verify" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Evidence Verify</button>
          <button class="secondary submission-evidence-sign" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Evidence Sign</button>
          <button class="secondary submission-evidence-reset" data-submission-id="${escapeHtml(submission.submission_id)}" type="button">Reset Evidence</button>
          ${exportSummary.zip_filename ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submission.submission_id)}/export.zip">Download</a>` : ""}
        </td>
      </tr>
    `;
  }).join("");
  return `
    <div id="release-submissions" class="panel">
      <div class="panel-title subhead"><span>Submission Workspace</span></div>
      <div class="summary-grid">
        ${metric("Batches", (submissionData.summary || {}).submission_count || 0)}
        ${metric("Latest", (submissionData.summary || {}).latest_status || "missing")}
        ${metric("Signed", (submissionData.summary || {}).signed_count || 0)}
        ${metric("Accepted", (submissionData.summary || {}).accepted_count || 0)}
      </div>
      <div class="grid2">
        <label>Batch Name <input id="submission-name" value="Platform Submission"></label>
        <label>Target <select id="submission-target">${targetOptions}</select></label>
      </div>
      <div class="actions">
        <button class="secondary" id="submission-create" type="button">Create Batch</button>
        <button class="secondary" id="submission-add-target" type="button">Add Target</button>
        <button class="secondary" id="submission-record-submitted" type="button">Record Submitted</button>
        <button class="secondary" id="submission-record-feedback" type="button">Record Feedback</button>
        <button class="secondary" id="submission-mark-accepted" type="button">Mark Accepted</button>
      </div>
      <div id="submission-evidence" class="inline-note">Submission Evidence · upload-only attachments · no source_path</div>
      <table>
        <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Items</th><th>Signoff</th><th>Evidence</th><th>Actions</th></tr></thead>
        <tbody>${rows || "<tr><td colspan='7'>No submission batches yet.</td></tr>"}</tbody>
      </table>
    </div>
  `;
}

function firstSubmissionId() {
  const row = document.querySelector(".submission-refresh,.submission-qa,.submission-export,.submission-zip,.submission-verify,.submission-sign");
  return row ? row.dataset.submissionId : "";
}

function firstSubmissionItemId(submission) {
  const items = (submission && submission.items) || [];
  return items.length ? items[0].item_id : "";
}

Object.assign(globalThis, { wireReleaseActions, releaseDistributionHtml, wireReleaseDistributionActions, releaseSubmissionsHtml, firstSubmissionId, firstSubmissionItemId });

export { wireReleaseActions, releaseDistributionHtml, wireReleaseDistributionActions, releaseSubmissionsHtml, firstSubmissionId, firstSubmissionItemId };
