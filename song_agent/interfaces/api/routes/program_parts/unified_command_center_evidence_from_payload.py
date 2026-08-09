from __future__ import annotations


from song_agent.platform.contracts.documents import JsonDocument



class ProgramRoutesUnifiedCommandCenterEvidenceFromPayload:
    def _unified_command_center_evidence_from_payload(self, payload: JsonDocument) -> JsonDocument:
        evidence = dict(payload or {})
        for key, zip_key, report_key in (
            ("release", "release_zip", "release_verification_report"),
            ("audio-command-center", "release_audio_command_center_zip", "release_audio_command_center_verification_report"),
            ("operations", "release_operations_zip", "release_operations_verification_report"),
            ("trust-operations-hub", "trust_operations_hub_zip", "trust_operations_hub_verification_report"),
            ("public-trust-center", "public_trust_center_zip", "public_trust_center_verification_report"),
            ("maintenance", "maintenance_backup_zip", "maintenance_backup_verification_report"),
        ):
            if payload.get(zip_key) or payload.get(report_key):
                evidence[key] = {"zip": payload.get(zip_key), "verification_report": payload.get(report_key)}
        if payload.get("distribution_zips") or payload.get("distribution_zip") or payload.get("distribution_verification_reports") or payload.get("distribution_verification_report"):
            evidence["distribution"] = {
                "zips": payload.get("distribution_zips") or ([payload.get("distribution_zip")] if payload.get("distribution_zip") else []),
                "verification_reports": payload.get("distribution_verification_reports") or ([payload.get("distribution_verification_report")] if payload.get("distribution_verification_report") else []),
            }
        if payload.get("submission_zips") or payload.get("submission_zip") or payload.get("submission_verification_reports") or payload.get("submission_verification_report"):
            evidence["submission"] = {
                "zips": payload.get("submission_zips") or ([payload.get("submission_zip")] if payload.get("submission_zip") else []),
                "verification_reports": payload.get("submission_verification_reports") or ([payload.get("submission_verification_report")] if payload.get("submission_verification_report") else []),
            }
        if payload.get("ga_readiness_report") or payload.get("ga_readiness_verification_report"):
            evidence["ga-readiness"] = {"report": payload.get("ga_readiness_report"), "verification_report": payload.get("ga_readiness_verification_report")}
        if payload.get("release_check_report"):
            evidence["release-check"] = {"report": payload.get("release_check_report")}
        if isinstance(payload.get("requirements"), dict):
            evidence["requirements"] = payload["requirements"]
        return evidence
