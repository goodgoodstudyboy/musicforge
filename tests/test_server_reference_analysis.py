from __future__ import annotations

import base64
import json
import struct
import threading
import wave
from http.client import HTTPConnection
from io import BytesIO
from pathlib import Path

from song_agent.server import create_server


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def tiny_wav() -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes((1000).to_bytes(2, "little", signed=True) * 512)
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
    melody = track([(0, b"\x90\x40\x64"), (480, b"\x40\x00"), (0, b"\x43\x64"), (480, b"\x43\x00")])
    bass = track([(0, b"\x92\x24\x58"), (960, b"\x82\x24\x00")])
    return b"MThd" + struct.pack(">IHHH", 6, 1, 3, 480) + meta + melody + bass


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


def request_bytes(server, method, path):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    connection.request(method, path)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def import_reference(server, reference_type: str, filename: str, content: bytes):
    status, data = request_json(
        server,
        "POST",
        "/api/references/import",
        {"reference_type": reference_type, "filename": filename, "title": filename, "content_base64": b64(content)},
    )
    assert status == 201
    return data["reference"]


def test_reference_analysis_api_for_wav_text_and_midi(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        wav_ref = import_reference(server, "audio_wav", "seed.wav", tiny_wav())
        text_ref = import_reference(server, "lyrics_text", "hook.txt", b"api_key=sk-polluted-secret\nhello city")
        midi_ref = import_reference(server, "midi", "seed.mid", tiny_midi())
        not_status, not_analyzed = request_json(server, "GET", f"/api/references/{wav_ref['reference_id']}/analysis")
        wav_status, wav_report = request_json(server, "POST", f"/api/references/{wav_ref['reference_id']}/analyze")
        text_status, text_report = request_json(server, "POST", f"/api/references/{text_ref['reference_id']}/analysis", {"force": True})
        midi_status, midi_report = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/analyze")
        slice_status, slices = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/slices")
        slice_id = slices["manifest"]["slices"][0]["slice_id"]
        render_status, rendered = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/slices/{slice_id}/render-midi")
        midi_download_status, midi_data = request_bytes(server, "GET", f"/api/references/{midi_ref['reference_id']}/slices/{slice_id}/midi")
        audio_status, audio_error = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/slices/{slice_id}/render-audio")
        asset_status, asset = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/slices/{slice_id}/create-asset", {"name": "Slice Asset"})
    finally:
        stop_test_server(server)

    assert not_status == 200
    assert not_analyzed["analysis"]["status"] == "not_analyzed"
    assert wav_status == 200
    assert wav_report["analysis"]["summary"]["sample_rate"] == 8000
    assert text_status == 200
    assert "sk-polluted-secret" not in json.dumps(text_report)
    assert midi_status == 200
    assert midi_report["analysis"]["summary"]["note_count"] == 3
    assert slice_status == 200
    assert slices["manifest"]["slices"]
    assert render_status == 200
    assert rendered["slice"]["midi_status"] == "completed"
    assert midi_download_status == 200
    assert midi_data.startswith(b"MThd")
    assert audio_status == 400
    assert "soundfont_path is required" in audio_error["error"]
    assert asset_status == 201
    assert asset["asset"]["content"]["notes"]


def test_reference_slice_stale_download_and_create_asset_return_409(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        midi_ref = import_reference(server, "midi", "seed.mid", tiny_midi())
        request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/analyze")
        _slice_status, slices = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/slices")
        slice_id = slices["manifest"]["slices"][0]["slice_id"]
        ref_dir = Path(".musicforge") / "references" / midi_ref["reference_id"]
        metadata = json.loads((ref_dir / "reference.json").read_text(encoding="utf-8"))
        metadata["sha256"] = "c" * 64
        (ref_dir / "reference.json").write_text(json.dumps(metadata), encoding="utf-8")
        midi_status, midi_error = request_json(server, "GET", f"/api/references/{midi_ref['reference_id']}/slices/{slice_id}/midi")
        asset_status, asset_error = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/slices/{slice_id}/create-asset", {})
    finally:
        stop_test_server(server)

    assert midi_status == 409
    assert "stale" in midi_error["error"]
    assert asset_status == 409
    assert "stale" in asset_error["error"]


def test_slices_for_non_midi_return_conflict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        text_ref = import_reference(server, "lyrics_text", "hook.txt", b"hello")
        request_json(server, "POST", f"/api/references/{text_ref['reference_id']}/analyze")
        status, data = request_json(server, "POST", f"/api/references/{text_ref['reference_id']}/slices")
    finally:
        stop_test_server(server)

    assert status == 409
    assert "Only MIDI" in data["error"]
