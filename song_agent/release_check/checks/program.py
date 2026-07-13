from song_agent.release_check.checks.legacy import delegated_check


DOMAIN = "program"
GROUPS = frozenset({"command-center", "program"})
TAGS = frozenset({"command-center", "continuity", "program", "unified-release-program"})
_CURRENT_PROGRAM_CHECKS = (
    "_v1213_v12_fixture_prepare_smoke",
    "_v129_command_center_runtime_inventory",
    "_v129_command_center_external_binding",
    "_v129_command_center_ga_gate",
    "_v1210_command_center_signoff_semantics",
    "_v1210_command_center_signoff_archive_verifier",
    "_v1210_command_center_signoff_reset_guard",
    "_v1211_receiver_acceptance_semantics",
    "_v1211_receiver_acceptance_zip_security",
    "_v1211_receiver_acceptance_ga_gate",
    "_v1212_receiver_acceptance_change_control_semantics",
    "_v1212_receiver_acceptance_change_control_zip_security",
    "_v1212_receiver_acceptance_change_control_external_binding",
    "_v1212_receiver_acceptance_change_control_signed_mutation",
    "_v1212_receiver_acceptance_change_control_thin_integration",
)
CALLABLES = {name: delegated_check(name) for name in _CURRENT_PROGRAM_CHECKS}
