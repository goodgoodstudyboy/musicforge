from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

from song_agent.server import create_server
import song_agent.provider_edits as provider_edits_module


def start_test_server():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop_test_server(server):
    server.shutdown()
    server.server_close()


def request_json(server, method, path, payload=None):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    if response.getheader("Content-Type", "").startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8"))
    return response.status, data


def request_bytes(server, method, path, payload=None):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def wait_for_job(server, job_id):
    for _ in range(120):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def request_payload(title="Edit Parent") -> dict[str, object]:
    return {
        "title": title,
        "language": "English",
        "style": "synth pop",
        "theme": "edit api",
    }


def create_project_version(server):
    _status, created = request_json(server, "POST", "/api/projects", {"name": "Edit Project"})
    project_id = created["project"]["project_id"]
    version_status, version_data = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/versions",
        {"request": request_payload(), "name": "Parent"},
    )
    assert version_status == 202
    parent_job = wait_for_job(server, version_data["job"]["job_id"])
    assert parent_job["status"] == "completed"
    return project_id, parent_job


def test_project_edit_api_creates_child_version_and_preserves_parent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, parent_job = create_project_version(server)
        parent_plan_path = Path(parent_job["output_dir"]) / "data" / "song-plan.json"
        parent_before = parent_plan_path.read_bytes()
        edit_status, edit_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "edit_type": "section_energy",
                "target": {"section_name": "chorus"},
                "instruction": "Make chorus stronger.",
                "preserve": ["tempo", "key", "structure"],
                "strength": 8,
                "name": "Chorus lift",
                "note": "local edit",
            },
        )
        edit_job = wait_for_job(server, edit_data["job"]["job_id"])
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}")
        edit_view_status, edit_view = request_json(server, "GET", f"/api/jobs/{edit_job['job_id']}/edit")
        version_edit_status, version_edit = request_json(server, "GET", f"/api/projects/{project_id}/versions/v002/edit")
        diff_status, diff = request_json(server, "GET", f"/api/projects/{project_id}/diff?left=v001&right=v002")
        events_status, events = request_json(server, "GET", f"/api/projects/{project_id}/events")
    finally:
        stop_test_server(server)

    assert edit_status == 202
    assert edit_data["version"]["version_id"] == "v002"
    assert edit_data["version"]["parent_version_id"] == "v001"
    assert edit_data["version"]["variant_type"] == "section_edit"
    assert edit_job["status"] == "completed"
    assert edit_job["job_type"] == "edit"
    assert edit_job["artifacts"]["edit_metadata"].endswith("edit-metadata.json")
    assert (Path(edit_job["output_dir"]) / "data" / "edit-metadata.json").exists()
    assert (Path(edit_job["output_dir"]) / "renders" / "song.mid").read_bytes().startswith(b"MThd")
    assert parent_plan_path.read_bytes() == parent_before
    assert detail_status == 200
    assert detail["project"]["version_count"] == 2
    assert edit_view_status == 200
    assert edit_view["edit"]["edit_type"] == "section_energy"
    assert version_edit_status == 200
    assert version_edit["edit"]["parent_version_id"] == "v001"
    assert diff_status == 200
    assert diff["changed"]["edit"]["right"]["edit_type"] == "section_energy"
    assert diff["changed"]["tracks"]
    assert events_status == 200
    assert any(event["type"] == "version_edit_created" for event in events["events"])


def test_project_edit_targets_and_validation_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, parent_job = create_project_version(server)
        targets_status, targets = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/edit-targets")
        missing_section_status, missing_section = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {"edit_type": "section_energy", "target": {"section_name": "bridge"}},
        )
        provider_status, provider = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {"edit_type": "section_energy", "target": {"section_name": "chorus"}, "provider_mode": "provider"},
        )
        bad_chord_status, bad_chord = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "edit_type": "section_harmony",
                "target": {"section_name": "chorus", "field": "chords"},
                "payload": {"chords": ["Hmaj7", "Cmaj7"]},
            },
        )
        job_edit_status, job_edit = request_json(server, "GET", f"/api/jobs/{parent_job['job_id']}/edit")
    finally:
        stop_test_server(server)

    assert targets_status == 200
    assert {section["name"] for section in targets["sections"]} >= {"verse", "chorus"}
    assert {track["name"] for track in targets["tracks"]} >= {"melody", "drums"}
    assert "lyrics_rewrite" in targets["supported_edit_types"]
    assert missing_section_status == 400
    assert "Section not found" in missing_section["error"]
    assert provider_status == 400
    assert "Provider-backed edit" in provider["error"]
    assert bad_chord_status == 400
    assert "Unsupported chord names: Hmaj7" in bad_chord["error"]
    assert job_edit_status == 404
    assert job_edit["error"] == "Edit metadata not found."


def test_edit_preset_api_and_project_edit_with_preset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        list_status, listed = request_json(server, "GET", "/api/edit-presets")
        create_status, created = request_json(
            server,
            "POST",
            "/api/edit-presets",
            {
                "preset_id": "custom-hook-lift",
                "name": "Custom Hook Lift",
                "description": "Lift hook energy",
                "edit_type": "section_energy",
                "strength": 0.8,
                "target_defaults": {"section_role": "chorus", "section_index": -1},
                "preserve": ["tempo", "key", "structure"],
            },
        )
        read_status, read_back = request_json(server, "GET", "/api/edit-presets/custom-hook-lift")
        project_id, _parent_job = create_project_version(server)
        edit_status, edit_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "preset_id": "custom-hook-lift",
                "intent": {"strength": 7},
                "name": "Preset child",
            },
        )
        edit_job = wait_for_job(server, edit_data["job"]["job_id"])
        metadata_status, metadata = request_json(server, "GET", f"/api/projects/{project_id}/versions/v002/edit")
        delete_status, deleted = request_json(server, "POST", "/api/edit-presets/custom-hook-lift/delete")
        builtin_delete_status, builtin_delete = request_json(server, "POST", "/api/edit-presets/lift-final-chorus/delete")
    finally:
        stop_test_server(server)

    assert list_status == 200
    assert listed["built_in_count"] >= 7
    assert create_status == 201
    assert created["preset"]["preset_id"] == "custom-hook-lift"
    assert read_status == 200
    assert read_back["preset"]["name"] == "Custom Hook Lift"
    assert edit_status == 202
    assert edit_data["edit"]["preset"]["preset_id"] == "custom-hook-lift"
    assert edit_job["status"] == "completed"
    assert metadata_status == 200
    assert metadata["edit"]["preset"]["name"] == "Custom Hook Lift"
    assert metadata["edit"]["strength"] == 7
    assert delete_status == 200
    assert deleted["user_count"] == 0
    assert builtin_delete_status == 409
    assert "Built-in presets cannot be deleted" in builtin_delete["error"]


def test_edit_preset_api_rejects_invalid_harmony_chord(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/edit-presets",
            {
                "preset_id": "bad-harmony",
                "name": "Bad Harmony",
                "edit_type": "section_harmony",
                "payload": {"chords": ["Hmaj7", "Cmaj7"]},
            },
        )
    finally:
        stop_test_server(server)

    assert status == 400
    assert "Unsupported chord names: Hmaj7" in data["error"]


def test_project_edit_with_preset_rejects_unresolved_target_and_bad_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        create_status, _created = request_json(
            server,
            "POST",
            "/api/edit-presets",
            {
                "preset_id": "missing-section",
                "name": "Missing Section",
                "edit_type": "section_energy",
                "target_defaults": {"section_name": "bridge"},
            },
        )
        project_id, _parent_job = create_project_version(server)
        missing_status, missing = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {"preset_id": "missing-section"},
        )
        bad_override_status, bad_override = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "preset_id": "brighter-chorus-harmony",
                "intent": {"payload": {"chords": ["Hmaj7"]}},
            },
        )
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert missing_status == 400
    assert "Section not found" in missing["error"]
    assert bad_override_status == 400
    assert "Unsupported chord names: Hmaj7" in bad_override["error"]


def test_project_edit_requires_completed_parent_and_existing_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Queued Edit Project"})
        project_id = created["project"]["project_id"]
        job = server.job_store.create_job(request_payload("Queued Parent"), start_immediately=False)
        request_json(server, "POST", f"/api/projects/{project_id}/versions/from-job", {"job_id": job.job_id})
        queued_status, queued = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {"edit_type": "section_energy", "target": {"section_name": "chorus"}},
        )
        server.job_store._update_job(job, status="completed", step="completed")
        missing_plan_status, missing_plan = request_json(
            server,
            "GET",
            f"/api/projects/{project_id}/versions/v001/edit-targets",
        )
    finally:
        stop_test_server(server)

    assert queued_status == 409
    assert queued["error"] == "Parent version must be completed before editing."
    assert missing_plan_status == 409
    assert missing_plan["error"] == "song-plan.json is not available for this version."


def test_cancelled_edit_job_does_not_start(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        status, data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "edit_type": "lyrics_rewrite",
                "target": {"section_name": "verse", "field": "lyrics"},
                "payload": {"lyrics": "edited line"},
                "start_immediately": False,
            },
        )
        job_id = data["job"]["job_id"]
        cancel_status, _cancel = request_json(server, "POST", f"/api/jobs/{job_id}/cancel")
        started = server.job_store.start_job(job_id)
        final_status, final = request_json(server, "GET", f"/api/jobs/{job_id}")
    finally:
        stop_test_server(server)

    assert status == 202
    assert cancel_status == 200
    assert started is False
    assert final_status == 200
    assert final["status"] == "cancelled"
    assert not (Path(final["output_dir"]) / "data" / "song-plan.json").exists()


def test_provider_edit_preview_and_apply_create_child_version_with_usage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main", "api_key": "sk-provider-secret"})
        project_id, parent_job = create_project_version(server)
        parent_plan_path = Path(parent_job["output_dir"]) / "data" / "song-plan.json"
        parent_before = parent_plan_path.read_bytes()
        preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview",
            {
                "instruction": "Make the final chorus more energetic but keep lyrics.",
                "template_id": "provider-edit-intent",
            },
        )
        detail_after_preview_status, detail_after_preview = request_json(server, "GET", f"/api/projects/{project_id}")
        preview_id = preview_data["preview"]["preview_id"]
        apply_status, applied = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview/{preview_id}/apply",
            {"name": "Provider edit child"},
        )
        edit_job = wait_for_job(server, applied["job"]["job_id"])
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right=v002")
        usage_status, usage = request_json(server, "GET", f"/api/jobs/{edit_job['job_id']}/provider-usage")
        project_usage_status, project_usage = request_json(server, "GET", f"/api/projects/{project_id}/provider-usage")
        metadata_status, metadata = request_json(server, "GET", f"/api/projects/{project_id}/versions/v002/edit")
    finally:
        stop_test_server(server)

    assert preview_status == 201
    assert preview_data["preview"]["status"] == "ready"
    assert detail_after_preview_status == 200
    assert len(detail_after_preview["versions"]) == 1
    assert apply_status == 202
    assert edit_job["status"] == "completed"
    assert applied["version"]["variant_type"] == "provider_edit"
    assert parent_plan_path.read_bytes() == parent_before
    assert compare_status == 200
    assert compare["right"]["edit"]["provider_mode"] == "provider"
    assert usage_status == 200
    assert usage["usage"]["operation"] == "provider_edit_apply"
    assert project_usage_status == 200
    assert project_usage["total_calls"] == 1
    assert metadata_status == 200
    serialized = json.dumps({"job": edit_job, "usage": usage, "metadata": metadata})
    assert "sk-provider-secret" not in serialized


def test_provider_edit_preview_delete_does_not_delete_versions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        project_id, _parent_job = create_project_version(server)
        _preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview",
            {"instruction": "Make chorus brighter.", "template_id": "provider-edit-intent"},
        )
        preview_id = preview_data["preview"]["preview_id"]
        delete_status, deleted = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview/{preview_id}/delete",
        )
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}")
    finally:
        stop_test_server(server)

    assert delete_status == 200
    assert deleted["deleted"] is True
    assert detail_status == 200
    assert len(detail["versions"]) == 1


def test_provider_edit_apply_reuses_preview_usage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original_generate = provider_edits_module.generate_provider_edit_patch

    def fake_generate(**kwargs):
        patch, snapshot = original_generate(**kwargs)
        snapshot["usage"] = {"prompt_tokens": 13, "completion_tokens": 5, "total_tokens": 18}
        snapshot["request_id"] = "req-preview-1"
        return patch, snapshot

    monkeypatch.setattr("song_agent.server.generate_provider_edit_patch", fake_generate)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        project_id, _parent_job = create_project_version(server)
        preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview",
            {"instruction": "Make the final chorus more energetic.", "template_id": "provider-edit-intent"},
        )
        preview_id = preview_data["preview"]["preview_id"]
        apply_status, applied = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview/{preview_id}/apply",
            {"name": "Provider usage child"},
        )
        edit_job = wait_for_job(server, applied["job"]["job_id"])
        usage_status, usage = request_json(server, "GET", f"/api/jobs/{edit_job['job_id']}/provider-usage")
    finally:
        stop_test_server(server)

    assert preview_status == 201
    assert preview_data["preview"]["provider_usage"]["total_tokens"] == 18
    assert preview_data["preview"]["provider_request_id"] == "req-preview-1"
    assert apply_status == 202
    assert usage_status == 200
    assert usage["usage"]["prompt_tokens"] == 13
    assert usage["usage"]["completion_tokens"] == 5
    assert usage["usage"]["total_tokens"] == 18
    assert usage["usage"]["request_id"] == "req-preview-1"


def test_provider_edit_preview_rejects_stale_and_duplicate_apply(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        project_id, parent_job = create_project_version(server)
        preview_status, preview_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview",
            {"instruction": "Make the final chorus more energetic.", "template_id": "provider-edit-intent"},
        )
        stale_preview_id = preview_data["preview"]["preview_id"]
        parent_plan_path = Path(parent_job["output_dir"]) / "data" / "song-plan.json"
        parent_plan = json.loads(parent_plan_path.read_text(encoding="utf-8"))
        parent_plan["tempo_bpm"] = int(parent_plan["tempo_bpm"]) + 1
        parent_plan_path.write_text(json.dumps(parent_plan), encoding="utf-8")
        stale_status, stale = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview/{stale_preview_id}/apply",
            {"name": "stale child"},
        )
        detail_after_stale_status, detail_after_stale = request_json(server, "GET", f"/api/projects/{project_id}")
        parent_plan["tempo_bpm"] = int(parent_plan["tempo_bpm"]) - 1
        parent_plan_path.write_text(json.dumps(parent_plan), encoding="utf-8")
        _fresh_status, fresh_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview",
            {"instruction": "Make the final chorus more energetic.", "template_id": "provider-edit-intent"},
        )
        fresh_preview_id = fresh_data["preview"]["preview_id"]
        first_apply_status, first_apply = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview/{fresh_preview_id}/apply",
            {"name": "fresh child"},
        )
        wait_for_job(server, first_apply["job"]["job_id"])
        duplicate_status, duplicate = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-preview/{fresh_preview_id}/apply",
            {"name": "duplicate child"},
        )
        final_detail_status, final_detail = request_json(server, "GET", f"/api/projects/{project_id}")
    finally:
        stop_test_server(server)

    assert preview_status == 201
    assert stale_status == 409
    assert "stale" in stale["error"]
    assert detail_after_stale_status == 200
    assert len(detail_after_stale["versions"]) == 1
    assert first_apply_status == 202
    assert duplicate_status == 409
    assert duplicate["error"] == "Provider edit preview has already been applied."
    assert final_detail_status == 200
    assert len(final_detail["versions"]) == 2


def test_provider_edit_candidates_create_rank_and_apply_best(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main", "api_key": "sk-provider-secret"})
        project_id, _parent_job = create_project_version(server)
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates",
            {
                "instruction": "Give me 3 stronger chorus options.",
                "candidate_count": 3,
                "template_id": "provider-edit-candidates",
            },
        )
        group_id = created["group"]["group_id"]
        candidate_id = created["group"]["ranking"][0]["candidate_id"]
        midi_status, midi_bytes = request_bytes(
            server,
            "GET",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/midi",
        )
        rerender_status, rerendered = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/render-midi",
        )
        audio_status, audio_error = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/render-audio",
        )
        list_status, listed = request_json(server, "GET", f"/api/projects/{project_id}/candidate-groups")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/candidate-groups/{group_id}")
        apply_status, applied = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/apply",
            {"name": "Best candidate"},
        )
        edit_job = wait_for_job(server, applied["job"]["job_id"])
        duplicate_status, duplicate = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/apply",
            {"name": "Duplicate candidate"},
        )
        usage_status, usage = request_json(server, "GET", f"/api/projects/{project_id}/provider-usage")
        report_status, report = request_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        group_usage_status, group_usage = request_json(server, "GET", f"/api/projects/{project_id}/candidate-groups/{group_id}/usage")
        global_usage_status, global_usage = request_json(server, "GET", "/api/usage/provider")
        project_status, project = request_json(server, "GET", f"/api/projects/{project_id}")
        metadata_status, metadata = request_json(server, "GET", f"/api/projects/{project_id}/versions/v002/edit")
        delete_status, _deleted = request_json(server, "POST", f"/api/projects/{project_id}/candidate-groups/{group_id}/delete")
        metadata_after_delete_status, metadata_after_delete = request_json(server, "GET", f"/api/projects/{project_id}/versions/v002/edit")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert created["group"]["status"] == "ready"
    assert len(created["group"]["candidates"]) == 3
    assert len(created["group"]["ranking"]) == 3
    assert created["group"]["candidates"][0]["midi_status"] == "completed"
    assert created["group"]["candidates"][0]["midi_url"].endswith("/midi")
    assert midi_status == 200
    assert midi_bytes.startswith(b"MThd")
    assert rerender_status == 200
    assert rerendered["candidate"]["midi_status"] == "completed"
    assert audio_status == 400
    assert "soundfont_path is required" in audio_error["error"]
    assert list_status == 200
    assert listed["groups"][0]["group_id"] == group_id
    assert detail_status == 200
    assert detail["group"]["ranking"][0]["candidate_id"]
    assert apply_status == 202
    assert applied["group"]["status"] == "applied"
    assert applied["version"]["parent_version_id"] == "v001"
    assert edit_job["status"] == "completed"
    assert duplicate_status == 409
    assert "already been applied" in duplicate["error"]
    assert usage_status == 200
    assert usage["total_calls"] >= 2
    assert report_status == 200
    assert report["scope"] == "project"
    assert report["total_calls"] >= 2
    assert report["total_tokens"] >= 0
    assert report["estimated_cost"] is None
    assert report["by_operation"]
    assert any(item["operation"] == "provider_edit_candidates" for item in report["by_operation"])
    assert not any("api_key" in record for record in report["records"])
    assert group_usage_status == 200
    assert group_usage["scope"] == "candidate_group"
    assert group_usage["candidate_group_records"][0]["group_id"] == group_id
    assert global_usage_status == 200
    assert global_usage["scope"] == "global"
    assert metadata_status == 200
    assert metadata["edit"]["candidate_group_id"] == group_id
    assert metadata["edit"]["candidate_id"] == applied["group"]["selected_candidate_id"]
    assert metadata["edit"]["candidate"]["candidate_group_id"] == group_id
    assert metadata["edit"]["candidate"]["candidate_id"] == applied["group"]["selected_candidate_id"]
    assert metadata["edit"]["candidate"]["rank"] == 1
    assert metadata["edit"]["candidate"]["score"] is not None
    assert metadata["edit"]["candidate"]["summary"]
    assert metadata["edit"]["preview_id"] == group_id
    assert delete_status == 200
    assert metadata_after_delete_status == 200
    assert metadata_after_delete["edit"]["candidate_group_id"] == group_id
    assert metadata_after_delete["edit"]["candidate_id"] == applied["group"]["selected_candidate_id"]
    assert metadata_after_delete["edit"]["candidate"]["rank"] == 1
    assert metadata_after_delete["edit"]["candidate"]["score"] is not None
    serialized = json.dumps({"created": created, "applied": applied, "usage": usage})
    assert "sk-provider-secret" not in serialized
    assert project_status == 200
    assert len(project["versions"]) == 2


def test_provider_usage_report_pricing_and_prompt_ab(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main", "api_key": "sk-provider-secret"})
        project_id, _parent_job = create_project_version(server)
        ab_status, ab_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates/ab",
            {
                "instruction": "Compare two prompt treatments for the chorus.",
                "candidate_count": 2,
                "template_ids": ["provider-edit-candidates", "provider-edit-candidates"],
            },
        )
        ab_id = ab_data["experiment"]["ab_id"]
        group_ids = ab_data["experiment"]["group_ids"]
        list_status, listed = request_json(server, "GET", f"/api/projects/{project_id}/prompt-ab")
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/prompt-ab/{ab_id}")
        no_price_status, no_price = request_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        pricing_path = tmp_path / ".musicforge" / "provider-pricing.json"
        pricing_path.parent.mkdir(parents=True, exist_ok=True)
        pricing_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "models": {
                        "mock-main": {
                            "input_per_1m": 1.0,
                            "output_per_1m": 2.0,
                            "currency": "USD",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        priced_status, priced = request_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        delete_status, deleted = request_json(server, "POST", f"/api/projects/{project_id}/prompt-ab/{ab_id}/delete")
        missing_status, missing = request_json(server, "GET", f"/api/projects/{project_id}/prompt-ab/{ab_id}")
    finally:
        stop_test_server(server)

    assert ab_status == 201
    assert len(group_ids) == 2
    assert len(ab_data["groups"]) == 2
    assert all(group["ranking"] for group in ab_data["groups"])
    assert list_status == 200
    assert listed["experiments"][0]["ab_id"] == ab_id
    assert detail_status == 200
    assert [group["group_id"] for group in detail["groups"]] == group_ids
    assert no_price_status == 200
    assert no_price["total_calls"] >= 2
    assert no_price["estimated_cost"] is None
    assert priced_status == 200
    assert priced["estimated_cost"] is not None
    assert priced["currency"] == "USD"
    assert delete_status == 200
    assert deleted["deleted"] is True
    assert missing_status == 404
    assert missing["error"] == "Prompt A/B experiment not found."
    serialized = json.dumps({"ab": ab_data, "priced": priced})
    assert "sk-provider-secret" not in serialized


def test_provider_edit_candidates_reject_stale_parent_and_delete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        project_id, parent_job = create_project_version(server)
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates",
            {"instruction": "Give me 2 chorus options.", "candidate_count": 2},
        )
        group_id = created["group"]["group_id"]
        parent_plan_path = Path(parent_job["output_dir"]) / "data" / "song-plan.json"
        parent_plan = json.loads(parent_plan_path.read_text(encoding="utf-8"))
        parent_plan["tempo_bpm"] = int(parent_plan["tempo_bpm"]) + 1
        parent_plan_path.write_text(json.dumps(parent_plan), encoding="utf-8")
        stale_status, stale = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/apply",
            {"candidate_id": created["group"]["ranking"][0]["candidate_id"]},
        )
        candidate_id = created["group"]["ranking"][0]["candidate_id"]
        midi_status, midi = request_json(
            server,
            "GET",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/midi",
        )
        rerender_status, rerender = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/render-midi",
        )
        group_render_status, group_render = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/render-midi",
        )
        audio_status, audio = request_json(
            server,
            "GET",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/audio",
        )
        audio_render_status, audio_render = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/candidates/{candidate_id}/render-audio",
        )
        delete_status, deleted = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/candidate-groups/{group_id}/delete",
        )
        missing_status, missing = request_json(server, "GET", f"/api/projects/{project_id}/candidate-groups/{group_id}")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert stale_status == 409
    assert "stale" in stale["error"]
    assert midi_status == 409
    assert "stale" in midi["error"]
    assert rerender_status == 409
    assert "stale" in rerender["error"]
    assert group_render_status == 409
    assert "stale" in group_render["error"]
    assert audio_status == 409
    assert "stale" in audio["error"]
    assert audio_render_status == 409
    assert "stale" in audio_render["error"]
    assert delete_status == 200
    assert deleted["deleted"] is True
    assert missing_status == 404
    assert missing["error"] == "Candidate group not found."


def test_prompt_ab_rolls_back_created_groups_when_later_template_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        project_id, _parent_job = create_project_version(server)
        ab_status, ab_error = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates/ab",
            {
                "instruction": "Compare one good and one bad template.",
                "candidate_count": 2,
                "template_ids": ["provider-edit-candidates", "missing-template"],
            },
        )
        groups_status, groups = request_json(server, "GET", f"/api/projects/{project_id}/candidate-groups")
        usage_status, usage = request_json(server, "GET", f"/api/projects/{project_id}/usage/provider")
        ab_list_status, ab_list = request_json(server, "GET", f"/api/projects/{project_id}/prompt-ab")
        events_status, events = request_json(server, "GET", f"/api/projects/{project_id}/events")
    finally:
        stop_test_server(server)

    assert ab_status == 404
    assert ab_error["error"] == "Provider edit resource not found."
    assert groups_status == 200
    assert groups["groups"] == []
    assert usage_status == 200
    assert usage["total_calls"] == 0
    assert ab_list_status == 200
    assert ab_list["experiments"] == []
    assert events_status == 200
    assert any(event["type"] == "provider_prompt_ab_rolled_back" for event in events["events"])
