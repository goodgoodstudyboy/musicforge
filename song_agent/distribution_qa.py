from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from song_agent.distribution import DistributionStore, DistributionTarget
from song_agent.distribution_artwork import distribution_artwork_file_path, latest_distribution_artwork, read_distribution_artwork
from song_agent.distribution_checklist import checklist_checks, checklist_summary, reconcile_distribution_checklist, read_distribution_checklist
from song_agent.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS, get_distribution_profile
from song_agent.distribution_templates import resolve_mapping_source, template_mapping, template_summary
from song_agent.projectio import read_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata
from song_agent.release_export import read_release_export_manifest
from song_agent.release_metadata import read_release_metadata, read_release_metadata_qa, release_metadata_source_hash
from song_agent.release_metadata_qa import mark_release_metadata_qa_stale
from song_agent.release_verifier import verify_release_zip, verification_summary
from song_agent.releases import ReleaseDocument, stable_hash


DISTRIBUTION_QA_SCHEMA_VERSION = 1
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def build_distribution_qa_report(
    *,
    store: DistributionStore,
    release_id: str,
    target: DistributionTarget,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    release = store.release_store.get_release(release_id)
    source = distribution_source_state(store=store, release=release, target=target)
    checks = _checks(store, release, target, source)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check.get("status") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    source_hash = stable_hash(source)
    report = {
        "schema_version": DISTRIBUTION_QA_SCHEMA_VERSION,
        "release_id": release_id,
        "target_id": target.target_id,
        "profile_id": target.profile_id,
        "generated_at": now,
        "status": status,
        "source_hash": source_hash,
        "source": source,
        "checks": checks,
        "blockers": [_check_message(check) for check in blockers],
        "warnings": [_check_message(check) for check in warnings],
        "summary": {
            "status": status,
            "target_id": target.target_id,
            "profile_id": target.profile_id,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "source_hash": source_hash,
            "generated_at": now,
        },
    }
    return sanitize_metadata(report, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def distribution_source_state(*, store: DistributionStore, release: ReleaseDocument, target: DistributionTarget) -> dict[str, Any]:
    export_manifest = _safe_release_export_manifest(store, release.release_id)
    release_zip_path = store.release_store.zip_path(release.release_id)
    release_signoff = store.release_store.read_signoff(release.release_id, default={})
    metadata = read_release_metadata(store.release_store, release.release_id, default={})
    metadata_qa = read_release_metadata_qa(store.release_store, release.release_id, default={}) if metadata else {}
    metadata_source = release_metadata_source_hash(release, metadata) if metadata else None
    artwork = _selected_artwork(store, release.release_id, target)
    profile = get_distribution_profile(target.profile_id)
    template = store.resolve_target_template(target)
    checklist = reconcile_distribution_checklist(store, release.release_id, target, template, write=False) if template else {}
    return sanitize_metadata(
        {
            "release": {
                "release_id": release.release_id,
                "name": release.name,
                "status": release.status,
                "track_count": len(release.tracks),
                "hidden": release.hidden,
                "updated_at": release.updated_at,
            },
            "target": {
                "target_id": target.target_id,
                "profile_id": target.profile_id,
                "template_pack_id": target.template_pack_id,
                "template_hash": target.template_hash,
                "options": target.options,
            },
            "profile_hash": profile.get("profile_hash"),
            "template": template_summary(template),
            "checklist": checklist_summary(checklist) if checklist else {},
            "release_export_manifest_hash": stable_hash({key: value for key, value in export_manifest.items() if key != "zip"}) if export_manifest else None,
            "release_zip_sha256": _sha256_file(release_zip_path),
            "release_signoff_hash": stable_hash(release_signoff) if release_signoff else None,
            "release_signoff_status": release_signoff.get("status"),
            "metadata_hash": stable_hash(metadata) if metadata else None,
            "metadata_source_hash": metadata_source,
            "metadata_qa_hash": stable_hash(metadata_qa) if metadata_qa else None,
            "metadata_qa_source_hash": metadata_qa.get("source_hash"),
            "artwork_hash": stable_hash(artwork) if artwork else None,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def distribution_qa_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or summary.get("status") or "missing",
            "target_id": data.get("target_id") or summary.get("target_id"),
            "profile_id": data.get("profile_id") or summary.get("profile_id"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "source_hash": data.get("source_hash") or summary.get("source_hash"),
            "generated_at": data.get("generated_at") or summary.get("generated_at"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def distribution_qa_allows_export(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> bool:
    if not isinstance(report, dict):
        return False
    if report.get("status") not in {"passed", "warning"}:
        return False
    if current_source_hash and report.get("source_hash") != current_source_hash:
        return False
    return True


def mark_distribution_qa_stale(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> dict[str, Any]:
    data = dict(report or {})
    data["status"] = "stale"
    data["stale"] = True
    if current_source_hash:
        data["current_source_hash"] = current_source_hash
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    summary["status"] = "stale"
    if current_source_hash:
        summary["current_source_hash"] = current_source_hash
    data["summary"] = summary
    return sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def csv_formula_cells(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error:
        return [{"row": 0, "column": 0, "message": "CSV parse failed."}]
    for row_index, row in enumerate(rows, start=1):
        for column_index, cell in enumerate(row, start=1):
            if _formula_cell(cell):
                findings.append({"row": row_index, "column": column_index, "value_prefix": cell[:1], "message": "CSV cell starts with a formula prefix."})
    return findings


def raw_metadata_formula_findings(value: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def walk(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                walk(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(item, str) and _formula_cell(item):
            findings.append({"path": path, "value_prefix": item[:1], "message": "Metadata value starts with a CSV formula prefix."})

    walk(value, "")
    return sanitize_metadata(findings, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _checks(store: DistributionStore, release: ReleaseDocument, target: DistributionTarget, source: dict[str, Any]) -> list[dict[str, Any]]:
    options = target.options if isinstance(target.options, dict) else {}
    checks: list[dict[str, Any]] = []
    export_manifest = _safe_release_export_manifest(store, release.release_id)
    release_zip_path = store.release_store.zip_path(release.release_id)
    release_signoff = store.release_store.read_signoff(release.release_id, default={})
    metadata = read_release_metadata(store.release_store, release.release_id, default={})
    metadata_qa = read_release_metadata_qa(store.release_store, release.release_id, default={}) if metadata else {}
    template = store.resolve_target_template(target)
    checklist = reconcile_distribution_checklist(store, release.release_id, target, template, write=False) if template else {}

    checks.append(_check("release_exists", False, "blocking", "Release exists."))
    checks.append(_check("release_not_hidden", bool(release.hidden), "blocking", "Release must not be hidden."))
    signed_ok = release.status == "signed" and release_signoff.get("status") in {"signed", "force_signed"}
    checks.append(_check("release_signed", not signed_ok, "blocking", "Release Signoff must exist and be current."))
    checks.append(_check("release_export_exists", not bool(export_manifest), "blocking", "Signed Release Export must exist."))
    checks.append(_check("release_zip_exists", not release_zip_path.exists(), "blocking", "Signed Release ZIP must exist."))
    if release_zip_path.exists():
        verify = verify_release_zip(release_zip_path, require_audio=bool(options.get("require_audio", False)))
        status = verify.get("status")
        checks.append(
            _check(
                "release_zip_verify",
                status not in {"passed", "warning"},
                "blocking",
                f"verify-release status is {status}.",
                extra={"verification_summary": verification_summary(verify)},
            )
        )
    metadata_summary = export_manifest.get("metadata") if isinstance(export_manifest.get("metadata"), dict) else {}
    checks.append(_check("metadata_exists", not bool(metadata), "blocking", "Release metadata must exist."))
    if metadata:
        current_meta_hash = release_metadata_source_hash(release, metadata)
        if metadata_qa and metadata_qa.get("source_hash") != current_meta_hash:
            metadata_qa = mark_release_metadata_qa_stale(metadata_qa, current_source_hash=current_meta_hash)
        checks.append(_check("metadata_qa_current", not metadata_qa or metadata_qa.get("status") not in {"passed", "warning"}, "blocking", "Release Metadata QA must be passed or warning and current."))
        checks.append(_check("metadata_export_present", not metadata_summary.get("exists"), "blocking", "Release Metadata Export must be present in signed Release Export."))
        checks.extend(_identifier_checks(metadata, options))
        if template:
            checks.extend(_mapping_checks(metadata, template))
        formula_warnings = raw_metadata_formula_findings(metadata)
        checks.append(_check("metadata_csv_formula_source", bool(formula_warnings), "warning", "Raw metadata contains CSV formula-prefixed values.", count=len(formula_warnings), extra={"findings": formula_warnings[:20]}))
    for csv_name in ("platform-metadata.csv", "credits.csv"):
        path = store.release_store.export_dir(release.release_id) / csv_name
        if path.exists():
            try:
                formula = csv_formula_cells(path.read_text(encoding="utf-8"))
            except OSError:
                formula = [{"row": 0, "column": 0, "message": "CSV could not be read."}]
            checks.append(_check(f"{csv_name.replace('-', '_').replace('.', '_')}_formula_safe", bool(formula), "warning", f"{csv_name} contains formula-prefixed cells; Distribution Export will escape them.", count=len(formula), extra={"findings": formula[:20]}))
    if bool(options.get("require_audio", False)):
        missing_audio = _missing_release_export_audio(store, release.release_id, export_manifest)
        checks.append(_check("audio_wav_present", bool(missing_audio), "blocking", "Each track must include song.wav for this profile.", count=len(missing_audio), extra={"missing": missing_audio[:20]}))
    artwork = _selected_artwork(store, release.release_id, target)
    require_artwork = bool(options.get("require_artwork", False))
    checks.append(_check("artwork_exists", require_artwork and not artwork, "blocking", "Artwork is required for this profile."))
    if artwork:
        checks.extend(_artwork_checks(store, release.release_id, artwork, options))
    if template:
        if target.template_hash and template.get("template_hash") != target.template_hash:
            checks.append(_check("template_current", True, "blocking", "Distribution template pack has changed since target binding. Rebind or refresh target template."))
        else:
            checks.append(_check("template_current", False, "blocking", "Distribution template pack binding is current."))
        checks.extend(checklist_checks(checklist))
    checks.append(_check("source_hash_computable", not bool(source), "blocking", "Distribution source hash can be computed."))
    return [sanitize_metadata(check, blocked_keys=DISTRIBUTION_BLOCKED_KEYS) for check in checks]


def _mapping_checks(metadata: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = template_mapping(template)
    rows = mapping.get("platform_csv") if isinstance(mapping.get("platform_csv"), list) else []
    tracks = metadata.get("tracks") if isinstance(metadata.get("tracks"), list) else []
    checks: list[dict[str, Any]] = []
    missing_required: list[str] = []
    missing_optional = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "")
        column = str(row.get("column") or source)
        for index, track in enumerate(tracks, start=1):
            if not isinstance(track, dict):
                continue
            try:
                value = resolve_mapping_source(source, release_metadata=metadata, track_metadata=track)
            except ValueError:
                missing_required.append(f"{column}:unsupported-source")
                continue
            if str(value or "").strip():
                continue
            if bool(row.get("required", False)):
                missing_required.append(f"{column}:track-{index}")
            else:
                missing_optional += 1
    checks.append(_check("template_mapping_required_fields", bool(missing_required), "blocking", "Template metadata mapping required fields are missing.", count=len(missing_required), extra={"missing": missing_required[:20]}))
    checks.append(_check("template_mapping_optional_fields", missing_optional > 0, "warning", "Template metadata mapping optional fields are missing.", count=missing_optional))
    return checks


def _identifier_checks(metadata: dict[str, Any], options: dict[str, Any]) -> list[dict[str, Any]]:
    release_meta = metadata.get("release") if isinstance(metadata.get("release"), dict) else {}
    tracks = metadata.get("tracks") if isinstance(metadata.get("tracks"), list) else []
    checks: list[dict[str, Any]] = []
    if bool(options.get("require_upc", False)):
        checks.append(_check("upc_required", not str(release_meta.get("upc") or "").strip(), "blocking", "UPC is required for this profile."))
    if bool(options.get("require_isrc", False)):
        missing = [str(item.get("track_id") or index) for index, item in enumerate(tracks, start=1) if isinstance(item, dict) and not str(item.get("isrc") or "").strip()]
        checks.append(_check("isrc_required", bool(missing), "blocking", "ISRC is required for every track in this profile.", count=len(missing), extra={"missing_track_ids": missing[:20]}))
    return checks


def _artwork_checks(store: DistributionStore, release_id: str, artwork: dict[str, Any], options: dict[str, Any]) -> list[dict[str, Any]]:
    path = distribution_artwork_file_path(store, release_id, artwork)
    min_px = int(options.get("artwork_min_px") or 0)
    max_bytes = int(options.get("artwork_max_bytes") or 0)
    width = int(artwork.get("width") or 0)
    height = int(artwork.get("height") or 0)
    checks = [
        _check("artwork_file_exists", not (path.exists() and path.is_file() and not path.is_symlink()), "blocking", "Artwork file exists."),
        _check("artwork_square", bool(options.get("artwork_square", False)) and width != height, "blocking", "Artwork must be square."),
        _check("artwork_min_dimensions", bool(min_px and (width < min_px or height < min_px)), "blocking", f"Artwork must be at least {min_px}px on each side."),
        _check("artwork_size_limit", bool(max_bytes and int(artwork.get("size_bytes") or 0) > max_bytes), "blocking", "Artwork exceeds profile size limit."),
    ]
    return checks


def _selected_artwork(store: DistributionStore, release_id: str, target: DistributionTarget) -> dict[str, Any]:
    artwork_id = str((target.options or {}).get("artwork_id") or "").strip()
    if artwork_id:
        try:
            return read_distribution_artwork(store, release_id, artwork_id)
        except (FileNotFoundError, ValueError):
            return {}
    return latest_distribution_artwork(store, release_id)


def _safe_release_export_manifest(store: DistributionStore, release_id: str) -> dict[str, Any]:
    try:
        return read_release_export_manifest(store.release_store, release_id)
    except (OSError, FileNotFoundError, ValueError, json.JSONDecodeError):
        return {}


def _missing_release_export_audio(store: DistributionStore, release_id: str, manifest: dict[str, Any]) -> list[str]:
    tracks = manifest.get("tracks") if isinstance(manifest.get("tracks"), list) else []
    missing: list[str] = []
    for item in tracks:
        if not isinstance(item, dict):
            continue
        directory = str(item.get("directory") or "").strip("/")
        if not directory:
            continue
        wav = store.release_store.export_dir(release_id) / directory / "song.wav"
        if not wav.exists() or not wav.is_file() or wav.is_symlink() or not _wav_header_ok(wav):
            missing.append(f"{directory}/song.wav")
    return missing


def _wav_header_ok(path: Path) -> bool:
    try:
        data = path.read_bytes()[:12]
    except OSError:
        return False
    return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"


def _formula_cell(cell: str) -> bool:
    text = str(cell or "")
    return bool(text and text.startswith(FORMULA_PREFIXES) and not text.startswith("'"))


def _check(check_id: str, failed: bool, severity: str, message: str, count: int | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "scope": "distribution",
        "check_id": check_id,
        "status": "failed" if failed and severity == "blocking" else "warning" if failed else "passed",
        "severity": severity,
        "message": message,
    }
    if count is not None:
        item["count"] = count
    if extra:
        item.update(extra)
    return sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _check_message(check: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "scope": check.get("scope"),
            "check_id": check.get("check_id"),
            "message": str(check.get("message") or "")[:240],
            "count": check.get("count"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
