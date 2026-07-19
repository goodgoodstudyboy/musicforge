from song_agent.platform.contracts import ImplementationDocument


DOMAIN = "trust"
GROUPS = frozenset({"attestation", "governance", "portal", "portfolio", "trust"})
TAGS = frozenset({"attestation", "governance", "portfolio", "trust"})
CALLABLES: ImplementationDocument = {}
