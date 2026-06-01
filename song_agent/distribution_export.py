from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent import __version__
from song_agent.distribution import (
    DistributionStore,
    DistributionTarget,
    build_distribution_signoff_record,
    distribution_signoff_summary,
)
from song_agent.distribution_artwork import distribution_artwork_file_path, latest_distribution_artwork, read_distribution_artwork
from song_agent.distribution_checklist import checklist_export_payload, checklist_markdown, checklist_summary, reconcile_distribution_checklist
from song_agent.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS, get_distribution_profile
from song_agent.distribution_layout import (
    build_distribution_layout_plan,
    layout_file_tree_text,
    layout_manifest_payload,
    layout_summary,
)
from song_agent.distribution_templates import resolve_mapping_source, template_mapping, template_summary
from song_agent.distribution_qa import distribution_qa_allows_export, distribution_source_state
from song_agent.projectio import read_json
from song_agent.projects import now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.release_export import read_release_export_manifest
from song_agent.release_metadata import read_release_metadata
from song_agent.release_qa import scan_release_payload_for_sensitive_values
from song_agent.releases import stable_hash
from song_agent.audio_encoding import AudioEncodingStore, resolve_target_audio_format_profiles
from song_agent.encoded_audio_acceptance import export_distribution_encoded_audio_acceptance
from song_agent.format_decisions import FormatDecisionStore


DISTRIBUTION_EXPORT_SCHEMA_VERSION = 1
DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS = {"export_manifest_hash"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


class DistributionExportError(ValueError):
    pass


def build_distribution_export_package(
    *,
    store: DistributionStore,
    release_id: str,
    target: DistributionTarget,
    qa_report: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    store.ensure_target_mutable(release_id, target)
    release = store.release_store.get_release(release_id)
    current_source_hash = stable_hash(distribution_source_state(store=store, release=release, target=target))
    if not distribution_qa_allows_export(qa_report, current_source_hash=current_source_hash):
        raise DistributionExportError("Distribution QA gate failed. Refresh Distribution QA before export.")
    release_export_dir = store.release_store.export_dir(release_id).resolve()
    release_manifest = read_release_export_manifest(store.release_store, release_id)
    package_id = store.reserve_package_id(release_id)
    package_dir = store.package_dir(release_id, package_id).resolve()
    export_dir = store.export_dir(release_id, package_id).resolve()
    _ensure_within(store.distribution_dir(release_id).resolve(), package_dir)
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[dict[str, Any]] = []
    template = store.resolve_target_template(target)
    checklist = reconcile_distribution_checklist(store, release_id, target, template, write=True) if template else {}
    release_metadata = read_release_metadata(store.release_store, release_id, default={})
    artwork = _selected_artwork(store, release_id, target)
    layout_plan = build_distribution_layout_plan(
        release_id=release_id,
        target=target,
        release=release,
        release_manifest=release_manifest,
        release_metadata=release_metadata,
        template=template,
        artwork=artwork,
        release_export_dir=release_export_dir,
        encoded_audio_summary=AudioEncodingStore(store.release_store, project_store=store.release_store.project_store).get_summary(release_id),
        encoded_audio_root=store.release_store.release_dir(release_id) / "encoded-audio",
    )
    if layout_plan.get("summary", {}).get("status") == "failed":
        errors = layout_plan.get("errors") if isinstance(layout_plan.get("errors"), list) else []
        message = str(errors[0].get("message") if errors and isinstance(errors[0], dict) else "Distribution layout plan failed.")
        raise DistributionExportError(message)
    _write_package_json(export_dir, release, target, package_id, qa_report, now)
    _copy_release_file(release_export_dir, export_dir, "release.json", copied_files)
    _copy_release_file(release_export_dir, export_dir, "tracklist.json", copied_files)
    for rel in ("release-metadata.json", "platform-metadata.csv", "credits.csv"):
        source = release_export_dir / rel
        if source.exists():
            _copy_release_file(release_export_dir, export_dir, rel, copied_files, csv_safe=rel.endswith(".csv"))
    if template:
        _write_template_files(export_dir, template, checklist)
        copied_files.extend(_file_record(export_dir, path) for path in [export_dir / "template-pack.json", export_dir / "template-summary.json", export_dir / "docs" / "checklist.json", export_dir / "docs" / "checklist.md"])
        mapped_csv = _write_template_platform_csv(export_dir, store, release_id, template)
        if mapped_csv:
            copied_files.append(_file_record(export_dir, mapped_csv))
    layout_records = _copy_layout_entries(store, release_id, release_export_dir, export_dir, layout_plan, artwork=artwork)
    copied_files.extend(layout_records)
    encoded_audio_summary = _write_encoded_audio_sidecars(store, release_id, target, export_dir, copied_files)
    encoded_audio_acceptance_summary = _write_encoded_audio_acceptance_sidecars(store, release_id, target, export_dir, copied_files)
    format_decision_summary = _write_format_decision_sidecars(store, release_id, target, export_dir, copied_files)
    artwork_record = _artwork_record(artwork, layout_plan)
    wrote_checklist_doc = _write_docs(export_dir, release, target, package_id, qa_report, artwork_record, checklist=checklist, write_checklist=not bool(template))
    _write_readme(export_dir, release, target, package_id, qa_report)
    copied_files.extend(_file_record(export_dir, path) for path in [export_dir / "package.json", export_dir / "README.txt", export_dir / "docs" / "submission-notes.md"])
    if wrote_checklist_doc and not template:
        copied_files.append(_file_record(export_dir, export_dir / "docs" / "checklist.json"))
    layout_payload = layout_manifest_payload(layout_plan, copied_files)
    _write_json(export_dir / "layout" / "manifest-layout.json", layout_payload)
    (export_dir / "layout" / "file-tree.txt").parent.mkdir(parents=True, exist_ok=True)
    file_tree_paths = [str(item.get("path") or "") for item in copied_files]
    file_tree_paths.extend(["layout/manifest-layout.json", "layout/file-tree.txt"])
    (export_dir / "layout" / "file-tree.txt").write_text(layout_file_tree_text(file_tree_paths), encoding="utf-8")
    copied_files.extend(_file_record(export_dir, path) for path in [export_dir / "layout" / "manifest-layout.json", export_dir / "layout" / "file-tree.txt"])
    layout_payload = layout_manifest_payload(layout_plan, copied_files)
    _write_json(export_dir / "layout" / "manifest-layout.json", layout_payload)
    copied_files = [_file_record(export_dir, export_dir / str(item["path"])) for item in copied_files if str(item.get("path") or "").strip()]

    signoff_public = _distribution_signoff_export_summary({})
    _write_json(export_dir / "distribution-signoff.json", signoff_public)
    manifest = {
        "schema_version": DISTRIBUTION_EXPORT_SCHEMA_VERSION,
        "tool": {"name": "MusicForge Distribution Export", "version": __version__},
        "package_id": package_id,
        "release_id": release_id,
        "target_id": target.target_id,
        "profile_id": target.profile_id,
        "generated_at": now,
        "source_hash": current_source_hash,
        "qa_source_hash": qa_report.get("source_hash"),
        "profile": _profile_public(target.profile_id),
        "template": template_summary(template) if template else {},
        "checklist": checklist_summary(checklist) if checklist else {},
        "target": {
            "target_id": target.target_id,
            "name": target.name,
            "profile_id": target.profile_id,
            "template_pack_id": target.template_pack_id,
            "template_hash": target.template_hash,
            "options": target.options,
        },
        "release": {
            "release_id": release.release_id,
            "name": release.name,
            "track_count": len(release.tracks),
            "release_export_manifest_hash": stable_hash({key: value for key, value in release_manifest.items() if key != "zip"}),
            "release_zip_sha256": _sha256_file(store.release_store.zip_path(release_id)),
        },
        "artwork": artwork_record,
        "encoded_audio": encoded_audio_summary,
        "encoded_audio_acceptance": encoded_audio_acceptance_summary,
        "format_decision": format_decision_summary,
        "layout": layout_payload,
        "sidecars": {
            "distribution_signoff": _distribution_signoff_sidecar_record(signoff_public),
        },
        "files": sorted(copied_files, key=lambda item: item["path"]),
        "summary": {
            "status": "exported",
            "file_count": len(copied_files),
            "total_bytes": sum(int(item.get("size_bytes") or 0) for item in copied_files),
            "qa_status": qa_report.get("status"),
            "signoff_status": "not_signed",
            "layout_status": layout_payload.get("summary", {}).get("status"),
        },
        "redaction_summary": {"status": "passed"},
    }
    _write_json(export_dir / "distribution-manifest.json", sanitize_metadata(manifest, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    manifest = read_distribution_export_manifest(store, release_id, package_id)
    target.latest_export_summary = distribution_export_summary(manifest)
    target.latest_signoff_summary = {"status": "not_signed"}
    store.save_target(target)
    store.append_event(release_id, "distribution_export_created", {"target_id": target.target_id, "package_id": package_id})
    return manifest


def build_distribution_package_zip(store: DistributionStore, release_id: str, target: DistributionTarget, *, now: str | None = None) -> dict[str, Any]:
    now = now or now_iso()
    package_id = store.latest_package_id(target)
    if not package_id:
        raise FileNotFoundError("Distribution export has not been generated.")
    refresh_distribution_export_signoff_summary(store, release_id, package_id)
    export_dir = store.export_dir(release_id, package_id).resolve()
    zip_path = store.package_zip_path(release_id, package_id).resolve()
    _ensure_within(store.package_dir(release_id, package_id).resolve(), export_dir)
    _ensure_within(store.package_dir(release_id, package_id).resolve(), zip_path)
    if not export_dir.exists():
        raise FileNotFoundError("Distribution export has not been generated.")
    entries = _zip_entries(export_dir)
    manifest = read_distribution_export_manifest(store, release_id, package_id)
    manifest["zip"] = {
        "created_at": now,
        "filename": zip_path.name,
        "entry_count": len(entries),
        "entries": [entry for _path, entry in entries],
    }
    _write_json(export_dir / "distribution-manifest.json", sanitize_metadata(manifest, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    entries = _zip_entries(export_dir)
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in entries:
                archive.write(resolved, entry)
        tmp_path.replace(zip_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    zip_info = {
        "created_at": now,
        "filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "sha256": _sha256_file(zip_path),
        "entry_count": len(entries),
        "entries": [entry for _path, entry in entries],
    }
    manifest = read_distribution_export_manifest(store, release_id, package_id)
    target.latest_export_summary = distribution_export_summary(manifest)
    store.save_target(target)
    store.append_event(release_id, "distribution_package_zip_created", {"target_id": target.target_id, "package_id": package_id, "sha256": zip_info.get("sha256")})
    return sanitize_metadata(zip_info, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def sign_distribution_package(
    *,
    store: DistributionStore,
    release_id: str,
    target: DistributionTarget,
    qa_report: dict[str, Any],
    payload: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    store.ensure_target_mutable(release_id, target)
    package_id = store.latest_package_id(target)
    if not package_id:
        raise FileNotFoundError("Distribution export has not been generated.")
    existing = store.read_signoff(release_id, target, default={})
    if existing:
        raise DistributionExportError("Distribution package is already signed off. Reset distribution signoff before signing again.")
    manifest = read_distribution_export_manifest(store, release_id, package_id)
    zip_path = store.package_zip_path(release_id, package_id)
    if not zip_path.exists() or not isinstance(manifest.get("zip"), dict) or not manifest["zip"].get("entry_count"):
        raise DistributionExportError("Distribution ZIP has not been generated.")
    pending = build_distribution_signoff_record(release_id=release_id, target=target, package_id=package_id, qa_report=qa_report, payload=payload or {}, export_manifest={}, now=now)
    store.write_signoff(release_id, package_id, {**pending, "export_manifest_hash": None})
    final_manifest = refresh_distribution_export_signoff_summary(store, release_id, package_id)
    final_manifest.pop("zip", None)
    final_hash = stable_hash(final_manifest)
    signoff = store.write_signoff(release_id, package_id, {**pending, "export_manifest_hash": final_hash})
    refresh_distribution_export_signoff_summary(store, release_id, package_id)
    build_distribution_package_zip(store, release_id, target, now=now)
    store.update_signoff_summary(release_id, target.target_id, distribution_signoff_summary(signoff))
    store.append_event(release_id, "distribution_package_signed", {"target_id": target.target_id, "package_id": package_id, "forced": bool((payload or {}).get("force"))})
    return signoff


def refresh_distribution_export_signoff_summary(store: DistributionStore, release_id: str, package_id: str) -> dict[str, Any]:
    export_dir = store.export_dir(release_id, package_id)
    manifest_path = export_dir / "distribution-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Distribution export has not been generated.")
    signoff_path = store.signoff_path(release_id, package_id)
    signoff = read_json(signoff_path) if signoff_path.exists() else {}
    signoff_public = _distribution_signoff_export_summary(signoff if isinstance(signoff, dict) else {})
    _write_json(export_dir / "distribution-signoff.json", signoff_public)
    manifest = read_distribution_export_manifest(store, release_id, package_id)
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    summary["signoff_status"] = signoff_public.get("status")
    manifest["summary"] = summary
    sidecars = manifest.get("sidecars") if isinstance(manifest.get("sidecars"), dict) else {}
    sidecars["distribution_signoff"] = _distribution_signoff_sidecar_record(signoff_public)
    manifest["sidecars"] = sidecars
    manifest["files"] = sorted([item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("path") != "distribution-signoff.json"], key=lambda item: item["path"])
    _write_json(manifest_path, sanitize_metadata(manifest, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    return read_distribution_export_manifest(store, release_id, package_id)


def read_distribution_export_manifest(store: DistributionStore, release_id: str, package_id: str) -> dict[str, Any]:
    path = store.export_dir(release_id, package_id) / "distribution-manifest.json"
    if not path.exists():
        raise FileNotFoundError("Distribution export has not been generated.")
    value = read_json(path)
    return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def distribution_export_summary(manifest: dict[str, Any] | None) -> dict[str, Any]:
    data = manifest if isinstance(manifest, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    zip_info = data.get("zip") if isinstance(data.get("zip"), dict) else {}
    return sanitize_metadata(
        {
            "status": "exported" if data else "missing",
            "exists": bool(data),
            "package_id": data.get("package_id"),
            "release_id": data.get("release_id"),
            "target_id": data.get("target_id"),
            "profile_id": data.get("profile_id"),
            "generated_at": data.get("generated_at"),
            "source_hash": data.get("source_hash"),
            "qa_source_hash": data.get("qa_source_hash"),
            "file_count": summary.get("file_count", 0),
            "total_bytes": summary.get("total_bytes", 0),
            "zip_filename": zip_info.get("filename"),
            "zip_entry_count": zip_info.get("entry_count"),
            "layout_status": (data.get("layout") or {}).get("summary", {}).get("status") if isinstance(data.get("layout"), dict) else None,
            "layout_hash": (data.get("layout") or {}).get("layout_hash") if isinstance(data.get("layout"), dict) else None,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _write_package_json(export_dir: Path, release: Any, target: DistributionTarget, package_id: str, qa_report: dict[str, Any], now: str) -> None:
    _write_json(
        export_dir / "package.json",
        sanitize_metadata(
            {
                "schema_version": 1,
                "package_id": package_id,
                "release_id": release.release_id,
                "target_id": target.target_id,
                "profile_id": target.profile_id,
                "name": target.name,
                "created_at": now,
                "qa_summary": qa_report.get("summary") if isinstance(qa_report.get("summary"), dict) else {},
            },
            blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
        ),
    )


def _copy_release_file(source_root: Path, export_dir: Path, rel: str, records: list[dict[str, Any]], *, csv_safe: bool = False) -> None:
    source = (source_root / _validate_relative_path(rel)).resolve()
    _ensure_within(source_root, source)
    if not source.exists() or not source.is_file() or source.is_symlink():
        raise DistributionExportError(f"Required Release Export file is missing: {rel}.")
    target = (export_dir / rel).resolve()
    _ensure_within(export_dir, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if csv_safe:
        target.write_text(_escape_csv_formulas(source.read_text(encoding="utf-8")), encoding="utf-8")
    elif source.suffix.lower() == ".json":
        value = read_json(source)
        _write_json(target, sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    elif source.suffix.lower() == ".txt":
        target.write_text(sanitize_sensitive_text(source.read_text(encoding="utf-8")), encoding="utf-8")
    else:
        shutil.copy2(source, target)
    records.append(_file_record(export_dir, target))


def _selected_artwork(store: DistributionStore, release_id: str, target: DistributionTarget) -> dict[str, Any]:
    artwork_id = str((target.options or {}).get("artwork_id") or "").strip()
    artwork = read_distribution_artwork(store, release_id, artwork_id) if artwork_id else latest_distribution_artwork(store, release_id)
    return artwork if isinstance(artwork, dict) else {}


def _copy_layout_entries(store: DistributionStore, release_id: str, release_export_dir: Path, export_dir: Path, layout_plan: dict[str, Any], *, artwork: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    encoded_root = store.release_store.release_dir(release_id).resolve() / "encoded-audio"
    for entry in layout_plan.get("entries", []) if isinstance(layout_plan.get("entries"), list) else []:
        if not isinstance(entry, dict) or not entry.get("exists") or entry.get("status") == "failed":
            continue
        kind = str(entry.get("kind") or "")
        path = str(entry.get("path") or "")
        if not path:
            continue
        target = (export_dir / _validate_relative_path(path)).resolve()
        _ensure_within(export_dir, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind in {"audio", "lyrics"}:
            source_rel = _validate_relative_path(str(entry.get("source_rel") or ""))
            source_kind = str(entry.get("source_kind") or "release_export")
            source_root = encoded_root if source_kind == "encoded_audio" else release_export_dir
            source = (source_root / source_rel).resolve()
            _ensure_within(source_root, source)
            if not source.exists() or not source.is_file() or source.is_symlink():
                if entry.get("required"):
                    raise DistributionExportError(f"Required layout source is missing: {source_rel}.")
                continue
            if kind == "lyrics":
                target.write_text(sanitize_sensitive_text(source.read_text(encoding="utf-8")), encoding="utf-8")
            else:
                shutil.copy2(source, target)
            records.append(_file_record(export_dir, target))
        elif kind == "artwork":
            if not artwork:
                if entry.get("required"):
                    raise DistributionExportError("Required artwork is missing.")
                continue
            source = distribution_artwork_file_path(store, release_id, artwork)
            shutil.copy2(source, target)
            records.append(_file_record(export_dir, target))
    return records


def _write_encoded_audio_sidecars(store: DistributionStore, release_id: str, target: DistributionTarget, export_dir: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    template = store.resolve_target_template(target)
    profile_ids = [profile_id for profile_id in resolve_target_audio_format_profiles(target, template) if profile_id != "wav_master"]
    encoding_store = AudioEncodingStore(store.release_store, project_store=store.release_store.project_store)
    summary = encoding_store.get_summary(release_id)
    if not profile_ids:
        return {"status": "not_required", "profiles": []}
    target_dir = export_dir / "encoded-audio"
    manifests_dir = target_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    _write_json(target_dir / "summary.json", summary)
    records.append(_file_record(export_dir, target_dir / "summary.json"))
    copied_profiles: list[dict[str, Any]] = []
    for profile_id in profile_ids:
        manifest = encoding_store.read_manifest(release_id, profile_id)
        manifest_path = manifests_dir / f"{profile_id}.json"
        _write_json(manifest_path, sanitize_metadata(manifest, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
        records.append(_file_record(export_dir, manifest_path))
        copied_profiles.append({"profile_id": profile_id, "manifest_path": f"encoded-audio/manifests/{profile_id}.json", "manifest_hash": manifest.get("integrity_hash"), "source_hash": manifest.get("source_hash")})
    return sanitize_metadata({"status": "included", "profiles": copied_profiles, "summary_path": "encoded-audio/summary.json"}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _write_encoded_audio_acceptance_sidecars(store: DistributionStore, release_id: str, target: DistributionTarget, export_dir: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    template = store.resolve_target_template(target)
    profile_ids = [profile_id for profile_id in resolve_target_audio_format_profiles(target, template) if profile_id != "wav_master"]
    if not profile_ids:
        return {"status": "not_required", "required_profiles": []}
    try:
        return export_distribution_encoded_audio_acceptance(
            store=store,
            release_id=release_id,
            target=target,
            export_dir=export_dir,
            required_profiles=profile_ids,
            records=records,
        )
    except Exception:
        return {"status": "missing", "required_profiles": profile_ids}


def _write_format_decision_sidecars(store: DistributionStore, release_id: str, target: DistributionTarget, export_dir: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        summary = FormatDecisionStore(store.release_store, project_store=store.release_store.project_store, distribution_store=store).export_distribution(release_id, target, export_dir)
    except Exception:
        summary = {"status": "missing", "required_profiles": []}
    target_path = export_dir / str(summary.get("summary_path") or "format-decision/target-decision-summary.json")
    if target_path.exists():
        records.append(_file_record(export_dir, target_path))
    return sanitize_metadata(summary, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _artwork_record(artwork: dict[str, Any], layout_plan: dict[str, Any]) -> dict[str, Any]:
    if not artwork:
        return {}
    entries = layout_plan.get("entries") if isinstance(layout_plan.get("entries"), list) else []
    package_path = next((entry.get("path") for entry in entries if isinstance(entry, dict) and entry.get("kind") == "artwork"), None)
    return sanitize_metadata({**artwork, "package_path": package_path}, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _write_docs(export_dir: Path, release: Any, target: DistributionTarget, package_id: str, qa_report: dict[str, Any], artwork: dict[str, Any], *, checklist: dict[str, Any] | None = None, write_checklist: bool = True) -> bool:
    checklist = {
        "package_id": package_id,
        "release_id": release.release_id,
        "target_id": target.target_id,
        "profile_id": target.profile_id,
        "qa_status": qa_report.get("status"),
        "artwork": bool(artwork),
        "metadata": True,
        **(checklist if isinstance(checklist, dict) else {}),
    }
    if write_checklist:
        _write_json(export_dir / "docs" / "checklist.json", sanitize_metadata(checklist, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    note = str((target.options or {}).get("submission_note") or "")
    (export_dir / "docs" / "submission-notes.md").write_text(sanitize_sensitive_text(note or "Prepared locally by MusicForge.\n"), encoding="utf-8")
    return write_checklist


def _write_readme(export_dir: Path, release: Any, target: DistributionTarget, package_id: str, qa_report: dict[str, Any]) -> None:
    lines = [
        f"MusicForge Distribution Package: {sanitize_sensitive_text(release.name)}",
        "",
        f"Package ID: {package_id}",
        f"Release ID: {release.release_id}",
        f"Target: {sanitize_sensitive_text(target.name)} ({target.profile_id})",
        f"Distribution QA: {qa_report.get('status', 'missing')}",
        "",
        "This package was prepared locally. It does not contain platform credentials or upload tokens.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_template_files(export_dir: Path, template: dict[str, Any], checklist: dict[str, Any]) -> None:
    _write_json(export_dir / "template-pack.json", sanitize_metadata(template, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    _write_json(export_dir / "template-summary.json", template_summary(template))
    payload = checklist_export_payload(checklist, template)
    _write_json(export_dir / "docs" / "checklist.json", payload)
    (export_dir / "docs" / "checklist.md").write_text(checklist_markdown(checklist, template), encoding="utf-8")


def _write_template_platform_csv(export_dir: Path, store: DistributionStore, release_id: str, template: dict[str, Any]) -> Path | None:
    mapping = template_mapping(template)
    rows = mapping.get("platform_csv") if isinstance(mapping.get("platform_csv"), list) else []
    if not rows:
        return None
    from song_agent.release_metadata import read_release_metadata

    metadata = read_release_metadata(store.release_store, release_id, default={})
    tracks = metadata.get("tracks") if isinstance(metadata.get("tracks"), list) else []
    headers = [str(row.get("column") or "") for row in rows if isinstance(row, dict) and row.get("column")]
    if not headers:
        return None
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    for track in tracks:
        if not isinstance(track, dict):
            continue
        out: dict[str, Any] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            column = str(row.get("column") or "")
            value = resolve_mapping_source(str(row.get("source") or ""), release_metadata=metadata, track_metadata=track)
            out[column] = _escape_csv_cell(str(value or ""))
        writer.writerow(out)
    target = export_dir / "template-platform-metadata.csv"
    target.write_text(buffer.getvalue(), encoding="utf-8")
    return target


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp-{os.getpid()}-{threading.get_ident()}.json"
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path


def _profile_public(profile_id: str) -> dict[str, Any]:
    profile = get_distribution_profile(profile_id)
    return {key: profile.get(key) for key in ("profile_id", "name", "description", "profile_hash")}


def _escape_csv_formulas(text: str) -> str:
    reader = csv.reader(io.StringIO(text))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    for row in reader:
        writer.writerow([_escape_csv_cell(cell) for cell in row])
    return buffer.getvalue()


def _escape_csv_cell(cell: str) -> str:
    text = str(cell or "")
    if text and text.startswith(FORMULA_PREFIXES) and not text.startswith("'"):
        return "'" + text
    return text


def _distribution_signoff_export_summary(signoff: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "status": signoff.get("status") or "not_signed",
            "signed_at": signoff.get("signed_at"),
            "signed_by": signoff.get("signed_by"),
            "forced": bool(signoff.get("forced", False)),
            "qa_source_hash": signoff.get("qa_source_hash"),
            "export_manifest_hash": signoff.get("export_manifest_hash"),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _distribution_signoff_sidecar_record(signoff_public: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": "distribution-signoff.json",
        "payload_hash": stable_hash(_distribution_signoff_hash_payload(signoff_public)),
        "payload_hash_excludes": sorted(DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS),
    }


def _distribution_signoff_hash_payload(signoff_public: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in signoff_public.items() if key not in DISTRIBUTION_SIGNOFF_PAYLOAD_HASH_EXCLUDE_KEYS}


def _file_record(export_dir: Path, path: Path) -> dict[str, Any]:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir, resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir).as_posix())
        if entry in seen:
            raise DistributionExportError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries


def _validate_relative_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise DistributionExportError("Unsafe relative path.")
    parts = [part for part in raw.split("/") if part]
    if not parts or raw.startswith("/") or raw.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise DistributionExportError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise DistributionExportError("Refusing to operate outside distribution export boundaries.") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
