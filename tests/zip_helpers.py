from __future__ import annotations

from pathlib import Path
from typing import Callable
import zipfile


def rewrite_zip(source_zip: Path, target_zip: Path, mutate: Callable[[dict[str, bytes]], None]) -> Path:
    with zipfile.ZipFile(source_zip, "r") as source:
        documents = {info.filename: source.read(info.filename) for info in source.infolist()}
    mutate(documents)
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, data in documents.items():
            target.writestr(name, data)
    return target_zip


_v76_rewrite_zip = rewrite_zip


__all__ = ["rewrite_zip", "_v76_rewrite_zip"]
