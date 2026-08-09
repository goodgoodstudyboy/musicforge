from __future__ import annotations

from song_agent.application.program.http_context import ProgramHttpContext

from http import HTTPStatus

class ProgramRootHttpRoutes(ProgramHttpContext):
    def _dispatch_root(self, method, path) -> bool:
        if path == '/api/unified-release-programs':
            if method == 'GET':
                programs = self.service.list_programs()
                self._send_json({'ok': True, 'programs': programs, 'summary': {'program_count': len(programs)}})
                return True
            if method == 'POST':
                program = self.service.create_program(self._optional_json_body())
                self._send_json({'ok': True, 'program': program, 'summary': {'program_id': program.get('program_id')}, 'status': program.get('status')}, status=HTTPStatus.CREATED)
                return True
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        return False
