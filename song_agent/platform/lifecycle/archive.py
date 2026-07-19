from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import json
import shutil
import zipfile
from collections.abc import Mapping
from pathlib import Path

from song_agent.platform.verification.hashing import sha256_file
from song_agent.platform.verification.zip_security import frozen_zip_snapshot_errors, is_safe_zip_entry


class ImmutableSnapshotGuard:
    @staticmethod
    def require_history_or_no_artifacts(history_path: Path, artifact_paths: tuple[Path, ...]) -> None:
        if not history_path.is_file() and any(path.exists() for path in artifact_paths):
            raise ValueError("Lifecycle history is missing while immutable artifacts remain.")

    @staticmethod
    def require_export_matches(export_dir: Path, expected: dict[str, bytes]) -> None:
        if not export_dir.is_dir():
            raise ValueError("Archive export directory is missing.")
        actual = {path.relative_to(export_dir).as_posix() for path in export_dir.rglob("*") if path.is_file()}
        if actual != set(expected):
            raise ValueError("Archive export layout does not match the frozen snapshot.")
        for name, data in expected.items():
            if (export_dir / name).read_bytes() != data:
                raise ValueError(f"Archive export entry changed: {name}")


class ArchiveBuilder:
    @staticmethod
    def export_documents(export_dir: Path, documents: dict[str, DomainDocument | str | bytes]) -> dict[str, bytes]:
        payloads = {name: _serialize(value) for name, value in documents.items()}
        unsafe = sorted(name for name in payloads if not is_safe_zip_entry(name) or name.endswith("/"))
        if unsafe:
            raise ValueError(f"Archive snapshot contains unsafe entry names: {unsafe}")
        if export_dir.exists():
            ImmutableSnapshotGuard.require_export_matches(export_dir, payloads)
            return payloads
        for name, data in payloads.items():
            path = export_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return payloads

    @staticmethod
    def build_zip(export_dir: Path, zip_path: Path, expected: dict[str, bytes]) -> Path:
        ImmutableSnapshotGuard.require_export_matches(export_dir, expected)
        return ArchiveBuilder.build_payload_zip(zip_path, expected)

    @staticmethod
    def build_directory_zip(export_dir: Path, zip_path: Path) -> Path:
        if not export_dir.is_dir():
            raise ValueError("Archive export directory is missing.")
        expected = {
            path.relative_to(export_dir).as_posix(): path.read_bytes()
            for path in sorted(export_dir.rglob("*"))
            if path.is_file() and path.resolve() != zip_path.resolve()
        }
        return ArchiveBuilder.build_payload_zip(zip_path, expected)

    @staticmethod
    def build_payload_zip(
        zip_path: Path,
        documents: Mapping[str, DomainDocument | str | bytes],
    ) -> Path:
        expected = {name: _serialize(value) for name, value in documents.items()}
        unsafe = sorted(name for name in expected if not is_safe_zip_entry(name) or name.endswith("/"))
        if unsafe:
            raise ValueError(f"Archive snapshot contains unsafe entry names: {unsafe}")
        if zip_path.exists():
            errors = frozen_zip_snapshot_errors(zip_path, expected)
            if errors:
                raise ValueError(f"Existing archive ZIP does not match the frozen snapshot: {', '.join(errors)}.")
            return zip_path
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        temp = zip_path.with_suffix(zip_path.suffix + ".tmp")
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(expected):
                archive.writestr(name, expected[name])
        temp.replace(zip_path)
        errors = frozen_zip_snapshot_errors(zip_path, expected)
        if errors:
            raise ValueError(f"Built archive ZIP does not match the frozen snapshot: {', '.join(errors)}.")
        return zip_path

    @staticmethod
    def copy_frozen(source: Path, target: Path, *, expected_sha256: str) -> Path:
        if sha256_file(source) != expected_sha256:
            raise ValueError("Frozen source fingerprint mismatch.")
        if target.exists():
            if sha256_file(target) != expected_sha256:
                raise ValueError("Existing frozen target fingerprint mismatch.")
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target


def _serialize(value: ImplementationDocument | str | bytes) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
