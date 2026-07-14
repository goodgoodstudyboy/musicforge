from __future__ import annotations

import re
import stat
import zipfile
import zlib
from collections.abc import Mapping
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


def is_regular_zip_entry(info: zipfile.ZipInfo) -> bool:
    if info.is_dir() or not is_safe_zip_entry(info.filename):
        return False
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    return file_type in (0, stat.S_IFREG)


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


def frozen_zip_snapshot_errors(zip_path: Path | str, expected: Mapping[str, bytes]) -> list[str]:
    target = Path(zip_path)
    errors: list[str] = []
    expected_names = sorted(expected)
    if not target.is_file():
        return ["missing"]
    if not zip_has_no_trailing_data(target):
        errors.append("trailing data")
    raw_names = raw_central_directory_entry_names(target)
    if raw_names != expected_names:
        errors.append("raw entry layout")
    try:
        with zipfile.ZipFile(target) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("duplicate entries")
            if names != expected_names:
                errors.append("entry layout or order")
            for info in infos:
                if not is_regular_zip_entry(info):
                    errors.append(f"non-regular entry:{info.filename}")
                    continue
                expected_data = expected.get(info.filename)
                if expected_data is None:
                    continue
                if info.file_size != len(expected_data):
                    errors.append(f"entry size:{info.filename}")
                if info.CRC != (zlib.crc32(expected_data) & 0xFFFFFFFF):
                    errors.append(f"entry crc:{info.filename}")
                try:
                    actual_data = archive.read(info)
                except (OSError, RuntimeError, zipfile.BadZipFile):
                    errors.append(f"entry readable:{info.filename}")
                    continue
                if actual_data != expected_data:
                    errors.append(f"entry content:{info.filename}")
    except (OSError, zipfile.BadZipFile):
        errors.append("readable")
    return sorted(set(errors))
