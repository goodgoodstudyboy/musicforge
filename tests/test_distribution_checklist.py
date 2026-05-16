from __future__ import annotations

import pytest

from song_agent.distribution import DistributionStateError, DistributionStore
from song_agent.distribution_checklist import (
    checklist_checks,
    checklist_summary,
    initialize_distribution_checklist,
    update_distribution_checklist_item,
)
from song_agent.distribution_templates import TemplatePackStore
from song_agent.releases import ReleaseStore


def test_checklist_init_update_and_summary(tmp_path):
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases")
    release = release_store.create_release({"name": "Checklist Release", "release_type": "demo_pack", "primary_artist": "Artist"})
    distribution = DistributionStore(release_store)
    target = distribution.create_target(release.release_id, {"profile_id": "demo_pitch"})
    template = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates").get_template("tpl-pitch-demo-basic")

    checklist = initialize_distribution_checklist(distribution, release.release_id, target, template)
    failed_checks = checklist_checks(checklist)
    updated = update_distribution_checklist_item(distribution, release.release_id, target, template, "pitch-note-reviewed", {"status": "done", "note": "Checked"})

    assert checklist_summary(checklist)["status"] == "failed"
    assert next(check for check in failed_checks if check["check_id"] == "checklist_required_pending")["status"] == "failed"
    assert checklist_summary(updated)["status"] == "passed"
    assert updated["payload_hash"]


def test_signed_target_blocks_checklist_update(tmp_path):
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases")
    release = release_store.create_release({"name": "Signed Checklist Release", "release_type": "demo_pack", "primary_artist": "Artist"})
    distribution = DistributionStore(release_store)
    target = distribution.create_target(release.release_id, {"profile_id": "demo_pitch"})
    target.latest_signoff_summary = {"status": "signed"}
    target.status = "signed"
    distribution.save_target(target)
    template = TemplatePackStore(tmp_path / ".musicforge" / "distribution-templates").get_template("tpl-pitch-demo-basic")

    with pytest.raises(DistributionStateError):
        initialize_distribution_checklist(distribution, release.release_id, target, template)
