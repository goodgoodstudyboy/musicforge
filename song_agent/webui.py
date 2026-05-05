from __future__ import annotations


def panel_html() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MusicForge Studio</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dce5;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --danger: #b42318;
      --ok: #027a48;
      --warn: #b54708;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      background: #101828;
      color: white;
      border-bottom: 1px solid #101828;
    }
    header h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
      letter-spacing: 0;
    }
    header .meta {
      display: flex;
      gap: 16px;
      color: #d0d5dd;
      font-size: 13px;
      white-space: nowrap;
    }
    main {
      display: grid;
      grid-template-columns: minmax(320px, 430px) minmax(0, 1fr);
      gap: 16px;
      padding: 16px;
      max-width: 1480px;
      margin: 0 auto;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-width: 0;
    }
    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 44px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-weight: 650;
    }
    .panel-body { padding: 14px; }
    label {
      display: block;
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    input, textarea, select {
      width: 100%;
      margin-top: 4px;
      border: 1px solid #c7cedb;
      border-radius: 6px;
      padding: 9px 10px;
      color: var(--ink);
      background: white;
      font: inherit;
    }
    textarea {
      min-height: 86px;
      resize: vertical;
    }
    .grid2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    button, .button-link {
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 9px 12px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
    }
    button:hover, .button-link:hover { background: var(--accent-dark); }
    button.secondary, .button-link.secondary {
      background: white;
      color: var(--ink);
      border-color: #c7cedb;
    }
    button.secondary:hover, .button-link.secondary:hover { background: #f2f4f7; }
    .status {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
      font-weight: 650;
      background: #eef4ff;
      color: #3538cd;
    }
    .status.completed { background: #ecfdf3; color: var(--ok); }
    .status.failed { background: #fef3f2; color: var(--danger); }
    .status.running { background: #fffaeb; color: var(--warn); }
    .jobs {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      min-height: calc(100vh - 88px);
    }
    .job-list {
      border-right: 1px solid var(--line);
      overflow: auto;
      max-height: calc(100vh - 134px);
    }
    .job-item {
      width: 100%;
      display: block;
      text-align: left;
      background: white;
      color: var(--ink);
      border: 0;
      border-bottom: 1px solid var(--line);
      border-radius: 0;
      padding: 12px 14px;
    }
    .job-item:hover, .job-item.active { background: #f8fafc; }
    .job-title {
      font-weight: 650;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      margin-bottom: 6px;
    }
    .job-sub {
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .detail {
      min-width: 0;
      padding: 14px;
      overflow: auto;
      max-height: calc(100vh - 134px);
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(110px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfe;
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }
    pre {
      margin: 0;
      max-height: 360px;
      overflow: auto;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0b1220;
      color: #e6edf7;
      font-size: 12px;
    }
    .tabs {
      display: flex;
      gap: 6px;
      margin: 10px 0;
      flex-wrap: wrap;
    }
    .tabs button {
      background: white;
      color: var(--ink);
      border-color: #c7cedb;
      padding: 7px 10px;
    }
    .tabs button.active {
      background: #e6fffb;
      border-color: var(--accent);
      color: var(--accent-dark);
    }
    .empty {
      color: var(--muted);
      padding: 24px;
      text-align: center;
    }
    .error { color: var(--danger); }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .jobs { grid-template-columns: 1fr; }
      .job-list { border-right: 0; max-height: none; }
      .summary-grid { grid-template-columns: 1fr 1fr; }
      header { height: auto; align-items: flex-start; flex-direction: column; gap: 6px; padding: 12px 16px; }
      header .meta { flex-wrap: wrap; }
    }
  </style>
</head>
<body>
  <header>
    <h1>MusicForge Studio</h1>
    <div class="meta">
      <span id="version">version</span>
      <span id="mode">mode</span>
      <span id="runs">runs</span>
      <span id="poll">polling</span>
    </div>
  </header>
  <main>
    <section>
      <div class="panel-title">
        <span>Song Request</span>
        <select id="preset"></select>
      </div>
      <div class="panel-body">
        <form id="song-form">
          <label>Title
            <input id="title" name="title" required>
          </label>
          <div class="grid2">
            <label>Language
              <input id="language" name="language" required>
            </label>
            <label>Vocal Mode
              <select id="vocal_mode" name="vocal_mode">
                <option value="guide_melody">guide_melody</option>
                <option value="instrumental">instrumental</option>
                <option value="lyrics_only">lyrics_only</option>
              </select>
            </label>
          </div>
          <label>Style
            <textarea id="style" name="style" required></textarea>
          </label>
          <label>Theme
            <textarea id="theme" name="theme" required></textarea>
          </label>
          <div class="grid2">
            <label>Duration Seconds
              <input id="duration_seconds" name="duration_seconds" type="number" min="30" max="600" required>
            </label>
            <label>Tempo BPM
              <input id="tempo_bpm" name="tempo_bpm" type="number" min="40" max="240">
            </label>
          </div>
          <label>Key
            <input id="key" name="key">
          </label>
          <label>Lyrics
            <textarea id="lyrics" name="lyrics"></textarea>
          </label>
          <div class="actions">
            <button type="submit">Generate</button>
            <button class="secondary" id="reset-form" type="button">Reset</button>
          </div>
        </form>
      </div>
    </section>
    <section>
      <div class="panel-title">
        <span>Jobs</span>
        <button class="secondary" id="refresh" type="button">Refresh</button>
      </div>
      <div class="jobs">
        <div class="job-list" id="job-list"><div class="empty">No jobs yet.</div></div>
        <div class="detail" id="detail"><div class="empty">Select or create a job.</div></div>
      </div>
    </section>
  </main>
  <script>
    let template = null;
    let jobs = [];
    let selectedJobId = null;
    let activeTab = "summary";

    const $ = (id) => document.getElementById(id);

    async function api(path, options = {}) {
      const res = await fetch(path, options);
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }

    async function init() {
      const info = await api("/api/info");
      template = await api("/api/template");
      $("version").textContent = "v" + info.version;
      $("mode").textContent = info.mode;
      $("runs").textContent = info.runs_dir;
      fillPresets();
      fillForm(template.defaults);
      await loadJobs();
      setInterval(loadJobs, 2000);
      $("poll").textContent = "polling 2s";
    }

    function fillPresets() {
      const select = $("preset");
      select.innerHTML = "<option value=''>Default</option>";
      template.presets.forEach((preset, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = preset.name;
        select.appendChild(option);
      });
      select.addEventListener("change", () => {
        const value = select.value;
        if (value === "") {
          fillForm(template.defaults);
        } else {
          fillForm({ ...template.defaults, ...template.presets[Number(value)] });
        }
      });
    }

    function fillForm(data) {
      for (const [key, value] of Object.entries(data)) {
        const el = $(key);
        if (el) el.value = value ?? "";
      }
    }

    function formPayload() {
      const payload = {
        title: $("title").value.trim(),
        language: $("language").value.trim(),
        style: $("style").value.trim(),
        theme: $("theme").value.trim(),
        duration_seconds: Number($("duration_seconds").value),
        vocal_mode: $("vocal_mode").value,
      };
      if ($("tempo_bpm").value) payload.tempo_bpm = Number($("tempo_bpm").value);
      if ($("key").value.trim()) payload.key = $("key").value.trim();
      if ($("lyrics").value.trim()) payload.lyrics = $("lyrics").value;
      return payload;
    }

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
    $("refresh").addEventListener("click", loadJobs);

    async function loadJobs() {
      try {
        const data = await api("/api/jobs");
        jobs = data.jobs;
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
          <div class="job-sub"><span class="status ${job.status}">${job.status}</span> ${escapeHtml(job.step)} · ${escapeHtml(job.job_id)}</div>
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

    async function renderDetail(jobId) {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      const detail = $("detail");
      const summary = job.summary || {};
      const tabs = ["summary", "logs", "json", "artifacts"];
      detail.innerHTML = `
        <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
          <span>${escapeHtml(job.title)}</span>
          <span class="status ${job.status}">${job.status}</span>
        </div>
        <div class="summary-grid">
          ${metric("Tempo", summary.tempo_bpm || "-")}
          ${metric("Key", summary.key || "-")}
          ${metric("Sections", summary.section_count || "-")}
          ${metric("Notes", summary.note_count || "-")}
        </div>
        <div class="actions">
          <a class="button-link" href="/api/jobs/${encodeURIComponent(job.job_id)}/midi">Download MIDI</a>
          <button class="secondary" id="open-folder" type="button">Open Folder</button>
          <span>${escapeHtml(job.output_dir)}</span>
        </div>
        ${job.error ? `<p class="error">${escapeHtml(job.error)}</p>` : ""}
        <div class="tabs">
          ${tabs.map(tab => `<button type="button" class="${activeTab === tab ? "active" : ""}" data-tab="${tab}">${tab}</button>`).join("")}
        </div>
        <div id="tab-content"></div>
      `;
      detail.querySelectorAll("[data-tab]").forEach((button) => {
        button.addEventListener("click", async () => {
          activeTab = button.dataset.tab;
          await renderDetail(job.job_id);
        });
      });
      $("open-folder").addEventListener("click", async () => {
        try { await api(`/api/jobs/${encodeURIComponent(job.job_id)}/open-folder`); }
        catch (err) { alert(err.message); }
      });
      await renderTab(job);
    }

    async function renderTab(job) {
      const target = $("tab-content");
      if (activeTab === "summary") {
        target.innerHTML = `<pre>${escapeHtml(JSON.stringify(job, null, 2))}</pre>`;
      } else if (activeTab === "logs") {
        const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/events`);
        target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.events, null, 2))}</pre>`;
      } else if (activeTab === "json") {
        try {
          const plan = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/song-plan`);
          target.innerHTML = `<pre>${escapeHtml(JSON.stringify(plan, null, 2))}</pre>`;
        } catch (err) {
          target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
        }
      } else if (activeTab === "artifacts") {
        const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/artifacts`);
        target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.artifacts, null, 2))}</pre>`;
      }
    }

    function metric(label, value) {
      return `<div class="metric"><span>${escapeHtml(label)}</span>${escapeHtml(String(value))}</div>`;
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    init().catch((err) => {
      document.body.innerHTML = `<pre>${escapeHtml(err.stack || err.message)}</pre>`;
    });
  </script>
</body>
</html>"""
