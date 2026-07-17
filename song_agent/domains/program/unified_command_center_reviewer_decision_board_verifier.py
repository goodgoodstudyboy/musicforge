from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center_evidence_review_verifier import UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_VERIFICATION_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_evidence_review_acceptance_package as verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package as verify_unified_command_center_evidence_review_package


UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE = "musicforge_unified_command_center_reviewer_decision_board"
UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_command_center_reviewer_decision_board_verification"
UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "board-source.json",
    "reviewer-roster.json",
    "response-index.json",
    "accepted-evidence-index.json",
    "finding-ledger.json",
    "conflict-report.json",
    "quorum-report.json",
    "decision-matrix.json",
    "decision-report.json",
    "manual-checklist.json",
    "decision-signoff.json",
    "signoff-binding-summary.json",
    "board-history.jsonl",
    "reviewer-guide.md",
    "README.txt",
}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_unified_command_center_reviewer_decision_board_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_quorum: bool = False,
    evidence_review_path: Path | str | None = None,
    evidence_review_verification_report_path: Path | str | None = None,
    accepted_evidence_paths: list[Path | str | None] | tuple[Path | str | None, ...] | None = None,
    accepted_evidence_verification_report_paths: list[Path | str | None] | tuple[Path | str | None, ...] | None = None,
    accepted_evidence_response_verification_report_paths: list[Path | str | None] | tuple[Path | str | None, ...] | None = None,
    max_zip_size_mb: int = 32,
    max_uncompressed_size_mb: int = 128,
    max_entry_count: int = 100,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_decision_board_zip_exists", False, "Reviewer Decision Board ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_decision_board_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_decision_board_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_decision_board_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_decision_board_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("ucc_decision_board_raw_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            nested = [name for name in names if name.lower().endswith(".zip")]
            checks.append(_check("ucc_decision_board_no_nested_zip", not nested, "Decision Board archive does not contain nested ZIP files.", {"nested": nested}))
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.append(_check("ucc_decision_board_allowed_entries", not extra, "Decision Board archive contains only fixed entries.", {"extra": extra}))
            checks.append(_check("ucc_decision_board_required_entries", not missing, "Decision Board archive contains all required entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            source = _read_json_entry(archive, "board-source.json")
            roster = _read_json_entry(archive, "reviewer-roster.json")
            response_index = _read_json_entry(archive, "response-index.json")
            accepted_index = _read_json_entry(archive, "accepted-evidence-index.json")
            finding_ledger = _read_json_entry(archive, "finding-ledger.json")
            conflict_report = _read_json_entry(archive, "conflict-report.json")
            quorum_report = _read_json_entry(archive, "quorum-report.json")
            decision_matrix = _read_json_entry(archive, "decision-matrix.json")
            decision_report = _read_json_entry(archive, "decision-report.json")
            checklist = _read_json_entry(archive, "manual-checklist.json")
            signoff = _read_json_entry(archive, "decision-signoff.json")
            signoff_binding = _read_json_entry(archive, "signoff-binding-summary.json")
            history_lines = archive.read("board-history.jsonl").decode("utf-8").splitlines()
            summary.update({"center_id": manifest.get("center_id"), "board_id": manifest.get("board_id"), "manifest_hash": manifest.get("integrity_hash"), "decision_status": decision_report.get("status")})

            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.append(_check("ucc_decision_board_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_decision_board_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            for check_id, doc in (
                ("ucc_decision_board_source_integrity", source),
                ("ucc_decision_board_roster_integrity", roster),
                ("ucc_decision_board_response_index_integrity", response_index),
                ("ucc_decision_board_accepted_evidence_index_integrity", accepted_index),
                ("ucc_decision_board_finding_ledger_integrity", finding_ledger),
                ("ucc_decision_board_conflict_report_integrity", conflict_report),
                ("ucc_decision_board_quorum_report_integrity", quorum_report),
                ("ucc_decision_board_decision_matrix_integrity", decision_matrix),
                ("ucc_decision_board_decision_report_integrity", decision_report),
                ("ucc_decision_board_manual_checklist_integrity", checklist),
                ("ucc_decision_board_signoff_integrity", signoff),
                ("ucc_decision_board_signoff_binding_integrity", signoff_binding),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, source, roster, response_index, accepted_index, finding_ledger, conflict_report, quorum_report, decision_matrix, decision_report, checklist, signoff, signoff_binding))
            checks.append(_history_chain_check(history_lines, signoff))
            if require_signed:
                checks.append(_check("ucc_decision_board_require_signed", signoff.get("status") == "signed" and decision_report.get("status") in {"ready_for_signoff", "signed"}, "Decision Board is signed.", {"signoff_status": signoff.get("status"), "decision_status": decision_report.get("status")}))
            if require_quorum:
                checks.append(_check("ucc_decision_board_quorum_passed", quorum_report.get("status") == "passed", "Decision Board quorum passed.", {"blockers": quorum_report.get("blockers", [])}))
                checks.append(_check("ucc_decision_board_no_blocking_findings", conflict_report.get("status") == "passed", "Decision Board has no blocking findings.", {"blockers": conflict_report.get("blockers", [])}))
                checks.append(_check("ucc_decision_board_no_required_rejection", "required_reviewer_rejected" not in conflict_report.get("blockers", []), "Required reviewers did not reject."))
            if strict or require_quorum:
                checks.extend(
                    _external_binding_checks(
                        source,
                        accepted_index,
                        evidence_review_path,
                        evidence_review_verification_report_path,
                        accepted_evidence_paths or [],
                        accepted_evidence_verification_report_paths or [],
                        accepted_evidence_response_verification_report_paths or [],
                    )
                )
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_decision_board_zip_readable", False, "Decision Board archive can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_reviewer_decision_board_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_reviewer_decision_board_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _document_binding_checks(
    manifest: ImplementationDocument,
    source: ImplementationDocument,
    roster: ImplementationDocument,
    response_index: ImplementationDocument,
    accepted_index: ImplementationDocument,
    finding_ledger: ImplementationDocument,
    conflict_report: ImplementationDocument,
    quorum_report: ImplementationDocument,
    decision_matrix: ImplementationDocument,
    decision_report: ImplementationDocument,
    checklist: ImplementationDocument,
    signoff: ImplementationDocument,
    signoff_binding: ImplementationDocument,
) -> list[ImplementationDocument]:
    manifest_source = _as_document(manifest.get("source"))
    source_hash = source.get("source_hash")
    docs = [
        ("reviewer_roster", roster),
        ("response_index", response_index),
        ("accepted_evidence_index", accepted_index),
        ("finding_ledger", finding_ledger),
        ("conflict_report", conflict_report),
        ("quorum_report", quorum_report),
        ("decision_matrix", decision_matrix),
        ("decision_report", decision_report),
        ("manual_checklist", checklist),
    ]
    checks = [_check("ucc_decision_board_source_hash_binding", all(doc.get("source_hash") == source_hash for _, doc in docs) and manifest.get("source_hash") == source_hash, "Decision Board documents bind the same source hash.")]
    for name, doc in docs:
        checks.append(_check(f"ucc_decision_board_manifest_{name}_binding", manifest_source.get(f"{name}_hash") == doc.get("integrity_hash"), f"Manifest binds {name}."))
    checks.extend(
        [
            _check("ucc_decision_board_manifest_source_binding", manifest_source.get("board_source_hash") == source.get("integrity_hash"), "Manifest binds Board source."),
            _check("ucc_decision_board_signoff_binding", signoff_binding.get("signoff_hash") == signoff.get("integrity_hash") and signoff_binding.get("decision_report_hash") == signoff.get("decision_report_hash"), "Signoff binding summary matches signoff."),
            _check("ucc_decision_board_signoff_decision_binding", signoff.get("decision_report_hash") == decision_report.get("integrity_hash") and signoff.get("quorum_report_hash") == quorum_report.get("integrity_hash") and signoff.get("accepted_evidence_index_hash") == accepted_index.get("integrity_hash"), "Signoff binds decision evidence."),
        ]
    )
    return checks


def _external_binding_checks(
    source: ImplementationDocument,
    accepted_index: ImplementationDocument,
    evidence_review_path: Path | str | None,
    evidence_review_verification_report_path: Path | str | None,
    accepted_evidence_paths: list[Path | str | None] | tuple[Path | str | None, ...],
    accepted_evidence_verification_report_paths: list[Path | str | None] | tuple[Path | str | None, ...],
    accepted_evidence_response_verification_report_paths: list[Path | str | None] | tuple[Path | str | None, ...],
) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    if not evidence_review_path or not evidence_review_verification_report_path:
        checks.append(_check("ucc_decision_board_evidence_review_external_binding", False, "Evidence Review ZIP and verification report are required."))
    else:
        evidence_review_path = Path(evidence_review_path)
        evidence_review_verification_report_path = Path(evidence_review_verification_report_path)
        runtime = verify_unified_command_center_evidence_review_package(evidence_review_path, strict=False, require_replay_passed=False)
        external = _read_json_file(evidence_review_verification_report_path)
        source_review = _as_document(source.get("evidence_review"))
        checks.extend(
            [
                _check("ucc_decision_board_evidence_review_external_package_type", external.get("package_type") == UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_VERIFICATION_PACKAGE_TYPE, "Evidence Review verification package type is valid."),
                _check("ucc_decision_board_evidence_review_external_integrity", _integrity_ok(external), "Evidence Review verification integrity is valid."),
                _check("ucc_decision_board_evidence_review_external_status", external.get("status") == "passed" and runtime.get("status") == "passed", "Evidence Review external and runtime verification passed."),
                _check("ucc_decision_board_evidence_review_external_binding", source_review.get("zip_sha256") == runtime.get("zip_sha256") == external.get("zip_sha256") and source_review.get("manifest_hash") == runtime.get("manifest_hash") == external.get("manifest_hash"), "Decision Board binds current Evidence Review Pack."),
            ]
        )
    expected_items = [row for row in accepted_index.get("items", []) if isinstance(row, dict)]
    external_items = _external_acceptance_items(evidence_review_path, evidence_review_verification_report_path, accepted_evidence_paths, accepted_evidence_verification_report_paths, accepted_evidence_response_verification_report_paths)
    external_by_id = {str(row.get("evidence_id")): row for row in external_items if row.get("evidence_id")}
    duplicate_external_ids = sorted({str(row.get("evidence_id")) for row in external_items if row.get("evidence_id") and [str(item.get("evidence_id")) for item in external_items].count(str(row.get("evidence_id"))) > 1})
    duplicate_board_ids = sorted({str(row.get("evidence_id")) for row in expected_items if row.get("evidence_id") and [str(item.get("evidence_id")) for item in expected_items].count(str(row.get("evidence_id"))) > 1})
    checks.append(_check("ucc_decision_board_accepted_evidence_unique", not duplicate_external_ids and not duplicate_board_ids, "Accepted evidence IDs are unique.", {"external_duplicates": duplicate_external_ids, "board_duplicates": duplicate_board_ids}))
    missing = []
    mismatched = []
    for item in expected_items:
        evidence_id = str(item.get("evidence_id") or "")
        external = _as_document(external_by_id.get(evidence_id))
        if not external:
            missing.append(evidence_id)
            continue
        comparisons = {
            "zip_sha256": item.get("zip_sha256") == external.get("zip_sha256"),
            "manifest_hash": item.get("manifest_hash") == external.get("manifest_hash"),
            "acceptance_verification_hash": item.get("acceptance_verification_hash") == external.get("acceptance_verification_hash"),
            "response_verification_hash": item.get("response_verification_hash") == external.get("response_verification_hash"),
            "response_public_hash": item.get("response_public_hash") == external.get("response_public_hash"),
            "response_id": item.get("response_id") == external.get("response_id"),
            "role": item.get("role") == external.get("role"),
            "organization": item.get("organization") == external.get("organization"),
            "result": item.get("result") == external.get("result") == "accepted",
            "status": item.get("status") == external.get("status") == "passed",
        }
        if not all(comparisons.values()):
            mismatched.append({"evidence_id": evidence_id, "comparisons": comparisons})
    checks.append(_check("ucc_decision_board_accepted_evidence_external_binding", not missing and not mismatched, "All Board accepted evidence rows match external acceptance evidence.", {"missing": missing, "mismatched": mismatched}))
    return checks


def _external_acceptance_items(
    review_pack_path: Path | str | None,
    review_pack_verification_report_path: Path | str | None,
    accepted_evidence_paths: list[Path | str | None] | tuple[Path | str | None, ...],
    accepted_evidence_verification_report_paths: list[Path | str | None] | tuple[Path | str | None, ...],
    accepted_evidence_response_verification_report_paths: list[Path | str | None] | tuple[Path | str | None, ...],
) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    count = max(len(accepted_evidence_paths), len(accepted_evidence_verification_report_paths), len(accepted_evidence_response_verification_report_paths))
    for index in range(count):
        zip_path = _path_at(accepted_evidence_paths, index)
        report_path = _path_at(accepted_evidence_verification_report_paths, index)
        response_path = _path_at(accepted_evidence_response_verification_report_paths, index)
        if not zip_path or not report_path or not response_path or not Path(zip_path).exists() or not Path(report_path).exists() or not Path(response_path).exists():
            rows.append({"evidence_id": f"missing-{index}", "status": "missing"})
            continue
        runtime = verify_unified_command_center_evidence_review_acceptance_package(zip_path, strict=True, require_accepted=True, review_pack_path=review_pack_path, review_pack_verification_report_path=review_pack_verification_report_path, response_verification_report_path=response_path)
        external = _read_json_file(report_path)
        response_summary = _read_json_file(response_path)
        public_response = _read_zip_json(Path(zip_path), "original-response-public.json")
        reviewer = _as_document(public_response.get("reviewer"))
        rows.append(
            {
                "evidence_id": str(runtime.get("summary", {}).get("evidence_id") or public_response.get("evidence_id") or ""),
                "response_id": str(public_response.get("response_id") or response_summary.get("response_id") or ""),
                "result": public_response.get("result") or runtime.get("summary", {}).get("result"),
                "status": "passed" if runtime.get("status") == external.get("status") == "passed" else "failed",
                "role": str(reviewer.get("role") or ""),
                "organization": str(reviewer.get("organization") or ""),
                "zip_sha256": runtime.get("zip_sha256"),
                "manifest_hash": runtime.get("manifest_hash"),
                "acceptance_verification_hash": external.get("integrity_hash"),
                "response_verification_hash": response_summary.get("integrity_hash"),
                "response_public_hash": public_response.get("integrity_hash"),
            }
        )
    return rows


def _path_at(values: list[Path | str | None] | tuple[Path | str | None, ...], index: int) -> Path | None:
    if index >= len(values) or not values[index]:
        return None
    return _as_path(values[index])


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str]) -> list[ImplementationDocument]:
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = REQUIRED_ENTRIES - {"manifest.json"}
    effective = names - {"manifest.json"}
    mismatches = []
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in names:
            continue
        data = archive.read(rel)
        info = archive.getinfo(rel)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(rel)
    return [
        _check("ucc_decision_board_manifest_declares_files", declared == effective, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective), "undeclared": sorted(effective - declared)}),
        _check("ucc_decision_board_manifest_files_fixed", declared == expected, "Manifest files match fixed structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
        _check("ucc_decision_board_manifest_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
    ]


def _history_chain_check(lines: list[str], signoff: ImplementationDocument) -> ImplementationDocument:
    previous = None
    found = False
    for line in lines:
        if not line.strip():
            continue
        event = json.loads(line)
        expected_payload = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event.get("previous_event_hash") != previous or event.get("payload_hash") != expected_payload or event.get("event_hash") != expected_event:
            return _check("ucc_decision_board_history_chain", False, "Decision Board history hash chain is valid.")
        if event.get("event_type") == "ucc_reviewer_decision_board_signoff_created" and event.get("signoff_hash") == signoff.get("integrity_hash"):
            found = True
        previous = event.get("event_hash")
    return _check("ucc_decision_board_history_chain", found, "Decision Board history contains the current signed event.")


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    hits = []
    for name in names:
        try:
            data = archive.read(name)
        except (KeyError, OSError):
            continue
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                hits.append(name)
                break
    return _check("ucc_decision_board_redaction_scan", not hits, "No sensitive strings appear in the package.", {"entries": sorted(set(hits))})


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, extra: ImplementationDocument | None = None) -> ImplementationDocument:
    if extra is not None:
        checks.append(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") != "blocking"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION,
        "status": status,
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, detail: ImplementationDocument | None = None, *, severity: str = "blocking") -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message, "detail": detail or {}}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_json_file(path: Path | str) -> ImplementationDocument:
    return read_json(Path(path))


def _read_zip_json(path: Path, rel: str) -> ImplementationDocument:
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read(rel).decode("utf-8"))


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path:
        return None
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _is_safe_entry(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized != name:
        return False
    if not normalized or normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        return False
    if re.match(r"^[A-Za-z]:", normalized):
        return False
    lower = normalized.lower()
    if lower.startswith(".musicforge/") or "/.musicforge/" in lower:
        return False
    return True
