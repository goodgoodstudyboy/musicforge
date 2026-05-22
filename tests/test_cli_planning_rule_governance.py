from __future__ import annotations

import json
import sys

from song_agent.cli import main
from tests.test_acceptance_fix_plan_reviews import _closed_planned_sprint


def test_planning_rule_governance_cli_promote_active_and_rollback(tmp_path, monkeypatch, capsys) -> None:
    review_store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="synthetic")
    review = review_store.refresh_for_plan(plan_id)

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-ruleset", "create", "--template", "synthetic_strict", "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    ruleset_id = json.loads(capsys.readouterr().out)["ruleset"]["ruleset_id"]

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-simulation", "run", "--ruleset-id", ruleset_id, "--review-id", review.review_id, "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    simulation_id = json.loads(capsys.readouterr().out)["simulation"]["simulation_id"]

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-governance", "promote-request", "--ruleset-id", ruleset_id, "--simulation-id", simulation_id, "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    promotion_id = json.loads(capsys.readouterr().out)["promotion"]["promotion_id"]

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-governance", "approve", promotion_id, "--note", "accepted", "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert json.loads(capsys.readouterr().out)["summary"]["status"] == "approved"

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-governance", "promote", promotion_id, "--promoted-by", "cli", "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    version_id = json.loads(capsys.readouterr().out)["version"]["version_id"]

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-governance", "active"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    active_output = capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-governance", "rollback", "--target-version-id", version_id, "--reason", "cli rollback", "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    rollback = json.loads(capsys.readouterr().out)

    assert f"active_version: {version_id}" in active_output
    assert rollback["summary"]["active_version_id"] == version_id
