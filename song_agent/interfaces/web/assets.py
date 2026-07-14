from __future__ import annotations

import json
import re
from importlib.resources import files


_ROOT = files("song_agent.interfaces.web")
_SCRIPT_PATH = re.compile(r"^[a-z0-9][a-z0-9_./-]*\.js$")


def _read(relative: str) -> str:
    return _ROOT.joinpath(relative).read_text(encoding="utf-8")


def panel_html() -> str:
    template = _read("index.html")
    return (
        template.replace("{{MUSICFORGE_STYLES}}", _read("styles/studio.css"))
        .replace(
            "{{MUSICFORGE_SCRIPTS}}",
            '<script type="module" src="/assets/musicforge/app.js"></script>',
        )
    )


def script_modules() -> tuple[str, ...]:
    rows = json.loads(_read("scripts/module-manifest.json"))
    if not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
        raise ValueError("Invalid Studio script module manifest.")
    modules = tuple(rows)
    if len(modules) != len(set(modules)) or any(not _safe_script_path(row) for row in modules):
        raise ValueError("Unsafe Studio script module manifest.")
    return modules


def web_script(relative: str) -> str:
    raw = str(relative or "").strip()
    if "\\" in raw:
        raise FileNotFoundError("Studio script module not found.")
    normalized = raw
    if not _safe_script_path(normalized) or normalized not in script_modules():
        raise FileNotFoundError("Studio script module not found.")
    return _read(f"scripts/{normalized}")


def panel_source() -> str:
    return panel_html() + "\n" + "\n".join(web_script(module) for module in script_modules())


def _safe_script_path(path: str) -> bool:
    return bool(
        _SCRIPT_PATH.fullmatch(path)
        and not path.startswith("/")
        and ".." not in path.split("/")
        and ".musicforge" not in path.lower()
    )
