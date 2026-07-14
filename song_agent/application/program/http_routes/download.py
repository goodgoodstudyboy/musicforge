from __future__ import annotations

from http import HTTPStatus

class ProgramDownloadHttpRoutes:
    def _dispatch_download(self, method, program_id, tail) -> bool:
        if tail == '/download':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
        return False
