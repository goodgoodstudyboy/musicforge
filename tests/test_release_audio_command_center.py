from __future__ import annotations

from pathlib import Path

from tests.helpers_release_audio_command_center import append_untrusted_entry, command_center_fixture


def _component(inventory: dict, key: str) -> dict:
    for row in inventory.get("components", []):
        if row.get("component_key") == key:
            return row
    raise AssertionError(f"missing component {key}")


def _gap(gap_plan: dict, key: str) -> dict:
    for row in gap_plan.get("gaps", []):
        if row.get("component_key") == key:
            return row
    raise AssertionError(f"missing gap {key}")


def test_command_center_refresh_records_runtime_status_and_gap_priority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with command_center_fixture() as fixture:
        report = fixture.store.refresh(fixture.release_id, fixture.evidence)
        assert report["status"] == "passed"
        inventory = fixture.store.read_inventory(fixture.release_id)
        action_queue = _component(inventory, "action_queue")
        assert action_queue["status"] == "ready"
        assert action_queue["readiness"] == "ready"
        assert action_queue["fingerprint"]["runtime_verification_status"] == "passed"
        assert action_queue["runtime_summary"]["status"] == "passed"

        append_untrusted_entry(fixture.evidence["action_queue"]["zip"])

        failed = fixture.store.refresh(fixture.release_id, fixture.evidence)
        assert failed["status"] == "failed"
        inventory = fixture.store.read_inventory(fixture.release_id)
        action_queue = _component(inventory, "action_queue")
        assert action_queue["status"] == "blocked"
        assert action_queue["readiness"] in {"stale", "runtime_failed"}
        assert action_queue["fingerprint"]["runtime_verification_status"] == "failed"
        assert action_queue["fingerprint"]["runtime_blockers"]

        gap_plan = fixture.store._ensure_docs(fixture.release_id, fixture.evidence)["gap_plan"]  # noqa: SLF001
        action_gap = _gap(gap_plan, "action_queue")
        assert action_gap["readiness"] in {"stale", "runtime_failed"}
        assert action_gap["priority"] in {10, 20}


def test_command_center_verifier_rejects_tampered_runtime_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with command_center_fixture() as fixture:
        fixture.store.refresh(fixture.release_id, fixture.evidence)
        zipped = fixture.store.build_zip(fixture.release_id, fixture.evidence)
        baseline = fixture.store.verify_zip(fixture.release_id, evidence=fixture.evidence, strict=True, require_ready=True)
        assert baseline["status"] == "passed"

        append_untrusted_entry(fixture.evidence["action_queue"]["zip"])

        failed = fixture.store.verify_zip(fixture.release_id, evidence=fixture.evidence, strict=True, require_ready=True)
        assert failed["status"] == "failed"
        assert "release_audio_command_center_action_queue_runtime_status" in failed["blockers"]
        assert Path(zipped["zip_path"]).exists()
