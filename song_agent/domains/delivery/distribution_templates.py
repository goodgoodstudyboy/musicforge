# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import copy as copy
import json as json
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash


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
    rules: ImplementationDocument = field(default_factory=dict)
    metadata_mapping: ImplementationDocument = field(default_factory=dict)
    file_naming: dict[str, str] = field(default_factory=dict)
    checklist: list[ImplementationDocument] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "TemplatePack":
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

    def list_templates(self) -> list[DomainDocument]:
        templates: list[ImplementationDocument] = [pack.to_dict() for pack in _builtin_template_packs()]
        if self.packs_dir().exists():
            for path in sorted(self.packs_dir().glob("tpl-*/template-pack.json")):
                try:
                    pack = TemplatePack.from_dict(read_json(path))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
                templates.append(pack.to_dict())
        return sorted(templates, key=lambda item: (str(item.get("source") or ""), str(item.get("slug") or "")))

    def get_template(self, template_pack_id: str) -> DomainDocument:
        template_id = _safe_template_id(template_pack_id)
        builtin = _builtin_template_by_id(template_id)
        if builtin is not None:
            return builtin.to_dict()
        path = self.pack_path(template_id)
        if not path.exists():
            raise DistributionTemplateError(f"Distribution template pack does not exist: {template_pack_id}.")
        return TemplatePack.from_dict(read_json(path)).to_dict()

    def create_template(self, payload: DomainDocument, *, now: str | None = None) -> DomainDocument:
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

    def update_template(self, template_pack_id: str, patch: DomainDocument, *, now: str | None = None) -> DomainDocument:
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

    def clone_template(self, template_pack_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def import_template(self, payload: DomainDocument, *, rename: bool = False, now: str | None = None) -> DomainDocument:
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

    def delete_template(self, template_pack_id: str) -> DomainDocument:
        with self.lock:
            current = self.get_template(template_pack_id)
            if current.get("source") == "builtin":
                raise DistributionTemplateError("Builtin distribution template packs cannot be deleted.")
            path = self.pack_dir(template_pack_id)
            if path.exists():
                import shutil

                shutil.rmtree(path)
            return {"template_pack_id": template_pack_id, "deleted": True}

    def validate_payload(self, payload: DomainDocument) -> DomainDocument:
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


def validate_template_pack(template: DomainDocument, *, existing_slugs: set[str] | None = None) -> DomainDocument:
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


def template_content_hash(template: DomainDocument, *, include_identity: bool = True) -> str:
    payload: ImplementationDocument = {
        "rules": _as_document(template.get("rules")),
        "metadata_mapping": _as_document(template.get("metadata_mapping")),
        "file_naming": _as_document(template.get("file_naming")),
        "checklist": _as_list(template.get("checklist")),
    }
    if include_identity:
        payload = {
            "slug": template.get("slug"),
            "name": template.get("name"),
            "description": template.get("description"),
            **payload,
        }
    return stable_hash(payload)


def template_summary(template: DomainDocument | None) -> DomainDocument:
    data = _as_document(template)
    rules = _as_document(data.get("rules"))
    return sanitize_metadata(
        {
            "template_pack_id": data.get("template_pack_id"),
            "slug": data.get("slug"),
            "name": data.get("name"),
            "source": data.get("source"),
            "template_hash": data.get("template_hash") or template_content_hash(data),
            "content_hash": data.get("content_hash") or template_content_hash(data, include_identity=False),
            "rules_summary": {key: rules.get(key) for key in sorted(rules)},
            "checklist_item_count": len(_as_list(data.get("checklist"))),
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


def template_rules(template: DomainDocument | None) -> DomainDocument:
    return _safe_rules(template.get("rules") if isinstance(template, dict) else {})


def template_mapping(template: DomainDocument | None) -> DomainDocument:
    return _safe_mapping(template.get("metadata_mapping") if isinstance(template, dict) else {})


def template_file_naming(template: DomainDocument | None) -> dict[str, str]:
    return _safe_file_naming(template.get("file_naming") if isinstance(template, dict) else {})


def template_redaction_findings(value: Any, *, prefix: str = "") -> list[DomainDocument]:
    findings: list[ImplementationDocument] = []
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


def resolve_mapping_source(source: str, *, release_metadata: DomainDocument, track_metadata: DomainDocument) -> Any:
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


def render_file_pattern(pattern: str, *, track: DomainDocument, ext: str) -> str:
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


from song_agent.domains.delivery import v142_dt_readiness as _v142_dt_readiness
from song_agent.domains.delivery.v142_dt_readiness import _builtin_template_packs as _builtin_template_packs, _builtin_template_by_id as _builtin_template_by_id, _template_payload as _template_payload, _ensure_import_payload_safe as _ensure_import_payload_safe, _payload_size as _payload_size, _safe_rules as _safe_rules, _safe_mapping as _safe_mapping, _safe_file_naming as _safe_file_naming, _safe_file_pattern as _safe_file_pattern, _safe_checklist as _safe_checklist, _safe_template_id as _safe_template_id, _safe_slug as _safe_slug, _safe_source as _safe_source, _safe_item_id as _safe_item_id, _safe_text as _safe_text, _slug as _slug, _validate_relative_path as _validate_relative_path, _validation_report as _validation_report, _first_validation_error as _first_validation_error

_v142_dt_readiness.bind_globals(globals())
