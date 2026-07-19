from typing import Any


DOMAIN = "trust"
GROUPS = frozenset({"attestation", "governance", "portal", "portfolio", "trust"})
TAGS = frozenset({"attestation", "governance", "portfolio", "trust"})
CALLABLES: dict[str, Any] = {}
