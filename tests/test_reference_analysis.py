from __future__ import annotations

import base64
import json
import struct
import wave
from io import BytesIO
from pathlib import Path

import pytest

from song_agent.assets import AssetStore
from song_agent.reference_analysis import (
    analyze_reference,
    create_asset_from_slice,
    generate_slices,
    get_analysis_report,
    get_slice_manifest,
    render_reference_slice_midi,
)
from song_agent.references import ReferenceStore


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def import_payload(reference_type: str, filename: str, content: bytes) -> dict[str, object]:
    return {"reference_type": reference_type, "filename": filename, "content_base64": b64(content), "title": filename}


def tiny_wav(frame_count: int = 512) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        frames = bytearray()
        for index in range(frame_count):
            value = int(12000 * (1 if index % 2 == 0 else -1))
            frames.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(bytes(frames))
    return buffer.getvalue()


def vlq(value: int) -> bytes:
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= (value & 0x7F) | 0x80
        value >>= 7
    out = bytearray()
    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            return bytes(out)


def track(events: list[tuple[int, bytes]]) -> bytes:
    body = bytearray()
    for delta, payload in events:
        body.extend(vlq(delta))
        body.extend(payload)
    body.extend(b"\x00\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def tiny_midi() -> bytes:
    meta = track([(0, b"\xff\x51\x03\x07\xa1\x20")])
    melody = track([(0, b"\xc0\x51"), (0, b"\x90\x40\x64"), (480, b"\x40\x00"), (0, b"\x43\x64"), (480, b"\x43\x00")])
    bass = track([(0, b"\x92\x24\x58"), (960, b"\x82\x24\x00")])
    return b"MThd" + struct.pack(">IHHH", 6, 1, 3, 480) + meta + melody + bass


def test_wav_analysis_summary_and_envelope_limit(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("audio_wav", "seed.wav", tiny_wav(frame_count=4096)))

    report = analyze_reference(store, reference.reference_id, now="2026-05-08T00:00:00Z")

    assert report["status"] == "completed"
    assert report["summary"]["sample_rate"] == 8000
    assert report["summary"]["channels"] == 1
    assert report["summary"]["peak"] > 0
    assert len(report["summary"]["envelope"]) <= 256
    assert get_analysis_report(store, reference.reference_id)["stale"] is False


def test_text_analysis_redacts_sensitive_values(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    content = "api_key=sk-polluted-secret\nUse the rainy city hook from D:\\Music\\hook.wav".encode("utf-8")
    reference, _ = store.import_reference(import_payload("lyrics_text", "hook.txt", content))

    report = analyze_reference(store, reference.reference_id)
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["summary"]["line_count"] == 2
    assert report["summary"]["language_hint"] in {"en", "zh"}
    assert "sk-polluted-secret" not in serialized
    assert "D:\\Music" not in serialized


def test_analysis_stale_detection(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("lyrics_text", "hook.txt", b"hello"))
    analyze_reference(store, reference.reference_id)
    path = store.reference_dir(reference.reference_id) / "reference.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sha256"] = "a" * 64
    path.write_text(json.dumps(data), encoding="utf-8")

    report = get_analysis_report(store, reference.reference_id)

    assert report["status"] == "stale"
    assert report["stale"] is True


def test_legacy_reference_returns_not_analyzed(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("lyrics_text", "hook.txt", b"hello"))

    report = get_analysis_report(store, reference.reference_id)

    assert report["status"] == "not_analyzed"


def test_midi_analysis_slices_render_and_create_asset(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    asset_store = AssetStore(tmp_path / ".musicforge" / "assets")
    reference, _ = store.import_reference(import_payload("midi", "seed.mid", tiny_midi()))

    report = analyze_reference(store, reference.reference_id)
    manifest = generate_slices(store, reference.reference_id)
    slice_id = manifest["slices"][0]["slice_id"]
    rendered = render_reference_slice_midi(store, reference.reference_id, slice_id)
    asset = create_asset_from_slice(store, reference.reference_id, slice_id, {"name": "Real MIDI slice"}, asset_store)

    assert report["summary"]["note_count"] == 3
    assert manifest["slices"]
    assert rendered["slice"]["midi_status"] == "completed"
    assert (store.reference_dir(reference.reference_id) / "preview" / f"{slice_id}.mid").read_bytes().startswith(b"MThd")
    assert asset["asset_type"] in {"motif", "bass_pattern"}
    assert asset["content"]["notes"]
    assert asset["content"]["notes"][0]["start_beat"] == 0
    assert store.read_reference(reference.reference_id).derived_asset_ids == [asset["asset_id"]]


def test_slice_manifest_stale_after_reference_hash_change(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("midi", "seed.mid", tiny_midi()))
    analyze_reference(store, reference.reference_id)
    generate_slices(store, reference.reference_id)
    path = store.reference_dir(reference.reference_id) / "reference.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sha256"] = "b" * 64
    path.write_text(json.dumps(data), encoding="utf-8")

    manifest = get_slice_manifest(store, reference.reference_id)

    assert manifest["status"] == "stale"
    assert manifest["stale"] is True


def test_non_midi_slices_rejected(tmp_path: Path) -> None:
    store = ReferenceStore(tmp_path / ".musicforge" / "references")
    reference, _ = store.import_reference(import_payload("lyrics_text", "hook.txt", b"hello"))
    analyze_reference(store, reference.reference_id)

    with pytest.raises(ValueError, match="Only MIDI"):
        generate_slices(store, reference.reference_id)
