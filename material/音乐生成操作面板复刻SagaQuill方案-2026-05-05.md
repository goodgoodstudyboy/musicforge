# MusicForge 操作面板方案：复刻 SagaQuill 的本地工作台能力

日期：2026-05-05

## 0. 结论先行

当前 MusicForge 已经完成 `v0.1.0` 的本地 CLI 闭环：读取歌曲请求、生成 `song-plan.json`、写出标准 MIDI、记录运行摘要和事件日志，并且已有测试覆盖。这个阶段适合验证“生成链路能跑通”，但还不适合真正作为日常生产工具使用。

下一步应该把项目升级成一个“本地操作面板优先”的产品形态。参考 SagaQuill 的做法，MusicForge 也需要一个浏览器中的本地工作台：用户在页面里填写歌曲需求、选择风格和输出目标、启动任务、观察进度、查看日志、预览产物、批量导入需求、恢复失败任务、管理 provider 配置。这样业务人员不需要反复敲命令，开发也能通过同一套状态、日志、产物结构排查问题。

本方案建议先复刻 SagaQuill 的架构形状，而不是先做复杂前端工程：第一版仍然使用 Python 标准库 HTTP server + 单页 HTML/CSS/JS + 后台线程任务队列。这样依赖少、本地验证快、可测试性强，符合“所有能力先本地化验证”的准则。

## 1. 背景和前因后果

MusicForge 当前能力：

- 可以通过 CLI 执行本地 deterministic composer。
- 可以输出 `request.json`、`song-plan.json`、`run-summary.json`、`events.jsonl`、`song.mid`。
- 可以用 `--resume` 恢复同一个请求，用 `--force` 显式覆盖旧 run。
- 已经有 schema、validator、MIDI writer、CLI 测试。

当前不足：

- 操作入口还是命令行，不适合高频试歌、改参数、批量生成。
- 没有任务列表、任务状态、失败恢复、暂停/继续、隐藏/删除等工作台能力。
- 没有可视化预览，用户看不到歌曲结构、段落时间线、轨道信息、校验报告。
- 没有 provider 配置面板，后续接入 LLM、编曲 agent、音频渲染服务时会难以管理。
- 没有批量需求导入，无法像小说项目一样批量生产和排队。

SagaQuill 已经证明了一条适合本地创作工具的路线：

- 浏览器面板作为主入口。
- 后端管理任务、日志、批次、provider、产物。
- 单个任务和批量任务都走同一套状态机。
- 所有产物落盘，可恢复、可追踪、可复现。
- 本地先跑通，再做发布和远程化。

因此 MusicForge 的下一阶段不是继续堆 CLI 参数，而是把 CLI 能力包进一个稳定的本地工作台。

## 2. 对 SagaQuill 面板的观察

SagaQuill 的面板不是一个简单表单，而是一个完整的本地生产控制台。它主要实现了以下能力。

### 2.1 本地服务入口

SagaQuill 通过类似下面的命令启动面板：

```powershell
python -m sagaquill serve --host 127.0.0.1 --port 8765
```

打开浏览器后，用户直接在面板里完成项目创建、任务启动、日志查看、批量管理和配置管理。

MusicForge 应该提供同类入口：

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

为了兼容当前 MVP，也要保留旧入口：

```powershell
python -m song_agent.cli examples\song_request.json --out runs\demo --force
```

### 2.2 Provider 配置

SagaQuill 面板内置 provider 配置区，支持：

- Base URL
- API key
- 主模型
- 轻量模型
- review 模型
- wire API
- gateway profile
- reasoning/service tier 类参数
- 保存配置
- 重置配置
- 测试 provider 连通性
- 每个 job 记录 provider snapshot

MusicForge 后续会用到 LLM 规划、歌词、旋律、和声、编曲、审稿、修复等能力，所以 provider 配置必须提前设计。第一版可以不真正调用外部模型，但面板和数据结构要先预留。

### 2.3 单任务生成

SagaQuill 的单任务区可以填写完整小说需求，并启动后台 job。job 会记录：

- job id
- title
- output dir
- status
- created_at / updated_at
- current step
- message
- summary
- error
- attempt_count
- cancel_requested
- input_payload
- provider_snapshot
- logs

MusicForge 需要相同的任务状态模型，只是业务输入换成歌曲需求。

### 2.4 批量任务

SagaQuill 支持 CSV 批量导入、批次启动、批次暂停、批次继续、失败重试、导出结果、打开批次目录。

MusicForge 对应需要支持：

- CSV 批量导入歌曲 briefs。
- 批量生成广告歌、短视频 BGM、游戏循环音乐、主题曲 demo。
- 设置最大并发数。
- 批量暂停/继续。
- 失败项重试。
- 批次导出 summary。

### 2.5 任务管理和运行保护

SagaQuill 有比较完善的 job 生命周期：

- pending
- running
- completed
- failed
- paused
- cancelled
- waiting retry
- hidden

并且支持：

- watchdog
- startup recovery
- stale attempt guard
- retry/backoff
- auto resume
- cancel
- pause/resume
- delete/hide/unhide

MusicForge 第一版可以先实现简化状态机，但必须从一开始按完整模型设计字段，避免后续重构。

### 2.6 产物和预览

SagaQuill 面板能显示：

- 任务摘要
- 运行日志
- provider snapshot
- 输出目录
- 小说内容预览
- delivery cleanup

MusicForge 应该显示：

- 歌曲请求摘要
- SongPlan JSON
- 段落时间线
- 轨道列表
- tempo/key/meter
- 旋律/和声/鼓组/贝斯等轨道统计
- validator 报告
- MIDI 下载或打开目录
- 后续音频波形和播放器

## 3. 复刻原则

这里的“复刻”不是复制小说业务，而是复刻 SagaQuill 的产品结构和工程模式。

应该复刻：

- 本地 web 面板作为主入口。
- Python 标准库 server 起步，减少依赖。
- 单页 HTML/CSS/JS 起步，避免过早引入前端构建链。
- 后台线程运行 job，前端轮询状态。
- job state、logs、summary、artifacts 全部落盘。
- provider 配置可在面板保存、重置、测试。
- batch CSV 导入和批次调度。
- startup recovery、resume、retry、watchdog 等本地生产保护。
- 测试优先，每个阶段都能本地验证。

不应该照搬：

- 小说领域字段。
- 章节/卷/字数等概念。
- SagaQuill 的项目名、UI 文案、内部路径。
- 与音乐业务无关的质量规则。

必须坚持：

- 默认 localhost。
- 默认无外部网络依赖。
- 默认 deterministic pipeline 可运行。
- provider 调用必须是可选能力。
- 每个版本发布前先本地测试通过。

## 4. SagaQuill 到 MusicForge 的业务映射

| SagaQuill 概念 | MusicForge 对应概念 | 说明 |
| --- | --- | --- |
| ProjectInput | SongRequest / SongBrief | 歌曲生成需求 |
| NovelPipeline | SongPipeline / MusicPipeline | 歌曲生成流水线 |
| Chapter | Section | intro、verse、chorus、bridge、outro 等 |
| Volume | Song / Album / Batch group | 单曲或批次集合 |
| Style Bible | Sonic Palette / Style Guide | 风格、音色、节奏、编曲约束 |
| Voice Cards | Instrument Voice Cards | 主旋律、贝斯、鼓、Pad、Lead 等声部设定 |
| Continuity | Motif / Arrangement Memory | 动机、主题、和声走向、能量曲线一致性 |
| Review | Music Review / Validator | 结构、音域、节奏密度、MIDI 合法性检查 |
| Novel Preview | MIDI / SongPlan Preview | 可视化 song-plan、时间线、轨道、MIDI |
| Batch Proposal CSV | Song Brief CSV | 批量导入歌曲需求 |
| Delivery Package | Render Package | MIDI、JSON、日志、后续 WAV/MP3/MusicXML |
| Delivery Cleanup | Render Cleanup | 清理中间产物、打包最终产物 |

## 5. MusicForge 面板目标

面板名称建议：MusicForge Studio 或 MusicForge Panel。

第一目标：

- 让用户不敲命令也能完成一次歌曲生成。
- 让开发不看黑盒也能定位每一步发生了什么。
- 让所有 run 都有清晰的输入、输出、日志、状态和版本记录。

用户在面板里应该能完成：

- 填写歌曲标题、风格、主题、时长、速度、调式、结构、乐器。
- 选择预设，例如中文流行、City Pop、Synthwave、Lo-fi、摇滚、游戏循环、广告短歌、影视配乐。
- 选择输出格式，例如 MIDI、song-plan JSON，后续增加 WAV、MP3、MusicXML、ABC。
- 启动生成任务。
- 查看任务列表和状态。
- 查看实时日志。
- 查看生成摘要。
- 查看段落时间线和轨道统计。
- 下载或打开 MIDI 产物目录。
- 批量导入 CSV 并排队生成。
- 管理 provider 配置。

## 6. 推荐项目结构

建议在现有 `song_agent` 包内新增以下模块。

```text
song_agent/
  cli.py                    # 增加 serve / doctor / init-request 子命令，保留旧 CLI 兼容
  server.py                 # 本地 HTTP server、API handler、JobState、后台任务
  webui.py                  # 单页操作面板 HTML/CSS/JS
  batching.py               # CSV 导入、批次状态、批次调度
  provider.py               # ProviderConfig、保存/读取/测试 provider
  runtime_views.py          # 面板预览用 compact view：段落、轨道、校验、摘要
  storage.py                # 可选：统一 job/batch/project 文件存储；也可先扩展 projectio.py
  agent/
    pipeline.py             # 现有 deterministic pipeline，后续扩展 agent 编排
  renderers/
    midi.py                 # 现有 MIDI writer
  schemas/
    song.py                 # 现有 SongPlan，后续扩展 SongPanelRequest
tests/
  test_server.py
  test_webui.py
  test_server_runtime.py
  test_batching.py
  test_provider.py
```

本地持久化建议：

```text
runs/
  <job_id_or_slug>/
    data/
      request.json
      song-plan.json
      run-summary.json
      job-state.json
      provider-snapshot.json
      validator-report.json
    logs/
      events.jsonl
      server.log.jsonl
    renders/
      song.mid
      song.wav              # 后续
      song.mp3              # 后续
    previews/
      timeline.json
      tracks.json
      chords.json           # 后续

.musicforge/
  provider.json
  batches/
    <batch_id>/
      batch.json
      proposals.json
      items.json
      export.json
```

## 7. 后端 API 设计

第一版 API 要和面板需求对齐，同时给后续批量和 provider 留接口。

### 7.1 基础接口

```text
GET  /
GET  /api/info
GET  /api/template
```

`/api/info` 返回：

- app name
- version
- cwd
- default runs dir
- provider summary
- deterministic mode status

`/api/template` 返回前端表单默认值和预设。

### 7.2 Provider 接口

```text
GET  /api/provider
POST /api/provider
POST /api/provider/reset
POST /api/provider/test
```

第一版可以只保存和回显配置，`test` 在没有配置时返回可理解的错误。后续接 OpenAI-compatible provider 时再真实请求模型。

### 7.3 Job 接口

```text
GET  /api/jobs
POST /api/jobs
GET  /api/jobs/<job_id>
GET  /api/jobs/<job_id>/song-plan
GET  /api/jobs/<job_id>/events
GET  /api/jobs/<job_id>/artifacts
GET  /api/jobs/<job_id>/midi
POST /api/jobs/<job_id>/cancel
POST /api/jobs/<job_id>/pause
POST /api/jobs/<job_id>/resume
POST /api/jobs/<job_id>/hide
POST /api/jobs/<job_id>/unhide
POST /api/jobs/<job_id>/delete
POST /api/jobs/<job_id>/open-folder
POST /api/jobs/<job_id>/render
```

第一版最低要求：

- `POST /api/jobs` 可以启动现有 deterministic composer。
- `GET /api/jobs` 可以列出当前进程内和已落盘的 job。
- `GET /api/jobs/<job_id>` 可以查看详情、日志、summary。
- `GET /api/jobs/<job_id>/song-plan` 可以返回 `song-plan.json`。
- `GET /api/jobs/<job_id>/midi` 可以下载 MIDI。
- `open-folder` 在 Windows 本地打开输出目录。

`pause/resume/cancel` 第一版可先对排队任务完整支持，对正在运行的短任务支持“请求标记”。后续当 pipeline 变成多阶段 agent 后，每个阶段检查 cancel/pause 标记。

### 7.4 Batch 接口

```text
GET  /api/batches
GET  /api/batches/<batch_id>
GET  /api/batches/<batch_id>/export
POST /api/batches/import-csv
POST /api/batches/<batch_id>/launch
POST /api/batches/<batch_id>/pause
POST /api/batches/<batch_id>/resume
POST /api/batches/<batch_id>/resume-all
POST /api/batches/<batch_id>/retry-failed
POST /api/batches/<batch_id>/hide
POST /api/batches/<batch_id>/unhide
POST /api/batches/<batch_id>/delete
POST /api/batches/<batch_id>/open-folder
```

批量可以放到第二或第三阶段，但 API 名称应尽早稳定。

## 8. 前端面板模块设计

第一版可以做成一个单页工作台，左侧为输入和配置，右侧为任务和预览，或者上方输入、下方任务列表。不要做营销页，不需要 hero 大图，直接进入可操作工作台。

### 8.1 顶部状态栏

显示：

- MusicForge 版本
- 当前运行模式：Local deterministic / Provider enabled
- 当前 provider 摘要
- runs 目录
- 轮询状态

### 8.2 Provider 配置区

字段：

- Base URL
- API key
- 主模型
- 轻量模型
- review 模型
- wire API
- gateway/profile
- reasoning effort
- service tier

操作：

- 保存
- 重置
- 测试

注意：

- API key 在前端只显示 masked 状态，不明文回显。
- 配置文件放 `.musicforge/provider.json`，不要写入公开文档。
- 每个 job 启动时保存 provider snapshot，便于复现。

### 8.3 单曲需求区

基础字段：

- title：歌曲名
- language：语言，例如 zh、en、instrumental
- prompt/theme：主题和情绪
- genre/style：风格
- audience/use_case：用途，例如短视频、游戏、广告、练习曲、demo
- duration_seconds：目标时长
- bpm：速度
- key：调
- meter：拍号
- mode：major/minor/modal

结构字段：

- structure：intro、verse、chorus、bridge、outro
- section_count 或 custom sections
- energy_curve：low-medium-high 等
- loopable：是否需要无缝循环

音乐字段：

- instrumentation：乐器列表
- lead_instrument：主旋律乐器
- drum_style：鼓组风格
- bass_style：贝斯风格
- chord_palette：和弦倾向
- melody_range：旋律音域
- density：音符密度
- humanize：人性化程度

歌词字段：

- vocal_mode：instrumental、guide_melody、lyrics_only、full_song_plan
- lyrics_prompt
- existing_lyrics
- rhyme_style
- syllable_density

约束字段：

- must_include
- avoid
- reference_notes
- output_formats

### 8.4 预设区

建议第一批预设：

- 中文流行 90 秒 demo
- City Pop 120 秒
- Synthwave 90 秒
- Lo-fi loop 60 秒
- 游戏战斗循环 45 秒
- 广告短歌 30 秒
- 影视氛围配乐 60 秒
- 摇滚副歌 demo 75 秒

预设只填默认值，不锁死用户编辑。

### 8.5 Job 控制台

显示：

- job id
- title
- status
- current step
- created/updated time
- attempt count
- output dir
- error
- summary

操作：

- 查看详情
- 暂停
- 继续
- 取消
- 隐藏
- 删除
- 打开目录
- 下载 MIDI

### 8.6 预览区

建议分 tab：

- Summary：一句话摘要、风格、时长、BPM、key、输出文件。
- Timeline：段落时间线，显示每个 section 的起止拍、时长、能量。
- Tracks：每个轨道的 channel、program、note count、range、role。
- Validator：schema、MIDI、音乐规则校验结果。
- SongPlan JSON：格式化 JSON。
- Logs：events.jsonl。
- Artifacts：所有文件链接。

MIDI 播放说明：

- 浏览器原生不稳定支持 MIDI 播放。
- 第一版可以提供下载和打开目录。
- 第二版可以引入 WebAudio/Tone.js 或把 MIDI 渲染为 WAV 后用 `<audio>` 播放。

### 8.7 Batch 控制台

字段：

- batch name
- CSV 文件路径或上传
- max concurrency
- default duration
- default style
- output formats
- failure policy

操作：

- 导入 CSV
- 启动批次
- 暂停批次
- 继续批次
- 重试失败
- 导出结果
- 打开目录

CSV 建议字段：

```csv
title,style,theme,use_case,duration_seconds,bpm,key,meter,instrumentation,vocal_mode,lyrics_prompt,must_include,avoid
```

## 9. Job 状态机建议

第一版就定义完整状态，哪怕部分状态暂时不用。

```text
created
queued
running
waiting_retry
paused
completed
failed
cancelled
hidden
```

`JobState` 建议字段：

```text
job_id
title
output_dir
status
created_at
updated_at
step
message
summary
error
attempt_count
auto_resume_count
cancel_requested
pause_requested
hidden
input_payload
provider_snapshot
artifacts
log
```

运行步骤建议：

```text
validate_request
prepare_output_dir
compose_song_plan
validate_song_plan
render_midi
collect_artifacts
write_summary
completed
```

后续 provider/agent 模式可扩展为：

```text
plan_style
draft_structure
write_lyrics
compose_harmony
compose_melody
arrange_tracks
critic_review
repair
render
package
```

## 10. Agent 编排路线

MusicForge 未来不应该只有一个 composer。建议借鉴多 agent 编排，但每一步都必须能落盘和复跑。

### 10.1 第一层：固定流水线

适合 `v0.1.x`：

- 输入校验
- deterministic song plan
- validator
- MIDI render
- summary

优点：稳定、可测试、无网络。

### 10.2 第二层：角色型 agent

适合 `v0.2.x`：

- Brief Planner：把用户需求变成结构化歌曲 brief。
- Lyric Agent：生成歌词或歌词分段。
- Harmony Agent：生成和弦走向。
- Melody Agent：生成主旋律。
- Arrangement Agent：生成配器、轨道、段落能量。
- Drum/Bass Agent：生成节奏组。
- Critic Agent：检查风格、结构、可唱性、MIDI 合法性。
- Repair Agent：根据 critic report 修复。

每个 agent 输出结构化 JSON，不直接输出最终文件。

### 10.3 第三层：图式编排

适合 `v0.3.x`：

```text
Brief -> Style Guide -> Structure
                 -> Lyrics
                 -> Harmony
                 -> Melody
                 -> Arrangement
                 -> Review -> Repair -> Render
```

要求：

- 每个节点输入输出落盘。
- 节点失败可单独重试。
- 节点结果可在面板预览。
- 支持局部重生成，例如只重写 chorus 或只重配鼓组。

### 10.4 第四层：批量和队列

适合 `v0.4.x`：

- CSV 批量导入。
- 每首歌作为独立 job。
- 批次聚合状态。
- max concurrency 控制。
- 失败重试。
- 导出批次报告。

## 11. 版本阶段和 Todo

### Phase A：v0.1.1 本地操作面板 MVP

目标：不接外部 provider，只把现有 CLI 能力搬到浏览器。

开发任务：

- [ ] 新增 `song_agent/webui.py`，提供 `panel_html()`。
- [ ] 新增 `song_agent/server.py`，提供本地 HTTP server。
- [ ] CLI 增加 `serve` 子命令。
- [ ] 保留旧 CLI 调用方式，避免破坏已有测试和文档。
- [ ] `POST /api/jobs` 启动 deterministic pipeline。
- [ ] 后台线程执行 job。
- [ ] job 状态写入 `job-state.json`。
- [ ] `/api/jobs` 返回任务列表。
- [ ] `/api/jobs/<id>` 返回任务详情。
- [ ] `/api/jobs/<id>/song-plan` 返回 song plan。
- [ ] `/api/jobs/<id>/midi` 下载 MIDI。
- [ ] 页面支持填写基础歌曲请求并启动生成。
- [ ] 页面支持查看任务状态、日志、summary、输出目录。
- [ ] 页面支持打开输出目录。
- [ ] 新增 `tests/test_webui.py`。
- [ ] 新增 `tests/test_server.py`。

本地验收：

```powershell
python -m pytest -q
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

浏览器验收：

- 打开面板能看到 MusicForge 版本和表单。
- 填写一首歌并点击生成。
- 任务从 queued/running 变成 completed。
- `runs/<job>/renders/song.mid` 存在。
- 面板可以看到 `song-plan.json` 摘要和日志。

### Phase B：v0.1.2 预览和恢复增强

目标：让面板具备真正排查和预览能力。

开发任务：

- [ ] 新增 `runtime_views.py`，把 SongPlan 转成 timeline/tracks/validator view。
- [ ] 页面增加 Summary / Timeline / Tracks / Validator / JSON / Logs tab。
- [ ] server 启动时扫描 `runs/`，恢复历史 job 列表。
- [ ] job 失败时保留 error 和已生成产物。
- [ ] 实现 hide/unhide/delete。
- [ ] 实现 cancel_requested。
- [ ] job detail 支持 artifact list。
- [ ] 增加更清晰的错误输出和前端错误提示。

本地验收：

- 重启 server 后，之前的 completed job 仍能在面板看到。
- 故意传入非法请求，job 失败但面板不崩。
- 删除/隐藏任务不会影响其他任务。

### Phase C：v0.2.0 Provider 配置和模型接入

目标：面板具备 provider 管理能力，开始支持 LLM 结构化输出。

开发任务：

- [ ] 新增 `provider.py`。
- [ ] 支持 `.musicforge/provider.json`。
- [ ] 支持环境变量覆盖。
- [ ] 面板支持保存、重置、测试 provider。
- [ ] 每个 job 写入 `provider-snapshot.json`。
- [ ] 新增 `doctor` 子命令，检查 Python、写权限、provider 配置。
- [ ] 新增 provider client 的最小封装。
- [ ] provider 调用必须可关闭，默认 deterministic 仍可用。
- [ ] 新增模型输出 schema 校验。
- [ ] 新增 provider 相关测试，使用 mock，不依赖真实网络。

本地验收：

- 未配置 provider 时，deterministic job 仍能成功。
- 配置错误 provider 时，`provider/test` 返回可理解错误。
- 测试中 mock provider 可以生成结构化 song plan。

### Phase D：v0.2.1/v0.3.0 音乐 agent 和 review loop

目标：从单 composer 变成多阶段音乐生成系统。

开发任务：

- [ ] 定义 StyleGuide/SonicPalette schema。
- [ ] 定义 SectionPlan schema。
- [ ] 定义 HarmonyPlan schema。
- [ ] 定义 MelodyPlan schema。
- [ ] 定义 ArrangementPlan schema。
- [ ] 定义 CriticReport schema。
- [ ] 实现 Brief Planner。
- [ ] 实现 Harmony Agent。
- [ ] 实现 Melody Agent。
- [ ] 实现 Arrangement Agent。
- [ ] 实现 Critic Agent。
- [ ] 实现 Repair Agent。
- [ ] 面板展示每个 agent 节点输出。
- [ ] 支持局部重生成，例如 regenerate chorus。

本地验收：

- 一个 job 的每个 agent 阶段都有落盘 JSON。
- 任一阶段失败，面板能定位失败阶段。
- critic 发现问题后可以自动修复一次，并记录修复前后差异。

### Phase E：v0.4.0 批量生产

目标：复刻 SagaQuill 的 batch console。

开发任务：

- [ ] 新增 `batching.py`。
- [ ] 支持 CSV 导入。
- [ ] 支持 batch record / proposal record / item state。
- [ ] 支持 max concurrency。
- [ ] 支持 launch/pause/resume/retry-failed/resume-all。
- [ ] 支持 batch export。
- [ ] 页面增加 batch 控制台。
- [ ] 批次任务复用单 job 状态机。

本地验收：

- 导入 3 首歌 CSV。
- max concurrency=1 时顺序执行。
- 其中 1 首失败后可以 retry failed。
- batch export 包含每首歌的状态、输出目录和错误信息。

### Phase F：v0.5.0 音频渲染和播放器

目标：从 MIDI demo 进入可听音频 demo。

开发任务：

- [ ] 评估本地 MIDI 到 WAV 渲染方案。
- [ ] 支持 SoundFont 配置。
- [ ] 输出 WAV。
- [ ] 可选输出 MP3。
- [ ] 面板增加 `<audio>` 播放器。
- [ ] 面板显示波形或基础时长信息。
- [ ] render 失败不能影响 song-plan 和 MIDI 保存。

本地验收：

- 生成 job 后能在浏览器播放 WAV。
- 没有 SoundFont 时给出明确提示。
- MIDI 文件仍然保留。

### Phase G：v0.6.0 运行保护、权限和发布

目标：让面板可以更安全地长期使用。

开发任务：

- [ ] 非 localhost 绑定必须要求 access token。
- [ ] 支持 bearer/basic/custom header。
- [ ] startup recovery 更完整。
- [ ] watchdog 监控长时间无进展任务。
- [ ] retry/backoff 策略可配置。
- [ ] provider secret 不明文回显。
- [ ] 发布前 secret scan。
- [ ] 增加 release checklist。

本地验收：

- `--host 0.0.0.0` 未提供 token 时拒绝启动。
- 提供 token 后 API 需要鉴权。
- 错误 token 被拒绝。

## 12. 测试策略

每个阶段都必须先本地测试。

基础测试：

```powershell
python -m pytest -q
```

面板测试：

- `test_webui.py` 检查 HTML 包含关键表单字段和按钮。
- `test_server.py` 检查 `/api/info`、`/api/template`、`/api/jobs`、`POST /api/jobs`。
- `test_server_runtime.py` 检查 job 成功、失败、取消、恢复。
- `test_provider.py` 检查保存、重置、masked key、mock test。
- `test_batching.py` 检查 CSV 导入、批次状态、失败重试。

手工验收：

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

然后在浏览器检查：

- 页面能打开。
- 创建任务能成功。
- 刷新页面任务仍在。
- 日志持续更新。
- MIDI 能下载。
- 输出目录能打开。

## 13. 风险和处理

### 13.1 面板范围过大

风险：一次性复刻 SagaQuill 全部能力会拖慢开发。

处理：严格按 Phase A 到 Phase G 执行。第一版只做本地单 job 面板，后续再加 provider、batch、音频。

### 13.2 浏览器不能稳定播放 MIDI

风险：用户以为面板能直接播放 MIDI，但不同浏览器支持不一致。

处理：第一版提供下载和打开目录。后续通过 WAV 渲染或 WebAudio 实现播放。

### 13.3 当前 pipeline 太短，pause/cancel 感知不明显

风险：deterministic composer 运行很快，暂停/取消没有真实效果。

处理：第一版先实现状态字段和排队任务控制。后续 agent pipeline 每个阶段检查 pause/cancel。

### 13.4 Provider 接入后不稳定

风险：模型输出不符合 schema，网络失败，任务卡住。

处理：所有 provider 输出必须 schema validate；失败落盘；retry/backoff；面板显示 provider snapshot 和错误。

### 13.5 公开仓库泄露本机信息

风险：文档或配置中出现本机路径、账号、token。

处理：公开文档只写通用命令和占位符。provider 配置、token 文件、个人路径不得进入仓库。

## 14. 开发执行准则

开发接手时按下面顺序做。

1. 先读现有 `README.md`、`song_agent/cli.py`、`song_agent/runtime.py`、`song_agent/projectio.py`、`song_agent/agent/pipeline.py`、`song_agent/renderers/midi.py`。
2. 先保留当前 CLI 行为，不破坏 `v0.1.0` 的测试。
3. 新增 `serve` 时做成增量能力，不要把 CLI 重写成不兼容模式。
4. 第一版不引入前端构建工具。
5. 第一版不强依赖任何外部 provider。
6. 所有 job 输入、状态、日志、产物必须落盘。
7. 所有预期错误返回 `error: ...` 或 JSON error，不给用户 traceback。
8. 所有新增 API 都要有测试。
9. 所有运行产物继续放 `runs/`，不得提交进 Git。
10. 所有私密配置放 `.musicforge/` 或用户目录，并加入 `.gitignore`。
11. 每个阶段完成后先跑 `python -m pytest -q`。
12. 本地面板手工跑通后，再考虑提交、打 tag、发布。

## 15. Phase A 详细 Todo

Phase A 是当前最该立刻执行的工作。开发不要先做 provider、batch、音频播放器，先让浏览器能跑通当前 MIDI MVP。

### 15.1 CLI

- [ ] 增加子命令解析。
- [ ] 支持 `serve`。
- [ ] 支持 `generate`，但保留旧 positional request 调用。
- [ ] `serve` 默认 host 为 `127.0.0.1`。
- [ ] `serve` 默认 port 为 `8787`。

### 15.2 Server

- [ ] 使用 `ThreadingHTTPServer`。
- [ ] 实现 JSON request/response helper。
- [ ] 实现 path router。
- [ ] 实现 job id 生成。
- [ ] 实现后台线程 runner。
- [ ] 实现 job state lock。
- [ ] 实现 event log append。
- [ ] 实现 artifact discovery。

### 15.3 Web UI

- [ ] 单页 HTML。
- [ ] 基础 CSS。
- [ ] 基础表单。
- [ ] fetch API 创建 job。
- [ ] 轮询 job list。
- [ ] 点击 job 显示详情。
- [ ] 显示日志。
- [ ] 显示 song plan JSON。
- [ ] 提供 MIDI 链接。

### 15.4 Project IO

- [ ] 复用现有 `ProjectWriter` 或 `projectio.py`。
- [ ] 增加 job-state 写入。
- [ ] 增加 validator report 写入。
- [ ] 保持 `request.json`、`song-plan.json`、`run-summary.json` 兼容。

### 15.5 Tests

- [ ] `test_webui_contains_music_fields`
- [ ] `test_info_endpoint`
- [ ] `test_create_job_completes`
- [ ] `test_job_detail_includes_artifacts`
- [ ] `test_midi_endpoint_returns_file`
- [ ] `test_invalid_request_returns_json_error`

## 16. 第一版完成定义

Phase A 完成后，应满足：

- 用户可以执行 `python -m song_agent.cli serve --host 127.0.0.1 --port 8787`。
- 浏览器打开后能看到 MusicForge 操作面板。
- 用户可以从面板创建一首歌。
- 面板能看到 job 从 running 到 completed。
- 面板能查看 summary、logs、song-plan。
- 面板能下载或打开 MIDI 所在目录。
- 关闭再重启 server 后，至少 completed job 可以被重新发现。
- `python -m pytest -q` 全部通过。
- 不需要任何外部网络和 API key。

## 17. 给开发的推荐提交节奏

建议不要一个大提交完成所有内容，按下面拆：

1. `feat: add local web server skeleton`
2. `feat: add musicforge panel shell`
3. `feat: run song jobs from panel`
4. `feat: expose song artifacts in panel`
5. `test: cover web server and panel job flow`
6. `docs: document local panel workflow`

每个提交前都运行：

```powershell
python -m pytest -q
```

每个阶段发布前再手工验证：

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

## 18. 最重要的产品判断

MusicForge 后续真正有价值的不是“能生成一个 MIDI 文件”，而是“能像一个音乐生产工作台一样持续试、改、批量跑、回看、修复、复现”。SagaQuill 的面板已经把这条路跑通了：本地服务、任务状态、日志、批量、provider、恢复、发布准则。

MusicForge 现在应该沿着同样的产品骨架前进，把小说生产工作台改造成音乐生产工作台。第一步不要贪多，只要把当前 CLI MVP 放进浏览器并且保证本地测试通过，就已经完成了从“脚本”到“工具”的关键升级。
