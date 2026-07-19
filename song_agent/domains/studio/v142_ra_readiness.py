# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts.documents import DomainDocument
import hashlib as hashlib
import json as json
import math as math
import shutil as shutil
import wave as wave
from collections import Counter as Counter
from dataclasses import dataclass as dataclass
from pathlib import Path as Path
from song_agent.domains.studio.assets import AssetStore as AssetStore, asset_public_dict as asset_public_dict
from song_agent.domains.creation.midi_analysis import MidiParseError as MidiParseError, midi_summary as midi_summary, notes_for_slice as notes_for_slice, parse_midi as parse_midi, render_slice_midi as render_slice_midi, suggest_slices as suggest_slices
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.studio.reference_paths import reference_file_path as reference_file_path
from song_agent.domains.creation.renderers.audio import RendererConfig as RendererConfig, RendererError as RendererError, render_audio as render_audio

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

ReferenceAnalysisError = _make_deferred_global('ReferenceAnalysisError')
char = _make_deferred_global('char')
get_analysis_report = _make_deferred_global('get_analysis_report')
key = _make_deferred_global('key')
note = _make_deferred_global('note')
sample = _make_deferred_global('sample')
word = _make_deferred_global('word')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReferenceAnalysisError, char, get_analysis_report, key, note, sample, word
    ReferenceAnalysisError = namespace.get('ReferenceAnalysisError', ReferenceAnalysisError)
    char = namespace.get('char', char)
    get_analysis_report = namespace.get('get_analysis_report', get_analysis_report)
    key = namespace.get('key', key)
    note = namespace.get('note', note)
    sample = namespace.get('sample', sample)
    word = namespace.get('word', word)
    _bind_deferred_defaults(namespace)


REFERENCE_ANALYSIS_SCHEMA_VERSION = 1
REFERENCE_SLICES_SCHEMA_VERSION = 1
MAX_ENVELOPE_POINTS = 256
MAX_TEXT_KEYWORDS = 20
MAX_PROVIDER_REFERENCE_SUMMARY_CHARS = 2_000
MAX_TOTAL_PROVIDER_REFERENCE_SUMMARY_CHARS = 6_000
MAX_EXPORT_ENVELOPE_POINTS = 16




def _base_report(reference: object, now: str, *, status: str = "completed", errors: list[str] | None = None) -> DomainDocument:
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

def _find_slice(manifest: DomainDocument, slice_id: str) -> DomainDocument:
    slice_id = _validate_slice_id(slice_id)
    for item in manifest.get("slices", []):
        if isinstance(item, dict) and item.get("slice_id") == slice_id:
            return dict(item)
    raise FileNotFoundError(slice_id)

def _update_slice(manifest: DomainDocument, slice_id: str, values: DomainDocument) -> DomainDocument:
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

def _export_slice_summary(slice_item: DomainDocument) -> DomainDocument:
    keys = ["slice_id", "slice_type", "name", "track_index", "channel", "start_beat", "duration_beats", "note_count", "pitch_min", "pitch_max", "quality_hint"]
    return {key: slice_item.get(key) for key in keys if slice_item.get(key) is not None}

def _compact_provider_reference_summary(data: DomainDocument) -> DomainDocument:
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

def _compact_analysis_inner(summary: object) -> DomainDocument:
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

def _asset_notes(notes: list[DomainDocument]) -> list[DomainDocument]:
    return [
        {
            "pitch": int(note["pitch"]),
            "start_beat": round(float(note["start_beat"]), 3),
            "duration_beats": round(float(note["duration_beats"]), 3),
            "velocity": int(note.get("velocity") or 90),
        }
        for note in notes[:1024]
    ]

def _tempo_from_analysis(store: object, reference_id: str) -> int | None:
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

def _bounded_text(value: object, max_length: int) -> str:
    text = sanitize_sensitive_text(str(value or "").strip())
    if len(text) > max_length:
        raise ValueError(f"text value must be {max_length} characters or fewer.")
    return text

def _clean_tags(value: object) -> list[str]:
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

def _sanitize_report(value: DomainDocument) -> DomainDocument:
    return sanitize_metadata(value)

def _append_reference_event(reference_dir: Path, event_type: str, payload: DomainDocument, timestamp: str | None = None) -> None:
    event = {"timestamp": timestamp or now_iso(), "type": event_type, "payload": sanitize_metadata(payload)}
    reference_dir.mkdir(parents=True, exist_ok=True)
    with (reference_dir / "events.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
