from __future__ import annotations

from pathlib import Path

from song_agent.release_check_fixtures import ReleaseCheckFixtureCache


def test_release_check_fixture_cache_hits_and_isolates_mutation(tmp_path: Path) -> None:
    cache = ReleaseCheckFixtureCache(tmp_path / "cache")
    builds = 0

    def builder(root: Path) -> dict[str, str]:
        nonlocal builds
        builds += 1
        (root / "evidence.txt").write_text("original\n", encoding="utf-8")
        return {"status": "prepared"}

    with cache.checkout("world", builder) as first:
        assert first.cache_hit is False
        first_path = first.path
        (first.path / "evidence.txt").write_text("tampered\n", encoding="utf-8")
    with cache.checkout("world", builder) as second:
        assert second.cache_hit is True
        assert second.path == first_path
        assert second.metadata["payload"]["status"] == "prepared"
        assert (second.path / "evidence.txt").read_text(encoding="utf-8") == "original\n"

    assert builds == 1
    assert cache.stats() == {"entries": 1, "hits": 1, "misses": 1, "checkouts": 2}


def test_release_check_fixture_cache_instances_do_not_share_sources(tmp_path: Path) -> None:
    builds = 0

    def builder(root: Path) -> None:
        nonlocal builds
        builds += 1
        (root / "ready.txt").write_text("ready\n", encoding="utf-8")

    for name in ("first", "second"):
        cache = ReleaseCheckFixtureCache(tmp_path / name)
        with cache.checkout("world", builder) as checkout:
            assert checkout.cache_hit is False

    assert builds == 2
