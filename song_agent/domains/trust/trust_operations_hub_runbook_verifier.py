from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib as hashlib
import json as json
import os as os
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_hub_runbook_contracts import RUNBOOK_EXPORT_ENTRIES as RUNBOOK_EXPORT_ENTRIES, TRUST_OPERATIONS_RUNBOOK_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_RUNBOOK_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_RUNBOOK_PACKAGE_TYPE as TRUST_OPERATIONS_RUNBOOK_PACKAGE_TYPE, TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE as TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE, TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION as TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION, runbook_hash as runbook_hash


TRUST_OPERATIONS_RUNBOOK_VERIFICATION_PACKAGE_TYPE = "musicforge_trust_operations_hub_runbook_verification"
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 64
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
VERIFIER_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


def verify_trust_operations_hub_runbook_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_completed: bool = False,
    require_no_blocked: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _RunbookVerifier(
        Path(zip_path),
        strict=strict,
        require_completed=require_completed,
        require_no_blocked=require_no_blocked,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def write_trust_operations_hub_runbook_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_trust_operations_hub_runbook_verification_report(report: dict[str, Any]) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge Trust Operations Hub Runbook verification")
    print(f"status: {report.get('status')}")
    print(f"runbook: {summary.get('runbook_id') or '-'}")
    print(f"result: {summary.get('result_status') or '-'}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")


def trust_operations_hub_runbook_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _RunbookVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_completed: bool,
        require_no_blocked: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_completed = require_completed
        self.require_no_blocked = require_no_blocked
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.entry_infos: list[zipfile.ZipInfo] = []
        self.entry_names: list[str] = []
        self.raw_entry_names: list[str] = []
        self.entry_map: dict[str, zipfile.ZipInfo] = {}
        self.redaction_findings: list[dict[str, Any]] = []
        self.zip_sha256: str | None = None
        self.zip_size_bytes = 0
        self.total_uncompressed_size = 0
        self.manifest: dict[str, Any] = {}
        self.runbook: dict[str, Any] = {}
        self.result: dict[str, Any] = {}
        self.checksum_json: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = self._open_zip()
            if archive is not None:
                self._verify_zip_structure(archive)
                self._read_documents(archive)
                self._verify_manifest(archive)
                self._verify_documents()
                self._verify_checksums(archive)
                self._verify_semantics()
                self._verify_requirements()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        zip_fs_path = _fs_path(self.zip_path)
        if not os.path.isfile(zip_fs_path) or os.path.islink(zip_fs_path):
            self._add_check("zip", "tohr_zip_open", "failed", "blocking", "Runbook ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = os.stat(zip_fs_path).st_size
        self.zip_sha256 = _sha256_file(self.zip_path)
        limit = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "tohr_zip_size_limit", "passed" if self.zip_size_bytes <= limit else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {limit} bytes.")
        try:
            archive = zipfile.ZipFile(zip_fs_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "tohr_zip_open", "failed", "blocking", f"Runbook ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "tohr_zip_open", "passed", "blocking", "Runbook ZIP can be opened.")
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
        self._add_check("zip", "tohr_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= self.max_uncompressed_size_mb * 1024 * 1024 else "failed", "blocking", "Runbook ZIP uncompressed size is within limit.")
        self._add_check("zip", "tohr_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", "Runbook ZIP entry count is within limit.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_entry(name)]
        self._add_check("zip", "tohr_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "tohr_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        forbidden = [name for name in self.entry_names if _is_forbidden_entry(name)]
        self._add_check("zip", "tohr_zip_no_internal_entries", "failed" if forbidden else "passed", "blocking", "Forbidden internal entries: " + ", ".join(forbidden[:5]) if forbidden else "No .musicforge entries are present.")
        nested = sorted(name for name in self.entry_names if name.lower().endswith(".zip"))
        self._add_check("zip", "tohr_zip_nested_allowlist", "failed" if nested else "passed", "blocking", "Nested ZIP entries are not allowed." if nested else "No nested ZIP entries are present.")
        missing = sorted(RUNBOOK_EXPORT_ENTRIES - set(self.entry_names))
        unexpected = sorted(set(self.entry_names) - RUNBOOK_EXPORT_ENTRIES)
        self._add_check("zip", "tohr_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing Runbook entries: " + ", ".join(missing[:8]) if missing else "All required Runbook entries exist.")
        self._add_check("zip", "tohr_zip_allowed_entries", "failed" if unexpected else "passed", "blocking", "Unexpected Runbook entries: " + ", ".join(unexpected[:8]) if unexpected else "Runbook ZIP contains only fixed entries.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.manifest = self._read_json_entry(archive, "trust-operations-hub-runbook-manifest.json", "manifest", "tohr_manifest_parse")
        self.runbook = self._read_json_entry(archive, "runbook.json", "runbook", "tohr_runbook_parse")
        self.result = self._read_json_entry(archive, "runbook-result.json", "result", "tohr_result_parse")
        self.checksum_json = self._read_json_entry(archive, "checksum/SHA256SUMS.json", "checksum", "tohr_checksum_json_parse")
        self.events = self._read_jsonl_entry(archive, "runbook-events.jsonl", "events", "tohr_events_parse")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        self._add_hash_check("manifest", "tohr_manifest_integrity", self.manifest.get("integrity_hash"), runbook_hash(self.manifest), "Runbook manifest integrity")
        self._add_exact_check("manifest", "tohr_manifest_package_type", self.manifest.get("package_type"), TRUST_OPERATIONS_RUNBOOK_MANIFEST_PACKAGE_TYPE, "Runbook manifest package_type")
        rows = _as_list(self.manifest.get("files"))
        manifest_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        self._add_exact_check("manifest", "tohr_manifest_allowed_files", sorted(manifest_paths), sorted(RUNBOOK_EXPORT_ENTRIES - {"trust-operations-hub-runbook-manifest.json"}), "Manifest file list matches fixed Runbook structure")
        mismatches: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(path + ":missing")
                continue
            actual_sha = _sha256_entry(archive, info)
            actual_size = int(info.file_size or 0)
            if actual_sha != item.get("sha256") or actual_size != item.get("size_bytes"):
                mismatches.append(path)
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if path not in mismatches else "failed"})
        self._add_check("manifest", "tohr_manifest_file_hashes", "failed" if mismatches else "passed", "blocking", "Manifest file mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Manifest file hashes match ZIP entries.")
        manifest_zip_entries = set(str(item) for item in (_as_list((self.manifest.get("zip") or {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else [])) if item)
        spoof = sorted(manifest_zip_entries - set(self.entry_names))
        self._add_check("manifest", "tohr_manifest_zip_entries_reference_only", "failed" if spoof else "passed", "blocking", "manifest.zip.entries references missing files." if spoof else "manifest.zip.entries does not expand ZIP contents.")

    def _verify_documents(self) -> None:
        for label, doc in {"runbook": self.runbook, "result": self.result, "checksum": self.checksum_json}.items():
            self._add_hash_check(label, f"tohr_{label}_integrity", doc.get("integrity_hash"), runbook_hash(doc), f"{label} integrity")
        self._add_exact_check("runbook", "tohr_runbook_package_type", self.runbook.get("package_type"), TRUST_OPERATIONS_RUNBOOK_PACKAGE_TYPE, "Runbook package_type")
        self._add_exact_check("result", "tohr_result_package_type", self.result.get("package_type"), TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE, "Runbook result package_type")
        source = _as_document(self.manifest.get("source"))
        self._add_exact_check("manifest", "tohr_manifest_source_runbook_hash", source.get("runbook_hash"), self.runbook.get("integrity_hash"), "Manifest runbook hash")
        self._add_exact_check("manifest", "tohr_manifest_source_result_hash", source.get("result_hash"), self.result.get("integrity_hash"), "Manifest result hash")
        self._add_exact_check("manifest", "tohr_manifest_source_event_chain_hash", source.get("event_chain_hash"), self.events[-1].get("event_hash") if self.events else None, "Manifest event chain hash")

    def _verify_checksums(self, archive: zipfile.ZipFile) -> None:
        rows = _as_list(self.checksum_json.get("files"))
        row_paths = {str(item.get("path") or "") for item in rows if isinstance(item, dict)}
        expected_paths = RUNBOOK_EXPORT_ENTRIES - {"trust-operations-hub-runbook-manifest.json", "checksum/SHA256SUMS.json", "checksum/SHA256SUMS.txt"}
        self._add_exact_check("checksum", "tohr_checksum_allowed_files", sorted(row_paths), sorted(expected_paths), "Checksum file list matches fixed Runbook payload files")
        mismatches: list[str] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(path + ":missing")
                continue
            if _sha256_entry(archive, info) != item.get("sha256") or int(info.file_size or 0) != item.get("size_bytes"):
                mismatches.append(path)
        self._add_check("checksum", "tohr_checksum_file_hashes", "failed" if mismatches else "passed", "blocking", "Checksum mismatches: " + ", ".join(mismatches[:8]) if mismatches else "Checksum hashes match ZIP entries.")

    def _verify_semantics(self) -> None:
        actions = _as_list(self.runbook.get("actions"))
        results = _as_list(self.result.get("results"))
        self._add_exact_check("runbook", "tohr_runbook_summary_matches_actions", self.runbook.get("summary"), _action_summary(actions), "Runbook summary matches actions")
        self._add_exact_check("result", "tohr_result_summary_matches_results", self.result.get("summary"), _result_summary(results), "Runbook result summary matches results")
        self._add_exact_check("result", "tohr_result_source_runbook_hash", (_as_document(self.result.get("source"))).get("runbook_hash"), self.runbook.get("integrity_hash"), "Result runbook hash")
        chain_ok = _event_chain_ok(self.events)
        self._add_check("events", "tohr_event_chain_integrity", "passed" if chain_ok else "failed", "blocking", "Runbook event chain is intact." if chain_ok else "Runbook event chain is broken.")
        expected_result_actions = sorted(str(action.get("action_id") or "") for action in actions if isinstance(action, dict))
        actual_result_actions = sorted(str(item.get("action_id") or "") for item in results if isinstance(item, dict))
        self._add_exact_check("result", "tohr_result_actions_match_runbook", actual_result_actions, expected_result_actions, "Result actions match runbook actions")
        event_action_ids = sorted(str((_as_document(event.get("payload"))).get("action_id") or "") for event in self.events if str(event.get("event_type") or "").startswith("runbook_action_"))
        safe_result_ids = sorted(str(item.get("action_id") or "") for item in results if isinstance(item, dict) and item.get("status") in {"completed", "blocked"})
        self._add_exact_check("events", "tohr_safe_results_match_events", safe_result_ids, event_action_ids, "Safe action results match event log")

    def _verify_requirements(self) -> None:
        completed = self.result.get("status") in {"completed", "completed_with_manual_actions"}
        self._add_check("requirements", "tohr_require_completed", "passed" if completed or not self.require_completed else "failed", "blocking", "Runbook completed." if completed else "Runbook is not completed.")
        blocked_count = int((_as_document(self.result.get("summary"))).get("blocked_count") or 0)
        self._add_check("requirements", "tohr_require_no_blocked", "passed" if blocked_count == 0 or not self.require_no_blocked else "failed", "blocking", "Runbook has no blocked safe actions." if blocked_count == 0 else "Runbook has blocked safe actions.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        findings: list[dict[str, Any]] = []
        for info in self.entry_infos:
            name = info.filename
            if not _is_text_scan_entry(name) or int(info.file_size or 0) > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8", errors="ignore")
            except (KeyError, OSError):
                continue
            if _contains_sensitive_text(text):
                findings.append({"path": name, "reason": "sensitive_text"})
        for doc_name, doc in {"manifest": self.manifest, "runbook": self.runbook, "result": self.result, "checksum": self.checksum_json}.items():
            for path, value in _walk_json_values(doc):
                if _contains_sensitive_text(str(value)):
                    findings.append({"path": f"{doc_name}:{path}", "reason": "sensitive_value"})
        self.redaction_findings = findings
        self._add_check("security", "tohr_redaction_scan", "failed" if findings else "passed", "blocking", "Sensitive values found in Runbook package." if findings else "No sensitive values found in Runbook package.")

    def _build_report(self) -> ImplementationDocument:
        blockers = [check for check in self.checks if check["status"] == "failed" and check["severity"] == "blocking"]
        warnings = [check for check in self.checks if check["status"] in {"failed", "warning"} and check["severity"] != "blocking"]
        summary = {
            "hub_id": self.runbook.get("hub_id"),
            "report_id": self.runbook.get("report_id"),
            "runbook_id": self.runbook.get("runbook_id"),
            "result_status": self.result.get("status"),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "zip_size_bytes": self.zip_size_bytes,
        }
        return sanitize_metadata(
            {
                "schema_version": TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION,
                "package_type": TRUST_OPERATIONS_RUNBOOK_VERIFICATION_PACKAGE_TYPE,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "passed",
                "zip_sha256": self.zip_sha256,
                "zip_size_bytes": self.zip_size_bytes,
                "manifest_hash": self.manifest.get("integrity_hash"),
                "source_hash": self.runbook.get("integrity_hash"),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "files": self.files,
                "summary": summary,
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        try:
            raw = archive.read(name)
            value = json.loads(raw.decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parsed.")
        return value

    def _read_jsonl_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> list[ImplementationDocument]:
        try:
            raw = archive.read(name)
        except (KeyError, OSError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be read: {exc}")
            return []
        rows: list[dict[str, Any]] = []
        for line in raw.decode("utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                self._add_check(scope, check_id, "failed", "blocking", f"{name} contains invalid JSONL.")
                return []
            if isinstance(value, dict):
                rows.append(value)
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parsed.")
        return rows

    def _add_hash_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected and actual else "failed", "blocking", f"{label} matches." if actual == expected and actual else f"{label} mismatch.")

    def _add_exact_check(self, scope: str, check_id: str, actual: Any, expected: Any, label: str) -> None:
        self._add_check(scope, check_id, "passed" if actual == expected else "failed", "blocking", f"{label} matches." if actual == expected else f"{label} mismatch.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


def _action_summary(actions: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "action_count": len(actions),
        "safe_action_count": sum(1 for action in actions if action.get("allowed_automation") is True),
        "manual_required_count": sum(1 for action in actions if action.get("status") == "manual_required"),
    }


def _result_summary(results: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "result_count": len(results),
        "completed_count": sum(1 for item in results if item.get("status") == "completed"),
        "blocked_count": sum(1 for item in results if item.get("status") == "blocked"),
        "manual_required_count": sum(1 for item in results if item.get("status") == "manual_required"),
    }


def _event_chain_ok(events: list[ImplementationDocument]) -> bool:
    previous_hash = None
    for event in events:
        if event.get("previous_event_hash") != previous_hash:
            return False
        expected = _event_hash(event)
        if event.get("event_hash") != expected:
            return False
        previous_hash = event.get("event_hash")
    return True


def _event_hash(event: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in event.items() if key != "event_hash"})


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _is_safe_entry(name: str) -> bool:
    if not name or "\\" in name:
        return False
    try:
        path = PurePosixPath(name)
    except ValueError:
        return False
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _is_forbidden_entry(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(".musicforge/") or "/.musicforge/" in lowered


def _is_text_scan_entry(name: str) -> bool:
    return name.lower().endswith((".json", ".txt", ".md", ".csv", ".html", ".jsonl"))


def _contains_sensitive_text(text: str) -> bool:
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    lowered = text.lower()
    extra_markers = ("github" + "key", "x-access" + "-token", "github" + "_pat_")
    return any(marker in lowered for marker in extra_markers)


def _walk_json_values(value: Any, prefix: str = "$") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(_walk_json_values(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_walk_json_values(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        rows.append((prefix, value))
    return rows


def _fs_path(path: Path) -> str:
    value = os.fspath(path)
    if os.name == "nt":
        absolute = os.path.abspath(value)
        if absolute.startswith("\\\\?\\"):
            return absolute
        if absolute.startswith("\\\\"):
            return "\\\\?\\UNC\\" + absolute[2:]
        return "\\\\?\\" + absolute
    return value
