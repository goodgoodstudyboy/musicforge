from __future__ import annotations

from http import HTTPStatus

class ProgramRootHttpRoutes:
    def _dispatch_root(self, method, path) -> bool:
        if path == '/api/unified-release-programs':
            if method == 'GET':
                programs = self.unified_release_program_store.list_programs()
                self._send_json({'ok': True, 'programs': programs, 'summary': {'program_count': len(programs)}})
                return True
            if method == 'POST':
                program = self.unified_release_program_store.create_program(self._optional_json_body())
                self._send_json({'ok': True, 'program': program, 'summary': {'program_id': program.get('program_id')}, 'status': program.get('status')}, status=HTTPStatus.CREATED)
                return True
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        return False
