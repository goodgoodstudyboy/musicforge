# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import copy as copy
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash

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

DistributionTemplateError = _make_deferred_global('DistributionTemplateError')
FILE_NAMING_VARIABLES = _make_deferred_global('FILE_NAMING_VARIABLES')
TemplatePack = _make_deferred_global('TemplatePack')
_FILE_VAR_RE = _make_deferred_global('_FILE_VAR_RE')
_SLUG_RE = _make_deferred_global('_SLUG_RE')
_TEMPLATE_ID_RE = _make_deferred_global('_TEMPLATE_ID_RE')
check = _make_deferred_global('check')
check_id = _make_deferred_global('check_id')
message = _make_deferred_global('message')
part = _make_deferred_global('part')
template_redaction_findings = _make_deferred_global('template_redaction_findings')

def bind_globals(namespace: dict[str, object]) -> None:
    global DistributionTemplateError, FILE_NAMING_VARIABLES, TemplatePack, _FILE_VAR_RE, _SLUG_RE, _TEMPLATE_ID_RE, check
    global check_id, message, part, template_redaction_findings
    DistributionTemplateError = namespace.get('DistributionTemplateError', DistributionTemplateError)
    FILE_NAMING_VARIABLES = namespace.get('FILE_NAMING_VARIABLES', FILE_NAMING_VARIABLES)
    TemplatePack = namespace.get('TemplatePack', TemplatePack)
    _FILE_VAR_RE = namespace.get('_FILE_VAR_RE', _FILE_VAR_RE)
    _SLUG_RE = namespace.get('_SLUG_RE', _SLUG_RE)
    _TEMPLATE_ID_RE = namespace.get('_TEMPLATE_ID_RE', _TEMPLATE_ID_RE)
    check = namespace.get('check', check)
    check_id = namespace.get('check_id', check_id)
    message = namespace.get('message', message)
    part = namespace.get('part', part)
    template_redaction_findings = namespace.get('template_redaction_findings', template_redaction_findings)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_TEMPLATE_SCHEMA_VERSION = 1
DISTRIBUTION_TEMPLATE_SOURCES = {"builtin", "user", "imported"}
DISTRIBUTION_TEMPLATE_RULE_KEYS = {
    "require_audio",
    "require_artwork",
    "require_upc",
    "require_isrc",
    "require_lyrics",
    "require_credits",
    "artwork_min_px",
    "artwork_square",
    "artwork_max_bytes",
    "csv_formula_escape",
}
MAPPING_SOURCE_ALLOWLIST = {
    "release.title",
    "release.display_artist",
    "release.primary_artist",
    "release.label",
    "release.upc",
    "release.release_date",
    "track.track_number",
    "track.title",
    "track.display_artist",
    "track.primary_artist",
    "track.featured_artists",
    "track.isrc",
    "track.explicit",
    "track.instrumental",
    "track.language",
    "track.lyrics",
    "track.credits",
}
FILE_NAMING_VARIABLES_BY_KEY = {
    "audio": {"track_number", "track_number:02d", "disc_number", "slug_title", "track_id", "isrc", "ext"},
    "lyrics": {"track_number", "track_number:02d", "disc_number", "slug_title", "track_id", "isrc", "language", "ext"},
    "artwork": {"release_slug", "release_id", "upc", "profile_id", "target_id", "ext"},
}
LOCAL_TEMPLATE_PATH_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b[A-Z]:[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "windows_path"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "unc_path"),
    (re.compile(r"(?<!\S)/Users/[^/\s,;]+(?:/[^\s,;]+)*"), "macos_path"),
    (re.compile(r"(?<!\S)/home/[^/\s,;]+(?:/[^\s,;]+)*"), "linux_home_path"),
)




def _builtin_template_packs() -> list[TemplatePack]:
    now = "2026-05-17T00:00:00+00:00"
    return [
        TemplatePack(
            schema_version=1,
            template_pack_id="tpl-generic-dsp-basic",
            slug="generic-dsp-basic",
            name="Generic DSP Basic",
            description="Local generic DSP preparation template. Not an official platform rule set.",
            source="builtin",
            rules={
                "require_audio": True,
                "require_artwork": True,
                "require_upc": True,
                "require_isrc": True,
                "require_lyrics": False,
                "require_credits": "warning",
                "artwork_min_px": 3000,
                "artwork_square": True,
                "artwork_max_bytes": 20 * 1024 * 1024,
                "csv_formula_escape": True,
            },
            metadata_mapping={
                "platform_csv": [
                    {"column": "Title", "source": "track.title", "required": True},
                    {"column": "Primary Artist", "source": "track.primary_artist", "required": True},
                    {"column": "ISRC", "source": "track.isrc", "required": True},
                    {"column": "UPC", "source": "release.upc", "required": True},
                ]
            },
            file_naming={"artwork": "cover.{ext}", "audio": "{track_number:02d}-{slug_title}.wav", "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt"},
            checklist=[{"item_id": "explicit-confirmed", "label": "Explicit flag checked", "required": True, "scope": "release"}],
            created_at=now,
            updated_at=now,
        ),
        TemplatePack(
            schema_version=1,
            template_pack_id="tpl-pitch-demo-basic",
            slug="pitch-demo-basic",
            name="Pitch Demo Basic",
            description="Local pitch/demo handoff template. Not an official platform rule set.",
            source="builtin",
            rules={
                "require_audio": False,
                "require_artwork": True,
                "require_upc": False,
                "require_isrc": False,
                "require_lyrics": False,
                "require_credits": "warning",
                "artwork_min_px": 1400,
                "artwork_square": True,
                "artwork_max_bytes": 20 * 1024 * 1024,
                "csv_formula_escape": True,
            },
            metadata_mapping={"platform_csv": [{"column": "Title", "source": "track.title", "required": True}, {"column": "Artist", "source": "track.primary_artist", "required": True}]},
            file_naming={"artwork": "cover.{ext}", "audio": "{track_number:02d}-{slug_title}.wav", "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt"},
            checklist=[{"item_id": "pitch-note-reviewed", "label": "Submission note reviewed", "required": True, "scope": "release"}],
            created_at=now,
            updated_at=now,
        ),
        TemplatePack(
            schema_version=1,
            template_pack_id="tpl-internal-archive-basic",
            slug="internal-archive-basic",
            name="Internal Archive Basic",
            description="Local internal archive template. Not an official platform rule set.",
            source="builtin",
            rules={
                "require_audio": False,
                "require_artwork": False,
                "require_upc": False,
                "require_isrc": False,
                "require_lyrics": False,
                "require_credits": False,
                "artwork_min_px": 0,
                "artwork_square": False,
                "artwork_max_bytes": 50 * 1024 * 1024,
                "csv_formula_escape": True,
            },
            metadata_mapping={"platform_csv": [{"column": "Title", "source": "track.title", "required": True}, {"column": "Track ID", "source": "track.track_number", "required": True}]},
            file_naming={"artwork": "cover.{ext}", "audio": "{track_number:02d}-{slug_title}.wav", "lyrics": "lyrics/{track_number:02d}-{slug_title}.txt"},
            checklist=[{"item_id": "archive-readme-reviewed", "label": "Archive README reviewed", "required": False, "scope": "release"}],
            created_at=now,
            updated_at=now,
        ),
    ]

def _builtin_template_by_id(template_pack_id: str) -> TemplatePack | None:
    for pack in _builtin_template_packs():
        if pack.template_pack_id == template_pack_id:
            return pack
    return None

def _template_payload(payload: DomainDocument) -> DomainDocument:
    if not isinstance(payload, dict):
        raise DistributionTemplateError("Template payload must be a JSON object.")
    data = _document_or(payload.get("template"), payload)
    data = {key: copy.deepcopy(value) for key, value in data.items() if key not in {"template_hash"}}
    return data

def _ensure_import_payload_safe(payload: object) -> None:
    findings = template_redaction_findings(payload)
    if findings:
        raise DistributionTemplateError(findings[0]["message"])

def _payload_size(payload: object) -> int:
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

def _safe_rules(value: object) -> DomainDocument:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DistributionTemplateError("rules must be an object.")
    result: DomainDocument = {}
    for key, item in value.items():
        key = str(key)
        if key not in DISTRIBUTION_TEMPLATE_RULE_KEYS:
            raise DistributionTemplateError(f"Unsupported template rule: {key}.")
        if key in {"artwork_min_px", "artwork_max_bytes"}:
            result[key] = max(0, int(item or 0))
        elif key == "require_credits":
            result[key] = item if item in {True, False, "warning"} else False
        elif isinstance(item, bool):
            result[key] = item
        else:
            raise DistributionTemplateError(f"Template rule {key} must be boolean or supported scalar.")
    return sanitize_metadata(result, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def _safe_mapping(value: object) -> DomainDocument:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DistributionTemplateError("metadata_mapping must be an object.")
    rows = _as_list(value.get("platform_csv"))
    result_rows: list[DomainDocument] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise DistributionTemplateError(f"metadata_mapping.platform_csv[{index}] must be an object.")
        column = _safe_text(row.get("column"), 80)
        source = _safe_text(row.get("source"), 80)
        if not column:
            raise DistributionTemplateError("metadata mapping column is required.")
        if column in seen:
            raise DistributionTemplateError(f"Duplicate metadata mapping column: {column}.")
        if source not in MAPPING_SOURCE_ALLOWLIST:
            raise DistributionTemplateError(f"Unsupported metadata mapping source: {source}.")
        seen.add(column)
        result_rows.append({"column": column, "source": source, "required": bool(row.get("required", False))})
    return sanitize_metadata({"platform_csv": result_rows}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS) if result_rows else {}

def _safe_file_naming(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DistributionTemplateError("file_naming must be an object.")
    result: dict[str, str] = {}
    for key, item in value.items():
        key = str(key)
        if key not in {"artwork", "audio", "lyrics"}:
            raise DistributionTemplateError(f"Unsupported file_naming key: {key}.")
        result[key] = _safe_file_pattern(str(item or ""), key=key)
    return result

def _safe_file_pattern(pattern: str, *, key: str | None = None) -> str:
    text = str(pattern or "").strip()[:160]
    if not text:
        raise DistributionTemplateError("file_naming pattern must be non-empty.")
    allowed = FILE_NAMING_VARIABLES_BY_KEY.get(key or "", FILE_NAMING_VARIABLES)
    for match in _FILE_VAR_RE.finditer(text):
        if match.group(1) not in allowed:
            raise DistributionTemplateError(f"Unsupported file_naming variable: {match.group(1)}.")
    stripped = _FILE_VAR_RE.sub("x", text)
    if "{" in stripped or "}" in stripped:
        raise DistributionTemplateError("file_naming braces are invalid.")
    _validate_relative_path(stripped.replace(".x", ".txt"))
    return text

def _safe_checklist(value: object) -> list[DomainDocument]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DistributionTemplateError("checklist must be a list.")
    result: list[DomainDocument] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DistributionTemplateError(f"checklist[{index}] must be an object.")
        item_id = _safe_item_id(item.get("item_id"))
        if item_id in seen:
            raise DistributionTemplateError(f"Duplicate checklist item_id: {item_id}.")
        seen.add(item_id)
        status = str(item.get("default_status") or "pending")
        if status not in {"pending", "done", "waived", "blocked"}:
            raise DistributionTemplateError(f"Unsupported checklist default_status: {status}.")
        result.append(
            {
                "item_id": item_id,
                "label": _safe_text(item.get("label"), 160) or item_id,
                "description": _safe_text(item.get("description"), 500),
                "required": bool(item.get("required", False)),
                "scope": _safe_text(item.get("scope"), 40) or "release",
                "default_status": status,
            }
        )
    return sanitize_metadata(result, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def _safe_template_id(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text or not _TEMPLATE_ID_RE.fullmatch(text):
        raise DistributionTemplateError("Invalid distribution template_pack_id.")
    return text

def _safe_slug(value: object) -> str:
    text = str(value or "").strip().lower().replace(" ", "-")
    if not text or not _SLUG_RE.fullmatch(text):
        raise DistributionTemplateError("Invalid distribution template slug.")
    return text

def _safe_source(value: object) -> str:
    text = str(value or "user").strip().lower()
    return text if text in DISTRIBUTION_TEMPLATE_SOURCES else "user"

def _safe_item_id(value: object) -> str:
    text = str(value or "").strip().lower().replace(" ", "-")
    if not text or not _SLUG_RE.fullmatch(text):
        raise DistributionTemplateError("Invalid checklist item_id.")
    return text

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return text or "track"

def _validate_relative_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise DistributionTemplateError("Unsafe template relative path.")
    parts = [part for part in raw.split("/") if part]
    if not parts or raw.startswith("/") or raw.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise DistributionTemplateError("Unsafe template relative path.")
    return PurePosixPath(*parts).as_posix()

def _validation_report(errors: list[tuple[str, str]], *, redaction_findings: list[DomainDocument] | None = None) -> DomainDocument:
    checks = [
        {
            "scope": "distribution_template",
            "check_id": check_id,
            "status": "failed",
            "severity": "blocking",
            "message": message,
        }
        for check_id, message in errors
    ]
    if not checks:
        checks.append({"scope": "distribution_template", "check_id": "template_valid", "status": "passed", "severity": "blocking", "message": "Distribution template pack is valid."})
    blockers = [check for check in checks if check["status"] == "failed"]
    return sanitize_metadata(
        {
            "status": "failed" if blockers else "passed",
            "checks": checks,
            "blockers": blockers,
            "redaction_findings": redaction_findings or [],
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def _first_validation_error(report: DomainDocument) -> str:
    blockers = _as_list(report.get("blockers"))
    if blockers:
        return str(blockers[0].get("message") or "Distribution template validation failed.")
    return "Distribution template validation failed."
