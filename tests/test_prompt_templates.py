from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.prompt_templates import PromptTemplateStore, render_prompt_template


def test_prompt_templates_load_builtins_and_render_context(tmp_path: Path) -> None:
    store = PromptTemplateStore(tmp_path / ".musicforge" / "prompt-templates.json")

    data = store.to_response()
    template = store.get_template("provider-edit-intent")
    rendered = render_prompt_template(template, {"instruction": "lift chorus"})

    assert data["built_in_count"] >= 4
    assert template.task == "provider_edit_patch"
    assert "lift chorus" in rendered
    assert "{{context_json}}" not in rendered


def test_prompt_template_override_and_reset(tmp_path: Path) -> None:
    path = tmp_path / ".musicforge" / "prompt-templates.json"
    store = PromptTemplateStore(path)

    saved = store.save_template(
        "provider-edit-intent",
        {
            "system_prompt": "Return safe JSON only.",
            "user_prompt": "Context: {{context_json}}",
        },
    )
    assert saved.system_prompt == "Return safe JSON only."
    assert path.exists()
    assert store.to_response()["override_count"] == 1

    store.reset_template("provider-edit-intent")
    assert store.to_response()["override_count"] == 0

    store.save_template("provider-edit-intent", {"system_prompt": "Return JSON only.", "user_prompt": "{{context_json}}"})
    store.reset()
    assert not path.exists()


def test_prompt_template_validation_rejects_bad_id_long_prompt_and_local_path(tmp_path: Path) -> None:
    store = PromptTemplateStore(tmp_path / ".musicforge" / "prompt-templates.json")

    with pytest.raises(ValueError, match="template_id"):
        store.get_template("Bad ID")
    with pytest.raises(ValueError, match="20000"):
        store.save_template("provider-edit-intent", {"system_prompt": "x" * 20_001})
    with pytest.raises(ValueError, match="absolute paths"):
        store.save_template("provider-edit-intent", {"system_prompt": r"read C:\Users\someone\secret.txt"})
    with pytest.raises(FileNotFoundError):
        store.save_template("unknown-template", {"system_prompt": "x"})
