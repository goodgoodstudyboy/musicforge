# Changelog

## v4.1.1 - 2026-05-17

### Fixed
- Global Distribution Template Pack update/delete now scans dependent Distribution targets and returns 409 when any signed or force-signed target is bound to that template.
- Template Pack changes that affect unsigned dependent targets now mark their QA/export summaries stale instead of leaving old summaries looking current.
- release-check v4.1 smoke now verifies signed-target global template update/delete guards.

### Verified
- `python -m pytest tests\test_server_distribution.py tests\test_release_check.py::test_v41_distribution_template_packs_smoke tests\test_distribution_templates.py tests\test_distribution.py -q`

## v4.1.0 - 2026-05-17

### Added
- Platform Template Packs for local Distribution Prep rules, metadata CSV mapping, file naming, and submission checklist definitions.
- Distribution targets can bind a template pack; template rules and checklist status now participate in Distribution QA source hashing and export gates.
- Distribution packages include `template-pack.json`, `template-summary.json`, template CSV output, and checklist JSON/Markdown docs.
- `verify-distribution-package` now validates template hashes, template summary hashes, checklist payload hashes, checklist status, and tamper scenarios.
- Studio Distribution Prep now exposes template pack selection, local template creation/clone controls, and checklist actions.
- release-check v4.1 smoke covers template import safety, mapping/checklist QA, export/verify, signed-target mutation guards, and template/checklist ZIP tamper detection.

### Scope
- Platform Template Packs are local preparation templates only. They are not official platform rules and do not upload, submit, connect to distributor APIs, or store platform credentials.

### Verified
- `python -m pytest tests\test_distribution_templates.py tests\test_distribution_checklist.py tests\test_distribution.py tests\test_server_distribution.py tests\test_release_check.py::test_v41_distribution_template_packs_smoke tests\test_webui.py::test_webui_contains_release_workspace_controls -q`

## v4.0.1 - 2026-05-17

### Fixed
- Distribution artwork import now rejects `source_path` payloads and only accepts uploaded base64 content, preventing API clients from reading server-local files.
- Distribution target signoff now checks signed-target mutability before refreshing QA, so repeat signoff returns 409 without changing `qa.json`.
- release-check v4.0 smoke now verifies `source_path` rejection and repeat signoff no-mutation behavior.

### Verified
- `python -m pytest tests\test_server_distribution.py tests\test_release_check.py::test_v40_distribution_prep_smoke tests\test_distribution.py tests\test_cli_verify_distribution.py -q`

## v4.0.0 - 2026-05-16

### Added
- Distribution Prep targets under each Release with built-in `generic_dsp`, `demo_pitch`, and `internal_archive` profiles.
- Distribution artwork import and QA for PNG/JPEG headers, dimensions, size limits, and selected artwork binding.
- Distribution QA source hashing over signed Release Export/ZIP/signoff, Release Metadata/QA, target options, profile, and artwork state.
- Distribution Export/ZIP packages with `distribution-manifest.json`, metadata JSON/CSV, lyrics, artwork, docs, optional audio, and signed sidecar payload hash binding for `distribution-signoff.json`.
- `python -m song_agent.cli verify-distribution-package <zip>` for offline package validation, including path safety, duplicate entries, ZIP bomb guard, manifest file hashes, signoff hash binding, artwork/WAV headers, CSV formula safety, and redaction scanning.
- Studio Distribution Prep controls and release-check v4.0 smoke coverage for package export, external verification, signed mutation blocking, signoff tamper failure, CSV formula pollution, and backslash ZIP entry failure.

### Scope
- Distribution Prep is local preparation and verification only. It does not upload to DSPs, call distributor APIs, or save platform credentials.

### Verified
- `python -m pytest tests\test_distribution.py tests\test_server_distribution.py tests\test_cli_verify_distribution.py tests\test_release_check.py::test_v40_distribution_prep_smoke tests\test_webui.py -q`

## v3.9.1 - 2026-05-16

### Fixed
- Signed releases now block `POST /api/releases/<id>/export`, `POST /api/releases/<id>/export/zip`, and `POST /api/releases/<id>/metadata/export` with 409 until signoff is reset, preserving the signed Release Export manifest hash and ZIP verification chain.
- release-check v3.9 smoke now verifies signed release export mutation is blocked for all three write endpoints.

### Verified
- `python -m pytest tests\test_server_release_metadata.py tests\test_release_check.py::test_v39_release_metadata_smoke -q`

## v3.9.0 - 2026-05-16

### Added
- Release Metadata documents under `.musicforge/releases/<release-id>/metadata.json` with release title, artists, label, language, release date, UPC, rights notes, track ISRC, explicit/instrumental flags, lyrics, and credits.
- Metadata QA for required fields, UPC/ISRC formats, duplicate ISRCs, tracklist consistency, lyrics/explicit/instrumental warnings, credits coverage, confirmation state, and sensitive value redaction.
- Metadata export files in Release Export and ZIP: `release-metadata.json`, `platform-metadata.csv`, `credits.csv`, and `lyrics/*.txt`.
- Release API endpoints for metadata init/save/QA/export plus platform and credits CSV downloads.
- Studio Release Metadata panel with initialize, save, QA refresh, export, and CSV download controls.
- `verify-release` metadata checks for manifest metadata summaries, protected metadata files, UTF-8 CSV parsing, tracklist consistency, metadata payload hash, lyrics/CSV/JSON redaction, and old pre-v3.9 ZIP compatibility warnings.
- release-check v3.9 smoke covering metadata init, QA, export, ZIP verification, missing metadata file failure, and metadata redaction failure.

### Verified
- `python -m pytest tests\test_release_metadata.py tests\test_server_release_metadata.py tests\test_release_export.py tests\test_release_verifier.py tests\test_server_releases.py tests\test_release_check.py tests\test_webui.py -q`

## v3.8.1 - 2026-05-16

### Fixed
- Release Export now records a signed sidecar payload hash for `release-signoff.json`, and `verify-release` fails if signed display fields such as `signed_by` or `signed_at` are tampered after ZIP creation.
- `verify-release` now inspects raw ZIP central-directory names and treats backslash entries as blocking path-safety failures instead of normalizing them to POSIX paths.

### Verified
- `python -m pytest tests\test_release_verifier.py tests\test_server_releases.py tests\test_release_check.py::test_v38_release_zip_verifier_smoke -q`

## v3.8.0 - 2026-05-15

### Added
- Release ZIP verifier module and `python -m song_agent.cli verify-release <zip>` CLI for portable, workspace-independent Release ZIP validation.
- Verification reports with human output, `--json`, `--report-out`, `--strict`, `--require-audio`, `--require-stems`, ZIP size, uncompressed size, entry count, path safety, duplicate entry, manifest/files/hash, signoff hash, track core artifact, MIDI/WAV header, stems, and redaction checks.
- release-check v3.8 smoke that copies a Release ZIP into a clean external directory and verifies failure cases for hash mismatch, dangerous entries, duplicate entries, spoofed `manifest.zip.entries`, redaction pollution, and ZIP bomb metadata.

### Fixed
- Release Export now sanitizes copied JSON/TXT track files before packaging, preventing local Project paths from leaking into portable Release ZIPs.

### Verified
- `python -m pytest tests\test_release_verifier.py tests\test_cli_verify_release.py tests\test_release_check.py tests\test_release_export.py tests\test_server_releases.py -q`

## v3.7.1 - 2026-05-15

### Fixed
- Release Signoff now binds to the final Release Export manifest after `release-signoff.json` has been written and the Release ZIP has been rebuilt, so the signoff record, disk manifest, and ZIP-contained manifest agree on `export_manifest_hash`.
- Release Export manifest ZIP metadata no longer writes the ZIP's own SHA back into `manifest.json`, avoiding self-referential manifest/ZIP hash drift.
- Batch stem audio completion now counts `skipped` stems as terminal when updating batch item stem audio progress, reducing release-check flakiness around stem audio waits.

### Verified
- `python -m pytest tests\test_server_releases.py tests\test_release_export.py tests\test_release_check.py tests\test_batch_stems.py -q`

## v3.7.0 - 2026-05-15

### Added
- Release Workspace persistence under `.musicforge/releases/<release-id>/` for multi-track EP/album/demo-pack assembly from Project Delivery QA and Signoff-approved Final Exports.
- Release Store, Release QA, Release Export, Release ZIP, and Release Signoff flows with track ordering, project snapshot refresh, stale guards, signed-release mutation blocking, reset history, and path-safe ZIP creation.
- Release APIs plus Project `release-targets` and `add-to-release` endpoints.
- Studio top-level Releases workspace and Project Final Export `Add to Release` controls.
- release-check v3.7 smoke covering multi-project release assembly, QA, export, ZIP download, signoff, signed mutation blocking, stale Project artifact detection, raw Release JSON redaction, and ZIP metadata/path safety.

### Scope
- Release Workspace is a local packaging and audit layer only. It does not rebuild Project Final Exports, change Project final versions, upload releases, call providers, auto-sign, or publish to external stores.

### Verified
- `python -m pytest tests\test_releases.py tests\test_release_qa.py tests\test_release_export.py tests\test_server_releases.py tests\test_webui.py -q`

## v3.6.1 - 2026-05-15

### Fixed
- Delivery QA now enforces a built-in required Final Export baseline instead of trusting `manifest.files` alone. `manifest.json`, `README.txt`, `project-export.json`, `song-plan.json`, and `song.mid` must exist even if a polluted manifest removes those entries.
- Delivery QA now scans the raw Final Export manifest for sensitive values before returning a sanitized report, so polluted fields such as `zip.path = C:\...` fail `redaction_scan`.
- Final Export ZIP metadata no longer writes a local absolute `zip.path` into `manifest.json` or the ZIP-contained manifest.

### Verified
- `python -m pytest tests\test_delivery_qa.py tests\test_server_delivery_qa.py tests\test_final_export.py tests\test_release_check.py -q`

## v3.6.0 - 2026-05-15

### Added
- Project-level Delivery QA Reports that verify final version selection, Final Export manifest consistency, required artifact presence, artifact path safety, ZIP integrity, review sprint closeout/signoff alignment, and delivery payload redaction.
- Delivery Signoff records with normal/force signoff, required override reasons, duplicate-sign protection, reset history, and project events.
- Delivery QA and Signoff APIs plus Studio Final Export Delivery QA controls for refresh, sign, force sign, reset, checks, artifacts, and ZIP state.
- Project Export and Final Export manifest summaries for delivery QA and delivery signoff.
- release-check v3.6 smoke covering failed QA before ZIP, successful QA/signoff, duplicate signoff rejection, reset history, stale ZIP detection, polluted ZIP failure, export summaries, final export summaries, and redaction.

### Scope
- Delivery QA is a local verification and audit layer only. It does not rebuild Final Export, rebuild ZIPs, call providers, apply candidates, change project final version, or upload anything.

### Verified
- `python -m pytest tests\test_delivery_qa.py tests\test_server_delivery_qa.py tests\test_final_export.py tests\test_projects.py tests\test_webui.py tests\test_server_auth.py tests\test_release_check.py -q`

## v3.5.1 - 2026-05-15

### Fixed
- Closeout no longer treats the project `latest_version_id` as a delivery-confirmed final version. A Sprint with resolved tasks but no applied candidate version, selected version, or final version now fails the `missing_applied_version` gate and normal close returns 409.

### Verified
- `python -m pytest tests\test_review_sprint_closeout.py tests\test_server_review_sprint_closeout.py tests\test_release_check.py -q`

## v3.5.0 - 2026-05-15

### Added
- Review Sprint Closeout Reports with gate checks for open/stale tasks, blocking conflicts, pending/failed Action Queue items, stale recommendations or Judge Reports, metrics readiness, and missing applied/selected versions.
- Sprint Signoff Records written separately from closeout reports, including forced-close audit metadata, selected version, closeout hash, acknowledged blockers, and acknowledged warnings.
- Close Sprint now refreshes closeout and returns 409 when the gate fails unless `force=true` is supplied with a non-empty `override_reason`.
- Closeout and Signoff APIs plus Studio Review Sprints controls for refreshing closeout, normal close, force close, and signoff display.
- Project Export, Final Export, Sprint Metrics, Project Review Metrics, and release-check now include compact closeout/signoff summaries.

### Scope
- Closeout is a local gate and audit layer only. It does not apply candidates, resolve tasks, call providers, auto-close Sprints, create final exports, or publish anything.

### Verified
- `python -m pytest tests\test_review_sprint_closeout.py tests\test_server_review_sprint_closeout.py tests\test_review_sprints.py tests\test_projects.py tests\test_final_export.py tests\test_review_sprint_metrics.py tests\test_webui.py -q`

## v3.4.1 - 2026-05-15

### Fixed
- Final Export review judge summaries now use `review_metrics_summary.latest_sprint_id` to select the matching Sprint judge summary in multi-Sprint projects.
- Project Export and Sprint Metrics now re-evaluate Judge Report stale state instead of reading raw `judge-report.json` as completed.
- Judge Report source hashes no longer become stale solely because a candidate was manually applied; content changes still mark the report stale.

### Verified
- `python -m pytest tests\test_final_export.py tests\test_projects.py tests\test_review_judge.py tests\test_review_sprint_metrics.py -q`

## v3.4.0 - 2026-05-14

### Added
- Provider Judge reports for ReviewTask candidates with strict JSON validation, source hashing, stale detection, per-candidate fit/precision/musicality/novelty/risk/confidence scores, and sanitized provider usage.
- ReviewTask Judge Report APIs plus Sprint Judge Summary get/refresh APIs.
- Decision Reports, manual apply metadata, Project Compare, Project Export, Final Export, and provider usage now include compact judge summaries.
- Review Sprint Action Queues can include `refresh_judge_report` provider-safe items; they remain skipped unless `include_provider=true` is supplied.
- Sprint Metrics and Project Review Metrics now include judge task counts, stale judge counts, judge tokens, local/judge disagreement, high-risk candidate counts, and judge apply match rate.
- Studio Review Workbench and Review Sprints now expose Judge Report, Judge Summary, provider-safe queue rows, and advisory/manual-apply wording.
- release-check now includes a v3.4 smoke covering task judge, sprint judge, queue default skip/provider opt-in, manual apply provenance, metrics, export/final export, usage, and redaction.

### Scope
- Provider Judge is advisory only. It does not generate candidates, apply candidates, resolve ReviewTasks, close ReviewSprints, or override manual decisions.

### Verified
- `python -m pytest tests\test_review_judge.py tests\test_server_review_judge.py tests\test_review_sprint_actions.py tests\test_server_review_sprint_actions.py tests\test_review_sprint_metrics.py tests\test_server_review_sprint_metrics.py tests\test_webui.py tests\test_release_check.py -q`

## v3.3.1 - 2026-05-14

### Fixed
- Final Export review metrics now use `review_metrics_summary.latest_sprint_id` to select the matching Sprint metrics summary, so multi-Sprint exports no longer mix the latest Sprint ID/readiness with an older Sprint's completion, quality delta, or warnings.

### Verified
- `python -m pytest tests\test_final_export.py tests\test_server_review_sprint_metrics.py tests\test_release_check.py -q`

## v3.3.0 - 2026-05-14

### Added
- Review Sprint Metrics Reports with task status, candidate funnel, recommendation adoption, Action Queue execution, provider usage, manual decision, quality delta, and readiness summaries.
- Project Review Metrics with project-level sprint totals, provider tokens, applied candidate counts, latest readiness, and quality trend.
- Metrics APIs for Sprint get/refresh and Project get/refresh, with cached derived JSON files and refresh events.
- Studio Review Sprints Dashboard panel plus Project Review Metrics summary.
- Project Export and Final Export now include compact review metrics summaries without exporting raw provider prompts, local paths, or full metrics reports.
- release-check now includes a v3.3 smoke covering dashboard metrics, project metrics, export/final export summaries, provider usage, manual apply metrics, quality delta, readiness, and redaction.

### Scope
- v3.3.0 only reads existing Review Sprint/Task/Candidate/Queue/provider/quality data and writes derived metrics reports. It does not auto-apply, auto-resolve, auto-close, or call provider judgment.

### Verified
- `python -m pytest tests\test_review_sprint_metrics.py tests\test_server_review_sprint_metrics.py tests\test_webui.py -q`

## v3.2.1 - 2026-05-14

### Fixed
- Review Sprint Action Queue runs no longer leave a queue stuck in `running` when provider-safe items are skipped because `include_provider=true` was not supplied.

### Verified
- `python -m pytest tests\test_review_sprint_actions.py tests\test_server_review_sprint_actions.py tests\test_release_check.py -q`

## v3.2.0 - 2026-05-14

### Added
- Review Sprint Action Queues that convert Recommendation Reports into persisted, auditable queue items with statuses, safety classes, event streams, and stale report hashes.
- Action Queue APIs for create/list/detail/run/archive, including selected-item execution, completed-item idempotency, provider opt-in, and queue-level event history.
- Safe Action Queue execution for saving recommended Context Packs, generating task-scoped local/provider candidates, refreshing Decision Reports, and refreshing sprint conflicts/recommendations.
- Studio Review Sprints Action Queue panel with queue creation, safe selection, provider authorization, run controls, manual-required rows, and queue summaries.
- Project Compare, Project Export, Final Export, and review candidate apply metadata now include compact Review Sprint Action Queue provenance.
- release-check now includes a v3.2 smoke covering queue creation, safe local/context execution, provider default skip, provider opt-in, Decision Report refresh, manual apply provenance, export/final export, stale recommendation blocking, stale context blocking, usage, and redaction.

### Scope
- v3.2.0 still does not auto-apply candidates, auto-resolve tasks, auto-close sprints, or create final exports automatically. Provider queue items remain skipped unless explicitly allowed for that run.

### Verified
- `python -m pytest tests\test_review_sprint_actions.py tests\test_server_review_sprint_actions.py tests\test_release_check.py tests\test_webui.py -q`

## v3.1.0 - 2026-05-14

### Added
- Review Sprint Recommendation Reports with deterministic task ordering, per-task recommended actions, scoring reasons, conflict awareness, and context pack previews.
- Review Sprint recommendation APIs for GET, refresh, and manual Context Pack save from a recommendation.
- Studio Review Sprints recommendations panel with next-action summaries, manual-apply warning, refresh, and Save Context Pack controls.
- Project Compare, Project Export, Final Export, and edit metadata now include Review Sprint recommendation summaries without exporting full context candidate details.
- release-check now includes a v3.1 smoke covering recommendation refresh, Context Pack save, stale source rejection, no-op recommendation APIs, provider generation with saved context, apply provenance, export, and final export.

### Scope
- v3.1.0 does not auto-apply candidates, auto-resolve tasks, or auto-generate candidates. Recommendations are advisory and all execution still requires explicit user action.

### Verified
- `python -m pytest tests\test_review_sprint_recommendations.py tests\test_review_sprints.py tests\test_server_review_sprint_recommendations.py tests\test_server_review_sprints.py tests\test_webui.py -q`

## v3.0.0 - 2026-05-13

### Added
- Review Sprints for organizing multiple ReviewTasks with ordered task refs, status/count summaries, conflict reports, and event history.
- Review Sprint APIs for create/list/detail, task add/remove/reorder, refresh/close/archive, conflict refresh, and batch local/provider candidate generation.
- Studio Review Sprints workspace plus Review Workbench add-to-sprint controls.
- Project Compare, Project Export, Final Export, and provider usage reports now include Review Sprint provenance and sprint rollups.
- release-check now includes a v3.0 smoke covering sprint conflicts, batch local/provider candidates, artifact path pollution, single-candidate apply, export, final export, and usage.

### Scope
- Review Sprints never batch-apply edits. They organize ReviewTasks and create candidates only; every apply still goes through the existing one-task, one-candidate ReviewTask guard.

### Verified
- `python -m pytest tests\test_review_sprints.py tests\test_server_review_sprints.py tests\test_final_export.py tests\test_project_compare.py tests\test_server_review_tasks.py tests\test_webui.py -q`

## v2.9.0 - 2026-05-13

### Added
- Provider review candidates for Review Tasks using the new `provider-review-candidates` prompt template and existing constrained ProviderEditPatch validation.
- Decision Report storage at `review-tasks/<task-id>/decision-report.json`, with local/provider ranking, source breakdown, risk flags, and manual-apply recommendation.
- Review Workbench controls for generating provider candidates, refreshing the Decision Report, and seeing provider/local source badges.
- Project Compare, Project Export, Final Export, and provider usage reports now include provider review candidate provenance and decision summaries.
- release-check now includes a v2.9 mock-provider smoke covering provider candidates, decision reports, candidate MIDI, artifact path pollution, apply, exports, and usage reporting.

### Scope
- Provider output is only a candidate source and explanation aid. It cannot auto-apply, cannot bypass local validation/scoring, and cannot replace the one-candidate-per-task apply guard.

### Verified
- `python -m pytest tests\test_review_tasks.py tests\test_server_review_tasks.py tests\test_webui.py -q`

## v2.8.0 - 2026-05-13

### Added
- Review Workbench for turning audition reviews into persistent Review Tasks with status, target, marker-coordinate, and follow-up provenance.
- Local review candidates with conservative, balanced, and bold strategies, ranking, validator/quality summaries, MIDI download, and optional WAV rendering through the local renderer.
- Candidate apply creates one official child Project Version from parent + candidate intents, not from cached candidate SongPlan files.
- ReviewTask lifecycle APIs for generate candidates, apply one candidate, resolve, mark needs_more_work with a linked follow-up task, and archive.
- Studio Review Workbench tab plus Review Board actions to create Review Tasks from audition reviews.
- Project Compare, Project Export, Final Export, and release-check now include review task and selected candidate provenance.

### Scope
- v2.8.0 keeps provider review candidates deferred. The completed workflow is local-first and deterministic.

### Verified
- `python -m pytest tests\test_review_tasks.py tests\test_server_review_tasks.py tests\test_server_review_edits.py tests\test_webui.py -q`

## v2.7.1 - 2026-05-12

### Fixed
- Review Edit now interprets audition review marker beats relative to the audition range start, so custom and changed_sections audition markers target the correct parent SongPlan section.

### Verified
- `python -m pytest tests\test_review_edits.py tests\test_server_review_edits.py -q`

## v2.7.0 - 2026-05-12

### Added
- Review-driven edit planning that maps sanitized audition review notes, status, rating, tags, and markers into safe local `EditIntent` objects.
- Review edit preview API that stores `review-edits/<review-edit-id>/review-edit.json`, candidate SongPlan, validator report, and summary.
- Review edit create API that produces a non-destructive child Project Version and records review provenance in edit metadata.
- Optional provider review edit preview route using a dedicated `provider-review-edit-intent` template and existing ProviderEditPatch validation.
- Audition review to Context Pack API for turning favorite/high-value audition assets into reusable context.
- Studio Review Board Next Actions: Preview Edit, Create Local Edit, Provider Preview, and Create Context Pack.
- Project Compare, Project Export, Final Export, and release-check now include review edit provenance summaries.

### Scope
- v2.7.0 is user-triggered only. Reviews do not automatically modify versions, and review text is never executed as arbitrary patch operations.

### Verified
- `python -m pytest tests\test_review_edits.py tests\test_server_review_edits.py tests\test_webui.py -q`

## v2.6.0 - 2026-05-12

### Added
- Audition Review Board for editor auditions with rating, status, favorite, notes, tags, marker metadata, filtering, and summary counts.
- Review marker APIs with beat bounds, supported kinds/severity, event logging, and sensitive text redaction.
- API to save an audition slice as a Creative Asset by rebuilding asset content from the audition SongPlan rather than copying cached audio or arbitrary paths.
- Studio review controls for scoring auditions, adding markers, filtering favorites, and saving audition motifs into the asset library.
- Audition review summary now flows into editor apply metadata, Project Compare, Project Export, Final Export summaries, and release-check.
- release-check now includes a v2.6 audition review smoke covering review redaction, markers, asset creation, apply metadata, compare, and project export.

### Scope
- v2.6.0 keeps review as metadata only; it does not modify preview patches, parent versions, or generated music content, and it does not include realtime waveform editing or automatic AI review.

### Verified
- `python -m pytest tests\test_editor_review.py tests\test_server_editor_review.py tests\test_server_editor_audition.py tests\test_webui.py -q`

## v2.5.1 - 2026-05-12

### Fixed
- Preview WAV rendering now recomputes the preview plan from the parent version SongPlan and stored editor patch before regenerating MIDI and WAV.
- Preview audio no longer trusts cached `editor-previews/<preview-id>/song.mid` or `song-plan.json`, keeping A/B playback aligned with the version that Apply would create.

### Verified
- `python -m pytest tests\test_server_editor_audition.py tests\test_editor_audition.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.5.0 - 2026-05-12

### Added
- Editor Preview audio status and render/download support for Preview WAV.
- Project Version parent WAV render/download routes for A/B listening in Studio.
- Editor Audition cache under Project editor previews with parent/preview sources, full song/section/changed/custom ranges, and all/solo/mute track modes.
- Audition MIDI download and optional WAV rendering using the existing local renderer configuration.
- Studio Project Editor A/B audio controls and Audition panel.
- Audition summary now flows into visual editor apply metadata, Project Compare, Project Export, Final Export summaries, and release-check.
- release-check now includes a v2.5 editor audition smoke covering parent/preview auditions, solo MIDI, renderer-missing audio error, apply metadata, compare, and project export.

### Scope
- v2.5.0 keeps audition artifacts as local editor-preview cache only; it does not copy temporary audition WAVs into Final Export and does not add realtime browser mixing.

### Verified
- `python -m pytest tests\test_webui.py tests\test_editor_audition.py tests\test_server_editor_audition.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.4.1 - 2026-05-12

### Fixed
- Multi-track template draft insert now validates `lane_mappings[].lane_id` against the selected template before generating operations.
- Unknown template lane IDs now return a clear `400 Unknown template lane_id: ...` instead of the generic no-notes conflict.

### Verified
- `python -m pytest tests\test_editor_templates.py tests\test_server_editor_templates.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.4.0 - 2026-05-11

### Added
- Editor Template Store for reusable section and track templates under `.musicforge/editor-templates/`.
- MultiTrackClip support for extracting full Project Version sections into role-based lanes.
- Section Template and Track Template APIs, including source hash summaries and hide/delete routes.
- Multi-track template mapping and draft insert APIs that reuse the visual editor patch engine and support current Patch Queue state.
- Studio Editor Templates panel, Project Editor Template Browser, Save Section Template, Save Track Template, and Draft Insert Template controls.
- Template provenance now flows through editor preview apply, Project Compare, Project Export, Final Export, and release-check.
- release-check now includes a v2.4 editor template smoke covering save, mapping, draft, preview, apply, compare, project export, and final export.

### Scope
- v2.4.0 intentionally keeps template reuse local and deterministic; it does not add DAW-style drag editing, realtime playback, audio-to-MIDI, MP3 import, AI arranger solving, or mixing automation.

### Verified
- `python -m pytest tests\test_editor_templates.py tests\test_server_editor_templates.py tests\test_server_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.3.2 - 2026-05-11

### Fixed
- Clip provenance group IDs now include the actual generated insert operations, so repeated inserts of the same clip at the same position but with different transpose/velocity/replace options remain separate audit records.

### Verified
- `python -m pytest tests\test_server_editor_clips.py tests\test_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.3.1 - 2026-05-11

### Fixed
- Clip `replace_range` drafts can now receive the current Project Editor Patch Queue and compute replacement deletes against the accumulated draft state, avoiding duplicate deletion of base note IDs.
- Studio clip provenance is now derived from `clip_group_id` on queued operations, so normal manual edits do not clear existing clip insert metadata.
- Editor clip draft responses now include a `combined_patch` for clients that want to preview/apply the accumulated queue in one request.

### Verified
- `python -m pytest tests\test_editor_clips.py tests\test_server_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.3.0 - 2026-05-11

### Added
- EditorClip layer for reusable note fragments from Assets, Reference MIDI slices, and Project Version sections/ranges.
- Project Editor APIs for listing reusable clips and creating nonpersistent clip insert drafts.
- Studio Clip Browser with overlay/replace insert modes, transpose, velocity scaling, and quantize controls.
- Clip insert metadata now flows through Editor Preview apply, Project Compare, Project Export, and Final Export summaries.
- release-check now includes a v2.3 editor clip insert smoke covering draft, preview, apply, compare, and export metadata.

### Scope
- v2.3.0 intentionally keeps clip insertion to a single target track and does not add audio-to-MIDI, MP3 import, automatic BPM/key detection, or a full DAW arranger.

### Verified
- `python -m pytest tests\test_editor_clips.py tests\test_server_editor_clips.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.2.2 - 2026-05-10

### Fixed
- Draft editor views now include notes created by `add_note` and `duplicate_section copy_notes` as visible `derived-note-*` entries.
- Derived draft notes are shown for audition/inspection but marked non-editable until the patch is previewed/applied or cleared.
- release-check now verifies the HTTP draft flow includes a derived note created during the same patch.

### Verified
- `python -m pytest tests\test_editor_view.py tests\test_server_editor_draft.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.2.1 - 2026-05-10

### Fixed
- Draft editor views now preserve base section and track identities after structural edits, so continued draft edits target the visible base section or track instead of a re-numbered array position.
- Newly added or duplicated draft-only sections/tracks are marked as derived and non-editable in the Studio controls until the user previews/applies or clears the patch.
- release-check now exercises the Project Editor draft flow through real HTTP calls, including delete-section followed by continued editing of the visible section ID.

### Verified
- `python -m pytest tests\test_editor_view.py tests\test_song_editor_structure.py tests\test_server_editor_draft.py tests\test_server_editor_structure.py tests\test_server_edits.py::test_project_editor_apply_ignores_polluted_preview_song_plan tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.2.0 - 2026-05-10

### Added
- Editor View Model for arranger timeline and piano-roll rendering, including section blocks, track lanes, note rectangles, pitch range, and note-to-section assignment.
- Nonpersistent Editor Draft API at `POST /api/projects/<project-id>/versions/<version-id>/editor-draft`, with optional view/diff output and no preview/run/project writes.
- Studio Project Editor now includes Arranger Timeline, Piano Roll, Inspector controls, Patch Queue, Undo/Redo, and Draft Refresh.
- release-check now includes a v2.2 interactive editor smoke covering draft, preview, apply, and metadata continuity.

### Scope
- v2.2.0 intentionally does not add a full DAW, realtime browser synthesizer, recording, audio-to-MIDI, drag editing, multi-user collaboration, or cloud storage.

### Verified
- `python -m pytest tests\test_editor_view.py tests\test_server_editor_draft.py tests\test_song_editor.py tests\test_song_editor_structure.py tests\test_server_editor_structure.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.1.2 - 2026-05-09

### Fixed
- Visual Editor note operations now resolve `note-*` IDs from the base editor state's `track_id` plus note identity, so earlier track structure edits in the same patch cannot make later note operations fail.
- Note identity is refreshed after `update_note`, `delete_notes`, `move_notes`, `transpose_notes`, `quantize_notes`, and `scale_velocity` within a patch.
- Section structure operations now keep base note identities aligned when notes are shifted, cropped, trimmed, or remapped by section movement.

### Verified
- `python -m pytest tests\test_song_editor_structure.py -q`
- `python -m pytest tests\test_song_editor.py tests\test_song_editor_structure.py tests\test_editor_previews.py tests\test_server_editor_structure.py tests\test_server_edits.py tests\test_projects.py tests\test_project_compare.py tests\test_final_export.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.1.1 - 2026-05-09

### Fixed
- Visual Editor patch operations now resolve `section-*` and `track-*` IDs against the base editor state, so structure edits earlier in the same patch cannot retarget later operations to the wrong section or track.
- Track identity now follows `rename_track` within the same patch, while deleted base IDs become unavailable for later operations.

### Verified
- `python -m pytest tests\test_song_editor_structure.py tests\test_editor_previews.py tests\test_server_editor_structure.py tests\test_server_edits.py::test_project_editor_apply_ignores_polluted_preview_song_plan -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.1.0 - 2026-05-08

### Added
- Visual Editor structure patch operations for add/duplicate/delete/resize/move section and add/duplicate/delete/rename track.
- Section timeline normalization with deterministic note shifting, copying, cropping, and bounds checks.
- Editor Preview History APIs for listing previews, reading patch summaries, and cleaning old unapplied previews.
- Studio structure editor controls and Preview History management.
- Project diff, Project Compare, Project Export, Final Export, and release-check now surface structure edit summaries.

### Scope
- v2.1.0 intentionally does not add a full DAW, piano-roll drag editing, MIDI import merge, arranger solver, or realtime audio playback.

### Verified
- `python -m pytest tests\test_song_editor.py tests\test_song_editor_structure.py tests\test_editor_previews.py -q`
- `python -m pytest tests\test_server_editor_structure.py tests\test_server_auth.py tests\test_projects.py tests\test_project_compare.py tests\test_final_export.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.0.1 - 2026-05-08

### Fixed
- Visual Editor Apply now writes and renders the recomputed editor patch result, instead of trusting the persisted preview `song-plan.json`.
- Editor Apply records a warning when a preview plan differs from the recomputed patch result, preserving the official child version from the trusted patch path.

### Verified
- `python -m pytest tests\test_server_edits.py::test_project_editor_apply_ignores_polluted_preview_song_plan tests\test_server_edits.py::test_project_editor_preview_apply_creates_manual_editor_version tests\test_song_editor.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v2.0.0 - 2026-05-08

### Added
- Visual SongPlan Editor for Project Versions with editor state, stable section/track/note IDs, patch preview, MIDI preview, and apply-as-version.
- Editor Patch engine for safe section chord/lyrics edits, track instrument edits, note add/update/delete/move/transpose/quantize/velocity operations.
- Persistent Project editor previews under `.musicforge/projects/<project>/editor-previews/`.
- Manual editor apply creates a new Project Version with `manual_editor_edit` lineage, `editor-patch.json`, `edit-metadata.json`, validator report, summary, and MIDI render.
- Studio Project Editor tab for local visual/manual SongPlan edits.
- Project diff, Project Compare, Project Export, and release-check now surface visual editor metadata.

### Scope
- v2.0.0 intentionally does not add a full DAW, browser synthesizer, realtime audio engine, recording, audio-to-MIDI, MP3/FLAC import, or section/track structural rearranging.

### Verified
- `python -m pytest tests\test_song_editor.py tests\test_server_edits.py tests\test_projects.py tests\test_project_compare.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.9.1 - 2026-05-08

### Fixed
- Context Pack creation is now protected by a store-level `RLock` and atomic directory reservation, preventing duplicate `pack-*` IDs under concurrent API requests.
- Context Pack creation cleanup now only removes the current thread's incomplete reservation, avoiding cross-thread directory deletion during failures.
- Library search now prefers newer items when score, favorite status, and quality score are tied.

### Verified
- `python -m pytest tests\test_context_packs.py tests\test_library_index.py tests\test_server_library_context.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.9.0 - 2026-05-08

### Added
- Local Library Index for searchable Creative Assets and References with deterministic scoring and score breakdowns.
- Library search and recommendation APIs for local, explainable retrieval without embeddings or external services.
- Persistent Context Packs under `.musicforge/context-packs/` with stale/hidden source validation.
- `context_pack_id` support for jobs, Project versions, variations, local/provider edits, provider previews, candidate groups, and Prompt A/B.
- Project Export and Final Export now include sanitized Context Pack summaries.
- Studio Library workflow with search, recommendation, Context Pack save/apply preview, and context selectors.
- Release-check now covers the v1.9 library/context-pack workflow.

### Scope
- v1.9.0 intentionally does not add vector databases, embeddings, audio fingerprinting, MP3, audio-to-MIDI, or automatic application of recommended context.

### Verified
- `python -m pytest tests\test_library_index.py tests\test_context_packs.py tests\test_server_library_context.py tests\test_projects.py::test_export_project_collects_context_pack_summaries tests\test_final_export.py::test_final_export_manifest_includes_context_pack_summary tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.8.0 - 2026-05-08

### Added
- Reference analysis reports for imported PCM WAV, MIDI, lyrics text, and style-note references.
- WAV summaries now include duration, sample rate, channels, sample width, peak, RMS, silence ratio, loudness hint, and bounded waveform envelopes.
- Lightweight Standard MIDI parser for format 0/1, PPQ, tempo, time signature, running status, program changes, note pairing, and role hints.
- MIDI reference slice suggestions, fixed-path slice MIDI/WAV previews, and note-based Creative Asset creation from slices.
- Studio References analysis tools with Analyze, MIDI slice generation, preview render/download, WAV envelope, MIDI track summaries, and slice asset actions.
- Project export, Final Export, provider reference summaries, and release-check now include bounded, sanitized analysis summaries.

### Scope
- v1.8.0 intentionally does not add MP3 import, audio-to-MIDI, audio transcription, BPM/key auto-detection, or heavy audio-analysis dependencies.

### Verified
- `python -m pytest tests\test_midi_analysis.py tests\test_reference_analysis.py tests\test_server_reference_analysis.py tests\test_server_auth.py tests\test_projects.py::test_export_project_includes_redacted_reference_refs tests\test_final_export.py::test_final_export_includes_sanitized_reference_refs_without_original_files tests\test_webui.py tests\test_references.py tests\test_provider_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.7.2 - 2026-05-08

### Fixed
- Value-level redaction now covers arbitrary Windows drive paths such as `D:\Music\...`.
- Value-level redaction now covers UNC and network-share style paths such as `\\server\share\...` and `//server/share/...`.
- Reference summaries, provider prompt summaries, Project export, Final Export, and release-check now share the expanded local-path redaction coverage.

### Verified
- `python -m pytest tests\test_references.py tests\test_projects.py tests\test_final_export.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.7.1 - 2026-05-08

### Fixed
- Reference metadata summaries now redact sensitive values embedded in free-text fields such as `source_note`, `license_note`, `text_excerpt`, and descriptions.
- Project export and Final Export now apply value-level redaction to reference summaries even when local artifact JSON was polluted.
- Reference import now rejects control-character and unsafe quoted filenames, and legacy/polluted filenames are safely downgraded before download.
- File downloads now emit sanitized `Content-Disposition` filenames with RFC 5987 `filename*` support.
- Reference import now rejects oversized request bodies before reading and base64-decoding them.

### Verified
- `python -m pytest tests\test_references.py tests\test_server_references.py tests\test_projects.py tests\test_final_export.py tests\test_assets.py tests\test_server_assets.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.7.0 - 2026-05-08

### Added
- Local Reference Library under `.musicforge/references/` for safe WAV, MIDI, lyrics text, and style-note imports.
- Reference import validates extension, header/UTF-8 content, size limits, path-like filenames, and duplicate SHA-256 content.
- Reference APIs for import/list/detail/update, hide/favorite/delete, fixed-path original download, Project link/unlink, and reference-to-asset conversion.
- `reference_refs` for jobs, Project versions, variations, local/provider edits, provider previews, candidate groups, and Prompt A/B.
- Project export and Final Export now include sanitized reference summaries without copying original reference files into final delivery bundles or ZIPs.
- Studio References workspace with safe import, search/filter, metadata editing, Project linking, asset conversion, and reference selectors.
- Release-check now covers reference import, dedupe, usage tracking, Project export, Final Export, and redaction behavior.

### Scope
- v1.7.0 intentionally does not add MP3 import, audio transcription, audio-to-MIDI, waveform analysis, BPM detection, or key detection.

### Verified
- `python -m pytest tests\test_references.py tests\test_server_references.py tests\test_server_auth.py -q`
- `python -m pytest tests\test_projects.py tests\test_final_export.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.6.1 - 2026-05-07

### Fixed
- Project export now redacts sensitive keys from asset reference `source` and `content_summary` metadata even if local artifact JSON was polluted.
- Final Export now applies the same secondary asset reference redaction before writing manifest summaries and `assets/<asset-id>.json`.

### Verified
- `python -m pytest tests\test_projects.py tests\test_final_export.py -q`
- `python -m pytest tests\test_assets.py tests\test_server_assets.py tests\test_projects.py tests\test_final_export.py tests\test_server_auth.py -q`
- `python -m song_agent.cli release-check`

## v1.6.0 - 2026-05-07

### Added
- Local Creative Asset Library under `.musicforge/assets/` with per-asset metadata, source fragments, events, MIDI preview, and optional WAV preview.
- Asset extraction from completed jobs, Project versions, and provider edit candidates.
- Asset references for job generation, Project version creation, variation, local/provider edit, provider previews, candidate groups, and Prompt A/B.
- Studio Assets workspace with search/filter, metadata editing, hide/favorite/delete, MIDI/WAV preview controls, extraction buttons, and asset selectors.
- Project export and Final Export now include sanitized asset reference summaries.
- Release-check now covers creative asset extraction, reuse, usage tracking, Project export, and Final Export asset refs.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.5.1 - 2026-05-07

### Fixed
- Stale provider edit candidate groups now return `409` for candidate MIDI/WAV downloads and candidate/group re-render endpoints.
- Prompt A/B creation now rolls back already-created candidate groups if a later template fails, preventing orphaned usage and UI artifacts.

### Verified
- `python -m pytest tests\test_server_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.5.0 - 2026-05-07

### Added
- Provider edit candidates now render MIDI previews and expose safe candidate MIDI download URLs.
- Candidate WAV previews can be rendered when the local renderer is configured, with Studio playback controls.
- Provider usage reports aggregate jobs and candidate groups by model, operation, and prompt template, with optional local pricing.
- Lightweight Prompt A/B experiments generate multiple candidate groups from different prompt templates for manual comparison.
- Release-check now covers candidate audition artifacts, usage reporting, and Prompt A/B smoke behavior.

### Verified
- `python -m pytest tests\test_candidate_groups.py tests\test_server_edits.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.4.1 - 2026-05-07

### Fixed
- Provider candidate apply now writes explicit `candidate_group_id` and `candidate_id` fields into the official child version edit metadata.
- Candidate-derived versions remain traceable to their selected candidate even if the original candidate group review artifacts are deleted later.
- Release-check now verifies provider candidate metadata survives candidate group deletion.

### Verified
- `python -m pytest tests\test_server_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.4.0 - 2026-05-07

### Added
- Provider Edit Candidate Groups for generating, storing, ranking, applying, and deleting multiple provider edit candidates.
- Built-in `provider-edit-candidates` prompt template and OpenAI-compatible multi-candidate edit response support.
- Deterministic candidate scoring based on quality, validator status, provider confidence, novelty, and instruction fit.
- Project Candidate APIs and Studio Candidates tab for Generate Candidates, candidate review, Apply Candidate, and Delete Candidate Group.
- Project provider usage now includes candidate group generation usage in addition to applied provider edit versions.
- Release-check coverage for the v1.4 multi-candidate provider edit workflow.

### Verified
- `python -m pytest tests\test_candidate_groups.py tests\test_candidate_scoring.py tests\test_provider_edits.py tests\test_provider_client.py tests\test_prompt_templates.py tests\test_server_edits.py tests\test_server_auth.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.3.1 - 2026-05-07

### Fixed
- Removed a duplicate Project edit-preview route branch from the Studio server router.
- Provider edit previews now record a parent song-plan source hash and reject stale applies after the parent version changes.
- Provider edit previews can no longer be applied more than once.
- OpenAI-compatible provider edit responses now preserve returned `usage` token counts and request ids for preview/apply audit records.
- Provider edit apply usage now reuses preview usage data instead of always writing zero-token placeholders when the provider supplies usage.

### Verified
- `python -m pytest tests\test_provider_client.py tests\test_provider_edits.py tests\test_server_edits.py tests\test_server_auth.py tests\test_webui.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.3.0 - 2026-05-07

### Added
- Prompt Template Store with built-in provider edit templates, local overrides under `.musicforge/prompt-templates.json`, and Studio controls.
- Provider edit patch schema for constrained natural-language edits, including operation, chord, target, size, and secret/path validation.
- Provider-backed Project edit preview/apply APIs that keep previews out of official Project versions until applied.
- Studio Provider Edit workflow with Generate Preview and Apply Preview controls.
- Provider edit usage/audit records and project-level usage summaries without storing API keys.
- Release-check coverage for v1.2.1 hardening and v1.3 provider edit smoke.

### Fixed
- Final Export rebuilds now invalidate stale `final-export.zip` files and do not carry old ZIP manifest metadata forward.
- Edit preset payload validation now checks deeper nested data, size limits, secret-like fields, and merged intent validity.
- Project Compare handles missing left/right inputs, corrupt edit metadata, old versions, and missing artifacts without server errors.
- Studio Compare uses responsive panels and horizontal table scrolling for long text and narrow screens.

### Verified
- `python -m pytest tests\test_prompt_templates.py tests\test_provider_edits.py tests\test_provider_client.py tests\test_server_edits.py tests\test_server_projects.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.2.0 - 2026-05-06

### Added
- Edit preset library with built-in presets, local user presets under `.musicforge/edit-presets.json`, Studio preset apply/save controls, and Project edit preset metadata.
- Project version Compare API and Studio A/B review view with quality, gate, edit metadata, section, track, MIDI, and WAV availability.
- Safe Final Export ZIP generation and download, including ZIP sha256, size, and entry count recorded in the final export manifest.
- Project search and filters for name/description/version text, status, hidden projects, and variant type.
- Release-check coverage for the v1.2 workflow: preset edit, compare, final export, and ZIP entry safety.

### Verified
- `python -m pytest tests\test_edit_presets.py tests\test_project_compare.py tests\test_final_export.py tests\test_server_edits.py tests\test_server_projects.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v1.1.1 - 2026-05-06

### Fixed
- Section harmony edits now reject unsupported explicit payload chord names such as `Hmaj7` before writing `SongPlan.sections[].chords`.
- Instruction-parsed harmony chords are filtered through the supported local MIDI chord set, with empty results falling back to the safe default progression.

### Verified
- `python -m pytest tests\test_edits.py tests\test_server_edits.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.1.0 - 2026-05-06

### Added
- Local non-destructive Project edit workflow with `EditIntent`, target validation, deterministic section/track/lyrics/melody edits, and edit-derived child versions.
- Edit jobs that write `data/edit-metadata.json`, regenerate SongPlan/MIDI/validator/summary artifacts, and preserve parent run artifacts.
- Project edit APIs, edit target preview, job edit metadata API, Project diff edit/section/track summaries, and Studio Edit controls.
- Release-check edit smoke coverage for parent protection and child MIDI generation.

### Verified
- `python -m pytest tests\test_edits.py tests\test_server_edits.py tests\test_server_projects.py tests\test_server_auth.py tests\test_webui.py tests\test_release_check.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.0.2 - 2026-05-06

### Fixed
- Quality Gate `require_stems=True` now rejects stem manifests that do not cover all note-bearing SongPlan tracks, including empty manifests with matching source hashes.

### Verified
- `python -m pytest tests\test_project_quality.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.0.1 - 2026-05-06

### Fixed
- Final Export now rejects polluted stem manifest paths outside `runs/<job-id>/stems/` and skips the stem bundle instead of copying non-stem files.
- Quality Gate `require_stems=True` now validates that each note-bearing stem MIDI file exists and that manifest paths remain inside the job stems directory.

### Verified
- `python -m pytest tests\test_final_export.py tests\test_project_quality.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v1.0.0 - 2026-05-06

### Added
- Project version lineage with `parent_version_id`, `variant_type`, and `change_summary`.
- Project variation API for creating child versions from any existing version with a controlled request patch.
- Project Quality Gate configuration, per-version evaluation, evaluate-all, and final-version blocking with force override events.
- Final Export Bundle under `.musicforge/projects/<project-id>/final-export/` with manifest, README, Project export, SongPlan, MIDI, optional WAV, quality report, and non-stale stems.
- Studio Project controls for Variation, Quality Gate, Final Export, lineage columns, gate status, and per-version actions.
- Release-check final export smoke coverage.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli release-check`
- `python -m song_agent.cli doctor`
- Local single and multinode CLI smoke.
- Studio v1 page smoke; only `favicon.ico` 404 was observed.

## v0.9.1 - 2026-05-06

### Fixed
- CLI `--force` now removes stale `stems/` artifacts along with `data/`, `renders/`, and `logs/`.

### Verified
- `python -m pytest tests\test_cli.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli release-check`

## v0.9.0 - 2026-05-06

### Added
- Project workspace metadata under `.musicforge/projects/<project-id>/` with project state, versions, events, and export manifests.
- Project APIs for create/list/detail, version creation, existing-job import, selected/final version markers, diff, export, hide/unhide, and metadata-only delete.
- Studio Projects workspace with project list, version table, new version creation, existing job import, selected/final controls, compare, export JSON, and events.
- Batch CSV optional `project`, `version_name`, and `version_note` columns with automatic completed-job archival into Projects.
- Batch export fields for project/version links.

### Verified
- `python -m pytest -q`
- Project API/auth tests and Batch Project archival tests.

## v0.8.1 - 2026-05-06

### Fixed
- Stem manifests now include a SongPlan source hash and stale manifests are invalidated when `data/song-plan.json` changes.
- Job reruns and node retry now clear existing stem MIDI/WAV artifacts so regenerated songs cannot expose previous-version stems.
- Stem MIDI/WAV download routes now reject stale manifests before serving files.
- Partial stem-audio renders now report `partial_completed` instead of top-level `not_started`.

### Verified
- `python -m pytest tests\test_stems.py tests\test_server_stems.py tests\test_server_nodes.py tests\test_batch_stems.py -q`
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli release-check`

## v0.8.0 - 2026-05-06

### Added
- Stem manifest and per-track MIDI export under `runs/<job-id>/stems/`.
- Job APIs for listing stems, rendering MIDI stems, rendering stem WAV files, and downloading individual stem MIDI/WAV artifacts.
- Studio Stems tab with Render Stems, Render Stem Audio, per-track downloads, audio controls, and simple Solo/Mute actions.
- Batch stem rendering APIs for MIDI stems, stem audio, failed stem retry, and failed stem-audio retry.
- Batch item stem metadata and export fields for manifest path, stem count, completed stem audio count, and stem errors.
- Path-safe stem file access that resolves downloads from the manifest instead of trusting request paths.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli release-check`
- Local single and multinode CLI smoke.
- Job and batch stem API tests with fake WAV renderer.

## v0.7.1 - 2026-05-06

### Fixed
- Runtime Timeline and Quality views now infer quality metadata for legacy `song-plan.json` files without rewriting artifacts.
- `GET /api/jobs/<job-id>/quality` now returns a clear 409 while `song-plan.json` is not available.
- Validator views merge quality warnings with validator warnings, including when `validator-report.json` is missing.
- Quality analyzer false positives were tightened for instrumental detection, bass-root octave/passing-note cases, and hook repetition.
- Provider-backed SongPlan output now gets local quality inference when a provider omits the optional `quality` field.
- Studio Quality tab now shows a friendly pending message plus warning and critic summary blocks.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli release-check`
- Local quality API smoke for pending jobs and legacy SongPlan inference.

## v0.7.0 - 2026-05-06

### Added
- Compatible SongPlan quality metadata with motif, section intent, hook sections, warnings, and dimension scores.
- `song_agent.music_quality` analyzer for structure, melody, harmony, arrangement, and lyric-fit scoring.
- Quality-aware deterministic and multinode generation with lifted chorus melody, section energy/tension/density, and hook metadata.
- Critic reports now include quality issues, dimension scores, and summaries; repair can apply low-risk quality metadata fixes.
- Provider prompts and mock provider node outputs now describe energy, tension, density, role, transition, and hook candidates.
- `GET /api/jobs/<job-id>/quality` and Studio Quality tab for overall score, dimension scores, motif, section intents, and issues.
- Timeline view now includes section role, energy, tension, density, and hook markers.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- Local single CLI smoke with quality metadata.
- Local multinode CLI smoke with quality metadata.

## v0.6.2 - 2026-05-06

### Added
- Batch audio render APIs for `POST /api/batches/<batch-id>/render-audio` and `POST /api/batches/<batch-id>/render-failed-audio`.
- Batch item audio metadata: `audio_status`, `audio_path`, and `audio_error`.
- Batch export now includes WAV render status and path information.
- Studio Batch actions for Render Audio and Render Failed Audio, plus per-item audio status and WAV path columns.

### Fixed
- JSON artifacts are written with same-directory atomic replacement to avoid Studio polling or background runners reading partially written files.

### Verified
- `python -m pytest -q`
- Batch audio smoke for missing renderer, missing MIDI, partial success, retry failed audio, and export metadata.

## v0.6.1 - 2026-05-05

### Fixed
- Public unauthenticated `/api/info` no longer returns local filesystem paths when Studio auth is enabled.
- Authorized `/api/info` requests still return full local Studio metadata for the unlocked session.

### Verified
- `python -m pytest -q`
- Auth-mode `/api/info` smoke for unauthenticated and Bearer-authenticated requests.
- `python -m song_agent.cli release-check`

## v0.6.0 - 2026-05-05

### Added
- Studio access-token configuration with `--access-token` and `MUSICFORGE_ACCESS_TOKEN`.
- Startup protection that refuses non-loopback hosts without an access token.
- Bearer-token API authentication for jobs, provider, renderer, batch, artifacts, audio, and file-system actions.
- Public `/api/info` auth status that avoids returning sensitive config details.
- Studio access-token prompt using `sessionStorage`, authenticated fetch, and 401 lock-back behavior.
- `python -m song_agent.cli release-check` for local release safety checks.
- Tests for auth config, CLI startup protection, server auth, Studio auth UI, and release-check helpers.

### Verified
- `python -m pytest -q`
- localhost no-token Studio smoke.
- non-localhost no-token startup rejection.
- Bearer auth API smoke for missing, wrong, and correct tokens.
- `python -m song_agent.cli release-check`

## v0.5.0 - 2026-05-05

### Added
- Local audio renderer configuration under `.musicforge/renderer.json` with environment variable overrides.
- Renderer APIs for read, save, reset, and test.
- FluidSynth MIDI-to-WAV command builder using list argv and `shell=False`.
- Manual `POST /api/jobs/<job-id>/render-audio` to render `runs/<job-id>/renders/song.wav`.
- `GET /api/jobs/<job-id>/audio` for WAV playback/download.
- Audio artifact discovery and validator view audio metadata after successful render.
- Studio Renderer Settings form, Render Audio action, WAV download link, and `<audio controls>` playback.
- Fake-runner tests so automated validation does not require FluidSynth or a real SoundFont.

### Verified
- `python -m pytest -q`
- Local renderer API smoke with missing SoundFont error.
- Fake renderer smoke for `render-audio` and WAV endpoint.
- Studio page smoke for Renderer Settings and audio controls.

## v0.4.0 - 2026-05-05

### Added
- CSV batch import with row-level validation for required fields, duration, tempo, generation mode, pipeline mode, and concurrency.
- Persistent batch metadata under `.musicforge/batches/<batch-id>/` with `batch.json`, `items.json`, `events.jsonl`, and generated `export.json`.
- Batch APIs for list, detail, import, launch, pause, resume, retry failed items, export, hide, unhide, delete, and open folder.
- Standard-library batch runner that launches existing job runs with a configurable max concurrency from 1 to 4.
- Batch retry behavior that creates new jobs for failed or cancelled items while preserving completed items.
- Studio Batch workspace for CSV file/text import, launch controls, pause/resume, retry failed, export, hide/unhide/delete, and job-detail linking.
- Tests for batch parsing, persistence, safe deletion, server endpoints, concurrency limits, provider readiness, and Studio batch controls.

### Verified
- `python -m pytest -q`
- Local batch API smoke for import, launch, completion, export, hide, and delete.

## v0.3.2 - 2026-05-05

### Fixed
- `harmony_planner` retry now invalidates and reruns `arrangement_planner`, keeping section chords and chord/bass tracks consistent.
- Node retry API now starts retry work in a background thread and returns `202 Accepted`, so Studio is not blocked by slow provider calls.

### Verified
- `python -m pytest -q`
- Local multinode harmony retry smoke.
- Node retry API returns `202` and job status is polled to completion.

## v0.3.1 - 2026-05-05

### Added
- Explicit multinode dependency graph with upstream, downstream, and affected-node helpers.
- Node invalidation metadata: `invalidated_at`, `invalidated_by`, `retry_count`, `last_error`, and `depends_on`.
- NodeStore helpers for invalidating nodes, reading required cached outputs, and checking completed node records.
- `rerun_multinode_from_node()` to reuse upstream node outputs and rerun the selected node plus downstream nodes.
- Real `POST /api/jobs/<job-id>/nodes/<node-name>/retry` behavior for multinode jobs.
- `GET /api/jobs/<job-id>/nodes/<node-name>/dependencies` for retry confirmation and inspection.
- Studio Retry node controls in the Nodes tab with affected downstream confirmation.

### Changed
- Node retry rewrites final `song-plan.json`, `song.mid`, `validator-report.json`, job summary, and job state.
- Node summaries now include retry/invalidation/dependency metadata and `can_retry`.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\v031-single-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v031-multinode-check --force --pipeline-mode multinode`
- Studio API smoke for local multinode node retry and mock-provider multinode node retry.

## v0.3.0 - 2026-05-05

### Added
- Multi-agent music planning node schemas for brief, style, structure, lyrics, harmony, melody, arrangement, critic, and repair records.
- Safe `NodeStore` persistence under `runs/<job-id>/data/nodes/`.
- Deterministic multinode pipeline that writes every node record and builds the final MIDI-safe `SongPlan`.
- Provider-backed planning nodes for brief, style, structure, lyrics, and harmony with strict JSON/schema validation.
- Critic and repair nodes for basic arrangement checks, missing bass/drums repair, and MIDI note clamping.
- `pipeline_mode=single|multinode` for CLI and Studio jobs.
- `run-options.json` to keep resume behavior tied to generation and pipeline modes.
- Node inspection APIs: `GET /api/jobs/<job-id>/nodes` and `GET /api/jobs/<job-id>/nodes/<node-name>`.
- Studio Nodes tab with node summaries and full JSON preview.
- Provider node prompt files under `song_agent/prompts/nodes/`.

### Changed
- Job state now records both `generation_mode` and `pipeline_mode`.
- Multinode resume checks node builder output instead of only `song-plan.json`.
- Resume now rejects generation or pipeline mode mismatches instead of reusing incompatible artifacts.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\v030-single-local-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v030-multinode-local-check --force --pipeline-mode multinode`
- Local Studio API smoke with mock provider, `generation_mode=provider`, `pipeline_mode=multinode`, node API reads, and masked provider snapshot.

## v0.2.1 - 2026-05-05

### Added
- Job heartbeat fields and retry metadata in persisted job state.
- Pipeline stage-boundary cancellation checks.
- `POST /api/jobs/<job-id>/retry` for failed, stalled, and interrupted jobs.
- Watchdog tick and background watchdog thread for stale running jobs.
- Studio display for attempt count, retry count, heartbeat, and stalled state.
- Studio Retry action for failed, stalled, and interrupted jobs.
- Tests for cancel boundaries, retry behavior, provider snapshot masking, watchdog, and UI retry controls.

### Fixed
- Provider request errors now redact echoed keys, bearer tokens, and token-like fields before surfacing errors.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli examples\song_request.json --out runs\v021-local-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v021-local-generate-check --force`
- Local mock provider smoke with provider-mode job, retry path, and masked snapshot.

## v0.2.0 - 2026-05-05

### Added
- Local provider configuration storage under `.musicforge/provider.json`.
- Masked provider public config and environment variable overrides.
- Provider APIs for read, save, reset, and test.
- Mock provider client for tests and local UI smoke.
- OpenAI-compatible chat completions client using the Python standard library.
- Provider-backed SongPlan pipeline with strict JSON, schema, and validator checks.
- Studio provider settings form and `local` / `provider` generation mode selector.
- Provider job snapshots written as masked `provider-snapshot.json`.
- `python -m song_agent.cli doctor` and optional `--provider-test`.
- Tests for provider config, provider API, clients, provider pipeline, job integration, and doctor CLI.

### Changed
- Local deterministic generation remains the default and does not require provider config.
- Provider mode fails jobs cleanly when provider calls or model output validation fail.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli doctor`
- `python -m song_agent.cli examples\song_request.json --out runs\v020-local-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v020-local-generate-check --force`
- Local panel smoke with mock provider: save, test, provider-mode job, timeline/tracks/validator, masked snapshot.

## v0.1.2 - 2026-05-05

### Added
- Runtime view builders for timeline, tracks, validator, and summary data from existing run artifacts.
- Job APIs for `timeline`, `tracks`, and `validator` views.
- Studio tabs for Timeline, Tracks, Validator, SongPlan JSON, Logs, and Artifacts.
- Job management actions for hide, unhide, cancel, and delete.
- Hidden job filtering with `GET /api/jobs?include_hidden=1`.
- Startup recovery that marks leftover `queued`, `running`, `paused`, and `waiting_retry` jobs as `interrupted`.
- Backward-compatible `job-state.json` loading for newly added job fields.
- Tests for runtime views, job action boundaries, safe deletion, and startup recovery.

### Changed
- `JobState` now tracks deletion/interruption metadata and start/finish timestamps.
- Runtime artifact endpoints return explicit JSON errors when required artifacts are not ready.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\v012-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\v012-generate-check --force`
- Local panel smoke through `python -m song_agent.cli serve --host 127.0.0.1 --port 8787`

## v0.1.1 - 2026-05-05

### Added
- Local MusicForge Studio web panel served by `python -m song_agent.cli serve`.
- `generate` CLI subcommand while preserving the original positional CLI flow.
- Standard-library HTTP API for info, templates, jobs, events, artifacts, song plans, and MIDI downloads.
- Background job runner with `job-state.json` persisted under each run directory.
- Single-page HTML/CSS/JS workspace for creating jobs, polling status, viewing logs, inspecting SongPlan JSON, and downloading MIDI.
- Startup discovery of completed jobs with persisted job state.
- Tests for web UI shell and server job flow.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\panel-cli-check --force`
- `python -m song_agent.cli generate examples\song_request.json --out runs\panel-generate-check --force`
- `python -m song_agent.cli serve --host 127.0.0.1 --port 8787`

## v0.1.0 - 2026-05-05

### Added
- Local graph runner with step events and run summaries.
- Artifact-first project IO under `runs/<run-id>/`.
- Deterministic composer for a local, model-optional MIDI demo.
- `SongPlan` serialization, deserialization, and deterministic validation.
- No-dependency Standard MIDI writer with melody, chords, bass, and drums tracks.
- CLI full local generation flow from request JSON to `song-plan.json` and `song.mid`.
- `--resume` request consistency guard.
- `--force` overwrite path for known run artifacts.
- CLI handling for expected local errors without Python tracebacks.
- MIDI semantic tests for header, tracks, tempo, programs, drum channel, note pairs, and EOT.

### Verified
- `python -m pytest -q`
- `python -m song_agent.cli examples\song_request.json --out runs\release-check --force`
