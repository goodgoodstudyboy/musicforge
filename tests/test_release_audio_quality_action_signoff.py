from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStateError, ReleaseAudioQualityActionQueueSignoffStore
from song_agent.release_audio_quality_action_signoff_verifier import verify_release_audio_quality_action_queue_signoff_archive_package
from song_agent.release_audio_quality_actions import ReleaseAudioQualityActionQueueStateError, ReleaseAudioQualityActionQueueStore
from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from song_agent.releases import stable_hash
from tests.test_release_audio_regression import _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def test_release_audio_quality_action_queue_signoff_archive_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Signoff")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_zip = observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id)["queue_id"]
        queue_store.run_safe(queue_id)
        queue_store.build_zip(queue_id)
        queue_store.verify_zip(queue_id, strict=True, require_current_observatory=True, require_no_blocking=False)
        signoff_store = ReleaseAudioQualityActionQueueSignoffStore(queue_store=queue_store, release_store=server.release_store)

        for item in signoff_store.list_manual_items(queue_id)["manual_items"]:
            signoff_store.resolve_manual_item(queue_id, item["item_id"], {"status": "completed", "resolved_by": "audio lead", "reason": "Reviewed and accepted."})
        closeout = signoff_store.refresh_closeout(queue_id)
        signoff = signoff_store.signoff(queue_id, {"signed_by": "audio lead", "reason": "Queue closeout accepted."})
        archive = signoff_store.build_archive_zip(queue_id)
        verification = signoff_store.verify_archive(queue_id, strict=True, require_current_queue=True, require_signed=True)
        external = verify_release_audio_quality_action_queue_signoff_archive_package(
            archive["zip_path"],
            strict=True,
            require_current_queue=True,
            require_signed=True,
            queue_zip_path=queue_store.zip_path(queue_id),
            queue_verification_report_path=queue_store.verification_report_path(queue_id),
            observatory_zip_path=observatory_zip["zip_path"],
            observatory_verification_report_path=observatory_store.verification_report_path(observatory_id),
            evidence_root=server.release_store.root,
            require_no_unresolved_manual=True,
        )
        gate = signoff_store.gate(release_id, queue_id=queue_id, required=True)
    finally:
        stop_test_server(server)

    assert closeout["status"] == "passed", closeout.get("checks")
    assert signoff["status"] == "signed"
    assert verification["status"] == "passed", verification.get("blockers")
    assert external["status"] == "passed", external.get("blockers")
    assert gate["status"] == "passed"


def test_release_audio_quality_action_queue_signed_mutation_and_deletion_guard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Signoff Guard")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id)["queue_id"]
        queue_store.run_safe(queue_id)
        queue_store.build_zip(queue_id)
        signoff_store = ReleaseAudioQualityActionQueueSignoffStore(queue_store=queue_store, release_store=server.release_store)
        signoff_store.signoff(queue_id, {"signed_by": "audio lead", "reason": "Queue closeout accepted."})

        with pytest.raises(ReleaseAudioQualityActionQueueStateError):
            queue_store.run_safe(queue_id)
        signoff_store.signoff_path(queue_id).unlink()
        with pytest.raises(ReleaseAudioQualityActionQueueStateError):
            queue_store.refresh_status(queue_id)
        with pytest.raises(ReleaseAudioQualityActionQueueSignoffStateError):
            signoff_store.resolve_manual_item(queue_id, "aqai-000001", {"status": "completed", "reason": "blocked"})
    finally:
        stop_test_server(server)


def test_release_audio_quality_action_queue_signoff_archive_rejects_declared_extra(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Signoff Extra")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id)["queue_id"]
        queue_store.run_safe(queue_id)
        queue_store.build_zip(queue_id)
        signoff_store = ReleaseAudioQualityActionQueueSignoffStore(queue_store=queue_store, release_store=server.release_store)
        signoff_store.signoff(queue_id, {"signed_by": "audio lead", "reason": "Queue closeout accepted."})
        archive = signoff_store.build_archive_zip(queue_id)
        tampered = tmp_path / "tampered-signoff-archive.zip"
        _add_declared_extra(Path(archive["zip_path"]), tampered)
        verification = verify_release_audio_quality_action_queue_signoff_archive_package(tampered, strict=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert verification["status"] == "failed"
    assert "release_audio_quality_action_queue_signoff_archive_zip_allowed_entries" in verification["blockers"]


def _add_declared_extra(source_zip: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(source_zip, "r") as source:
        docs = {info.filename: source.read(info.filename) for info in source.infolist()}
    docs["extra.txt"] = b"untrusted instructions\n"
    manifest = json.loads(docs["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": "extra.txt", "size_bytes": len(docs["extra.txt"]), "sha256": _sha256_bytes(docs["extra.txt"])})
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    docs["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(docs.items()):
            archive.writestr(name, data)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
