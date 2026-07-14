from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioResourcesDispatch:
    def _dispatch_studio_resources(self, method, path, parsed) -> bool:
        if path == '/api/releases':
            self._handle_releases_root(method, parsed.query)
            return True
        if path == '/api/acceptance/suites':
            self._handle_acceptance_suites_root(method, parsed.query)
            return True
        if path == '/api/acceptance/profiles':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self._send_json({'ok': True, 'profiles': list_acceptance_profiles()})
            return True
        if path == '/api/acceptance/songbook':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self._send_json({'ok': True, 'songbook': builtin_songbook()})
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
