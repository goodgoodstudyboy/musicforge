from __future__ import annotations

from song_agent.domains.delivery.releases import stable_hash


PUBLICATION_MONITORING_SCHEMA_VERSION = 1


PUBLICATION_MONITOR_RUN_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitor_run"


PUBLICATION_PROBE_RESULTS_PACKAGE_TYPE = "musicforge_public_trust_center_publication_probe_results"


PUBLICATION_DRIFT_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_publication_drift_report"


PUBLICATION_INCIDENT_REPORT_PACKAGE_TYPE = "musicforge_public_trust_center_publication_incident_report"


PUBLICATION_MONITORING_PACKAGE_TYPE = "musicforge_public_trust_center_publication_monitoring"


PUBLICATION_MONITORING_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


def monitoring_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in PUBLICATION_MONITORING_HASH_EXCLUDE_KEYS})


def monitoring_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})


def verification_hash(report: dict[str, Any]) -> str | None:
    if not report:
        return None
    return stable_hash({key: value for key, value in report.items() if key != "generated_at"})
