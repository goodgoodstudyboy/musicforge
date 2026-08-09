from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable, Mapping
from os import PathLike
from typing import TypeAlias, TypeGuard


JsonPrimitive: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonDocument: TypeAlias = dict[str, JsonValue]


def is_json_value(value: object) -> TypeGuard[JsonValue]:
    if value is not None and not isinstance(value, (bool, int, float, str, list, dict)):
        return False
    try:
        _validate_json_input(value, set())
    except ValueError:
        return False
    return True


def is_json_document(value: object) -> TypeGuard[JsonDocument]:
    return isinstance(value, dict) and is_json_value(value)


def is_json_document_list(value: object) -> TypeGuard[list[JsonDocument]]:
    return isinstance(value, list) and all(is_json_document(item) for item in value)


def normalize_json_value(value: object) -> JsonValue:
    _validate_json_input(value, set())
    normalized: object = json.loads(
        json.dumps(value, ensure_ascii=False, allow_nan=False, default=_json_default)
    )
    if not is_json_value(normalized):
        raise ValueError("Value cannot be normalized to JSON.")
    return normalized


def normalize_json_document(value: Mapping[str, object]) -> JsonDocument:
    normalized = normalize_json_value(value)
    if not isinstance(normalized, dict):
        raise ValueError("JSON document must be an object.")
    return normalized


def _validate_json_input(value: object, active: set[int]) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite.")
        return
    if isinstance(value, PathLike):
        path = os.fspath(value)
        if not isinstance(path, str):
            raise ValueError("JSON path values must resolve to text.")
        return
    if not isinstance(value, (Mapping, list, tuple)):
        raise ValueError(f"Unsupported JSON value type: {type(value).__name__}.")
    identity = id(value)
    if identity in active:
        raise ValueError("Recursive JSON structures are not supported.")
    active.add(identity)
    try:
        if isinstance(value, Mapping):
            if not all(isinstance(key, str) for key in value):
                raise ValueError("JSON object keys must be strings.")
            values: Iterable[object] = value.values()
        else:
            values = value
        for item in values:
            _validate_json_input(item, active)
    finally:
        active.remove(identity)


def _json_default(value: object) -> object:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, PathLike):
        path = os.fspath(value)
        if isinstance(path, str):
            return path
    raise TypeError(f"Unsupported JSON value type: {type(value).__name__}.")
