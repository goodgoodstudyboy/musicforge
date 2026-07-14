from __future__ import annotations

import json
import re
import shutil
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from song_agent.assets import AssetStore, asset_refs_snapshot
from song_agent.library_index import asset_source_hash
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.reference_analysis import get_analysis_report
from song_agent.references import ReferenceStore, reference_refs_snapshot


CONTEXT_PACK_ROOT = Path(".musicforge") / "context-packs"
CONTEXT_PACK_SCHEMA_VERSION = 1
CONTEXT_PACK_ID_PATTERN = re.compile(r"^pack-[0-9]{3,6}$")
MAX_CONTEXT_PACK_ASSET_REFS = 5
MAX_CONTEXT_PACK_REFERENCE_REFS = 5


class ContextPackError(ValueError):
    pass


class ContextPackStaleError(ContextPackError):
    pass


@dataclass(frozen=True)
class ContextPack:
    schema_version: int
    pack_id: str
    name: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_from: dict[str, Any] = field(default_factory=dict)
    query: dict[str, Any] = field(default_factory=dict)
    asset_refs: list[dict[str, Any]] = field(default_factory=list)
    reference_refs: list[dict[str, Any]] = field(default_factory=list)
    selection: dict[str, Any] = field(default_factory=dict)
    hidden: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextPack":
        pack_id = validate_context_pack_id(str(data.get("pack_id") or "pack-001"))
        asset_refs = _clean_asset_refs(data.get("asset_refs"))
        reference_refs = _clean_reference_refs(data.get("reference_refs"))
        return cls(
            schema_version=int(data.get("schema_version", CONTEXT_PACK_SCHEMA_VERSION) or CONTEXT_PACK_SCHEMA_VERSION),
            pack_id=pack_id,
            name=_bounded_text(data.get("name"), 120) or pack_id,
            description=_bounded_text(data.get("description"), 1000),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            created_from=sanitize_metadata(dict(data.get("created_from") or {})),
            query=sanitize_metadata(dict(data.get("query") or {})),
            asset_refs=asset_refs,
            reference_refs=reference_refs,
            selection=sanitize_metadata(dict(data.get("selection") or {})),
            hidden=bool(data.get("hidden", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextPackStore:
    def __init__(self, root: Path | str = CONTEXT_PACK_ROOT):
        self.root = Path(root)
        self.lock = threading.RLock()

    def list_packs(self, include_hidden: bool = False) -> list[ContextPack]:
        if not self.root.exists():
            return []
        packs = []
        for path in self.root.glob("*/pack.json"):
            try:
                pack = ContextPack.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if pack.hidden and not include_hidden:
                continue
            packs.append(pack)
        return sorted(packs, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_pack(self, pack_id: str) -> ContextPack:
        path = self.pack_dir(pack_id) / "pack.json"
        if not path.exists():
            raise FileNotFoundError(pack_id)
        return ContextPack.from_dict(read_json(path))

    def create_pack(self, payload: dict[str, Any], *, asset_store: AssetStore, reference_store: ReferenceStore, now: str | None = None) -> ContextPack:
        now = now or now_iso()
        asset_refs, reference_refs = prepare_context_pack_refs(payload, asset_store, reference_store)
        with self.lock:
            self.root.mkdir(parents=True, exist_ok=True)
            pack_id, pack_dir = self._reserve_pack_dir()
            try:
                data = {
                    "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
                    "pack_id": pack_id,
                    "name": payload.get("name") or pack_id,
                    "description": payload.get("description") or "",
                    "created_at": now,
                    "updated_at": now,
                    "created_from": payload.get("created_from") or {},
                    "query": payload.get("query") or {},
                    "asset_refs": asset_refs,
                    "reference_refs": reference_refs,
                    "selection": payload.get("selection") or {"mode": "manual", "selected_by": "user", "score_summary": []},
                    "hidden": False,
                }
                pack = ContextPack.from_dict(data)
                write_json(pack_dir / "pack.json", pack.to_dict())
                self.append_event(pack.pack_id, "context_pack_created", {"asset_count": len(pack.asset_refs), "reference_count": len(pack.reference_refs)}, now=now)
            except Exception:
                if pack_dir.exists() and not (pack_dir / "pack.json").exists():
                    shutil.rmtree(pack_dir)
                raise
            return pack

    def hide_pack(self, pack_id: str, hidden: bool = True) -> ContextPack:
        with self.lock:
            pack = self.read_pack(pack_id)
            updated = ContextPack.from_dict({**pack.to_dict(), "hidden": hidden, "updated_at": now_iso()})
            self._write_pack(updated)
            self.append_event(pack_id, "context_pack_hidden" if hidden else "context_pack_unhidden", {}, now=updated.updated_at)
            return updated

    def delete_pack(self, pack_id: str) -> None:
        with self.lock:
            pack_dir = self.pack_dir(pack_id)
            if not pack_dir.exists():
                raise FileNotFoundError(pack_id)
            resolved = pack_dir.resolve()
            base = self.root.resolve()
            try:
                resolved.relative_to(base)
            except ValueError as exc:
                raise ValueError("Refusing to delete outside context packs.") from exc
            if resolved.is_symlink():
                raise ValueError("Refusing to delete symlink context pack.")
            shutil.rmtree(resolved)

    def apply_preview(self, pack_id: str, *, asset_store: AssetStore, reference_store: ReferenceStore, captured_at: str | None = None) -> dict[str, Any]:
        pack = self.read_pack(pack_id)
        return apply_context_pack(pack, asset_store=asset_store, reference_store=reference_store, captured_at=captured_at)

    def pack_dir(self, pack_id: str) -> Path:
        pack_id = validate_context_pack_id(pack_id)
        base = self.root.resolve()
        raw_target = base / pack_id
        if raw_target.is_symlink():
            raise ValueError("Refusing to operate on symlink context pack.")
        target = raw_target.resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside context packs.") from exc
        return target

    def append_event(self, pack_id: str, event_type: str, payload: dict[str, Any], *, now: str | None = None) -> None:
        with self.lock:
            pack_dir = self.pack_dir(pack_id)
            pack_dir.mkdir(parents=True, exist_ok=True)
            event = {"timestamp": now or now_iso(), "type": event_type, "payload": sanitize_metadata(payload)}
            with (pack_dir / "events.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _write_pack(self, pack: ContextPack) -> ContextPack:
        with self.lock:
            write_json(self.pack_dir(pack.pack_id) / "pack.json", pack.to_dict())
            return pack

    def _reserve_pack_dir(self) -> tuple[str, Path]:
        for index in range(1, 1_000_000):
            pack_id = f"pack-{index:03d}"
            pack_dir = self.pack_dir(pack_id)
            try:
                pack_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return pack_id, pack_dir
        raise RuntimeError("Could not allocate context pack id.")


def prepare_context_pack_refs(payload: dict[str, Any], asset_store: AssetStore, reference_store: ReferenceStore) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_asset_refs = payload.get("asset_refs") or []
    raw_reference_refs = payload.get("reference_refs") or []
    asset_snapshot = asset_refs_snapshot(asset_store, raw_asset_refs)
    reference_snapshot = reference_refs_snapshot(reference_store, raw_reference_refs)
    asset_refs = []
    for ref in asset_snapshot["asset_refs"]:
        asset = asset_store.read_asset(ref["asset_id"])
        asset_refs.append({**_pack_asset_ref(ref), "source_hash": asset_source_hash(asset)})
    reference_refs = []
    for ref in reference_snapshot["reference_refs"]:
        reference = reference_store.read_reference(ref["reference_id"])
        reference_refs.append({**_pack_reference_ref(ref), "source_hash": reference.sha256})
    if len(asset_refs) > MAX_CONTEXT_PACK_ASSET_REFS:
        raise ContextPackError(f"context pack supports at most {MAX_CONTEXT_PACK_ASSET_REFS} asset refs.")
    if len(reference_refs) > MAX_CONTEXT_PACK_REFERENCE_REFS:
        raise ContextPackError(f"context pack supports at most {MAX_CONTEXT_PACK_REFERENCE_REFS} reference refs.")
    return asset_refs, reference_refs


def apply_context_pack(pack: ContextPack, *, asset_store: AssetStore, reference_store: ReferenceStore, captured_at: str | None = None) -> dict[str, Any]:
    if pack.hidden:
        raise ContextPackStaleError("Context pack is hidden.")
    warnings = []
    raw_asset_refs = []
    raw_reference_refs = []
    for ref in pack.asset_refs:
        asset = asset_store.read_asset(str(ref.get("asset_id") or ""))
        if asset.hidden:
            raise ContextPackStaleError("Context pack is stale. Rebuild or update this context pack.")
        if asset_source_hash(asset) != str(ref.get("source_hash") or ""):
            raise ContextPackStaleError("Context pack is stale. Rebuild or update this context pack.")
        raw_asset_refs.append({"asset_id": asset.asset_id, "role": ref.get("role"), "strength": ref.get("strength")})
    for ref in pack.reference_refs:
        reference = reference_store.read_reference(str(ref.get("reference_id") or ""))
        if reference.hidden:
            raise ContextPackStaleError("Context pack is stale. Rebuild or update this context pack.")
        if reference.sha256 != str(ref.get("source_hash") or ""):
            raise ContextPackStaleError("Context pack is stale. Rebuild or update this context pack.")
        if ref.get("requires_fresh_analysis"):
            report = get_analysis_report(reference_store, reference.reference_id)
            if report.get("stale"):
                raise ContextPackStaleError("Context pack is stale. Rebuild or update this context pack.")
        raw_reference_refs.append({"reference_id": reference.reference_id, "role": ref.get("role"), "strength": ref.get("strength")})
    asset_snapshot = asset_refs_snapshot(asset_store, raw_asset_refs, captured_at=captured_at or now_iso())
    reference_snapshot = reference_refs_snapshot(reference_store, raw_reference_refs, captured_at=captured_at or now_iso())
    return {
        "ok": True,
        "pack": context_pack_summary(pack),
        "asset_refs": asset_snapshot["asset_refs"],
        "reference_refs": reference_snapshot["reference_refs"],
        "warnings": warnings,
    }


def merge_context_refs(explicit_refs: Any, pack_refs: list[dict[str, Any]], id_key: str, limit: int) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for source in (explicit_refs if isinstance(explicit_refs, list) else [], pack_refs):
        if not isinstance(source, list):
            continue
        for ref in source:
            if not isinstance(ref, dict):
                continue
            item_id = str(ref.get(id_key) or "").strip()
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            merged.append(dict(ref))
    if len(merged) > limit:
        raise ContextPackError(f"{id_key.replace('_id', '_refs')} supports at most {limit} items after context pack merge.")
    return merged


def context_pack_snapshot(pack: ContextPack, applied: dict[str, Any], *, captured_at: str | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
            "pack_id": pack.pack_id,
            "name": pack.name,
            "description": pack.description,
            "asset_refs": applied.get("asset_refs", []),
            "reference_refs": applied.get("reference_refs", []),
            "captured_at": captured_at or now_iso(),
        }
    )


def write_context_pack_snapshot(run_dir: Path, snapshot: dict[str, Any]) -> Path:
    return write_json(run_dir / "data" / "context-pack.json", snapshot)


def context_pack_summary(pack: ContextPack, *, used_by_versions: list[str] | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "pack_id": pack.pack_id,
            "name": pack.name,
            "description": pack.description,
            "asset_count": len(pack.asset_refs),
            "reference_count": len(pack.reference_refs),
            "created_from": pack.created_from,
            "query": pack.query,
            "used_by_versions": sorted(set(used_by_versions or [])),
            "hidden": pack.hidden,
        }
    )


def context_pack_public_dict(pack: ContextPack) -> dict[str, Any]:
    return sanitize_metadata(pack.to_dict())


def validate_context_pack_id(pack_id: str) -> str:
    if not CONTEXT_PACK_ID_PATTERN.match(pack_id):
        raise ValueError("Invalid context pack id.")
    return pack_id


def _pack_asset_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "asset_id": ref.get("asset_id"),
            "role": _bounded_text(ref.get("role"), 80) or "asset",
            "strength": _strength(ref.get("strength")),
        }
    )


def _pack_reference_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "reference_id": ref.get("reference_id"),
            "role": _bounded_text(ref.get("role"), 80) or "reference",
            "strength": _strength(ref.get("strength")),
            "requires_fresh_analysis": bool(ref.get("analysis_summary") or ref.get("requires_fresh_analysis")),
        }
    )


def _clean_asset_refs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    if len(value) > MAX_CONTEXT_PACK_ASSET_REFS:
        raise ContextPackError(f"context pack supports at most {MAX_CONTEXT_PACK_ASSET_REFS} asset refs.")
    refs = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise ContextPackError("asset_refs items must be objects.")
        asset_id = str(item.get("asset_id") or "").strip()
        if not asset_id or asset_id in seen:
            continue
        seen.add(asset_id)
        refs.append(sanitize_metadata(dict(item)))
    return refs


def _clean_reference_refs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    if len(value) > MAX_CONTEXT_PACK_REFERENCE_REFS:
        raise ContextPackError(f"context pack supports at most {MAX_CONTEXT_PACK_REFERENCE_REFS} reference refs.")
    refs = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise ContextPackError("reference_refs items must be objects.")
        reference_id = str(item.get("reference_id") or "").strip()
        if not reference_id or reference_id in seen:
            continue
        seen.add(reference_id)
        refs.append(sanitize_metadata(dict(item)))
    return refs


def _bounded_text(value: Any, max_length: int) -> str:
    text = sanitize_sensitive_text(str(value or "")).strip()
    if len(text) > max_length:
        text = text[:max_length].rstrip()
    return text


def _strength(value: Any) -> float:
    try:
        strength = float(value)
    except (TypeError, ValueError):
        strength = 0.7
    return round(max(0.0, min(1.0, strength)), 2)
