from song_agent.release_check.checks.legacy import delegated_check


DOMAIN = "creation"
GROUPS = frozenset({"creation", "editing"})
TAGS = frozenset({"assets", "candidate", "editor", "provider", "references"})
CALLABLES = {
    "_final_export_smoke": delegated_check("_final_export_smoke"),
    "_edit_smoke": delegated_check("_edit_smoke"),
}
