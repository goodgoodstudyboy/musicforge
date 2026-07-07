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
    assert "v74.attestation_portal_smoke" in ids
    assert "v75.release_check_matrix_smoke" in ids
    assert "v76.attestation_portal_review_response_smoke" in ids
    assert "v77.attestation_accepted_evidence_smoke" in ids
    assert "v78.attestation_transparency_feed_smoke" in ids
    assert "v79.attestation_transparency_acknowledgement_smoke" in ids
    assert "v80.public_trust_center_smoke" in ids
    assert "v90.trust_operations_hub_smoke" in ids
    assert "v91.trust_operations_hub_delivery_runbook_smoke" in ids
    assert "v94.trust_operations_control_catalog_smoke" in ids
    assert "v97.trust_operations_assurance_watch_smoke" in ids
    assert "v98.trust_operations_assurance_watch_signoff_smoke" in ids


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


def test_release_check_cli_group_timing(tmp_path: Path) -> None:
    timing_out = tmp_path / "portal-timing.json"
    completed = _run_cli(["release-check", "--profile", "latest", "--group", "portal", "--list", "--json", "--timing-out", str(timing_out)])

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert {item["check_id"] for item in payload["checks"]} == {
        "v74.attestation_portal_smoke",
        "v76.attestation_portal_review_response_smoke",
        "v77.attestation_accepted_evidence_smoke",
        "v78.attestation_transparency_feed_smoke",
        "v79.attestation_transparency_acknowledgement_smoke",
        "v80.public_trust_center_smoke",
    }


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
        "v120.unified_release_program_board_smoke",
        "v121.unified_release_program_operations_smoke",
        "v122.unified_release_program_final_handoff_smoke",
        "v123.unified_release_program_evidence_vault_smoke",
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
    assert "v75.release_check_matrix_smoke" in ids
    assert "v99.trust_operations_final_readiness_smoke" in ids
    assert "v100.ga_lts_readiness_smoke" in ids


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


def test_release_check_cli_list_allows_empty_selection() -> None:
    completed = _run_cli(["release-check", "--profile", "latest", "--since", "99.0", "--list", "--json"])

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["checks"] == []
