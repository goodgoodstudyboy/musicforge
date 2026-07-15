from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.studio.projectio import write_json
from song_agent.domains.trust.public_trust_center_anchor_registry_contracts import ANCHOR_ENTRY_STATUSES, ANCHOR_REGISTRY_BLOCKED_KEYS, ANCHOR_REGISTRY_PACKAGE_TYPE, anchor_entry_hash, anchor_entry_signature_ok, anchor_event_hash, anchor_registry_hash, anchor_registry_manifest_hash, anchor_registry_report_hash, anchor_registry_summary, anchor_registry_verification_summary
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash


ANCHOR_REGISTRY_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"anchor-registry-manifest.json", "registry.json", "anchor-registry-report.json", "chain-of-custody.json", "current-anchor.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"anchor-registry-manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = ANCHOR_REGISTRY_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_public_trust_center_anchor_registry_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_current: bool = False,
    require_anchor_published: bool = False,
    require_anchor_not_revoked: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _AnchorRegistryVerifier(
        Path(zip_path),
        strict=strict,
        require_current=require_current,
        require_anchor_published=require_anchor_published,
        require_anchor_not_revoked=require_anchor_not_revoked,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_public_trust_center_anchor_registry_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_public_trust_center_anchor_registry_verification_report(report: dict[str, Any]) -> None:
    summary = anchor_registry_verification_summary(report)
    print("MusicForge Public Trust Center Anchor Registry verification")
    print(f"status: {summary.get('status')}")
    print(f"center: {summary.get('center_id') or 'unknown'}")
    print(f"current entry: {summary.get('current_entry_id') or 'none'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        rows = report.get(key) if isinstance(report.get(key), list) else []
        if not rows:
            continue
        print(f"{label}:")
        for item in rows[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def public_trust_center_anchor_registry_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _AnchorRegistryVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_current: bool,
        require_anchor_published: bool,
        require_anchor_not_revoked: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_current = require_current
        self.require_anchor_published = require_anchor_published
        self.require_anchor_not_revoked = require_anchor_not_revoked
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.registry: dict[str, Any] = {}
        self.report_doc: dict[str, Any] = {}
        self.chain: dict[str, Any] = {}
        self.current_anchor: dict[str, Any] = {}
        self.entries: dict[str, dict[str, Any]] = {}
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
                if "anchor-registry-manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "anchor-registry-manifest.json", "manifest", "ptcar_manifest_parse")
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
            self._add_check("zip", "ptcar_zip_open", "failed", "blocking", "Anchor Registry ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "ptcar_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "ptcar_zip_open", "failed", "blocking", f"Anchor Registry ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "ptcar_zip_open", "passed", "blocking", "Anchor Registry ZIP can be opened.")
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
        self._add_check("zip", "ptcar_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "ptcar_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "ptcar_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "ptcar_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "ptcar_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Anchor Registry entries exist.")
        forbidden = [name for name in self.entry_names if _is_forbidden_public_entry(name)]
        self._add_check("zip", "ptcar_zip_no_nested_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden nested/internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No nested ZIP or .musicforge entries are present.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "ptcar_manifest_exists", "failed", "blocking", "anchor-registry-manifest.json is missing or invalid.")
            return
        self._add_hash_check("manifest", "ptcar_manifest_integrity", self.manifest.get("integrity_hash"), anchor_registry_manifest_hash(self.manifest), "Anchor Registry manifest integrity")
        self._add_exact_check("manifest", "ptcar_manifest_package_type", self.manifest.get("package_type"), ANCHOR_REGISTRY_PACKAGE_TYPE, "Manifest package_type")
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
        self._add_check("manifest", "ptcar_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "ptcar_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "ptcar_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            spoof_status = "failed" if spoofed and self.strict else "warning" if spoofed else "passed"
            self._add_check("manifest", "ptcar_manifest_zip_entries_reference_only", spoof_status, "blocking" if spoof_status == "failed" else "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.registry = self._read_json_entry(archive, "registry.json", "registry", "ptcar_registry_parse")
        self.report_doc = self._read_json_entry(archive, "anchor-registry-report.json", "report", "ptcar_report_parse")
        self.chain = self._read_json_entry(archive, "chain-of-custody.json", "chain", "ptcar_chain_parse")
        self.current_anchor = self._read_json_entry(archive, "current-anchor.json", "anchor", "ptcar_current_anchor_parse")
        for name in self.entry_names:
            if name.startswith("entries/") and name.endswith(".json"):
                self.entries[name] = self._read_json_entry(archive, name, "entries", f"ptcar_{name.replace('/', '_').replace('-', '_').replace('.', '_')}_parse")

    def _verify_documents(self) -> None:
        if self.registry:
            self._add_hash_check("registry", "ptcar_registry_integrity", self.registry.get("integrity_hash"), anchor_registry_hash(self.registry), "Registry integrity")
            row = self.manifest.get("registry") if isinstance(self.manifest.get("registry"), dict) else {}
            self._add_hash_check("registry", "ptcar_manifest_registry_hash", row.get("integrity_hash"), self.registry.get("integrity_hash"), "Manifest registry hash")
            self._verify_registry_entries()
            self._verify_event_chain()
        else:
            self._add_check("registry", "ptcar_registry_exists", "failed", "blocking", "registry.json must contain a JSON object.")
        if self.report_doc:
            self._add_hash_check("report", "ptcar_report_integrity", self.report_doc.get("integrity_hash"), anchor_registry_report_hash(self.report_doc), "Report integrity")
            report_row = self.manifest.get("registry_report") if isinstance(self.manifest.get("registry_report"), dict) else {}
            self._add_hash_check("report", "ptcar_manifest_report_hash", report_row.get("integrity_hash"), self.report_doc.get("integrity_hash"), "Manifest report hash")
            self._add_hash_check("report", "ptcar_manifest_report_source_hash", self.manifest.get("source_hash"), self.report_doc.get("source_hash"), "Manifest report source hash")
            expected_source = _report_source_from_registry(self.registry)
            source = self.report_doc.get("source") if isinstance(self.report_doc.get("source"), dict) else {}
            self._add_hash_check("report", "ptcar_report_source_hash", self.report_doc.get("source_hash"), stable_hash(source), "Report source hash")
            for key, expected in expected_source.items():
                self._add_exact_check("report", f"ptcar_report_source_{key}", source.get(key), expected, f"Report source {key}")
            expected_summary = anchor_registry_summary(self.registry)
            summary = self.report_doc.get("summary") if isinstance(self.report_doc.get("summary"), dict) else {}
            for key in ("current_entry_id", "current_anchor_hash", "entry_count", "published_count", "revoked_count", "superseded_count"):
                self._add_exact_check("report", f"ptcar_report_summary_{key}", summary.get(key), expected_summary.get(key), f"Report summary {key}")
        else:
            self._add_check("report", "ptcar_report_exists", "failed", "blocking", "anchor-registry-report.json must contain a JSON object.")
        if self.chain:
            self._add_hash_check("chain", "ptcar_chain_integrity", self.chain.get("integrity_hash"), stable_hash({key: value for key, value in self.chain.items() if key != "integrity_hash"}), "Chain of custody integrity")
            self._add_hash_check("chain", "ptcar_chain_source_hash", self.chain.get("source_hash"), self.report_doc.get("source_hash"), "Chain source hash")
            expected_events = self.registry.get("events") if isinstance(self.registry.get("events"), list) else []
            actual_events = self.chain.get("events") if isinstance(self.chain.get("events"), list) else []
            self._add_exact_check("chain", "ptcar_chain_events_match_registry", actual_events, expected_events, "Chain events derive from registry")
            chain_summary = self.chain.get("summary") if isinstance(self.chain.get("summary"), dict) else {}
            self._add_exact_check("chain", "ptcar_chain_summary_current_entry_id", chain_summary.get("current_entry_id"), self.registry.get("current_entry_id"), "Chain current entry")
            self._add_exact_check("chain", "ptcar_chain_summary_event_count", chain_summary.get("event_count"), len(expected_events), "Chain event count")
        else:
            self._add_check("chain", "ptcar_chain_exists", "failed", "blocking", "chain-of-custody.json must contain a JSON object.")
        current = _current_entry(self.registry)
        expected_anchor = current.get("anchor") if current and isinstance(current.get("anchor"), dict) else {}
        self._add_exact_check("anchor", "ptcar_current_anchor_matches_entry", self.current_anchor, expected_anchor, "current-anchor.json matches current entry")

    def _verify_registry_entries(self) -> None:
        entries = self.registry.get("entries") if isinstance(self.registry.get("entries"), list) else []
        ids = [str(item.get("entry_id") or "") for item in entries if isinstance(item, dict)]
        self._add_check("registry", "ptcar_entry_ids_unique", "passed" if len(ids) == len(set(ids)) else "failed", "blocking", "Entry ids are unique." if len(ids) == len(set(ids)) else "Entry ids are duplicated.")
        expected_entry_docs = {f"entries/{_safe_id(str(item.get('entry_id') or 'entry'))}.json": item for item in entries if isinstance(item, dict)}
        self._add_exact_check("entries", "ptcar_entry_sidecar_set", sorted(self.entries), sorted(expected_entry_docs), "Entry sidecar set")
        for entry in entries:
            if not isinstance(entry, dict):
                self._add_check("registry", "ptcar_entry_shape", "failed", "blocking", "Registry entry is not an object.")
                continue
            entry_id = str(entry.get("entry_id") or "unknown")
            self._add_hash_check("registry", f"{entry_id}_integrity", entry.get("integrity_hash"), anchor_entry_hash(entry), f"Entry {entry_id} integrity")
            self._add_check("registry", f"{entry_id}_status", "passed" if entry.get("status") in ANCHOR_ENTRY_STATUSES else "failed", "blocking", f"Entry {entry_id} status is valid." if entry.get("status") in ANCHOR_ENTRY_STATUSES else f"Entry {entry_id} status is invalid.")
            self._add_check("registry", f"{entry_id}_signature", "passed" if anchor_entry_signature_ok(entry) else "failed", "blocking", f"Entry {entry_id} signature envelope is valid." if anchor_entry_signature_ok(entry) else f"Entry {entry_id} signature envelope is invalid.")
            anchor = entry.get("anchor") if isinstance(entry.get("anchor"), dict) else {}
            self._add_hash_check("registry", f"{entry_id}_anchor_hash", entry.get("anchor_hash"), anchor.get("anchor_hash"), f"Entry {entry_id} anchor hash")
            self._add_hash_check("registry", f"{entry_id}_anchor_payload_hash", anchor.get("anchor_hash"), stable_hash({key: val for key, val in anchor.items() if key != "anchor_hash"}), f"Entry {entry_id} anchor payload hash")
            if entry.get("status") == "superseded":
                target = str(entry.get("superseded_by_entry_id") or "")
                self._add_check("registry", f"{entry_id}_superseded_target", "passed" if target and target in ids else "failed", "blocking", f"Entry {entry_id} replacement exists." if target and target in ids else f"Entry {entry_id} replacement is missing.")
            sidecar_path = f"entries/{_safe_id(entry_id)}.json"
            self._add_exact_check("entries", f"{entry_id}_sidecar_matches_registry", self.entries.get(sidecar_path), entry, f"Entry {entry_id} sidecar matches registry")
        current_id = str(self.registry.get("current_entry_id") or "")
        current = _find_entry(self.registry, current_id) if current_id else {}
        self._add_check("registry", "ptcar_current_entry_exists", "passed" if not current_id or current else "failed", "blocking", "Current entry exists when set." if not current_id or current else "Current entry is missing.")
        self._add_check("registry", "ptcar_current_entry_published", "passed" if not current_id or current.get("status") == "published" else "failed", "blocking", "Current entry is published." if not current_id or current.get("status") == "published" else "Current entry is not published.")
        self._add_check("registry", "ptcar_current_not_revoked", "passed" if not current_id or current.get("status") != "revoked" else "failed", "blocking", "Current entry is not revoked." if not current_id or current.get("status") != "revoked" else "Current entry is revoked.")

    def _verify_event_chain(self) -> None:
        previous = None
        ok = True
        for event in self.registry.get("events", []) if isinstance(self.registry.get("events"), list) else []:
            if not isinstance(event, dict) or event.get("previous_event_hash") != previous or event.get("event_hash") != anchor_event_hash(event):
                ok = False
                break
            previous = event.get("event_hash")
        self._add_check("registry", "ptcar_event_chain", "passed" if ok else "failed", "blocking", "Event chain is valid." if ok else "Event chain is invalid.")

    def _verify_requirements(self) -> None:
        current_id = str(self.registry.get("current_entry_id") or "")
        current = _find_entry(self.registry, current_id) if current_id else {}
        if self.require_current:
            self._add_check("requirements", "ptcar_require_current", "passed" if current_id and current else "failed", "blocking", "Current anchor entry exists." if current_id and current else "Current anchor entry is required.")
        if self.require_anchor_published:
            self._add_check("requirements", "ptcar_require_anchor_published", "passed" if current and current.get("status") == "published" else "failed", "blocking", "Current anchor entry is published." if current and current.get("status") == "published" else "Published current anchor entry is required.")
        if self.require_anchor_not_revoked:
            self._add_check("requirements", "ptcar_require_anchor_not_revoked", "passed" if current and current.get("status") != "revoked" else "failed", "blocking", "Current anchor entry is not revoked." if current and current.get("status") != "revoked" else "Current anchor entry must not be revoked.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".txt", ".md", ".html")):
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
        self._add_check("redaction", "ptcar_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
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
        return sanitize_metadata(value if isinstance(value, dict) else {}, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = anchor_registry_summary(self.registry)
        summary.update({"center_id": self.manifest.get("center_id") or self.registry.get("center_id"), "blocker_count": len(blockers), "warning_count": len(warnings)})
        report = {
            "schema_version": ANCHOR_REGISTRY_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
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


def _report_source_from_registry(registry: dict[str, Any]) -> dict[str, Any]:
    current = _current_entry(registry)
    zip_fingerprint = current.get("zip_fingerprint") if current and isinstance(current.get("zip_fingerprint"), dict) else {}
    return {
        "registry_hash": registry.get("integrity_hash"),
        "current_entry_id": registry.get("current_entry_id"),
        "current_entry_hash": current.get("integrity_hash") if current else None,
        "current_anchor_hash": current.get("anchor_hash") if current else None,
        "current_zip_sha256": zip_fingerprint.get("zip_sha256") if current else None,
        "current_manifest_hash": zip_fingerprint.get("manifest_hash") if current else None,
        "current_source_hash": zip_fingerprint.get("source_hash") if current else None,
    }


def _current_entry(registry: dict[str, Any]) -> dict[str, Any]:
    return _find_entry(registry, str(registry.get("current_entry_id") or "")) if registry.get("current_entry_id") else {}


def _find_entry(registry: dict[str, Any], entry_id: str) -> dict[str, Any]:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}


def _is_safe_zip_entry(name: str) -> bool:
    text = str(name or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        return False
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return False
    if ":" in path.parts[0]:
        return False
    return True


def _is_forbidden_public_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")


def _raw_zip_entry_names(path: Path) -> list[str]:
    data = path.read_bytes() if path.exists() else b""
    names: list[str] = []
    index = 0
    signature = b"PK\x01\x02"
    while True:
        index = data.find(signature, index)
        if index < 0 or index + 46 > len(data):
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, index + 28)
        start = index + 46
        end = start + name_len
        if end > len(data):
            break
        try:
            names.append(data[start:end].decode("utf-8"))
        except UnicodeDecodeError:
            names.append(data[start:end].decode("cp437", errors="replace"))
        index = end + extra_len + comment_len
    return names


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "").strip())
    return text.strip("-") or "default"


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


def _redaction_findings(path: str, text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": kind, "excerpt": match.group(0)[:120]})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            rows.append({"path": path, "type": "sensitive_value", "pattern": replacement, "excerpt": match.group(0)[:120]})
    return rows


def _blocked_key_findings(path: str, value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(current: Any, trail: str) -> None:
        if isinstance(current, dict):
            for key, item in current.items():
                lowered = str(key).lower()
                if any(marker in lowered for marker in ("api_key", "access_token", "token", "secret", "password", "provider-snapshot", "renderer.json", "source_path", "local_path", "file_path")):
                    rows.append({"path": path, "type": "blocked_key", "key": f"{trail}.{key}" if trail else str(key)})
                walk(item, f"{trail}.{key}" if trail else str(key))
        elif isinstance(current, list):
            for index, item in enumerate(current):
                walk(item, f"{trail}[{index}]")

    walk(value, "")
    return rows
