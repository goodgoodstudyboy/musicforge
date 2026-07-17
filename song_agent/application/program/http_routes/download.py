from __future__ import annotations

from song_agent.application.program.http_context import ProgramHttpContext

from http import HTTPStatus

class ProgramDownloadHttpRoutes(ProgramHttpContext):
    def _dispatch_download(self, method, program_id, tail) -> bool:
        if tail == '/download':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
        return False
