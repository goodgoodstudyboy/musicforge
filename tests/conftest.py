from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.path)).name.lower()
        name = item.name.lower()
        markers: set[str] = set()
        if "architecture" in path or "contract" in path or "registry" in path or "matrix" in path:
            markers.add("contract")
        if "verifier" in path or "security" in path or "zip" in name or "tamper" in name or "forg" in name:
            markers.add("security")
        if path.startswith(("test_cli", "test_server", "test_webui")) or "integration" in name:
            markers.add("integration")
        if path == "test_release_check.py" and name.startswith("test_v"):
            markers.update({"legacy", "slow"})
        if "smoke" in name and path != "test_release_check_governance.py":
            markers.add("slow")
        if "windows" in name or "backslash" in name:
            markers.add("platform_windows")
        if not markers:
            markers.add("unit")
        for marker in sorted(markers):
            item.add_marker(getattr(pytest.mark, marker))
