from __future__ import annotations

from song_agent.interfaces.api.route_contexts.studio_dispatch import StudioDispatchRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioDistributionDispatch(StudioDispatchRouteContext):
    def _dispatch_studio_distribution(self, method, path, parsed) -> bool:
        if path == '/api/distribution/profiles':
            self._handle_distribution_profiles_root(method)
            return True
        if path == '/api/distribution/template-packs':
            self._handle_distribution_templates_root(method)
            return True
        distribution_template_route = _interfaces_api_runtime._match_distribution_template_route(path)
        if distribution_template_route is not None:
            self._handle_distribution_template_route(method, distribution_template_route)
            return True
        if path == '/api/distribution/template-packs/import':
            self._handle_distribution_template_import(method, parsed.query)
            return True
        distribution_profile_route = _interfaces_api_runtime._match_distribution_profile_route(path)
        if distribution_profile_route is not None:
            self._handle_distribution_profile_route(method, distribution_profile_route)
            return True
        if path == '/api/usage/provider':
            self._handle_provider_usage_root(method)
            return True
        return False
