from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import now_iso, read_json, write_json


SCHEMA_VERSION = 1
PROMPT_TEMPLATE_PATH = Path(".musicforge") / "prompt-templates.json"
TEMPLATE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")
MAX_PROMPT_CHARS = 20_000
MAX_TEMPLATE_JSON_BYTES = 64_000
BLOCKED_PROMPT_PATTERNS = (
    re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
)


@dataclass(frozen=True)
class PromptTemplate:
    template_id: str
    name: str
    description: str
    task: str
    system_prompt: str
    user_prompt: str
    output_schema: dict[str, Any]
    built_in: bool = False
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, built_in: bool | None = None) -> "PromptTemplate":
        if not isinstance(data, dict):
            raise ValueError("prompt template must be an object.")
        template = cls(
            template_id=_clean_template_id(data.get("template_id")),
            name=_bounded_text(data.get("name"), "name", 100) or "Untitled Template",
            description=_bounded_text(data.get("description"), "description", 500),
            task=_bounded_text(data.get("task"), "task", 80),
            system_prompt=_prompt_text(data.get("system_prompt"), "system_prompt"),
            user_prompt=_prompt_text(data.get("user_prompt"), "user_prompt"),
            output_schema=_mapping(data.get("output_schema"), "output_schema"),
            built_in=bool(data.get("built_in", False) if built_in is None else built_in),
            enabled=bool(data.get("enabled", True)),
            created_at=_optional_str(data.get("created_at")),
            updated_at=_optional_str(data.get("updated_at")),
        )
        template.validate()
        return template

    def validate(self) -> None:
        _clean_template_id(self.template_id)
        if not self.task.strip():
            raise ValueError("task must not be empty.")
        if not self.system_prompt.strip():
            raise ValueError("system_prompt must not be empty.")
        if not self.user_prompt.strip():
            raise ValueError("user_prompt must not be empty.")
        if not isinstance(self.output_schema, dict) or not self.output_schema:
            raise ValueError("output_schema must be a non-empty object.")
        _validate_prompt_text(self.system_prompt, "system_prompt")
        _validate_prompt_text(self.user_prompt, "user_prompt")
        size = len(json.dumps(self.to_dict(), ensure_ascii=False).encode("utf-8"))
        if size > MAX_TEMPLATE_JSON_BYTES:
            raise ValueError(f"prompt template JSON must be {MAX_TEMPLATE_JSON_BYTES} bytes or fewer.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PromptTemplateStore:
    def __init__(self, path: Path | str = PROMPT_TEMPLATE_PATH) -> None:
        self.path = Path(path)
        self.lock = threading.RLock()

    def list_templates(self) -> list[PromptTemplate]:
        with self.lock:
            overrides = {template.template_id: template for template in self._read_user_templates()}
            result = []
            for built_in in BUILT_IN_TEMPLATES:
                result.append(overrides.get(built_in.template_id, built_in))
            return result

    def to_response(self) -> dict[str, Any]:
        templates = self.list_templates()
        override_ids = {template.template_id for template in self._read_user_templates()}
        return {
            "schema_version": SCHEMA_VERSION,
            "templates": [
                {**template.to_dict(), "overridden": template.template_id in override_ids}
                for template in templates
            ],
            "built_in_count": len(BUILT_IN_TEMPLATES),
            "override_count": len(override_ids),
        }

    def get_template(self, template_id: str) -> PromptTemplate:
        template_id = _clean_template_id(template_id)
        for template in self.list_templates():
            if template.template_id == template_id:
                return template
        raise FileNotFoundError(template_id)

    def save_template(self, template_id: str, data: dict[str, Any]) -> PromptTemplate:
        with self.lock:
            template_id = _clean_template_id(template_id)
            built_in = _built_in_template(template_id)
            if built_in is None:
                raise FileNotFoundError(template_id)
            now = now_iso()
            merged = built_in.to_dict()
            for key in ("name", "description", "system_prompt", "user_prompt", "enabled"):
                if key in data:
                    merged[key] = data[key]
            if "output_schema" in data:
                merged["output_schema"] = data["output_schema"]
            merged["template_id"] = template_id
            merged["task"] = built_in.task
            merged["built_in"] = True
            merged["created_at"] = built_in.created_at or now
            merged["updated_at"] = now
            template = PromptTemplate.from_dict(merged, built_in=True)
            overrides = {item.template_id: item for item in self._read_user_templates()}
            overrides[template.template_id] = template
            self._write_user_templates(list(overrides.values()))
            return template

    def reset_template(self, template_id: str) -> None:
        with self.lock:
            template_id = _clean_template_id(template_id)
            overrides = [template for template in self._read_user_templates() if template.template_id != template_id]
            self._write_user_templates(overrides)

    def reset(self) -> None:
        with self.lock:
            if self.path.exists():
                self.path.unlink()

    def _read_user_templates(self) -> list[PromptTemplate]:
        if not self.path.exists():
            return []
        try:
            data = read_json(self.path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return []
        raw_templates = data.get("templates", []) if isinstance(data, dict) else []
        templates = []
        for item in raw_templates:
            try:
                templates.append(PromptTemplate.from_dict(item, built_in=True))
            except ValueError:
                continue
        return templates

    def _write_user_templates(self, templates: list[PromptTemplate]) -> None:
        write_json(
            self.path,
            {
                "schema_version": SCHEMA_VERSION,
                "templates": [template.to_dict() for template in sorted(templates, key=lambda item: item.template_id)],
            },
        )


def render_prompt_template(template: PromptTemplate, context: dict[str, Any]) -> str:
    payload = json.dumps(context, ensure_ascii=False, indent=2)
    rendered = template.user_prompt.replace("{{context_json}}", payload)
    return f"{template.system_prompt.strip()}\n\n{rendered.strip()}"


def _built_in_template(template_id: str) -> PromptTemplate | None:
    for template in BUILT_IN_TEMPLATES:
        if template.template_id == template_id:
            return template
    return None


def _clean_template_id(value: Any) -> str:
    template_id = str(value or "").strip()
    if not TEMPLATE_ID_PATTERN.match(template_id):
        raise ValueError("template_id must use lowercase letters, numbers, hyphen, or underscore.")
    return template_id


def _bounded_text(value: Any, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return text


def _prompt_text(value: Any, field_name: str) -> str:
    text = str(value or "")
    if len(text) > MAX_PROMPT_CHARS:
        raise ValueError(f"{field_name} must be {MAX_PROMPT_CHARS} characters or fewer.")
    return text


def _validate_prompt_text(value: str, field_name: str) -> None:
    for pattern in BLOCKED_PROMPT_PATTERNS:
        if pattern.search(value):
            raise ValueError(f"{field_name} must not contain local absolute paths.")


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object.")
    return dict(value)


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


PROVIDER_EDIT_PATCH_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "summary", "operations"],
    "properties": {
        "schema_version": {"const": 1},
        "summary": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["op"],
                "properties": {
                    "op": {
                        "enum": [
                            "set_section_energy",
                            "set_section_chords",
                            "set_track_density",
                            "rewrite_section_lyrics",
                            "melody_variation",
                            "arrangement_variation",
                        ]
                    }
                },
            },
        },
    },
}


PROVIDER_EDIT_CANDIDATES_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "candidates"],
    "properties": {
        "schema_version": {"const": 1},
        "candidates": {
            "type": "array",
            "minItems": 2,
            "maxItems": 5,
            "items": PROVIDER_EDIT_PATCH_SCHEMA,
        },
    },
}


PROVIDER_REVIEW_JUDGE_SCHEMA = {
    "type": "object",
    "required": ["recommended_candidate_id", "candidate_scores", "comparison_summary", "manual_review_required"],
    "properties": {
        "recommended_candidate_id": {"type": "string"},
        "candidate_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["candidate_id", "overall", "review_fit", "target_precision", "musicality", "novelty", "risk", "confidence", "reason"],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "overall": {"type": "integer", "minimum": 0, "maximum": 100},
                    "review_fit": {"type": "integer", "minimum": 0, "maximum": 100},
                    "target_precision": {"type": "integer", "minimum": 0, "maximum": 100},
                    "musicality": {"type": "integer", "minimum": 0, "maximum": 100},
                    "novelty": {"type": "integer", "minimum": 0, "maximum": 100},
                    "risk": {"type": "integer", "minimum": 0, "maximum": 100},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string"},
                    "risks": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "comparison_summary": {
            "type": "object",
            "properties": {
                "best_candidate_id": {"type": "string"},
                "reason": {"type": "string"},
                "tradeoffs": {"type": "array", "items": {"type": "string"}},
            },
        },
        "manual_review_required": {"type": "boolean"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}


BUILT_IN_TEMPLATES = [
    PromptTemplate.from_dict(
        {
            "template_id": "provider-edit-intent",
            "name": "Provider edit patch",
            "description": "Convert natural-language edit instructions into a constrained MusicForge edit patch.",
            "task": "provider_edit_patch",
            "system_prompt": (
                "You are a MusicForge edit planner. Return one JSON object only. "
                "Do not include file paths, URLs, secrets, or free-form code. "
                "Use only the supported operations and supported chord names from the context."
            ),
            "user_prompt": (
                "Create a concise edit patch for this context. Preserve anything the instruction says to preserve.\n"
                "{{context_json}}"
            ),
            "output_schema": PROVIDER_EDIT_PATCH_SCHEMA,
        },
        built_in=True,
    ),
    PromptTemplate.from_dict(
        {
            "template_id": "provider-edit-song-plan",
            "name": "Provider edit SongPlan candidate",
            "description": "Reserved template for whole SongPlan candidates. Disabled by default.",
            "task": "provider_edit_song_plan",
            "system_prompt": "Return a complete MusicForge SongPlan JSON object only.",
            "user_prompt": "{{context_json}}",
            "output_schema": {"type": "object", "required": ["title", "sections", "tracks"]},
            "enabled": False,
        },
        built_in=True,
    ),
    PromptTemplate.from_dict(
        {
            "template_id": "provider-edit-candidates",
            "name": "Provider edit candidates",
            "description": "Generate multiple constrained MusicForge edit patch candidates for one instruction.",
            "task": "provider_edit_candidates",
            "system_prompt": (
                "You are a MusicForge edit planner. Return one JSON object only with a candidates array. "
                "Each candidate must be distinct, concise, and use only supported operations and chord names. "
                "Do not include file paths, URLs, secrets, or free-form code."
            ),
            "user_prompt": (
                "Create the requested number of candidate edit patches for this context. "
                "Each candidate summary must explain how it differs from the others.\n"
                "{{context_json}}"
            ),
            "output_schema": PROVIDER_EDIT_CANDIDATES_SCHEMA,
        },
        built_in=True,
    ),
    PromptTemplate.from_dict(
        {
            "template_id": "provider-review-edit-intent",
            "name": "Provider review edit patch",
            "description": "Convert sanitized audition review feedback into a constrained MusicForge edit patch.",
            "task": "provider_review_edit_patch",
            "system_prompt": (
                "You are a MusicForge review-feedback edit planner. Return one JSON object only. "
                "Use only supported operations and chord names from the context. "
                "Do not include file paths, URLs, secrets, credentials, or free-form code."
            ),
            "user_prompt": (
                "Create a concise edit patch from this audition review context. "
                "Treat hook/keep markers as preserve signals unless the instruction explicitly asks to alter them.\n"
                "{{context_json}}"
            ),
            "output_schema": PROVIDER_EDIT_PATCH_SCHEMA,
        },
        built_in=True,
    ),
    PromptTemplate.from_dict(
        {
            "template_id": "provider-review-candidates",
            "name": "Provider review candidates",
            "description": "Generate constrained provider patch candidates for a persistent Review Task.",
            "task": "provider_review_candidates",
            "system_prompt": (
                "You are a MusicForge review workbench candidate planner. Return one JSON object only with a candidates array. "
                "Each candidate must be a constrained ProviderEditPatch that can be locally validated and scored. "
                "Do not apply changes automatically. Do not include file paths, URLs, secrets, credentials, raw prompts, or free-form code."
            ),
            "user_prompt": (
                "Create the requested number of review candidate edit patches for this sanitized Review Task context. "
                "Use local candidate context only to understand tradeoffs, not to copy invalid operations. "
                "Treat keep/hook markers as preserve signals and keep edits targeted to the review task target.\n"
                "{{context_json}}"
            ),
            "output_schema": PROVIDER_EDIT_CANDIDATES_SCHEMA,
        },
        built_in=True,
    ),
    PromptTemplate.from_dict(
        {
            "template_id": "provider-review-judge",
            "name": "Provider review judge",
            "description": "Score ready ReviewTask candidates across fit, precision, musicality, novelty, risk, and confidence.",
            "task": "provider_review_judge",
            "system_prompt": (
                "You are a MusicForge candidate judge. Return one JSON object only. "
                "Judge the provided ready candidates without creating edits, applying candidates, resolving tasks, or changing project state. "
                "Do not include file paths, URLs, secrets, credentials, raw prompts, or free-form code."
            ),
            "user_prompt": (
                "Score each ready candidate for this sanitized ReviewTask context. "
                "Risk is danger, so higher risk means more manual caution. "
                "Return JSON that follows the schema exactly and keep explanations concise.\n"
                "{{context_json}}"
            ),
            "output_schema": PROVIDER_REVIEW_JUDGE_SCHEMA,
        },
        built_in=True,
    ),
    PromptTemplate.from_dict(
        {
            "template_id": "provider-edit-critic",
            "name": "Provider edit critic",
            "description": "Review a provider edit patch for obvious musical and schema risks.",
            "task": "provider_edit_critic",
            "system_prompt": "Return JSON with warnings for a MusicForge edit patch.",
            "user_prompt": "{{context_json}}",
            "output_schema": {"type": "object", "properties": {"warnings": {"type": "array"}}},
            "enabled": False,
        },
        built_in=True,
    ),
    PromptTemplate.from_dict(
        {
            "template_id": "provider-edit-repair",
            "name": "Provider edit repair",
            "description": "Reserved template for low-risk provider patch repair.",
            "task": "provider_edit_repair",
            "system_prompt": "Return a corrected MusicForge edit patch JSON object only.",
            "user_prompt": "{{context_json}}",
            "output_schema": PROVIDER_EDIT_PATCH_SCHEMA,
            "enabled": False,
        },
        built_in=True,
    ),
]
