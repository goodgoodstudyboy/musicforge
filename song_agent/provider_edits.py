from __future__ import annotations

import json
import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.edits import (
    EditIntent,
    EditedSongPlanResult,
    SUPPORTED_HARMONY_CHORDS,
    apply_edit_intent,
    validate_edit_intent,
)
from song_agent.music_quality import attach_quality
from song_agent.prompt_templates import PromptTemplate, render_prompt_template
from song_agent.provider import ProviderConfig, ProviderConfigError, ProviderEditResponse, ProviderOutputError
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.quality import validate_song_plan
from song_agent.schemas.song import SongPlan


SCHEMA_VERSION = 1
MAX_PATCH_JSON_BYTES = 32_768
MAX_CANDIDATE_SET_JSON_BYTES = 128_000
MAX_OPERATION_COUNT = 8
MIN_CANDIDATE_COUNT = 2
MAX_CANDIDATE_COUNT = 5
MAX_PATCH_TEXT = 800
MAX_LYRIC_TEXT = 2_000
ALLOWED_OPS = {
    "set_section_energy",
    "set_section_chords",
    "set_track_density",
    "rewrite_section_lyrics",
    "melody_variation",
    "arrangement_variation",
}
BLOCKED_KEYS = {"path", "file", "absolute_path", "local_path", "token", "api_key", "secret", "password", "credential"}


class ProviderEditError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderEditOperation:
    op: str
    section_name: str | None = None
    track_name: str | None = None
    energy: float | None = None
    strength: int | None = None
    chords: list[str] = field(default_factory=list)
    lyrics: str | None = None
    instrument: str | None = None
    preserve: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderEditOperation":
        if not isinstance(data, dict):
            raise ProviderEditError("provider edit operation must be an object.")
        _scan_blocked_fields(data)
        op = str(data.get("op") or "").strip()
        if op not in ALLOWED_OPS:
            raise ProviderEditError(f"Unsupported provider edit operation: {op}.")
        operation = cls(
            op=op,
            section_name=_optional_text(data.get("section_name"), "section_name", 80),
            track_name=_optional_text(data.get("track_name"), "track_name", 80),
            energy=_optional_float(data.get("energy")),
            strength=_optional_strength(data.get("strength")),
            chords=_chord_list(data.get("chords")),
            lyrics=_optional_text(data.get("lyrics"), "lyrics", MAX_LYRIC_TEXT),
            instrument=_optional_text(data.get("instrument"), "instrument", 120),
            preserve=_string_list(data.get("preserve"), "preserve", max_items=8),
        )
        operation.validate_shape()
        return operation

    def validate_shape(self) -> None:
        if self.op in {"set_section_energy", "set_section_chords", "rewrite_section_lyrics", "melody_variation"} and not self.section_name:
            raise ProviderEditError(f"{self.op} requires section_name.")
        if self.op == "set_track_density" and not self.track_name:
            raise ProviderEditError("set_track_density requires track_name.")
        if self.op == "set_section_chords" and not self.chords:
            raise ProviderEditError("set_section_chords requires chords.")
        if self.op == "rewrite_section_lyrics" and not self.lyrics:
            raise ProviderEditError("rewrite_section_lyrics requires lyrics.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderEditPatch:
    schema_version: int
    summary: str
    operations: list[ProviderEditOperation]
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderEditPatch":
        if not isinstance(data, dict):
            raise ProviderEditError("provider edit patch must be an object.")
        _scan_blocked_fields(data)
        size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        if size > MAX_PATCH_JSON_BYTES:
            raise ProviderEditError(f"provider edit patch must be {MAX_PATCH_JSON_BYTES} bytes or fewer.")
        schema_version = int(data.get("schema_version", SCHEMA_VERSION) or SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            raise ProviderEditError(f"provider edit patch schema_version must be {SCHEMA_VERSION}.")
        raw_operations = data.get("operations")
        if not isinstance(raw_operations, list) or not raw_operations:
            raise ProviderEditError("provider edit patch operations must be a non-empty list.")
        if len(raw_operations) > MAX_OPERATION_COUNT:
            raise ProviderEditError(f"provider edit patch supports at most {MAX_OPERATION_COUNT} operations.")
        patch = cls(
            schema_version=schema_version,
            summary=_bounded_text(data.get("summary"), "summary", MAX_PATCH_TEXT) or "Provider edit",
            operations=[ProviderEditOperation.from_dict(item) for item in raw_operations],
            warnings=_string_list(data.get("warnings"), "warnings", max_items=12),
            confidence=_confidence(data.get("confidence")),
        )
        return patch

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "summary": self.summary,
            "operations": [operation.to_dict() for operation in self.operations],
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ProviderEditCandidateSet:
    schema_version: int
    candidates: list[ProviderEditPatch]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderEditCandidateSet":
        if not isinstance(data, dict):
            raise ProviderEditError("provider edit candidate set must be an object.")
        _scan_blocked_fields(data)
        size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        if size > MAX_CANDIDATE_SET_JSON_BYTES:
            raise ProviderEditError(f"provider edit candidate set must be {MAX_CANDIDATE_SET_JSON_BYTES} bytes or fewer.")
        schema_version = int(data.get("schema_version", SCHEMA_VERSION) or SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            raise ProviderEditError(f"provider edit candidate set schema_version must be {SCHEMA_VERSION}.")
        raw_candidates = data.get("candidates")
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ProviderEditError("provider edit candidate set candidates must be a non-empty list.")
        candidates = [ProviderEditPatch.from_dict(item) for item in raw_candidates if isinstance(item, dict)]
        if not candidates:
            raise ProviderEditError("provider edit candidate set has no valid candidates.")
        if len(candidates) > MAX_CANDIDATE_COUNT:
            candidates = candidates[:MAX_CANDIDATE_COUNT]
        return cls(schema_version=schema_version, candidates=candidates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class ProviderEditPreview:
    preview_id: str
    project_id: str
    parent_version_id: str
    parent_job_id: str
    instruction: str
    template_id: str
    status: str
    created_at: str
    patch: dict[str, Any]
    summary: dict[str, Any]
    source: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] | None = None
    validator: dict[str, Any] = field(default_factory=dict)
    provider_usage: dict[str, Any] = field(default_factory=dict)
    provider_request_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def provider_patch_to_intents(patch: ProviderEditPatch, parent_plan: SongPlan) -> list[EditIntent]:
    intents = [_operation_to_intent(operation) for operation in patch.operations]
    for intent in intents:
        validate_edit_intent(parent_plan, intent)
    return intents


def apply_provider_edit_patch(parent_plan: SongPlan, patch: ProviderEditPatch) -> EditedSongPlanResult:
    current = parent_plan
    summaries: list[dict[str, Any]] = []
    warnings = list(patch.warnings)
    for intent in provider_patch_to_intents(patch, current):
        result = apply_edit_intent(current, intent)
        current = result.plan
        summaries.append(result.summary)
        warnings.extend(result.warnings)
    final_plan = attach_quality(current)
    validate_song_plan(final_plan)
    return EditedSongPlanResult(
        plan=final_plan,
        summary={
            "provider_patch_summary": patch.summary,
            "operation_count": len(patch.operations),
            "operations": summaries,
            "confidence": patch.confidence,
        },
        warnings=warnings,
    )


def generate_provider_edit_patch(
    *,
    parent_plan: SongPlan,
    instruction: str,
    template: PromptTemplate,
    config: ProviderConfig,
    client: Any | None = None,
) -> tuple[ProviderEditPatch, dict[str, Any]]:
    config.validate_ready_for_provider()
    prompt = render_prompt_template(
        template,
        {
            "instruction": instruction,
            "song_plan": parent_plan.to_dict(),
            "supported_chords": list(SUPPORTED_HARMONY_CHORDS),
            "supported_operations": sorted(ALLOWED_OPS),
        },
    )
    client = client or _client_for_config(config)
    try:
        if config.wire_api == "mock":
            response = client.generate_edit_patch_json(parent_plan, instruction, config, prompt=prompt)
        else:
            response = client.generate_edit_patch_json(parent_plan, instruction, config, prompt=prompt)
        data, usage, request_id = _provider_edit_response_parts(response)
        patch = ProviderEditPatch.from_dict(data)
        provider_patch_to_intents(patch, parent_plan)
    except ProviderEditError as exc:
        raise ProviderOutputError(str(exc)) from exc
    except ValueError as exc:
        raise ProviderOutputError(f"Provider edit patch is invalid: {exc}") from exc
    snapshot = {
        "mode": "provider",
        "operation": "provider_edit",
        "wire_api": config.wire_api,
        "model": config.model,
        "template_id": template.template_id,
        "api_key_set": bool(config.api_key),
        "usage": usage,
        "request_id": request_id,
    }
    return patch, snapshot


def generate_provider_edit_candidates(
    *,
    parent_plan: SongPlan,
    instruction: str,
    template: PromptTemplate,
    config: ProviderConfig,
    candidate_count: int,
    client: Any | None = None,
) -> tuple[list[ProviderEditPatch], dict[str, Any]]:
    count = _candidate_count(candidate_count)
    config.validate_ready_for_provider()
    prompt = render_prompt_template(
        template,
        {
            "instruction": instruction,
            "candidate_count": count,
            "song_plan": parent_plan.to_dict(),
            "supported_chords": list(SUPPORTED_HARMONY_CHORDS),
            "supported_operations": sorted(ALLOWED_OPS),
        },
    )
    client = client or _client_for_config(config)
    try:
        if hasattr(client, "generate_edit_candidates_json"):
            response = client.generate_edit_candidates_json(parent_plan, instruction, config, candidate_count=count, prompt=prompt)
            data, usage, request_id = _provider_edit_response_parts(response)
            candidate_set = ProviderEditCandidateSet.from_dict(data)
            patches = candidate_set.candidates[:count]
        else:
            patches = []
            usage = {}
            request_id = None
            for _index in range(count):
                response = client.generate_edit_patch_json(parent_plan, instruction, config, prompt=prompt)
                data, call_usage, call_request_id = _provider_edit_response_parts(response)
                patches.append(ProviderEditPatch.from_dict(data))
                usage = _merge_usage(usage, call_usage)
                request_id = request_id or call_request_id
        if len(patches) < MIN_CANDIDATE_COUNT:
            raise ProviderEditError(f"provider returned fewer than {MIN_CANDIDATE_COUNT} candidates.")
        for patch in patches:
            provider_patch_to_intents(patch, parent_plan)
    except ProviderEditError as exc:
        raise ProviderOutputError(str(exc)) from exc
    except ValueError as exc:
        raise ProviderOutputError(f"Provider edit candidates are invalid: {exc}") from exc
    snapshot = {
        "mode": "provider",
        "operation": "provider_edit_candidates",
        "wire_api": config.wire_api,
        "model": config.model,
        "template_id": template.template_id,
        "api_key_set": bool(config.api_key),
        "usage": usage,
        "request_id": request_id,
        "candidate_count": len(patches),
    }
    return patches, snapshot


def create_provider_edit_preview(
    *,
    project_dir: Path,
    project_id: str,
    parent_version_id: str,
    parent_job_id: str,
    parent_plan: SongPlan,
    instruction: str,
    template: PromptTemplate,
    patch: ProviderEditPatch,
    now: str | None = None,
    provider_usage: dict[str, Any] | None = None,
    provider_request_id: str | None = None,
) -> ProviderEditPreview:
    now = now or now_iso()
    preview_root = project_dir / "edit-previews"
    preview_root.mkdir(parents=True, exist_ok=True)
    preview_id = _next_preview_id(preview_root)
    preview_dir = preview_root / preview_id
    preview_dir.mkdir(parents=True, exist_ok=False)
    result = apply_provider_edit_patch(parent_plan, patch)
    candidate_path = preview_dir / "candidate-song-plan.json"
    patch_path = preview_dir / "patch.json"
    quality_path = preview_dir / "quality.json"
    validator_path = preview_dir / "validator-report.json"
    write_json(candidate_path, result.plan.to_dict())
    write_json(patch_path, patch.to_dict())
    quality = result.plan.quality.to_dict() if result.plan.quality is not None else None
    write_json(quality_path, quality or {})
    validator = {
        "status": "passed",
        "checks": ["provider_edit_patch_schema", "edit_intent_validation", "song_plan_validation"],
        "checked_at": now,
    }
    write_json(validator_path, validator)
    preview = ProviderEditPreview(
        preview_id=preview_id,
        project_id=project_id,
        parent_version_id=parent_version_id,
        parent_job_id=parent_job_id,
        instruction=instruction,
        template_id=template.template_id,
        status="ready",
        created_at=now,
        patch=patch.to_dict(),
        summary=result.summary,
        source={
            "parent_version_id": parent_version_id,
            "parent_job_id": parent_job_id,
            "song_plan_sha256": song_plan_hash(parent_plan),
        },
        quality=quality,
        validator=validator,
        provider_usage=dict(provider_usage or {}),
        provider_request_id=provider_request_id,
    )
    write_json(preview_dir / "preview.json", preview.to_dict())
    return preview


def read_provider_edit_preview(project_dir: Path, preview_id: str) -> ProviderEditPreview:
    preview_dir = _safe_preview_dir(project_dir, preview_id)
    data = read_json(preview_dir / "preview.json")
    return ProviderEditPreview(
        preview_id=str(data["preview_id"]),
        project_id=str(data["project_id"]),
        parent_version_id=str(data["parent_version_id"]),
        parent_job_id=str(data["parent_job_id"]),
        instruction=str(data.get("instruction") or ""),
        template_id=str(data.get("template_id") or "provider-edit-intent"),
        status=str(data.get("status") or "ready"),
        created_at=str(data.get("created_at") or ""),
        patch=dict(data.get("patch") or {}),
        summary=dict(data.get("summary") or {}),
        source=dict(data.get("source") or {}),
        quality=data.get("quality") if isinstance(data.get("quality"), dict) else None,
        validator=dict(data.get("validator") or {}),
        provider_usage=dict(data.get("provider_usage") or {}),
        provider_request_id=None if data.get("provider_request_id") is None else str(data.get("provider_request_id")),
        error=None if data.get("error") is None else str(data.get("error")),
    )


def delete_provider_edit_preview(project_dir: Path, preview_id: str) -> None:
    preview_dir = _safe_preview_dir(project_dir, preview_id)
    if not preview_dir.exists():
        raise FileNotFoundError(preview_id)
    for path in sorted(preview_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    preview_dir.rmdir()


def mark_provider_edit_preview_applied(project_dir: Path, preview_id: str, job_id: str, version_id: str) -> ProviderEditPreview:
    preview_dir = _safe_preview_dir(project_dir, preview_id)
    preview = read_provider_edit_preview(project_dir, preview_id)
    data = preview.to_dict()
    data["status"] = "applied"
    data["applied_job_id"] = job_id
    data["applied_version_id"] = version_id
    write_json(preview_dir / "preview.json", data)
    return read_provider_edit_preview(project_dir, preview_id)


def preview_candidate_plan(project_dir: Path, preview_id: str) -> SongPlan:
    preview_dir = _safe_preview_dir(project_dir, preview_id)
    return SongPlan.from_dict(read_json(preview_dir / "candidate-song-plan.json"))


def preview_patch(project_dir: Path, preview_id: str) -> ProviderEditPatch:
    preview_dir = _safe_preview_dir(project_dir, preview_id)
    return ProviderEditPatch.from_dict(read_json(preview_dir / "patch.json"))


def song_plan_hash(plan: SongPlan) -> str:
    payload = json.dumps(plan.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def preview_stale(preview: ProviderEditPreview, parent_plan: SongPlan) -> bool:
    expected = str(preview.source.get("song_plan_sha256") or "")
    return bool(expected and expected != song_plan_hash(parent_plan))


def _operation_to_intent(operation: ProviderEditOperation) -> EditIntent:
    preserve = list(operation.preserve)
    strength = operation.strength or 6
    if operation.op == "set_section_energy":
        if operation.energy is not None:
            strength = 8 if operation.energy >= 0.55 else 3
        return EditIntent.from_dict(
            {
                "edit_type": "section_energy",
                "target": {"section_name": operation.section_name},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "set_section_chords":
        return EditIntent.from_dict(
            {
                "edit_type": "section_harmony",
                "target": {"section_name": operation.section_name, "field": "chords"},
                "payload": {"chords": operation.chords},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "set_track_density":
        return EditIntent.from_dict(
            {
                "edit_type": "track_density",
                "target": {"section_name": operation.section_name, "track_name": operation.track_name},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "rewrite_section_lyrics":
        return EditIntent.from_dict(
            {
                "edit_type": "lyrics_rewrite",
                "target": {"section_name": operation.section_name, "field": "lyrics"},
                "payload": {"lyrics": operation.lyrics},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "melody_variation":
        return EditIntent.from_dict(
            {
                "edit_type": "melody_variation",
                "target": {"section_name": operation.section_name},
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    if operation.op == "arrangement_variation":
        target: dict[str, Any] = {}
        if operation.section_name:
            target["section_name"] = operation.section_name
        if operation.track_name:
            target["track_name"] = operation.track_name
        payload = {"instrument": operation.instrument} if operation.instrument else {}
        return EditIntent.from_dict(
            {
                "edit_type": "arrangement_variation",
                "target": target,
                "payload": payload,
                "strength": strength,
                "provider_mode": "local",
                "preserve": preserve,
            }
        )
    raise ProviderEditError(f"Unsupported provider edit operation: {operation.op}.")


def _client_for_config(config: ProviderConfig) -> Any:
    if config.wire_api == "mock":
        from song_agent.providers.mock import MockProviderClient

        return MockProviderClient()
    if config.wire_api == "openai_chat_completions":
        from song_agent.providers.openai_compatible import OpenAICompatibleClient

        return OpenAICompatibleClient()
    raise ProviderConfigError(f"Unsupported provider wire_api: {config.wire_api}.")


def _provider_edit_response_parts(response: Any) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    if isinstance(response, ProviderEditResponse):
        return response.data, dict(response.usage or {}), response.request_id
    if isinstance(response, dict) and "data" in response and isinstance(response.get("data"), dict):
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        request_id = response.get("request_id")
        return response["data"], dict(usage), None if request_id is None else str(request_id)
    if isinstance(response, dict):
        return response, {}, None
    raise ProviderEditError("provider edit response must be a JSON object.")


def _scan_blocked_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in BLOCKED_KEYS or lowered.endswith("_path"):
                raise ProviderEditError(f"provider edit patch contains unsupported path or secret field: {key}.")
            _scan_blocked_fields(item)
    elif isinstance(value, list):
        for item in value:
            _scan_blocked_fields(item)


def _optional_text(value: Any, field_name: str, max_length: int) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return _bounded_text(value, field_name, max_length)


def _bounded_text(value: Any, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise ProviderEditError(f"{field_name} must be {max_length} characters or fewer.")
    return text


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ProviderEditError("energy must be between 0.0 and 1.0.")
    return number


def _optional_strength(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    strength = int(value)
    if strength < 1 or strength > 10:
        raise ProviderEditError("strength must be between 1 and 10.")
    return strength


def _chord_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProviderEditError("chords must be a list.")
    result = []
    invalid = []
    supported = {chord.lower(): chord for chord in SUPPORTED_HARMONY_CHORDS}
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        chord = supported.get(text.lower())
        if chord is None:
            invalid.append(text)
        else:
            result.append(chord)
    if invalid:
        raise ProviderEditError(f"Unsupported chord names: {', '.join(invalid)}.")
    return result[:8]


def _string_list(value: Any, field_name: str, *, max_items: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProviderEditError(f"{field_name} must be a list.")
    return [str(item).strip() for item in value if str(item).strip()][:max_items]


def _confidence(value: Any) -> float:
    if value is None or str(value).strip() == "":
        return 0.0
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise ProviderEditError("confidence must be between 0.0 and 1.0.")
    return number


def _candidate_count(value: Any) -> int:
    count = int(value or MIN_CANDIDATE_COUNT)
    if count < MIN_CANDIDATE_COUNT or count > MAX_CANDIDATE_COUNT:
        raise ProviderEditError(f"candidate_count must be between {MIN_CANDIDATE_COUNT} and {MAX_CANDIDATE_COUNT}.")
    return count


def _merge_usage(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    result = dict(left)
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        result[key] = int(result.get(key) or 0) + int(right.get(key) or 0)
    return result


def _next_preview_id(preview_root: Path) -> str:
    for index in range(1, 10_000):
        preview_id = f"preview-{index:03d}"
        if not (preview_root / preview_id).exists():
            return preview_id
    raise RuntimeError("Could not allocate a provider edit preview id.")


def _safe_preview_dir(project_dir: Path, preview_id: str) -> Path:
    if not re.match(r"^preview-[0-9]{3,5}$", preview_id):
        raise ValueError("Invalid preview id.")
    base = (project_dir / "edit-previews").resolve()
    target = (base / preview_id).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside edit-previews.") from exc
    return target
