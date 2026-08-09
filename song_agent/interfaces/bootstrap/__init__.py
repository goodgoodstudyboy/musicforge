from __future__ import annotations

from collections.abc import Callable
from typing import ParamSpec, TypeVar


_P = ParamSpec("_P")
_T = TypeVar("_T")


def constructor(factory: Callable[_P, _T]) -> Callable[_P, _T]:
    """Preserve a concrete constructor's signature at a composition root."""

    return factory


__all__ = ["constructor"]
