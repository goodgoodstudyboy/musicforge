async function projectReviewMetricsSummaryHtml(project) {
  try {
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-metrics`);
    const summary = data.summary || {};
    return `
      <div class="review-metrics-summary">
        <h4>Review Metrics</h4>
        <div class="summary-grid">
          ${metric("Active Sprints", summary.active_sprint_count ?? 0)}
          ${metric("Latest Readiness", summary.latest_readiness || "-")}
          ${metric("Provider Tokens", summary.total_provider_tokens ?? 0)}
          ${metric("Applied Candidates", summary.total_applied_candidate_count ?? 0)}
          ${metric("Quality Trend", (summary.quality_trend || {}).overall_delta ?? (summary.quality_trend || {}).status ?? "-")}
        </div>
      </div>
    `;
  } catch (err) {
    return `<div class="empty small">Review Metrics unavailable: ${escapeHtml(err.message)}</div>`;
  }
}

function renderProjectEditorPreview() {
  const target = $("project-editor-preview-result");
  if (!target || !projectEditorPreview) return;
  const parentVersion = $("project-editor-parent") ? $("project-editor-parent").value : (projectEditorParentId || "");
  const previewAudioUrl = projectEditorPreview.audio_url || `/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/audio`;
  const parentAudioUrl = parentVersion ? `/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(parentVersion)}/audio` : "";
  target.innerHTML = `
    <div class="summary-grid">
      ${metric("Preview", projectEditorPreview.preview_id)}
      ${metric("Ops", projectEditorPreview.operation_count)}
      ${metric("Quality", (projectEditorPreview.quality || {}).overall ?? "-")}
      ${metric("Status", projectEditorPreview.status)}
      ${metric("Preview WAV", projectEditorPreview.audio_status || "not_started")}
      ${metric("Auditions", projectEditorAuditions.length)}
    </div>
    <div class="actions">
      ${projectEditorPreview.midi_url ? `<a class="button-link secondary" href="${escapeHtml(projectEditorPreview.midi_url)}">MIDI</a>` : ""}
      <button class="secondary" id="project-editor-render-preview-audio" type="button">Render Preview Audio</button>
      <button class="secondary" id="project-editor-render-parent-audio" type="button">Render Parent Audio</button>
      ${projectEditorPreview.audio_status === "completed" ? `<a class="button-link secondary" href="${escapeHtml(previewAudioUrl)}">Preview WAV</a>` : ""}
      ${parentVersion ? `<a class="button-link secondary" href="${escapeHtml(parentAudioUrl)}">Parent WAV</a>` : ""}
    </div>
    <div class="grid2">
      <section>
        <h3>A/B Parent</h3>
        <audio id="project-editor-audio-parent" controls src="${escapeHtml(parentAudioUrl)}"></audio>
      </section>
      <section>
        <h3>A/B Preview</h3>
        <audio id="project-editor-audio-preview" controls src="${escapeHtml(previewAudioUrl)}"></audio>
      </section>
    </div>
    <section id="project-editor-audition-panel">
      <h3>Audition Review Board</h3>
      <div class="grid2">
        <label>Source
          <select id="project-editor-audition-source">
            <option value="preview">Preview</option>
            <option value="parent">Parent</option>
          </select>
        </label>
        <label>Range
          <select id="project-editor-audition-range">
            <option value="full_song">Full song</option>
            <option value="section">Current section</option>
            <option value="changed_sections">Changed sections</option>
            <option value="custom">Custom beat range</option>
          </select>
        </label>
      </div>
      <div class="grid2">
        <label>Track mode
          <select id="project-editor-audition-track-mode">
            <option value="all">All</option>
            <option value="solo">Solo</option>
            <option value="mute">Mute</option>
          </select>
        </label>
        <label>Track selector
          <select id="project-editor-audition-track">${projectEditorAuditionTrackOptions()}</select>
        </label>
      </div>
      <div class="grid2">
        <label>Start Beat <input id="project-editor-audition-start" type="number" step="0.125" value="0"></label>
        <label>End Beat <input id="project-editor-audition-end" type="number" step="0.125" value="${escapeHtml((currentProjectEditorView().song || {}).total_beats || 4)}"></label>
      </div>
      <div class="actions">
        <button class="secondary" id="project-editor-create-audition" type="button">Create Audition</button>
        <button class="secondary" id="project-editor-refresh-auditions" type="button">Refresh Auditions</button>
        <button class="secondary" id="project-editor-filter-favorites" type="button">Favorites</button>
      </div>
      <div id="project-editor-audition-list">${projectEditorAuditionListHtml()}</div>
    </section>
    <pre>${escapeHtml(JSON.stringify(projectEditorPreview, null, 2))}</pre>
  `;
  bindProjectEditorPreviewAudioControls();
  bindProjectEditorAuditionControls();
  const apply = $("project-editor-apply");
  if (apply) apply.disabled = false;
}

async function loadProjectEditorPreviewHistory(projectId) {
  const target = $("project-editor-history");
  if (!target) return;
  const data = await api(`/api/projects/${encodeURIComponent(projectId)}/editor-previews`);
  projectEditorPreviewHistory = data.previews || [];
  target.innerHTML = `
    <section>
      <h3>Preview History</h3>
      ${projectEditorPreviewHistory.length ? `
        <div class="table-wrap">
          <table>
            <thead><tr><th>Preview</th><th>Status</th><th>Ops</th><th>Sections</th><th>Tracks</th><th>Actions</th></tr></thead>
            <tbody>${projectEditorPreviewHistory.map((preview) => `
              <tr>
                <td>${escapeHtml(preview.preview_id)}</td>
                <td>${escapeHtml(preview.status)} / ${escapeHtml(preview.audio_status || "not_started")}</td>
                <td>${escapeHtml(preview.operation_count)}</td>
                <td>${escapeHtml((preview.changed_sections || []).join(", ") || "-")}</td>
                <td>${escapeHtml((preview.changed_tracks || []).join(", ") || "-")}</td>
                <td>
                  <button class="secondary" data-editor-history-preview="${escapeHtml(preview.preview_id)}" type="button">Open Summary</button>
                  ${preview.midi_url ? `<a class="button-link secondary" href="${escapeHtml(preview.midi_url)}">MIDI</a>` : ""}
                  ${preview.audio_status === "completed" ? `<a class="button-link secondary" href="/api/projects/${encodeURIComponent(projectId)}/editor-previews/${encodeURIComponent(preview.preview_id)}/audio">WAV</a>` : ""}
                  <button class="secondary" data-editor-history-auditions="${escapeHtml(preview.preview_id)}" type="button">Open Auditions</button>
                </td>
              </tr>
            `).join("")}</tbody>
          </table>
        </div>` : "<div class='empty'>No editor previews yet.</div>"}
      <div id="project-editor-history-detail"></div>
    </section>
  `;
  target.querySelectorAll("[data-editor-history-preview]").forEach((button) => {
    button.addEventListener("click", async () => {
      const detail = await api(`/api/projects/${encodeURIComponent(projectId)}/editor-previews/${encodeURIComponent(button.dataset.editorHistoryPreview)}/patch`);
      $("project-editor-history-detail").innerHTML = `<pre>${escapeHtml(JSON.stringify(detail.patch, null, 2))}</pre>`;
      projectEditorPreview = projectEditorPreviewHistory.find((item) => item.preview_id === button.dataset.editorHistoryPreview) || null;
      projectEditorAuditions = [];
      renderProjectEditorPreview();
    });
  });
  target.querySelectorAll("[data-editor-history-auditions]").forEach((button) => {
    button.addEventListener("click", async () => {
      const data = await api(`/api/projects/${encodeURIComponent(projectId)}/editor-previews/${encodeURIComponent(button.dataset.editorHistoryAuditions)}/auditions`);
      $("project-editor-history-detail").innerHTML = `<pre>${escapeHtml(JSON.stringify(data.auditions || [], null, 2))}</pre>`;
    });
  });
}

function projectProviderPreviewPayload() {
  const payload = {
    provider_mode: "provider",
    instruction: $("project-edit-instruction").value.trim(),
    template_id: "provider-edit-intent",
  };
  const refs = assetRefsPayload("project-edit-asset-refs");
  if (refs.length) payload.asset_refs = refs;
  const referenceRefs = referenceRefsPayload("project-edit-reference-refs");
  if (referenceRefs.length) payload.reference_refs = referenceRefs;
  const contextPackId = contextPackIdPayload("project-edit-context-pack");
  if (contextPackId) payload.context_pack_id = contextPackId;
  return payload;
}

function providerPreviewHtml(preview, patch) {
  if (!preview) return `<div class="empty">No preview.</div>`;
  return `
    <div class="summary-grid">
      ${metric("Preview", preview.preview_id || "-")}
      ${metric("Status", preview.status || "-")}
      ${metric("Template", preview.template_id || "-")}
      ${metric("Operations", ((patch || {}).operations || []).length)}
    </div>
    <pre>${escapeHtml(JSON.stringify({ preview, patch }, null, 2))}</pre>
  `;
}

async function renderProjectReviewWorkbench(project, versions, target) {
  let tasks = [];
  let summary = {};
  let sprints = [];
  try {
    const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks?include_archived=1`);
    summary = data.summary || {};
    tasks = await Promise.all((data.tasks || []).map(async (task) => {
      try {
        const detail = await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(task.task_id)}`);
        return { ...(detail.task || task), candidates: detail.candidates || [], decision_report: detail.decision_report || {}, judge_report: detail.judge_report || {}, judge_summary: detail.judge_summary || {}, events: detail.events || [] };
      } catch (_err) {
        return task;
      }
    }));
    try {
      const sprintData = await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints?include_archived=1`);
      sprints = sprintData.sprints || [];
    } catch (_err) {
      sprints = [];
    }
  } catch (err) {
    target.innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
    return;
  }
  target.innerHTML = projectReviewWorkbenchHtml(project, tasks, summary, sprints);
  bindAction("project-review-task-refresh", async () => {
    await renderProjectReviewWorkbench(project, versions, target);
  });
  const sprintSelect = $("project-review-add-sprint");
  target.querySelectorAll("[data-review-add-to-sprint]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!sprintSelect || !sprintSelect.value) {
        activeProjectTab = "review-sprints";
        await renderProjectDetail(project.project_id);
        return;
      }
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprintSelect.value)}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_ids: [button.dataset.reviewAddToSprint] }),
      });
      activeProjectTab = "review-sprints";
      await renderProjectDetail(project.project_id);
    });
  });
  target.querySelectorAll("[data-review-task-generate]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.reviewTaskGenerate)}/candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ render_midi: true }),
      });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-provider]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.reviewProvider)}/provider-candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_count: Number(button.dataset.candidateCount || 3),
          template_id: "provider-review-candidates",
          render_midi: true,
        }),
      });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-report-refresh]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.reviewReportRefresh)}/decision-report/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "Refreshed in Review Workbench" }),
      });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-judge-refresh]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.reviewJudgeRefresh)}/judge-report/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_id: "provider-review-judge", note: "Refreshed in Review Workbench" }),
      });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-candidate-render-midi]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.taskId)}/candidates/${encodeURIComponent(button.dataset.candidateId)}/render-midi`, { method: "POST" });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-candidate-render-audio]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.taskId)}/candidates/${encodeURIComponent(button.dataset.candidateId)}/render-audio`, { method: "POST" });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-candidate-apply]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.taskId)}/candidates/${encodeURIComponent(button.dataset.candidateId)}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version_name: `${button.dataset.taskId} ${button.dataset.candidateId}`,
          version_note: "Created from Review Workbench",
        }),
      });
      await loadJobs();
      await loadProjects();
    });
  });
  target.querySelectorAll("[data-review-task-resolve]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.reviewTaskResolve)}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "Resolved in Review Workbench" }),
      });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-task-needs-work]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.reviewTaskNeedsWork)}/needs-more-work`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: "Needs another Review Workbench pass" }),
      });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-task-archive]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(button.dataset.reviewTaskArchive)}/archive`, { method: "POST" });
      await renderProjectReviewWorkbench(project, versions, target);
    });
  });
}

function projectReviewWorkbenchHtml(project, tasks, summary, sprints) {
  const openSprints = (sprints || []).filter((sprint) => ["open", "in_progress", "blocked"].includes(sprint.status));
  return `
    <div class="summary-grid">
      ${metric("Review Tasks", summary.total ?? tasks.length)}
      ${metric("Open", summary.open ?? 0)}
      ${metric("Candidate Ready", summary.candidate_ready ?? 0)}
      ${metric("Applied", summary.applied ?? 0)}
      ${metric("Needs More Work", summary.needs_more_work ?? 0)}
      ${metric("Resolved", summary.resolved ?? 0)}
    </div>
    <div class="actions">
      <button class="secondary" id="project-review-task-refresh" type="button">Refresh Review Tasks</button>
      <select id="project-review-add-sprint" style="max-width:260px;">
        <option value="">Add to Review Sprint</option>
        ${openSprints.map((sprint) => `<option value="${escapeHtml(sprint.sprint_id)}">${escapeHtml(sprint.sprint_id)} · ${escapeHtml(sprint.name || "Review Sprint")}</option>`).join("")}
      </select>
    </div>
    ${tasks.length ? tasks.map((task) => reviewTaskWorkbenchRowHtml(project, task)).join("") : `<div class="empty">Review tasks will appear here after you create one from an audition review.</div>`}
  `;
}

function reviewTaskWorkbenchRowHtml(project, task) {
  const target = task.target || {};
  const snapshot = task.review_snapshot || {};
  const source = task.source || {};
  const candidates = task.candidates || [];
  const decision = task.decision_report || {};
  const judge = task.judge_report || {};
  const providerSummary = task.provider_summary || {};
  return `
    <div class="review-task-row">
      <h4>${escapeHtml(task.title || task.task_id)}</h4>
      <div class="summary-grid">
        ${metric("Task", task.task_id)}
        ${metric("Status", task.status || "-")}
        ${metric("Priority", task.priority ?? "-")}
        ${metric("Rating", snapshot.rating ?? "-")}
        ${metric("Review", snapshot.status || "-")}
        ${metric("Parent", task.parent_version_id || "-")}
        ${metric("Section", target.section_name || "-")}
        ${metric("Track", target.track_name || "-")}
        ${metric("Global Beat", target.global_marker_beat ?? "-")}
        ${metric("Candidates", (task.counts || {}).candidate_count ?? candidates.length)}
        ${metric("Provider Candidates", providerSummary.provider_candidate_count ?? 0)}
        ${metric("Selected", task.selected_candidate_id || "-")}
        ${metric("Applied Version", task.applied_version_id || "-")}
      </div>
      <p>${escapeHtml(task.summary || "-")}</p>
      <div class="empty small">
        ${escapeHtml([snapshot.notes_excerpt || "", `tags: ${(snapshot.tags || []).join(", ") || "-"}`, `source: ${task.preview_id}/${task.audition_id}`, `range: ${((source.audition_range || {}).mode) || "-"}`, `track mode: ${source.track_mode || "-"}`].filter(Boolean).join(" · "))}
      </div>
      ${decision && decision.schema_version ? reviewDecisionReportHtml(decision, providerSummary) : ""}
      ${reviewJudgeReportHtml(task, judge)}
      <div class="actions">
        <button class="secondary" data-review-task-generate="${escapeHtml(task.task_id)}" type="button" ${["resolved", "archived", "stale", "needs_more_work"].includes(task.status) ? "disabled" : ""}>Generate Local Candidates</button>
        <button class="secondary" data-review-provider="${escapeHtml(task.task_id)}" data-candidate-count="3" type="button" ${["resolved", "archived", "stale", "needs_more_work"].includes(task.status) ? "disabled" : ""}>Generate Provider Candidates</button>
        <button class="secondary" data-review-judge-refresh="${escapeHtml(task.task_id)}" type="button" ${["resolved", "archived", "stale", "needs_more_work"].includes(task.status) ? "disabled" : ""}>Refresh Judge Report</button>
        <button class="secondary" data-review-report-refresh="${escapeHtml(task.task_id)}" type="button" ${["stale"].includes(task.status) ? "disabled" : ""}>Refresh Decision Report</button>
        <button class="secondary" data-review-task-resolve="${escapeHtml(task.task_id)}" type="button" ${task.status === "applied" ? "" : "disabled"}>Resolve Task</button>
        <button class="secondary" data-review-task-needs-work="${escapeHtml(task.task_id)}" type="button" ${task.status === "applied" ? "" : "disabled"}>Needs More Work</button>
        <button class="secondary" data-review-add-to-sprint="${escapeHtml(task.task_id)}" type="button">Add to Sprint</button>
        <button class="danger" data-review-task-archive="${escapeHtml(task.task_id)}" type="button" ${["resolved", "archived", "stale"].includes(task.status) ? "disabled" : ""}>Archive Task</button>
      </div>
      <div class="candidate-grid">
        ${candidates.length ? candidates.map((candidate) => reviewCandidateWorkbenchCardHtml(project, task, candidate)).join("") : `<div class="empty small">Generate local candidates to compare options.</div>`}
      </div>
    </div>
  `;
}

function reviewDecisionReportHtml(report, providerSummary) {
  const ranking = Array.isArray(report.ranking) ? report.ranking : [];
  const top = ranking[0] || {};
  const source = report.source_breakdown || providerSummary || {};
  const judge = report.judge_summary || {};
  return `
    <div class="decision-report-panel">
      <h5>Decision Report</h5>
      <div class="summary-grid">
        ${metric("Recommended", report.recommended_candidate_id || "-")}
        ${metric("Local", report.local_recommended_candidate_id || source.local_candidate_count || 0)}
        ${metric("Judge", report.judge_recommended_candidate_id || judge.recommended_candidate_id || "-")}
        ${metric("Manual Apply", report.requires_manual_apply ? "required" : "-")}
        ${metric("Provider", source.provider_candidate_count ?? 0)}
        ${metric("Top Score", top.combined ?? "-")}
        ${metric("Risk Flags", (report.risk_flags || []).length)}
      </div>
      ${report.recommendation_reason ? `<p>${escapeHtml(report.recommendation_reason)}</p>` : ""}
      ${ranking.length ? `<pre>${escapeHtml(JSON.stringify(ranking.slice(0, 5), null, 2))}</pre>` : ""}
    </div>
  `;
}

function reviewJudgeReportHtml(task, report) {
  const scores = Array.isArray(report.candidate_scores) ? report.candidate_scores : [];
  const summary = task.judge_summary || {};
  const comparison = report.comparison_summary || {};
  const rows = scores.slice(0, 8).map((score) => `
    <tr>
      <td>${escapeHtml(score.candidate_id || "-")}</td>
      <td>${escapeHtml(score.overall ?? "-")}</td>
      <td>${escapeHtml(score.review_fit ?? "-")}</td>
      <td>${escapeHtml(score.target_precision ?? "-")}</td>
      <td>${escapeHtml(score.musicality ?? "-")}</td>
      <td>${escapeHtml(score.novelty ?? "-")}</td>
      <td>${escapeHtml(score.risk ?? "-")}</td>
      <td>${escapeHtml(score.confidence ?? "-")}</td>
      <td>${escapeHtml(score.reason || "-")}</td>
    </tr>
  `).join("");
  return `
    <div class="decision-report-panel">
      <h5>Judge Report</h5>
      <div class="empty small">Judge reports are advisory. Applying a candidate remains manual.</div>
      <div class="summary-grid">
        ${metric("Status", summary.status || report.status || "not_started")}
        ${metric("Recommended", report.recommended_candidate_id || summary.recommended_candidate_id || "-")}
        ${metric("Top Overall", summary.top_overall ?? "-")}
        ${metric("Risk", summary.top_risk ?? "-")}
        ${metric("Confidence", summary.top_confidence ?? "-")}
        ${metric("Stale", report.stale ? "yes" : "no")}
      </div>
      ${comparison.reason ? `<p>${escapeHtml(comparison.reason)}</p>` : ""}
      <div class="table-scroll">
        <table>
          <thead><tr><th>Candidate</th><th>Overall</th><th>Fit</th><th>Precision</th><th>Musicality</th><th>Novelty</th><th>Risk</th><th>Confidence</th><th>Reason</th></tr></thead>
          <tbody>${rows || `<tr><td colspan="9">Refresh Judge Report after candidates are ready.</td></tr>`}</tbody>
        </table>
      </div>
    </div>
  `;
}

function reviewCandidateWorkbenchCardHtml(project, task, candidate) {
  const scores = candidate.scores || {};
  const warnings = candidate.warnings || [];
  const source = candidate.source || {};
  const sourceLabel = source.provider ? "provider" : "local";
  const applyDisabled = task.status === "applied" || candidate.status !== "ready";
  const midiUrl = candidate.midi_url || `/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(task.task_id)}/candidates/${encodeURIComponent(candidate.candidate_id)}/midi`;
  const audioUrl = candidate.audio_url || `/api/projects/${encodeURIComponent(project.project_id)}/review-tasks/${encodeURIComponent(task.task_id)}/candidates/${encodeURIComponent(candidate.candidate_id)}/audio`;
  return `
    <div class="review-candidate-card">
      <h5>${escapeHtml(candidate.rank ? `#${candidate.rank} ` : "")}${escapeHtml(candidate.candidate_id)}<span class="review-candidate-source ${source.provider ? "provider" : "local"}">${escapeHtml(sourceLabel)}</span></h5>
      <div class="summary-grid">
        ${metric("Strategy", candidate.strategy || "-")}
        ${metric("Type", candidate.candidate_type || "-")}
        ${metric("Status", candidate.status || "-")}
        ${metric("Model", source.model || "-")}
        ${metric("Combined", scores.combined ?? "-")}
        ${metric("Review Fit", scores.review_fit ?? "-")}
        ${metric("Precision", scores.target_precision ?? "-")}
        ${metric("Risk", scores.risk ?? "-")}
        ${metric("Quality", scores.quality_overall ?? "-")}
        ${metric("MIDI", candidate.midi_status || "not_started")}
        ${metric("WAV", candidate.audio_status || "not_started")}
      </div>
      <p>${escapeHtml(candidate.summary || "-")}</p>
      ${warnings.length ? `<div class="empty small">${escapeHtml(warnings.join(" "))}</div>` : ""}
      <div class="actions">
        <button class="secondary" data-review-candidate-render-midi data-task-id="${escapeHtml(task.task_id)}" data-candidate-id="${escapeHtml(candidate.candidate_id)}" type="button">Render MIDI</button>
        ${candidate.midi_status === "completed" ? `<a class="button-link secondary" href="${escapeHtml(midiUrl)}">Download MIDI</a>` : ""}
        <button class="secondary" data-review-candidate-render-audio data-task-id="${escapeHtml(task.task_id)}" data-candidate-id="${escapeHtml(candidate.candidate_id)}" type="button">Render WAV</button>
        ${candidate.audio_status === "completed" ? `<a class="button-link secondary" href="${escapeHtml(audioUrl)}">Download WAV</a>` : ""}
        <button class="secondary" data-review-candidate-apply data-task-id="${escapeHtml(task.task_id)}" data-candidate-id="${escapeHtml(candidate.candidate_id)}" type="button" ${applyDisabled ? "disabled" : ""}>Apply Candidate</button>
        <button class="secondary" type="button" disabled>Save as Asset</button>
        <button class="secondary" type="button" disabled>Create Context Pack</button>
      </div>
      ${candidate.audio_status === "completed" ? `<audio class="audio-player" controls src="${escapeHtml(audioUrl)}"></audio>` : ""}
      ${candidate.audio_error ? `<div class="empty error">${escapeHtml(candidate.audio_error)}</div>` : ""}
      <pre>${escapeHtml(JSON.stringify({ scores, validator: candidate.validator, intents: candidate.intents }, null, 2))}</pre>
    </div>
  `;
}

async function renderProjectReviewSprints(project, versions, target) {
  let sprints = [];
  let tasks = [];
  let summary = {};
  try {
    const sprintData = await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints?include_archived=1`);
    sprints = sprintData.sprints || [];
    sprints = await Promise.all(sprints.map(async (sprint) => {
      try {
        const [recommendationData, queueData, metricsData, judgeData, closeoutData, signoffData] = await Promise.all([
          api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprint.sprint_id)}/recommendations`),
          api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprint.sprint_id)}/action-queues`),
          api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprint.sprint_id)}/metrics`),
          api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprint.sprint_id)}/judge-summary`),
          api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprint.sprint_id)}/closeout`),
          api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprint.sprint_id)}/signoff`),
        ]);
        return {
          ...sprint,
          recommendation_report: recommendationData.recommendation_report || {},
          recommendation_summary: recommendationData.summary || {},
          action_queues: queueData.queues || [],
          latest_action_queue: queueData.latest_queue || {},
          action_queue_summary: queueData.summary || sprint.action_queue_summary || {},
          metrics_report: metricsData.metrics_report || {},
          metrics_summary: metricsData.summary || sprint.metrics_summary || {},
          judge_summary: judgeData.judge_summary || sprint.judge_summary || {},
          closeout_report: closeoutData.closeout_report || {},
          closeout_summary: closeoutData.summary || sprint.closeout_summary || {},
          signoff: signoffData.signoff || {},
          signoff_summary: signoffData.summary || sprint.signoff_summary || {},
        };
      } catch (err) {
        return { ...sprint, recommendation_error: err.message };
      }
    }));
    summary = sprintData.summary || {};
    const taskData = await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-tasks?include_archived=1`);
    tasks = taskData.tasks || [];
  } catch (err) {
    target.innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
    return;
  }
  const metricsHtml = await projectReviewMetricsSummaryHtml(project);
  target.innerHTML = metricsHtml + projectReviewSprintsHtml(project, sprints, tasks, summary, versions);
  bindAction("project-review-sprint-refresh", async () => {
    await renderProjectReviewSprints(project, versions, target);
  });
  bindAction("project-review-sprint-create", async () => {
    const taskIds = Array.from(target.querySelectorAll("[data-review-sprint-task]:checked")).map((item) => item.value);
    await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("project-review-sprint-name").value.trim() || "Review Sprint",
        description: $("project-review-sprint-description").value.trim(),
        task_ids: taskIds,
        settings: {
          local_candidate_strategies: [$("project-review-sprint-local-strategy").value],
          provider_candidate_count: Number($("project-review-sprint-provider-count").value || 2),
          provider_template_id: $("project-review-sprint-template").value.trim() || "provider-review-candidates",
          render_midi: $("project-review-sprint-render-midi").checked,
          stop_on_conflict: $("project-review-sprint-stop-conflict").checked,
        },
      }),
    });
    await renderProjectReviewSprints(project, versions, target);
  });
  target.querySelectorAll("[data-review-sprint-add-task]").forEach((button) => {
    button.addEventListener("click", async () => {
      const select = $(`review-sprint-add-task-${button.dataset.reviewSprintAddTask}`);
      if (!select || !select.value) return;
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintAddTask)}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_ids: [select.value] }),
      });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-refresh]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintRefresh)}/refresh`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-conflicts]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintConflicts)}/conflicts/refresh`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-recommendations]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintRecommendations)}/recommendations/refresh`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-metrics]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintMetrics)}/metrics/refresh`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-judge]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintJudge)}/judge-summary/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_id: "provider-review-judge", skip_existing_current: true, max_tasks: 5 }),
      });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-closeout]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintCloseout)}/closeout/refresh`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-queue]").forEach((button) => {
    button.addEventListener("click", async () => {
      const sprintId = button.dataset.reviewSprintQueue;
      const refresh = $(`review-sprint-queue-refresh-${sprintId}`);
      const includeContext = $(`review-sprint-queue-context-${sprintId}`);
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprintId)}/action-queues`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          refresh_recommendations: !refresh || refresh.checked,
          settings: {
            run_context_pack_actions: !includeContext || includeContext.checked,
            run_provider_actions: false,
            run_local_actions: true,
          },
        }),
      });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-queue-select-safe]").forEach((button) => {
    button.addEventListener("click", () => {
      target.querySelectorAll(`[data-review-sprint-queue-item="${CSS.escape(button.dataset.queueId)}"]`).forEach((checkbox) => {
        checkbox.checked = checkbox.dataset.safety === "auto_safe";
      });
    });
  });
  target.querySelectorAll("[data-review-sprint-run-queue]").forEach((button) => {
    button.addEventListener("click", async () => {
      const itemIds = Array.from(target.querySelectorAll(`[data-review-sprint-queue-item="${CSS.escape(button.dataset.queueId)}"]:checked`)).map((checkbox) => checkbox.value);
      const providerToggle = $(`review-sprint-queue-provider-${button.dataset.sprintId}-${button.dataset.queueId}`);
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.sprintId)}/action-queues/${encodeURIComponent(button.dataset.queueId)}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_ids: itemIds, include_provider: !!(providerToggle && providerToggle.checked) }),
      });
      await loadContextPacks();
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-run-all-queue]").forEach((button) => {
    button.addEventListener("click", async () => {
      const providerToggle = $(`review-sprint-queue-provider-${button.dataset.sprintId}-${button.dataset.queueId}`);
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.sprintId)}/action-queues/${encodeURIComponent(button.dataset.queueId)}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include_provider: !!(providerToggle && providerToggle.checked) }),
      });
      await loadContextPacks();
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-archive-queue]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.sprintId)}/action-queues/${encodeURIComponent(button.dataset.queueId)}/archive`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-save-context]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.sprintId)}/recommendations/${encodeURIComponent(button.dataset.taskId)}/context-pack`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: `${button.dataset.sprintId} ${button.dataset.taskId} Context Pack` }),
      });
      await loadContextPacks();
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-local]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintLocal)}/generate-local-candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ render_midi: true }),
      });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-provider]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintProvider)}/generate-provider-candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template_id: "provider-review-candidates", candidate_count: 2, render_midi: true }),
      });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-close]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintClose)}/close`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-force-close]").forEach((button) => {
    button.addEventListener("click", async () => {
      const sprintId = button.dataset.reviewSprintForceClose;
      const reason = $(`review-sprint-force-reason-${sprintId}`);
      const selected = $(`review-sprint-selected-version-${sprintId}`);
      const notes = $(`review-sprint-close-notes-${sprintId}`);
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(sprintId)}/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          force: true,
          override_reason: reason ? reason.value : "",
          selected_version_id: selected ? selected.value : "",
          notes: notes ? notes.value : "",
        }),
      });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
  target.querySelectorAll("[data-review-sprint-archive]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${encodeURIComponent(project.project_id)}/review-sprints/${encodeURIComponent(button.dataset.reviewSprintArchive)}/archive`, { method: "POST" });
      await renderProjectReviewSprints(project, versions, target);
    });
  });
}

function projectReviewSprintsHtml(project, sprints, tasks, summary, versions) {
  const taskOptions = (tasks || []).map((task) => `<option value="${escapeHtml(task.task_id)}">${escapeHtml(task.task_id)} · ${escapeHtml(task.title || task.status || "")}</option>`).join("");
  return `
    <div class="summary-grid">
      ${metric("Review Sprints", summary.total ?? sprints.length)}
      ${metric("Conflicts", summary.conflict_count ?? 0)}
      ${metric("Blocking", summary.blocking_conflict_count ?? 0)}
      ${metric("Open", (summary.statuses || {}).open ?? 0)}
      ${metric("In Progress", (summary.statuses || {}).in_progress ?? 0)}
      ${metric("Closed", (summary.statuses || {}).closed ?? 0)}
    </div>
    <div class="grid2">
      <label>Sprint Name
        <input id="project-review-sprint-name" value="Review Sprint ${(sprints.length || 0) + 1}">
      </label>
      <label>Provider Template
        <input id="project-review-sprint-template" value="provider-review-candidates">
      </label>
      <label>Local Strategy
        <select id="project-review-sprint-local-strategy">
          <option value="balanced">balanced</option>
          <option value="conservative">conservative</option>
          <option value="bold">bold</option>
        </select>
      </label>
      <label>Provider Candidate Count
        <select id="project-review-sprint-provider-count">
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="4">4</option>
        </select>
      </label>
    </div>
    <label>Description
      <input id="project-review-sprint-description" placeholder="group feedback for the next review pass">
    </label>
    <div class="grid2">
      <label><input id="project-review-sprint-render-midi" type="checkbox" checked> Render MIDI</label>
      <label><input id="project-review-sprint-stop-conflict" type="checkbox"> Stop on blocking conflicts</label>
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Add</th><th>Task</th><th>Status</th><th>Parent</th><th>Priority</th></tr></thead>
        <tbody>${tasks.length ? tasks.map((task) => `
          <tr>
            <td><input data-review-sprint-task value="${escapeHtml(task.task_id)}" type="checkbox"></td>
            <td>${escapeHtml(task.title || task.task_id)}</td>
            <td><span class="status ${escapeHtml(task.status || "")}">${escapeHtml(task.status || "-")}</span></td>
            <td>${escapeHtml(task.parent_version_id || "-")}</td>
            <td>${escapeHtml(task.priority ?? "-")}</td>
          </tr>
        `).join("") : `<tr><td colspan="5">No ReviewTasks available.</td></tr>`}</tbody>
      </table>
    </div>
    <div class="actions">
      <button id="project-review-sprint-create" type="button">Create Review Sprint</button>
      <button class="secondary" id="project-review-sprint-refresh" type="button">Refresh Review Sprints</button>
    </div>
    ${sprints.length ? sprints.map((sprint) => reviewSprintRowHtml(project, sprint, taskOptions, versions)).join("") : `<div class="empty">Review Sprints will appear here after you create one.</div>`}
  `;
}

Object.assign(globalThis, { projectReviewMetricsSummaryHtml, renderProjectEditorPreview, loadProjectEditorPreviewHistory, projectProviderPreviewPayload, providerPreviewHtml, renderProjectReviewWorkbench, projectReviewWorkbenchHtml, reviewTaskWorkbenchRowHtml, reviewDecisionReportHtml, reviewJudgeReportHtml, reviewCandidateWorkbenchCardHtml, renderProjectReviewSprints, projectReviewSprintsHtml });

export { projectReviewMetricsSummaryHtml, renderProjectEditorPreview, loadProjectEditorPreviewHistory, projectProviderPreviewPayload, providerPreviewHtml, renderProjectReviewWorkbench, projectReviewWorkbenchHtml, reviewTaskWorkbenchRowHtml, reviewDecisionReportHtml, reviewJudgeReportHtml, reviewCandidateWorkbenchCardHtml, renderProjectReviewSprints, projectReviewSprintsHtml };
