async function loadGaHealth() {
  try {
    const data = await api("/api/ga");
    renderGaHealth(data.report || {});
  } catch (err) {
    $("ga-status").textContent = "failed";
    $("ga-status").className = "status failed";
    $("ga-check-result").textContent = err.message;
  }
}

function renderGaHealth(report) {
  const status = report.status || "unknown";
  $("ga-status").textContent = status;
  $("ga-status").className = `status ${status === "ready" ? "completed" : status === "blocked" ? "failed" : "running"}`;
  const summary = report.summary || {};
  $("ga-summary").innerHTML = `
    ${metric("GA", status)}
    ${metric("Doctor", summary.doctor_status || "unknown")}
    ${metric("Manual Review", summary.acceptance_status || "unknown")}
    ${metric("Final Readiness", summary.trust_final_readiness_status || "unknown")}
  `;
  const actions = report.next_actions || [];
  $("ga-check-result").textContent = JSON.stringify({
    status,
    summary,
    next_actions: actions.slice(0, 8),
  }, null, 2);
}

async function loadMaintenanceStatus() {
  try {
    const data = await api("/api/maintenance/status");
    renderMaintenanceStatus(data.status || {});
  } catch (err) {
    $("maintenance-status").textContent = "failed";
    $("maintenance-status").className = "status failed";
    $("maintenance-result").textContent = err.message;
  }
}

function renderMaintenanceStatus(statusDoc) {
  const status = statusDoc.status || "unknown";
  $("maintenance-status").textContent = status;
  $("maintenance-status").className = `status ${status === "ready" ? "completed" : status === "blocked" ? "failed" : "running"}`;
  const backups = statusDoc.backups || {};
  const migration = statusDoc.migration || {};
  const checks = statusDoc.checks || {};
  $("maintenance-summary").innerHTML = `
    ${metric("LTS", status)}
    ${metric("Backup", (backups.latest || {}).verification_status || (backups.latest || {}).status || "missing")}
    ${metric("Migration", migration.status || "unknown")}
    ${metric("Check", (checks.latest || {}).status || "missing")}
  `;
  $("maintenance-result").textContent = JSON.stringify({
    status,
    version: statusDoc.version,
    warnings: (statusDoc.warnings || []).slice(0, 8),
    blockers: (statusDoc.blockers || []).slice(0, 8),
  }, null, 2);
}

Object.assign(globalThis, { loadGaHealth, renderGaHealth, loadMaintenanceStatus, renderMaintenanceStatus });

export { loadGaHealth, renderGaHealth, loadMaintenanceStatus, renderMaintenanceStatus };
