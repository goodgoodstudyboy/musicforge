from __future__ import annotations

import json
from pathlib import Path

from tests.test_server_editor_audition import _create_preview
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server, wait_for_job


def _review_task_source(server):
    project_id, preview_id = _create_preview(server)
    create_status, created = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions",
        {
            "source": "preview",
            "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0},
            "track_mode": "solo",
            "track_ids": ["track-003"],
        },
    )
    assert create_status == 201
    audition_id = created["audition"]["audition_id"]
    review_status, _review = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review",
        {
            "rating": 4,
            "status": "needs_fix",
            "favorite": True,
            "notes": r"bass 太满, chorus 更强 api_key=sk-secret-value C:\Users\demo\song.wav",
            "tags": ["review"],
        },
    )
    assert review_status == 200
    keep_status, _keep = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
        {"beat": 0, "kind": "keep", "label": "keep hook"},
    )
    assert keep_status == 201
    fix_status, _fix = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers",
        {"beat": 1, "kind": "fix", "label": "fix bass"},
    )
    assert fix_status == 201
    return project_id, preview_id, audition_id


def _create_review_task(server):
    project_id, preview_id, audition_id = _review_task_source(server)
    task_status, task_data = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-task",
        {},
    )
    assert task_status == 201
    return project_id, preview_id, audition_id, task_data["task"]["task_id"], task_data


def test_review_task_create_generate_candidates_apply_and_follow_up(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _preview_id, audition_id, task_id, task_data = _create_review_task(server)
        list_status, listed = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks")
        candidates_status, candidates = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-tasks/{task_id}/candidates",
            {"render_midi": True},
        )
        candidate_id = candidates["candidates"][0]["candidate_id"]
        midi_status, midi = request_bytes(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/midi")
        audio_status, audio = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/render-audio")
        apply_status, applied = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/apply",
            {"version_name": "Review Candidate Child", "version_note": "review task"},
        )
        job = wait_for_job(server, applied["job"]["job_id"])
        duplicate_status, duplicate = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/apply", {})
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}")
        compare_status, compare = request_json(server, "GET", f"/api/projects/{project_id}/compare?left=v001&right={applied['version']['version_id']}")
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        needs_status, needs = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/needs-more-work", {"note": "still too dense"})
        old_generate_status, old_generate = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates", {})
        second_candidate_id = next(candidate["candidate_id"] for candidate in candidates["candidates"] if candidate["candidate_id"] != candidate_id)
        old_apply_status, old_apply = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{second_candidate_id}/apply", {})
        follow_up_id = needs["follow_up_task"]["task_id"]
        follow_status, follow = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{follow_up_id}")
        metadata = json.loads((Path(job["output_dir"]) / "data" / "edit-metadata.json").read_text(encoding="utf-8"))
        serialized = json.dumps({"task": task_data, "project_export": project_export, "metadata": metadata}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert task_data["task"]["target"]["marker_kind"] == "fix"
    assert task_data["task"]["target"]["section_name"] == "verse"
    assert task_data["task"]["target"]["global_marker_beat"] == 17.0
    assert list_status == 200
    assert listed["summary"]["total"] == 1
    assert candidates_status == 201
    assert len(candidates["candidates"]) >= 2
    assert candidates["task"]["status"] == "candidate_ready"
    assert midi_status == 200
    assert midi.startswith(b"MThd")
    assert audio_status == 400
    assert "soundfont_path is required" in audio["error"]
    assert apply_status == 202
    assert applied["task"]["status"] == "applied"
    assert applied["version"]["parent_version_id"] == "v001"
    assert job["status"] == "completed"
    assert duplicate_status == 409
    assert "already applied" in duplicate["error"]
    assert detail_status == 200
    assert detail["task"]["selected_candidate_id"] == candidate_id
    assert compare_status == 200
    assert compare["right"]["edit"]["review_task"]["task_id"] == task_id
    assert export_status == 200
    assert project_export["review_tasks"][0]["task_id"] == task_id
    assert project_export["versions"][1]["edit"]["review_task"]["task_id"] == task_id
    assert metadata["edit_source"] == "review_task_candidate"
    assert metadata["review_task"]["audition_id"] == audition_id
    assert needs_status == 201
    assert needs["task"]["status"] == "needs_more_work"
    assert needs["follow_up_task"]["parent_version_id"] == applied["version"]["version_id"]
    assert old_generate_status == 409
    assert "needs_more_work" in old_generate["error"]
    assert old_apply_status == 409
    assert "needs_more_work" in old_apply["error"]
    assert follow_status == 200
    assert follow["task"]["source"]["previous_task_id"] == task_id
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_review_task_artifact_path_pollution_returns_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _preview_id, _audition_id, task_id, _task_data = _create_review_task(server)
        candidates_status, candidates = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates", {})
        candidate_id = candidates["candidates"][0]["candidate_id"]
        candidate_path = Path(".musicforge") / "projects" / project_id / "review-tasks" / task_id / "candidates" / candidate_id / "candidate.json"
        data = json.loads(candidate_path.read_text(encoding="utf-8"))
        data["artifacts"]["midi_path"] = f"review-tasks/{task_id}/candidates/revcand-999/renders/song.mid"
        candidate_path.write_text(json.dumps(data), encoding="utf-8")
        midi_status, midi = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/midi")
    finally:
        stop_test_server(server)

    assert candidates_status == 201
    assert midi_status == 409
    assert "unsafe" in midi["error"]


def test_review_task_stale_parent_rejects_candidate_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _preview_id, _audition_id, task_id, _task_data = _create_review_task(server)
        _candidates_status, candidates = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates", {})
        candidate_id = candidates["candidates"][0]["candidate_id"]
        project_status, project = request_json(server, "GET", f"/api/projects/{project_id}")
        parent_path = Path(project["versions"][0]["output_dir"]) / "data" / "song-plan.json"
        parent = json.loads(parent_path.read_text(encoding="utf-8"))
        parent["tempo_bpm"] += 1
        parent_path.write_text(json.dumps(parent), encoding="utf-8")
        midi_status, midi = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/midi")
        apply_status, apply = request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{task_id}/candidates/{candidate_id}/apply", {})
    finally:
        stop_test_server(server)

    assert project_status == 200
    assert midi_status == 409
    assert "stale" in midi["error"]
    assert apply_status == 409
    assert "stale" in apply["error"]
