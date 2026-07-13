from typing import Any


DOMAIN = "delivery"
GROUPS = frozenset({"distribution", "submission", "operations", "delivery"})
TAGS = frozenset({"delivery", "distribution", "operations", "release", "submission"})
CALLABLES: dict[str, Any] = {}
