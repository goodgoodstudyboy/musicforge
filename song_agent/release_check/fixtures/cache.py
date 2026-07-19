from __future__ import annotations

import atexit
import hashlib
import inspect
import json
import platform
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from song_agent import __version__


FIXTURE_SCHEMA_VERSION = 1
FixtureBuilder = Callable[[Path], dict[str, Any] | None]
FixtureRelocator = Callable[[Path, Path], None]


@dataclass(frozen=True)
class FixtureCheckout:
    key: str
    path: Path
    metadata: dict[str, Any]
    cache_hit: bool


class ReleaseCheckFixtureCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path(tempfile.mkdtemp(prefix="mfrc-"))
        self.root.mkdir(parents=True, exist_ok=True)
        self._sources: dict[str, Path] = {}
        self._hits = 0
        self._misses = 0
        self._checkouts = 0
        self._active: set[str] = set()
        self._owns_root = root is None
        if self._owns_root:
            atexit.register(shutil.rmtree, self.root, True)

    @contextmanager
    def checkout(
        self,
        key: str,
        builder: FixtureBuilder,
        *,
        relocate: FixtureRelocator | None = None,
    ) -> Iterator[FixtureCheckout]:
        normalized_key = str(key).strip()
        if not normalized_key:
            raise ValueError("Release-check fixture key is required.")
        source, metadata, cache_hit = self._prepare(normalized_key, builder)
        if normalized_key in self._active:
            raise RuntimeError(f"Release-check fixture is already checked out: {normalized_key}")
        clone = self._workspace_path(normalized_key)
        shutil.rmtree(clone, ignore_errors=True)
        clone.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, clone)
        if relocate is not None:
            relocate(source, clone)
        self._active.add(normalized_key)
        self._checkouts += 1
        try:
            yield FixtureCheckout(key=normalized_key, path=clone, metadata=dict(metadata), cache_hit=cache_hit)
        finally:
            self._active.discard(normalized_key)
            shutil.rmtree(clone, ignore_errors=True)

    def stats(self) -> dict[str, int]:
        return {
            "entries": len(self._sources),
            "hits": self._hits,
            "misses": self._misses,
            "checkouts": self._checkouts,
        }

    def clear(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self._sources.clear()
        self._hits = 0
        self._misses = 0
        self._checkouts = 0
        self._active.clear()

    def _prepare(self, key: str, builder: FixtureBuilder) -> tuple[Path, dict[str, Any], bool]:
        cached = self._sources.get(key)
        if cached is not None and cached.is_dir():
            self._hits += 1
            return cached, _read_metadata(cached), True
        source = self.root / "s" / hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
        if source.is_dir():
            self._sources[key] = source
            self._hits += 1
            return source, _read_metadata(source), True
        workspace = self._workspace_path(key)
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=False)
        try:
            payload = dict(builder(workspace) or {})
            metadata = {
                "schema_version": FIXTURE_SCHEMA_VERSION,
                "key": key,
                "app_version": __version__,
                "python": f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}",
                "payload": payload,
            }
            (workspace / ".release-check-fixture.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(workspace, source)
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
        self._sources[key] = source
        self._misses += 1
        return source, metadata, False

    def _workspace_path(self, key: str) -> Path:
        return self.root / "w" / hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def fixture_key(name: str, builder: FixtureBuilder, *, variant: str = "default") -> str:
    try:
        source = inspect.getsource(builder)
    except (OSError, TypeError):
        source = repr(builder)
    helper_hash = hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()[:16]
    python_key = f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}"
    return f"v{FIXTURE_SCHEMA_VERSION}:{__version__}:{python_key}:{name}:{variant}:{helper_hash}"


@contextmanager
def prepare_v12_command_center_world(
    builder: FixtureBuilder,
    *,
    variant: str = "complete",
    cache: ReleaseCheckFixtureCache | None = None,
    relocate: FixtureRelocator | None = None,
) -> Iterator[FixtureCheckout]:
    selected_cache = cache or release_check_fixture_cache()
    key = fixture_key("v12-command-center-world", builder, variant=variant)
    with selected_cache.checkout(key, builder, relocate=relocate) as checkout:
        yield checkout


def release_check_fixture_cache() -> ReleaseCheckFixtureCache:
    global _PROCESS_CACHE
    if _PROCESS_CACHE is None:
        _PROCESS_CACHE = ReleaseCheckFixtureCache()
    return _PROCESS_CACHE


def reset_release_check_fixture_cache() -> None:
    global _PROCESS_CACHE
    if _PROCESS_CACHE is not None:
        _PROCESS_CACHE.clear()
    _PROCESS_CACHE = None


def _read_metadata(source: Path) -> dict[str, Any]:
    path = source / ".release-check-fixture.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


_PROCESS_CACHE: ReleaseCheckFixtureCache | None = None
