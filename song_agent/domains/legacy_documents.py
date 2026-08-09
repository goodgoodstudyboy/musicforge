from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Callable
from typing import cast

from song_agent.domains import (
    _ImplementationDocument as ImplementationDocument,
    _ImplementationValue,
)
from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.persistence.program import program_json_facade as _typed_program_json_facade


# Domain migration is intentionally staged across Waves 2-4. This private
# compatibility contract keeps the existing domain implementations stable
# while Wave 1 removes dynamic JSON from platform, application, and interfaces.
def _as_document(value: object) -> ImplementationDocument:
    return cast(ImplementationDocument, value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[_ImplementationValue]:
    return cast(list[_ImplementationValue], value) if isinstance(value, list) else []


def _document_or(
    value: object,
    fallback: ImplementationDocument,
) -> ImplementationDocument:
    return cast(ImplementationDocument, value) if isinstance(value, dict) else fallback


def _list_or(
    value: object,
    fallback: list[_ImplementationValue],
) -> list[_ImplementationValue]:
    return cast(list[_ImplementationValue], value) if isinstance(value, list) else fallback


def _as_path(value: object) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, os.PathLike):
        return Path(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A non-empty path is required.")
    return Path(value)


def _as_int(value: object) -> int:
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return int(value)
    raise ValueError("An integer-compatible value is required.")


def _as_float(value: object) -> float:
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return float(value)
    raise ValueError("A numeric value is required.")


def _as_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("A string value is required.")
    return value


def _program_json_facade(
    error_type: type[Exception],
) -> tuple[
    Callable[[Path], ImplementationDocument],
    Callable[[Path, ImplementationDocument], Path],
]:
    """Adapt the strict persistence port for domains scheduled after Wave 1."""
    typed_read, typed_write = _typed_program_json_facade(error_type)

    def read(path: Path) -> ImplementationDocument:
        return cast(ImplementationDocument, typed_read(path))

    def write(path: Path, data: ImplementationDocument) -> Path:
        return typed_write(path, cast(JsonDocument, data))

    return read, write


__all__ = [
    "ImplementationDocument",
    "_as_document",
    "_as_float",
    "_as_int",
    "_as_list",
    "_as_path",
    "_as_text",
    "_document_or",
    "_list_or",
    "_program_json_facade",
]
