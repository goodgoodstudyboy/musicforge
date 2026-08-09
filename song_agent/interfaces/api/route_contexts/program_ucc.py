from __future__ import annotations

from typing import Protocol

from song_agent.application.program.http_context import ErrorSender, JsonBodyReader, JsonSender
from song_agent.interfaces.api.route_contexts.program import FileSender, ProgramServerPort
from song_agent.platform.contracts.documents import JsonDocument


class EvidencePayloadBuilder(Protocol):
    def __call__(self, payload: JsonDocument) -> JsonDocument: ...


class ProgramUccRouteContext(ProgramServerPort, Protocol):
    """Static UCC route contract supplied by API composition."""

    server: ProgramServerPort
    _optional_json_body: JsonBodyReader
    _read_json_body: JsonBodyReader
    _send_error: ErrorSender
    _send_file: FileSender
    _send_json: JsonSender
    _unified_command_center_evidence_from_payload: EvidencePayloadBuilder
