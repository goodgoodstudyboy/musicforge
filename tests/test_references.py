from __future__ import annotations

import base64
from pathlib import Path

import pytest

from song_agent.assets import AssetStore
from song_agent.references import (
    ReferenceStore,
    reference_file_path,
    reference_prompt_summaries,
    reference_public_dict,
    reference_refs_snapshot,
    resolve_reference_refs,
)


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def wav_bytes() -> bytes:
    return b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt "


def midi_bytes() -> bytes:
    return b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff/\x00"


def import_payload(reference_type: str, filename: str, content: bytes) -> dict[str, object]:
    return {
        "reference_type": reference_type,
        "filename": filename,
        "title": "Seed Reference",
        "description": "synthetic test fixture",
        "tags": ["seed"],
        "content_base64": b64(content),
        "metadata": {"path": "C:/secret", "api_key": "sk-secret", "note": "safe"},
    }


def test_reference_store_imports_reads_filters_and_deletes(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, duplicate = store.import_reference(import_payload("audio_wav", "reference.wav", wav_bytes()), now="2026-05-08T00:00:00Z")

    assert duplicate is False
    assert reference.reference_id == "ref-001"
    assert reference.stored_filename == "reference.wav"
    assert store.file_path("ref-001").read_bytes().startswith(b"RIFF")
    assert store.read_reference("ref-001").metadata == {"note": "safe"}
    assert store.list_references(filters={"q": "seed"})[0].reference_id == "ref-001"
    assert store.list_references(filters={"type": "audio_wav"})[0].reference_id == "ref-001"
    assert store.list_references(filters={"tag": "seed"})[0].reference_id == "ref-001"

    updated = store.update_reference("ref-001", {"favorite": True, "tags": ["saved"], "tempo_bpm": 100})
    assert updated.favorite is True
    assert store.list_references(filters={"favorite": "1"})[0].tags == ["saved"]

    hidden = store.hide_reference("ref-001")
    assert hidden.hidden is True
    assert store.list_references() == []
    assert store.list_references(include_hidden=True)[0].reference_id == "ref-001"
    assert store.hide_reference("ref-001", hidden=False).hidden is False

    store.delete_reference("ref-001")
    assert store.list_references(include_hidden=True) == []


def test_reference_store_rejects_unsafe_imports(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    with pytest.raises(ValueError, match="Unsupported reference_type"):
        store.import_reference(import_payload("mp3", "bad.mp3", b"ID3"))
    with pytest.raises(ValueError, match="does not support"):
        store.import_reference(import_payload("audio_wav", "bad.mp3", b"ID3"))
    with pytest.raises(ValueError, match="valid WAV"):
        store.import_reference(import_payload("audio_wav", "bad.wav", b"not-wave"))
    with pytest.raises(ValueError, match="MThd"):
        store.import_reference(import_payload("midi", "bad.mid", b"bad-midi"))
    with pytest.raises(ValueError, match="valid base64"):
        store.import_reference({"reference_type": "lyrics_text", "filename": "lyric.txt", "content_base64": "***"})
    with pytest.raises(ValueError, match="path separators"):
        store.import_reference(import_payload("lyrics_text", "../lyric.txt", b"hello"))
    with pytest.raises(ValueError, match="reserved system name"):
        store.import_reference(import_payload("lyrics_text", "CON.txt", b"hello"))
    with pytest.raises(ValueError, match="control characters"):
        store.import_reference(import_payload("lyrics_text", "safe\r\nXInjected yes.txt", b"hello"))
    with pytest.raises(ValueError, match="unsupported characters"):
        store.import_reference(import_payload("lyrics_text", 'quote"bad.txt', b"hello"))
    with pytest.raises(ValueError, match="UTF-8"):
        store.import_reference(import_payload("lyrics_text", "lyric.txt", b"\xff\xff"))


def test_reference_duplicate_content_returns_existing(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    first, first_duplicate = store.import_reference(import_payload("lyrics_text", "a.txt", b"same text"))
    second, second_duplicate = store.import_reference(import_payload("lyrics_text", "b.txt", b"same text"))

    assert first_duplicate is False
    assert second_duplicate is True
    assert second.reference_id == first.reference_id
    assert len(store.list_references(include_hidden=True)) == 1


def test_reference_delete_rejects_symlink(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    store.root.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "outside"
    target.mkdir()
    link = store.root / "ref-001"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        return
    with pytest.raises(ValueError, match="symlink"):
        store.delete_reference("ref-001")


def test_reference_file_path_ignores_polluted_stored_filename(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("midi", "seed.mid", midi_bytes()))
    reference_dir = store.reference_dir(reference.reference_id)
    metadata_path = reference_dir / "reference.json"
    data = metadata_path.read_text(encoding="utf-8")
    metadata_path.write_text(data.replace("reference.mid", "../outside.mid"), encoding="utf-8")

    loaded = store.read_reference(reference.reference_id)
    assert reference_file_path(reference_dir, loaded).name == "reference.mid"
    assert store.file_path(reference.reference_id).read_bytes().startswith(b"MThd")


def test_reference_refs_resolve_snapshot_prompt_and_hidden_reject(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("style_note", "style.md", b"Use sparse verses and a bright hook."))
    refs = resolve_reference_refs(store, [{"reference_id": reference.reference_id, "role": "style", "strength": 0.8}])

    assert refs[0]["reference_id"] == reference.reference_id
    assert refs[0]["metadata_summary"]["text_excerpt"].startswith("Use sparse")
    assert reference_refs_snapshot(store, [{"reference_id": reference.reference_id}])["reference_refs"][0]["role"] == "reference_style"
    assert reference_prompt_summaries(store, [{"reference_id": reference.reference_id}])[0]["summary"]["text_excerpt"].startswith("Use sparse")

    store.mark_used([{"reference_id": reference.reference_id, "role": "style"}], {"usage_type": "test"})
    assert store.read_reference(reference.reference_id).usage_count == 1

    store.hide_reference(reference.reference_id)
    with pytest.raises(ValueError, match="Hidden references"):
        resolve_reference_refs(store, [{"reference_id": reference.reference_id}])


def test_reference_refs_reject_bad_shape_and_too_many(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    with pytest.raises(ValueError, match="must be a list"):
        resolve_reference_refs(store, {"reference_id": "ref-001"})
    with pytest.raises(ValueError, match="at most 5"):
        resolve_reference_refs(store, [{"reference_id": "ref-001"}] * 6)


def test_reference_to_asset_conversion_for_text_and_midi(tmp_path: Path) -> None:
    reference_store = ReferenceStore(tmp_path / ".musicforge" / "references")
    asset_store = AssetStore(tmp_path / ".musicforge" / "assets")
    lyric_ref, _ = reference_store.import_reference(import_payload("lyrics_text", "hook.txt", b"Shine on the final line"))
    midi_ref, _ = reference_store.import_reference(import_payload("midi", "seed.mid", midi_bytes()))
    wav_ref, _ = reference_store.import_reference(import_payload("audio_wav", "reference.wav", wav_bytes()))

    lyric_asset = reference_store.create_asset_from_reference(lyric_ref.reference_id, {"asset_type": "lyric_hook"}, asset_store)
    midi_asset = reference_store.create_asset_from_reference(midi_ref.reference_id, {"asset_type": "motif"}, asset_store)

    assert lyric_asset["asset_type"] == "lyric_hook"
    assert lyric_asset["content"]["text"] == "Shine on the final line"
    assert midi_asset["asset_type"] == "motif"
    assert midi_asset["content"]["midi_sha256"] == midi_ref.sha256
    assert reference_store.read_reference(lyric_ref.reference_id).derived_asset_ids == [lyric_asset["asset_id"]]

    with pytest.raises(ValueError, match="audio_wav"):
        reference_store.create_asset_from_reference(wav_ref.reference_id, {}, asset_store)


def test_reference_public_dict_redacts_metadata_and_adds_file_url(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("lyrics_text", "hook.txt", b"hello"))
    public = reference_public_dict(reference)

    assert public["file_url"] == "/api/references/ref-001/file"
    assert "api_key" not in public["metadata"]


def test_reference_text_fields_redact_sensitive_values(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(
        {
            **import_payload("style_note", "style.md", b"api_key=sk-polluted-secret use hook from C:\\Users\\bad\\song.wav"),
            "source_note": "Authorization: Bearer secret-token-value",
            "license_note": "github_pat_123456789012345678901234 and /Users/bad/private/ref.wav",
        }
    )
    updated = store.update_reference(reference.reference_id, {"description": "token=super-secret-value ghp_123456789012345678901234"})
    summary = reference_prompt_summaries(store, [{"reference_id": reference.reference_id}])[0]["summary"]
    serialized = str(updated.to_dict()) + str(summary)

    assert "sk-polluted-secret" not in serialized
    assert "secret-token-value" not in serialized
    assert "github_pat_123456789012345678901234" not in serialized
    assert "ghp_123456789012345678901234" not in serialized
    assert "C:\\Users\\bad" not in serialized
    assert "/Users/bad" not in serialized
    assert "[REDACTED]" in serialized or "[REDACTED_LOCAL_PATH]" in serialized
