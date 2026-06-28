# MusicForge

MusicForge is a local-first songwriting, review, release, and trust-operations
workbench. It does not wrap a closed music generator. The core path is:

1. Plan lyrics, structure, harmony, melody, arrangement, and review work.
2. Emit open musical artifacts such as JSON, MIDI, MusicXML, ABC, and package
   manifests.
3. Render and verify locally controlled audio and evidence packages.
4. Keep release, distribution, submission, operations, and public trust evidence
   auditable through deterministic local verifiers.

## Quick Start

```powershell
git clone https://github.com/goodgoodstudyboy/musicforge.git
cd musicforge
python -m pip install -e .[dev]
python -m song_agent.cli doctor
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787` and use Studio to create a song, inspect projects,
run acceptance checks, assemble releases, and review system health.

Generate a local deterministic MIDI demo:

```powershell
python -m song_agent.cli examples\song_request.json --out runs\quickstart --force
```

The default generation path is model-optional and can run without network
provider access. Real WAV output requires a local renderer profile and
SoundFont. Provider-assisted review and generation require a local provider
configuration.

## Studio Panel

The browser panel runs locally and uses the same deterministic pipeline as the
CLI:

```powershell
python -m song_agent.cli serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`, fill in a song request, and start a job. Completed
jobs write `job-state.json`, `song-plan.json`, `events.jsonl`, and `song.mid`
under `runs/<job-id>/`.

The System Health panel shows GA readiness, doctor status, manual acceptance
status, and final readiness status. It can run `ga-check` through `/api/ga/check`
and show the required GA documentation index.

The Maintenance panel shows LTS status, backups, migration state, and periodic
maintenance checks. It can create a verified local workspace backup, run upgrade
preflight, run migrations, and launch weekly maintenance checks through
`/api/maintenance/*`.

## Generate / Edit / Review / Release

MusicForge covers the full local workflow: generate Project versions, edit and
compare versions, create review tasks, run Acceptance and Human Review flows,
assemble Release and Distribution packages, track Submission evidence, and
build Trust Operations evidence through final handoff.

## GA Validation

Use these commands before treating a branch as releasable:

```powershell
python -m song_agent.cli doctor
python -m song_agent.cli release-check --profile ga --skip-tests --json
python -m song_agent.cli ga-check --json
```

`--auto-review` is synthetic smoke evidence only. Manual music acceptance means
a person played the MIDI or WAV and recorded a manual review.

## Audio Lab

Use Audio Lab when you need to prove the generated music can be rendered,
played, reviewed, and routed into repair work:

```powershell
python -m song_agent.cli audio-lab status --json
python -m song_agent.cli audio-lab detect --json
python -m song_agent.cli audio-lab test-profile --profile default --json
python -m song_agent.cli audio-lab smoke --cases 1 --render-audio never --json
python -m song_agent.cli audio-lab session create --from-smoke alsm-000001 --json
python -m song_agent.cli audio-lab session review als-000001 item-001 --result accepted --rating 4 --reviewer "Developer" --role "developer" --playback-confirmed --json
```

Real WAV checks require a local renderer profile and SoundFont. SoundFont files
and renderer paths stay in local `.musicforge/` configuration and must not be
committed. `--render-audio never` is MIDI-only smoke evidence; it is not real
audio acceptance. Automated tests may use a `test_fake` WAV writer, and reports
mark that runner as not release-ready. Manual Audio Lab reviews require a current
WAV hash, `playback_confirmed=true`, and reviewer name/role.

## Audio Fix Sprints

Audio Fix Sprints turn Audio Lab `needs_fix` or `rejected` markers into a
manual repair loop:

```powershell
python -m song_agent.cli audio-fix-sprint create --from-session als-000001 --json
python -m song_agent.cli audio-fix-sprint create-drafts afs-000001 --draft-type mix_patch --json
python -m song_agent.cli audio-fix-sprint generate-candidates afs-000001 --json
python -m song_agent.cli audio-fix-sprint review-candidate afs-000001 afi-000001 afc-000001 --preferred right --rating 4 --reviewer "Developer" --role developer --playback-confirmed --json
python -m song_agent.cli audio-fix-sprint select-candidate afs-000001 afi-000001 afc-000001 --json
python -m song_agent.cli audio-fix-sprint create-recheck-session afs-000001 --json
python -m song_agent.cli audio-fix-sprint review-recheck afs-000001 item-001 --result accepted --rating 4 --reviewer "Developer" --role developer --playback-confirmed --json
python -m song_agent.cli audio-fix-sprint closeout afs-000001 --json
python -m song_agent.cli audio-fix-sprint close afs-000001 --closed-by "Developer" --json
```

The sprint never auto-applies a candidate. A candidate must have manual A/B
review, be selected explicitly, and then pass a manual recheck before close.
Stale Audio Lab sources or stale candidate artifacts block progress. Test fake
or copied test WAV evidence cannot close a sprint as release-ready.

## Audio Campaigns

Audio Campaigns batch Audio Lab sessions into a release-candidate listening
gate. They require current release-ready WAV evidence, manual playback-confirmed
reviews, closed Audio Fix Sprints for `needs_fix` or high markers, and explicit
signoff before the package verifies as ready:

```powershell
python -m song_agent.cli audio-campaign create --from-session als-000001 --json
python -m song_agent.cli audio-campaign create-fix-sprints acmp-000001 --json
python -m song_agent.cli audio-campaign report acmp-000001 --json
python -m song_agent.cli audio-campaign signoff acmp-000001 --signed-by "Developer" --role developer --json
python -m song_agent.cli audio-campaign zip acmp-000001 --json
python -m song_agent.cli verify-audio-campaign-package .musicforge\audio-campaigns\acmp-000001\audio-campaign.zip --require-real-audio --require-manual-review --require-fix-sprints-closed --require-signed --json
```

`test_fake` WAVs and synthetic reviews are blocked by default. Use this as the
batch music-readiness gate after Audio Lab listening and Audio Fix Sprint
rechecks are complete. After signoff, the campaign report, case index, and
source hash are treated as immutable evidence; refresh/export/ZIP paths refuse
to rewrite or package a signed campaign if those bindings no longer match.

Audio Campaign Governance binds signed campaign evidence into GA and Release
readiness. A signed campaign can generate governance, analytics, immutable
archive, and offline verification evidence. Rebuilding an archive for the same
signoff is blocked; reset requires an approved single-use Change Request:

```powershell
python -m song_agent.cli audio-campaign governance acmp-000001 --json
python -m song_agent.cli audio-campaign analytics acmp-000001 --json
python -m song_agent.cli audio-campaign archive-zip acmp-000001 --json
python -m song_agent.cli audio-campaign verify-archive acmp-000001 --json
python -m song_agent.cli verify-audio-campaign-archive-package .musicforge\audio-campaigns\acmp-000001\archive\audio-campaign-archive.zip --require-signed --require-verification-passed --json
python -m song_agent.cli ga-check --require-audio-campaign acmp-000001 --audio-campaign-archive .musicforge\audio-campaigns\acmp-000001\archive\audio-campaign-archive.zip --audio-campaign-archive-verification-report .musicforge\audio-campaigns\acmp-000001\archive\audio-campaign-archive-verification-report.json --json
```

Release-driven Audio Campaign planning can create the correctly bound Audio Lab
session and Campaign directly from a Release, using each track's project id,
version id, and final-export hash:

```powershell
python -m song_agent.cli audio-campaign plan-release rel-000001 --json
python -m song_agent.cli audio-campaign preflight-release rel-000001 --json
python -m song_agent.cli audio-campaign create-from-release rel-000001 --name "Release RC Listening" --json
python -m song_agent.cli audio-campaign release-status rel-000001 --json
```

The planner refuses missing WAV/final-export evidence and rejects unrelated
Campaigns whose cases do not cover the current Release track identities.

Release Audio Campaign remediation closes the loop when a release-bound Campaign
contains `needs_fix`, `rejected`, or high/critical marker cases. Safe actions can
create Fix Sprints, drafts, candidates, recheck sessions, and closeout refreshes;
manual A/B review, candidate selection, and manual recheck remain human steps:

```powershell
python -m song_agent.cli audio-campaign remediation-plan rel-000001 --json
python -m song_agent.cli audio-campaign remediation-run-safe rel-000001 --json
python -m song_agent.cli audio-campaign remediation-closeout rel-000001 --json
python -m song_agent.cli audio-campaign remediation-signoff rel-000001 --signed-by "QA" --role developer --json
python -m song_agent.cli audio-campaign remediation-zip rel-000001 --json
python -m song_agent.cli audio-campaign remediation-verify rel-000001 --strict --require-passed --require-signed --json
python -m song_agent.cli verify-audio-campaign-remediation-package .musicforge\releases\rel-000001\audio-campaign-remediation\audio-campaign-remediation.zip --strict --require-passed --require-signed --json
```

Release signoff can require remediation closeout with
`require_audio_campaign_remediation=true`; this gate is a hard block and cannot be
bypassed with `force=true` while unresolved or stale remediation remains.

Release Audio Certification is the release-level audio gate. It aggregates the
current Release track Final Export hashes, real WAV evidence, manual accepted
Audio Campaign reviews, Campaign Governance, and required remediation evidence
into a signed fixed-structure ZIP that GA readiness and Release signoff can
require:

```powershell
python -m song_agent.cli release-audio-certification refresh rel-000001 --json
python -m song_agent.cli release-audio-certification signoff rel-000001 --signed-by "Developer" --role developer --json
python -m song_agent.cli release-audio-certification zip rel-000001 --json
python -m song_agent.cli release-audio-certification verify rel-000001 --strict --require-passed --require-signed --require-real-audio --require-manual-review --require-remediation-when-needed --json
python -m song_agent.cli verify-release-audio-certification-package .musicforge\releases\rel-000001\audio-certification\release-audio-certification.zip --strict --require-passed --require-signed --require-real-audio --require-manual-review --require-remediation-when-needed --json
python -m song_agent.cli ga-check --require-release-audio-certification --release-audio-certification .musicforge\releases\rel-000001\audio-certification\release-audio-certification.zip --release-audio-certification-verification-report .musicforge\releases\rel-000001\audio-certification\verification-report.json --json
```

Signed certification evidence is immutable. If any current Release track Final
Export manifest, campaign case binding, manual review, governance archive, or
remediation evidence drifts after signoff, gate/export/ZIP/verify paths hard
block until certification is refreshed and signed again.

Release Audio Timeline turns the signed certification chain into a track-level
event ledger, quality trend, issue taxonomy, risk register, and fixed-layout
offline verification package. It does not embed audio files; it binds the
current Release Audio Certification ZIP and verification report:

```powershell
python -m song_agent.cli release-audio-timeline refresh rel-000001 --json
python -m song_agent.cli release-audio-timeline signoff rel-000001 --signed-by "Developer" --role developer --json
python -m song_agent.cli release-audio-timeline zip rel-000001 --json
python -m song_agent.cli release-audio-timeline verify rel-000001 --strict --require-passed --require-signed --require-real-audio --require-manual-review --require-current-certification --json
python -m song_agent.cli verify-release-audio-timeline-package .musicforge\releases\rel-000001\audio-timelines\ratl-000001\release-audio-timeline.zip --strict --require-passed --require-signed --require-real-audio --require-manual-review --require-current-certification --release-audio-certification .musicforge\releases\rel-000001\audio-certification\release-audio-certification.zip --release-audio-certification-verification-report .musicforge\releases\rel-000001\audio-certification\verification-report.json --json
python -m song_agent.cli ga-check --require-release-audio-timeline --release-audio-timeline .musicforge\releases\rel-000001\audio-timelines\ratl-000001\release-audio-timeline.zip --release-audio-timeline-verification-report .musicforge\releases\rel-000001\audio-timelines\ratl-000001\verification-report.json --json
```

Release signoff can require `require_release_audio_timeline=true` and
`require_release_audio_timeline_signed=true`. Signed timelines are immutable;
stale Final Export or Certification evidence blocks gate/export/ZIP/verify.

Release Audio Regression Guard compares a baseline signed Timeline/Certification
chain against the current signed Timeline/Certification chain. The verifier
rebuilds normalized facts from those external packages; it does not trust the
Regression ZIP's internal JSON summaries alone:

```powershell
python -m song_agent.cli release-audio-regression configure rel-000002 --baseline-release-id rel-000001 --baseline-timeline .musicforge\releases\rel-000001\audio-timelines\ratl-000001\release-audio-timeline.zip --baseline-timeline-verification-report .musicforge\releases\rel-000001\audio-timelines\ratl-000001\verification-report.json --baseline-certification .musicforge\releases\rel-000001\audio-certification\release-audio-certification.zip --baseline-certification-verification-report .musicforge\releases\rel-000001\audio-certification\verification-report.json --json
python -m song_agent.cli release-audio-regression refresh rel-000002 --json
python -m song_agent.cli release-audio-regression signoff rel-000002 --signed-by "Developer" --role developer --json
python -m song_agent.cli release-audio-regression zip rel-000002 --json
python -m song_agent.cli release-audio-regression verify rel-000002 --strict --require-passed --require-signed --require-current --require-baseline-current --json
python -m song_agent.cli verify-release-audio-regression-package .musicforge\releases\rel-000002\audio-regression\release-audio-regression.zip --strict --require-passed --require-signed --require-current --require-baseline-current --baseline-timeline .musicforge\releases\rel-000001\audio-timelines\ratl-000001\release-audio-timeline.zip --baseline-timeline-verification-report .musicforge\releases\rel-000001\audio-timelines\ratl-000001\verification-report.json --baseline-certification .musicforge\releases\rel-000001\audio-certification\release-audio-certification.zip --baseline-certification-verification-report .musicforge\releases\rel-000001\audio-certification\verification-report.json --current-timeline .musicforge\releases\rel-000002\audio-timelines\ratl-000001\release-audio-timeline.zip --current-timeline-verification-report .musicforge\releases\rel-000002\audio-timelines\ratl-000001\verification-report.json --current-certification .musicforge\releases\rel-000002\audio-certification\release-audio-certification.zip --current-certification-verification-report .musicforge\releases\rel-000002\audio-certification\verification-report.json --json
```

Release signoff can require `require_release_audio_regression_guard=true` and
`require_release_audio_regression_signed=true`. Internal full-resign attacks,
stale baseline/current Timeline evidence, stale Certification ZIPs, and signed
history deletion are hard-blocked.

## LTS Maintenance

Create and verify local backups before upgrades or machine migration:

```powershell
python -m song_agent.cli maintenance status --json
python -m song_agent.cli maintenance backup create --mode workspace --json
python -m song_agent.cli maintenance backup verify --backup-id mb-000001 --json
python -m song_agent.cli verify-maintenance-backup .musicforge\maintenance\backups\mb-000001\musicforge-maintenance-backup.zip --json
python -m song_agent.cli maintenance backup restore-plan --backup-id mb-000001 --target C:\tmp\musicforge-restore --json
python -m song_agent.cli maintenance upgrade preflight --target-version 10.1.1 --require-verified-backup --json
```

Maintenance backups exclude provider and renderer local config. Recreate those
settings manually after restoring onto a new machine.

## Documentation Index

- `docs/GETTING_STARTED.md`
- `docs/LOCAL_ACCEPTANCE_RUNBOOK.md`
- `docs/MUSIC_REVIEW_GUIDE.md`
- `docs/RELEASE_RUNBOOK.md`
- `docs/BACKUP_RESTORE_RUNBOOK.md`
- `docs/UPGRADE_RUNBOOK.md`
- `docs/TROUBLESHOOTING.md`
- `docs/MAINTENANCE_POLICY.md`
- `docs/SECURITY_AND_SECRETS.md`

## Safety Notes

Do not put tokens in Git remotes. Do not commit `.musicforge/provider.json` or
`.musicforge/renderer.json`. Keep local absolute paths out of public evidence
packages and documentation.

## Historical Notes

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

v7.6.0 adds a Public Attestation Portal Review Response loop. After building a
v7.4 Attestation Portal ZIP, create a review pack and import an external
response locally:

```powershell
python -m song_agent.cli release-portfolio-governance-attestation-portal-review --portfolio-id <portfolio-id> --refresh-pack --export-pack --zip-pack --verify-pack --strict --require-current
python -m song_agent.cli verify-release-portfolio-governance-attestation-portal-review-pack .musicforge\portfolio-audits\<portfolio-id>\governance-attestation-portal-review\governance-attestation-portal-review-pack.zip --strict --require-current
python -m song_agent.cli verify-release-portfolio-governance-attestation-portal-response <response.zip> --strict --require-current --require-pack
```

Review responses are imported from uploaded/base64 content only. `source_path`
is rejected so the API cannot read arbitrary server-side files. `needs_changes`
and `rejected` responses can create local Change Request drafts; they do not
auto-approve, reset, sign off, or mutate governance evidence.

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

Release Operations Dashboard aggregates Release, Metadata, Audio, Rights,
Format Decision, Distribution, Submission, Submission Evidence, and verifier
summaries into a read-only readiness report. It shows the current stage, next
blocking actions, package/evidence status, and can export a portable Operations
Package for offline verification. It does not sign, reset, upload, mark accepted,
or mutate any existing Release/Distribution/Submission evidence.

Release Operations Runbooks turn dashboard `next_actions` into an auditable
local action queue. Only safe refresh/export/zip/verify actions can execute;
signoff, reset, accepted/submitted status changes, external upload, provider
work, and manual reviews remain `manual_required`. A Runbook binds to the
Operations Report source hash, so stale Runbooks cannot execute safe actions
after the Release state changes.

Release Operations Signoff archives the accepted Operations Report after the
safe Runbook and package verifiers are clean. The archive ZIP contains summary
evidence only and can be verified offline. After Operations Signoff, changes to
the archived evidence require an approved Operations Change Request before the
signoff can be reset.

Release Operations Audit Ledger links the Dashboard, Runbook, Signoff,
Change Request, Archive, and verifier records into a deterministic hash-chained
ledger. The audit ZIP contains summary evidence only and can be verified
offline for ledger ordering, report integrity, reset Change Request causality,
ZIP path safety, manifest spoofing, duplicate entries, and redaction issues.

Release Portfolio Audit aggregates multiple Releases into a cross-release
governance report. It produces release readiness ranking, Portfolio Risk Score,
trend findings, risk register, deterministic recommendations, reviewer-pack
coverage, Operations Audit verification, Operations Archive verification,
Runbook summaries, and Change Request summaries. It is read-only governance:
Portfolio Audit does not sign, reset, upload, mutate Release evidence, or bypass
any per-Release gate. The portable Portfolio ZIP can be verified outside the
workspace for manifest/file hashes, report/trend/risk integrity, path safety,
duplicate entries, manifest spoofing, redaction, and required reviewer/audit/
archive evidence.

Release Portfolio Governance Queue turns Portfolio Audit risks and
recommendations into an auditable action queue. It can run only safe local
refresh/export/zip/verify actions, such as Reviewer Pack, Operations Audit, and
Operations Archive verification refreshes. Signoff, reset, approval, manual
review, provider work, and external upload remain manual-required actions. A
queue binds to the Portfolio Audit source hash; stale queues return 409 on
`run-safe`, export, and ZIP rebuild, and must be recreated from a refreshed
Portfolio Audit.

Release Portfolio Governance Signoff closes a Governance Queue with queue,
action-plan, execution, manual-action, queue-verifier, and source evidence
bound into a signed record. Signed queues are immutable for `run-safe`, export,
and ZIP rebuild; reset requires an approved one-time Governance Change Request.
Queue verification evidence must match the current Governance Queue ZIP
sha256, ZIP size, and export manifest hash, so rebuilding the queue ZIP after
verification requires running verification again before signoff.
Governance Archive ZIPs can be verified offline:

```powershell
python -m song_agent.cli verify-release-portfolio-governance-archive-package path\to\governance-archive.zip --strict --require-signed --json
```

Release Portfolio Governance Audit Ledger links Portfolio Audit, Governance
Queues, queue verification, signoff, archive verification, Change Requests, and
reset causality into a deterministic hash-chained audit package. The exported
ZIP contains `portfolio-governance-audit-ledger.jsonl`,
`portfolio-governance-audit-report.json`, queue/signoff/archive summaries, and
Markdown review notes. It can be verified outside the local workspace for
ledger ordering, report integrity, reset Change Request causality, signed queue
archive coverage, ZIP safety, manifest spoofing, duplicate entries, and
redaction issues. Archive verification evidence is bound to the current
Governance Archive ZIP sha256 and manifest hash, so rebuilding the archive ZIP
requires re-running archive verification before the Portfolio Governance Audit
can pass:

```powershell
python -m song_agent.cli release-portfolio-governance-audit --portfolio-id <portfolio-id> --refresh --export --zip --verify --require-signed --require-archives --json
python -m song_agent.cli verify-release-portfolio-governance-audit-package path\to\portfolio-governance-audit.zip --strict --require-signed --require-archives --json
```

Release Portfolio Governance Reviewer Pack turns the v6.8 governance audit
ledger into a portable human review package. It writes a reviewer report,
retrospective, evidence index, timeline, Markdown guide, manifest, and ZIP
under `governance-reviewer-pack/`. The pack is read-only: it does not create
queues, run safe actions, signoff, reset, approve Change Requests, or feed back
into the Governance Audit source hash. The offline verifier checks package
type, sidecar integrity, manifest file hashes, required entries, duplicate and
unsafe ZIP entries, manifest spoofing, redaction, audit verification, signed
queue coverage, archive coverage, and reset causality. The required Governance
Audit verification report must match the current Audit ZIP sha256, ZIP size,
and Audit export manifest hash; rebuilding the Audit ZIP requires re-running
Audit verification before a Reviewer Pack can pass:

```powershell
python -m song_agent.cli release-portfolio-governance-reviewer-pack --portfolio-id <portfolio-id> --refresh --export --zip --verify --strict --require-audit --require-signed --require-archives --json
python -m song_agent.cli verify-release-portfolio-governance-reviewer-pack path\to\portfolio-governance-reviewer-pack.zip --strict --require-audit --require-signed --require-archives --json
```

Release Portfolio Governance Final Board turns the v6.9 reviewer package into
final portfolio governance signoff evidence. It requires current Reviewer Pack
verification, current Governance Audit verification, verified Governance
Archive coverage, and an accepted reviewer response before signing. The archive
is immutable for a given signoff: rebuilding Final Board archive evidence
requires an approved Final Board Change Request, reset, and new signoff. This
immutability is backed by persisted history, not just by the presence of export
files, so deleting the archive directory or ZIP does not permit a silent rebuild.

```powershell
python -m song_agent.cli release-portfolio-governance-final-board --portfolio-id <portfolio-id> --refresh --import-reviewer-response reviewer-response.json --require-reviewer-response --sign --signed-by local-user --export --zip --verify --strict --require-signed --require-reviewer-pack --require-audit --require-archives --require-reviewer-response --json
python -m song_agent.cli verify-release-portfolio-governance-final-board path\to\portfolio-governance-final-board-archive.zip --strict --require-signed --require-reviewer-pack --require-audit --require-archives --require-reviewer-response --json
```

Release Portfolio Governance Evidence Vault packages the current Final Board
Archive, Governance Reviewer Pack, Governance Audit, signed Governance Archives,
and optional Governance Queue packages into a long-term portable evidence vault.
The vault does not mutate Final Board, Audit, Reviewer Pack, Queue, or Archive
source evidence. It verifies nested ZIP sha256, ZIP size, manifest hashes, and
the saved verification reports before export, and `--deep` re-runs nested
offline verifiers from a clean temporary directory. Like the Final Board
Archive, vault export and ZIP rebuild are immutable for the current Final Board
signoff hash; deleting vault files does not permit a silent rebuild.

```powershell
python -m song_agent.cli release-portfolio-governance-evidence-vault --portfolio-id <portfolio-id> --refresh --export --zip --verify --strict --deep --require-final-board --require-reviewer-pack --require-audit --require-archives --json
python -m song_agent.cli verify-release-portfolio-governance-evidence-vault path\to\portfolio-governance-evidence-vault.zip --strict --deep --require-final-board --require-reviewer-pack --require-audit --require-archives --json
```

Release Portfolio Governance Public Attestation creates a lightweight public
certificate package from a current, deep-verified Evidence Vault. It contains
`certificate.json`, `certificate.md`, optional static HTML, hash fingerprints,
and verification status, but it does not include nested Evidence Vault, Final
Board, Audit, Queue, or Archive ZIP packages. Export and ZIP rebuild are
immutable for the same Evidence Vault ZIP hash, Final Board signoff hash, and
attestation profile, so deleting files does not permit a silent rebuild.

```powershell
python -m song_agent.cli release-portfolio-governance-attestation --portfolio-id <portfolio-id> --refresh --export --zip --verify --strict --require-vault --require-final-board --json
python -m song_agent.cli verify-release-portfolio-governance-attestation path\to\portfolio-governance-public-attestation.zip --strict --require-vault --require-final-board --json
```

Release Portfolio Governance Attestation Registry records the lifecycle of
public certificates. It registers the current verified Public Attestation,
publishes one current entry, supersedes older entries only with explicit
confirmation, supports revocation without deletion, and exports a registry ZIP
that can be verified offline. Registry export and ZIP rebuild are immutable for
the same registry state, so deleting files does not permit silent regeneration.

```powershell
python -m song_agent.cli release-portfolio-governance-attestation-registry --portfolio-id <portfolio-id> --register-current --publish pgar-000001 --refresh --export --zip --verify --strict --require-current --require-published --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-registry path\to\governance-attestation-registry.zip --strict --require-current --require-published --json
```

Release Portfolio Governance Attestation Portal Snapshot turns a verified
Public Attestation Registry into a static offline HTML/JSON portal. The portal
contains human-readable pages plus machine-readable summaries, but it does not
embed Public Attestation, Registry, Evidence Vault, or Final Board ZIP packages.
The verifier rejects scripts, remote links, local paths, nested packages, data
summary tamper, manifest spoofing, and fully re-signed packages whose Portal
summary no longer matches the Registry or Public Attestation verification
summary sidecars.

```powershell
python -m song_agent.cli release-portfolio-governance-attestation-portal --portfolio-id <portfolio-id> --refresh --export --zip --verify --strict --require-current --require-registry --require-attestation --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-portal path\to\governance-attestation-portal.zip --strict --require-current --require-registry --require-attestation --json
```

Release Verification Matrix makes `release-check` selectable and auditable.
The default command still runs the full verification set, while profiles can be
used for focused hotfix or reviewer checks. Reports are written without tokens
or local key paths. Execution fails if the selected matrix is empty; `--list`
may be used to inspect an empty selection without failing:

```powershell
python -m song_agent.cli release-check
python -m song_agent.cli release-check --profile latest --json --report-out runs\release-check-latest.json
python -m song_agent.cli release-check --profile v7 --timing-out runs\release-check-v7-timing.json
python -m song_agent.cli release-check --group portal --list
python -m song_agent.cli release-check --only v75.release_check_matrix_smoke --json
```

Release Portfolio Governance Attestation Accepted Evidence turns a verified
accepted Portal Review Response into a public-safe evidence record. It does not
publish, revoke, supersede, or rewrite Registry history; it only records that
the current Portal/Registry/Public Attestation chain has accepted external
review evidence. Registry and Portal verifiers can require this evidence with
`--require-accepted-evidence`:

```powershell
python -m song_agent.cli release-portfolio-governance-attestation-accepted-evidence --portfolio-id <portfolio-id> --refresh --export --zip --verify --strict --require-current --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-accepted-evidence path\to\governance-attestation-accepted-evidence.zip --strict --require-current --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-registry path\to\governance-attestation-registry.zip --strict --require-current --require-published --require-accepted-evidence --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-portal path\to\governance-attestation-portal.zip --strict --require-current --require-registry --require-attestation --require-accepted-evidence --json
```

Release Portfolio Governance Attestation Transparency Feed records the public
state of the Registry, Portal, Public Attestation, and Accepted Evidence as a
hash-chained event feed with change notices. It does not publish online or embed
nested evidence ZIPs; it creates a public-safe ZIP that an external reviewer can
verify offline:

```powershell
python -m song_agent.cli release-portfolio-governance-attestation-transparency --portfolio-id <portfolio-id> --refresh --export --zip --verify --strict --require-current --require-accepted-evidence --require-contiguous-chain --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-transparency path\to\governance-attestation-transparency.zip --strict --require-current --require-accepted-evidence --require-contiguous-chain --json
```

Release Portfolio Governance Attestation Transparency Acknowledgement lets an
external reviewer confirm the current Transparency ZIP and change notices. The
response payload must explicitly bind to the acknowledgement pack id/source hash
and current Transparency ZIP/manifest/feed source; the importer will not fill
those fields for a bare JSON response. Accepted responses can be converted into
public-safe acknowledgement evidence. Evidence ZIPs include response verification
and original response binding sidecars, so the offline verifier rejects fully
re-signed forged reviewer summaries. `needs_changes` and `rejected` responses
only create local Change Request drafts and never mutate Registry, Portal,
Transparency, or Accepted Evidence state automatically:

```powershell
python -m song_agent.cli release-portfolio-governance-attestation-transparency-acknowledgement --portfolio-id <portfolio-id> --refresh-pack --export-pack --zip-pack --verify-pack --strict --require-transparency --json
python -m song_agent.cli release-portfolio-governance-attestation-transparency-acknowledgement --portfolio-id <portfolio-id> --import-response --content-base64 <base64-json-or-zip> --refresh-evidence --export-evidence --zip-evidence --verify-evidence --strict --require-accepted --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-transparency-acknowledgement path\to\transparency-acknowledgement-pack.zip --strict --require-pack --require-transparency --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-transparency-acknowledgement path\to\transparency-acknowledgement-evidence.zip --strict --require-response --require-accepted --json
```

Public Trust Center aggregates the public-safe evidence chain across Releases,
Distribution targets, Submissions, Submission Evidence, Release Operations, and
Portfolio Governance into a static portal ZIP. It is read-only: refresh,
export, ZIP, verify, and archive never sign off, reset, approve, upload, or
mutate underlying Release/Distribution/Submission/Operations/Portfolio
evidence. The ZIP does not embed internal evidence packages; it references
fingerprints and verification summaries, and the verifier can run in a clean
directory without `.musicforge`. Public package fingerprints and delivery-chain
summaries are checked against independent sidecars exported from the underlying
verification reports, so fully re-signed forged package or delivery summaries
are rejected:

```powershell
python -m song_agent.cli public-trust-center --center-id ptc-default --refresh --export --zip --verify --strict --require-registry-current --require-portal-current --require-transparency-current --require-acknowledgement-current --include-delivery --json
python -m song_agent.cli verify-public-trust-center-package path\to\public-trust-center.zip --strict --require-registry-current --require-portal-current --require-transparency-current --require-acknowledgement-current --require-delivery-readiness --require-distribution-ready --require-submission-accepted --require-submission-evidence --require-operations-signed --require-operations-audit --require-operations-reviewer-pack --json
```

Public Trust Center Anchor Registry registers the current delivery anchor as a
publishable, revocable trust-anchor entry. The registry ZIP is verified outside
the Trust Center ZIP and can be supplied back to the Trust Center verifier when
anchor registry requirements are enabled:

```powershell
python -m song_agent.cli public-trust-center --center-id ptc-default --anchor-register --anchor-publish --anchor-export --anchor-zip --anchor-verify --strict --require-anchor-registry-current --require-anchor-published --require-anchor-not-revoked --json
python -m song_agent.cli verify-public-trust-center-anchor-registry-package path\to\public-trust-center-anchor-registry.zip --strict --require-current --require-anchor-published --require-anchor-not-revoked --json
python -m song_agent.cli verify-public-trust-center-package path\to\public-trust-center.zip --strict --require-delivery-readiness --delivery-anchor path\to\public-trust-center.delivery-anchor.json --anchor-registry path\to\public-trust-center-anchor-registry.zip --require-anchor-registry-current --require-anchor-published --require-anchor-not-revoked --json
```

Public Trust Center Anchor Transparency adds an append-only local ledger and a
small external checkpoint on top of the Anchor Registry. The checkpoint can be
saved outside the ZIP set and supplied back to the verifier to detect wholesale
replacement of the Trust Center ZIP, delivery anchor, and Anchor Registry ZIP:

```powershell
python -m song_agent.cli public-trust-center --center-id ptc-default --anchor-transparency-refresh --anchor-checkpoint-create --anchor-transparency-export --anchor-transparency-zip --anchor-transparency-verify --strict --require-anchor-registry-current --require-anchor-published --require-anchor-not-revoked --require-anchor-transparency-current --require-anchor-checkpoint --json
python -m song_agent.cli verify-public-trust-center-anchor-transparency-package path\to\public-trust-center-anchor-transparency.zip --strict --checkpoint path\to\ptc-anchor-checkpoint-current.json --anchor-registry path\to\public-trust-center-anchor-registry.zip --require-current-checkpoint --require-published-anchor --require-not-revoked --json
python -m song_agent.cli verify-public-trust-center-package path\to\public-trust-center.zip --strict --require-delivery-readiness --delivery-anchor path\to\public-trust-center.delivery-anchor.json --anchor-registry path\to\public-trust-center-anchor-registry.zip --anchor-transparency path\to\public-trust-center-anchor-transparency.zip --anchor-checkpoint path\to\ptc-anchor-checkpoint-current.json --require-anchor-registry-current --require-anchor-published --require-anchor-not-revoked --require-anchor-transparency-current --require-anchor-checkpoint --json
```

Public Trust Center Distribution Kit packages the current Public Trust Center
ZIP, delivery anchor, Anchor Registry ZIP, Anchor Transparency ZIP, current
checkpoint, and their verification reports into one external handoff ZIP. The
Kit verifier can run in a clean directory, re-run nested verification with
`--deep`, only permits the three expected nested ZIP files, and rejects stale
reports, path traversal, backslash entries, `.musicforge` entries, manifest
spoofing, redaction leaks, and unexpected nested ZIPs:

```powershell
python -m song_agent.cli public-trust-center --center-id ptc-default --distribution-kit-refresh --distribution-kit-export --distribution-kit-zip --distribution-kit-verify --strict --require-anchor-registry-current --require-anchor-published --require-anchor-not-revoked --require-anchor-transparency-current --require-anchor-checkpoint --json
python -m song_agent.cli verify-public-trust-center-distribution-kit-package path\to\public-trust-center-distribution-kit.zip --strict --deep --require-current --json
```

Distribution Kit Acceptance records an external receiver response to the
current Kit. Imported responses must explicitly bind the current Kit ZIP hash,
manifest hash, report/source hash, and verification report hash; the importer
does not fill those fields in for the reviewer. Only current
`external_manual` accepted responses can produce public-safe Accepted Evidence
ZIPs. Accepted Evidence also carries stored response verification and binding
proof sidecars, so verifier checks the public reviewer projection against the
original imported response evidence instead of trusting package-internal
re-signing:

```powershell
python -m song_agent.cli public-trust-center --center-id ptc-default --distribution-kit-acceptance-template --json --report-out kit-acceptance-template.json
python -m song_agent.cli public-trust-center --center-id ptc-default --distribution-kit-acceptance-response-file receiver-response.json --distribution-kit-accepted-evidence-export --distribution-kit-accepted-evidence-zip --distribution-kit-accepted-evidence-verify --strict --json
python -m song_agent.cli verify-public-trust-center-distribution-kit-accepted-evidence-package path\to\accepted-evidence.zip --strict --require-current --distribution-kit path\to\public-trust-center-distribution-kit.zip --json
```

Public Trust Center Acceptance Board aggregates multiple current external
receiver acceptances into a quorum decision. A board policy can require a
minimum accepted count, distinct organizations, and roles such as legal or
distribution partner. `needs_changes`, `rejected`, critical findings, stale
responses, and stale accepted evidence block readiness by default. The Board
ZIP carries response proofs, accepted evidence summaries, and quorum evidence;
the verifier cross-checks those sidecars instead of trusting a re-signed board
report alone. For ready/quorum/role-gated verification, provide the external
Accepted Evidence directory so the verifier can bind each counted participant
back to the original accepted evidence ZIP rather than package-internal
sidecars:

```powershell
python -m song_agent.cli public-trust-center --center-id ptc-default --acceptance-board-policy-save acceptance-board-policy.json --acceptance-board-refresh --acceptance-board-export --acceptance-board-zip --acceptance-board-verify --strict --require-ready --require-quorum --require-no-conflicts --json
python -m song_agent.cli verify-public-trust-center-acceptance-board-package path\to\public-trust-center-acceptance-board.zip --strict --require-ready --require-quorum --require-no-conflicts --distribution-kit path\to\public-trust-center-distribution-kit.zip --accepted-evidence-dir path\to\accepted-evidence --json
```

When the Acceptance Board is ready, it can be formally signed and archived.
Signoff freezes the Board policy/report/export/ZIP until an approved Board
Change Request is applied. The signoff archive binds the Board ZIP, Board
verification report, Distribution Kit ZIP, quorum participants, and external
Accepted Evidence fingerprints:

```powershell
python -m song_agent.cli public-trust-center --center-id ptc-default --acceptance-board-signoff --acceptance-board-signed-by "Release Reviewer" --acceptance-board-signoff-reason "Board quorum is ready." --acceptance-board-signoff-archive-export --acceptance-board-signoff-archive-zip --acceptance-board-signoff-archive-verify --strict --json
python -m song_agent.cli verify-public-trust-center-acceptance-board-signoff-archive-package path\to\public-trust-center-acceptance-board-signoff-archive.zip --strict --require-signed --require-current --require-ready --board-zip path\to\public-trust-center-acceptance-board.zip --board-verification-report path\to\acceptance-board-verification-report.json --distribution-kit path\to\public-trust-center-distribution-kit.zip --accepted-evidence-dir path\to\accepted-evidence --json
```

Top-level Public Trust Center and Distribution Kit verification can require the
same signed Board evidence. Public Trust Center verification does not accept an
archive-only shortcut for this gate; the Board ZIP, Board verification report,
Distribution Kit ZIP, and Accepted Evidence directory must be supplied so the
signoff archive is checked against current external evidence:

```powershell
python -m song_agent.cli verify-public-trust-center-package path\to\public-trust-center.zip --strict --require-acceptance-board-signoff --acceptance-board-signoff-archive path\to\public-trust-center-acceptance-board-signoff-archive.zip --acceptance-board path\to\public-trust-center-acceptance-board.zip --acceptance-board-verification-report path\to\acceptance-board-verification-report.json --distribution-kit path\to\public-trust-center-distribution-kit.zip --accepted-evidence-dir path\to\accepted-evidence --json
python -m song_agent.cli verify-public-trust-center-distribution-kit-package path\to\public-trust-center-distribution-kit.zip --strict --deep --require-current --no-require-delivery-readiness --require-acceptance-board-signoff --acceptance-board-signoff-archive path\to\public-trust-center-acceptance-board-signoff-archive.zip --acceptance-board path\to\public-trust-center-acceptance-board.zip --acceptance-board-verification-report path\to\acceptance-board-verification-report.json --accepted-evidence-dir path\to\accepted-evidence --json
```

Public Trust Center Publication Channels turn the current public evidence set
into a static publication mirror and a portable publication ZIP. The verifier
uses a fixed package structure, checksum binding, mirror policy checks, nested
package allow-lists, and optional current-anchor / no-revoked gates:

```powershell
python -m song_agent.cli public-trust-center-publication --center-id ptc-default --channel-id public-release --create-channel --refresh --export --zip --verify --verify-mirror --strict --deep --require-ready --require-acceptance-board-signoff --require-anchor-current --require-no-revoked --json
python -m song_agent.cli verify-public-trust-center-publication-package path\to\public-trust-center-publication.zip --strict --deep --require-ready --require-acceptance-board-signoff --require-anchor-current --require-no-revoked --publication-channel-state path\to\publication-channel-state.json --json
python -m song_agent.cli verify-public-trust-center-publication-mirror path\to\publication-mirror --strict --require-ready --require-acceptance-board-signoff --require-anchor-current --require-no-revoked --publication-channel-state path\to\publication-channel-state.json --json
```

`--require-no-revoked` intentionally needs the external channel state file. A
previously exported ZIP is immutable, so revoke/supersede status must be checked
against the current publication channel ledger rather than the ZIP's internal
report alone.

Public Trust Center Publication Monitoring runs repeatable probes against a
publication ZIP, its mirror directory, and the external channel state. It writes
probe results, drift reports, incident summaries, and a fixed-structure
monitoring ZIP that can be verified offline. Current/revoke/supersede gates
require the external `publication-channel-state.json`; the monitoring ZIP does
not self-certify whether a publication has since been withdrawn or replaced.
Monitoring packages include raw `incident-events.jsonl` evidence, and the
verifier rebuilds incident status from that event chain before applying
`--require-no-open-critical-incidents`.

```powershell
python -m song_agent.cli public-trust-center-publication-monitor --center-id ptc-default --channel-id public-release --create-monitor --run --export --zip --verify --strict --require-current --require-no-revoked --require-ready --require-no-drift --require-no-open-critical-incidents --json
python -m song_agent.cli verify-public-trust-center-publication-monitoring-package path\to\public-trust-center-publication-monitoring.zip --strict --require-current --require-no-revoked --require-ready --require-no-drift --require-no-open-critical-incidents --publication-channel-state path\to\publication-channel-state.json --json
```

Trust Operations Hub aggregates the top-level public trust and operations
readiness evidence into a single local readiness matrix, blocker register,
manual action queue, and fixed-structure Hub ZIP. Hub verification never relies
only on the package's own summary for current-state gates: `--require-current`
must be paired with the external publication channel state and the current
verification reports used to build the Hub.
It can also bind full delivery-chain evidence from Release, Distribution,
Submission, Submission Evidence, and Release Operations verification reports.
When `--require-delivery-ready` is enabled, those external reports are required
and are checked against the Hub delivery sidecars; the Hub ZIP cannot self-certify
delivery readiness. Repeat delivery verification arguments such as
`--distribution-verification` when a release has multiple targets of the same
type.
Signed Hub verification is also an external-evidence gate: use
`--require-signed` with both the Hub `signoff.json` sidecar and the Hub
verification report that was written before signoff.
Trust Operations Hub Runbook turns Hub blockers and next steps into a safe local
queue. Only refresh-free Hub export, ZIP, and verify actions are automated;
signoff, reset, submit, accept, provider, and manual review actions remain
manual-required.
Trust Operations Hub Incidents turn Hub blockers and failed delivery verification
checks into auditable remediation records. Incident evidence must be uploaded as
JSON content, never by `source_path`; closeout exports include the raw event
chain and are verified before they can satisfy the Hub
`--require-incident-closeout` gate.
Trust Operations Incident Knowledge turns closed, verified incidents into local
Knowledge Entries and deterministic Regression Guards. The Hub verifier can
require the Knowledge ZIP plus its verification report with
`--require-incident-regression-guards`, so recurring incident patterns must have
current guard evidence before Hub readiness is accepted. Knowledge verification
requires the external Incident Board ZIP and verification report so entry
severity, component scope, root cause, and recommended guard type are checked
against the original incident facts, not just the Knowledge ZIP's own JSON.
Trust Operations Control Catalog turns baseline controls and Knowledge-derived
guards into an auditable preventive control policy. Control assessment packages
bind the current Hub, Incident Board, and Incident Knowledge verification
reports, and the Hub verifier can require them with `--require-trust-controls`.
The Control verifier replays baseline specs, derived-control semantics, external
evidence bindings, and fixed ZIP allow-lists instead of trusting the Control ZIP
alone.
Trust Operations Control Signoff turns a passed Control assessment into signed
control evidence. It supports medium/low non-required exceptions, approved
Change Request reset, immutable archive export, and offline verification. The
signed state is backed by history, so deleting `signoff.json` does not unlock
archive rebuilds or reset. The Hub verifier can require both Controls and their
Signoff Archive with `--require-trust-control-signoff`.
Trust Operations Continuous Assurance checks whether signed Hub, delivery,
Control, Incident, Knowledge, and Regression Guard evidence is still current
after signoff. The Assurance Archive binds external verification reports and
package fingerprints, rejects stale sources before export/ZIP, and can be
required by the Hub verifier with `--require-continuous-assurance`. Explicitly
provided delivery verification reports must pass; failed delivery evidence or
policy-required missing delivery evidence blocks the Assurance run.
Trust Operations Assurance Watch schedules recurring Continuous Assurance
review, turns missing/due/overdue/stale/failed Assurance into a Watch Queue and
Drift Action Pack, and never performs repairs automatically. The Watch ZIP is a
fixed-structure archive whose verifier re-derives queue rows and action
semantics from the Assurance run index and checks current external Assurance and
Hub verification reports. The Hub verifier can require a clear Watch with
`--require-assurance-watch-clear`.
Trust Operations Assurance Watch Signoff turns a clear, verified Watch Queue
into signed closeout evidence. Its archive is immutable after signing, reset
requires an approved unused Change Request, and the Hub verifier can require the
current signoff archive with `--require-assurance-watch-signoff`.
Trust Operations Final Readiness Certificate turns the signed Hub, delivery,
Incident, Knowledge, Control, Continuous Assurance, Assurance Watch, and Watch
Signoff evidence into the final handoff certificate and fixed-structure Handoff
Pack. The handoff is signed with hash-chained history, reset requires an
approved unused Change Request, and the Hub verifier can require the current
Final Handoff package with `--require-final-readiness`.

```powershell
python -m song_agent.cli trust-operations-hub --hub-id hub-default --create --refresh --export --zip --verify --strict --require-ready --require-current --require-publication-monitoring-clean --publication-channel-state path\to\publication-channel-state.json --public-trust-center-verification path\to\public-trust-center-verification.json --publication-monitoring-verification path\to\monitoring-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-ready --require-current --require-publication-monitoring-clean --publication-channel-state path\to\publication-channel-state.json --public-trust-center-verification path\to\public-trust-center-verification.json --publication-monitoring-verification path\to\monitoring-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-delivery-ready --release-verification path\to\release-verification.json --distribution-verification path\to\distribution-verification.json --submission-verification path\to\submission-verification.json --submission-evidence-verification path\to\submission-evidence-verification.json --release-operations-verification path\to\operations-verification.json --json
python -m song_agent.cli trust-operations-hub --hub-id hub-default --signoff --signed-by reviewer --reason "Trust Operations Hub accepted." --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-signed --hub-signoff path\to\signoff.json --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli trust-operations-hub-runbook --hub-id hub-default --report-id trust-hub-report-000001 --create --run-safe --export --zip --verify --strict --require-completed --require-no-blocked --json
python -m song_agent.cli verify-trust-operations-hub-runbook-package path\to\trust-operations-hub-runbook.zip --strict --require-completed --require-no-blocked --json
python -m song_agent.cli trust-operations-assurance-watch-signoff --queue-id toawq-000001 --refresh-closeout --sign --signed-by reviewer --reason "Assurance Watch queue accepted." --export --zip --verify --strict --require-current --watch-package path\to\trust-operations-assurance-watch.zip --watch-verification-report path\to\watch-verification-report.json --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --continuous-assurance-report path\to\assurance-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-assurance-watch-signoff --assurance-watch-package path\to\trust-operations-assurance-watch.zip --assurance-watch-verification-report path\to\watch-verification-report.json --assurance-watch-signoff-archive path\to\trust-operations-assurance-watch-signoff.zip --assurance-watch-signoff-verification-report path\to\watch-signoff-verification-report.json --continuous-assurance-verification-report path\to\assurance-verification-report.json --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli trust-operations-final-readiness --hub-id hub-default --refresh-report --create-certificate --sign --signed-by reviewer --reason "Final readiness accepted." --export --zip --verify --strict --require-current --require-signed --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --assurance-watch-signoff-archive path\to\trust-operations-assurance-watch-signoff.zip --assurance-watch-signoff-verification-report path\to\watch-signoff-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-final-readiness --final-handoff-package path\to\trust-operations-final-handoff.zip --final-handoff-verification-report path\to\final-handoff-verification-report.json --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli trust-operations-hub-incidents --hub-id hub-default --refresh --list --json
python -m song_agent.cli trust-operations-hub-incidents --hub-id hub-default --incident-id inc-000001 --triage --create-plan --evidence-file path\to\verification-report.json --verify-fix --close --export --zip --verify --strict --require-no-open-blocking --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-incident-package path\to\trust-operations-incident-board.zip --strict --require-no-open-blocking --require-current-hub --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli trust-operations-incident-knowledge --hub-id hub-default --refresh --create-guard --run-all-guards --refresh-recurrence --export --zip --verify --strict --require-guards-passed --require-no-open-recurrence --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli verify-trust-operations-incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --strict --require-guards-passed --require-no-open-recurrence --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-delivery-ready --require-incident-closeout --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --hub-verification-report path\to\hub-verification-report.json --release-verification path\to\release-verification.json --distribution-verification path\to\distribution-verification.json --submission-verification path\to\submission-verification.json --submission-evidence-verification path\to\submission-evidence-verification.json --release-operations-verification path\to\operations-verification.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-delivery-ready --require-incident-closeout --require-incident-regression-guards --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --hub-verification-report path\to\hub-verification-report.json --release-verification path\to\release-verification.json --distribution-verification path\to\distribution-verification.json --submission-verification path\to\submission-verification.json --submission-evidence-verification path\to\submission-evidence-verification.json --release-operations-verification path\to\operations-verification.json --json
python -m song_agent.cli trust-operations-controls --hub-id hub-default --refresh-catalog --create-policy --assess --export --zip --verify --strict --require-policy-passed --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --json
python -m song_agent.cli verify-trust-operations-control-package path\to\trust-operations-controls.zip --strict --require-policy-passed --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-delivery-ready --require-incident-closeout --require-incident-regression-guards --require-trust-controls --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --trust-control-package path\to\trust-operations-controls.zip --trust-control-verification-report path\to\trust-operations-controls-verification-report.json --hub-verification-report path\to\hub-verification-report.json --release-verification path\to\release-verification.json --distribution-verification path\to\distribution-verification.json --submission-verification path\to\submission-verification.json --submission-evidence-verification path\to\submission-evidence-verification.json --release-operations-verification path\to\operations-verification.json --json
python -m song_agent.cli trust-operations-control-signoff --hub-id hub-default --assessment-id toc-assess-000001 --sign --signed-by reviewer --export --zip --verify --strict --require-signed --require-current --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --json
python -m song_agent.cli verify-trust-operations-control-signoff-archive-package path\to\trust-operations-control-signoff-archive.zip --strict --require-signed --require-current --control-package path\to\trust-operations-controls.zip --control-verification-report path\to\trust-operations-controls-verification-report.json --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-delivery-ready --require-incident-closeout --require-incident-regression-guards --require-trust-controls --require-trust-control-signoff --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --trust-control-package path\to\trust-operations-controls.zip --trust-control-verification-report path\to\trust-operations-controls-verification-report.json --trust-control-signoff-archive path\to\trust-operations-control-signoff-archive.zip --trust-control-signoff-verification-report path\to\control-signoff-verification-report.json --hub-verification-report path\to\hub-verification-report.json --release-verification path\to\release-verification.json --distribution-verification path\to\distribution-verification.json --submission-verification path\to\submission-verification.json --submission-evidence-verification path\to\submission-evidence-verification.json --release-operations-verification path\to\operations-verification.json --json
python -m song_agent.cli trust-operations-assurance --hub-id hub-default --refresh --export --zip --verify --strict --require-passed --require-current --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --control-signoff-archive path\to\trust-operations-control-signoff-archive.zip --control-signoff-verification-report path\to\control-signoff-verification-report.json --control-package path\to\trust-operations-controls.zip --control-verification-report path\to\trust-operations-controls-verification-report.json --incident-board-package path\to\trust-operations-incident-board.zip --incident-board-verification-report path\to\incident-verification-report.json --incident-knowledge-package path\to\trust-operations-incident-knowledge.zip --incident-knowledge-verification-report path\to\knowledge-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-continuous-assurance --continuous-assurance-archive path\to\trust-operations-assurance.zip --continuous-assurance-verification-report path\to\trust-operations-assurance-verification-report.json --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli trust-operations-assurance-watch --hub-id hub-default --refresh --export --zip --verify --strict --require-clear --require-current --assurance-archive path\to\trust-operations-assurance.zip --assurance-verification-report path\to\trust-operations-assurance-verification-report.json --hub-package path\to\trust-operations-hub.zip --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli verify-trust-operations-hub-package path\to\trust-operations-hub.zip --strict --require-assurance-watch-clear --assurance-watch-package path\to\trust-operations-assurance-watch.zip --assurance-watch-verification-report path\to\trust-operations-assurance-watch-verification-report.json --hub-verification-report path\to\hub-verification-report.json --json
python -m song_agent.cli trust-operations-hub --hub-id hub-default --create-change-request --change-request-id toh-cr-000001 --reason "Approved Hub evidence refresh." --json
python -m song_agent.cli trust-operations-hub --hub-id hub-default --approve-change-request toh-cr-000001 --json
python -m song_agent.cli trust-operations-hub --hub-id hub-default --reset-signoff --change-request-id toh-cr-000001 --json
```

```powershell
python -m song_agent.cli verify-submission-package path\to\submission-package.zip --json --deep --report-out submission-verification-report.json
```

```powershell
python -m song_agent.cli verify-submission-evidence-package path\to\submission-evidence-package.zip --json --deep --require-accepted --report-out submission-evidence-verification-report.json
```

```powershell
python -m song_agent.cli release-operations --release-id rel-000001 --refresh --export --zip --verify --require-submission-evidence --json
python -m song_agent.cli verify-release-operations-package path\to\release-operations-package.zip --json --require-accepted --require-submission-evidence --report-out operations-verification-report.json
python -m song_agent.cli release-operations-runbook rel-000001 --create --json
python -m song_agent.cli release-operations-runbook rel-000001 --runbook-id orb-000001 --run-safe --export --zip --verify --require-current --json
python -m song_agent.cli verify-release-operations-runbook-package path\to\runbook-export.zip --json --require-current --report-out runbook-verification-report.json
python -m song_agent.cli release-operations-signoff rel-000001 --sign --signed-by local-user --json
python -m song_agent.cli release-operations-archive rel-000001 --export --zip --verify --require-signed --json
python -m song_agent.cli verify-release-operations-archive-package path\to\operations-archive.zip --json --require-signed --report-out operations-archive-verification-report.json
python -m song_agent.cli release-operations-signoff rel-000001 --reset --reason "Approved operations evidence change" --change-request-id ocr-000001 --json
python -m song_agent.cli release-operations-audit rel-000001 --refresh --export --zip --verify --require-current --require-signed --require-archive --json
python -m song_agent.cli verify-release-operations-audit-package path\to\operations-audit.zip --json --strict --require-signed --require-archive --report-out operations-audit-verification-report.json
python -m song_agent.cli release-operations-reviewer-pack rel-000001 --refresh --export --zip --verify --strict --require-audit --require-signed --require-archive --json
python -m song_agent.cli verify-release-operations-reviewer-pack path\to\operations-reviewer-pack.zip --json --strict --require-audit --require-signed --require-archive --report-out reviewer-pack-verification-report.json
python -m song_agent.cli release-portfolio-audit --create --name "Q2 Portfolio Audit" --release-ids rel-000001,rel-000002 --require-reviewer-packs --require-audit --require-archive --json
python -m song_agent.cli release-portfolio-audit --portfolio-id pfa-000001 --refresh --export --zip --verify --strict --require-reviewer-packs --require-audit --require-archive --json
python -m song_agent.cli verify-release-portfolio-audit-package path\to\portfolio-audit.zip --json --strict --require-reviewer-packs --require-audit --require-archive --report-out portfolio-audit-verification-report.json
python -m song_agent.cli release-portfolio-governance-queue --portfolio-id pfa-000001 --create --json
python -m song_agent.cli release-portfolio-governance-queue --queue-id pgq-000001 --run-safe --export --zip --verify --strict --require-manual-actions --json
python -m song_agent.cli verify-release-portfolio-governance-package path\to\governance-queue.zip --json --strict --require-manual-actions --report-out governance-verification-report.json
python -m song_agent.cli release-portfolio-governance-audit --portfolio-id pfa-000001 --refresh --export --zip --verify --require-signed --require-archives --json
python -m song_agent.cli release-portfolio-governance-reviewer-pack --portfolio-id pfa-000001 --refresh --export --zip --verify --strict --require-audit --require-signed --require-archives --json
python -m song_agent.cli verify-release-portfolio-governance-reviewer-pack path\to\portfolio-governance-reviewer-pack.zip --json --strict --require-audit --require-signed --require-archives --report-out governance-reviewer-verification-report.json
python -m song_agent.cli release-portfolio-governance-final-board --portfolio-id pfa-000001 --refresh --import-reviewer-response reviewer-response.json --require-reviewer-response --sign --signed-by local-user --export --zip --verify --strict --require-signed --require-reviewer-pack --require-audit --require-archives --require-reviewer-response --json
python -m song_agent.cli verify-release-portfolio-governance-final-board path\to\portfolio-governance-final-board-archive.zip --json --strict --require-signed --require-reviewer-pack --require-audit --require-archives --require-reviewer-response --report-out final-board-verification-report.json
python -m song_agent.cli release-portfolio-governance-evidence-vault --portfolio-id pfa-000001 --refresh --export --zip --verify --strict --deep --require-final-board --require-reviewer-pack --require-audit --require-archives --json
python -m song_agent.cli verify-release-portfolio-governance-evidence-vault path\to\portfolio-governance-evidence-vault.zip --json --strict --deep --require-final-board --require-reviewer-pack --require-audit --require-archives --report-out evidence-vault-verification-report.json
python -m song_agent.cli release-portfolio-governance-attestation --portfolio-id pfa-000001 --refresh --export --zip --verify --strict --require-vault --require-final-board --json
python -m song_agent.cli verify-release-portfolio-governance-attestation path\to\portfolio-governance-public-attestation.zip --json --strict --require-vault --require-final-board --report-out public-attestation-verification-report.json
python -m song_agent.cli release-portfolio-governance-attestation-registry --portfolio-id pfa-000001 --register-current --publish pgar-000001 --refresh --export --zip --verify --strict --require-current --require-published --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-registry path\to\governance-attestation-registry.zip --json --strict --require-current --require-published --report-out attestation-registry-verification-report.json
python -m song_agent.cli release-portfolio-governance-attestation-portal --portfolio-id pfa-000001 --refresh --export --zip --verify --strict --require-current --require-registry --require-attestation --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-portal path\to\governance-attestation-portal.zip --json --strict --require-current --require-registry --require-attestation --report-out attestation-portal-verification-report.json
python -m song_agent.cli release-portfolio-governance-attestation-transparency --portfolio-id pfa-000001 --refresh --export --zip --verify --strict --require-current --require-accepted-evidence --require-contiguous-chain --json
python -m song_agent.cli verify-release-portfolio-governance-attestation-transparency path\to\governance-attestation-transparency.zip --json --strict --require-current --require-accepted-evidence --require-contiguous-chain --report-out attestation-transparency-verification-report.json
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
