from __future__ import annotations

from song_agent.interfaces.api.route_contexts.program_ucc import ProgramUccRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class ProgramUccEvidence_RootRoutes(ProgramUccRouteContext):
    def _dispatch_ucc_evidence_root(self, method, center_id, tail) -> bool:
        if tail == '/evidence-reviews':
            if method == 'GET':
                reviews = self.unified_command_center_evidence_review_store.list_reviews(center_id)
                self._send_json({'ok': True, 'reviews': reviews, 'summary': {'review_count': len(reviews)}})
                return True
            if method == 'POST':
                docs = self.unified_command_center_evidence_review_store.create_review(center_id, self._optional_json_body())
                source = docs.get('source', {})
                self._send_json({'ok': True, 'review': docs, 'summary': {'review_id': source.get('review_id')}, 'status': source.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        return False
