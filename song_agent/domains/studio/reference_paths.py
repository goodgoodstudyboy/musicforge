from __future__ import annotations

from pathlib import Path
from typing import Any


def reference_file_path(reference_dir: Path, reference: Any) -> Path:
    base = (reference_dir / "original").resolve()
    filename = stored_reference_filename(
        str(reference.reference_type),
        str(reference.extension),
    )
    target = (base / filename).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside reference original directory.") from exc
    return target


def stored_reference_filename(reference_type: str, extension: str) -> str:
    if reference_type == "audio_wav":
        return "reference.wav"
    if reference_type == "midi":
        return "reference.mid"
    return "reference.md" if extension == ".md" else "reference.txt"
