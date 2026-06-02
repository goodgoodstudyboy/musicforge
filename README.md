# Song Agent

An open, model-provider-agnostic songwriting agent.

The goal is not to wrap Suno, Udio, Mureka, ElevenLabs Music, or any other
closed music generator. The core idea is:

1. Use a frontier/world model API for reasoning, lyrics, composition, and
   arrangement planning.
2. Emit open musical formats such as JSON, MIDI, MusicXML, ABC, or Strudel code.
3. Render with open or locally controlled tools such as FluidSynth, MuseScore,
   REAPER, Ableton, LMMS, Strudel, or Tone.js.

## MVP

The first working version generates an instrumental song demo:

```text
song brief
  -> lyrics and structure
  -> chords
  -> melody
  -> bass and drums
  -> MIDI
  -> WAV/MP3 render
```

Human vocals are intentionally deferred. Singing synthesis is a separate
problem and needs a dedicated open backend.

Current local MVP:

```powershell
python -m song_agent.cli examples\song_request.json --dry-run
python -m song_agent.cli examples\song_request.json --out runs\demo
python -m song_agent.cli generate examples\song_request.json --out runs\demo
python -m song_agent.cli generate examples\song_request.json --out runs\demo-nodes --pipeline-mode multinode
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

The full run writes:

```text
runs/demo/data/request.json
runs/demo/data/run-options.json
runs/demo/data/nodes/*.json
runs/demo/data/song-plan.json
runs/demo/data/run-summary.json
runs/demo/logs/events.jsonl
runs/demo/renders/song.mid
```

The default generation path is model-optional: it uses a deterministic composer
so the JSON-to-MIDI loop can be tested without network access.

## Local Studio

The browser panel runs locally and uses the same deterministic pipeline as the
CLI:

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`, fill in a song request, and start a job. Completed
jobs write `job-state.json`, `song-plan.json`, `events.jsonl`, and `song.mid`
under `runs/<job-id>/`.

v4.7.0 includes a local Release Workspace for assembling multiple Project Delivery
Signoff-approved Final Exports into an EP, album, or demo pack. Release QA checks
each track's Project Final Export, Project Delivery QA, Project Delivery Signoff,
artifact baseline, ZIP integrity, stale snapshots, and redaction before creating
a path-safe Release Export folder and Release ZIP under `.musicforge/releases/`.
Release Signoff is explicit and audited; signed releases cannot be silently
mutated without resetting signoff. The signoff record binds to the final Release
Export manifest that is also written into the Release ZIP.

Music Acceptance Lab adds a developer self-check workspace for generated music
quality before release. It can create representative generated-song suites, run
automatic SongPlan/MIDI/WAV health checks, collect explicit listening reviews,
build `music-acceptance-report.json`, and sign off the suite with report and
payload hashes. Signed acceptance suites are read-only until signoff is reset,
and report reads re-check source/content hashes so tampered reviews or reports
show up as failed.

```powershell
python -m song_agent.cli acceptance-check --profile midi_smoke --auto-review --render-audio never
python -m song_agent.cli acceptance-check --profile developer_manual --render-audio auto --report-out runs\acceptance-v450.json
python -m song_agent.cli acceptance-check --profile release_candidate --render-audio auto
python -m song_agent.cli acceptance-check --profile audio_required --render-audio require --manual-required
python -m song_agent.cli acceptance-diff runs\acceptance-baseline.json runs\acceptance-current.json --json
python -m song_agent.cli acceptance-analytics --scope global --refresh --json
python -m song_agent.cli acceptance-fix-sprint create --analytics-report-id analytics-20260520-example --json
python -m song_agent.cli acceptance-kb refresh --json
python -m song_agent.cli acceptance-kb search --issue-type hook --style rap --json
python -m song_agent.cli acceptance-kb recommend --issue-type rhythm --song-id rap_beat_001 --json
```

Acceptance Profiles make the gate repeatable: `midi_smoke` is a synthetic
MIDI-only smoke, `developer_manual` is the default six-case developer run,
`release_candidate` runs the full 12-song regression songbook and requires one
manual accepted review for every built-in song ID with no duplicate song IDs;
`audio_required` also requires WAV output. Use
`--render-audio never` for stable MIDI-only self-checks; it disables WAV as a
required health gate even when a local renderer config exists. `--auto-review`
is only for CI/smoke and writes `review_mode=synthetic`; release-candidate
readiness still requires a person to play the MIDI/WAV and record manual
listening reviews. Release Signoff can bind an acceptance suite and blocks
non-manual, incomplete-songbook, or otherwise non-release-ready acceptance
reports unless force signoff is used and audited.

Human Review Packs turn an Acceptance Suite into an offline listening package
for business or external reviewers. The pack ZIP contains a static `index.html`,
case MIDI/WAV assets, `response-template.json`, `pack.json`, `manifest.json`,
and checksums. Reviewers can open the pack locally, listen, export a response
JSON, and the Studio/API import writes those responses back as manual
`listening-review.json` records. Imports are source-hash guarded, reject
`source_path`, and `needs_fix` or `rejected` responses create follow-up review
work records without applying edits automatically.

```powershell
python -m song_agent.cli verify-human-review-pack path\to\human-review-pack.zip --json --report-out human-review-verification-report.json
```

Acceptance Analytics turns Acceptance Suites, Regression Songbook cases, Human
Review Pack imports, and follow-up ReviewTasks into deterministic quality
reports. It produces songbook heatmaps, issue taxonomy, reviewer summaries,
trend and weakness rankings, and manual-only recommendations. Recommendations
can create ReviewTasks only through an explicit user action; analytics never
generates candidates, applies edits, closes tasks, or signs releases. Release
Export writes `acceptance-analytics-summary.json`, and Release Signoff records
analytics evidence. A blocked analytics readiness status prevents normal release
signoff until force signoff is used with an audited override.

Acceptance-driven Fix Sprints turn stale-safe Acceptance Analytics
recommendations into an explicit repair loop: create a Fix Sprint, create or
bind ReviewTasks, run a recheck Acceptance Suite, refresh the delta report, and
close the sprint only after non-waived items are fixed or audited. The sprint
never generates candidates, applies edits, resolves tasks, or signs releases on
its own. Recheck suites are kept out of the source analytics hash so the repair
loop can compare before/after reports without making its own source stale.
Release Export writes `acceptance-fix-sprints-summary.json`, and Release
Signoff can require closed Fix Sprint evidence with
`require_acceptance_fix_sprint=true`. Project Export and Final Export also carry
the latest matching Fix Sprint summary for project-level handoff review.

Acceptance Knowledge Base turns closed, non-stale Fix Sprints into local
issue/fix/outcome entries with deterministic effectiveness scores, issue/style
patterns, search, and advisory recommendations. It is local-only and does not
call external models, create tasks, apply edits, or gate release signoff.
Project Export, Release Export, Final Export, and Release Signoff carry only
sanitized KB summaries, not full listening notes or raw provider responses.

Knowledge-assisted Fix Plans use fresh Acceptance Analytics plus local KB
evidence to rank proposed repair work before a Fix Sprint is created. A plan can
create only one Fix Sprint, and every execution remains manual: it never applies
edits, resolves tasks, changes scoring rules, or signs releases automatically.

Fix Plan Outcome Review evaluates a used Fix Plan after its generated Fix
Sprint is closed. It compares the plan, planned items, Fix Sprint items, delta
report, closeout report, and KB evidence to produce deterministic plan
effectiveness, ranking alignment, KB helpfulness, item outcomes, and calibration
hints. Outcome Review is source-hash guarded and can be refreshed from Studio or
CLI:

```powershell
python -m song_agent.cli acceptance-fix-plan review afp-000001 --refresh
python -m song_agent.cli acceptance-fix-plan review afp-000001 --json --report-out runs\fix-plan-review.json
```

Release Signoff can require non-stale Outcome Review evidence with
`require_acceptance_fix_plan_review=true`. Project Export, Release Export, and
Final Export carry only sanitized summaries; full item outcomes stay in the
local workspace.

Planning Rule Simulation replays historical Outcome Reviews through local
candidate rule sets such as `synthetic_strict`, `waiver_strict`, and
`manual_conservative`. It is a scoring sandbox only: it does not modify
production planning rules, create Fix Plans, create Sprints, apply edits, or
call providers. Simulations are source-hash guarded against changed rulesets or
Outcome Reviews, and exports/signoff carry only sanitized summaries.

```powershell
python -m song_agent.cli planning-ruleset create --template synthetic_strict --name "Synthetic Strict"
python -m song_agent.cli planning-simulation run --ruleset-id afprs-000001 --review-id afpr-000001 --json --report-out runs\planning-simulation.json
```

Release Signoff can require non-stale simulation evidence with
`require_planning_rule_simulation=true`; a worse candidate recommendation is
recorded as evidence for review but does not automatically activate rules.

Planning Rule Governance promotes simulated rule sets into frozen active rule
versions. A promotion must be created from non-stale simulation evidence, then
manually approved and promoted before new Acceptance Fix Plans record it. The
active pointer can be rolled back, and governance never creates Fix Plans,
creates Sprints, applies edits, or signs releases automatically.

```powershell
python -m song_agent.cli planning-rule-governance promote-request --ruleset-id afprs-000001 --simulation-id afpsim-000001 --json
python -m song_agent.cli planning-rule-governance approve prgprom-000001 --approved-by developer --note "Historical alignment improved"
python -m song_agent.cli planning-rule-governance promote prgprom-000001 --promoted-by developer
python -m song_agent.cli planning-rule-governance active --json
```

Release Signoff can require non-stale active governance evidence with
`require_planning_rule_governance=true`. Project Export, Release Export, and
Final Export include compact governance summaries and do not include the full
frozen ruleset payload.

Planning Rule Impact Monitoring observes what happens after an active Planning
Rule Version is used by Fix Plans. It aggregates adoption, Outcome Review
effectiveness, manual versus synthetic evidence, risk drift, and rollback
recommendations. It is monitoring only: rollback recommendations never execute
automatically and must still go through explicit Governance rollback.

```powershell
python -m song_agent.cli planning-rule-impact refresh --json
python -m song_agent.cli planning-rule-impact list --json
python -m song_agent.cli planning-rule-impact show prgir-000001 --json
```

Release Signoff can require non-stale impact evidence with
`require_planning_rule_impact=true`. Stale reports, active-version mismatch, and
report integrity failures cannot be force-signed. Impact report conclusions are
hash-bound with `integrity_hash`, so local edits to recommendation, warning, or
manual evidence fields block signoff; rollback recommendations require
`force=true` plus an audited `override_reason`.

Real Audio Baseline adds deterministic WAV health reports and manual WAV review
evidence. Acceptance cases with WAV output write `audio-health.json` and bind
manual `audio_mode=wav` reviews to the current WAV hash and health report hash.
Release Audio QA checks every selected track's `song.wav` before signoff; use
`require_audio_health=true` and `require_human_audio_review=true` on Release
Signoff when real audio is a release gate.

Per-track Audio Review evidence tightens that gate for Release tracks. Each
track can store a manual review under `.musicforge/releases/<release-id>/audio-
reviews/`, bound to the current track WAV hash, audio artifact, audio health
hash, and marker-to-section mapping. Release Signoff with
`require_per_track_audio_review=true` requires every track to have a current
manual accepted WAV review; synthetic-only, missing, stale, tampered, or
redaction-failed reviews hard-block signoff. Release Export writes
`audio-reviews/summary.json` and individual review JSON files into the ZIP, and
`verify-release --require-audio --require-human-review` checks those per-track
reviews against the packaged `song.wav` files offline.

Audio Revision Workbench closes the loop from a `needs_fix` audio marker to a
reviewed mix correction. A Release audio review marker can create an audio
revision issue, generate deterministic Mix Patch candidates, render MIDI plus
real renderer-backed WAV previews for A/B listening, require a manual accepted
candidate review, and apply the selected candidate as a new
`audio_revision_mix_edit` Project Version. Renderer failures keep candidates
out of manual A/B approval. The Release track is explicitly moved to that
applied version, old audio reviews become historical/stale, and the issue must
be manually rechecked before the session closeout can pass. Release Signoff can
require current active marker coverage with
`require_audio_revision_closeout=true`, and portable verification can require
the exported session/issue/candidate evidence with
`verify-release --require-audio-revisions`.

Mastering QA adds a deterministic release-level audio consistency pass after
track audio revision and mix work. Built-in Mastering Profiles define target
sample format, peak ceiling, clipping tolerance, loudness proxy target, album
track delta, and head/tail silence thresholds. A Release can run Mastering
Analysis, create a local gain/trim plan, render mastered candidates, collect a
manual A/B accepted review, and select one mastered candidate for export. Release
Signoff with `require_mastering_qa=true` blocks missing, stale, tampered, or
synthetic-only mastering evidence. Release Export packages the selected mastered
WAV as each track's `song.wav` plus `mastering/` analysis, plan, summary, and
selected-candidate evidence; `verify-release --require-mastering` validates that
evidence offline.

Distribution Audio Formats add local MP3/FLAC/AAC/WAV derivative generation from
the selected mastered WAV, with built-in encoding profiles and a redacted local
encoder config. Real use points to FFmpeg through local config or environment
variables; deterministic fake runners are test-only injection helpers and cannot
be persisted through the public API or Studio.
Release Signoff with `require_encoded_audio=true` requires current encoded
profile manifests and a rebuilt Release Export; signed releases cannot render or
reset encoded audio without resetting signoff. Release Export writes
`encoded-audio-summary.json`, and `verify-release --require-encoded-audio
--require-audio-formats mp3_320` validates encoded evidence offline. Distribution
Targets can require audio format profiles such as `mp3_320`; Distribution Export
packages matching encoded track audio plus `encoded-audio/` manifests, and
`verify-distribution-package --require-encoded-audio` catches hash or header
tampering such as fake MP3 files.

Encoded Audio Acceptance adds per-format health reports and per-track listening
reviews for encoded delivery files. Health checks reject stale manifests, fake
encoder evidence, bad headers, missing hashes, and tiny placeholder outputs.
Release and Distribution Signoff can require
`require_encoded_audio_review=true`, which means every required encoded
profile/track needs one current manual or external-import accepted review bound
to the exact encoded file hash. Synthetic-only reviews, stale source hashes,
duplicate accepted reviews, redaction findings, or stale exports block signoff.
Release Export writes `encoded-audio-acceptance-summary.json`,
`encoded-audio-health/`, and `encoded-audio-reviews/`; Distribution Export writes
the same evidence under `encoded-audio-acceptance/`. Offline verifiers can enforce
the evidence with `--require-encoded-audio-review`.

Release Format Decision Workbench explains why specific encoded profiles are
delivered. A Release can create a format decision session, build a deterministic
matrix for profiles such as `mp3_320`, `flac_lossless`, and `aac_256`, generate
recommendations, and record a manual decision that selects delivery profiles,
archives fallback profiles, and rejects unsuitable profiles. Release Signoff
with `require_format_decision=true` requires selected profiles to cover the
requested delivery formats and blocks stale, tampered, fake-runner, or rejected
profile evidence. Release Export writes `format-decision/` sidecars, and
`verify-release --require-format-decision` validates the decision report offline.
Distribution Targets can also require format decision evidence; target packages
write `format-decision/target-decision-summary.json`, and
`verify-distribution-package --require-format-decision` validates the packaged
decision evidence.

Rights Clearance Workbench records local copyright and clearance evidence for a
Release. It stores parties, per-track contributor splits, source usage
declarations, and manual clearance reviews, then builds a signed
`rights/report.json` with source and integrity hashes. Release Signoff can require
`require_rights_clearance=true`; incomplete contributor splits, uncleared
sources, stale reports, tampered evidence, synthetic review modes, metadata credit
mismatches, or redaction findings block signoff. Rights reports also aggregate
required source provenance from Project versions, Final Export, job artifacts,
asset/reference refs, context packs, editor clips/templates, and provider
summaries, so original-only declarations do not cover external references or
assets. Release Export writes
`rights/summary.json`, `rights/report.json`, and per-track rights records.
Distribution and Submission packages carry rights summaries, and offline
verifiers support `--require-rights-clearance`.

Useful local commands:

```powershell
python -m song_agent.cli release-audio-review list release-000001
python -m song_agent.cli release-audio-review add release-000001 --track-id track-000001 --status accepted --rating 4 --reviewer local-user --playback-confirmed --notes "Manual WAV playback accepted."
python -m song_agent.cli release-audio-review summary release-000001 --write
python -m song_agent.cli release-audio-review create-task release-000001 arv-000001 m-000001
python -m song_agent.cli release-encode release-000001 --profiles mp3_320,flac_lossless --json
python -m song_agent.cli encoded-audio-acceptance release-000001 --profiles mp3_320 --refresh-health --write --json
python -m song_agent.cli format-decision release-000001 --profiles mp3_320,flac_lossless --select mp3_320 --archive flac_lossless --reason "MP3 delivery with FLAC archive" --activate --json
python -m song_agent.cli verify-release path\to\release-export.zip --require-rights-clearance
python -m song_agent.cli verify-distribution-package path\to\distribution-package.zip --require-rights-clearance
python -m song_agent.cli verify-submission-package path\to\submission-package.zip --require-rights-clearance
```

Arrangement Mix Controls add a local Mix Board for small, auditable corrections
before a new Project Version is created. A Mix Patch can adjust track volume,
pan, mute/solo, velocity scale, and section-level velocity/volume automation.
Mix preview renders MIDI without mutating the parent version; apply creates a
`mix_control_edit` child version with `mix-state.json` and `mix-patch.json`
evidence. Stem rendering writes `stems/manifest.json` and `stems/stem-health.json`.
Release Audio Review markers can create a Mix Patch draft, and Release Signoff
can require `require_current_mix_state=true` plus
`require_stem_audio_health=true`. Release Export and `verify-release
--require-stems` carry and validate the stem health evidence offline.

Release Metadata stores release-level fields, track-level ISRC/lyrics/credits,
metadata QA, and export files for `release-metadata.json`,
`platform-metadata.csv`, `credits.csv`, and `lyrics/*.txt`. Metadata exports are
included in the Release Export manifest and ZIP, with hash checks and redaction
scanning in the portable verifier.

Release ZIPs can be
verified outside the workspace:

```powershell
python -m song_agent.cli verify-release path\to\release-export.zip --json --report-out release-verification-report.json
python -m song_agent.cli verify-release path\to\release-export.zip --require-audio --require-human-review
python -m song_agent.cli verify-release path\to\release-export.zip --require-audio --require-human-review --require-audio-revisions
python -m song_agent.cli verify-release path\to\release-export.zip --require-audio --require-mastering
python -m song_agent.cli verify-release path\to\release-export.zip --require-encoded-audio --require-audio-formats mp3_320
python -m song_agent.cli verify-release path\to\release-export.zip --require-encoded-audio --require-encoded-audio-review --require-audio-formats mp3_320
python -m song_agent.cli verify-release path\to\release-export.zip --require-format-decision --require-audio-formats mp3_320
```

The verifier reads only the ZIP, checks entry safety, duplicate entries,
manifest file hashes, signoff hash binding, track core artifacts, redaction, and
optional audio/stem requirements. Release signoff sidecar payloads are also
hash-bound so displayed signer and signed-at fields cannot be changed without
failing verification.

Distribution Prep builds platform handoff packages from a signed Release Export
without reading Project workspaces or storing platform credentials. It supports
built-in distribution profiles, cover artwork import/QA, metadata and CSV
formula checks, Distribution Export/ZIP, Distribution Signoff, and portable
package verification. Artwork import accepts uploaded base64 payloads only, and
signed distribution targets reject repeat signoff before any QA refresh can
mutate the signed package audit trail:

Platform Template Packs add local-only distribution templates for target rules,
metadata CSV mapping, package file naming, and human submission checklists.
Templates can be created, cloned, imported, exported, and bound to Distribution
Targets; they are not official platform rules and do not upload, submit, connect
to distributor APIs, or store platform credentials. Template and checklist hashes
are written into Distribution Export/ZIP and checked by the portable verifier.

Distribution Package Layout Contract turns template `file_naming` into an
auditable package layout rule set. Audio, artwork, and lyrics are rendered
through one layout planner; Distribution Export writes
`layout/manifest-layout.json` and `layout/file-tree.txt`; Studio exposes a
Layout preview; and `verify-distribution-package` validates layout hashes,
paths, file hashes, artwork package paths, and legacy v4.1 package
compatibility.

Submission Workspace groups signed Distribution Targets into local submission
batches for platform handoff tracking. It adds Submission QA, Export, ZIP,
Signoff, portable verification, and external submitted/feedback/accepted records.
Signed Submission packages cannot be silently rebuilt or have targets changed
without resetting signoff, while external status records remain auditable local
events. External status records require a signed Submission package and valid
item state: pending or stale items cannot be marked submitted or accepted. This
is local tracking only; it does not upload to platforms or store platform
credentials.

Submission Evidence Archive records what happens after a signed Submission
Package leaves MusicForge: platform submission receipts, feedback, needs-change
notices, acceptance confirmations, resubmission rounds, and uploaded evidence
attachments. Legacy submitted/feedback/accepted APIs now create evidence records
automatically. Evidence attachments accept uploaded base64 content only and
reject `source_path`, `local_path`, or `file_path`. Evidence Export/ZIP and
Evidence Signoff are independent from the original signed Submission Package, so
post-submission evidence can be audited without rebuilding the submitted package.

```powershell
python -m song_agent.cli verify-submission-package path\to\submission-package.zip --json --deep --report-out submission-verification-report.json
```

```powershell
python -m song_agent.cli verify-submission-evidence-package path\to\submission-evidence-package.zip --json --deep --require-accepted --report-out submission-evidence-verification-report.json
```

```powershell
python -m song_agent.cli verify-distribution-package path\to\distribution-package.zip --json --require-encoded-audio --require-format-decision --report-out distribution-verification-report.json
```

v0.6.0 adds local access control for Studio. Loopback hosts can still run without
a token:

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

Binding to a non-localhost host requires a token:

```powershell
python -m song_agent.cli serve --host 0.0.0.0 --port 8787 --access-token <token>
```

## Reference Analysis

Studio can import local WAV, MIDI, lyrics text, and style-note references, then
analyze them without external services. WAV analysis reports basic PCM metadata
and a bounded waveform envelope. MIDI analysis parses format 0/1 files, shows
track role hints, generates slice suggestions, and can turn a slice into a real
note-based Creative Asset.

v1.8.0 keeps the scope local and low-dependency: it does not add MP3 import,
audio-to-MIDI, transcription, or automatic BPM/key detection.

## Library Search and Context Packs

v1.9.0 adds a local Library Index over Creative Assets and References. Search
and recommendation are deterministic and explainable: results include score
breakdowns for token, role, style, tempo/key, quality, favorite, usage, and
freshness matches. The index is derived data under `.musicforge/library/` and
can be rebuilt at any time.

Context Packs are saved selections of `asset_refs` and `reference_refs` under
`.musicforge/context-packs/`. Applying a pack expands back into the existing
reference snapshot chain, so generation, Project versions, variations, edits,
provider previews, candidates, and Prompt A/B all keep using the same safety
checks. Hidden or stale sources are rejected before use.

Library and Context Pack APIs:

```text
GET  /api/library/index
POST /api/library/rebuild
POST /api/library/search
POST /api/library/recommend
GET  /api/context-packs
POST /api/context-packs
GET  /api/context-packs/<pack-id>
POST /api/context-packs/<pack-id>/apply-preview
POST /api/context-packs/<pack-id>/hide
POST /api/context-packs/<pack-id>/unhide
POST /api/context-packs/<pack-id>/delete
```

v1.9.0 intentionally does not add embeddings, vector databases, audio
fingerprinting, MP3 import, or automatic application of recommended context.

You can also use `MUSICFORGE_ACCESS_TOKEN`. When auth is enabled, Studio stores
the token only in `sessionStorage` and sends it as `Authorization: Bearer ...`.
`GET /api/info` remains public and reports whether auth is required; jobs,
provider, renderer, batch, artifacts, audio, delete, open-folder, and render
actions require Bearer auth.

The v0.1.2 panel adds single-job inspection and management:

- Timeline, Tracks, Validator, SongPlan JSON, Logs, and Artifacts tabs.
- `hide` / `unhide` for keeping old jobs out of the default list without
  deleting files.
- `cancel` for queued/running jobs and `delete` for non-running jobs, with run
  directory path checks before deletion.
- Startup recovery that marks leftover `queued` or `running` jobs as
  `interrupted` instead of showing them as active forever.

Runtime view APIs:

```text
GET /api/jobs/<job-id>/timeline
GET /api/jobs/<job-id>/tracks
GET /api/jobs/<job-id>/quality
GET /api/jobs/<job-id>/validator
POST /api/jobs/<job-id>/hide
POST /api/jobs/<job-id>/unhide
POST /api/jobs/<job-id>/cancel
POST /api/jobs/<job-id>/delete
```

## Music Quality Layer

v0.7.0 adds compatible quality metadata to `song-plan.json`. Existing plans
without this field still load and render, while new local and multinode runs add:

- primary motif metadata
- section role, energy, tension, density, transition, and hook markers
- hook section list
- structure, melody, harmony, arrangement, lyric-fit, and overall scores
- quality warnings and critic issues

Studio exposes this through the Quality tab. The Timeline tab also shows section
energy, tension, density, role, and hook markers so a generated song can be
checked as a musical structure, not only as MIDI data.

v0.7.1 keeps this layer backward compatible: old `song-plan.json` files without
`quality` are inferred in Runtime, Timeline, Validator, and Quality views without
rewriting the artifact.

## Batch Production

v0.4.0 adds local batch production to Studio. Batch metadata is stored under
`.musicforge/batches/<batch-id>/`, while every generated song still writes a
normal job run under `runs/<job-id>/`.

The Batch workspace can import CSV from a file or textarea, launch items with a
max concurrency from 1 to 4, pause queued work, resume, retry failed items,
export a JSON report, and open each linked job detail.

CSV columns:

```text
title,language,style,theme,duration_seconds,tempo_bpm,key,vocal_mode,lyrics,generation_mode,pipeline_mode
```

Required columns are `title`, `language`, `style`, and `theme`. Defaults are
`duration_seconds=180`, `vocal_mode=guide_melody`, `generation_mode=local`, and
`pipeline_mode=multinode`. Row-level `generation_mode` and `pipeline_mode`
values override the batch defaults.

Optional Project archival columns:

```text
project,version_name,version_note
```

When `project` is present, a completed batch item is automatically attached as a
Project version. Existing CSV files without those columns keep the old behavior.

Batch APIs:

```text
GET  /api/batches
GET  /api/batches/<batch-id>
POST /api/batches/import-csv
POST /api/batches/<batch-id>/launch
POST /api/batches/<batch-id>/pause
POST /api/batches/<batch-id>/resume
POST /api/batches/<batch-id>/retry-failed
GET  /api/batches/<batch-id>/export
POST /api/batches/<batch-id>/hide
POST /api/batches/<batch-id>/unhide
POST /api/batches/<batch-id>/delete
POST /api/batches/<batch-id>/open-folder
```

## Project Workspace

v0.9.0 adds Project workspace metadata for organizing multiple generated jobs
as versions of the same song. v1.0.0 extends this into a controlled creation
and delivery workflow: versions can branch from selected/final/any parent
version, quality gates can block low-scoring final candidates, and final export
bundles collect the approved artifacts for handoff. v1.2.0 rounds out the
workspace with reusable edit presets, A/B version comparison, safe Final Export
ZIP delivery, and Project list search/filter controls.

Project metadata lives under
`.musicforge/projects/<project-id>/` and does not copy or delete run artifacts:

```text
.musicforge/projects/<project-id>/project.json
.musicforge/projects/<project-id>/versions.json
.musicforge/projects/<project-id>/events.jsonl
.musicforge/projects/<project-id>/export.json
.musicforge/projects/<project-id>/quality-gate.json
.musicforge/projects/<project-id>/final-export/
.musicforge/projects/<project-id>/final-export.zip
.musicforge/edit-presets.json
```

A Project can hold several versions, each referencing one existing job/run.
Studio can create a Project, create a new version job from the current song
form, attach an existing job, mark selected/final versions, compare two
versions, and export a Project manifest. Deleting a Project removes only Project
metadata; job runs still use the normal Job delete flow.

Project versions now record lineage and release metadata:

- `parent_version_id`
- `variant_type`
- `change_summary`
- `quality_gate_status`
- `quality_gate_score`
- `final_export_path`

Variation creation reuses the parent version request and applies an explicit
patch for allowed request fields such as style, theme, tempo, key, duration, and
lyrics. The new child job can run in local or provider mode and single or
multinode pipeline mode.

v1.1.0 adds non-destructive local edit versions. Pick a completed Project
version, choose an edit type and target, and MusicForge creates a new child
version instead of modifying the parent run. The first local edit engine supports
section energy, section harmony, track density, lyrics rewrite, melody
variation, and light arrangement edits. Each edit job writes:

```text
runs/<job-id>/data/edit-metadata.json
runs/<job-id>/data/song-plan.json
runs/<job-id>/renders/song.mid
```

Edit metadata records the parent version/job, target, instruction, preserve
constraints, strength, summary, and warnings. Stems and audio are not inherited;
render them again for the edited version when needed.

v2.0.0 adds a Visual SongPlan Editor for Project versions. The Project Editor
tab can preview manual patches for section chords, lyrics, track instruments,
and note-level changes, then apply the preview as a new child version without
modifying the parent run.

v2.1.0 extends the Visual Editor with structure edits: add, duplicate, delete,
resize, and move sections; add, duplicate, delete, and rename tracks; and view
or clean up editor preview history. Section edits normalize `start_bar` values
and adjust affected notes deterministically. Applied editor previews are kept
for audit history and are not removed by preview cleanup.

v2.2.0 upgrades the Project Editor into an interactive arranger workspace.
Studio now shows an Arranger Timeline, track overview lanes, a current-track
Piano Roll, an Inspector, Patch Queue, Undo/Redo, and Draft Refresh. Draft
Refresh calls a nonpersistent draft API, so users can check patch results
without creating preview directories, runs, MIDI files, or project events.
Preview still creates an auditable editor preview, and Apply as Version still
creates a child Project Version without modifying the parent.

v2.6.0 adds an Audition Review Board. Editor auditions can be rated, marked as
keep/maybe/reject/needs_fix, favorited, tagged, annotated with beat markers, and
saved into the Creative Asset library. Review text is redacted before storage
and export, and saving an audition as an asset rebuilds note/chord content from
the audition SongPlan instead of copying temporary MIDI or WAV files.

v2.7.0 turns reviewed auditions into explicit next actions. From the Review
Board, users can preview a local review edit, create a non-destructive child
Project Version from review feedback, ask the configured provider for a review
edit preview, or turn a saved favorite audition asset into a Context Pack. Local
review edits map sanitized notes, status, rating, tags, and markers into
whitelisted `EditIntent` objects; review text is never executed as arbitrary
patch operations, and no version changes until the user triggers an action.

v2.8.0 adds the Review Workbench. A reviewed audition can become a persistent
Review Task, then generate local conservative, balanced, and bold candidates.
Each ReviewCandidate stores sanitized source metadata, strategy intents,
validator and quality summaries, ranking scores, MIDI previews, and optional WAV
previews. Applying a candidate creates one official child Project Version by
recomputing from the parent version plus candidate intents; cached candidate
SongPlan files are used for listening and inspection only. A task can then be
resolved, archived, or marked needs_more_work, which creates a linked follow-up
task with the applied child version as its parent. Project Compare, Project
Export, Final Export, and release-check include review task and selected
candidate provenance without copying candidate audio into deliverables.

v2.9.0 connects providers to the Review Workbench as candidate sources only.
Generate Provider Candidates asks the configured provider for constrained
ProviderEditPatch options with `provider-review-candidates`, then MusicForge
converts, validates, scores, ranks, and renders them locally just like other
ReviewCandidates. The Decision Report compares local and provider candidates,
records source/usage breakdowns and risk flags, and always requires a manual
Apply Candidate action. Provider candidates cannot auto-apply, cannot bypass
the stale/artifact guards, and cannot modify a Review Task that already applied
one candidate.

v3.0.0 adds Review Sprints for working through multiple Review Tasks together.
A sprint stores ordered task references, summaries, conflict reports, and event
history under the project without copying candidate artifacts or SongPlan data.
Studio's Review Sprints tab can create sprints, add/reorder tasks, refresh
conflicts, and batch-generate local or provider candidates. Batch generation is
still candidate creation only: applying changes remains a one-task, one-candidate
manual action through the existing Review Workbench safeguards. Project Compare,
Project Export, Final Export, provider usage, and release-check include sprint
provenance and sprint rollups.

v3.1.0 adds deterministic Review Sprint recommendations. A Sprint
Recommendation Report ranks included Review Tasks, explains the next action for
each task, and previews a Context Pack built from local Library assets and
references. The report is advisory only: recommendation APIs do not generate
candidates, apply candidates, resolve tasks, or close sprints. Users can
refresh recommendations, save a recommended Context Pack, and then explicitly
choose whether to generate local/provider candidates or manually apply a ready
candidate. Saved context packs reject hidden or stale source assets/references,
and Project Compare, Project Export, and Final Export include compact
recommendation summaries.

v3.2.0 adds Review Sprint Action Queues. A queue is created from the latest
Recommendation Report, stores per-task action items with safety labels, and can
run selected safe actions while recording an event stream. It can save
recommended Context Packs, generate task-scoped local/provider candidates, and
refresh Decision Reports, conflicts, or recommendations. Provider actions are
skipped unless explicitly allowed for that run, and manual actions such as
candidate apply, task resolve, and follow-up creation stay as `manual_required`
items. Queue execution rechecks stale tasks, changed Recommendation Reports, and
hidden/stale Context Pack sources before doing work. Project Compare, Project
Export, Final Export, and release-check include compact Action Queue summaries
and apply provenance.

v3.3.0 adds Review Sprint Dashboard metrics. Sprint metrics are derived reports,
not business state: refreshing them reads existing ReviewTasks, candidates,
Decision Reports, Recommendation Reports, Action Queues, provider usage, and
version quality metadata, then writes `metrics-report.json` and
`review-metrics.json` summaries. The Dashboard shows readiness, task status,
candidate funnel, recommendation adoption, queue execution, provider tokens,
manual decisions, quality delta, and warnings. Metrics refresh never applies a
candidate, resolves a task, closes a Sprint, creates a final export, or calls a
provider. Project Export and Final Export include only compact metrics
summaries, with token and local-path redaction.

v3.3.1 fixes the multi-Sprint Final Export metrics summary so the latest
Sprint ID/readiness, completion rate, quality delta, and warnings all come from
the same Sprint metrics snapshot.

v3.4.0 adds Provider Judge reports for ReviewTask candidates. A Judge Report
asks the configured provider to score existing ready candidates across review
fit, target precision, musicality, novelty, risk, and confidence, then stores a
strictly validated `judge-report.json` plus provider usage. Judge is advisory:
it does not create candidates, apply candidates, resolve tasks, close sprints,
or override the local Decision Report recommendation. Decision Reports,
candidate apply metadata, Sprint judge summaries, Metrics Dashboard, Project
Compare, Project Export, Final Export, and release-check now carry compact
judge summaries. Action Queue `refresh_judge_report` items are `provider_safe`
and are skipped unless provider actions are explicitly allowed for that run.

v3.4.1 tightens Judge Report audit summaries. Multi-Sprint Final Export now
selects the latest Sprint judge summary using the Project metrics latest Sprint
ID, and Project Export / Sprint Metrics re-check Judge Report stale state before
surfacing summaries. Applying a candidate does not by itself stale a Judge
Report; candidate content, parent plan, or prompt template changes still do.

v3.5.0 adds Review Sprint Closeout and Signoff. A Closeout Report reads current
ReviewTasks, candidates, conflicts, recommendations, Action Queues, Judge
summaries, Metrics, and project version state, then writes a local gate report
with blockers, warnings, readiness, and a recommended final version. Closing a
Sprint now passes through this gate by default. Failed gates return 409 unless
the user explicitly force-closes with an override reason, which writes a
separate `signoff.json` audit record. Closeout never applies candidates,
resolves tasks, calls a provider, closes automatically, or creates final export
artifacts. Studio, Project Export, Final Export, Project Metrics, and
release-check include compact closeout/signoff summaries with token and path
redaction.

v3.5.1 tightens the Closeout delivery gate. The recommended final version can
come only from a Sprint-applied candidate, an explicit final version, or an
explicit selected version. The project `latest_version_id` is not enough to
prove delivery readiness, so resolved tasks without applied/selected/final
version evidence still fail normal close.

v3.6.0 adds a project-level Delivery QA and Handoff layer. Delivery QA reads the
current project final version, Final Export manifest, actual final-export files,
the built ZIP, Review Sprint closeout/signoff summaries, and quality gate
metadata, then writes `delivery-qa.json` with blocking checks, warnings,
artifact hashes, ZIP integrity, and handoff readiness. Delivery Signoff writes a
separate `delivery-signoff.json`; failed QA cannot be signed normally, force
sign requires an override reason, duplicate signing is rejected until reset, and
reset writes `delivery-signoff-history.jsonl`. Delivery QA never rebuilds export
artifacts, calls providers, changes project final version, uploads files, or
auto-signs anything.

v3.6.1 hardens Delivery QA against polluted Final Export manifests. Required
handoff artifacts are checked from a built-in baseline, so removing `song.mid`
or `song-plan.json` from `manifest.files` cannot hide a missing file. Final
Export ZIP metadata also omits local absolute paths, and Delivery QA scans the
raw manifest before sanitizing its report.

Edit presets can be applied from Studio's Project Edit tab. Built-in presets
cover common edits such as lifting the final chorus, simplifying verse bass,
brightening chorus harmony, and rewriting a chorus hook. User presets are stored
locally in `.musicforge/edit-presets.json`, which is ignored by Git. Presets
store only generic edit intent defaults, not project IDs, version IDs, job IDs,
tokens, or local file paths. Section harmony presets are validated against the
supported local MIDI chord set before they can be saved or applied.

v1.3.0 adds provider-backed edit previews. In Studio, choose Provider mode in
the Project Edit tab, write a natural-language instruction, then Generate
Preview. The provider returns a constrained edit patch only; MusicForge applies
that patch locally, validates the resulting SongPlan, and stores preview files
under:

```text
.musicforge/projects/<project-id>/edit-previews/<preview-id>/
  preview.json
  patch.json
  candidate-song-plan.json
  validator-report.json
  quality.json
```

Apply Preview creates the official child Project version. Preview alone does
not modify the parent version, selected version, final version, or version
list. Provider usage records are written to `runs/<job-id>/data/provider-usage.json`
after apply; they contain model, operation, template, status, request id, and
token counts when the provider returns usage data, but no API key or raw
credential.

v1.4.0 adds Provider Edit Candidate Groups. In the Project Candidates tab,
choose a parent version, set Candidate Count from 2 to 5, and Generate
Candidates. MusicForge stores each provider patch candidate under the Project,
applies it locally to a candidate SongPlan, validates it, scores it, and ranks
the ready candidates. Candidate groups do not create official Project versions
until one candidate is applied.

```text
.musicforge/projects/<project-id>/candidate-groups/<group-id>/
  group.json
  provider-usage.json
  candidates/
    cand-001/
      candidate.json
      patch.json
      candidate-song-plan.json
      song.mid
      song.wav
      render-report.json
      audio-render-report.json
      validator-report.json
      quality.json
      critic.json
```

Candidate groups are bound to the parent `song-plan.json` source hash. If the
parent changes after candidate generation, applying the group is rejected as
stale, and candidate MIDI/WAV download or re-render endpoints return `409`
instead of serving old audition files. Applying a candidate creates one official child Project version; the
remaining candidates stay as review artifacts and are not added to the version
list. Candidate MIDI previews are generated for ready candidates; WAV previews
can be rendered when `.musicforge/renderer.json` is configured.

Provider usage reports aggregate version jobs and candidate group generation by
model, operation, and prompt template. Reports never include API keys or raw
prompts. Optional local pricing can be placed in
`.musicforge/provider-pricing.json`, which is ignored by Git:

```json
{
  "schema_version": 1,
  "models": {
    "mock-main": {
      "input_per_1m": 0.0,
      "output_per_1m": 0.0,
      "currency": "USD"
    }
  }
}
```

Prompt A/B in the Candidates tab runs the same instruction through two prompt
templates and creates two candidate groups. It does not auto-apply a candidate;
the user still reviews, listens, and applies manually.

Prompt templates are managed from Studio's Prompt Templates panel and stored in
`.musicforge/prompt-templates.json`, which is ignored by Git. Built-in provider
edit templates can be overridden locally and reset. Templates are validated for
size and local absolute path leakage before saving.

## Creative Assets

v1.6.0 adds a local Creative Asset Library for reusable motifs, chord
progressions, drum patterns, bass patterns, section templates, arrangement
templates, and lyric hooks. Assets are stored as independent local snapshots:

```text
.musicforge/assets/<asset-id>/
  asset.json
  source-fragment.json
  preview.mid
  preview.wav
  events.jsonl
```

Studio can extract assets from a completed job, a Project version, or a provider
candidate. The Assets workspace supports search, type/tag/favorite filters,
metadata edits, hide/unhide, favorite, delete, MIDI preview rendering, and WAV
preview rendering when the local renderer is configured.

Asset references can be attached to new jobs, Project versions, variations,
local/provider edits, provider previews, candidate groups, and Prompt A/B. Each
run that uses assets writes a compact snapshot:

```text
runs/<job-id>/data/asset-refs.json
```

The snapshot records asset id, type, name, role, strength, source summary, and
content summary. Full notes and source fragments remain in `.musicforge/assets/`
instead of being copied into every job. Hidden assets cannot be used as
references.

Provider prompts receive only sanitized asset summaries. Project export and
Final Export include asset reference summaries for traceability, but do not copy
asset preview WAV files, API keys, raw provider responses, or local config
files.

Creative Asset APIs:

```text
GET  /api/assets
POST /api/assets
GET  /api/assets/<asset-id>
POST /api/assets/<asset-id>
POST /api/assets/<asset-id>/hide
POST /api/assets/<asset-id>/unhide
POST /api/assets/<asset-id>/favorite
POST /api/assets/<asset-id>/unfavorite
POST /api/assets/<asset-id>/delete
POST /api/assets/<asset-id>/render-midi
POST /api/assets/<asset-id>/render-audio
GET  /api/assets/<asset-id>/midi
GET  /api/assets/<asset-id>/audio
POST /api/assets/extract/from-job
POST /api/assets/extract/from-project-version
POST /api/assets/extract/from-candidate
```

## Reference Materials

v1.7.0 adds a local Reference Library for safely importing external materials
before they are reused in generation or editing. References are stored under
`.musicforge/references/` and are ignored by Git:

```text
.musicforge/references/<reference-id>/
  reference.json
  original/reference.wav
  original/reference.mid
  original/reference.txt
  original/reference.md
  events.jsonl
```

Supported v1.7.0 reference types are `audio_wav`, `midi`, `lyrics_text`, and
`style_note`. Import uses JSON plus base64 content, validates extension and
file headers, rejects path-like filenames, rejects MP3 and unsupported formats,
and deduplicates identical content by SHA-256. Automated tests use synthetic
fixtures only; do not put real reference material into tests.

References can be linked to Projects and attached as `reference_refs` to new
jobs, Project versions, variations, local/provider edits, provider previews,
candidate groups, and Prompt A/B. Each run that uses references writes:

```text
runs/<job-id>/data/reference-refs.json
```

Provider prompts receive only sanitized metadata summaries. Project export and
Final Export include reference summaries for traceability, but Final Export
does not copy original imported reference files into delivery bundles or ZIPs.
v1.7.0 intentionally does not do audio transcription, audio-to-MIDI, MP3
import, waveform analysis, BPM detection, or key detection.

Reference APIs:

```text
GET  /api/references
POST /api/references/import
GET  /api/references/<reference-id>
POST /api/references/<reference-id>
GET  /api/references/<reference-id>/file
POST /api/references/<reference-id>/hide
POST /api/references/<reference-id>/unhide
POST /api/references/<reference-id>/favorite
POST /api/references/<reference-id>/unfavorite
POST /api/references/<reference-id>/delete
POST /api/references/<reference-id>/link-project
POST /api/references/<reference-id>/unlink-project
POST /api/references/<reference-id>/create-asset
GET  /api/projects/<project-id>/references
POST /api/projects/<project-id>/references/link
POST /api/projects/<project-id>/references/unlink
```

Quality Gate is stored per Project. Defaults require the generated `SongPlan`
to meet baseline quality scores, but do not require WAV or stems because local
audio rendering depends on user renderer setup. Setting final evaluates the gate
and rejects failed versions unless `force=true` is used; force overrides are
recorded in Project events.

Final Export writes a directory bundle under the Project:

```text
.musicforge/projects/<project-id>/final-export/
  manifest.json
  README.txt
  project-export.json
  song-plan.json
  run-summary.json
  validator-report.json
  quality-report.json
  song.mid
  song.wav
  assets/
    asset-001.json
  stems/
```

The bundle copies only files from the selected version's run directory. Stale
stem manifests are detected by source hash and skipped instead of copying old
track material.

Final Export ZIP builds `.musicforge/projects/<project-id>/final-export.zip`
from the existing `final-export/` directory. ZIP entries are relative paths
only; symlinks, `..`, absolute paths, and files outside the final-export
directory are rejected or skipped. The manifest records ZIP size, sha256, and
entry count for handoff checks.

The Compare tab uses the Project Compare API to show A/B quality, gate status,
edit preset metadata, changed sections, changed tracks, MIDI links, and WAV
players when audio exists. The recommendation field is deterministic guidance
only; it never changes selected or final versions.

Project APIs:

```text
GET  /api/projects?q=<text>&status=<status>&variant_type=<type>&hidden=false&include_hidden=false
POST /api/projects
GET  /api/projects/<project-id>
POST /api/projects/<project-id>/versions
POST /api/projects/<project-id>/versions/from-job
POST /api/projects/<project-id>/versions/<version-id>/variation
POST /api/projects/<project-id>/versions/<version-id>/edit
GET  /api/projects/<project-id>/versions/<version-id>/edit
GET  /api/projects/<project-id>/versions/<version-id>/edit-targets
GET  /api/projects/<project-id>/versions/<version-id>/editor-state
GET  /api/projects/<project-id>/versions/<version-id>/editor-view
POST /api/projects/<project-id>/versions/<version-id>/editor-draft
POST /api/projects/<project-id>/versions/<version-id>/editor-preview
GET  /api/projects/<project-id>/editor-previews
GET  /api/projects/<project-id>/editor-previews/<preview-id>
GET  /api/projects/<project-id>/editor-previews/<preview-id>/patch
GET  /api/projects/<project-id>/editor-previews/<preview-id>/song-plan
GET  /api/projects/<project-id>/editor-previews/<preview-id>/midi
POST /api/projects/<project-id>/editor-previews/<preview-id>/apply
GET  /api/projects/<project-id>/audition-reviews
GET  /api/projects/<project-id>/editor-previews/<preview-id>/audition-reviews
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/review
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/markers
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/markers/<marker-id>
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/markers/<marker-id>/delete
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/create-asset
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/review-edit-preview
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/review-edit
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/provider-review-edit-preview
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/create-context-pack
POST /api/projects/<project-id>/editor-previews/<preview-id>/auditions/<audition-id>/review-task
GET  /api/projects/<project-id>/review-tasks
GET  /api/projects/<project-id>/review-tasks/<task-id>
POST /api/projects/<project-id>/review-tasks/<task-id>/candidates
POST /api/projects/<project-id>/review-tasks/<task-id>/resolve
POST /api/projects/<project-id>/review-tasks/<task-id>/needs-more-work
POST /api/projects/<project-id>/review-tasks/<task-id>/archive
GET  /api/projects/<project-id>/review-tasks/<task-id>/candidates/<candidate-id>/midi
GET  /api/projects/<project-id>/review-tasks/<task-id>/candidates/<candidate-id>/audio
POST /api/projects/<project-id>/review-tasks/<task-id>/candidates/<candidate-id>/render-midi
POST /api/projects/<project-id>/review-tasks/<task-id>/candidates/<candidate-id>/render-audio
POST /api/projects/<project-id>/review-tasks/<task-id>/candidates/<candidate-id>/apply
POST /api/projects/<project-id>/versions/<version-id>/edit-preview
POST /api/projects/<project-id>/versions/<version-id>/edit-preview/<preview-id>/apply
POST /api/projects/<project-id>/versions/<version-id>/edit-preview/<preview-id>/delete
POST /api/projects/<project-id>/versions/<version-id>/edit-candidates
POST /api/projects/<project-id>/versions/<version-id>/edit-candidates/ab
GET  /api/projects/<project-id>/candidate-groups
GET  /api/projects/<project-id>/candidate-groups/<group-id>
POST /api/projects/<project-id>/candidate-groups/<group-id>/apply
POST /api/projects/<project-id>/candidate-groups/<group-id>/delete
POST /api/projects/<project-id>/candidate-groups/<group-id>/render-midi
POST /api/projects/<project-id>/candidate-groups/<group-id>/render-audio
GET  /api/projects/<project-id>/candidate-groups/<group-id>/usage
GET  /api/projects/<project-id>/candidate-groups/<group-id>/candidates/<candidate-id>/midi
GET  /api/projects/<project-id>/candidate-groups/<group-id>/candidates/<candidate-id>/audio
POST /api/projects/<project-id>/candidate-groups/<group-id>/candidates/<candidate-id>/render-midi
POST /api/projects/<project-id>/candidate-groups/<group-id>/candidates/<candidate-id>/render-audio
GET  /api/projects/<project-id>/prompt-ab
GET  /api/projects/<project-id>/prompt-ab/<ab-id>
POST /api/projects/<project-id>/prompt-ab/<ab-id>/delete
POST /api/projects/<project-id>/versions/<version-id>/evaluate
POST /api/projects/<project-id>/selected
POST /api/projects/<project-id>/final
GET  /api/projects/<project-id>/quality-gate
POST /api/projects/<project-id>/quality-gate
POST /api/projects/<project-id>/quality-gate/evaluate-all
GET  /api/projects/<project-id>/final-export
POST /api/projects/<project-id>/final-export
POST /api/projects/<project-id>/final-export/zip
GET  /api/projects/<project-id>/final-export.zip
GET  /api/projects/<project-id>/diff?left=v001&right=v002
GET  /api/projects/<project-id>/compare?left=v001&right=v002
GET  /api/projects/<project-id>/provider-usage
GET  /api/projects/<project-id>/usage/provider
GET  /api/projects/<project-id>/export
GET  /api/projects/<project-id>/events
POST /api/projects/<project-id>/hide
POST /api/projects/<project-id>/unhide
POST /api/projects/<project-id>/delete
GET  /api/jobs/<job-id>/edit
GET  /api/usage/provider
GET  /api/edit-presets
POST /api/edit-presets
GET  /api/edit-presets/<preset-id>
POST /api/edit-presets/<preset-id>
POST /api/edit-presets/<preset-id>/delete
POST /api/edit-presets/reset
GET  /api/prompt-templates
GET  /api/prompt-templates/<template-id>
POST /api/prompt-templates/<template-id>
POST /api/prompt-templates/<template-id>/reset
POST /api/prompt-templates/reset
GET  /api/jobs/<job-id>/provider-usage
```

## Multi-node Pipeline

v0.3.0 adds a selectable multinode backend for inspecting each planning stage
before MIDI rendering. It keeps `single` as the default for backward
compatibility, while `multinode` writes structured node records under
`runs/<job-id>/data/nodes/`.

First-pass node order:

```text
brief_planner
style_planner
structure_planner
lyric_planner
harmony_planner
melody_planner
arrangement_planner
critic
repair
song_plan_builder
```

Node APIs:

```text
GET  /api/jobs/<job-id>/nodes
GET  /api/jobs/<job-id>/nodes/<node-name>
GET  /api/jobs/<job-id>/nodes/<node-name>/dependencies
POST /api/jobs/<job-id>/nodes/<node-name>/retry
```

v0.3.1 adds node-level retry for multinode jobs. Retrying a node invalidates
that node plus downstream nodes, reuses completed upstream node outputs, then
rewrites the final SongPlan, MIDI, validator report, summary, and job state.
Studio exposes this through the Nodes tab with a downstream-node confirmation.
As of v0.3.2, node retry runs in the background and the API returns `202
Accepted`; Studio polls job state until the retry completes.

## Provider Mode

v0.2.0 adds optional provider-backed `SongPlan` generation while keeping local
deterministic generation as the default.

Provider settings are stored locally in `.musicforge/provider.json`, which is
ignored by Git. API keys are never returned by the HTTP API, job state, or
provider snapshot except as a masked value.

Provider APIs:

```text
GET  /api/provider
POST /api/provider
POST /api/provider/reset
POST /api/provider/test
```

Supported first-pass provider wires:

- `mock`: local test provider with no network access.
- `openai_chat_completions`: OpenAI-compatible `/chat/completions` wire format.

The Studio form can save, reset, and test provider settings. Song jobs can run
in `local` or `provider` mode. Provider mode validates model output through
`SongPlan.from_dict()` and the same MIDI-safe validator before rendering.

## Job Controls

v0.2.1 adds task control and running protection for the local Studio:

- queued jobs can be cancelled before they start.
- running jobs accept cancel requests and stop at pipeline stage boundaries.
- failed, stalled, and interrupted jobs can be retried from the original input.
- retry appends events, increments retry metadata, and keeps provider snapshots masked.
- running jobs write `heartbeat_at`; stale running jobs are marked `stalled` by a watchdog.
- Studio job details show attempt count, retry count, heartbeat, and stalled state.

Local setup checks:

```powershell
python -m song_agent.cli doctor
python -m song_agent.cli doctor --provider-test
python -m song_agent.cli release-check
```

## Audio Rendering

v0.5.0 adds optional local WAV rendering for completed jobs:

```text
runs/<job-id>/renders/song.mid -> runs/<job-id>/renders/song.wav
```

The first renderer backend is FluidSynth with a local SoundFont. MIDI generation
does not require renderer configuration, and audio render failures do not change
a completed job into a failed job.

Renderer settings are stored in `.musicforge/renderer.json`, which is ignored by
Git. The Studio Renderer Settings form can save, reset, and test:

- renderer type: `fluidsynth`
- FluidSynth executable path
- SoundFont path (`.sf2` or `.sf3`)
- sample rate
- gain

Environment overrides:

```text
MUSICFORGE_RENDERER_TYPE
MUSICFORGE_FLUIDSYNTH_PATH
MUSICFORGE_SOUNDFONT_PATH
MUSICFORGE_AUDIO_SAMPLE_RATE
MUSICFORGE_AUDIO_GAIN
```

v5.0 also adds local renderer profiles under `.musicforge/audio-profiles/`.
Public profile summaries redact engine and SoundFont paths and expose only
hashes and render settings:

```powershell
python -m song_agent.cli audio-profile list
python -m song_agent.cli audio-profile create --name "Local FluidSynth" --engine fluidsynth --soundfont D:\sf2\gm.sf2
python -m song_agent.cli audio-profile test arp-000001
python -m song_agent.cli audio-profile set-default arp-000001
```

Renderer APIs:

```text
GET  /api/renderer
POST /api/renderer
POST /api/renderer/reset
POST /api/renderer/test
GET  /api/audio/profiles
POST /api/audio/profiles
POST /api/audio/profiles/<profile-id>/test
POST /api/jobs/<job-id>/render-audio
GET  /api/jobs/<job-id>/audio
```

In Studio, open a completed job and click `Render Audio`. When `song.wav`
exists, the job detail shows a browser audio player and a WAV download link.
For a standalone WAV check, run:

```powershell
python -m song_agent.cli audio-health runs\demo\renders\song.wav --json
```

## Stem Export

v0.8.0 adds per-track stem export for the tracks already present in
`song-plan.json`:

```text
runs/<job-id>/stems/manifest.json
runs/<job-id>/stems/midi/<stem-id>.mid
runs/<job-id>/stems/audio/<stem-id>.wav
```

The first pass renders one MIDI stem per SongPlan track. If a local FluidSynth
renderer is configured, each stem MIDI can also be rendered to a WAV stem.
Studio exposes this through the Stems tab with per-track download links, audio
players, and simple Solo/Mute controls.

Stem manifests are bound to the current `data/song-plan.json` by a source hash.
If a job retry, node retry, or direct SongPlan rewrite changes the source plan,
old stem artifacts are invalidated before they can be reused or downloaded.

Stem APIs:

```text
GET  /api/jobs/<job-id>/stems
POST /api/jobs/<job-id>/render-stems
POST /api/jobs/<job-id>/render-stem-audio
GET  /api/jobs/<job-id>/stems/<stem-id>/midi
GET  /api/jobs/<job-id>/stems/<stem-id>/audio
POST /api/batches/<batch-id>/render-stems
POST /api/batches/<batch-id>/render-stem-audio
POST /api/batches/<batch-id>/render-failed-stems
POST /api/batches/<batch-id>/render-failed-stem-audio
```

Stem downloads are resolved through `manifest.json`; request path segments are
not used as arbitrary file paths. Batch export includes stem status, manifest
path, stem count, completed stem-audio count, and stem error fields.

## Initial Direction

- Agent core: Python
- Control surface: CLI first, web console second
- LLM providers: OpenAI-compatible API first, then Anthropic/Qwen/DeepSeek
- Music interchange: structured JSON + MIDI/MusicXML
- Renderer target: MIDI first, then MuseScore/FluidSynth/REAPER adapters

## Project Layout

```text
song_agent/
  agent/        Fixed and multinode songwriting workflows
  providers/    LLM provider adapters
  renderers/    MIDI/audio render backends
  schemas/      Song data contracts
  prompts/      Prompt templates
docs/
  ARCHITECTURE.md
  MVP_PLAN.md
examples/
  song_request.json
```
