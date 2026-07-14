function reviewSprintRowHtml(project, sprint, taskOptions, versions) {
  const summary = sprint.summary || {};
  const counts = summary.counts || sprint.counts || {};
  const report = sprint.conflict_report || {};
  const conflicts = Array.isArray(report.conflicts) ? report.conflicts : [];
  const recommendationReport = sprint.recommendation_report || {};
  const recommendationSummary = sprint.recommendation_summary || {};
  const recommendationActions = Array.isArray(recommendationReport.recommended_actions) ? recommendationReport.recommended_actions : [];
  const latestQueue = sprint.latest_action_queue || {};
  const actionQueueSummary = sprint.action_queue_summary || {};
  const metricsReport = sprint.metrics_report || {};
  const metricsSummary = sprint.metrics_summary || {};
  const judgeSummary = sprint.judge_summary || {};
  const closeoutReport = sprint.closeout_report || {};
  const closeoutSummary = sprint.closeout_summary || {};
  const signoff = sprint.signoff || {};
  const signoffSummary = sprint.signoff_summary || {};
  const taskIds = (sprint.task_refs || []).filter((ref) => ref.included !== false).sort((a, b) => Number(a.order || 0) - Number(b.order || 0)).map((ref) => ref.task_id);
  const mutable = ["open", "in_progress", "blocked"].includes(sprint.status);
  return `
    <div class="review-sprint-row">
      <h4>${escapeHtml(sprint.name || sprint.sprint_id)} <span class="status ${escapeHtml(sprint.status || "")}">${escapeHtml(sprint.status || "-")}</span></h4>
      <div class="summary-grid">
        ${metric("Sprint", sprint.sprint_id)}
        ${metric("Parent", sprint.parent_version_id || "-")}
        ${metric("Tasks", taskIds.length)}
        ${metric("Ready", counts.ready_candidate_count ?? 0)}
        ${metric("Local", counts.local_candidate_count ?? 0)}
        ${metric("Provider", counts.provider_candidate_count ?? 0)}
        ${metric("Applied", counts.applied ?? 0)}
        ${metric("Conflicts", counts.conflict_count ?? conflicts.length)}
        ${metric("Blocking", counts.blocking_conflict_count ?? 0)}
        ${metric("Queues", actionQueueSummary.queue_count ?? 0)}
        ${metric("Queue Status", actionQueueSummary.latest_status || "-")}
      </div>
      <div class="empty small">${escapeHtml(taskIds.join(" · ") || "No tasks")}</div>
      ${conflicts.length ? `<div class="review-conflict-list">${conflicts.slice(0, 8).map((conflict) => reviewSprintConflictHtml(conflict)).join("")}</div>` : `<div class="empty small">No conflicts reported.</div>`}
      ${reviewSprintRecommendationsHtml(sprint, recommendationSummary, recommendationActions)}
      ${reviewSprintActionQueueHtml(sprint, latestQueue, actionQueueSummary)}
      ${reviewSprintJudgeSummaryHtml(sprint, judgeSummary)}
      ${reviewSprintDashboardHtml(sprint, metricsSummary, metricsReport)}
      ${reviewSprintCloseoutHtml(sprint, closeoutReport, closeoutSummary, signoff, signoffSummary, versions || [])}
      <div class="actions">
        <select id="review-sprint-add-task-${escapeHtml(sprint.sprint_id)}" style="max-width:260px;" ${mutable ? "" : "disabled"}>
          <option value="">Add task</option>
          ${taskOptions}
        </select>
        <button class="secondary" data-review-sprint-add-task="${escapeHtml(sprint.sprint_id)}" type="button" ${mutable ? "" : "disabled"}>Add Task</button>
        <button class="secondary" data-review-sprint-refresh="${escapeHtml(sprint.sprint_id)}" type="button">Refresh Sprint</button>
        <button class="secondary" data-review-sprint-conflicts="${escapeHtml(sprint.sprint_id)}" type="button">Refresh Conflicts</button>
        <button class="secondary" data-review-sprint-recommendations="${escapeHtml(sprint.sprint_id)}" type="button">Refresh Recommendations</button>
        <button class="secondary" data-review-sprint-judge="${escapeHtml(sprint.sprint_id)}" type="button">Refresh Sprint Judge</button>
        <button class="secondary" data-review-sprint-metrics="${escapeHtml(sprint.sprint_id)}" type="button">Refresh Metrics</button>
        <button class="secondary" data-review-sprint-closeout="${escapeHtml(sprint.sprint_id)}" type="button">Refresh Closeout</button>
        <button class="secondary" data-review-sprint-local="${escapeHtml(sprint.sprint_id)}" type="button" ${mutable ? "" : "disabled"}>Generate Sprint Local</button>
        <button class="secondary" data-review-sprint-provider="${escapeHtml(sprint.sprint_id)}" type="button" ${mutable ? "" : "disabled"}>Generate Sprint Provider</button>
        <button class="secondary" data-review-sprint-close="${escapeHtml(sprint.sprint_id)}" type="button" ${mutable ? "" : "disabled"}>Close Sprint</button>
        <button class="danger" data-review-sprint-archive="${escapeHtml(sprint.sprint_id)}" type="button" ${sprint.status === "archived" ? "disabled" : ""}>Archive Sprint</button>
      </div>
      ${sprint.recommendation_error ? `<div class="empty error">${escapeHtml(sprint.recommendation_error)}</div>` : ""}
      <pre>${escapeHtml(JSON.stringify({ summary, conflict_report: report, recommendation_summary: recommendationSummary, judge_summary: judgeSummary, action_queue_summary: actionQueueSummary, metrics_summary: metricsSummary, closeout_summary: closeoutSummary, signoff_summary: signoffSummary, settings: sprint.settings }, null, 2))}</pre>
    </div>
  `;
}

function reviewSprintCloseoutHtml(sprint, report, summary, signoff, signoffSummary, versions) {
  const checks = Array.isArray(report.checks) ? report.checks : [];
  const blockers = Array.isArray(report.blockers) ? report.blockers : [];
  const warnings = Array.isArray(report.warnings) ? report.warnings : [];
  const versionOptions = (versions || []).map((version) => `<option value="${escapeHtml(version.version_id || "")}">${escapeHtml(version.version_id || "")} · ${escapeHtml(version.name || version.status || "")}</option>`).join("");
  const forceVisible = !summary.close_allowed && sprint.status !== "closed" && sprint.status !== "archived";
  const checkRows = checks.slice(0, 12).map((check) => `
    <tr>
      <td><span class="status ${escapeHtml(check.severity || "")}">${escapeHtml(check.severity || "-")}</span></td>
      <td>${escapeHtml(check.check_id || "-")}</td>
      <td><span class="status ${escapeHtml(check.status || "")}">${escapeHtml(check.status || "-")}</span></td>
      <td>${escapeHtml(check.count ?? "-")}</td>
      <td>${escapeHtml(check.message || "-")}</td>
    </tr>
  `).join("");
  return `
    <div class="review-sprint-dashboard">
      <h5>Closeout</h5>
      <div class="summary-grid">
        ${metric("Status", summary.status || report.status || "-")}
        ${metric("Readiness", summary.readiness || report.readiness || "-")}
        ${metric("Close Allowed", summary.close_allowed ? "yes" : "no")}
        ${metric("Blockers", summary.blocker_count ?? blockers.length)}
        ${metric("Warnings", summary.warning_count ?? warnings.length)}
        ${metric("Recommended Final", summary.recommended_final_version_id || ((report.recommended_final_version || {}).version_id) || "-")}
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Severity</th><th>Check</th><th>Status</th><th>Count</th><th>Message</th></tr></thead>
          <tbody>${checkRows || `<tr><td colspan="5">Refresh Closeout to build gate checks.</td></tr>`}</tbody>
        </table>
      </div>
      ${forceVisible ? `
        <div class="grid2">
          <label>Override reason
            <textarea id="review-sprint-force-reason-${escapeHtml(sprint.sprint_id)}" placeholder="Required for force close"></textarea>
          </label>
          <label>Signoff notes
            <textarea id="review-sprint-close-notes-${escapeHtml(sprint.sprint_id)}" placeholder="Accepted after local playback"></textarea>
          </label>
          <label>Selected version
            <select id="review-sprint-selected-version-${escapeHtml(sprint.sprint_id)}">
              <option value="">Recommended / current</option>
              ${versionOptions}
            </select>
          </label>
        </div>
        <div class="actions">
          <button class="danger" data-review-sprint-force-close="${escapeHtml(sprint.sprint_id)}" type="button">Force Close</button>
        </div>
      ` : ""}
      <h5>Signoff</h5>
      <div class="summary-grid">
        ${metric("Signoff", signoffSummary.status || "not_signed")}
        ${metric("Signed At", signoffSummary.signed_at || "-")}
        ${metric("Signed By", signoffSummary.signed_by || "-")}
        ${metric("Forced", signoffSummary.forced ? "yes" : "no")}
        ${metric("Selected Version", signoffSummary.selected_version_id || "-")}
        ${metric("Closeout Status", signoffSummary.closeout_status || "-")}
      </div>
      ${signoff && Object.keys(signoff).length ? `<pre>${escapeHtml(JSON.stringify({ signoff_summary: signoffSummary, acknowledged_blockers: signoff.acknowledged_blockers || [], acknowledged_warnings: signoff.acknowledged_warnings || [] }, null, 2))}</pre>` : `<div class="empty small">No Sprint Signoff yet.</div>`}
    </div>
  `;
}

function reviewSprintJudgeSummaryHtml(sprint, summary) {
  const top = summary.top_judge_recommendation || {};
  return `
    <div class="review-sprint-dashboard">
      <h5>Judge Summary</h5>
      <div class="empty small">Judge summaries are advisory and provider-safe actions require explicit provider approval.</div>
      <div class="summary-grid">
        ${metric("Judged Tasks", summary.judged_task_count ?? 0)}
        ${metric("Stale Judge", summary.stale_judge_count ?? 0)}
        ${metric("Judge Tokens", summary.judge_provider_tokens ?? 0)}
        ${metric("High Risk", summary.high_risk_candidate_count ?? 0)}
        ${metric("Top Judge", top.task_id ? `${top.task_id} / ${top.recommended_candidate_id || "-"}` : "-")}
      </div>
    </div>
  `;
}

function reviewSprintDashboardHtml(sprint, summary, report) {
  const candidate = report.candidate_funnel || {};
  const queue = report.action_queue_execution || {};
  const provider = report.provider_usage || {};
  const quality = report.quality_delta || {};
  const risk = report.risk_readiness || {};
  const judge = report.judge_metrics || {};
  const warnings = Array.isArray(report.warnings) ? report.warnings : [];
  const statusRows = Object.entries((report.task_throughput || {}).task_status_counts || {}).map(([status, count]) => `<tr><td>${escapeHtml(status)}</td><td>${escapeHtml(count)}</td></tr>`).join("");
  const sourceRows = Object.entries(candidate.candidate_source_counts || {}).map(([source, count]) => `<tr><td>${escapeHtml(source)}</td><td>${escapeHtml(count)}</td></tr>`).join("");
  return `
    <div class="review-sprint-dashboard">
      <h5>Dashboard</h5>
      <div class="summary-grid">
        ${metric("Readiness", summary.readiness || risk.readiness || "-")}
        ${metric("Completion", summary.completion_rate == null ? "-" : `${Math.round(Number(summary.completion_rate) * 100)}%`)}
        ${metric("Candidates", summary.candidate_count ?? candidate.candidate_count ?? 0)}
        ${metric("Provider Tokens", summary.provider_tokens ?? provider.total_tokens ?? 0)}
        ${metric("Judged Tasks", (summary.judge_metrics || {}).judged_task_count ?? judge.judged_task_count ?? 0)}
        ${metric("Judge Tokens", (summary.judge_metrics || {}).judge_provider_tokens ?? judge.judge_provider_tokens ?? 0)}
        ${metric("Quality Delta", summary.quality_delta ?? quality.overall_delta ?? quality.status ?? "-")}
        ${metric("Warnings", summary.warning_count ?? warnings.length)}
      </div>
      <div class="grid2">
        <div class="table-scroll">
          <table>
            <thead><tr><th>Task Status</th><th>Count</th></tr></thead>
            <tbody>${statusRows || `<tr><td colspan="2">No task metrics.</td></tr>`}</tbody>
          </table>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Candidate Source</th><th>Count</th></tr></thead>
            <tbody>${sourceRows || `<tr><td colspan="2">No candidate metrics.</td></tr>`}</tbody>
          </table>
        </div>
      </div>
      <div class="summary-grid">
        ${metric("Queue Completed", queue.completed_action_count ?? 0)}
        ${metric("Queue Failed", queue.failed_action_count ?? 0)}
        ${metric("Manual Decisions", (report.manual_decisions || {}).manual_apply_count ?? 0)}
        ${metric("Provider Calls", provider.provider_call_count ?? 0)}
      </div>
      ${warnings.length ? `<div class="review-conflict-list">${warnings.slice(0, 8).map((warning) => `<div class="review-conflict warning">${escapeHtml(warning)}</div>`).join("")}</div>` : `<div class="empty small">No dashboard warnings.</div>`}
    </div>
  `;
}

function reviewSprintRecommendationsHtml(sprint, summary, actions) {
  const top = summary.top_recommendation || {};
  const rows = (actions || []).slice(0, 8).map((action) => {
    const preview = action.context_pack_preview || {};
    const assetCount = Array.isArray(preview.asset_refs) ? preview.asset_refs.length : 0;
    const referenceCount = Array.isArray(preview.reference_refs) ? preview.reference_refs.length : 0;
    const canSaveContext = assetCount + referenceCount > 0;
    return `
      <tr>
        <td>${escapeHtml(action.rank ?? "-")}</td>
        <td>${escapeHtml(action.task_id || "-")}</td>
        <td><span class="status ${escapeHtml(action.action || "")}">${escapeHtml(action.action || "-")}</span></td>
        <td>${escapeHtml(action.score ?? "-")}</td>
        <td>${escapeHtml(action.reason || "-")}</td>
        <td>${escapeHtml(`${assetCount} assets / ${referenceCount} refs`)}</td>
        <td><button class="secondary" data-review-sprint-save-context data-sprint-id="${escapeHtml(sprint.sprint_id)}" data-task-id="${escapeHtml(action.task_id || "")}" type="button" ${canSaveContext ? "" : "disabled"}>Save Context Pack</button></td>
      </tr>
    `;
  }).join("");
  return `
    <div class="review-sprint-recommendations">
      <h5>Recommendations</h5>
      <div class="empty small">Recommendations only rank next steps. Applying candidates still requires manual confirmation.</div>
      <div class="summary-grid">
        ${metric("Next Action", summary.next_action || top.action || "-")}
        ${metric("Open Recommendations", summary.open_recommendation_count ?? 0)}
        ${metric("Context Packs", summary.context_recommendation_count ?? 0)}
        ${metric("Ready To Close", summary.ready_to_close ? "yes" : "no")}
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Rank</th><th>Task</th><th>Recommended Action</th><th>Score</th><th>Reason</th><th>Context</th><th>Pack</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="7">Refresh recommendations to build a Sprint Recommendation Report.</td></tr>`}</tbody>
        </table>
      </div>
    </div>
  `;
}

function reviewSprintActionQueueHtml(sprint, queue, summary) {
  const queueId = queue.queue_id || "";
  const items = Array.isArray(queue.items) ? queue.items : [];
  const rows = items.map((item) => {
    const isRunnable = ["auto_safe", "provider_safe"].includes(item.safety) && ["pending", "failed"].includes(item.status);
    const result = item.result && Object.keys(item.result).length ? JSON.stringify(item.result) : "";
    return `
      <tr>
        <td><input data-review-sprint-queue-item="${escapeHtml(queueId)}" data-safety="${escapeHtml(item.safety || "")}" value="${escapeHtml(item.item_id || "")}" type="checkbox" ${isRunnable ? "" : "disabled"}></td>
        <td>${escapeHtml(item.rank ?? "-")}</td>
        <td>${escapeHtml(item.task_id || "-")}</td>
        <td><span class="status ${escapeHtml(item.action || "")}">${escapeHtml(actionQueueActionLabel(item.action))}</span></td>
        <td><span class="status ${escapeHtml(item.safety || "")}">${escapeHtml(item.safety || "-")}</span></td>
        <td><span class="status ${escapeHtml(item.status || "")}">${escapeHtml(item.status === "manual_required" ? "manual required" : item.status || "-")}</span></td>
        <td>${escapeHtml(item.reason || "-")}</td>
        <td>${escapeHtml(result || item.error || "-")}</td>
      </tr>
    `;
  }).join("");
  return `
    <div class="review-sprint-action-queue">
      <h5>Action Queue</h5>
      <div class="summary-grid">
        ${metric("Latest Queue", queueId || "-")}
        ${metric("Status", queue.status || "-")}
        ${metric("Completed", summary.completed_action_count ?? (queue.summary || {}).completed ?? 0)}
        ${metric("Manual Required", summary.manual_required_count ?? (queue.summary || {}).manual_required ?? 0)}
        ${metric("Failed", summary.failed_action_count ?? (queue.summary || {}).failed ?? 0)}
      </div>
      <div class="grid2">
        <label><input id="review-sprint-queue-refresh-${escapeHtml(sprint.sprint_id)}" type="checkbox" checked> Refresh recommendations before creating</label>
        <label><input id="review-sprint-queue-context-${escapeHtml(sprint.sprint_id)}" type="checkbox" checked> Include context pack save actions</label>
      </div>
      <div class="actions">
        <button class="secondary" data-review-sprint-queue="${escapeHtml(sprint.sprint_id)}" type="button">Create Queue from Recommendations</button>
        ${queueId ? `<button class="secondary" data-review-sprint-queue-select-safe data-queue-id="${escapeHtml(queueId)}" type="button">Select Safe Actions</button>` : ""}
        ${queueId ? `<label style="display:inline-flex;align-items:center;gap:6px;"><input id="review-sprint-queue-provider-${escapeHtml(sprint.sprint_id)}-${escapeHtml(queueId)}" type="checkbox"> Allow provider actions</label>` : ""}
        ${queueId ? `<button class="secondary" data-review-sprint-run-queue data-sprint-id="${escapeHtml(sprint.sprint_id)}" data-queue-id="${escapeHtml(queueId)}" type="button">Run Selected Safe Actions</button>` : ""}
        ${queueId ? `<button class="secondary" data-review-sprint-run-all-queue data-sprint-id="${escapeHtml(sprint.sprint_id)}" data-queue-id="${escapeHtml(queueId)}" type="button">Run All Safe Actions</button>` : ""}
        ${queueId ? `<button class="danger" data-review-sprint-archive-queue data-sprint-id="${escapeHtml(sprint.sprint_id)}" data-queue-id="${escapeHtml(queueId)}" type="button">Archive Queue</button>` : ""}
      </div>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Select</th><th>Rank</th><th>Task</th><th>Action</th><th>Safety</th><th>Status</th><th>Reason</th><th>Result</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="8">Create an Action Queue from the latest recommendations.</td></tr>`}</tbody>
        </table>
      </div>
    </div>
  `;
}

function reviewSprintConflictHtml(conflict) {
  return `
    <div class="review-conflict ${escapeHtml(conflict.severity || "")}">
      <strong>${escapeHtml(conflict.kind || "conflict")}</strong>
      <span class="status ${escapeHtml(conflict.severity || "")}">${escapeHtml(conflict.severity || "-")}</span>
      <div>${escapeHtml(conflict.message || "")}</div>
      <div class="empty small">${escapeHtml((conflict.task_ids || []).join(" · "))}</div>
    </div>
  `;
}

async function renderProjectCandidates(project, versions, target) {
  const parentId = projectEditParentId || project.selected_version_id || project.final_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
  let groups = [];
  let usage = null;
  let experiments = [];
  try {
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/candidate-groups`);
    groups = data.groups || [];
    const usageData = await api(`/api/projects/${encodeURIComponent(project.project_id)}/usage/provider`);
    usage = usageData;
    const abData = await api(`/api/projects/${encodeURIComponent(project.project_id)}/prompt-ab`);
    experiments = abData.experiments || [];
  } catch (err) {
    target.innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
    return;
  }
  target.innerHTML = projectCandidateControls(versions, parentId, groups, usage, experiments);
  renderAssetSelectors();
  renderReferenceSelectors();
  renderContextPackSelectors();
  const parentSelect = $("project-candidate-parent");
  if (parentSelect) {
    parentSelect.addEventListener("change", async () => {
      projectEditParentId = parentSelect.value;
      await renderProjectCandidates(project, versions, target);
    });
  }
  bindAction("project-generate-candidates", async () => {
    const parent = $("project-candidate-parent").value;
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit-candidates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectCandidatePayload()),
    });
    await renderProjectCandidates(project, versions, target);
  });
  bindAction("project-generate-candidates-ab", async () => {
    const parent = $("project-candidate-parent").value;
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit-candidates/ab`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectCandidateABPayload()),
    });
    await renderProjectCandidates(project, versions, target);
  });
  target.querySelectorAll("[data-render-candidate-midi]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/candidate-groups/${encodeURIComponent(button.dataset.groupId)}/candidates/${encodeURIComponent(button.dataset.candidateId)}/render-midi`, { method: "POST" });
      await renderProjectCandidates(project, versions, target);
    });
  });
  target.querySelectorAll("[data-render-candidate-audio]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/candidate-groups/${encodeURIComponent(button.dataset.groupId)}/candidates/${encodeURIComponent(button.dataset.candidateId)}/render-audio`, { method: "POST" });
      await renderProjectCandidates(project, versions, target);
    });
  });
  target.querySelectorAll("[data-render-candidate-group-midi]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/candidate-groups/${encodeURIComponent(button.dataset.groupId)}/render-midi`, { method: "POST" });
      await renderProjectCandidates(project, versions, target);
    });
  });
  target.querySelectorAll("[data-render-candidate-group-audio]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/candidate-groups/${encodeURIComponent(button.dataset.groupId)}/render-audio`, { method: "POST" });
      await renderProjectCandidates(project, versions, target);
    });
  });
  target.querySelectorAll("[data-apply-candidate-group]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/candidate-groups/${encodeURIComponent(button.dataset.applyCandidateGroup)}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: button.dataset.applyCandidateId,
          name: $("project-candidate-version-name").value.trim(),
          change_summary: "Applied provider edit candidate",
        }),
      });
      activeProjectTab = "versions";
      await loadJobs();
      await loadProjects();
    });
  });
  target.querySelectorAll("[data-delete-candidate-group]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/candidate-groups/${encodeURIComponent(button.dataset.deleteCandidateGroup)}/delete`, { method: "POST" });
      await renderProjectCandidates(project, versions, target);
    });
  });
  target.querySelectorAll("[data-save-candidate-asset]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api("/api/assets/extract/from-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: project.project_id,
          candidate_group_id: button.dataset.groupId,
          candidate_id: button.dataset.candidateId,
          asset_types: [button.dataset.assetType || "motif"],
          section_name: "chorus",
          tags: ["candidate", "studio"],
          favorite: true,
        }),
      });
      await loadAssets();
    });
  });
}

function projectCandidateControls(versions, parentId, groups, usage, experiments) {
  return `
    <div class="grid2">
      <label>Parent Version
        <select id="project-candidate-parent">${projectVersionOptions(versions, parentId)}</select>
      </label>
      <label>Candidate Count
        <select id="project-candidate-count">
          <option value="2">2</option>
          <option value="3" selected>3</option>
          <option value="4">4</option>
          <option value="5">5</option>
        </select>
      </label>
    </div>
    <div class="grid2">
      <label>Version Name
        <input id="project-candidate-version-name" value="Provider Candidate ${(versions.length || 0) + 1}">
      </label>
      <label>Template
        <input id="project-candidate-template" value="provider-edit-candidates">
      </label>
    </div>
    <label>Instruction
      <textarea id="project-candidate-instruction" placeholder="Give me 3 stronger chorus options while preserving tempo and key."></textarea>
    </label>
    <label>Asset References
      <div id="project-candidate-asset-refs" class="asset-ref-list"></div>
    </label>
    <label>Reference Materials
      <div id="project-candidate-reference-refs" class="reference-ref-list"></div>
    </label>
    <label>Context Pack
      <select id="project-candidate-context-pack" class="context-pack-select"><option value="">none</option></select>
    </label>
    <div class="actions">
      <button id="project-generate-candidates" type="button" ${parentId ? "" : "disabled"}>Generate Candidates</button>
      <span id="project-candidate-message" class="message"></span>
    </div>
    <div class="grid2">
      <label>Prompt A
        <input id="project-candidate-template-a" value="provider-edit-candidates">
      </label>
      <label>Prompt B
        <input id="project-candidate-template-b" value="provider-edit-candidates">
      </label>
    </div>
    <div class="actions">
      <button id="project-generate-candidates-ab" type="button" ${parentId ? "" : "disabled"}>Generate Prompt A/B</button>
    </div>
    ${projectCandidateUsageHtml(usage)}
    ${projectPromptABHtml(experiments)}
    ${projectCandidateGroupsHtml(groups)}
  `;
}

function projectCandidatePayload() {
  const payload = {
    instruction: $("project-candidate-instruction").value.trim(),
    candidate_count: Number($("project-candidate-count").value || 3),
    template_id: $("project-candidate-template").value.trim() || "provider-edit-candidates",
  };
  const refs = assetRefsPayload("project-candidate-asset-refs");
  if (refs.length) payload.asset_refs = refs;
  const referenceRefs = referenceRefsPayload("project-candidate-reference-refs");
  if (referenceRefs.length) payload.reference_refs = referenceRefs;
  const contextPackId = contextPackIdPayload("project-candidate-context-pack");
  if (contextPackId) payload.context_pack_id = contextPackId;
  return payload;
}

function projectCandidateABPayload() {
  const payload = {
    instruction: $("project-candidate-instruction").value.trim(),
    candidate_count: Number($("project-candidate-count").value || 2),
    template_ids: [
      $("project-candidate-template-a").value.trim() || "provider-edit-candidates",
      $("project-candidate-template-b").value.trim() || "provider-edit-candidates",
    ],
  };
  const refs = assetRefsPayload("project-candidate-asset-refs");
  if (refs.length) payload.asset_refs = refs;
  const referenceRefs = referenceRefsPayload("project-candidate-reference-refs");
  if (referenceRefs.length) payload.reference_refs = referenceRefs;
  const contextPackId = contextPackIdPayload("project-candidate-context-pack");
  if (contextPackId) payload.context_pack_id = contextPackId;
  return payload;
}

function projectCandidateUsageHtml(usage) {
  if (!usage) return "";
  return `
    <div class="summary-grid">
      ${metric("Provider Calls", usage.total_calls ?? 0)}
      ${metric("Total Tokens", usage.total_tokens ?? 0)}
      ${metric("Prompt Tokens", usage.prompt_tokens ?? 0)}
      ${metric("Completion Tokens", usage.completion_tokens ?? 0)}
      ${metric("Estimated Cost", usage.estimated_cost == null ? "-" : `${usage.estimated_cost} ${usage.currency || ""}`)}
      ${metric("Unpriced Calls", usage.unpriced_calls ?? 0)}
    </div>
    <pre>${escapeHtml(JSON.stringify({ by_model: usage.by_model, by_operation: usage.by_operation, by_template: usage.by_template }, null, 2))}</pre>
  `;
}

function projectCandidateGroupsHtml(groups) {
  if (!groups.length) return `<div class="empty">Candidate groups will appear here.</div>`;
  return groups.map((group) => `
    <div class="candidate-group">
      <div class="summary-grid">
        ${metric("Group", group.group_id)}
        ${metric("Status", group.status)}
        ${metric("Parent", group.parent_version_id)}
        ${metric("Candidates", (group.candidates || []).length)}
      </div>
      <div class="actions">
        <button class="secondary" data-render-candidate-group-midi="${escapeHtml(group.group_id)}" data-group-id="${escapeHtml(group.group_id)}" type="button">Render Group MIDI</button>
        <button class="secondary" data-render-candidate-group-audio="${escapeHtml(group.group_id)}" data-group-id="${escapeHtml(group.group_id)}" type="button">Render Group Audio</button>
        <button class="danger" data-delete-candidate-group="${escapeHtml(group.group_id)}" type="button">Delete Candidate Group</button>
      </div>
      ${group.source && (group.source.asset_refs || group.source.reference_refs) ? `<pre>${escapeHtml(JSON.stringify({ asset_refs: group.source.asset_refs || [], reference_refs: group.source.reference_refs || [] }, null, 2))}</pre>` : ""}
      <div class="candidate-grid">
        ${(group.candidates || []).map((candidate) => candidateCardHtml(group, candidate)).join("")}
      </div>
    </div>
  `).join("");
}

function candidateCardHtml(group, candidate) {
  const scores = candidate.scores || {};
  const disabled = group.status === "applied" || candidate.status !== "ready";
  return `
    <div class="candidate-card">
      <h4>${escapeHtml(candidate.rank ? `#${candidate.rank} ` : "")}${escapeHtml(candidate.candidate_id)}</h4>
      <div class="summary-grid">
        ${metric("Score", scores.combined ?? "-")}
        ${metric("Quality", scores.quality_overall ?? "-")}
        ${metric("Novelty", scores.novelty ?? "-")}
        ${metric("Status", candidate.status || "-")}
        ${metric("MIDI", candidate.midi_status || "not_started")}
        ${metric("WAV", candidate.audio_status || "not_started")}
      </div>
      <p>${escapeHtml(candidate.summary || "-")}</p>
      <div class="actions">
        <button class="secondary" data-apply-candidate-group="${escapeHtml(group.group_id)}" data-apply-candidate-id="${escapeHtml(candidate.candidate_id)}" type="button" ${disabled ? "disabled" : ""}>Apply Candidate</button>
        <button class="secondary" data-render-candidate-midi data-group-id="${escapeHtml(group.group_id)}" data-candidate-id="${escapeHtml(candidate.candidate_id)}" type="button">Render MIDI</button>
        ${candidate.midi_url ? `<a class="button-link secondary" href="${escapeHtml(candidate.midi_url)}">Download MIDI</a>` : ""}
        <button class="secondary" data-render-candidate-audio data-group-id="${escapeHtml(group.group_id)}" data-candidate-id="${escapeHtml(candidate.candidate_id)}" type="button">Render Audio</button>
        ${candidate.audio_url ? `<a class="button-link secondary" href="${escapeHtml(candidate.audio_url)}">Download WAV</a>` : ""}
        <button class="secondary" data-save-candidate-asset data-group-id="${escapeHtml(group.group_id)}" data-candidate-id="${escapeHtml(candidate.candidate_id)}" data-asset-type="motif" type="button">Save as Asset</button>
      </div>
      ${candidate.audio_url ? `<audio class="audio-player" controls src="${escapeHtml(candidate.audio_url)}"></audio>` : ""}
      ${candidate.audio_error ? `<div class="empty error">${escapeHtml(candidate.audio_error)}</div>` : ""}
      <pre>${escapeHtml(JSON.stringify({ patch: candidate.patch, scores }, null, 2))}</pre>
    </div>
  `;
}

async function renderProjectQualityGate(project, versions, target) {
  const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/quality-gate`);
  const config = data.config;
  const rows = versions.map((version) => `
    <tr>
      <td>${escapeHtml(version.version_id)}</td>
      <td>${escapeHtml(version.name || "-")}</td>
      <td><span class="status ${version.quality_gate_status || "not_evaluated"}">${escapeHtml(version.quality_gate_status || "not_evaluated")}</span></td>
      <td>${escapeHtml(version.quality_gate_score ?? "-")}</td>
      <td>${escapeHtml((version.quality_gate_warnings || []).length)}</td>
      <td><button class="secondary" data-project-evaluate-version="${escapeHtml(version.version_id)}" type="button">Evaluate Gate</button></td>
    </tr>
  `).join("");
  target.innerHTML = `
    <div class="grid2">
      <label>Min Overall
        <input id="project-gate-min-overall" type="number" min="0" max="100" value="${escapeHtml(config.min_overall)}">
      </label>
      <label>Min Structure
        <input id="project-gate-min-structure" type="number" min="0" max="100" value="${escapeHtml(config.min_structure)}">
      </label>
    </div>
    <div class="grid2">
      <label>Min Melody
        <input id="project-gate-min-melody" type="number" min="0" max="100" value="${escapeHtml(config.min_melody)}">
      </label>
      <label>Min Harmony
        <input id="project-gate-min-harmony" type="number" min="0" max="100" value="${escapeHtml(config.min_harmony)}">
      </label>
    </div>
    <div class="grid2">
      <label>Min Arrangement
        <input id="project-gate-min-arrangement" type="number" min="0" max="100" value="${escapeHtml(config.min_arrangement)}">
      </label>
      <label>Max Warnings
        <input id="project-gate-max-warnings" type="number" min="0" max="99" value="${escapeHtml(config.max_warnings)}">
      </label>
    </div>
    <div class="actions">
      <label><input id="project-gate-allow-warnings" type="checkbox" ${config.allow_warnings ? "checked" : ""}> Allow Warnings</label>
      <label><input id="project-gate-require-audio" type="checkbox" ${config.require_audio ? "checked" : ""}> Require Audio</label>
      <label><input id="project-gate-require-stems" type="checkbox" ${config.require_stems ? "checked" : ""}> Require Stems</label>
    </div>
    <div class="actions">
      <button id="project-save-gate" type="button">Save Quality Gate</button>
      <button class="secondary" id="project-evaluate-all" type="button">Evaluate All</button>
      <span id="project-gate-message" class="message"></span>
    </div>
    <table>
      <thead><tr><th>Version</th><th>Name</th><th>Gate</th><th>Score</th><th>Warnings</th><th>Actions</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='6'>No versions yet.</td></tr>"}</tbody>
    </table>
  `;
  bindAction("project-save-gate", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/quality-gate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectQualityGatePayload()),
    });
    $("project-gate-message").textContent = "saved";
  });
  bindAction("project-evaluate-all", async () => {
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/quality-gate/evaluate-all`, { method: "POST" });
    await loadProjects();
  });
}

function projectQualityGatePayload() {
  return {
    min_overall: Number($("project-gate-min-overall").value || 0),
    min_structure: Number($("project-gate-min-structure").value || 0),
    min_melody: Number($("project-gate-min-melody").value || 0),
    min_harmony: Number($("project-gate-min-harmony").value || 0),
    min_arrangement: Number($("project-gate-min-arrangement").value || 0),
    max_warnings: Number($("project-gate-max-warnings").value || 0),
    allow_warnings: $("project-gate-allow-warnings").checked,
    require_audio: $("project-gate-require-audio").checked,
    require_stems: $("project-gate-require-stems").checked,
  };
}

async function renderQuality(job, target) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/quality`);
    const view = data.view;
    const scores = view.scores || {};
    const motif = view.primary_motif || {};
    const intentRows = (view.section_intents || []).map((intent) => `
      <tr>
        <td>${escapeHtml(intent.section_name)}</td>
        <td>${escapeHtml(intent.role || "-")}</td>
        <td>${escapeHtml(intent.energy)}</td>
        <td>${escapeHtml(intent.tension)}</td>
        <td>${escapeHtml(intent.density)}</td>
        <td>${intent.hook ? "yes" : "-"}</td>
      </tr>
    `).join("");
    const issueRows = (view.issues || []).map((issue) => `
      <tr>
        <td>${escapeHtml(issue.severity)}</td>
        <td>${escapeHtml(issue.code)}</td>
        <td>${escapeHtml(issue.message)}</td>
        <td>${escapeHtml(issue.target || "-")}</td>
      </tr>
    `).join("");
    const warningRows = (view.warnings || []).map((warning) => `
      <tr><td>${escapeHtml(warning)}</td></tr>
    `).join("");
    const critic = view.critic || {};
    target.innerHTML = `
      <div class="summary-grid">
        ${metric("Overall", view.overall ?? scores.overall ?? "-")}
        ${metric("Structure", scores.structure ?? "-")}
        ${metric("Melody", scores.melody ?? "-")}
        ${metric("Arrangement", scores.arrangement ?? "-")}
      </div>
      <div class="summary-grid">
        ${metric("Harmony", scores.harmony ?? "-")}
        ${metric("Lyric Fit", scores.lyric_fit ?? "-")}
        ${metric("Hook", (view.hook_sections || []).join(", ") || "-")}
        ${metric("Motif", motif.name || "-")}
      </div>
      <div class="summary-grid">
        ${metric("Critic", critic.score ?? "-")}
        ${metric("Critic Passed", critic.passed == null ? "-" : (critic.passed ? "yes" : "no"))}
        ${metric("Warnings", (view.warnings || []).length)}
        ${metric("Issues", (view.issues || []).length)}
      </div>
      <p>${escapeHtml(view.summary || "")}</p>
      <table>
        <thead><tr><th>Section</th><th>Role</th><th>Energy</th><th>Tension</th><th>Density</th><th>Hook</th></tr></thead>
        <tbody>${intentRows || "<tr><td colspan='6'>No section intents.</td></tr>"}</tbody>
      </table>
      <table>
        <thead><tr><th>Warning</th></tr></thead>
        <tbody>${warningRows || "<tr><td>No quality warnings.</td></tr>"}</tbody>
      </table>
      <table>
        <thead><tr><th>Severity</th><th>Code</th><th>Message</th><th>Target</th></tr></thead>
        <tbody>${issueRows || "<tr><td colspan='4'>No quality issues.</td></tr>"}</tbody>
      </table>
    `;
  } catch (err) {
    if (String(err.message || "").includes("song-plan.json is not available")) {
      target.innerHTML = `<div class="empty">Quality view will be available after the song plan is generated.</div>`;
      return;
    }
    target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
  }
}

Object.assign(globalThis, { reviewSprintRowHtml, reviewSprintCloseoutHtml, reviewSprintJudgeSummaryHtml, reviewSprintDashboardHtml, reviewSprintRecommendationsHtml, reviewSprintActionQueueHtml, reviewSprintConflictHtml, renderProjectCandidates, projectCandidateControls, projectCandidatePayload, projectCandidateABPayload, projectCandidateUsageHtml, projectCandidateGroupsHtml, candidateCardHtml, renderProjectQualityGate, projectQualityGatePayload, renderQuality });

export { reviewSprintRowHtml, reviewSprintCloseoutHtml, reviewSprintJudgeSummaryHtml, reviewSprintDashboardHtml, reviewSprintRecommendationsHtml, reviewSprintActionQueueHtml, reviewSprintConflictHtml, renderProjectCandidates, projectCandidateControls, projectCandidatePayload, projectCandidateABPayload, projectCandidateUsageHtml, projectCandidateGroupsHtml, candidateCardHtml, renderProjectQualityGate, projectQualityGatePayload, renderQuality };
