# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.domains.program.ports import ProgramReleaseStore as ProgramReleaseStore
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION, verify_unified_release_program_package as verify_unified_release_program_package, write_unified_release_program_verification_report as write_unified_release_program_verification_report
from song_agent.domains.program.unified_command_center_release_train_handoff_verifier import UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_release_train_handoff_package as verify_unified_command_center_release_train_handoff_package
from song_agent.domains.program.v142_urp_readiness_2 import UnifiedReleaseProgramStoreReadinessMixin
from song_agent.domains.program import v142_urp_readiness_2 as _v142_urp_readiness_2
from song_agent.domains.program.v142_urp_evidence import UnifiedReleaseProgramStoreEvidenceMixin
from song_agent.domains.program import v142_urp_evidence as _v142_urp_evidence

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

ch = _make_deferred_global('ch')
count = _make_deferred_global('count')
item = _make_deferred_global('item')
read_json = _make_deferred_global('read_json')
role = _make_deferred_global('role')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch, count, item, read_json, role
    ch = namespace.get('ch', ch)
    count = namespace.get('count', count)
    item = namespace.get('item', item)
    read_json = namespace.get('read_json', read_json)
    role = namespace.get('role', role)
    _bind_deferred_defaults(namespace)


DEFAULT_POLICY = {
    "require_all_required_trains_ready": True,
    "require_no_dependency_cycle": True,
    "require_no_critical_risk": True,
    "require_external_handoff_acceptance": False,
    "allow_advisory_warnings": True,
    "allow_optional_defer": True,
    "required_program_roles": ["release_owner"],
}




def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}

def _recipient_guide(docs: DomainDocument) -> str:
    return f"# Unified Release Program\n\nProgram: {docs['report'].get('program_id')}\nStatus: {docs['report'].get('status')}\n"

def _read_optional_json(path: Path) -> DomainDocument:
    if path.exists():
        return read_json(path)
    return {}

def _source_inputs(payload: DomainDocument) -> DomainDocument:
    return {
        key: _json_safe_input(value)
        for key, value in payload.items()
        if key in {"external_evidence_manifest", "external_evidence_manifest_path", "external_evidence", "external_evidence_items"}
    }

def _merge_inputs(base: DomainDocument, incoming: DomainDocument) -> DomainDocument:
    merged = dict(base or {})
    merged.update({key: value for key, value in incoming.items() if value not in (None, "", [])})
    return merged

def _json_safe_input(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe_input(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_input(item) for item in value]
    return value

def _policy(payload: object) -> DomainDocument:
    data: DomainDocument = dict(DEFAULT_POLICY)
    if isinstance(payload, dict):
        for key in data:
            if key in payload:
                data[key] = payload[key]
    data["required_program_roles"] = [str(role) for role in data.get("required_program_roles") or ["release_owner"]]
    return data

def _safe_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return safe.strip("-")[:120]

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

def _integrity_hash(doc: DomainDocument) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})

def _integrity_ok(doc: DomainDocument) -> bool:
    return bool(doc.get("integrity_hash")) and doc.get("integrity_hash") == _integrity_hash(doc)

def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _sha256_or_integrity(path: Path) -> str:
    try:
        doc = read_json(path)
        if isinstance(doc, dict) and doc.get("integrity_hash"):
            return str(doc.get("integrity_hash"))
    except Exception:
        pass
    return _sha256_path(path)

def _verification_zip_sha256(report: DomainDocument) -> str | None:
    summary = _as_document(report.get("summary"))
    return report.get("zip_sha256") or summary.get("zip_sha256")

def _verification_manifest_hash(report: DomainDocument) -> str | None:
    summary = _as_document(report.get("summary"))
    return report.get("manifest_hash") or summary.get("manifest_hash")

def _item_key(row: DomainDocument) -> str:
    return "|".join(str(row.get(key) or "") for key in ("item_id", "train_id", "handoff_id"))

def _history_text(rows: list[DomainDocument]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

def _has_cycle(from_nodes: list[str], to_nodes: list[str]) -> bool:
    graph: dict[str, list[str]] = {}
    for source, target in zip(from_nodes, to_nodes):
        if source and target:
            graph.setdefault(source, []).append(target)
            graph.setdefault(target, [])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in graph.get(node, []):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in list(graph))

def _topological_order(nodes: list[DomainDocument], edges: list[DomainDocument]) -> list[str]:
    remaining = {str(row.get("item_id")) for row in nodes}
    incoming = {node: 0 for node in remaining}
    outgoing: dict[str, list[str]] = {node: [] for node in remaining}
    for edge in edges:
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source in remaining and target in remaining:
            incoming[target] += 1
            outgoing[source].append(target)
    order = []
    ready = sorted(node for node, count in incoming.items() if count == 0)
    while ready:
        node = ready.pop(0)
        order.append(node)
        remaining.discard(node)
        for nxt in outgoing.get(node, []):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    return order
