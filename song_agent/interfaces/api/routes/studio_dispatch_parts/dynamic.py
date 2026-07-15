from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioDynamicDispatch:
    def _dispatch_studio_dynamic(self, method, path, parsed) -> bool:
        editor_template_route = _interfaces_api_runtime._match_editor_template_route(path)
        if editor_template_route is not None:
            template_type, template_id, tail = editor_template_route
            self._handle_editor_template_route(method, template_type, template_id, tail)
            return True
        prompt_template_route = _interfaces_api_runtime._match_prompt_template_route(path)
        if prompt_template_route is not None:
            template_id, tail = prompt_template_route
            self._handle_prompt_template_route(method, template_id, tail)
            return True
        edit_preset_route = _interfaces_api_runtime._match_edit_preset_route(path)
        if edit_preset_route is not None:
            preset_id, tail = edit_preset_route
            self._handle_edit_preset_route(method, preset_id, tail)
            return True
        asset_route = _interfaces_api_runtime._match_asset_route(path)
        if asset_route is not None:
            asset_id, tail = asset_route
            self._handle_asset_route(method, asset_id, tail)
            return True
        reference_route = _interfaces_api_runtime._match_reference_route(path)
        if reference_route is not None:
            reference_id, tail = reference_route
            self._handle_reference_route(method, reference_id, tail)
            return True
        context_pack_route = _interfaces_api_runtime._match_context_pack_route(path)
        if context_pack_route is not None:
            pack_id, tail = context_pack_route
            self._handle_context_pack_route(method, pack_id, tail)
            return True
        project_route = _interfaces_api_runtime._match_project_route(path)
        if project_route is not None:
            project_id, tail = project_route
            self._handle_project_route(method, project_id, tail, parsed.query)
            return True
        release_route = _interfaces_api_runtime._match_release_route(path)
        if release_route is not None:
            release_id, tail = release_route
            self._handle_release_route(method, release_id, tail, parsed.query)
            return True
        acceptance_route = _interfaces_api_runtime._match_acceptance_route(path)
        if acceptance_route is not None:
            suite_id, tail = acceptance_route
            self._handle_acceptance_route(method, suite_id, tail)
            return True
        batch_route = _interfaces_api_runtime._match_batch_route(path)
        if batch_route is not None:
            batch_id, tail = batch_route
            self._handle_batch_route(method, batch_id, tail)
            return True
        job_route = _interfaces_api_runtime._match_job_route(path)
        if job_route is not None:
            job_id, tail = job_route
            self._handle_job_route(method, job_id, tail)
            return True
        return False
