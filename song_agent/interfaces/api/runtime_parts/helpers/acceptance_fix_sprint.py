from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.interfaces.api.runtime_parts.dependencies.program_dependencies import AnalyticsScope

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import Any, json, parse_qs, unquote

from song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies import sanitize_metadata

def _match_acceptance_fix_sprint_route(path: str) -> tuple[str, list[str]] | None:
    prefix = "/api/acceptance/fix-sprints/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    return parts[0], parts[1:]

def _query_value(query: dict[str, list[str]], name: str) -> str:
    return str(query.get(name, [""])[0] or "").strip()

def _analytics_scope_from_query(query_string: str) -> AnalyticsScope:
    query = parse_qs(query_string)
    return AnalyticsScope.from_values(
        scope_type=_query_value(query, "scope") or "global",
        suite_id=_query_value(query, "suite_id") or None,
        release_id=_query_value(query, "release_id") or None,
        project_id=_query_value(query, "project_id") or None,
    )

def _match_distribution_profile_route(path: str) -> str | None:
    prefix = "/api/distribution/profiles/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or "/" in rest:
        return None
    return unquote(rest)

def _match_distribution_template_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/distribution/template-packs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    parts = [unquote(part) for part in rest.split("/") if part]
    if not parts or parts[0] == "import":
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"clone", "delete", "export", "validate"}:
        return parts[0], parts[1]
    return None

def _match_distribution_target_tail(tail: str) -> tuple[str, str] | None:
    parts = [part for part in tail.strip("/").split("/") if part]
    if len(parts) < 2 or parts[0] != "targets":
        return None
    target_id = unquote(parts[1])
    if len(parts) == 2:
        return target_id, ""
    if parts[2:] == ["delete"]:
        return target_id, "delete"
    if parts[2:] == ["qa"]:
        return target_id, "qa"
    if parts[2:] == ["qa", "refresh"]:
        return target_id, "qa-refresh"
    if parts[2:] == ["checklist"]:
        return target_id, "checklist"
    if parts[2:] == ["layout"] or parts[2:] == ["layout", "refresh"]:
        return target_id, "layout"
    if len(parts) == 5 and parts[2:4] == ["checklist", "items"]:
        return target_id, "checklist-item:" + unquote(parts[4])
    if parts[2:] == ["export"]:
        return target_id, "export"
    if parts[2:] == ["export", "zip"]:
        return target_id, "export-zip"
    if parts[2:] == ["export.zip"]:
        return target_id, "export-zip-download"
    if parts[2:] == ["verify"]:
        return target_id, "verify"
    if parts[2:] == ["signoff"]:
        return target_id, "signoff"
    if parts[2:] == ["signoff", "reset"]:
        return target_id, "signoff-reset"
    return None

def _match_distribution_artwork_tail(tail: str) -> tuple[str, str] | None:
    parts = [part for part in tail.strip("/").split("/") if part]
    if len(parts) < 2 or parts[0] != "artwork":
        return None
    artwork_id = unquote(parts[1])
    if len(parts) == 2:
        return artwork_id, ""
    if len(parts) == 3 and parts[2] in {"download", "delete"}:
        return artwork_id, parts[2]
    return None

def _match_submission_tail(tail: str) -> tuple[str, str, str | None] | None:
    parts = [unquote(part) for part in tail.strip("/").split("/") if part]
    if not parts:
        return None
    if parts[0] == "batches" and len(parts) >= 2:
        parts = parts[1:]
    submission_id = parts[0]
    if len(parts) == 1:
        return submission_id, "", None
    rest = parts[1:]
    if rest == ["targets"]:
        return submission_id, "targets", None
    if rest == ["refresh"]:
        return submission_id, "refresh", None
    if rest == ["qa"]:
        return submission_id, "qa", None
    if rest == ["qa", "refresh"]:
        return submission_id, "qa-refresh", None
    if rest == ["export"]:
        return submission_id, "export", None
    if rest == ["export", "zip"]:
        return submission_id, "export-zip", None
    if rest == ["export.zip"]:
        return submission_id, "export-zip-download", None
    if rest == ["signoff"]:
        return submission_id, "signoff", None
    if rest == ["signoff", "reset"]:
        return submission_id, "signoff-reset", None
    if rest == ["verify"]:
        return submission_id, "verify", None
    if rest == ["evidence"]:
        return submission_id, "evidence", None
    if rest == ["evidence", "report", "refresh"]:
        return submission_id, "evidence-report-refresh", None
    if rest == ["evidence", "export"]:
        return submission_id, "evidence-export", None
    if rest == ["evidence", "export", "zip"]:
        return submission_id, "evidence-export-zip", None
    if rest == ["evidence", "export.zip"]:
        return submission_id, "evidence-export-zip-download", None
    if rest == ["evidence", "signoff"]:
        return submission_id, "evidence-signoff", None
    if rest == ["evidence", "signoff", "reset"]:
        return submission_id, "evidence-signoff-reset", None
    if rest == ["evidence", "verify"]:
        return submission_id, "evidence-verify", None
    if rest == ["archive"]:
        return submission_id, "archive", None
    if len(rest) == 4 and rest[0] == "items" and rest[2] == "evidence":
        item_id = rest[1]
        action = rest[3]
        if action == "attachments":
            return submission_id, "evidence-upload-attachment", item_id
        if action == "submission-receipt":
            return submission_id, "evidence-submission-receipt", item_id
        if action == "feedback":
            return submission_id, "evidence-feedback", item_id
        if action == "acceptance":
            return submission_id, "evidence-acceptance", item_id
        if action == "resubmission-round":
            return submission_id, "evidence-resubmission-round", item_id
    if len(rest) == 3 and rest[0] == "items":
        item_id = rest[1]
        action = rest[2]
        if action == "remove":
            return submission_id, "remove-item", item_id
        if action == "record-submission":
            return submission_id, "record-submission", item_id
        if action == "record-feedback":
            return submission_id, "record-feedback", item_id
        if action == "accepted":
            return submission_id, "mark-accepted", item_id
    return None

def _match_release_track_tail(tail: str) -> tuple[str, str] | None:
    parts = [part for part in tail.strip("/").split("/") if part]
    if len(parts) != 3 or parts[0] != "tracks":
        return None
    action = parts[2]
    if action not in {"refresh", "remove"}:
        return None
    return unquote(parts[1]), action

def _merge_editor_patch_metadata(left: ImplementationDocument | None, right: ImplementationDocument | None) -> ImplementationDocument:
    merged: dict[str, Any] = {}
    for source in (left, right):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if key in {"clip_inserts", "template_inserts"}:
                continue
            merged[key] = value
    inserts: list[dict[str, Any]] = []
    template_inserts: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_templates: set[str] = set()
    for source in (left, right):
        raw_inserts = source.get("clip_inserts") if isinstance(source, dict) else None
        if not isinstance(raw_inserts, list):
            continue
        for item in raw_inserts:
            if not isinstance(item, dict):
                continue
            group_id = str(item.get("clip_group_id") or "")
            key = group_id or json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            inserts.append(sanitize_metadata(dict(item)))
    if inserts:
        merged["clip_inserts"] = inserts[:20]
    for source in (left, right):
        raw_inserts = source.get("template_inserts") if isinstance(source, dict) else None
        if not isinstance(raw_inserts, list):
            continue
        for item in raw_inserts:
            if not isinstance(item, dict):
                continue
            group_id = str(item.get("template_group_id") or "")
            key = group_id or json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen_templates:
                continue
            seen_templates.add(key)
            template_inserts.append(sanitize_metadata(dict(item)))
    if template_inserts:
        merged["template_inserts"] = template_inserts[:20]
    return sanitize_metadata(merged)

def _match_editor_template_route(path: str) -> tuple[str, str, str] | None:
    prefix = "/api/editor-templates/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    parts = rest.split("/")
    if len(parts) < 2 or parts[0] not in {"sections", "tracks"}:
        return None
    template_id = unquote(parts[1])
    tail = "" if len(parts) == 2 else "/" + "/".join(parts[2:])
    return parts[0], template_id, tail

def _match_edit_preset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/edit-presets/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "reset":
        return None
    if "/" in rest:
        preset_id, tail = rest.split("/", 1)
        return unquote(preset_id), "/" + tail
    return unquote(rest), ""

def _match_prompt_template_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/prompt-templates/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "reset":
        return None
    if "/" in rest:
        template_id, tail = rest.split("/", 1)
        return unquote(template_id), "/" + tail
    return unquote(rest), ""

def _match_asset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/assets/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest.startswith("extract/"):
        return None
    if "/" in rest:
        asset_id, tail = rest.split("/", 1)
        return unquote(asset_id), "/" + tail
    return unquote(rest), ""

def _match_reference_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/references/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "import":
        return None
    if "/" in rest:
        reference_id, tail = rest.split("/", 1)
        return unquote(reference_id), "/" + tail
    return unquote(rest), ""

__all__ = ['_analytics_scope_from_query', '_match_acceptance_fix_sprint_route', '_match_asset_route', '_match_distribution_artwork_tail', '_match_distribution_profile_route', '_match_distribution_target_tail', '_match_distribution_template_route', '_match_edit_preset_route', '_match_editor_template_route', '_match_prompt_template_route', '_match_reference_route', '_match_release_track_tail', '_match_submission_tail', '_merge_editor_patch_metadata', '_query_value']
