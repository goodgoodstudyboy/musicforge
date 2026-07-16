from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json


PRICING_PATH = Path(".musicforge") / "provider-pricing.json"
SENSITIVE_USAGE_KEYS = {
    "api_key",
    "api_key_masked",
    "authorization",
    "credential",
    "credentials",
    "messages",
    "password",
    "prompt",
    "raw_prompt",
    "secret",
}


def build_provider_usage_report(
    *,
    scope: str,
    records: list[dict[str, Any]],
    project_id: str | None = None,
    pricing_path: Path = PRICING_PATH,
) -> dict[str, Any]:
    pricing = load_provider_pricing(pricing_path)
    normalized = [normalize_provider_usage_record(record, pricing=pricing) for record in records]
    totals = _aggregate_records(normalized)
    report = {
        "scope": scope,
        "project_id": project_id,
        "total_calls": len(normalized),
        "prompt_tokens": totals["prompt_tokens"],
        "completion_tokens": totals["completion_tokens"],
        "total_tokens": totals["total_tokens"],
        "estimated_cost": totals["estimated_cost"],
        "currency": totals["currency"],
        "priced_calls": totals["priced_calls"],
        "unpriced_calls": len(normalized) - totals["priced_calls"],
        "by_model": aggregate_provider_usage(normalized, "model"),
        "by_operation": aggregate_provider_usage(normalized, "operation"),
        "by_template": aggregate_provider_usage(normalized, "template_id"),
        "records": normalized,
    }
    report["candidate_group_records"] = [record for record in normalized if record.get("source_type") == "candidate_group"]
    return report


def collect_project_provider_usage_records(project_id: str, versions: list[Any], project_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for version in versions:
        usage_path = Path(version.output_dir) / "data" / "provider-usage.json"
        record = usage_record_from_file(
            usage_path,
            source_type="version",
            source_id=str(version.version_id),
            project_id=project_id,
            version_id=str(version.version_id),
            job_id=str(version.job_id),
        )
        if record is not None:
            records.append(record)
    groups_dir = project_dir / "candidate-groups"
    if groups_dir.exists():
        for usage_path in sorted(groups_dir.glob("*/provider-usage.json")):
            record = usage_record_from_file(
                usage_path,
                source_type="candidate_group",
                source_id=usage_path.parent.name,
                project_id=project_id,
                group_id=usage_path.parent.name,
            )
            if record is not None:
                records.append(record)
    review_tasks_dir = project_dir / "review-tasks"
    if review_tasks_dir.exists():
        for usage_path in sorted(review_tasks_dir.glob("review-task-*/provider-usage.json")):
            task_id = usage_path.parent.name
            record = usage_record_from_file(
                usage_path,
                source_type="review_task",
                source_id=task_id,
                project_id=project_id,
                group_id=task_id,
            )
            if record is not None:
                records.append(record)
        for usage_path in sorted(review_tasks_dir.glob("review-task-*/judge-provider-usage.json")):
            task_id = usage_path.parent.name
            record = usage_record_from_file(
                usage_path,
                source_type="review_task_judge",
                source_id=task_id,
                project_id=project_id,
                group_id=task_id,
            )
            if record is not None:
                records.append(record)
    return records


def collect_candidate_group_provider_usage_records(project_id: str, group_id: str, project_dir: Path) -> list[dict[str, Any]]:
    usage_path = project_dir / "candidate-groups" / group_id / "provider-usage.json"
    record = usage_record_from_file(
        usage_path,
        source_type="candidate_group",
        source_id=group_id,
        project_id=project_id,
        group_id=group_id,
    )
    return [] if record is None else [record]


def usage_record_from_file(
    path: Path,
    *,
    source_type: str,
    source_id: str,
    project_id: str | None = None,
    version_id: str | None = None,
    job_id: str | None = None,
    group_id: str | None = None,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        "project_id": project_id,
        "version_id": version_id,
        "job_id": job_id,
        "group_id": group_id,
        "source_type": source_type,
        "source_id": source_id,
        "usage": sanitize_provider_usage(data),
    }


def normalize_provider_usage_record(record: dict[str, Any], *, pricing: dict[str, Any] | None = None) -> dict[str, Any]:
    usage = record.get("usage") if isinstance(record.get("usage"), dict) else record
    nested_usage = usage.get("usage") if isinstance(usage.get("usage"), dict) else {}
    prompt_tokens = _usage_int(usage, "prompt_tokens") or _usage_int(nested_usage, "prompt_tokens")
    completion_tokens = _usage_int(usage, "completion_tokens") or _usage_int(nested_usage, "completion_tokens")
    total_tokens = _usage_int(usage, "total_tokens") or _usage_int(nested_usage, "total_tokens") or prompt_tokens + completion_tokens
    model = str(usage.get("model") or usage.get("provider_model") or "")
    estimated_cost, currency = estimate_provider_cost(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        pricing=pricing or {},
    )
    return {
        "project_id": record.get("project_id"),
        "version_id": record.get("version_id"),
        "job_id": record.get("job_id"),
        "group_id": record.get("group_id"),
        "source_type": str(record.get("source_type") or "unknown"),
        "source_id": str(record.get("source_id") or ""),
        "provider_type": str(usage.get("provider_type") or usage.get("wire_api") or "unknown"),
        "model": model,
        "operation": str(usage.get("operation") or "unknown"),
        "template_id": str(usage.get("template_id") or ""),
        "started_at": None if usage.get("started_at") is None else str(usage.get("started_at")),
        "completed_at": None if usage.get("completed_at") is None else str(usage.get("completed_at")),
        "latency_ms": _optional_number(usage.get("latency_ms")),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": estimated_cost,
        "currency": currency,
        "request_id": None if usage.get("request_id") is None else str(usage.get("request_id")),
        "status": str(usage.get("status") or "unknown"),
    }


def aggregate_provider_usage(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        bucket = str(record.get(key) or "unknown")
        buckets.setdefault(bucket, []).append(record)
    rows = []
    for value, bucket_records in buckets.items():
        totals = _aggregate_records(bucket_records)
        rows.append(
            {
                key: value,
                "total_calls": len(bucket_records),
                "prompt_tokens": totals["prompt_tokens"],
                "completion_tokens": totals["completion_tokens"],
                "total_tokens": totals["total_tokens"],
                "estimated_cost": totals["estimated_cost"],
                "currency": totals["currency"],
                "priced_calls": totals["priced_calls"],
                "unpriced_calls": len(bucket_records) - totals["priced_calls"],
            }
        )
    return sorted(rows, key=lambda item: (-int(item.get("total_tokens") or 0), str(item.get(key) or "")))


def load_provider_pricing(path: Path = PRICING_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    if int(data.get("schema_version", 1) or 1) != 1:
        return {}
    models = data.get("models")
    return models if isinstance(models, dict) else {}


def estimate_provider_cost(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    pricing: dict[str, Any],
) -> tuple[float | None, str | None]:
    model_pricing = pricing.get(model)
    if not isinstance(model_pricing, dict):
        return None, None
    currency = str(model_pricing.get("currency") or "USD")
    if "total_per_1m" in model_pricing:
        total_rate = _optional_number(model_pricing.get("total_per_1m"))
        if total_rate is not None:
            return round((total_tokens / 1_000_000) * total_rate, 8), currency
    input_rate = _optional_number(model_pricing.get("input_per_1m"))
    output_rate = _optional_number(model_pricing.get("output_per_1m"))
    if input_rate is None and output_rate is None:
        return None, None
    input_cost = (prompt_tokens / 1_000_000) * (input_rate or 0.0)
    output_cost = (completion_tokens / 1_000_000) * (output_rate or 0.0)
    return round(input_cost + output_cost, 8), currency


def sanitize_provider_usage(value: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if lowered in SENSITIVE_USAGE_KEYS:
            continue
        if isinstance(item, dict):
            cleaned[key] = sanitize_provider_usage(item)
        elif isinstance(item, list):
            cleaned[key] = [sanitize_provider_usage(child) if isinstance(child, dict) else child for child in item]
        else:
            cleaned[key] = item
    return cleaned


def _aggregate_records(records: list[ImplementationDocument]) -> ImplementationDocument:
    prompt_tokens = sum(int(record.get("prompt_tokens") or 0) for record in records)
    completion_tokens = sum(int(record.get("completion_tokens") or 0) for record in records)
    total_tokens = sum(int(record.get("total_tokens") or 0) for record in records)
    costs = [float(record["estimated_cost"]) for record in records if record.get("estimated_cost") is not None]
    currencies = {str(record.get("currency")) for record in records if record.get("estimated_cost") is not None and record.get("currency")}
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": round(sum(costs), 8) if costs else None,
        "currency": currencies.pop() if len(currencies) == 1 else None,
        "priced_calls": len(costs),
    }


def _usage_int(data: ImplementationDocument, field_name: str) -> int:
    value = data.get(field_name)
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _optional_number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
