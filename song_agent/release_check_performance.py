from __future__ import annotations

from typing import Any, Iterable


DEFAULT_SLOW_CHECK_SECONDS = 30.0
PROFILE_DURATION_BUDGET_SECONDS: dict[str, float] = {
    "v12": 360.0,
    "latest": 480.0,
    "ga": 600.0,
}
PROFILE_BUDGET_WARNING_ONLY = frozenset(PROFILE_DURATION_BUDGET_SECONDS)


def check_budget_status(
    *,
    duration_ms: int,
    duration_budget_seconds: float | None,
    profile: str,
    budget_enforced_profiles: Iterable[str],
    budget_warning_only: bool,
) -> str:
    if duration_budget_seconds is None:
        return "not_configured"
    if duration_ms <= int(float(duration_budget_seconds) * 1000):
        return "passed"
    enforced = str(profile) in {str(item) for item in budget_enforced_profiles}
    return "failed" if enforced and not budget_warning_only else "warning"


def performance_summary(
    results: Iterable[Any],
    *,
    profile: str,
    duration_ms: int,
    slow_check_seconds: float = DEFAULT_SLOW_CHECK_SECONDS,
) -> dict[str, Any]:
    rows = list(results)
    slow_threshold_ms = int(float(slow_check_seconds) * 1000)
    slow_checks = [
        _performance_row(result)
        for result in sorted(rows, key=lambda item: int(getattr(item, "duration_ms", 0)), reverse=True)
        if int(getattr(result, "duration_ms", 0)) >= slow_threshold_ms
    ]
    checks_over_budget = [
        _performance_row(result)
        for result in rows
        if getattr(result, "duration_budget_status", "not_configured") in {"warning", "failed"}
    ]
    profile_budget = PROFILE_DURATION_BUDGET_SECONDS.get(str(profile))
    profile_over_budget = profile_budget is not None and duration_ms > int(profile_budget * 1000)
    hard_check_overrun = any(row.get("duration_budget_status") == "failed" for row in checks_over_budget)
    if hard_check_overrun:
        status = "failed"
    elif checks_over_budget or profile_over_budget:
        status = "warning"
    else:
        status = "passed"
    return {
        "slow_checks": slow_checks,
        "checks_over_budget": checks_over_budget,
        "duration_budget_status": status,
        "profile_duration_budget_seconds": profile_budget,
        "profile_duration_ms": int(duration_ms),
        "profile_over_budget": bool(profile_over_budget),
        "profile_budget_warning_only": str(profile) in PROFILE_BUDGET_WARNING_ONLY,
        "slow_check_threshold_seconds": float(slow_check_seconds),
    }


def _performance_row(result: Any) -> dict[str, Any]:
    return {
        "check_id": str(getattr(result, "check_id", "")),
        "name": str(getattr(result, "name", "")),
        "duration_ms": int(getattr(result, "duration_ms", 0)),
        "duration_budget_seconds": getattr(result, "duration_budget_seconds", None),
        "duration_budget_status": str(getattr(result, "duration_budget_status", "not_configured")),
        "budget_warning_only": bool(getattr(result, "budget_warning_only", True)),
        "status": str(getattr(result, "status", "")),
    }
