from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import math
import shutil
import wave
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from song_agent.domains.studio.assets import AssetStore, asset_public_dict
from song_agent.domains.creation.midi_analysis import MidiParseError, midi_summary, notes_for_slice, parse_midi, render_slice_midi, suggest_slices
from song_agent.domains.studio.projectio import now_iso, read_json, write_json
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.studio.reference_paths import reference_file_path
from song_agent.domains.creation.renderers.audio import RendererConfig, RendererError, render_audio


REFERENCE_ANALYSIS_SCHEMA_VERSION = 1
REFERENCE_SLICES_SCHEMA_VERSION = 1
MAX_ENVELOPE_POINTS = 256
MAX_TEXT_KEYWORDS = 20
MAX_PROVIDER_REFERENCE_SUMMARY_CHARS = 2_000
MAX_TOTAL_PROVIDER_REFERENCE_SUMMARY_CHARS = 6_000
MAX_EXPORT_ENVELOPE_POINTS = 16


class ReferenceAnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceContext:
    reference: Any
    reference_dir: Path
    source_path: Path


def reference_context(store: Any, reference_id: str) -> ReferenceContext:
    reference = store.read_reference(reference_id)
    reference_dir = store.reference_dir(reference.reference_id)
    source_path = reference_file_path(reference_dir, reference)
    _ensure_within(reference_dir / "original", source_path)
    if not source_path.exists():
        raise FileNotFoundError(reference.reference_id)
    return ReferenceContext(reference=reference, reference_dir=reference_dir, source_path=source_path)


def get_analysis_report(store: ReferenceStore, reference_id: str) -> dict[str, Any]:
    context = reference_context(store, reference_id)
    path = analysis_path(context.reference_dir)
    if not path.exists():
        return not_analyzed_report(context.reference)
    report = _sanitize_report(read_json(path))
    if report.get("source_sha256") != context.reference.sha256:
        report["status"] = "stale"
        report["stale"] = True
        report.setdefault("warnings", []).append("Analysis source hash does not match the current reference.")
    else:
        report["stale"] = False
    return report


def analyze_reference(store: ReferenceStore, reference_id: str, *, force: bool = False, now: str | None = None) -> dict[str, Any]:
    now = now or now_iso()
    context = reference_context(store, reference_id)
    path = analysis_path(context.reference_dir)
    if path.exists() and not force:
        existing = get_analysis_report(store, reference_id)
        if not existing.get("stale"):
            return existing
    if force:
        clear_reference_analysis_artifacts(context.reference_dir, keep_analysis=False)
    if context.reference.reference_type == "audio_wav":
        report = _analyze_wav(context, now)
    elif context.reference.reference_type == "midi":
        report = _analyze_midi(context, now)
    elif context.reference.reference_type in {"lyrics_text", "style_note"}:
        report = _analyze_text(context, now)
    else:
        report = _base_report(context.reference, now, status="failed", errors=["Unsupported reference type."])
    write_json(path, _sanitize_report(report))
    _append_reference_event(context.reference_dir, "reference_analyzed", {"status": report["status"], "reference_type": context.reference.reference_type}, now)
    return get_analysis_report(store, reference_id)


def get_slice_manifest(store: ReferenceStore, reference_id: str) -> dict[str, Any]:
    context = reference_context(store, reference_id)
    path = slices_path(context.reference_dir)
    if not path.exists():
        return {"schema_version": REFERENCE_SLICES_SCHEMA_VERSION, "reference_id": context.reference.reference_id, "source_sha256": context.reference.sha256, "status": "not_generated", "slices": []}
    manifest = _sanitize_report(read_json(path))
    if manifest.get("source_sha256") != context.reference.sha256:
        manifest["status"] = "stale"
        manifest["stale"] = True
    else:
        manifest["stale"] = False
        manifest.setdefault("status", "completed")
    return manifest


def generate_slices(store: ReferenceStore, reference_id: str, *, force: bool = False, now: str | None = None) -> dict[str, Any]:
    now = now or now_iso()
    context = reference_context(store, reference_id)
    if context.reference.reference_type != "midi":
        raise ReferenceAnalysisError("Only MIDI references can generate slices.")
    manifest_path = slices_path(context.reference_dir)
    if manifest_path.exists() and not force:
        existing = get_slice_manifest(store, reference_id)
        if not existing.get("stale"):
            return existing
    if force:
        clear_reference_analysis_artifacts(context.reference_dir, keep_analysis=True)
    midi = parse_midi(context.source_path.read_bytes())
    slices = suggest_slices(midi)
    manifest = {
        "schema_version": REFERENCE_SLICES_SCHEMA_VERSION,
        "reference_id": context.reference.reference_id,
        "source_sha256": context.reference.sha256,
        "status": "completed",
        "generated_at": now,
        "slice_count": len(slices),
        "slices": slices,
    }
    write_json(manifest_path, _sanitize_report(manifest))
    _append_reference_event(context.reference_dir, "reference_slices_generated", {"slice_count": len(slices)}, now)
    return get_slice_manifest(store, reference_id)


def render_reference_slice_midi(store: ReferenceStore, reference_id: str, slice_id: str, *, now: str | None = None) -> dict[str, Any]:
    now = now or now_iso()
    context = reference_context(store, reference_id)
    manifest = require_fresh_slices(store, reference_id)
    slice_item = _find_slice(manifest, slice_id)
    midi = parse_midi(context.source_path.read_bytes())
    path = slice_midi_path(context.reference_dir, slice_id)
    try:
        render_slice_midi(midi, slice_item, path, title=f"{context.reference.title} {slice_id}")
    except Exception as exc:
        updated = _update_slice(manifest, slice_id, {"midi_status": "failed", "midi_error": str(exc), "midi_url": None, "midi_size_bytes": 0})
        write_json(slices_path(context.reference_dir), updated)
        raise
    updated = _update_slice(
        manifest,
        slice_id,
        {
            "midi_status": "completed",
            "midi_error": None,
            "midi_url": slice_midi_url(reference_id, slice_id),
            "midi_size_bytes": path.stat().st_size,
            "updated_at": now,
        },
    )
    write_json(slices_path(context.reference_dir), updated)
    _append_reference_event(context.reference_dir, "reference_slice_midi_rendered", {"slice_id": slice_id, "size_bytes": path.stat().st_size}, now)
    return {"slice": _find_slice(updated, slice_id), "manifest": updated}


def render_reference_slice_audio(store: ReferenceStore, reference_id: str, slice_id: str, config: RendererConfig, *, now: str | None = None) -> dict[str, Any]:
    now = now or now_iso()
    context = reference_context(store, reference_id)
    manifest = require_fresh_slices(store, reference_id)
    midi_path = slice_midi_path(context.reference_dir, slice_id)
    if not midi_path.exists():
        render_reference_slice_midi(store, reference_id, slice_id, now=now)
        manifest = require_fresh_slices(store, reference_id)
    wav_path = slice_audio_path(context.reference_dir, slice_id)
    try:
        render_audio(midi_path, wav_path, config)
    except RendererError as exc:
        updated = _update_slice(manifest, slice_id, {"audio_status": "failed", "audio_error": str(exc), "audio_url": None, "audio_size_bytes": 0})
        write_json(slices_path(context.reference_dir), updated)
        raise
    updated = _update_slice(
        manifest,
        slice_id,
        {
            "audio_status": "completed",
            "audio_error": None,
            "audio_url": slice_audio_url(reference_id, slice_id),
            "audio_size_bytes": wav_path.stat().st_size,
            "updated_at": now,
        },
    )
    write_json(slices_path(context.reference_dir), updated)
    _append_reference_event(context.reference_dir, "reference_slice_audio_rendered", {"slice_id": slice_id, "size_bytes": wav_path.stat().st_size}, now)
    return {"slice": _find_slice(updated, slice_id), "manifest": updated}


def create_asset_from_slice(store: ReferenceStore, reference_id: str, slice_id: str, payload: dict[str, Any], asset_store: AssetStore, *, now: str | None = None) -> dict[str, Any]:
    now = now or now_iso()
    context = reference_context(store, reference_id)
    if context.reference.hidden:
        raise ReferenceAnalysisError("Hidden references cannot create slice assets.")
    manifest = require_fresh_slices(store, reference_id)
    slice_item = _find_slice(manifest, slice_id)
    midi = parse_midi(context.source_path.read_bytes())
    notes = notes_for_slice(midi, slice_item)
    if not notes:
        raise ReferenceAnalysisError("Slice has no notes.")
    asset_type = str(payload.get("asset_type") or slice_item.get("slice_type") or "motif")
    if asset_type not in {"motif", "chord_progression", "drum_pattern", "bass_pattern"}:
        raise ReferenceAnalysisError("Slice assets must be motif, chord_progression, drum_pattern, or bass_pattern.")
    duration_beats = float(slice_item.get("duration_beats") or max(note["start_beat"] + note["duration_beats"] for note in notes))
    midi_path = slice_midi_path(context.reference_dir, slice_id)
    midi_sha = hashlib.sha256(midi_path.read_bytes()).hexdigest() if midi_path.exists() else context.reference.sha256
    asset_payload = {
        "asset_type": asset_type,
        "name": _bounded_text(payload.get("name"), 120) or f"{context.reference.title} {slice_id}",
        "description": _bounded_text(payload.get("description"), 1000) or f"Created from MIDI reference {context.reference.reference_id} {slice_id}.",
        "tags": _clean_tags(payload.get("tags") or context.reference.tags),
        "key": context.reference.key or "C",
        "tempo_bpm": context.reference.tempo_bpm or _tempo_from_analysis(store, reference_id) or 120,
        "meter": context.reference.meter or "4/4",
        "duration_beats": max(0.25, duration_beats),
        "favorite": bool(payload.get("favorite", False)),
        "source": {
            "source_type": "reference_slice",
            "reference_id": context.reference.reference_id,
            "reference_type": context.reference.reference_type,
            "slice_id": slice_id,
            "sha256": context.reference.sha256,
        },
        "content": {
            "kind": asset_type,
            "reference_id": context.reference.reference_id,
            "slice_id": slice_id,
            "notes": _asset_notes(notes),
            "midi_sha256": midi_sha,
            "track_index": slice_item.get("track_index"),
            "channel": slice_item.get("channel"),
        },
        "source_fragment": {
            "schema_version": 1,
            "reference_id": context.reference.reference_id,
            "source_sha256": context.reference.sha256,
            "slice": _export_slice_summary(slice_item),
            "note_count": len(notes),
            "created_at": now,
        },
    }
    if asset_type == "chord_progression":
        asset_payload["content"]["chords"] = ["Cmaj7"]
    asset = asset_store.create_asset(asset_payload, now=now)
    linked = list(context.reference.derived_asset_ids)
    if asset.asset_id not in linked:
        linked.append(asset.asset_id)
    updated = type(context.reference).from_dict({**context.reference.to_dict(), "derived_asset_ids": linked, "updated_at": now})
    store._write_reference(updated)
    _append_reference_event(context.reference_dir, "reference_slice_asset_created", {"slice_id": slice_id, "asset_id": asset.asset_id}, now)
    return asset_public_dict(asset)


def require_fresh_analysis(store: ReferenceStore, reference_id: str) -> dict[str, Any]:
    report = get_analysis_report(store, reference_id)
    if report.get("status") == "not_analyzed":
        raise ReferenceAnalysisError("Reference analysis has not been generated.")
    if report.get("stale"):
        raise ReferenceAnalysisError("Reference analysis is stale. Re-analyze the reference.")
    return report


def require_fresh_slices(store: ReferenceStore, reference_id: str) -> dict[str, Any]:
    manifest = get_slice_manifest(store, reference_id)
    if manifest.get("status") == "not_generated":
        raise ReferenceAnalysisError("Reference slices have not been generated.")
    if manifest.get("stale"):
        raise ReferenceAnalysisError("Reference slices are stale. Regenerate slices.")
    return manifest


def reference_analysis_summary_for_export(store: ReferenceStore, reference_id: str) -> dict[str, Any]:
    try:
        report = get_analysis_report(store, reference_id)
        slices = get_slice_manifest(store, reference_id)
    except (FileNotFoundError, ValueError):
        return {}
    if report.get("status") not in {"completed", "failed"} or report.get("stale"):
        return {"status": report.get("status", "not_analyzed")}
    summary = dict(report.get("summary") or {})
    if "envelope" in summary and isinstance(summary["envelope"], list):
        summary["envelope_points"] = len(summary["envelope"])
        summary["envelope"] = summary["envelope"][:MAX_EXPORT_ENVELOPE_POINTS]
    roles = []
    if isinstance(summary.get("track_summaries"), list):
        roles = sorted({str(track.get("likely_role")) for track in summary["track_summaries"] if track.get("likely_role")})
        summary["track_summaries"] = [
            {
                "track_index": track.get("track_index"),
                "likely_role": track.get("likely_role"),
                "note_count": track.get("note_count"),
                "pitch_min": track.get("pitch_min"),
                "pitch_max": track.get("pitch_max"),
            }
            for track in summary["track_summaries"][:12]
            if isinstance(track, dict)
        ]
    export_summary = {
        "status": report.get("status"),
        "reference_type": report.get("reference_type"),
        "summary": summary,
        "roles": roles,
        "slice_count": len(slices.get("slices") or []) if not slices.get("stale") else 0,
    }
    return sanitize_metadata(export_summary)


def enrich_reference_refs_with_analysis(store: ReferenceStore, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for ref in refs:
        item = dict(ref)
        summary = reference_analysis_summary_for_export(store, str(ref.get("reference_id") or ""))
        if summary:
            item["analysis_summary"] = summary
        enriched.append(sanitize_metadata(item))
    return enriched


def provider_reference_summaries_with_analysis(store: ReferenceStore, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = 0
    output = []
    for ref in enrich_reference_refs_with_analysis(store, refs):
        data = sanitize_metadata(ref)
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
        warnings = []
        if len(encoded) > MAX_PROVIDER_REFERENCE_SUMMARY_CHARS:
            data = _compact_provider_reference_summary(data)
            encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
            warnings.append("Reference analysis summary was compacted for provider prompt.")
        if total + len(encoded) > MAX_TOTAL_PROVIDER_REFERENCE_SUMMARY_CHARS:
            data = {
                "reference_id": data.get("reference_id"),
                "reference_type": data.get("reference_type"),
                "title": data.get("title"),
                "warnings": ["Reference summary was omitted because provider reference summaries reached the size limit."],
            }
            encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
        if warnings:
            data["warnings"] = [*data.get("warnings", []), *warnings] if isinstance(data.get("warnings"), list) else warnings
        total += len(encoded)
        output.append(data)
    return output


def analysis_path(reference_dir: Path) -> Path:
    return _safe_reference_file(reference_dir, "analysis.json")


def slices_path(reference_dir: Path) -> Path:
    return _safe_reference_file(reference_dir, "slices.json")


def slice_midi_path(reference_dir: Path, slice_id: str) -> Path:
    return _safe_preview_file(reference_dir, f"{_validate_slice_id(slice_id)}.mid")


def slice_audio_path(reference_dir: Path, slice_id: str) -> Path:
    return _safe_preview_file(reference_dir, f"{_validate_slice_id(slice_id)}.wav")


def slice_midi_url(reference_id: str, slice_id: str) -> str:
    return f"/api/references/{reference_id}/slices/{slice_id}/midi"


def slice_audio_url(reference_id: str, slice_id: str) -> str:
    return f"/api/references/{reference_id}/slices/{slice_id}/audio"


def clear_reference_analysis_artifacts(reference_dir: Path, *, keep_analysis: bool) -> None:
    if not keep_analysis:
        path = analysis_path(reference_dir)
        if path.exists():
            path.unlink()
    slice_file = slices_path(reference_dir)
    if slice_file.exists():
        slice_file.unlink()
    preview = _safe_reference_file(reference_dir, "preview")
    if preview.exists():
        if preview.is_symlink():
            raise ReferenceAnalysisError("Refusing to remove symlinked reference preview directory.")
        shutil.rmtree(preview)


def not_analyzed_report(reference: ReferenceItem) -> dict[str, Any]:
    return {
        "schema_version": REFERENCE_ANALYSIS_SCHEMA_VERSION,
        "reference_id": reference.reference_id,
        "reference_type": reference.reference_type,
        "source_sha256": reference.sha256,
        "status": "not_analyzed",
        "summary": {},
        "warnings": [],
        "errors": [],
        "stale": False,
    }


def _analyze_wav(context: ReferenceContext, now: str) -> ImplementationDocument:
    report = _base_report(context.reference, now)
    try:
        with wave.open(str(context.source_path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            frame_rate = wav.getframerate()
            frame_count = wav.getnframes()
            if wav.getcomptype() != "NONE":
                raise ReferenceAnalysisError("Unsupported WAV encoding.")
            if sample_width not in {1, 2, 3, 4}:
                raise ReferenceAnalysisError("Unsupported WAV sample width.")
            raw = wav.readframes(frame_count)
    except (wave.Error, EOFError) as exc:
        report["status"] = "failed"
        report["errors"] = [f"Unsupported WAV encoding: {exc}"]
        return report
    except ReferenceAnalysisError as exc:
        report["status"] = "failed"
        report["errors"] = [str(exc)]
        return report
    samples = _pcm_samples(raw, sample_width)
    if not samples:
        peak = 0.0
        rms = 0.0
        silence_ratio = 1.0
    else:
        peak = max(abs(sample) for sample in samples)
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        silence_ratio = sum(1 for sample in samples if abs(sample) < 0.01) / len(samples)
    summary = {
        "duration_seconds": round(frame_count / frame_rate, 3) if frame_rate else 0.0,
        "sample_rate": frame_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "frame_count": frame_count,
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "loudness_hint": _loudness_hint(rms),
        "silence_ratio": round(silence_ratio, 4),
        "envelope": _wav_envelope(samples, channels, frame_rate),
    }
    if context.reference.tempo_bpm:
        summary["manual_tempo_bpm"] = context.reference.tempo_bpm
    if context.reference.key:
        summary["manual_key"] = context.reference.key
    report["summary"] = summary
    return report


def _analyze_midi(context: ReferenceContext, now: str) -> ImplementationDocument:
    report = _base_report(context.reference, now)
    try:
        midi = parse_midi(context.source_path.read_bytes())
    except MidiParseError as exc:
        report["status"] = "failed"
        report["errors"] = [str(exc)]
        return report
    report["summary"] = midi_summary(midi)
    warnings = list(midi.warnings)
    for track in midi.tracks:
        warnings.extend(track.warnings)
    report["warnings"] = warnings[:40]
    return report


def _analyze_text(context: ReferenceContext, now: str) -> ImplementationDocument:
    report = _base_report(context.reference, now)
    try:
        text = context.source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        report["status"] = "failed"
        report["errors"] = [f"Text reference is not valid UTF-8: {exc}"]
        return report
    clean = sanitize_sensitive_text(text)
    words = _text_words(clean)
    lines = clean.splitlines()
    report["summary"] = sanitize_metadata(
        {
            "character_count": len(clean),
            "line_count": len(lines),
            "word_count": len(words),
            "language_hint": _language_hint(clean),
            "keywords": _keywords(clean, words),
            "safe_excerpt": clean.strip()[:500],
            "contains_chord_like_tokens": bool(_chord_like_tokens(clean)),
            "contains_lyrics_like_lines": sum(1 for line in lines if line.strip()) >= 2,
        }
    )
    return report


def _base_report(reference: ReferenceItem, now: str, *, status: str = "completed", errors: list[str] | None = None) -> ImplementationDocument:
    return {
        "schema_version": REFERENCE_ANALYSIS_SCHEMA_VERSION,
        "reference_id": reference.reference_id,
        "reference_type": reference.reference_type,
        "source_sha256": reference.sha256,
        "status": status,
        "analyzed_at": now,
        "summary": {},
        "warnings": [],
        "errors": list(errors or []),
    }


def _pcm_samples(raw: bytes, sample_width: int) -> list[float]:
    if not raw:
        return []
    samples = []
    step = sample_width
    max_abs = float((1 << (8 * sample_width - 1)) - 1)
    for offset in range(0, len(raw) - step + 1, step):
        chunk = raw[offset : offset + step]
        if sample_width == 1:
            value = int(chunk[0]) - 128
            denom = 128.0
        else:
            value = int.from_bytes(chunk, "little", signed=True)
            denom = max_abs
        samples.append(max(-1.0, min(1.0, value / denom)))
    return samples


def _wav_envelope(samples: list[float], channels: int, sample_rate: int) -> list[dict[str, float]]:
    if not samples:
        return []
    frame_count = max(1, len(samples) // max(1, channels))
    bucket_frames = max(1, math.ceil(frame_count / MAX_ENVELOPE_POINTS))
    bucket_samples = bucket_frames * max(1, channels)
    envelope = []
    for start in range(0, len(samples), bucket_samples):
        bucket = samples[start : start + bucket_samples]
        if not bucket:
            continue
        peak = max(abs(sample) for sample in bucket)
        rms = math.sqrt(sum(sample * sample for sample in bucket) / len(bucket))
        time_value = (start / max(1, channels)) / sample_rate if sample_rate else 0.0
        envelope.append({"time": round(time_value, 3), "peak": round(peak, 4), "rms": round(rms, 4)})
    return envelope[:MAX_ENVELOPE_POINTS]


def _loudness_hint(rms: float) -> str:
    if rms < 0.04:
        return "quiet"
    if rms < 0.2:
        return "medium"
    return "loud"


def _text_words(text: str) -> list[str]:
    return [word.lower() for word in __import__("re").findall(r"[A-Za-z][A-Za-z'-]{2,}", text)]


def _keywords(text: str, words: list[str]) -> list[str]:
    stop_words = {"the", "and", "for", "with", "that", "this", "from", "you", "your", "are", "was", "were", "into", "over", "under"}
    counts: Counter[str] = Counter(word for word in words if word not in stop_words and len(word) > 2)
    zh_tokens = __import__("re").findall(r"[\u4e00-\u9fff]{2,6}", text)
    counts.update(zh_tokens)
    return [word for word, _count in counts.most_common(MAX_TEXT_KEYWORDS)]


def _language_hint(text: str) -> str:
    zh = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    letters = sum(1 for char in text if char.isascii() and char.isalpha())
    if zh > letters:
        return "zh"
    if letters:
        return "en"
    return "unknown"


def _chord_like_tokens(text: str) -> list[str]:
    return __import__("re").findall(r"\b[A-G](?:#|b)?(?:maj7|min7|m7|m|7|sus4|dim)?\b", text)


def _find_slice(manifest: ImplementationDocument, slice_id: str) -> ImplementationDocument:
    slice_id = _validate_slice_id(slice_id)
    for item in manifest.get("slices", []):
        if isinstance(item, dict) and item.get("slice_id") == slice_id:
            return dict(item)
    raise FileNotFoundError(slice_id)


def _update_slice(manifest: ImplementationDocument, slice_id: str, values: ImplementationDocument) -> ImplementationDocument:
    updated = dict(manifest)
    slices = []
    found = False
    for item in manifest.get("slices", []):
        if isinstance(item, dict) and item.get("slice_id") == slice_id:
            slices.append({**item, **values})
            found = True
        else:
            slices.append(item)
    if not found:
        raise FileNotFoundError(slice_id)
    updated["slices"] = slices
    updated["slice_count"] = len(slices)
    return _sanitize_report(updated)


def _export_slice_summary(slice_item: ImplementationDocument) -> ImplementationDocument:
    keys = ["slice_id", "slice_type", "name", "track_index", "channel", "start_beat", "duration_beats", "note_count", "pitch_min", "pitch_max", "quality_hint"]
    return {key: slice_item.get(key) for key in keys if slice_item.get(key) is not None}


def _compact_provider_reference_summary(data: ImplementationDocument) -> ImplementationDocument:
    compact = {
        "reference_id": data.get("reference_id"),
        "reference_type": data.get("reference_type"),
        "title": data.get("title"),
        "role": data.get("role"),
        "strength": data.get("strength"),
    }
    analysis = data.get("analysis_summary")
    if isinstance(analysis, dict):
        compact["analysis_summary"] = {
            "status": analysis.get("status"),
            "reference_type": analysis.get("reference_type"),
            "roles": analysis.get("roles"),
            "slice_count": analysis.get("slice_count"),
            "summary": _compact_analysis_inner(analysis.get("summary")),
        }
    return sanitize_metadata(compact)


def _compact_analysis_inner(summary: Any) -> ImplementationDocument:
    if not isinstance(summary, dict):
        return {}
    allowed = {
        "duration_seconds",
        "duration_beats",
        "sample_rate",
        "channels",
        "loudness_hint",
        "format",
        "track_count",
        "ppq",
        "tempo_bpm",
        "time_signature",
        "note_count",
        "drum_note_count",
        "keywords",
        "safe_excerpt",
    }
    return {key: summary.get(key) for key in allowed if key in summary}


def _asset_notes(notes: list[ImplementationDocument]) -> list[ImplementationDocument]:
    return [
        {
            "pitch": int(note["pitch"]),
            "start_beat": round(float(note["start_beat"]), 3),
            "duration_beats": round(float(note["duration_beats"]), 3),
            "velocity": int(note.get("velocity") or 90),
        }
        for note in notes[:1024]
    ]


def _tempo_from_analysis(store: ReferenceStore, reference_id: str) -> int | None:
    try:
        summary = get_analysis_report(store, reference_id).get("summary") or {}
        tempo = summary.get("tempo_bpm")
        if tempo:
            return max(40, min(240, int(round(float(tempo)))))
    except (OSError, ValueError, TypeError):
        return None
    return None


def _safe_reference_file(reference_dir: Path, name: str) -> Path:
    base = reference_dir.resolve()
    target = (base / name).resolve()
    _ensure_within(base, target)
    return target


def _safe_preview_file(reference_dir: Path, filename: str) -> Path:
    base = _safe_reference_file(reference_dir, "preview")
    target = (base / filename).resolve()
    _ensure_within(base, target)
    return target


def _ensure_within(base: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError as exc:
        raise ReferenceAnalysisError("Refusing to operate outside the reference directory.") from exc


def _validate_slice_id(slice_id: str) -> str:
    text = str(slice_id or "").strip()
    if not __import__("re").fullmatch(r"slice-[0-9]{3,6}", text):
        raise ValueError("Invalid slice id.")
    return text


def _bounded_text(value: Any, max_length: int) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())
    if len(text) > max_length:
        raise ValueError(f"text value must be {max_length} characters or fewer.")
    return text


def _clean_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be a list.")
    tags = []
    for item in value:
        tag = str(item).strip()
        if tag and tag not in tags:
            tags.append(tag[:48])
    return tags[:32]


def _sanitize_report(value: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(value)


def _append_reference_event(reference_dir: Path, event_type: str, payload: ImplementationDocument, timestamp: str | None = None) -> None:
    event = {"timestamp": timestamp or now_iso(), "type": event_type, "payload": sanitize_metadata(payload)}
    reference_dir.mkdir(parents=True, exist_ok=True)
    with (reference_dir / "events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
