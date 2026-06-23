from __future__ import annotations

from pathlib import Path

from song_agent.release_check_matrix import (
    ReleaseCheckDefinition,
    ReleaseCheckMatrixError,
    all_check_definitions,
    select_check_definitions,
    validate_check_definitions,
)
from song_agent.release_check_runner import run_release_check_matrix


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
    assert by_id["pytest.full"].timeout_seconds >= 6000


def test_release_check_profile_and_filters() -> None:
    latest = select_check_definitions(profile="latest")
    v7 = select_check_definitions(profile="v7")
    v8 = select_check_definitions(profile="v8")
    ga = select_check_definitions(profile="ga", run_tests=False)
    portal = select_check_definitions(profile="latest", groups=["portal"])
    since = select_check_definitions(profile="v7", since="7.2")
    only = select_check_definitions(profile="full", only=["v75.release_check_matrix_smoke"])

    assert "v74.attestation_portal_smoke" in {definition.check_id for definition in latest}
    assert "v75.release_check_matrix_smoke" in {definition.check_id for definition in latest}
    assert "v76.attestation_portal_review_response_smoke" in {definition.check_id for definition in latest}
    assert "v77.attestation_accepted_evidence_smoke" in {definition.check_id for definition in latest}
    assert "v78.attestation_transparency_feed_smoke" in {definition.check_id for definition in latest}
    assert "v79.attestation_transparency_acknowledgement_smoke" in {definition.check_id for definition in latest}
    assert "v80.public_trust_center_smoke" in {definition.check_id for definition in latest}
    assert "v81.public_trust_center_delivery_smoke" in {definition.check_id for definition in latest}
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
    assert "v75.release_check_matrix_smoke" in {definition.check_id for definition in ga}
    assert "v99.trust_operations_final_readiness_smoke" in {definition.check_id for definition in ga}
    assert "v100.ga_lts_readiness_smoke" in {definition.check_id for definition in ga}
    assert {definition.check_id for definition in portal} == {
        "v74.attestation_portal_smoke",
        "v76.attestation_portal_review_response_smoke",
        "v77.attestation_accepted_evidence_smoke",
        "v78.attestation_transparency_feed_smoke",
        "v79.attestation_transparency_acknowledgement_smoke",
        "v80.public_trust_center_smoke",
    }
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


def test_release_check_runner_empty_selection_fails() -> None:
    report = run_release_check_matrix(profile="latest", groups=["audio"])
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
