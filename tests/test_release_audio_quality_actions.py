from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from song_agent.release_audio_quality_actions import ReleaseAudioQualityActionQueueStateError, ReleaseAudioQualityActionQueueStore
from song_agent.release_audio_quality_actions_verifier import verify_release_audio_quality_action_queue_package
from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from song_agent.releases import stable_hash
from tests.test_release_audio_regression import _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def test_release_audio_quality_action_queue_lifecycle_and_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue Track")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_zip = observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True, require_no_critical_risk=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue = queue_store.create_from_observatory(observatory_id)
        run = queue_store.run_safe(queue["queue_id"])
        zipped = queue_store.build_zip(queue["queue_id"])
        verification = queue_store.verify_zip(queue["queue_id"], strict=True, require_current_observatory=True)
        external = verify_release_audio_quality_action_queue_package(
            zipped["zip_path"],
            strict=True,
            require_current_observatory=True,
            observatory_zip_path=observatory_zip["zip_path"],
            observatory_verification_report_path=observatory_store.verification_report_path(observatory_id),
            evidence_root=server.release_store.root,
        )
        gate = queue_store.gate(release_id, queue_id=queue["queue_id"], required=True)
    finally:
        stop_test_server(server)

    assert run["status"] in {"completed", "completed_with_manual_actions"}
    assert verification["status"] == "passed", verification.get("blockers")
    assert external["status"] == "passed", external.get("blockers")
    assert gate["status"] == "passed"


def test_release_audio_quality_action_queue_blocks_stale_source_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue Stale")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id)["queue_id"]
        observatory_store.refresh(observatory_id, {"quality_floor": 0.99})
        try:
            queue_store.export_package(queue_id)
        except ReleaseAudioQualityActionQueueStateError:
            blocked = True
        else:
            blocked = False
    finally:
        stop_test_server(server)

    assert blocked is True


def test_release_audio_quality_action_queue_verifier_rejects_full_resign_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue Full Resign")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_zip = observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id)["queue_id"]
        queue_store.run_safe(queue_id)
        zipped = queue_store.build_zip(queue_id)
        tampered = tmp_path / "action-queue-full-resign.zip"
        _rewrite_action_queue_source_fingerprint(Path(zipped["zip_path"]), tampered)
        verification = verify_release_audio_quality_action_queue_package(
            tampered,
            strict=True,
            require_current_observatory=True,
            observatory_zip_path=observatory_zip["zip_path"],
            observatory_verification_report_path=observatory_store.verification_report_path(observatory_id),
            evidence_root=server.release_store.root,
        )
    finally:
        stop_test_server(server)

    assert verification["status"] == "failed"
    assert "release_audio_quality_action_queue_external_source_binding" in verification["blockers"]


def test_release_audio_quality_action_queue_filter_policy_round_trips_to_verifier(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Action Queue Filtered")
        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"release_ids": [release_id]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_zip = observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True)
        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue = queue_store.create_from_observatory(
            observatory_id,
            include_risks=True,
            include_recommendations=False,
            severity_floor="critical",
        )
        run = queue_store.run_safe(queue["queue_id"])
        zipped = queue_store.build_zip(queue["queue_id"])
        verification = verify_release_audio_quality_action_queue_package(
            zipped["zip_path"],
            strict=True,
            require_current_observatory=True,
            observatory_zip_path=observatory_zip["zip_path"],
            observatory_verification_report_path=observatory_store.verification_report_path(observatory_id),
            evidence_root=server.release_store.root,
        )
        queue_doc = queue_store.read_queue(queue["queue_id"])
        summary = queue_store.read_summary(queue["queue_id"])
    finally:
        stop_test_server(server)

    manual_ids = {row["item_id"] for row in run["manual_actions"]["manual_actions"]}
    manual_ids.update(row["item_id"] for row in run["results"]["results"] if row.get("status") == "manual_required")
    assert queue_doc["action_selection"] == {"include_risks": True, "include_recommendations": False, "severity_floor": "critical"}
    assert verification["status"] == "passed", verification.get("blockers")
    assert "release_audio_quality_action_queue_external_action_items" not in verification.get("blockers", [])
    assert summary["summary"]["manual_required_count"] == len(manual_ids)


def _rewrite_action_queue_source_fingerprint(source_zip: Path, target_zip: Path) -> None:
    with zipfile.ZipFile(source_zip, "r") as source:
        docs = {info.filename: source.read(info.filename) for info in source.infolist()}
    payloads = {name: json.loads(data.decode("utf-8")) for name, data in docs.items() if name.endswith(".json")}
    binding = payloads["source-binding.json"]
    queue = payloads["action-queue.json"]
    items = payloads["action-items.json"]
    results = payloads["action-results.json"]
    manual = payloads["manual-actions.json"]
    summary = payloads["queue-summary.json"]
    manifest = payloads["manifest.json"]
    binding["observatory"]["zip_sha256"] = "f" * 64
    binding["source_hash"] = stable_hash(
        {
            "observatory_id": binding.get("observatory_id"),
            "observatory_zip_sha256": binding["observatory"]["zip_sha256"],
            "observatory_zip_size_bytes": binding["observatory"].get("zip_size_bytes"),
            "observatory_manifest_hash": binding["observatory"].get("manifest_hash"),
            "observatory_source_hash": binding["observatory"].get("source_hash"),
            "risk_register_hash": binding.get("risk_register", {}).get("integrity_hash"),
            "recommendation_report_hash": binding.get("recommendation_report", {}).get("integrity_hash"),
        }
    )
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    source_hash = binding["source_hash"]
    for doc in (queue, items, results, manual, summary):
        doc["source_hash"] = source_hash
    queue["source"] = binding["observatory"]
    for doc in (queue, items, results, manual):
        doc["integrity_hash"] = stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})
    summary["document_hashes"]["source_binding"] = binding["integrity_hash"]
    summary["document_hashes"]["action_queue"] = queue["integrity_hash"]
    summary["document_hashes"]["action_items"] = items["integrity_hash"]
    summary["document_hashes"]["action_results"] = results["integrity_hash"]
    summary["document_hashes"]["manual_actions"] = manual["integrity_hash"]
    summary["integrity_hash"] = stable_hash({key: value for key, value in summary.items() if key != "integrity_hash"})
    manifest["source_hash"] = source_hash
    manifest["source_binding_hash"] = binding["integrity_hash"]
    manifest["action_queue_hash"] = queue["integrity_hash"]
    manifest["action_items_hash"] = items["integrity_hash"]
    manifest["action_results_hash"] = results["integrity_hash"]
    manifest["manual_actions_hash"] = manual["integrity_hash"]
    manifest["summary_hash"] = summary["integrity_hash"]
    payloads.update(
        {
            "source-binding.json": binding,
            "action-queue.json": queue,
            "action-items.json": items,
            "action-results.json": results,
            "manual-actions.json": manual,
            "queue-summary.json": summary,
        }
    )
    for name, payload in payloads.items():
        if name == "manifest.json":
            continue
        docs[name] = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    files = []
    for record in manifest.get("files", []):
        rel = record["path"]
        record = dict(record)
        record["size_bytes"] = len(docs[rel])
        record["sha256"] = hashlib.sha256(docs[rel]).hexdigest()
        files.append(record)
    manifest["files"] = files
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    docs["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(docs.items()):
            archive.writestr(name, data)
