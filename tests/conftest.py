from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import uuid

import pytest


_MANAGED_BASETEMP_ATTRIBUTE = "_musicforge_managed_basetemp"
_SLOW_ACTIVE_TEST_PREFIXES = (
    "test_public_trust_center",
    "test_release_portfolio_",
    "test_trust_operations_",
    "test_unified_",
)
_PRIMARY_MARKERS = frozenset({"unit", "contract", "integration", "legacy"})
_MARKER_MANIFEST = Path(__file__).with_name("marker-manifest.json")


def pytest_configure(config: pytest.Config) -> None:
    """Keep xdist paths bounded and make generated test trees reclaimable."""
    if config.option.basetemp:
        return
    basetemp = Path(tempfile.gettempdir()) / f"mf-{uuid.uuid4().hex[:10]}"
    config.option.basetemp = str(basetemp)
    setattr(config, _MANAGED_BASETEMP_ATTRIBUTE, basetemp)


def pytest_unconfigure(config: pytest.Config) -> None:
    basetemp = getattr(config, _MANAGED_BASETEMP_ATTRIBUTE, None)
    if basetemp is not None and _is_managed_basetemp(basetemp):
        shutil.rmtree(basetemp, ignore_errors=True)


def _is_managed_basetemp(path: Path) -> bool:
    resolved = path.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    return resolved.parent == temp_root and re.fullmatch(r"mf-[0-9a-f]{10}", resolved.name) is not None


def _is_managed_test_path(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError:
        return False
    return len(relative.parts) >= 2 and re.fullmatch(r"mf-[0-9a-f]{10}", relative.parts[0]) is not None


@pytest.fixture(autouse=True)
def _cleanup_managed_tmp_path(request: pytest.FixtureRequest):
    yield
    tmp_path = request.node.funcargs.get("tmp_path")
    if isinstance(tmp_path, Path) and _is_managed_test_path(tmp_path):
        shutil.rmtree(tmp_path, ignore_errors=True)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    manifest = _load_marker_manifest()
    for item in items:
        path = Path(str(item.path)).name.lower()
        name = item.name.lower()
        primary_marker = _declared_primary_marker(path, manifest)
        markers: set[str] = {primary_marker}
        if primary_marker == "legacy":
            markers.add("slow")
            markers.add(_legacy_release_check_shard(name))
        else:
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


def _load_marker_manifest(path: Path = _MARKER_MANIFEST) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise pytest.UsageError(f"Cannot read explicit pytest marker manifest: {exc}") from exc
    files = payload.get("files") if isinstance(payload, dict) else None
    if payload.get("schema_version") != 1 or not isinstance(files, dict):
        raise pytest.UsageError("Invalid tests/marker-manifest.json schema.")
    return {Path(str(key)).name.lower(): str(value) for key, value in files.items()}


def _declared_primary_marker(path: str, manifest: dict[str, str]) -> str:
    marker = manifest.get(Path(path).name.lower(), "")
    if marker not in _PRIMARY_MARKERS:
        raise pytest.UsageError(f"Test module {path} has no explicit primary marker in tests/marker-manifest.json.")
    return marker


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
