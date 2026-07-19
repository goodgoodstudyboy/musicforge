from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument
import os
from pathlib import Path
from typing import Any


def as_document(value: Any) -> DomainDocument:
    """Return a mapping-shaped JSON value without copying it."""
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    """Return a list-shaped JSON value without copying it."""
    return value if isinstance(value, list) else []


def document_or(value: Any, fallback: DomainDocument) -> DomainDocument:
    """Return a mapping-shaped value or an explicit mapping fallback."""
    return value if isinstance(value, dict) else fallback


def list_or(value: Any, fallback: list[Any]) -> list[Any]:
    """Return a list-shaped value or an explicit list fallback."""
    return value if isinstance(value, list) else fallback


def as_path(value: Any) -> Path:
    """Coerce a required path while preserving fail-closed input semantics."""
    if isinstance(value, Path):
        return value
    if isinstance(value, os.PathLike):
        return Path(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A non-empty path is required.")
    return Path(value)


def as_int(value: Any) -> int:
    """Apply the native integer conversion behind a typed JSON boundary."""
    return int(value)


def as_float(value: Any) -> float:
    """Apply the native float conversion behind a typed JSON boundary."""
    return float(value)


def as_text(value: Any) -> str:
    """Coerce a required string without turning missing values into text."""
    if not isinstance(value, str):
        raise ValueError("A string value is required.")
    return value
