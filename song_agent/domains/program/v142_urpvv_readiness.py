# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
import io as io
import json as json
import re as re
import tempfile as tempfile
import zipfile as zipfile
from pathlib import Path as Path
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

check = _make_deferred_global('check')

def bind_globals(namespace: dict[str, object]) -> None:
    global check
    check = namespace.get('check', check)
    _bind_deferred_defaults(namespace)


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




def _deep_checks(
    archive: zipfile.ZipFile,
    package_index: DomainDocument,
    verification_index: DomainDocument,
    proof_index: DomainDocument,
    *,
    require_current_program: bool,
    require_current_operations: bool,
    require_current_handoff: bool,
    require_accepted_evidence: bool,
) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
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

def _deep_program_checks(root: Path, package_row: DomainDocument | None, verification_row: DomainDocument | None, proofs: dict[tuple[object, object], DomainDocument], *, require_current: bool) -> list[DomainDocument]:
    checks: list[DomainDocument] = []
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

def _deep_operations_checks(root: Path, package_row: DomainDocument | None, verification_row: DomainDocument | None, proofs: dict[tuple[object, object], DomainDocument], *, require_current: bool) -> list[DomainDocument]:
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

def _deep_handoff_checks(root: Path, package_row: DomainDocument | None, verification_row: DomainDocument | None, proofs: dict[tuple[object, object], DomainDocument], *, require_current: bool) -> list[DomainDocument]:
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

def _deep_accepted_evidence_checks(root: Path, package_row: DomainDocument, verification_index: DomainDocument, proof_index: DomainDocument, *, require: bool) -> list[DomainDocument]:
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

def _runtime_report_checks(prefix: str, runtime: DomainDocument, external: DomainDocument, zip_path: Path, package_type: str) -> list[DomainDocument]:
    return [
        _check(f"{prefix}_runtime_passed", runtime.get("status") == "passed", "Runtime verifier passed.", {"blockers": runtime.get("blockers", [])}),
        _check(f"{prefix}_external_passed", external.get("status") == "passed", "External verification report passed.", {"blockers": external.get("blockers", [])}),
        _check(f"{prefix}_external_integrity", _integrity_ok(external), "External verification integrity is valid."),
        _check(f"{prefix}_external_package_type", external.get("package_type") == package_type, "External verification package type is valid."),
        _check(f"{prefix}_zip_sha256", external.get("zip_sha256") == runtime.get("zip_sha256") == _sha256_path(zip_path), "Runtime and external ZIP hash match."),
        _check(f"{prefix}_manifest_hash", external.get("manifest_hash") == runtime.get("manifest_hash"), "Runtime and external manifest hash match."),
    ]

def _proof_path(root: Path, proofs: dict[tuple[object, object], DomainDocument], component_type: str, proof_type: str) -> Path | None:
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

def _has_blocking_failures(checks: list[DomainDocument]) -> bool:
    return any(check.get("status") == "failed" and check.get("severity") == "blocking" for check in checks)

def _finish(checks: list[DomainDocument], summary: DomainDocument, first_check: DomainDocument | None = None) -> DomainDocument:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_VAULT_SCHEMA_VERSION,
    )

def _read_json_entry(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    return json.loads(archive.read(name).decode("utf-8"))

def _safe_identifier(value: str) -> bool:
    return bool(value) and re.fullmatch(r"[A-Za-z0-9_.-]+", value) is not None and "/" not in value and "\\" not in value and ".." not in value.split(".")

def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> DomainDocument:
    return archive_redaction_check(archive, names, check_id="urpv_redaction_scan")

def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"
