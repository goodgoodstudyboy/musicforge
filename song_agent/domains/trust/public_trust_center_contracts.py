from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document
from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

import html
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


PTC_PACKAGE_TYPE = "musicforge_public_trust_center"


PTC_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


PTC_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


PTC_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


PTC_HTML_PAGES = (
    "index.html",
    "releases.html",
    "portfolios.html",
    "delivery.html",
    "distribution.html",
    "submissions.html",
    "operations.html",
    "evidence.html",
    "risk.html",
    "verify.html",
)


_DELIVERY_COLLECTION_DOMAINS = (
    ("release_delivery_summaries", "release"),
    ("distribution_summaries", "distribution"),
    ("submission_summaries", "submission"),
    ("submission_evidence_summaries", "submission_evidence"),
    ("operations_summaries", "operations"),
)


def public_trust_center_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in report.items() if key not in PTC_REPORT_HASH_EXCLUDE_KEYS})


def public_trust_center_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in PTC_MANIFEST_HASH_EXCLUDE_KEYS})


def public_trust_center_data_documents(
    report: dict[str, Any],
    verification_sidecars: dict[str, dict[str, Any]] | None = None,
    delivery_sidecars: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    source = _as_document(report.get("source"))
    source_hash = report.get("source_hash")
    release_index = {"source_hash": source_hash, "releases": report.get("release_readiness", [])}
    portfolio_index = {"source_hash": source_hash, "portfolios": report.get("portfolio_readiness", [])}
    package_index = {"source_hash": source_hash, "packages": report.get("package_index", [])}
    verification_index = {"source_hash": source_hash, "verifications": report.get("verification_index", [])}
    risk_register = {"source_hash": source_hash, "risks": report.get("risk_register", [])}
    transparency_index = {"source_hash": source_hash, "transparency": source.get("transparency", [])}
    acknowledgement_index = {"source_hash": source_hash, "acknowledgements": source.get("acknowledgements", [])}
    verification_sidecar = _package_verification_index_from_sidecars(source_hash, verification_sidecars) if verification_sidecars is not None else {"source_hash": source_hash, "packages": _package_verification_sidecars(source), "verifications": _verification_sidecars(source), "sidecars": []}
    delivery_index = {"source_hash": source_hash, "releases": report.get("delivery_readiness", [])}
    distribution_index = {"source_hash": source_hash, "targets": source.get("distribution_summaries", [])}
    submission_index = {"source_hash": source_hash, "submissions": source.get("submission_summaries", [])}
    submission_evidence_index = {"source_hash": source_hash, "evidence": source.get("submission_evidence_summaries", [])}
    operations_index = {"source_hash": source_hash, "operations": source.get("operations_summaries", [])}
    operations_package_index = {"source_hash": source_hash, "packages": source.get("operations_package_fingerprints", [])}
    readiness_matrix = {"source_hash": source_hash, "columns": ["release", "distribution", "submission", "submission_evidence", "operations", "portfolio_public_proof"], "rows": source.get("delivery_readiness_matrix", [])}
    delivery_risk_register = {"source_hash": source_hash, "risks": report.get("delivery_risk_register", [])}
    delivery_verification = _delivery_verification_index_from_sidecars(source_hash, delivery_sidecars) if delivery_sidecars is not None else _delivery_verification_index_from_source(source_hash, source)
    data = {
        "source_hash": source_hash,
        "summary": report.get("summary", {}),
        "releases": release_index["releases"],
        "portfolios": portfolio_index["portfolios"],
        "packages": package_index["packages"],
        "verifications": verification_index["verifications"],
        "package_verification_summaries": verification_sidecar["packages"],
        "risks": risk_register["risks"],
        "transparency": transparency_index["transparency"],
        "acknowledgements": acknowledgement_index["acknowledgements"],
        "delivery": delivery_index["releases"],
        "distribution": distribution_index["targets"],
        "submissions": submission_index["submissions"],
        "submission_evidence": submission_evidence_index["evidence"],
        "operations": operations_index["operations"],
        "operations_packages": operations_package_index["packages"],
        "readiness_matrix": readiness_matrix["rows"],
        "delivery_risks": delivery_risk_register["risks"],
        "delivery_verification_summaries": delivery_verification["summaries"],
    }
    return {
        "trust-center-data.json": data,
        "release-index.json": release_index,
        "portfolio-index.json": portfolio_index,
        "package-index.json": package_index,
        "verification-index.json": verification_index,
        "public-package-verification-index.json": verification_sidecar,
        "risk-register.json": risk_register,
        "transparency-index.json": transparency_index,
        "acknowledgement-index.json": acknowledgement_index,
        "delivery-index.json": delivery_index,
        "distribution-index.json": distribution_index,
        "submission-index.json": submission_index,
        "submission-evidence-index.json": submission_evidence_index,
        "operations-index.json": operations_index,
        "operations-package-index.json": operations_package_index,
        "readiness-matrix.json": readiness_matrix,
        "delivery-risk-register.json": delivery_risk_register,
        "delivery-verification-index.json": delivery_verification,
    }


def public_trust_center_html_pages(report: dict[str, Any], data_docs: dict[str, dict[str, Any]]) -> dict[str, str]:
    summary = _as_document(report.get("summary"))
    source_hash = str(report.get("source_hash") or "")
    report_hash = str(report.get("integrity_hash") or "")
    data_hash = stable_hash(data_docs.get("trust-center-data.json", {}))
    package_rows = data_docs.get("package-index.json", {}).get("packages", []) if isinstance(data_docs.get("package-index.json"), dict) else []
    risk_rows = data_docs.get("risk-register.json", {}).get("risks", []) if isinstance(data_docs.get("risk-register.json"), dict) else []
    delivery_rows = data_docs.get("delivery-index.json", {}).get("releases", []) if isinstance(data_docs.get("delivery-index.json"), dict) else []
    distribution_rows = data_docs.get("distribution-index.json", {}).get("targets", []) if isinstance(data_docs.get("distribution-index.json"), dict) else []
    submission_rows = data_docs.get("submission-index.json", {}).get("submissions", []) if isinstance(data_docs.get("submission-index.json"), dict) else []
    operations_rows = data_docs.get("operations-index.json", {}).get("operations", []) if isinstance(data_docs.get("operations-index.json"), dict) else []
    delivery_risk_rows = data_docs.get("delivery-risk-register.json", {}).get("risks", []) if isinstance(data_docs.get("delivery-risk-register.json"), dict) else []
    body = {
        "index.html": [
            "<h1>MusicForge Public Trust Center</h1>",
            _kv("Status", summary.get("status")),
            _kv("Readiness", summary.get("readiness")),
            _kv("Releases", summary.get("release_count")),
            _kv("Portfolios", summary.get("portfolio_count")),
            _kv("Delivery ready", summary.get("delivery_ready_count")),
            _kv("Public packages", summary.get("public_package_count")),
            _kv("Passed verifications", summary.get("passed_verification_count")),
            _links(),
        ],
        "releases.html": [
            "<h1>Release Readiness</h1>",
            _table(data_docs.get("release-index.json", {}).get("releases", []) if isinstance(data_docs.get("release-index.json"), dict) else [], ("release_id", "name", "status", "signoff_status")),
            _links(),
        ],
        "portfolios.html": [
            "<h1>Portfolio Governance</h1>",
            _table(data_docs.get("portfolio-index.json", {}).get("portfolios", []) if isinstance(data_docs.get("portfolio-index.json"), dict) else [], ("portfolio_id", "status", "public_package_status")),
            _links(),
        ],
        "delivery.html": [
            "<h1>Delivery Readiness</h1>",
            _table(delivery_rows, ("release_id", "name", "readiness", "release_signoff_status", "distribution_status", "submission_status", "operations_status", "risk_count")),
            _links(),
        ],
        "distribution.html": [
            "<h1>Distribution Targets</h1>",
            _table(distribution_rows, ("release_id", "target_id", "profile_id", "status", "signoff_status", "verification_status")),
            _links(),
        ],
        "submissions.html": [
            "<h1>Submissions</h1>",
            _table(submission_rows, ("release_id", "submission_id", "status", "signoff_status", "accepted_count", "verification_status")),
            _links(),
        ],
        "operations.html": [
            "<h1>Release Operations</h1>",
            _table(operations_rows, ("release_id", "operations_report_status", "operations_signoff_status", "operations_audit_status", "operations_reviewer_pack_status")),
            _links(),
        ],
        "evidence.html": [
            "<h1>Public Evidence Fingerprints</h1>",
            _table(package_rows, ("portfolio_id", "package_type", "verification_status", "zip_sha256", "manifest_hash")),
            _links(),
        ],
        "risk.html": [
            "<h1>Public Risk Register</h1>",
            _table(risk_rows, ("risk_id", "severity", "category", "title")),
            "<h2>Delivery Risks</h2>",
            _table(delivery_risk_rows, ("risk_id", "severity", "domain", "title")),
            _links(),
        ],
        "verify.html": [
            "<h1>Offline Verification</h1>",
            "<pre>python -m song_agent.cli verify-public-trust-center-package public-trust-center.zip --strict --json</pre>",
            "<p>This Trust Center references evidence packages by fingerprint and does not embed internal ZIP files.</p>",
            _links(),
        ],
    }
    return {name: _html_shell(name, title=name, body="".join(parts), source_hash=source_hash, report_hash=report_hash, data_hash=data_hash) for name, parts in body.items()}


def expected_public_trust_center_documents(
    report: dict[str, Any],
    verification_sidecars: dict[str, dict[str, Any]] | None = None,
    delivery_sidecars: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    data_docs = public_trust_center_data_documents(report, verification_sidecars, delivery_sidecars)
    return data_docs, public_trust_center_html_pages(report, data_docs)


def _package_index(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("public_package_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _verification_index(source: ImplementationDocument) -> list[ImplementationDocument]:
    return sorted([dict(item) for item in source.get("verification_fingerprints", []) if isinstance(item, dict)], key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _package_verification_sidecars(source: ImplementationDocument) -> list[ImplementationDocument]:
    packages = _package_index(source)
    verifications = {
        _fingerprint_key(item): dict(item)
        for item in source.get("verification_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for package in packages:
        verification = verifications.get(_fingerprint_key(package), {})
        rows.append(
            {
                "portfolio_id": package.get("portfolio_id"),
                "profile": package.get("profile"),
                "package_type": package.get("package_type"),
                "zip_sha256": package.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash"),
                "verification_hash": package.get("verification_hash"),
                "verification_status": package.get("verification_status"),
                "verification_report_hash": verification.get("verification_hash") or package.get("verification_hash"),
                "verification_report_status": verification.get("verification_status") or package.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _package_verification_index_from_sidecars(source_hash: Any, sidecars: dict[str, ImplementationDocument] | None) -> ImplementationDocument:
    rows = []
    for path, doc in sorted((sidecars or {}).items()):
        if not isinstance(doc, dict):
            continue
        row = dict(_as_document(doc.get("package")))
        row["sidecar_path"] = path
        row["sidecar_hash"] = stable_hash(doc)
        rows.append(row)
    return {
        "source_hash": source_hash,
        "packages": sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")), str(item.get("profile")))),
        "verifications": _verification_sidecars_from_docs(sidecars or {}),
        "sidecars": [{"path": path, "hash": stable_hash(doc)} for path, doc in sorted((sidecars or {}).items()) if isinstance(doc, dict)],
    }


def _verification_sidecars_from_docs(sidecars: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    for doc in sidecars.values():
        if not isinstance(doc, dict):
            continue
        package = _as_document(doc.get("package"))
        verification = _as_document(doc.get("verification"))
        rows.append(
            {
                "portfolio_id": package.get("portfolio_id"),
                "profile": package.get("profile"),
                "package_type": package.get("package_type"),
                "verification_hash": verification.get("verification_report_hash"),
                "verification_status": verification.get("verification_report_status"),
                "verification_report_hash": verification.get("verification_report_hash"),
                "verification_report_status": verification.get("verification_report_status"),
                "blocker_count": verification.get("blocker_count", 0),
                "zip_sha256": verification.get("zip_sha256"),
                "zip_size_bytes": verification.get("zip_size_bytes"),
                "manifest_hash": verification.get("manifest_hash"),
                "sidecar_path": doc.get("sidecar_path"),
                "sidecar_hash": stable_hash(doc),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type")), str(item.get("profile"))))


def _delivery_verification_index_from_source(source_hash: Any, source: ImplementationDocument) -> ImplementationDocument:
    rows: list[dict[str, Any]] = []
    for collection, domain in _DELIVERY_COLLECTION_DOMAINS:
        for item in source.get(collection, []) if isinstance(source.get(collection), list) else []:
            if isinstance(item, dict):
                rows.append(_delivery_summary_from_item(domain, item))
    return {"source_hash": source_hash, "summaries": sorted(rows, key=_delivery_summary_key), "sidecars": []}


def _delivery_verification_index_from_sidecars(source_hash: Any, sidecars: dict[str, ImplementationDocument] | None) -> ImplementationDocument:
    summaries: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    fingerprint_rows: list[dict[str, Any]] = []
    for path, doc in sorted((sidecars or {}).items()):
        if not isinstance(doc, dict):
            continue
        if path.startswith("delivery-fingerprint-summaries/"):
            fingerprint_rows.append({"path": path, "hash": stable_hash(doc)})
            continue
        if not path.startswith("delivery-verification-summaries/"):
            continue
        summary = dict(_as_document(doc.get("summary")))
        summary["sidecar_path"] = path
        summary["sidecar_hash"] = stable_hash(doc)
        if doc.get("fingerprint_sidecar_path"):
            summary["fingerprint_sidecar_path"] = doc.get("fingerprint_sidecar_path")
            summary["fingerprint_sidecar_hash"] = doc.get("fingerprint_sidecar_hash")
        summaries.append(summary)
        rows.append({"path": path, "hash": stable_hash(doc)})
    return {"source_hash": source_hash, "summaries": sorted(summaries, key=_delivery_summary_key), "sidecars": rows, "fingerprint_sidecars": fingerprint_rows}


def _delivery_summary_from_item(domain: str, item: ImplementationDocument) -> ImplementationDocument:
    entity_id = str(item.get("target_id") or item.get("submission_id") or item.get("release_id") or "")
    row = {
        "domain": domain,
        "release_id": item.get("release_id"),
        "entity_id": entity_id,
        "status": _delivery_item_status(domain, item),
        "summary_hash": stable_hash(_delivery_public_payload(domain, item)),
    }
    for key in (
        "target_id",
        "submission_id",
        "package_id",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "signoff_status",
        "operations_report_status",
        "operations_signoff_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "release_signoff_status",
        "release_zip_status",
        "distribution_status",
        "submission_status",
        "submission_evidence_status",
        "operations_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "portfolio_public_proof_status",
        "risk_count",
        "readiness",
        "fingerprint_hash",
    ):
        if key in item:
            row[key] = item.get(key)
    return row


def _delivery_public_payload(domain: str, item: ImplementationDocument) -> ImplementationDocument:
    allowed = {
        "release_id",
        "target_id",
        "submission_id",
        "package_id",
        "status",
        "name",
        "readiness",
        "release_signoff_status",
        "release_zip_status",
        "distribution_status",
        "submission_status",
        "submission_evidence_status",
        "operations_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "portfolio_public_proof_status",
        "risk_count",
        "signoff_status",
        "profile_id",
        "platform",
        "target_name",
        "target_status",
        "track_count",
        "ready_count",
        "submitted_count",
        "accepted_count",
        "latest_feedback_status",
        "report_status",
        "report_hash",
        "signoff_hash",
        "redaction_status",
        "accepted_evidence_count",
        "attachment_count",
        "package_zip_sha256",
        "package_zip_size_bytes",
        "package_zip_status",
        "manifest_hash",
        "verification_status",
        "verification_hash",
        "verification_report_status",
        "operations_report_status",
        "operations_report_hash",
        "operations_source_hash",
        "operations_signoff_status",
        "operations_signoff_hash",
        "operations_archive_status",
        "operations_audit_status",
        "operations_reviewer_pack_status",
        "runbook_status",
        "change_request_count",
        "fingerprint_hash",
    }
    return {"domain": domain, **{key: item.get(key) for key in sorted(allowed) if key in item}}


def _delivery_summary_key(item: ImplementationDocument) -> tuple[str, str, str]:
    return (str(item.get("release_id") or ""), str(item.get("domain") or ""), str(item.get("entity_id") or item.get("target_id") or item.get("submission_id") or ""))


def _verification_sidecars(source: ImplementationDocument) -> list[ImplementationDocument]:
    packages = {
        _fingerprint_key(item): dict(item)
        for item in source.get("public_package_fingerprints", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for verification in _verification_index(source):
        package = packages.get(_fingerprint_key(verification), {})
        rows.append(
            {
                "portfolio_id": verification.get("portfolio_id"),
                "profile": verification.get("profile"),
                "package_type": verification.get("package_type"),
                "verification_hash": verification.get("verification_hash"),
                "verification_status": verification.get("verification_status"),
                "blocker_count": verification.get("blocker_count", 0),
                "zip_sha256": package.get("zip_sha256") or verification.get("zip_sha256"),
                "zip_size_bytes": package.get("zip_size_bytes") or verification.get("zip_size_bytes"),
                "manifest_hash": package.get("manifest_hash") or verification.get("manifest_hash"),
            }
        )
    return sorted(rows, key=lambda item: (str(item.get("portfolio_id")), str(item.get("package_type"))))


def _fingerprint_key(item: ImplementationDocument) -> tuple[str, str, str]:
    return (str(item.get("portfolio_id") or ""), str(item.get("package_type") or ""), str(item.get("profile") or ""))


def _delivery_item_status(domain: str, item: ImplementationDocument) -> str:
    if domain == "distribution":
        return str(item.get("verification_status") or item.get("status") or "missing")
    if domain == "submission":
        return str(item.get("status") or item.get("verification_status") or "missing")
    if domain == "submission_evidence":
        return str(item.get("signoff_status") or item.get("report_status") or "missing")
    if domain == "operations":
        return str(item.get("operations_signoff_status") or item.get("operations_report_status") or "missing")
    return str(item.get("readiness") or item.get("status") or "missing")


def _html_shell(page: str, title: str, body: str, *, source_hash: str, report_hash: str, data_hash: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)} - MusicForge Public Trust Center</title>\n"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.45;color:#17202a;background:#fff}nav a{margin-right:1rem}table{border-collapse:collapse;max-width:100%}td,th{border:1px solid #bbb;padding:.35rem .55rem;text-align:left}code,pre{background:#f4f4f4;padding:.2rem .35rem}</style>\n"
        "</head>\n"
        f'<body data-source-hash="{html.escape(source_hash)}" data-report-integrity="{html.escape(report_hash)}" data-data-hash="{html.escape(data_hash)}" data-page="{html.escape(page)}">\n'
        f"<nav>{_links()}</nav>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _links() -> str:
    return '<a href="index.html">Overview</a><a href="releases.html">Releases</a><a href="portfolios.html">Portfolios</a><a href="evidence.html">Evidence</a><a href="risk.html">Risk</a><a href="verify.html">Verify</a>'


def _kv(label: str, value: Any) -> str:
    return f"<p><strong>{html.escape(label)}:</strong> {html.escape(str(value if value is not None else 'missing'))}</p>"


def _table(rows: Any, columns: tuple[str, ...]) -> str:
    if not isinstance(rows, list) or not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = ""
    for row in rows[:250]:
        if not isinstance(row, dict):
            continue
        body += "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, ''))[:96])}</td>" for column in columns) + "</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
