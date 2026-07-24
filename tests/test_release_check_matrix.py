from __future__ import annotations

from pathlib import Path

from song_agent.release_check.matrix import (
    ReleaseCheckDefinition,
    ReleaseCheckMatrixError,
    all_check_definitions,
    select_check_definitions,
    validate_check_definitions,
)
from song_agent.release_check.runner import run_release_check_matrix


def test_release_check_definitions_are_valid() -> None:
    validate_check_definitions()
    definitions = all_check_definitions()
    by_id = {definition.check_id: definition for definition in definitions}

    assert len({definition.check_id for definition in definitions}) == len(definitions)
    assert "v74.attestation_portal_smoke" in {definition.check_id for definition in definitions}
    assert "v75.release_check_matrix_smoke" in {definition.check_id for definition in definitions}
    assert "v76.attestation_portal_review_response_smoke" in {definition.check_id for definition in definitions}
    assert "v77.attestation_accepted_evidence_smoke" in {definition.check_id for definition in definitions}
    assert "v78.attestation_transparency_feed_smoke" in {definition.check_id for definition in definitions}
    assert "v79.attestation_transparency_acknowledgement_smoke" in {definition.check_id for definition in definitions}
    assert "v80.public_trust_center_smoke" in {definition.check_id for definition in definitions}
    assert "v81.public_trust_center_delivery_smoke" in {definition.check_id for definition in definitions}
    assert "v101.lts_maintenance_backup_restore_smoke" in {definition.check_id for definition in definitions}
    assert "v102.audio_lab_real_listening_smoke" in {definition.check_id for definition in definitions}
    assert "v104.audio_campaign_smoke" in {definition.check_id for definition in definitions}
    assert "v105.audio_campaign_governance_smoke" in {definition.check_id for definition in definitions}
    assert "v109.release_audio_timeline_smoke" in {definition.check_id for definition in definitions}
    assert "v1012.release_audio_quality_observatory_smoke" in {definition.check_id for definition in definitions}
    assert "v1015.release_audio_command_center_smoke" in {definition.check_id for definition in definitions}
    assert "v112.unified_command_center_continuous_review_smoke" in {definition.check_id for definition in definitions}
    assert "v113.unified_command_center_drift_response_smoke" in {definition.check_id for definition in definitions}
    assert "v1211.unified_release_program_continuity_command_center_receiver_acceptance_smoke" in {definition.check_id for definition in definitions}
    assert "v1212.unified_release_program_continuity_command_center_receiver_acceptance_change_control_smoke" in {definition.check_id for definition in definitions}
    assert "v1213.release_check_acceleration_smoke" in {definition.check_id for definition in definitions}
    assert "v1214.architecture_guardrails_smoke" in {definition.check_id for definition in definitions}
    assert "v1301.shared_kernel_security_smoke" in {definition.check_id for definition in definitions}
    assert "v131.architecture_ratchet_smoke" in {definition.check_id for definition in definitions}
    assert "v132.kernel_adoption_smoke" in {definition.check_id for definition in definitions}
    assert "v133.program_persistence_authority_smoke" in {definition.check_id for definition in definitions}
    assert "v134.program_vertical_slice_smoke" in {definition.check_id for definition in definitions}
    assert "v135.interface_decomposition_smoke" in {definition.check_id for definition in definitions}
    assert "v136.policy_gate_cutover_smoke" in {definition.check_id for definition in definitions}
    assert "v140.architecture_cutover_smoke" in {definition.check_id for definition in definitions}
    assert "v141.quality_debt_closure_smoke" in {definition.check_id for definition in definitions}
    assert "v1421.stabilization_rollback_smoke" in {definition.check_id for definition in definitions}
    assert "v1422.explicit_any_scope_smoke" in {definition.check_id for definition in definitions}
    assert "v1423.explicit_any_lambda_scope_smoke" in {definition.check_id for definition in definitions}
    assert "v1424.explicit_any_definition_time_scope_smoke" in {definition.check_id for definition in definitions}
    assert "v1425.explicit_any_class_global_scope_smoke" in {definition.check_id for definition in definitions}
    assert "v1426.explicit_any_indirect_target_scope_smoke" in {definition.check_id for definition in definitions}
    assert "v1427.explicit_any_derived_uncertain_scope_smoke" in {definition.check_id for definition in definitions}
    assert "v1428.explicit_any_object_alias_scope_smoke" in {definition.check_id for definition in definitions}
    assert "v1429.explicit_any_alias_dataflow_smoke" in {definition.check_id for definition in definitions}
    assert "v14210.explicit_any_alias_fail_closed_smoke" in {
        definition.check_id for definition in definitions
    }
    assert by_id["v1212.receiver_acceptance_change_control_zip_security"].duration_budget_seconds == 90
    assert by_id["pytest.full"].timeout_seconds >= 6000


def test_release_check_profile_and_filters() -> None:
    latest = select_check_definitions(profile="latest")
    v7 = select_check_definitions(profile="v7")
    v8 = select_check_definitions(profile="v8")
    v10 = select_check_definitions(profile="v10")
    v11 = select_check_definitions(profile="v11")
    v14 = select_check_definitions(profile="v14")
    ga = select_check_definitions(profile="ga", run_tests=False)
    portal = select_check_definitions(profile="latest", groups=["portal"])
    since = select_check_definitions(profile="v7", since="7.2")
    only = select_check_definitions(profile="full", only=["v75.release_check_matrix_smoke"])

    assert "v1219.evidence_policy_smoke" in {definition.check_id for definition in latest}
    assert "v1220.release_check_governance_smoke" in {definition.check_id for definition in latest}
    assert "v74.attestation_portal_smoke" not in {definition.check_id for definition in latest}
    assert "v70.release_portfolio_governance_final_board_smoke" in {definition.check_id for definition in v7}
    assert [definition.check_id for definition in v8] == [
        "v80.public_trust_center_smoke",
        "v81.public_trust_center_delivery_smoke",
        "v82.public_trust_center_anchor_registry_smoke",
        "v83.public_trust_center_anchor_transparency_smoke",
        "v84.public_trust_center_distribution_kit_smoke",
        "v85.public_trust_center_distribution_kit_acceptance_smoke",
        "v86.public_trust_center_acceptance_board_smoke",
        "v87.public_trust_center_acceptance_board_signoff_smoke",
        "v88.public_trust_center_publication_channels_smoke",
        "v89.public_trust_center_publication_monitoring_smoke",
    ]
    assert "git.diff_check" in {definition.check_id for definition in ga}
    assert "meta.version_consistency" in {definition.check_id for definition in ga}
    assert "security.secret_scan" in {definition.check_id for definition in ga}
    assert "v1219.evidence_policy_smoke" in {definition.check_id for definition in ga}
    assert "v1220.release_check_governance_smoke" in {definition.check_id for definition in ga}
    assert "v140.architecture_cutover_smoke" in {definition.check_id for definition in v14}
    assert [definition.check_id for definition in v14] == [
        "git.diff_check",
        "meta.version_consistency",
        "security.secret_scan",
        "v140.architecture_cutover_smoke",
        "v140.compatibility_zero_smoke",
        "v140.interface_application_boundary_smoke",
        "v140.domain_vertical_slice_smoke",
        "v140.verification_lifecycle_security_smoke",
        "v140.migration_rollback_smoke",
        "v140.typing_coverage_ratchet_smoke",
        "v140.public_contract_compatibility_smoke",
        "v140.reviewer_package_smoke",
        "v141.quality_debt_closure_smoke",
        "v1421.stabilization_rollback_smoke",
        "v1422.explicit_any_scope_smoke",
        "v1423.explicit_any_lambda_scope_smoke",
        "v1424.explicit_any_definition_time_scope_smoke",
        "v1425.explicit_any_class_global_scope_smoke",
        "v1426.explicit_any_indirect_target_scope_smoke",
        "v1427.explicit_any_derived_uncertain_scope_smoke",
        "v1428.explicit_any_object_alias_scope_smoke",
        "v1429.explicit_any_alias_dataflow_smoke",
        "v14210.explicit_any_alias_fail_closed_smoke",
    ]
    assert "v75.release_check_matrix_smoke" not in {definition.check_id for definition in ga}
    assert [definition.check_id for definition in v10] == [
        "v100.ga_lts_readiness_smoke",
        "v101.lts_maintenance_backup_restore_smoke",
        "v102.audio_lab_real_listening_smoke",
        "v103.audio_fix_sprint_smoke",
        "v104.audio_campaign_smoke",
        "v105.audio_campaign_governance_smoke",
        "v106.release_driven_audio_campaign_smoke",
        "v107.release_audio_campaign_remediation_smoke",
        "v108.release_audio_certification_smoke",
        "v109.release_audio_timeline_smoke",
        "v1010.release_audio_regression_guard_smoke",
        "v1011.release_audio_baseline_response_smoke",
        "v1012.release_audio_quality_observatory_smoke",
        "v1013.release_audio_quality_action_queue_smoke",
        "v1014.release_audio_quality_action_queue_signoff_smoke",
        "v1015.release_audio_command_center_smoke",
    ]
    assert [definition.check_id for definition in v11] == [
        "v110.unified_command_center_smoke",
        "v111.unified_command_center_signoff_archive_smoke",
        "v112.unified_command_center_continuous_review_smoke",
        "v113.unified_command_center_drift_response_smoke",
        "v114.unified_command_center_evidence_review_smoke",
        "v115.unified_command_center_reviewer_decision_board_smoke",
        "v116.unified_command_center_release_train_smoke",
        "v117.unified_command_center_release_train_change_control_smoke",
        "v118.unified_command_center_release_train_lifecycle_smoke",
        "v119.unified_command_center_release_train_handoff_smoke",
    ]
    assert [definition.check_id for definition in select_check_definitions(profile="v12")] == [
        "v1213.v12_continuity_fixture_prepare",
        "v129.command_center_runtime_inventory",
        "v129.command_center_external_binding",
        "v129.command_center_ga_gate",
        "v1210.command_center_signoff_semantics",
        "v1210.command_center_signoff_archive_verifier",
        "v1210.command_center_signoff_reset_guard",
        "v1211.receiver_acceptance_semantics",
        "v1211.receiver_acceptance_zip_security",
        "v1211.receiver_acceptance_ga_gate",
        "v1212.receiver_acceptance_change_control_semantics",
        "v1212.receiver_acceptance_change_control_zip_security",
        "v1212.receiver_acceptance_change_control_external_binding",
        "v1212.receiver_acceptance_change_control_signed_mutation",
        "v1212.receiver_acceptance_change_control_thin_integration",
        "v1213.release_check_acceleration_smoke",
        "v1214.architecture_guardrails_smoke",
        "v1215.verification_kernel_smoke",
        "v1216.lifecycle_kernel_smoke",
        "v1217.persistence_kernel_smoke",
        "v1218.interface_registry_smoke",
        "v1219.evidence_policy_smoke",
        "v1220.release_check_governance_smoke",
    ]
    assert portal == []
    assert all(definition.version is not None and tuple(int(part) for part in definition.version.split(".")[:2]) >= (7, 2) for definition in since)
    assert [definition.check_id for definition in only] == ["v75.release_check_matrix_smoke"]


def test_release_check_unknown_filters_fail() -> None:
    try:
        select_check_definitions(profile="latest", groups=["missing-group"])
    except ReleaseCheckMatrixError as exc:
        assert "Unknown release-check group" in str(exc)
    else:
        raise AssertionError("unknown group should fail")

    try:
        select_check_definitions(only=["missing.check"])
    except ReleaseCheckMatrixError as exc:
        assert "Unknown release-check id" in str(exc)
    else:
        raise AssertionError("unknown check id should fail")


def test_release_check_runner_json_and_timing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "7.5.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## v7.5.0\n", encoding="utf-8")

    report = run_release_check_matrix(repo_root=tmp_path, profile="latest", only=["v75.release_check_matrix_smoke"])
    payload = report.to_json_report()
    timing = report.to_timing_report()

    assert report.ok is True, payload
    assert payload["summary"]["total"] == 1
    assert payload["results"][0]["check_id"] == "v75.release_check_matrix_smoke"
    assert timing["results"][0]["duration_ms"] >= 0
    assert payload["summary"]["duration_budget_status"] in {"passed", "warning"}
    assert "slow_checks" in payload["summary"]
    assert "checks_over_budget" in timing


def test_release_check_runner_empty_selection_fails() -> None:
    report = run_release_check_matrix(profile="latest", since="99.0")
    payload = report.to_json_report()

    assert report.ok is False
    assert payload["summary"]["total"] == 1
    assert payload["results"][0]["check_id"] == "release_check.selection"
    assert "No release-checks selected" in payload["results"][0]["detail"]


def test_release_check_warning_summary_counts_expected_and_unexpected(tmp_path: Path) -> None:
    definitions = [
        ReleaseCheckDefinition(
            check_id="fake.warning",
            name="fake warning",
            group="meta",
            version="7.5",
            kind="pytest",
            risk="normal",
            timeout_seconds=10,
            command=("python", "-c", "import sys; print('warning: expected', file=sys.stderr); print('warning: surprise', file=sys.stderr)"),
            expected_warnings=("warning: expected",),
            profiles=("latest",),
        )
    ]

    report = run_release_check_matrix(repo_root=tmp_path, profile="latest", definitions=definitions)
    summary = report.to_json_report()["summary"]

    assert report.ok is True
    assert summary["warning"] == 0
    assert summary["checks_with_warnings"] == 1
    assert summary["expected_warnings"] == 1
    assert summary["unexpected_warnings"] == 1
