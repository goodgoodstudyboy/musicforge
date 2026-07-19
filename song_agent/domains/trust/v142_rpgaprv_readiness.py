# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
from song_agent.platform.verification import (
    is_safe_zip_entry as _is_safe_zip_entry,
    raw_central_directory_entry_names as _raw_zip_entry_names,
)
import hashlib as hashlib
import json as json
import re as re
import struct as struct
import zipfile as zipfile
from datetime import datetime as datetime, timezone as timezone
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_review_contracts import PORTAL_REVIEW_BLOCKED_KEYS as PORTAL_REVIEW_BLOCKED_KEYS, PORTAL_REVIEW_PACK_PACKAGE_TYPE as PORTAL_REVIEW_PACK_PACKAGE_TYPE, PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE as PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE, response_integrity_hash as response_integrity_hash, response_payload_hash as response_payload_hash, response_summary as response_summary, review_manifest_hash as review_manifest_hash, review_pack_hash as review_pack_hash, review_pack_summary as review_pack_summary
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

VERIFIER_BLOCKED_KEYS = _make_deferred_global('VERIFIER_BLOCKED_KEYS')

def bind_globals(namespace: dict[str, object]) -> None:
    global VERIFIER_BLOCKED_KEYS
    VERIFIER_BLOCKED_KEYS = namespace.get('VERIFIER_BLOCKED_KEYS', VERIFIER_BLOCKED_KEYS)
    _bind_deferred_defaults(namespace)


PORTAL_REVIEW_VERIFICATION_SCHEMA_VERSION = 1
DEFAULT_MAX_ZIP_SIZE_MB = 64
DEFAULT_MAX_UNCOMPRESSED_SIZE_MB = 128
DEFAULT_MAX_ENTRY_COUNT = 200
PACK_REQUIRED_ENTRIES = {
    "review-pack-manifest.json",
    "review-pack.json",
    "reviewer-guide.md",
    "portal-review-form.json",
    "portal-review-form.md",
    "data/portal-summary.json",
    "data/registry-verification-summary.json",
    "data/attestation-verification-summary.json",
    "data/portal-verification-summary.json",
    "data/response-schema.json",
    "README.txt",
}
RESPONSE_REQUIRED_ENTRIES = {
    "response-manifest.json",
    "review-response.json",
    "review-response.md",
    "data/review-pack-source.json",
    "data/portal-binding-summary.json",
    "README.txt",
}
LEGAL_PACK_SIDECARS = {"review-pack-manifest.json"}
LEGAL_RESPONSE_SIDECARS = {"response-manifest.json"}




class _ResponseDocumentVerifier:
    def __init__(self, response: DomainDocument, pack: DomainDocument, *, now: str | None) -> None:
        self.response = sanitize_metadata(response, blocked_keys=VERIFIER_BLOCKED_KEYS)
        self.pack = sanitize_metadata(pack, blocked_keys=VERIFIER_BLOCKED_KEYS)
        self.generated_at = now or datetime.now(timezone.utc).isoformat()
        self.checks: list[DomainDocument] = []
        self.redaction_findings: list[DomainDocument] = []

    def run(self) -> DomainDocument:
        self._add_hash_check("response", "portal_review_response_payload_hash", self.response.get("payload_hash"), response_payload_hash(self.response), "Response payload hash")
        self._add_hash_check("response", "portal_review_response_integrity", self.response.get("integrity_hash"), response_integrity_hash(self.response), "Response integrity")
        self._add_exact_check("response", "portal_review_response_pack_source_current", self.response.get("review_pack_source_hash"), self.pack.get("source_hash"), "Response source hash")
        self._add_check("response", "portal_review_response_decision", "passed" if self.response.get("decision") in {"accepted", "needs_changes", "rejected"} else "failed", "blocking", "Decision is valid.")
        reviewer_ok = isinstance(self.response.get("reviewer"), dict) and bool(self.response.get("reviewer", {}).get("name"))
        self._add_check("response", "portal_review_response_reviewer", "passed" if reviewer_ok else "failed", "blocking", "Reviewer is present." if reviewer_ok else "reviewer.name is required.")
        if self.response.get("decision") == "accepted":
            high = _unresolved_high_findings(self.response)
            self._add_check("response", "portal_review_response_accepted_no_unresolved_high_findings", "failed" if high else "passed", "blocking", f"Accepted response has unresolved high findings: {len(high)}" if high else "Accepted response has no unresolved high or critical findings.")
        text = json.dumps({"response": self.response}, ensure_ascii=False, sort_keys=True, default=str)
        self.redaction_findings.extend(_redaction_findings("review-response.json", text))
        self.redaction_findings.extend(_blocked_key_findings("review-response.json", self.response))
        self._add_check("redaction", "portal_review_response_redaction_scan", "failed" if self.redaction_findings else "passed", "blocking", "Sensitive values found." if self.redaction_findings else "No sensitive values found.")
        blockers = [item for item in self.checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
        warnings = [item for item in self.checks if item.get("status") in {"warning", "failed"} and item.get("severity") == "warning"]
        return sanitize_metadata(
            {
                "schema_version": PORTAL_REVIEW_VERIFICATION_SCHEMA_VERSION,
                "generated_at": self.generated_at,
                "status": "failed" if blockers else "warning" if warnings else "passed",
                "package_kind": "response_document",
                "summary": response_summary(self.response),
                "checks": self.checks,
                "blockers": blockers,
                "warnings": warnings,
                "redaction_findings": self.redaction_findings[:50],
            },
            blocked_keys=VERIFIER_BLOCKED_KEYS,
        )

    def _add_hash_check(self, scope: str, check_id: str, expected: object, actual: object, label: str) -> None:
        ok = bool(expected) and str(expected) == str(actual)
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_exact_check(self, scope: str, check_id: str, expected: object, actual: object, label: str) -> None:
        ok = expected == actual
        self._add_check(scope, check_id, "passed" if ok else "failed", "blocking", f"{label} matches." if ok else f"{label} does not match.")

    def _add_check(self, scope: str, check_id: str, status: str, severity: str, message: str) -> None:
        self.checks.append({"scope": scope, "check_id": check_id, "status": status, "severity": severity, "message": message})

def _print_report(title: str, report: DomainDocument) -> None:
    print(title)
    print(f"status: {report.get('status')}")
    summary = _as_document(report.get("summary"))
    if summary.get("portfolio_id"):
        print(f"portfolio: {summary.get('portfolio_id')}")
    if summary.get("review_pack_id"):
        print(f"review pack: {summary.get('review_pack_id')}")
    if summary.get("response_id"):
        print(f"response: {summary.get('response_id')}")
    print(f"blockers: {len(_as_list(report.get('blockers')))}")
    print(f"warnings: {len(_as_list(report.get('warnings')))}")

def _is_forbidden_entry(name: str) -> bool:
    lowered = str(name or "").lower()
    return lowered.endswith(".zip") or lowered.startswith("nested/") or ".musicforge/" in lowered or lowered.startswith(".musicforge/")

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

def _redaction_findings(name: str, text: str) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": replacement, "excerpt": match.group(0)[:120]})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"entry": name, "pattern": "local_path", "excerpt": match.group(0)[:120]})
    return findings

def _blocked_key_findings(name: str, value: object, path: str = "") -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in VERIFIER_BLOCKED_KEYS:
                findings.append({"entry": name, "pattern": "blocked_key", "excerpt": key_path[:120]})
            findings.extend(_blocked_key_findings(name, item, key_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_blocked_key_findings(name, item, f"{path}[{index}]"))
    return findings

def _unresolved_high_findings(response: DomainDocument) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for finding in response.get("findings", []) if isinstance(response.get("findings"), list) else []:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").lower()
        status = str(finding.get("status") or "open").lower()
        if severity in {"high", "critical"} and status not in {"resolved", "accepted_risk"}:
            rows.append(finding)
    return rows
