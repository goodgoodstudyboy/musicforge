from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.studio.projectio import write_json
from song_agent.domains.trust.public_trust_center_anchor_registry_contracts import ANCHOR_REGISTRY_BLOCKED_KEYS
from song_agent.domains.trust.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package
from song_agent.domains.trust.public_trust_center_anchor_transparency_contracts import ANCHOR_CHECKPOINT_PACKAGE_TYPE, ANCHOR_TRANSPARENCY_PACKAGE_TYPE, anchor_checkpoint_hash, anchor_checkpoint_integrity_ok, anchor_checkpoint_signature_ok, anchor_transparency_event_hash, anchor_transparency_ledger_hash, anchor_transparency_manifest_hash, anchor_transparency_report_hash, anchor_transparency_summary
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash


ANCHOR_TRANSPARENCY_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 250
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "anchor-transparency-manifest.json",
    "anchor-transparency-report.json",
    "ledger.jsonl",
    "checkpoints/ptc-anchor-checkpoint-current.json",
    "registry-verification-summary.json",
    "current-anchor-registry-summary.json",
    "chain-of-custody.json",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"anchor-transparency-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ANCHOR_REGISTRY_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_public_trust_center_anchor_transparency_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    checkpoint_path: Path | str | None = None,
    anchor_registry_path: Path | str | None = None,
    require_current_checkpoint: bool = False,
    require_published_anchor: bool = False,
    require_not_revoked: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AnchorTransparencyVerifier(
        Path(zip_path),
        strict=strict,
        checkpoint_path=Path(checkpoint_path) if checkpoint_path is not None else None,
        anchor_registry_path=Path(anchor_registry_path) if anchor_registry_path is not None else None,
        require_current_checkpoint=require_current_checkpoint,
        require_published_anchor=require_published_anchor,
        require_not_revoked=require_not_revoked,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_public_trust_center_anchor_transparency_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_anchor_transparency_verification_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge Public Trust Center Anchor Transparency verification")
    print(f"status: {report.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"checkpoint: {summary.get('checkpoint_id') or 'none'}")
    print(f"blockers: {len(report.get('blockers') if isinstance(report.get('blockers'), list) else [])}")
    print(f"warnings: {len(report.get('warnings') if isinstance(report.get('warnings'), list) else [])}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = report.get(key) if isinstance(report.get(key), list) else []
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def public_trust_center_anchor_transparency_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AnchorTransparencyVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        checkpoint_path: Path | None,
        anchor_registry_path: Path | None,
        require_current_checkpoint: bool,
        require_published_anchor: bool,
        require_not_revoked: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.checkpoint_path = checkpoint_path
        self.anchor_registry_path = anchor_registry_path
        self.require_current_checkpoint = require_current_checkpoint
        self.require_published_anchor = require_published_anchor
        self.require_not_revoked = require_not_revoked
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.ledger_events: list[dict[str, Any]] = []
        self.current_checkpoint: dict[str, Any] = {}
        self.external_checkpoint: dict[str, Any] = {}
        self.registry_verification_summary: dict[str, Any] = {}
        self.registry_summary: dict[str, Any] = {}
        self.chain: dict[str, Any] = {}
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                if "anchor-transparency-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "anchor-transparency-manifest.json", "manifest", "ptcat_manifest_parse")
                self._verify_manifest(archive)
                self._read_documents(archive)
                self._verify_documents()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "ptcat_zip_open", "failed", "blocking", "Anchor Transparency ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcat_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcat_zip_open", "failed", "blocking", f"Anchor Transparency ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcat_zip_open", "passed", "blocking", "Anchor Transparency ZIP can be opened.")
        return archive

    def _verify_zip_structure(self, archive: zipfile.ZipFile) -> None:
        self.entry_infos = archive.infolist()
        self.entry_names = [info.filename for info in self.entry_infos]
        self.raw_entry_names = _raw_zip_entry_names(self.zip_path)
        self.entry_map = {}
        for info in self.entry_infos:
            if info.filename not in self.entry_map:
                self.entry_map[info.filename] = info
        self.total_uncompressed_size = sum(max(0, int(info.file_size or 0)) for info in self.entry_infos)
        max_uncompressed = self.max_uncompressed_size_mb * 1024 * 1024
        self._add_check("zip", "ptcat_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ptcat_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ptcat_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcat_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "ptcat_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Anchor Transparency entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_public_entry(name)]
        self._add_check("zip", "ptcat_zip_no_nested_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden nested/internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "ptcat_manifest_exists", "failed", "blocking", "anchor-transparency-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "ptcat_manifest_integrity", self.manifest.get("integrity_hash"), anchor_transparency_manifest_hash(self.manifest), "Anchor Transparency manifest integrity")
        self._add_exact_check("manifest", "ptcat_manifest_package_type", self.manifest.get("package_type"), ANCHOR_TRANSPARENCY_PACKAGE_TYPE, "Manifest package_type")
        rows = self.manifest.get("files") if isinstance(self.manifest.get("files"), list) else []
        valid: list[dict[str, Any]] = []
        errors: list[str] = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                errors.append(f"files[{index}] is not an object")
                continue
            path = str(item.get("path") or "")
            if not _is_safe_zip_entry(path):
                errors.append(f"{path or index} has unsafe path")
            if not isinstance(item.get("size_bytes"), int) or int(item.get("size_bytes") or 0) < 0:
                errors.append(f"{path or index} has invalid size")
            if not HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                errors.append(f"{path or index} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(item.get("size_bytes"), int) and HEX_SHA256.fullmatch(str(item.get("sha256") or "")):
                valid.append(item)
        self._add_check("manifest", "ptcat_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
        mismatches: list[str] = []
        for item in valid:
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(f"{path} missing")
                continue
            actual_sha = _sha256_entry(archive, info)
            actual_size = int(info.file_size or 0)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if actual_size == item.get("size_bytes") and actual_sha == item.get("sha256") else "failed"})
            if actual_size != item.get("size_bytes") or actual_sha != item.get("sha256"):
                mismatches.append(path)
        self._add_check("manifest", "ptcat_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "ptcat_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", "ptcat_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.report_doc = self._read_json_entry(archive, "anchor-transparency-report.json", "report", "ptcat_report_parse")
        self.ledger_events = self._read_ledger_entry(archive, "ledger.jsonl")
        self.current_checkpoint = self._read_json_entry(archive, "checkpoints/ptc-anchor-checkpoint-current.json", "checkpoint", "ptcat_current_checkpoint_parse")
        self.registry_verification_summary = self._read_json_entry(archive, "registry-verification-summary.json", "registry", "ptcat_registry_verification_summary_parse")
        self.registry_summary = self._read_json_entry(archive, "current-anchor-registry-summary.json", "registry", "ptcat_registry_summary_parse")
        self.chain = self._read_json_entry(archive, "chain-of-custody.json", "chain", "ptcat_chain_parse")
        if self.checkpoint_path is not None:
            try:
                value = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                self.external_checkpoint = value if isinstance(value, dict) else {}
                self._add_check("checkpoint", "ptcat_external_checkpoint_parse", "passed", "blocking", "External checkpoint parses as JSON.")
            except (OSError, json.JSONDecodeError) as exc:
                self._add_check("checkpoint", "ptcat_external_checkpoint_parse", "failed", "blocking", f"External checkpoint cannot be parsed: {exc}")

    def _verify_documents(self) -> None:
        latest = self.ledger_events[-1] if self.ledger_events else {}
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        self._add_hash_check("report", "ptcat_report_integrity", self.report_doc.get("integrity_hash"), anchor_transparency_report_hash(self.report_doc), "Report integrity")
        self._add_hash_check("report", "ptcat_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Report source hash")
        self._add_hash_check("manifest", "ptcat_manifest_report_hash", self.manifest.get("report", {}).get("integrity_hash") if isinstance(self.manifest.get("report"), dict) else None, self.report_doc.get("integrity_hash"), "Manifest report hash")
        self._add_hash_check("manifest", "ptcat_manifest_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest source hash")
        self._verify_ledger(latest, source)
        self._verify_checkpoint(self.current_checkpoint, latest, source, "current")
        if self.external_checkpoint:
            self._verify_checkpoint(self.external_checkpoint, latest, source, "external")
            self._add_hash_check("checkpoint", "ptcat_external_checkpoint_matches_current", self.external_checkpoint.get("integrity_hash"), self.current_checkpoint.get("integrity_hash"), "External checkpoint hash")
        self._verify_registry_summary(source)
        self._verify_chain(source)

    def _verify_ledger(self, latest: ImplementationDocument, source: ImplementationDocument) -> None:
        ok = True
        previous = None
        for index, event in enumerate(self.ledger_events, start=1):
            if not isinstance(event, dict) or event.get("sequence") != index or event.get("previous_event_hash") != previous or event.get("event_hash") != anchor_transparency_event_hash(event):
                ok = False
                break
            previous = event.get("event_hash")
        self._add_check("ledger", "ptcat_ledger_event_chain", "passed" if ok else "failed", "blocking", "Ledger event chain is valid." if ok else "Ledger event chain is invalid.")
        self._add_hash_check("ledger", "ptcat_ledger_hash", source.get("ledger_hash"), anchor_transparency_ledger_hash(self.ledger_events), "Ledger hash")
        self._add_hash_check("ledger", "ptcat_latest_event_hash", source.get("latest_event_hash"), latest.get("event_hash"), "Latest event hash")
        self._add_exact_check("ledger", "ptcat_latest_sequence", source.get("latest_sequence"), latest.get("sequence"), "Latest sequence")
        latest_state = latest.get("state") if isinstance(latest.get("state"), dict) else {}
        for key in ("registry_hash", "registry_zip_sha256", "registry_manifest_hash", "registry_verification_status", "registry_verification_report_hash", "current_entry_id", "current_anchor_hash", "current_entry_status", "ptc_zip_sha256", "ptc_manifest_hash", "ptc_source_hash"):
            self._add_exact_check("ledger", f"ptcat_source_{key}", source.get(key), latest_state.get(key), f"Report source {key}")

    def _verify_checkpoint(self, checkpoint: ImplementationDocument, latest: ImplementationDocument, source: ImplementationDocument, label: str) -> None:
        prefix = f"ptcat_{label}_checkpoint"
        self._add_exact_check("checkpoint", f"{prefix}_package_type", checkpoint.get("package_type"), ANCHOR_CHECKPOINT_PACKAGE_TYPE, f"{label} checkpoint package_type")
        self._add_hash_check("checkpoint", f"{prefix}_integrity", checkpoint.get("integrity_hash"), anchor_checkpoint_hash(checkpoint), f"{label} checkpoint integrity")
        self._add_check("checkpoint", f"{prefix}_signature", "passed" if anchor_checkpoint_signature_ok(checkpoint) else "failed", "blocking", f"{label} checkpoint signature envelope is valid." if anchor_checkpoint_signature_ok(checkpoint) else f"{label} checkpoint signature envelope is invalid.")
        self._add_hash_check("checkpoint", f"{prefix}_latest_event", checkpoint.get("latest_event_hash"), latest.get("event_hash"), f"{label} checkpoint latest event")
        self._add_hash_check("checkpoint", f"{prefix}_ledger_hash", checkpoint.get("ledger_hash"), source.get("ledger_hash"), f"{label} checkpoint ledger hash")
        for key in ("current_entry_id", "current_anchor_hash", "registry_hash", "registry_zip_sha256", "registry_manifest_hash", "ptc_zip_sha256", "ptc_manifest_hash", "ptc_source_hash"):
            self._add_exact_check("checkpoint", f"{prefix}_{key}", checkpoint.get(key), source.get(key), f"{label} checkpoint {key}")

    def _verify_registry_summary(self, source: ImplementationDocument) -> None:
        summary = self.registry_summary.get("summary") if isinstance(self.registry_summary.get("summary"), dict) else {}
        current = self.registry_summary.get("current_entry") if isinstance(self.registry_summary.get("current_entry"), dict) else {}
        anchor = self.registry_summary.get("current_anchor") if isinstance(self.registry_summary.get("current_anchor"), dict) else {}
        self._add_hash_check("registry", "ptcat_registry_summary_hash", self.manifest.get("current_anchor_registry_summary", {}).get("hash") if isinstance(self.manifest.get("current_anchor_registry_summary"), dict) else None, stable_hash(self.registry_summary), "Registry summary manifest hash")
        self._add_hash_check("registry", "ptcat_registry_summary_registry_hash", self.registry_summary.get("registry_hash"), source.get("registry_hash"), "Registry summary registry hash")
        self._add_exact_check("registry", "ptcat_registry_summary_current_entry_id", summary.get("current_entry_id"), source.get("current_entry_id"), "Registry summary current entry")
        self._add_exact_check("registry", "ptcat_registry_summary_current_status", summary.get("current_entry_status"), source.get("current_entry_status"), "Registry summary current status")
        self._add_hash_check("registry", "ptcat_registry_summary_current_anchor_hash", summary.get("current_anchor_hash"), source.get("current_anchor_hash"), "Registry summary current anchor hash")
        self._add_hash_check("registry", "ptcat_registry_current_entry_hash", current.get("integrity_hash"), source.get("current_entry_hash"), "Registry current entry hash")
        self._add_hash_check("registry", "ptcat_registry_current_anchor_zip", anchor.get("zip_sha256"), source.get("ptc_zip_sha256"), "Registry current anchor PTC ZIP hash")
        self._add_hash_check("registry", "ptcat_registry_current_anchor_manifest", anchor.get("manifest_hash"), source.get("ptc_manifest_hash"), "Registry current anchor manifest hash")
        self._add_hash_check("registry", "ptcat_registry_verification_summary_hash", self.manifest.get("registry_verification_summary", {}).get("hash") if isinstance(self.manifest.get("registry_verification_summary"), dict) else None, stable_hash(self.registry_verification_summary), "Registry verification summary manifest hash")
        self._add_exact_check("registry", "ptcat_registry_verification_status", self.registry_verification_summary.get("status"), source.get("registry_verification_status"), "Registry verification status")
        self._add_hash_check("registry", "ptcat_registry_verification_zip_sha256", self.registry_verification_summary.get("zip_sha256"), source.get("registry_zip_sha256"), "Registry verification ZIP sha256")
        self._add_hash_check("registry", "ptcat_registry_verification_manifest_hash", self.registry_verification_summary.get("manifest_hash"), source.get("registry_manifest_hash"), "Registry verification manifest hash")
        self._add_hash_check("registry", "ptcat_registry_verification_report_hash", self.registry_verification_summary.get("verification_report_hash"), source.get("registry_verification_report_hash"), "Registry verification report hash")
        if self.anchor_registry_path is not None:
            registry_report = verify_public_trust_center_anchor_registry_package(
                self.anchor_registry_path,
                strict=self.strict,
                require_current=True,
                require_anchor_published=self.require_published_anchor,
                require_anchor_not_revoked=self.require_not_revoked,
                max_zip_size_mb=self.max_zip_size_mb,
                max_uncompressed_size_mb=self.max_uncompressed_size_mb,
                max_entry_count=self.max_entry_count,
                now=self.generated_at,
            )
            self._add_exact_check("registry", "ptcat_external_anchor_registry_verification_status", registry_report.get("status"), "passed", "External Anchor Registry verification status")
            self._add_hash_check("registry", "ptcat_external_anchor_registry_zip_sha256", registry_report.get("zip_sha256"), source.get("registry_zip_sha256"), "External Anchor Registry ZIP sha256")
            self._add_hash_check("registry", "ptcat_external_anchor_registry_manifest_hash", registry_report.get("manifest_hash"), source.get("registry_manifest_hash"), "External Anchor Registry manifest hash")

    def _verify_chain(self, source: ImplementationDocument) -> None:
        self._add_hash_check("chain", "ptcat_chain_integrity", self.chain.get("integrity_hash"), stable_hash({key: value for key, value in self.chain.items() if key != "integrity_hash"}), "Chain of custody integrity")
        self._add_hash_check("chain", "ptcat_chain_source_hash", self.chain.get("source_hash"), self.report_doc.get("source_hash"), "Chain source hash")
        self._add_exact_check("chain", "ptcat_chain_events_match_ledger", self.chain.get("events"), self.ledger_events, "Chain events derive from ledger")
        chain_summary = self.chain.get("summary") if isinstance(self.chain.get("summary"), dict) else {}
        latest_event_hash = self.chain.get("latest_event_hash") or chain_summary.get("latest_event_hash")
        self._add_exact_check("chain", "ptcat_chain_latest_event_hash", latest_event_hash, source.get("latest_event_hash"), "Chain latest event")

    def _verify_requirements(self) -> None:
        source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
        current_status = source.get("current_entry_status")
        if self.require_current_checkpoint:
            self._add_check("requirements", "ptcat_require_current_checkpoint", "passed" if self.current_checkpoint and self.current_checkpoint.get("latest_event_hash") == source.get("latest_event_hash") else "failed", "blocking", "Current checkpoint exists and binds latest event." if self.current_checkpoint and self.current_checkpoint.get("latest_event_hash") == source.get("latest_event_hash") else "Current checkpoint is required.")
        if self.require_published_anchor:
            self._add_exact_check("requirements", "ptcat_require_published_anchor", current_status, "published", "Current anchor is published")
        if self.require_not_revoked:
            ok = bool(source.get("current_entry_id")) and current_status != "revoked"
            self._add_check("requirements", "ptcat_require_not_revoked", "passed" if ok else "failed", "blocking", "Current anchor is not revoked." if ok else "Current anchor is revoked or missing.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".txt", ".md", ".html", ".jsonl")):
                continue
            info = self.entry_map.get(name)
            if info is None or info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (OSError, UnicodeDecodeError, RuntimeError):
                continue
            self.redaction_findings.extend(_redaction_findings(name, text))
            if name.endswith(".json"):
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    continue
                self.redaction_findings.extend(_blocked_key_findings(name, value))
        self._add_check("redaction", "ptcat_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        info = self.entry_map.get(name)
        if not name or info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name or 'entry'} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parses as JSON.")
        return value if isinstance(value, dict) else {}

    def _read_ledger_entry(self, archive: zipfile.ZipFile, name: str) -> list[ImplementationDocument]:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check("ledger", "ptcat_ledger_parse", "failed", "blocking", "ledger.jsonl is missing.")
            return []
        try:
            text = archive.read(info).decode("utf-8")
            events = [json.loads(line) for line in text.splitlines() if line.strip()]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check("ledger", "ptcat_ledger_parse", "failed", "blocking", f"ledger.jsonl cannot be parsed: {exc}")
            return []
        if not all(isinstance(item, dict) for item in events):
            self._add_check("ledger", "ptcat_ledger_parse", "failed", "blocking", "ledger.jsonl contains non-object rows.")
            return []
        self._add_check("ledger", "ptcat_ledger_parse", "passed", "blocking", "ledger.jsonl parses as JSONL.")
        return events

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = anchor_transparency_summary(self.report_doc)
        summary.update({"center_id": self.manifest.get("center_id") or self.report_doc.get("center_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        report = {
            "schema_version": ANCHOR_TRANSPARENCY_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "checkpoint_hash": self.current_checkpoint.get("integrity_hash") if isinstance(self.current_checkpoint, dict) else None,
            "summary": summary,
            "checks": self.checks,
            "files": self.files,
            "blockers": blockers,
            "warnings": warnings,
            "redaction_findings": self.redaction_findings[:50],
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_hash_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: Any, actual: Any, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _is_forbidden_public_entry(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".musicforge/") or lower.endswith(".zip")


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_findings(name: str, text: str) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    for pattern in SENSITIVE_VALUE_PATTERNS + LOCAL_PATH_VALUE_PATTERNS:
        compiled = pattern[0] if isinstance(pattern, tuple) and pattern else pattern
        label = pattern[1] if isinstance(pattern, tuple) and len(pattern) > 1 else getattr(compiled, "pattern", str(compiled))
        if compiled.search(text):
            findings.append({"path": name, "pattern": label})
    return findings


def _blocked_key_findings(name: str, value: Any, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"path": name, "key": path})
            findings.extend(_blocked_key_findings(name, item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{prefix}[{index}]"))
    return findings
