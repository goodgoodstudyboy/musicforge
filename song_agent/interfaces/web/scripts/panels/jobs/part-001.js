function batchPayload() {
  return {
    name: $("batch-name").value.trim(),
    csv_text: $("batch-csv-text").value,
    generation_mode: $("batch-generation-mode").value,
    pipeline_mode: $("batch-pipeline-mode").value,
    max_concurrency: Number($("batch-max-concurrency").value || 1),
  };
}

async function loadJobs() {
  try {
    const data = await api(includeHidden ? "/api/jobs?include_hidden=1" : "/api/jobs");
    jobs = data.jobs;
    if (selectedJobId && !jobs.some((job) => job.job_id === selectedJobId)) {
      selectedJobId = null;
      $("detail").innerHTML = "<div class='empty'>Select or create a job.</div>";
    }
    renderJobs();
    if (selectedJobId) await renderDetail(selectedJobId);
  } catch (err) {
    $("job-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

function renderJobs() {
  const list = $("job-list");
  if (!jobs.length) {
    list.innerHTML = "<div class='empty'>No jobs yet.</div>";
    return;
  }
  list.innerHTML = "";
  jobs.forEach((job) => {
    const item = document.createElement("button");
    item.className = "job-item" + (job.job_id === selectedJobId ? " active" : "");
    item.innerHTML = `
      <div class="job-title">${escapeHtml(job.title)}</div>
      <div class="job-sub"><span class="status ${job.status}">${job.status}</span> ${job.hidden ? "hidden · " : ""}${escapeHtml(job.step)} · ${escapeHtml(job.job_id)}</div>
    `;
    item.addEventListener("click", async () => {
      selectedJobId = job.job_id;
      activeTab = "summary";
      renderJobs();
      await renderDetail(job.job_id);
    });
    list.appendChild(item);
  });
}

async function loadBatches() {
  try {
    const data = await api(includeHiddenBatches ? "/api/batches?include_hidden=1" : "/api/batches");
    batches = data.batches;
    if (selectedBatchId && !batches.some((batch) => batch.batch_id === selectedBatchId)) {
      selectedBatchId = null;
      $("batch-detail").innerHTML = "<div class='empty'>Select or import a batch.</div>";
    }
    renderBatches();
    if (selectedBatchId) await renderBatchDetail(selectedBatchId);
  } catch (err) {
    $("batch-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
  }
}

function renderBatches() {
  const list = $("batch-list");
  if (!batches.length) {
    list.innerHTML = "<div class='empty'>No batches yet.</div>";
    return;
  }
  const rows = batches.map((batch) => `
    <tr class="${batch.batch_id === selectedBatchId ? "active" : ""}">
      <td><button class="secondary batch-open" data-batch-id="${escapeHtml(batch.batch_id)}" type="button">Open</button></td>
      <td>${escapeHtml(batch.name)}</td>
      <td><span class="status ${batch.status}">${escapeHtml(batch.status)}</span></td>
      <td>${escapeHtml(batch.total_count)}</td>
      <td>${escapeHtml(batch.completed_count)}</td>
      <td>${escapeHtml(batch.failed_count)}</td>
      <td>${escapeHtml(batch.running_count)}</td>
      <td>${escapeHtml(batch.updated_at || "-")}</td>
    </tr>
  `).join("");
  list.innerHTML = `
    <table>
      <thead><tr><th></th><th>Name</th><th>Status</th><th>Total</th><th>Completed</th><th>Failed</th><th>Running</th><th>Updated</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  list.querySelectorAll(".batch-open").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedBatchId = button.dataset.batchId;
      renderBatches();
      await renderBatchDetail(selectedBatchId);
    });
  });
}

async function renderBatchDetail(batchId) {
  const data = await api(`/api/batches/${encodeURIComponent(batchId)}`);
  const batch = data.batch;
  const items = data.items || [];
  const target = $("batch-detail");
  const rows = items.map((item) => `
    <tr>
      <td>${escapeHtml(item.index)}</td>
      <td>${escapeHtml(item.request.title || "-")}</td>
      <td>${escapeHtml(item.request.generation_mode || batch.generation_mode)}</td>
      <td>${escapeHtml(item.request.pipeline_mode || batch.pipeline_mode)}</td>
      <td><span class="status ${item.status}">${escapeHtml(item.status)}</span></td>
      <td><span class="status ${item.audio_status || "not_started"}">${escapeHtml(item.audio_status || "not_started")}</span></td>
      <td><span class="status ${item.stem_status || "not_started"}">${escapeHtml(item.stem_status || "not_started")}</span></td>
      <td>${escapeHtml(item.stem_audio_completed_count || 0)}/${escapeHtml(item.stem_count || 0)}</td>
      <td>${item.project_id ? `<button class="secondary batch-project-link" data-project-id="${escapeHtml(item.project_id)}" type="button">${escapeHtml(item.project_id)} ${escapeHtml(item.version_id || "")}</button>` : escapeHtml(item.project || "-")}</td>
      <td>${escapeHtml(item.attempt_count)}</td>
      <td>${item.job_id ? `<button class="secondary batch-job-link" data-job-id="${escapeHtml(item.job_id)}" type="button">${escapeHtml(item.job_id)}</button>` : "-"}</td>
      <td>${escapeHtml(item.output_dir || "-")}</td>
      <td>${escapeHtml(item.audio_path || "-")}</td>
      <td>${escapeHtml(item.error || item.audio_error || item.stem_error || "-")}</td>
      <td>${escapeHtml(item.updated_at || "-")}</td>
    </tr>
  `).join("");
  target.innerHTML = `
    <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
      <span>${escapeHtml(batch.name)}</span>
      <span class="status ${batch.status}">${escapeHtml(batch.status)}</span>
    </div>
    <div class="summary-grid">
      ${metric("Total", batch.total_count)}
      ${metric("Completed", batch.completed_count)}
      ${metric("Failed", batch.failed_count)}
      ${metric("Running", batch.running_count)}
    </div>
    <div class="summary-grid">
      ${metric("Queued", batch.queued_count)}
      ${metric("Concurrency", batch.max_concurrency)}
      ${metric("Mode", batch.generation_mode)}
      ${metric("Pipeline", batch.pipeline_mode)}
    </div>
    <div class="actions">
      ${batchActionButtons(batch)}
      <span>${escapeHtml(batch.batch_id)}</span>
    </div>
    ${batch.error ? `<p class="error">${escapeHtml(batch.error)}</p>` : ""}
    <table>
      <thead><tr><th>Index</th><th>Title</th><th>Mode</th><th>Pipeline</th><th>Status</th><th>Audio</th><th>Stem</th><th>Stem Audio</th><th>Project</th><th>Attempt</th><th>Job</th><th>Output</th><th>WAV</th><th>Error</th><th>Updated</th></tr></thead>
      <tbody>${rows || "<tr><td colspan='15'>No batch items.</td></tr>"}</tbody>
    </table>
  `;
  wireBatchActions(batch);
  target.querySelectorAll(".batch-job-link").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedJobId = button.dataset.jobId;
      activeTab = "summary";
      await loadJobs();
    });
  });
  target.querySelectorAll(".batch-project-link").forEach((button) => {
    button.addEventListener("click", async () => {
      selectedProjectId = button.dataset.projectId;
      activeProjectTab = "versions";
      await loadProjects();
    });
  });
}

function batchActionButtons(batch) {
  const id = encodeURIComponent(batch.batch_id);
  const buttons = [];
  if (batch.status !== "running" && batch.queued_count > 0) {
    buttons.push(`<button id="launch-batch" type="button">Launch</button>`);
  }
  if (batch.status === "running") {
    buttons.push(`<button class="secondary" id="pause-batch" type="button">Pause</button>`);
  }
  if (batch.status === "paused") {
    buttons.push(`<button id="resume-batch" type="button">Resume</button>`);
  }
  if ((batch.failed_count || batch.cancelled_count) && batch.status !== "running") {
    buttons.push(`<button class="secondary" id="retry-failed-batch" type="button">Retry Failed</button>`);
  }
  if (batch.status !== "running") {
    buttons.push(`<button class="secondary" id="render-batch-audio" type="button">Render Audio</button>`);
    buttons.push(`<button class="secondary" id="render-failed-batch-audio" type="button">Render Failed Audio</button>`);
    buttons.push(`<button class="secondary" id="render-batch-stems" type="button">Render Stems</button>`);
    buttons.push(`<button class="secondary" id="render-batch-stem-audio" type="button">Render Stem Audio</button>`);
    buttons.push(`<button class="secondary" id="render-failed-batch-stems" type="button">Render Failed Stems</button>`);
    buttons.push(`<button class="secondary" id="render-failed-batch-stem-audio" type="button">Render Failed Stem Audio</button>`);
  }
  buttons.push(`<a class="button-link secondary" href="/api/batches/${id}/export">Export</a>`);
  buttons.push(`<button class="secondary" id="open-batch-folder" type="button">Open Folder</button>`);
  if (batch.hidden) {
    buttons.push(`<button class="secondary" id="unhide-batch" type="button">Unhide</button>`);
  } else {
    buttons.push(`<button class="secondary" id="hide-batch" type="button">Hide</button>`);
  }
  if (batch.status !== "running") {
    buttons.push(`<button class="danger" id="delete-batch" type="button">Delete</button>`);
  }
  return buttons.join("");
}

function wireBatchActions(batch) {
  const id = encodeURIComponent(batch.batch_id);
  bindAction("launch-batch", async () => {
    await api(`/api/batches/${id}/launch`, { method: "POST" });
    await loadBatches();
  });
  bindAction("pause-batch", async () => {
    await api(`/api/batches/${id}/pause`, { method: "POST" });
    await loadBatches();
  });
  bindAction("resume-batch", async () => {
    await api(`/api/batches/${id}/resume`, { method: "POST" });
    await loadBatches();
  });
  bindAction("retry-failed-batch", async () => {
    if (!confirm("Retry failed batch items?")) return;
    await api(`/api/batches/${id}/retry-failed`, { method: "POST" });
    await loadBatches();
  });
  bindAction("render-batch-audio", async () => {
    await api(`/api/batches/${id}/render-audio`, { method: "POST" });
    await loadBatches();
  });
  bindAction("render-failed-batch-audio", async () => {
    await api(`/api/batches/${id}/render-failed-audio`, { method: "POST" });
    await loadBatches();
  });
  bindAction("render-batch-stems", async () => {
    await api(`/api/batches/${id}/render-stems`, { method: "POST" });
    await loadBatches();
  });
  bindAction("render-batch-stem-audio", async () => {
    await api(`/api/batches/${id}/render-stem-audio`, { method: "POST" });
    await loadBatches();
  });
  bindAction("render-failed-batch-stems", async () => {
    await api(`/api/batches/${id}/render-failed-stems`, { method: "POST" });
    await loadBatches();
  });
  bindAction("render-failed-batch-stem-audio", async () => {
    await api(`/api/batches/${id}/render-failed-stem-audio`, { method: "POST" });
    await loadBatches();
  });
  bindAction("open-batch-folder", async () => {
    await api(`/api/batches/${id}/open-folder`, { method: "POST" });
  });
  bindAction("hide-batch", async () => {
    await api(`/api/batches/${id}/hide`, { method: "POST" });
    await loadBatches();
  });
  bindAction("unhide-batch", async () => {
    await api(`/api/batches/${id}/unhide`, { method: "POST" });
    await loadBatches();
  });
  bindAction("delete-batch", async () => {
    if (!confirm("Delete this batch metadata? Generated job runs stay in runs/.")) return;
    await api(`/api/batches/${id}/delete`, { method: "POST" });
    selectedBatchId = null;
    await loadBatches();
  });
}

async function renderNodes(job, target) {
  try {
    const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/nodes`);
    const rows = data.nodes.map((node) => `
      <tr data-node="${escapeHtml(node.node)}">
        <td>
          <button class="secondary node-json" data-node="${escapeHtml(node.node)}" type="button">View JSON</button>
          ${nodeRetryButton(job, node)}
        </td>
        <td>${escapeHtml(node.node)}</td>
        <td>${escapeHtml(node.status)}</td>
        <td>${escapeHtml(node.provider_mode || "-")}</td>
        <td>${escapeHtml(node.started_at || "-")}</td>
        <td>${escapeHtml(node.finished_at || "-")}</td>
        <td>${escapeHtml(JSON.stringify(node.output_summary || {}))}</td>
        <td>${escapeHtml(node.error || "-")}</td>
      </tr>
    `).join("");
    target.innerHTML = `
      <table>
        <thead><tr><th></th><th>Node</th><th>Status</th><th>Provider</th><th>Started</th><th>Finished</th><th>Summary</th><th>Error</th></tr></thead>
        <tbody>${rows || "<tr><td colspan='8'>No node records.</td></tr>"}</tbody>
      </table>
      <pre id="node-json-preview"></pre>
    `;
    target.querySelectorAll(".node-json").forEach((button) => {
      button.addEventListener("click", async () => {
        const nodeName = button.dataset.node;
        const preview = target.querySelector("#node-json-preview");
        try {
          const detail = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/nodes/${encodeURIComponent(nodeName)}`);
          preview.textContent = JSON.stringify(detail.node, null, 2);
        } catch (err) {
          preview.textContent = err.message;
        }
      });
    });
    target.querySelectorAll(".node-retry").forEach((button) => {
      button.addEventListener("click", async () => {
        const nodeName = button.dataset.node;
        try {
          const deps = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/nodes/${encodeURIComponent(nodeName)}/dependencies`);
          const downstream = deps.downstream.length ? deps.downstream.join(", ") : "no downstream nodes";
          if (!confirm(`Retry ${nodeName} and rebuild downstream nodes: ${downstream}?`)) return;
          await api(`/api/jobs/${encodeURIComponent(job.job_id)}/nodes/${encodeURIComponent(nodeName)}/retry`, { method: "POST" });
          await loadJobs();
        } catch (err) {
          alert(err.message);
        }
      });
    });
  } catch (err) {
    target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
  }
}

function nodeRetryButton(job, node) {
  if (job.pipeline_mode !== "multinode") return "";
  if (job.status === "running" || job.status === "queued") return "";
  if (!node.can_retry) return "";
  return `<button class="secondary node-retry" data-node="${escapeHtml(node.node)}" type="button">Retry node</button>`;
}

function metric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span>${escapeHtml(String(value))}</div>`;
}

function runtimeHeader(view) {
  return `
    <div class="summary-grid">
      ${metric("Tempo", view.tempo_bpm || "-")}
      ${metric("Meter", view.meter || "-")}
      ${metric("Bars", view.total_bars ?? "-")}
      ${metric("Seconds", view.estimated_seconds ?? "-")}
    </div>
  `;
}

function warnings(items) {
  if (!items || !items.length) return "";
  return `<p class="error">${escapeHtml(items.join(" "))}</p>`;
}

function wireJobActions(job) {
  bindAction("render-audio", async () => {
    await api(`/api/jobs/${encodeURIComponent(job.job_id)}/render-audio`, { method: "POST" });
    await loadJobs();
  });
  bindAction("open-folder", async () => {
    await api(`/api/jobs/${encodeURIComponent(job.job_id)}/open-folder`, { method: "POST" });
  });
  bindAction("hide-job", async () => {
    await api(`/api/jobs/${encodeURIComponent(job.job_id)}/hide`, { method: "POST" });
    await loadJobs();
  });
  bindAction("unhide-job", async () => {
    await api(`/api/jobs/${encodeURIComponent(job.job_id)}/unhide`, { method: "POST" });
    await loadJobs();
  });
  bindAction("cancel-job", async () => {
    if (job.status === "running" && !confirm("Cancel this running job?")) return;
    await api(`/api/jobs/${encodeURIComponent(job.job_id)}/cancel`, { method: "POST" });
    await loadJobs();
  });
  bindAction("retry-job", async () => {
    if (!confirm("Retry this job?")) return;
    await api(`/api/jobs/${encodeURIComponent(job.job_id)}/retry`, { method: "POST" });
    await loadJobs();
  });
  bindAction("delete-job", async () => {
    if (!confirm("Delete this job and its run directory?")) return;
    await api(`/api/jobs/${encodeURIComponent(job.job_id)}/delete`, { method: "POST" });
    selectedJobId = null;
    await loadJobs();
  });
}

Object.assign(globalThis, { batchPayload, loadJobs, renderJobs, loadBatches, renderBatches, renderBatchDetail, batchActionButtons, wireBatchActions, renderNodes, nodeRetryButton, metric, runtimeHeader, warnings, wireJobActions });

export { batchPayload, loadJobs, renderJobs, loadBatches, renderBatches, renderBatchDetail, batchActionButtons, wireBatchActions, renderNodes, nodeRetryButton, metric, runtimeHeader, warnings, wireJobActions };
