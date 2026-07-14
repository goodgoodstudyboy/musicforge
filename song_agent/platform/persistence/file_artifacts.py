from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any


class FileArtifactStore:
    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.state_root = self.workspace_root / "state"
        self.transactions_root = self.state_root / "transactions"
        self.artifacts_root = self.state_root / "artifacts"

    def transaction_dir(self, transaction_id: str) -> Path:
        return self.transactions_root / _safe_segment(transaction_id)

    def staging_dir(self, transaction_id: str) -> Path:
        return self.transaction_dir(transaction_id) / "staging"

    def intent_path(self, transaction_id: str) -> Path:
        return self.transaction_dir(transaction_id) / "intent.json"

    def marker_path(self, transaction_id: str) -> Path:
        return self.transaction_dir(transaction_id) / "commit.marker"

    def generation_dir(self, namespace: str, generation_id: str) -> Path:
        return self.artifacts_root / _safe_segment(namespace) / "generations" / _safe_segment(generation_id)

    def current_pointer_path(self, namespace: str) -> Path:
        return self.artifacts_root / _safe_segment(namespace) / "current.json"

    def write_staged(self, transaction_id: str, relative_path: str, data: bytes) -> dict[str, Any]:
        relative = _safe_relative(relative_path)
        staging = self.staging_dir(transaction_id)
        path = staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.resolve().is_relative_to(staging.resolve()):
            raise ValueError("Artifact path escapes the transaction staging directory.")
        path.write_bytes(data)
        return {"path": relative.as_posix(), "sha256": sha256_path(path), "size_bytes": len(data)}

    def write_staged_json(self, transaction_id: str, relative_path: str, value: dict[str, Any]) -> dict[str, Any]:
        return self.write_staged(
            transaction_id,
            relative_path,
            (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )

    def fingerprint_tree(self, root: Path) -> list[dict[str, Any]]:
        if not root.is_dir():
            return []
        return [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_path(path),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(item for item in root.rglob("*") if item.is_file())
        ]

    def verify_tree(self, root: Path, expected: list[dict[str, Any]]) -> bool:
        return self.fingerprint_tree(root) == sorted(expected, key=lambda row: str(row.get("path") or ""))

    def read_pointer(self, namespace: str) -> dict[str, Any]:
        path = self.current_pointer_path(namespace)
        if not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}

    def write_pointer_atomic(self, namespace: str, value: dict[str, Any]) -> Path:
        path = self.current_pointer_path(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(path)
        return path


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_tree_hash(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(sorted(rows, key=lambda row: str(row.get("path") or "")), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json_atomic(path: Path | str, value: Any) -> Path:
    """Write a JSON projection atomically without depending on legacy project I/O."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".tmp-{os.getpid()}-{threading.get_ident()}.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def read_json_document(path: Path | str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object.")
    return value


def _safe_relative(value: str) -> Path:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise ValueError("Artifact path must be a safe relative path.")
    return path


def _safe_segment(value: str) -> str:
    if not value or value in {".", ".."} or any(char in value for char in "/\\:"):
        raise ValueError("Persistence identifier is invalid.")
    return value
