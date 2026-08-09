from __future__ import annotations

from song_agent.platform.contracts.coercion import JsonDocument, as_document as _as_document

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Mapping, Sequence, cast

from song_agent.platform.resource_access import PackagedResource, read_packaged_text
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok


STATE_POLICY_RESOURCE = ("runtime-state-authority-policy.json", "36f09b71009a715d8e559da9933d226d2d616ca18e89aef813c987483629c52b")
RUNTIME_STATE_AUTHORITY_POLICY_TYPE = "musicforge_v144_runtime_state_authority_policy"


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

    def write_staged(self, transaction_id: str, relative_path: str, data: bytes) -> JsonDocument:
        relative = _safe_relative(relative_path)
        staging = self.staging_dir(transaction_id)
        path = staging / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.resolve().is_relative_to(staging.resolve()):
            raise ValueError("Artifact path escapes the transaction staging directory.")
        path.write_bytes(data)
        return {"path": relative.as_posix(), "sha256": sha256_path(path), "size_bytes": len(data)}

    def write_staged_json(self, transaction_id: str, relative_path: str, value: Mapping[str, object]) -> JsonDocument:
        return self.write_staged(
            transaction_id,
            relative_path,
            (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )

    def fingerprint_tree(self, root: Path) -> list[JsonDocument]:
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

    def verify_tree(self, root: Path, expected: Sequence[Mapping[str, object]]) -> bool:
        return self.fingerprint_tree(root) == sorted(expected, key=lambda row: str(row.get("path") or ""))

    def read_pointer(self, namespace: str) -> JsonDocument:
        path = self.current_pointer_path(namespace)
        if not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return _as_document(value)

    def write_pointer_atomic(self, namespace: str, value: Mapping[str, object]) -> Path:
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


def stable_tree_hash(rows: Sequence[Mapping[str, object]]) -> str:
    payload = json.dumps(sorted(rows, key=lambda row: str(row.get("path") or "")), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_json_atomic(path: Path | str, value: object) -> Path:
    """Write a JSON projection atomically without depending on legacy project I/O."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".tmp-{os.getpid()}-{threading.get_ident()}.json")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def read_json_document(path: Path | str) -> JsonDocument:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object.")
    return value


def build_runtime_state_authority_policy(registry: dict[str, object], baseline: dict[str, object]) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": 1,
        "package_type": RUNTIME_STATE_AUTHORITY_POLICY_TYPE,
        "state_registry_integrity_hash": registry.get("integrity_hash"),
        "baseline_integrity_hash": baseline.get("integrity_hash"),
        "state_registry": registry,
        "wave0_baseline": baseline,
    }
    document["integrity_hash"] = integrity_hash(document)
    return document


def load_runtime_state_authority_policy() -> tuple[dict[str, object], str, list[str]]:
    try:
        text = read_packaged_text(PackagedResource.STATE_AUTHORITY_POLICY)
        value = json.loads(text)
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return {}, "", ["v144_wave0_state_runtime_policy_missing"]
    if not isinstance(value, dict):
        return {}, "", ["v144_wave0_state_runtime_policy_shape"]
    policy = cast(dict[str, object], value)
    blockers = validate_runtime_state_authority_policy(policy)
    if blockers:
        return {}, "", blockers
    registry = cast(dict[str, object], policy["state_registry"])
    baseline = cast(dict[str, object], policy["wave0_baseline"])
    return registry, str(baseline["integrity_hash"]), []


def validate_runtime_state_authority_policy(policy: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    if (
        policy.get("integrity_hash") != STATE_POLICY_RESOURCE[1]
        or policy.get("package_type") != RUNTIME_STATE_AUTHORITY_POLICY_TYPE
        or policy.get("schema_version") != 1
        or not integrity_ok(policy)
    ):
        blockers.append("v144_wave0_state_runtime_policy_integrity")
    registry = policy.get("state_registry")
    baseline = policy.get("wave0_baseline")
    if not isinstance(registry, dict) or not isinstance(baseline, dict):
        return sorted(set([*blockers, "v144_wave0_state_runtime_policy_documents"]))
    roots = registry.get("roots")
    entries = registry.get("entries")
    exceptions = registry.get("writer_overlap_exceptions")
    if (
        registry.get("package_type") != "musicforge_v144_state_authority_registry"
        or registry.get("schema_version") != 4
        or not integrity_ok(registry)
        or not isinstance(roots, list)
        or not roots
        or not isinstance(entries, list)
        or not entries
        or not isinstance(exceptions, list)
    ):
        blockers.append("v144_wave0_state_runtime_registry_integrity")
    if (
        baseline.get("package_type") != "musicforge_v144_wave0_baseline"
        or baseline.get("schema_version") != 5
        or baseline.get("status") != "frozen"
        or not integrity_ok(baseline)
    ):
        blockers.append("v144_wave0_state_runtime_baseline_integrity")
    registry_hash = str(registry.get("integrity_hash") or "")
    baseline_hash = str(baseline.get("integrity_hash") or "")
    if policy.get("state_registry_integrity_hash") != registry_hash or policy.get("baseline_integrity_hash") != baseline_hash:
        blockers.append("v144_wave0_state_runtime_policy_binding")
    freeze = baseline.get("registry_freeze")
    if not isinstance(freeze, dict) or any(
        freeze.get(key) != value for key, value in _runtime_state_freeze(cast(dict[str, object], registry)).items()
    ):
        blockers.append("v144_wave0_state_runtime_baseline_binding")
    if isinstance(exceptions, list) and any(
        not isinstance(row, dict) or row.get("baseline_integrity_hash") != baseline_hash for row in exceptions
    ):
        blockers.append("v144_wave0_state_runtime_exception_binding")
    return sorted(set(blockers))


def _runtime_state_freeze(registry: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for target, key, identity, excluded in (
        ("state", "entries", "store_id", set()),
        ("state_roots", "roots", "root_authority_id", set()),
        ("state_overlap_exceptions", "writer_overlap_exceptions", "exception_id", {"baseline_integrity_hash"}),
    ):
        rows = cast(list[dict[str, object]], registry.get(key) or [])
        result[target] = {
            str(row.get(identity) or ""): {field: value for field, value in row.items() if field not in {identity, *excluded}}
            for row in rows
        }
    return result


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
