from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from song_agent.architecture_guardrails import build_architecture_snapshot


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def _migration_document() -> dict[str, object]:
    return json.loads(
        (ROOT / "architecture-v14-domain-migration.json").read_text(encoding="utf-8")
    )


def _migration_rows() -> list[dict[str, object]]:
    document = _migration_document()
    return [row for wave in document["waves"] for row in wave["modules"]]


def test_migrated_facades_preserve_export_identity() -> None:
    rows = _migration_rows()

    waves = {
        tuple(wave["contexts"]): int(wave["module_count"])
        for wave in _migration_document()["waves"]
    }
    assert waves[("creation", "studio")] == 59
    assert waves[("quality",)] == 61
    assert len(rows) == 120
    for row in rows:
        facade = importlib.import_module(str(row["source"]))
        owner = importlib.import_module(str(row["target"]))
        exports = tuple(getattr(facade, "__all__", ()))
        assert len(exports) == int(row["export_count"])
        for name in exports:
            assert getattr(facade, name) is getattr(owner, name), f"{row['source']}:{name}"


def test_domain_migration_has_no_dynamic_facade_or_active_debt() -> None:
    rows = _migration_rows()
    for row in rows:
        facade_path = ROOT.joinpath(*str(row["source"]).split(".")).with_suffix(".py")
        if not facade_path.is_file():
            facade_path = facade_path.with_suffix("") / "__init__.py"
        source = facade_path.read_text(encoding="utf-8")
        assert "globals().update" not in source
        assert "import_module(" not in source

    snapshot = build_architecture_snapshot(ROOT)
    ownership = {str(row["module"]): row for row in snapshot["modules"]}
    contexts = {
        str(ownership[str(row["imported"])].get("context"))
        for row in snapshot["active_to_compatibility_imports"]
    }
    assert "creation" not in contexts
    assert "studio" not in contexts
    assert "quality" not in contexts
    assert snapshot["cycles"] == []
    assert snapshot["boundary_violations"] == []
