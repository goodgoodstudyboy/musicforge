from __future__ import annotations

import json
import re

from song_agent.platform.resource_access import PackagedResource, read_packaged_text, read_web_script_text


_SCRIPT_PATH = re.compile(r"^[a-z0-9][a-z0-9_./-]*\.js$")


def _read(relative: str) -> str:
    fixed = {
        "index.html": PackagedResource.WEB_INDEX,
        "scripts/module-manifest.json": PackagedResource.WEB_MODULE_MANIFEST,
        "styles/studio.css": PackagedResource.WEB_STYLES,
    }
    resource = fixed.get(relative)
    if resource is not None:
        return read_packaged_text(resource)
    if relative.startswith("scripts/"):
        return read_web_script_text(relative.removeprefix("scripts/"))
    raise FileNotFoundError("Studio resource not found.")


def panel_html() -> str:
    template = _read("index.html")
    return template.replace("{{MUSICFORGE_STYLES}}", _read("styles/studio.css")).replace(
        "{{MUSICFORGE_SCRIPTS}}",
        '<script type="module" src="/assets/musicforge/app.js"></script>',
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
    if not _safe_script_path(raw) or raw not in script_modules():
        raise FileNotFoundError("Studio script module not found.")
    return _read(f"scripts/{raw}")


def panel_source() -> str:
    return panel_html() + "\n" + "\n".join(web_script(module) for module in script_modules())


def _safe_script_path(path: str) -> bool:
    return bool(
        _SCRIPT_PATH.fullmatch(path)
        and not path.startswith("/")
        and ".." not in path.split("/")
        and ".musicforge" not in path.lower()
    )


__all__ = ["panel_html", "panel_source", "script_modules", "web_script"]
