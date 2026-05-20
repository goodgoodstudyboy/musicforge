from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.human_review_pack import HumanReviewPackStateError, HumanReviewPackStore, HumanReviewPackValidationError
from song_agent.human_review_verifier import verify_human_review_pack
from song_agent.music_acceptance import AcceptanceStore
from song_agent.projectio import read_json


def _suite_with_cases(tmp_path: Path, *, count: int = 2) -> tuple[AcceptanceStore, str, list[str]]:
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"name": "Human Review", "min_rating": 3, "require_audio_if_renderer_configured": False})
    case_ids: list[str] = []
    for index in range(count):
        case = store.add_case(
            suite.suite_id,
            {
                "song_id": f"song_{index + 1:03d}",
                "request": {"title": f"Human Review {index + 1}", "language": "English", "style": "pop", "theme": "review", "duration_seconds": 90},
            },
        )
        store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
        store.run_health(suite.suite_id, case.case_id)
        case_ids.append(case.case_id)
    return store, suite.suite_id, case_ids


def _response(pack: dict, *, statuses: list[str] | None = None) -> dict:
    statuses = statuses or ["accepted"] * len(pack["cases"])
    return {
        "schema_version": 1,
        "suite_id": pack["suite_id"],
        "pack_id": pack["pack_id"],
        "pack_source_hash": pack["source_hash"],
        "reviewer": {"name": "manual reviewer", "organization": "qa"},
        "reviewed_at": "2026-05-19T00:00:00+00:00",
        "reviews": [
            {
                "case_id": case["case_id"],
                "song_id": case["song_id"],
                "status": statuses[index],
                "rating": 5 if statuses[index] == "accepted" else 2,
                "playback_confirmed": True,
                "audio_mode": "midi",
                "notes": "Manual listener confirmed playback and captured review notes.",
                "issues": ["hook needs clearer lift"] if statuses[index] != "accepted" else [],
                "tags": ["external"],
                "markers": [{"beat": 4, "severity": "warning", "label": "hook", "note": "Needs clearer lift"}] if statuses[index] != "accepted" else [],
            }
            for index, case in enumerate(pack["cases"])
        ],
    }


def test_human_review_pack_create_zip_verify_and_import(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, case_ids = _suite_with_cases(tmp_path)
    pack_store = HumanReviewPackStore(acceptance_store)

    created = pack_store.create_pack(suite_id)
    pack = created["pack"]
    zipped = pack_store.build_zip(suite_id, pack["pack_id"])
    report = verify_human_review_pack(pack_store.zip_path(suite_id, pack["pack_id"]), strict=True)
    imported = pack_store.import_response(suite_id, {"response": _response(pack, statuses=["accepted", "needs_fix"])})
    acceptance_report = acceptance_store.read_report(suite_id)
    stored_review = acceptance_store.read_review(suite_id, case_ids[1])

    assert created["manifest"]["case_count"] == 2
    assert zipped["zip"]["entry_count"] >= 6
    assert report["status"] == "passed"
    assert imported["summary"]["accepted_count"] == 1
    assert imported["summary"]["needs_fix_count"] == 1
    assert imported["summary"]["created_review_task_count"] == 1
    assert stored_review["source"]["source_type"] == "human_review_pack"
    assert stored_review["source"]["pack_id"] == pack["pack_id"]
    assert stored_review["markers"][0]["label"] == "hook"
    assert acceptance_report["summary"]["human_review_pack"]["latest_import_id"] == imported["import_id"]
    assert acceptance_report["status"] == "failed"


def test_human_review_pack_import_all_accepted_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_ids = _suite_with_cases(tmp_path)
    pack_store = HumanReviewPackStore(acceptance_store)
    pack = pack_store.create_pack(suite_id)["pack"]
    pack_store.build_zip(suite_id, pack["pack_id"])

    imported = pack_store.import_response(suite_id, {"response": _response(pack)})
    report = acceptance_store.read_report(suite_id)

    assert imported["summary"]["accepted_count"] == 2
    assert report["status"] == "passed"
    assert report["summary"]["manual_accepted_count"] == 2


def test_human_review_pack_import_does_not_stale_pack_and_allows_reimport(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_ids = _suite_with_cases(tmp_path)
    pack_store = HumanReviewPackStore(acceptance_store)
    pack = pack_store.create_pack(suite_id)["pack"]
    pack_store.build_zip(suite_id, pack["pack_id"])

    imported = pack_store.import_response(suite_id, {"response": _response(pack, statuses=["accepted", "needs_fix"])})
    after_first = pack_store.get_pack(suite_id, pack["pack_id"])
    revised = _response(pack)
    revised["reviews"][0]["notes"] = "Manual listener revised this response after a second full playback."
    imported_revised = pack_store.import_response(suite_id, {"response": revised})
    after_second = pack_store.get_pack(suite_id, pack["pack_id"])

    assert imported["summary"]["needs_fix_count"] == 1
    assert after_first["stale"] is False
    assert imported_revised["summary"]["accepted_count"] == 2
    assert after_second["stale"] is False


def test_human_review_response_rejects_song_id_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_ids = _suite_with_cases(tmp_path)
    pack_store = HumanReviewPackStore(acceptance_store)
    pack = pack_store.create_pack(suite_id)["pack"]
    pack_store.build_zip(suite_id, pack["pack_id"])
    response = _response(pack)
    response["reviews"][0]["song_id"] = "WRONG_SONG"

    with pytest.raises(HumanReviewPackValidationError, match="song_id"):
        pack_store.import_response(suite_id, {"response": response})


def test_human_review_pack_stale_and_signed_guards(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_ids = _suite_with_cases(tmp_path)
    pack_store = HumanReviewPackStore(acceptance_store)
    pack = pack_store.create_pack(suite_id)["pack"]
    pack_store.build_zip(suite_id, pack["pack_id"])
    response = _response(pack)
    changed = acceptance_store.add_case(suite_id, {"request": {"title": "Changed", "language": "English", "style": "pop", "theme": "stale", "duration_seconds": 90}})
    with pytest.raises(HumanReviewPackStateError):
        pack_store.import_response(suite_id, {"response": response})

    acceptance_store.generate_case(suite_id, changed.case_id, render_audio_mode="never")
    acceptance_store.run_health(suite_id, changed.case_id)
    fresh = pack_store.create_pack(suite_id)["pack"]
    pack_store.build_zip(suite_id, fresh["pack_id"])
    pack_store.import_response(suite_id, {"response": _response(fresh)})
    acceptance_store.signoff(suite_id, {"signed_by": "tester"})
    with pytest.raises(HumanReviewPackStateError):
        pack_store.create_pack(suite_id)


def test_human_review_response_rejects_source_path_and_dangerous_keys(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_ids = _suite_with_cases(tmp_path)
    pack_store = HumanReviewPackStore(acceptance_store)
    pack = pack_store.create_pack(suite_id)["pack"]

    with pytest.raises(HumanReviewPackValidationError):
        pack_store.import_response(suite_id, {"source_path": str(tmp_path / "response.json")})
    bad = _response(pack)
    bad["reviews"][0]["source_path"] = "C:\\Users\\secret\\response.json"
    with pytest.raises(HumanReviewPackValidationError):
        pack_store.import_response(suite_id, {"response": bad})


def test_human_review_verifier_blocks_duplicate_backslash_and_remote_html(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_ids = _suite_with_cases(tmp_path)
    pack_store = HumanReviewPackStore(acceptance_store)
    pack = pack_store.create_pack(suite_id)["pack"]
    pack_store.build_zip(suite_id, pack["pack_id"])
    good_zip = pack_store.zip_path(suite_id, pack["pack_id"])
    assert verify_human_review_pack(good_zip, strict=True)["status"] == "passed"

    bad_zip = tmp_path / "bad-human-review-pack.zip"
    with zipfile.ZipFile(good_zip, "r") as source, zipfile.ZipFile(bad_zip, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "index.html":
                data = data.replace(b"</body>", b'<script src="https://example.com/app.js"></script></body>')
            target.writestr(info.filename, data)
        target.writestr("manifest.json", json.dumps(read_json(pack_store.manifest_path(suite_id, pack["pack_id"]))))
        target.writestr("../evil.txt", "bad")

    report = verify_human_review_pack(bad_zip, strict=True)
    assert report["status"] == "failed"
    check_ids = {item["check_id"] for item in report["blockers"]}
    assert "zip_duplicate_entries" in check_ids
    assert "zip_entry_path_safe" in check_ids
    assert "human_review_static_html_offline" in check_ids
