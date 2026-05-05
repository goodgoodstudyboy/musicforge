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
    .batch-layout {
      display: grid;
      grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .batch-list, .batch-detail {
      overflow: auto;
    }
    .batch-detail {
      margin-top: 14px;
    }
    .audio-player {
      width: 100%;
      margin: 8px 0 4px;
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
      await loadRenderer();
      await loadJobs();
      await loadBatches();
      setInterval(() => {
        loadJobs();
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
          <td>${escapeHtml(item.attempt_count)}</td>
          <td>${item.job_id ? `<button class="secondary batch-job-link" data-job-id="${escapeHtml(item.job_id)}" type="button">${escapeHtml(item.job_id)}</button>` : "-"}</td>
          <td>${escapeHtml(item.output_dir || "-")}</td>
          <td>${escapeHtml(item.audio_path || "-")}</td>
          <td>${escapeHtml(item.error || item.audio_error || "-")}</td>
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
          <thead><tr><th>Index</th><th>Title</th><th>Mode</th><th>Pipeline</th><th>Status</th><th>Audio</th><th>Attempt</th><th>Job</th><th>Output</th><th>WAV</th><th>Error</th><th>Updated</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='12'>No batch items.</td></tr>"}</tbody>
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
      const tabs = ["summary", "nodes", "timeline", "tracks", "validator", "json", "logs", "artifacts"];
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
      } else if (activeTab === "timeline") {
        await renderTimeline(job, target);
      } else if (activeTab === "nodes") {
        await renderNodes(job, target);
      } else if (activeTab === "tracks") {
        await renderTracks(job, target);
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
          </tr>
        `).join("");
        target.innerHTML = `
          ${runtimeHeader(view)}
          ${warnings(view.warnings)}
          <table>
            <thead><tr><th>Section</th><th>Bars</th><th>Start</th><th>End</th><th>Chords</th></tr></thead>
            <tbody>${rows || "<tr><td colspan='5'>No sections.</td></tr>"}</tbody>
          </table>
        `;
      } catch (err) {
        target.innerHTML = `<pre>${escapeHtml(err.message)}</pre>`;
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
        nodes: "Nodes",
        timeline: "Timeline",
        tracks: "Tracks",
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

    init().catch((err) => {
      document.body.innerHTML = `<pre>${escapeHtml(err.stack || err.message)}</pre>`;
    });
  </script>
</body>
</html>"""
