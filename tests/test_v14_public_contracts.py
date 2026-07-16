from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.release_check.v14_contracts import (
    CONTRACT_PATH,
    V138_FINAL_SHA,
    build_v14_contract_document,
    verify_v14_public_contracts,
)
from song_agent.platform.verification.hashing import integrity_hash


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def test_v14_public_contracts_match_v138_baseline() -> None:
    report = verify_v14_public_contracts(ROOT)

    assert report["status"] == "passed", report["blockers"]
    assert report["summary"] == {
        "command_count": 173,
        "route_count": 117,
        "web_control_count": report["summary"]["web_control_count"],
        "web_endpoint_count": report["summary"]["web_endpoint_count"],
    }
    assert report["summary"]["web_control_count"] > 500
    assert report["summary"]["web_endpoint_count"] > 50


def test_v14_public_contract_policy_is_reproducible() -> None:
    tracked = json.loads((ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))

    assert tracked == build_v14_contract_document(ROOT)
    assert tracked["baseline"]["sha"] == V138_FINAL_SHA
    assert tracked["diffs"] == {"api": [], "cli": [], "web": []}


def test_v14_public_contract_verifier_rejects_resigned_break(tmp_path: Path) -> None:
    policy = json.loads((ROOT / CONTRACT_PATH).read_text(encoding="utf-8"))
    policy["baseline"]["contracts"]["api"]["route_contract_hash"] = "f" * 64
    policy["integrity_hash"] = integrity_hash(policy)
    target = tmp_path / CONTRACT_PATH
    target.write_text(json.dumps(policy), encoding="utf-8")

    report = verify_v14_public_contracts(ROOT, policy_path=target)

    assert report["status"] == "failed"
    assert "v14_contract_baseline_api_routes" in report["blockers"]
