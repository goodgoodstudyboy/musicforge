from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioAcceptance_ItemsDispatch:
    def _dispatch_studio_acceptance_items(self, method, path, parsed) -> bool:
        fix_plan_review_route = _interfaces_api_runtime._match_acceptance_fix_plan_review_route(path)
        if fix_plan_review_route is not None:
            self._handle_acceptance_fix_plan_review_route(method, fix_plan_review_route)
            return True
        fix_plan_route = _interfaces_api_runtime._match_acceptance_fix_plan_route(path)
        if fix_plan_route is not None:
            self._handle_acceptance_fix_plan_route(method, fix_plan_route)
            return True
        if path == '/api/acceptance/kb':
            self._handle_acceptance_kb_root(method)
            return True
        if path == '/api/acceptance/kb/refresh':
            self._handle_acceptance_kb_refresh(method)
            return True
        if path == '/api/acceptance/kb/entries':
            self._handle_acceptance_kb_entries(method, parsed.query)
            return True
        if path == '/api/acceptance/kb/search':
            self._handle_acceptance_kb_search(method, parsed.query)
            return True
        if path == '/api/acceptance/kb/recommend':
            self._handle_acceptance_kb_recommend(method)
            return True
        kb_entry_route = _interfaces_api_runtime._match_acceptance_kb_entry_route(path)
        if kb_entry_route is not None:
            self._handle_acceptance_kb_entry_route(method, kb_entry_route)
            return True
        kb_report_id = _interfaces_api_runtime._match_acceptance_kb_report_route(path)
        if kb_report_id is not None:
            self._handle_acceptance_kb_report(method, kb_report_id)
            return True
        fix_sprint_route = _interfaces_api_runtime._match_acceptance_fix_sprint_route(path)
        if fix_sprint_route is not None:
            self._handle_acceptance_fix_sprint_route(method, fix_sprint_route)
            return True
        if path == '/api/acceptance/analytics':
            self._handle_acceptance_analytics_root(method, parsed.query)
            return True
        if path == '/api/acceptance/analytics/refresh':
            self._handle_acceptance_analytics_refresh(method, parsed.query)
            return True
        analytics_recommendation_route = _interfaces_api_runtime._match_acceptance_analytics_recommendation_route(path)
        if analytics_recommendation_route is not None:
            report_id, recommendation_id = analytics_recommendation_route
            self._handle_acceptance_analytics_recommendation(method, report_id, recommendation_id)
            return True
        analytics_report_route = _interfaces_api_runtime._match_acceptance_analytics_report_route(path)
        if analytics_report_route is not None:
            self._handle_acceptance_analytics_report(method, analytics_report_route)
            return True
        return False
