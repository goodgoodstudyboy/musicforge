from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "song_agent.cli", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)


def test_release_check_cli_list_json() -> None:
    completed = _run_cli(["release-check", "--profile", "latest", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    ids = {item["check_id"] for item in payload["checks"]}
    assert "v1219.evidence_policy_smoke" in ids
    assert "v1220.release_check_governance_smoke" in ids
    assert "v74.attestation_portal_smoke" not in ids
    assert "v110.unified_command_center_smoke" not in ids


def test_release_check_cli_only_json_report_out(tmp_path: Path) -> None:
    report_out = tmp_path / "release-check.json"
    timing_out = tmp_path / "timing.json"
    completed = _run_cli(
        [
            "release-check",
            "--only",
            "v110.unified_command_center_smoke",
            "--json",
            "--report-out",
            str(report_out),
            "--timing-out",
            str(timing_out),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    written = json.loads(report_out.read_text(encoding="utf-8"))
    timing = json.loads(timing_out.read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 1
    assert written["results"][0]["check_id"] == "v110.unified_command_center_smoke"
    assert timing["results"][0]["check_id"] == "v110.unified_command_center_smoke"
    assert "performance" in payload
    assert "checks_over_budget" in timing


def test_release_check_cli_group_timing(tmp_path: Path) -> None:
    timing_out = tmp_path / "portal-timing.json"
    completed = _run_cli(["release-check", "--profile", "latest", "--group", "portal", "--list", "--json", "--timing-out", str(timing_out)])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["checks"] == []


def test_release_check_cli_v8_profile_lists_public_trust_center() -> None:
    completed = _run_cli(["release-check", "--profile", "v8", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    ids = [item["check_id"] for item in payload["checks"]]
    assert ids[0] == "v80.public_trust_center_smoke"


def test_release_check_cli_v11_profile_lists_unified_command_center() -> None:
    completed = _run_cli(["release-check", "--profile", "v11", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    ids = [item["check_id"] for item in payload["checks"]]
    assert ids == [
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


def test_release_check_cli_v12_profile_lists_unified_release_program() -> None:
    completed = _run_cli(["release-check", "--profile", "v12", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert [item["check_id"] for item in payload["checks"]] == [
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


def test_release_check_cli_v13_profile_lists_cutover_governance() -> None:
    completed = _run_cli(["release-check", "--profile", "v13", "--skip-tests", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert [item["check_id"] for item in payload["checks"]] == [
        "git.diff_check",
        "meta.version_consistency",
        "security.secret_scan",
        "v1214.architecture_guardrails_smoke",
        "v1215.verification_kernel_smoke",
        "v1216.lifecycle_kernel_smoke",
        "v1217.persistence_kernel_smoke",
        "v1218.interface_registry_smoke",
        "v1219.evidence_policy_smoke",
        "v1220.release_check_governance_smoke",
        "v130.lts_cutover_smoke",
        "v1301.shared_kernel_security_smoke",
        "v131.architecture_ratchet_smoke",
        "v132.kernel_adoption_smoke",
        "v133.program_persistence_authority_smoke",
        "v134.program_vertical_slice_smoke",
        "v135.interface_decomposition_smoke",
        "v136.policy_gate_cutover_smoke",
    ]


def test_release_check_cli_v9_profile_lists_trust_operations_hub() -> None:
    completed = _run_cli(["release-check", "--profile", "v9", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert [item["check_id"] for item in payload["checks"]] == [
        "v90.trust_operations_hub_smoke",
        "v91.trust_operations_hub_delivery_runbook_smoke",
        "v92.trust_operations_hub_incident_response_smoke",
        "v93.trust_operations_incident_knowledge_smoke",
        "v94.trust_operations_control_catalog_smoke",
        "v95.trust_operations_control_signoff_smoke",
        "v96.trust_operations_continuous_assurance_smoke",
        "v97.trust_operations_assurance_watch_smoke",
        "v98.trust_operations_assurance_watch_signoff_smoke",
        "v99.trust_operations_final_readiness_smoke",
    ]


def test_release_check_cli_ga_profile_lists_readiness_checks() -> None:
    completed = _run_cli(["release-check", "--profile", "ga", "--skip-tests", "--list", "--json"])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    ids = [item["check_id"] for item in payload["checks"]]
    assert "git.diff_check" in ids
    assert "meta.version_consistency" in ids
    assert "security.secret_scan" in ids
    assert "v1219.evidence_policy_smoke" in ids
    assert "v1220.release_check_governance_smoke" in ids
    assert "v75.release_check_matrix_smoke" not in ids


def test_release_check_cli_empty_selection_fails() -> None:
    completed = _run_cli(["release-check", "--profile", "latest", "--since", "99.0", "--json"])

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["summary"]["total"] == 1
    assert payload["results"][0]["check_id"] == "release_check.selection"


def test_release_check_cli_empty_since_fails() -> None:
    completed = _run_cli(["release-check", "--profile", "v11", "--since", "12.0", "--json"])

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["results"][0]["check_id"] == "release_check.selection"


def test_release_check_cli_security_and_nightly_profiles_are_available() -> None:
    security = _run_cli(["release-check", "--profile", "security", "--list", "--json"])
    nightly = _run_cli(["release-check", "--profile", "nightly", "--list", "--json"])

    assert security.returncode == 0, security.stderr
    assert nightly.returncode == 0, nightly.stderr
    assert any(row["check_id"] == "security.secret_scan" for row in json.loads(security.stdout)["checks"])
    assert any("legacy" in row["tags"] for row in json.loads(nightly.stdout)["checks"])


def test_release_check_cli_list_allows_empty_selection() -> None:
    completed = _run_cli(["release-check", "--profile", "latest", "--since", "99.0", "--list", "--json"])

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["checks"] == []
