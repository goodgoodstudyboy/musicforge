from __future__ import annotations

from song_agent.interfaces.api.route_contexts.studio import StudioRouteContext

from http import HTTPStatus
from pathlib import Path

import song_agent.interfaces.api.runtime as _interfaces_api_runtime
from song_agent.platform.contracts.documents import JsonDocument


class StudioRoutesSendHtml(StudioRouteContext):
    def _read_json_body(self) -> JsonDocument:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            raise ValueError("Request body must be JSON.")
        data = _interfaces_api_runtime.json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _optional_json_body(self) -> JsonDocument:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            return {}
        data = _interfaces_api_runtime.json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _merge_editor_patch_metadata(self, left: JsonDocument | None, right: JsonDocument | None) -> JsonDocument:
        return _interfaces_api_runtime._merge_editor_patch_metadata(left, right)

    def _send_json(self, data: JsonDocument, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = _interfaces_api_runtime.json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(_interfaces_api_runtime.HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str | None = None, *, filename: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "File not found.")
            return
        body = path.read_bytes()
        self.send_response(_interfaces_api_runtime.HTTPStatus.OK.value)
        self.send_header(
            "Content-Type",
            content_type or _interfaces_api_runtime.mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", _interfaces_api_runtime._content_disposition_filename(filename or path.name))
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
        self.send_response(_interfaces_api_runtime.HTTPStatus.UNAUTHORIZED.value)
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
        return _interfaces_api_runtime.validate_bearer_header(self.headers.get("Authorization"), token)
