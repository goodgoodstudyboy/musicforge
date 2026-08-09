from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_int

import io as io
import json as json
import re as re
import tempfile as tempfile
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.contracts.packages import PackageSpec as PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope as verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report as build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check as archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program_handoff_verifier import UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_accepted_evidence_package as verify_unified_release_program_accepted_evidence_package, verify_unified_release_program_handoff_package as verify_unified_release_program_handoff_package
from song_agent.domains.program.unified_release_program_operations_verifier import UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_operations_package as verify_unified_release_program_operations_package
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_package as verify_unified_release_program_package


UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE = "musicforge_unified_release_program_evidence_vault"
UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_evidence_vault_verification"
UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE = "musicforge_unified_release_program_evidence_vault_anchor"
UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION = 1

STATIC_REQUIRED_ENTRIES = {
    "manifest.json",
    "vault-report.json",
    "source-summary.json",
    "package-index.json",
    "verification-index.json",
    "proof-index.json",
    "chain-of-custody.json",
    "replay-plan.json",
    "auditor-guide.md",
    "public-summary.json",
    "README.txt",
    "packages/unified-release-program.zip",
    "packages/unified-release-program-operations.zip",
    "packages/unified-release-program-handoff.zip",
    "proofs/program-verification-report.json",
    "proofs/program-signoff-binding-summary.json",
    "proofs/program-external-evidence-manifest.json",
    "proofs/operations-verification-report.json",
    "proofs/handoff-verification-report.json",
    "proofs/handoff-signoff-binding-summary.json",
    "proofs/handoff-external-evidence-manifest.json",
}

def verify_unified_release_program_vault_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_anchor: bool = False,
    vault_anchor_path: Path | str | None = None,
    require_current_program: bool = False,
    require_current_operations: bool = False,
    require_current_handoff: bool = False,
    require_accepted_evidence: bool = True,
    max_zip_size_mb: int = 512,
    max_uncompressed_size_mb: int = 2048,
    max_entry_count: int = 5000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpv_kernel",
                required_entries=frozenset(STATIC_REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                allowed_entry_patterns=(
                    r"packages/accepted-evidence/[A-Za-z0-9_.-]+\.zip",
                    r"proofs/accepted-evidence/[A-Za-z0-9_.-]+-(?:verification-report|response-verification-report|response-binding-summary)\.json",
                ),
                nested_zip_policy="allowlisted",
                allowed_nested_entries=frozenset({
                    "packages/unified-release-program.zip",
                    "packages/unified-release-program-operations.zip",
                    "packages/unified-release-program-handoff.zip",
                }),
                allowed_nested_patterns=(r"packages/accepted-evidence/[A-Za-z0-9_.-]+\.zip",),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("urpv_zip_exists", False, "Vault ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpv_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            checks.extend(
                [
                    _check("urpv_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpv_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpv_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpv_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                ]
            )
            if not STATIC_REQUIRED_ENTRIES <= name_set:
                checks.append(_check("urpv_required_entries", False, "Vault ZIP contains required entries.", {"missing": sorted(STATIC_REQUIRED_ENTRIES - name_set)}))
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "vault-report.json")
            source = _read_json_entry(archive, "source-summary.json")
            package_index = _read_json_entry(archive, "package-index.json")
            verification_index = _read_json_entry(archive, "verification-index.json")
            proof_index = _read_json_entry(archive, "proof-index.json")
            chain = _read_json_entry(archive, "chain-of-custody.json")
            public_summary = _read_json_entry(archive, "public-summary.json")
            replay_plan = _read_json_entry(archive, "replay-plan.json")
            expected_entries = _expected_entries(package_index, verification_index, proof_index)
            extra = sorted(name_set - expected_entries)
            missing = sorted(expected_entries - name_set)
            summary.update(
                {
                    "program_id": report.get("program_id") or manifest.get("program_id"),
                    "vault_id": report.get("vault_id") or manifest.get("vault_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "status": report.get("status"),
                    "package_count": len(package_index.get("packages") or []),
                    "verification_count": len(verification_index.get("verifications") or []),
                }
            )
            checks.extend(
                [
                    _check("urpv_allowed_entries", not extra, "Vault ZIP contains only fixed or indexed entries.", {"extra": extra}),
                    _check("urpv_indexed_required_entries", not missing, "Vault ZIP contains all indexed entries.", {"missing": missing}),
                    _check("urpv_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_VAULT_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpv_manifest_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION, "Manifest schema version is supported."),
                ]
            )
            checks.extend(_manifest_checks(archive, manifest, name_set, expected_entries))
            for check_id, doc in (
                ("urpv_manifest_integrity", manifest),
                ("urpv_report_integrity", report),
                ("urpv_source_integrity", source),
                ("urpv_package_index_integrity", package_index),
                ("urpv_verification_index_integrity", verification_index),
                ("urpv_proof_index_integrity", proof_index),
                ("urpv_chain_integrity", chain),
                ("urpv_public_summary_integrity", public_summary),
                ("urpv_replay_plan_integrity", replay_plan),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, report, source, package_index, verification_index, proof_index, chain, public_summary, replay_plan))
            checks.extend(_package_index_checks(archive, package_index))
            checks.extend(_verification_index_checks(archive, verification_index))
            checks.extend(_proof_index_checks(archive, proof_index))
            checks.extend(_anchor_checks(vault_anchor_path, zip_path, manifest, report, source, package_index, verification_index, proof_index, chain, require=require_anchor))
            if deep:
                if _has_blocking_failures(checks):
                    checks.append(_check("urpv_deep_preflight", False, "Deep verification is skipped when ZIP structure, manifest, anchor, or index checks fail."))
                else:
                    checks.extend(
                        _deep_checks(
                            archive,
                            package_index,
                            verification_index,
                            proof_index,
                            require_current_program=require_current_program,
                            require_current_operations=require_current_operations,
                            require_current_handoff=require_current_handoff,
                            require_accepted_evidence=require_accepted_evidence,
                        )
                    )
            elif strict:
                checks.append(_check("urpv_deep_verification_requested", True, "Deep verification was not requested.", severity="warning"))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpv_zip_readable", False, "Vault ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_vault_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_vault_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _expected_entries(package_index: ImplementationDocument, verification_index: ImplementationDocument, proof_index: ImplementationDocument) -> set[str]:
    entries = set(STATIC_REQUIRED_ENTRIES)
    for row in package_index.get("packages", []) or []:
        if isinstance(row, dict) and _expected_package_path(row):
            entries.add(str(_expected_package_path(row)))
    for row in verification_index.get("verifications", []) or []:
        if isinstance(row, dict) and _expected_verification_path(row):
            entries.add(str(_expected_verification_path(row)))
    for row in proof_index.get("proofs", []) or []:
        if isinstance(row, dict) and _expected_proof_path(row):
            entries.add(str(_expected_proof_path(row)))
    return entries


def _expected_package_path(row: ImplementationDocument) -> str | None:
    component_type = str(row.get("component_type") or "")
    component_id = str(row.get("component_id") or row.get("evidence_id") or "")
    fixed = {
        "program": "packages/unified-release-program.zip",
        "operations": "packages/unified-release-program-operations.zip",
        "handoff": "packages/unified-release-program-handoff.zip",
    }
    if component_type in fixed:
        return fixed[component_type]
    if component_type == "accepted_evidence" and component_id and _safe_identifier(component_id):
        return f"packages/accepted-evidence/{component_id}.zip"
    return None


def _expected_verification_path(row: ImplementationDocument) -> str | None:
    component_type = str(row.get("component_type") or "")
    component_id = str(row.get("component_id") or row.get("evidence_id") or "")
    fixed = {
        "program": "proofs/program-verification-report.json",
        "operations": "proofs/operations-verification-report.json",
        "handoff": "proofs/handoff-verification-report.json",
    }
    if component_type in fixed:
        return fixed[component_type]
    if component_type == "accepted_evidence" and component_id and _safe_identifier(component_id):
        return f"proofs/accepted-evidence/{component_id}-verification-report.json"
    return None


def _expected_proof_path(row: ImplementationDocument) -> str | None:
    component_type = str(row.get("component_type") or "")
    component_id = str(row.get("component_id") or row.get("evidence_id") or "")
    proof_type = str(row.get("proof_type") or "")
    fixed = {
        ("program", "signoff_binding"): "proofs/program-signoff-binding-summary.json",
        ("program", "external_evidence_manifest"): "proofs/program-external-evidence-manifest.json",
        ("handoff", "signoff_binding"): "proofs/handoff-signoff-binding-summary.json",
        ("handoff", "external_evidence_manifest"): "proofs/handoff-external-evidence-manifest.json",
    }
    if (component_type, proof_type) in fixed:
        return fixed[(component_type, proof_type)]
    if component_type == "accepted_evidence" and component_id and _safe_identifier(component_id):
        if proof_type == "response_verification":
            return f"proofs/accepted-evidence/{component_id}-response-verification-report.json"
        if proof_type == "response_binding":
            return f"proofs/accepted-evidence/{component_id}-response-binding-summary.json"
    return None


def _expected_nested_package_type(component_type: str) -> str | None:
    return {
        "program": UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE,
        "operations": UNIFIED_RELEASE_PROGRAM_OPERATIONS_PACKAGE_TYPE,
        "handoff": UNIFIED_RELEASE_PROGRAM_HANDOFF_PACKAGE_TYPE,
        "accepted_evidence": UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_PACKAGE_TYPE,
    }.get(component_type)


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, name_set: set[str], expected_entries: set[str]) -> list[ImplementationDocument]:
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    file_paths = {str(row.get("path")) for row in files}
    expected_files = expected_entries - {"manifest.json"}
    checks = [
        _check("urpv_manifest_files_exact", file_paths == expected_files, "Manifest files match Vault fixed/indexed layout.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check("urpv_manifest_no_zip_entry_spoof", set(manifest.get("zip", {}).get("entries") or []) <= name_set, "Manifest ZIP entries do not spoof extra paths."),
    ]
    for row in files:
        rel = str(row.get("path") or "")
        if rel not in name_set:
            checks.append(_check(f"urpv_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP.", {"path": rel}))
            continue
        data = archive.read(rel)
        checks.append(_check(f"urpv_manifest_file_{_safe_check_key(rel)}_hash", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry.", {"path": rel}))
    return checks


def _document_binding_checks(
    manifest: ImplementationDocument,
    report: ImplementationDocument,
    source: ImplementationDocument,
    package_index: ImplementationDocument,
    verification_index: ImplementationDocument,
    proof_index: ImplementationDocument,
    chain: ImplementationDocument,
    public_summary: ImplementationDocument,
    replay_plan: ImplementationDocument,
) -> list[ImplementationDocument]:
    source_doc = _as_document(manifest.get("source"))
    source_hash = source.get("source_hash")
    return [
        _check("urpv_source_hash_binding", manifest.get("source_hash") == report.get("source_hash") == source_hash, "Manifest, report, and source use one source hash."),
        _check("urpv_manifest_report_hash", source_doc.get("vault_report_hash") == report.get("integrity_hash"), "Manifest binds vault report."),
        _check("urpv_manifest_source_hash", source_doc.get("source_summary_hash") == source.get("integrity_hash"), "Manifest binds source summary."),
        _check("urpv_manifest_package_index_hash", source_doc.get("package_index_hash") == package_index.get("integrity_hash"), "Manifest binds package index."),
        _check("urpv_manifest_verification_index_hash", source_doc.get("verification_index_hash") == verification_index.get("integrity_hash"), "Manifest binds verification index."),
        _check("urpv_manifest_proof_index_hash", source_doc.get("proof_index_hash") == proof_index.get("integrity_hash"), "Manifest binds proof index."),
        _check("urpv_manifest_chain_hash", source_doc.get("chain_of_custody_hash") == chain.get("integrity_hash"), "Manifest binds chain of custody."),
        _check("urpv_manifest_public_summary_hash", source_doc.get("public_summary_hash") == public_summary.get("integrity_hash"), "Manifest binds public summary."),
        _check("urpv_manifest_replay_plan_hash", source_doc.get("replay_plan_hash") == replay_plan.get("integrity_hash"), "Manifest binds replay plan."),
        _check("urpv_index_source_hash", package_index.get("source_hash") == verification_index.get("source_hash") == proof_index.get("source_hash") == chain.get("source_hash") == source_hash, "Indexes and chain bind the same source hash."),
    ]


def _package_index_checks(archive: zipfile.ZipFile, package_index: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    seen_required: set[str] = set()
    for row in package_index.get("packages", []) or []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if not rel:
            continue
        prefix = f"urpv_package_{_safe_check_key(rel)}"
        component_type = str(row.get("component_type") or "")
        expected_path = _expected_package_path(row)
        expected_package_type = _expected_nested_package_type(component_type)
        if component_type in {"program", "operations", "handoff"}:
            seen_required.add(component_type)
        checks.extend(
            [
                _check(f"{prefix}_allowed_component", expected_path is not None, "Nested package component is allowed.", {"component_type": component_type}),
                _check(f"{prefix}_fixed_path", bool(expected_path) and rel == expected_path, "Nested package path matches fixed Vault layout.", {"expected_path": expected_path, "actual_path": rel}),
                _check(f"{prefix}_under_packages", rel.startswith("packages/") and rel.lower().endswith(".zip"), "Nested package is a ZIP under packages/."),
            ]
        )
        if rel not in archive.namelist():
            checks.append(_check(f"{prefix}_exists", False, "Indexed package exists in Vault ZIP."))
            continue
        data = archive.read(rel)
        nested_package_type = _nested_manifest_package_type(data)
        checks.extend(
            [
                _check(f"{prefix}_sha256", row.get("zip_sha256") == _sha256_bytes(data), "Indexed package hash matches ZIP entry."),
                _check(f"{prefix}_size", int(row.get("zip_size_bytes") or -1) == len(data), "Indexed package size matches ZIP entry."),
                _check(f"{prefix}_package_type", bool(expected_package_type) and nested_package_type == expected_package_type, "Nested package manifest package type is valid.", {"expected_package_type": expected_package_type, "actual_package_type": nested_package_type}),
            ]
        )
    checks.append(_check("urpv_package_index_required_components", {"program", "operations", "handoff"} <= seen_required, "Package index contains required fixed Program, Operations, and Handoff packages.", {"missing": sorted({"program", "operations", "handoff"} - seen_required)}))
    return checks


def _verification_index_checks(archive: zipfile.ZipFile, verification_index: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    for row in verification_index.get("verifications", []) or []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        prefix = f"urpv_verification_{_safe_check_key(rel)}"
        if not rel:
            continue
        expected_path = _expected_verification_path(row)
        checks.extend(
            [
                _check(f"{prefix}_allowed_component", expected_path is not None, "Verification component is allowed.", {"component_type": row.get("component_type")}),
                _check(f"{prefix}_fixed_path", bool(expected_path) and rel == expected_path, "Verification path matches fixed Vault layout.", {"expected_path": expected_path, "actual_path": rel}),
                _check(f"{prefix}_under_proofs", rel.startswith("proofs/") and rel.lower().endswith(".json"), "Verification report is under proofs/."),
            ]
        )
        if rel not in archive.namelist():
            checks.append(_check(f"{prefix}_exists", False, "Indexed verification exists in Vault ZIP."))
            continue
        doc = _read_json_entry(archive, rel)
        checks.extend(
            [
                _check(f"{prefix}_integrity", _integrity_ok(doc), "Indexed verification integrity is valid."),
                _check(f"{prefix}_hash", row.get("verification_report_hash") == doc.get("integrity_hash"), "Indexed verification hash matches report."),
                _check(f"{prefix}_status", row.get("status") == doc.get("status"), "Indexed verification status matches report."),
                _check(f"{prefix}_package_type", not row.get("package_type") or row.get("package_type") == doc.get("package_type"), "Indexed verification package type matches report."),
            ]
        )
    return checks


def _proof_index_checks(archive: zipfile.ZipFile, proof_index: ImplementationDocument) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    for row in proof_index.get("proofs", []) or []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        prefix = f"urpv_proof_{_safe_check_key(rel)}"
        if not rel:
            continue
        expected_path = _expected_proof_path(row)
        checks.extend(
            [
                _check(f"{prefix}_allowed_component", expected_path is not None, "Proof component is allowed.", {"component_type": row.get("component_type"), "proof_type": row.get("proof_type")}),
                _check(f"{prefix}_fixed_path", bool(expected_path) and rel == expected_path, "Proof path matches fixed Vault layout.", {"expected_path": expected_path, "actual_path": rel}),
                _check(f"{prefix}_under_proofs", rel.startswith("proofs/") and rel.lower().endswith((".json", ".jsonl")), "Proof is under proofs/."),
            ]
        )
        if rel not in archive.namelist():
            checks.append(_check(f"{prefix}_exists", False, "Indexed proof exists in Vault ZIP."))
            continue
        data = archive.read(rel)
        checks.extend(
            [
                _check(f"{prefix}_sha256", row.get("sha256") == _sha256_bytes(data), "Indexed proof hash matches ZIP entry."),
                _check(f"{prefix}_size", int(row.get("size_bytes") or -1) == len(data), "Indexed proof size matches ZIP entry."),
            ]
        )
        if rel.lower().endswith(".json"):
            doc = json.loads(data.decode("utf-8"))
            if row.get("integrity_hash"):
                checks.append(_check(f"{prefix}_integrity_hash", row.get("integrity_hash") == doc.get("integrity_hash"), "Indexed proof integrity hash matches document."))
    return checks


def _anchor_checks(
    path: Path | str | None,
    zip_path: Path,
    manifest: ImplementationDocument,
    report: ImplementationDocument,
    source: ImplementationDocument,
    package_index: ImplementationDocument,
    verification_index: ImplementationDocument,
    proof_index: ImplementationDocument,
    chain: ImplementationDocument,
    *,
    require: bool,
) -> list[ImplementationDocument]:
    if not path:
        return [_check("urpv_anchor_required", not require, "External Vault anchor is present when required.")]
    anchor_path = Path(path)
    checks = [_check("urpv_anchor_exists", anchor_path.exists() and anchor_path.is_file(), "External Vault anchor exists.")]
    if not anchor_path.exists() or not anchor_path.is_file():
        return checks
    anchor = read_json(anchor_path)
    checks.extend(
        [
            _check("urpv_anchor_package_type", anchor.get("package_type") == UNIFIED_RELEASE_PROGRAM_VAULT_ANCHOR_PACKAGE_TYPE, "Vault anchor package type is valid."),
            _check("urpv_anchor_integrity", _integrity_ok(anchor), "Vault anchor integrity hash is valid."),
            _check("urpv_anchor_zip_sha256", anchor.get("vault_zip_sha256") == _sha256_path(zip_path), "Vault anchor binds current ZIP hash."),
            _check("urpv_anchor_zip_size", _as_int(anchor.get("vault_zip_size_bytes") or -1) == zip_path.stat().st_size, "Vault anchor binds current ZIP size."),
            _check("urpv_anchor_manifest_hash", anchor.get("vault_manifest_hash") == manifest.get("integrity_hash"), "Vault anchor binds manifest hash."),
            _check("urpv_anchor_source_hash", anchor.get("vault_source_hash") == source.get("source_hash") == report.get("source_hash"), "Vault anchor binds source hash."),
            _check("urpv_anchor_report_hash", anchor.get("vault_report_hash") == report.get("integrity_hash"), "Vault anchor binds report hash."),
            _check("urpv_anchor_package_index_hash", anchor.get("package_index_hash") == package_index.get("integrity_hash"), "Vault anchor binds package index."),
            _check("urpv_anchor_verification_index_hash", anchor.get("verification_index_hash") == verification_index.get("integrity_hash"), "Vault anchor binds verification index."),
            _check("urpv_anchor_proof_index_hash", anchor.get("proof_index_hash") == proof_index.get("integrity_hash"), "Vault anchor binds proof index."),
            _check("urpv_anchor_chain_hash", anchor.get("chain_of_custody_hash") == chain.get("integrity_hash"), "Vault anchor binds chain of custody."),
        ]
    )
    return checks


def _deep_checks(
    archive: zipfile.ZipFile,
    package_index: ImplementationDocument,
    verification_index: ImplementationDocument,
    proof_index: ImplementationDocument,
    *,
    require_current_program: bool,
    require_current_operations: bool,
    require_current_handoff: bool,
    require_accepted_evidence: bool,
) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mf-urpv-deep-") as temp:
        root = Path(temp)
        root_resolved = root.resolve()
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            dest = (root / name).resolve()
            if dest != root_resolved and root_resolved not in dest.parents:
                checks.append(_check("urpv_deep_extract_containment", False, "Deep extraction target stays inside temp root.", {"entry": name}))
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(name))
        packages = {row.get("component_type"): row for row in package_index.get("packages", []) if isinstance(row, dict)}
        verifications = {row.get("component_type"): row for row in verification_index.get("verifications", []) if isinstance(row, dict)}
        proofs = {(row.get("component_type"), row.get("proof_type")): row for row in proof_index.get("proofs", []) if isinstance(row, dict)}
        checks.extend(
            _deep_program_checks(
                root,
                packages.get("program"),
                verifications.get("program"),
                proofs,
                require_current=require_current_program,
            )
        )
        checks.extend(
            _deep_operations_checks(
                root,
                packages.get("operations"),
                verifications.get("operations"),
                proofs,
                require_current=require_current_operations,
            )
        )
        checks.extend(
            _deep_handoff_checks(
                root,
                packages.get("handoff"),
                verifications.get("handoff"),
                proofs,
                require_current=require_current_handoff,
            )
        )
        accepted_rows = [row for row in package_index.get("packages", []) if isinstance(row, dict) and row.get("component_type") == "accepted_evidence"]
        if require_accepted_evidence and not accepted_rows:
            checks.append(_check("urpv_deep_accepted_evidence_required", False, "Accepted evidence packages are present."))
        for row in accepted_rows:
            checks.extend(_deep_accepted_evidence_checks(root, row, verification_index, proof_index, require=require_accepted_evidence))
    return checks


def _deep_program_checks(root: Path, package_row: ImplementationDocument | None, verification_row: ImplementationDocument | None, proofs: dict[tuple[Any, Any], ImplementationDocument], *, require_current: bool) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    if not package_row or not verification_row:
        return [_check("urpv_deep_program_required", False, "Program package and verification are indexed.")]
    zip_path = root / str(package_row.get("path"))
    report_path = root / str(verification_row.get("path"))
    binding_path = _proof_path(root, proofs, "program", "signoff_binding")
    manifest_path = _proof_path(root, proofs, "program", "external_evidence_manifest")
    runtime = verify_unified_release_program_package(
        zip_path,
        strict=True,
        require_current=require_current,
        require_signed=True,
        external_evidence_manifest_path=manifest_path if require_current else None,
        program_signoff_binding_path=binding_path,
    )
    external = read_json(report_path)
    checks.extend(_runtime_report_checks("urpv_deep_program", runtime, external, zip_path, UNIFIED_RELEASE_PROGRAM_VERIFICATION_PACKAGE_TYPE))
    return checks


def _deep_operations_checks(root: Path, package_row: ImplementationDocument | None, verification_row: ImplementationDocument | None, proofs: dict[tuple[Any, Any], ImplementationDocument], *, require_current: bool) -> list[ImplementationDocument]:
    if not package_row or not verification_row:
        return [_check("urpv_deep_operations_required", False, "Operations package and verification are indexed.")]
    zip_path = root / str(package_row.get("path"))
    report_path = root / str(verification_row.get("path"))
    runtime = verify_unified_release_program_operations_package(
        zip_path,
        strict=True,
        require_current=require_current,
        require_signed_program=require_current,
        require_continuous_review_clear=True,
        require_lifecycle_audit=True,
        program_zip_path=root / "packages/unified-release-program.zip",
        program_verification_report_path=root / "proofs/program-verification-report.json",
        program_signoff_binding_path=root / "proofs/program-signoff-binding-summary.json",
        external_evidence_manifest_path=root / "proofs/program-external-evidence-manifest.json" if require_current else None,
    )
    external = read_json(report_path)
    return _runtime_report_checks("urpv_deep_operations", runtime, external, zip_path, UNIFIED_RELEASE_PROGRAM_OPERATIONS_VERIFICATION_PACKAGE_TYPE)


def _deep_handoff_checks(root: Path, package_row: ImplementationDocument | None, verification_row: ImplementationDocument | None, proofs: dict[tuple[Any, Any], ImplementationDocument], *, require_current: bool) -> list[ImplementationDocument]:
    if not package_row or not verification_row:
        return [_check("urpv_deep_handoff_required", False, "Handoff package and verification are indexed.")]
    zip_path = root / str(package_row.get("path"))
    report_path = root / str(verification_row.get("path"))
    runtime = verify_unified_release_program_handoff_package(
        zip_path,
        strict=True,
        require_current=require_current,
        require_accepted=False,
        require_signed=True,
        external_evidence_manifest_path=root / "proofs/handoff-external-evidence-manifest.json" if require_current else None,
        handoff_signoff_binding_path=root / "proofs/handoff-signoff-binding-summary.json",
    )
    external = read_json(report_path)
    return _runtime_report_checks("urpv_deep_handoff", runtime, external, zip_path, UNIFIED_RELEASE_PROGRAM_HANDOFF_VERIFICATION_PACKAGE_TYPE)


def _deep_accepted_evidence_checks(root: Path, package_row: ImplementationDocument, verification_index: ImplementationDocument, proof_index: ImplementationDocument, *, require: bool) -> list[ImplementationDocument]:
    evidence_id = str(package_row.get("component_id") or package_row.get("evidence_id") or "")
    verification_row = next((row for row in verification_index.get("verifications", []) if row.get("component_type") == "accepted_evidence" and str(row.get("component_id") or row.get("evidence_id") or "") == evidence_id), None)
    response_report = next((row for row in proof_index.get("proofs", []) if row.get("component_type") == "accepted_evidence" and str(row.get("component_id") or row.get("evidence_id") or "") == evidence_id and row.get("proof_type") == "response_verification"), None)
    response_binding = next((row for row in proof_index.get("proofs", []) if row.get("component_type") == "accepted_evidence" and str(row.get("component_id") or row.get("evidence_id") or "") == evidence_id and row.get("proof_type") == "response_binding"), None)
    if not verification_row:
        return [_check(f"urpv_deep_accepted_{_safe_check_key(evidence_id)}_verification_required", False, "Accepted evidence verification is indexed.")]
    runtime = verify_unified_release_program_accepted_evidence_package(
        root / str(package_row.get("path")),
        strict=True,
        require_accepted=require,
        response_verification_report_path=root / str(response_report.get("path")) if response_report else None,
        response_binding_summary_path=root / str(response_binding.get("path")) if response_binding else None,
    )
    external = read_json(root / str(verification_row.get("path")))
    return _runtime_report_checks(f"urpv_deep_accepted_{_safe_check_key(evidence_id)}", runtime, external, root / str(package_row.get("path")), UNIFIED_RELEASE_PROGRAM_ACCEPTED_EVIDENCE_VERIFICATION_PACKAGE_TYPE)


def _runtime_report_checks(prefix: str, runtime: ImplementationDocument, external: ImplementationDocument, zip_path: Path, package_type: str) -> list[ImplementationDocument]:
    return [
        _check(f"{prefix}_runtime_passed", runtime.get("status") == "passed", "Runtime verifier passed.", {"blockers": runtime.get("blockers", [])}),
        _check(f"{prefix}_external_passed", external.get("status") == "passed", "External verification report passed.", {"blockers": external.get("blockers", [])}),
        _check(f"{prefix}_external_integrity", _integrity_ok(external), "External verification integrity is valid."),
        _check(f"{prefix}_external_package_type", external.get("package_type") == package_type, "External verification package type is valid."),
        _check(f"{prefix}_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Runtime and external ZIP hash match."),
        _check(f"{prefix}_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Runtime and external manifest hash match."),
    ]


def _proof_path(root: Path, proofs: dict[tuple[Any, Any], ImplementationDocument], component_type: str, proof_type: str) -> Path | None:
    row = proofs.get((component_type, proof_type))
    if not row:
        return None
    return root / str(row.get("path"))


def _nested_manifest_package_type(data: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as nested:
            manifest = json.loads(nested.read("manifest.json").decode("utf-8"))
        return str(manifest.get("package_type") or "")
    except Exception:
        return None


def _has_blocking_failures(checks: list[ImplementationDocument]) -> bool:
    return any(check.get("status") == "failed" and check.get("severity") == "blocking" for check in checks)


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, first_check: ImplementationDocument | None = None) -> ImplementationDocument:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _safe_identifier(value: str) -> bool:
    return bool(value) and re.fullmatch(r"[A-Za-z0-9_.-]+", value) is not None and "/" not in value and "\\" not in value and ".." not in value.split(".")


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    return archive_redaction_check(archive, names, check_id="urpv_redaction_scan")


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"
