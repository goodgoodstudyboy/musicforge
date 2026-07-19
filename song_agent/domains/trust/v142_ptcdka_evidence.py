# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import base64 as base64
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.trust.public_trust_center_distribution_kit import DISTRIBUTION_KIT_BLOCKED_KEYS as DISTRIBUTION_KIT_BLOCKED_KEYS, PublicTrustCenterDistributionKitStore as PublicTrustCenterDistributionKitStore, distribution_kit_manifest_hash as distribution_kit_manifest_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package as verify_public_trust_center_distribution_kit_package, write_public_trust_center_distribution_kit_verification_report as write_public_trust_center_distribution_kit_verification_report
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_verifier import LOCAL_PATH_VALUE_PATTERNS as LOCAL_PATH_VALUE_PATTERNS
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance_contracts import ACCEPTANCE_BLOCKED_KEYS as ACCEPTANCE_BLOCKED_KEYS, ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS as ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS as ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS, ACCEPTED_EVIDENCE_PACKAGE_TYPE as ACCEPTED_EVIDENCE_PACKAGE_TYPE, ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE as ACCEPTED_EVIDENCE_REPORT_PACKAGE_TYPE, accepted_evidence_hash as accepted_evidence_hash, accepted_evidence_manifest_hash as accepted_evidence_manifest_hash, verification_hash as verification_hash

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

PublicTrustCenterDistributionKitAcceptanceStateError = _make_deferred_global('PublicTrustCenterDistributionKitAcceptanceStateError')
ch = _make_deferred_global('ch')
key = _make_deferred_global('key')
name = _make_deferred_global('name')

def bind_globals(namespace: dict[str, object]) -> None:
    global PublicTrustCenterDistributionKitAcceptanceStateError, ch, key, name
    PublicTrustCenterDistributionKitAcceptanceStateError = namespace.get('PublicTrustCenterDistributionKitAcceptanceStateError', PublicTrustCenterDistributionKitAcceptanceStateError)
    ch = namespace.get('ch', ch)
    key = namespace.get('key', key)
    name = namespace.get('name', name)
    _bind_deferred_defaults(namespace)


DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION = 1
ACCEPTANCE_RESPONSE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_response"
ACCEPTANCE_TEMPLATE_TYPE = "musicforge_public_trust_center_distribution_kit_acceptance_template"
ACCEPTANCE_ALLOWED_RESULTS = {"accepted", "needs_changes", "rejected"}
RESPONSE_RECORD_HASH_EXCLUDE_KEYS = {"integrity_hash", "imported_at"}
RESPONSE_PAYLOAD_HASH_EXCLUDE_KEYS = {"response_hash", "payload_hash", "integrity_hash"}




def response_template(center_id: str, binding: DomainDocument) -> DomainDocument:
    return {
        "response_type": ACCEPTANCE_RESPONSE_TYPE,
        "response_id": "",
        "center_id": center_id,
        "result": "accepted",
        "review_mode": "external_manual",
        "reviewer": {"name": "", "organization": "", "role": ""},
        "reviewed_at": "",
        "verification": {"status": "passed", "tool": "verify-public-trust-center-distribution-kit-package", "tool_version": __version__, "command": "", "report_hash": binding.get("distribution_kit_verification_report_hash"), "summary": {}},
        "kit_binding": dict(binding),
        "findings": [],
        "comments": "",
    }

def verify_response_document(response: DomainDocument, binding: DomainDocument) -> DomainDocument:
    checks: list[DomainDocument] = []
    checks.append(_check("ptcdka_response_type", response.get("response_type") == ACCEPTANCE_RESPONSE_TYPE, "Response type is valid."))
    response_id = str(response.get("response_id") or "")
    checks.append(_check("ptcdka_response_id", bool(response_id) and _safe_id(response_id) == response_id, "Response id is safe."))
    result = str(response.get("result") or "")
    checks.append(_check("ptcdka_response_result", result in ACCEPTANCE_ALLOWED_RESULTS, "Response result is allowed."))
    checks.append(_check("ptcdka_response_review_mode", response.get("review_mode") == "external_manual", "Response review mode is external_manual."))
    required = [
        "distribution_kit_zip_sha256",
        "distribution_kit_zip_size_bytes",
        "distribution_kit_manifest_hash",
        "distribution_kit_report_hash",
        "distribution_kit_source_hash",
        "distribution_kit_verification_report_hash",
    ]
    kit_binding = _as_document(response.get("kit_binding"))
    missing = [key for key in required if not kit_binding.get(key)]
    checks.append(_check("ptcdka_response_required_binding", not missing, "Response Kit binding fields are present." if not missing else "Response Kit binding is missing: " + ", ".join(missing)))
    binding_ok = all(kit_binding.get(key) == binding.get(key) for key in required)
    checks.append(_check("ptcdka_response_kit_binding_current", binding_ok, "Response Kit binding matches current Distribution Kit."))
    verification = _as_document(response.get("verification"))
    checks.append(_check("ptcdka_response_external_verification_passed", result != "accepted" or verification.get("status") == "passed", "Accepted response has passed external verification."))
    checks.append(_check("ptcdka_response_hash", not response.get("response_hash") or response.get("response_hash") == response_payload_hash(response), "Response hash matches payload."))
    findings = _redaction_findings("response", json.dumps(response, ensure_ascii=False, sort_keys=True))
    checks.append({"scope": "response", "check_id": "ptcdka_response_redaction_scan", "status": "failed" if findings else "passed", "severity": "blocking", "message": f"Found {len(findings)} sensitive value(s)." if findings else "No sensitive values found."})
    blockers = [item for item in checks if item.get("status") == "failed" and item.get("severity") == "blocking"]
    return _sanitize({"schema_version": DISTRIBUTION_KIT_ACCEPTANCE_SCHEMA_VERSION, "package_kind": "distribution_kit_acceptance_response", "generated_at": now_iso(), "status": "failed" if blockers else "passed", "summary": {"result": result, "blocker_count": len(blockers)}, "checks": checks, "blockers": blockers})

def response_payload_hash(response: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in RESPONSE_PAYLOAD_HASH_EXCLUDE_KEYS})

def response_record_hash(response: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in RESPONSE_RECORD_HASH_EXCLUDE_KEYS})

def response_summary(response: DomainDocument) -> DomainDocument:
    return {
        "response_id": response.get("response_id"),
        "external_response_id": response.get("external_response_id"),
        "result": response.get("result"),
        "status": response.get("status"),
        "verification_status": response.get("verification_status"),
        "kit_binding_status": response.get("kit_binding_status"),
        "accepted_evidence_id": response.get("accepted_evidence_id"),
        "imported_at": response.get("imported_at"),
    }

def accepted_evidence_summary(evidence: DomainDocument | None) -> DomainDocument:
    data = _as_document(evidence)
    reviewer = _as_document(data.get("reviewer_summary"))
    return {"status": data.get("status") or "missing", "result": data.get("result") or "missing", "evidence_id": data.get("evidence_id"), "response_id": data.get("response_id"), "reviewer_name": reviewer.get("name"), "reviewer_organization": reviewer.get("organization")}

def redaction_summary(value: object) -> DomainDocument:
    findings = _redaction_findings("payload", json.dumps(value, ensure_ascii=False, sort_keys=True))
    return {"status": "failed" if findings else "passed", "finding_count": len(findings)}

def _evidence_documents(evidence: DomainDocument, *, response_verification_report: DomainDocument | None = None, response_binding_summary: DomainDocument | None = None) -> DomainDocument:
    source = _as_document(evidence.get("source"))
    public = _as_document(evidence.get("public_response"))
    binding = _as_document(evidence.get("kit_binding"))
    response_verification_report = _as_document(response_verification_report)
    response_binding_summary = _as_document(response_binding_summary)
    response_verification = {
        "source_hash": evidence.get("source_hash"),
        "response_id": source.get("response_id"),
        "status": source.get("response_verification_status"),
        "response_payload_hash": source.get("response_payload_hash"),
        "response_integrity_hash": source.get("response_integrity_hash"),
        "verification_hash": source.get("response_verification_hash"),
    }
    response_verification_report_summary = _sanitize(
        {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "status": response_verification_report.get("status"),
            "response_payload_hash": source.get("response_payload_hash"),
            "raw_response_sha256": source.get("raw_response_sha256"),
            "response_public_summary_hash": source.get("response_public_summary_hash"),
            "response_verification_hash": verification_hash(response_verification_report),
            "check_count": len(_as_list(response_verification_report.get("checks"))),
            "blocker_count": len(_as_list(response_verification_report.get("blockers"))),
        }
    )
    response_binding_proof = _sanitize(
        {
            "source_hash": evidence.get("source_hash"),
            "response_id": source.get("response_id"),
            "binding_summary_hash": stable_hash(response_binding_summary),
            "response_payload_hash": source.get("response_payload_hash"),
            "raw_response_sha256": source.get("raw_response_sha256"),
            "response_public_summary_hash": source.get("response_public_summary_hash"),
            "kit_binding_status": response_binding_summary.get("kit_binding_status") or response_binding_summary.get("status"),
            "response_binding": _as_document(response_binding_summary.get("response_binding")),
            "current_binding": _as_document(response_binding_summary.get("current_binding")),
        }
    )
    return {
        "evidence-report.json": evidence,
        "original-response-public.json": public,
        "original-response-binding-summary.json": {"source_hash": evidence.get("source_hash"), **source, "public_response": public, "response_public_summary_hash": source.get("response_public_summary_hash"), **binding},
        "response-verification-summary.json": response_verification,
        "response-verification-report-summary.json": response_verification_report_summary,
        "original-response-binding-proof.json": response_binding_proof,
        "distribution-kit-verification-summary.json": {"source_hash": evidence.get("source_hash"), **binding},
        "README.txt": _evidence_readme(evidence),
        "VERIFY.txt": _evidence_verify_text(),
    }

def _public_response(response: DomainDocument) -> DomainDocument:
    payload = _document_or(response.get("response_payload"), response)
    reviewer = _as_document(payload.get("reviewer"))
    public_findings = []
    for item in payload.get("findings", []) if isinstance(payload.get("findings"), list) else []:
        if isinstance(item, dict):
            public_findings.append({"severity": item.get("severity"), "code": item.get("code"), "public_message": sanitize_sensitive_text(str(item.get("public_message") or item.get("message") or ""))[:500]})
    return _sanitize(
        {
            "response_id": payload.get("response_id"),
            "result": payload.get("result"),
            "review_mode": payload.get("review_mode"),
            "reviewed_at": payload.get("reviewed_at"),
            "reviewer": {"name": reviewer.get("name"), "organization": reviewer.get("organization"), "role": reviewer.get("role")},
            "verification_status": (_as_document(payload.get("verification"))).get("status"),
            "comments_excerpt": sanitize_sensitive_text(str(payload.get("comments") or ""))[:500],
            "findings": public_findings,
        }
    )

def _response_binding_summary(record: DomainDocument, current_binding: DomainDocument) -> DomainDocument:
    return _sanitize({"response_id": record.get("response_id"), "status": record.get("status"), "kit_binding_status": record.get("kit_binding_status"), "response_binding": record.get("kit_binding"), "current_binding": current_binding, "response_payload_hash": record.get("response_payload_hash"), "response_integrity_hash": record.get("integrity_hash")})

def _response_state_status(result: str, stale: bool, verification: DomainDocument) -> str:
    if verification.get("status") == "failed":
        return "invalid"
    prefix = result if result in ACCEPTANCE_ALLOWED_RESULTS else "invalid"
    if prefix == "invalid":
        return "invalid"
    return prefix + ("_stale" if stale else "_current")

def _response_binding_stale(response: DomainDocument, binding: DomainDocument) -> bool:
    response_binding = _as_document(response.get("kit_binding"))
    keys = ["distribution_kit_zip_sha256", "distribution_kit_zip_size_bytes", "distribution_kit_manifest_hash", "distribution_kit_report_hash", "distribution_kit_source_hash", "distribution_kit_verification_report_hash"]
    return any(response_binding.get(key) != binding.get(key) for key in keys)

def _binding_from_response(response: DomainDocument) -> DomainDocument:
    return dict(_as_document(response.get("kit_binding")))

def _require_response_binding(response: DomainDocument) -> None:
    if response.get("response_type") != ACCEPTANCE_RESPONSE_TYPE:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response_type is invalid.")
    required = ["distribution_kit_zip_sha256", "distribution_kit_zip_size_bytes", "distribution_kit_manifest_hash", "distribution_kit_report_hash", "distribution_kit_source_hash", "distribution_kit_verification_report_hash"]
    binding = _as_document(response.get("kit_binding"))
    missing = [key for key in required if not binding.get(key)]
    if missing:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response is missing required Kit binding fields: " + ", ".join(missing))
    if response.get("result") not in ACCEPTANCE_ALLOWED_RESULTS:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response result is invalid.")
    if response.get("review_mode") != "external_manual":
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response review_mode must be external_manual.")

def _reject_path_payload(payload: DomainDocument) -> None:
    if any(payload.get(key) for key in ("source_path", "local_path", "file_path")):
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance import only accepts uploaded content; source_path/local_path/file_path are not allowed.")

def _payload_bytes(payload: DomainDocument, *, max_size: int) -> bytes:
    if payload.get("content_base64"):
        try:
            raw = base64.b64decode(str(payload.get("content_base64")), validate=True)
        except Exception as exc:
            raise PublicTrustCenterDistributionKitAcceptanceStateError(f"Invalid content_base64: {exc}") from exc
    elif payload.get("data_base64"):
        try:
            raw = base64.b64decode(str(payload.get("data_base64")), validate=True)
        except Exception as exc:
            raise PublicTrustCenterDistributionKitAcceptanceStateError(f"Invalid data_base64: {exc}") from exc
    elif isinstance(payload.get("response"), dict):
        raw = json.dumps(payload.get("response"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    elif isinstance(payload.get("content"), dict):
        raw = json.dumps(payload.get("content"), ensure_ascii=False, sort_keys=True).encode("utf-8")
    elif payload.get("content"):
        raw = str(payload.get("content")).encode("utf-8")
    else:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response content is required.")
    if len(raw) > max_size:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response content is too large.")
    return raw

def _response_payload_from_bytes(raw: bytes) -> DomainDocument:
    try:
        if raw[:4] == b"PK\x03\x04":
            import io

            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                names = archive.namelist()
                candidate = "acceptance-response.json" if "acceptance-response.json" in names else next((name for name in names if name.endswith(".json")), "")
                if not candidate:
                    raise PublicTrustCenterDistributionKitAcceptanceStateError("Acceptance response ZIP does not contain a JSON response.")
                raw = archive.read(candidate)
        value = json.loads(raw.decode("utf-8"))
    except PublicTrustCenterDistributionKitAcceptanceStateError:
        raise
    except Exception as exc:
        raise PublicTrustCenterDistributionKitAcceptanceStateError(f"Distribution Kit acceptance response could not be parsed: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Distribution Kit acceptance response must be a JSON object.")
    return _sanitize(value)

def _read_zip_json(zip_path: Path, entry: str) -> DomainDocument:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            value = json.loads(archive.read(entry).decode("utf-8"))
    except Exception:
        return {}
    return _as_document(value)

def _read_json_default(path: Path, *, default: DomainDocument | None = None) -> DomainDocument:
    if not path.exists():
        return dict(default or {})
    try:
        value = json.loads(_read_text(path))
    except Exception:
        return dict(default or {})
    return _sanitize(_document_or(value, dict(default or {})))

def _write_json(path: Path, payload: DomainDocument) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text(path, json.dumps(_sanitize(payload), ensure_ascii=False, indent=2) + "\n")
    return path

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(_fs_path(path), "w", encoding="utf-8") as handle:
        handle.write(text)

def _read_text(path: Path) -> str:
    with open(_fs_path(path), "r", encoding="utf-8") as handle:
        return handle.read()

def _append_jsonl(path: Path, payload: DomainDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(_fs_path(path), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(_sanitize(payload), ensure_ascii=False, sort_keys=True) + "\n")

def _file_record(root: Path, path: Path) -> DomainDocument:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": os.stat(_fs_path(path)).st_size, "sha256": _sha256(path)}

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    return [(path.resolve(), path.relative_to(root).as_posix()) for path in sorted(root.rglob("*")) if _is_file(path)]

def _is_file(path: Path) -> bool:
    try:
        return os.path.isfile(_fs_path(path))
    except OSError:
        return False

def _write_zip(zip_path: Path, export_dir: Path) -> None:
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with zipfile.ZipFile(_fs_path(tmp_path), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for resolved, entry in _zip_entries(export_dir):
                archive.write(_fs_path(resolved), entry)
        os.replace(_fs_path(tmp_path), _fs_path(zip_path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

def _sha256(path: Path) -> str | None:
    try:
        if not os.path.isfile(_fs_path(path)):
            return None
    except OSError:
        return None
    digest = hashlib.sha256()
    with open(_fs_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _evidence_readme(evidence: DomainDocument) -> str:
    return sanitize_sensitive_text("\n".join(["MusicForge Distribution Kit Accepted Evidence", "", f"Center ID: {evidence.get('center_id')}", f"Evidence ID: {evidence.get('evidence_id')}", f"Status: {evidence.get('status')}", ""]))

def _evidence_verify_text() -> str:
    return "Verify this evidence:\npython -m song_agent.cli verify-public-trust-center-distribution-kit-accepted-evidence-package public-trust-center-distribution-kit-accepted-evidence.zip --strict --json\n"

def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if target != root and root not in target.parents:
        raise PublicTrustCenterDistributionKitAcceptanceStateError("Resolved path escapes Distribution Kit Acceptance root.")

def _fs_path(path: Path) -> str:
    text = str(path.resolve())
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text

def _safe_id(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "item")).strip(".-")
    return text or "item"

def _next_response_id(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    return f"ptcdkar-{len([path for path in root.iterdir() if path.is_dir()]) + 1:06d}"

def _next_change_request_id(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    return f"ptcdkcr-{len(list(root.glob('ptcdkcr-*.json'))) + 1:06d}"

def _check(check_id: str, ok: bool, message: str) -> DomainDocument:
    return {"scope": "response", "check_id": check_id, "status": "passed" if ok else "failed", "severity": "blocking", "message": message}

def _redaction_findings(scope: str, text: str) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    sanitized = sanitize_sensitive_text(text)
    if sanitized != text:
        findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _replacement in SENSITIVE_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "sensitive_value", "message": "Sensitive value pattern found."})
    for pattern, _kind in LOCAL_PATH_VALUE_PATTERNS:
        if pattern.search(text):
            findings.append({"scope": scope, "kind": "local_path", "message": "Local path pattern found."})
    lowered = text.lower()
    for marker in ("github" + "key", "x-access-" + "token", "api_" + "key", "access_" + "token", "source_" + "path", "local_" + "path", "file_" + "path"):
        if marker in lowered:
            findings.append({"scope": scope, "kind": "blocked_marker", "message": f"Blocked marker found: {marker}"})
    return findings

def _sanitize(payload: object) -> DomainDocument:
    return sanitize_metadata(payload, blocked_keys=ACCEPTANCE_BLOCKED_KEYS)
