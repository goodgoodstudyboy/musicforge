from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from song_agent.platform.contracts.documents import (
    JsonDocument,
    JsonValue,
    is_json_document_list,
    normalize_json_document,
    normalize_json_value,
)

def as_document(value: object) -> JsonDocument:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("Expected a JSON object.")
    return normalize_json_document(value)

def as_documents(value: object) -> list[JsonDocument]:
    if not isinstance(value, list):
        return []
    normalized = normalize_json_value(value)
    if not is_json_document_list(normalized):
        raise ValueError("Expected a JSON array containing only objects.")
    return normalized

def as_list(value: object) -> list[JsonValue]:
    if not isinstance(value, list):
        return []
    normalized = normalize_json_value(value)
    if not isinstance(normalized, list):
        raise ValueError("Expected a JSON array.")
    return normalized


def as_string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def document_or(value: object, fallback: JsonDocument) -> JsonDocument:
    selected: Mapping[str, object] = value if isinstance(value, Mapping) else fallback
    return normalize_json_document(selected)


def list_or(value: object, fallback: Sequence[object]) -> list[JsonValue]:
    selected = value if isinstance(value, list) else list(fallback)
    normalized = normalize_json_value(selected)
    if not isinstance(normalized, list):
        raise ValueError("Expected a JSON array.")
    return normalized


def as_path(value: object) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, os.PathLike):
        return Path(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A non-empty path is required.")
    return Path(value)


def as_int(value: object) -> int:
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return int(value)
    raise ValueError("An integer-compatible value is required.")


def as_float(value: object) -> float:
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return float(value)
    raise ValueError("A numeric value is required.")


def as_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("A string value is required.")
    return value
