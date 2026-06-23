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
    .panel-title.subhead {
      margin-top: 12px;
      padding: 8px 0;
      border-bottom: 0;
      min-height: 0;
    }
    .waveform {
      display: flex;
      align-items: end;
      gap: 1px;
      min-height: 52px;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      overflow: hidden;
    }
    .waveform span {
      flex: 1 1 2px;
      min-width: 1px;
      background: var(--accent);
      border-radius: 2px 2px 0 0;
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
    .batch-layout, .project-layout, .release-layout {
      display: grid;
      grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .batch-list, .batch-detail, .project-list, .project-detail, .release-list, .release-detail {
      overflow: auto;
    }
    .batch-detail, .project-detail, .release-detail {
      margin-top: 14px;
    }
    .audio-player {
      width: 100%;
      margin: 8px 0 4px;
    }
    .asset-layout {
      display: grid;
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .asset-list {
      overflow: auto;
      max-height: 520px;
    }
    .asset-ref-list {
      display: grid;
      gap: 6px;
      max-height: 180px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      margin-top: 4px;
      background: #fbfcfe;
    }
    .asset-ref-row {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) 72px;
      gap: 8px;
      align-items: center;
      font-size: 12px;
    }
    .library-result {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      margin: 8px 0;
      background: #fbfcfe;
    }
    .library-result h4 {
      margin: 0 0 6px;
      font-size: 14px;
      letter-spacing: 0;
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
    .review-task-row {
      border-top: 1px solid var(--line);
      padding: 12px 0;
    }
    .review-task-row:first-child { border-top: 0; }
    .review-task-row h4 {
      margin: 0 0 8px;
      font-size: 14px;
      letter-spacing: 0;
    }
    .review-sprint-row {
      border-top: 1px solid var(--line);
      padding: 12px 0;
    }
    .review-sprint-row:first-child { border-top: 0; }
    .review-sprint-row h4 {
      margin: 0 0 8px;
      font-size: 14px;
      letter-spacing: 0;
    }
    .review-conflict-list {
      display: grid;
      gap: 6px;
      margin: 10px 0;
    }
    .review-conflict {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      background: #fbfcfe;
    }
    .review-conflict.blocking {
      border-color: #fecdca;
      background: #fef3f2;
    }
    .review-candidate-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: white;
      min-width: 0;
    }
    .review-candidate-card .summary-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .review-candidate-card h5 {
      margin: 0 0 8px;
      font-size: 14px;
      letter-spacing: 0;
    }
    .review-candidate-source {
      display: inline-block;
      margin-left: 6px;
      padding: 2px 6px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 11px;
      color: var(--muted);
      background: #f8fafc;
    }
    .review-candidate-source.provider {
      color: #064e3b;
      border-color: #a7f3d0;
      background: #ecfdf5;
    }
    .decision-report-panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #f8fafc;
      margin: 10px 0;
    }
    .decision-report-panel h5 {
      margin: 0 0 8px;
      font-size: 13px;
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
    .editor-workbench {
      display: grid;
      gap: 12px;
    }
    .editor-arranger, .editor-piano-roll, .patch-queue {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 10px;
      overflow: auto;
    }
    .arranger-ruler, .track-lane {
      display: grid;
      grid-template-columns: 90px minmax(520px, 1fr);
      gap: 8px;
      align-items: center;
      margin-bottom: 6px;
    }
    .bar-ruler, .section-row, .lane-notes {
      position: relative;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      overflow: hidden;
    }
    .bar-tick {
      position: absolute;
      top: 0;
      bottom: 0;
      border-left: 1px solid #eef2f7;
      color: var(--muted);
      font-size: 10px;
      padding-left: 2px;
    }
    .project-editor-section-block, .lane-note, .project-editor-note-rect {
      position: absolute;
      border: 1px solid #0f766e;
      background: #ccfbf1;
      color: #134e4a;
      border-radius: 6px;
      padding: 4px 6px;
      min-width: 26px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      cursor: pointer;
      font-size: 12px;
      text-align: left;
    }
    .project-editor-section-block.selected, .project-editor-note-rect.selected {
      outline: 2px solid #101828;
      outline-offset: 1px;
    }
    .lane-note {
      height: 14px;
      top: 9px;
      padding: 0;
      background: #dbeafe;
      border-color: #2563eb;
    }
    .editor-split {
      display: grid;
      grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
      gap: 10px;
      align-items: start;
    }
    .track-list {
      display: grid;
      gap: 6px;
    }
    .track-list button {
      width: 100%;
      justify-content: flex-start;
      background: white;
      color: var(--ink);
      border-color: #c7cedb;
    }
    .track-list button.active {
      background: #e6fffb;
      border-color: var(--accent);
      color: var(--accent-dark);
    }
    .piano-grid {
      position: relative;
      min-width: 680px;
      min-height: 360px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: repeating-linear-gradient(to bottom, #ffffff 0, #ffffff 19px, #f8fafc 20px), repeating-linear-gradient(to right, transparent 0, transparent 39px, #eef2f7 40px);
      overflow: hidden;
    }
    .pitch-label {
      position: absolute;
      left: 0;
      width: 42px;
      height: 20px;
      padding: 2px 4px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.8);
      font-size: 10px;
    }
    .project-editor-note-rect {
      height: 18px;
      padding: 0 4px;
      background: #fde68a;
      border-color: #b45309;
      color: #78350f;
    }
    .project-editor-note-rect.derived {
      background: #f1f5f9;
      border-color: #94a3b8;
      color: #475569;
    }
    .patch-queue-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
      border-bottom: 1px solid var(--line);
      padding: 7px 0;
    }
    .patch-queue-row:last-child { border-bottom: 0; }
    .editor-inspector {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: white;
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
      .release-layout { grid-template-columns: 1fr; }
      .asset-layout { grid-template-columns: 1fr; }
      .compare-grid { grid-template-columns: 1fr; }
      .candidate-grid { grid-template-columns: 1fr; }
      .editor-split { grid-template-columns: 1fr; }
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
          <span>System Health</span>
          <span id="ga-status" class="status">unknown</span>
        </div>
        <div class="panel-body">
          <div id="ga-summary" class="summary-grid">
            <div class="metric"><span>GA</span>unknown</div>
            <div class="metric"><span>Doctor</span>unknown</div>
            <div class="metric"><span>Manual Review</span>unknown</div>
            <div class="metric"><span>Final Readiness</span>unknown</div>
          </div>
          <div class="actions">
            <button class="secondary" id="ga-check-run" type="button">Run GA Check</button>
            <button class="secondary" id="ga-docs-index" type="button">Docs Index</button>
          </div>
          <pre id="ga-check-result">No GA check has been run in this session.</pre>
        </div>
      </section>
      <section id="maintenance-panel">
        <div class="panel-title">
          <span>Maintenance</span>
          <span id="maintenance-status" class="status">unknown</span>
        </div>
        <div class="panel-body">
          <div id="maintenance-summary" class="summary-grid">
            <div class="metric"><span>LTS</span>unknown</div>
            <div class="metric"><span>Backup</span>unknown</div>
            <div class="metric"><span>Migration</span>unknown</div>
            <div class="metric"><span>Check</span>unknown</div>
          </div>
          <div class="actions">
            <button class="secondary" id="maintenance-refresh" type="button">Refresh Status</button>
            <button class="secondary" id="maintenance-create-backup" type="button">Create Backup</button>
            <button class="secondary" id="maintenance-run-preflight" type="button">Run Preflight</button>
            <button class="secondary" id="maintenance-run-weekly" type="button">Run Weekly</button>
          </div>
          <div class="actions">
            <button class="secondary" id="maintenance-run-migration" type="button">Run Migration</button>
            <button class="secondary" id="maintenance-backup-list" type="button">List Backups</button>
          </div>
          <pre id="maintenance-result">No maintenance check has been run in this session.</pre>
        </div>
      </section>
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
          <span>Editor Templates</span>
          <span id="editor-template-status" class="status">0 templates</span>
        </div>
        <div class="panel-body">
          <div class="actions">
            <button class="secondary" id="editor-template-refresh" type="button">Refresh Templates</button>
          </div>
          <div id="editor-template-list" class="table-wrap"><div class="empty">No editor templates saved yet.</div></div>
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
      <section id="audio-lab">
        <div class="panel-title">
          <span>Audio Lab</span>
          <span class="status">Real Audio Baseline</span>
        </div>
        <div class="panel-body">
          <div class="grid3">
            <div>${metric("Renderer Profile", "local")}</div>
            <div>${metric("WAV Health", "available")}</div>
            <div>${metric("Manual Audio Review", "required when gated")}</div>
          </div>
          <div class="actions">
            <button class="secondary" id="audio-health-run" type="button">Run Audio Health</button>
            <button class="secondary" id="release-refresh-audio-qa" type="button">Refresh Release Audio QA</button>
          </div>
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
            <label>Asset References
              <div id="song-asset-refs" class="asset-ref-list"></div>
            </label>
            <label>Reference Materials
              <div id="song-reference-refs" class="reference-ref-list"></div>
            </label>
            <label>Context Pack
              <select id="song-context-pack"><option value="">none</option></select>
            </label>
            <div class="actions">
              <button type="submit">Generate</button>
              <button class="secondary" id="song-suggest-context" type="button">Suggest Context</button>
              <button class="secondary" id="reset-form" type="button">Reset</button>
            </div>
            <div id="song-context-suggestion" class="message"></div>
          </form>
        </div>
      </section>
      <section>
        <div class="panel-title">
          <span>Library</span>
          <button class="secondary" id="library-rebuild" type="button">Rebuild Index</button>
        </div>
        <div class="panel-body">
          <div class="grid2">
            <label>Search
              <input id="library-query" placeholder="rainy synth hook">
            </label>
            <label>Kind
              <select id="library-kind">
                <option value="">assets + references</option>
                <option value="asset">assets</option>
                <option value="reference">references</option>
              </select>
            </label>
          </div>
          <div class="grid2">
            <label>Role
              <input id="library-role" placeholder="hook, melody, harmony">
            </label>
            <label>Tempo BPM
              <input id="library-tempo" type="number" min="40" max="240">
            </label>
          </div>
          <div class="grid2">
            <label>Key
              <input id="library-key" placeholder="C">
            </label>
            <label>Flags
              <span style="display:flex;gap:10px;margin-top:8px;">
                <label style="margin:0;"><input id="library-include-stale" type="checkbox"> stale</label>
                <label style="margin:0;"><input id="library-include-hidden" type="checkbox"> hidden</label>
              </span>
            </label>
          </div>
          <div class="actions">
            <button id="library-search" type="button">Search Library</button>
            <button class="secondary" id="library-recommend" type="button">Recommend</button>
            <span id="library-message" class="message"></span>
          </div>
          <div id="library-results"><div class="empty">Library results will appear here.</div></div>
          <div class="panel-title subhead"><span>Context Packs</span></div>
          <div class="grid2">
            <label>Name
              <input id="context-pack-name" placeholder="Rainy context">
            </label>
            <label>Saved Packs
              <select id="context-pack-select"><option value="">none</option></select>
            </label>
          </div>
          <div class="actions">
            <button id="context-pack-save-selection" type="button">Save Selected Context</button>
            <button class="secondary" id="context-pack-apply-preview" type="button">Apply Preview</button>
            <button class="secondary" id="context-pack-refresh" type="button">Refresh Packs</button>
            <span id="context-pack-message" class="message"></span>
          </div>
          <div id="context-pack-list"><div class="empty">No context packs yet.</div></div>
          <pre id="context-pack-preview">{}</pre>
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
      <section>
        <div class="panel-title">
          <span>References</span>
          <div class="actions" style="margin-top:0;">
            <label style="margin:0;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:650;">
              <input id="include-hidden-references" type="checkbox" style="width:auto;margin:0;">
              Hidden
            </label>
            <button class="secondary" id="refresh-references" type="button">Refresh</button>
          </div>
        </div>
        <div class="panel-body">
          <form id="reference-import-form">
            <div class="grid2">
              <label>Reference Type
                <select id="reference-type">
                  <option value="audio_wav">audio_wav</option>
                  <option value="midi">midi</option>
                  <option value="lyrics_text">lyrics_text</option>
                  <option value="style_note">style_note</option>
                </select>
              </label>
              <label>Title
                <input id="reference-title" placeholder="Reference title">
              </label>
            </div>
            <label>File
              <input id="reference-file" type="file" accept=".wav,.mid,.midi,.txt,.md">
            </label>
            <label>Tags
              <input id="reference-tags" placeholder="hook, style, client">
            </label>
            <div class="actions">
              <button type="submit">Import Reference</button>
              <span id="reference-message" class="message"></span>
            </div>
          </form>
          <div class="grid2">
            <label>Search References
              <input id="reference-search" placeholder="title, tag">
            </label>
            <label>Reference Type
              <select id="reference-type-filter">
                <option value="">all</option>
                <option value="audio_wav">audio_wav</option>
                <option value="midi">midi</option>
                <option value="lyrics_text">lyrics_text</option>
                <option value="style_note">style_note</option>
              </select>
            </label>
          </div>
          <div class="grid2">
            <label>Tag
              <input id="reference-tag-filter" placeholder="hook">
            </label>
            <label>Favorite
              <select id="reference-favorite-filter">
                <option value="">all</option>
                <option value="1">favorite</option>
              </select>
            </label>
          </div>
          <div id="reference-list" class="asset-list"><div class="empty">No references yet.</div></div>
          <div id="reference-detail"><div class="empty">Select a reference.</div></div>
        </div>
      </section>
      <section>
        <div class="panel-title">
          <span>Assets</span>
          <div class="actions" style="margin-top:0;">
            <label style="margin:0;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:650;">
              <input id="include-hidden-assets" type="checkbox" style="width:auto;margin:0;">
              Hidden
            </label>
            <button class="secondary" id="refresh-assets" type="button">Refresh</button>
          </div>
        </div>
        <div class="panel-body">
          <div class="grid2">
            <label>Search Assets
              <input id="asset-search" placeholder="name, tag, style">
            </label>
            <label>Asset Type
              <select id="asset-type-filter">
                <option value="">all</option>
                <option value="motif">motif</option>
                <option value="chord_progression">chord_progression</option>
                <option value="drum_pattern">drum_pattern</option>
                <option value="bass_pattern">bass_pattern</option>
                <option value="section_template">section_template</option>
                <option value="arrangement_template">arrangement_template</option>
                <option value="lyric_hook">lyric_hook</option>
              </select>
            </label>
          </div>
          <div class="grid2">
            <label>Tag
              <input id="asset-tag-filter" placeholder="chorus">
            </label>
            <label>Favorite
              <select id="asset-favorite-filter">
                <option value="">all</option>
                <option value="1">favorite</option>
              </select>
            </label>
          </div>
          <div id="asset-list" class="asset-list"><div class="empty">No assets yet.</div></div>
          <div id="asset-detail"><div class="empty">Select an asset.</div></div>
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
        <span>Releases</span>
        <div class="actions" style="margin-top:0;">
          <label style="margin:0;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:650;">
            <input id="include-hidden-releases" type="checkbox" style="width:auto;margin:0;">
            Hidden
          </label>
          <button class="secondary" id="refresh-releases" type="button">Refresh</button>
        </div>
      </div>
      <div class="panel-body">
        <div class="release-layout">
          <form id="release-form">
            <label>Release Name
              <input id="release-name" placeholder="EP, album, client pack">
            </label>
            <div class="grid2">
              <label>Release Type
                <select id="release-type">
                  <option value="demo_pack">demo_pack</option>
                  <option value="single_pack">single_pack</option>
                  <option value="ep">ep</option>
                  <option value="album">album</option>
                </select>
              </label>
              <label>Primary Artist
                <input id="release-primary-artist" placeholder="Artist">
              </label>
            </div>
            <div class="grid2">
              <label>Catalog ID
                <input id="release-catalog-id" placeholder="optional">
              </label>
              <label>Language
                <input id="release-language" placeholder="English">
              </label>
            </div>
            <label>Notes
              <textarea id="release-notes" rows="2"></textarea>
            </label>
            <div class="actions">
              <button type="submit">New Release</button>
              <span id="release-message" class="message"></span>
            </div>
          </form>
          <div>
            <div id="release-list" class="release-list"><div class="empty">No releases yet.</div></div>
          </div>
        </div>
        <div id="release-detail" class="release-detail"><div class="empty">Select or create a release.</div></div>
      </div>
    </section>
    <section style="grid-column: 1 / -1;">
      <div class="panel-title">
        <span>Portfolio Audit</span>
        <div class="actions" style="margin-top:0;">
          <label style="margin:0;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:650;">
            <input id="include-archived-portfolio-audits" type="checkbox" style="width:auto;margin:0;">
            Archived
          </label>
          <button class="secondary" id="refresh-portfolio-audits" type="button">Refresh</button>
        </div>
      </div>
      <div class="panel-body">
        <div class="release-layout">
          <form id="portfolio-audit-form">
            <label>Portfolio Name
              <input id="portfolio-audit-name" value="Release Portfolio Audit">
            </label>
            <label>Release IDs
              <textarea id="portfolio-audit-release-ids" rows="3" placeholder="rel-000001, rel-000002"></textarea>
            </label>
            <div class="grid2">
              <label>Max Releases
                <input id="portfolio-audit-max-releases" type="number" min="1" max="500" value="50">
              </label>
              <label>Selection Flags
                <span style="display:flex;gap:10px;margin-top:8px;flex-wrap:wrap;">
                  <label style="margin:0;"><input id="portfolio-audit-include-hidden-releases" type="checkbox"> hidden releases</label>
                  <label style="margin:0;"><input id="portfolio-audit-include-archived-releases" type="checkbox" checked> archived releases</label>
                </span>
              </label>
            </div>
            <div class="grid3">
              <label style="margin:0;"><input id="portfolio-audit-require-reviewer-packs" type="checkbox" checked> Require reviewer packs</label>
              <label style="margin:0;"><input id="portfolio-audit-require-audit" type="checkbox" checked> Require audit</label>
              <label style="margin:0;"><input id="portfolio-audit-require-archive" type="checkbox" checked> Require archive</label>
            </div>
            <div class="actions">
              <button type="submit">New Portfolio Audit</button>
              <span id="portfolio-audit-message" class="message"></span>
            </div>
          </form>
          <div>
            <div id="portfolio-audit-list" class="release-list"><div class="empty">No Portfolio Audits yet.</div></div>
          </div>
        </div>
        <div id="portfolio-audit-detail" class="release-detail"><div class="empty">Select or create a Portfolio Audit.</div></div>
      </div>
    </section>
    <section style="grid-column: 1 / -1;">
      <div class="panel-title">
        <span>Acceptance</span>
        <button class="secondary" id="refresh-acceptance" type="button">Refresh</button>
      </div>
      <div class="panel-body">
        <div class="release-layout">
          <form id="acceptance-form">
            <label>Suite Name
              <input id="acceptance-name" value="v4.5 regression songbook acceptance">
            </label>
            <div class="grid2">
              <label>Profile
                <select id="acceptance-profile">
                  <option value="developer_manual">developer_manual</option>
                  <option value="midi_smoke">midi_smoke</option>
                  <option value="release_candidate">release_candidate</option>
                  <option value="audio_required">audio_required</option>
                </select>
              </label>
              <label>Min Rating
                <input id="acceptance-min-rating" type="number" min="1" max="5" value="3">
              </label>
            </div>
            <div class="grid2">
              <label>Mode
                <select id="acceptance-mode">
                  <option value="developer_self_test">developer_self_test</option>
                  <option value="release_review">release_review</option>
                </select>
              </label>
            </div>
            <div class="actions">
              <button type="submit">New Suite</button>
              <span id="acceptance-message" class="message"></span>
            </div>
          </form>
          <div>
            <div class="panel-title subhead"><span>Regression Songbook</span></div>
            <div id="acceptance-songbook" class="release-list"><div class="empty">Loading songbook.</div></div>
            <div class="panel-title subhead"><span>Suites</span></div>
            <div id="acceptance-list" class="release-list"><div class="empty">No acceptance suites yet.</div></div>
          </div>
        </div>
        <div id="acceptance-detail" class="release-detail"><div class="empty">Select or create an acceptance suite.</div></div>
        <div class="panel-title subhead"><span>Acceptance Analytics</span></div>
        <div class="actions">
          <button class="secondary" id="acceptance-refresh-analytics" type="button">Refresh Analytics</button>
          <button class="secondary" id="acceptance-create-fix-sprint" type="button">Create Fix Sprint</button>
        </div>
        <div id="acceptance-analytics" class="release-detail"><div class="empty">No acceptance analytics report yet.</div></div>
        <div class="panel-title subhead"><span>Acceptance Fix Sprints</span></div>
        <div class="actions">
          <button class="secondary" id="acceptance-refresh-fix-sprints" type="button">Refresh Fix Sprints</button>
        </div>
        <div id="acceptance-fix-sprints" class="release-detail"><div class="empty">No acceptance fix sprints yet.</div></div>
        <div class="panel-title subhead"><span>Fix Planning</span></div>
        <div class="actions">
          <button class="secondary" id="acceptance-fix-plan-refresh" type="button">Refresh Plans</button>
          <button class="secondary" id="acceptance-fix-plan-create" type="button">Create Plan</button>
          <button class="secondary" id="acceptance-fix-plan-create-sprint" type="button">Create Sprint From Plan</button>
          <button class="secondary" id="acceptance-fix-plan-review-refresh" type="button">Refresh Outcome Review</button>
        </div>
        <div class="grid3">
          <label>Plan Max Items <input id="acceptance-fix-plan-max-items" type="number" min="1" max="50" value="20"></label>
          <label>Include Hidden KB <input id="acceptance-fix-plan-hidden" type="checkbox" style="width:auto;margin-top:10px;"></label>
          <label>Plan ID <input id="acceptance-fix-plan-id" readonly value=""></label>
        </div>
        <div id="acceptance-fix-plans" class="release-detail"><div class="empty">No acceptance fix plans yet.</div></div>
        <div class="panel-title subhead"><span>Fix Plan Outcome Review</span></div>
        <div id="acceptance-fix-plan-review" class="release-detail"><div class="empty">Select a Fix Plan and refresh Outcome Review.</div></div>
        <div class="panel-title subhead"><span>Planning Rule Simulation</span></div>
        <div class="actions">
          <select id="planning-ruleset-template">
            <option value="baseline">baseline</option>
            <option value="manual_conservative">manual_conservative</option>
            <option value="kb_trust_light">kb_trust_light</option>
            <option value="waiver_strict">waiver_strict</option>
            <option value="synthetic_strict">synthetic_strict</option>
          </select>
          <button class="secondary" id="planning-ruleset-create" type="button">Create Rule Set</button>
          <button class="secondary" id="planning-simulation-run" type="button">Run Simulation</button>
          <button class="secondary" id="planning-simulation-refresh" type="button">Refresh Simulations</button>
        </div>
        <div id="planning-rule-simulation" class="release-detail"><div class="empty">Simulation only. No production rules are changed.</div></div>
        <div class="panel-title subhead"><span>Planning Rule Governance</span></div>
        <div class="actions">
          <button class="secondary" id="planning-governance-refresh" type="button">Refresh Governance</button>
          <button class="secondary" id="planning-governance-create" type="button">Create Promotion</button>
          <button class="secondary" id="planning-governance-approve" type="button">Approve</button>
          <button class="secondary" id="planning-governance-promote" type="button">Promote</button>
        </div>
        <div id="planning-rule-governance" class="release-detail"><div class="empty">No active planning rule version.</div></div>
        <div class="panel-title subhead"><span>Planning Rule Impact</span></div>
        <div class="actions">
          <button class="secondary" id="planning-impact-refresh" type="button">Refresh Impact Report</button>
        </div>
        <div id="planning-rule-impact" class="release-detail"><div class="empty">No planning rule impact report yet.</div></div>
        <div class="panel-title subhead"><span>Knowledge Base</span></div>
        <div class="actions">
          <button class="secondary" id="acceptance-kb-refresh" type="button">Refresh KB</button>
          <button class="secondary" id="acceptance-kb-recommend" type="button">Recommend</button>
        </div>
        <div class="grid3">
          <label>Issue Type <input id="acceptance-kb-issue-type" value="hook"></label>
          <label>Style <input id="acceptance-kb-style" value=""></label>
          <label>Song ID <input id="acceptance-kb-song-id" value=""></label>
        </div>
        <div id="acceptance-kb" class="release-detail"><div class="empty">No acceptance knowledge report yet.</div></div>
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
    let releases = [];
    let selectedReleaseId = null;
    let includeHiddenReleases = false;
    let portfolioAudits = [];
    let selectedPortfolioAuditId = null;
    let includeArchivedPortfolioAudits = false;
    let acceptanceSuites = [];
    let acceptanceProfiles = [];
    let acceptanceSongbook = null;
    let selectedAcceptanceSuiteId = null;
    let acceptanceAnalytics = null;
    let acceptanceFixSprints = [];
    let acceptanceFixPlans = [];
    let acceptanceFixPlanReview = null;
    let planningRuleSets = [];
    let planningSimulations = [];
    let planningGovernance = null;
    let planningPromotions = [];
    let planningVersions = [];
    let planningImpact = null;
    let planningImpactReports = [];
    let acceptanceKb = null;
    let acceptanceKbRecommendation = null;
    let projects = [];
    let selectedProjectId = null;
    let includeHiddenProjects = false;
    let activeProjectTab = "versions";
    let projectVariationParentId = null;
    let projectEditParentId = null;
    let projectEditorParentId = null;
    let projectEditorState = null;
    let projectEditorView = null;
    let projectEditorPatch = [];
    let projectEditorRedo = [];
    let projectEditorPreview = null;
    let projectEditorPreviewHistory = [];
    let projectEditorAuditions = [];
    let projectEditorDraft = null;
    let projectEditorClips = null;
    let editorTemplates = null;
    let projectEditorTemplateMapping = null;
    let projectEditorSelectedTemplateIndex = 0;
    let projectEditorClipInsertMap = {};
    let projectEditorTemplateInsertMap = {};
    let projectEditorSelectedClipIndex = 0;
    let projectEditorSelectedSectionId = null;
    let projectEditorSelectedTrackId = null;
    let projectEditorSelectedNoteId = null;
    let editPresets = [];
    let promptTemplates = [];
    let providerEditPreview = null;
    let assets = [];
    let selectedAssetId = null;
    let includeHiddenAssets = false;
    let references = [];
    let selectedReferenceId = null;
    let includeHiddenReferences = false;
    let contextPacks = [];
    let librarySelection = { asset_refs: [], reference_refs: [] };

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
      await loadGaHealth();
      await loadMaintenanceStatus();
      await loadPromptTemplates();
      await loadEditorTemplates();
      await loadRenderer();
      await loadEditPresets();
      await loadAssets();
      await loadReferences();
      await loadContextPacks();
      await loadJobs();
      await loadProjects();
      await loadReleases();
      await loadPortfolioAudits();
      await loadAcceptanceReferenceData();
      await loadAcceptanceAnalytics();
      await loadAcceptanceFixSprints();
      await loadAcceptanceKb();
      await loadPlanningSimulations();
      await loadPlanningGovernance();
      await loadPlanningImpact();
      await loadAcceptanceSuites();
      await loadBatches();
      setInterval(() => {
        loadJobs();
        loadProjects();
        loadReleases();
        loadPortfolioAudits();
        loadAcceptanceAnalytics();
        loadAcceptanceFixSprints();
        loadAcceptanceKb();
        loadPlanningSimulations();
        loadPlanningGovernance();
        loadPlanningImpact();
        loadAcceptanceSuites();
        loadAssets();
        loadReferences();
        loadContextPacks();
        loadEditorTemplates();
        loadBatches();
      }, 2000);
      $("poll").textContent = "polling 2s";
    }

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
      const refs = assetRefsPayload("song-asset-refs");
      if (refs.length) payload.asset_refs = refs;
      const referenceRefs = referenceRefsPayload("song-reference-refs");
      if (referenceRefs.length) payload.reference_refs = referenceRefs;
      const contextPackId = contextPackIdPayload("song-context-pack");
      if (contextPackId) payload.context_pack_id = contextPackId;
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
    $("song-suggest-context").addEventListener("click", async () => {
      try {
        const data = await api("/api/library/recommend", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source: "song_request",
            goal: "generate",
            song_request: formPayload(),
          }),
        });
        applyLibraryPreview(data.recommendation.context_pack_preview || {});
        renderLibraryResults([...(data.recommendation.asset_results || []), ...(data.recommendation.reference_results || [])]);
        $("song-context-suggestion").textContent = "context suggested";
      } catch (err) {
        $("song-context-suggestion").textContent = err.message;
      }
    });
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
    $("refresh-releases").addEventListener("click", loadReleases);
    $("include-hidden-releases").addEventListener("change", async () => {
      includeHiddenReleases = $("include-hidden-releases").checked;
      await loadReleases();
    });
    $("release-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/releases", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(releasePayload()),
        });
        selectedReleaseId = data.release.release_id;
        $("release-message").textContent = "created";
        await loadReleases();
      } catch (err) {
        $("release-message").textContent = err.message;
      }
    });
    $("refresh-portfolio-audits").addEventListener("click", loadPortfolioAudits);
    $("include-archived-portfolio-audits").addEventListener("change", async () => {
      includeArchivedPortfolioAudits = $("include-archived-portfolio-audits").checked;
      await loadPortfolioAudits();
    });
    $("portfolio-audit-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/release-portfolio-audits", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(portfolioAuditPayload()),
        });
        selectedPortfolioAuditId = (data.portfolio || {}).portfolio_id || null;
        $("portfolio-audit-message").textContent = "created";
        await loadPortfolioAudits();
      } catch (err) {
        $("portfolio-audit-message").textContent = err.message;
      }
    });
    $("refresh-acceptance").addEventListener("click", loadAcceptanceSuites);
    $("acceptance-refresh-analytics").addEventListener("click", async () => {
      try {
        const data = await api("/api/acceptance/analytics/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: "global" }) });
        acceptanceAnalytics = data.analytics || null;
        renderAcceptanceAnalytics();
      } catch (err) {
        $("acceptance-analytics").innerHTML = `<div class="empty">${escapeHtml(err.message)}</div>`;
      }
    });
    $("acceptance-refresh-fix-sprints").addEventListener("click", loadAcceptanceFixSprints);
    $("acceptance-fix-plan-refresh").addEventListener("click", loadAcceptanceFixPlans);
    $("acceptance-fix-plan-create").addEventListener("click", async () => {
      try {
        if (!acceptanceAnalytics || !acceptanceAnalytics.report_id) throw new Error("Refresh Acceptance Analytics first.");
        const data = await api("/api/acceptance/fix-plans", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            analytics_report_id: acceptanceAnalytics.report_id,
            kb_report_id: (acceptanceKb || {}).report_id || null,
            max_items: Number($("acceptance-fix-plan-max-items").value || 20),
            include_hidden_kb: $("acceptance-fix-plan-hidden").checked,
          }),
        });
        $("acceptance-fix-plan-id").value = (data.fix_plan || {}).plan_id || "";
        await loadAcceptanceFixPlans();
      } catch (err) {
        $("acceptance-fix-plans").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("acceptance-fix-plan-create-sprint").addEventListener("click", async () => {
      try {
        const planId = $("acceptance-fix-plan-id").value.trim() || ((acceptanceFixPlans[0] || {}).plan_id || "");
        if (!planId) throw new Error("Create or select a Fix Plan first.");
        await api(`/api/acceptance/fix-plans/${encodeURIComponent(planId)}/create-fix-sprint`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Knowledge-assisted Fix Sprint" }) });
        await loadAcceptanceFixPlans();
        await loadAcceptanceFixSprints();
      } catch (err) {
        $("acceptance-fix-plans").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("acceptance-fix-plan-review-refresh").addEventListener("click", async () => {
      try {
        const planId = $("acceptance-fix-plan-id").value.trim() || ((acceptanceFixPlans[0] || {}).plan_id || "");
        if (!planId) throw new Error("Select a Fix Plan first.");
        const data = await api(`/api/acceptance/fix-plans/${encodeURIComponent(planId)}/outcome-review/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        acceptanceFixPlanReview = data.outcome_review || null;
        renderAcceptanceFixPlanReview();
      } catch (err) {
        $("acceptance-fix-plan-review").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("planning-ruleset-create").addEventListener("click", async () => {
      try {
        await api("/api/acceptance/planning-rulesets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ template: $("planning-ruleset-template").value }),
        });
        await loadPlanningSimulations();
      } catch (err) {
        $("planning-rule-simulation").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("planning-simulation-run").addEventListener("click", async () => {
      try {
        const ruleset = planningRuleSets[0];
        if (!ruleset) throw new Error("Create a Planning Rule Set first.");
        const reviewId = (acceptanceFixPlanReview || {}).review_id;
        if (!reviewId) throw new Error("Refresh an Outcome Review first.");
        await api("/api/acceptance/planning-simulations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ruleset_id: ruleset.ruleset_id, review_ids: [reviewId], include_warning_reviews: true }),
        });
        await loadPlanningSimulations();
      } catch (err) {
        $("planning-rule-simulation").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("planning-simulation-refresh").addEventListener("click", loadPlanningSimulations);
    $("planning-governance-refresh").addEventListener("click", loadPlanningGovernance);
    $("planning-impact-refresh").addEventListener("click", async () => {
      try {
        const data = await api("/api/acceptance/planning-rule-impact/reports", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: { type: "global" }, include_legacy: true, include_superseded: true }) });
        planningImpact = data.impact_report || null;
        await loadPlanningImpact();
      } catch (err) {
        $("planning-rule-impact").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("planning-governance-create").addEventListener("click", async () => {
      try {
        const simulation = planningSimulations[0];
        if (!simulation) throw new Error("Run a Planning Rule Simulation first.");
        await api("/api/acceptance/planning-rule-governance/promotions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ruleset_id: simulation.ruleset_id, simulation_id: simulation.simulation_id, note: "Studio promotion request" }),
        });
        await loadPlanningGovernance();
      } catch (err) {
        $("planning-rule-governance").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("planning-governance-approve").addEventListener("click", async () => {
      try {
        const promotion = planningPromotions.find((item) => item.status === "pending") || planningPromotions[0];
        if (!promotion) throw new Error("Create a Planning Rule Promotion first.");
        await api(`/api/acceptance/planning-rule-governance/promotions/${encodeURIComponent(promotion.promotion_id)}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved_by: "studio", approval_note: "Approved in Studio" }),
        });
        await loadPlanningGovernance();
      } catch (err) {
        $("planning-rule-governance").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("planning-governance-promote").addEventListener("click", async () => {
      try {
        const promotion = planningPromotions.find((item) => item.status === "approved") || planningPromotions[0];
        if (!promotion) throw new Error("Approve a Planning Rule Promotion first.");
        await api(`/api/acceptance/planning-rule-governance/promotions/${encodeURIComponent(promotion.promotion_id)}/promote`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ promoted_by: "studio" }),
        });
        await loadPlanningGovernance();
      } catch (err) {
        $("planning-rule-governance").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("acceptance-kb-refresh").addEventListener("click", async () => {
      try {
        const data = await api("/api/acceptance/kb/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: "global" }) });
        acceptanceKb = data.knowledge_report || null;
        acceptanceKbRecommendation = null;
        renderAcceptanceKb();
      } catch (err) {
        $("acceptance-kb").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("acceptance-kb-recommend").addEventListener("click", async () => {
      try {
        const payload = {
          issue_types: [$("acceptance-kb-issue-type").value.trim()].filter(Boolean),
          style: $("acceptance-kb-style").value.trim(),
          song_id: $("acceptance-kb-song-id").value.trim(),
        };
        const data = await api("/api/acceptance/kb/recommend", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        acceptanceKbRecommendation = data.recommendation || null;
        renderAcceptanceKb();
      } catch (err) {
        $("acceptance-kb").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("acceptance-create-fix-sprint").addEventListener("click", async () => {
      try {
        if (!acceptanceAnalytics || !acceptanceAnalytics.report_id) throw new Error("Refresh Acceptance Analytics first.");
        await api("/api/acceptance/fix-sprints", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ analytics_report_id: acceptanceAnalytics.report_id, name: "Acceptance-driven Fix Sprint" }),
        });
        await loadAcceptanceFixSprints();
      } catch (err) {
        $("acceptance-fix-sprints").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    });
    $("acceptance-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const data = await api("/api/acceptance/suites", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: $("acceptance-name").value.trim() || "Music Acceptance Suite",
            mode: $("acceptance-mode").value,
            profile_id: $("acceptance-profile").value,
            min_rating: Number($("acceptance-min-rating").value || 3),
          }),
        });
        selectedAcceptanceSuiteId = data.suite.suite_id;
        $("acceptance-message").textContent = "created";
        await loadAcceptanceSuites();
      } catch (err) {
        $("acceptance-message").textContent = err.message;
      }
    });
    $("refresh-assets").addEventListener("click", loadAssets);
    $("include-hidden-assets").addEventListener("change", async () => {
      includeHiddenAssets = $("include-hidden-assets").checked;
      await loadAssets();
    });
    ["asset-type-filter", "asset-favorite-filter"].forEach((id) => {
      $(id).addEventListener("change", loadAssets);
    });
    ["asset-search", "asset-tag-filter"].forEach((id) => {
      $(id).addEventListener("input", debounce(loadAssets, 250));
    });
    $("refresh-references").addEventListener("click", loadReferences);
    $("include-hidden-references").addEventListener("change", async () => {
      includeHiddenReferences = $("include-hidden-references").checked;
      await loadReferences();
    });
    ["reference-type-filter", "reference-favorite-filter"].forEach((id) => {
      $(id).addEventListener("change", loadReferences);
    });
    ["reference-search", "reference-tag-filter"].forEach((id) => {
      $(id).addEventListener("input", debounce(loadReferences, 250));
    });
    $("library-search").addEventListener("click", searchLibrary);
    $("library-recommend").addEventListener("click", recommendLibrary);
    $("library-rebuild").addEventListener("click", rebuildLibrary);
    $("context-pack-refresh").addEventListener("click", loadContextPacks);
    $("context-pack-save-selection").addEventListener("click", saveSelectedContextPack);
    $("context-pack-apply-preview").addEventListener("click", previewSelectedContextPack);
    $("context-pack-select").addEventListener("change", () => {
      $("song-context-pack").value = $("context-pack-select").value;
    });
    $("editor-template-refresh").addEventListener("click", loadEditorTemplates);
    $("reference-import-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const payload = await referenceImportPayload();
        const data = await api("/api/references/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        selectedReferenceId = data.reference.reference_id;
        $("reference-message").textContent = data.duplicate ? "duplicate" : "imported";
        $("reference-file").value = "";
        await loadReferences();
      } catch (err) {
        $("reference-message").textContent = err.message;
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

    async function loadEditorTemplates() {
      editorTemplates = await api("/api/editor-templates");
      const sections = (editorTemplates.section_templates || []).filter((template) => !template.hidden);
      const tracks = (editorTemplates.track_templates || []).filter((template) => !template.hidden);
      const total = sections.length + tracks.length;
      $("editor-template-status").textContent = `${total} templates`;
      const target = $("editor-template-list");
      if (!total) {
        target.innerHTML = `<div class="empty">No editor templates saved yet.</div>`;
        return;
      }
      target.innerHTML = `
        <table>
          <thead><tr><th>Name</th><th>Type</th><th>Lanes</th><th>Notes</th><th>Updated</th></tr></thead>
          <tbody>
            ${sections.map((template) => `<tr><td>${escapeHtml(template.name)}</td><td>section</td><td>${escapeHtml(((template.clip || {}).lane_count) || 0)}</td><td>${escapeHtml(((template.clip || {}).note_count) || 0)}</td><td>${escapeHtml(template.updated_at || "-")}</td></tr>`).join("")}
            ${tracks.map((template) => `<tr><td>${escapeHtml(template.name)}</td><td>track</td><td>1</td><td>${escapeHtml(template.default_note_count || 0)}</td><td>${escapeHtml(template.updated_at || "-")}</td></tr>`).join("")}
          </tbody>
        </table>
      `;
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

    async function loadContextPacks() {
      try {
        const data = await api("/api/context-packs");
        contextPacks = data.context_packs || [];
        renderContextPacks();
        renderContextPackSelectors();
      } catch (err) {
        $("context-pack-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    async function rebuildLibrary() {
      const data = await api("/api/library/rebuild", { method: "POST" });
      $("library-message").textContent = `${data.index.item_count} indexed`;
    }

    async function searchLibrary() {
      const payload = librarySearchPayload();
      const data = await api("/api/library/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      renderLibraryResults(data.results || []);
      $("library-message").textContent = `${data.total || 0} results`;
    }

    async function recommendLibrary() {
      const data = await api("/api/library/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "song_request",
          goal: "generate",
          song_request: formPayload(),
          limit: 10,
        }),
      });
      const recommendation = data.recommendation || {};
      applyLibraryPreview(recommendation.context_pack_preview || {});
      renderLibraryResults([...(recommendation.asset_results || []), ...(recommendation.reference_results || [])]);
      $("library-message").textContent = "recommended";
    }

    function librarySearchPayload() {
      const payload = {
        query: $("library-query").value.trim(),
        include_stale: $("library-include-stale").checked,
        include_hidden: $("library-include-hidden").checked,
        limit: 30,
      };
      if ($("library-kind").value) payload.item_kinds = [$("library-kind").value];
      if ($("library-role").value.trim()) payload.roles = $("library-role").value.split(",").map((item) => item.trim()).filter(Boolean);
      if ($("library-tempo").value) payload.tempo_bpm = Number($("library-tempo").value);
      if ($("library-key").value.trim()) payload.key = $("library-key").value.trim();
      return payload;
    }

    function renderLibraryResults(results) {
      const target = $("library-results");
      if (!results.length) {
        target.innerHTML = "<div class='empty'>No library results.</div>";
        return;
      }
      target.innerHTML = results.map((result) => `
        <div class="library-result">
          <h4>${escapeHtml(result.title)} <span class="status">${escapeHtml(result.item_kind)} · ${escapeHtml(result.item_type)}</span></h4>
          <div class="summary-grid">
            ${metric("Score", result.score ?? "-")}
            ${metric("Key", result.key || "-")}
            ${metric("Tempo", result.tempo_bpm || "-")}
            ${metric("Uses", result.usage_count || 0)}
          </div>
          <div class="actions">
            <button class="secondary" data-library-add="${escapeHtml(result.item_id)}" data-kind="${escapeHtml(result.item_kind)}" data-source-id="${escapeHtml(result.source_id)}" data-role="${escapeHtml(((result.features || {}).roles || ["reference"])[0] || "reference")}" type="button">Add to Context</button>
          </div>
          <pre>${escapeHtml(JSON.stringify({ tags: result.tags || [], reasons: result.score_breakdown || [], summary: result.summary || {} }, null, 2))}</pre>
        </div>
      `).join("");
      target.querySelectorAll("[data-library-add]").forEach((button) => {
        button.addEventListener("click", () => {
          if (button.dataset.kind === "asset") {
            upsertContextRef(librarySelection.asset_refs, "asset_id", { asset_id: button.dataset.sourceId, role: button.dataset.role, strength: 0.8 });
          } else {
            upsertContextRef(librarySelection.reference_refs, "reference_id", { reference_id: button.dataset.sourceId, role: button.dataset.role, strength: 0.6 });
          }
          renderContextPackPreview();
        });
      });
    }

    function applyLibraryPreview(preview) {
      librarySelection = {
        asset_refs: (preview.asset_refs || []).slice(0, 5),
        reference_refs: (preview.reference_refs || []).slice(0, 5),
      };
      renderContextPackPreview();
    }

    function upsertContextRef(list, key, item) {
      if (list.some((ref) => ref[key] === item[key])) return;
      if (list.length >= 5) return;
      list.push(item);
    }

    async function saveSelectedContextPack() {
      try {
        const pack = await api("/api/context-packs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: $("context-pack-name").value.trim() || "Studio Context",
            created_from: { source: "studio", goal: "generate" },
            query: librarySearchPayload(),
            asset_refs: librarySelection.asset_refs,
            reference_refs: librarySelection.reference_refs,
            selection: { mode: "manual", selected_by: "user" },
          }),
        });
        $("context-pack-message").textContent = "saved";
        $("context-pack-select").value = pack.context_pack.pack_id;
        await loadContextPacks();
      } catch (err) {
        $("context-pack-message").textContent = err.message;
      }
    }

    async function previewSelectedContextPack() {
      const packId = $("context-pack-select").value;
      if (!packId) return;
      try {
        const data = await api(`/api/context-packs/${encodeURIComponent(packId)}/apply-preview`, { method: "POST" });
        $("context-pack-preview").textContent = JSON.stringify(data, null, 2);
        librarySelection = { asset_refs: data.asset_refs || [], reference_refs: data.reference_refs || [] };
      } catch (err) {
        $("context-pack-preview").textContent = err.message;
      }
    }

    function renderContextPacks() {
      const target = $("context-pack-list");
      if (!contextPacks.length) {
        target.innerHTML = "<div class='empty'>No context packs yet.</div>";
        return;
      }
      target.innerHTML = `
        <table><thead><tr><th>Pack</th><th>Assets</th><th>References</th><th>Updated</th></tr></thead><tbody>
          ${contextPacks.map((pack) => `<tr><td>${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</td><td>${escapeHtml((pack.asset_refs || []).length)}</td><td>${escapeHtml((pack.reference_refs || []).length)}</td><td>${escapeHtml(pack.updated_at || "-")}</td></tr>`).join("")}
        </tbody></table>
      `;
    }

    function renderContextPackSelectors() {
      document.querySelectorAll(".context-pack-select").forEach((select) => {
        const selected = select.value;
        select.innerHTML = `<option value="">none</option>${contextPacks.map((pack) => `<option value="${escapeHtml(pack.pack_id)}">${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</option>`).join("")}`;
        select.value = selected;
      });
      if ($("context-pack-select")) {
        const selected = $("context-pack-select").value;
        $("context-pack-select").innerHTML = `<option value="">none</option>${contextPacks.map((pack) => `<option value="${escapeHtml(pack.pack_id)}">${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</option>`).join("")}`;
        $("context-pack-select").value = selected;
      }
      if ($("song-context-pack")) {
        const selected = $("song-context-pack").value;
        $("song-context-pack").innerHTML = `<option value="">none</option>${contextPacks.map((pack) => `<option value="${escapeHtml(pack.pack_id)}">${escapeHtml(pack.name)} · ${escapeHtml(pack.pack_id)}</option>`).join("")}`;
        $("song-context-pack").value = selected;
      }
    }

    function renderContextPackPreview() {
      $("context-pack-preview").textContent = JSON.stringify(librarySelection, null, 2);
    }

    function contextPackIdPayload(selectId) {
      const select = $(selectId);
      return select && select.value ? select.value : "";
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

    async function loadReleases() {
      try {
        const data = await api(includeHiddenReleases ? "/api/releases?include_hidden=1" : "/api/releases");
        releases = data.releases || [];
        if (selectedReleaseId && !releases.some((release) => release.release_id === selectedReleaseId)) {
          selectedReleaseId = null;
          $("release-detail").innerHTML = "<div class='empty'>Select or create a release.</div>";
        }
        renderReleases();
        if (selectedReleaseId) await renderReleaseDetail(selectedReleaseId);
      } catch (err) {
        $("release-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadPortfolioAudits() {
      try {
        const data = await api(includeArchivedPortfolioAudits ? "/api/release-portfolio-audits?include_archived=1" : "/api/release-portfolio-audits");
        portfolioAudits = data.portfolios || [];
        if (selectedPortfolioAuditId && !portfolioAudits.some((portfolio) => portfolio.portfolio_id === selectedPortfolioAuditId)) {
          selectedPortfolioAuditId = null;
          $("portfolio-audit-detail").innerHTML = "<div class='empty'>Select or create a Portfolio Audit.</div>";
        }
        renderPortfolioAudits();
        if (selectedPortfolioAuditId) await renderPortfolioAuditDetail(selectedPortfolioAuditId);
      } catch (err) {
        $("portfolio-audit-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadAcceptanceSuites() {
      try {
        const data = await api("/api/acceptance/suites");
        acceptanceSuites = data.suites || [];
        if (selectedAcceptanceSuiteId && !acceptanceSuites.some((suite) => suite.suite_id === selectedAcceptanceSuiteId)) {
          selectedAcceptanceSuiteId = null;
          $("acceptance-detail").innerHTML = "<div class='empty'>Select or create an acceptance suite.</div>";
        }
        renderAcceptanceSuites();
        if (selectedAcceptanceSuiteId) await renderAcceptanceDetail(selectedAcceptanceSuiteId);
      } catch (err) {
        $("acceptance-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadAcceptanceReferenceData() {
      try {
        const [profilesData, songbookData] = await Promise.all([
          api("/api/acceptance/profiles"),
          api("/api/acceptance/songbook"),
        ]);
        acceptanceProfiles = profilesData.profiles || [];
        acceptanceSongbook = songbookData.songbook || null;
        renderAcceptanceReferenceData();
      } catch (err) {
        $("acceptance-songbook").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadAcceptanceAnalytics() {
      try {
        const data = await api("/api/acceptance/analytics");
        acceptanceAnalytics = data.analytics || null;
      } catch (err) {
        acceptanceAnalytics = null;
      }
      renderAcceptanceAnalytics();
    }

    async function loadAcceptanceFixSprints() {
      try {
        const data = await api("/api/acceptance/fix-sprints");
        acceptanceFixSprints = data.fix_sprints || [];
      } catch (err) {
        acceptanceFixSprints = [];
      }
      renderAcceptanceFixSprints();
    }

    async function loadAcceptanceFixPlans() {
      try {
        const data = await api("/api/acceptance/fix-plans");
        acceptanceFixPlans = data.fix_plans || [];
      } catch (err) {
        acceptanceFixPlans = [];
      }
      renderAcceptanceFixPlans();
    }

    async function loadAcceptanceFixPlanReview(planId) {
      if (!planId) {
        acceptanceFixPlanReview = null;
        renderAcceptanceFixPlanReview();
        return;
      }
      try {
        const data = await api(`/api/acceptance/fix-plans/${encodeURIComponent(planId)}/outcome-review`);
        acceptanceFixPlanReview = data.outcome_review || null;
      } catch (err) {
        acceptanceFixPlanReview = null;
      }
      renderAcceptanceFixPlanReview();
    }

    async function loadPlanningSimulations() {
      try {
        const [rulesetsData, simulationsData] = await Promise.all([
          api("/api/acceptance/planning-rulesets"),
          api("/api/acceptance/planning-simulations"),
        ]);
        planningRuleSets = rulesetsData.rulesets || [];
        planningSimulations = simulationsData.simulations || [];
      } catch (err) {
        planningRuleSets = [];
        planningSimulations = [];
      }
      renderPlanningSimulations();
    }

    async function loadPlanningGovernance() {
      try {
        const [activeData, promotionsData, versionsData] = await Promise.all([
          api("/api/acceptance/planning-rule-governance/active"),
          api("/api/acceptance/planning-rule-governance/promotions"),
          api("/api/acceptance/planning-rule-governance/versions"),
        ]);
        planningGovernance = activeData || null;
        planningPromotions = promotionsData.promotions || [];
        planningVersions = versionsData.versions || [];
      } catch (err) {
        planningGovernance = null;
        planningPromotions = [];
        planningVersions = [];
      }
      renderPlanningGovernance();
    }

    async function loadPlanningImpact() {
      try {
        const data = await api("/api/acceptance/planning-rule-impact/reports");
        planningImpactReports = data.reports || [];
        planningImpact = planningImpactReports[0] || null;
      } catch (err) {
        planningImpactReports = [];
        planningImpact = null;
      }
      renderPlanningImpact();
    }

    async function loadAcceptanceKb() {
      try {
        const data = await api("/api/acceptance/kb");
        acceptanceKb = data.knowledge_report || null;
      } catch (err) {
        acceptanceKb = null;
      }
      renderAcceptanceKb();
    }

    async function loadAssets() {
      try {
        const params = new URLSearchParams();
        if (includeHiddenAssets) params.set("include_hidden", "1");
        if ($("asset-search").value.trim()) params.set("q", $("asset-search").value.trim());
        if ($("asset-type-filter").value) params.set("type", $("asset-type-filter").value);
        if ($("asset-tag-filter").value.trim()) params.set("tag", $("asset-tag-filter").value.trim());
        if ($("asset-favorite-filter").value) params.set("favorite", $("asset-favorite-filter").value);
        const data = await api(`/api/assets${params.toString() ? "?" + params.toString() : ""}`);
        assets = data.assets || [];
        if (selectedAssetId && !assets.some((asset) => asset.asset_id === selectedAssetId)) {
          selectedAssetId = null;
          $("asset-detail").innerHTML = "<div class='empty'>Select an asset.</div>";
        }
        renderAssets();
        renderAssetSelectors();
        if (selectedAssetId) await renderAssetDetail(selectedAssetId);
      } catch (err) {
        $("asset-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    async function loadReferences() {
      try {
        const params = new URLSearchParams();
        if (includeHiddenReferences) params.set("include_hidden", "1");
        if ($("reference-search").value.trim()) params.set("q", $("reference-search").value.trim());
        if ($("reference-type-filter").value) params.set("type", $("reference-type-filter").value);
        if ($("reference-tag-filter").value.trim()) params.set("tag", $("reference-tag-filter").value.trim());
        if ($("reference-favorite-filter").value) params.set("favorite", $("reference-favorite-filter").value);
        const data = await api(`/api/references${params.toString() ? "?" + params.toString() : ""}`);
        references = data.references || [];
        if (selectedReferenceId && !references.some((reference) => reference.reference_id === selectedReferenceId)) {
          selectedReferenceId = null;
          $("reference-detail").innerHTML = "<div class='empty'>Select a reference.</div>";
        }
        renderReferences();
        renderReferenceSelectors();
        if (selectedReferenceId) await renderReferenceDetail(selectedReferenceId);
      } catch (err) {
        $("reference-list").innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
    }

    function renderReferences() {
      const list = $("reference-list");
      if (!references.length) {
        list.innerHTML = "<div class='empty'>No references yet.</div>";
        renderReferenceSelectors();
        return;
      }
      const rows = references.map((reference) => `
        <tr>
          <td><button class="secondary reference-open" data-reference-id="${escapeHtml(reference.reference_id)}" type="button">Open</button></td>
          <td>${escapeHtml(reference.title)}</td>
          <td>${escapeHtml(reference.reference_type)}</td>
          <td>${escapeHtml((reference.tags || []).join(", "))}</td>
          <td>${escapeHtml(reference.size_bytes || 0)}</td>
          <td>${escapeHtml(reference.usage_count || 0)}</td>
          <td>${reference.favorite ? "yes" : "-"}</td>
        </tr>
      `).join("");
      list.innerHTML = `
        <table>
          <thead><tr><th></th><th>Title</th><th>Type</th><th>Tags</th><th>Bytes</th><th>Uses</th><th>Favorite</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      list.querySelectorAll(".reference-open").forEach((button) => {
        button.addEventListener("click", async () => {
          selectedReferenceId = button.dataset.referenceId;
          await renderReferenceDetail(selectedReferenceId);
        });
      });
    }

    async function renderReferenceDetail(referenceId) {
      const data = await api(`/api/references/${encodeURIComponent(referenceId)}`);
      const reference = data.reference;
      let analysis = { status: "not_loaded", summary: {} };
      let sliceManifest = { status: "not_loaded", slices: [] };
      try {
        analysis = (await api(`/api/references/${encodeURIComponent(referenceId)}/analysis`)).analysis || analysis;
      } catch (err) {
        analysis = { status: "error", error: err.message, summary: {} };
      }
      if (reference.reference_type === "midi") {
        try {
          sliceManifest = (await api(`/api/references/${encodeURIComponent(referenceId)}/slices`)).manifest || sliceManifest;
        } catch (err) {
          sliceManifest = { status: "error", error: err.message, slices: [] };
        }
      }
      $("reference-detail").innerHTML = `
        <div class="summary-grid">
          ${metric("Reference", reference.reference_id)}
          ${metric("Type", reference.reference_type)}
          ${metric("Size", reference.size_bytes || 0)}
          ${metric("Uses", reference.usage_count || 0)}
          ${metric("Key", reference.key || "-")}
          ${metric("Tempo", reference.tempo_bpm || "-")}
          ${metric("Projects", (reference.linked_project_ids || []).length)}
          ${metric("Assets", (reference.derived_asset_ids || []).length)}
        </div>
        <div class="grid2">
          <label>Title
            <input id="reference-edit-title" value="${escapeHtml(reference.title)}">
          </label>
          <label>Tags
            <input id="reference-edit-tags" value="${escapeHtml((reference.tags || []).join(", "))}">
          </label>
        </div>
        <label>Description
          <textarea id="reference-edit-description">${escapeHtml(reference.description || "")}</textarea>
        </label>
        <div class="actions">
          <button id="reference-save" type="button">Save Metadata</button>
          <a class="button-link secondary" href="${escapeHtml(reference.file_url)}">Download Original</a>
          ${reference.reference_type !== "audio_wav" ? `<button class="secondary" id="reference-create-asset" type="button">Create Asset</button>` : ""}
          ${selectedProjectId ? `<button class="secondary" id="reference-link-project" type="button">Link Project</button><button class="secondary" id="reference-unlink-project" type="button">Unlink Project</button>` : ""}
          ${reference.hidden ? `<button class="secondary" id="reference-unhide" type="button">Unhide Reference</button>` : `<button class="secondary" id="reference-hide" type="button">Hide Reference</button>`}
          ${reference.favorite ? `<button class="secondary" id="reference-unfavorite" type="button">Unfavorite</button>` : `<button class="secondary" id="reference-favorite" type="button">Favorite</button>`}
          <button class="danger" id="reference-delete" type="button">Delete Reference</button>
        </div>
        <div class="panel-title subhead"><span>Analysis</span></div>
        <div class="summary-grid">
          ${metric("Analysis", analysis.status || "-")}
          ${metric("Slices", (sliceManifest.slices || []).length)}
          ${metric("Stale", analysis.stale ? "yes" : "-")}
          ${metric("Warnings", (analysis.warnings || []).length)}
        </div>
        <div class="actions">
          <button class="secondary" id="reference-analyze" type="button">Analyze Reference</button>
          ${reference.reference_type === "midi" ? `<button class="secondary" id="reference-generate-slices" type="button">Generate MIDI Slices</button>` : ""}
        </div>
        ${referenceAnalysisHtml(reference, analysis, sliceManifest)}
        <pre>${escapeHtml(JSON.stringify({ summary: referenceSummary(reference), linked_project_ids: reference.linked_project_ids, derived_asset_ids: reference.derived_asset_ids }, null, 2))}</pre>
      `;
      bindAction("reference-save", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: $("reference-edit-title").value.trim(),
            description: $("reference-edit-description").value,
            tags: $("reference-edit-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
          }),
        });
        await loadReferences();
      });
      bindAction("reference-create-asset", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/create-asset`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ asset_type: defaultAssetTypeForReference(reference.reference_type) }),
        });
        await loadAssets();
        await loadReferences();
      });
      bindAction("reference-analyze", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/analyze`, { method: "POST" });
        await renderReferenceDetail(reference.reference_id);
      });
      bindAction("reference-generate-slices", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices`, { method: "POST" });
        await renderReferenceDetail(reference.reference_id);
      });
      $("reference-detail").querySelectorAll("[data-render-reference-slice-midi]").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices/${encodeURIComponent(button.dataset.sliceId)}/render-midi`, { method: "POST" });
          await renderReferenceDetail(reference.reference_id);
        });
      });
      $("reference-detail").querySelectorAll("[data-render-reference-slice-audio]").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices/${encodeURIComponent(button.dataset.sliceId)}/render-audio`, { method: "POST" });
          await renderReferenceDetail(reference.reference_id);
        });
      });
      $("reference-detail").querySelectorAll("[data-create-reference-slice-asset]").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/references/${encodeURIComponent(reference.reference_id)}/slices/${encodeURIComponent(button.dataset.sliceId)}/create-asset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: `${reference.title} ${button.dataset.sliceId}` }),
          });
          await loadAssets();
          await loadReferences();
        });
      });
      bindAction("reference-link-project", async () => {
        if (!selectedProjectId) return;
        await api(`/api/projects/${encodeURIComponent(selectedProjectId)}/references/link`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference_id: reference.reference_id }),
        });
        await loadReferences();
        await loadProjects();
      });
      bindAction("reference-unlink-project", async () => {
        if (!selectedProjectId) return;
        await api(`/api/projects/${encodeURIComponent(selectedProjectId)}/references/unlink`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference_id: reference.reference_id }),
        });
        await loadReferences();
        await loadProjects();
      });
      bindAction("reference-hide", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/hide`, { method: "POST" });
        await loadReferences();
      });
      bindAction("reference-unhide", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/unhide`, { method: "POST" });
        await loadReferences();
      });
      bindAction("reference-favorite", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/favorite`, { method: "POST" });
        await loadReferences();
      });
      bindAction("reference-unfavorite", async () => {
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/unfavorite`, { method: "POST" });
        await loadReferences();
      });
      bindAction("reference-delete", async () => {
        if (!confirm("Delete this reference?")) return;
        await api(`/api/references/${encodeURIComponent(reference.reference_id)}/delete`, { method: "POST" });
        selectedReferenceId = null;
        await loadReferences();
      });
    }

    function referenceAnalysisHtml(reference, analysis, sliceManifest) {
      const summary = analysis.summary || {};
      let body = "";
      if (reference.reference_type === "audio_wav" && analysis.status === "completed") {
        const envelope = summary.envelope || [];
        body = `
          <div class="summary-grid">
            ${metric("Duration", summary.duration_seconds ?? "-")}
            ${metric("Sample Rate", summary.sample_rate ?? "-")}
            ${metric("Channels", summary.channels ?? "-")}
            ${metric("Peak / RMS", `${summary.peak ?? "-"} / ${summary.rms ?? "-"}`)}
          </div>
          <div class="waveform">${envelope.map((point) => `<span style="height:${Math.max(2, Math.round((Number(point.peak) || 0) * 44))}px"></span>`).join("")}</div>
        `;
      } else if (reference.reference_type === "midi" && analysis.status === "completed") {
        const tracks = summary.track_summaries || [];
        body = `
          <div class="summary-grid">
            ${metric("Format", summary.format ?? "-")}
            ${metric("PPQ", summary.ppq ?? "-")}
            ${metric("Tempo", summary.tempo_bpm ?? "-")}
            ${metric("Notes", summary.note_count ?? "-")}
          </div>
          <div class="table-scroll">
            <table><thead><tr><th>Track</th><th>Role</th><th>Notes</th><th>Pitch</th></tr></thead><tbody>
              ${tracks.map((track) => `<tr><td>${escapeHtml(track.track_index)}</td><td>${escapeHtml(track.likely_role || "-")}</td><td>${escapeHtml(track.note_count || 0)}</td><td>${escapeHtml(track.pitch_min ?? "-")} - ${escapeHtml(track.pitch_max ?? "-")}</td></tr>`).join("") || `<tr><td colspan="4">No MIDI tracks.</td></tr>`}
            </tbody></table>
          </div>
          ${referenceSlicesHtml(reference, sliceManifest)}
        `;
      } else if ((reference.reference_type === "lyrics_text" || reference.reference_type === "style_note") && analysis.status === "completed") {
        body = `
          <div class="summary-grid">
            ${metric("Characters", summary.character_count ?? "-")}
            ${metric("Lines", summary.line_count ?? "-")}
            ${metric("Words", summary.word_count ?? "-")}
            ${metric("Language", summary.language_hint || "-")}
          </div>
          <pre>${escapeHtml(JSON.stringify({ keywords: summary.keywords || [], safe_excerpt: summary.safe_excerpt || "" }, null, 2))}</pre>
        `;
      } else {
        body = `<div class="empty">${escapeHtml(analysis.error || "Analysis is not available yet.")}</div>`;
      }
      return body;
    }

    function referenceSlicesHtml(reference, sliceManifest) {
      const slices = sliceManifest.slices || [];
      if (!slices.length) return `<div class="empty">No MIDI slices yet.</div>`;
      return `
        <div class="table-scroll">
          <table><thead><tr><th>Slice</th><th>Type</th><th>Start</th><th>Beats</th><th>Notes</th><th>Actions</th></tr></thead><tbody>
            ${slices.map((slice) => `
              <tr>
                <td>${escapeHtml(slice.slice_id)}</td>
                <td>${escapeHtml(slice.slice_type)}</td>
                <td>${escapeHtml(slice.start_beat)}</td>
                <td>${escapeHtml(slice.duration_beats)}</td>
                <td>${escapeHtml(slice.note_count)}</td>
                <td>
                  <button class="secondary" data-render-reference-slice-midi data-slice-id="${escapeHtml(slice.slice_id)}" type="button">Render MIDI</button>
                  ${slice.midi_url ? `<a class="button-link secondary" href="${escapeHtml(slice.midi_url)}">Download MIDI</a>` : ""}
                  <button class="secondary" data-render-reference-slice-audio data-slice-id="${escapeHtml(slice.slice_id)}" type="button">Render WAV</button>
                  ${slice.audio_url ? `<a class="button-link secondary" href="${escapeHtml(slice.audio_url)}">Download WAV</a><audio controls src="${escapeHtml(slice.audio_url)}"></audio>` : ""}
                  <button class="secondary" data-create-reference-slice-asset data-slice-id="${escapeHtml(slice.slice_id)}" type="button">Create Asset</button>
                </td>
              </tr>
            `).join("")}
          </tbody></table>
        </div>
      `;
    }

    function renderReferenceSelectors() {
      document.querySelectorAll(".reference-ref-list").forEach((container) => {
        const previous = new Map(Array.from(container.querySelectorAll("input[type='checkbox']")).map((input) => [input.value, input.checked]));
        const strengths = new Map(Array.from(container.querySelectorAll("input[type='number']")).map((input) => [input.dataset.referenceId, input.value]));
        container.innerHTML = references.slice(0, 60).map((reference) => `
          <label class="asset-ref-row">
            <input type="checkbox" value="${escapeHtml(reference.reference_id)}" ${previous.get(reference.reference_id) ? "checked" : ""}>
            <span>${escapeHtml(reference.reference_type)} · ${escapeHtml(reference.title)}</span>
            <input type="number" data-reference-id="${escapeHtml(reference.reference_id)}" min="0" max="1" step="0.1" value="${escapeHtml(strengths.get(reference.reference_id) || "0.7")}">
          </label>
        `).join("") || "<div class='empty'>No references available.</div>";
      });
    }

    function referenceRefsPayload(containerId) {
      const container = $(containerId);
      if (!container) return [];
      return Array.from(container.querySelectorAll("input[type='checkbox']:checked")).slice(0, 5).map((checkbox) => {
        const reference = references.find((item) => item.reference_id === checkbox.value) || {};
        const strengthInput = container.querySelector(`input[type='number'][data-reference-id="${CSS.escape(checkbox.value)}"]`);
        return {
          reference_id: checkbox.value,
          role: defaultReferenceRole(reference.reference_type),
          strength: Number((strengthInput && strengthInput.value) || 0.7),
        };
      });
    }

    async function referenceImportPayload() {
      const file = $("reference-file").files && $("reference-file").files[0];
      if (!file) throw new Error("Choose a reference file.");
      return {
        reference_type: $("reference-type").value,
        filename: file.name,
        title: $("reference-title").value.trim() || file.name,
        tags: $("reference-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
        content_base64: await fileToBase64(file),
      };
    }

    function fileToBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
        reader.onerror = () => reject(reader.error || new Error("File read failed."));
        reader.readAsDataURL(file);
      });
    }

    function defaultReferenceRole(referenceType) {
      return {
        audio_wav: "reference_audio",
        midi: "reference_midi",
        lyrics_text: "reference_lyrics",
        style_note: "reference_style",
      }[referenceType] || "reference";
    }

    function defaultAssetTypeForReference(referenceType) {
      return {
        midi: "motif",
        lyrics_text: "lyric_hook",
        style_note: "section_template",
      }[referenceType] || "lyric_hook";
    }

    function referenceSummary(reference) {
      return {
        description: reference.description,
        tags: reference.tags || [],
        text_excerpt: reference.text_excerpt,
        source_note: reference.source_note,
        license_note: reference.license_note,
      };
    }

    function renderAssets() {
      const list = $("asset-list");
      if (!assets.length) {
        list.innerHTML = "<div class='empty'>No assets yet.</div>";
        renderAssetSelectors();
        return;
      }
      const rows = assets.map((asset) => `
        <tr>
          <td><button class="secondary asset-open" data-asset-id="${escapeHtml(asset.asset_id)}" type="button">Open</button></td>
          <td>${escapeHtml(asset.name)}</td>
          <td>${escapeHtml(asset.asset_type)}</td>
          <td>${escapeHtml((asset.tags || []).join(", "))}</td>
          <td>${escapeHtml(asset.quality_score ?? "-")}</td>
          <td>${escapeHtml(asset.usage_count || 0)}</td>
          <td>${asset.favorite ? "yes" : "-"}</td>
        </tr>
      `).join("");
      list.innerHTML = `
        <table>
          <thead><tr><th></th><th>Name</th><th>Type</th><th>Tags</th><th>Quality</th><th>Uses</th><th>Favorite</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      list.querySelectorAll(".asset-open").forEach((button) => {
        button.addEventListener("click", async () => {
          selectedAssetId = button.dataset.assetId;
          await renderAssetDetail(selectedAssetId);
        });
      });
    }

    async function renderAssetDetail(assetId) {
      const data = await api(`/api/assets/${encodeURIComponent(assetId)}`);
      const asset = data.asset;
      const preview = asset.preview || {};
      $("asset-detail").innerHTML = `
        <div class="summary-grid">
          ${metric("Asset", asset.asset_id)}
          ${metric("Type", asset.asset_type)}
          ${metric("Quality", asset.quality_score ?? "-")}
          ${metric("Uses", asset.usage_count || 0)}
          ${metric("Key", asset.key || "-")}
          ${metric("Tempo", asset.tempo_bpm || "-")}
          ${metric("MIDI", preview.midi_status || "not_started")}
          ${metric("WAV", preview.audio_status || "not_started")}
        </div>
        <div class="grid2">
          <label>Name
            <input id="asset-name" value="${escapeHtml(asset.name)}">
          </label>
          <label>Tags
            <input id="asset-tags" value="${escapeHtml((asset.tags || []).join(", "))}">
          </label>
        </div>
        <label>Description
          <textarea id="asset-description">${escapeHtml(asset.description || "")}</textarea>
        </label>
        <div class="actions">
          <button id="asset-save" type="button">Save Metadata</button>
          <button class="secondary" id="asset-render-midi" type="button">Render Asset MIDI</button>
          <button class="secondary" id="asset-render-audio" type="button">Render Asset Audio</button>
          ${preview.midi_url ? `<a class="button-link secondary" href="${escapeHtml(preview.midi_url)}">Download Asset MIDI</a>` : ""}
          ${preview.audio_url ? `<a class="button-link secondary" href="${escapeHtml(preview.audio_url)}">Download Asset WAV</a>` : ""}
          ${asset.hidden ? `<button class="secondary" id="asset-unhide" type="button">Unhide Asset</button>` : `<button class="secondary" id="asset-hide" type="button">Hide Asset</button>`}
          ${asset.favorite ? `<button class="secondary" id="asset-unfavorite" type="button">Unfavorite</button>` : `<button class="secondary" id="asset-favorite" type="button">Favorite</button>`}
          <button class="danger" id="asset-delete" type="button">Delete Asset</button>
        </div>
        ${preview.audio_url ? `<audio class="audio-player" controls src="${escapeHtml(preview.audio_url)}"></audio>` : ""}
        <pre>${escapeHtml(JSON.stringify({ source: asset.source, content_summary: assetContentSummary(asset), content: asset.content }, null, 2))}</pre>
      `;
      bindAction("asset-save", async () => {
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: $("asset-name").value.trim(),
            description: $("asset-description").value,
            tags: $("asset-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
          }),
        });
        await loadAssets();
      });
      bindAction("asset-render-midi", async () => {
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/render-midi`, { method: "POST" });
        await loadAssets();
      });
      bindAction("asset-render-audio", async () => {
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/render-audio`, { method: "POST" });
        await loadAssets();
      });
      bindAction("asset-hide", async () => {
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/hide`, { method: "POST" });
        await loadAssets();
      });
      bindAction("asset-unhide", async () => {
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/unhide`, { method: "POST" });
        await loadAssets();
      });
      bindAction("asset-favorite", async () => {
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/favorite`, { method: "POST" });
        await loadAssets();
      });
      bindAction("asset-unfavorite", async () => {
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/unfavorite`, { method: "POST" });
        await loadAssets();
      });
      bindAction("asset-delete", async () => {
        if (!confirm("Delete this asset?")) return;
        await api(`/api/assets/${encodeURIComponent(asset.asset_id)}/delete`, { method: "POST" });
        selectedAssetId = null;
        await loadAssets();
      });
    }

    function renderAssetSelectors() {
      document.querySelectorAll(".asset-ref-list").forEach((container) => {
        const previous = new Map(Array.from(container.querySelectorAll("input[type='checkbox']")).map((input) => [input.value, input.checked]));
        const strengths = new Map(Array.from(container.querySelectorAll("input[type='number']")).map((input) => [input.dataset.assetId, input.value]));
        container.innerHTML = assets.slice(0, 60).map((asset) => `
          <label class="asset-ref-row">
            <input type="checkbox" value="${escapeHtml(asset.asset_id)}" ${previous.get(asset.asset_id) ? "checked" : ""}>
            <span>${escapeHtml(asset.asset_type)} · ${escapeHtml(asset.name)}</span>
            <input type="number" data-asset-id="${escapeHtml(asset.asset_id)}" min="0" max="1" step="0.1" value="${escapeHtml(strengths.get(asset.asset_id) || "0.7")}">
          </label>
        `).join("") || "<div class='empty'>No assets available.</div>";
      });
    }

    function assetRefsPayload(containerId) {
      const container = $(containerId);
      if (!container) return [];
      return Array.from(container.querySelectorAll("input[type='checkbox']:checked")).slice(0, 5).map((checkbox) => {
        const asset = assets.find((item) => item.asset_id === checkbox.value) || {};
        const strengthInput = container.querySelector(`input[type='number'][data-asset-id="${CSS.escape(checkbox.value)}"]`);
        return {
          asset_id: checkbox.value,
          role: defaultAssetRole(asset.asset_type),
          strength: Number((strengthInput && strengthInput.value) || 0.7),
        };
      });
    }

    function defaultAssetRole(assetType) {
      return {
        motif: "motif_reference",
        chord_progression: "chord_reference",
        drum_pattern: "drum_reference",
        bass_pattern: "bass_reference",
      }[assetType] || "reference";
    }

    function assetContentSummary(asset) {
      const content = asset.content || {};
      return {
        note_count: Array.isArray(content.notes) ? content.notes.length : 0,
        chord_count: Array.isArray(content.chords) ? content.chords.length : 0,
        section_name: content.section_name || "",
        track_name: content.track_name || "",
      };
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

    function releasePayload() {
      return {
        name: $("release-name").value.trim() || "Untitled Release",
        release_type: $("release-type").value || "demo_pack",
        primary_artist: $("release-primary-artist").value.trim(),
        catalog_id: $("release-catalog-id").value.trim(),
        language: $("release-language").value.trim(),
        notes: $("release-notes").value.trim(),
      };
    }

    function portfolioAuditPayload() {
      const releaseIds = $("portfolio-audit-release-ids").value
        .split(/[,\n]/)
        .map((item) => item.trim())
        .filter(Boolean);
      const payload = {
        name: $("portfolio-audit-name").value.trim() || "Release Portfolio Audit",
        release_ids: releaseIds,
        include_hidden: $("portfolio-audit-include-hidden-releases").checked,
        include_archived: $("portfolio-audit-include-archived-releases").checked,
        require_reviewer_packs: $("portfolio-audit-require-reviewer-packs").checked,
        require_audit: $("portfolio-audit-require-audit").checked,
        require_archive: $("portfolio-audit-require-archive").checked,
      };
      const maxReleases = Number($("portfolio-audit-max-releases").value || 0);
      if (maxReleases > 0) payload.max_releases = maxReleases;
      return payload;
    }

    function renderReleases() {
      const list = $("release-list");
      if (!releases.length) {
        list.innerHTML = "<div class='empty'>No releases yet.</div>";
        return;
      }
      const rows = releases.map((release) => `
        <tr class="${release.release_id === selectedReleaseId ? "active" : ""}">
          <td><button class="secondary release-open" data-release-id="${escapeHtml(release.release_id)}" type="button">Open</button></td>
          <td>${escapeHtml(release.name || release.release_id)}</td>
          <td>${escapeHtml(release.release_type || "-")}</td>
          <td><span class="status ${escapeHtml(release.status || "")}">${escapeHtml(release.status || "-")}</span></td>
          <td>${escapeHtml(release.track_count || 0)}</td>
          <td>${escapeHtml((release.qa_summary || {}).status || "missing")}</td>
          <td>${escapeHtml((release.signoff_summary || {}).status || "not_signed")}</td>
        </tr>
      `).join("");
      list.innerHTML = `
        <table>
          <thead><tr><th></th><th>Name</th><th>Type</th><th>Status</th><th>Tracks</th><th>QA</th><th>Signoff</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      list.querySelectorAll(".release-open").forEach((button) => {
        button.addEventListener("click", async () => {
          selectedReleaseId = button.dataset.releaseId;
          renderReleases();
          await renderReleaseDetail(selectedReleaseId);
        });
      });
    }

    function renderPortfolioAudits() {
      const list = $("portfolio-audit-list");
      if (!portfolioAudits.length) {
        list.innerHTML = "<div class='empty'>No Portfolio Audits yet.</div>";
        return;
      }
      const rows = portfolioAudits.map((portfolio) => `
        <tr class="${portfolio.portfolio_id === selectedPortfolioAuditId ? "active" : ""}">
          <td><button class="secondary portfolio-audit-open" data-portfolio-id="${escapeHtml(portfolio.portfolio_id)}" type="button">Open</button></td>
          <td>${escapeHtml(portfolio.name || portfolio.portfolio_id)}</td>
          <td><span class="status ${escapeHtml(portfolio.status || "")}">${escapeHtml(portfolio.status || "-")}</span></td>
          <td>${escapeHtml(portfolio.source_hash ? "current" : "draft")}</td>
          <td>${escapeHtml(portfolio.latest_export_manifest_hash ? "built" : "missing")}</td>
        </tr>
      `).join("");
      list.innerHTML = `
        <table>
          <thead><tr><th></th><th>Name</th><th>Status</th><th>Source</th><th>Export</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      list.querySelectorAll(".portfolio-audit-open").forEach((button) => {
        button.addEventListener("click", async () => {
          selectedPortfolioAuditId = button.dataset.portfolioId;
          renderPortfolioAudits();
          await renderPortfolioAuditDetail(selectedPortfolioAuditId);
        });
      });
    }

    async function renderPortfolioAuditDetail(portfolioId) {
      const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}`);
      const portfolio = data.portfolio || {};
      let reportData = { report: data.report || {}, summary: data.summary || {} };
      let trendData = { trend_report: {}, summary: {} };
      let riskData = { risk_register: {}, summary: {} };
      try { reportData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/report`); } catch (err) {}
      try { trendData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/trends`); } catch (err) {}
      try { riskData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/risks`); } catch (err) {}
      let governanceData = { queues: [], summary: {} };
      try { governanceData = await api(`/api/release-portfolio-governance-queues?portfolio_id=${encodeURIComponent(portfolioId)}`); } catch (err) {}
      let governanceAuditData = { report: {}, summary: {} };
      try { governanceAuditData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit`); } catch (err) {}
      let governanceReviewerData = { report: {}, summary: {} };
      try { governanceReviewerData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack`); } catch (err) {}
      let governanceFinalBoardData = { report: {}, summary: {}, signoff_summary: {} };
      try { governanceFinalBoardData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board`); } catch (err) {}
      let governanceEvidenceVaultData = { report: {}, summary: {} };
      try { governanceEvidenceVaultData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault`); } catch (err) {}
      let governanceAttestationData = { report: {}, summary: {}, certificate: {} };
      try { governanceAttestationData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation`); } catch (err) {}
      let governanceAttestationRegistryData = { registry: {}, report: {}, summary: {} };
      try { governanceAttestationRegistryData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry`); } catch (err) {}
      let governanceAttestationPortalData = { report: {}, summary: {} };
      try { governanceAttestationPortalData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal`); } catch (err) {}
      let governanceAttestationPortalReviewData = { review_pack: {}, summary: {}, responses: [] };
      try { governanceAttestationPortalReviewData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review`); } catch (err) {}
      let governanceAttestationAcceptedEvidenceData = { accepted_evidence: {}, summary: {}, verification: {} };
      try { governanceAttestationAcceptedEvidenceData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence`); } catch (err) {}
      let governanceAttestationTransparencyData = { feed: {}, summary: {}, verification: {} };
      try { governanceAttestationTransparencyData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency`); } catch (err) {}
      let governanceAttestationTransparencyAcknowledgementData = { pack: {}, summary: {}, evidence_summary: {}, responses: [] };
      try { governanceAttestationTransparencyAcknowledgementData = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement`); } catch (err) {}
      const report = reportData.report || {};
      const summary = report.summary || reportData.summary || {};
      const governanceAuditSummary = governanceAuditData.summary || {};
      const governanceReviewerSummary = governanceReviewerData.summary || {};
      const governanceFinalBoardSummary = governanceFinalBoardData.summary || {};
      const governanceFinalBoardSignoff = governanceFinalBoardData.signoff_summary || {};
      const governanceEvidenceVaultSummary = governanceEvidenceVaultData.summary || {};
      const governanceAttestationSummary = governanceAttestationData.summary || {};
      const governanceAttestationCertificate = governanceAttestationData.certificate || {};
      const governanceAttestationRegistrySummary = governanceAttestationRegistryData.summary || {};
      const governanceAttestationRegistry = governanceAttestationRegistryData.registry || {};
      const governanceAttestationPortalSummary = governanceAttestationPortalData.summary || {};
      const governanceAttestationPortalReviewSummary = governanceAttestationPortalReviewData.summary || {};
      const governanceAttestationPortalReviewResponses = governanceAttestationPortalReviewData.responses || [];
      const governanceAttestationAcceptedEvidenceSummary = governanceAttestationAcceptedEvidenceData.summary || {};
      const governanceAttestationTransparencySummary = governanceAttestationTransparencyData.summary || {};
      const governanceAttestationTransparencyAcknowledgementSummary = governanceAttestationTransparencyAcknowledgementData.summary || {};
      const governanceAttestationTransparencyAcknowledgementEvidenceSummary = governanceAttestationTransparencyAcknowledgementData.evidence_summary || {};
      const governanceAttestationTransparencyAcknowledgementResponses = governanceAttestationTransparencyAcknowledgementData.responses || [];
      const governanceAttestationRegistryRows = (governanceAttestationRegistry.entries || []).slice(-6).reverse().map((entry) => `
        <tr>
          <td>${escapeHtml(entry.entry_id || "-")}</td>
          <td><span class="status ${escapeHtml(entry.status || "")}">${escapeHtml(entry.status || "-")}</span></td>
          <td>${escapeHtml(entry.certificate_id || "-")}</td>
          <td>${escapeHtml(((entry.source || {}).attestation_zip_sha256 || "").slice(0, 12) || "-")}</td>
          <td>
            <button class="secondary portfolio-governance-attestation-registry-publish" data-entry-id="${escapeHtml(entry.entry_id || "")}" type="button">Publish</button>
            <button class="secondary portfolio-governance-attestation-registry-revoke" data-entry-id="${escapeHtml(entry.entry_id || "")}" type="button">Revoke</button>
          </td>
        </tr>
      `).join("");
      const score = report.risk_score || {};
      const stale = Boolean(reportData.stale || (reportData.summary || {}).stale || (data.summary || {}).stale);
      const trend = trendData.trend_report || {};
      const risks = riskData.risk_register || {};
      const selection = portfolio.selection || {};
      const releaseRows = (report.release_readiness_ranking || []).map((item) => `
        <tr>
          <td>${escapeHtml(item.release_id || "-")}</td>
          <td>${escapeHtml(item.release_name || "-")}</td>
          <td><span class="status ${escapeHtml(item.readiness_status || "")}">${escapeHtml(item.readiness_status || "-")}</span></td>
          <td>${escapeHtml(item.coverage_score ?? "-")}</td>
          <td>${escapeHtml(item.risk_score ?? "-")}</td>
          <td>${escapeHtml(item.recommendation || "-")}</td>
        </tr>
      `).join("");
      const riskRows = (risks.risks || []).slice(0, 12).map((risk) => `
        <tr>
          <td>${escapeHtml(risk.severity || "-")}</td>
          <td>${escapeHtml(risk.category || "-")}</td>
          <td class="wrap-cell">${escapeHtml(risk.title || "-")}</td>
          <td>${escapeHtml((risk.release_ids || []).join(", ") || "-")}</td>
        </tr>
      `).join("");
      const recommendationRows = (report.recommendations || []).slice(0, 12).map((item) => `
        <tr>
          <td>${escapeHtml(item.severity || "-")}</td>
          <td>${escapeHtml(item.category || "-")}</td>
          <td class="wrap-cell">${escapeHtml(item.reason || "-")}</td>
          <td class="wrap-cell">${escapeHtml(item.suggested_action || "-")}</td>
        </tr>
      `).join("");
      const trendRows = (trend.trend_findings || []).slice(0, 12).map((item) => `
        <tr>
          <td>${escapeHtml(item.category || "-")}</td>
          <td>${escapeHtml(item.status || "-")}</td>
          <td class="wrap-cell">${escapeHtml(item.message || item.title || "-")}</td>
        </tr>
      `).join("");
      const governanceQueues = governanceData.queues || [];
      const governanceRows = governanceQueues.slice(0, 8).map((queue) => {
        const execution = queue.execution || {};
        return `
          <tr>
            <td>${escapeHtml(queue.queue_id || "-")}</td>
            <td><span class="status ${escapeHtml(queue.status || "")}">${escapeHtml(queue.status || "-")}</span></td>
            <td>${escapeHtml(execution.total_items ?? "-")}</td>
            <td>${escapeHtml(execution.safe_action_count ?? "-")}</td>
            <td>${escapeHtml(execution.manual_required_count ?? "-")}</td>
            <td>${execution.post_portfolio_refresh_required ? "yes" : "-"}</td>
            <td>
              <button class="secondary portfolio-governance-run-safe" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Run Safe</button>
              <button class="secondary portfolio-governance-export" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Export</button>
              <button class="secondary portfolio-governance-zip" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">ZIP</button>
              <button class="secondary portfolio-governance-verify" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Verify</button>
              <a class="button-link secondary" href="/api/release-portfolio-governance-queues/${encodeURIComponent(queue.queue_id)}/download">Download</a>
              <button class="secondary portfolio-governance-signoff" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Signoff</button>
              <button class="secondary portfolio-governance-force-signoff" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Force Signoff</button>
              <button class="secondary portfolio-governance-cr" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">New Change Request</button>
              <button class="secondary portfolio-governance-reset" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Reset Signoff</button>
              <button class="secondary portfolio-governance-archive-export" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Archive Export</button>
              <button class="secondary portfolio-governance-archive-zip" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Archive ZIP</button>
              <button class="secondary portfolio-governance-archive-verify" data-queue-id="${escapeHtml(queue.queue_id)}" type="button">Archive Verify</button>
              <a class="button-link secondary" href="/api/release-portfolio-governance-queues/${encodeURIComponent(queue.queue_id)}/archive.zip">Archive Download</a>
            </td>
          </tr>
        `;
      }).join("");
      $("portfolio-audit-detail").innerHTML = `
        <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
          <span>Release Portfolio Audit · ${escapeHtml(portfolio.name || portfolio.portfolio_id)}</span>
          <span class="status ${escapeHtml(report.status || portfolio.status || "")}">${escapeHtml(report.status || portfolio.status || "draft")}</span>
        </div>
        <div class="summary-grid">
          ${metric("Portfolio", portfolio.portfolio_id || "-")}
          ${metric("Releases", summary.release_count || 0)}
          ${metric("Risk Score", score.score ?? "-")}
          ${metric("Risk Status", score.status || "-")}
          ${metric("Blockers", summary.blocker_count || 0)}
          ${metric("Warnings", summary.warning_count || 0)}
          ${metric("Stale", stale ? "yes" : "-")}
          ${metric("Reviewer Packs", selection.require_reviewer_packs ? "required" : "optional")}
          ${metric("Archive", selection.require_archive ? "required" : "optional")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-audit-refresh" type="button">Refresh Portfolio Audit</button>
          <button class="secondary" id="portfolio-audit-export" type="button">Export Portfolio Audit</button>
          <button class="secondary" id="portfolio-audit-zip" type="button">Build Portfolio ZIP</button>
          <button class="secondary" id="portfolio-audit-verify" type="button">Verify Portfolio ZIP</button>
          <button class="danger" id="portfolio-audit-archive" type="button">Archive Portfolio Audit</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/download">Download Portfolio ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Release Readiness Ranking</span></div>
        <table>
          <thead><tr><th>Release</th><th>Name</th><th>Readiness</th><th>Coverage</th><th>Risk</th><th>Recommendation</th></tr></thead>
          <tbody>${releaseRows || "<tr><td colspan='6'>Refresh Portfolio Audit to build release ranking.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Portfolio Risk Register</span></div>
        <table>
          <thead><tr><th>Severity</th><th>Category</th><th>Risk</th><th>Releases</th></tr></thead>
          <tbody>${riskRows || "<tr><td colspan='4'>No portfolio risks.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Deterministic Recommendations</span></div>
        <table>
          <thead><tr><th>Severity</th><th>Category</th><th>Reason</th><th>Action</th></tr></thead>
          <tbody>${recommendationRows || "<tr><td colspan='4'>No portfolio recommendations.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Portfolio Trend Report</span></div>
        <table>
          <thead><tr><th>Category</th><th>Status</th><th>Finding</th></tr></thead>
          <tbody>${trendRows || "<tr><td colspan='3'>No trend findings.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Portfolio Governance Queue</span></div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-create" type="button">Create Governance Queue</button>
          <span id="portfolio-governance-message" class="message"></span>
        </div>
        <table>
          <thead><tr><th>Queue</th><th>Status</th><th>Items</th><th>Safe</th><th>Manual</th><th>Refresh Needed</th><th>Safe Actions</th></tr></thead>
          <tbody>${governanceRows || "<tr><td colspan='7'>No Governance Queues yet.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Governance Closeout</span></div>
        <div class="summary-grid">
          ${metric("Signoff", "queue-level")}
          ${metric("Archive", "verifiable")}
          ${metric("Change Control", "approved CR required")}
        </div>
        <div class="panel-title subhead"><span>Portfolio Governance Audit Ledger</span></div>
        <div class="summary-grid">
          ${metric("Audit", governanceAuditSummary.status || "missing")}
          ${metric("Entries", governanceAuditSummary.entry_count || 0)}
          ${metric("Signed Queues", governanceAuditSummary.signed_queue_count || 0)}
          ${metric("Archive Verified", governanceAuditSummary.archive_verified_count || 0)}
          ${metric("Blockers", governanceAuditSummary.blocker_count || 0)}
          ${metric("Warnings", governanceAuditSummary.warning_count || 0)}
          ${metric("Stale", governanceAuditSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-audit-refresh" type="button">Refresh Governance Audit</button>
          <button class="secondary" id="portfolio-governance-audit-export" type="button">Export Governance Audit</button>
          <button class="secondary" id="portfolio-governance-audit-zip" type="button">Build Governance Audit ZIP</button>
          <button class="secondary" id="portfolio-governance-audit-verify" type="button">Verify Governance Audit ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-audit.zip">Download Governance Audit ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Portfolio Governance Reviewer Pack</span></div>
        <div class="summary-grid">
          ${metric("Reviewer Pack", governanceReviewerSummary.status || "missing")}
          ${metric("Audit", governanceReviewerSummary.audit_status || "-")}
          ${metric("Audit Verified", governanceReviewerSummary.audit_package_verification_status || "-")}
          ${metric("Queues", governanceReviewerSummary.queue_count || 0)}
          ${metric("Signed Queues", governanceReviewerSummary.signed_queue_count || 0)}
          ${metric("Archive Verified", governanceReviewerSummary.archive_verified_count || 0)}
          ${metric("Blockers", governanceReviewerSummary.blocker_count || 0)}
          ${metric("Warnings", governanceReviewerSummary.warning_count || 0)}
          ${metric("Stale", governanceReviewerSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-reviewer-refresh" type="button">Refresh Governance Reviewer Pack</button>
          <button class="secondary" id="portfolio-governance-reviewer-export" type="button">Export Governance Reviewer Pack</button>
          <button class="secondary" id="portfolio-governance-reviewer-zip" type="button">Build Governance Reviewer ZIP</button>
          <button class="secondary" id="portfolio-governance-reviewer-verify" type="button">Verify Governance Reviewer ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-reviewer-pack.zip">Download Governance Reviewer ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Portfolio Governance Final Board</span></div>
        <div class="summary-grid">
          ${metric("Final Board", governanceFinalBoardSummary.status || "missing")}
          ${metric("Signoff", governanceFinalBoardSignoff.status || "-")}
          ${metric("Reviewer Response", governanceFinalBoardSummary.reviewer_response_status || "-")}
          ${metric("Reviewer Pack", governanceFinalBoardSummary.reviewer_pack_verification_status || "-")}
          ${metric("Audit", governanceFinalBoardSummary.audit_verification_status || "-")}
          ${metric("Archive Verified", governanceFinalBoardSummary.archive_verified_count || 0)}
          ${metric("Blockers", governanceFinalBoardSummary.blocker_count || 0)}
          ${metric("Warnings", governanceFinalBoardSummary.warning_count || 0)}
          ${metric("Stale", governanceFinalBoardSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-final-board-refresh" type="button">Refresh Final Board</button>
          <button class="secondary" id="portfolio-governance-final-board-import-accepted" type="button">Import Accepted Response</button>
          <button class="secondary" id="portfolio-governance-final-board-signoff" type="button">Final Board Signoff</button>
          <button class="secondary" id="portfolio-governance-final-board-cr" type="button">New Final Board Change Request</button>
          <button class="secondary" id="portfolio-governance-final-board-reset" type="button">Reset Final Board Signoff</button>
          <button class="secondary" id="portfolio-governance-final-board-export" type="button">Export Final Board Archive</button>
          <button class="secondary" id="portfolio-governance-final-board-zip" type="button">Build Final Board ZIP</button>
          <button class="secondary" id="portfolio-governance-final-board-verify" type="button">Verify Final Board ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-final-board.zip">Download Final Board ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Governance Evidence Vault</span></div>
        <div class="summary-grid">
          ${metric("Evidence Vault", governanceEvidenceVaultSummary.status || "missing")}
          ${metric("Nested Required", governanceEvidenceVaultSummary.required_package_count || 0)}
          ${metric("Nested Current", governanceEvidenceVaultSummary.current_required_package_count || 0)}
          ${metric("Archives", governanceEvidenceVaultSummary.archive_package_count || 0)}
          ${metric("Queues", governanceEvidenceVaultSummary.queue_package_count || 0)}
          ${metric("Verification", governanceEvidenceVaultSummary.verification_status || "-")}
          ${metric("Deep Verify", governanceEvidenceVaultSummary.deep_verification_status || "-")}
          ${metric("Blockers", governanceEvidenceVaultSummary.blocker_count || 0)}
          ${metric("Warnings", governanceEvidenceVaultSummary.warning_count || 0)}
          ${metric("Stale", governanceEvidenceVaultSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-vault-refresh" type="button">Refresh Evidence Vault</button>
          <button class="secondary" id="portfolio-governance-vault-export" type="button">Export Evidence Vault</button>
          <button class="secondary" id="portfolio-governance-vault-zip" type="button">Build Evidence Vault ZIP</button>
          <button class="secondary" id="portfolio-governance-vault-verify" type="button">Verify Evidence Vault ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-evidence-vault.zip">Download Evidence Vault ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Governance Public Attestation</span></div>
        <div class="summary-grid">
          ${metric("Public Attestation", governanceAttestationSummary.status || "missing")}
          ${metric("Profile", governanceAttestationSummary.profile || "public_summary")}
          ${metric("Certificate", governanceAttestationSummary.certificate_id || governanceAttestationCertificate.certificate_id || "-")}
          ${metric("Vault Verify", governanceAttestationSummary.vault_verification_status || governanceAttestationSummary.verification_status || "-")}
          ${metric("Deep Verify", governanceAttestationSummary.deep_verification_status || "-")}
          ${metric("Signed Queues", governanceAttestationSummary.signed_queue_count || 0)}
          ${metric("Blockers", governanceAttestationSummary.blocker_count || 0)}
          ${metric("Warnings", governanceAttestationSummary.warning_count || 0)}
          ${metric("Stale", governanceAttestationSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-attestation-refresh" type="button">Refresh Public Attestation</button>
          <button class="secondary" id="portfolio-governance-attestation-export" type="button">Export Public Attestation</button>
          <button class="secondary" id="portfolio-governance-attestation-zip" type="button">Build Public Attestation ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-verify" type="button">Verify Public Attestation ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation.zip">Download Public Attestation ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Governance Attestation Registry</span></div>
        <div class="summary-grid">
          ${metric("Registry", governanceAttestationRegistrySummary.status || "missing")}
          ${metric("Current Entry", governanceAttestationRegistrySummary.current_entry_id || "-")}
          ${metric("Entries", governanceAttestationRegistrySummary.entry_count || 0)}
          ${metric("Published", governanceAttestationRegistrySummary.published_count || 0)}
          ${metric("Revoked", governanceAttestationRegistrySummary.revoked_count || 0)}
          ${metric("Superseded", governanceAttestationRegistrySummary.superseded_count || 0)}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-attestation-registry-register-current" type="button">Register Current Attestation</button>
          <button class="secondary" id="portfolio-governance-attestation-registry-refresh" type="button">Refresh Registry Report</button>
          <button class="secondary" id="portfolio-governance-attestation-registry-export" type="button">Export Registry</button>
          <button class="secondary" id="portfolio-governance-attestation-registry-zip" type="button">Build Registry ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-registry-verify" type="button">Verify Registry ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-registry.zip">Download Registry ZIP</a>
        </div>
        <table class="compact-table">
          <thead><tr><th>Entry</th><th>Status</th><th>Certificate</th><th>ZIP SHA</th><th>Actions</th></tr></thead>
          <tbody>${governanceAttestationRegistryRows || '<tr><td colspan="5">No registry entries.</td></tr>'}</tbody>
        </table>
        <div class="panel-title subhead"><span>Governance Attestation Portal Snapshot</span></div>
        <div class="summary-grid">
          ${metric("Portal", governanceAttestationPortalSummary.status || "missing")}
          ${metric("Current Entry", governanceAttestationPortalSummary.current_entry_id || "-")}
          ${metric("Current Certificate", governanceAttestationPortalSummary.current_certificate_id || "-")}
          ${metric("Registry", governanceAttestationPortalSummary.registry_status || "-")}
          ${metric("Attestation", governanceAttestationPortalSummary.attestation_status || "-")}
          ${metric("Blockers", governanceAttestationPortalSummary.blocker_count || 0)}
          ${metric("Warnings", governanceAttestationPortalSummary.warning_count || 0)}
          ${metric("Stale", governanceAttestationPortalSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-attestation-portal-refresh" type="button">Refresh Portal</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-export" type="button">Export Portal</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-zip" type="button">Build Portal ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-verify" type="button">Verify Portal ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-portal.zip">Download Portal ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Portal Review Response</span></div>
        <div class="summary-grid">
          ${metric("Review Pack", governanceAttestationPortalReviewSummary.status || "missing")}
          ${metric("Pack ID", governanceAttestationPortalReviewSummary.review_pack_id || "-")}
          ${metric("Current Entry", governanceAttestationPortalReviewSummary.current_entry_id || "-")}
          ${metric("Responses", governanceAttestationPortalReviewResponses.length || 0)}
          ${metric("Stale", governanceAttestationPortalReviewSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-attestation-portal-review-refresh-pack" type="button">Refresh Review Pack</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-review-export-pack" type="button">Export Review Pack</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-review-zip-pack" type="button">Build Review Pack ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-review-verify-pack" type="button">Verify Review Pack</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-review-import-response" type="button">Import Response</button>
          <button class="secondary" id="portfolio-governance-attestation-portal-review-create-change-request" type="button">Create Change Request</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-portal-review-pack.zip">Download Review Pack ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Accepted Evidence</span></div>
        <div class="summary-grid">
          ${metric("Evidence", governanceAttestationAcceptedEvidenceSummary.status || "missing")}
          ${metric("External Review", governanceAttestationAcceptedEvidenceSummary.external_review_status || "-")}
          ${metric("Accepted Evidence", governanceAttestationAcceptedEvidenceSummary.accepted_evidence_id || "-")}
          ${metric("Response", governanceAttestationAcceptedEvidenceSummary.response_id || "-")}
          ${metric("Verification", governanceAttestationAcceptedEvidenceSummary.accepted_evidence_verification_status || governanceAttestationAcceptedEvidenceSummary.verification_status || "-")}
          ${metric("Stale", governanceAttestationAcceptedEvidenceSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-refresh" type="button">Refresh Accepted Evidence</button>
          <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-export" type="button">Export Accepted Evidence</button>
          <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-zip" type="button">Build Accepted Evidence ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-verify" type="button">Verify Accepted Evidence ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-accepted-evidence-archive" type="button">Archive Accepted Evidence</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-accepted-evidence.zip">Download Accepted Evidence ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Transparency Feed</span></div>
        <div class="summary-grid">
          ${metric("Feed", governanceAttestationTransparencySummary.status || "missing")}
          ${metric("Current Entry", governanceAttestationTransparencySummary.current_entry_id || "-")}
          ${metric("External Review", governanceAttestationTransparencySummary.external_review_status || "-")}
          ${metric("Events", governanceAttestationTransparencySummary.event_count ?? 0)}
          ${metric("Notices", governanceAttestationTransparencySummary.notice_count ?? 0)}
          ${metric("Verification", governanceAttestationTransparencySummary.verification_status || "-")}
          ${metric("Stale", governanceAttestationTransparencySummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-attestation-transparency-refresh" type="button">Refresh Transparency</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-export" type="button">Export Transparency</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-zip" type="button">Build Transparency ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-verify" type="button">Verify Transparency ZIP</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-transparency.zip">Download Transparency ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Transparency Acknowledgement</span></div>
        <div class="summary-grid">
          ${metric("Pack", governanceAttestationTransparencyAcknowledgementSummary.status || "missing")}
          ${metric("Pack ID", governanceAttestationTransparencyAcknowledgementSummary.pack_id || "-")}
          ${metric("Responses", governanceAttestationTransparencyAcknowledgementResponses.length || 0)}
          ${metric("Evidence", governanceAttestationTransparencyAcknowledgementEvidenceSummary.status || "missing")}
          ${metric("External Review", governanceAttestationTransparencyAcknowledgementEvidenceSummary.external_review_status || "-")}
          ${metric("Acknowledgement", governanceAttestationTransparencyAcknowledgementEvidenceSummary.acknowledgement_id || "-")}
          ${metric("Stale", governanceAttestationTransparencyAcknowledgementSummary.stale || governanceAttestationTransparencyAcknowledgementEvidenceSummary.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-refresh-pack" type="button">Refresh Ack Pack</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-export-pack" type="button">Export Ack Pack</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-zip-pack" type="button">Build Ack Pack ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-verify-pack" type="button">Verify Ack Pack</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-import-response" type="button">Import Ack Response</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-refresh-evidence" type="button">Refresh Ack Evidence</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-export-evidence" type="button">Export Ack Evidence</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-zip-evidence" type="button">Build Ack Evidence ZIP</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-verify-evidence" type="button">Verify Ack Evidence</button>
          <button class="secondary" id="portfolio-governance-attestation-transparency-ack-create-change-request" type="button">Create Ack Change Request</button>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-transparency-acknowledgement-pack.zip">Download Ack Pack ZIP</a>
          <a class="button-link secondary" href="/api/release-portfolio-audits/${encodeURIComponent(portfolio.portfolio_id)}/governance-attestation-transparency-acknowledgement-evidence.zip">Download Ack Evidence ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Public Trust Center</span></div>
        <div class="summary-grid">
          ${metric("Delivery", "Release / Distribution / Submission / Operations")}
          ${metric("Requirement", "Current public proof + delivery sidecars")}
        </div>
        <div class="actions">
          <button class="secondary" id="public-trust-center-refresh" type="button">Refresh Trust Center</button>
          <button class="secondary" id="public-trust-center-export" type="button">Export Trust Center</button>
          <button class="secondary" id="public-trust-center-zip" type="button">Build Trust Center ZIP</button>
          <button class="secondary" id="public-trust-center-verify" type="button">Verify Trust Center ZIP</button>
          <button class="secondary" id="public-trust-center-archive" type="button">Archive Trust Center</button>
          <a class="button-link secondary" href="/api/public-trust-centers/ptc-default.zip">Download Trust Center ZIP</a>
          <button class="secondary" id="public-trust-center-anchor-register" type="button">Register Anchor</button>
          <button class="secondary" id="public-trust-center-anchor-export" type="button">Export Anchor Registry</button>
          <button class="secondary" id="public-trust-center-anchor-zip" type="button">Build Anchor Registry ZIP</button>
          <button class="secondary" id="public-trust-center-anchor-verify" type="button">Verify Anchor Registry</button>
          <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/anchor-registry/download">Download Anchor Registry ZIP</a>
          <button class="secondary" id="public-trust-center-anchor-transparency-refresh" type="button">Refresh Anchor Transparency</button>
          <button class="secondary" id="public-trust-center-anchor-transparency-export" type="button">Export Anchor Transparency</button>
          <button class="secondary" id="public-trust-center-anchor-transparency-zip" type="button">Build Anchor Transparency ZIP</button>
          <button class="secondary" id="public-trust-center-anchor-transparency-verify" type="button">Verify Anchor Transparency</button>
          <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/anchor-transparency/download">Download Anchor Transparency ZIP</a>
          <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/anchor-transparency/checkpoint">Download Anchor Checkpoint</a>
          <button class="secondary" id="public-trust-center-distribution-kit-refresh" type="button">Refresh Distribution Kit</button>
          <button class="secondary" id="public-trust-center-distribution-kit-export" type="button">Export Distribution Kit</button>
          <button class="secondary" id="public-trust-center-distribution-kit-zip" type="button">Build Distribution Kit ZIP</button>
          <button class="secondary" id="public-trust-center-distribution-kit-verify" type="button">Verify Distribution Kit</button>
          <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/distribution-kit/download">Download Distribution Kit ZIP</a>
          <button class="secondary" id="public-trust-center-distribution-kit-acceptance-template" type="button">Create Kit Acceptance Template</button>
          <button class="secondary" id="public-trust-center-distribution-kit-accepted-evidence-export" type="button">Export Kit Accepted Evidence</button>
          <button class="secondary" id="public-trust-center-distribution-kit-accepted-evidence-zip" type="button">Build Kit Accepted Evidence ZIP</button>
          <button class="secondary" id="public-trust-center-distribution-kit-accepted-evidence-verify" type="button">Verify Kit Accepted Evidence</button>
          <button class="secondary" id="public-trust-center-acceptance-board-refresh" type="button">Refresh Acceptance Board</button>
          <button class="secondary" id="public-trust-center-acceptance-board-export" type="button">Export Acceptance Board</button>
          <button class="secondary" id="public-trust-center-acceptance-board-zip" type="button">Build Acceptance Board ZIP</button>
          <button class="secondary" id="public-trust-center-acceptance-board-verify" type="button">Verify Acceptance Board</button>
          <button class="secondary" id="public-trust-center-acceptance-board-signoff-draft" type="button">Create Board Signoff Draft</button>
          <button class="secondary" id="public-trust-center-acceptance-board-signoff" type="button">Sign Acceptance Board</button>
          <button class="secondary" id="public-trust-center-acceptance-board-signoff-archive-export" type="button">Export Board Signoff Archive</button>
          <button class="secondary" id="public-trust-center-acceptance-board-signoff-archive-zip" type="button">Build Board Signoff Archive ZIP</button>
          <button class="secondary" id="public-trust-center-acceptance-board-signoff-archive-verify" type="button">Verify Board Signoff Archive</button>
          <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/acceptance-board/download">Download Acceptance Board ZIP</a>
          <a class="button-link secondary" href="/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/download">Download Board Signoff Archive ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Trust Operations Hub</span></div>
        <div class="summary-grid">
          ${metric("Scope", "Release / Distribution / Submission / Operations / PTC / Publication")}
          ${metric("Evidence", "Readiness matrix + blocker register + verification index")}
        </div>
        <div class="actions">
          <button class="secondary" id="trust-operations-hub-refresh" type="button">Refresh Hub</button>
          <button class="secondary" id="trust-operations-hub-export" type="button">Export Hub</button>
          <button class="secondary" id="trust-operations-hub-zip" type="button">Build Hub ZIP</button>
          <button class="secondary" id="trust-operations-hub-verify" type="button">Verify Hub ZIP</button>
          <button class="secondary" id="trust-operations-hub-signoff" type="button">Sign Hub</button>
          <button class="secondary" id="trust-operations-hub-change-request" type="button">Create Hub Change Request</button>
          <button class="secondary" id="trust-operations-hub-reset" type="button">Reset Hub Signoff</button>
          <a class="button-link secondary" href="/api/trust-operations/hubs/default.zip">Download Hub ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Trust Operations Runbook</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-runbook-create" type="button">Create Runbook</button>
          <button class="secondary" id="trust-operations-runbook-run-safe" type="button">Run Safe Actions</button>
          <button class="secondary" id="trust-operations-runbook-export" type="button">Export Runbook</button>
          <button class="secondary" id="trust-operations-runbook-zip" type="button">Build Runbook ZIP</button>
          <button class="secondary" id="trust-operations-runbook-verify" type="button">Verify Runbook</button>
        </div>
        <div class="panel-title subhead"><span>Trust Operations Incidents</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-incidents-refresh" type="button">Refresh Incidents</button>
          <button class="secondary" id="trust-operations-incidents-triage" type="button">Triage Incident</button>
          <button class="secondary" id="trust-operations-incidents-plan" type="button">Create Remediation Plan</button>
          <button class="secondary" id="trust-operations-incidents-evidence" type="button">Add Evidence</button>
          <button class="secondary" id="trust-operations-incidents-close" type="button">Close Incident</button>
          <button class="secondary" id="trust-operations-incidents-export" type="button">Export Incident Board</button>
          <button class="secondary" id="trust-operations-incidents-zip" type="button">Build Incident ZIP</button>
          <button class="secondary" id="trust-operations-incidents-verify" type="button">Verify Incident ZIP</button>
        </div>
        <div class="panel-title subhead"><span>Trust Operations Knowledge</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-knowledge-refresh" type="button">Refresh Knowledge</button>
          <button class="secondary" id="trust-operations-knowledge-create-guard" type="button">Create Regression Guard</button>
          <button class="secondary" id="trust-operations-knowledge-run-guards" type="button">Run Regression Guards</button>
          <button class="secondary" id="trust-operations-knowledge-recurrence" type="button">Refresh Recurrence</button>
          <button class="secondary" id="trust-operations-knowledge-export" type="button">Export Knowledge</button>
          <button class="secondary" id="trust-operations-knowledge-zip" type="button">Build Knowledge ZIP</button>
          <button class="secondary" id="trust-operations-knowledge-verify" type="button">Verify Knowledge ZIP</button>
          <a class="button-link secondary" href="/api/trust-operations/hubs/default/knowledge.zip">Download Knowledge ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Trust Operations Controls</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-controls-refresh" type="button">Refresh Control Catalog</button>
          <button class="secondary" id="trust-operations-controls-policy" type="button">Create Control Policy</button>
          <button class="secondary" id="trust-operations-controls-assess" type="button">Assess Controls</button>
          <button class="secondary" id="trust-operations-controls-export" type="button">Export Controls</button>
          <button class="secondary" id="trust-operations-controls-zip" type="button">Build Controls ZIP</button>
          <button class="secondary" id="trust-operations-controls-verify" type="button">Verify Controls ZIP</button>
          <a class="button-link secondary" href="/api/trust-operations/hubs/default/controls/toc-assess-000001.zip">Download Controls ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Trust Control Signoff</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-control-signoff-sign" type="button">Sign Controls</button>
          <button class="secondary" id="trust-operations-control-signoff-exception" type="button">Request Exception</button>
          <button class="secondary" id="trust-operations-control-signoff-cr" type="button">Create Change Request</button>
          <button class="secondary" id="trust-operations-control-signoff-reset" type="button">Reset Control Signoff</button>
          <button class="secondary" id="trust-operations-control-signoff-export" type="button">Export Signoff Archive</button>
          <button class="secondary" id="trust-operations-control-signoff-zip" type="button">Build Signoff ZIP</button>
          <button class="secondary" id="trust-operations-control-signoff-verify" type="button">Verify Signoff ZIP</button>
          <a class="button-link secondary" href="/api/trust-operations/control-signoff/default/download">Download Control Signoff ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Continuous Assurance</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-assurance-refresh" type="button">Refresh Assurance</button>
          <button class="secondary" id="trust-operations-assurance-export" type="button">Export Assurance</button>
          <button class="secondary" id="trust-operations-assurance-zip" type="button">Build Assurance ZIP</button>
          <button class="secondary" id="trust-operations-assurance-verify" type="button">Verify Assurance</button>
          <a class="button-link secondary" href="/api/trust-operations/assurance/runs/toa-000001/download">Download Assurance ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Assurance Watch</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-assurance-watch-schedule" type="button">Update Schedule</button>
          <button class="secondary" id="trust-operations-assurance-watch-refresh" type="button">Refresh Watch Queue</button>
          <button class="secondary" id="trust-operations-assurance-watch-export" type="button">Export Watch Archive</button>
          <button class="secondary" id="trust-operations-assurance-watch-zip" type="button">Build Watch ZIP</button>
          <button class="secondary" id="trust-operations-assurance-watch-verify" type="button">Verify Watch ZIP</button>
          <a class="button-link secondary" href="/api/trust-operations/assurance-watch/queues/toawq-000001/download">Download Watch ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Assurance Watch Signoff</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-assurance-watch-signoff-closeout" type="button">Refresh Watch Closeout</button>
          <button class="secondary" id="trust-operations-assurance-watch-signoff-sign" type="button">Sign Watch Closeout</button>
          <button class="secondary" id="trust-operations-assurance-watch-signoff-cr" type="button">Create Watch Change Request</button>
          <button class="secondary" id="trust-operations-assurance-watch-signoff-reset" type="button">Reset Watch Signoff</button>
          <button class="secondary" id="trust-operations-assurance-watch-signoff-export" type="button">Export Watch Signoff Archive</button>
          <button class="secondary" id="trust-operations-assurance-watch-signoff-zip" type="button">Build Watch Signoff ZIP</button>
          <button class="secondary" id="trust-operations-assurance-watch-signoff-verify" type="button">Verify Watch Signoff ZIP</button>
          <a class="button-link secondary" href="/api/trust-operations/assurance-watch/signoffs/toawq-000001/download">Download Watch Signoff ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Final Readiness Handoff</span></div>
        <div class="actions">
          <button class="secondary" id="trust-operations-final-readiness-refresh" type="button">Refresh Final Readiness</button>
          <button class="secondary" id="trust-operations-final-readiness-certificate" type="button">Create Certificate</button>
          <button class="secondary" id="trust-operations-final-readiness-sign" type="button">Sign Final Handoff</button>
          <button class="secondary" id="trust-operations-final-readiness-cr" type="button">Create Final Change Request</button>
          <button class="secondary" id="trust-operations-final-readiness-reset" type="button">Reset Final Handoff</button>
          <button class="secondary" id="trust-operations-final-readiness-export" type="button">Export Final Handoff</button>
          <button class="secondary" id="trust-operations-final-readiness-zip" type="button">Build Final Handoff ZIP</button>
          <button class="secondary" id="trust-operations-final-readiness-verify" type="button">Verify Final Handoff ZIP</button>
          <a class="button-link secondary" href="/api/trust-operations/final-readiness/download">Download Final Handoff ZIP</a>
        </div>
      `;
      wirePortfolioAuditActions(portfolio.portfolio_id);
      wirePortfolioGovernanceActions(portfolio.portfolio_id);
      wirePublicTrustCenterActions(portfolio.portfolio_id);
    }

    function wirePortfolioAuditActions(portfolioId) {
      const payload = () => ({
        strict: true,
        require_reviewer_packs: $("portfolio-audit-require-reviewer-packs").checked,
        require_audit: $("portfolio-audit-require-audit").checked,
        require_archive: $("portfolio-audit-require-archive").checked,
      });
      bindAction("portfolio-audit-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(portfolioAuditPayload()),
        });
        await loadPortfolioAudits();
      });
      bindAction("portfolio-audit-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/export`, { method: "POST" });
        await loadPortfolioAudits();
      });
      bindAction("portfolio-audit-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/export/zip`, { method: "POST" });
        await loadPortfolioAudits();
      });
      bindAction("portfolio-audit-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload()),
        });
        await loadPortfolioAudits();
      });
      bindAction("portfolio-audit-archive", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/archive`, { method: "POST" });
        await loadPortfolioAudits();
      });
      bindAction("portfolio-governance-audit-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/refresh`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-audit-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-audit-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-audit-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-audit/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, require_signed: true, require_archives: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-reviewer-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/refresh`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-reviewer-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-reviewer-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-reviewer-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-reviewer-pack/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, require_audit: true, require_signed: true, require_archives: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ require_reviewer_response: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-import-accepted", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/reviewer-responses/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reviewer: { name: "Studio Reviewer" }, decision: "accepted", findings: [], notes: "Accepted in Studio." }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-signoff", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/signoff`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ signed_by: "studio-user" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-cr", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/change-requests`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "Final Board archive change requested." }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-reset", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/signoff/reset`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "Reset Final Board signoff after approved change.", change_request_id: "" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/archive/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/archive/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-final-board-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-final-board/archive/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, require_signed: true, require_reviewer_pack: true, require_audit: true, require_archives: true, require_reviewer_response: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-vault-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/refresh`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-vault-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-vault-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-vault-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-evidence-vault/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, deep: true, require_final_board: true, require_reviewer_pack: true, require_audit: true, require_archives: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_vault: true, require_final_board: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-registry-register-current", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/register-current`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-registry-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-registry-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-registry-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-registry-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true, require_published: true, require_no_revoked_current: true, require_accepted_evidence: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      document.querySelectorAll(".portfolio-governance-attestation-registry-publish").forEach((button) => {
        button.addEventListener("click", async () => {
          const entryId = button.dataset.entryId;
          if (!entryId) return;
          await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/entries/${encodeURIComponent(entryId)}/publish`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ profile: "public_summary", supersede_current: true }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-attestation-registry-revoke").forEach((button) => {
        button.addEventListener("click", async () => {
          const entryId = button.dataset.entryId;
          if (!entryId) return;
          const reason = prompt("Revocation reason");
          if (!reason) return;
          await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-registry/entries/${encodeURIComponent(entryId)}/revoke`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ profile: "public_summary", reason }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      bindAction("portfolio-governance-attestation-portal-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true, require_registry: true, require_attestation: true, require_accepted_evidence: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-review-refresh-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-review-export-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-review-zip-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-review-verify-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/pack/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-review-import-response", async () => {
        const contentBase64 = prompt("Portal Review Response content_base64");
        if (!contentBase64) return;
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/responses/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", content_base64: contentBase64 }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-portal-review-create-change-request", async () => {
        const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review`);
        const responses = data.responses || [];
        const response = responses[responses.length - 1] || {};
        if (!response.response_id) return;
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-portal-review/responses/${encodeURIComponent(response.response_id)}/create-change-request`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ created_by: "studio" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-accepted-evidence-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-accepted-evidence-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-accepted-evidence-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-accepted-evidence-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-accepted-evidence-archive", async () => {
        const reason = prompt("Accepted Evidence archive reason");
        if (!reason) return;
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-accepted-evidence/archive`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", reason }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-refresh", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", require_accepted_evidence: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-export", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-zip", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-verify", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_current: true, require_accepted_evidence: true, require_contiguous_chain: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-refresh-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-export-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-zip-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-verify-pack", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/pack/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_transparency: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-import-response", async () => {
        const contentBase64 = prompt("Transparency Acknowledgement Response content_base64");
        if (!contentBase64) return;
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/responses/import`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", content_base64: contentBase64 }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-refresh-evidence", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-export-evidence", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-zip-evidence", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/zip`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-verify-evidence", async () => {
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/evidence/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary", strict: true, require_accepted: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("portfolio-governance-attestation-transparency-ack-create-change-request", async () => {
        const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement`);
        const responses = data.responses || [];
        const response = responses[responses.length - 1] || {};
        if (!response.response_id) return;
        await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-attestation-transparency-acknowledgement/responses/${encodeURIComponent(response.response_id)}/create-change-request`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: "public_summary" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
    }

    function wirePublicTrustCenterActions(portfolioId) {
      const payload = () => ({
        center_id: "ptc-default",
        portfolio_ids: [portfolioId],
        include_all_releases: true,
        include_all_portfolios: false,
        include_delivery: true,
        include_distribution: true,
        include_submission: true,
        include_submission_evidence: true,
        include_operations: true,
        attestation_profile: "public_summary",
        require_registry_current: true,
        require_portal_current: true,
        require_transparency_current: true,
      });
      bindAction("public-trust-center-refresh", async () => {
        await api(`/api/public-trust-centers/ptc-default/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload()),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-export", async () => {
        await api(`/api/public-trust-centers/ptc-default/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload()),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-zip", async () => {
        await api(`/api/public-trust-centers/ptc-default/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-verify", async () => {
        await api(`/api/public-trust-centers/ptc-default/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, require_registry_current: true, require_portal_current: true, require_transparency_current: true, require_delivery_readiness: false, require_distribution_ready: false, require_submission_accepted: false, require_submission_evidence: false, require_operations_signed: false, require_operations_audit: false, require_operations_reviewer_pack: false, require_anchor_registry_current: true, require_anchor_published: true, require_anchor_not_revoked: true, require_anchor_transparency_current: true, require_anchor_checkpoint: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-archive", async () => {
        await api(`/api/public-trust-centers/ptc-default/archive`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-register", async () => {
        const registered = await api(`/api/public-trust-centers/ptc-default/anchor-registry/register-current`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "Studio anchor registration" }),
        });
        const entryId = (registered.entry || {}).entry_id;
        if (entryId) {
          await api(`/api/public-trust-centers/ptc-default/anchor-registry/publish/${encodeURIComponent(entryId)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason: "Studio anchor publication" }),
          });
        }
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-export", async () => {
        await api(`/api/public-trust-centers/ptc-default/anchor-registry/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-zip", async () => {
        await api(`/api/public-trust-centers/ptc-default/anchor-registry/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-verify", async () => {
        await api(`/api/public-trust-centers/ptc-default/anchor-registry/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, require_current: true, require_anchor_published: true, require_anchor_not_revoked: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-transparency-refresh", async () => {
        await api(`/api/public-trust-centers/ptc-default/anchor-transparency/refresh`, { method: "POST" });
        await api(`/api/public-trust-centers/ptc-default/anchor-transparency/checkpoint/create`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-transparency-export", async () => {
        await api(`/api/public-trust-centers/ptc-default/anchor-transparency/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-transparency-zip", async () => {
        await api(`/api/public-trust-centers/ptc-default/anchor-transparency/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-anchor-transparency-verify", async () => {
        await api(`/api/public-trust-centers/ptc-default/anchor-transparency/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, use_checkpoint: true, use_anchor_registry: true, require_current_checkpoint: true, require_published_anchor: true, require_not_revoked: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-refresh", async () => {
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/refresh`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-export", async () => {
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-zip", async () => {
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-verify", async () => {
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, deep: true, require_current: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-acceptance-template", async () => {
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/template`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-accepted-evidence-export", async () => {
        const data = await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance`);
        const responses = data.responses || [];
        const response = responses[responses.length - 1] || {};
        if (!response.response_id) return;
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/responses/${encodeURIComponent(response.response_id)}/evidence/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-accepted-evidence-zip", async () => {
        const data = await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance`);
        const responses = data.responses || [];
        const response = responses[responses.length - 1] || {};
        if (!response.response_id) return;
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/responses/${encodeURIComponent(response.response_id)}/evidence/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-distribution-kit-accepted-evidence-verify", async () => {
        const data = await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance`);
        const responses = data.responses || [];
        const response = responses[responses.length - 1] || {};
        if (!response.response_id) return;
        await api(`/api/public-trust-centers/ptc-default/distribution-kit/acceptance/responses/${encodeURIComponent(response.response_id)}/evidence/verify`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-refresh", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/refresh`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-export", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-zip", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-verify", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true, require_ready: true, require_quorum: true, require_no_conflicts: true, use_distribution_kit: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-signoff-draft", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-draft`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "studio" }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-signoff", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ signed_by: "Studio Reviewer", reason: "Acceptance Board quorum is ready for public release." }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-signoff-archive-export", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/export`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-signoff-archive-zip", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/zip`, { method: "POST" });
        await renderPortfolioAuditDetail(portfolioId);
      });
      bindAction("public-trust-center-acceptance-board-signoff-archive-verify", async () => {
        await api(`/api/public-trust-centers/ptc-default/acceptance-board/signoff-archive/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strict: true }),
        });
        await renderPortfolioAuditDetail(portfolioId);
      });
    }

    function wirePortfolioGovernanceActions(portfolioId) {
      bindAction("portfolio-governance-create", async () => {
        const data = await api(`/api/release-portfolio-audits/${encodeURIComponent(portfolioId)}/governance-queues`, { method: "POST" });
        $("portfolio-governance-message").textContent = (data.queue || {}).existing ? "existing queue" : "created";
        await renderPortfolioAuditDetail(portfolioId);
      });
      document.querySelectorAll(".portfolio-governance-run-safe").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/run-safe`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_portfolio_after_safe_actions: false }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-export").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/export`, { method: "POST" });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-zip").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/export/zip`, { method: "POST" });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-verify").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ strict: true, require_manual_actions: true }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      async function manualAcknowledgements(queueId) {
        const data = await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/manual-actions`);
        return ((data.manual_action_list || {}).items || []).map((item) => ({
          item_id: item.item_id,
          action_type: item.action_type,
          resolution: "accepted_for_followup",
          owner: "developer",
          due_note: "next governance cycle",
        }));
      }
      document.querySelectorAll(".portfolio-governance-signoff").forEach((button) => {
        button.addEventListener("click", async () => {
          const queueId = button.dataset.queueId;
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/signoff`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ signed_by: "studio-user", manual_acknowledgements: await manualAcknowledgements(queueId) }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-force-signoff").forEach((button) => {
        button.addEventListener("click", async () => {
          const queueId = button.dataset.queueId;
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/signoff`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ signed_by: "studio-user", force: true, override_reason: "accepted residual governance follow-up", manual_acknowledgements: await manualAcknowledgements(queueId) }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-cr").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/change-requests`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason: "Governance signoff reset requested from Studio", requested_by: "studio-user" }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-reset").forEach((button) => {
        button.addEventListener("click", async () => {
          const queueId = button.dataset.queueId;
          const changes = await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/change-requests`);
          const approved = ((changes.change_requests || []).find((item) => item.status === "approved") || {}).change_request_id || "";
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(queueId)}/signoff/reset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ reason: "Reset with approved governance change", change_request_id: approved }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-archive-export").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/archive/export`, { method: "POST" });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-archive-zip").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/archive/zip`, { method: "POST" });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
      document.querySelectorAll(".portfolio-governance-archive-verify").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/release-portfolio-governance-queues/${encodeURIComponent(button.dataset.queueId)}/archive/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ strict: true, require_signed: true }),
          });
          await renderPortfolioAuditDetail(portfolioId);
        });
      });
    }

    async function renderReleaseDetail(releaseId) {
      const data = await api(`/api/releases/${encodeURIComponent(releaseId)}`);
      const release = data.release;
      const summary = data.summary || {};
      let qaData = { summary: release.qa_summary || {}, release_qa: { checks: [], track_checks: [] } };
      let exportData = { summary: release.export_summary || {}, manifest: {} };
      let signoffData = { summary: release.signoff_summary || {}, signoff: {} };
      let metadataData = { summary: {}, metadata: {}, metadata_qa: { checks: [], track_checks: [] } };
      let audioReviewData = { summary: {}, reviews: [] };
      let audioRevisionData = { summary: {}, sessions: [] };
      let masteringData = { summary: {}, analysis: {}, plan: {}, candidates: [], selected_candidate: {} };
      let encodedAudioData = { summary: {}, profiles: [] };
      let formatDecisionData = { sessions: [], active_session: {} };
      let rightsData = { report: {}, parties: [] };
      let distributionData = { summary: {}, targets: [], artwork: [] };
      let submissionData = { summary: {}, submissions: [] };
      let operationsData = { summary: {}, report: {} };
      let operationsReviewerData = { summary: {}, report: {}, retrospective_summary: {} };
      let releaseAnalyticsData = { summary: {}, analytics: null };
      try { qaData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/qa`); } catch (err) {}
      try { exportData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/export`); } catch (err) {}
      try { signoffData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/signoff`); } catch (err) {}
      try { audioReviewData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews`); } catch (err) {}
      try {
        audioRevisionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions`);
        const firstRevisionSession = ((audioRevisionData.sessions || [])[0] || {}).session_id;
        if (firstRevisionSession) {
          audioRevisionData.detail = await api(`/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(firstRevisionSession)}`);
        }
      } catch (err) {}
      try { masteringData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/mastering`); } catch (err) {}
      try { encodedAudioData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/encoded-audio`); } catch (err) {}
      try { formatDecisionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/format-decisions`); } catch (err) {}
      try { rightsData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/rights`); } catch (err) {}
      try {
        metadataData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata`);
        const metadataQa = await api(`/api/releases/${encodeURIComponent(release.release_id)}/metadata/qa`);
        metadataData.metadata_qa = metadataQa.metadata_qa || {};
        metadataData.qa_summary = metadataQa.summary || {};
      } catch (err) {}
      try {
        distributionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution`);
        const artworkData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/distribution/artwork`);
        distributionData.artwork = artworkData.artwork || [];
        const templateData = await api(`/api/distribution/template-packs`);
        distributionData.template_packs = templateData.template_packs || distributionData.template_packs || [];
      } catch (err) {}
      try { submissionData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/submissions`); } catch (err) {}
      try {
        operationsData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations`);
        const runbookData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks`);
        operationsData.runbooks = runbookData.runbooks || [];
        const auditData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/audit`);
        operationsData.audit = auditData || {};
        operationsReviewerData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack`);
      } catch (err) {}
      try { releaseAnalyticsData = await api(`/api/releases/${encodeURIComponent(release.release_id)}/acceptance-analytics`); } catch (err) {}
      const target = $("release-detail");
      target.innerHTML = `
        <div class="panel-title" style="padding:0 0 12px;border-bottom:0;">
          <span>Release Workspace · ${escapeHtml(release.name || release.release_id)}</span>
          <span class="status ${escapeHtml(release.status || "")}">${escapeHtml(release.status || "-")}</span>
        </div>
        <div class="summary-grid">
          ${metric("Release", release.release_id)}
          ${metric("Type", release.release_type || "-")}
          ${metric("Tracks", summary.track_count || 0)}
          ${metric("Artist", release.primary_artist || "-")}
        </div>
        <div class="summary-grid">
          ${metric("Release QA", (qaData.summary || {}).status || "missing")}
          ${metric("Release Export", (exportData.summary || {}).status || ((exportData.manifest || {}).schema_version ? "built" : "missing"))}
          ${metric("Release ZIP", ((exportData.manifest || {}).zip || {}).filename || "-")}
          ${metric("Release Signoff", (signoffData.summary || {}).status || "not_signed")}
        </div>
        <div class="grid2">
          <label>Add Project
            <select id="release-add-project">${releaseProjectOptions()}</select>
          </label>
          <label>Track Title
            <input id="release-add-title" placeholder="optional title override">
          </label>
        </div>
        <div class="actions">
          ${releaseActionButtons(release, signoffData.summary || {})}
          <span id="release-action-message" class="message"></span>
        </div>
        ${releaseTrackTable(release)}
        ${releaseMetadataHtml(metadataData, release)}
        ${releaseAudioReviewHtml(audioReviewData, release)}
        ${releaseAudioRevisionHtml(audioRevisionData, release)}
        ${releaseMasteringHtml(masteringData, release)}
        ${releaseEncodedAudioHtml(encodedAudioData, release)}
        ${releaseFormatDecisionHtml(formatDecisionData, release)}
        ${releaseRightsClearanceHtml(rightsData, release)}
        ${releaseOperationsHtml(operationsData, operationsReviewerData, release)}
        ${releaseDistributionHtml(distributionData, release)}
        ${releaseSubmissionsHtml(submissionData, distributionData, release)}
        ${releaseAcceptanceAnalyticsHtml(releaseAnalyticsData, release)}
        ${releaseQaHtml(qaData)}
        ${releaseExportHtml(exportData, release)}
        ${releaseSignoffHtml(signoffData)}
      `;
      wireReleaseActions(release);
    }

    function renderAcceptanceSuites() {
      const list = $("acceptance-list");
      if (!acceptanceSuites.length) {
        list.innerHTML = "<div class='empty'>No acceptance suites yet.</div>";
        return;
      }
      const rows = acceptanceSuites.map((suite) => `
        <tr class="${suite.suite_id === selectedAcceptanceSuiteId ? "active" : ""}">
          <td><button class="secondary acceptance-open" data-suite-id="${escapeHtml(suite.suite_id)}" type="button">Open</button></td>
          <td>${escapeHtml(suite.name || suite.suite_id)}</td>
          <td><span class="status ${escapeHtml(suite.status || "")}">${escapeHtml(suite.status || "-")}</span></td>
          <td>${escapeHtml(suite.case_count || 0)}</td>
          <td>${escapeHtml(suite.accepted_count || 0)}</td>
          <td>${escapeHtml((suite.latest_report_summary || {}).status || "missing")}</td>
          <td>${escapeHtml((suite.latest_signoff_summary || {}).status || "not_signed")}</td>
        </tr>
      `).join("");
      list.innerHTML = `
        <table>
          <thead><tr><th></th><th>Name</th><th>Status</th><th>Cases</th><th>Accepted</th><th>Report</th><th>Signoff</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      list.querySelectorAll(".acceptance-open").forEach((button) => {
        button.addEventListener("click", async () => {
          selectedAcceptanceSuiteId = button.dataset.suiteId;
          renderAcceptanceSuites();
          await renderAcceptanceDetail(selectedAcceptanceSuiteId);
        });
      });
    }

    function renderAcceptanceReferenceData() {
      if ($("acceptance-profile") && acceptanceProfiles.length) {
        const current = $("acceptance-profile").value || "developer_manual";
        $("acceptance-profile").innerHTML = acceptanceProfiles.map((profile) => {
          const id = profile.profile_id || "";
          return `<option value="${escapeHtml(id)}" ${id === current ? "selected" : ""}>${escapeHtml(id)}</option>`;
        }).join("");
      }
      const songs = (acceptanceSongbook || {}).songs || [];
      const songbook = $("acceptance-songbook");
      if (!songbook) return;
      if (!songs.length) {
        songbook.innerHTML = "<div class='empty'>No regression songs available.</div>";
        return;
      }
      songbook.innerHTML = `
        <table>
          <thead><tr><th>Song ID</th><th>Title</th><th>Style</th><th>Min</th></tr></thead>
          <tbody>${songs.slice(0, 12).map((song) => `
            <tr>
              <td>${escapeHtml(song.song_id || "-")}</td>
              <td>${escapeHtml(song.title || "-")}</td>
              <td>${escapeHtml(song.style || "-")}</td>
              <td>${escapeHtml(((song.expectations || {}).quality_min) || "-")}</td>
            </tr>
          `).join("")}</tbody>
        </table>
      `;
    }

    function acceptanceSongOptions() {
      const songs = (acceptanceSongbook || {}).songs || [];
      return songs.map((song) => `<option value="${escapeHtml(song.song_id)}">${escapeHtml(song.song_id)} · ${escapeHtml(song.title || "")}</option>`).join("");
    }

    function acceptanceSuiteOptions(selectedId = "") {
      return acceptanceSuites.map((suite) => {
        const summary = suite.latest_report_summary || {};
        const label = `${suite.name || suite.suite_id} · ${suite.profile_id || "-"} · ${summary.acceptance_status || summary.status || "missing"}`;
        return `<option value="${escapeHtml(suite.suite_id)}" ${suite.suite_id === selectedId ? "selected" : ""}>${escapeHtml(label)}</option>`;
      }).join("");
    }

    function renderAcceptanceAnalytics(report = acceptanceAnalytics) {
      const target = $("acceptance-analytics");
      if (!target) return;
      if (!report || !report.report_id) {
        target.innerHTML = "<div class='empty'>No acceptance analytics report yet.</div>";
        return;
      }
      const summary = report.summary || {};
      const heatmapRows = (report.songbook_heatmap || []).slice(0, 12).map((item) => `
        <tr>
          <td>${escapeHtml(item.song_id || "-")}</td>
          <td>${escapeHtml(item.status || "-")}</td>
          <td>${escapeHtml(item.case_count || 0)}</td>
          <td>${escapeHtml(item.manual_accepted_count || 0)}</td>
          <td>${escapeHtml(item.issue_count || 0)}</td>
          <td>${escapeHtml(item.average_rating ?? "-")}</td>
        </tr>
      `).join("");
      const issueRows = (report.issue_taxonomy || []).slice(0, 8).map((item) => `
        <tr>
          <td>${escapeHtml(item.issue_type || "-")}</td>
          <td>${escapeHtml(item.count || 0)}</td>
          <td>${escapeHtml(item.severity || "-")}</td>
          <td>${escapeHtml(item.example_excerpt || "")}</td>
        </tr>
      `).join("");
      const recommendationRows = (report.recommendations || []).slice(0, 8).map((item) => `
        <tr>
          <td>${escapeHtml(item.type || "-")}</td>
          <td>${escapeHtml(item.song_id || "-")}</td>
          <td>${escapeHtml(item.priority || "-")}</td>
          <td>${escapeHtml(item.reason || "")}</td>
          <td>${item.type === "create_review_task" ? `<button class="secondary acceptance-analytics-create-task" data-report-id="${escapeHtml(report.report_id)}" data-recommendation-id="${escapeHtml(item.recommendation_id)}" type="button">Create Task</button>` : "-"}</td>
        </tr>
      `).join("");
      target.innerHTML = `
        <div class="summary-grid">
          ${metric("Readiness", summary.readiness_status || "watch")}
          ${metric("Cases", summary.case_count || 0)}
          ${metric("Manual Accepted", summary.manual_accepted_count || 0)}
          ${metric("Needs Fix", summary.needs_fix_count || 0)}
          ${metric("Blocked", summary.blocked_count || 0)}
          ${metric("Stale", report.stale ? "yes" : "-")}
        </div>
        <div class="grid2">
          <label>Report ID <input id="acceptance-analytics-report-id" readonly value="${escapeHtml(report.report_id)}"></label>
          <label>Source Hash <input readonly value="${escapeHtml(report.source_hash || "")}"></label>
        </div>
        <div class="panel-title subhead"><span>Songbook Heatmap</span></div>
        <table>
          <thead><tr><th>Song ID</th><th>Status</th><th>Cases</th><th>Manual</th><th>Issues</th><th>Rating</th></tr></thead>
          <tbody>${heatmapRows || "<tr><td colspan='6'>No songbook metrics yet.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Issue Taxonomy</span></div>
        <table>
          <thead><tr><th>Issue</th><th>Count</th><th>Severity</th><th>Example</th></tr></thead>
          <tbody>${issueRows || "<tr><td colspan='4'>No issues detected.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Recommendations</span></div>
        <table>
          <thead><tr><th>Action</th><th>Song</th><th>Priority</th><th>Reason</th><th></th></tr></thead>
          <tbody>${recommendationRows || "<tr><td colspan='5'>No recommendations.</td></tr>"}</tbody>
        </table>
      `;
      document.querySelectorAll(".acceptance-analytics-create-task").forEach((button) => button.addEventListener("click", async () => {
        const data = await api(`/api/acceptance/analytics/reports/${encodeURIComponent(button.dataset.reportId)}/recommendations/${encodeURIComponent(button.dataset.recommendationId)}/create-review-task`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        $("acceptance-analytics-report-id").value = data.status || data.task_id || report.report_id;
      }));
    }

    function renderAcceptanceFixSprints() {
      const target = $("acceptance-fix-sprints");
      if (!target) return;
      if (!acceptanceFixSprints.length) {
        target.innerHTML = "<div class='empty'>No acceptance fix sprints yet.</div>";
        return;
      }
      const rows = acceptanceFixSprints.map((sprint) => {
        const counts = sprint.counts || {};
        const recheck = sprint.recheck || {};
        const delta = sprint.delta_summary || {};
        return `
          <tr>
            <td>${escapeHtml(sprint.fix_sprint_id)}</td>
            <td>${escapeHtml(sprint.name || "")}</td>
            <td>${escapeHtml(sprint.status || "-")}</td>
            <td>${escapeHtml(counts.item_count || 0)}</td>
            <td>${escapeHtml(counts.open_item_count || 0)}</td>
            <td>${escapeHtml(recheck.suite_id || "-")}</td>
            <td>${escapeHtml(delta.status || "-")}</td>
            <td class="actions">
              <button class="secondary acceptance-fix-tasks" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Create ReviewTasks</button>
              <button class="secondary acceptance-fix-recheck" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Create Recheck</button>
              <button class="secondary acceptance-fix-delta" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Delta</button>
              <button class="secondary acceptance-fix-close" data-fix-sprint-id="${escapeHtml(sprint.fix_sprint_id)}" type="button">Close</button>
            </td>
          </tr>
        `;
      }).join("");
      target.innerHTML = `
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Items</th><th>Open</th><th>Recheck</th><th>Delta</th><th>Actions</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      document.querySelectorAll(".acceptance-fix-tasks").forEach((button) => button.addEventListener("click", async () => {
        await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/create-review-tasks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        await loadAcceptanceFixSprints();
      }));
      document.querySelectorAll(".acceptance-fix-recheck").forEach((button) => button.addEventListener("click", async () => {
        await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/create-recheck-suite`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        await loadAcceptanceFixSprints();
        await loadAcceptanceSuites();
      }));
      document.querySelectorAll(".acceptance-fix-delta").forEach((button) => button.addEventListener("click", async () => {
        await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/delta/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        await loadAcceptanceFixSprints();
      }));
      document.querySelectorAll(".acceptance-fix-close").forEach((button) => button.addEventListener("click", async () => {
        await api(`/api/acceptance/fix-sprints/${encodeURIComponent(button.dataset.fixSprintId)}/close`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        await loadAcceptanceFixSprints();
      }));
    }

    function renderAcceptanceFixPlans() {
      const target = $("acceptance-fix-plans");
      if (!target) return;
      if (!acceptanceFixPlans.length) {
        target.innerHTML = "<div class='empty'>No acceptance fix plans yet.</div>";
        return;
      }
      const rows = acceptanceFixPlans.map((plan) => {
        const summary = plan.summary || {};
        const execution = plan.execution || {};
        return `
          <tr>
            <td><button class="secondary acceptance-fix-plan-select" data-plan-id="${escapeHtml(plan.plan_id)}" type="button">Select</button></td>
            <td>${escapeHtml(plan.plan_id)}</td>
            <td>${escapeHtml(plan.status || "-")}</td>
            <td>${escapeHtml(summary.planned_item_count || 0)}</td>
            <td>${escapeHtml(summary.kb_match_count || 0)}</td>
            <td>${escapeHtml(summary.risk_warning_count || 0)}</td>
            <td>${escapeHtml(execution.created_fix_sprint_id || "-")}</td>
          </tr>
        `;
      }).join("");
      target.innerHTML = `
        <table>
          <thead><tr><th></th><th>Plan</th><th>Status</th><th>Items</th><th>KB Matches</th><th>Risks</th><th>Fix Sprint</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
      document.querySelectorAll(".acceptance-fix-plan-select").forEach((button) => button.addEventListener("click", () => {
        $("acceptance-fix-plan-id").value = button.dataset.planId || "";
        loadAcceptanceFixPlanReview(button.dataset.planId || "");
      }));
    }

    function renderAcceptanceFixPlanReview() {
      const target = $("acceptance-fix-plan-review");
      if (!target) return;
      const review = acceptanceFixPlanReview || {};
      if (!review.review_id) {
        const status = review.status || "missing";
        target.innerHTML = `<div class="empty">Outcome Review ${escapeHtml(status)}.</div>`;
        return;
      }
      const summary = review.summary || {};
      const hints = (review.calibration_hints || []).slice(0, 5).map((hint) => `<li>${escapeHtml(hint.type || "hint")}: ${escapeHtml(hint.reason || "")}</li>`).join("");
      const items = (review.item_outcomes || []).slice(0, 8).map((item) => {
        const outcome = item.outcome || {};
        return `
          <tr>
            <td>${escapeHtml(item.planned_item_id || "-")}</td>
            <td>${escapeHtml(item.fix_item_id || "-")}</td>
            <td>${escapeHtml(item.planning_score ?? "-")}</td>
            <td>${escapeHtml(outcome.evidence_status || "-")}</td>
            <td>${escapeHtml(outcome.observed_effectiveness_score ?? "-")}</td>
          </tr>
        `;
      }).join("");
      target.innerHTML = `
        <div class="grid3">
          <div><b>Review</b><br>${escapeHtml(review.review_id)}</div>
          <div><b>Status</b><br>${escapeHtml(review.status || "-")}</div>
          <div><b>Plan Effectiveness</b><br>${escapeHtml(summary.plan_effectiveness_score ?? "-")}</div>
          <div><b>Ranking Alignment</b><br>${escapeHtml(summary.ranking_alignment_score ?? "-")}</div>
          <div><b>KB Helpfulness</b><br>${escapeHtml(summary.kb_evidence_helpfulness || "-")}</div>
          <div><b>Warnings</b><br>${escapeHtml(summary.warning_count || 0)}</div>
        </div>
        <table>
          <thead><tr><th>Planned Item</th><th>Fix Item</th><th>Score</th><th>Evidence</th><th>Effectiveness</th></tr></thead>
          <tbody>${items || "<tr><td colspan='5'>No item outcomes.</td></tr>"}</tbody>
        </table>
        ${hints ? `<ul>${hints}</ul>` : ""}
      `;
    }

    function renderPlanningSimulations() {
      const target = $("planning-rule-simulation");
      if (!target) return;
      const ruleset = planningRuleSets[0] || {};
      if (!planningSimulations.length) {
        target.innerHTML = `<div class="empty">Simulation only. Rule sets: ${escapeHtml(planningRuleSets.length)}. Latest rule set: ${escapeHtml(ruleset.ruleset_id || "-")}.</div>`;
        return;
      }
      const rows = planningSimulations.slice(0, 8).map((simulation) => {
        const summary = simulation.summary || {};
        return `
          <tr>
            <td>${escapeHtml(simulation.simulation_id || "-")}</td>
            <td>${escapeHtml(simulation.ruleset_id || "-")}</td>
            <td>${escapeHtml(simulation.status || "-")}</td>
            <td>${escapeHtml(summary.review_count || 0)}</td>
            <td>${escapeHtml(summary.alignment_delta ?? "-")}</td>
            <td>${escapeHtml(summary.recommendation || "-")}</td>
          </tr>
        `;
      }).join("");
      target.innerHTML = `
        <div class="grid3">
          <div><b>Mode</b><br>simulation only</div>
          <div><b>Rule Sets</b><br>${escapeHtml(planningRuleSets.length)}</div>
          <div><b>Simulations</b><br>${escapeHtml(planningSimulations.length)}</div>
        </div>
        <table>
          <thead><tr><th>Simulation</th><th>Rule Set</th><th>Status</th><th>Reviews</th><th>Delta</th><th>Recommendation</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function renderPlanningGovernance() {
      const target = $("planning-rule-governance");
      if (!target) return;
      const summary = (planningGovernance || {}).summary || {};
      const active = (planningGovernance || {}).active || {};
      const promotionRows = planningPromotions.slice(0, 8).map((promotion) => {
        const evidence = promotion.evidence || {};
        return `
          <tr>
            <td>${escapeHtml(promotion.promotion_id || "-")}</td>
            <td>${escapeHtml(promotion.status || "-")}</td>
            <td>${escapeHtml(promotion.ruleset_id || "-")}</td>
            <td>${escapeHtml(promotion.simulation_id || "-")}</td>
            <td>${escapeHtml(evidence.recommendation || "-")}</td>
            <td>${escapeHtml(evidence.alignment_delta ?? "-")}</td>
          </tr>
        `;
      }).join("");
      const versionRows = planningVersions.slice(0, 6).map((version) => `
        <tr>
          <td>${escapeHtml(version.version_id || "-")}</td>
          <td>${escapeHtml(version.status || "-")}</td>
          <td>${escapeHtml(version.ruleset_id || "-")}</td>
          <td>${escapeHtml((version.promoted_from || {}).simulation_id || "-")}</td>
        </tr>
      `).join("");
      target.innerHTML = `
        <div class="grid3">
          <div><b>Active Version</b><br>${escapeHtml(summary.active_version_id || active.active_version_id || "-")}</div>
          <div><b>Ruleset</b><br>${escapeHtml(summary.ruleset_id || "-")}</div>
          <div><b>Evidence</b><br>${escapeHtml(summary.evidence_stale ? "stale" : summary.status || "missing")}</div>
        </div>
        <table>
          <thead><tr><th>Promotion</th><th>Status</th><th>Rule Set</th><th>Simulation</th><th>Recommendation</th><th>Delta</th></tr></thead>
          <tbody>${promotionRows || "<tr><td colspan='6'>No promotions.</td></tr>"}</tbody>
        </table>
        <table>
          <thead><tr><th>Version</th><th>Status</th><th>Rule Set</th><th>Simulation</th></tr></thead>
          <tbody>${versionRows || "<tr><td colspan='4'>No versions.</td></tr>"}</tbody>
        </table>
      `;
    }

    function renderPlanningImpact() {
      const target = $("planning-rule-impact");
      if (!target) return;
      if (!planningImpact || !planningImpact.report_id) {
        target.innerHTML = "<div class='empty'>No planning rule impact report yet.</div>";
        return;
      }
      const summary = planningImpact.summary || {};
      const adoption = planningImpact.adoption || {};
      const risk = planningImpact.risk_drift || {};
      const rows = (planningImpact.version_metrics || []).slice(0, 8).map((item) => `
        <tr>
          <td>${escapeHtml(item.version_id || "-")}</td>
          <td>${escapeHtml(item.plan_count ?? 0)}</td>
          <td>${escapeHtml(item.review_count ?? 0)}</td>
          <td>${escapeHtml(item.average_plan_effectiveness_score ?? "-")}</td>
          <td>${escapeHtml(item.average_ranking_alignment_score ?? "-")}</td>
          <td>${escapeHtml(item.synthetic_only_rate ?? 0)}%</td>
          <td>${escapeHtml(item.waiver_rate ?? 0)}%</td>
          <td>${escapeHtml(item.force_close_rate ?? 0)}%</td>
        </tr>
      `).join("");
      target.innerHTML = `
        <div class="grid3">
          <div><b>Active Version</b><br>${escapeHtml(summary.active_version_id || "-")}</div>
          <div><b>Adoption Rate</b><br>${escapeHtml(adoption.active_adoption_rate ?? 0)}%</div>
          <div><b>Recommendation</b><br>${escapeHtml(summary.recommendation || "-")}</div>
        </div>
        <div class="grid3">
          <div><b>Plans</b><br>${escapeHtml(summary.observed_plan_count ?? 0)}</div>
          <div><b>Reviews</b><br>${escapeHtml(summary.observed_review_count ?? 0)}</div>
          <div><b>Rollback Recommended</b><br>${summary.rollback_recommended ? "yes" : "-"}</div>
        </div>
        <div class="grid3">
          <div><b>Manual Review</b><br>${escapeHtml(summary.manual_review_count ?? 0)}</div>
          <div><b>Synthetic Review</b><br>${escapeHtml(summary.synthetic_review_count ?? 0)}</div>
          <div><b>Risk Drift</b><br>${escapeHtml((risk.warnings || []).join(", ") || "-")}</div>
        </div>
        <table>
          <thead><tr><th>Version</th><th>Plans</th><th>Reviews</th><th>Effectiveness</th><th>Ranking</th><th>Synthetic</th><th>Waiver</th><th>Force</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='8'>No version metrics.</td></tr>"}</tbody>
        </table>
      `;
    }

    function renderAcceptanceKb(report = acceptanceKb) {
      const target = $("acceptance-kb");
      if (!target) return;
      if (!report || !report.report_id) {
        target.innerHTML = "<div class='empty'>No acceptance knowledge report yet.</div>";
        return;
      }
      const summary = report.summary || {};
      const issueRows = (report.issue_patterns || []).slice(0, 8).map((item) => `
        <tr>
          <td>${escapeHtml(item.issue_type || "-")}</td>
          <td>${escapeHtml(item.entry_count || 0)}</td>
          <td>${escapeHtml(item.effective_count || 0)}</td>
          <td>${escapeHtml(item.average_effectiveness_score ?? "-")}</td>
          <td>${escapeHtml(item.risk || "-")}</td>
        </tr>
      `).join("");
      const styleRows = (report.style_patterns || []).slice(0, 8).map((item) => `
        <tr>
          <td>${escapeHtml(item.style || "-")}</td>
          <td>${escapeHtml(item.entry_count || 0)}</td>
          <td>${escapeHtml((item.recurring_issues || []).join(", "))}</td>
          <td>${escapeHtml(item.average_effectiveness_score ?? "-")}</td>
          <td>${escapeHtml(item.stability_status || "-")}</td>
        </tr>
      `).join("");
      const entryRows = (report.recommendations || []).slice(0, 6).map((item) => `
        <tr>
          <td>${escapeHtml(item.type || "-")}</td>
          <td>${escapeHtml(item.issue_type || item.style || item.song_id || "-")}</td>
          <td>${escapeHtml(item.reason || "")}</td>
        </tr>
      `).join("");
      const rec = acceptanceKbRecommendation || {};
      target.innerHTML = `
        <div class="summary-grid">
          ${metric("Entries", summary.entry_count || 0)}
          ${metric("Effective", summary.effective_count || 0)}
          ${metric("Mixed", summary.mixed_count || 0)}
          ${metric("Ineffective", summary.ineffective_count || 0)}
          ${metric("Average", summary.average_effectiveness_score ?? "-")}
          ${metric("Stale", report.stale ? "yes" : "-")}
        </div>
        <div class="panel-title subhead"><span>Issue Patterns</span></div>
        <table>
          <thead><tr><th>Issue</th><th>Entries</th><th>Effective</th><th>Score</th><th>Risk</th></tr></thead>
          <tbody>${issueRows || "<tr><td colspan='5'>No issue patterns yet.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Style Patterns</span></div>
        <table>
          <thead><tr><th>Style</th><th>Entries</th><th>Recurring Issues</th><th>Score</th><th>Status</th></tr></thead>
          <tbody>${styleRows || "<tr><td colspan='5'>No style patterns yet.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Recommendation Panel</span></div>
        ${rec.status ? `<pre>${escapeHtml(JSON.stringify(rec, null, 2))}</pre>` : `<table><thead><tr><th>Type</th><th>Target</th><th>Reason</th></tr></thead><tbody>${entryRows || "<tr><td colspan='3'>No KB recommendations yet.</td></tr>"}</tbody></table>`}
      `;
    }

    function selectedAcceptanceSong() {
      const songId = $("acceptance-song-id")?.value || "";
      return ((acceptanceSongbook || {}).songs || []).find((song) => song.song_id === songId) || null;
    }

    async function renderAcceptanceDetail(suiteId) {
      const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}`);
      const suite = data.suite || {};
      const cases = data.cases || [];
      const report = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/report`).catch(() => ({ report: {}, summary: {} }));
      const signoff = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/signoff`).catch(() => ({ signoff: {}, summary: {} }));
      const humanPacks = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`).catch(() => ({ packs: [], summary: {} }));
      const humanImports = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/review-imports`).catch(() => ({ imports: [], summary: {} }));
      const analyticsData = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/analytics`).catch(() => ({ analytics: null, summary: {} }));
      const latestHumanPack = (humanPacks.packs || [])[0] || {};
      const latestHumanImport = (humanImports.imports || [])[0] || {};
      const caseRows = cases.map((item) => {
        const health = item.health_summary || {};
        const review = item.review_summary || {};
        return `
          <tr>
            <td>${escapeHtml(item.case_id)}</td>
            <td>${escapeHtml(item.song_id || "-")}</td>
            <td>${escapeHtml(item.name)}</td>
            <td><span class="status ${escapeHtml(item.status)}">${escapeHtml(item.status)}</span></td>
            <td>${escapeHtml(health.status || "missing")}</td>
            <td>${escapeHtml(health.audio_status || "-")}</td>
            <td>${escapeHtml(review.status || "missing")}</td>
            <td>${escapeHtml(review.rating ?? "-")}</td>
            <td>
              <button class="secondary acceptance-generate" data-case-id="${escapeHtml(item.case_id)}" type="button">Generate</button>
              <button class="secondary acceptance-health" data-case-id="${escapeHtml(item.case_id)}" type="button">Health</button>
              <a class="button-link secondary" href="/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(item.case_id)}/midi">MIDI</a>
            </td>
          </tr>
        `;
      }).join("");
      $("acceptance-detail").innerHTML = `
        <div class="panel-title subhead"><span>${escapeHtml(suite.name || suite.suite_id)}</span></div>
        <div class="quick-grid">
          ${metric("Status", suite.status || "-")}
          ${metric("Profile", suite.profile_id || "-")}
          ${metric("Songbook", suite.songbook_id || "-")}
          ${metric("Cases", suite.case_count || 0)}
          ${metric("Accepted", suite.accepted_count || 0)}
          ${metric("Report", (report.summary || {}).status || "missing")}
          ${metric("Acceptance", (report.summary || {}).acceptance_status || "missing")}
          ${metric("Signoff", (signoff.summary || {}).status || "not_signed")}
        </div>
        <div class="grid2">
          <label>Regression Song
            <select id="acceptance-song-id">${acceptanceSongOptions()}</select>
          </label>
          <label>Case Title <input id="acceptance-case-title" value="Acceptance Song"></label>
        </div>
        <div class="grid2">
          <label>Style <input id="acceptance-case-style" value="upbeat pop"></label>
          <label>Theme <input id="acceptance-case-theme" value="local acceptance review"></label>
        </div>
        <div class="actions">
          <button id="acceptance-add-case" type="button">Add Case</button>
          <button class="secondary" id="acceptance-build-report" type="button">Build Report</button>
          <button class="secondary" id="acceptance-refresh-suite-analytics" type="button">Refresh Analytics</button>
          <button class="secondary" id="acceptance-signoff" type="button">Signoff</button>
          <button class="secondary" id="acceptance-reset-signoff" type="button">Reset Signoff</button>
        </div>
        <div class="panel-title subhead"><span>Suite Analytics</span></div>
        <div class="quick-grid">
          ${metric("Readiness", (analyticsData.summary || {}).readiness_status || "missing")}
          ${metric("Top Issue", (((analyticsData.analytics || {}).issue_taxonomy || [])[0] || {}).issue_type || "-")}
          ${metric("Recommendations", ((analyticsData.analytics || {}).recommendations || []).length)}
          ${metric("Stale", (analyticsData.analytics || {}).stale ? "yes" : "-")}
        </div>
        <div class="panel-title subhead"><span>Acceptance Diff</span></div>
        <div class="grid2">
          <label>Baseline Suite
            <select id="acceptance-diff-suite"><option value="">select baseline</option>${acceptanceSuiteOptions()}</select>
          </label>
          <label>Diff Status
            <input id="acceptance-diff-status" readonly value="-">
          </label>
        </div>
        <div class="actions"><button class="secondary" id="acceptance-run-diff" type="button">Compare Suites</button></div>
        <pre id="acceptance-diff-result"></pre>
        <div class="panel-title subhead"><span>Human Review Pack</span></div>
        <div class="quick-grid">
          ${metric("Packs", (humanPacks.summary || {}).pack_count || 0)}
          ${metric("Latest Pack", latestHumanPack.pack_id || "-")}
          ${metric("Pack Status", latestHumanPack.status || "-")}
          ${metric("Latest Import", latestHumanImport.import_id || "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="acceptance-create-human-pack" type="button">Create Pack</button>
          <button class="secondary" id="acceptance-zip-human-pack" type="button" ${latestHumanPack.pack_id ? "" : "disabled"}>Build Pack ZIP</button>
          <button class="secondary" id="acceptance-verify-human-pack" type="button" ${latestHumanPack.pack_id ? "" : "disabled"}>Verify Pack</button>
          ${latestHumanPack.pack_id ? `<a class="button-link secondary" href="/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs/${encodeURIComponent(latestHumanPack.pack_id)}/zip">Download Pack</a>` : ""}
        </div>
        <label>Review Response JSON <textarea id="acceptance-human-review-response" placeholder="Paste exported human review response JSON here"></textarea></label>
        <div class="actions"><button class="secondary" id="acceptance-import-human-review" type="button">Import Response</button></div>
        <pre id="acceptance-human-review-result">${escapeHtml(JSON.stringify({ pack: latestHumanPack, import: latestHumanImport }, null, 2))}</pre>
        <div class="panel-title subhead"><span>Cases</span></div>
        <div class="table-wrap">
          ${caseRows ? `<table><thead><tr><th>ID</th><th>Song ID</th><th>Name</th><th>Status</th><th>Health</th><th>Audio</th><th>Review</th><th>Rating</th><th>Actions</th></tr></thead><tbody>${caseRows}</tbody></table>` : "<div class='empty'>No acceptance cases yet.</div>"}
        </div>
        <div class="panel-title subhead"><span>Listening Review</span></div>
        <div class="grid2">
          <label>Case ID <input id="acceptance-review-case-id" value="${escapeHtml((cases[0] || {}).case_id || "")}"></label>
          <label>Rating <input id="acceptance-review-rating" type="number" min="1" max="5" value="4"></label>
        </div>
        <div class="grid2">
          <label>Status
            <select id="acceptance-review-status"><option value="accepted">accepted</option><option value="needs_fix">needs_fix</option><option value="rejected">rejected</option><option value="waived">waived</option></select>
          </label>
          <label>Audio Mode <input id="acceptance-review-audio-mode" value="midi"></label>
        </div>
        <label style="display:flex;gap:8px;align-items:center;"><input id="acceptance-review-playback" type="checkbox" style="width:auto;"> Playback Confirmed</label>
        <label>Notes <textarea id="acceptance-review-notes">I listened to the generated MIDI and the structure is acceptable for this review.</textarea></label>
        <div class="actions"><button id="acceptance-save-review" type="button">Save Review</button></div>
        <pre>${escapeHtml(JSON.stringify(report.report || {}, null, 2))}</pre>
      `;
      wireAcceptanceActions(suiteId);
    }

    function wireAcceptanceActions(suiteId) {
      $("acceptance-song-id")?.addEventListener("change", () => {
        const song = selectedAcceptanceSong();
        if (!song) return;
        $("acceptance-case-title").value = song.title || "Acceptance Song";
        $("acceptance-case-style").value = song.style || "pop";
        $("acceptance-case-theme").value = song.theme || "acceptance review";
      });
      $("acceptance-add-case")?.addEventListener("click", async () => {
        const song = selectedAcceptanceSong();
        const request = song && song.request ? song.request : {
          title: $("acceptance-case-title").value.trim() || "Acceptance Song",
          language: "English",
          style: $("acceptance-case-style").value.trim() || "pop",
          theme: $("acceptance-case-theme").value.trim() || "acceptance review",
          duration_seconds: 90,
        };
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: (song && song.title) || $("acceptance-case-style").value.trim() || "acceptance case",
            source_type: song ? "regression_songbook" : "generated_request",
            song_id: song ? song.song_id : undefined,
            songbook_id: song ? (acceptanceSongbook || {}).songbook_id : undefined,
            songbook_version: song ? (acceptanceSongbook || {}).songbook_version : undefined,
            expectations: song ? (song.expectations || {}) : {},
            request,
          }),
        });
        await loadAcceptanceSuites();
      });
      document.querySelectorAll(".acceptance-generate").forEach((button) => button.addEventListener("click", async () => {
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(button.dataset.caseId)}/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ render_audio: "auto" }) });
        await loadAcceptanceSuites();
      }));
      document.querySelectorAll(".acceptance-health").forEach((button) => button.addEventListener("click", async () => {
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(button.dataset.caseId)}/health`, { method: "POST" });
        await loadAcceptanceSuites();
      }));
      $("acceptance-save-review")?.addEventListener("click", async () => {
        const caseId = $("acceptance-review-case-id").value.trim();
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(caseId)}/review`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rating: Number($("acceptance-review-rating").value || 4),
            status: $("acceptance-review-status").value,
            playback_confirmed: $("acceptance-review-playback").checked,
            audio_mode: $("acceptance-review-audio-mode").value.trim() || "midi",
            notes: $("acceptance-review-notes").value,
          }),
        });
        await loadAcceptanceSuites();
      });
      $("acceptance-build-report")?.addEventListener("click", async () => {
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/report`, { method: "POST" });
        await loadAcceptanceSuites();
      });
      $("acceptance-refresh-suite-analytics")?.addEventListener("click", async () => {
        const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/analytics/refresh`, { method: "POST" });
        acceptanceAnalytics = data.analytics || acceptanceAnalytics;
        renderAcceptanceAnalytics(acceptanceAnalytics);
        await loadAcceptanceSuites();
      });
      $("acceptance-run-diff")?.addEventListener("click", async () => {
        const otherSuiteId = $("acceptance-diff-suite").value;
        if (!otherSuiteId) return;
        const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/diff`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ other_suite_id: otherSuiteId }),
        });
        $("acceptance-diff-status").value = (data.diff || {}).status || "-";
        $("acceptance-diff-result").textContent = JSON.stringify(data.diff || {}, null, 2);
      });
      $("acceptance-create-human-pack")?.addEventListener("click", async () => {
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        await loadAcceptanceSuites();
      });
      $("acceptance-zip-human-pack")?.addEventListener("click", async () => {
        const packId = ((await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`)).packs || [])[0]?.pack_id;
        if (!packId) return;
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs/${encodeURIComponent(packId)}/zip`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        await loadAcceptanceSuites();
      });
      $("acceptance-verify-human-pack")?.addEventListener("click", async () => {
        const packId = ((await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs`)).packs || [])[0]?.pack_id;
        if (!packId) return;
        const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/human-review-packs/${encodeURIComponent(packId)}/verify`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ strict: true }) });
        $("acceptance-human-review-result").textContent = JSON.stringify(data.report || data, null, 2);
      });
      $("acceptance-import-human-review")?.addEventListener("click", async () => {
        const raw = $("acceptance-human-review-response").value.trim();
        if (!raw) return;
        const response = JSON.parse(raw);
        const data = await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/review-imports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response }) });
        $("acceptance-human-review-result").textContent = JSON.stringify(data.import || data, null, 2);
        await loadAcceptanceSuites();
      });
      $("acceptance-signoff")?.addEventListener("click", async () => {
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/signoff`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ signed_by: "developer" }) });
        await loadAcceptanceSuites();
      });
      $("acceptance-reset-signoff")?.addEventListener("click", async () => {
        await api(`/api/acceptance/suites/${encodeURIComponent(suiteId)}/signoff/reset`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reason: "review update" }) });
        await loadAcceptanceSuites();
      });
    }

    function releaseProjectOptions() {
      return projects.map((project) => `<option value="${escapeHtml(project.project_id)}">${escapeHtml(project.name)} · ${escapeHtml(project.final_version_id || "-")}</option>`).join("");
    }

    function releaseActionButtons(release, signoffSummary) {
      const signed = ["signed", "force_signed"].includes(signoffSummary.status);
      return `
        <button id="release-add-track" type="button" ${signed || !projects.length ? "disabled" : ""}>Add Track</button>
        <button class="secondary" id="release-init-metadata" type="button" ${signed ? "disabled" : ""}>Initialize Metadata</button>
        <button class="secondary" id="release-refresh-metadata-qa" type="button">Refresh Metadata QA</button>
        <button class="secondary" id="release-export-metadata" type="button">Export Metadata</button>
        <button class="secondary" id="release-refresh-qa" type="button">Refresh Release QA</button>
        <button class="secondary" id="release-refresh-audio-qa" type="button">Refresh Release Audio QA</button>
        <button class="secondary" id="release-build-export" type="button" ${signed ? "disabled" : ""}>Build Release Export</button>
        <button class="secondary" id="release-build-zip" type="button">Build Release ZIP</button>
        <button id="release-signoff" type="button" ${signed ? "disabled" : ""}>Sign Release</button>
        <button class="danger" id="release-force-signoff" type="button" ${signed ? "disabled" : ""}>Force Sign</button>
        <button class="danger" id="release-reset-signoff" type="button" ${signed ? "" : "disabled"}>Reset Signoff</button>
        <button class="secondary" id="release-hide" type="button">${release.hidden ? "Unhide" : "Hide"}</button>
        <button class="secondary" id="release-archive" type="button">Archive</button>
        ${release.export_summary && release.export_summary.zip_filename ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/export.zip">Download Release ZIP</a>` : ""}
      `;
    }

    function releaseTrackTable(release) {
      const rows = (release.tracks || []).map((track) => `
        <tr>
          <td>${escapeHtml(track.disc_number || 1)}.${escapeHtml(track.track_number || 0)}</td>
          <td>${escapeHtml(track.title || "-")}</td>
          <td>${escapeHtml(track.project_id)}</td>
          <td>${escapeHtml(track.version_id || "-")}</td>
          <td>${escapeHtml(track.delivery_qa_status || "-")}</td>
          <td>${escapeHtml(track.delivery_signoff_status || "-")}</td>
          <td>
            <button class="secondary release-track-refresh" data-track-id="${escapeHtml(track.track_id)}" type="button">Refresh</button>
            <button class="danger release-track-remove" data-track-id="${escapeHtml(track.track_id)}" type="button">Remove</button>
          </td>
        </tr>
      `).join("");
      return `
        <div class="panel-title subhead"><span>Tracklist</span></div>
        <table>
          <thead><tr><th>#</th><th>Title</th><th>Project</th><th>Version</th><th>Delivery QA</th><th>Signoff</th><th>Actions</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='7'>No tracks yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseQaHtml(qaData) {
      const summary = (qaData && qaData.summary) || {};
      const report = (qaData && qaData.release_qa) || {};
      return `
        <div class="panel-title subhead"><span>Release QA</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.status || "-")}
          ${metric("Blockers", summary.blocker_count || 0)}
          ${metric("Warnings", summary.warning_count || 0)}
          ${metric("Tracks", summary.track_count || 0)}
        </div>
        ${deliveryChecksHtml([...(report.checks || []), ...(report.track_checks || [])])}
      `;
    }

    function releaseMetadataHtml(metadataData, release) {
      const metadata = (metadataData && metadataData.metadata) || {};
      const summary = (metadataData && metadataData.summary) || {};
      const qaSummary = (metadataData && metadataData.qa_summary) || {};
      const releaseMeta = metadata.release || {};
      const rows = (metadata.tracks || []).map((track) => `
        <tr>
          <td>${escapeHtml(track.track_number || "-")}</td>
          <td>${escapeHtml(track.title || "-")}</td>
          <td>${escapeHtml(track.display_artist || "-")}</td>
          <td>${escapeHtml(track.isrc || "-")}</td>
          <td>${track.explicit ? "yes" : "-"}</td>
          <td>${track.instrumental ? "yes" : "-"}</td>
          <td>${track.confirmed ? "yes" : "-"}</td>
        </tr>
      `).join("");
      return `
        <div class="panel-title subhead"><span>Release Metadata</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.exists ? "ready" : "missing")}
          ${metric("Metadata QA", qaSummary.status || summary.qa_status || "missing")}
          ${metric("Title", releaseMeta.title || release.name || "-")}
          ${metric("UPC", releaseMeta.upc || "-")}
        </div>
        <div class="grid2">
          <label>Release Title
            <input id="release-metadata-title" value="${escapeHtml(releaseMeta.title || release.name || "")}">
          </label>
          <label>UPC
            <input id="release-metadata-upc" value="${escapeHtml(releaseMeta.upc || "")}">
          </label>
        </div>
        <div class="actions">
          <button class="secondary" id="release-save-metadata" type="button" ${metadata.schema_version ? "" : "disabled"}>Save Metadata</button>
          ${summary.exists ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/metadata/platform.csv">Platform CSV</a>` : ""}
          ${summary.exists ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/metadata/credits.csv">Credits CSV</a>` : ""}
        </div>
        <table>
          <thead><tr><th>#</th><th>Title</th><th>Artist</th><th>ISRC</th><th>Explicit</th><th>Instrumental</th><th>Confirmed</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='7'>Initialize metadata to edit release and track fields.</td></tr>"}</tbody>
        </table>
        ${deliveryChecksHtml([...((metadataData.metadata_qa || {}).checks || []), ...((metadataData.metadata_qa || {}).track_checks || [])])}
      `;
    }

    function releaseAudioReviewHtml(audioReviewData, release) {
      const summary = (audioReviewData && audioReviewData.summary) || {};
      const reviews = (audioReviewData && audioReviewData.reviews) || [];
      const rows = (release.tracks || []).map((track) => {
        const review = reviews.find((item) => item.track_id === track.track_id && item.status === "accepted" && item.review_mode === "manual" && !item.stale) || reviews.find((item) => item.track_id === track.track_id) || {};
        return `
          <tr>
            <td>${escapeHtml(track.track_number || "-")}</td>
            <td>${escapeHtml(track.title || "-")}</td>
            <td>${escapeHtml(track.track_id || "-")}</td>
            <td>${escapeHtml(review.status || "missing")}</td>
            <td>${escapeHtml(review.review_mode || "-")}</td>
            <td>${escapeHtml(review.rating || "-")}</td>
            <td>${review.stale ? "yes" : "-"}</td>
            <td>${escapeHtml(((review.markers || []).length) || 0)}</td>
          </tr>
        `;
      }).join("");
      return `
        <div class="panel-title subhead"><span>Audio Review Board</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.status || "missing")}
          ${metric("Manual Accepted", summary.manual_accepted_track_count || 0)}
          ${metric("Missing", (summary.missing_track_ids || []).length)}
          ${metric("Stale", summary.stale_review_count || 0)}
        </div>
        <div class="grid2">
          <label>Review Track
            <select id="release-audio-review-track">${(release.tracks || []).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.track_number || "-")}. ${escapeHtml(track.title || track.track_id)}</option>`).join("")}</select>
          </label>
          <label>Reviewer
            <input id="release-audio-reviewer" value="local-user">
          </label>
        </div>
        <div class="grid2">
          <label>Status
            <select id="release-audio-review-status"><option value="accepted">accepted</option><option value="needs_fix">needs_fix</option><option value="rejected">rejected</option><option value="waived">waived</option></select>
          </label>
          <label>Rating
            <input id="release-audio-review-rating" type="number" min="0" max="5" value="4">
          </label>
        </div>
        <label>Notes
          <textarea id="release-audio-review-notes" rows="2"></textarea>
        </label>
        <div class="actions">
          <button class="secondary" id="release-refresh-audio-review-summary" type="button">Refresh Audio Review Summary</button>
          <button class="secondary" id="release-add-audio-review" type="button">Add Track Review</button>
          <button class="secondary release-marker-mix-patch-draft" data-endpoint="/api/releases/${encodeURIComponent(release.release_id)}/audio-reviews/{review_id}/markers/{marker_id}/mix-patch-draft" type="button" disabled>Create Mix Patch Draft</button>
        </div>
        <table>
          <thead><tr><th>#</th><th>Title</th><th>Track</th><th>Review</th><th>Mode</th><th>Rating</th><th>Stale</th><th>Markers</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='8'>No release tracks yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseAudioRevisionHtml(audioRevisionData, release) {
      const summary = (audioRevisionData && audioRevisionData.summary) || {};
      const sessions = (audioRevisionData && audioRevisionData.sessions) || [];
      const detail = (audioRevisionData && audioRevisionData.detail) || {};
      const issues = detail.issues || [];
      const candidates = detail.candidates || [];
      const latest = sessions[0] || {};
      const sessionId = latest.session_id || "";
      const rows = sessions.map((session) => `
        <tr>
          <td>${escapeHtml(session.session_id || "-")}</td>
          <td>${escapeHtml(session.status || "-")}</td>
          <td>${escapeHtml(session.issue_count || 0)}</td>
          <td>${escapeHtml(session.open_issue_count || 0)}</td>
          <td>${escapeHtml(session.applied_candidate_count || 0)}</td>
          <td>${session.stale ? "yes" : "-"}</td>
        </tr>
      `).join("");
      const issueRows = issues.map((issue) => `
        <tr>
          <td>${escapeHtml(issue.issue_id || "-")}</td>
          <td><span class="status ${escapeHtml(issue.status || "")}">${escapeHtml(issue.status || "-")}</span></td>
          <td>${escapeHtml(issue.track_id || "-")}</td>
          <td>${escapeHtml(issue.category || "-")}</td>
          <td>${escapeHtml(issue.severity || "-")}</td>
          <td>${escapeHtml(issue.selected_candidate_id || "-")}</td>
          <td>${escapeHtml(issue.applied_version_id || "-")}</td>
        </tr>
      `).join("");
      const candidateRows = candidates.map((candidate) => {
        const candidateId = candidate.candidate_id || "";
        const previewBase = `/api/releases/${encodeURIComponent(release.release_id)}/audio-revisions/${encodeURIComponent(sessionId)}/candidates/${encodeURIComponent(candidateId)}`;
        return `
          <tr>
            <td>${escapeHtml(candidateId || "-")}</td>
            <td><span class="status ${escapeHtml(candidate.status || "")}">${escapeHtml(candidate.status || "-")}</span></td>
            <td>${candidate.selected ? "yes" : "-"}</td>
            <td>${escapeHtml(candidate.score || 0)}</td>
            <td>${escapeHtml((candidate.review || {}).status || "-")}</td>
            <td>${escapeHtml(candidate.applied_version_id || "-")}</td>
            <td>${candidateId ? `<a href="${previewBase}/midi" target="_blank" rel="noreferrer">MIDI</a> · <a href="${previewBase}/audio" target="_blank" rel="noreferrer">WAV</a>` : "-"}</td>
          </tr>
        `;
      }).join("");
      const issueControl = issues.length
        ? `<select id="release-audio-revision-issue">${issues.map((issue) => `<option value="${escapeHtml(issue.issue_id || "")}">${escapeHtml(issue.issue_id || "-")} · ${escapeHtml(issue.status || "-")} · ${escapeHtml(issue.severity || "-")}</option>`).join("")}</select>`
        : `<input id="release-audio-revision-issue" placeholder="ari-000001">`;
      const candidateControl = candidates.length
        ? `<select id="release-audio-revision-candidate">${candidates.map((candidate) => `<option value="${escapeHtml(candidate.candidate_id || "")}">${escapeHtml(candidate.candidate_id || "-")} · ${escapeHtml(candidate.status || "-")}${candidate.selected ? " · selected" : ""}</option>`).join("")}</select>`
        : `<input id="release-audio-revision-candidate" placeholder="arc-000001">`;
      return `
        <div class="panel-title subhead"><span>Audio Revision Workbench</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.status || "missing")}
          ${metric("Sessions", summary.session_count || sessions.length || 0)}
          ${metric("Open Issues", summary.open_issue_count || 0)}
          ${metric("Rechecked", summary.rechecked_issue_count || 0)}
        </div>
        <div class="grid2">
          <label>Session
            <select id="release-audio-revision-session">${sessions.map((session) => `<option value="${escapeHtml(session.session_id || "")}">${escapeHtml(session.session_id || "-")} · ${escapeHtml(session.status || "-")}</option>`).join("")}</select>
          </label>
          <label>Issue
            ${issueControl}
          </label>
        </div>
        <div class="grid2">
          <label>Candidate
            ${candidateControl}
          </label>
          <label>Session Title
            <input id="release-audio-revision-title" value="Audio revision pass">
          </label>
        </div>
        <div class="actions">
          <button class="secondary" id="release-create-audio-revision" type="button">Create Revision Session</button>
          <button class="secondary" id="release-generate-audio-revision-candidates" type="button" ${sessionId ? "" : "disabled"}>Generate Candidates</button>
          <button class="secondary" id="release-review-audio-revision-candidate" type="button" ${sessionId ? "" : "disabled"}>Accept Candidate</button>
          <button class="secondary" id="release-select-audio-revision-candidate" type="button" ${sessionId ? "" : "disabled"}>Select Candidate</button>
          <button class="secondary" id="release-apply-audio-revision-candidate" type="button" ${sessionId ? "" : "disabled"}>Apply Candidate</button>
          <button class="secondary" id="release-refresh-audio-revision" type="button" ${sessionId ? "" : "disabled"}>Refresh Recheck</button>
          <button class="secondary" id="release-close-audio-revision" type="button" ${sessionId ? "" : "disabled"}>Close Session</button>
        </div>
        <table>
          <thead><tr><th>Issue</th><th>Status</th><th>Track</th><th>Category</th><th>Severity</th><th>Selected Candidate</th><th>Applied Version</th></tr></thead>
          <tbody>${issueRows || "<tr><td colspan='7'>No audio revision issues yet.</td></tr>"}</tbody>
        </table>
        <table>
          <thead><tr><th>Candidate</th><th>Status</th><th>Selected</th><th>Score</th><th>Review</th><th>Applied Version</th><th>A/B Preview</th></tr></thead>
          <tbody>${candidateRows || "<tr><td colspan='7'>No audio revision candidates yet.</td></tr>"}</tbody>
        </table>
        <table>
          <thead><tr><th>Session</th><th>Status</th><th>Issues</th><th>Open</th><th>Applied</th><th>Stale</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='6'>No audio revision sessions yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseMasteringHtml(masteringData, release) {
      const summary = (masteringData && masteringData.summary) || {};
      const analysis = (masteringData && masteringData.analysis) || {};
      const plan = (masteringData && masteringData.plan) || {};
      const candidates = (masteringData && masteringData.candidates) || [];
      const selectedId = ((masteringData && masteringData.selected_candidate) || {}).candidate_id || "";
      const candidateOptions = candidates.map((candidate) => `<option value="${escapeHtml(candidate.candidate_id || "")}" ${candidate.candidate_id === selectedId ? "selected" : ""}>${escapeHtml(candidate.candidate_id || "-")} · ${escapeHtml(candidate.status || "-")}${candidate.selected ? " · selected" : ""}</option>`).join("");
      const rows = (analysis.tracks || []).map((track) => `
        <tr>
          <td>${escapeHtml(track.track_id || "-")}</td>
          <td><span class="status ${escapeHtml(track.status || "")}">${escapeHtml(track.status || "-")}</span></td>
          <td>${escapeHtml(((track.metrics || {}).loudness_proxy_db ?? "-"))}</td>
          <td>${escapeHtml(((track.metrics || {}).peak_dbfs ?? "-"))}</td>
          <td>${escapeHtml(((track.metrics || {}).clipping_ratio ?? "-"))}</td>
          <td>${escapeHtml(((track.metrics || {}).leading_silence_seconds ?? "-"))}</td>
          <td>${escapeHtml(((track.metrics || {}).trailing_silence_seconds ?? "-"))}</td>
        </tr>
      `).join("");
      return `
        <div class="panel-title subhead"><span>Mastering QA</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.status || "missing")}
          ${metric("Profile", summary.profile_id || "demo_review")}
          ${metric("Avg Loudness", summary.average_loudness_proxy_db ?? "-")}
          ${metric("Max Delta", summary.max_track_loudness_delta_db ?? "-")}
          ${metric("Candidate", summary.selected_candidate_id || "-")}
          ${metric("Actions", (plan.summary || {}).action_count || 0)}
        </div>
        <div class="grid2">
          <label>Mastering Profile
            <select id="release-mastering-profile">
              <option value="demo_review">demo_review</option>
              <option value="streaming_balanced">streaming_balanced</option>
              <option value="album_consistency">album_consistency</option>
              <option value="podcast_music_bed">podcast_music_bed</option>
            </select>
          </label>
          <label>Candidate
            <select id="release-mastering-candidate">${candidateOptions || "<option value=''>none</option>"}</select>
          </label>
        </div>
        <div class="actions">
          <button class="secondary" id="release-mastering-analyze" type="button">Analyze Mastering</button>
          <button class="secondary" id="release-mastering-plan" type="button">Create Mastering Plan</button>
          <button class="secondary" id="release-render-mastering-candidate" type="button">Render Mastered Candidate</button>
          <button class="secondary" id="release-mastering-review" type="button">Accept Mastered Candidate</button>
          <button class="secondary" id="release-mastering-select" type="button">Select Mastered Candidate</button>
          <button class="secondary" id="release-mastering-reset" type="button">Reset Mastering</button>
        </div>
        <table>
          <thead><tr><th>Track</th><th>Status</th><th>Loudness Proxy</th><th>Peak dBFS</th><th>Clip</th><th>Lead Silence</th><th>Tail Silence</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='7'>No mastering analysis yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseEncodedAudioHtml(encodedAudioData, release) {
      const summary = (encodedAudioData && encodedAudioData.summary) || {};
      const profiles = (encodedAudioData && encodedAudioData.profiles) || [];
      const profileRows = profiles.map((profile) => `
        <tr>
          <td>${escapeHtml(profile.profile_id || "-")}</td>
          <td><span class="status ${escapeHtml(profile.status || "")}">${escapeHtml(profile.status || "-")}</span></td>
          <td>${escapeHtml(profile.format || "-")}</td>
          <td>${escapeHtml(profile.extension || "-")}</td>
          <td>${escapeHtml(profile.completed_count || 0)}/${escapeHtml(profile.track_count || 0)}</td>
          <td>${profile.current === false ? "stale" : "current"}</td>
        </tr>
      `).join("");
      return `
        <div class="panel-title subhead"><span>Encoded Audio Formats</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.status || "missing")}
          ${metric("Profiles", summary.profile_count || 0)}
          ${metric("Completed", (summary.completed_profiles || []).length || 0)}
          ${metric("Failed", (summary.failed_profiles || []).length || 0)}
        </div>
        <div class="grid2">
          <label>Format Profiles
            <input id="release-encoded-audio-profiles" value="mp3_320,flac_lossless">
          </label>
        </div>
        <div class="actions">
          <button class="secondary" id="release-render-encoded-audio" type="button">Render Encoded Audio</button>
          <button class="secondary" id="release-verify-encoded-audio" type="button">Verify Encoded Audio</button>
          <button class="secondary" id="release-refresh-encoded-audio-health" type="button">Refresh Encoded Health</button>
          <button class="secondary" id="release-reset-encoded-audio" type="button">Reset Encoded Audio</button>
        </div>
        <table>
          <thead><tr><th>Profile</th><th>Status</th><th>Format</th><th>Ext</th><th>Tracks</th><th>Current</th></tr></thead>
          <tbody>${profileRows || "<tr><td colspan='6'>No encoded audio profiles yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseFormatDecisionHtml(formatDecisionData, release) {
      const sessions = (formatDecisionData && formatDecisionData.sessions) || [];
      const active = (formatDecisionData && formatDecisionData.active_session) || {};
      const latest = sessions[0] || {};
      return `
        <div class="panel-title subhead"><span>Format Decision Workbench</span></div>
        <div class="summary-grid">
          ${metric("Sessions", sessions.length || 0)}
          ${metric("Active", active.session_id || "-")}
          ${metric("Latest", latest.session_id || "-")}
          ${metric("Status", latest.status || "missing")}
        </div>
        <div class="grid2">
          <label>Candidate Profiles
            <input id="release-format-decision-profiles" value="mp3_320,flac_lossless">
          </label>
          <label>Selected Profiles
            <input id="release-format-decision-selected" value="mp3_320">
          </label>
          <label>Archive Profiles
            <input id="release-format-decision-archive" value="flac_lossless">
          </label>
          <label>Rejected Profiles
            <input id="release-format-decision-rejected" value="">
          </label>
        </div>
        <label>Decision Reason
          <textarea id="release-format-decision-reason" rows="2"></textarea>
        </label>
        <div class="actions">
          <button class="secondary" id="release-create-format-decision" type="button">Create Format Decision</button>
        </div>
      `;
    }

    function releaseRightsClearanceHtml(rightsData, release) {
      const report = (rightsData && rightsData.report) || {};
      const parties = (rightsData && rightsData.parties) || [];
      const rows = (report.tracks || []).map((track) => `
        <tr>
          <td>${escapeHtml(track.track_id || "-")}</td>
          <td><span class="status ${escapeHtml(track.status || "")}">${escapeHtml(track.status || "-")}</span></td>
          <td>${escapeHtml(track.manual_clearance_status || "-")}</td>
          <td>${escapeHtml((track.failures || []).join(", ") || "-")}</td>
        </tr>
      `).join("");
      const trackOptions = (release.tracks || []).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(`${track.track_number || ""} ${track.title || track.track_id}`)}</option>`).join("");
      const partyOptions = parties.map((party) => `<option value="${escapeHtml(party.party_id || "")}">${escapeHtml(party.public_credit_name || party.display_name || party.party_id)}</option>`).join("");
      return `
        <div class="panel-title subhead"><span>Rights Clearance</span></div>
        <div class="summary-grid">
          ${metric("Status", report.status || "missing")}
          ${metric("Tracks", report.track_count || 0)}
          ${metric("Manual Cleared", report.manual_cleared_track_count || 0)}
          ${metric("Parties", parties.length || 0)}
        </div>
        <div class="grid2">
          <label>Party Name
            <input id="rights-party-name" value="MusicForge">
          </label>
          <label>Public Credit
            <input id="rights-party-credit" value="MusicForge">
          </label>
          <label>Track
            <select id="rights-track-id">${trackOptions}</select>
          </label>
          <label>Contributor
            <select id="rights-party-id">${partyOptions}</select>
          </label>
          <label>Role
            <select id="rights-contributor-role"><option value="composer">composer</option><option value="lyricist">lyricist</option><option value="producer">producer</option><option value="performer">performer</option></select>
          </label>
          <label>Share
            <input id="rights-contributor-share" type="number" value="100" min="0" max="100">
          </label>
        </div>
        <label>Attestation
          <textarea id="rights-attestation" rows="2">Original composition rights confirmed.</textarea>
        </label>
        <div class="actions">
          <button class="secondary" id="rights-create-party" type="button">Create Party</button>
          <button class="secondary" id="rights-save-track" type="button">Save Track Rights</button>
          <button class="secondary" id="rights-review-track" type="button">Accept Rights</button>
          <button class="secondary" id="rights-refresh-report" type="button">Refresh Rights Report</button>
        </div>
        <table>
          <thead><tr><th>Track</th><th>Status</th><th>Manual</th><th>Failures</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='4'>No rights report yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseOperationsHtml(operationsData, reviewerPackData, release) {
      const summary = (operationsData && operationsData.summary) || {};
      const report = (operationsData && operationsData.report) || {};
      const progress = report.stage_progress || {};
      const manifest = operationsData.manifest || {};
      const zip = operationsData.zip || manifest.zip || {};
      const runbooks = operationsData.runbooks || [];
      const activeRunbook = runbooks[0] || {};
      const runbookSummary = activeRunbook.summary || {};
      const audit = operationsData.audit || {};
      const auditSummary = audit.summary || {};
      const reviewerSummary = (reviewerPackData && reviewerPackData.summary) || {};
      const reviewerReport = (reviewerPackData && reviewerPackData.report) || {};
      const retrospectiveSummary = (reviewerPackData && reviewerPackData.retrospective_summary) || {};
      const reviewerFindings = (reviewerReport.warnings || []).slice(0, 5).map((item) => `
        <tr><td>${escapeHtml(item.check_id || "-")}</td><td>${escapeHtml(item.message || "-")}</td></tr>
      `).join("");
      const stageRows = (report.stage_statuses || []).map((stage) => `
        <tr>
          <td>${escapeHtml(stage.stage || "-")}</td>
          <td><span class="status ${escapeHtml(stage.status || "")}">${escapeHtml(stage.status || "-")}</span></td>
          <td>${escapeHtml(stage.blocker_count || 0)}</td>
          <td>${escapeHtml(stage.warning_count || 0)}</td>
        </tr>
      `).join("");
      const actionRows = (report.next_actions || []).slice(0, 8).map((action) => `
        <tr>
          <td>${escapeHtml(action.label || action.action_type || "-")}</td>
          <td>${escapeHtml(action.entity_id || "-")}</td>
          <td>${escapeHtml((action.blocked_by || []).join(", ") || "-")}</td>
          <td>${escapeHtml((action.unblocks || []).join(", ") || "-")}</td>
        </tr>
      `).join("");
      const runbookOptions = runbooks.map((runbook) => `<option value="${escapeHtml(runbook.runbook_id || "")}">${escapeHtml(runbook.runbook_id || "-")} · ${escapeHtml(runbook.status || "-")}</option>`).join("");
      const runbookRows = runbooks.slice(0, 8).map((runbook) => {
        const itemSummary = runbook.summary || {};
        return `
          <tr>
            <td>${escapeHtml(runbook.runbook_id || "-")}</td>
            <td><span class="status ${escapeHtml(runbook.status || "")}">${escapeHtml(runbook.status || "-")}</span></td>
            <td>${escapeHtml(itemSummary.safe_count || 0)}</td>
            <td>${escapeHtml(itemSummary.manual_required_count || 0)}</td>
            <td>${escapeHtml(itemSummary.failed_count || 0)}</td>
          </tr>
        `;
      }).join("");
      const operationsSignoff = report.operations_signoff || (summary.operations_signoff || {});
      return `
        <div class="panel-title subhead"><span>Release Operations</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.status || report.status || "missing")}
          ${metric("Stage", summary.current_stage || report.current_stage || "draft")}
          ${metric("Next", summary.next_stage || report.next_stage || "-")}
          ${metric("Progress", `${progress.completed_count || 0}/${progress.total_count || 0}`)}
          ${metric("Blockers", summary.blocker_count || 0)}
          ${metric("Warnings", summary.warning_count || 0)}
          ${metric("Stale", operationsData.stale ? "yes" : "-")}
          ${metric("Integrity", operationsData.integrity_ok === false ? "failed" : "ok")}
        </div>
        <div class="actions">
          <button class="secondary" id="release-operations-refresh" type="button">Refresh Operations</button>
          <button class="secondary" id="release-operations-export" type="button">Export Operations</button>
          <button class="secondary" id="release-operations-zip" type="button">Build Operations ZIP</button>
          <button class="secondary" id="release-operations-verify" type="button">Verify Operations ZIP</button>
          ${(zip.filename || (manifest.zip || {}).filename) ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/export.zip">Download Operations ZIP</a>` : ""}
        </div>
        <table>
          <thead><tr><th>Stage</th><th>Status</th><th>Blockers</th><th>Warnings</th></tr></thead>
          <tbody>${stageRows || "<tr><td colspan='4'>No Operations report yet.</td></tr>"}</tbody>
        </table>
        <table>
          <thead><tr><th>Next Action</th><th>Entity</th><th>Blocked By</th><th>Unblocks</th></tr></thead>
          <tbody>${actionRows || "<tr><td colspan='4'>No pending Operations actions.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Release Operations Runbook</span></div>
        <div class="summary-grid">
          ${metric("Runbook", activeRunbook.runbook_id || "missing")}
          ${metric("Status", activeRunbook.status || "-")}
          ${metric("Safe Actions", runbookSummary.safe_count || 0)}
          ${metric("Manual Required", runbookSummary.manual_required_count || 0)}
          ${metric("Failed", runbookSummary.failed_count || 0)}
        </div>
        <div class="actions">
          <select id="release-runbook-id">${runbookOptions || "<option value=''>No runbook</option>"}</select>
          <button class="secondary" id="release-runbook-create" type="button">Create Runbook</button>
          <button class="secondary" id="release-runbook-run-safe" type="button">Run Safe Actions</button>
          <button class="secondary" id="release-runbook-refresh-stale" type="button">Refresh Runbook Stale</button>
          <button class="secondary" id="release-runbook-export" type="button">Export Runbook</button>
          <button class="secondary" id="release-runbook-zip" type="button">Build Runbook ZIP</button>
          <button class="secondary" id="release-runbook-verify" type="button">Verify Runbook ZIP</button>
          ${activeRunbook.runbook_id ? `<a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/runbooks/${encodeURIComponent(activeRunbook.runbook_id)}/export.zip">Download Runbook ZIP</a>` : ""}
        </div>
        <table>
          <thead><tr><th>Runbook</th><th>Status</th><th>Safe</th><th>Manual Required</th><th>Failed</th></tr></thead>
          <tbody>${runbookRows || "<tr><td colspan='5'>No Operations Runbooks yet.</td></tr>"}</tbody>
        </table>
        <div class="panel-title subhead"><span>Release Operations Signoff</span></div>
        <div class="summary-grid">
          ${metric("Signoff", operationsSignoff.status || "not_signed")}
          ${metric("Signed By", operationsSignoff.signed_by || "-")}
          ${metric("Stale", operationsSignoff.stale ? "yes" : "-")}
          ${metric("Integrity", operationsSignoff.integrity_ok === false ? "failed" : "ok")}
        </div>
        <div class="grid2">
          <label>Operations Signed By <input id="release-operations-signed-by" value="local-user"></label>
          <label>Operations Reset Reason <input id="release-operations-reset-reason" value="Approved operations evidence change"></label>
          <label>Change Request Reason <input id="release-operations-change-reason" value="Refresh archived operations evidence after approved change"></label>
          <label>Change Request Scope <input id="release-operations-change-scope" value="operations,release_export"></label>
          <label>Change Request ID <input id="release-operations-change-id" placeholder="ocr-000001"></label>
        </div>
        <div class="actions">
          <button class="secondary" id="release-operations-sign" type="button">Sign Operations</button>
          <button class="secondary" id="release-operations-archive-export" type="button">Export Archive</button>
          <button class="secondary" id="release-operations-archive-zip" type="button">Build Archive ZIP</button>
          <button class="secondary" id="release-operations-archive-verify" type="button">Verify Archive ZIP</button>
          <button class="secondary" id="release-operations-change-create" type="button">Create Change Request</button>
          <button class="danger" id="release-operations-reset-signoff" type="button">Reset Operations Signoff</button>
          <a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/archive.zip">Download Archive ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Release Operations Audit Ledger</span></div>
        <div class="summary-grid">
          ${metric("Audit", auditSummary.status || "missing")}
          ${metric("Entries", auditSummary.entry_count || 0)}
          ${metric("Blockers", auditSummary.blocker_count || 0)}
          ${metric("Warnings", auditSummary.warning_count || 0)}
          ${metric("Integrity", auditSummary.integrity_ok === false ? "failed" : "ok")}
        </div>
        <div class="actions">
          <button class="secondary" id="release-operations-audit-refresh" type="button">Refresh Audit Ledger</button>
          <button class="secondary" id="release-operations-audit-export" type="button">Export Audit Package</button>
          <button class="secondary" id="release-operations-audit-zip" type="button">Build Audit ZIP</button>
          <button class="secondary" id="release-operations-audit-verify" type="button">Verify Audit ZIP</button>
          <a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/audit.zip">Download Audit ZIP</a>
        </div>
        <div class="panel-title subhead"><span>Reviewer Pack</span></div>
        <div class="summary-grid">
          ${metric("Reviewer", reviewerSummary.status || "missing")}
          ${metric("Readiness", reviewerSummary.readiness || "-")}
          ${metric("Audit", reviewerSummary.audit_status || "-")}
          ${metric("Archive", reviewerSummary.archive_verified ? "verified" : "-")}
          ${metric("Warnings", reviewerSummary.warning_count || 0)}
          ${metric("Retrospective", retrospectiveSummary.status || "missing")}
        </div>
        <div class="actions">
          <button class="secondary" id="release-reviewer-pack-refresh" type="button">Refresh Reviewer Report</button>
          <button class="secondary" id="release-reviewer-pack-export" type="button">Export Reviewer Pack</button>
          <button class="secondary" id="release-reviewer-pack-zip" type="button">Build Reviewer ZIP</button>
          <button class="secondary" id="release-reviewer-pack-verify" type="button">Verify Reviewer ZIP</button>
          <a class="button-link secondary" href="/api/releases/${encodeURIComponent(release.release_id)}/operations/reviewer-pack.zip">Download Reviewer ZIP</a>
        </div>
        <table>
          <thead><tr><th>Risk hotspots</th><th>Reviewer note</th></tr></thead>
          <tbody>${reviewerFindings || "<tr><td colspan='2'>No Reviewer Pack warnings.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseExportHtml(exportData, release) {
      const manifest = (exportData && exportData.manifest) || {};
      const zip = manifest.zip || {};
      const rows = (manifest.files || []).slice(0, 80).map((file) => `
        <tr><td>${escapeHtml(file.kind || "-")}</td><td>${escapeHtml(file.path || "-")}</td><td>${escapeHtml(file.size_bytes || 0)}</td></tr>
      `).join("");
      return `
        <div class="panel-title subhead"><span>Release Export</span></div>
        <div class="summary-grid">
          ${metric("Status", (exportData.summary || {}).status || (manifest.schema_version ? "built" : "missing"))}
          ${metric("Files", (manifest.summary || {}).file_count || 0)}
          ${metric("Tracks", (manifest.summary || {}).track_count || (release.tracks || []).length)}
          ${metric("ZIP", zip.filename || "-")}
        </div>
        <table>
          <thead><tr><th>Kind</th><th>Path</th><th>Size</th></tr></thead>
          <tbody>${rows || "<tr><td colspan='3'>No release export yet.</td></tr>"}</tbody>
        </table>
      `;
    }

    function releaseAcceptanceAnalyticsHtml(analyticsData, release) {
      const summary = (analyticsData && analyticsData.summary) || {};
      const report = (analyticsData && analyticsData.analytics) || {};
      return `
        <div class="panel-title subhead"><span>Acceptance Analytics</span></div>
        <div class="summary-grid">
          ${metric("Readiness", summary.readiness_status || "missing")}
          ${metric("Cases", summary.case_count || 0)}
          ${metric("Needs Fix", summary.needs_fix_count || 0)}
          ${metric("Blocked", summary.blocked_count || 0)}
          ${metric("Report", report.report_id || "-")}
          ${metric("Stale", report.stale ? "yes" : "-")}
        </div>
        <div class="actions">
          <button class="secondary" id="release-refresh-acceptance-analytics" type="button">Refresh Acceptance Analytics</button>
        </div>
      `;
    }

    function releaseSignoffHtml(signoffData) {
      const summary = (signoffData && signoffData.summary) || {};
      const signoff = (signoffData && signoffData.signoff) || {};
      const gate = summary.acceptance_gate || signoff.acceptance_gate || {};
      const analyticsGate = gate.acceptance_analytics || {};
      return `
        <div class="panel-title subhead"><span>Release Signoff</span></div>
        <div class="summary-grid">
          ${metric("Status", summary.status || "not_signed")}
          ${metric("Signed At", summary.signed_at || "-")}
          ${metric("Signed By", summary.signed_by || "-")}
          ${metric("Forced", summary.forced ? "yes" : "-")}
          ${metric("Acceptance Gate", gate.status || "-")}
          ${metric("Acceptance Suite", gate.suite_id || "-")}
          ${metric("Analytics", analyticsGate.readiness_status || "-")}
        </div>
        <div class="grid2">
          <label>Signed By
            <input id="release-signed-by" value="${escapeHtml(signoff.signed_by || "local-user")}">
          </label>
          <label>Acceptance Suite
            <select id="release-acceptance-suite">
              <option value="">none</option>
              ${acceptanceSuiteOptions((gate || {}).suite_id || "")}
            </select>
          </label>
        </div>
        <div class="grid2">
          <label>Reset Reason
            <input id="release-reset-reason" placeholder="Reason required before reset">
          </label>
          <label>Gate Status
            <input value="${escapeHtml(gate.acceptance_status || "-")}" readonly>
          </label>
        </div>
        <label>Notes
          <textarea id="release-signoff-notes" rows="2">${escapeHtml(signoff.notes || "")}</textarea>
        </label>
        <label>Override Reason
          <textarea id="release-override-reason" rows="2" placeholder="Required for force sign"></textarea>
        </label>
        <label class="inline">
          <input id="release-require-per-track-audio-review" type="checkbox">
          Require per-track audio review
        </label>
        <label class="inline">
          <input id="release-require-stem-audio-health" type="checkbox">
          Require stem audio health
        </label>
        <label class="inline">
          <input id="release-require-current-mix-state" type="checkbox">
          Require current mix state
        </label>
        <label class="inline">
          <input id="release-require-audio-revision-closeout" type="checkbox">
          Require audio revision closeout
        </label>
        <label class="inline">
          <input id="release-require-mastering-qa" type="checkbox">
          Require mastering QA
        </label>
        <label class="inline">
          <input id="release-require-encoded-audio" type="checkbox">
          Require encoded audio
        </label>
        <label class="inline">
          <input id="release-require-encoded-audio-review" type="checkbox">
          Require encoded audio review
        </label>
        <label class="inline">
          <input id="release-require-format-decision" type="checkbox">
          Require format decision
        </label>
        <label class="inline">
          <input id="release-require-rights-clearance" type="checkbox">
          Require rights clearance
        </label>
        <label>Required Audio Formats
          <input id="release-required-audio-formats" value="mp3_320">
        </label>
      `;
    }

    function releaseSignoffPayload(force) {
      return {
        force,
        signed_by: $("release-signed-by").value.trim() || "local-user",
        notes: $("release-signoff-notes").value.trim(),
        override_reason: $("release-override-reason").value.trim(),
        acceptance_suite_id: $("release-acceptance-suite").value,
        require_per_track_audio_review: $("release-require-per-track-audio-review")?.checked || false,
        require_stem_audio_health: $("release-require-stem-audio-health")?.checked || false,
        require_current_mix_state: $("release-require-current-mix-state")?.checked || false,
        require_audio_revision_closeout: $("release-require-audio-revision-closeout")?.checked || false,
        require_mastering_qa: $("release-require-mastering-qa")?.checked || false,
        require_encoded_audio: $("release-require-encoded-audio")?.checked || false,
        require_encoded_audio_review: $("release-require-encoded-audio-review")?.checked || false,
        require_format_decision: $("release-require-format-decision")?.checked || false,
        require_rights_clearance: $("release-require-rights-clearance")?.checked || false,
        required_audio_format_profiles: ($("release-required-audio-formats")?.value || "").split(",").map((item) => item.trim()).filter(Boolean),
        mastering_profile_id: $("release-mastering-profile")?.value || "",
      };
    }

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

    async function renderProjectDetail(projectId) {
      const data = await api(`/api/projects/${encodeURIComponent(projectId)}`);
      const project = data.project;
      const versions = data.versions || [];
      const tabs = ["versions", "variation", "edit", "editor", "mix-board", "review-workbench", "review-sprints", "candidates", "quality-gate", "final-export", "references", "compare", "export", "events"];
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
        <label>Asset References
          <div id="project-version-asset-refs" class="asset-ref-list"></div>
        </label>
        <label>Reference Materials
          <div id="project-version-reference-refs" class="reference-ref-list"></div>
        </label>
        <label>Context Pack
          <select id="project-version-context-pack" class="context-pack-select"><option value="">none</option></select>
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
      renderAssetSelectors();
      renderReferenceSelectors();
      renderContextPackSelectors();
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
            asset_refs: assetRefsPayload("project-version-asset-refs"),
            reference_refs: referenceRefsPayload("project-version-reference-refs"),
            context_pack_id: contextPackIdPayload("project-version-context-pack"),
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
        if (target.dataset.projectEditorVersion) {
          projectEditorParentId = target.dataset.projectEditorVersion;
          activeProjectTab = "editor";
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
          return;
        }
        if (target.dataset.projectExtractVersion) {
          await api("/api/assets/extract/from-project-version", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project_id: project.project_id,
              version_id: target.dataset.projectExtractVersion,
              asset_types: [target.dataset.assetType || "motif"],
              section_name: "chorus",
              tags: ["studio"],
              favorite: true,
            }),
          });
          await loadAssets();
        }
      });
    }

    async function renderProjectTab(project, versions) {
      const target = $("project-tab-content");
      if (activeProjectTab === "versions") {
        target.innerHTML = projectVersionsTable(project, versions);
      } else if (activeProjectTab === "variation") {
        target.innerHTML = projectVariationControls(project, versions);
        renderAssetSelectors();
        renderContextPackSelectors();
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
      } else if (activeProjectTab === "editor") {
        await renderProjectEditor(project, versions, target);
      } else if (activeProjectTab === "mix-board") {
        await renderProjectMixBoard(project, versions, target);
      } else if (activeProjectTab === "review-workbench") {
        await renderProjectReviewWorkbench(project, versions, target);
      } else if (activeProjectTab === "review-sprints") {
        await renderProjectReviewSprints(project, versions, target);
      } else if (activeProjectTab === "candidates") {
        await renderProjectCandidates(project, versions, target);
      } else if (activeProjectTab === "quality-gate") {
        await renderProjectQualityGate(project, versions, target);
      } else if (activeProjectTab === "final-export") {
        await renderProjectFinalExport(project, versions, target);
      } else if (activeProjectTab === "references") {
        await renderProjectReferences(project, target);
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

    async function renderProjectMixBoard(project, versions, target) {
      const versionId = (project.selected_version_id || project.final_version_id || (versions[versions.length - 1] || {}).version_id || "").trim();
      let stateData = {};
      let stemHealth = {};
      if (versionId) {
        try { stateData = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(versionId)}/mix-state`); } catch (err) { stateData = { error: err.message }; }
        try { stemHealth = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(versionId)}/mix-stems/health`); } catch (err) { stemHealth = { summary: { status: "missing" } }; }
      }
      const state = stateData.mix_state || {};
      const tracks = state.tracks || [];
      const selectedOptions = versions.map((version) => `<option value="${escapeHtml(version.version_id)}" ${version.version_id === versionId ? "selected" : ""}>${escapeHtml(version.version_id)} · ${escapeHtml(version.name || version.job_id)}</option>`).join("");
      target.innerHTML = `
        <div class="panel-title subhead"><span>Mix Board</span></div>
        <div class="summary-grid">
          ${metric("Version", versionId || "-")}
          ${metric("Mix State", stateData.summary ? "ready" : (stateData.error || "missing"))}
          ${metric("Stem Health", (stemHealth.summary || {}).status || "missing")}
          ${metric("Tracks", tracks.length || 0)}
        </div>
        <div class="grid2">
          <label>Version
            <select id="mix-board-version">${selectedOptions}</select>
          </label>
          <label>Patch Label
            <input id="mix-patch-label" value="Mix Board preview">
          </label>
        </div>
        <div class="grid2">
          <label>Track
            <select id="mix-track-id">${tracks.map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.track_id)} · ${escapeHtml(track.name)}</option>`).join("")}</select>
          </label>
          <label>Volume dB
            <input id="mix-track-volume" type="number" min="-36" max="12" step="0.5" value="-2">
          </label>
        </div>
        <div class="grid2">
          <label>Pan
            <input id="mix-track-pan" type="number" min="-100" max="100" step="1" value="0">
          </label>
          <label>Velocity Scale
            <input id="mix-track-velocity" type="number" min="0" max="2" step="0.05" value="1">
          </label>
        </div>
        <div class="actions">
          <label class="inline"><input id="mix-track-mute" type="checkbox"> Mute</label>
          <label class="inline"><input id="mix-track-solo" type="checkbox"> Solo</label>
          <button class="secondary" id="mix-preview-create" type="button">Create Preview</button>
          <button class="secondary" id="mix-stems-render" type="button">Render Stems</button>
          <button class="secondary" id="mix-state-reset" type="button">Reset Mix State</button>
        </div>
        <pre id="mix-board-result">${escapeHtml(JSON.stringify({ mix_state: state, stem_health: stemHealth.summary || {} }, null, 2))}</pre>
      `;
      $("mix-board-version")?.addEventListener("change", async () => {
        await renderProjectMixBoard(project, versions, target);
      });
      bindAction("mix-preview-create", async () => {
        const selectedVersion = $("mix-board-version").value;
        const operations = [
          { op: "set_track_volume", track_id: $("mix-track-id").value, volume_db: Number($("mix-track-volume").value || 0) },
          { op: "set_track_pan", track_id: $("mix-track-id").value, pan: Number($("mix-track-pan").value || 0) },
          { op: "set_track_velocity_scale", track_id: $("mix-track-id").value, velocity_scale: Number($("mix-track-velocity").value || 1) },
        ];
        if ($("mix-track-mute").checked) operations.push({ op: "set_track_mute", track_id: $("mix-track-id").value, mute: true });
        if ($("mix-track-solo").checked) operations.push({ op: "set_track_solo", track_id: $("mix-track-id").value, solo: true });
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(selectedVersion)}/mix-preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label: $("mix-patch-label").value.trim(), operations }),
        });
        $("mix-board-result").textContent = JSON.stringify(data, null, 2);
      });
      bindAction("mix-stems-render", async () => {
        const selectedVersion = $("mix-board-version").value;
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(selectedVersion)}/mix-stems/render`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ require_wav: false }),
        });
        $("mix-board-result").textContent = JSON.stringify(data.summary || data, null, 2);
      });
      bindAction("mix-state-reset", async () => {
        const selectedVersion = $("mix-board-version").value;
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent(selectedVersion)}/mix-state/reset`, { method: "POST" });
        $("mix-board-result").textContent = JSON.stringify(data.mix_state || data, null, 2);
      });
    }

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
              <button class="secondary" data-project-editor-version="${escapeHtml(version.version_id)}" type="button">Open Editor</button>
              <button class="secondary" data-project-evaluate-version="${escapeHtml(version.version_id)}" type="button">Evaluate Gate</button>
              <button class="secondary" data-project-export-version="${escapeHtml(version.version_id)}" type="button">Export Final</button>
              <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="motif" type="button">Save Motif</button>
              <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="chord_progression" type="button">Save Chords</button>
              <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="drum_pattern" type="button">Save Drums</button>
              <button class="secondary" data-project-extract-version="${escapeHtml(version.version_id)}" data-asset-type="bass_pattern" type="button">Save Bass</button>
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
        <label>Asset References
          <div id="project-variation-asset-refs" class="asset-ref-list"></div>
        </label>
        <label>Reference Materials
          <div id="project-variation-reference-refs" class="reference-ref-list"></div>
        </label>
        <label>Context Pack
          <select id="project-variation-context-pack" class="context-pack-select"><option value="">none</option></select>
        </label>
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
      const refs = assetRefsPayload("project-variation-asset-refs");
      if (refs.length) payload.asset_refs = refs;
      const referenceRefs = referenceRefsPayload("project-variation-reference-refs");
      if (referenceRefs.length) payload.reference_refs = referenceRefs;
      const contextPackId = contextPackIdPayload("project-variation-context-pack");
      if (contextPackId) payload.context_pack_id = contextPackId;
      if ($("project-variation-generation-mode").value) payload.generation_mode = $("project-variation-generation-mode").value;
      if ($("project-variation-pipeline-mode").value) payload.pipeline_mode = $("project-variation-pipeline-mode").value;
      return payload;
    }

    async function renderProjectEditor(project, versions, target) {
      const parentId = projectEditorParentId || project.selected_version_id || project.final_version_id || project.latest_version_id || (versions[0] && versions[0].version_id) || "";
      target.innerHTML = projectEditorShell(versions, parentId);
      const parentSelect = $("project-editor-parent");
      if (parentSelect) {
        parentSelect.addEventListener("change", async () => {
          projectEditorParentId = parentSelect.value;
          projectEditorState = null;
          projectEditorView = null;
          projectEditorPatch = [];
          projectEditorRedo = [];
          projectEditorDraft = null;
          projectEditorClips = null;
          projectEditorClipInsertMap = {};
          projectEditorTemplateInsertMap = {};
          projectEditorTemplateMapping = null;
          projectEditorSelectedClipIndex = 0;
          projectEditorSelectedTemplateIndex = 0;
          projectEditorPreview = null;
          projectEditorAuditions = [];
          await renderProjectEditor(project, versions, target);
        });
      }
      bindAction("project-editor-load-history", async () => {
        await loadProjectEditorPreviewHistory(project.project_id);
      });
      bindAction("project-editor-cleanup-history", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/editor-previews/cleanup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ delete_unapplied_older_than_days: 7, keep_latest: 20 }),
        });
        await loadProjectEditorPreviewHistory(project.project_id);
      });
      bindAction("project-editor-load", async () => {
        await loadProjectEditorState(project.project_id, $("project-editor-parent").value);
      });
      bindAction("project-editor-clear", () => {
        projectEditorPatch = [];
        projectEditorRedo = [];
        projectEditorDraft = null;
        projectEditorClips = null;
        projectEditorClipInsertMap = {};
        projectEditorTemplateInsertMap = {};
        projectEditorTemplateMapping = null;
        projectEditorSelectedClipIndex = 0;
        projectEditorSelectedTemplateIndex = 0;
        projectEditorPreview = null;
        projectEditorAuditions = [];
        renderProjectEditorDraft();
        renderProjectEditorState();
      });
      bindAction("project-editor-undo", () => {
        const op = projectEditorPatch.pop();
        if (op) projectEditorRedo.push(op);
        projectEditorPreview = null;
        renderProjectEditorDraft();
      });
      bindAction("project-editor-redo", () => {
        const op = projectEditorRedo.pop();
        if (op) projectEditorPatch.push(op);
        projectEditorPreview = null;
        renderProjectEditorDraft();
      });
      bindAction("project-editor-draft-refresh", async () => {
        await refreshProjectEditorDraft(project.project_id, $("project-editor-parent").value);
      });
      bindAction("project-editor-preview", async () => {
        if (!projectEditorState) await loadProjectEditorState(project.project_id, $("project-editor-parent").value);
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/versions/${encodeURIComponent($("project-editor-parent").value)}/editor-preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patch: {
              schema_version: 1,
              base_plan_hash: projectEditorState.base_plan_hash,
              label: $("project-editor-label").value.trim(),
              operations: projectEditorPatch,
              metadata: projectEditorPatchMetadata(),
            },
            render_midi: true,
          }),
        });
        projectEditorPreview = data.preview;
        renderProjectEditorPreview();
      });
      bindAction("project-editor-apply", async () => {
        if (!projectEditorPreview) return;
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/apply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            version_name: $("project-editor-version-name").value.trim(),
            version_note: $("project-editor-version-note").value.trim(),
            change_summary: $("project-editor-label").value.trim(),
          }),
        });
        projectEditorParentId = null;
        projectEditorState = null;
        projectEditorView = null;
        projectEditorPatch = [];
        projectEditorRedo = [];
        projectEditorDraft = null;
        projectEditorClips = null;
        projectEditorClipInsertMap = {};
        projectEditorTemplateInsertMap = {};
        projectEditorTemplateMapping = null;
        projectEditorSelectedClipIndex = 0;
        projectEditorSelectedTemplateIndex = 0;
        projectEditorPreview = null;
        projectEditorAuditions = [];
        activeProjectTab = "versions";
        await loadJobs();
        await loadProjects();
      });
      if (parentId) await loadProjectEditorState(project.project_id, parentId);
      await loadProjectEditorPreviewHistory(project.project_id);
    }

    function projectEditorShell(versions, parentId) {
      return `
        <div class="grid2">
          <label>Parent Version
            <select id="project-editor-parent">${projectVersionOptions(versions, parentId)}</select>
          </label>
          <label>Patch Label
            <input id="project-editor-label" value="Manual editor patch">
          </label>
        </div>
        <div class="grid2">
          <label>New Version Name
            <input id="project-editor-version-name" value="Editor Version ${(versions.length || 0) + 1}">
          </label>
          <label>Version Note
            <input id="project-editor-version-note" placeholder="manual visual editor patch">
          </label>
        </div>
        <div class="actions">
          <button class="secondary" id="project-editor-load" type="button" ${parentId ? "" : "disabled"}>Open</button>
          <button class="secondary" id="project-editor-draft-refresh" type="button" disabled>Draft Refresh</button>
          <button class="secondary" id="project-editor-undo" type="button" disabled>Undo</button>
          <button class="secondary" id="project-editor-redo" type="button" disabled>Redo</button>
          <button class="secondary" id="project-editor-clear" type="button">Clear Patch</button>
          <button id="project-editor-preview" type="button" disabled>Preview</button>
          <button id="project-editor-apply" type="button" disabled>Apply as Version</button>
          <button class="secondary" id="project-editor-load-history" type="button">Preview History</button>
          <button class="secondary" id="project-editor-cleanup-history" type="button">Cleanup Previews</button>
          <span id="project-editor-message" class="message"></span>
        </div>
        <div id="project-editor-state"><div class="empty">Select a version to open the editor.</div></div>
        <div id="project-editor-preview-result"><div class="empty">Preview result will appear here.</div></div>
        <div id="project-editor-history"><div class="empty">Preview history will appear here.</div></div>
      `;
    }

    async function loadProjectEditorState(projectId, versionId) {
      if (!versionId) return;
      projectEditorState = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-state`);
      const viewData = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-view`);
      projectEditorClips = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-clips`);
      projectEditorView = viewData.view;
      projectEditorPatch = [];
      projectEditorRedo = [];
      projectEditorDraft = null;
      projectEditorPreview = null;
      projectEditorClipInsertMap = {};
      projectEditorTemplateInsertMap = {};
      projectEditorTemplateMapping = null;
      projectEditorSelectedClipIndex = 0;
      projectEditorSelectedTemplateIndex = 0;
      projectEditorSelectedSectionId = (projectEditorState.sections[0] || {}).section_id || null;
      projectEditorSelectedTrackId = (projectEditorState.tracks[0] || {}).track_id || null;
      projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
      projectEditorAuditions = [];
      renderProjectEditorState();
      renderProjectEditorDraft();
    }

    function renderProjectEditorState() {
      const target = $("project-editor-state");
      if (!target || !projectEditorState) return;
      const view = currentProjectEditorView();
      const viewSections = view.sections || [];
      const viewTracks = view.tracks || [];
      if (!viewSections.some((section) => section.section_id === projectEditorSelectedSectionId)) {
        projectEditorSelectedSectionId = (viewSections[0] || {}).section_id || projectEditorSelectedSectionId;
      }
      const sectionOptions = viewSections.map((section) => {
        const derived = isDerivedSection(section.section_id);
        const label = `${section.name} · bar ${section.start_bar}${derived ? " · draft" : ""}`;
        return `<option value="${escapeHtml(section.section_id)}"${derived ? " disabled" : ""}>${escapeHtml(label)}</option>`;
      }).join("");
      const afterSectionOptions = `<option value="">start/end</option>${viewSections.filter((section) => !isDerivedSection(section.section_id)).map((section) => `<option value="${escapeHtml(section.section_id)}">${escapeHtml(section.name)} · bar ${escapeHtml(section.start_bar)}</option>`).join("")}`;
      const trackOptions = viewTracks.map((track) => {
        const derived = isDerivedTrack(track.track_id);
        const label = `${track.name} · ${track.note_count || 0}${derived ? " · draft" : ""}`;
        return `<option value="${escapeHtml(track.track_id)}"${derived ? " disabled" : ""}>${escapeHtml(label)}</option>`;
      }).join("");
      const selectedTrack = viewTracks.find((track) => track.track_id === projectEditorSelectedTrackId) || viewTracks[0] || { notes: [] };
      projectEditorSelectedTrackId = selectedTrack.track_id || projectEditorSelectedTrackId;
      const clipOptions = projectEditorClipOptions();
      const templateOptions = projectEditorTemplateOptions();
      target.innerHTML = `
        <div class="summary-grid">
          ${metric("Title", projectEditorState.song.title)}
          ${metric("Tempo", projectEditorState.song.tempo_bpm)}
          ${metric("Key", projectEditorState.song.key)}
          ${metric("Base Hash", projectEditorState.base_plan_hash.slice(0, 12))}
        </div>
        <div class="editor-workbench">
          <section>
            <h3>Arranger Timeline</h3>
            <div id="project-editor-arranger" class="editor-arranger">
              <div id="project-editor-section-ruler" class="arranger-ruler">
                <strong>Bars</strong>
                ${projectEditorBarRuler(view)}
              </div>
              <div class="arranger-ruler">
                <strong>Sections</strong>
                <div class="section-row">${projectEditorSectionBlocks(view)}</div>
              </div>
              ${projectEditorTrackOverview(view)}
            </div>
          </section>
          <div class="editor-split">
            <section>
              <h3>Tracks</h3>
              <div class="track-list">${projectEditorTrackButtons(view)}</div>
            </section>
            <section>
              <h3>Piano Roll</h3>
              <div id="project-editor-piano-roll" class="editor-piano-roll">
                ${projectEditorPianoRoll(view)}
              </div>
            </section>
          </div>
          <section id="project-editor-note-inspector" class="editor-inspector">
            <h3>Inspector</h3>
            <div class="summary-grid">
              ${metric("Selected Section", projectEditorSelectedSectionId || "-")}
              ${metric("Selected Track", projectEditorSelectedTrackId || "-")}
              ${metric("Selected Note", projectEditorSelectedNoteId || "-")}
              ${metric("Patch Ops", projectEditorPatch.length)}
            </div>
            <div class="actions">
              <button class="secondary" id="project-editor-section-move-left" type="button">Move Section Left</button>
              <button class="secondary" id="project-editor-section-move-right" type="button">Move Section Right</button>
              <button class="secondary" id="project-editor-section-shorten" type="button">Shorten</button>
              <button class="secondary" id="project-editor-section-lengthen" type="button">Lengthen</button>
              <button class="secondary" id="project-editor-nudge-left" type="button">Nudge Left</button>
              <button class="secondary" id="project-editor-nudge-right" type="button">Nudge Right</button>
              <button class="secondary" id="project-editor-pitch-up" type="button">Pitch Up</button>
              <button class="secondary" id="project-editor-pitch-down" type="button">Pitch Down</button>
            </div>
          </section>
        </div>
        <section id="project-editor-clip-browser">
          <h3>Clip Browser</h3>
          <div class="grid2">
            <label>Clip
              <select id="project-editor-clip-select">${clipOptions}</select>
            </label>
            <label>Insert Mode
              <select id="project-editor-clip-mode">
                <option value="overlay">overlay</option>
                <option value="replace_range">replace_range</option>
              </select>
            </label>
          </div>
          <div class="grid2">
            <label>Start Beat <input id="project-editor-clip-start" type="number" step="0.125" value="${escapeHtml((viewSections.find((section) => section.section_id === projectEditorSelectedSectionId) || {}).start_beat ?? 0)}"></label>
            <label>Transpose <input id="project-editor-clip-transpose" type="number" min="-24" max="24" value="0"></label>
          </div>
          <div class="grid2">
            <label>Velocity Scale <input id="project-editor-clip-velocity" type="number" min="0.25" max="2" step="0.05" value="1"></label>
            <label>Quantize
              <select id="project-editor-clip-quantize">
                <option value="">none</option>
                <option value="1/16">1/16</option>
                <option value="1/8">1/8</option>
                <option value="1/4">1/4</option>
              </select>
            </label>
          </div>
          <div class="actions">
            <button class="secondary" id="project-editor-clip-draft" type="button" ${clipOptions ? "" : "disabled"}>Draft Insert Clip</button>
          </div>
          <div class="empty small">${escapeHtml(projectEditorClipSummaryText())}</div>
        </section>
        <section id="project-editor-template-browser">
          <h3>Template Browser</h3>
          <div class="grid2">
            <label>Section Template
              <select id="project-editor-template-select">${templateOptions}</select>
            </label>
            <label>Start Beat <input id="project-editor-template-start" type="number" step="0.125" value="${escapeHtml((viewSections.find((section) => section.section_id === projectEditorSelectedSectionId) || {}).start_beat ?? 0)}"></label>
          </div>
          <div class="grid2">
            <label>Insert Mode
              <select id="project-editor-template-mode">
                <option value="overlay">overlay</option>
                <option value="replace_range">replace_range</option>
              </select>
            </label>
            <label>Transpose <input id="project-editor-template-transpose" type="number" min="-24" max="24" value="0"></label>
          </div>
          <div class="grid2">
            <label>Velocity Scale <input id="project-editor-template-velocity" type="number" min="0.25" max="2" step="0.05" value="1"></label>
            <label>Quantize
              <select id="project-editor-template-quantize">
                <option value="">none</option>
                <option value="1/16">1/16</option>
                <option value="1/8">1/8</option>
                <option value="1/4">1/4</option>
              </select>
            </label>
          </div>
          <div id="project-editor-template-mapping" class="table-wrap"><div class="empty small">${escapeHtml(projectEditorTemplateSummaryText())}</div></div>
          <div class="actions">
            <button class="secondary" id="project-editor-template-map" type="button" ${templateOptions ? "" : "disabled"}>Suggest Mapping</button>
            <button class="secondary" id="project-editor-template-draft" type="button" ${templateOptions ? "" : "disabled"}>Draft Insert Template</button>
          </div>
        </section>
        <div class="grid2">
          <section>
            <h3>Sections</h3>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Bars</th><th>Chords</th><th>Lyrics</th></tr></thead>
                <tbody>${projectEditorState.sections.map((section) => `<tr><td>${escapeHtml(section.name)}</td><td>${escapeHtml(section.start_bar)}+${escapeHtml(section.bars)}</td><td>${escapeHtml(section.chords.join(" · "))}</td><td>${escapeHtml((section.lyrics || "").slice(0, 80))}</td></tr>`).join("")}</tbody>
              </table>
            </div>
          </section>
          <section>
            <h3>Tracks</h3>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Instrument</th><th>Notes</th><th>Range</th></tr></thead>
                <tbody>${projectEditorState.tracks.map((track) => `<tr><td>${escapeHtml(track.name)}</td><td>${escapeHtml(track.instrument)}</td><td>${escapeHtml(track.note_count)}</td><td>${escapeHtml(track.pitch_min ?? "-")}..${escapeHtml(track.pitch_max ?? "-")}</td></tr>`).join("")}</tbody>
              </table>
            </div>
          </section>
        </div>
        <div class="grid2">
          <section>
            <h3>Section Fields</h3>
            <label>Section <select id="project-editor-section">${sectionOptions}</select></label>
            <label>Chords <input id="project-editor-chords" placeholder="Cmaj7, G7, Am7, Fmaj7"></label>
            <label>Lyrics <textarea id="project-editor-lyrics"></textarea></label>
            <div class="actions">
              <button class="secondary" id="project-editor-add-chords" type="button">Set Chords</button>
              <button class="secondary" id="project-editor-add-lyrics" type="button">Set Lyrics</button>
              <button class="secondary" id="project-editor-save-section-template" type="button">Save Section Template</button>
            </div>
          </section>
          <section>
            <h3>Track Fields</h3>
            <label>Track <select id="project-editor-track">${trackOptions}</select></label>
            <label>Instrument <input id="project-editor-instrument" placeholder="warm lead synth"></label>
            <div class="actions">
              <button class="secondary" id="project-editor-add-instrument" type="button">Set Instrument</button>
              <button class="secondary" id="project-editor-save-track-template" type="button">Save Track Template</button>
            </div>
          </section>
        </div>
        <div class="grid2">
          <section>
            <h3>Section Structure</h3>
            <label>Name <input id="project-editor-section-name" placeholder="bridge"></label>
            <label>After <select id="project-editor-after-section">${afterSectionOptions}</select></label>
            <label>Bars <input id="project-editor-section-bars" type="number" min="1" max="64" value="4"></label>
            <label>Chords <input id="project-editor-section-structure-chords" placeholder="Fmaj7, G7"></label>
            <label>Note Policy
              <select id="project-editor-section-note-policy">
                <option value="delete">delete</option>
                <option value="shift_left">shift_left</option>
                <option value="crop">crop</option>
                <option value="shift_tail">shift_tail</option>
              </select>
            </label>
            <div class="actions">
              <button class="secondary" id="project-editor-add-section-op" type="button">Add Section</button>
              <button class="secondary" id="project-editor-duplicate-section-op" type="button">Duplicate Section</button>
              <button class="secondary" id="project-editor-delete-section-op" type="button">Delete Section</button>
              <button class="secondary" id="project-editor-resize-section-op" type="button">Resize Section</button>
              <button class="secondary" id="project-editor-move-section-op" type="button">Move Section</button>
            </div>
          </section>
          <section>
            <h3>Track Structure</h3>
            <label>Name <input id="project-editor-track-name" placeholder="counter melody"></label>
            <label>Instrument <input id="project-editor-track-structure-instrument" placeholder="warm pad"></label>
            <label>Transpose <input id="project-editor-track-transpose" type="number" min="-24" max="24" value="0"></label>
            <div class="actions">
              <button class="secondary" id="project-editor-add-track-op" type="button">Add Track</button>
              <button class="secondary" id="project-editor-duplicate-track-op" type="button">Duplicate Track</button>
              <button class="secondary" id="project-editor-delete-track-op" type="button">Delete Track</button>
              <button class="secondary" id="project-editor-rename-track-op" type="button">Rename Track</button>
            </div>
          </section>
        </div>
        <section>
          <h3>Notes</h3>
          <div class="grid2">
            <label>Note <select id="project-editor-note"></select></label>
            <label>Patch <input id="project-editor-note-patch" placeholder='{"pitch":67,"velocity":96}'></label>
          </div>
          <div class="grid2">
            <label>Add Note <input id="project-editor-add-note-json" placeholder='{"pitch":64,"start_beat":4,"duration_beats":1,"velocity":90}'></label>
            <label>Batch Range <input id="project-editor-range-json" placeholder='{"start_beat":0,"end_beat":16}'></label>
          </div>
          <div class="grid2">
            <label>Transpose Semitones <input id="project-editor-transpose" type="number" min="-24" max="24" value="0"></label>
            <label>Velocity Factor <input id="project-editor-velocity-factor" type="number" min="0.25" max="2" step="0.05" value="1"></label>
          </div>
          <div class="actions">
            <button class="secondary" id="project-editor-add-note" type="button">Add Note</button>
            <button class="secondary" id="project-editor-update-note" type="button">Update Note</button>
            <button class="secondary" id="project-editor-delete-note" type="button">Delete Note</button>
            <button class="secondary" id="project-editor-transpose-range" type="button">Transpose Range</button>
            <button class="secondary" id="project-editor-velocity-range" type="button">Scale Velocity</button>
          </div>
        </section>
        <section>
          <h3>Patch Queue</h3>
          <div id="project-editor-patch-queue" class="patch-queue"></div>
          <h3>Patch Summary</h3>
          <pre id="project-editor-patch-json"></pre>
        </section>
      `;
      setSelectValue("project-editor-section", projectEditorSelectedSectionId);
      setSelectValue("project-editor-track", projectEditorSelectedTrackId);
      renderProjectEditorNoteOptions();
      setSelectValue("project-editor-note", projectEditorSelectedNoteId);
      $("project-editor-track").addEventListener("change", renderProjectEditorNoteOptions);
      $("project-editor-section").addEventListener("change", () => { projectEditorSelectedSectionId = $("project-editor-section").value; });
      $("project-editor-track").addEventListener("change", () => {
        projectEditorSelectedTrackId = $("project-editor-track").value;
        projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
        renderProjectEditorState();
      });
      $("project-editor-note").addEventListener("change", () => { projectEditorSelectedNoteId = $("project-editor-note").value; fillSelectedProjectEditorNotePatch(); });
      const clipSelect = $("project-editor-clip-select");
      if (clipSelect) {
        clipSelect.value = String(projectEditorSelectedClipIndex || 0);
        clipSelect.addEventListener("change", () => {
          projectEditorSelectedClipIndex = Number(clipSelect.value || 0);
          renderProjectEditorState();
        });
      }
      const templateSelect = $("project-editor-template-select");
      if (templateSelect) {
        templateSelect.value = String(projectEditorSelectedTemplateIndex || 0);
        templateSelect.addEventListener("change", async () => {
          projectEditorSelectedTemplateIndex = Number(templateSelect.value || 0);
          projectEditorTemplateMapping = null;
          renderProjectEditorTemplateMapping();
        });
      }
      target.querySelectorAll("[data-editor-section-id]").forEach((button) => {
        button.addEventListener("click", () => {
          projectEditorSelectedSectionId = button.dataset.editorSectionId;
          setSelectValue("project-editor-section", projectEditorSelectedSectionId);
          renderProjectEditorState();
        });
      });
      target.querySelectorAll("[data-editor-track-id]").forEach((button) => {
        button.addEventListener("click", () => {
          projectEditorSelectedTrackId = button.dataset.editorTrackId;
          projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
          renderProjectEditorState();
        });
      });
      target.querySelectorAll("[data-editor-note-id]").forEach((button) => {
        button.addEventListener("click", () => {
          projectEditorSelectedTrackId = button.dataset.editorTrackId;
          projectEditorSelectedNoteId = button.dataset.editorNoteId;
          renderProjectEditorState();
        });
      });
      bindAction("project-editor-add-chords", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "set_section_chords", section_id: $("project-editor-section").value, chords: $("project-editor-chords").value.split(",").map((item) => item.trim()).filter(Boolean) }); });
      bindAction("project-editor-add-lyrics", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "set_section_lyrics", section_id: $("project-editor-section").value, lyrics: $("project-editor-lyrics").value }); });
      bindAction("project-editor-add-instrument", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "set_track_instrument", track_id: $("project-editor-track").value, instrument: $("project-editor-instrument").value.trim() }); });
      bindAction("project-editor-save-section-template", () => saveProjectEditorSectionTemplate());
      bindAction("project-editor-save-track-template", () => saveProjectEditorTrackTemplate());
      bindAction("project-editor-add-section-op", () => addProjectEditorOperation({ op: "add_section", after_section_id: $("project-editor-after-section").value, name: $("project-editor-section-name").value.trim(), bars: Number($("project-editor-section-bars").value || 4), chords: chordList("project-editor-section-structure-chords") }));
      bindAction("project-editor-duplicate-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "duplicate_section", section_id: $("project-editor-section").value, after_section_id: $("project-editor-after-section").value, name: $("project-editor-section-name").value.trim(), copy_notes: true }); });
      bindAction("project-editor-delete-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "delete_section", section_id: $("project-editor-section").value, note_policy: $("project-editor-section-note-policy").value === "shift_left" ? "shift_left" : "delete" }); });
      bindAction("project-editor-resize-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "resize_section", section_id: $("project-editor-section").value, bars: Number($("project-editor-section-bars").value || 4), note_policy: $("project-editor-section-note-policy").value === "crop" ? "crop" : "shift_tail" }); });
      bindAction("project-editor-move-section-op", () => { if (!isDerivedSection($("project-editor-section").value)) addProjectEditorOperation({ op: "move_section", section_id: $("project-editor-section").value, after_section_id: $("project-editor-after-section").value, move_notes: true }); });
      bindAction("project-editor-add-track-op", () => addProjectEditorOperation({ op: "add_track", name: $("project-editor-track-name").value.trim(), instrument: $("project-editor-track-structure-instrument").value.trim() }));
      bindAction("project-editor-duplicate-track-op", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "duplicate_track", track_id: $("project-editor-track").value, name: $("project-editor-track-name").value.trim(), instrument: $("project-editor-track-structure-instrument").value.trim(), transpose: Number($("project-editor-track-transpose").value || 0) }); });
      bindAction("project-editor-delete-track-op", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "delete_track", track_id: $("project-editor-track").value }); });
      bindAction("project-editor-rename-track-op", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "rename_track", track_id: $("project-editor-track").value, name: $("project-editor-track-name").value.trim() }); });
      bindAction("project-editor-add-note", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "add_note", track_id: $("project-editor-track").value, note: parseJsonField("project-editor-add-note-json") }); });
      bindAction("project-editor-update-note", () => { if (!isDerivedTrack($("project-editor-track").value) && !isDerivedNote($("project-editor-note").value)) addProjectEditorOperation({ op: "update_note", track_id: $("project-editor-track").value, note_id: $("project-editor-note").value, patch: parseJsonField("project-editor-note-patch") }); });
      bindAction("project-editor-delete-note", () => { if (!isDerivedTrack($("project-editor-track").value) && !isDerivedNote($("project-editor-note").value)) addProjectEditorOperation({ op: "delete_notes", track_id: $("project-editor-track").value, note_ids: [$("project-editor-note").value] }); });
      bindAction("project-editor-nudge-left", () => addSelectedProjectEditorNoteOperation({ op: "move_notes", delta_beats: -0.25 }));
      bindAction("project-editor-nudge-right", () => addSelectedProjectEditorNoteOperation({ op: "move_notes", delta_beats: 0.25 }));
      bindAction("project-editor-pitch-up", () => addSelectedProjectEditorNoteOperation({ op: "transpose_notes", semitones: 1 }));
      bindAction("project-editor-pitch-down", () => addSelectedProjectEditorNoteOperation({ op: "transpose_notes", semitones: -1 }));
      bindAction("project-editor-section-move-left", () => addProjectEditorSectionMove(-1));
      bindAction("project-editor-section-move-right", () => addProjectEditorSectionMove(1));
      bindAction("project-editor-section-shorten", () => addProjectEditorSectionResize(-1));
      bindAction("project-editor-section-lengthen", () => addProjectEditorSectionResize(1));
      bindAction("project-editor-transpose-range", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "transpose_notes", track_id: $("project-editor-track").value, range: parseJsonField("project-editor-range-json"), semitones: Number($("project-editor-transpose").value || 0) }); });
      bindAction("project-editor-velocity-range", () => { if (!isDerivedTrack($("project-editor-track").value)) addProjectEditorOperation({ op: "scale_velocity", track_id: $("project-editor-track").value, range: parseJsonField("project-editor-range-json"), factor: Number($("project-editor-velocity-factor").value || 1) }); });
      bindAction("project-editor-clip-draft", () => draftInsertProjectEditorClip());
      bindAction("project-editor-template-map", () => loadProjectEditorTemplateMapping());
      bindAction("project-editor-template-draft", () => draftInsertProjectEditorTemplate());
      renderProjectEditorTemplateMapping();
      renderProjectEditorDraft();
    }

    function projectEditorFlattenedClips() {
      return (((projectEditorClips || {}).clips) || []).filter((clip) => clip && clip.clip_ref);
    }

    function projectEditorSectionTemplates() {
      return (((editorTemplates || {}).section_templates) || []).filter((template) => template && !template.hidden && template.template_id);
    }

    function projectEditorClipOptions() {
      const clips = projectEditorFlattenedClips();
      return clips.map((clip, index) => `<option value="${escapeHtml(index)}">${escapeHtml(clip.title || clip.source_id)} · ${escapeHtml(clip.source_type)} · ${escapeHtml(clip.note_count || 0)} notes</option>`).join("");
    }

    function projectEditorTemplateOptions() {
      const templates = projectEditorSectionTemplates();
      return templates.map((template, index) => `<option value="${escapeHtml(index)}">${escapeHtml(template.name || template.template_id)} · ${escapeHtml(((template.clip || {}).lane_count) || 0)} lanes · ${escapeHtml(((template.clip || {}).note_count) || 0)} notes</option>`).join("");
    }

    function projectEditorClipSummaryText() {
      const clip = projectEditorFlattenedClips()[projectEditorSelectedClipIndex || 0];
      if (!clip) return "No reusable clips are available yet.";
      return `${clip.source_type} · ${clip.kind || "clip"} · ${clip.duration_beats || 0} beats · ${clip.note_count || 0} notes`;
    }

    function projectEditorTemplateSummaryText() {
      const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
      if (!template) return "No section templates are available yet.";
      const clip = template.clip || {};
      return `${template.template_id} · ${clip.lane_count || 0} lanes · ${clip.note_count || 0} notes`;
    }

    function projectEditorPatchMetadata() {
      const inserts = [];
      const templateInserts = [];
      const seen = new Set();
      const seenTemplates = new Set();
      for (const operation of projectEditorPatch) {
        const groupId = operation && operation.clip_group_id;
        const insert = groupId ? projectEditorClipInsertMap[groupId] : null;
        if (!insert || !groupId || seen.has(groupId)) continue;
        seen.add(groupId);
        inserts.push(insert);
      }
      for (const operation of projectEditorPatch) {
        const groupId = operation && operation.template_group_id;
        const insert = groupId ? projectEditorTemplateInsertMap[groupId] : null;
        if (!insert || !groupId || seenTemplates.has(groupId)) continue;
        seenTemplates.add(groupId);
        templateInserts.push(insert);
      }
      const metadata = {};
      if (inserts.length) metadata.clip_inserts = inserts;
      if (templateInserts.length) metadata.template_inserts = templateInserts;
      return metadata;
    }

    async function draftInsertProjectEditorClip() {
      if (!projectEditorState || !projectEditorSelectedTrackId || isDerivedTrack(projectEditorSelectedTrackId)) return;
      const clips = projectEditorFlattenedClips();
      const clip = clips[projectEditorSelectedClipIndex || 0];
      if (!clip) return;
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/editor-clip-draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          include_view: true,
          include_diff: true,
          clip_ref: clip.clip_ref,
          current_patch: projectEditorPatch.length ? {
            schema_version: 1,
            base_plan_hash: projectEditorState.base_plan_hash,
            label: $("project-editor-label").value.trim(),
            operations: projectEditorPatch,
            metadata: projectEditorPatchMetadata(),
          } : null,
          target: {
            track_id: projectEditorSelectedTrackId,
            section_id: projectEditorSelectedSectionId,
            start_beat: Number($("project-editor-clip-start").value || 0),
          },
          options: {
            mode: $("project-editor-clip-mode").value,
            transpose: Number($("project-editor-clip-transpose").value || 0),
            velocity_scale: Number($("project-editor-clip-velocity").value || 1),
            quantize_grid: $("project-editor-clip-quantize").value || null,
          },
        }),
      });
      const clipInsert = ((((data.patch || {}).metadata || {}).clip_inserts) || [])[0] || null;
      if (clipInsert && clipInsert.clip_group_id) projectEditorClipInsertMap[clipInsert.clip_group_id] = clipInsert;
      projectEditorPatch.push(...((data.patch || {}).operations || []));
      projectEditorRedo = [];
      projectEditorPreview = null;
      projectEditorDraft = data;
      projectEditorView = data.draft_view || data.view || projectEditorView;
      renderProjectEditorState();
      const result = $("project-editor-preview-result");
      if (result) {
        result.innerHTML = `
          <div class="summary-grid">
            ${metric("Clip", (data.clip_summary || {}).title || "-")}
            ${metric("Ops Added", ((data.patch || {}).operations || []).length)}
            ${metric("Notes", (data.clip_summary || {}).note_count ?? "-")}
            ${metric("Validator", (data.validator || {}).status || "-")}
          </div>
          <pre>${escapeHtml(JSON.stringify({ clip_summary: data.clip_summary, warnings: data.warnings, diff: data.diff }, null, 2))}</pre>
        `;
      }
    }

    async function saveProjectEditorSectionTemplate() {
      if (!projectEditorState || !projectEditorSelectedSectionId || isDerivedSection(projectEditorSelectedSectionId)) return;
      try {
        const section = (currentProjectEditorView().sections || []).find((item) => item.section_id === projectEditorSelectedSectionId) || {};
        const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/section-templates`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            section_id: projectEditorSelectedSectionId,
            name: `${section.name || projectEditorSelectedSectionId} Template`,
            tags: ["editor", "section"],
          }),
        });
        $("project-editor-message").textContent = `saved ${data.template.template_id}`;
        await loadEditorTemplates();
        renderProjectEditorState();
      } catch (err) {
        $("project-editor-message").textContent = err.message;
      }
    }

    async function saveProjectEditorTrackTemplate() {
      if (!projectEditorState || !projectEditorSelectedTrackId || isDerivedTrack(projectEditorSelectedTrackId)) return;
      try {
        const track = (currentProjectEditorView().tracks || []).find((item) => item.track_id === projectEditorSelectedTrackId) || {};
        const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/track-templates`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            track_id: projectEditorSelectedTrackId,
            name: `${track.name || projectEditorSelectedTrackId} Template`,
            tags: ["editor", "track"],
          }),
        });
        $("project-editor-message").textContent = `saved ${data.template.template_id}`;
        await loadEditorTemplates();
        renderProjectEditorState();
      } catch (err) {
        $("project-editor-message").textContent = err.message;
      }
    }

    async function loadProjectEditorTemplateMapping() {
      if (!projectEditorState) return;
      const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
      if (!template) return;
      try {
        projectEditorTemplateMapping = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/editor-template-mapping`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_ref: { source_type: "section_template", template_id: template.template_id } }),
        });
        renderProjectEditorTemplateMapping();
      } catch (err) {
        $("project-editor-message").textContent = err.message;
      }
    }

    function renderProjectEditorTemplateMapping() {
      const target = $("project-editor-template-mapping");
      if (!target) return;
      const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
      if (!template) {
        target.innerHTML = `<div class="empty small">No section templates are available yet.</div>`;
        return;
      }
      const suggestions = (projectEditorTemplateMapping || {}).suggestions || [];
      if (!suggestions.length) {
        target.innerHTML = `<div class="empty small">${escapeHtml(projectEditorTemplateSummaryText())}</div>`;
        return;
      }
      const trackOptions = (currentProjectEditorView().tracks || []).filter((track) => !isDerivedTrack(track.track_id)).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.name)} · ${escapeHtml(track.track_id)}</option>`).join("");
      target.innerHTML = `
        <table>
          <thead><tr><th>Lane</th><th>Role</th><th>Notes</th><th>Target Track</th><th>Mode</th></tr></thead>
          <tbody>
            ${suggestions.map((item) => `
              <tr data-template-lane-id="${escapeHtml(item.lane_id)}">
                <td>${escapeHtml(item.lane_name || item.lane_id)}</td>
                <td>${escapeHtml(item.lane_role || "-")}</td>
                <td>${escapeHtml(item.note_count || 0)}</td>
                <td><select data-template-target-track>${trackOptions}</select></td>
                <td>
                  <select data-template-mode>
                    <option value="overlay">overlay</option>
                    <option value="replace_range">replace_range</option>
                    <option value="skip">skip</option>
                  </select>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
      target.querySelectorAll("[data-template-lane-id]").forEach((row) => {
        const item = suggestions.find((suggestion) => suggestion.lane_id === row.dataset.templateLaneId) || {};
        const select = row.querySelector("[data-template-target-track]");
        const mode = row.querySelector("[data-template-mode]");
        if (select && item.suggested_track_id) select.value = item.suggested_track_id;
        if (mode && !item.suggested_track_id) mode.value = "skip";
      });
    }

    function projectEditorTemplateLaneMappings() {
      const table = $("project-editor-template-mapping");
      if (!table) return [];
      return Array.from(table.querySelectorAll("[data-template-lane-id]")).map((row) => ({
        lane_id: row.dataset.templateLaneId,
        target_track_id: (row.querySelector("[data-template-target-track]") || {}).value || "",
        mode: (row.querySelector("[data-template-mode]") || {}).value || "overlay",
      }));
    }

    async function draftInsertProjectEditorTemplate() {
      if (!projectEditorState) return;
      const template = projectEditorSectionTemplates()[projectEditorSelectedTemplateIndex || 0];
      if (!template) return;
      if (!projectEditorTemplateMapping) {
        await loadProjectEditorTemplateMapping();
      }
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(projectEditorState.version_id)}/editor-multitrack-clip-draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          include_view: true,
          include_diff: true,
          source_ref: { source_type: "section_template", template_id: template.template_id },
          current_patch: projectEditorPatch.length ? {
            schema_version: 1,
            base_plan_hash: projectEditorState.base_plan_hash,
            label: $("project-editor-label").value.trim(),
            operations: projectEditorPatch,
            metadata: projectEditorPatchMetadata(),
          } : null,
          target: {
            section_id: projectEditorSelectedSectionId,
            start_beat: Number($("project-editor-template-start").value || 0),
          },
          lane_mappings: projectEditorTemplateLaneMappings(),
          options: {
            mode: $("project-editor-template-mode").value,
            transpose: Number($("project-editor-template-transpose").value || 0),
            velocity_scale: Number($("project-editor-template-velocity").value || 1),
            quantize_grid: $("project-editor-template-quantize").value || null,
          },
        }),
      });
      const templateInsert = ((((data.patch || {}).metadata || {}).template_inserts) || [])[0] || null;
      if (templateInsert && templateInsert.template_group_id) projectEditorTemplateInsertMap[templateInsert.template_group_id] = templateInsert;
      projectEditorPatch.push(...((data.patch || {}).operations || []));
      projectEditorRedo = [];
      projectEditorPreview = null;
      projectEditorDraft = data;
      projectEditorView = data.draft_view || data.view || projectEditorView;
      renderProjectEditorState();
      const result = $("project-editor-preview-result");
      if (result) {
        result.innerHTML = `
          <div class="summary-grid">
            ${metric("Template", (data.template_summary || {}).title || "-")}
            ${metric("Ops Added", ((data.patch || {}).operations || []).length)}
            ${metric("Lanes", (data.template_summary || {}).lane_count ?? "-")}
            ${metric("Validator", (data.validator || {}).status || "-")}
          </div>
          <pre>${escapeHtml(JSON.stringify({ template_summary: data.template_summary, warnings: data.warnings, diff: data.diff }, null, 2))}</pre>
        `;
      }
    }

    function renderProjectEditorNoteOptions() {
      const select = $("project-editor-note");
      if (!select) return;
      const trackId = $("project-editor-track") ? $("project-editor-track").value : projectEditorSelectedTrackId;
      const track = (projectEditorViewTrackWithNotes(trackId) || { notes: [] });
      select.innerHTML = (track.notes || []).slice(0, 256).map((note) => `<option value="${escapeHtml(note.note_id)}">${escapeHtml(note.pitch)} @ ${escapeHtml(note.start_beat)}</option>`).join("");
      if (!projectEditorSelectedNoteId || !(track.notes || []).some((note) => note.note_id === projectEditorSelectedNoteId)) {
        projectEditorSelectedNoteId = ((track.notes || [])[0] || {}).note_id || null;
      }
      setSelectValue("project-editor-note", projectEditorSelectedNoteId);
      fillSelectedProjectEditorNotePatch();
    }

    function addProjectEditorOperation(operation) {
      projectEditorPatch.push(operation);
      projectEditorRedo = [];
      projectEditorPreview = null;
      projectEditorDraft = null;
      renderProjectEditorDraft();
    }

    function addSelectedProjectEditorNoteOperation(operation) {
      if (!projectEditorSelectedTrackId || !projectEditorSelectedNoteId || isDerivedTrack(projectEditorSelectedTrackId) || isDerivedNote(projectEditorSelectedNoteId)) return;
      addProjectEditorOperation({ ...operation, track_id: projectEditorSelectedTrackId, note_ids: [projectEditorSelectedNoteId] });
    }

    function addProjectEditorSectionMove(delta) {
      const sections = (projectEditorView || projectEditorState || { sections: [] }).sections || [];
      const index = sections.findIndex((section) => section.section_id === projectEditorSelectedSectionId);
      if (index < 0) return;
      if (String(projectEditorSelectedSectionId || "").startsWith("derived-section-")) return;
      if (delta < 0 && index === 0) return;
      if (delta > 0 && index >= sections.length - 1) return;
      const targetIndex = delta < 0 ? index - 2 : index + 1;
      const after = targetIndex >= 0 ? sections[targetIndex].section_id : "";
      if (after && isDerivedSection(after)) return;
      addProjectEditorOperation({ op: "move_section", section_id: projectEditorSelectedSectionId, after_section_id: after, move_notes: true });
    }

    function addProjectEditorSectionResize(delta) {
      const section = ((projectEditorView || projectEditorState || { sections: [] }).sections || []).find((item) => item.section_id === projectEditorSelectedSectionId);
      if (!section) return;
      if (String(section.section_id || "").startsWith("derived-section-")) return;
      addProjectEditorOperation({ op: "resize_section", section_id: section.section_id, bars: Math.max(1, Number(section.bars || 1) + delta), note_policy: delta < 0 ? "crop" : "shift_tail" });
    }

    function chordList(id) {
      return $(id).value.split(",").map((item) => item.trim()).filter(Boolean);
    }

    function renderProjectEditorDraft() {
      const pre = $("project-editor-patch-json");
      if (pre) pre.textContent = projectEditorPatch.map(describeProjectEditorOperation).join("\\n") + "\\n\\n" + JSON.stringify({ operations: projectEditorPatch }, null, 2);
      const queue = $("project-editor-patch-queue");
      if (queue) queue.innerHTML = projectEditorPatch.length ? projectEditorPatch.map((operation, index) => `
        <div class="patch-queue-row">
          <span>${escapeHtml(index + 1)}. ${escapeHtml(describeProjectEditorOperation(operation))}</span>
          <button class="secondary" data-editor-remove-op="${escapeHtml(index)}" type="button">Remove</button>
        </div>
      `).join("") : "<div class='empty'>Patch queue is empty.</div>";
      if (queue) queue.querySelectorAll("[data-editor-remove-op]").forEach((button) => {
        button.addEventListener("click", () => {
          projectEditorPatch.splice(Number(button.dataset.editorRemoveOp), 1);
          projectEditorPreview = null;
          projectEditorDraft = null;
          renderProjectEditorDraft();
        });
      });
      const preview = $("project-editor-preview");
      if (preview) preview.disabled = !projectEditorState || projectEditorPatch.length === 0;
      const draftRefresh = $("project-editor-draft-refresh");
      if (draftRefresh) draftRefresh.disabled = !projectEditorState || projectEditorPatch.length === 0;
      const undo = $("project-editor-undo");
      if (undo) undo.disabled = projectEditorPatch.length === 0;
      const redo = $("project-editor-redo");
      if (redo) redo.disabled = projectEditorRedo.length === 0;
      const apply = $("project-editor-apply");
      if (apply) apply.disabled = !projectEditorPreview;
      const result = $("project-editor-preview-result");
      if (result && !projectEditorPreview && !projectEditorDraft) result.innerHTML = "<div class='empty'>Preview result will appear here.</div>";
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

    function projectEditorAuditionTrackOptions() {
      const view = currentProjectEditorView();
      return (view.tracks || []).filter((track) => !isDerivedTrack(track.track_id)).map((track) => `<option value="${escapeHtml(track.track_id)}">${escapeHtml(track.name)} · ${escapeHtml(track.track_id)}</option>`).join("");
    }

    function projectEditorAuditionListHtml() {
      if (!projectEditorAuditions.length) return "<div class='empty small'>No auditions.</div>";
      return `
        <div class="table-wrap">
          <table>
            <thead><tr><th>Audition</th><th>Source</th><th>Range</th><th>Track mode</th><th>Notes</th><th>Review</th><th>WAV</th><th>Actions</th></tr></thead>
            <tbody>${projectEditorAuditions.map((audition) => `
              <tr>
                <td>${escapeHtml(audition.audition_id)}</td>
                <td>${escapeHtml(audition.source)}</td>
                <td>${escapeHtml((audition.range || {}).mode || "-")}</td>
                <td>${escapeHtml(audition.track_mode)}</td>
                <td>${escapeHtml(audition.note_count || 0)}</td>
                <td>
                  <div class="compact-form">
                    <input data-editor-audition-rating="${escapeHtml(audition.audition_id)}" type="number" min="0" max="5" value="${escapeHtml(((audition.review || {}).rating) || 0)}">
                    <select data-editor-audition-status="${escapeHtml(audition.audition_id)}">
                      ${["unreviewed", "keep", "maybe", "needs_fix", "reject"].map((status) => `<option value="${status}" ${((audition.review || {}).status || "unreviewed") === status ? "selected" : ""}>${status}</option>`).join("")}
                    </select>
                    <label class="inline-check"><input data-editor-audition-favorite="${escapeHtml(audition.audition_id)}" type="checkbox" ${((audition.review || {}).favorite) ? "checked" : ""}> Fav</label>
                    <input data-editor-audition-notes="${escapeHtml(audition.audition_id)}" value="${escapeHtml((audition.review || {}).notes || "")}" placeholder="review notes">
                    <input data-editor-audition-tags="${escapeHtml(audition.audition_id)}" value="${escapeHtml(((audition.review || {}).tags || []).join(", "))}" placeholder="tags">
                    <button class="secondary" data-editor-audition-review="${escapeHtml(audition.audition_id)}" type="button">Save Review</button>
                    <div class="actions">
                      <input data-editor-audition-marker-beat="${escapeHtml(audition.audition_id)}" type="number" step="0.125" value="0" title="Marker beat">
                      <select data-editor-audition-marker-kind="${escapeHtml(audition.audition_id)}">
                        ${["hook", "drop", "issue", "keep", "fix", "note"].map((kind) => `<option value="${kind}">${kind}</option>`).join("")}
                      </select>
                      <input data-editor-audition-marker-label="${escapeHtml(audition.audition_id)}" placeholder="marker label">
                      <button class="secondary" data-editor-audition-marker-add="${escapeHtml(audition.audition_id)}" type="button">Add Marker</button>
                    </div>
                    <div class="empty small">${escapeHtml(((audition.review || {}).markers || []).map((marker) => `${marker.kind}@${marker.beat}`).join(" · ") || "No markers")}</div>
                  </div>
                </td>
                <td>${escapeHtml(((audition.audio || {}).status) || "not_started")}</td>
                <td>
                  ${(audition.midi || {}).url ? `<a class="button-link secondary" href="${escapeHtml(audition.midi.url)}">MIDI</a>` : ""}
                  <button class="secondary" data-editor-audition-render="${escapeHtml(audition.audition_id)}" type="button">Render Audition WAV</button>
                  ${(audition.audio || {}).status === "completed" && (audition.audio || {}).url ? `<audio class="inline-audio" controls src="${escapeHtml(audition.audio.url)}"></audio>` : ""}
                  <button class="secondary" data-editor-audition-create-asset="${escapeHtml(audition.audition_id)}" type="button">Save Audition Asset</button>
                  <button class="secondary" data-editor-audition-preview-edit="${escapeHtml(audition.audition_id)}" type="button">Preview Edit</button>
                  <button class="secondary" data-editor-audition-create-edit="${escapeHtml(audition.audition_id)}" type="button">Create Local Edit</button>
                  <button class="secondary" data-editor-audition-provider-preview="${escapeHtml(audition.audition_id)}" type="button">Provider Preview</button>
                  <button class="secondary" data-editor-audition-create-review-task="${escapeHtml(audition.audition_id)}" type="button">Create Review Task</button>
                  <button class="secondary" data-editor-audition-create-context="${escapeHtml(audition.audition_id)}" type="button">Create Context Pack</button>
                  <button class="secondary" data-editor-audition-delete="${escapeHtml(audition.audition_id)}" type="button">Delete</button>
                </td>
              </tr>
            `).join("")}</tbody>
          </table>
        </div>
        <div id="project-editor-review-edit-result"><div class="empty small">Review Edit result will appear here.</div></div>
      `;
    }

    function bindProjectEditorPreviewAudioControls() {
      bindAction("project-editor-render-preview-audio", async () => {
        const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/render-audio`, { method: "POST" });
        projectEditorPreview = data.preview;
        renderProjectEditorPreview();
      });
      bindAction("project-editor-render-parent-audio", async () => {
        const parentVersion = $("project-editor-parent") ? $("project-editor-parent").value : projectEditorParentId;
        await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/versions/${encodeURIComponent(parentVersion)}/render-audio`, { method: "POST" });
        renderProjectEditorPreview();
      });
      const parentAudio = $("project-editor-audio-parent");
      const previewAudio = $("project-editor-audio-preview");
      if (parentAudio && previewAudio) {
        parentAudio.addEventListener("play", () => previewAudio.pause());
        previewAudio.addEventListener("play", () => parentAudio.pause());
      }
    }

    function bindProjectEditorAuditionControls() {
      bindAction("project-editor-refresh-auditions", async () => {
        await loadProjectEditorAuditions();
        renderProjectEditorPreview();
      });
      bindAction("project-editor-filter-favorites", async () => {
        await loadProjectEditorAuditions({ favorite: true, sort: "rating" });
        renderProjectEditorPreview();
      });
      bindAction("project-editor-create-audition", async () => {
        const rangeMode = $("project-editor-audition-range").value;
        const range = { mode: rangeMode };
        if (rangeMode === "section") range.section_id = projectEditorSelectedSectionId;
        if (rangeMode === "custom") {
          range.start_beat = Number($("project-editor-audition-start").value || 0);
          range.end_beat = Number($("project-editor-audition-end").value || 0);
        }
        const trackMode = $("project-editor-audition-track-mode").value;
        const trackIds = trackMode === "all" ? [] : [$("project-editor-audition-track").value];
        const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source: $("project-editor-audition-source").value,
            range,
            track_mode: trackMode,
            track_ids: trackIds,
          }),
        });
        projectEditorAuditions = [data.audition, ...projectEditorAuditions.filter((item) => item.audition_id !== data.audition.audition_id)];
        renderProjectEditorPreview();
      });
      document.querySelectorAll("[data-editor-audition-render]").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(button.dataset.editorAuditionRender)}/render-audio`, { method: "POST" });
          await loadProjectEditorAuditions();
          renderProjectEditorPreview();
        });
      });
      document.querySelectorAll("[data-editor-audition-review]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionReview;
          const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              rating: Number((document.querySelector(`[data-editor-audition-rating="${CSS.escape(id)}"]`) || {}).value || 0),
              status: (document.querySelector(`[data-editor-audition-status="${CSS.escape(id)}"]`) || {}).value || "unreviewed",
              favorite: Boolean((document.querySelector(`[data-editor-audition-favorite="${CSS.escape(id)}"]`) || {}).checked),
              notes: (document.querySelector(`[data-editor-audition-notes="${CSS.escape(id)}"]`) || {}).value || "",
              tags: ((document.querySelector(`[data-editor-audition-tags="${CSS.escape(id)}"]`) || {}).value || "").split(",").map((item) => item.trim()).filter(Boolean),
            }),
          });
          projectEditorAuditions = projectEditorAuditions.map((item) => item.audition_id === id ? data.audition : item);
          renderProjectEditorPreview();
        });
      });
      document.querySelectorAll("[data-editor-audition-marker-add]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionMarkerAdd;
          const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/markers`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              beat: Number((document.querySelector(`[data-editor-audition-marker-beat="${CSS.escape(id)}"]`) || {}).value || 0),
              kind: (document.querySelector(`[data-editor-audition-marker-kind="${CSS.escape(id)}"]`) || {}).value || "note",
              label: (document.querySelector(`[data-editor-audition-marker-label="${CSS.escape(id)}"]`) || {}).value || "",
            }),
          });
          projectEditorAuditions = projectEditorAuditions.map((item) => item.audition_id === id ? data.audition : item);
          renderProjectEditorPreview();
        });
      });
      document.querySelectorAll("[data-editor-audition-create-asset]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionCreateAsset;
          await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/create-asset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ asset_type: "motif", name: `${id} motif`, tags: ["audition"] }),
          });
          await loadAssets();
          await loadProjectEditorAuditions();
          renderProjectEditorPreview();
        });
      });
      document.querySelectorAll("[data-editor-audition-preview-edit]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionPreviewEdit;
          const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review-edit-preview`, { method: "POST" });
          const result = $("project-editor-review-edit-result");
          if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ review_edit: data.review_edit, summary: data.summary, validator: data.validator }, null, 2))}</pre>`;
        });
      });
      document.querySelectorAll("[data-editor-audition-create-edit]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionCreateEdit;
          const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review-edit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ version_name: `${id} Review Edit`, version_note: "Created from audition review" }),
          });
          const result = $("project-editor-review-edit-result");
          if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ version: data.version, job: data.job, review_edit: data.review_edit }, null, 2))}</pre>`;
          await loadProjects();
        });
      });
      document.querySelectorAll("[data-editor-audition-provider-preview]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionProviderPreview;
          const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/provider-review-edit-preview`, { method: "POST" });
          providerEditPreview = data.preview;
          const result = $("project-editor-review-edit-result");
          if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ preview: data.preview, patch: data.patch, review_edit: data.review_edit }, null, 2))}</pre>`;
        });
      });
      document.querySelectorAll("[data-editor-audition-create-review-task]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionCreateReviewTask;
          const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/review-task`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          const result = $("project-editor-review-edit-result");
          if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ task: data.task }, null, 2))}</pre>`;
          activeProjectTab = "review-workbench";
          await loadProjects();
        });
      });
      document.querySelectorAll("[data-editor-audition-create-context]").forEach((button) => {
        button.addEventListener("click", async () => {
          const id = button.dataset.editorAuditionCreateContext;
          const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(id)}/create-context-pack`, { method: "POST" });
          await loadContextPacks();
          const result = $("project-editor-review-edit-result");
          if (result) result.innerHTML = `<pre>${escapeHtml(JSON.stringify({ context_pack: data.context_pack }, null, 2))}</pre>`;
        });
      });
      document.querySelectorAll("[data-editor-audition-delete]").forEach((button) => {
        button.addEventListener("click", async () => {
          await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/auditions/${encodeURIComponent(button.dataset.editorAuditionDelete)}/delete`, { method: "POST" });
          projectEditorAuditions = projectEditorAuditions.filter((item) => item.audition_id !== button.dataset.editorAuditionDelete);
          renderProjectEditorPreview();
        });
      });
    }

    async function loadProjectEditorAuditions(filters = {}) {
      if (!projectEditorPreview || !projectEditorState) return;
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => params.set(key, value));
      const suffix = params.toString() ? `?${params.toString()}` : "";
      const data = await api(`/api/projects/${encodeURIComponent(projectEditorState.project_id)}/editor-previews/${encodeURIComponent(projectEditorPreview.preview_id)}/audition-reviews${suffix}`);
      projectEditorAuditions = data.auditions || [];
    }

    async function refreshProjectEditorDraft(projectId, versionId) {
      if (!projectEditorState || !projectEditorPatch.length) return;
      const data = await api(`/api/projects/${encodeURIComponent(projectId)}/versions/${encodeURIComponent(versionId)}/editor-draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          include_view: true,
          include_diff: true,
          patch: {
            schema_version: 1,
            base_plan_hash: projectEditorState.base_plan_hash,
            label: $("project-editor-label").value.trim(),
            operations: projectEditorPatch,
            metadata: projectEditorPatchMetadata(),
          },
        }),
      });
      projectEditorDraft = data;
      projectEditorView = data.view;
      const track = projectEditorViewTrackWithNotes(projectEditorSelectedTrackId);
      if (!track || !(track.notes || []).some((note) => note.note_id === projectEditorSelectedNoteId)) {
        projectEditorSelectedNoteId = firstProjectEditorNoteId(projectEditorSelectedTrackId);
      }
      renderProjectEditorState();
      const result = $("project-editor-preview-result");
      if (result) {
        result.innerHTML = `
          <div class="summary-grid">
            ${metric("Draft Ops", data.operation_count)}
            ${metric("Sections", (data.summary.changed_sections || []).join(", ") || "-")}
            ${metric("Tracks", (data.summary.changed_tracks || []).join(", ") || "-")}
            ${metric("Validator", (data.validator || {}).status || "-")}
          </div>
          <pre>${escapeHtml(JSON.stringify({ summary: data.summary, diff: data.diff }, null, 2))}</pre>
        `;
      }
    }

    function currentProjectEditorView() {
      return projectEditorView || {
        song: { ...(projectEditorState.song || {}), total_beats: (projectEditorState.song.total_bars || 1) * (projectEditorState.song.beats_per_bar || 4) },
        sections: projectEditorState.sections || [],
        tracks: (projectEditorState.tracks || []).map((track) => {
          const copy = { ...track };
          delete copy.notes;
          return copy;
        }),
        lanes: (projectEditorState.tracks || []).map((track) => ({ track_id: track.track_id, notes: track.notes || [] })),
        pitch_range: { min: 36, max: 84 },
      };
    }

    function projectEditorViewTrackWithNotes(trackId) {
      const view = currentProjectEditorView();
      const track = (view.tracks || []).find((item) => item.track_id === trackId) || (view.tracks || [])[0] || null;
      if (!track) return null;
      const lane = (view.lanes || []).find((item) => item.track_id === track.track_id) || { notes: [] };
      return { ...track, notes: lane.notes || [] };
    }

    function firstProjectEditorNoteId(trackId) {
      const track = projectEditorViewTrackWithNotes(trackId);
      return ((track && track.notes) || [])[0]?.note_id || null;
    }

    function fillSelectedProjectEditorNotePatch() {
      const input = $("project-editor-note-patch");
      if (!input) return;
      const track = projectEditorViewTrackWithNotes(projectEditorSelectedTrackId);
      const note = ((track && track.notes) || []).find((item) => item.note_id === projectEditorSelectedNoteId);
      if (note) {
        input.value = JSON.stringify({ pitch: note.pitch, start_beat: note.start_beat, duration_beats: note.duration_beats, velocity: note.velocity });
      }
    }

    function setSelectValue(id, value) {
      const select = $(id);
      if (select && value != null) select.value = value;
    }

    function isDerivedSection(sectionId) {
      return String(sectionId || "").startsWith("derived-section-");
    }

    function isDerivedTrack(trackId) {
      return String(trackId || "").startsWith("derived-track-");
    }

    function isDerivedNote(noteId) {
      return String(noteId || "").startsWith("derived-note-");
    }

    function projectEditorBarRuler(view) {
      const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
      const beatsPerBar = Math.max(1, Number((view.song || {}).beats_per_bar || 4));
      const totalBars = Math.max(1, Number((view.song || {}).total_bars || Math.ceil(totalBeats / beatsPerBar)));
      return `<div class="bar-ruler">${Array.from({ length: totalBars }, (_, index) => {
        const left = (index * beatsPerBar / totalBeats) * 100;
        return `<span class="bar-tick" style="left:${left}%">${index + 1}</span>`;
      }).join("")}</div>`;
    }

    function projectEditorSectionBlocks(view) {
      const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
      return (view.sections || []).map((section) => {
        const left = (Number(section.start_beat || 0) / totalBeats) * 100;
        const width = Math.max(2, ((Number(section.end_beat || 0) - Number(section.start_beat || 0)) / totalBeats) * 100);
        const selected = section.section_id === projectEditorSelectedSectionId ? " selected" : "";
        return `<button class="project-editor-section-block${selected}" data-editor-section-id="${escapeHtml(section.section_id)}" style="left:${left}%;width:${width}%;" type="button">${escapeHtml(section.name)} · ${escapeHtml(section.bars)} bars</button>`;
      }).join("");
    }

    function projectEditorTrackOverview(view) {
      const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
      return (view.tracks || []).map((track) => {
        const lane = (view.lanes || []).find((item) => item.track_id === track.track_id) || { notes: [] };
        const notes = (lane.notes || []).slice(0, 180).map((note) => {
          const left = (Number(note.start_beat || 0) / totalBeats) * 100;
          const width = Math.max(0.6, (Number(note.duration_beats || 0.25) / totalBeats) * 100);
          return `<span class="lane-note" style="left:${left}%;width:${width}%"></span>`;
        }).join("");
        return `<div class="track-lane"><button class="secondary" data-editor-track-id="${escapeHtml(track.track_id)}" type="button">${escapeHtml(track.name)}</button><div class="lane-notes">${notes}</div></div>`;
      }).join("");
    }

    function projectEditorTrackButtons(view) {
      return (view.tracks || []).map((track) => {
        const active = track.track_id === projectEditorSelectedTrackId ? " active" : "";
        return `<button class="${active}" data-editor-track-id="${escapeHtml(track.track_id)}" type="button">${escapeHtml(track.name)} · ${escapeHtml(track.note_count || 0)}</button>`;
      }).join("") || "<div class='empty'>No tracks.</div>";
    }

    function projectEditorPianoRoll(view) {
      const track = projectEditorViewTrackWithNotes(projectEditorSelectedTrackId);
      if (!track) return "<div class='empty'>Select a track.</div>";
      const notes = track.notes || [];
      const totalBeats = Math.max(1, Number((view.song || {}).total_beats || 1));
      const pitchMin = Math.max(0, Number((view.pitch_range || {}).min ?? 36));
      const pitchMax = Math.min(127, Number((view.pitch_range || {}).max ?? 84));
      const pitchSpan = Math.max(1, pitchMax - pitchMin + 1);
      const labels = [];
      for (let pitch = pitchMax; pitch >= pitchMin; pitch -= 12) {
        const top = ((pitchMax - pitch) / pitchSpan) * 100;
        labels.push(`<span class="pitch-label" style="top:${top}%">${pitch}</span>`);
      }
      const rects = notes.slice(0, 1200).map((note) => {
        const left = Math.max(0, (Number(note.start_beat || 0) / totalBeats) * 100);
        const width = Math.max(0.8, (Number(note.duration_beats || 0.25) / totalBeats) * 100);
        const top = Math.max(0, Math.min(96, ((pitchMax - Number(note.pitch || pitchMin)) / pitchSpan) * 100));
        const selected = note.note_id === projectEditorSelectedNoteId ? " selected" : "";
        const derived = isDerivedNote(note.note_id) ? " derived" : "";
        return `<button class="project-editor-note-rect${selected}${derived}" data-editor-track-id="${escapeHtml(track.track_id)}" data-editor-note-id="${escapeHtml(note.note_id)}" style="left:${left}%;top:${top}%;width:${width}%;" type="button">${escapeHtml(note.pitch)}</button>`;
      }).join("");
      return `<div class="piano-grid">${labels.join("")}${rects || "<div class='empty'>No notes in this track.</div>"}</div>`;
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

    function describeProjectEditorOperation(operation) {
      const op = operation.op || "operation";
      if (operation.template_group_id) return `template ${operation.template_group_id}: ${op} ${operation.track_id || operation.section_id || ""}`.trim();
      if (operation.clip_group_id) return `clip ${operation.clip_group_id}: ${op} ${operation.track_id || operation.section_id || ""}`.trim();
      if (op === "add_section") return `add_section: ${operation.name || "section"} after ${operation.after_section_id || "end"}`;
      if (op === "duplicate_section") return `duplicate_section: ${operation.section_id || "section"} -> ${operation.name || "copy"}`;
      if (op === "delete_section") return `delete_section: ${operation.section_id || "section"}`;
      if (op === "resize_section") return `resize_section: ${operation.section_id || "section"} -> ${operation.bars || "?"} bars`;
      if (op === "move_section") return `move_section: ${operation.section_id || "section"} after ${operation.after_section_id || "start"}`;
      if (op === "add_track") return `add_track: ${operation.name || "track"}`;
      if (op === "duplicate_track") return `duplicate_track: ${operation.track_id || "track"} -> ${operation.name || "copy"}`;
      if (op === "delete_track") return `delete_track: ${operation.track_id || "track"}`;
      if (op === "rename_track") return `rename_track: ${operation.track_id || "track"} -> ${operation.name || "track"}`;
      return `${op}: ${operation.section_id || operation.track_id || ""}`.trim();
    }

    function parseJsonField(id) {
      const raw = $(id).value.trim();
      if (!raw) return {};
      return JSON.parse(raw);
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
      renderAssetSelectors();
      renderReferenceSelectors();
      renderContextPackSelectors();
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
        <label>Asset References
          <div id="project-edit-asset-refs" class="asset-ref-list"></div>
        </label>
        <label>Reference Materials
          <div id="project-edit-reference-refs" class="reference-ref-list"></div>
        </label>
        <label>Context Pack
          <select id="project-edit-context-pack" class="context-pack-select"><option value="">none</option></select>
        </label>
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
      const refs = assetRefsPayload("project-edit-asset-refs");
      if (refs.length) data.asset_refs = refs;
      const referenceRefs = referenceRefsPayload("project-edit-reference-refs");
      if (referenceRefs.length) data.reference_refs = referenceRefs;
      const contextPackId = contextPackIdPayload("project-edit-context-pack");
      if (contextPackId) data.context_pack_id = contextPackId;
      return data;
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

    function actionQueueActionLabel(action) {
      return ({
        refresh_recommendations: "Recommendations",
        refresh_conflicts: "Conflicts",
        save_recommended_context_pack: "Context",
        generate_local_candidates: "Local",
        generate_provider_candidates: "Provider",
        refresh_judge_report: "Judge",
        refresh_decision_report: "Decision",
        inspect_conflict: "Inspect",
        manual_apply_candidate: "Manual Apply",
        manual_resolve_task: "Manual Resolve",
        manual_add_follow_up: "Manual Follow-up",
        skip_stale_task: "Blocked Stale",
        skip_archived_task: "Blocked Archived",
        no_action: "No Action",
      })[action] || action || "-";
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
      let deliveryQa = null;
      let deliverySignoff = { summary: { status: "not_signed" } };
      let message = "No final export yet.";
      try {
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/final-export`);
        manifest = data.final_export;
      } catch (err) {
        message = err.message;
      }
      try {
        deliveryQa = await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-qa`);
      } catch (err) {
        deliveryQa = { summary: { status: "not_ready", readiness: "needs_export", handoff_allowed: false }, delivery_qa: { checks: [], artifact_integrity: { files: [] }, zip: {} }, error: err.message };
      }
      try {
        deliverySignoff = await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff`);
      } catch (err) {
        deliverySignoff = { summary: { status: "not_signed" }, signoff: {}, error: err.message };
      }
      let releaseTargets = { releases: [] };
      try {
        releaseTargets = await api(`/api/projects/${encodeURIComponent(project.project_id)}/release-targets`);
      } catch (err) {
        releaseTargets = { releases: [], error: err.message };
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
          <label><input id="project-final-export-references" type="checkbox" checked> Include Reference Summaries</label>
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
        ${deliveryQaHtml(deliveryQa, deliverySignoff)}
        ${projectAddToReleaseHtml(releaseTargets)}
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
      bindAction("project-refresh-delivery-qa", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-qa/refresh`, { method: "POST" });
        await renderProjectFinalExport(project, versions, target);
      });
      bindAction("project-sign-delivery", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(deliverySignoffPayload(false)),
        });
        await renderProjectFinalExport(project, versions, target);
      });
      bindAction("project-force-sign-delivery", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(deliverySignoffPayload(true)),
        });
        await renderProjectFinalExport(project, versions, target);
      });
      bindAction("project-reset-delivery-signoff", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/delivery-signoff/reset`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: $("project-delivery-reset-reason").value.trim() }),
        });
        await renderProjectFinalExport(project, versions, target);
      });
      bindAction("project-add-to-release", async () => {
        await api(`/api/projects/${encodeURIComponent(project.project_id)}/add-to-release`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            release_id: $("project-release-target").value,
            title: $("project-release-track-title").value.trim(),
          }),
        });
        await loadReleases();
        await renderProjectFinalExport(project, versions, target);
      });
    }

    function projectFinalExportPayload() {
      return {
        version_id: $("project-final-export-version").value,
        include_audio: $("project-final-export-audio").checked,
        include_stems: $("project-final-export-stems").checked,
        include_stem_audio: $("project-final-export-stem-audio").checked,
        include_reference_refs: $("project-final-export-references").checked,
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

    async function renderProjectReferences(project, target) {
      try {
        const data = await api(`/api/projects/${encodeURIComponent(project.project_id)}/references`);
        const rows = (data.references || []).map((reference) => `
          <tr>
            <td>${escapeHtml(reference.reference_id)}</td>
            <td>${escapeHtml(reference.title)}</td>
            <td>${escapeHtml(reference.reference_type)}</td>
            <td>${escapeHtml((reference.tags || []).join(", "))}</td>
            <td>${escapeHtml(reference.usage_count || 0)}</td>
            <td><button class="secondary project-reference-unlink" data-reference-id="${escapeHtml(reference.reference_id)}" type="button">Unlink</button></td>
          </tr>
        `).join("");
        target.innerHTML = `
          <label>Link Reference
            <div id="project-link-reference-refs" class="reference-ref-list"></div>
          </label>
          <div class="actions">
            <button id="project-link-selected-reference" type="button">Link Selected Reference</button>
          </div>
          <table>
            <thead><tr><th>Reference</th><th>Title</th><th>Type</th><th>Tags</th><th>Uses</th><th></th></tr></thead>
            <tbody>${rows || "<tr><td colspan='6'>No linked references.</td></tr>"}</tbody>
          </table>
        `;
        renderReferenceSelectors();
        bindAction("project-link-selected-reference", async () => {
          const refs = referenceRefsPayload("project-link-reference-refs");
          for (const ref of refs) {
            await api(`/api/projects/${encodeURIComponent(project.project_id)}/references/link`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ reference_id: ref.reference_id }),
            });
          }
          await loadReferences();
          await renderProjectReferences(project, target);
        });
        target.querySelectorAll(".project-reference-unlink").forEach((button) => {
          button.addEventListener("click", async () => {
            await api(`/api/projects/${encodeURIComponent(project.project_id)}/references/unlink`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ reference_id: button.dataset.referenceId }),
            });
            await loadReferences();
            await renderProjectReferences(project, target);
          });
        });
      } catch (err) {
        target.innerHTML = `<div class="empty error">${escapeHtml(err.message)}</div>`;
      }
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
        editor: "Editor",
        "review-workbench": "Review Workbench",
        "mix-board": "Mix Board",
        "review-sprints": "Review Sprints",
        candidates: "Candidates",
        "quality-gate": "Quality Gate",
        "final-export": "Final Export",
        compare: "Compare",
        references: "References",
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
      const tabs = ["summary", "edit", "assets", "nodes", "timeline", "tracks", "stems", "quality", "validator", "json", "logs", "artifacts"];
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
        ${job.input_payload && job.input_payload.context_pack ? `
          <div class="summary-grid">
            ${metric("Context Pack", job.input_payload.context_pack.pack_id || "-")}
            ${metric("Context Name", job.input_payload.context_pack.name || "-")}
            ${metric("Context Assets", (job.input_payload.context_pack.asset_refs || []).length)}
            ${metric("Context References", (job.input_payload.context_pack.reference_refs || []).length)}
          </div>
        ` : ""}
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
      } else if (activeTab === "assets") {
        await renderJobAssets(job, target);
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

    async function renderJobAssets(job, target) {
      target.innerHTML = `
        <div class="grid2">
          <label>Asset Types
            <input id="job-asset-types" value="motif,chord_progression">
          </label>
          <label>Section
            <input id="job-asset-section" value="chorus">
          </label>
        </div>
        <div class="grid2">
          <label>Track
            <input id="job-asset-track" placeholder="melody, drums, bass">
          </label>
          <label>Tags
            <input id="job-asset-tags" placeholder="chorus, hook">
          </label>
        </div>
        <div class="actions">
          <button id="job-extract-asset" type="button">Extract Asset</button>
          <span id="job-asset-message" class="message"></span>
        </div>
      `;
      bindAction("job-extract-asset", async () => {
        const data = await api("/api/assets/extract/from-job", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            job_id: job.job_id,
            asset_types: $("job-asset-types").value.split(",").map((item) => item.trim()).filter(Boolean),
            section_name: $("job-asset-section").value.trim(),
            track_name: $("job-asset-track").value.trim(),
            tags: $("job-asset-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
          }),
        });
        $("job-asset-message").textContent = `saved ${data.count || 0}`;
        await loadAssets();
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
        assets: "Assets",
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
        body: JSON.stringify({ target_version: "10.1.0", require_verified_backup: true, allow_dirty: true }),
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
