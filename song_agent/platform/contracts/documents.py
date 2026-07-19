from __future__ import annotations

from typing import Any, TypeAlias


JsonPrimitive: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonDocument: TypeAlias = dict[str, JsonValue]

# Dynamic JSON is still required at parser and persistence boundaries.  Keeping
# that escape hatch named lets the architecture gate prevent it from becoming a
# public command, query, or report contract.
ImplementationDocument: TypeAlias = dict[str, Any]


__all__ = [
    "ImplementationDocument",
    "JsonDocument",
    "JsonPrimitive",
    "JsonValue",
]
