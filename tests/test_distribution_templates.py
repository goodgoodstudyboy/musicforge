from __future__ import annotations

import pytest

from song_agent.distribution_templates import (
    DistributionTemplateError,
    TemplatePackStore,
    resolve_mapping_source,
    template_content_hash,
    validate_template_pack,
)


def test_builtin_templates_validate_and_hash_is_stable(tmp_path):
    store = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates")

    templates = store.list_templates()
    generic = store.get_template("tpl-generic-dsp-basic")

    assert any(item["slug"] == "generic-dsp-basic" for item in templates)
    assert generic["source"] == "builtin"
    assert validate_template_pack(generic)["status"] == "passed"
    assert generic["template_hash"] == template_content_hash(generic)


def test_user_template_create_clone_import_roundtrip_and_source_path_block(tmp_path):
    store = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates")
    created = store.create_template(
        {
            "slug": "custom-pitch-basic",
            "name": "Custom Pitch Basic",
            "rules": {"require_artwork": True, "require_upc": True, "require_isrc": False, "csv_formula_escape": True},
            "metadata_mapping": {"platform_csv": [{"column": "Title", "source": "track.title", "required": True}]},
            "file_naming": {"audio": "{track_number:02d}-{slug_title}.wav"},
            "checklist": [{"item_id": "explicit-confirmed", "label": "Explicit checked", "required": True}],
        }
    )
    cloned = store.clone_template("tpl-generic-dsp-basic", {"slug": "generic-copy"})
    exported = store.get_template(created["template_pack_id"])
    imported = store.import_template({"template": exported}, rename=True)

    assert created["source"] == "user"
    assert cloned["source"] == "user"
    assert imported["source"] == "imported"
    assert imported["content_hash"] == created["content_hash"]
    with pytest.raises(DistributionTemplateError):
        store.import_template({"source_path": str(tmp_path / "template.json"), "template": exported})


def test_template_rejects_mapping_code_paths_and_sensitive_values(tmp_path):
    store = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates")

    with pytest.raises(DistributionTemplateError):
        store.create_template({"slug": "bad-eval", "name": "Bad Eval", "metadata_mapping": {"platform_csv": [{"column": "X", "source": "__import__('os').system('dir')", "required": True}]}})
    with pytest.raises(DistributionTemplateError):
        store.create_template({"slug": "bad-path", "name": "Bad Path", "description": r"C:\Users\demo\secret.json"})
    with pytest.raises(DistributionTemplateError):
        store.create_template({"slug": "bad-token", "name": "Bad Token", "description": "api_key=sk-secret-value"})


def test_mapping_resolves_allowlisted_fields_only():
    value = resolve_mapping_source(
        "track.title",
        release_metadata={"release": {"upc": "123"}},
        track_metadata={"title": "Song", "track_number": 1},
    )

    assert value == "Song"
    with pytest.raises(DistributionTemplateError):
        resolve_mapping_source("track.title.upper()", release_metadata={}, track_metadata={})
