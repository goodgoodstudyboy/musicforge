from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)

import hashlib as hashlib
import json as json
import re as re
import struct as struct
import sys as sys
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS


HUMAN_REVIEW_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 512
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 2048
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {"manifest.json", "pack.json", "index.html", "response-template.json", "checksums.json", "README.txt"}
LEGAL_SIDECAR_ENTRIES = {"manifest.json", "checksums.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_REPORT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


def verify_human_review_pack(
    zip_path: Path | str,
    *,
    strict: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _HumanReviewPackVerifier(
        Path(zip_path),
        strict=strict,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def human_review_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "suite_id": summary.get("suite_id"),
            "pack_id": summary.get("pack_id"),
            "case_count": summary.get("case_count", 0),
            "entry_count": summary.get("entry_count", 0),
            "checked_file_count": summary.get("checked_file_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS,
    )


def write_human_review_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))


def print_human_review_verification_report(report: dict[str, Any]) -> None:
    summary = human_review_verification_summary(report)
    print("MusicForge human review pack verification")
    print(f"status: {summary.get('status')}")
    print(f"suite: {summary.get('suite_id') or 'unknown'}")
    print(f"pack: {summary.get('pack_id') or 'unknown'}")
    print(f"cases: {summary.get('case_count', 0)}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"checked files: {summary.get('checked_file_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = _as_list(report.get(key))
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            check_id = item.get("check_id", "unknown") if isinstance(item, dict) else "unknown"
            message = item.get("message", str(item)) if isinstance(item, dict) else str(item)
            print(f"  [{check_id}] {message}")
        if len(items) > 10:
            print(f"  ... {len(items) - 10} more")


def human_review_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _HumanReviewPackVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.case_checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.pack: dict[str, Any] = {}
        self.checksums: dict[str, Any] = {}
        self.response_template: dict[str, Any] = {}
        self.valid_json_entries: set[str] = set()
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
                if "manifest.json" in self.entry_map:
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "human_review_manifest_parse")
                if "pack.json" in self.entry_map:
                    self.pack = self._read_json_entry(archive, "pack.json", "pack", "human_review_pack_parse")
                if "checksums.json" in self.entry_map:
                    self.checksums = self._read_json_entry(archive, "checksums.json", "checksums", "human_review_checksums_parse")
                if "response-template.json" in self.entry_map:
                    self.response_template = self._read_json_entry(archive, "response-template.json", "response_template", "human_review_response_template_parse")
                self._verify_manifest(archive)
                self._verify_pack_schema()
                self._verify_assets(archive)
                self._verify_static_html(archive)
                self._verify_response_template()
                self._verify_redaction(archive)
        finally:
            if archive is not None:
                archive.close()
        return self._build_report()

    def _open_zip(self) -> zipfile.ZipFile | None:
        if not self.zip_path.exists() or not self.zip_path.is_file() or self.zip_path.is_symlink():
            self._add_check("zip", "zip_open", "failed", "blocking", "Human review pack ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.", count=self.zip_size_bytes)
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "zip_open", "failed", "blocking", f"Human review pack ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "zip_open", "passed", "blocking", "Human review pack ZIP can be opened.")
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
        self._add_check("zip", "zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.", count=self.total_uncompressed_size)
        self._add_check("zip", "zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.", count=len(self.entry_infos))
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.", count=len(unsafe))
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.", count=len(duplicates))
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required human review entries exist.", count=len(missing))

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "human_review_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        missing_fields = [field for field in ("schema_version", "suite_id", "pack_id", "source_hash") if self.manifest.get(field) in (None, "")]
        if not isinstance(self.manifest.get("files"), list):
            missing_fields.append("files")
        if not isinstance(self.manifest.get("cases"), list):
            missing_fields.append("cases")
        self._add_check("manifest", "human_review_manifest_schema", "failed" if missing_fields else "passed", "blocking", "Missing manifest fields: " + ", ".join(missing_fields) if missing_fields else "Human review manifest schema has required fields.", count=len(missing_fields))
        rows = _as_list(self.manifest.get("files"))
        valid_rows: list[dict[str, Any]] = []
        shape_errors: list[str] = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                shape_errors.append(f"files[{index}] is not an object")
                continue
            path = str(item.get("path") or "")
            size = item.get("size_bytes")
            sha = str(item.get("sha256") or "")
            if not _is_safe_zip_entry(path):
                shape_errors.append(f"{path or f'files[{index}]'} has unsafe path")
            if not isinstance(size, int) or size < 0:
                shape_errors.append(f"{path or f'files[{index}]'} has invalid size")
            if not HEX_SHA256.fullmatch(sha):
                shape_errors.append(f"{path or f'files[{index}]'} has invalid sha256")
            if _is_safe_zip_entry(path) and isinstance(size, int) and size >= 0 and HEX_SHA256.fullmatch(sha):
                valid_rows.append(item)
        self._add_check("manifest", "human_review_manifest_files_shape", "failed" if shape_errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(shape_errors[:5]) if shape_errors else "Manifest file rows are valid.", count=len(shape_errors))
        mismatches: list[str] = []
        for item in valid_rows:
            path = str(item["path"])
            info = self.entry_map.get(path)
            if info is None:
                mismatches.append(f"{path} missing from ZIP")
                continue
            actual_size = int(info.file_size or 0)
            actual_sha = _sha256_entry(archive, info)
            expected_size = int(item["size_bytes"])
            expected_sha = str(item["sha256"])
            self.files.append({"path": path, "size_bytes": actual_size, "sha256": actual_sha, "status": "passed" if actual_size == expected_size and actual_sha == expected_sha else "failed"})
            if actual_size != expected_size:
                mismatches.append(f"{path} size mismatch")
            if actual_sha != expected_sha:
                mismatches.append(f"{path} hash mismatch")
        self._add_check("manifest", "human_review_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Human review file mismatches: " + "; ".join(mismatches[:5]) if mismatches else "Manifest files match ZIP bytes.", count=len(mismatches))
        allowed = {str(item.get("path")) for item in valid_rows}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "human_review_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside manifest.files.", count=len(extra))

    def _verify_pack_schema(self) -> None:
        if not self.pack:
            self._add_check("pack", "human_review_pack_exists", "failed", "blocking", "pack.json is missing or invalid.")
            return
        suite_match = self.pack.get("suite_id") == self.manifest.get("suite_id")
        pack_match = self.pack.get("pack_id") == self.manifest.get("pack_id")
        source_match = self.pack.get("source_hash") == self.manifest.get("source_hash")
        cases = _as_list(self.pack.get("cases"))
        self._add_check("pack", "human_review_pack_manifest_match", "passed" if suite_match and pack_match and source_match else "failed", "blocking", "Pack identity matches manifest." if suite_match and pack_match and source_match else "Pack identity does not match manifest.")
        self._add_check("pack", "human_review_pack_cases", "passed" if cases else "failed", "blocking", f"Pack includes {len(cases)} review case(s)." if cases else "Pack includes no review cases.", count=len(cases))
        case_ids = [str(item.get("case_id") or "") for item in cases if isinstance(item, dict)]
        duplicates = sorted(case_id for case_id, count in _counts(case_ids).items() if case_id and count > 1)
        self._add_check("pack", "human_review_pack_duplicate_cases", "failed" if duplicates else "passed", "blocking", "Duplicate case ids: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate case ids.", count=len(duplicates))

    def _verify_assets(self, archive: zipfile.ZipFile) -> None:
        cases = _as_list(self.pack.get("cases"))
        for item in cases:
            if not isinstance(item, dict):
                continue
            case_id = str(item.get("case_id") or "")
            midi_path = str(item.get("midi_path") or "")
            wav_path = str(item.get("wav_path") or "")
            if not midi_path:
                self._add_case_check(case_id, "human_review_case_midi_declared", "failed", "blocking", "Case does not declare a MIDI asset.")
            elif midi_path not in self.entry_map:
                self._add_case_check(case_id, "human_review_case_midi_exists", "failed", "blocking", f"MIDI asset is missing: {midi_path}")
            else:
                data = archive.read(self.entry_map[midi_path])[:4]
                self._add_case_check(case_id, "human_review_case_midi_header", "passed" if data == b"MThd" else "failed", "blocking", "MIDI asset has a valid header." if data == b"MThd" else f"MIDI asset is not a valid MIDI file: {midi_path}")
            if wav_path:
                if wav_path not in self.entry_map:
                    self._add_case_check(case_id, "human_review_case_wav_exists", "failed", "blocking", f"WAV asset is missing: {wav_path}")
                else:
                    data = archive.read(self.entry_map[wav_path])[:12]
                    ok = data[:4] == b"RIFF" and data[8:12] == b"WAVE"
                    self._add_case_check(case_id, "human_review_case_wav_header", "passed" if ok else "failed", "blocking", "WAV asset has a valid header." if ok else f"WAV asset is not a valid WAV file: {wav_path}")

    def _verify_static_html(self, archive: zipfile.ZipFile) -> None:
        info = self.entry_map.get("index.html")
        if info is None:
            return
        text = archive.read(info).decode("utf-8", errors="replace")
        remote_patterns = ("http://", "https://", "<script src=", "<link href=", "eval(", "new Function")
        hits = [pattern for pattern in remote_patterns if pattern.lower() in text.lower()]
        self._add_check("html", "human_review_static_html_offline", "failed" if hits else "passed", "blocking", "index.html contains remote or dynamic script references: " + ", ".join(hits) if hits else "index.html is self-contained and offline-safe.", count=len(hits))

    def _verify_response_template(self) -> None:
        template = self.response_template
        if not template:
            return
        reviews = _as_list(template.get("reviews"))
        status = "passed" if template.get("suite_id") == self.manifest.get("suite_id") and template.get("pack_id") == self.manifest.get("pack_id") and reviews else "failed"
        self._add_check("response_template", "human_review_response_template_schema", status, "blocking", f"Response template includes {len(reviews)} review row(s)." if status == "passed" else "Response template does not match manifest or has no reviews.", count=len(reviews))
    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for info in self.entry_infos:
            name = info.filename
            if info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            lower = name.lower()
            if not lower.endswith((".json", ".txt", ".html", ".csv", ".md")):
                continue
            try:
                text = archive.read(info).decode("utf-8")
            except (UnicodeDecodeError, OSError, RuntimeError):
                continue
            self.redaction_findings.extend(_redaction_findings(name, text))
            if lower.endswith(".json"):
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    continue
                self.redaction_findings.extend(_blocked_key_findings(name, value))
        self._add_check("redaction", "human_review_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.", count=len(self.redaction_findings))

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> ImplementationDocument:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not valid UTF-8 JSON: {exc}")
            return {}
        if not isinstance(value, dict):
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is not a JSON object.")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} is valid JSON.")
        self.valid_json_entries.add(name)
        return value

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str, *, count: int | None = None) -> None:
        item: dict[str, Any] = {"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message}
        if count is not None:
            item["count"] = count
        self.checks.append(sanitize_metadata(item, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))

    def _add_case_check(self, case_id: str, check_id: str, status: str, severity: str, message: str, *, count: int | None = None) -> None:
        item: dict[str, Any] = {"scope": "case", "case_id": case_id, "check_id": check_id, "status": status, "severity": severity, "message": message}
        if count is not None:
            item["count"] = count
        self.case_checks.append(sanitize_metadata(item, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS))

    def _build_report(self) -> ImplementationDocument:
        blockers = [item for item in [*self.checks, *self.case_checks] if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in [*self.checks, *self.case_checks] if item.get("status") == "warning"]
        status = "failed" if blockers else "warning" if warnings else "passed"
        cases = _as_list(self.pack.get("cases"))
        report = {
            "schema_version": HUMAN_REVIEW_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "tool": {"name": "MusicForge Human Review Pack Verifier", "version": __version__},
            "input": {"filename": self.zip_path.name, "size_bytes": self.zip_size_bytes, "sha256": self.zip_sha256},
            "status": status,
            "strict": self.strict,
            "summary": {
                "suite_id": self.manifest.get("suite_id"),
                "pack_id": self.manifest.get("pack_id"),
                "source_hash": self.manifest.get("source_hash"),
                "case_count": len(cases),
                "entry_count": len(self.entry_infos),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "total_uncompressed_size_bytes": self.total_uncompressed_size,
            },
            "checks": self.checks,
            "case_checks": self.case_checks,
            "files": self.files,
            "redaction_findings": self.redaction_findings,
            "warnings": warnings,
            "blockers": blockers,
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_REPORT_BLOCKED_KEYS)


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info, "r") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redaction_findings(path: str, text: str) -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    for pattern, kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": kind, "message": f"{path} contains a local path-like value."})
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "sensitive_value", "message": f"{path} contains a sensitive value pattern: {replacement}."})
    return findings


def _blocked_key_findings(path: str, value: Any, *, prefix: str = "") -> list[ImplementationDocument]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in VERIFIER_REPORT_BLOCKED_KEYS:
                findings.append({"path": path, "field": child_path, "kind": "blocked_key", "message": f"{path} contains blocked key {child_path}."})
            findings.extend(_blocked_key_findings(path, item, prefix=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(path, item, prefix=f"{prefix}[{index}]"))
    return findings


def _main() -> None:
    report = verify_human_review_pack(Path(sys.argv[1]))
    print_human_review_verification_report(report)
    raise SystemExit(human_review_verification_exit_code(report))


if __name__ == "__main__":
    _main()
