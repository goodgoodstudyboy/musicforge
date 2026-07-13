from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundedContextSpec:
    context_id: str
    owns: tuple[str, ...]
    public_api: str


BOUNDED_CONTEXTS = (
    BoundedContextSpec("creation", ("song request", "composition", "render jobs"), "song_agent.domains.creation"),
    BoundedContextSpec("studio", ("projects", "versions", "editing"), "song_agent.domains.studio"),
    BoundedContextSpec("quality", ("audio review", "campaigns", "certification"), "song_agent.domains.quality"),
    BoundedContextSpec("delivery", ("release", "distribution", "submission"), "song_agent.domains.delivery"),
    BoundedContextSpec("trust", ("operations", "public trust", "assurance"), "song_agent.domains.trust"),
    BoundedContextSpec("program", ("program", "vault", "continuity", "handoff"), "song_agent.domains.program"),
)
