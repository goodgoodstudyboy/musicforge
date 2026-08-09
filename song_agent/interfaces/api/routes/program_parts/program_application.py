from __future__ import annotations

from song_agent.application.program.http_context import ProgramServicePort
from song_agent.interfaces.api.route_contexts.program import ProgramRouteContext


class ProgramRoutesProgramApplication(ProgramRouteContext):
    @property
    def program_application(self) -> ProgramServicePort:
        return self.server.program_application_service
