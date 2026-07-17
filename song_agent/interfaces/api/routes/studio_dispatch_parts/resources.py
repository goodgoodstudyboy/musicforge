from __future__ import annotations

from song_agent.interfaces.api.route_contexts.studio_dispatch import StudioDispatchRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioResourcesDispatch(StudioDispatchRouteContext):
    def _dispatch_studio_resources(self, method, path, parsed) -> bool:
        if path == '/api/releases':
            self._handle_releases_root(method, parsed.query)
            return True
        if path == '/api/acceptance/suites':
            self._handle_acceptance_suites_root(method, parsed.query)
            return True
        if path == '/api/acceptance/profiles':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self._send_json({'ok': True, 'profiles': _interfaces_api_runtime.list_acceptance_profiles()})
            return True
        if path == '/api/acceptance/songbook':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self._send_json({'ok': True, 'songbook': _interfaces_api_runtime.builtin_songbook()})
            return True
        if path == '/api/acceptance/fix-sprints':
            self._handle_acceptance_fix_sprints_root(method, parsed.query)
            return True
        if path == '/api/acceptance/fix-plans':
            self._handle_acceptance_fix_plans_root(method, parsed.query)
            return True
        if path == '/api/acceptance/fix-plans/recommend':
            self._handle_acceptance_fix_plans_recommend(method)
            return True
        if path == '/api/acceptance/fix-plan-reviews':
            self._handle_acceptance_fix_plan_reviews_root(method, parsed.query)
            return True
        if path == '/api/acceptance/planning-rulesets':
            self._handle_planning_rulesets_root(method, parsed.query)
            return True
        return False
