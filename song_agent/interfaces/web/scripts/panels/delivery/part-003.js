function wireReleaseSubmissionActions(release) {
  bindAction("submission-create", async () => {
    const targetId = $("submission-target").value;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: $("submission-name").value.trim() || "Platform Submission", target_ids: targetId ? [targetId] : [] }),
    });
    await loadReleases();
  });
  bindAction("submission-add-target", async () => {
    const submissionId = firstSubmissionId();
    if (!submissionId) return;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}/targets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: $("submission-target").value }),
    });
    await loadReleases();
  });
  document.querySelectorAll(".submission-refresh").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/refresh`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-qa").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/qa/refresh`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-export").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/export`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-zip").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/export/zip`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-verify").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deep: true }),
    });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-sign").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signed_by: "local-user" }),
    });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-evidence-report").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/report/refresh`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-evidence-export").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/export`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-evidence-zip").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/export/zip`, { method: "POST" });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-evidence-verify").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deep: true, require_submitted: true }),
    });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-evidence-sign").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/signoff`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signed_by: "local-user", require_submitted: true }),
    });
    await loadReleases();
  }));
  document.querySelectorAll(".submission-evidence-reset").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(button.dataset.submissionId)}/evidence/signoff/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "New submission evidence" }),
    });
    await loadReleases();
  }));
  bindAction("submission-record-submitted", async () => {
    const submissionId = firstSubmissionId();
    if (!submissionId) return;
    const data = await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}`);
    const itemId = firstSubmissionItemId(data.submission);
    if (!itemId) return;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}/items/${encodeURIComponent(itemId)}/record-submission`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ external_reference: "local-submission" }),
    });
    await loadReleases();
  });
  bindAction("submission-record-feedback", async () => {
    const submissionId = firstSubmissionId();
    if (!submissionId) return;
    const data = await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}`);
    const itemId = firstSubmissionItemId(data.submission);
    if (!itemId) return;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}/items/${encodeURIComponent(itemId)}/record-feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "needs_changes", message: "Local feedback" }),
    });
    await loadReleases();
  });
  bindAction("submission-mark-accepted", async () => {
    const submissionId = firstSubmissionId();
    if (!submissionId) return;
    const data = await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}`);
    const itemId = firstSubmissionItemId(data.submission);
    if (!itemId) return;
    await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions/${encodeURIComponent(submissionId)}/items/${encodeURIComponent(itemId)}/accepted`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ external_reference: "accepted-local" }),
    });
    await loadReleases();
  });
}

function deliverySignoffPayload(force) {
  return {
    force,
    override_reason: $("project-delivery-override-reason").value.trim(),
    signed_by: $("project-delivery-signed-by").value.trim() || "local-user",
    notes: $("project-delivery-notes").value.trim(),
  };
}

function deliveryQaHtml(qaData, signoffData) {
  const summary = (qaData && qaData.summary) || {};
  const report = (qaData && qaData.delivery_qa) || {};
  const signoffSummary = (signoffData && signoffData.summary) || { status: "not_signed" };
  const signoff = (signoffData && signoffData.signoff) || {};
  const zip = report.zip || {};
  const artifact = report.artifact_integrity || {};
  const checks = report.checks || [];
  const files = artifact.files || [];
  const signed = signoffSummary.status === "signed" || signoffSummary.status === "force_signed";
  const canSign = summary.handoff_allowed && !signed;
  const canForce = !signed;
  return `
    <div class="panel">
      <div class="panel-title">Delivery QA</div>
      <div class="summary-grid">
        ${metric("Status", summary.status || "-")}
        ${metric("Readiness", summary.readiness || "-")}
        ${metric("Handoff", summary.handoff_allowed ? "yes" : "-")}
        ${metric("Final Version", summary.final_version_id || "-")}
      </div>
      <div class="summary-grid">
        ${metric("Blockers", summary.blocker_count || 0)}
        ${metric("Warnings", summary.warning_count || 0)}
        ${metric("Artifacts", artifact.checked_count || summary.artifact_count || 0)}
        ${metric("Missing", artifact.missing_count || summary.missing_artifact_count || 0)}
      </div>
      <div class="summary-grid">
        ${metric("ZIP", zip.exists ? "ok" : "-")}
        ${metric("ZIP Entries", zip.entry_count || 0)}
        ${metric("ZIP Match", zip.matches_manifest ? "yes" : "-")}
        ${metric("ZIP SHA", (zip.sha256 || "").slice(0, 12) || "-")}
      </div>
      <div class="grid2">
        <label>Signed By
          <input id="project-delivery-signed-by" value="${escapeHtml(signoff.signed_by || "local-user")}">
        </label>
        <label>Reset Reason
          <input id="project-delivery-reset-reason" placeholder="Reason required before reset">
        </label>
      </div>
      <label>Notes
        <textarea id="project-delivery-notes" rows="2">${escapeHtml(signoff.notes || "")}</textarea>
      </label>
      <label>Override Reason
        <textarea id="project-delivery-override-reason" rows="2" placeholder="Required for force sign"></textarea>
      </label>
      <div class="actions">
        <button class="secondary" id="project-refresh-delivery-qa" type="button">Refresh Delivery QA</button>
        <button id="project-sign-delivery" type="button" ${canSign ? "" : "disabled"}>Sign Delivery</button>
        <button class="secondary" id="project-force-sign-delivery" type="button" ${canForce ? "" : "disabled"}>Force Sign</button>
        <button class="danger" id="project-reset-delivery-signoff" type="button" ${signed ? "" : "disabled"}>Reset Signoff</button>
      </div>
      <div class="summary-grid">
        ${metric("Signoff", signoffSummary.status || "not_signed")}
        ${metric("Signed At", signoffSummary.signed_at || "-")}
        ${metric("Forced", signoffSummary.forced ? "yes" : "-")}
        ${metric("Signoff Version", signoffSummary.final_version_id || "-")}
      </div>
      ${deliveryChecksHtml(checks)}
      ${deliveryArtifactsHtml(files)}
    </div>
  `;
}

function projectAddToReleaseHtml(targets) {
  const releases = targets.releases || [];
  const options = releases.map((release) => `<option value="${escapeHtml(release.release_id)}">${escapeHtml(release.name || release.release_id)} · ${escapeHtml(release.status || "-")}</option>`).join("");
  return `
    <div class="panel-title subhead"><span>Add to Release</span></div>
    <div class="grid2">
      <label>Release
        <select id="project-release-target">${options}</select>
      </label>
      <label>Track Title
        <input id="project-release-track-title" placeholder="optional title override">
      </label>
    </div>
    <div class="actions">
      <button class="secondary" id="project-add-to-release" type="button" ${releases.length ? "" : "disabled"}>Add to Release</button>
      <span class="message">${escapeHtml(targets.error || "")}</span>
    </div>
  `;
}

function deliveryChecksHtml(checks) {
  const rows = checks.map((check) => `
    <tr>
      <td>${escapeHtml(check.severity || "-")}</td>
      <td>${escapeHtml(check.check_id || "-")}</td>
      <td><span class="status ${escapeHtml(check.status || "")}">${escapeHtml(check.status || "-")}</span></td>
      <td>${escapeHtml(check.count ?? "-")}</td>
      <td>${escapeHtml(check.message || "-")}</td>
    </tr>
  `).join("");
  return `
    <table>
      <thead><tr><th>Severity</th><th>Check</th><th>Status</th><th>Count</th><th>Message</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='5'>No checks yet.</td></tr>"}</tbody>
    </table>
  `;
}

function deliveryArtifactsHtml(files) {
  const rows = files.slice(0, 80).map((file) => `
    <tr>
      <td>${escapeHtml(file.kind || "-")}</td>
      <td>${escapeHtml(file.path || "-")}</td>
      <td>${file.required ? "yes" : "-"}</td>
      <td>${file.exists ? "yes" : "-"}</td>
      <td>${escapeHtml(file.size_bytes ?? "-")}</td>
      <td>${escapeHtml((file.sha256 || "").slice(0, 12) || "-")}</td>
    </tr>
  `).join("");
  return `
    <table>
      <thead><tr><th>Kind</th><th>Path</th><th>Required</th><th>Exists</th><th>Size</th><th>SHA</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='6'>No artifacts.</td></tr>"}</tbody>
    </table>
  `;
}

Object.assign(globalThis, { wireReleaseSubmissionActions, deliverySignoffPayload, deliveryQaHtml, projectAddToReleaseHtml, deliveryChecksHtml, deliveryArtifactsHtml });

export { wireReleaseSubmissionActions, deliverySignoffPayload, deliveryQaHtml, projectAddToReleaseHtml, deliveryChecksHtml, deliveryArtifactsHtml };
