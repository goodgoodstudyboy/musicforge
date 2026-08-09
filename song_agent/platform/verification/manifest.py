from __future__ import annotations

import re
import zipfile
from collections.abc import Mapping

from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.verification.hashing import sha256_bytes
from song_agent.platform.verification.model import build_check


def manifest_file_checks(
    archive: zipfile.ZipFile,
    manifest: Mapping[str, object],
    *,
    expected_files: set[str],
    check_prefix: str,
) -> list[JsonDocument]:
    file_rows = manifest.get("files")
    rows = [row for row in file_rows if isinstance(row, dict)] if isinstance(file_rows, list) else []
    paths = {str(row.get("path") or "") for row in rows}
    checks = [
        build_check(
            f"{check_prefix}_files_unique",
            len(paths) == len(rows),
            "Manifest file paths are unique.",
        ),
        build_check(
            f"{check_prefix}_files_exact",
            paths == expected_files,
            "Manifest files match the PackageSpec layout.",
            {"missing": sorted(expected_files - paths), "extra": sorted(paths - expected_files)},
        )
    ]
    names = set(archive.namelist())
    for row in rows:
        path = str(row.get("path") or "")
        size_bytes = row.get("size_bytes")
        required_fields = (
            bool(path)
            and isinstance(row.get("sha256"), str)
            and len(str(row.get("sha256"))) == 64
            and isinstance(size_bytes, int)
            and not isinstance(size_bytes, bool)
            and size_bytes >= 0
        )
        checks.append(build_check(f"{check_prefix}_file_{safe_check_key(path)}_fields", required_fields, "Manifest file row includes path, sha256, and size_bytes.", {"entry": path}))
        exists = path in names
        checks.append(build_check(f"{check_prefix}_file_{safe_check_key(path)}_exists", exists, "Manifest file exists in ZIP.", {"entry": path}))
        if exists:
            data = archive.read(path)
            checks.append(build_check(f"{check_prefix}_file_{safe_check_key(path)}_hash", row.get("sha256") == sha256_bytes(data), "Manifest file hash matches ZIP entry.", {"entry": path}))
            checks.append(build_check(f"{check_prefix}_file_{safe_check_key(path)}_size", row.get("size_bytes") == len(data), "Manifest file size matches ZIP entry.", {"entry": path}))
    return checks


def safe_check_key(value: str) -> str:
    return re_sub_non_identifier(value)[:120] or "root"


def re_sub_non_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip("/").replace("/", "_"))
