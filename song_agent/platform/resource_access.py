from __future__ import annotations

from enum import StrEnum
from importlib import resources as _resources
from pathlib import PurePosixPath


class PackagedResource(StrEnum):
    PACKAGE_REGISTRY = "package-registry"
    PACKAGE_WRITER_POLICY = "package-writer-policy"
    STATE_AUTHORITY_POLICY = "state-authority-policy"
    WEB_INDEX = "web-index"
    WEB_MODULE_MANIFEST = "web-module-manifest"
    WEB_STYLES = "web-styles"


_RESOURCE_PATHS = {
    PackagedResource.PACKAGE_REGISTRY: "platform/contracts/runtime-package-registry.json",
    PackagedResource.PACKAGE_WRITER_POLICY: "platform/contracts/runtime-package-writer-policy.json",
    PackagedResource.STATE_AUTHORITY_POLICY: "platform/persistence/runtime-state-authority-policy.json",
    PackagedResource.WEB_INDEX: "interfaces/web/index.html",
    PackagedResource.WEB_MODULE_MANIFEST: "interfaces/web/scripts/module-manifest.json",
    PackagedResource.WEB_STYLES: "interfaces/web/styles/studio.css",
}
_PACKAGE_ANCHOR = "song_agent"
_WEB_SCRIPT_ROOT = PurePosixPath("interfaces/web/scripts")


def read_packaged_text(resource: PackagedResource) -> str:
    """Read one reviewed package resource from the fixed application anchor."""

    relative = PurePosixPath(_RESOURCE_PATHS[resource])
    return _resources.files(_PACKAGE_ANCHOR).joinpath(*relative.parts).read_text(encoding="utf-8")


def read_web_script_text(relative: str) -> str:
    """Read a validated Studio script path without exposing a package loader."""

    raw = str(relative or "").strip()
    path = PurePosixPath(raw)
    if (
        not raw
        or "\\" in raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or ".musicforge" in raw.lower()
        or path.suffix != ".js"
    ):
        raise FileNotFoundError("Studio script module not found.")
    resource_path = _WEB_SCRIPT_ROOT.joinpath(path)
    return _resources.files(_PACKAGE_ANCHOR).joinpath(*resource_path.parts).read_text(encoding="utf-8")


__all__ = ["PackagedResource", "read_packaged_text", "read_web_script_text"]
