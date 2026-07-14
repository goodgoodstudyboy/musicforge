from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioDistributionDispatch:
    def _dispatch_studio_distribution(self, method, path, parsed) -> bool:
        if path == '/api/distribution/profiles':
            self._handle_distribution_profiles_root(method)
            return True
        if path == '/api/distribution/template-packs':
            self._handle_distribution_templates_root(method)
            return True
        distribution_template_route = _match_distribution_template_route(path)
        if distribution_template_route is not None:
            self._handle_distribution_template_route(method, distribution_template_route)
            return True
        if path == '/api/distribution/template-packs/import':
            self._handle_distribution_template_import(method, parsed.query)
            return True
        distribution_profile_route = _match_distribution_profile_route(path)
        if distribution_profile_route is not None:
            self._handle_distribution_profile_route(method, distribution_profile_route)
            return True
        if path == '/api/usage/provider':
            self._handle_provider_usage_root(method)
            return True
        return False
