from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.contracts.evidence_manifest import ExternalEvidenceManifest
from song_agent.platform.contracts.lifecycle import GenerationRef, ResetAuthorization, SignoffRef
from song_agent.platform.lifecycle import (
    ArchiveBuilder,
    ChangeRequestService,
    GenerationService,
    HistoryChain,
    SignoffService,
)
from song_agent.platform.verification.hashing import integrity_hash, sha256_file


def _integrity(document: dict[str, object]) -> dict[str, object]:
    result = dict(document)
    result["integrity_hash"] = integrity_hash(result)
    return result


def test_history_chain_append_validation_binding_and_explicit_migration(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    history = HistoryChain(path)
    first = history.append({"event_type": "signed", "signoff_hash": "s1"})
    second = history.append({"event_type": "reset", "signoff_hash": "s1"})

    assert history.validate().valid
    assert history.through(first["event_hash"]) == [first]
    assert history.latest_state({"signed": "signed", "reset": "reset"})["status"] == "reset"

    source_bytes = path.read_bytes()
    target = tmp_path / "migrated" / "history.jsonl"
    report = history.migrate_copy(
        target,
        source_schema_version=1,
        target_schema_version=2,
        adapter=lambda rows: [{**row, "schema_version": 2} for row in rows],
    )
    assert path.read_bytes() == source_bytes
    assert Path(report.rollback_path).read_bytes() == source_bytes
    assert report.source_hash != report.target_hash
    assert HistoryChain(target).validate().valid
    assert report.row_count == 2
    with pytest.raises(ValueError, match="already exists"):
        history.migrate_copy(target)

    reference = SignoffRef("subject", 1, "s1", "binding", second["event_hash"])
    assert SignoffService.validate_history_binding(history, reference)
    rows = history.read()
    rows.reverse()
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    assert not history.validate().valid
    assert not SignoffService.validate_history_binding(history, reference)


def test_signoff_transition_rejects_deleted_or_invalid_history(tmp_path: Path) -> None:
    history = HistoryChain(tmp_path / "history.jsonl")
    signoff_path = tmp_path / "signoff.json"
    signoff_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="history is missing"):
        SignoffService.assert_transition_allowed(
            history,
            artifact_paths=(signoff_path,),
            signed_event_types={"signed"},
            reset_event_types={"reset"},
        )

    signoff_path.unlink()
    history.append({"event_type": "signed", "signoff_hash": "s1"})
    with pytest.raises(ValueError, match="already signed"):
        SignoffService.assert_transition_allowed(
            history,
            artifact_paths=(),
            signed_event_types={"signed"},
            reset_event_types={"reset"},
        )
    history.append({"event_type": "reset", "signoff_hash": "s1"})
    SignoffService.assert_transition_allowed(
        history,
        artifact_paths=(),
        signed_event_types={"signed"},
        reset_event_types={"reset"},
    )


def test_change_request_authorization_is_approved_scoped_bound_and_single_use() -> None:
    target = {"signoff_hash": "s1", "generation": 1}
    source = {"source_hash": "source-1"}
    request = {
        "program_id": "program-1",
        "change_request_id": "cr-1",
        "change_type": "reset_signoff",
        "allowed_actions": ["reset_signoff"],
        "status": "approved",
        "target": target,
        "source": source,
        "submitted_request_hash": "submitted-1",
    }
    approval = _integrity(
        {
            "program_id": "program-1",
            "change_request_id": "cr-1",
            "status": "approved",
            "target": target,
            "source": source,
            "approved_actions": ["reset_signoff"],
            "request_hash": "submitted-1",
        }
    )
    request["approval_hash"] = approval["integrity_hash"]
    request = _integrity(request)
    expected = ResetAuthorization("program-1", "cr-1", "reset_signoff", "reset_signoff", target, source)

    ChangeRequestService.validate_reset_authorization(request, approval, expected)

    mutations = (
        {"allowed_actions": ["refresh"]},
        {"target": {"signoff_hash": "wrong", "generation": 1}},
        {"source": {"source_hash": "wrong"}},
        {"applied_at": "2026-07-13T00:00:00Z"},
    )
    for mutation in mutations:
        forged = _integrity({**request, **mutation, "integrity_hash": ""})
        with pytest.raises(ValueError):
            ChangeRequestService.validate_reset_authorization(forged, approval, expected)

    resigned_approval = _integrity({**approval, "target": {"signoff_hash": "wrong"}, "integrity_hash": ""})
    with pytest.raises(ValueError, match="target"):
        ChangeRequestService.validate_reset_authorization(request, resigned_approval, expected)


def test_generation_and_external_evidence_identity_are_order_independent() -> None:
    assert GenerationService.successor(1) == 2
    with pytest.raises(ValueError):
        GenerationService.require_current(1, 2)
    generation = GenerationService.build_document(
        GenerationRef("program-1", 2, "current", previous_generation=1, reset_proof_hash="proof"),
        package_type="musicforge_test_generation",
    )
    assert generation["generation"] == 2
    assert generation["previous_generation"] == 1
    assert generation["integrity_hash"] == integrity_hash(generation)

    first = EvidenceRef("vault", "v1", "archive", 1, zip_sha256="a" * 64)
    second = EvidenceRef("continuity", "c1", "archive", 2, zip_sha256="b" * 64)
    expected = ExternalEvidenceManifest((first, second))
    assert expected.matches_identity_set((second, first))
    assert not expected.matches_identity_set((first, first))


def test_archive_builder_freezes_layout_content_and_existing_zip(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    zip_path = tmp_path / "archive.zip"
    documents = {"manifest.json": {"status": "passed"}, "README.txt": "archive\n"}
    expected = ArchiveBuilder.export_documents(export_dir, documents)
    ArchiveBuilder.build_zip(export_dir, zip_path, expected)

    (export_dir / "README.txt").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        ArchiveBuilder.export_documents(export_dir, documents)
    (export_dir / "README.txt").write_bytes(expected["README.txt"])

    with zip_path.open("ab") as stream:
        stream.write(b"tamper")
    with pytest.raises(ValueError, match="trailing data"):
        ArchiveBuilder.build_zip(export_dir, zip_path, expected)

    source = tmp_path / "source.bin"
    target = tmp_path / "frozen.bin"
    source.write_bytes(b"source")
    fingerprint = str(sha256_file(source))
    ArchiveBuilder.copy_frozen(source, target, expected_sha256=fingerprint)
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="target fingerprint"):
        ArchiveBuilder.copy_frozen(source, target, expected_sha256=fingerprint)
