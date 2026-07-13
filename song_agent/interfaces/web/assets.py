from __future__ import annotations

from importlib.resources import files


_ROOT = files("song_agent.interfaces.web")


def _read(relative: str) -> str:
    return _ROOT.joinpath(relative).read_text(encoding="utf-8")


def panel_html() -> str:
    template = _read("index.html")
    return (
        template.replace("{{MUSICFORGE_STYLES}}", _read("styles/studio.css"))
        .replace("{{MUSICFORGE_SCRIPTS}}", _read("scripts/app.js"))
    )
