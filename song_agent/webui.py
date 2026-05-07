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
    input[type="checkbox"] {
      width: auto;
      margin: 0 6px 0 0;
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
    .stack {
      display: grid;
      gap: 16px;
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
    button.danger {
      background: #fff;
      color: var(--danger);
      border-color: #fecdca;
    }
    button.danger:hover { background: #fef3f2; }
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
    .auth-lock {
      display: none;
      max-width: 420px;
      margin: 28px auto 0;
    }
    body.locked main { display: none; }
    body.locked .auth-lock { display: block; }
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
    table {
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      background: white;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      background: #f8fafc;
    }
    tr:last-child td { border-bottom: 0; }
    .message {
      min-height: 20px;
      color: var(--muted);
      font-size: 13px;
    }
    .batch-layout, .project-layout {
      display: grid;
      grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .batch-list, .batch-detail, .project-list, .project-detail {
      overflow: auto;
    }
    .batch-detail, .project-detail {
      margin-top: 14px;
    }
    .audio-player {
      width: 100%;
      margin: 8px 0 4px;
    }
    .candidate-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(220px, 1fr));
      gap: 10px;
      margin: 12px 0;
    }
    .candidate-group {
      border-top: 1px solid var(--line);
      padding-top: 12px;
      margin-top: 16px;
    }
    .candidate-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: white;
      min-width: 0;
    }
    .candidate-card .summary-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .candidate-card h4 {
      margin: 0 0 8px;
      font-size: 14px;
      letter-spacing: 0;
    }
    .compare-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      align-items: start;
    }
    .table-scroll {
      overflow-x: auto;
      margin-top: 10px;
    }
    .table-scroll table {
      min-width: 720px;
    }
    .wrap-cell {
      overflow-wrap: anywhere;
      word-break: break-word;
      max-width: 360px;
    }
    td .actions {
      margin-top: 0;
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .jobs { grid-template-columns: 1fr; }
      .job-list { border-right: 0; max-height: none; }
      .summary-grid { grid-template-columns: 1fr 1fr; }
      .batch-layout { grid-template-columns: 1fr; }
      .project-layout { grid-template-columns: 1fr; }
      .compare-grid { grid-template-columns: 1fr; }
      .candidate-grid { grid-template-columns: 1fr; }
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
  <section id="auth-lock" class="auth-lock">
    <div class="panel-title">Access token</div>
    <div class="panel-body">
      <form id="auth-form">
        <label>Access token
          <input id="auth-token" type="password" autocomplete="off">
        </label>
        <div class="actions">
          <button type="submit">Unlock</button>
          <span id="auth-message" class="message"></span>
        </div>
      </form>
    </div>
  </section>
  <main>
    <div class="stack">
      <section>
        <div class="panel-title">
          <span>Provider Settings</span>
          <span id="provider-status" class="status">not configured</span>
        </div>
        <div class="panel-body">
          <form id="provider-form">
            <label>Base URL
              <input id="provider-base-url" name="base_url" placeholder="https://api.example.com/v1">
            </label>
            <div class="grid2">
              <label>Wire API
                <select id="provider-wire-api" name="wire_api">
                  <option value="openai_chat_completions">openai_chat_completions</option>
                  <option value="mock">mock</option>
                </select>
              </label>
              <label>Model
                <input id="provider-model" name="model">
              </label>
            </div>
            <label>API Key
              <input id="provider-api-key" name="api_key" type="password" autocomplete="off" placeholder="leave blank to save empty key">
            </label>
            <div class="grid2">
              <label>Light Model
                <input id="provider-light-model" name="light_model">
              </label>
              <label>Review Model
                <input id="provider-review-model" name="review_model">
              </label>
            </div>
            <div class="grid2">
              <label>Timeout Seconds
                <input id="provider-timeout-seconds" name="timeout_seconds" type="number" min="5" max="300">
              </label>
              <label>Max Retries
                <input id="provider-max-retries" name="max_retries" type="number" min="0" max="5">
              </label>
            </div>
            <label>Max Output Tokens
              <input id="provider-max-output-tokens" name="max_output_tokens" type="number" min="256" max="16000">
            </label>
            <div class="actions">
              <button type="submit">Save</button>
              <button class="secondary" id="provider-reset" type="button">Reset</button>
              <button class="secondary" id="provider-test" type="button">Test</button>
              <span id="provider-message"></span>
            </div>
          </form>
        </div>
      </section>
      <section>
        <div class="panel-title">
          <span>Prompt Templates</span>
          <span id="prompt-template-status" class="status">built-in</span>
        </div>
        <div class="panel-body">
          <label>Template
            <select id="prompt-template-select"></select>
          </label>
          <label>System Prompt
            <textarea id="prompt-template-system" spellcheck="false"></textarea>
          </label>
          <label>User Prompt
            <textarea id="prompt-template-user" spellcheck="false"></textarea>
          </label>
          <div class="actions">
            <button id="prompt-template-save" type="button">Save Template Override</button>
            <button class="secondary" id="prompt-template-reset" type="button">Reset Template</button>
            <span id="prompt-template-message" class="message"></span>
          </div>
        </div>
      </section>
      <section>
        <div class="panel-title">
          <span>Renderer Settings</span>
          <span id="renderer-status" class="status">missing</span>
        </div>
        <div class="panel-body">
          <form id="renderer-form">
            <label>Renderer Type
              <select id="renderer-type" name="renderer_type">
                <option value="fluidsynth">fluidsynth</option>
              </select>
            </label>
            <label>FluidSynth Path
              <input id="renderer-fluidsynth-path" name="fluidsynth_path" placeholder="fluidsynth">
            </label>
            <label>SoundFont Path
              <input id="renderer-soundfont-path" name="soundfont_path" placeholder="C:\path\to\soundfont.sf2">
            </label>
            <div class="grid2">
              <label>Sample Rate
                <input id="renderer-sample-rate" name="sample_rate" type="number" min="8000" max="192000">
              </label>
              <label>Gain
                <input id="renderer-gain" name="gain" type="number" min="0" max="10" step="0.1">
              </label>
            </div>
            <div class="actions">
              <button type="submit">Save</button>
              <button class="secondary" id="renderer-reset" type="button">Reset</button>
              <button class="secondary" id="renderer-test" type="button">Test renderer</button>
              <span id="renderer-message"></span>
            </div>
          </form>
        </div>
      </section>
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
            <label>Generation Mode
              <select id="generation_mode" name="generation_mode">
                <option value="local">local</option>
                <option value="provider">provider</option>
              </select>
            </label>
            <label>Pipeline Mode
              <select id="pipeline_mode" name="pipeline_mode">
                <option value="single">single</option>
                <option value="multinode">multinode</option>
              </select>
            </label>
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
          <span>Projects</span>
          <div class="actions" style="margin-top:0;">
            <label style="margin:0;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:650;">
              <input id="include-hidden-projects" type="checkbox" style="width:auto;margin:0;">
              Hidden
            </label>
            <button class="secondary" id="refresh-projects" type="button">Refresh</button>
          </div>
        </div>
        <div class="panel-body">
          <form id="project-form">
            <label>Project Name
              <input id="project-name" name="project-name" placeholder="New song project">
            </label>
            <label>Description
              <textarea id="project-description" name="project-description"></textarea>
            </label>
            <label>Tags
              <input id="project-tags" name="project-tags" placeholder="demo, pop">
            </label>
            <div class="actions">
              <button type="submit">New Project</button>
              <span id="project-message" class="message"></span>
            </div>
          </form>
          <div class="grid2">
            <label>Search Projects
              <input id="project-search" placeholder="name, description, version">
            </label>
            <label>Status Filter
              <select id="project-status-filter">
                <option value="">all</option>
                <option value="active">active</option>
                <option value="finalized">finalized</option>
                <option value="selected">selected</option>
                <option value="final">final</option>
                <option value="gate_failed">gate_failed</option>
              </select>
            </label>
          </div>
          <div class="grid2">
            <label>Variant Filter
              <select id="project-variant-filter">
                <option value="">all</option>
                <option value="original">original</option>
                <option value="manual">manual</option>
                <option value="section_edit">section_edit</option>
                <option value="track_edit">track_edit</option>
                <option value="lyrics_edit">lyrics_edit</option>
                <option value="melody_edit">melody_edit</option>
                <option value="arrangement_edit">arrangement_edit</option>
                <option value="style_variation">style_variation</option>
              </select>
            </label>
            <label>Filters
              <button class="secondary" id="clear-project-filters" type="button" style="width:100%;margin-top:4px;">Clear Filters</button>
            </label>
          </div>
          <div id="project-list" class="project-list"><div class="empty">No projects yet.</div></div>
        </div>
      </section>
    </div>
    <section>
      <div class="panel-title">
        <span>Jobs</span>
        <div class="actions" style="margin-top:0;">
          <label style="margin:0;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:650;">
            <input id="include-hidden" type="checkbox" style="width:auto;margin:0;">
            Hidden
          </label>
          <button class="secondary" id="refresh" type="button">Refresh</button>
        </div>
      </div>
      <div class="jobs">
        <div class="job-list" id="job-list"><div class="empty">No jobs yet.</div></div>
        <div class="detail" id="detail"><div class="empty">Select or create a job.</div></div>
      </div>
    </section>
    <section style="grid-column: 1 / -1;">
      <div class="panel-title">
        <span>Project Detail</span>
      </div>
      <div class="panel-body">
        <div id="project-detail" class="project-detail"><div class="empty">Select or create a project.</div></div>
      </div>
    </section>
    <section style="grid-column: 1 / -1;">
      <div class="panel-title">
        <span>Batch</span>
        <div class="actions" style="margin-top:0;">
          <label style="margin:0;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:650;">
            <input id="include-hidden-batches" type="checkbox" style="width:auto;margin:0;">
            Hidden
          </label>
          <button class="secondary" id="refresh-batches" type="button">Refresh</button>
        </div>
      </div>
      <div class="panel-body">
        <div class="batch-layout">
          <form id="batch-form">
            <label>Batch Name
              <input id="batch-name" name="batch-name" value="MusicForge Batch">
            </label>
            <label>CSV File
              <input id="batch-csv-file" name="batch-csv-file" type="file" accept=".csv,text/csv,text/plain">
            </label>
            <label>CSV Text
              <textarea id="batch-csv-text" name="batch-csv-text" spellcheck="false">title,language,style,theme,duration_seconds,tempo_bpm,key,vocal_mode,lyrics,generation_mode,pipeline_mode
Batch Demo One,English,synth pop,late city lights,90,100,C,guide_melody,,local,multinode
Batch Demo Two,English,lo-fi,quiet morning room,60,82,A minor,guide_melody,,local,single</textarea>
            </label>
            <div class="grid2">
              <label>Generation Mode
                <select id="batch-generation-mode" name="batch-generation-mode">
                  <option value="local">local</option>
                  <option value="provider">provider</option>
                </select>
              </label>
              <label>Pipeline Mode
                <select id="batch-pipeline-mode" name="batch-pipeline-mode">
                  <option value="multinode">multinode</option>
                  <option value="single">single</option>
                </select>
              </label>
            </div>
            <label>Max Concurrency
              <input id="batch-max-concurrency" name="batch-max-concurrency" type="number" min="1" max="4" value="1">
            </label>
            <div class="actions">
              <button type="submit">Import</button>
              <span id="batch-message" class="message"></span>
            </div>
          </form>
          <div>
            <div id="batch-list" class="batch-list"><div class="empty">No batches yet.</div></div>
          </div>
        </div>
        <div id="batch-detail" class="batch-detail"><div class="empty">Select or import a batch.</div></div>
      </div>
    </section>
  </main>
  <script>
    let template = null;
    let jobs = [];
    let selectedJobId = null;
    let activeTab = "summary";
    let includeHidden = false;
    let providerConfig = null;
    let rendererConfig = null;
    let authRequired = false;
    let accessToken = sessionStorage.getItem("musicforge_access_token") || "";
    let batches = [];
    let selectedBatchId = null;
    let includeHiddenBatches = false;
    let projects = [];
    let selectedProjectId = null;
    let includeHiddenProjects = false;
    let activeProjectTab = "versions";
    let projectVariationParentId = null;
    let projectEditParentId = null;
    let editPresets = [];
    let promptTemplates = [];
    let providerEditPreview = null;

    const $ = (id) => document.getElementById(id);

    async function api(path, options = {}) {
      if (authRequired && !accessToken && path !== "/api/info") {
        showAuthLock("");
        throw new Error("Unauthorized.");
      }
      const headers = new Headers(options.headers || {});
      if (authRequired && accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
      const res = await fetch(path, { ...options, headers });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (res.status === 401) {
        sessionStorage.removeItem("musicforge_access_token");
        accessToken = "";
        showAuthLock("Unauthorized.");
        throw new Error(data.error || res.statusText);
      }
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }

    async function init() {
      const info = await api("/api/info");
      authRequired = Boolean(info.auth_required);
      if (authRequired && !accessToken) {
        showAuthLock("");
        $("version").textContent = "v" + info.version;
        $("mode").textContent = info.mode;
        $("runs").textContent = info.runs_dir;
        return;
      }
      hideAuthLock();
      template = await api("/api/template");
      $("version").textContent = "v" + info.version;
      $("mode").textContent = info.mode;
      $("runs").textContent = info.runs_dir;
      fillPresets();
      fillForm(template.defaults);
      await loadProvider();
      await loadPromptTemplates();
      await loadRenderer();
      await loadEditPresets();
      await loadJobs();
      await loadProjects();
      await loadBatches();
      setInterval(() => {
        loadJobs();
        loadProjects();
        loadBatches();
      }, 2000);
      $("poll").textContent = "polling 2s";
    }

    $("auth-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      accessToken = $("auth-token").value.trim();
      sessionStorage.setItem("musicforge_access_token", accessToken);
      $("auth-token").value = "";
      try {
        await init();
      } catch (err) {
        showAuthLock(err.message);
      }
    });

    function showAuthLock(message) {
      document.body.classList.add("locked");
      $("auth-message").textContent = message || "";
    }

    function hideAuthLock() {
      document.body.classList.remove("locked");
      $("auth-message").textContent = "";
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
        generation_mode: $("generation_mode").value,
        pipeline_mode: $("pipeline_mode").value,
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
    $("include-hidden").addEventListener("change", async () => {
      includeHidden = $("include-hidden").checked;
      await loadJobs();
    });
    $("refresh-projects").addEventListener("click", loadProjects);
    $("include-hidden-projects").addEventListener("change", async () => {
      includeHiddenProjects = $("include-hidden-projects").checked;
      await loadProjects();
    });
    ["project-search", "project-status-filter", "project-variant-filter"].forEach((id) => {
      $(id).addEventListener("change", loadProjects);
    });
    $("project-search").addEventListener("input", debounce(loadProjects, 250));
    $("clear-project-filters").addEventListener("click", async () => {
      $("project-search").value = "";
      $("project-status-filter").value = "";
      $("project-variant-filter").value = "";
      $("include-hidden-projects").checked = false;
      includeHiddenProjects = false;
      await loadProjects();
    });
    $("project-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(projectPayload()),
        });
        selectedProjectId = data.project.project_id;
        activeProjectTab = "versions";
        $("project-message").textContent = "created";
        await loadProjects();
      } catch (err) {
        $("project-message").textContent = err.message;
      }
    });
    $("refresh-batches").addEventListener("click", loadBatches);
    $("include-hidden-batches").addEventListener("change", async () => {
      includeHiddenBatches = $("include-hidden-batches").checked;
      await loadBatches();
    });
    $("batch-csv-file").addEventListener("change", async (event) => {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      $("batch-csv-text").value = await file.text();
    });
    $("batch-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/batches/import-csv", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(batchPayload()),
        });
        selectedBatchId = data.batch.batch_id;
        $("batch-message").textContent = "imported";
        await loadBatches();
      } catch (err) {
        $("batch-message").textContent = err.message;
      }
    });
    $("provider-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/provider", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(providerPayload()),
        });
        applyProvider(data);
        $("provider-message").textContent = "saved";
        $("provider-api-key").value = "";
      } catch (err) {
        $("provider-message").textContent = err.message;
      }
    });
    $("provider-reset").addEventListener("click", async () => {
      if (!confirm("Reset provider settings?")) return;
      try {
        await api("/api/provider/reset", { method: "POST" });
        await loadProvider();
        $("provider-message").textContent = "reset";
      } catch (err) {
        $("provider-message").textContent = err.message;
      }
    });
    $("provider-test").addEventListener("click", async () => {
      try {
        const data = await api("/api/provider/test", { method: "POST" });
        $("provider-message").textContent = data.message || "test ok";
      } catch (err) {
        $("provider-message").textContent = err.message;
      }
    });
    $("prompt-template-select").addEventListener("change", () => {
      applyPromptTemplateSelection();
    });
    $("prompt-template-save").addEventListener("click", async () => {
      const templateId = $("prompt-template-select").value || "provider-edit-intent";
      try {
        await api(`/api/prompt-templates/${encodeURIComponent(templateId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            system_prompt: $("prompt-template-system").value,
            user_prompt: $("prompt-template-user").value,
          }),
        });
        $("prompt-template-message").textContent = "saved";
        await loadPromptTemplates();
      } catch (err) {
        $("prompt-template-message").textContent = err.message;
      }
    });
    $("prompt-template-reset").addEventListener("click", async () => {
      const templateId = $("prompt-template-select").value || "provider-edit-intent";
      try {
        await api(`/api/prompt-templates/${encodeURIComponent(templateId)}/reset`, { method: "POST" });
        $("prompt-template-message").textContent = "reset";
        await loadPromptTemplates();
      } catch (err) {
        $("prompt-template-message").textContent = err.message;
      }
    });
    $("renderer-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/renderer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(rendererPayload()),
        });
        applyRenderer(data);
        $("renderer-message").textContent = "saved";
      } catch (err) {
        $("renderer-message").textContent = err.message;
      }
    });
    $("renderer-reset").addEventListener("click", async () => {
      if (!confirm("Reset renderer settings?")) return;
      try {
        await api("/api/renderer/reset", { method: "POST" });
        await loadRenderer();
        $("renderer-message").textContent = "reset";
      } catch (err) {
        $("renderer-message").textContent = err.message;
      }
    });
    $("renderer-test").addEventListener("click", async () => {
      try {
        const data = await api("/api/renderer/test", { method: "POST" });
        $("renderer-message").textContent = data.message || "test ok";
      } catch (err) {
        $("renderer-message").textContent = err.message;
      }
    });

    async function loadProvider() {
      const data = await api("/api/provider");
      applyProvider(data);
    }

    function applyProvider(data) {
      providerConfig = data.config;
      $("provider-status").textContent = data.configured ? "configured" : "not configured";
      $("provider-base-url").value = providerConfig.base_url || "";
      $("provider-wire-api").value = providerConfig.wire_api || "openai_chat_completions";
      $("provider-model").value = providerConfig.model || "";
      $("provider-light-model").value = providerConfig.light_model || "";
      $("provider-review-model").value = providerConfig.review_model || "";
      $("provider-timeout-seconds").value = providerConfig.timeout_seconds || 60;
      $("provider-max-retries").value = providerConfig.max_retries ?? 1;
      $("provider-max-output-tokens").value = providerConfig.max_output_tokens || 4000;
      $("provider-api-key").placeholder = providerConfig.api_key_set
        ? `saved: ${providerConfig.api_key_masked}`
        : "leave blank to save empty key";
    }

    function providerPayload() {
      return {
        base_url: $("provider-base-url").value.trim(),
        wire_api: $("provider-wire-api").value,
        api_key: $("provider-api-key").value,
        model: $("provider-model").value.trim(),
        light_model: $("provider-light-model").value.trim(),
        review_model: $("provider-review-model").value.trim(),
        timeout_seconds: Number($("provider-timeout-seconds").value || 60),
        max_retries: Number($("provider-max-retries").value || 0),
        max_output_tokens: Number($("provider-max-output-tokens").value || 4000),
      };
    }

    async function loadRenderer() {
      const data = await api("/api/renderer");
      applyRenderer(data);
    }

    async function loadEditPresets() {
      const data = await api("/api/edit-presets");
      editPresets = data.presets || [];
    }

    async function loadPromptTemplates() {
      const data = await api("/api/prompt-templates");
      promptTemplates = data.templates || [];
      const select = $("prompt-template-select");
      select.innerHTML = promptTemplates.map((template) => `<option value="${escapeHtml(template.template_id)}">${escapeHtml(template.name)}${template.overridden ? " · override" : ""}</option>`).join("");
      if (!select.value && promptTemplates.some((template) => template.template_id === "provider-edit-intent")) {
        select.value = "provider-edit-intent";
      }
      $("prompt-template-status").textContent = `${data.override_count || 0} overrides`;
      applyPromptTemplateSelection();
    }

    function applyPromptTemplateSelection() {
      const template = promptTemplates.find((item) => item.template_id === $("prompt-template-select").value) || promptTemplates[0];
      if (!template) return;
      $("prompt-template-system").value = template.system_prompt || "";
      $("prompt-template-user").value = template.user_prompt || "";
    }

    function applyRenderer(data) {
      rendererConfig = data.config;
      $("renderer-status").textContent = data.configured ? "configured" : "missing";
      $("renderer-type").value = rendererConfig.renderer_type || "fluidsynth";
      $("renderer-fluidsynth-path").value = rendererConfig.fluidsynth_path || "fluidsynth";
      $("renderer-soundfont-path").value = rendererConfig.soundfont_path || "";
      $("renderer-sample-rate").value = rendererConfig.sample_rate || 44100;
      $("renderer-gain").value = rendererConfig.gain ?? 0.6;
      const exists = rendererConfig.soundfont_exists ? "soundfont exists" : "soundfont missing";
      $("renderer-message").textContent = rendererConfig.soundfont_path ? exists : "";
    }

    function rendererPayload() {
      return {
        renderer_type: $("renderer-type").value,
        fluidsynth_path: $("renderer-fluidsynth-path").value.trim(),
        soundfont_path: $("renderer-soundfont-path").value.trim(),
        sample_rate: Number($("renderer-sample-rate").value || 44100),
        gain: Number($("renderer-gain").value || 0.6),
      };
    }

    function batchPayload() {
      return {
        name: $("batch-name").value.trim(),
        csv_text: $("batch-csv-text").value,
        generation_mode: $("batch-generation-mode").value,
        pipeline_mode: $("batch-pipeline-mode").value,
        max_concurrency: Number($("batch-max-concurrency").value || 1),
      };
    }

    function projectPayload() {
      return {
        name: $("project-name").value.trim() || $("title").value.trim() || "Untitled Project",
        description: $("project-description").value.trim(),
        tags: $("project-tags").value
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
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

    async function loadProjects() {
      try {
        const params = new URLSearchParams();
        if (includeHiddenProjects) params.set("include_hidden", "1");
        if ($("project-search").value.trim()) params.set("q", $("project-search").value.trim());
        if ($("project-status-filter").value) params.set("status", $("project-status-filter").value);
        if ($("project-variant-filter").value) params.set("variant_type", $("project-variant-filter").value);
        const data = await api(`/api/projects${params.toString() ? "?" + params.toString() : ""}`);
        projects = data.projects;
        if (selectedProjectId && !projects.some((project) => project.project_id === selectedProjectId)) {
          selectedProjectId = null;
          $("project-detail").innerHTML = "<div class='empty'>Select or create a project.</div>";
        }
        renderProjects();
        if (selectedProjectId) await renderProjectDetail(selectedProjectId);
      } catch (err) {
        $("project-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    function renderProjects() {
      const list = $("project-list");
      if (!projects.length) {
        list.innerHTML = "<div class='empty'>No projects yet.</div>";
        return;
      }
      const rows = projects.map((project) => `
        <tr class="${project.project_id === selectedProjectId ? "active" : ""}">
          <td><button class="secondary project-open" data-project-id="${escapeHtml(project.project_id)}" type="button">Open</button></td>
          <td>${escapeHtml(project.name)}</td>
          <td><span class="status ${project.status}">${escapeHtml(project.status)}</span></td>
          <td>${escapeHtml(project.version_count || 0)}</td>
          <td>${escapeHtml(project.selected_version_id || "-")}</td>
          <td>${escapeHtml(project.final_version_id || "-")}</td>
          <td>${escapeHtml(project.best_quality_score ?? "-")}</td>
        </tr>
      `).join("");
      list.innerHTML = `
        <table>
          <thead><tr><th></th><th>Name</th><th>Status</th><th>Versions</th><th>Selected</th><th>Final</th><th>Best Quality</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      list.querySelectorAll(".project-open").forEach((button) => {
        button.addEventListener("click", async () => {
          selectedProjectId = button.dataset.projectId;
          activeProjectTab = "versions";
          renderProjects();
          await renderProjectDetail(selectedProjectId);
        });
      });
    }

    async function renderProjectDetail(projectId) {
      const data = await api(`/api/projects/${encodeURIComponent(projectId)}`);
      const project = data.project;
      const versions = data.versions || [];
      const tabs = ["versions", "variation", "edit", "candidates", "quality-gate", "final-export", "compare", "export", "events"];
      const target = $("project-detail");
      target.innerHTML = `
        <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
          <span>${escapeHtml(project.name)}</span>
          <span class="status ${project.status}">${escapeHtml(project.status)}</span>
        </div>
        <div class="summary-grid">
          ${metric("Versions", project.version_count || 0)}
          ${metric("Selected", project.selected_version_id || "-")}
          ${metric("Final", project.final_version_id || "-")}
          ${metric("Best Quality", project.best_quality_score ?? "-")}
        </div>
        <div class="actions">
          ${projectActionButtons(project)}
          <span>${escapeHtml(project.project_id)}</span>
        </div>
        <div class="grid2">
          <label>New Version Name
            <input id="project-version-name" value="Version ${(versions.length || 0) + 1}">
          </label>
          <label>Add Existing Job ID
            <input id="project-existing-job-id" placeholder="job-id">
          </label>
        </div>
        <label>Version Note
          <input id="project-version-note" placeholder="short note">
        </label>
        <div class="actions">
          <button id="project-new-version" type="button">New Version</button>
          <button class="secondary" id="project-add-job" type="button">Add Existing Job</button>
        </div>
        <div class="tabs">
          ${tabs.map(tab => `<button type="button" class="${activeProjectTab === tab ? "active" : ""}" data-project-tab="${tab}">${projectTabLabel(tab)}</button>`).join("")}
        </div>
        <div id="project-tab-content"></div>
      `;
      target.querySelectorAll("[data-project-tab]").forEach((button) => {
        button.addEventListener("click", async () => {
          activeProjectTab = button.dataset.projectTab;
          await renderProjectDetail(project.project_id);
        });
      });
      wireProjectActions(project, versions);
      await renderProjectTab(project, versions);
    }

    function projectActionButtons(project) {
      const buttons = [];
      buttons.push(`<a class="button-link secondary" href="/api/projects/${encodeURIComponent(project.project_id)}/export">Export</a>`);
      if (project.hidden) {
        buttons.push(`<button class="secondary" id="unhide-project" type="button">Unhide</button>`);
      } else {
        buttons.push(`<button class="secondary" id="hide-project" type="button">Hide</button>`);
      }
      buttons.push(`<button class="danger" id="delete-project" type="button">Delete Project</button>`);
      return buttons.join("");
    }

    function wireProjectActions(project, versions) {
      const id = encodeURIComponent(project.project_id);
      bindAction("project-new-version", async () => {
        await api(`/api/projects/${id}/versions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            request: formPayload(),
            name: $("project-version-name").value.trim(),
            note: $("project-version-note").value.trim(),
            generation_mode: $("generation_mode").value,
            pipeline_mode: $("pipeline_mode").value,
          }),
        });
        await loadJobs();
        await loadProjects();
      });
      bindAction("project-add-job", async () => {
        await api(`/api/projects/${id}/versions/from-job`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            job_id: $("project-existing-job-id").value.trim(),
            name: $("project-version-name").value.trim(),
            note: $("project-version-note").value.trim(),
          }),
        });
        await loadProjects();
      });
      bindAction("hide-project", async () => {
        await api(`/api/projects/${id}/hide`, { method: "POST" });
        await loadProjects();
      });
      bindAction("unhide-project", async () => {
        await api(`/api/projects/${id}/unhide`, { method: "POST" });
        await loadProjects();
      });
      bindAction("delete-project", async () => {
        if (!confirm("Delete this project metadata? Job runs stay in runs/.")) return;
        await api(`/api/projects/${id}/delete`, { method: "POST" });
        selectedProjectId = null;
        await loadProjects();
      });
      $("project-tab-content").addEventListener("click", async (event) => {
        const target = event.target;
        if (!target.dataset) return;
        if (target.dataset.projectJobId) {
          selectedJobId = target.dataset.projectJobId;
          activeTab = "summary";
          await loadJobs();
          return;
        }
        if (target.dataset.projectSelectVersion) {
          await api(`/api/projects/${id}/selected`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ version_id: target.dataset.projectSelectVersion }),
          });
          await loadProjects();
          return;
        }
        if (target.dataset.projectVariationVersion) {
          projectVariationParentId = target.dataset.projectVariationVersion;
          activeProjectTab = "variation";
          await renderProjectDetail(project.project_id);
          return;
        }
        if (target.dataset.projectEditVersion) {
          projectEditParentId = target.dataset.projectEditVersion;
          activeProjectTab = "edit";
          await renderProjectDetail(project.project_id);
          return;
        }
        if (target.dataset.projectEvaluateVersion) {
          await api(`/api/projects/${id}/versions/${encodeURIComponent(target.dataset.projectEvaluateVersion)}/evaluate`, { method: "POST" });
          await loadProjects();
          return;
        }
        if (target.dataset.projectExportVersion) {
          await api(`/api/projects/${id}/final-export`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ version_id: target.dataset.projectExportVersion }),
          });
          activeProjectTab = "final-export";
          await loadProjects();
          return;
        }
        if (target.dataset.projectFinalVersion) {
          await api(`/api/projects/${id}/final`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ version_id: target.dataset.projectFinalVersion }),
          });
          await loadProjects();
        }
      });
    }

    async function renderProjectTab(project, versions) {
      const target = $("project-tab-content");
      if (activeProjectTab === "versions") {
        target.innerHTML = projectVersionsTable(project, versions);
      } else if (activeProjectTab === "variation") {
        target.innerHTML = projectVariationControls(project, versions);
        bindAction("project-create-variation", async () => {
          const parentId = $("project-variation-parent").value;
          await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parentId)}/variation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(projectVariationPayload()),
          });
          projectVariationParentId = null;
          activeProjectTab = "versions";
          await loadJobs();
          await loadProjects();
        });
      } else if (activeProjectTab === "edit") {
        await renderProjectEdit(project, versions, target);
      } else if (activeProjectTab === "candidates") {
        await renderProjectCandidates(project, versions, target);
      } else if (activeProjectTab === "quality-gate") {
        await renderProjectQualityGate(project, versions, target);
      } else if (activeProjectTab === "final-export") {
        await renderProjectFinalExport(project, versions, target);
      } else if (activeProjectTab === "compare") {
        target.innerHTML = projectCompareControls(versions);
        bindAction("project-compare", async () => {
          const left = $("project-diff-left").value;
          const right = $("project-diff-right").value;
          const compare = await api(`/api/projects/${encodeURIComponent(project.project_id)}/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`);
          $("project-diff-result").innerHTML = projectCompareResultHtml(compare);
        });
      } else if (activeProjectTab === "export") {
        try {
          const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/export`);
          target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
        } catch (err) {
          target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
        }
      } else if (activeProjectTab === "events") {
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/events`);
        target.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.events, null, 2))}</pre>`;
      }
    }

    function projectVersionsTable(project, versions) {
      const rows = versions.map((version) => `
        <tr>
          <td>${escapeHtml(version.version_id)}${project.selected_version_id === version.version_id ? " selected" : ""}${project.final_version_id === version.version_id ? " final" : ""}</td>
          <td>${escapeHtml(version.name || "-")}</td>
          <td><button class="secondary" data-project-job-id="${escapeHtml(version.job_id)}" type="button">${escapeHtml(version.job_id)}</button></td>
          <td><span class="status ${version.status}">${escapeHtml(version.status)}</span></td>
          <td>${escapeHtml(version.quality_score ?? "-")}</td>
          <td>${escapeHtml(version.parent_version_id || "-")}</td>
          <td>${escapeHtml(version.variant_type || "original")}</td>
          <td><span class="status ${version.quality_gate_status || "not_evaluated"}">${escapeHtml(version.quality_gate_status || "not_evaluated")}</span> ${escapeHtml(version.quality_gate_score ?? "")}</td>
          <td>${version.final_export_path ? "yes" : "-"}</td>
          <td>${escapeHtml(version.request.tempo_bpm || "-")}</td>
          <td>${escapeHtml(version.request.key || "-")}</td>
          <td>${version.has_midi ? "yes" : "-"}</td>
          <td>${version.has_audio ? "yes" : "-"}</td>
          <td>${version.has_stems ? "yes" : "-"}</td>
          <td>${version.has_stem_audio ? "yes" : "-"}</td>
          <td>${escapeHtml(version.note || "-")}</td>
          <td>
            <div class="actions">
              <button class="secondary" data-project-select-version="${escapeHtml(version.version_id)}" type="button">Set Selected</button>
              <button class="secondary" data-project-final-version="${escapeHtml(version.version_id)}" type="button">Set Final</button>
              <button class="secondary" data-project-variation-version="${escapeHtml(version.version_id)}" type="button">Create Variation</button>
              <button class="secondary" data-project-edit-version="${escapeHtml(version.version_id)}" type="button">Edit Version</button>
              <button class="secondary" data-project-evaluate-version="${escapeHtml(version.version_id)}" type="button">Evaluate Gate</button>
              <button class="secondary" data-project-export-version="${escapeHtml(version.version_id)}" type="button">Export Final</button>
            </div>
          </td>
        </tr>
      `).join("");
      return `
        <table>
          <thead><tr><th>Version</th><th>Name</th><th>Job</th><th>Status</th><th>Quality</th><th>Parent</th><th>Variant Type</th><th>Gate</th><th>Final Export</th><th>Tempo</th><th>Key</th><th>MIDI</th><th>WAV</th><th>Stems</th><th>Stem WAV</th><th>Note</th><th>Actions</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='17'>No versions yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function projectVariationControls(project, versions) {
      const parentId = projectVariationParentId || project.selected_version_id || project.final_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
      const parent = versions.find((version) => version.version_id === parentId) || versions[0] || null;
      const options = projectVersionOptions(versions, parentId);
      return `
        <div class="grid2">
          <label>Parent Version
            <select id="project-variation-parent">${options}</select>
          </label>
          <label>Variant Type
            <select id="project-variation-type">
              <option value="style_variation">style_variation</option>
              <option value="tempo_key_variation">tempo_key_variation</option>
              <option value="lyrics_variation">lyrics_variation</option>
              <option value="arrangement_variation">arrangement_variation</option>
              <option value="quality_repair">quality_repair</option>
              <option value="manual">manual</option>
            </select>
          </label>
        </div>
        <div class="grid2">
          <label>Name
            <input id="project-variation-name" value="Variation ${(versions.length || 0) + 1}">
          </label>
          <label>Change Summary
            <input id="project-variation-summary" placeholder="short change summary">
          </label>
        </div>
        <div class="grid2">
          <label>Generation Mode
            <select id="project-variation-generation-mode">
              <option value="">inherit</option>
              <option value="local">local</option>
              <option value="provider">provider</option>
            </select>
          </label>
          <label>Pipeline Mode
            <select id="project-variation-pipeline-mode">
              <option value="">inherit</option>
              <option value="single">single</option>
              <option value="multinode">multinode</option>
            </select>
          </label>
        </div>
        <div class="grid2">
          <label>Style Patch
            <textarea id="project-variation-style"></textarea>
          </label>
          <label>Theme Patch
            <textarea id="project-variation-theme"></textarea>
          </label>
        </div>
        <div class="grid2">
          <label>Tempo BPM
            <input id="project-variation-tempo" type="number" min="40" max="240">
          </label>
          <label>Key
            <input id="project-variation-key">
          </label>
        </div>
        <div class="grid2">
          <label>Duration Seconds
            <input id="project-variation-duration" type="number" min="30" max="600">
          </label>
          <label>Lyrics Patch
            <textarea id="project-variation-lyrics"></textarea>
          </label>
        </div>
        <div class="actions">
          <button id="project-create-variation" type="button" ${parent ? "" : "disabled"}>Create Variation</button>
          <span id="project-variation-message" class="message"></span>
        </div>
        <pre>${escapeHtml(JSON.stringify(parent ? parent.request : {}, null, 2))}</pre>
      `;
    }

    function projectVariationPayload() {
      const requestPatch = {};
      const textFields = [
        ["style", "project-variation-style"],
        ["theme", "project-variation-theme"],
        ["key", "project-variation-key"],
        ["lyrics", "project-variation-lyrics"],
      ];
      textFields.forEach(([field, id]) => {
        const value = $(id).value;
        if (value.trim()) requestPatch[field] = field === "lyrics" ? value : value.trim();
      });
      if ($("project-variation-tempo").value) requestPatch.tempo_bpm = Number($("project-variation-tempo").value);
      if ($("project-variation-duration").value) requestPatch.duration_seconds = Number($("project-variation-duration").value);
      const payload = {
        variant_type: $("project-variation-type").value,
        name: $("project-variation-name").value.trim(),
        change_summary: $("project-variation-summary").value.trim(),
        request_patch: requestPatch,
      };
      if ($("project-variation-generation-mode").value) payload.generation_mode = $("project-variation-generation-mode").value;
      if ($("project-variation-pipeline-mode").value) payload.pipeline_mode = $("project-variation-pipeline-mode").value;
      return payload;
    }

    async function renderProjectEdit(project, versions, target) {
      const parentId = projectEditParentId || project.selected_version_id || project.final_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
      let targets = { sections: [], tracks: [], supported_edit_types: [] };
      let preview = "";
      if (parentId) {
        try {
          targets = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parentId)}/edit-targets`);
          preview = JSON.stringify(targets, null, 2);
        } catch (err) {
          preview = err.message;
        }
      }
      target.innerHTML = projectEditControls(project, versions, parentId, targets, preview);
      const parentSelect = $("project-edit-parent");
      if (parentSelect) {
        parentSelect.addEventListener("change", async () => {
          projectEditParentId = parentSelect.value;
          await renderProjectEdit(project, versions, target);
        });
      }
      bindAction("project-create-edit", async () => {
        const parent = $("project-edit-parent").value;
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(projectEditPayload()),
        });
        projectEditParentId = null;
        activeProjectTab = "versions";
        await loadJobs();
        await loadProjects();
      });
      bindAction("project-provider-preview", async () => {
        const parent = $("project-edit-parent").value;
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit-preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(projectProviderPreviewPayload()),
        });
        providerEditPreview = data.preview;
        $("project-provider-preview-result").innerHTML = providerPreviewHtml(data.preview, data.patch);
      });
      bindAction("project-provider-apply-preview", async () => {
        if (!providerEditPreview) return;
        const parent = $("project-edit-parent").value;
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(parent)}/edit-preview/${encodeURIComponent(providerEditPreview.preview_id)}/apply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: $("project-edit-name").value.trim(),
            change_summary: $("project-edit-summary").value.trim(),
          }),
        });
        providerEditPreview = null;
        activeProjectTab = "versions";
        await loadJobs();
        await loadProjects();
      });
      bindAction("project-apply-preset", async () => {
        applyEditPresetToForm();
      });
      bindAction("project-save-edit-preset", async () => {
        const presetId = slugifyClient($("project-edit-preset-id").value || $("project-edit-name").value || "custom-edit");
        await api("/api/edit-presets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(projectEditPresetPayload(presetId)),
        });
        await loadEditPresets();
        await renderProjectEdit(project, versions, target);
      });
    }

    function projectEditControls(project, versions, parentId, targets, preview) {
      const sectionOptions = (targets.sections || []).map((section) => `<option value="${escapeHtml(section.name)}">${escapeHtml(section.name)} · ${escapeHtml(section.bars)} bars</option>`).join("");
      const trackOptions = (targets.tracks || []).map((track) => `<option value="${escapeHtml(track.name)}">${escapeHtml(track.name)} · ${escapeHtml(track.instrument)} · ${escapeHtml(track.note_count)} notes</option>`).join("");
      const editTypeOptions = (targets.supported_edit_types || ["section_energy", "section_harmony", "track_density", "lyrics_rewrite", "melody_variation", "arrangement_variation"]).map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`).join("");
      const presetOptions = editPresets.map((preset) => `<option value="${escapeHtml(preset.preset_id)}">${escapeHtml(preset.name)}${preset.built_in ? " · built-in" : ""}</option>`).join("");
      return `
        <div class="grid2">
          <label>Edit Preset
            <select id="project-edit-preset"><option value="">none</option>${presetOptions}</select>
          </label>
          <label>Preset ID
            <input id="project-edit-preset-id" placeholder="custom-edit-preset">
          </label>
        </div>
        <div class="actions">
          <button class="secondary" id="project-apply-preset" type="button">Apply Preset</button>
          <button class="secondary" id="project-save-edit-preset" type="button">Save Current As Preset</button>
          <span id="project-preset-message" class="message"></span>
        </div>
        <div class="grid2">
          <label>Parent Version
            <select id="project-edit-parent">${projectVersionOptions(versions, parentId)}</select>
          </label>
          <label>Edit Type
            <select id="project-edit-type">${editTypeOptions}</select>
          </label>
        </div>
        <div class="grid2">
          <label>Section
            <select id="project-edit-section"><option value="">none</option>${sectionOptions}</select>
          </label>
          <label>Track
            <select id="project-edit-track"><option value="">none</option>${trackOptions}</select>
          </label>
        </div>
        <div class="grid2">
          <label>Field
            <select id="project-edit-field">
              <option value="">none</option>
              <option value="lyrics">lyrics</option>
              <option value="chords">chords</option>
              <option value="notes">notes</option>
              <option value="instrument">instrument</option>
            </select>
          </label>
          <label>Strength
            <input id="project-edit-strength" type="number" min="1" max="10" value="6">
          </label>
        </div>
        <div class="grid2">
          <label>Name
            <input id="project-edit-name" value="Edit ${(versions.length || 0) + 1}">
          </label>
          <label>Change Summary
            <input id="project-edit-summary" placeholder="short edit summary">
          </label>
        </div>
        <label>Instruction
          <textarea id="project-edit-instruction" placeholder="Make the chorus more energetic while keeping tempo and key."></textarea>
        </label>
        <div class="grid2">
          <label>Payload Lyrics
            <textarea id="project-edit-lyrics" placeholder="lyrics_rewrite text"></textarea>
          </label>
          <label>Payload Chords
            <input id="project-edit-chords" placeholder="Cmaj7, Am7, Fmaj7, G7">
          </label>
        </div>
        <div class="grid2">
          <label>Payload Instrument
            <input id="project-edit-instrument" placeholder="alternate instrument">
          </label>
          <label>Provider Mode
            <select id="project-edit-provider-mode">
              <option value="local">local</option>
              <option value="provider">provider</option>
            </select>
          </label>
        </div>
        <div class="actions">
          ${["tempo", "key", "structure", "lyrics", "harmony", "melody", "arrangement"].map((item) => `<label><input class="project-edit-preserve" type="checkbox" value="${item}" ${["tempo", "key", "structure"].includes(item) ? "checked" : ""}> ${item}</label>`).join("")}
        </div>
        <div class="actions">
          <button id="project-create-edit" type="button" ${parentId ? "" : "disabled"}>Create Edit Version</button>
          <button class="secondary" id="project-provider-preview" type="button" ${parentId ? "" : "disabled"}>Generate Preview</button>
          <button class="secondary" id="project-provider-apply-preview" type="button">Apply Preview</button>
          <span id="project-edit-message" class="message"></span>
        </div>
        <div id="project-provider-preview-result"><div class="empty">Provider edit preview will appear here.</div></div>
        <pre>${escapeHtml(preview || "{}")}</pre>
      `;
    }

    function projectEditPayload() {
      const target = {};
      if ($("project-edit-section").value) target.section_name = $("project-edit-section").value;
      if ($("project-edit-track").value) target.track_name = $("project-edit-track").value;
      if ($("project-edit-field").value) target.field = $("project-edit-field").value;
      const payload = {};
      if ($("project-edit-lyrics").value.trim()) payload.lyrics = $("project-edit-lyrics").value;
      if ($("project-edit-chords").value.trim()) payload.chords = $("project-edit-chords").value.split(",").map((item) => item.trim()).filter(Boolean);
      if ($("project-edit-instrument").value.trim()) payload.instrument = $("project-edit-instrument").value.trim();
      const presetId = $("project-edit-preset") ? $("project-edit-preset").value : "";
      const data = {
        edit_type: $("project-edit-type").value,
        target,
        instruction: $("project-edit-instruction").value.trim(),
        preserve: Array.from(document.querySelectorAll(".project-edit-preserve:checked")).map((item) => item.value),
        strength: Number($("project-edit-strength").value || 5),
        provider_mode: $("project-edit-provider-mode").value,
        payload,
        name: $("project-edit-name").value.trim(),
        change_summary: $("project-edit-summary").value.trim(),
      };
      if (presetId) data.preset_id = presetId;
      return data;
    }

    function projectProviderPreviewPayload() {
      return {
        provider_mode: "provider",
        instruction: $("project-edit-instruction").value.trim(),
        template_id: "provider-edit-intent",
      };
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
      return {
        instruction: $("project-candidate-instruction").value.trim(),
        candidate_count: Number($("project-candidate-count").value || 3),
        template_id: $("project-candidate-template").value.trim() || "provider-edit-candidates",
      };
    }

    function projectCandidateABPayload() {
      return {
        instruction: $("project-candidate-instruction").value.trim(),
        candidate_count: Number($("project-candidate-count").value || 2),
        template_ids: [
          $("project-candidate-template-a").value.trim() || "provider-edit-candidates",
          $("project-candidate-template-b").value.trim() || "provider-edit-candidates",
        ],
      };
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

    function projectPromptABHtml(experiments) {
      if (!experiments || !experiments.length) return `<div class="empty">Prompt A/B experiments will appear here.</div>`;
      return `
        <table>
          <thead><tr><th>A/B</th><th>Templates</th><th>Groups</th><th>Status</th></tr></thead>
          <tbody>
            ${experiments.map((experiment) => `
              <tr>
                <td>${escapeHtml(experiment.ab_id)}</td>
                <td>${escapeHtml((experiment.template_ids || []).join(" / "))}</td>
                <td>${escapeHtml((experiment.group_ids || []).join(", "))}</td>
                <td>${escapeHtml(experiment.status || "-")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
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
          </div>
          ${candidate.audio_url ? `<audio class="audio-player" controls src="${escapeHtml(candidate.audio_url)}"></audio>` : ""}
          ${candidate.audio_error ? `<div class="empty error">${escapeHtml(candidate.audio_error)}</div>` : ""}
          <pre>${escapeHtml(JSON.stringify({ patch: candidate.patch, scores }, null, 2))}</pre>
        </div>
      `;
    }

    function applyEditPresetToForm() {
      const preset = editPresets.find((item) => item.preset_id === $("project-edit-preset").value);
      if (!preset) return;
      $("project-edit-type").value = preset.edit_type;
      $("project-edit-strength").value = Math.max(1, Math.min(10, Math.round(Number(preset.strength || 0.5) * 10)));
      $("project-edit-instruction").value = preset.description || "";
      if (preset.target_defaults) {
        if (preset.target_defaults.field) $("project-edit-field").value = preset.target_defaults.field;
        const sectionName = resolveOptionByRole("project-edit-section", preset.target_defaults.section_role, preset.target_defaults.section_index);
        if (preset.target_defaults.section_name || sectionName) $("project-edit-section").value = preset.target_defaults.section_name || sectionName;
        const trackName = resolveOptionByRole("project-edit-track", preset.target_defaults.track_role, 0);
        if (preset.target_defaults.track_name || trackName) $("project-edit-track").value = preset.target_defaults.track_name || trackName;
      }
      if (preset.payload) {
        $("project-edit-lyrics").value = preset.payload.lyrics || "";
        $("project-edit-chords").value = Array.isArray(preset.payload.chords) ? preset.payload.chords.join(", ") : "";
        $("project-edit-instrument").value = preset.payload.instrument || "";
      }
      document.querySelectorAll(".project-edit-preserve").forEach((checkbox) => {
        checkbox.checked = (preset.preserve || []).includes(checkbox.value);
      });
      $("project-preset-message").textContent = preset.name;
    }

    function projectEditPresetPayload(presetId) {
      const payload = projectEditPayload();
      return {
        preset_id: presetId,
        name: $("project-edit-name").value.trim() || presetId,
        description: $("project-edit-instruction").value.trim(),
        edit_type: payload.edit_type,
        strength: Math.max(0, Math.min(1, Number(payload.strength || 5) / 10)),
        target_defaults: payload.target,
        payload: payload.payload,
        preserve: payload.preserve,
        tags: ["studio"],
      };
    }

    function resolveOptionByRole(selectId, role, index) {
      if (!role) return "";
      const options = Array.from($(selectId).options).filter((option) => option.value && option.value.toLowerCase().includes(String(role).toLowerCase()));
      if (!options.length) return "";
      const targetIndex = Number(index || 0);
      return (options[targetIndex < 0 ? options.length - 1 : Math.min(targetIndex, options.length - 1)] || options[0]).value;
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

    async function renderProjectFinalExport(project, versions, target) {
      let manifest = null;
      let message = "No final export yet.";
      try {
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/final-export`);
        manifest = data.final_export;
      } catch (err) {
        message = err.message;
      }
      const selectedId = project.final_version_id || project.selected_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
      const selected = versions.find((version) => version.version_id === selectedId) || versions[0] || {};
      target.innerHTML = `
        <div class="summary-grid">
          ${metric("Final", project.final_version_id || "-")}
          ${metric("Gate", selected.quality_gate_status || "not_evaluated")}
          ${metric("MIDI", selected.has_midi ? "yes" : "-")}
          ${metric("WAV", selected.has_audio ? "yes" : "-")}
        </div>
        <div class="summary-grid">
          ${metric("Stems", selected.has_stems ? "yes" : "-")}
          ${metric("Stem WAV", selected.has_stem_audio ? "yes" : "-")}
          ${metric("Quality", selected.quality_score ?? "-")}
          ${metric("Final Export", selected.final_export_path || "-")}
        </div>
        <div class="grid2">
          <label>Version
            <select id="project-final-export-version">${projectVersionOptions(versions, selectedId)}</select>
          </label>
          <label>Force Gate Override
            <select id="project-final-export-force">
              <option value="false">false</option>
              <option value="true">true</option>
            </select>
          </label>
        </div>
        <div class="actions">
          <label><input id="project-final-export-audio" type="checkbox" checked> Include Audio</label>
          <label><input id="project-final-export-stems" type="checkbox" checked> Include Stems</label>
          <label><input id="project-final-export-stem-audio" type="checkbox" checked> Include Stem Audio</label>
        </div>
        <div class="actions">
          <button id="project-generate-final-export" type="button" ${versions.length ? "" : "disabled"}>Generate Final Export</button>
          <button class="secondary" id="project-build-final-export-zip" type="button" ${manifest ? "" : "disabled"}>Build ZIP</button>
          <button class="secondary" id="project-refresh-final-export" type="button">Refresh</button>
          <a class="button-link secondary" href="/api/projects/${encodeURIComponent(project.project_id)}/export">Export JSON</a>
          ${manifest && manifest.zip ? `<a class="button-link secondary" href="/api/projects/${encodeURIComponent(project.project_id)}/final-export.zip">Download ZIP</a>` : ""}
          <span id="project-final-export-message" class="message"></span>
        </div>
        ${manifest ? finalExportManifestHtml(manifest) : `<div class="empty">${escapeHtml(message)}</div>`}
      `;
      bindAction("project-generate-final-export", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/final-export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(projectFinalExportPayload()),
        });
        await loadProjects();
      });
      bindAction("project-refresh-final-export", async () => {
        await renderProjectFinalExport(project, versions, target);
      });
      bindAction("project-build-final-export-zip", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/final-export/zip`, { method: "POST" });
        await renderProjectFinalExport(project, versions, target);
      });
    }

    function projectFinalExportPayload() {
      return {
        version_id: $("project-final-export-version").value,
        include_audio: $("project-final-export-audio").checked,
        include_stems: $("project-final-export-stems").checked,
        include_stem_audio: $("project-final-export-stem-audio").checked,
        force: $("project-final-export-force").value === "true",
      };
    }

    function finalExportManifestHtml(manifest) {
      const rows = (manifest.files || []).map((file) => `
        <tr>
          <td>${escapeHtml(file.kind)}</td>
          <td>${escapeHtml(file.path)}</td>
          <td>${file.exists ? "yes" : "-"}</td>
          <td>${escapeHtml(file.skipped || file.size_bytes || "-")}</td>
        </tr>
      `).join("");
      return `
        <div class="summary-grid">
          ${metric("Export Version", manifest.version_id || "-")}
          ${metric("Job", manifest.job_id || "-")}
          ${metric("Gate", (manifest.quality_gate || {}).status || "-")}
          ${metric("Generated", manifest.generated_at || "-")}
        </div>
        ${manifest.zip ? `<div class="summary-grid">
          ${metric("ZIP", manifest.zip.filename || "final-export.zip")}
          ${metric("ZIP Size", manifest.zip.size_bytes || 0)}
          ${metric("ZIP Entries", manifest.zip.entry_count || 0)}
          ${metric("ZIP SHA", (manifest.zip.sha256 || "").slice(0, 12))}
        </div>` : ""}
        <table>
          <thead><tr><th>Kind</th><th>Path</th><th>Exists</th><th>Info</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='4'>No files.</td></tr>"}</tbody>
        </table>
      `;
    }

    function projectCompareControls(versions) {
      const options = versions.map((version) => `<option value="${escapeHtml(version.version_id)}">${escapeHtml(version.version_id)} · ${escapeHtml(version.name || version.job_id)}</option>`).join("");
      return `
        <div class="grid2">
          <label>Left
            <select id="project-diff-left">${options}</select>
          </label>
          <label>Right
            <select id="project-diff-right">${options}</select>
          </label>
        </div>
        <div class="actions"><button id="project-compare" type="button">Compare</button></div>
        <div id="project-diff-result"><div class="empty">Choose two versions to compare.</div></div>
      `;
    }

    function projectCompareResultHtml(compare) {
      const sectionRows = (compare.sections || []).map((row) => `
        <tr>
          <td>${escapeHtml(row.section)}</td>
          <td>${escapeHtml(row.changed ? "changed" : "-")}</td>
          <td class="wrap-cell">${escapeHtml(JSON.stringify(row.left || {}))}</td>
          <td class="wrap-cell">${escapeHtml(JSON.stringify(row.right || {}))}</td>
        </tr>
      `).join("");
      const trackRows = (compare.tracks || []).map((row) => `
        <tr>
          <td>${escapeHtml(row.track)}</td>
          <td>${escapeHtml(row.changed ? "changed" : "-")}</td>
          <td class="wrap-cell">${escapeHtml(JSON.stringify(row.left || {}))}</td>
          <td class="wrap-cell">${escapeHtml(JSON.stringify(row.right || {}))}</td>
        </tr>
      `).join("");
      return `
        <div class="summary-grid">
          ${metric("Recommendation", compare.summary.recommendation || "-")}
          ${metric("Quality Delta", compare.summary.quality_delta ?? "-")}
          ${metric("Section Changes", compare.summary.section_changes || 0)}
          ${metric("Track Changes", compare.summary.track_changes || 0)}
        </div>
        <div class="compare-grid">
          ${projectCompareSideHtml("Left", compare.left, (compare.artifacts || {}).left)}
          ${projectCompareSideHtml("Right", compare.right, (compare.artifacts || {}).right)}
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Section</th><th>Changed</th><th>Left</th><th>Right</th></tr></thead>
            <tbody>${sectionRows || "<tr><td colspan='4'>No section data.</td></tr>"}</tbody>
          </table>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Track</th><th>Changed</th><th>Left</th><th>Right</th></tr></thead>
            <tbody>${trackRows || "<tr><td colspan='4'>No track data.</td></tr>"}</tbody>
          </table>
        </div>
      `;
    }

    function projectCompareSideHtml(label, version, artifacts) {
      if (!version) return `<div class="empty">${escapeHtml(label)}</div>`;
      return `
        <div>
          <div class="panel-title" style="padding:0 0 8px;border-bottom:0;">${escapeHtml(label)} ${escapeHtml(version.version_id)}</div>
          <div class="summary-grid">
            ${metric("Quality", (version.quality || {}).overall ?? "-")}
            ${metric("Gate", (version.gate || {}).status || "-")}
            ${metric("Variant", version.variant_type || "-")}
            ${metric("Preset", ((version.edit || {}).preset || {}).name || "-")}
          </div>
          <div class="actions">
            ${artifacts && artifacts.midi ? `<a class="button-link secondary" href="${escapeHtml(artifacts.midi)}">MIDI</a>` : ""}
            ${artifacts && artifacts.audio ? `<a class="button-link secondary" href="${escapeHtml(artifacts.audio)}">WAV</a>` : `<span class="message">WAV not rendered</span>`}
          </div>
          ${artifacts && artifacts.audio ? `<audio class="audio-player" controls src="${escapeHtml(artifacts.audio)}"></audio>` : ""}
        </div>
      `;
    }

    function projectVersionOptions(versions, selectedId) {
      return versions.map((version) => `
        <option value="${escapeHtml(version.version_id)}" ${version.version_id === selectedId ? "selected" : ""}>${escapeHtml(version.version_id)} · ${escapeHtml(version.name || version.job_id)}</option>
      `).join("");
    }

    function projectTabLabel(tab) {
      return {
        versions: "Versions",
        variation: "Variation",
        edit: "Edit",
        candidates: "Candidates",
        "quality-gate": "Quality Gate",
        "final-export": "Final Export",
        compare: "Compare",
        export: "Export JSON",
        events: "Events",
      }[tab] || tab;
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

    async function renderDetail(jobId) {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      const detail = $("detail");
      const summary = job.summary || {};
      const tabs = ["summary", "edit", "nodes", "timeline", "tracks", "stems", "quality", "validator", "json", "logs", "artifacts"];
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
        <div class="summary-grid">
          ${metric("Attempt", job.attempt_count ?? 0)}
          ${metric("Retry Count", job.retry_count ?? 0)}
          ${metric("Heartbeat", job.heartbeat_at || "-")}
          ${metric("Stalled", job.stalled ? "yes" : "no")}
        </div>
        <div class="summary-grid">
          ${metric("Generation Mode", job.generation_mode || (job.provider_snapshot || {}).mode || "-")}
          ${metric("Pipeline Mode", job.pipeline_mode || "single")}
          ${metric("Step", job.step || "-")}
          ${metric("Updated", job.updated_at || "-")}
        </div>
        ${providerSnapshotHtml(job.provider_snapshot || {})}
        <div class="actions">
          ${actionButtons(job)}
          <span>${escapeHtml(job.output_dir)}</span>
        </div>
        ${audioControls(job)}
        ${job.error ? `<p class="error">${escapeHtml(job.error)}</p>` : ""}
        <div class="tabs">
          ${tabs.map(tab => `<button type="button" class="${activeTab === tab ? "active" : ""}" data-tab="${tab}">${tabLabel(tab)}</button>`).join("")}
        </div>
        <div id="tab-content"></div>
      `;
      detail.querySelectorAll("[data-tab]").forEach((button) => {
        button.addEventListener("click", async () => {
          activeTab = button.dataset.tab;
          await renderDetail(job.job_id);
        });
      });
      wireJobActions(job);
      await renderTab(job);
    }

    async function renderTab(job) {
      const target = $("tab-content");
      if (activeTab === "summary") {
        target.innerHTML = `<pre>${escapeHtml(JSON.stringify(job, null, 2))}</pre>`;
      } else if (activeTab === "edit") {
        await renderEdit(job, target);
      } else if (activeTab === "timeline") {
        await renderTimeline(job, target);
      } else if (activeTab === "nodes") {
        await renderNodes(job, target);
      } else if (activeTab === "tracks") {
        await renderTracks(job, target);
      } else if (activeTab === "stems") {
        await renderStems(job, target);
      } else if (activeTab === "quality") {
        await renderQuality(job, target);
      } else if (activeTab === "validator") {
        await renderValidator(job, target);
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

    async function renderTimeline(job, target) {
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/timeline`);
        const view = data.view;
        const rows = view.sections.map((section) => `
          <tr>
            <td>${escapeHtml(section.name)}</td>
            <td>${escapeHtml(section.start_bar)}-${escapeHtml(section.end_bar)} (${escapeHtml(section.bars)})</td>
            <td>${escapeHtml(section.estimated_start_seconds)}s</td>
            <td>${escapeHtml(section.estimated_end_seconds)}s</td>
            <td>${escapeHtml(section.chords.join(" · "))}</td>
            <td>${escapeHtml(section.role || "-")}</td>
            <td>${escapeHtml(section.energy ?? 0)}</td>
            <td>${escapeHtml(section.tension ?? 0)}</td>
            <td>${escapeHtml(section.density ?? 0)}</td>
            <td>${section.hook ? "yes" : "-"}</td>
          </tr>
        `).join("");
        target.innerHTML = `
          ${runtimeHeader(view)}
          ${warnings(view.warnings)}
          <table>
            <thead><tr><th>Section</th><th>Bars</th><th>Start</th><th>End</th><th>Chords</th><th>Role</th><th>Energy</th><th>Tension</th><th>Density</th><th>Hook</th></tr></thead>
            <tbody>${rows || "<tr><td colspan='10'>No sections.</td></tr>"}</tbody>
          </table>
        `;
      } catch (err) {
        target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
      }
    }

    async function renderEdit(job, target) {
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/edit`);
        const edit = data.edit || {};
        const targetData = edit.target || {};
        target.innerHTML = `
          <div class="summary-grid">
            ${metric("Edit Type", edit.edit_type || "-")}
            ${metric("Parent Version", edit.parent_version_id || "-")}
            ${metric("Parent Job", edit.parent_job_id || "-")}
            ${metric("Strength", edit.strength ?? "-")}
          </div>
          <div class="summary-grid">
            ${metric("Section", targetData.section_name || "-")}
            ${metric("Track", targetData.track_name || "-")}
            ${metric("Field", targetData.field || "-")}
            ${metric("Provider Mode", edit.provider_mode || "-")}
          </div>
          <p>${escapeHtml(edit.instruction || "")}</p>
          <pre>${escapeHtml(JSON.stringify(edit, null, 2))}</pre>
        `;
      } catch (err) {
        target.innerHTML = `<div class="empty">No edit metadata for this job.</div>`;
      }
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

    async function renderTracks(job, target) {
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/tracks`);
        const view = data.view;
        const rows = view.tracks.map((track) => `
          <tr>
            <td>${escapeHtml(track.name)}</td>
            <td>${escapeHtml(track.instrument)}</td>
            <td>${escapeHtml(track.note_count)}</td>
            <td>${escapeHtml(pitchRange(track))}</td>
            <td>${escapeHtml(track.end_beat_max ?? "-")}</td>
            <td>${escapeHtml(track.average_velocity ?? "-")}</td>
          </tr>
        `).join("");
        target.innerHTML = `
          <div class="summary-grid">
            ${metric("Tracks", view.track_count)}
            ${metric("Notes", view.note_count)}
            ${metric("Total Bars", view.total_bars)}
            ${metric("Density", view.tracks.length ? (view.tracks[0].density_notes_per_bar ?? "-") : "-")}
          </div>
          <table>
            <thead><tr><th>Track</th><th>Instrument</th><th>Notes</th><th>Pitch Range</th><th>End Beat</th><th>Avg Velocity</th></tr></thead>
            <tbody>${rows || "<tr><td colspan='6'>No tracks.</td></tr>"}</tbody>
          </table>
        `;
      } catch (err) {
        target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
      }
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

    async function renderStems(job, target) {
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/stems`);
        const manifest = data.manifest || {};
        const stems = manifest.stems || [];
        const rows = stems.map((stem) => `
          <tr data-stem-id="${escapeHtml(stem.stem_id)}">
            <td>${escapeHtml(stem.stem_id)}</td>
            <td>${escapeHtml(stem.role || "-")}</td>
            <td>${escapeHtml(stem.instrument || "-")}</td>
            <td>${escapeHtml(stem.note_count ?? 0)}</td>
            <td>${escapeHtml(stem.duration_beats ?? 0)}</td>
            <td>${stem.midi_exists ? `<a href="/api/jobs/${encodeURIComponent(job.job_id)}/stems/${encodeURIComponent(stem.stem_id)}/midi">Download MIDI</a>` : "-"}</td>
            <td><span class="status ${stem.audio_status || "not_started"}">${escapeHtml(stem.audio_status || "not_started")}</span></td>
            <td>${escapeHtml(stem.audio_error || "-")}</td>
            <td>
              <div class="actions">
                <button class="secondary render-stem-audio" data-stem-id="${escapeHtml(stem.stem_id)}" type="button">Render Audio</button>
                ${stem.audio_exists ? `<a class="button-link secondary" href="/api/jobs/${encodeURIComponent(job.job_id)}/stems/${encodeURIComponent(stem.stem_id)}/audio">Download WAV</a>` : ""}
                <button class="secondary stem-solo" data-stem-id="${escapeHtml(stem.stem_id)}" type="button">Solo</button>
                <button class="secondary stem-mute" data-stem-id="${escapeHtml(stem.stem_id)}" type="button">Mute</button>
              </div>
              ${stem.audio_exists ? `<audio class="audio-player stem-audio" data-stem-id="${escapeHtml(stem.stem_id)}" controls src="/api/jobs/${encodeURIComponent(job.job_id)}/stems/${encodeURIComponent(stem.stem_id)}/audio"></audio>` : ""}
            </td>
          </tr>
        `).join("");
        target.innerHTML = `
          <div class="actions">
            <button id="render-stems" type="button">Render Stems</button>
            <button class="secondary" id="render-stem-audio" type="button">Render Stem Audio</button>
            <button class="secondary" id="refresh-stems" type="button">Refresh</button>
          </div>
          ${stems.length && data.status === "not_started" ? `<div class="empty">Stems have not been rendered yet.</div>` : ""}
          <table>
            <thead><tr><th>Stem</th><th>Role</th><th>Instrument</th><th>Notes</th><th>Duration</th><th>MIDI</th><th>WAV</th><th>Error</th><th>Actions</th></tr></thead>
            <tbody>${rows || "<tr><td colspan='9'>Stems have not been rendered yet.</td></tr>"}</tbody>
          </table>
        `;
        bindAction("render-stems", async () => {
          await api(`/api/jobs/${encodeURIComponent(job.job_id)}/render-stems`, { method: "POST" });
          await renderStems(job, target);
        });
        bindAction("render-stem-audio", async () => {
          await api(`/api/jobs/${encodeURIComponent(job.job_id)}/render-stem-audio`, { method: "POST" });
          await renderStems(job, target);
        });
        bindAction("refresh-stems", async () => {
          await renderStems(job, target);
        });
        target.querySelectorAll(".render-stem-audio").forEach((button) => {
          button.addEventListener("click", async () => {
            await api(`/api/jobs/${encodeURIComponent(job.job_id)}/render-stem-audio`, {
              method: "POST",
              body: JSON.stringify({ stem_ids: [button.dataset.stemId] }),
            });
            await renderStems(job, target);
          });
        });
        target.querySelectorAll(".stem-solo").forEach((button) => {
          button.addEventListener("click", () => soloStem(target, button.dataset.stemId));
        });
        target.querySelectorAll(".stem-mute").forEach((button) => {
          button.addEventListener("click", () => muteStem(target, button.dataset.stemId));
        });
      } catch (err) {
        if (String(err.message || "").includes("song-plan.json is not available")) {
          target.innerHTML = `<div class="empty">SongPlan is not available yet.</div>`;
          return;
        }
        target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
      }
    }

    async function renderValidator(job, target) {
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(job.job_id)}/validator`);
        const view = data.view;
        const rows = view.checks.map((check) => `
          <tr><td>${escapeHtml(check.name)}</td><td>${escapeHtml(check.status)}</td></tr>
        `).join("");
        target.innerHTML = `
          <div class="summary-grid">
            ${metric("Status", view.status)}
            ${metric("Passed", view.passed ? "yes" : "no")}
          ${metric("Checks", view.check_count)}
          ${metric("MIDI Size", view.midi.size)}
          ${metric("Audio Size", view.audio ? view.audio.size_bytes : 0)}
        </div>
          ${warnings(view.warnings)}
          <table>
            <thead><tr><th>Check</th><th>Status</th></tr></thead>
            <tbody>${rows || "<tr><td colspan='2'>No checks.</td></tr>"}</tbody>
          </table>
        `;
      } catch (err) {
        target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
      }
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

    function providerSnapshotHtml(snapshot) {
      if (!snapshot || !snapshot.mode) return "";
      return `
        <div class="summary-grid">
          ${metric("Generation Mode", snapshot.mode)}
          ${metric("Provider Model", snapshot.model || "-")}
          ${metric("Wire API", snapshot.wire_api || "-")}
          ${metric("API Key", snapshot.api_key_masked || (snapshot.api_key_set ? "set" : "-"))}
        </div>
      `;
    }

    function warnings(items) {
      if (!items || !items.length) return "";
      return `<p class="error">${escapeHtml(items.join(" "))}</p>`;
    }

    function pitchRange(track) {
      if (track.pitch_min == null || track.pitch_max == null) return "-";
      return `${track.pitch_min}-${track.pitch_max}`;
    }

    function tabLabel(tab) {
      const labels = {
        summary: "Summary",
        edit: "Edit",
        nodes: "Nodes",
        timeline: "Timeline",
        tracks: "Tracks",
        stems: "Stems",
        quality: "Quality",
        validator: "Validator",
        json: "SongPlan JSON",
        logs: "Logs",
        artifacts: "Artifacts",
      };
      return labels[tab] || tab;
    }

    function actionButtons(job) {
      const id = encodeURIComponent(job.job_id);
      const canDownload = job.artifacts && job.artifacts.midi;
      const buttons = [];
      if (canDownload) buttons.push(`<a class="button-link" href="/api/jobs/${id}/midi">Download MIDI</a>`);
      if (job.status === "completed" && canDownload) {
        buttons.push(`<button class="secondary" id="render-audio" type="button">Render Audio</button>`);
      }
      if (job.artifacts && job.artifacts.audio) {
        buttons.push(`<a class="button-link secondary" href="/api/jobs/${id}/audio">Download WAV</a>`);
      }
      buttons.push(`<button class="secondary" id="open-folder" type="button">Open Folder</button>`);
      if (job.status === "running" || job.status === "queued") {
        buttons.push(`<button class="danger" id="cancel-job" type="button">Cancel</button>`);
      }
      if (job.status === "failed" || job.status === "stalled" || job.status === "interrupted") {
        buttons.push(`<button class="secondary" id="retry-job" type="button">Retry</button>`);
      }
      if (job.hidden) {
        buttons.push(`<button class="secondary" id="unhide-job" type="button">Unhide</button>`);
      } else {
        buttons.push(`<button class="secondary" id="hide-job" type="button">Hide</button>`);
      }
      if (job.status !== "running") {
        buttons.push(`<button class="danger" id="delete-job" type="button">Delete</button>`);
      }
      return buttons.join("");
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

    function audioControls(job) {
      if (!job.artifacts || !job.artifacts.audio) return "";
      return `
        <audio class="audio-player" controls src="/api/jobs/${encodeURIComponent(job.job_id)}/audio"></audio>
      `;
    }

    function soloStem(target, stemId) {
      target.querySelectorAll(".stem-audio").forEach((audio) => {
        if (audio.dataset.stemId === stemId) {
          audio.muted = false;
          audio.play().catch(() => {});
        } else {
          audio.pause();
          audio.currentTime = 0;
        }
      });
    }

    function muteStem(target, stemId) {
      target.querySelectorAll(".stem-audio").forEach((audio) => {
        if (audio.dataset.stemId === stemId) {
          audio.pause();
          audio.muted = true;
        }
      });
    }

    function bindAction(id, fn) {
      const el = $(id);
      if (!el) return;
      el.addEventListener("click", async () => {
        try { await fn(); }
        catch (err) { alert(err.message); }
      });
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function slugifyClient(value) {
      return String(value || "custom-edit")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 64) || "custom-edit";
    }

    function debounce(fn, delay) {
      let timer = null;
      return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
      };
    }

    init().catch((err) => {
      document.body.innerHTML = `<pre>${escapeHtml(err.stack || err.message)}</pre>`;
    });
  </script>
</body>
</html>"""
