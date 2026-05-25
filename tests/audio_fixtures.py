from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def write_test_wav(path: Path, *, duration_seconds: float = 9.0, sample_rate: int = 44100, amplitude: float = 0.25) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frame_count):
            value = int(amplitude * 32767 * math.sin(2 * math.pi * 440 * (index / sample_rate)))
            frame = struct.pack("<hh", value, value)
            wav.writeframesraw(frame)
    return path


def write_silent_wav(path: Path, *, duration_seconds: float = 9.0, sample_rate: int = 44100) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00\x00\x00" * frame_count)
    return path
