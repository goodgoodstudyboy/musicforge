from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath, PurePosixPath
from typing import cast

from song_agent.platform.contracts.coercion import as_document as _as_document
from song_agent.platform.persistence.database import MusicForgeDatabase
from song_agent.platform.verification.hashing import integrity_ok
from song_agent.platform.version import VERSION


@dataclass(frozen=True)
class WorkflowRecord:
    object_type: str
    object_id: str
    generation: int
    status: str
    version: int
    payload_hash: str
    updated_at: str


class WorkflowRepository:
    def __init__(self, database: MusicForgeDatabase) -> None:
        self.database = database
        self.database.initialize()

    def get(self, object_type: str, object_id: str) -> WorkflowRecord | None:
        with self.database.session() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
        return _record(row) if row else None

    def save(
        self,
        object_type: str,
        object_id: str,
        *,
        generation: int,
        status: str,
        payload_hash: str = "",
        expected_version: int | None = None,
    ) -> WorkflowRecord:
        with self.database.transaction() as connection:
            current = connection.execute(
                "SELECT version FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
            current_version = int(current[0]) if current else 0
            if expected_version is not None and current_version != expected_version:
                raise RuntimeError("Workflow record changed concurrently.")
            version = current_version + 1
            connection.execute(
                """
                INSERT INTO workflow_objects(object_type, object_id, generation, status, version, payload_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(object_type, object_id) DO UPDATE SET
                    generation=excluded.generation,
                    status=excluded.status,
                    version=excluded.version,
                    payload_hash=excluded.payload_hash,
                    updated_at=excluded.updated_at
                """,
                (object_type, object_id, int(generation), status, version, payload_hash, _now()),
            )
            row = connection.execute(
                "SELECT * FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
        return _record(row)

    def next_id(self, namespace: str, *, prefix: str) -> str:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT next_value FROM id_counters WHERE namespace=?", (namespace,)).fetchone()
            value = int(row[0]) if row else 1
            connection.execute(
                "INSERT INTO id_counters(namespace, next_value) VALUES (?, ?) ON CONFLICT(namespace) DO UPDATE SET next_value=excluded.next_value",
                (namespace, value + 1),
            )
        return f"{prefix}{value:06d}"


def _record(row: sqlite3.Row) -> WorkflowRecord:
    return WorkflowRecord(
        object_type=str(row["object_type"]),
        object_id=str(row["object_id"]),
        generation=int(row["generation"]),
        status=str(row["status"]),
        version=int(row["version"]),
        payload_hash=str(row["payload_hash"]),
        updated_at=str(row["updated_at"]),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def namespace_identity_hash(store_id: str, namespace: dict[str, object]) -> str:
    evidence = _as_document(namespace.get("path_evidence"))
    payload = {
        "store_id": store_id,
        "root_authority_id": namespace.get("root_authority_id"),
        "relative_path_template": namespace.get("relative_path_template"),
        "source": evidence.get("source"),
        "source_evidence_schema_version": evidence.get("source_evidence_schema_version"),
        "line": evidence.get("line"),
        "column": evidence.get("column"),
        "end_line": evidence.get("end_line"),
        "end_column": evidence.get("end_column"),
        "expression_source_hash": evidence.get("expression_source_hash"),
        "relative_path_template_hash": evidence.get("relative_path_template_hash"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_runtime_state_composition(
    registry: dict[str, object],
    composition: object,
    workspace: Path,
    *,
    baseline_integrity_hash: str | None = None,
) -> list[str]:
    contract_blockers = _runtime_registry_contract_blockers(registry, baseline_integrity_hash)
    if contract_blockers:
        return contract_blockers
    resolved, blockers = resolve_runtime_state_roots(registry, composition, workspace)
    blockers.extend(
        validate_runtime_state_namespaces(
            registry,
            resolved,
            baseline_integrity_hash=baseline_integrity_hash,
        )
    )
    return sorted(set(blockers))


def _runtime_registry_contract_blockers(
    registry: dict[str, object], baseline_integrity_hash: str | None
) -> list[str]:
    roots = registry.get("roots")
    entries = registry.get("entries")
    exceptions = registry.get("writer_overlap_exceptions")
    blockers: list[str] = []
    if (
        registry.get("package_type") != "musicforge_v144_state_authority_registry"
        or registry.get("schema_version") != 4
        or not integrity_ok(registry)
    ):
        blockers.append("v144_wave0_state_runtime_registry_integrity")
    if not isinstance(roots, list) or not roots or not isinstance(entries, list) or not entries or not isinstance(exceptions, list):
        blockers.append("v144_wave0_state_runtime_registry_sections")
    if baseline_integrity_hash and isinstance(exceptions, list) and any(
        not isinstance(row, dict) or row.get("baseline_integrity_hash") != baseline_integrity_hash for row in exceptions
    ):
        blockers.append("v144_wave0_state_runtime_registry_baseline")
    return blockers


def resolve_runtime_state_roots(
    registry: dict[str, object], composition: object, workspace: Path
) -> tuple[dict[str, Path], list[str]]:
    entries = cast(list[dict[str, object]], registry.get("entries") or [])
    roots = cast(list[dict[str, object]], registry.get("roots") or [])
    objects = _composition_store_objects(composition)
    root_entries: dict[str, list[dict[str, object]]] = {}
    for entry in entries:
        for namespace in cast(list[dict[str, object]], entry.get("physical_namespaces") or []):
            root_entries.setdefault(str(namespace.get("root_authority_id") or ""), []).append(entry)
    resolved: dict[str, Path] = {}
    blockers: list[str] = []
    for row in roots:
        root_id = str(row.get("root_authority_id") or "")
        if row.get("path_template") == "{workspace}/.musicforge":
            resolved[root_id] = (workspace / ".musicforge").resolve()
            continue
        candidates: set[Path] = set()
        for entry in root_entries.get(root_id, []):
            store = objects.get(str(entry.get("store_id") or ""))
            if store is None:
                continue
            relative_values = [
                str(namespace.get("relative_path_template") or "")
                for namespace in cast(list[dict[str, object]], entry.get("physical_namespaces") or [])
                if namespace.get("root_authority_id") == root_id
            ]
            actual = _store_root_path(store, set())
            if actual is not None:
                candidates.add(_remove_static_prefix(actual, relative_values).resolve())
        if not candidates:
            fallback = _request_scoped_root(root_id, composition, workspace)
            if fallback is not None:
                candidates.add(fallback.resolve())
        if len(candidates) == 1:
            resolved[root_id] = next(iter(candidates))
        elif not candidates:
            blockers.append(f"v144_wave0_state_runtime_root_unresolved:{root_id}")
        else:
            blockers.append(f"v144_wave0_state_runtime_root_ambiguous:{root_id}")
    return resolved, blockers


def validate_runtime_state_namespaces(
    registry: dict[str, object],
    resolved_roots: dict[str, Path],
    *,
    baseline_integrity_hash: str | None = None,
) -> list[str]:
    blockers: list[str] = []
    roots = {
        str(row.get("root_authority_id") or ""): row
        for row in cast(list[dict[str, object]], registry.get("roots") or [])
    }
    writers: dict[str, list[tuple[str, Path, str]]] = {"resolved": []}
    for row in cast(list[dict[str, object]], registry.get("entries") or []):
        access = cast(dict[str, object], row.get("access") or {})
        if not access.get("write"):
            continue
        store_id = str(row.get("store_id") or "")
        for namespace in cast(list[dict[str, object]], row.get("physical_namespaces") or []):
            root_id = str(namespace.get("root_authority_id") or "")
            root_path = resolved_roots.get(root_id)
            if root_id not in roots or root_path is None:
                blockers.append(f"v144_wave0_state_runtime_root_missing:{root_id}")
                continue
            relative = relative_state_path(namespace.get("relative_path_template"))
            if relative is None:
                blockers.append(f"v144_wave0_state_runtime_relative:{store_id}")
                continue
            target = (root_path / Path(*relative.parts)).resolve()
            writers["resolved"].append((store_id, target, namespace_identity_hash(store_id, namespace)))
    for root_id, row in roots.items():
        if row.get("disjointness") == "runtime_required" and root_id not in resolved_roots:
            blockers.append(f"v144_wave0_state_runtime_root_missing:{root_id}")
    static_exceptions = validated_overlap_exceptions(
        registry,
        roots,
        blockers,
        baseline_integrity_hash=baseline_integrity_hash,
    )
    check_state_path_overlaps(
        writers,
        blockers,
        prefix="v144_wave0_state_runtime_writer",
        exceptions={("resolved", left_hash, right_hash) for _, left_hash, right_hash in static_exceptions},
    )
    return sorted(set(blockers))


def check_state_path_overlaps(
    groups: Mapping[str, Sequence[tuple[str, PurePath, str]]],
    blockers: list[str],
    *,
    prefix: str,
    exceptions: set[tuple[str, str, str]] | None = None,
) -> None:
    for root_id, rows in groups.items():
        for index, (left_store, left_path, left_hash) in enumerate(rows):
            for right_store, right_path, right_hash in rows[index + 1 :]:
                if left_store == right_store:
                    continue
                if _contains(left_path, right_path) or _contains(right_path, left_path):
                    pair = (root_id, *sorted((left_hash, right_hash)))
                    if pair in (exceptions or set()):
                        continue
                    blockers.append(f"{prefix}_overlap:{root_id}:{left_store}:{right_store}")


def validated_overlap_exceptions(
    registry: dict[str, object],
    roots: dict[str, dict[str, object]],
    blockers: list[str],
    *,
    repo_root: Path | None = None,
    baseline_integrity_hash: str | None = None,
    current_version: str = VERSION,
) -> set[tuple[str, str, str]]:
    result: set[tuple[str, str, str]] = set()
    rows = cast(list[dict[str, object]], registry.get("writer_overlap_exceptions") or [])
    seen: set[str] = set()
    for row in rows:
        exception_id = str(row.get("exception_id") or "")
        stores = [str(row.get("left_store_id") or ""), str(row.get("right_store_id") or "")]
        root_ids = [str(row.get("left_root_authority_id") or ""), str(row.get("right_root_authority_id") or "")]
        if not exception_id or exception_id in seen or any(value not in roots for value in root_ids):
            blockers.append(f"v144_wave0_state_overlap_exception:{exception_id}")
            continue
        seen.add(exception_id)
        if (
            row.get("status") != "approved"
            or row.get("approved_by") != "architecture-reviewers"
            or not _approved_at(str(row.get("approved_at") or ""))
            or not str(row.get("reason") or "")
            or not str(row.get("owner") or "")
            or str(row.get("expires_version") or "") != "14.4.0"
            or _version_at_or_after(current_version, str(row.get("expires_version") or ""))
            or not str(row.get("adr") or "").endswith("ADR-033-v144-wave0-capability-freeze.md")
            or (baseline_integrity_hash is not None and row.get("baseline_integrity_hash") != baseline_integrity_hash)
        ):
            blockers.append(f"v144_wave0_state_overlap_exception_approval:{exception_id}")
            continue
        if repo_root is not None and not (repo_root / str(row["adr"])).is_file():
            blockers.append(f"v144_wave0_state_overlap_exception_adr:{exception_id}")
            continue
        actual_hashes = [str(row.get("left_namespace_hash") or ""), str(row.get("right_namespace_hash") or "")]
        namespaces = [
            _writer_namespace(registry, store_id, root_id, namespace_hash)
            for store_id, root_id, namespace_hash in zip(stores, root_ids, actual_hashes)
        ]
        if any(namespace is None for namespace in namespaces):
            blockers.append(f"v144_wave0_state_overlap_exception_namespace:{exception_id}")
            continue
        expected_hashes = [
            namespace_identity_hash(store_id, cast(dict[str, object], namespace))
            for store_id, namespace in zip(stores, namespaces)
        ]
        if actual_hashes != expected_hashes:
            blockers.append(f"v144_wave0_state_overlap_exception_binding:{exception_id}")
            continue
        group_id = root_ids[0] if root_ids[0] == root_ids[1] else "resolved"
        left_hash, right_hash = sorted(expected_hashes)
        result.add((group_id, left_hash, right_hash))
    return result


def relative_state_path(value: object) -> PurePosixPath | None:
    text = str(value or "").replace("\\", "/").strip("/")
    path = PurePosixPath(text or ".")
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def _writer_namespace(
    registry: dict[str, object], store_id: str, root_id: str, expected_hash: str
) -> dict[str, object] | None:
    for entry in cast(list[dict[str, object]], registry.get("entries") or []):
        if entry.get("store_id") != store_id:
            continue
        for namespace in cast(list[dict[str, object]], entry.get("physical_namespaces") or []):
            if namespace.get("root_authority_id") == root_id and namespace_identity_hash(store_id, namespace) == expected_hash:
                return namespace
    return None


def _approved_at(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _version_at_or_after(current: str, expiry: str) -> bool:
    current_key = _semantic_version_key(current)
    expiry_key = _semantic_version_key(expiry)
    return current_key is None or expiry_key is None or current_key >= expiry_key


def _semantic_version_key(value: str) -> tuple[int, int, int, int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+)?)?", value.strip())
    if match is None:
        return None
    prerelease = match.group(4)
    rank = {"a": 0, "b": 1, "rc": 2, None: 3}[prerelease]
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), rank, int(match.group(5) or 0)


def _contains(parent: PurePath, child: PurePath) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _composition_store_objects(composition: object) -> dict[str, object]:
    result: dict[str, object] = {}
    pending = [composition]
    visited: set[int] = set()
    while pending:
        value = pending.pop()
        if id(value) in visited:
            continue
        visited.add(id(value))
        value_type = type(value)
        if value_type.__name__.endswith("Store"):
            result[f"{value_type.__module__}.{value_type.__name__}"] = value
        try:
            attributes = vars(value).values()
        except TypeError:
            continue
        for child in attributes:
            if hasattr(child, "__dict__") and (type(child).__name__.endswith("Store") or child is composition):
                pending.append(child)
    return result


def _store_root_path(store: object, visited: set[int]) -> Path | None:
    if id(store) in visited:
        return None
    visited.add(id(store))
    for attribute in ("root", "store_root", "project_dir", "runs_dir", "transactions_root", "maintenance_root"):
        if not hasattr(store, attribute):
            continue
        value = getattr(store, attribute)
        return value if isinstance(value, Path) else None
    if hasattr(store, "path"):
        path = getattr(store, "path")
        return path if isinstance(path, Path) else None
    try:
        attributes = vars(store).items()
    except TypeError:
        return None
    for name, value in attributes:
        if name.endswith("_store") and type(value).__name__.endswith("Store"):
            nested = _store_root_path(value, visited)
            if nested is not None:
                return nested
    return None


def _remove_static_prefix(actual: Path, relative_values: list[str]) -> Path:
    prefixes = []
    for value in relative_values:
        parts = [part for part in PurePosixPath(value).parts if not part.startswith("{") and "{" not in part]
        if parts:
            prefixes.append(parts)
    if not prefixes:
        return actual
    prefix = min(prefixes, key=len)
    actual_parts = [part.lower() for part in actual.parts]
    prefix_parts = [part.lower() for part in prefix]
    if len(prefix_parts) <= len(actual_parts) and actual_parts[-len(prefix_parts) :] == prefix_parts:
        result = actual
        for _ in prefix_parts:
            result = result.parent
        return result
    return actual


def _request_scoped_root(root_id: str, composition: object, workspace: Path) -> Path | None:
    project_store = getattr(composition, "project_store", None)
    project_root = getattr(project_store, "root", None)
    if "configured-project-dir" in root_id and isinstance(project_root, Path):
        return project_root / "{project_id}"
    job_store = getattr(composition, "job_store", None)
    runs_dir = getattr(job_store, "runs_dir", None)
    if root_id.endswith("run-dir") and isinstance(runs_dir, Path):
        return runs_dir / "{job_id}"
    if root_id.endswith("configured-sprint-dir") and isinstance(project_root, Path):
        return project_root / "{project_id}" / "review-sprints" / "{sprint_id}"
    if root_id.endswith("transactions-root"):
        return workspace / ".musicforge" / "transactions"
    if "public-trust-center-publication" in root_id:
        trust_store = getattr(composition, "public_trust_center_store", None)
        trust_root = getattr(trust_store, "root", None)
        if isinstance(trust_root, Path):
            return trust_root
    if root_id.endswith("trust-operations-hub-runbook.configured-root"):
        hub_store = getattr(composition, "trust_operations_hub_store", None)
        hub_root = getattr(hub_store, "root", None)
        if isinstance(hub_root, Path):
            return hub_root
    return None


def sync_active_v12_state(workspace_root: Path | str) -> int:
    root = Path(workspace_root)
    rows = collect_active_v12_state(root)
    if not rows:
        return 0
    database = MusicForgeDatabase.from_workspace(root)
    database.initialize()
    with database.transaction() as connection:
        for row in rows:
            object_type = str(row["object_type"])
            object_id = str(row["object_id"])
            current = connection.execute(
                "SELECT version FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
            version = int(current[0]) + 1 if current else 1
            connection.execute(
                """
                INSERT INTO workflow_objects(object_type, object_id, generation, status, version, payload_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(object_type, object_id) DO UPDATE SET
                    generation=excluded.generation,
                    status=excluded.status,
                    version=excluded.version,
                    payload_hash=excluded.payload_hash,
                    updated_at=excluded.updated_at
                """,
                (object_type, object_id, row["generation"], row["status"], version, row["payload_hash"], _now()),
            )
    return len(rows)


def collect_active_v12_state(workspace_root: Path | str) -> list[dict[str, object]]:
    root = Path(workspace_root)
    candidates = [
        *root.glob("unified-release-programs/*/continuity-command-center/command-center-report.json"),
        *root.glob("unified-release-programs/*/continuity-command-center/signoff/command-center-signoff-state.json"),
        *root.glob("urpccca/*/signoff/receiver-acceptance-state.json"),
        *root.glob("urpccca/*/change-control/current-generation.json"),
    ]
    rows: list[dict[str, object]] = []
    for path in sorted(set(candidates)):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Mutable workflow index source is unreadable: {path.name}") from exc
        if not isinstance(document, dict):
            raise RuntimeError(f"Mutable workflow index source is not an object: {path.name}")
        if not integrity_ok(document):
            raise RuntimeError(f"Mutable workflow index source integrity failed: {path.name}")
        program_id = str(document.get("program_id") or path.parts[-3])
        if path.name == "command-center-report.json":
            object_type = "continuity_command_center"
        elif path.name == "command-center-signoff-state.json":
            object_type = "continuity_command_center_signoff"
        elif path.name == "receiver-acceptance-state.json":
            object_type = "receiver_acceptance"
        else:
            object_type = "receiver_acceptance_change"
        rows.append(
            {
                "object_type": object_type,
                "object_id": program_id,
                "generation": int(document.get("generation") or 1),
                "status": str(document.get("status") or "unknown"),
                "payload_hash": str(document.get("integrity_hash") or ""),
            }
        )
    return rows
