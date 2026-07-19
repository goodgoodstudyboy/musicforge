from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import hashlib as hashlib
import io as io
import math as math
import wave as wave
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.quality.mix_controls import stable_hash as stable_hash


AUDIO_HEALTH_SCHEMA_VERSION = 1
DEFAULT_MIN_DURATION_SECONDS = 8.0
DEFAULT_MAX_DURATION_SECONDS = 600.0
DEFAULT_MIN_PEAK = 0.001
DEFAULT_MIN_RMS = 0.005
DEFAULT_NEAR_SILENCE_THRESHOLD = 0.001
DEFAULT_CLIPPING_WARNING_RATIO = 0.001
DEFAULT_CLIPPING_FAILURE_RATIO = 0.01
DEFAULT_LEADING_SILENCE_WARNING_SECONDS = 5.0
DEFAULT_TRAILING_SILENCE_WARNING_SECONDS = 8.0

INTEGRITY_EXCLUDE_KEYS = {"integrity_hash"}


def analyze_wav_health(
    wav_path: str | Path,
    *,
    source: DomainDocument | None = None,
    expected_sample_rate: int | None = None,
    expected_channels: int | None = None,
    expected_bit_depth: int | None = None,
    expected_duration_seconds: float | None = None,
    report_id: str | None = None,
    now: str | None = None,
) -> DomainDocument:
    path = Path(wav_path)
    source = source or {}
    now = now or now_iso()
    base = {
        "schema_version": AUDIO_HEALTH_SCHEMA_VERSION,
        "report_id": report_id or _default_report_id(path),
        "generated_at": now,
        "source": sanitize_metadata(source),
    }
    if not path.exists() or not path.is_file() or path.is_symlink():
        return _finalize_report({**base, "status": "failed", "wav_sha256": None, "format": {}, "metrics": {}, "checks": [_check("wav_exists", "failed", "WAV file is missing.")], "warnings": [], "failures": ["wav_missing"]})
    data = path.read_bytes()
    return analyze_wav_bytes(
        data,
        filename=path.name,
        source=source,
        expected_sample_rate=expected_sample_rate,
        expected_channels=expected_channels,
        expected_bit_depth=expected_bit_depth,
        expected_duration_seconds=expected_duration_seconds,
        report_id=report_id or _default_report_id(path),
        now=now,
    )


def analyze_wav_bytes(
    data: bytes,
    *,
    filename: str = "song.wav",
    source: DomainDocument | None = None,
    expected_sample_rate: int | None = None,
    expected_channels: int | None = None,
    expected_bit_depth: int | None = None,
    expected_duration_seconds: float | None = None,
    report_id: str | None = None,
    now: str | None = None,
) -> DomainDocument:
    source = source or {}
    now = now or now_iso()
    checks: list[ImplementationDocument] = []
    warnings: list[str] = []
    failures: list[str] = []
    base = {
        "schema_version": AUDIO_HEALTH_SCHEMA_VERSION,
        "report_id": report_id or _default_report_id(filename),
        "generated_at": now,
        "source": sanitize_metadata(source),
        "wav_sha256": hashlib.sha256(data).hexdigest(),
    }
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            sample_width = wav.getsampwidth()
            frame_count = wav.getnframes()
            pcm = wav.readframes(frame_count)
            compression = wav.getcomptype()
    except (wave.Error, EOFError, OSError) as exc:
        checks.append(_check("wav_header", "failed", f"Invalid WAV header: {exc}"))
        failures.append("wav_header")
        return _finalize_report({**base, "status": "failed", "format": {}, "metrics": {}, "checks": checks, "warnings": warnings, "failures": failures})

    duration = frame_count / sample_rate if sample_rate else 0.0
    bit_depth = sample_width * 8
    fmt = {
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "bit_depth": bit_depth,
        "duration_seconds": round(duration, 3),
        "frame_count": frame_count,
        "compression": compression,
    }
    if compression != "NONE":
        checks.append(_check("wav_header", "failed", f"Unsupported WAV compression: {compression}."))
        failures.append("wav_compression")
    else:
        checks.append(_check("wav_header", "passed", "Valid PCM WAV."))

    metrics = _pcm_metrics(pcm, channels=channels, sample_width=sample_width, sample_rate=sample_rate)
    _check_expected(checks, warnings, failures, "sample_rate", sample_rate, expected_sample_rate, "sample rate")
    _check_expected(checks, warnings, failures, "channels", channels, expected_channels, "channel count")
    _check_expected(checks, warnings, failures, "bit_depth", bit_depth, expected_bit_depth, "bit depth")
    if duration < DEFAULT_MIN_DURATION_SECONDS:
        checks.append(_check("duration_min", "failed", f"WAV duration {duration:.2f}s is below {DEFAULT_MIN_DURATION_SECONDS:.0f}s."))
        failures.append("duration_too_short")
    elif duration > DEFAULT_MAX_DURATION_SECONDS:
        checks.append(_check("duration_max", "warning", f"WAV duration {duration:.2f}s exceeds {DEFAULT_MAX_DURATION_SECONDS:.0f}s."))
        warnings.append("duration_long")
    else:
        checks.append(_check("duration_range", "passed", "WAV duration is within the expected baseline range."))
    if expected_duration_seconds and duration:
        ratio = abs(duration - expected_duration_seconds) / max(expected_duration_seconds, 1.0)
        if ratio > 0.25:
            checks.append(_check("duration_match", "failed", f"WAV duration differs from expected duration by {ratio:.1%}."))
            failures.append("duration_mismatch")
        elif ratio > 0.10:
            checks.append(_check("duration_match", "warning", f"WAV duration differs from expected duration by {ratio:.1%}."))
            warnings.append("duration_mismatch")
        else:
            checks.append(_check("duration_match", "passed", "WAV duration is close to expected duration."))
    peak = float(metrics.get("peak") or 0.0)
    rms = float(metrics.get("rms") or 0.0)
    clipping_ratio = float(metrics.get("clipping_ratio") or 0.0)
    if peak <= DEFAULT_MIN_PEAK:
        checks.append(_check("peak_level", "failed", "WAV peak is effectively silent."))
        failures.append("peak_silent")
    else:
        checks.append(_check("peak_level", "passed", "WAV has non-silent peak level."))
    if rms <= DEFAULT_MIN_RMS:
        checks.append(_check("rms_level", "failed", "WAV RMS is too low."))
        failures.append("rms_too_low")
    else:
        checks.append(_check("rms_level", "passed", "WAV RMS is above the minimum threshold."))
    if clipping_ratio > DEFAULT_CLIPPING_FAILURE_RATIO:
        checks.append(_check("clipping_ratio", "failed", f"WAV clipping ratio is {clipping_ratio:.4f}."))
        failures.append("clipping_severe")
    elif clipping_ratio > DEFAULT_CLIPPING_WARNING_RATIO:
        checks.append(_check("clipping_ratio", "warning", f"WAV clipping ratio is {clipping_ratio:.4f}."))
        warnings.append("clipping_warning")
    else:
        checks.append(_check("clipping_ratio", "passed", "WAV clipping ratio is within threshold."))
    if float(metrics.get("leading_silence_seconds") or 0.0) > DEFAULT_LEADING_SILENCE_WARNING_SECONDS:
        checks.append(_check("leading_silence", "warning", "WAV has long leading silence."))
        warnings.append("leading_silence")
    else:
        checks.append(_check("leading_silence", "passed", "WAV leading silence is acceptable."))
    if float(metrics.get("trailing_silence_seconds") or 0.0) > DEFAULT_TRAILING_SILENCE_WARNING_SECONDS:
        checks.append(_check("trailing_silence", "warning", "WAV has long trailing silence."))
        warnings.append("trailing_silence")
    else:
        checks.append(_check("trailing_silence", "passed", "WAV trailing silence is acceptable."))
    status = "failed" if failures else "warning" if warnings else "passed"
    return _finalize_report({**base, "status": status, "format": fmt, "metrics": metrics, "checks": checks, "warnings": warnings, "failures": failures})


def audio_health_summary(report: DomainDocument) -> DomainDocument:
    fmt = _as_document(report.get("format"))
    metrics = _as_document(report.get("metrics"))
    return sanitize_metadata(
        {
            "status": report.get("status") or "missing",
            "report_id": report.get("report_id"),
            "wav_sha256": report.get("wav_sha256"),
            "duration_seconds": fmt.get("duration_seconds"),
            "sample_rate": fmt.get("sample_rate"),
            "channels": fmt.get("channels"),
            "bit_depth": fmt.get("bit_depth"),
            "peak": metrics.get("peak"),
            "rms": metrics.get("rms"),
            "clipping_ratio": metrics.get("clipping_ratio"),
            "warning_count": len(report.get("warnings", [])) if isinstance(report.get("warnings"), list) else 0,
            "failure_count": len(report.get("failures", [])) if isinstance(report.get("failures"), list) else 0,
            "integrity_hash": report.get("integrity_hash"),
        }
    )


def audio_health_allows_release(report: DomainDocument) -> bool:
    if not report:
        return False
    return str(report.get("status") or "") in {"passed", "warning"} and bool(report.get("wav_sha256"))


def audio_health_integrity_hash(report: DomainDocument) -> str:
    core = {key: value for key, value in report.items() if key not in INTEGRITY_EXCLUDE_KEYS}
    return stable_hash(sanitize_metadata(core))


def audio_health_integrity_ok(report: DomainDocument) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == audio_health_integrity_hash(report)


def _pcm_metrics(pcm: bytes, *, channels: int, sample_width: int, sample_rate: int) -> ImplementationDocument:
    if channels <= 0 or sample_width not in {1, 2, 3, 4} or not pcm:
        return {
            "peak": 0.0,
            "rms": 0.0,
            "clipping_ratio": 0.0,
            "near_silence_ratio": 1.0,
            "leading_silence_seconds": 0.0,
            "trailing_silence_seconds": 0.0,
            "dc_offset": 0.0,
        }
    frame_size = sample_width * channels
    frame_count = len(pcm) // frame_size
    if frame_count <= 0:
        return {
            "peak": 0.0,
            "rms": 0.0,
            "clipping_ratio": 0.0,
            "near_silence_ratio": 1.0,
            "leading_silence_seconds": 0.0,
            "trailing_silence_seconds": 0.0,
            "dc_offset": 0.0,
        }
    max_raw = float(127 if sample_width == 1 else (2 ** (sample_width * 8 - 1) - 1))
    clipping_raw = max_raw * 0.999
    total_samples = frame_count * channels
    sum_sq = 0.0
    sum_norm = 0.0
    peak = 0.0
    clipping = 0
    near_silent = 0
    frame_levels: list[float] = []
    for frame_index in range(frame_count):
        frame_peak = 0.0
        base = frame_index * frame_size
        for channel_index in range(channels):
            offset = base + channel_index * sample_width
            raw = _decode_sample(pcm[offset : offset + sample_width], sample_width)
            norm = raw / max_raw if max_raw else 0.0
            abs_norm = abs(norm)
            peak = max(peak, abs_norm)
            frame_peak = max(frame_peak, abs_norm)
            sum_sq += norm * norm
            sum_norm += norm
            if abs(raw) >= clipping_raw:
                clipping += 1
            if abs_norm <= DEFAULT_NEAR_SILENCE_THRESHOLD:
                near_silent += 1
        frame_levels.append(frame_peak)
    leading = 0
    for level in frame_levels:
        if level <= DEFAULT_NEAR_SILENCE_THRESHOLD:
            leading += 1
        else:
            break
    trailing = 0
    for level in reversed(frame_levels):
        if level <= DEFAULT_NEAR_SILENCE_THRESHOLD:
            trailing += 1
        else:
            break
    return {
        "peak": round(min(peak, 1.0), 6),
        "rms": round(math.sqrt(sum_sq / total_samples), 6) if total_samples else 0.0,
        "clipping_ratio": round(clipping / total_samples, 6) if total_samples else 0.0,
        "near_silence_ratio": round(near_silent / total_samples, 6) if total_samples else 1.0,
        "leading_silence_seconds": round(leading / sample_rate, 3) if sample_rate else 0.0,
        "trailing_silence_seconds": round(trailing / sample_rate, 3) if sample_rate else 0.0,
        "dc_offset": round(sum_norm / total_samples, 6) if total_samples else 0.0,
    }


def _decode_sample(data: bytes, sample_width: int) -> int:
    if sample_width == 1:
        return int(data[0]) - 128
    return int.from_bytes(data, byteorder="little", signed=True)


def _check(check_id: str, status: str, message: str) -> ImplementationDocument:
    return {"id": check_id, "status": status, "message": message}


def _check_expected(checks: list[ImplementationDocument], warnings: list[str], failures: list[str], check_id: str, actual: int, expected: int | None, label: str) -> None:
    if expected is None:
        return
    if actual == expected:
        checks.append(_check(check_id, "passed", f"WAV {label} matches expected {expected}."))
    else:
        checks.append(_check(check_id, "failed", f"WAV {label} is {actual}, expected {expected}."))
        failures.append(f"{check_id}_mismatch")


def _finalize_report(report: ImplementationDocument) -> ImplementationDocument:
    source = _as_document(report.get("source"))
    source_payload = {
        "source": source,
        "wav_sha256": report.get("wav_sha256"),
        "format": _as_document(report.get("format")),
    }
    report["source_hash"] = stable_hash(sanitize_metadata(source_payload))
    report["integrity_hash"] = audio_health_integrity_hash(report)
    return sanitize_metadata(report)


def _default_report_id(value: str | Path) -> str:
    name = Path(value).name if not isinstance(value, str) else Path(value).name
    digest = hashlib.sha256(name.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"ahr-{digest}"
