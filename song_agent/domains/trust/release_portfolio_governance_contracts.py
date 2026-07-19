from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


PORTFOLIO_GOVERNANCE_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


QUEUE_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at", "latest_execution_report_hash", "latest_export_manifest_hash", "latest_zip_sha256", "existing"}


ACTION_PLAN_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


EXECUTION_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


MANUAL_LIST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def queue_integrity_hash(queue: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (queue or {}).items() if key not in QUEUE_HASH_EXCLUDE_KEYS})


def action_plan_integrity_hash(plan: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (plan or {}).items() if key not in ACTION_PLAN_HASH_EXCLUDE_KEYS})


def execution_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in EXECUTION_REPORT_HASH_EXCLUDE_KEYS})


def manual_action_list_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in MANUAL_LIST_HASH_EXCLUDE_KEYS})


def governance_manifest_integrity_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in MANIFEST_HASH_EXCLUDE_KEYS})
