from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tests import conftest
from tests.conftest import (
    _declared_primary_marker,
    _is_managed_basetemp,
    _is_managed_test_path,
    _is_slow_test,
    _integration_partition,
    _load_marker_manifest,
    _slow_partition,
    pytest_configure,
    pytest_unconfigure,
)


def test_active_test_taxonomy_has_one_deterministic_primary_shard() -> None:
    manifest = _load_marker_manifest()
    assert _declared_primary_marker("test_agent_nodes.py", manifest) == "unit"
    assert _declared_primary_marker("test_release_check_matrix.py", manifest) == "contract"
    assert _declared_primary_marker("test_cli_release_check_matrix.py", manifest) == "integration"
    assert _is_slow_test("test_unified_release_program.py", "test_happy_path") is True
    assert _is_slow_test("test_song.py", "test_happy_path") is False
    assert _slow_partition("tests/test_example.py::test_case") in {0, 1}
    assert _slow_partition("tests/test_example.py::test_case") == _slow_partition("tests/test_example.py::test_case")
    assert _integration_partition("tests/test_example.py::test_case") in {0, 1}
    assert _integration_partition("tests/test_example.py::test_case") == _integration_partition(
        "tests/test_example.py::test_case"
    )


def test_managed_basetemp_guard_only_accepts_direct_unique_directories(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(conftest.tempfile, "gettempdir", lambda: str(tmp_path))

    assert _is_managed_basetemp(tmp_path / "mf-deadbeef12") is True
    assert _is_managed_basetemp(tmp_path / "mf-123") is False
    assert _is_managed_basetemp(tmp_path / "mf-current") is False
    assert _is_managed_basetemp(tmp_path / "nested" / "mf-deadbeef12") is False

    assert _is_managed_test_path(tmp_path / "mf-deadbeef12" / "test-case") is True
    assert _is_managed_test_path(tmp_path / "mf-123" / "test-case") is False
    assert _is_managed_test_path(tmp_path / "mf-current" / "test-case") is False
    assert _is_managed_test_path(tmp_path.parent / "mf-deadbeef12" / "test-case") is False


def test_managed_basetemp_lifecycle_does_not_touch_explicit_configuration(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(conftest.tempfile, "gettempdir", lambda: str(tmp_path))
    config = SimpleNamespace(option=SimpleNamespace(basetemp=None))

    pytest_configure(config)
    managed = Path(config.option.basetemp)
    managed.mkdir()
    pytest_unconfigure(config)

    assert managed.name.startswith("mf-")
    assert not managed.exists()

    explicit = SimpleNamespace(option=SimpleNamespace(basetemp=str(tmp_path / "explicit")))
    pytest_configure(explicit)
    assert explicit.option.basetemp == str(tmp_path / "explicit")
