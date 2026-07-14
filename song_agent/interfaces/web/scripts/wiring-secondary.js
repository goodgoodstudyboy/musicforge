bindAction("ga-check-run", async () => {
  const data = await api("/api/ga/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ require_manual_acceptance: false, require_final_readiness: false }),
  });
  renderGaHealth(data.report || {});
});

bindAction("ga-docs-index", async () => {
  const data = await api("/api/docs/index");
  $("ga-check-result").textContent = JSON.stringify(data, null, 2);
});

bindAction("maintenance-refresh", async () => {
  await loadMaintenanceStatus();
});

bindAction("maintenance-create-backup", async () => {
  const data = await api("/api/maintenance/backups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: "workspace" }),
  });
  $("maintenance-result").textContent = JSON.stringify(data, null, 2);
  await loadMaintenanceStatus();
});

bindAction("maintenance-backup-list", async () => {
  const data = await api("/api/maintenance/backups");
  $("maintenance-result").textContent = JSON.stringify(data, null, 2);
});

bindAction("maintenance-run-preflight", async () => {
  const data = await api("/api/maintenance/upgrade/preflight", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ require_verified_backup: true, allow_dirty: true }),
  });
  $("maintenance-result").textContent = JSON.stringify(data, null, 2);
  await loadMaintenanceStatus();
});

bindAction("maintenance-run-weekly", async () => {
  const data = await api("/api/maintenance/checks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile: "weekly" }),
  });
  $("maintenance-result").textContent = JSON.stringify(data, null, 2);
  await loadMaintenanceStatus();
});

bindAction("maintenance-run-migration", async () => {
  const data = await api("/api/maintenance/migrations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ require_backup: false }),
  });
  $("maintenance-result").textContent = JSON.stringify(data, null, 2);
  await loadMaintenanceStatus();
});














bindAction("continuity-receiver-refresh", async () => {
  await showContinuityReceiver(continuityReceiverBase());
});
bindAction("continuity-receiver-review-pack", async () => {
  await showContinuityReceiver(`${continuityReceiverBase()}/review-pack`, { method: "POST" });
});
bindAction("continuity-receiver-verify-pack", async () => {
  await showContinuityReceiver(`${continuityReceiverBase()}/review-pack/verify`, { method: "POST" });
});
bindAction("continuity-receiver-import", async () => {
  const response = JSON.parse($("continuity-receiver-response").value || "{}");
  const verification = JSON.parse($("continuity-receiver-response-verification").value || "{}");
  const binding = JSON.parse($("continuity-receiver-response-binding").value || "{}");
  await showContinuityReceiver(`${continuityReceiverBase()}/responses/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ response, response_verification_report: verification, response_binding_summary: binding }),
  });
});
bindAction("continuity-receiver-accept", async () => {
  const responseId = $("continuity-receiver-response-id").value.trim();
  if (!responseId) throw new Error("Response ID is required.");
  await showContinuityReceiver(`${continuityReceiverBase()}/responses/${encodeURIComponent(responseId)}/accepted-evidence`, { method: "POST" });
});
bindAction("continuity-receiver-board", async () => {
  await showContinuityReceiver(`${continuityReceiverBase()}/board/refresh`, { method: "POST" });
});
bindAction("continuity-receiver-signoff", async () => {
  const signedBy = $("continuity-receiver-signed-by").value.trim();
  await showContinuityReceiver(`${continuityReceiverBase()}/signoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ signed_by: signedBy || "receiver-acceptance-chair", role: "program_owner" }),
  });
});
bindAction("continuity-receiver-zip", async () => {
  await showContinuityReceiver(`${continuityReceiverBase()}/archive/zip`, { method: "POST" });
});
bindAction("continuity-receiver-verify", async () => {
  await showContinuityReceiver(`${continuityReceiverBase()}/archive/verify`, { method: "POST" });
});




bindAction("continuity-receiver-change-refresh", async () => {
  await showContinuityReceiver(continuityReceiverChangeBase());
});
bindAction("continuity-receiver-change-create", async () => {
  const reason = $("continuity-receiver-change-reason").value.trim();
  const data = await showContinuityReceiver(`${continuityReceiverChangeBase()}/cr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || "Receiver acceptance scope changed", allowed_actions: ["reset_receiver_acceptance_signoff"] }),
  });
  const requestId = (data.change_request || {}).change_request_id;
  if (requestId) $("continuity-receiver-change-request-id").value = requestId;
});
bindAction("continuity-receiver-change-approve", async () => {
  const requestId = $("continuity-receiver-change-request-id").value.trim();
  if (!requestId) throw new Error("Change Request ID is required.");
  await showContinuityReceiver(`${continuityReceiverChangeBase()}/cr/${encodeURIComponent(requestId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_by: "release-owner", approved_actions: ["reset_receiver_acceptance_signoff"] }),
  });
});
bindAction("continuity-receiver-change-reset", async () => {
  const requestId = $("continuity-receiver-change-request-id").value.trim();
  if (!requestId) throw new Error("Change Request ID is required.");
  await showContinuityReceiver(`${continuityReceiverChangeBase()}/cr/${encodeURIComponent(requestId)}/reset-signoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reset_by: "continuity-operator" }),
  });
});
bindAction("continuity-receiver-change-lifecycle", async () => {
  await showContinuityReceiver(`${continuityReceiverChangeBase()}/lifecycle`, { method: "POST" });
});
bindAction("continuity-receiver-change-zip", async () => {
  await showContinuityReceiver(`${continuityReceiverChangeBase()}/zip`, { method: "POST" });
});
bindAction("continuity-receiver-change-verify", async () => {
  await showContinuityReceiver(`${continuityReceiverChangeBase()}/verify`, { method: "POST" });
});



























init().catch((err) => {
  document.body.innerHTML = `<pre>${escapeHtml(err.stack || err.message)}</pre>`;
});
