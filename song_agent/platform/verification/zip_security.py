from __future__ import annotations

import re
from pathlib import Path, PurePosixPath


_DRIVE_PATH = re.compile(r"^[A-Za-z]:")


def is_safe_zip_entry(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name:
        return False
    if name.startswith("/") or _DRIVE_PATH.match(name):
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if any(part.lower() == ".musicforge" for part in path.parts):
        return False
    return True


def raw_central_directory_entry_names(zip_path: Path | str) -> list[str]:
    data = Path(zip_path).read_bytes()
    names: list[str] = []
    offset = 0
    while True:
        offset = data.find(b"PK\x01\x02", offset)
        if offset < 0:
            break
        if offset + 46 > len(data):
            break
        name_len = int.from_bytes(data[offset + 28 : offset + 30], "little")
        extra_len = int.from_bytes(data[offset + 30 : offset + 32], "little")
        comment_len = int.from_bytes(data[offset + 32 : offset + 34], "little")
        end = offset + 46 + name_len
        if end > len(data):
            break
        names.append(data[offset + 46 : end].decode("utf-8", errors="replace"))
        offset = end + extra_len + comment_len
    return names


def raw_unsafe_entry_names(zip_path: Path | str) -> list[str]:
    return [name for name in raw_central_directory_entry_names(zip_path) if not is_safe_zip_entry(name)]


def zip_has_no_trailing_data(zip_path: Path | str) -> bool:
    data = Path(zip_path).read_bytes()
    signature = b"PK\x05\x06"
    search_start = max(0, len(data) - (65535 + 22))
    offset = data.rfind(signature, search_start)
    if offset < 0 or offset + 22 > len(data):
        return False
    comment_len = int.from_bytes(data[offset + 20 : offset + 22], "little")
    return offset + 22 + comment_len == len(data)
