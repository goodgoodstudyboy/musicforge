from __future__ import annotations

import base64
from pathlib import Path

from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_releases import _signed_project


def test_distribution_api_end_to_end_and_signed_mutation_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _signed_release(server)
        profiles_status, profiles = request_json(server, "GET", "/api/distribution/profiles")
        templates_status, templates = request_json(server, "GET", "/api/distribution/template-packs")
        template_status, template_created = request_json(
            server,
            "POST",
            "/api/distribution/template-packs",
            {
                "slug": "server-template-basic",
                "name": "Server Template Basic",
                "rules": {"require_artwork": True, "require_upc": True, "require_isrc": True, "csv_formula_escape": True},
                "metadata_mapping": {"platform_csv": [{"column": "Title", "source": "track.title", "required": True}]},
                "file_naming": {"artwork": "cover.{ext}", "audio": "{track_number:02d}-{slug_title}.wav"},
                "checklist": [{"item_id": "explicit-confirmed", "label": "Explicit checked", "required": True}],
            },
        )
        template_id = template_created["template"]["template_pack_id"]
        clone_status, cloned = request_json(server, "POST", "/api/distribution/template-packs/tpl-generic-dsp-basic/clone", {"slug": "server-generic-copy"})
        validate_status, validated = request_json(server, "POST", f"/api/distribution/template-packs/{template_id}/validate", {"template": template_created["template"]})
        export_template_status, exported_template = request_json(server, "GET", f"/api/distribution/template-packs/{template_id}/export")
        import_blocked_status, import_blocked = request_json(server, "POST", "/api/distribution/template-packs/import", {"source_path": str(tmp_path / "template.json"), "template": exported_template["template"]})
        import_status, imported = request_json(server, "POST", "/api/distribution/template-packs/import?rename=true", {"template": exported_template["template"]})
        target_status, target_data = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "template_pack_id": template_id, "name": "Pitch"})
        target_id = target_data["target"]["target_id"]
        local_cover = tmp_path / "server-cover.png"
        local_cover.write_bytes(_png(1400, 1400))
        blocked_source_status, blocked_source = request_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "source_path": str(local_cover)})
        artwork_list_status, artwork_list = request_json(server, "GET", f"/api/releases/{release_id}/distribution/artwork")
        artwork_status, artwork = request_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
        update_status, _updated = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork["artwork"]["artwork_id"]}})
        checklist_status, checklist = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist")
        qa_failed_status, qa_failed = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        checklist_update_status, checklist_updated = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist/items/explicit-confirmed", {"status": "done", "note": "Checked"})
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "server-test"})
        qa_path = Path(".musicforge") / "releases" / release_id / "distribution" / "qa" / f"{target_id}-qa.json"
        qa_before_repeat_signoff = qa_path.read_bytes()
        repeat_sign_status, repeat_signoff = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "server-test"})
        qa_after_repeat_signoff = qa_path.read_bytes()
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/verify", {"require_artwork": True})
        blocked_export_status, blocked_export = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        blocked_qa_status, blocked_qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        blocked_checklist_status, blocked_checklist = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/checklist/items/explicit-confirmed", {"status": "blocked"})
        blocked_template_status, blocked_template = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"template_pack_id": imported["template"]["template_pack_id"]})
        blocked_global_template_update_status, blocked_global_template_update = request_json(server, "POST", f"/api/distribution/template-packs/{template_id}", {"name": "Changed After Signoff"})
        blocked_global_template_delete_status, blocked_global_template_delete = request_json(server, "POST", f"/api/distribution/template-packs/{template_id}/delete")
        zip_download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}/export.zip")
        reset_status, reset = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff/reset", {"reason": "rebuild distribution"})
        export_after_reset_status, _after = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
    finally:
        stop_test_server(server)

    assert profiles_status == 200
    assert any(item["profile_id"] == "demo_pitch" for item in profiles["profiles"])
    assert templates_status == 200
    assert any(item["slug"] == "generic-dsp-basic" for item in templates["template_packs"])
    assert template_status == 201
    assert clone_status == 201
    assert cloned["template"]["source"] == "user"
    assert validate_status == 200
    assert validated["validation"]["status"] == "passed"
    assert export_template_status == 200
    assert import_blocked_status == 400
    assert "source_path" in import_blocked["error"]
    assert import_status == 201
    assert imported["template"]["content_hash"] == template_created["template"]["content_hash"]
    assert target_status == 201
    assert target_data["target"]["template_pack_id"] == template_id
    assert blocked_source_status == 400
    assert "source_path" in blocked_source["error"]
    assert artwork_list_status == 200
    assert artwork_list["artwork"] == []
    assert artwork_status == 201
    assert update_status == 200
    assert checklist_status == 200
    assert checklist["summary"]["status"] == "failed"
    assert qa_failed_status == 200
    assert qa_failed["summary"]["status"] == "failed"
    assert checklist_update_status == 200
    assert checklist_updated["summary"]["status"] == "passed"
    assert qa_status == 200
    assert qa["summary"]["status"] in {"passed", "warning"}
    assert export_status == 201
    assert exported["summary"]["status"] == "exported"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert sign_status == 200
    assert signed["summary"]["status"] == "signed"
    assert repeat_sign_status == 409
    assert "signed" in repeat_signoff["error"].lower()
    assert qa_after_repeat_signoff == qa_before_repeat_signoff
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert blocked_export_status == 409
    assert blocked_qa_status == 409
    assert blocked_checklist_status == 409
    assert blocked_template_status == 409
    assert blocked_global_template_update_status == 409
    assert blocked_global_template_delete_status == 409
    assert "signed" in blocked_export["error"].lower()
    assert "signed" in blocked_qa["error"].lower()
    assert "signed" in blocked_checklist["error"].lower()
    assert "signed" in blocked_template["error"].lower()
    assert "signed" in blocked_global_template_update["error"].lower()
    assert "signed" in blocked_global_template_delete["error"].lower()
    assert zip_download_status == 200
    assert zip_bytes.startswith(b"PK")
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
    assert export_after_reset_status == 201


def test_distribution_template_update_stales_unsigned_targets(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _signed_release(server)
        template_status, template_created = request_json(
            server,
            "POST",
            "/api/distribution/template-packs",
            {
                "slug": "server-template-stale",
                "name": "Server Template Stale",
                "rules": {"require_upc": True, "require_isrc": True},
                "metadata_mapping": {"platform_csv": [{"column": "Title", "source": "track.title", "required": True}]},
                "file_naming": {"audio": "{track_number:02d}-{slug_title}.wav"},
            },
        )
        template_id = template_created["template"]["template_pack_id"]
        target_status, target_data = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "generic_dsp", "template_pack_id": template_id, "name": "Unsigned Target"})
        target_id = target_data["target"]["target_id"]
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        update_template_status, updated_template = request_json(server, "POST", f"/api/distribution/template-packs/{template_id}", {"name": "Server Template Stale Updated"})
        get_target_status, current_target = request_json(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}")
        delete_template_status, deleted_template = request_json(server, "POST", f"/api/distribution/template-packs/{template_id}/delete")
        get_after_delete_status, target_after_delete = request_json(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}")
    finally:
        stop_test_server(server)

    assert template_status == 201
    assert target_status == 201
    assert qa_status == 200
    assert qa["summary"]["status"] in {"passed", "warning", "failed"}
    assert update_template_status == 200
    assert updated_template["stale_targets"][0]["target_id"] == target_id
    assert get_target_status == 200
    assert current_target["target"]["latest_qa_summary"]["status"] == "stale"
    assert current_target["target"]["latest_qa_summary"]["stale_reason"] == "template_updated"
    assert delete_template_status == 200
    assert deleted_template["stale_targets"][0]["target_id"] == target_id
    assert get_after_delete_status == 200
    assert target_after_delete["target"]["latest_qa_summary"]["status"] == "stale"
    assert target_after_delete["target"]["latest_qa_summary"]["stale_reason"] == "template_deleted"


def _signed_release(server) -> str:
    project_id = _signed_project(server, "Distribution API Song")
    created_status, created = request_json(server, "POST", "/api/releases", {"name": "Distribution API Pack", "release_type": "demo_pack", "primary_artist": "MusicForge"})
    release_id = created["release"]["release_id"]
    add_status, _added = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
    init_status, initialized = request_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
    metadata = initialized["metadata"]
    metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
    metadata["tracks"][0].update({"isrc": "USABC2600001", "lyrics": "Clean lyric", "credits": [{"role": "composer", "name": "Writer"}], "confirmed": True})
    save_status, _saved = request_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
    metadata_qa_status, _metadata_qa = request_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
    qa_status, _qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
    export_status, _export = request_json(server, "POST", f"/api/releases/{release_id}/export")
    metadata_export_status, _metadata_export = request_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
    sign_status, _signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-test"})
    assert created_status == 201
    assert add_status == 200
    assert init_status == 200
    assert save_status == 200
    assert metadata_qa_status == 200
    assert qa_status == 200
    assert export_status == 200
    assert metadata_export_status == 200
    assert sign_status == 200
    return release_id


def _png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" + b"\x00" * 16
