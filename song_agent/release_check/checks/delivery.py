from song_agent.platform.contracts import ImplementationDocument


DOMAIN = "delivery"
GROUPS = frozenset({"distribution", "submission", "operations", "delivery"})
TAGS = frozenset({"delivery", "distribution", "operations", "release", "submission"})
CALLABLES: ImplementationDocument = {}
