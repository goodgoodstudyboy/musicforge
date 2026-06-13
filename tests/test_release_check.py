from pathlib import Path

from song_agent.release_checks import (
    ReleaseCheckReport,
    _edit_smoke,
    _final_export_smoke,
    _redact_line,
    _remote_has_token,
    _status_is_clean,
    _v38_release_zip_verifier_smoke,
    _v39_release_metadata_smoke,
    _v40_distribution_prep_smoke,
    _v41_distribution_template_packs_smoke,
    _v42_distribution_layout_contract_smoke,
    _v43_submission_workspace_smoke,
    _v44_music_acceptance_lab_smoke,
    _v45_acceptance_profiles_songbook_smoke,
    _v46_human_review_pack_smoke,
    _v47_acceptance_analytics_smoke,
    _v48_acceptance_fix_sprint_smoke,
    _v49_acceptance_knowledge_base_smoke,
    _v410_knowledge_assisted_fix_planning_smoke,
    _v411_fix_plan_outcome_review_smoke,
    _v412_planning_rule_simulation_smoke,
    _v413_planning_rule_governance_smoke,
    _v414_planning_rule_impact_smoke,
    _v50_real_audio_baseline_smoke,
    _v51_per_track_audio_review_smoke,
    _v52_arrangement_mix_controls_smoke,
    _v53_audio_revision_workbench_smoke,
    _v54_mastering_qa_smoke,
    _v55_distribution_audio_formats_smoke,
    _v56_encoded_audio_acceptance_smoke,
    _v57_release_format_decision_smoke,
    _v58_rights_clearance_smoke,
    _v59_submission_evidence_archive_smoke,
    _v60_release_operations_dashboard_smoke,
    _v61_release_operations_runbook_smoke,
    _v62_release_operations_signoff_archive_smoke,
    _v63_release_operations_audit_ledger_smoke,
    _v64_release_operations_reviewer_pack_smoke,
    _v65_release_portfolio_audit_smoke,
    _v66_release_portfolio_governance_queue_smoke,
    _v67_release_portfolio_governance_signoff_smoke,
    _v68_release_portfolio_governance_audit_ledger_smoke,
    _v69_release_portfolio_governance_reviewer_pack_smoke,
    _v70_release_portfolio_governance_final_board_smoke,
    _v71_release_portfolio_governance_evidence_vault_smoke,
    _v72_release_portfolio_governance_attestation_smoke,
    _v73_release_portfolio_governance_attestation_registry_smoke,
    _v74_release_portfolio_governance_attestation_portal_smoke,
    _v75_release_check_matrix_smoke,
    _v76_attestation_portal_review_response_smoke,
    _v77_attestation_accepted_evidence_smoke,
    _v78_attestation_transparency_feed_smoke,
    _v79_attestation_transparency_acknowledgement_smoke,
    _v80_public_trust_center_smoke,
    _v81_public_trust_center_delivery_smoke,
    _version_consistency,
    print_release_check_report,
)


def test_status_is_clean_accepts_only_clean_branch_line() -> None:
    assert _status_is_clean("## master...origin/master") is True
    assert _status_is_clean("## master...origin/master [ahead 1]") is False
    assert _status_is_clean("## master...origin/master\n M README.md") is False


def test_remote_token_detection() -> None:
    assert _remote_has_token("origin https://github.com/user/repo.git") is False
    assert _remote_has_token("origin https://x-access-token:secret@github.com/user/repo.git") is True
    assert _remote_has_token("origin https://github_pat_abc123@github.com/user/repo.git") is True


def test_redact_line_masks_secret_like_values() -> None:
    line = _redact_line('Authorization: Bearer secret-token api_key="secret-value" sk-test-secret-value')

    assert "secret-token" not in line
    assert "secret-value" not in line
    assert "sk-test-secret-value" not in line


def test_version_consistency_checks_pyproject_and_changelog(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.5.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## v0.5.0\n", encoding="utf-8")
    monkeypatch.setattr("song_agent.release_checks.__version__", "0.5.0")

    ok, detail = _version_consistency(tmp_path)

    assert ok is True, detail
    assert "package=0.5.0" in detail


def test_final_export_smoke_builds_bundle(tmp_path: Path) -> None:
    ok, detail = _final_export_smoke(tmp_path)

    assert ok is True
    assert "version=v001" in detail


def test_edit_smoke_preserves_parent_and_renders_child(tmp_path: Path) -> None:
    ok, detail = _edit_smoke(tmp_path)

    assert ok is True
    assert "parent_unchanged=True" in detail


def test_v38_release_zip_verifier_smoke(tmp_path: Path) -> None:
    ok, detail = _v38_release_zip_verifier_smoke(tmp_path)

    assert ok is True, detail
    assert "external=warning" in detail


def test_v39_release_metadata_smoke(tmp_path: Path) -> None:
    ok, detail = _v39_release_metadata_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail


def test_v40_distribution_prep_smoke(tmp_path: Path) -> None:
    ok, detail = _v40_distribution_prep_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "external=passed" in detail


def test_v41_distribution_template_packs_smoke(tmp_path: Path) -> None:
    ok, detail = _v41_distribution_template_packs_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "template_tamper=failed" in detail
    assert "checklist_tamper=failed" in detail


def test_v42_distribution_layout_contract_smoke(tmp_path: Path) -> None:
    ok, detail = _v42_distribution_layout_contract_smoke(tmp_path)

    assert ok is True, detail
    assert "external=passed" in detail
    assert "layout_tamper=failed" in detail
    assert "artwork_path_tamper=failed" in detail


def test_v57_release_format_decision_smoke(tmp_path: Path) -> None:
    ok, detail = _v57_release_format_decision_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "tampered=failed" in detail
    assert "pitch_archive_only=409/failed" in detail
    assert "internal_archive=200/passed" in detail


def test_v58_rights_clearance_smoke(tmp_path: Path) -> None:
    ok, detail = _v58_rights_clearance_smoke(tmp_path)

    assert ok is True, detail
    assert "release=200/200/200/passed" in detail
    assert "tampered=failed" in detail
    assert "distribution=201/200/passed" in detail
    assert "submission=201/200/200/passed" in detail


def test_v59_submission_evidence_archive_smoke(tmp_path: Path) -> None:
    ok, detail = _v59_submission_evidence_archive_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "source_path=400" in detail
    assert "blocked_after_sign=409" in detail
    assert "signoff_tamper=failed" in detail
    assert "report_tamper=failed" in detail


def test_v60_release_operations_dashboard_smoke(tmp_path: Path) -> None:
    ok, detail = _v60_release_operations_dashboard_smoke(tmp_path)

    assert ok is True, detail
    assert "stage=submission_ready->accepted" in detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "tamper=failed" in detail
    assert "duplicate=failed" in detail
    assert "redaction=failed" in detail


def test_v61_release_operations_runbook_smoke(tmp_path: Path) -> None:
    ok, detail = _v61_release_operations_runbook_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "stale=409" in detail
    assert "tamper=failed" in detail
    assert "duplicate=failed" in detail
    assert "redaction=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "signed_mutation=5/unchanged" in detail


def test_v62_release_operations_signoff_archive_smoke(tmp_path: Path) -> None:
    ok, detail = _v62_release_operations_signoff_archive_smoke(tmp_path)

    assert ok is True, detail
    assert "sign=signed" in detail
    assert "archive=passed" in detail
    assert "external=passed" in detail
    assert "stale=409" in detail
    assert "tamper=failed/failed" in detail
    assert "duplicate_zip=failed" in detail
    assert "redaction=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "reset_guard=409/409" in detail
    assert "change_request=applied" in detail


def test_v63_release_operations_audit_ledger_smoke(tmp_path: Path) -> None:
    ok, detail = _v63_release_operations_audit_ledger_smoke(tmp_path)

    assert ok is True, detail
    assert "audit=passed" in detail
    assert "external=passed" in detail
    assert "archive_verified_missing=failed" in detail
    assert "tamper=failed" in detail
    assert "missing=failed" in detail
    assert "reorder=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail
    assert "history_reset=failed" in detail
    assert "cr=applied" in detail


def test_v64_release_operations_reviewer_pack_smoke(tmp_path: Path) -> None:
    ok, detail = _v64_release_operations_reviewer_pack_smoke(tmp_path)

    assert ok is True, detail
    assert "reviewer=passed" in detail
    assert "external=passed" in detail
    assert "tamper=failed" in detail
    assert "retro_tamper=failed" in detail
    assert "missing=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail


def test_v65_release_portfolio_audit_smoke(tmp_path: Path) -> None:
    ok, detail = _v65_release_portfolio_audit_smoke(tmp_path)

    assert ok is True, detail
    assert "portfolio=passed" in detail
    assert "external=passed" in detail
    assert "releases=2" in detail
    assert "tamper=failed" in detail
    assert "trend_tamper=failed" in detail
    assert "risk_tamper=failed" in detail
    assert "missing=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail
    assert "missing_reviewer=failed" in detail


def test_v66_release_portfolio_governance_queue_smoke(tmp_path: Path) -> None:
    ok, detail = _v66_release_portfolio_governance_queue_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "manual=" in detail
    assert "post_refresh=True" in detail
    assert "duplicate_existing=True" in detail
    assert "action_tamper=failed" in detail
    assert "execution_tamper=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail
    assert "stale=True" in detail
    assert "stale_export=True" in detail
    assert "stale_zip=True" in detail


def test_v67_release_portfolio_governance_signoff_smoke(tmp_path: Path) -> None:
    ok, detail = _v67_release_portfolio_governance_signoff_smoke(tmp_path)

    assert ok is True, detail
    assert "signoff=passed" in detail
    assert "archive=passed" in detail
    assert "external=passed" in detail
    assert "stale=409" in detail
    assert "signed_mutation=409/409/409" in detail
    assert "reset=409/200/409" in detail
    assert "tamper=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail


def test_v68_release_portfolio_governance_audit_ledger_smoke(tmp_path: Path) -> None:
    ok, detail = _v68_release_portfolio_governance_audit_ledger_smoke(tmp_path)

    assert ok is True, detail
    assert "report=passed" in detail
    assert "ledger=passed" in detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "stale_archive=failed" in detail
    assert "stale_export=True" in detail
    assert "stale_zip=True" in detail
    assert "tamper=failed" in detail
    assert "reorder=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail
    assert "package_type=failed" in detail


def test_v69_release_portfolio_governance_reviewer_pack_smoke(tmp_path: Path) -> None:
    ok, detail = _v69_release_portfolio_governance_reviewer_pack_smoke(tmp_path)

    assert ok is True, detail
    assert "report=passed" in detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "stale_audit_verification=failed" in detail
    assert "stale_export=True" in detail
    assert "stale_zip=True" in detail
    assert "tamper=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail
    assert "package_type=failed" in detail


def test_v70_release_portfolio_governance_final_board_smoke(tmp_path: Path) -> None:
    ok, detail = _v70_release_portfolio_governance_final_board_smoke(tmp_path)

    assert ok is True, detail
    assert "report=passed" in detail
    assert "signoff=signed" in detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "missing_response=failed" in detail
    assert "needs_changes=failed/409" in detail
    assert "signed_mutation=True/True" in detail
    assert "delete_rebuild=True/True" in detail
    assert "stale_reviewer=failed" in detail
    assert "stale_audit=failed" in detail
    assert "tamper=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail
    assert "package_type=failed" in detail


def test_v43_submission_workspace_smoke(tmp_path: Path) -> None:
    ok, detail = _v43_submission_workspace_smoke(tmp_path)

    assert ok is True, detail
    assert "external=passed" in detail
    assert "signoff_tamper=failed" in detail
    assert "target_tamper=failed" in detail


def test_v44_music_acceptance_lab_smoke(tmp_path: Path) -> None:
    ok, detail = _v44_music_acceptance_lab_smoke(tmp_path)

    assert ok is True, detail
    assert "health=passed" in detail
    assert "report_tamper=failed" in detail
    assert "signoff_integrity=failed" in detail
    assert "missing_midi=failed" in detail
    assert "signed_guard=409" in detail


def test_v45_acceptance_profiles_songbook_smoke(tmp_path: Path) -> None:
    ok, detail = _v45_acceptance_profiles_songbook_smoke(tmp_path)

    assert ok is True, detail
    assert "songs=12" in detail
    assert "diff=passed" in detail
    assert "rc=failed" in detail
    assert "incomplete_rc=failed" in detail
    assert "release_gate=409" in detail


def test_v46_human_review_pack_smoke(tmp_path: Path) -> None:
    ok, detail = _v46_human_review_pack_smoke(tmp_path)

    assert ok is True, detail
    assert "cases=12" in detail
    assert "verify=passed" in detail
    assert "needs_fix=1" in detail
    assert "reimport=201" in detail
    assert "all=release_ready_passed" in detail
    assert "pack_stale=False/False" in detail
    assert "tampered=failed" in detail
    assert "guards=400/409" in detail
    assert "song_mismatch=400" in detail


def test_v47_acceptance_analytics_smoke(tmp_path: Path) -> None:
    ok, detail = _v47_acceptance_analytics_smoke(tmp_path)

    assert ok is True, detail
    assert "heatmap=12" in detail
    assert "readiness=blocked" in detail
    assert "stale=True/409" in detail
    assert "release_gate=409/200" in detail
    assert "export_summary=blocked" in detail


def test_v48_acceptance_fix_sprint_smoke(tmp_path: Path) -> None:
    ok, detail = _v48_acceptance_fix_sprint_smoke(tmp_path)

    assert ok is True, detail
    assert "tasks=201/200" in detail
    assert "close=passed" in detail
    assert "project=closed" in detail
    assert "final=closed" in detail
    assert "gate=passed" in detail
    assert "stale_guard=409" in detail
    assert "stale_force_close=409" in detail


def test_v49_acceptance_knowledge_base_smoke(tmp_path: Path) -> None:
    ok, detail = _v49_acceptance_knowledge_base_smoke(tmp_path)

    assert ok is True, detail
    assert "entries=1" in detail
    assert "effective=1" in detail
    assert "search=1" in detail
    assert "recommendation=available" in detail
    assert "export=ok" in detail
    assert "hide_refresh=0/1" in detail


def test_v410_knowledge_assisted_fix_planning_smoke(tmp_path: Path) -> None:
    ok, detail = _v410_knowledge_assisted_fix_planning_smoke(tmp_path)

    assert ok is True, detail
    assert "plan=afp-" in detail
    assert "items=1" in detail
    assert "kb=1" in detail
    assert "sprint=afs-" in detail
    assert "duplicate=409" in detail
    assert "stale_guard=409" in detail
    assert "hidden=excluded/included" in detail


def test_v411_fix_plan_outcome_review_smoke(tmp_path: Path) -> None:
    ok, detail = _v411_fix_plan_outcome_review_smoke(tmp_path)

    assert ok is True, detail
    assert "review=afpr-" in detail
    assert "effectiveness=" in detail
    assert "helpfulness=" in detail
    assert "stale_guard=409" in detail
    assert "manual=False" in detail
    assert "synthetic_only=True" in detail
    assert "signoff=passed" in detail


def test_v412_planning_rule_simulation_smoke(tmp_path: Path) -> None:
    ok, detail = _v412_planning_rule_simulation_smoke(tmp_path)

    assert ok is True, detail
    assert "ruleset=afprs-" in detail
    assert "simulation=afpsim-" in detail
    assert "synthetic=1" in detail
    assert "stale_guard=409" in detail
    assert "signoff=passed" in detail


def test_v413_planning_rule_governance_smoke(tmp_path: Path) -> None:
    ok, detail = _v413_planning_rule_governance_smoke(tmp_path)

    assert ok is True, detail
    assert "promotion=prgprom-" in detail
    assert "version=prgv-" in detail
    assert "signoff=passed" in detail
    assert "stale_guard=409" in detail
    assert "tampered_version=409" in detail
    assert "rollback=passed" in detail


def test_v414_planning_rule_impact_smoke(tmp_path: Path) -> None:
    ok, detail = _v414_planning_rule_impact_smoke(tmp_path)

    assert ok is True, detail
    assert "report=prgir-" in detail
    assert "active=prgv-" in detail
    assert "signoff=" in detail
    assert "tampered_report=409" in detail
    assert "stale_guard=409" in detail
    assert "rollback_watch=409/200" in detail


def test_v50_real_audio_baseline_smoke(tmp_path: Path) -> None:
    ok, detail = _v50_real_audio_baseline_smoke(tmp_path)

    assert ok is True, detail
    assert "audio=passed" in detail
    assert "missing_audio=failed" in detail
    assert "human_missing=409" in detail
    assert "verify=" in detail


def test_v51_per_track_audio_review_smoke(tmp_path: Path) -> None:
    ok, detail = _v51_per_track_audio_review_smoke(tmp_path)

    assert ok is True, detail
    assert "missing_gate=409" in detail
    assert "synthetic_gate=409" in detail
    assert "sign=200" in detail
    assert "verify=" in detail
    assert "tampered=failed" in detail
    assert "redaction=failed" in detail


def test_v52_arrangement_mix_controls_smoke(tmp_path: Path) -> None:
    ok, detail = _v52_arrangement_mix_controls_smoke(tmp_path)

    assert ok is True, detail
    assert "preview=201" in detail
    assert "apply=201" in detail
    assert "missing_mix_gate=409" in detail
    assert "sign=200" in detail
    assert "tampered_stem=failed" in detail


def test_v53_audio_revision_workbench_smoke(tmp_path: Path) -> None:
    ok, detail = _v53_audio_revision_workbench_smoke(tmp_path)

    assert ok is True, detail
    assert "session=201" in detail
    assert "apply=200" in detail
    assert "close=200" in detail
    assert "sign=200" in detail
    assert "verify=" in detail
    assert "candidate_tamper=failed" in detail


def test_v54_mastering_qa_smoke(tmp_path: Path) -> None:
    ok, detail = _v54_mastering_qa_smoke(tmp_path)

    assert ok is True, detail
    assert "analysis_only=409" in detail
    assert "stale_export=409" in detail
    assert "sign=200" in detail
    assert "tamper_selected=failed" in detail


def test_v55_distribution_audio_formats_smoke(tmp_path: Path) -> None:
    ok, detail = _v55_distribution_audio_formats_smoke(tmp_path)

    assert ok is True, detail
    assert "encode=201/completed" in detail
    assert "stale_export=409" in detail
    assert "sign=200" in detail
    assert "dist_verify=" in detail
    assert "tampered=failed" in detail
    assert "signed_guard=409" in detail


def test_v56_encoded_audio_acceptance_smoke(tmp_path: Path) -> None:
    ok, detail = _v56_encoded_audio_acceptance_smoke(tmp_path)

    assert ok is True, detail
    assert "missing_review=409" in detail
    assert "synthetic_gate=409" in detail
    assert "manual=201" in detail
    assert "acceptance=200/passed" in detail
    assert "stale_export=409" in detail
    assert "sign=200" in detail
    assert "tampered_review=failed" in detail


def test_v71_release_portfolio_governance_evidence_vault_smoke(tmp_path: Path) -> None:
    ok, detail = _v71_release_portfolio_governance_evidence_vault_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed/passed" in detail
    assert "external=passed" in detail
    assert "stale_reviewer=failed" in detail
    assert "stale_audit=failed" in detail
    assert "delete_rebuild=True/True" in detail
    assert "nested_tamper=failed" in detail
    assert "duplicate=failed" in detail
    assert "redaction=failed" in detail


def test_v72_release_portfolio_governance_attestation_smoke(tmp_path: Path) -> None:
    ok, detail = _v72_release_portfolio_governance_attestation_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "external=passed" in detail
    assert "stale_vault=failed" in detail
    assert "delete_rebuild=True/True" in detail
    assert "cert_tamper=failed" in detail
    assert "report_tamper=failed" in detail
    assert "nested=failed" in detail
    assert "duplicate=failed" in detail
    assert "redaction=failed" in detail


def test_v73_release_portfolio_governance_attestation_registry_smoke(tmp_path: Path) -> None:
    ok, detail = _v73_release_portfolio_governance_attestation_registry_smoke(tmp_path)

    assert ok is True, detail
    assert "verify=passed" in detail
    assert "publish_blocked=True" in detail
    assert "delete_rebuild=True/True/True/True" in detail
    assert "tamper=failed" in detail
    assert "package_type=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "case_musicforge=failed" in detail
    assert "nested=failed" in detail
    assert "spoof=failed/warning" in detail
    assert "redaction=failed" in detail
    assert "no_current=failed" in detail
    assert "report_source=failed" in detail
    assert "package_index=failed" in detail


def test_v74_release_portfolio_governance_attestation_portal_smoke(tmp_path: Path) -> None:
    ok, detail = _v74_release_portfolio_governance_attestation_portal_smoke(tmp_path)

    assert ok is True, detail
    assert "refresh=passed" in detail
    assert "external=passed" in detail
    assert "immutable=True/True/True/True" in detail
    assert "report_source=failed" in detail
    assert "data_summary=failed" in detail
    assert "html_script=failed" in detail
    assert "html_remote=failed" in detail
    assert "duplicate=failed" in detail
    assert "dangerous=failed" in detail
    assert "backslash=failed" in detail
    assert "case_musicforge=failed" in detail
    assert "nested=failed" in detail
    assert "spoof=failed" in detail
    assert "redaction=failed" in detail
    assert "package_type=failed" in detail
    assert "full_resign=failed/failed" in detail
    assert "verification_summary=failed" in detail


def test_v75_release_check_matrix_smoke(tmp_path: Path) -> None:
    ok, detail = _v75_release_check_matrix_smoke(tmp_path)

    assert ok is True, detail
    assert "empty=failed" in detail
    assert "timeout=timed_out" in detail
    assert "warning=passed/1" in detail
    assert "warning_summary=1/1" in detail


def test_v76_attestation_portal_review_response_smoke(tmp_path: Path) -> None:
    ok, detail = _v76_attestation_portal_review_response_smoke(tmp_path)

    assert ok is True, detail
    assert "pack=ready/passed" in detail
    assert "accepted=passed" in detail
    assert "change_request=draft" in detail
    assert "source_path=True" in detail
    assert "bare_json=True" in detail
    assert "response_tamper=failed" in detail
    assert "response_source=failed" in detail
    assert "response_redaction=failed" in detail


def test_v77_attestation_accepted_evidence_smoke(tmp_path: Path) -> None:
    ok, detail = _v77_attestation_accepted_evidence_smoke(tmp_path)

    assert ok is True, detail
    assert "accepted=current/passed" in detail
    assert "registry=passed" in detail
    assert "portal=passed" in detail
    assert "rejected=True" in detail
    assert "stale=True" in detail
    assert "report_source=failed" in detail
    assert "summary=failed" in detail
    assert "redaction=failed" in detail


def test_v78_attestation_transparency_feed_smoke(tmp_path: Path) -> None:
    ok, detail = _v78_attestation_transparency_feed_smoke(tmp_path)

    assert ok is True, detail
    assert "feed=current/passed" in detail
    assert "event=failed" in detail
    assert "event_full_resign=failed" in detail
    assert "notice_full_resign=failed" in detail
    assert "data=failed" in detail
    assert "backslash=failed" in detail
    assert "redaction=failed" in detail
    assert "stale_export=True" in detail
    assert "stale_zip=True" in detail


def test_v79_attestation_transparency_acknowledgement_smoke(tmp_path: Path) -> None:
    ok, detail = _v79_attestation_transparency_acknowledgement_smoke(tmp_path)

    assert ok is True, detail
    assert "pack=ready/passed" in detail
    assert "evidence=current/passed" in detail
    assert "missing_binding=True" in detail
    assert "wrong_source=True" in detail
    assert "change_request=draft" in detail
    assert "full_resign=failed" in detail
    assert "backslash=failed" in detail
    assert "redaction=failed" in detail
    assert "stale_export=True" in detail
    assert "stale_zip=True" in detail


def test_v80_public_trust_center_smoke(tmp_path: Path) -> None:
    ok, detail = _v80_public_trust_center_smoke(tmp_path)

    assert ok is True, detail
    assert "trust=passed/passed" in detail
    assert "report=failed" in detail
    assert "data=failed" in detail
    assert "html=failed" in detail
    assert "backslash=failed" in detail
    assert "redaction=failed" in detail
    assert "stale_export=True" in detail
    assert "stale_zip=True" in detail


def test_v81_public_trust_center_delivery_smoke(tmp_path: Path) -> None:
    ok, detail = _v81_public_trust_center_delivery_smoke(tmp_path)

    assert ok is True, detail
    assert "delivery_full_resign=failed" in detail


def test_print_release_check_report(capsys) -> None:
    report = ReleaseCheckReport()
    report.add("example", True, "detail")

    print_release_check_report(report)

    output = capsys.readouterr().out
    assert "MusicForge release-check" in output
    assert "example: ok" in output
