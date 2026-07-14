from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioRoutesPart005:
    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str | None = None, *, filename: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "File not found.")
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header(
            "Content-Type",
            content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", _content_disposition_filename(filename or path.name))
        self.end_headers()
        self.wfile.write(body)

    def _content_length_within(self, limit: int) -> bool:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return False
        return 0 <= length <= limit

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _send_unauthorized(self) -> None:
        body = b'{\n  "error": "Unauthorized."\n}'
        self.send_response(HTTPStatus.UNAUTHORIZED.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("WWW-Authenticate", "Bearer")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_required(self, path: str) -> bool:
        if not self.auth_config.enabled:
            return False
        if path == "/" or path == "/api/info":
            return False
        return True

    def _is_authorized(self) -> bool:
        token = self.auth_config.token
        if not token:
            return False
        return validate_bearer_header(self.headers.get("Authorization"), token)
