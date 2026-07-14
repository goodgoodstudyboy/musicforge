from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile

import pytest


_MANAGED_BASETEMP_ATTRIBUTE = "_musicforge_managed_basetemp"
_SLOW_ACTIVE_TEST_PREFIXES = (
    "test_public_trust_center",
    "test_release_portfolio_",
    "test_trust_operations_",
    "test_unified_",
)


def pytest_configure(config: pytest.Config) -> None:
    """Keep xdist paths bounded and make generated test trees reclaimable."""
    if config.option.basetemp:
        return
    basetemp = Path(tempfile.gettempdir()) / f"mf-{os.getpid()}"
    config.option.basetemp = str(basetemp)
    setattr(config, _MANAGED_BASETEMP_ATTRIBUTE, basetemp)


def pytest_unconfigure(config: pytest.Config) -> None:
    basetemp = getattr(config, _MANAGED_BASETEMP_ATTRIBUTE, None)
    if basetemp is not None and _is_managed_basetemp(basetemp):
        shutil.rmtree(basetemp, ignore_errors=True)


def _is_managed_basetemp(path: Path) -> bool:
    resolved = path.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    return resolved.parent == temp_root and re.fullmatch(r"mf-\d+", resolved.name) is not None


def _is_managed_test_path(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError:
        return False
    return len(relative.parts) >= 2 and re.fullmatch(r"mf-\d+", relative.parts[0]) is not None


@pytest.fixture(autouse=True)
def _cleanup_managed_tmp_path(request: pytest.FixtureRequest):
    yield
    tmp_path = request.node.funcargs.get("tmp_path")
    if isinstance(tmp_path, Path) and _is_managed_test_path(tmp_path):
        shutil.rmtree(tmp_path, ignore_errors=True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.path)).name.lower()
        name = item.name.lower()
        markers: set[str] = set()
        if path == "test_release_check.py" and name.startswith("test_v"):
            markers.update({"legacy", "slow"})
            markers.add(_legacy_release_check_shard(name))
        else:
            primary_marker = _primary_marker(path, name, item=item)
            markers.add(primary_marker)
            if primary_marker == "integration":
                markers.add(f"integration_partition_{_integration_partition(item.nodeid)}")
            if "verifier" in path or "security" in path or "zip" in name or "tamper" in name or "forg" in name:
                markers.add("security")
            if _is_slow_test(path, name):
                markers.add("slow")
        if "windows" in name or "backslash" in name:
            markers.add("platform_windows")
        if "slow" in markers and "legacy" not in markers:
            markers.add(f"slow_partition_{_slow_partition(item.nodeid)}")
        for marker in sorted(markers):
            item.add_marker(getattr(pytest.mark, marker))


def _primary_marker(path: str, name: str, *, item: pytest.Item | None = None) -> str:
    code = getattr(getattr(item, "obj", None), "__code__", None)
    starts_http_server = code is not None and "start_test_server" in {*code.co_names, *code.co_freevars}
    if path.startswith(("test_cli", "test_server", "test_webui")) or "integration" in name or starts_http_server:
        return "integration"
    if any(token in path for token in ("architecture", "contract", "registry", "matrix")):
        return "contract"
    return "unit"


def _is_slow_test(path: str, name: str) -> bool:
    return (
        ("smoke" in name and path != "test_release_check_governance.py")
        or path.startswith(_SLOW_ACTIVE_TEST_PREFIXES)
    )


def _slow_partition(nodeid: str, *, count: int = 2) -> int:
    digest = hashlib.sha256(nodeid.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % count


def _integration_partition(nodeid: str, *, count: int = 2) -> int:
    return _slow_partition(nodeid, count=count)


def _legacy_release_check_shard(name: str) -> str:
    match = re.match(r"test_v(\d+)", name)
    digits = match.group(1) if match else ""
    if digits.startswith(("11", "12")):
        return "legacy_program"
    if digits.startswith("10"):
        return "legacy_audio"
    if digits.startswith(("8", "9")):
        return "legacy_trust"
    return "legacy_early"
