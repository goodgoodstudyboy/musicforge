from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS, get_distribution_profile, merge_profile_options
from song_agent.distribution_templates import TemplatePackStore, template_rules, template_summary
from song_agent.projectio import read_json, write_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import ReleaseStore, stable_hash


DISTRIBUTION_ROOT_NAME = "distribution"
DISTRIBUTION_TARGET_SCHEMA_VERSION = 1
DISTRIBUTION_TARGET_STATUSES = {"draft", "qa_failed", "qa_warning", "qa_passed", "exported", "signed", "archived"}
SIGNED_DISTRIBUTION_STATUSES = {"signed", "force_signed"}


class DistributionError(Exception):
    pass


class DistributionNotFoundError(DistributionError):
    pass


class DistributionValidationError(DistributionError):
    pass


class DistributionStateError(DistributionError):
    pass


@dataclass
class DistributionTarget:
    schema_version: int
    target_id: str
    release_id: str
    profile_id: str
    name: str
    status: str
    template_pack_id: str | None = None
    template_hash: str | None = None
    template_source: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    latest_qa_summary: dict[str, Any] = field(default_factory=dict)
    latest_export_summary: dict[str, Any] = field(default_factory=dict)
    latest_signoff_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "target_id": self.target_id,
                "release_id": self.release_id,
                "profile_id": self.profile_id,
                "name": self.name,
                "status": self.status,
                "template_pack_id": self.template_pack_id,
                "template_hash": self.template_hash,
                "template_source": self.template_source,
                "options": self.options,
                "latest_qa_summary": self.latest_qa_summary,
                "latest_export_summary": self.latest_export_summary,
                "latest_signoff_summary": self.latest_signoff_summary,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DistributionTarget":
        created_at = str(data.get("created_at") or now_iso())
        profile_id = _safe_id(data.get("profile_id"), default="generic_dsp")
        profile = get_distribution_profile(profile_id)
        template_pack_id = _optional_id(data.get("template_pack_id"))
        template_hash = _optional_text(data.get("template_hash"), 128)
        template_source = _optional_text(data.get("template_source"), 80)
        rules = data.get("template_rules") if isinstance(data.get("template_rules"), dict) else {}
        options = _merge_target_options(profile, rules, data.get("options") if isinstance(data.get("options"), dict) else {})
        status = str(data.get("status") or "draft")
        if status not in DISTRIBUTION_TARGET_STATUSES:
            status = "draft"
        return cls(
            schema_version=int(data.get("schema_version", DISTRIBUTION_TARGET_SCHEMA_VERSION) or DISTRIBUTION_TARGET_SCHEMA_VERSION),
            target_id=_validate_target_id(str(data.get("target_id") or "target-000001")),
            release_id=str(data.get("release_id") or ""),
            profile_id=profile_id,
            name=_safe_text(data.get("name"), 120) or profile.get("name") or "Distribution Target",
            status=status,
            template_pack_id=template_pack_id,
            template_hash=template_hash,
            template_source=template_source,
            options=options,
            latest_qa_summary=_safe_dict(data.get("latest_qa_summary")),
            latest_export_summary=_safe_dict(data.get("latest_export_summary")),
            latest_signoff_summary=_safe_dict(data.get("latest_signoff_summary")),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
        )


class DistributionStore:
    def __init__(self, release_store: ReleaseStore) -> None:
        self.release_store = release_store
        self.lock = threading.RLock()

    def distribution_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / DISTRIBUTION_ROOT_NAME

    def targets_dir(self, release_id: str) -> Path:
        return self.distribution_dir(release_id) / "targets"

    def target_path(self, release_id: str, target_id: str) -> Path:
        return self.targets_dir(release_id) / f"{_validate_target_id(target_id)}.json"

    def qa_path(self, release_id: str, target_id: str) -> Path:
        return self.distribution_dir(release_id) / "qa" / f"{_validate_target_id(target_id)}-qa.json"

    def layout_path(self, release_id: str, target_id: str) -> Path:
        return self.distribution_dir(release_id) / "layout" / f"{_validate_target_id(target_id)}-layout.json"

    def artwork_dir(self, release_id: str) -> Path:
        return self.distribution_dir(release_id) / "artwork"

    def packages_dir(self, release_id: str) -> Path:
        return self.distribution_dir(release_id) / "packages"

    def package_dir(self, release_id: str, package_id: str) -> Path:
        return self.packages_dir(release_id) / _validate_package_id(package_id)

    def export_dir(self, release_id: str, package_id: str) -> Path:
        return self.package_dir(release_id, package_id) / "distribution-export"

    def package_zip_path(self, release_id: str, package_id: str) -> Path:
        return self.package_dir(release_id, package_id) / "distribution-package.zip"

    def signoff_path(self, release_id: str, package_id: str) -> Path:
        return self.package_dir(release_id, package_id) / "distribution-signoff.json"

    def signoff_history_path(self, release_id: str, package_id: str) -> Path:
        return self.package_dir(release_id, package_id) / "signoff-history.jsonl"

    def list_targets(self, release_id: str) -> list[DistributionTarget]:
        self.release_store.get_release(release_id)
        targets: list[DistributionTarget] = []
        for path in sorted(self.targets_dir(release_id).glob("target-*.json")):
            try:
                targets.append(DistributionTarget.from_dict(read_json(path)))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return sorted(targets, key=lambda item: item.updated_at, reverse=True)

    def get_target(self, release_id: str, target_id: str) -> DistributionTarget:
        self.release_store.get_release(release_id)
        path = self.target_path(release_id, target_id)
        if not path.exists():
            raise DistributionNotFoundError(target_id)
        return DistributionTarget.from_dict(read_json(path))

    def create_target(self, release_id: str, payload: dict[str, Any]) -> DistributionTarget:
        with self.lock:
            release = self.release_store.get_release(release_id)
            if release.status == "archived":
                raise DistributionStateError("Archived releases cannot create distribution targets.")
            target_id = self._reserve_target_id(release_id)
            now = now_iso()
            profile_id = _safe_id(payload.get("profile_id"), default="generic_dsp")
            profile = get_distribution_profile(profile_id)
            template = self._template_from_payload(payload)
            rules = template_rules(template)
            target = DistributionTarget(
                schema_version=DISTRIBUTION_TARGET_SCHEMA_VERSION,
                target_id=target_id,
                release_id=release_id,
                profile_id=profile_id,
                name=_safe_text(payload.get("name"), 120) or str(profile.get("name") or "Distribution Target"),
                status="draft",
                template_pack_id=template.get("template_pack_id") if template else None,
                template_hash=template.get("template_hash") if template else None,
                template_source=template.get("source") if template else None,
                options=_merge_target_options(profile, rules, payload.get("options") if isinstance(payload.get("options"), dict) else {}),
                created_at=now,
                updated_at=now,
            )
            self.save_target(target, touch=False)
            self.append_event(release_id, "distribution_target_created", {"target_id": target_id, "profile_id": profile_id, "template_pack_id": target.template_pack_id})
            return target

    def update_target(self, release_id: str, target_id: str, patch: dict[str, Any]) -> DistributionTarget:
        with self.lock:
            target = self.get_target(release_id, target_id)
            self.ensure_target_mutable(release_id, target)
            if "profile_id" in patch:
                target.profile_id = _safe_id(patch.get("profile_id"), default=target.profile_id)
            profile = get_distribution_profile(target.profile_id)
            template = self.resolve_target_template(target)
            if "template_pack_id" in patch:
                template = self._template_from_payload(patch)
                target.template_pack_id = template.get("template_pack_id") if template else None
                target.template_hash = template.get("template_hash") if template else None
                target.template_source = template.get("source") if template else None
            if "name" in patch:
                target.name = _safe_text(patch.get("name"), 120) or target.name
            rules = template_rules(template)
            if "options" in patch and isinstance(patch.get("options"), dict):
                target.options = _merge_target_options(profile, rules, {**target.options, **patch["options"]})
            elif "profile_id" in patch or "template_pack_id" in patch:
                target.options = _merge_target_options(profile, rules, target.options)
            target.latest_qa_summary = _stale_summary(target.latest_qa_summary, "target_updated")
            target.latest_export_summary = _stale_summary(target.latest_export_summary, "target_updated")
            self.save_target(target)
            self.append_event(release_id, "distribution_target_updated", {"target_id": target.target_id})
            return target

    def delete_target(self, release_id: str, target_id: str) -> dict[str, Any]:
        with self.lock:
            target = self.get_target(release_id, target_id)
            self.ensure_target_mutable(release_id, target)
            path = self.target_path(release_id, target_id)
            if path.exists():
                path.unlink()
            self.append_event(release_id, "distribution_target_deleted", {"target_id": target_id})
            return {"target_id": target_id, "deleted": True}

    def save_target(self, target: DistributionTarget, *, touch: bool = True) -> DistributionTarget:
        if target.status not in DISTRIBUTION_TARGET_STATUSES:
            raise DistributionValidationError(f"Unsupported distribution target status: {target.status}.")
        if touch:
            target.updated_at = now_iso()
        path = self.target_path(target.release_id, target.target_id)
        write_json(path, target.to_dict())
        return target

    def update_qa_summary(self, release_id: str, target_id: str, summary: dict[str, Any]) -> DistributionTarget:
        target = self.get_target(release_id, target_id)
        target.latest_qa_summary = _safe_dict(summary)
        status = str(summary.get("status") or "")
        if target.status not in {"signed", "archived"}:
            target.status = {"passed": "qa_passed", "warning": "qa_warning", "failed": "qa_failed", "stale": "qa_failed"}.get(status, target.status)
        return self.save_target(target)

    def update_export_summary(self, release_id: str, target_id: str, summary: dict[str, Any]) -> DistributionTarget:
        target = self.get_target(release_id, target_id)
        target.latest_export_summary = _safe_dict(summary)
        if target.status not in {"signed", "archived"}:
            target.status = "exported"
        return self.save_target(target)

    def update_signoff_summary(self, release_id: str, target_id: str, summary: dict[str, Any]) -> DistributionTarget:
        target = self.get_target(release_id, target_id)
        target.latest_signoff_summary = _safe_dict(summary)
        if str(summary.get("status") or "") in SIGNED_DISTRIBUTION_STATUSES and target.status != "archived":
            target.status = "signed"
        return self.save_target(target)

    def read_qa(self, release_id: str, target_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.qa_path(release_id, target_id)
        if not path.exists():
            if default is not None:
                return default
            raise DistributionNotFoundError("Distribution QA does not exist.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_qa(self, release_id: str, target_id: str, report: dict[str, Any]) -> dict[str, Any]:
        self.get_target(release_id, target_id)
        clean = sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.qa_path(release_id, target_id), clean)
        return clean

    def read_layout(self, release_id: str, target_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.layout_path(release_id, target_id)
        if not path.exists():
            if default is not None:
                return default
            raise DistributionNotFoundError("Distribution layout does not exist.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_layout(self, release_id: str, target_id: str, layout: dict[str, Any]) -> dict[str, Any]:
        self.get_target(release_id, target_id)
        clean = sanitize_metadata(layout, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.layout_path(release_id, target_id), clean)
        return clean

    def template_store(self) -> TemplatePackStore:
        return TemplatePackStore(self.release_store.root.parent / "distribution-templates")

    def resolve_target_template(self, target: DistributionTarget) -> dict[str, Any]:
        if not target.template_pack_id:
            return {}
        try:
            template = self.template_store().get_template(target.template_pack_id)
        except ValueError:
            return {}
        return template

    def target_template_summary(self, target: DistributionTarget) -> dict[str, Any]:
        template = self.resolve_target_template(target)
        return template_summary(template) if template else {}

    def targets_using_template(self, template_pack_id: str) -> list[DistributionTarget]:
        template_id = _optional_id(template_pack_id)
        if not template_id:
            return []
        matches: list[DistributionTarget] = []
        for release in self.release_store.list_releases(include_hidden=True):
            for target in self.list_targets(release.release_id):
                if target.template_pack_id == template_id:
                    matches.append(target)
        return sorted(matches, key=lambda item: (item.release_id, item.target_id))

    def ensure_template_pack_mutable(self, template_pack_id: str) -> None:
        blockers = [target for target in self.targets_using_template(template_pack_id) if self._target_has_signed_package(target)]
        if blockers:
            ids = ", ".join(f"{target.release_id}/{target.target_id}" for target in blockers[:5])
            suffix = "..." if len(blockers) > 5 else ""
            raise DistributionStateError(
                f"Distribution template pack is bound to signed distribution target(s): {ids}{suffix}. "
                "Reset distribution signoff before changing this template."
            )

    def ensure_template_pack_deletable(self, template_pack_id: str) -> None:
        targets = self.targets_using_template(template_pack_id)
        if not targets:
            return
        signed_targets = [target for target in targets if self._target_has_signed_package(target)]
        blockers = signed_targets or targets
        ids = ", ".join(f"{target.release_id}/{target.target_id}" for target in blockers[:5])
        suffix = "..." if len(blockers) > 5 else ""
        if signed_targets:
            raise DistributionStateError(
                f"Distribution template pack is bound to signed distribution target(s): {ids}{suffix}. "
                "Reset distribution signoff before deleting this template."
            )
        raise DistributionStateError(
            f"Distribution template pack is bound to distribution target(s): {ids}{suffix}. "
            "Unbind dependent targets before deleting this template."
        )

    def mark_template_dependents_stale(self, template_pack_id: str, reason: str) -> list[dict[str, Any]]:
        stale_targets: list[dict[str, Any]] = []
        with self.lock:
            for target in self.targets_using_template(template_pack_id):
                if self._target_has_signed_package(target):
                    continue
                before_qa = target.latest_qa_summary
                before_export = target.latest_export_summary
                target.latest_qa_summary = _stale_summary(target.latest_qa_summary, reason)
                target.latest_export_summary = _stale_summary(target.latest_export_summary, reason)
                if target.latest_qa_summary == before_qa and target.latest_export_summary == before_export:
                    continue
                self.save_target(target)
                self.append_event(
                    target.release_id,
                    "distribution_template_dependency_stale",
                    {"target_id": target.target_id, "template_pack_id": target.template_pack_id, "reason": reason},
                )
                stale_targets.append(distribution_target_summary(target))
        return stale_targets

    def latest_package_id(self, target: DistributionTarget) -> str | None:
        summary = target.latest_export_summary if isinstance(target.latest_export_summary, dict) else {}
        package_id = str(summary.get("package_id") or "").strip()
        return _validate_package_id(package_id) if package_id else None

    def reserve_package_id(self, release_id: str) -> str:
        packages_dir = self.packages_dir(release_id)
        packages_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            package_id = f"package-{index:06d}"
            package_dir = packages_dir / package_id
            try:
                package_dir.mkdir(parents=True, exist_ok=False)
                return package_id
            except FileExistsError:
                continue
        raise DistributionValidationError("Unable to allocate a unique distribution package id.")

    def read_signoff(self, release_id: str, target: DistributionTarget, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
        package_id = self.latest_package_id(target)
        if not package_id:
            if default is not None:
                return default
            raise DistributionNotFoundError("Distribution package does not exist.")
        path = self.signoff_path(release_id, package_id)
        if not path.exists():
            if default is not None:
                return default
            raise DistributionNotFoundError("Distribution signoff does not exist.")
        value = read_json(path)
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def write_signoff(self, release_id: str, package_id: str, record: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        write_json(self.signoff_path(release_id, package_id), clean)
        return clean

    def reset_signoff(self, release_id: str, target_id: str, reason: str) -> dict[str, Any]:
        with self.lock:
            target = self.get_target(release_id, target_id)
            package_id = self.latest_package_id(target)
            if not package_id:
                target.latest_signoff_summary = {"status": "not_signed"}
                if target.status == "signed":
                    target.status = "exported"
                    self.save_target(target)
                return {"status": "not_signed", "target_id": target_id}
            existing = self.read_signoff(release_id, target, default={})
            event = distribution_signoff_history_event(existing, reason=reason, now=now_iso())
            if existing:
                history_path = self.signoff_history_path(release_id, package_id)
                history_path.parent.mkdir(parents=True, exist_ok=True)
                with history_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event, ensure_ascii=False) + "\n")
            signoff_path = self.signoff_path(release_id, package_id)
            if signoff_path.exists():
                signoff_path.unlink()
            export_sidecar = self.export_dir(release_id, package_id) / "distribution-signoff.json"
            if export_sidecar.exists():
                export_sidecar.unlink()
            target.latest_signoff_summary = {"status": "not_signed"}
            if target.status == "signed":
                target.status = "exported" if target.latest_export_summary.get("exists") else "qa_passed"
            self.save_target(target)
            self.append_event(release_id, "distribution_signoff_reset", {"target_id": target_id, "reason": event.get("reason")})
            return event

    def any_signed_target(self, release_id: str) -> bool:
        return any(target.status == "signed" or target.latest_signoff_summary.get("status") in SIGNED_DISTRIBUTION_STATUSES for target in self.list_targets(release_id))

    def ensure_target_mutable(self, release_id: str, target: DistributionTarget) -> None:
        if target.status == "archived":
            raise DistributionStateError("Archived distribution targets are read-only.")
        if self._target_has_signed_package(target):
            raise DistributionStateError("Signed distribution packages cannot be modified. Reset distribution signoff before changing this target.")

    def _target_has_signed_package(self, target: DistributionTarget) -> bool:
        if target.status == "signed" or target.latest_signoff_summary.get("status") in SIGNED_DISTRIBUTION_STATUSES:
            return True
        signoff = self.read_signoff(target.release_id, target, default={})
        return signoff.get("status") in SIGNED_DISTRIBUTION_STATUSES

    def append_event(self, release_id: str, event_type: str, payload: dict[str, Any]) -> None:
        path = self.distribution_dir(release_id) / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def read_events(self, release_id: str) -> list[dict[str, Any]]:
        path = self.distribution_dir(release_id) / "events.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return sanitize_metadata(events, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

    def summary(self, release_id: str) -> dict[str, Any]:
        targets = self.list_targets(release_id)
        return sanitize_metadata(
            {
                "target_count": len(targets),
                "signed_target_count": sum(1 for target in targets if target.status == "signed"),
                "latest_target_id": targets[0].target_id if targets else None,
                "latest_status": targets[0].status if targets else "missing",
                "template_target_count": sum(1 for target in targets if target.template_pack_id),
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        )

    def _reserve_target_id(self, release_id: str) -> str:
        self.targets_dir(release_id).mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            target_id = f"target-{index:06d}"
            path = self.target_path(release_id, target_id)
            if not path.exists():
                return target_id
        raise DistributionValidationError("Unable to allocate a unique distribution target id.")

    def _template_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = str(payload.get("template_pack_id") or "").strip()
        if not raw:
            return {}
        return self.template_store().get_template(raw)


def distribution_target_summary(target: DistributionTarget | dict[str, Any] | None) -> dict[str, Any]:
    data = target.to_dict() if isinstance(target, DistributionTarget) else target if isinstance(target, dict) else {}
    return sanitize_metadata(
        {
            "target_id": data.get("target_id"),
            "release_id": data.get("release_id"),
            "profile_id": data.get("profile_id"),
            "template_pack_id": data.get("template_pack_id"),
            "template_hash": data.get("template_hash"),
            "template_source": data.get("template_source"),
            "name": data.get("name"),
            "status": data.get("status") or "missing",
            "qa_status": (data.get("latest_qa_summary") or {}).get("status") if isinstance(data.get("latest_qa_summary"), dict) else None,
            "export_status": (data.get("latest_export_summary") or {}).get("status") if isinstance(data.get("latest_export_summary"), dict) else None,
            "package_id": (data.get("latest_export_summary") or {}).get("package_id") if isinstance(data.get("latest_export_summary"), dict) else None,
            "signoff_status": (data.get("latest_signoff_summary") or {}).get("status") if isinstance(data.get("latest_signoff_summary"), dict) else None,
            "updated_at": data.get("updated_at"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def distribution_signoff_summary(record: dict[str, Any] | None) -> dict[str, Any]:
    data = record if isinstance(record, dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "not_signed",
            "release_id": data.get("release_id"),
            "target_id": data.get("target_id"),
            "package_id": data.get("package_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "qa_source_hash": data.get("qa_source_hash"),
            "export_manifest_hash": data.get("export_manifest_hash"),
            "forced": bool(data.get("forced", False)),
            "encoded_audio_acceptance": data.get("encoded_audio_acceptance") if isinstance(data.get("encoded_audio_acceptance"), dict) else {},
            "format_decision": data.get("format_decision") if isinstance(data.get("format_decision"), dict) else {},
            "rights_clearance": data.get("rights_clearance") if isinstance(data.get("rights_clearance"), dict) else {},
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def build_distribution_signoff_record(
    *,
    release_id: str,
    target: DistributionTarget,
    package_id: str,
    qa_report: dict[str, Any],
    payload: dict[str, Any] | None = None,
    export_manifest: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    payload = payload or {}
    force = bool(payload.get("force", False))
    if force and not str(payload.get("override_reason") or "").strip():
        raise ValueError("override_reason is required when force=true.")
    blockers = qa_report.get("blockers", []) if isinstance(qa_report.get("blockers"), list) else []
    warnings = qa_report.get("warnings", []) if isinstance(qa_report.get("warnings"), list) else []
    if not force and (qa_report.get("status") not in {"passed", "warning"} or blockers):
        raise ValueError("Distribution QA does not allow signoff.")
    record = {
        "schema_version": 1,
        "release_id": release_id,
        "target_id": target.target_id,
        "package_id": package_id,
        "profile_id": target.profile_id,
        "status": "force_signed" if force else "signed",
        "signed_at": now,
        "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
        "qa_source_hash": qa_report.get("source_hash"),
        "distribution_source_hash": qa_report.get("source_hash"),
        "export_manifest_hash": stable_hash(export_manifest) if isinstance(export_manifest, dict) and export_manifest else None,
        "forced": force,
        "override_reason": _safe_text(payload.get("override_reason"), 500) if force else None,
        "acknowledged_blockers": blockers if force else [],
        "acknowledged_warnings": warnings,
        "encoded_audio_acceptance": payload.get("encoded_audio_acceptance") if isinstance(payload.get("encoded_audio_acceptance"), dict) else {},
        "format_decision": payload.get("format_decision") if isinstance(payload.get("format_decision"), dict) else {},
        "rights_clearance": payload.get("rights_clearance") if isinstance(payload.get("rights_clearance"), dict) else {},
        "notes": _safe_text(payload.get("notes"), 2000),
    }
    return sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def distribution_signoff_history_event(record: dict[str, Any], *, reason: str, now: str | None = None) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "timestamp": now or now_iso(),
            "event": "distribution_signoff_reset",
            "reason": sanitize_sensitive_text(str(reason or ""))[:500],
            "previous_summary": distribution_signoff_summary(record),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def remove_distribution_dir(store: DistributionStore, release_id: str) -> None:
    path = store.distribution_dir(release_id)
    root = store.release_store.release_dir(release_id).resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise DistributionValidationError("Refusing to operate outside release distribution boundaries.") from exc
    if path.exists():
        shutil.rmtree(path)


def _stale_summary(summary: dict[str, Any] | None, reason: str) -> dict[str, Any]:
    data = dict(summary or {})
    if data:
        data["stale"] = True
        data["status"] = "stale"
        data["stale_reason"] = reason
    return sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _safe_dict(value: Any) -> dict[str, Any]:
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _safe_id(value: Any, *, default: str) -> str:
    text = str(value or default).strip().lower().replace(" ", "_")
    if not text:
        return default
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in text):
        raise DistributionValidationError("Identifier contains unsupported characters.")
    return text[:80]


def _optional_id(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in text):
        raise DistributionValidationError("Identifier contains unsupported characters.")
    return text[:80]


def _optional_text(value: Any, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None


def _merge_target_options(profile: dict[str, Any], rules: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    base = merge_profile_options(profile, rules)
    overrides = overrides if isinstance(overrides, dict) else {}
    allowed = set(base) | {"artwork_id", "submission_note"}
    for key, value in overrides.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            base[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            base[key] = value
    return sanitize_metadata(base, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _validate_target_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("target-") or not text.removeprefix("target-").isdigit():
        raise DistributionValidationError("Invalid distribution target id.")
    return text


def _validate_package_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("package-") or not text.removeprefix("package-").isdigit():
        raise DistributionValidationError("Invalid distribution package id.")
    return text
