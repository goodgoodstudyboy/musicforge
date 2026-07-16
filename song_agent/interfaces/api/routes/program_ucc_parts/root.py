from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class ProgramUccRootRoutes:
    def _dispatch_ucc_root(self, method, path) -> bool:
        if path == '/api/unified-command-centers':
            if method == 'GET':
                centers = self.unified_command_center_store.list_centers()
                self._send_json({'ok': True, 'centers': centers, 'summary': {'center_count': len(centers)}})
                return True
            if method == 'POST':
                center = self.unified_command_center_store.create(self._optional_json_body())
                self._send_json({'ok': True, 'center': center, 'summary': {'center_id': center.get('center_id')}, 'status': center.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        return False
