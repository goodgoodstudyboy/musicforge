from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.projectio import write_json
from song_agent.redaction import DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS, sanitize_metadata
from song_agent.release_portfolio_governance import (
    PORTFOLIO_GOVERNANCE_BLOCKED_KEYS,
    action_plan_integrity_hash,
    execution_report_integrity_hash,
    governance_manifest_integrity_hash,
    manual_action_list_integrity_hash,
    queue_integrity_hash,
)
from song_agent.release_verifier import LOCAL_PATH_VALUE_PATTERNS


PORTFOLIO_GOVERNANCE_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 128
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 512
DEFAULT_MAX_ENTRY_COUNT = 5000
MAX_TEXT_SCAN_BYTES = 2 * 1024 * 1024
REQUIRED_ENTRIES = {
    "manifest.json",
    "queue.json",
    "action-plan.json",
    "execution-report.json",
    "manual-action-list.json",
    "portfolio-source-summary.json",
    "action-source-map.json",
    "GOVERNANCE_ACTIONS.md",
    "MANUAL_ACTIONS.md",
    "README.txt",
}
LEGAL_SIDECAR_ENTRIES = {"manifest.json"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")
VERIFIER_BLOCKED_KEYS = PORTFOLIO_GOVERNANCE_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


def verify_release_portfolio_governance_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_manual_actions: bool = False,
    require_no_blocked: bool = False,
    max_zip_size_mb: int = DEFAULT_MAX_ZIP_SIZE_MB,
    max_uncompressed_size_mb: int = DEFAULT_MAX_UNCOMPRESSED_SIZE_MB,
    max_entry_count: int = DEFAULT_MAX_ENTRY_COUNT,
    now: str | None = None,
) -> dict[str, Any]:
    verifier = _PortfolioGovernanceVerifier(
        Path(zip_path),
        strict=strict,
        require_manual_actions=require_manual_actions,
        require_no_blocked=require_no_blocked,
        max_zip_size_mb=max_zip_size_mb,
        max_uncompressed_size_mb=max_uncompressed_size_mb,
        max_entry_count=max_entry_count,
        now=now,
    )
    return verifier.run()


def release_portfolio_governance_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "queue_id": summary.get("queue_id"),
            "portfolio_id": summary.get("portfolio_id"),
            "total_items": summary.get("total_items", 0),
            "manual_required": summary.get("manual_required", 0),
            "blocked": summary.get("blocked", 0),
            "failed": summary.get("failed", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=VERIFIER_BLOCKED_KEYS,
    )


def write_release_portfolio_governance_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS))


def print_release_portfolio_governance_verification_report(report: dict[str, Any]) -> None:
    summary = release_portfolio_governance_verification_summary(report)
    print("MusicForge release portfolio governance queue verification")
    print(f"status: {summary.get('status')}")
    print(f"queue: {summary.get('queue_id') or 'unknown'}")
    print(f"portfolio: {summary.get('portfolio_id') or 'unknown'}")
    print(f"items: {summary.get('total_items', 0)}")
    print(f"manual required: {summary.get('manual_required', 0)}")
    print(f"blocked: {summary.get('blocked', 0)}")
    print(f"failed: {summary.get('failed', 0)}")
    for label, key in (("Blockers", "blockers"), ("Warnings", "warnings")):
        items = report.get(key) if isinstance(report.get(key), list) else []
        if not items:
            continue
        print(f"{label}:")
        for item in items[:10]:
            print(f"  [{item.get('check_id', 'unknown')}] {item.get('message', '')}")


def release_portfolio_governance_verification_exit_code(report: dict[str, Any]) -> int:
    return 1 if report.get("status") == "failed" else 0


class _PortfolioGovernanceVerifier:
    def __init__(
        self,
        zip_path: Path,
        *,
        strict: bool,
        require_manual_actions: bool,
        require_no_blocked: bool,
        max_zip_size_mb: int,
        max_uncompressed_size_mb: int,
        max_entry_count: int,
        now: str | None,
    ) -> None:
        self.zip_path = zip_path
        self.strict = strict
        self.require_manual_actions = require_manual_actions
        self.require_no_blocked = require_no_blocked
        self.max_zip_size_mb = max(1, int(max_zip_size_mb))
        self.max_uncompressed_size_mb = max(1, int(max_uncompressed_size_mb))
        self.max_entry_count = max(1, int(max_entry_count))
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[dict[str, Any]] = []
        self.files: list[dict[str, Any]] = []
        self.redaction_findings: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {}
        self.queue: dict[str, Any] = {}
        self.action_plan: dict[str, Any] = {}
        self.execution_report: dict[str, Any] = {}
        self.manual_actions: dict[str, Any] = {}
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
                    self.manifest = self._read_json_entry(archive, "manifest.json", "manifest", "portfolio_governance_manifest_parse")
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
            self._add_check("zip", "portfolio_governance_zip_open", "failed", "blocking", "Governance Queue ZIP does not exist or is not a regular file.")
            return None
        self.zip_size_bytes = self.zip_path.stat().st_size
        max_size = self.max_zip_size_mb * 1024 * 1024
        self._add_check("zip", "portfolio_governance_zip_size_limit", "passed" if self.zip_size_bytes <= max_size else "failed", "blocking", f"ZIP size is {self.zip_size_bytes} bytes; limit is {max_size} bytes.")
        self.zip_sha256 = _sha256_file(self.zip_path)
        try:
            archive = zipfile.ZipFile(self.zip_path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            self._add_check("zip", "portfolio_governance_zip_open", "failed", "blocking", f"Governance Queue ZIP cannot be opened: {exc}")
            return None
        self._add_check("zip", "portfolio_governance_zip_open", "passed", "blocking", "Governance Queue ZIP can be opened.")
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
        self._add_check("zip", "portfolio_governance_zip_uncompressed_size_limit", "passed" if self.total_uncompressed_size <= max_uncompressed else "failed", "blocking", f"Total uncompressed size is {self.total_uncompressed_size} bytes; limit is {max_uncompressed} bytes.")
        self._add_check("zip", "portfolio_governance_zip_entry_count_limit", "passed" if len(self.entry_infos) <= self.max_entry_count else "failed", "blocking", f"ZIP has {len(self.entry_infos)} entries; limit is {self.max_entry_count}.")
        unsafe = [name for name in [*self.entry_names, *self.raw_entry_names] if not _is_safe_zip_entry(name)]
        self._add_check("zip", "portfolio_governance_zip_entry_path_safe", "failed" if unsafe else "passed", "blocking", "Unsafe ZIP entries: " + ", ".join(unsafe[:5]) if unsafe else "All ZIP entry paths are safe.")
        duplicates = sorted(name for name, count in _counts(self.entry_names).items() if count > 1)
        self._add_check("zip", "portfolio_governance_zip_duplicate_entries", "failed" if duplicates else "passed", "blocking", "Duplicate ZIP entries: " + ", ".join(duplicates[:5]) if duplicates else "No duplicate ZIP entries.")
        missing = sorted(REQUIRED_ENTRIES - set(self.entry_names))
        self._add_check("zip", "portfolio_governance_zip_required_entries", "failed" if missing else "passed", "blocking", "Missing required entries: " + ", ".join(missing) if missing else "All required Governance Queue entries exist.")

    def _verify_manifest(self, archive: zipfile.ZipFile) -> None:
        if not self.manifest:
            self._add_check("manifest", "portfolio_governance_manifest_exists", "failed", "blocking", "manifest.json is missing or invalid.")
            return
        self._add_check("manifest", "portfolio_governance_manifest_exists", "passed", "blocking", "manifest.json exists.")
        actual_manifest_hash = governance_manifest_integrity_hash(self.manifest)
        self._add_check("manifest", "portfolio_governance_manifest_integrity", "passed" if self.manifest.get("integrity_hash") == actual_manifest_hash else "failed", "blocking", "Governance Queue manifest integrity hash matches." if self.manifest.get("integrity_hash") == actual_manifest_hash else "Governance Queue manifest integrity hash does not match.")
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
        self._add_check("manifest", "portfolio_governance_manifest_files_shape", "failed" if errors else "passed", "blocking", "Invalid manifest file rows: " + "; ".join(errors[:5]) if errors else "Manifest file rows are valid.")
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
        self._add_check("manifest", "portfolio_governance_manifest_file_hash_match", "failed" if mismatches else "passed", "blocking", "Governance Queue file mismatches: " + ", ".join(mismatches[:5]) if mismatches else "Governance Queue manifest files match ZIP bytes.")
        allowed = {str(item.get("path")) for item in valid}
        allowed.update(LEGAL_SIDECAR_ENTRIES)
        extra = sorted(set(self.entry_names) - allowed)
        status = "failed" if extra and self.strict else "warning" if extra else "passed"
        self._add_check("manifest", "portfolio_governance_manifest_extra_entries", status, "blocking" if status == "failed" else "warning", "Extra ZIP entries not declared in manifest.files: " + ", ".join(extra[:5]) if extra else "No extra entries outside legal sidecars.")
        zip_entries = self.manifest.get("zip", {}).get("entries") if isinstance(self.manifest.get("zip"), dict) else None
        if isinstance(zip_entries, list):
            spoofed = sorted((set(str(item) for item in zip_entries) - allowed) & set(self.entry_names))
            self._add_check("manifest", "portfolio_governance_manifest_zip_entries_reference_only", "warning" if spoofed else "passed", "warning", "manifest.zip.entries contains entries not allowed by manifest.files: " + ", ".join(spoofed[:5]) if spoofed else "manifest.zip.entries does not expand the allowed file set.")

    def _read_documents(self, archive: zipfile.ZipFile) -> None:
        self.queue = self._read_json_entry(archive, "queue.json", "queue", "portfolio_governance_queue_parse")
        self.action_plan = self._read_json_entry(archive, "action-plan.json", "action_plan", "portfolio_governance_action_plan_parse")
        self.execution_report = self._read_json_entry(archive, "execution-report.json", "execution_report", "portfolio_governance_execution_report_parse")
        self.manual_actions = self._read_json_entry(archive, "manual-action-list.json", "manual_actions", "portfolio_governance_manual_action_list_parse")

    def _verify_documents(self) -> None:
        if self.queue:
            actual = queue_integrity_hash(self.queue)
            self._add_check("queue", "portfolio_governance_queue_integrity", "passed" if self.queue.get("integrity_hash") == actual else "failed", "blocking", "Governance Queue integrity hash matches." if self.queue.get("integrity_hash") == actual else "Governance Queue integrity hash does not match.")
            sidecar = self.manifest.get("sidecars", {}).get("queue") if isinstance(self.manifest.get("sidecars"), dict) else {}
            ok = isinstance(sidecar, dict) and sidecar.get("payload_hash") == self.queue.get("integrity_hash")
            self._add_check("queue", "portfolio_governance_manifest_queue_hash", "passed" if ok else "failed", "blocking", "Manifest queue hash matches queue.json." if ok else "Manifest queue hash does not match queue.json.")
        if self.action_plan:
            actual = action_plan_integrity_hash(self.action_plan)
            self._add_check("action_plan", "portfolio_governance_action_plan_integrity", "passed" if self.action_plan.get("integrity_hash") == actual else "failed", "blocking", "Action Plan integrity hash matches." if self.action_plan.get("integrity_hash") == actual else "Action Plan integrity hash does not match.")
            sidecar = self.manifest.get("sidecars", {}).get("action_plan") if isinstance(self.manifest.get("sidecars"), dict) else {}
            ok = isinstance(sidecar, dict) and sidecar.get("payload_hash") == self.action_plan.get("integrity_hash")
            self._add_check("action_plan", "portfolio_governance_manifest_action_plan_hash", "passed" if ok else "failed", "blocking", "Manifest action plan hash matches action-plan.json." if ok else "Manifest action plan hash does not match action-plan.json.")
        if self.execution_report:
            actual = execution_report_integrity_hash(self.execution_report)
            self._add_check("execution_report", "portfolio_governance_execution_report_integrity", "passed" if self.execution_report.get("integrity_hash") == actual else "failed", "blocking", "Execution Report integrity hash matches." if self.execution_report.get("integrity_hash") == actual else "Execution Report integrity hash does not match.")
            sidecar = self.manifest.get("sidecars", {}).get("execution_report") if isinstance(self.manifest.get("sidecars"), dict) else {}
            ok = isinstance(sidecar, dict) and sidecar.get("payload_hash") == self.execution_report.get("integrity_hash")
            self._add_check("execution_report", "portfolio_governance_manifest_execution_report_hash", "passed" if ok else "failed", "blocking", "Manifest execution report hash matches execution-report.json." if ok else "Manifest execution report hash does not match execution-report.json.")
        if self.manual_actions:
            actual = manual_action_list_integrity_hash(self.manual_actions)
            self._add_check("manual_actions", "portfolio_governance_manual_action_list_integrity", "passed" if self.manual_actions.get("integrity_hash") == actual else "failed", "blocking", "Manual Action List integrity hash matches." if self.manual_actions.get("integrity_hash") == actual else "Manual Action List integrity hash does not match.")
            sidecar = self.manifest.get("sidecars", {}).get("manual_action_list") if isinstance(self.manifest.get("sidecars"), dict) else {}
            ok = isinstance(sidecar, dict) and sidecar.get("payload_hash") == self.manual_actions.get("integrity_hash")
            self._add_check("manual_actions", "portfolio_governance_manifest_manual_action_list_hash", "passed" if ok else "failed", "blocking", "Manifest manual action list hash matches manual-action-list.json." if ok else "Manifest manual action list hash does not match manual-action-list.json.")
        if self.queue and self.action_plan:
            ok = str(self.queue.get("action_plan_hash") or "") == str(self.action_plan.get("integrity_hash") or "")
            self._add_check("cross_reference", "portfolio_governance_queue_action_plan_link", "passed" if ok else "failed", "blocking", "Queue action_plan_hash links to action-plan.json." if ok else "Queue action_plan_hash does not link to action-plan.json.")
        if self.queue and self.execution_report:
            ok = str(self.queue.get("latest_execution_report_hash") or "") == str(self.execution_report.get("integrity_hash") or "")
            self._add_check("cross_reference", "portfolio_governance_queue_execution_link", "passed" if ok else "failed", "blocking", "Queue latest execution hash links to execution-report.json." if ok else "Queue latest execution hash does not link to execution-report.json.")

    def _verify_requirements(self) -> None:
        summary = self.execution_report.get("summary") if isinstance(self.execution_report.get("summary"), dict) else {}
        manual_required = int(summary.get("manual_required") or 0)
        blocked = int(summary.get("blocked") or 0)
        failed = int(summary.get("failed") or 0)
        manual_items = self.manual_actions.get("items") if isinstance(self.manual_actions.get("items"), list) else []
        plan_items = self.action_plan.get("items") if isinstance(self.action_plan.get("items"), list) else []
        required_manual_ids = {str(item.get("item_id")) for item in plan_items if isinstance(item, dict) and item.get("status") == "manual_required"}
        manual_list_ids = {str(item.get("item_id")) for item in manual_items if isinstance(item, dict)}
        if self.require_manual_actions:
            missing = sorted(required_manual_ids - manual_list_ids)
            ok = manual_required == 0 or not missing
            self._add_check("requirements", "portfolio_governance_require_manual_actions", "passed" if ok else "failed", "blocking", "Manual action list covers manual-required items." if ok else "Manual action list is missing items: " + ", ".join(missing[:5]))
        if self.require_no_blocked:
            ok = blocked == 0 and failed == 0
            self._add_check("requirements", "portfolio_governance_require_no_blocked", "passed" if ok else "failed", "blocking", "No blocked or failed governance items remain." if ok else f"Blocked={blocked}, failed={failed}.")

    def _verify_redaction(self, archive: zipfile.ZipFile) -> None:
        for name in self.entry_names:
            if not name.endswith((".json", ".jsonl", ".txt", ".csv", ".md")):
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
            elif name.endswith(".jsonl"):
                for line in text.splitlines():
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.redaction_findings.extend(_blocked_key_findings(name, value))
        self._add_check("redaction", "portfolio_governance_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", f"Found {len(self.redaction_findings)} sensitive redaction issue(s)." if self.redaction_findings else "No sensitive values found in scanned text entries.")

    def _read_json_entry(self, archive: zipfile.ZipFile, name: str, scope: str, check_id: str) -> dict[str, Any]:
        info = self.entry_map.get(name)
        if info is None:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} is missing.")
            return {}
        try:
            value = json.loads(archive.read(info).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._add_check(scope, check_id, "failed", "blocking", f"{name} cannot be parsed: {exc}")
            return {}
        self._add_check(scope, check_id, "passed", "blocking", f"{name} parses as JSON.")
        return value if isinstance(value, dict) else {}

    def _build_report(self) -> dict[str, Any]:
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        summary = self.execution_report.get("summary") if isinstance(self.execution_report.get("summary"), dict) else {}
        report = {
            "schema_version": PORTFOLIO_GOVERNANCE_VERIFICATION_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "status": "failed" if blockers else "warning" if warnings else "passed",
            "zip_path": self.zip_path.name,
            "zip_sha256": self.zip_sha256,
            "zip_size_bytes": self.zip_size_bytes,
            "manifest_hash": self.manifest.get("integrity_hash") if isinstance(self.manifest, dict) else None,
            "zip": {
                "filename": self.zip_path.name,
                "sha256": self.zip_sha256,
                "size_bytes": self.zip_size_bytes,
                "entry_count": len(self.entry_infos),
                "uncompressed_size_bytes": self.total_uncompressed_size,
            },
            "summary": {
                "queue_id": self.manifest.get("queue_id") or self.queue.get("queue_id"),
                "portfolio_id": self.manifest.get("portfolio_id") or self.queue.get("portfolio_id"),
                "queue_status": self.queue.get("status"),
                "execution_status": self.execution_report.get("status"),
                "total_items": summary.get("total_items", 0),
                "manual_required": summary.get("manual_required", 0),
                "blocked": summary.get("blocked", 0),
                "failed": summary.get("failed", 0),
                "checked_file_count": len(self.files),
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
            },
            "checks": self.checks,
            "files": self.files,
            "blockers": blockers,
            "warnings": warnings,
            "redaction_findings": self.redaction_findings[:50],
        }
        return sanitize_metadata(report, blocked_keys=VERIFIER_BLOCKED_KEYS)

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})


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


def _is_safe_zip_entry(name: str) -> bool:
    if "\\" in name or not name:
        return False
    if name.startswith("/") or name.startswith("//"):
        return False
    path = PurePosixPath(name)
    if path.is_absolute():
        return False
    parts = path.parts
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if ":" in parts[0]:
        return False
    return True


def _counts(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _raw_zip_entry_names(path: Path) -> list[str]:
    data = path.read_bytes()
    names: list[str] = []
    signature = b"PK\x01\x02"
    index = 0
    while True:
        index = data.find(signature, index)
        if index < 0 or index + 46 > len(data):
            break
        try:
            name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, index + 28)
        except struct.error:
            break
        name_start = index + 46
        name_end = name_start + name_len
        if name_end > len(data):
            break
        raw_name = data[name_start:name_end]
        try:
            names.append(raw_name.decode("utf-8"))
        except UnicodeDecodeError:
            names.append(raw_name.decode("cp437", errors="replace"))
        index = name_end + extra_len + comment_len
    return names


def _redaction_findings(path: str, text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "sensitive_value", "pattern": pattern.pattern})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"path": path, "kind": "local_path", "pattern": pattern.pattern})
    return findings


def _blocked_key_findings(path: str, value: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def walk(node: Any, dotted: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                key_text = str(key)
                child_path = f"{dotted}.{key_text}" if dotted else key_text
                if key_text.lower() in VERIFIER_BLOCKED_KEYS:
                    findings.append({"path": path, "kind": "blocked_key", "key": child_path})
                walk(child, child_path)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{dotted}[{index}]")

    walk(value, "")
    return findings
