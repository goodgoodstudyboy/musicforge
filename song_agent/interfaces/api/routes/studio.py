from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document
from song_agent.interfaces.api.runtime import *
from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioRoutes:
    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_PATCH(self) -> None:
        self._handle_request("PATCH")

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def store(self) -> JobStore:
        return self.server.job_store  # type: ignore[attr-defined]

    @property
    def human_review_pack_store(self) -> HumanReviewPackStore:
        return self.server.human_review_pack_store  # type: ignore[attr-defined]

    @property
    def edit_preset_store(self) -> EditPresetStore:
        return self.server.edit_preset_store  # type: ignore[attr-defined]

    @property
    def auth_config(self) -> AuthConfig:
        return self.server.auth_config  # type: ignore[attr-defined]

    def _handle_request(self, method: str) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if self._auth_required(path) and not self._is_authorized():
                self._send_unauthorized()
                return
            if method == "GET" and path == "/":
                self._send_html(panel_html())
                return
            if method == "GET" and path == "/api/info":
                self._send_json(
                    api_info(
                        self.auth_config,
                        authorized=(not self.auth_config.enabled) or self._is_authorized(),
                    )
                )
                return
            if method == "GET" and path == "/api/template":
                self._send_json(api_template())
                return
            if path == "/api/ga":
                self._handle_ga_route(method)
                return
            if path == "/api/ga/check":
                self._handle_ga_check_route(method)
                return
            if path == "/api/docs/index":
                self._handle_docs_index_route(method)
                return
            if path == "/api/maintenance/status" or path.startswith("/api/maintenance/"):
                self._handle_maintenance_route(method, path)
                return
            if path == "/api/unified-command-center-release-trains" or path.startswith("/api/unified-command-center-release-trains/"):
                self._handle_unified_command_center_release_trains_route(method, path)
                return
            if PROGRAM_ROUTE_REGISTRY.dispatch(self, method, path):
                return
            if path == "/api/unified-command-centers" or path.startswith("/api/unified-command-centers/"):
                self._handle_unified_command_centers_route(method, path)
                return
            if path == "/api/provider":
                self._handle_provider_route(method)
                return
            if path == "/api/provider/reset":
                self._handle_provider_reset(method)
                return
            if path == "/api/provider/test":
                self._handle_provider_test(method)
                return
            if path == "/api/renderer":
                self._handle_renderer_route(method)
                return
            if path == "/api/renderer/reset":
                self._handle_renderer_reset(method)
                return
            if path == "/api/renderer/test":
                self._handle_renderer_test(method)
                return
            if path == "/api/audio/profiles" or path.startswith("/api/audio/profiles/"):
                self._handle_audio_profiles_route(method, path)
                return
            if path == "/api/audio-lab" or path.startswith("/api/audio-lab/"):
                self._handle_audio_lab_route(method, path)
                return
            if path == "/api/audio-fix-sprints" or path.startswith("/api/audio-fix-sprints/"):
                self._handle_audio_fix_sprint_route(method, path)
                return
            if path == "/api/audio-campaigns" or path.startswith("/api/audio-campaigns/"):
                self._handle_audio_campaign_route(method, path)
                return
            if path == "/api/audio-baselines" or path.startswith("/api/audio-baselines/"):
                self._handle_audio_baselines_route(method, path)
                return
            if path == "/api/audio-quality-observatories" or path.startswith("/api/audio-quality-observatories/"):
                self._handle_audio_quality_observatories_route(method, path)
                return
            if path == "/api/audio-quality-actions" or path.startswith("/api/audio-quality-actions/"):
                self._handle_audio_quality_actions_route(method, path)
                return
            if path == "/api/mastering/profiles" or path.startswith("/api/mastering/profiles/"):
                self._handle_mastering_profiles_route(method, path)
                return
            if path == "/api/audio-encoding/config" or path.startswith("/api/audio-encoding/config/") or path == "/api/audio-encoding/profiles" or path.startswith("/api/audio-encoding/profiles/"):
                self._handle_audio_encoding_route(method, path)
                return
            if path == "/api/release-portfolio-audits" or path.startswith("/api/release-portfolio-audits/"):
                self._handle_release_portfolio_audits(method, path)
                return
            if path == "/api/release-portfolio-governance-queues" or path.startswith("/api/release-portfolio-governance-queues/"):
                self._handle_release_portfolio_governance_queues(method, path)
                return
            if path == "/api/public-trust-centers" or path.startswith("/api/public-trust-centers/"):
                self._handle_public_trust_centers(method, path)
                return
            if path == "/api/trust-operations" or path.startswith("/api/trust-operations/"):
                self._handle_trust_operations(method, path)
                return
            if path == "/api/jobs":
                if method == "GET":
                    query = parse_qs(parsed.query)
                    include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
                    self._send_json(
                        {
                            "jobs": [
                                job.to_dict()
                                for job in self.store.list_jobs(include_hidden=include_hidden)
                            ]
                        }
                    )
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    payload = self._expand_context_pack_payload(payload)
                    job = self.store.create_job(payload)
                    self._send_json(job.to_dict(), status=HTTPStatus.ACCEPTED)
                    return

            if path == "/api/batches":
                if method == "GET":
                    query = parse_qs(parsed.query)
                    include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
                    self._send_json(
                        {
                            "batches": [
                                document.state.to_dict()
                                for document in self.batch_store.list_batches(
                                    include_hidden=include_hidden
                                )
                            ]
                        }
                    )
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if path == "/api/batches/import-csv":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                document = self.batch_store.import_csv(
                    name=str(payload.get("name") or "Untitled Batch"),
                    csv_text=str(payload.get("csv_text") or ""),
                    generation_mode=str(payload.get("generation_mode") or "local"),
                    pipeline_mode=str(payload.get("pipeline_mode") or "multinode"),
                    max_concurrency=payload.get("max_concurrency", 1),
                )
                self._send_json(document.to_dict(), status=HTTPStatus.CREATED)
                return

            if path == "/api/projects":
                self._handle_projects_root(method, parsed.query)
                return

            if path == "/api/releases":
                self._handle_releases_root(method, parsed.query)
                return

            if path == "/api/acceptance/suites":
                self._handle_acceptance_suites_root(method, parsed.query)
                return

            if path == "/api/acceptance/profiles":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "profiles": list_acceptance_profiles()})
                return

            if path == "/api/acceptance/songbook":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "songbook": builtin_songbook()})
                return

            if path == "/api/acceptance/fix-sprints":
                self._handle_acceptance_fix_sprints_root(method, parsed.query)
                return

            if path == "/api/acceptance/fix-plans":
                self._handle_acceptance_fix_plans_root(method, parsed.query)
                return

            if path == "/api/acceptance/fix-plans/recommend":
                self._handle_acceptance_fix_plans_recommend(method)
                return

            if path == "/api/acceptance/fix-plan-reviews":
                self._handle_acceptance_fix_plan_reviews_root(method, parsed.query)
                return

            if path == "/api/acceptance/planning-rulesets":
                self._handle_planning_rulesets_root(method, parsed.query)
                return

            planning_ruleset_route = _match_planning_ruleset_route(path)
            if planning_ruleset_route is not None:
                self._handle_planning_ruleset_route(method, planning_ruleset_route)
                return

            if path == "/api/acceptance/planning-simulations":
                self._handle_planning_simulations_root(method, parsed.query)
                return

            planning_simulation_route = _match_planning_simulation_route(path)
            if planning_simulation_route is not None:
                self._handle_planning_simulation_route(method, planning_simulation_route)
                return

            if path == "/api/acceptance/planning-rule-governance/active":
                self._handle_planning_rule_governance_active(method)
                return

            if path == "/api/acceptance/planning-rule-governance/versions":
                self._handle_planning_rule_governance_versions(method, parsed.query)
                return

            if path == "/api/acceptance/planning-rule-governance/promotions":
                self._handle_planning_rule_governance_promotions(method, parsed.query)
                return

            if path == "/api/acceptance/planning-rule-governance/rollback":
                self._handle_planning_rule_governance_rollback(method)
                return

            if path == "/api/acceptance/planning-rule-governance/events":
                self._handle_planning_rule_governance_events(method, parsed.query)
                return

            governance_version_route = _match_planning_rule_governance_version_route(path)
            if governance_version_route is not None:
                self._handle_planning_rule_governance_version_route(method, governance_version_route)
                return

            governance_promotion_route = _match_planning_rule_governance_promotion_route(path)
            if governance_promotion_route is not None:
                self._handle_planning_rule_governance_promotion_route(method, governance_promotion_route)
                return

            if path == "/api/acceptance/planning-rule-impact/reports":
                self._handle_planning_rule_impact_reports(method, parsed.query)
                return

            if path == "/api/acceptance/planning-rule-impact/latest":
                self._handle_planning_rule_impact_latest(method, parsed.query)
                return

            impact_report_route = _match_planning_rule_impact_report_route(path)
            if impact_report_route is not None:
                self._handle_planning_rule_impact_report_route(method, impact_report_route)
                return

            fix_plan_review_route = _match_acceptance_fix_plan_review_route(path)
            if fix_plan_review_route is not None:
                self._handle_acceptance_fix_plan_review_route(method, fix_plan_review_route)
                return

            fix_plan_route = _match_acceptance_fix_plan_route(path)
            if fix_plan_route is not None:
                self._handle_acceptance_fix_plan_route(method, fix_plan_route)
                return

            if path == "/api/acceptance/kb":
                self._handle_acceptance_kb_root(method)
                return

            if path == "/api/acceptance/kb/refresh":
                self._handle_acceptance_kb_refresh(method)
                return

            if path == "/api/acceptance/kb/entries":
                self._handle_acceptance_kb_entries(method, parsed.query)
                return

            if path == "/api/acceptance/kb/search":
                self._handle_acceptance_kb_search(method, parsed.query)
                return

            if path == "/api/acceptance/kb/recommend":
                self._handle_acceptance_kb_recommend(method)
                return

            kb_entry_route = _match_acceptance_kb_entry_route(path)
            if kb_entry_route is not None:
                self._handle_acceptance_kb_entry_route(method, kb_entry_route)
                return

            kb_report_id = _match_acceptance_kb_report_route(path)
            if kb_report_id is not None:
                self._handle_acceptance_kb_report(method, kb_report_id)
                return

            fix_sprint_route = _match_acceptance_fix_sprint_route(path)
            if fix_sprint_route is not None:
                self._handle_acceptance_fix_sprint_route(method, fix_sprint_route)
                return

            if path == "/api/acceptance/analytics":
                self._handle_acceptance_analytics_root(method, parsed.query)
                return

            if path == "/api/acceptance/analytics/refresh":
                self._handle_acceptance_analytics_refresh(method, parsed.query)
                return

            analytics_recommendation_route = _match_acceptance_analytics_recommendation_route(path)
            if analytics_recommendation_route is not None:
                report_id, recommendation_id = analytics_recommendation_route
                self._handle_acceptance_analytics_recommendation(method, report_id, recommendation_id)
                return

            analytics_report_route = _match_acceptance_analytics_report_route(path)
            if analytics_report_route is not None:
                self._handle_acceptance_analytics_report(method, analytics_report_route)
                return

            if path == "/api/distribution/profiles":
                self._handle_distribution_profiles_root(method)
                return

            if path == "/api/distribution/template-packs":
                self._handle_distribution_templates_root(method)
                return

            distribution_template_route = _match_distribution_template_route(path)
            if distribution_template_route is not None:
                self._handle_distribution_template_route(method, distribution_template_route)
                return

            if path == "/api/distribution/template-packs/import":
                self._handle_distribution_template_import(method, parsed.query)
                return

            distribution_profile_route = _match_distribution_profile_route(path)
            if distribution_profile_route is not None:
                self._handle_distribution_profile_route(method, distribution_profile_route)
                return

            if path == "/api/usage/provider":
                self._handle_provider_usage_root(method)
                return

            if path == "/api/assets":
                self._handle_assets_root(method, parsed.query)
                return

            if path == "/api/assets/extract/from-job":
                self._handle_asset_extract_from_job(method)
                return

            if path == "/api/assets/extract/from-project-version":
                self._handle_asset_extract_from_project_version(method)
                return

            if path == "/api/assets/extract/from-candidate":
                self._handle_asset_extract_from_candidate(method)
                return

            if path == "/api/library/index":
                self._handle_library_index(method)
                return

            if path == "/api/library/rebuild":
                self._handle_library_rebuild(method)
                return

            if path == "/api/library/search":
                self._handle_library_search(method)
                return

            if path == "/api/library/recommend":
                self._handle_library_recommend(method)
                return

            if path == "/api/context-packs":
                self._handle_context_packs_root(method, parsed.query)
                return

            if path == "/api/references":
                self._handle_references_root(method, parsed.query)
                return

            if path == "/api/references/import":
                self._handle_reference_import(method)
                return

            if path == "/api/edit-presets":
                self._handle_edit_presets_root(method)
                return

            if path == "/api/edit-presets/reset":
                self._handle_edit_presets_reset(method)
                return

            if path == "/api/prompt-templates":
                self._handle_prompt_templates_root(method)
                return

            if path == "/api/prompt-templates/reset":
                self._handle_prompt_templates_reset(method)
                return

            if path == "/api/editor-templates":
                self._handle_editor_templates_root(method, parsed.query)
                return

            editor_template_route = _match_editor_template_route(path)
            if editor_template_route is not None:
                template_type, template_id, tail = editor_template_route
                self._handle_editor_template_route(method, template_type, template_id, tail)
                return

            prompt_template_route = _match_prompt_template_route(path)
            if prompt_template_route is not None:
                template_id, tail = prompt_template_route
                self._handle_prompt_template_route(method, template_id, tail)
                return

            edit_preset_route = _match_edit_preset_route(path)
            if edit_preset_route is not None:
                preset_id, tail = edit_preset_route
                self._handle_edit_preset_route(method, preset_id, tail)
                return

            asset_route = _match_asset_route(path)
            if asset_route is not None:
                asset_id, tail = asset_route
                self._handle_asset_route(method, asset_id, tail)
                return

            reference_route = _match_reference_route(path)
            if reference_route is not None:
                reference_id, tail = reference_route
                self._handle_reference_route(method, reference_id, tail)
                return

            context_pack_route = _match_context_pack_route(path)
            if context_pack_route is not None:
                pack_id, tail = context_pack_route
                self._handle_context_pack_route(method, pack_id, tail)
                return

            project_route = _match_project_route(path)
            if project_route is not None:
                project_id, tail = project_route
                self._handle_project_route(method, project_id, tail, parsed.query)
                return

            release_route = _match_release_route(path)
            if release_route is not None:
                release_id, tail = release_route
                self._handle_release_route(method, release_id, tail, parsed.query)
                return

            acceptance_route = _match_acceptance_route(path)
            if acceptance_route is not None:
                suite_id, tail = acceptance_route
                self._handle_acceptance_route(method, suite_id, tail)
                return

            batch_route = _match_batch_route(path)
            if batch_route is not None:
                batch_id, tail = batch_route
                self._handle_batch_route(method, batch_id, tail)
                return

            job_route = _match_job_route(path)
            if job_route is not None:
                job_id, tail = job_route
                self._handle_job_route(method, job_id, tail)
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Route not found.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ContextPackStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except HumanReviewPackStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except HumanReviewPackNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except HumanReviewPackValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _handle_edit_presets_root(self, method: str) -> None:
        if method == "GET":
            self._send_json(self.edit_preset_store.to_response())
            return
        if method == "POST":
            try:
                preset = self.edit_preset_store.save_preset(self._read_json_body())
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "preset": preset.to_dict(), **self.edit_preset_store.to_response()}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_edit_preset_route(self, method: str, preset_id: str, tail: str) -> None:
        if tail == "":
            if method == "GET":
                try:
                    preset = self.edit_preset_store.get_preset(preset_id)
                except (FileNotFoundError, ValueError):
                    self._send_error(HTTPStatus.NOT_FOUND, "Edit preset not found.")
                    return
                self._send_json({"preset": preset.to_dict()})
                return
            if method == "POST":
                try:
                    preset = self.edit_preset_store.save_preset(self._read_json_body(), preset_id=preset_id)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json({"ok": True, "preset": preset.to_dict(), **self.edit_preset_store.to_response()})
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.edit_preset_store.delete_preset(preset_id)
            except PermissionError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            except (FileNotFoundError, ValueError):
                self._send_error(HTTPStatus.NOT_FOUND, "Edit preset not found.")
                return
            self._send_json({"ok": True, **self.edit_preset_store.to_response()})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Edit preset route not found.")

    def _handle_edit_presets_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        self.edit_preset_store.reset()
        self._send_json({"ok": True, **self.edit_preset_store.to_response()})

    def _get_or_refresh_delivery_qa(self, project_id: str, *, refresh: bool) -> dict[str, Any]:
        project_dir = self.project_store.project_dir(project_id)
        if not refresh:
            existing = self.project_store.read_delivery_qa(project_id, default={})
            if existing:
                try:
                    document = self.project_store.sync_project(project_id, self.store.get_job)
                except FileNotFoundError:
                    document = self.project_store.get_project(project_id)
                project_export = self.project_store.project_export_snapshot(project_id)
                try:
                    manifest = read_final_export_manifest(project_dir)
                except FileNotFoundError:
                    manifest = {}
                current_hash = delivery_qa_source_hash(project_id=project_id, project_document=document, project_dir=project_dir, project_export=project_export, final_export_manifest=manifest)
                if str(existing.get("source_hash") or "") != current_hash:
                    return mark_delivery_qa_stale(existing, current_source_hash=current_hash)
                return existing
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            document = self.project_store.get_project(project_id)
        project_export = self.project_store.project_export_snapshot(project_id)
        try:
            manifest = read_final_export_manifest(project_dir)
        except FileNotFoundError:
            manifest = {}
        report = build_delivery_qa_report(
            project_id=project_id,
            project_document=document,
            project_dir=project_dir,
            project_export=project_export,
            final_export_manifest=manifest,
            now=_utc_now(),
        )
        return self.project_store.write_delivery_qa(project_id, report, now=_utc_now())

    def _set_final_version_with_gate(self, project_id: str, version_id: str, *, force: bool) -> tuple[Any, Any]:
        document = self.project_store.get_project(project_id)
        version = next((version for version in document.versions if version.version_id == version_id), None)
        if version is None:
            raise FileNotFoundError(version_id)
        if version.status != "completed":
            raise ValueError("Only completed versions can be marked final.")
        result = self._evaluate_project_version(project_id, version)
        self.project_store.update_version_quality_gate(project_id, version.version_id, result)
        if result.status not in {"passed", "warning"} and not force:
            self.project_store.append_event(
                project_id,
                "final_version_gate_failed",
                {"version_id": version.version_id, "status": result.status, "score": result.score},
            )
            raise PermissionError(
                {
                    "error": "Quality gate failed.",
                    "quality_gate": result.to_dict(),
                }
            )
        document = self.project_store.set_final_version(project_id, version.version_id)
        if force and result.status not in {"passed", "warning"}:
            self.project_store.append_event(
                project_id,
                "final_version_force_set",
                {"version_id": version.version_id, "status": result.status, "score": result.score},
            )
        return document, result

    def _review_sprint_response(
        self,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        *,
        include_events: bool = False,
    ) -> dict[str, Any]:
        summary = sprint_store.read_summary(sprint.sprint_id, default={})
        conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        judge_summary_data = sprint_store.read_judge_summary(sprint.sprint_id, default={})
        action_queue_summary_data = self._review_sprint_action_queue_summary(sprint_store, sprint)
        closeout_report = sprint_store.read_closeout_report(sprint.sprint_id, default={})
        signoff = sprint_store.read_signoff(sprint.sprint_id, default={})
        response = {
            "ok": True,
            "sprint": sprint.to_dict(),
            "summary": summary,
            "conflict_report": conflict_report,
            "recommendation_report": recommendation_report,
            "recommendation_summary": recommendation_report_summary(recommendation_report),
            "judge_summary": judge_summary_data,
            "action_queue_summary": action_queue_summary_data,
            "metrics_summary": self._review_sprint_metrics_summary(sprint_store, sprint),
            "closeout_report": closeout_report,
            "closeout_summary": closeout_report_summary(closeout_report),
            "signoff": signoff,
            "signoff_summary": signoff_summary(signoff),
            "export_summary": review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, action_queue_summary_data, judge_summary_data),
            "tasks": self._review_sprint_task_items(task_store, sprint),
        }
        if include_events:
            response["events"] = sprint_store.read_events(sprint.sprint_id)
        return response

    def _review_sprint_public_payload(self, sprint_store: ReviewSprintStore, sprint: Any) -> dict[str, Any]:
        summary = sprint_store.read_summary(sprint.sprint_id, default={})
        conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        judge_summary_data = sprint_store.read_judge_summary(sprint.sprint_id, default={})
        action_queue_summary_data = self._review_sprint_action_queue_summary(sprint_store, sprint)
        closeout_report = sprint_store.read_closeout_report(sprint.sprint_id, default={})
        signoff = sprint_store.read_signoff(sprint.sprint_id, default={})
        return {
            **sprint.to_dict(),
            "summary": summary,
            "conflict_report": conflict_report,
            "recommendation_report": recommendation_report,
            "recommendation_summary": recommendation_report_summary(recommendation_report),
            "judge_summary": judge_summary_data,
            "action_queue_summary": action_queue_summary_data,
            "metrics_summary": self._review_sprint_metrics_summary(sprint_store, sprint),
            "closeout_summary": closeout_report_summary(closeout_report),
            "signoff_summary": signoff_summary(signoff),
            "export_summary": review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, action_queue_summary_data, judge_summary_data),
        }

    def _review_sprint_metrics_summary(self, sprint_store: ReviewSprintStore, sprint: Any) -> dict[str, Any]:
        try:
            metrics_store = ReviewMetricsStore(sprint_store.project_dir)
            return sprint_metrics_summary(metrics_store.read_sprint_metrics(sprint.sprint_id, default={}))
        except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
            return {}

    def _review_sprint_action_queue_summary(self, sprint_store: ReviewSprintStore, sprint: Any) -> dict[str, Any]:
        try:
            queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
            return action_queue_collection_summary(queue_store.list_queues(include_archived=True))
        except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
            return {}

    def _get_or_refresh_sprint_closeout(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        *,
        refresh: bool,
    ) -> dict[str, Any]:
        project_dir = self.project_store.project_dir(project_id)
        if not refresh:
            existing = sprint_store.read_closeout_report(sprint.sprint_id, default={})
            if existing:
                try:
                    project_document = self.project_store.sync_project(project_id, self.store.get_job)
                except FileNotFoundError:
                    project_document = self.project_store.get_project(project_id)
                queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                metrics_store = ReviewMetricsStore(project_dir)
                current_hash = closeout_source_hash(
                    sprint=sprint,
                    project_document=project_document,
                    task_store=task_store,
                    sprint_store=sprint_store,
                    queue_store=queue_store,
                    metrics_report=metrics_store.read_sprint_metrics(sprint.sprint_id, default={}),
                    judge_summary=sprint_store.read_judge_summary(sprint.sprint_id, default={}),
                    recommendation_report=sprint_store.read_recommendation_report(sprint.sprint_id, default={}),
                    conflict_report=sprint_store.read_conflict_report(sprint.sprint_id, default={}),
                )
                if str(existing.get("source_hash") or "") != current_hash:
                    return mark_closeout_report_stale(existing, current_source_hash=current_hash)
                return existing
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        metrics_report = self._get_or_refresh_sprint_metrics(project_id, sprint_store, task_store, sprint, refresh=refresh)
        report = build_closeout_report(
            project_id=project_id,
            sprint=sprint,
            project_document=project_document,
            task_store=task_store,
            sprint_store=sprint_store,
            queue_store=ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id)),
            metrics_report=metrics_report,
            judge_summary=sprint_store.read_judge_summary(sprint.sprint_id, default={}),
            recommendation_report=sprint_store.read_recommendation_report(sprint.sprint_id, default={}),
            conflict_report=sprint_store.read_conflict_report(sprint.sprint_id, default={}),
            now=_utc_now(),
        )
        return sprint_store.write_closeout_report(sprint, report, now=_utc_now())

    def _get_or_refresh_sprint_metrics(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        *,
        refresh: bool,
    ) -> dict[str, Any]:
        project_dir = self.project_store.project_dir(project_id)
        metrics_store = ReviewMetricsStore(project_dir)
        if not refresh:
            existing = metrics_store.read_sprint_metrics(sprint.sprint_id, default={})
            if existing:
                return existing
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        provider_records = collect_project_provider_usage_records(project_id, project_document.versions, project_dir)
        queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
        report = build_sprint_metrics_report(
            project_id=project_id,
            sprint=sprint,
            project_document=project_document,
            task_store=task_store,
            sprint_store=sprint_store,
            queue_store=queue_store,
            provider_usage_records=provider_records,
            now=_utc_now(),
        )
        return metrics_store.write_sprint_metrics(sprint.sprint_id, report)

    def _get_or_refresh_sprint_judge_summary(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        *,
        refresh: bool,
    ) -> dict[str, Any]:
        if not refresh:
            existing = sprint_store.read_judge_summary(sprint.sprint_id, default={})
            if existing:
                return existing
        reports = []
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                reports.append(self._read_review_task_judge_report(project_id, task_store, task, candidates))
            except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
                continue
        summary = sprint_judge_summary(sprint_id=sprint.sprint_id, task_reports=[report for report in reports if report], now=_utc_now())
        return sprint_store.write_judge_summary(sprint, summary, now=_utc_now())

    def _refresh_review_sprint_judge_reports(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        requested = [str(item) for item in payload.get("task_ids", []) if str(item).strip()] if isinstance(payload.get("task_ids"), list) else []
        sprint_task_ids = self._review_sprint_ordered_task_ids(sprint)
        task_ids = [task_id for task_id in sprint_task_ids if not requested or task_id in requested]
        max_tasks = max(1, min(20, int(payload.get("max_tasks") or len(task_ids) or 1)))
        skip_existing = bool(payload.get("skip_existing_current", False))
        results = []
        processed = 0
        for task_id in task_ids:
            if processed >= max_tasks:
                results.append({"task_id": task_id, "status": "skipped", "reason": "max_tasks reached"})
                continue
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                ready = [candidate for candidate in candidates if candidate.status == "ready"]
                if not ready:
                    results.append({"task_id": task_id, "status": "skipped", "reason": "no ready candidates"})
                    continue
                existing = self._read_review_task_judge_report(project_id, task_store, task, candidates)
                if skip_existing and existing and existing.get("status") == "completed" and not existing.get("stale"):
                    results.append({"task_id": task_id, "status": "skipped", "reason": "current judge report exists", "summary": judge_report_summary(existing)})
                    continue
                result = self._refresh_review_task_judge_report(project_id, task_store, task, payload)
                results.append({"task_id": task_id, "status": "completed", "summary": result.get("summary", {})})
                processed += 1
            except (ReviewTaskStateError, ReviewTaskError, ProviderError, ValueError, FileNotFoundError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        summary = self._get_or_refresh_sprint_judge_summary(project_id, sprint_store, task_store, sprint, refresh=True)
        self.project_store.append_event(project_id, "review_sprint_judge_summary_refreshed", {"sprint_id": sprint.sprint_id, "judged_task_count": summary.get("judged_task_count")})
        return sanitize_metadata({**summary, "results": results})

    def _review_sprint_task_items(self, task_store: ReviewTaskStore, sprint: Any) -> list[dict[str, Any]]:
        items = []
        for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
            if not ref.get("included", True):
                continue
            task_id = str(ref.get("task_id") or "")
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                decision_report = _try_read_review_decision_report(task_store, task.task_id)
                judge_report = self._read_review_task_judge_report(sprint.project_id, task_store, task, candidates)
                items.append(
                    {
                        "ref": ref,
                        "task": task.to_dict(),
                        "candidates": [candidate.to_dict() for candidate in candidates],
                        "decision_report": decision_report,
                        "judge_report": judge_report,
                        "judge_summary": judge_report_summary(judge_report),
                        "provider_summary": review_candidate_source_breakdown(candidates),
                    }
                )
            except FileNotFoundError:
                items.append({"ref": ref, "task_id": task_id, "missing": True})
        return items

    def _refresh_review_sprint_state(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any) -> tuple[Any, dict[str, Any]]:
        parent_hashes = self._review_sprint_parent_plan_hashes(project_id, task_store, sprint)
        report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes=parent_hashes, now=_utc_now())
        sprint = sprint_store.refresh_summary(sprint, task_store=task_store, now=_utc_now())
        return sprint, report

    def _refresh_review_sprint_recommendations(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any) -> dict[str, Any]:
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        report = build_review_sprint_recommendation_report(
            project_id=project_id,
            sprint=sprint,
            task_store=task_store,
            sprint_store=sprint_store,
            library_index=index,
            project_document=project_document,
            now=_utc_now(),
        )
        return sprint_store.write_recommendation_report(sprint, report, now=report.get("created_at") or _utc_now())

    def _review_sprint_parent_plan_hashes(self, project_id: str, task_store: ReviewTaskStore, sprint: Any) -> dict[str, str]:
        hashes: dict[str, str] = {}
        version_ids = []
        for ref in sprint.task_refs:
            if not ref.get("included", True):
                continue
            try:
                task = task_store.read_task(str(ref.get("task_id") or ""))
            except FileNotFoundError:
                continue
            if task.project_id == project_id and task.parent_version_id not in version_ids:
                version_ids.append(task.parent_version_id)
        for version_id in version_ids:
            try:
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            except FileNotFoundError:
                continue
            hashes[version_id] = song_plan_hash(parent_plan)
        return hashes

    def _review_sprint_ordered_task_ids(self, sprint: Any) -> list[str]:
        task_ids = []
        for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
            if ref.get("included", True) and ref.get("task_id"):
                task_ids.append(str(ref.get("task_id")))
        return task_ids

    def _review_sprint_membership_summary(self, project_id: str, task_id: str) -> dict[str, Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                refs = [ref for ref in sprint.task_refs if ref.get("included", True)]
                if task_id not in {str(ref.get("task_id") or "") for ref in refs}:
                    continue
                summary = sprint_store.read_summary(sprint.sprint_id, default={})
                conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
                recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                queue_summary = action_queue_collection_summary(queue_store.list_queues(include_archived=True))
                judge_summary_data = sprint_store.read_judge_summary(sprint.sprint_id, default={})
                matches.append(review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, queue_summary, judge_summary_data))
            if not matches:
                return {}
            return sanitize_metadata({"sprint_ids": [item["sprint_id"] for item in matches], "primary": matches[0], "sprints": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
            return {}

    def _review_sprint_recommendation_summary_for_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                if task_id not in self._review_sprint_ordered_task_ids(sprint):
                    continue
                report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                action = _recommendation_action_for_task(report, task_id)
                if action:
                    matches.append(
                        {
                            "sprint_id": sprint.sprint_id,
                            "task_id": task_id,
                            "report_created_at": report.get("created_at"),
                            "rank": action.get("rank"),
                            "action": action.get("action"),
                            "score": action.get("score"),
                            "reason": action.get("reason"),
                            "context_ref_count": _context_ref_count(action.get("context_pack_preview")),
                        }
                    )
            if not matches:
                return {}
            return sanitize_metadata({"primary": matches[0], "recommendations": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
            return {}

    def _review_sprint_action_queue_summary_for_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                if task_id not in self._review_sprint_ordered_task_ids(sprint):
                    continue
                queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                for queue in queue_store.list_queues(include_archived=True):
                    related = [item for item in queue.items if item.task_id == task_id]
                    if not related:
                        continue
                    manual_apply = next((item for item in related if item.action == "manual_apply_candidate"), None)
                    primary_item = manual_apply or related[0]
                    matches.append(
                        {
                            "sprint_id": sprint.sprint_id,
                            "queue_id": queue.queue_id,
                            "task_id": task_id,
                            "status": queue.status,
                            "related_action": primary_item.action,
                            "related_item_id": primary_item.item_id,
                            "related_item_status": primary_item.status,
                        }
                    )
            if not matches:
                return {}
            return sanitize_metadata({"primary": matches[0], "queues": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
            return {}

    def _generate_review_sprint_local_candidates(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if sprint.status not in {"open", "in_progress", "blocked"}:
            raise ReviewSprintStateError(f"Cannot generate candidates for a {sprint.status} review sprint.")
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        stop_on_conflict = bool(payload.get("stop_on_conflict", sprint.settings.get("stop_on_conflict", False)))
        if stop_on_conflict and any(item.get("severity") == "blocking" for item in conflict_report.get("conflicts", [])):
            raise ReviewSprintStateError("Review sprint has blocking conflicts.")
        strategies = payload.get("strategies") if isinstance(payload.get("strategies"), list) else sprint.settings.get("local_candidate_strategies")
        render_midi = bool(payload.get("render_midi", sprint.settings.get("render_midi", True)))
        skip_existing = bool(payload.get("skip_existing_ready", True))
        results = []
        created_total = 0
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                if skip_existing and any(candidate.candidate_type == "local_review_intents" and candidate.status in {"ready", "applied"} for candidate in candidates):
                    results.append({"task_id": task.task_id, "status": "skipped", "reason": "ready local candidate exists"})
                    continue
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                generated = []
                for candidate, candidate_plan, validator, summary in build_local_review_candidates(task, parent_plan, strategies=strategies):
                    stored = task_store.create_candidate(
                        task=task,
                        candidate=candidate,
                        candidate_plan=candidate_plan,
                        validator=validator,
                        summary=summary,
                        render_midi_file=render_midi,
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now()), now=_utc_now())
                created_total += len(generated)
                results.append(
                    {
                        "task_id": task.task_id,
                        "status": "generated" if generated else "skipped",
                        "created_count": len(generated),
                        "created_candidate_ids": [candidate.candidate_id for candidate in generated],
                        "decision_report": review_decision_summary(decision_report),
                        "provider_summary": review_candidate_source_breakdown(ranked),
                    }
                )
            except (FileNotFoundError, ReviewTaskError, ReviewTaskStateError, ValueError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        self.project_store.append_event(project_id, "review_sprint_local_candidates_generated", {"sprint_id": sprint.sprint_id, "created_count": created_total})
        response = self._review_sprint_response(sprint_store, task_store, sprint)
        response.update({"results": sanitize_metadata(results), "created_count": created_total})
        return response

    def _run_review_sprint_action_queue(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        queue_store: ReviewSprintActionQueueStore,
        queue_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        queue = queue_store.read_queue(queue_id)
        if queue.project_id != project_id or queue.sprint_id != sprint.sprint_id:
            raise FileNotFoundError(queue_id)
        if queue.status == "archived":
            raise ReviewSprintStateError("Archived action queue cannot be run.")
        selected_ids = payload.get("item_ids") if isinstance(payload.get("item_ids"), list) else []
        selected_ids = [str(item) for item in selected_ids if str(item).strip()]
        include_provider = bool(payload.get("include_provider", queue.settings.get("run_provider_actions", False)))
        rerun_failed = bool(payload.get("rerun_failed", False))
        stop_on_failure = bool(payload.get("stop_on_failure", queue.settings.get("stop_on_failure", False)))
        results: list[dict[str, Any]] = []
        queue = queue_store.update_queue(replace(queue, status="running"), event="queue_run_started", payload={"selected_item_ids": selected_ids, "include_provider": include_provider}, now=_utc_now())
        self.project_store.append_event(project_id, "review_sprint_action_queue_started", {"sprint_id": sprint.sprint_id, "queue_id": queue.queue_id})
        provider_runs = 0
        max_provider = int(queue.settings.get("max_provider_actions") or 3)
        for item in _select_action_queue_items(queue, selected_ids, rerun_failed=rerun_failed):
            if item.safety == "provider_safe" and not include_provider:
                results.append({"item_id": item.item_id, "status": "skipped", "reason": "provider action requires include_provider=true"})
                continue
            if item.safety == "provider_safe":
                if provider_runs >= max_provider:
                    item = self._set_action_item(queue_store, queue, item, status="blocked", error="Provider action limit reached for this queue run.", event="item_blocked")
                    queue = queue_store.read_queue(queue.queue_id)
                    results.append({"item_id": item.item_id, "status": item.status, "error": item.error})
                    if stop_on_failure:
                        break
                    continue
                provider_runs += 1
            item = self._set_action_item(queue_store, queue, item, status="running", event="item_started")
            queue = queue_store.read_queue(queue.queue_id)
            try:
                item = self._execute_review_sprint_action_item(project_id, sprint_store, task_store, sprint, queue, item)
                event = "item_blocked" if item.status == "blocked" else ("item_skipped" if item.status == "skipped" else "item_completed")
                item = self._set_action_item(queue_store, queue, item, status=item.status, result=item.result, error=item.error, event=event)
                self.project_store.append_event(project_id, "review_sprint_action_item_completed", {"sprint_id": sprint.sprint_id, "queue_id": queue.queue_id, "item_id": item.item_id, "status": item.status, "action": item.action})
                results.append({"item_id": item.item_id, "status": item.status, "result": item.result, "error": item.error})
            except (ReviewSprintStateError, ReviewTaskStateError, ContextPackStaleError) as exc:
                item = self._set_action_item(queue_store, queue, item, status="blocked", error=str(exc), event="item_blocked")
                results.append({"item_id": item.item_id, "status": item.status, "error": item.error})
                if stop_on_failure:
                    break
            except (ProviderError, ReviewTaskError, ValueError, FileNotFoundError) as exc:
                item = self._set_action_item(queue_store, queue, item, status="failed", error=str(exc), event="item_failed")
                results.append({"item_id": item.item_id, "status": item.status, "error": item.error})
                if stop_on_failure:
                    break
            finally:
                queue = queue_store.read_queue(queue.queue_id)
        completed_status = "pending" if queue.status == "running" else queue.status
        queue = queue_store.update_queue(replace(queue, status=completed_status), event="queue_run_completed", payload={"result_count": len(results)}, now=_utc_now())
        self.project_store.append_event(project_id, "review_sprint_action_queue_completed", {"sprint_id": sprint.sprint_id, "queue_id": queue.queue_id, "status": queue.status})
        refreshed_sprint = sprint_store.read_sprint(sprint.sprint_id)
        response = self._review_sprint_response(sprint_store, task_store, refreshed_sprint)
        response.update({"queue": queue.to_dict(), "queue_events": queue_store.read_events(queue.queue_id), "results": sanitize_metadata(results), "action_queue_summary": action_queue_summary(queue)})
        return response

    def _execute_review_sprint_action_item(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        queue: SprintActionQueue,
        item: SprintActionItem,
    ) -> SprintActionItem:
        if item.safety in {"manual_required", "informational"}:
            return replace(item, status="manual_required" if item.safety == "manual_required" else "skipped", completed_at=_utc_now())
        if item.safety == "blocked":
            return replace(item, status="blocked", error=item.error or "Action item is blocked.", completed_at=_utc_now())
        if item.action == "refresh_conflicts":
            sprint, report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
            return replace(item, status="completed", result={"conflict_count": len(report.get("conflicts", []))}, completed_at=_utc_now())
        if item.action == "refresh_recommendations":
            sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
            report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
            return replace(item, status="completed", result={"recommended_count": len(report.get("recommended_order", [])), "created_at": report.get("created_at")}, completed_at=_utc_now())
        report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        if queue_report_is_stale(queue, report):
            return replace(item, status="blocked", error="Action queue is stale because the Recommendation Report changed. Recreate the queue.", completed_at=_utc_now())
        task = self._ensure_action_item_task_current(project_id, task_store, sprint, item)
        if item.action == "save_recommended_context_pack":
            result = self._execute_queue_context_pack_action(project_id, sprint_store, task_store, sprint, item)
        elif item.action == "generate_local_candidates":
            result = self._generate_review_task_local_candidates_for_queue(project_id, task_store, task, item.input)
        elif item.action == "generate_provider_candidates":
            result = self._generate_review_task_provider_candidates_for_queue(project_id, task_store, task, item.input)
        elif item.action == "refresh_judge_report":
            result = self._refresh_review_task_judge_report(project_id, task_store, task, item.input)
            result["sprint_judge_summary"] = self._get_or_refresh_sprint_judge_summary(project_id, sprint_store, task_store, sprint, refresh=True)
        elif item.action == "refresh_decision_report":
            result = self._refresh_review_task_decision_report_for_queue(project_id, task_store, task, item.input)
        else:
            result = {"message": "Action is not executable from the queue."}
            return replace(item, status="skipped", result=result, completed_at=_utc_now())
        self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint_store.read_sprint(sprint.sprint_id))
        return replace(item, status="completed", result=sanitize_metadata(result), error=None, completed_at=_utc_now())

    def _ensure_action_item_task_current(self, project_id: str, task_store: ReviewTaskStore, sprint: Any, item: SprintActionItem) -> Any:
        if not item.task_id or item.task_id not in self._review_sprint_ordered_task_ids(sprint):
            raise ReviewSprintStateError("Action item task is no longer in this sprint.")
        task = task_store.read_task(item.task_id)
        if task.project_id != project_id:
            raise FileNotFoundError(item.task_id)
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        ensure_task_current(task, parent_plan)
        return task

    def _generate_review_task_local_candidates_for_queue(self, project_id: str, task_store: ReviewTaskStore, task: Any, payload: dict[str, Any]) -> dict[str, Any]:
        candidates = task_store.list_candidates(task.task_id)
        if bool(payload.get("skip_existing_ready", True)) and any(candidate.candidate_type == "local_review_intents" and candidate.status in {"ready", "applied"} for candidate in candidates):
            return {"status": "skipped", "reason": "ready local candidate exists", "created_count": 0, "created_candidate_ids": []}
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        ensure_task_current(task, parent_plan)
        strategies = payload.get("strategies") if isinstance(payload.get("strategies"), list) else ["balanced"]
        render_midi = bool(payload.get("render_midi", True))
        generated = []
        for candidate, candidate_plan, validator, summary in build_local_review_candidates(task, parent_plan, strategies=strategies):
            generated.append(task_store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=render_midi, now=_utc_now()))
        ranked = task_store.rank_candidates(task)
        updated_task = task_store.update_counts(task, now=_utc_now())
        decision_report = task_store.write_decision_report(updated_task, build_review_decision_report(task=updated_task, candidates=ranked, parent_plan=parent_plan, now=_utc_now()), now=_utc_now())
        self.project_store.append_event(project_id, "review_sprint_action_local_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated)})
        return {"status": "generated" if generated else "skipped", "created_count": len(generated), "created_candidate_ids": [candidate.candidate_id for candidate in generated], "decision_report": review_decision_summary(decision_report), "provider_summary": review_candidate_source_breakdown(ranked)}

    def _read_review_task_judge_report(self, project_id: str, task_store: ReviewTaskStore, task: Any, candidates: list[Any] | None = None, *, parent_plan: SongPlan | None = None) -> dict[str, Any]:
        report = task_store.read_judge_report(task.task_id, default={})
        if not report:
            return {}
        try:
            if parent_plan is None:
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
            template_id = str(report.get("template_id") or REVIEW_JUDGE_TEMPLATE_ID)
            template = self.prompt_template_store.get_template(template_id)
            return read_judge_report_with_stale(task_store, task, candidates=candidates, parent_plan=parent_plan, template=template)
        except (FileNotFoundError, ProviderError, ReviewTaskError, ReviewTaskStateError, ValueError, TypeError):
            return mark_judge_report_stale(report, stale=True)

    def _refresh_review_task_judge_report(self, project_id: str, task_store: ReviewTaskStore, task: Any, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        ensure_task_current(task, parent_plan)
        template_id = str(payload.get("template_id") or REVIEW_JUDGE_TEMPLATE_ID).strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise ReviewTaskStateError("Prompt template is disabled.")
        all_candidates = task_store.rank_candidates(task)
        requested_ids = [str(item) for item in payload.get("candidate_ids", []) if str(item).strip()] if isinstance(payload.get("candidate_ids"), list) else []
        candidates = [candidate for candidate in all_candidates if not requested_ids or candidate.candidate_id in requested_ids]
        candidates = [candidate for candidate in candidates if candidate.status == "ready"]
        if not candidates:
            raise ReviewTaskStateError("Review judge requires at least one ready candidate.")
        decision_report = _try_read_review_decision_report(task_store, task.task_id)
        config, _sources = load_provider_config()
        started_at = _utc_now()
        report, provider_snapshot = run_provider_review_judge(
            project_id=project_id,
            task=task,
            candidates=candidates,
            parent_plan=parent_plan,
            template=template,
            config=config,
            decision_report=decision_report,
            note=str(payload.get("note") or ""),
            now=_utc_now(),
        )
        saved = task_store.write_judge_report(task, report, now=_utc_now())
        provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
        usage_record = _provider_usage_record(
            config_snapshot=provider_snapshot,
            operation="provider_review_judge",
            template_id=template.template_id,
            started_at=started_at,
            status="completed",
            provider_usage=provider_usage,
            request_id=provider_snapshot.get("request_id"),
        )
        write_interface_document(task_store.judge_provider_usage_path(task.task_id), usage_record)
        ranked = task_store.rank_candidates(task)
        refreshed_decision = task_store.write_decision_report(
            task,
            build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("decision_note") or ""), judge_report=saved),
            now=_utc_now(),
        )
        self.project_store.append_event(project_id, "review_task_judge_report_refreshed", {"task_id": task.task_id, "recommended_candidate_id": saved.get("recommended_candidate_id"), "template_id": template.template_id})
        return {"ok": True, "task": task.to_dict(), "judge_report": saved, "summary": judge_report_summary(saved), "decision_report": refreshed_decision, "provider_snapshot": provider_snapshot}

    def _refresh_review_task_decision_report_for_queue(self, project_id: str, task_store: ReviewTaskStore, task: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        ensure_task_current(task, parent_plan)
        ranked = task_store.rank_candidates(task)
        judge_report = self._read_review_task_judge_report(project_id, task_store, task, ranked, parent_plan=parent_plan)
        decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("note") or ""), judge_report=judge_report), now=_utc_now())
        self.project_store.append_event(project_id, "review_sprint_action_decision_report_refreshed", {"task_id": task.task_id, "recommended_candidate_id": decision_report.get("recommended_candidate_id")})
        return {"decision_report": review_decision_summary(decision_report), "provider_summary": review_candidate_source_breakdown(ranked), "candidate_count": len(ranked)}

    def _set_action_item(
        self,
        queue_store: ReviewSprintActionQueueStore,
        queue: SprintActionQueue,
        item: SprintActionItem,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        event: str | None = None,
    ) -> SprintActionItem:
        now = _utc_now()
        updated_item = replace(
            item,
            status=status,
            result=sanitize_metadata(result if result is not None else item.result),
            error=None if error is None else str(sanitize_metadata({"error": error}).get("error") or ""),
            started_at=now if status == "running" else item.started_at,
            completed_at=now if status in {"completed", "failed", "skipped", "blocked", "manual_required"} else item.completed_at,
            attempt=item.attempt + 1 if status == "running" else item.attempt,
        )
        items = [updated_item if existing.item_id == item.item_id else existing for existing in queue.items]
        updated_queue = replace(queue, items=items)
        queue_store.update_queue(updated_queue, event=event, payload={"item_id": item.item_id, "action": item.action, "status": status}, now=now)
        return updated_item

    def _apply_review_task_candidate(
        self,
        project_id: str,
        task_store: ReviewTaskStore,
        task: Any,
        candidate: Any,
        parent: Any,
        parent_job: JobState,
        parent_plan: SongPlan,
        payload: dict[str, Any],
    ) -> tuple[Any, Any, Any, JobState, Any]:
        _ensure_task_open_for_apply(task)
        if candidate.status != "ready":
            raise ReviewTaskStateError("Candidate is not ready.")
        result = apply_candidate_intents(parent_plan, [EditIntent.from_dict(item) for item in candidate.intents])
        primary = EditIntent.from_dict(candidate.intents[0])
        name = str(payload.get("name") or payload.get("version_name") or f"Review Candidate {candidate.candidate_id}")
        job = self.store.create_edit_job(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_job=parent_job,
            parent_plan=parent_plan,
            intent=primary,
            name=name,
            start_immediately=False,
            asset_refs=payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else None,
            reference_refs=payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else None,
            context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
        )
        decision_report = _try_read_review_decision_report(task_store, task.task_id)
        judge_report = self._read_review_task_judge_report(project_id, task_store, task, task_store.list_candidates(task.task_id), parent_plan=parent_plan)
        metadata = {
            **job.edit_metadata,
            **candidate_apply_metadata(task, candidate, result, decision_report=decision_report),
            "edit_type": primary.edit_type,
            "target": primary.target.to_dict(),
            "instruction": primary.instruction,
            "preserve": list(primary.preserve),
            "strength": primary.strength,
        }
        judge_apply_summary = judge_summary_for_apply(judge_report, candidate_id=candidate.candidate_id, stale=bool(judge_report.get("stale"))) if judge_report else {}
        if judge_apply_summary:
            metadata["review_judge"] = judge_apply_summary
        sprint_membership = self._review_sprint_membership_summary(project_id, task.task_id)
        if sprint_membership:
            metadata["review_sprint"] = sprint_membership
        sprint_recommendation = self._review_sprint_recommendation_summary_for_task(project_id, task.task_id)
        if sprint_recommendation:
            metadata["review_sprint_recommendation"] = sprint_recommendation
        sprint_action_queue = self._review_sprint_action_queue_summary_for_task(project_id, task.task_id)
        if sprint_action_queue:
            metadata["review_sprint_action_queue"] = sprint_action_queue
        job.edit_metadata = metadata
        job.input_payload["review_task_id"] = task.task_id
        job.input_payload["review_candidate_id"] = candidate.candidate_id
        job.input_payload["review_task"] = review_task_summary(task, candidate)
        job.input_payload["review_candidate"] = review_candidate_summary(candidate)
        if decision_report:
            job.input_payload["review_decision"] = review_decision_summary(decision_report)
        if judge_apply_summary:
            job.input_payload["review_judge"] = judge_apply_summary
        if sprint_membership:
            job.input_payload["review_sprint"] = sprint_membership
        if sprint_recommendation:
            job.input_payload["review_sprint_recommendation"] = sprint_recommendation
        if sprint_action_queue:
            job.input_payload["review_sprint_action_queue"] = sprint_action_queue
        persist_interface_job(self.store, job)
        write_interface_document(ProjectPaths.create(Path(job.output_dir)).data / "edit-metadata.json", metadata)
        self.store.start_job(job.job_id)
        document = self.project_store.add_version_from_job(
            project_id,
            job,
            name=name,
            note=str(payload.get("note") or payload.get("version_note") or ""),
            parent_version_id=parent.version_id,
            variant_type=edit_variant_type(primary.edit_type),
            change_summary=str(payload.get("change_summary") or f"Review task {task.task_id} candidate {candidate.candidate_id}"),
        )
        version = next(version for version in document.versions if version.job_id == job.job_id)
        candidate = task_store.update_candidate(
            type(candidate).from_dict({**candidate.to_dict(), "status": "applied"}),
            event="review_candidate_applied",
            payload={"version_id": version.version_id, "job_id": job.job_id},
            now=_utc_now(),
        )
        task = task_store.update_task(
            type(task).from_dict(
                {
                    **task.to_dict(),
                    "status": "applied",
                    "selected_candidate_id": candidate.candidate_id,
                    "applied_version_id": version.version_id,
                    "applied_job_id": job.job_id,
                }
            ),
            event="review_task_candidate_applied",
            payload={"candidate_id": candidate.candidate_id, "version_id": version.version_id, "job_id": job.job_id},
            now=_utc_now(),
        )
        self.project_store.append_event(project_id, "review_task_candidate_applied", {"task_id": task.task_id, "candidate_id": candidate.candidate_id, "version_id": version.version_id, "job_id": job.job_id})
        return task, candidate, version, job, result

    def _create_review_task_follow_up(self, project_id: str, task_store: ReviewTaskStore, task: Any, payload: dict[str, Any]) -> tuple[Any, Any]:
        if task.status != "applied" or not task.applied_version_id:
            raise ReviewTaskStateError("Only applied review tasks can be marked needs_more_work.")
        candidate = task_store.read_candidate(task.task_id, task.selected_candidate_id or "")
        _document, parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.applied_version_id)
        preview = EditorPreviewStore(self.project_store.project_dir(project_id)).read_preview(task.preview_id)
        audition_store = EditorAuditionStore(self.project_store.project_dir(project_id))
        audition = audition_store.read_audition(task.preview_id, task.audition_id)
        audition_plan = audition_store.read_plan(task.preview_id, task.audition_id)
        follow_up = task_store.create_task(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_plan=parent_plan,
            preview=preview,
            audition=audition,
            audition_plan=audition_plan,
            payload={
                "title": payload.get("title") or f"Follow-up for {task.task_id}",
            },
            previous={
                "previous_task_id": task.task_id,
                "previous_candidate_id": candidate.candidate_id,
                "previous_applied_version_id": task.applied_version_id,
            },
            now=_utc_now(),
        )
        task = task_store.update_task(
            type(task).from_dict({**task.to_dict(), "status": "needs_more_work", "follow_up_task_id": follow_up.task_id, "resolution_note": str(payload.get("note") or "")}),
            event="review_task_needs_more_work",
            payload={"follow_up_task_id": follow_up.task_id, "note": payload.get("note") or ""},
            now=_utc_now(),
        )
        self.project_store.append_event(project_id, "review_task_needs_more_work", {"task_id": task.task_id, "follow_up_task_id": follow_up.task_id, "version_id": task.applied_version_id})
        return task, follow_up

    def _rollback_prompt_ab_groups(self, project_id: str, group_ids: list[str]) -> None:
        if not group_ids:
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            group_store = CandidateGroupStore(project_dir)
            deleted = []
            for group_id in group_ids:
                try:
                    group_store.delete_group(group_id)
                    deleted.append(group_id)
                except (FileNotFoundError, ValueError):
                    continue
            if deleted:
                self.project_store.append_event(project_id, "provider_prompt_ab_rolled_back", {"group_ids": deleted})
        except (FileNotFoundError, ValueError):
            return

    def _send_runtime_view(self, job: JobState, view_name: str) -> None:
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        validator_path = run_dir / "data" / "validator-report.json"
        if view_name in {"timeline", "tracks", "quality"} and not plan_path.exists():
            self._send_error(
                HTTPStatus.CONFLICT,
                "song-plan.json is not available for this job yet.",
            )
            return

        if view_name == "validator":
            report = read_json(validator_path) if validator_path.exists() else None
            plan = read_json(plan_path) if plan_path.exists() else None
            self._send_json(
                {
                    "job_id": job.job_id,
                    "view": build_validator_view(report, plan),
                }
            )
            return
        if view_name == "quality":
            plan = read_json(plan_path)
            critic_report = _read_critic_report(run_dir)
            self._send_json(
                {
                    "job_id": job.job_id,
                    "view": build_quality_view(plan, critic_report),
                }
            )
            return

        plan = read_json(plan_path)
        if view_name == "timeline":
            view = build_timeline_view(plan)
        elif view_name == "tracks":
            view = build_tracks_view(plan)
        else:
            self._send_error(HTTPStatus.NOT_FOUND, "Runtime view not found.")
            return
        self._send_json({"job_id": job.job_id, "view": view})

    def _send_nodes_list(self, job: JobState) -> None:
        records = NodeStore(Path(job.output_dir)).list_nodes()
        self._send_json(
            {
                "job_id": job.job_id,
                "nodes": [record.to_summary_dict() for record in records],
            }
        )

    def _send_node_retry(self, method: str, job: JobState, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "nodes" or parts[2] != "retry":
            self._send_error(HTTPStatus.NOT_FOUND, "Node route not found.")
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        node_name = unquote(parts[1])
        job, status, error, retry = self.store.retry_job_node(job.job_id, node_name)
        if error is not None:
            self._send_error(status, error)
            return
        self._send_json(
            {"ok": True, "job": job.to_dict() if job is not None else None, "retry": retry},
            status=status,
        )

    def _send_node_route(self, method: str, job: JobState, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) == 2:
            _nodes, node_name = parts
            try:
                record = NodeStore(Path(job.output_dir)).read_node(unquote(node_name))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Node record not found.")
                return
            self._send_json({"job_id": job.job_id, "node": record.to_dict()})
            return
        if len(parts) == 3 and parts[2] == "dependencies":
            try:
                node_name = unquote(parts[1])
                upstream = upstream_nodes(node_name)
                downstream = downstream_nodes(node_name)
            except ValueError as exc:
                if str(exc).startswith("Unknown node:"):
                    self._send_error(HTTPStatus.NOT_FOUND, "Node record not found.")
                    return
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(
                {
                    "job_id": job.job_id,
                    "node": node_name,
                    "upstream": upstream,
                    "downstream": downstream,
                    "affected_nodes": [node_name, *downstream],
                }
            )
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Node route not found.")

    def _send_stem_file(self, job: JobState, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "stems" or parts[2] not in {"midi", "audio"}:
            self._send_error(HTTPStatus.NOT_FOUND, "Stem route not found.")
            return
        stem_id = unquote(parts[1])
        run_dir = Path(job.output_dir)
        manifest = read_stem_manifest(run_dir)
        if manifest is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Stem manifest not found.")
            return
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            if stem_manifest_stale(manifest, plan):
                clear_stem_artifacts(run_dir)
                self._send_error(HTTPStatus.CONFLICT, "Stem manifest is stale. Render stems again.")
                return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        try:
            if parts[2] == "midi":
                self._send_file(stem_midi_path(run_dir, manifest, stem_id), "audio/midi")
            else:
                self._send_file(stem_audio_path(run_dir, manifest, stem_id), "audio/wav")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Stem not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            raise ValueError("Request body must be JSON.")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _optional_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            return {}
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _merge_editor_patch_metadata(self, left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
        return _merge_editor_patch_metadata(left, right)

    def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str | None = None, *, filename: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "File not found.")
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header(
            "Content-Type",
            content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", _content_disposition_filename(filename or path.name))
        self.end_headers()
        self.wfile.write(body)

    def _content_length_within(self, limit: int) -> bool:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return False
        return 0 <= length <= limit

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _send_unauthorized(self) -> None:
        body = b'{\n  "error": "Unauthorized."\n}'
        self.send_response(HTTPStatus.UNAUTHORIZED.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("WWW-Authenticate", "Bearer")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_required(self, path: str) -> bool:
        if not self.auth_config.enabled:
            return False
        if path == "/" or path == "/api/info":
            return False
        return True

    def _is_authorized(self) -> bool:
        token = self.auth_config.token
        if not token:
            return False
        return validate_bearer_header(self.headers.get("Authorization"), token)
