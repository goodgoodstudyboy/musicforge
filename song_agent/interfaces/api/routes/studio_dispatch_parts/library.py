from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioLibraryDispatch:
    def _dispatch_studio_library(self, method, path, parsed) -> bool:
        if path == '/api/assets':
            self._handle_assets_root(method, parsed.query)
            return True
        if path == '/api/assets/extract/from-job':
            self._handle_asset_extract_from_job(method)
            return True
        if path == '/api/assets/extract/from-project-version':
            self._handle_asset_extract_from_project_version(method)
            return True
        if path == '/api/assets/extract/from-candidate':
            self._handle_asset_extract_from_candidate(method)
            return True
        if path == '/api/library/index':
            self._handle_library_index(method)
            return True
        if path == '/api/library/rebuild':
            self._handle_library_rebuild(method)
            return True
        if path == '/api/library/search':
            self._handle_library_search(method)
            return True
        if path == '/api/library/recommend':
            self._handle_library_recommend(method)
            return True
        if path == '/api/context-packs':
            self._handle_context_packs_root(method, parsed.query)
            return True
        if path == '/api/references':
            self._handle_references_root(method, parsed.query)
            return True
        if path == '/api/references/import':
            self._handle_reference_import(method)
            return True
        if path == '/api/edit-presets':
            self._handle_edit_presets_root(method)
            return True
        if path == '/api/edit-presets/reset':
            self._handle_edit_presets_reset(method)
            return True
        if path == '/api/prompt-templates':
            self._handle_prompt_templates_root(method)
            return True
        if path == '/api/prompt-templates/reset':
            self._handle_prompt_templates_reset(method)
            return True
        if path == '/api/editor-templates':
            self._handle_editor_templates_root(method, parsed.query)
            return True
        return False
