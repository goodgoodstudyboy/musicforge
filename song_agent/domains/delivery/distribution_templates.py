from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import copy
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS, sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash


DISTRIBUTION_TEMPLATE_SCHEMA_VERSION = 1
DISTRIBUTION_TEMPLATE_ROOT = Path(".musicforge") / "distribution-templates"
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
FILE_NAMING_VARIABLES = set().union(*FILE_NAMING_VARIABLES_BY_KEY.values())
TEMPLATE_IMPORT_BLOCKED_KEYS = DISTRIBUTION_BLOCKED_KEYS | {
    "path",
    "source_path",
    "file_path",
    "local_path",
    "url",
    "cookie",
    "authorization",
}
MAX_TEMPLATE_IMPORT_BYTES = 512 * 1024
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,78}[a-z0-9]$")
_TEMPLATE_ID_RE = re.compile(r"^tpl-[a-z0-9][a-z0-9_-]{1,78}$|^tpl-\d{6}$")
_FILE_VAR_RE = re.compile(r"\{([^{}]+)\}")
LOCAL_TEMPLATE_PATH_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b[A-Z]:[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "windows_path"),
    (re.compile(r"(?<![\\/\w])(?:\\\\|(?<!:)//)[^\\/\s,;]+[\\/]+[^\\/\s,;]+(?:[\\/]+[^\\/\s,;]+)*"), "unc_path"),
    (re.compile(r"(?<!\S)/Users/[^/\s,;]+(?:/[^\s,;]+)*"), "macos_path"),
    (re.compile(r"(?<!\S)/home/[^/\s,;]+(?:/[^\s,;]+)*"), "linux_home_path"),
)


class DistributionTemplateError(ValueError):
    pass


@dataclass
class TemplatePack:
    schema_version: int
    template_pack_id: str
    slug: str
    name: str
    description: str = ""
    source: str = "user"
    rules: dict[str, Any] = field(default_factory=dict)
    metadata_mapping: dict[str, Any] = field(default_factory=dict)
    file_naming: dict[str, str] = field(default_factory=dict)
    checklist: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "template_pack_id": self.template_pack_id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "rules": self.rules,
            "metadata_mapping": self.metadata_mapping,
            "file_naming": self.file_naming,
            "checklist": self.checklist,
        }
        payload = sanitize_metadata(payload, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        payload["template_hash"] = template_content_hash(payload)
        payload["content_hash"] = template_content_hash(payload, include_identity=False)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TemplatePack":
        now = str(data.get("created_at") or now_iso())
        source = _safe_source(data.get("source"))
        return cls(
            schema_version=int(data.get("schema_version", DISTRIBUTION_TEMPLATE_SCHEMA_VERSION) or DISTRIBUTION_TEMPLATE_SCHEMA_VERSION),
            template_pack_id=_safe_template_id(data.get("template_pack_id")),
            slug=_safe_slug(data.get("slug")),
            name=_safe_text(data.get("name"), 120) or "Distribution Template",
            description=_safe_text(data.get("description"), 500),
            source=source,
            rules=_safe_rules(data.get("rules")),
            metadata_mapping=_safe_mapping(data.get("metadata_mapping")),
            file_naming=_safe_file_naming(data.get("file_naming")),
            checklist=_safe_checklist(data.get("checklist")),
            created_at=now,
            updated_at=str(data.get("updated_at") or now),
        )


class TemplatePackStore:
    def __init__(self, root: Path | str = DISTRIBUTION_TEMPLATE_ROOT) -> None:
        self.root = Path(root).resolve()
        self.lock = threading.RLock()

    def packs_dir(self) -> Path:
        return self.root / "packs"

    def pack_dir(self, template_pack_id: str) -> Path:
        return self.packs_dir() / _safe_template_id(template_pack_id)

    def pack_path(self, template_pack_id: str) -> Path:
        return self.pack_dir(template_pack_id) / "template-pack.json"

    def list_templates(self) -> list[dict[str, Any]]:
        templates: list[dict[str, Any]] = [pack.to_dict() for pack in _builtin_template_packs()]
        if self.packs_dir().exists():
            for path in sorted(self.packs_dir().glob("tpl-*/template-pack.json")):
                try:
                    pack = TemplatePack.from_dict(read_json(path))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
                templates.append(pack.to_dict())
        return sorted(templates, key=lambda item: (str(item.get("source") or ""), str(item.get("slug") or "")))

    def get_template(self, template_pack_id: str) -> dict[str, Any]:
        template_id = _safe_template_id(template_pack_id)
        builtin = _builtin_template_by_id(template_id)
        if builtin is not None:
            return builtin.to_dict()
        path = self.pack_path(template_id)
        if not path.exists():
            raise DistributionTemplateError(f"Distribution template pack does not exist: {template_pack_id}.")
        return TemplatePack.from_dict(read_json(path)).to_dict()

    def create_template(self, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            data = _template_payload(payload)
            _ensure_import_payload_safe(payload)
            template_id = self._reserve_template_id()
            data = {
                **data,
                "template_pack_id": template_id,
                "source": "user",
                "created_at": now,
                "updated_at": now,
            }
            pack = TemplatePack.from_dict(data)
            self._ensure_slug_available(pack.slug)
            report = validate_template_pack(pack.to_dict(), existing_slugs=self._slug_set(exclude_id=pack.template_pack_id))
            if report["status"] != "passed":
                raise DistributionTemplateError(_first_validation_error(report))
            return self._write_pack(pack)

    def update_template(self, template_pack_id: str, patch: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            current = self.get_template(template_pack_id)
            if current.get("source") == "builtin":
                raise DistributionTemplateError("Builtin distribution template packs are read-only. Clone before editing.")
            now = now or now_iso()
            data = {**current, **_template_payload(patch)}
            data["template_pack_id"] = current["template_pack_id"]
            data["source"] = current.get("source") or "user"
            data["created_at"] = current.get("created_at") or now
            data["updated_at"] = now
            _ensure_import_payload_safe(patch)
            pack = TemplatePack.from_dict(data)
            report = validate_template_pack(pack.to_dict(), existing_slugs=self._slug_set(exclude_id=pack.template_pack_id))
            if report["status"] != "passed":
                raise DistributionTemplateError(_first_validation_error(report))
            return self._write_pack(pack)

    def clone_template(self, template_pack_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        source = self.get_template(template_pack_id)
        payload = payload or {}
        now = now or now_iso()
        base_slug = _safe_slug(payload.get("slug") or f"{source.get('slug')}-copy")
        clone_payload = {
            key: copy.deepcopy(source.get(key))
            for key in ("name", "description", "rules", "metadata_mapping", "file_naming", "checklist")
        }
        clone_payload["slug"] = self._unique_slug(base_slug)
        if payload.get("name"):
            clone_payload["name"] = payload["name"]
        return self.create_template(clone_payload, now=now)

    def import_template(self, payload: dict[str, Any], *, rename: bool = False, now: str | None = None) -> dict[str, Any]:
        with self.lock:
            now = now or now_iso()
            if _payload_size(payload) > MAX_TEMPLATE_IMPORT_BYTES:
                raise DistributionTemplateError("Distribution template import payload is too large.")
            _ensure_import_payload_safe(payload)
            data = _template_payload(payload)
            if not data:
                raise DistributionTemplateError("template is required.")
            slug = _safe_slug(data.get("slug"))
            if slug in self._slug_set() and not rename:
                raise DistributionTemplateError("Distribution template slug already exists. Pass rename=true to import a copy.")
            if slug in self._slug_set():
                slug = self._unique_slug(slug)
            data = {
                **data,
                "template_pack_id": self._reserve_template_id(),
                "slug": slug,
                "source": "imported",
                "created_at": now,
                "updated_at": now,
            }
            pack = TemplatePack.from_dict(data)
            report = validate_template_pack(pack.to_dict(), existing_slugs=self._slug_set(exclude_id=pack.template_pack_id))
            if report["status"] != "passed":
                raise DistributionTemplateError(_first_validation_error(report))
            return self._write_pack(pack)

    def delete_template(self, template_pack_id: str) -> dict[str, Any]:
        with self.lock:
            current = self.get_template(template_pack_id)
            if current.get("source") == "builtin":
                raise DistributionTemplateError("Builtin distribution template packs cannot be deleted.")
            path = self.pack_dir(template_pack_id)
            if path.exists():
                import shutil

                shutil.rmtree(path)
            return {"template_pack_id": template_pack_id, "deleted": True}

    def validate_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            _ensure_import_payload_safe(payload)
            data = _template_payload(payload)
            if not data:
                raise DistributionTemplateError("template is required.")
            if not data.get("template_pack_id"):
                data["template_pack_id"] = "tpl-000001"
            if not data.get("source"):
                data["source"] = "user"
            if not data.get("created_at"):
                data["created_at"] = now_iso()
            if not data.get("updated_at"):
                data["updated_at"] = data["created_at"]
            return validate_template_pack(TemplatePack.from_dict(data).to_dict(), existing_slugs=self._slug_set(exclude_id=str(data.get("template_pack_id") or "")))
        except DistributionTemplateError as exc:
            return _validation_report([("template_payload", str(exc))])

    def _write_pack(self, pack: TemplatePack) -> ImplementationDocument:
        data = pack.to_dict()
        write_json(self.pack_path(pack.template_pack_id), data)
        return data

    def _reserve_template_id(self) -> str:
        self.packs_dir().mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            template_id = f"tpl-{index:06d}"
            if _builtin_template_by_id(template_id) is None and not self.pack_path(template_id).exists():
                return template_id
        raise DistributionTemplateError("Unable to allocate a unique distribution template id.")

    def _slug_set(self, *, exclude_id: str | None = None) -> set[str]:
        slugs: set[str] = set()
        for item in self.list_templates():
            if exclude_id and item.get("template_pack_id") == exclude_id:
                continue
            slugs.add(str(item.get("slug") or ""))
        return slugs

    def _ensure_slug_available(self, slug: str) -> None:
        if slug in self._slug_set():
            raise DistributionTemplateError("Distribution template slug already exists.")

    def _unique_slug(self, slug: str) -> str:
        existing = self._slug_set()
        if slug not in existing:
            return slug
        for index in range(2, 10_000):
            candidate = f"{slug}-{index}"
            if candidate not in existing:
                return candidate
        raise DistributionTemplateError("Unable to allocate a unique distribution template slug.")


def validate_template_pack(template: dict[str, Any], *, existing_slugs: set[str] | None = None) -> dict[str, Any]:
    errors: list[tuple[str, str]] = []
    if int(template.get("schema_version") or 0) != DISTRIBUTION_TEMPLATE_SCHEMA_VERSION:
        errors.append(("schema_version", "Unsupported distribution template schema_version."))
    try:
        _safe_template_id(template.get("template_pack_id"))
    except DistributionTemplateError as exc:
        errors.append(("template_id", str(exc)))
    try:
        slug = _safe_slug(template.get("slug"))
        if existing_slugs and slug in existing_slugs:
            errors.append(("slug", "Distribution template slug must be unique."))
    except DistributionTemplateError as exc:
        errors.append(("slug", str(exc)))
    if not str(template.get("name") or "").strip():
        errors.append(("name", "Distribution template name is required."))
    try:
        _safe_rules(template.get("rules"))
    except DistributionTemplateError as exc:
        errors.append(("rules_shape", str(exc)))
    try:
        _safe_mapping(template.get("metadata_mapping"))
    except DistributionTemplateError as exc:
        errors.append(("metadata_mapping_shape", str(exc)))
    try:
        _safe_file_naming(template.get("file_naming"))
    except DistributionTemplateError as exc:
        errors.append(("file_naming_shape", str(exc)))
    try:
        _safe_checklist(template.get("checklist"))
    except DistributionTemplateError as exc:
        errors.append(("checklist_shape", str(exc)))
    findings = template_redaction_findings(template)
    if findings:
        errors.append(("redaction_scan", "Distribution template contains blocked key, local path, URL, or sensitive value."))
    return _validation_report(errors, redaction_findings=findings)


def template_content_hash(template: dict[str, Any], *, include_identity: bool = True) -> str:
    payload = {
        "rules": template.get("rules") if isinstance(template.get("rules"), dict) else {},
        "metadata_mapping": template.get("metadata_mapping") if isinstance(template.get("metadata_mapping"), dict) else {},
        "file_naming": template.get("file_naming") if isinstance(template.get("file_naming"), dict) else {},
        "checklist": template.get("checklist") if isinstance(template.get("checklist"), list) else [],
    }
    if include_identity:
        payload = {
            "slug": template.get("slug"),
            "name": template.get("name"),
            "description": template.get("description"),
            **payload,
        }
    return stable_hash(payload)


def template_summary(template: dict[str, Any] | None) -> dict[str, Any]:
    data = template if isinstance(template, dict) else {}
    rules = data.get("rules") if isinstance(data.get("rules"), dict) else {}
    return sanitize_metadata(
        {
            "template_pack_id": data.get("template_pack_id"),
            "slug": data.get("slug"),
            "name": data.get("name"),
            "source": data.get("source"),
            "template_hash": data.get("template_hash") or template_content_hash(data),
            "content_hash": data.get("content_hash") or template_content_hash(data, include_identity=False),
            "rules_summary": {key: rules.get(key) for key in sorted(rules)},
            "checklist_item_count": len(data.get("checklist") if isinstance(data.get("checklist"), list) else []),
            "payload_hash": stable_hash(
                {
                    "template_pack_id": data.get("template_pack_id"),
                    "slug": data.get("slug"),
                    "name": data.get("name"),
                    "source": data.get("source"),
                    "template_hash": data.get("template_hash") or template_content_hash(data),
                    "content_hash": data.get("content_hash") or template_content_hash(data, include_identity=False),
                }
            ),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def template_rules(template: dict[str, Any] | None) -> dict[str, Any]:
    return _safe_rules(template.get("rules") if isinstance(template, dict) else {})


def template_mapping(template: dict[str, Any] | None) -> dict[str, Any]:
    return _safe_mapping(template.get("metadata_mapping") if isinstance(template, dict) else {})


def template_file_naming(template: dict[str, Any] | None) -> dict[str, str]:
    return _safe_file_naming(template.get("file_naming") if isinstance(template, dict) else {})


def template_redaction_findings(value: Any, *, prefix: str = "") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            lower = key_text.lower()
            if lower in TEMPLATE_IMPORT_BLOCKED_KEYS or lower.endswith("_path"):
                findings.append({"path": path, "kind": "blocked_key", "message": f"Blocked template key: {path}."})
            findings.extend(template_redaction_findings(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(template_redaction_findings(item, prefix=f"{prefix}[{index}]"))
    elif isinstance(value, str):
        text = value
        if re.search(r"(?i)\bhttps?://", text):
            findings.append({"path": prefix, "kind": "url", "message": "Template value contains a URL."})
        for pattern, kind in LOCAL_TEMPLATE_PATH_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append({"path": prefix, "kind": kind, "message": "Template value contains a local path."})
        for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(text):
                findings.append({"path": prefix, "kind": "sensitive_value", "message": f"Template value contains sensitive pattern: {replacement}."})
    return findings


def resolve_mapping_source(source: str, *, release_metadata: dict[str, Any], track_metadata: dict[str, Any]) -> Any:
    source = str(source or "").strip()
    if source not in MAPPING_SOURCE_ALLOWLIST:
        raise DistributionTemplateError(f"Unsupported metadata mapping source: {source}.")
    scope, field_name = source.split(".", 1)
    data = release_metadata.get("release") if scope == "release" else track_metadata
    if not isinstance(data, dict):
        return ""
    value = data.get(field_name)
    if isinstance(value, list):
        if field_name == "credits":
            return "; ".join(str(item.get("name") or "") for item in value if isinstance(item, dict) and item.get("name"))
        return "; ".join(str(item) for item in value if str(item).strip())
    if isinstance(value, bool):
        return "yes" if value else "no"
    return "" if value is None else value


def render_file_pattern(pattern: str, *, track: dict[str, Any], ext: str) -> str:
    pattern = _safe_file_pattern(pattern)
    values = {
        "track_number": int(track.get("track_number") or 1),
        "disc_number": int(track.get("disc_number") or 1),
        "slug_title": _slug(str(track.get("title") or track.get("track_id") or "track")),
        "track_id": _slug(str(track.get("track_id") or "track")),
        "ext": ext.strip(".").lower(),
    }
    try:
        rendered = pattern.format(**values)
    except (KeyError, ValueError) as exc:
        raise DistributionTemplateError("Distribution file naming pattern is invalid.") from exc
    return _validate_relative_path(rendered)


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


def _template_payload(payload: ImplementationDocument) -> ImplementationDocument:
    if not isinstance(payload, dict):
        raise DistributionTemplateError("Template payload must be a JSON object.")
    data = payload.get("template") if isinstance(payload.get("template"), dict) else payload
    data = {key: copy.deepcopy(value) for key, value in data.items() if key not in {"template_hash"}}
    return data


def _ensure_import_payload_safe(payload: Any) -> None:
    findings = template_redaction_findings(payload)
    if findings:
        raise DistributionTemplateError(findings[0]["message"])


def _payload_size(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _safe_rules(value: Any) -> ImplementationDocument:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DistributionTemplateError("rules must be an object.")
    result: dict[str, Any] = {}
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


def _safe_mapping(value: Any) -> ImplementationDocument:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DistributionTemplateError("metadata_mapping must be an object.")
    rows = value.get("platform_csv") if isinstance(value.get("platform_csv"), list) else []
    result_rows: list[dict[str, Any]] = []
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


def _safe_file_naming(value: Any) -> dict[str, str]:
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


def _safe_checklist(value: Any) -> list[ImplementationDocument]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DistributionTemplateError("checklist must be a list.")
    result: list[dict[str, Any]] = []
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


def _safe_template_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text or not _TEMPLATE_ID_RE.fullmatch(text):
        raise DistributionTemplateError("Invalid distribution template_pack_id.")
    return text


def _safe_slug(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "-")
    if not text or not _SLUG_RE.fullmatch(text):
        raise DistributionTemplateError("Invalid distribution template slug.")
    return text


def _safe_source(value: Any) -> str:
    text = str(value or "user").strip().lower()
    return text if text in DISTRIBUTION_TEMPLATE_SOURCES else "user"


def _safe_item_id(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "-")
    if not text or not _SLUG_RE.fullmatch(text):
        raise DistributionTemplateError("Invalid checklist item_id.")
    return text


def _safe_text(value: Any, limit: int) -> str:
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


def _validation_report(errors: list[tuple[str, str]], *, redaction_findings: list[ImplementationDocument] | None = None) -> ImplementationDocument:
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


def _first_validation_error(report: ImplementationDocument) -> str:
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if blockers:
        return str(blockers[0].get("message") or "Distribution template validation failed.")
    return "Distribution template validation failed."
