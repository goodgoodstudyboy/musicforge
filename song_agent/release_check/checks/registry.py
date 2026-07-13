from __future__ import annotations

from functools import lru_cache
from typing import Any

from song_agent.release_check.checks import creation, delivery, meta, program, quality, security, studio, trust

PROVIDERS = (
    meta,
    security,
    creation,
    studio,
    quality,
    delivery,
    trust,
    program,
)


@lru_cache(maxsize=1)
def _providers() -> tuple[Any, ...]:
    return PROVIDERS


def resolve_callable(name: str) -> Any:
    for provider in _providers():
        target = provider.CALLABLES.get(name)
        if target is not None:
            return target
    from song_agent.release_check.checks.legacy import monolith as legacy
    try:
        return getattr(legacy, name)
    except AttributeError as exc:
        raise AttributeError(f"Unknown release-check callable: {name}") from exc


def check_domain(*, group: str, tags: tuple[str, ...] = (), callable_name: str | None = None) -> str:
    if callable_name:
        for provider in _providers():
            if callable_name in provider.CALLABLES:
                return str(provider.DOMAIN)
    normalized_group = str(group).strip().lower()
    normalized_tags = {str(item).strip().lower() for item in tags}
    matches = [
        provider.DOMAIN
        for provider in _providers()
        if normalized_group in provider.GROUPS or normalized_tags.intersection(provider.TAGS)
    ]
    if not matches:
        return "legacy"
    return matches[0]


def provider_inventory() -> list[dict[str, Any]]:
    return [
        {
            "domain": provider.DOMAIN,
            "groups": sorted(provider.GROUPS),
            "tags": sorted(provider.TAGS),
            "callables": sorted(provider.CALLABLES),
        }
        for provider in _providers()
    ]
