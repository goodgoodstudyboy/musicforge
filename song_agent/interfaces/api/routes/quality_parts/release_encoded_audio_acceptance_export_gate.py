from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseEncodedAudioAcceptanceExportGate:
    def _release_encoded_audio_acceptance_export_gate(self, export_manifest: dict[str, Any], acceptance_gate: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_acceptance = export_manifest.get("encoded_audio_acceptance") if isinstance(export_manifest.get("encoded_audio_acceptance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_acceptance:
            missing.append("encoded_audio_acceptance")
        summary: dict[str, _interfaces_api_runtime.Any] = {}
        release_id = str(export_manifest.get("release_id") or "")
        export_dir = self.release_store.export_dir(release_id)
        summary_path = str(manifest_acceptance.get("summary_path") or "encoded-audio-acceptance-summary.json")
        if manifest_acceptance:
            try:
                candidate = _interfaces_api_runtime.read_json(export_dir / summary_path)
                summary = candidate if isinstance(candidate, dict) else {}
            except Exception:
                missing.append(summary_path)
        if summary:
            expected_hash = str(manifest_acceptance.get("summary_hash") or "")
            actual_hash = _interfaces_api_runtime.encoded_audio_acceptance_summary_hash(summary)
            if not expected_hash or expected_hash != actual_hash or not _interfaces_api_runtime.encoded_audio_acceptance_summary_integrity_ok(summary):
                mismatched.append("summary_hash")
        elif manifest_acceptance:
            mismatched.append("summary")
        manifest_profiles = {str(item) for item in summary.get("required_profiles", []) if str(item).strip()} if isinstance(summary.get("required_profiles"), list) else {str(item) for item in manifest_acceptance.get("required_profiles", []) if str(item).strip()} if isinstance(manifest_acceptance.get("required_profiles"), list) else set()
        gate_profiles = {str(item) for item in acceptance_gate.get("required_profiles", []) if str(item).strip()} if isinstance(acceptance_gate.get("required_profiles"), list) else set()
        missing_profiles = sorted(gate_profiles - manifest_profiles)
        summary_tracks = summary.get("tracks") if isinstance(summary.get("tracks"), list) else []
        by_profile_track = {
            (str(row.get("profile_id") or ""), str(row.get("track_id") or "")): row
            for row in summary_tracks
            if isinstance(row, dict)
        }
        gate_summary = self.encoded_audio_acceptance_store.build_summary(release_id, required_profiles=sorted(gate_profiles), now=_interfaces_api_runtime._utc_now())
        gate_tracks = gate_summary.get("tracks") if isinstance(gate_summary.get("tracks"), list) else []
        review_hashes = {
            str(row.get("review_id") or ""): {"path": str(row.get("path") or ""), "payload_hash": str(row.get("payload_hash") or "")}
            for row in manifest_acceptance.get("review_hashes", [])
            if isinstance(row, dict) and str(row.get("review_id") or "")
        }
        for row in gate_tracks:
            if not isinstance(row, dict):
                continue
            profile_id = str(row.get("profile_id") or "")
            track_id = str(row.get("track_id") or "")
            manifest_row = by_profile_track.get((profile_id, track_id))
            if not manifest_row:
                missing.append(f"{profile_id}/{track_id}")
                continue
            for field in ("status", "manifest_hash", "health_hash", "encoded_track_hash", "accepted_review_id"):
                if str(manifest_row.get(field) or "") != str(row.get(field) or ""):
                    mismatched.append(f"{profile_id}/{track_id}:{field}")
            review_id = str(row.get("accepted_review_id") or "")
            review_record = review_hashes.get(review_id) or {}
            review_path = str(review_record.get("path") or "")
            if not review_path:
                missing.append(f"{profile_id}/{track_id}:review")
                continue
            try:
                review = _interfaces_api_runtime.read_json(export_dir / review_path)
            except Exception:
                missing.append(review_path)
                continue
            if not isinstance(review, dict) or not _interfaces_api_runtime.encoded_audio_review_integrity_ok(review):
                mismatched.append(f"{profile_id}/{track_id}:review_integrity")
            if _interfaces_api_runtime.encoded_audio_review_integrity_hash(review if isinstance(review, dict) else {}) != str(review_record.get("payload_hash") or ""):
                mismatched.append(f"{profile_id}/{track_id}:review_hash")
        failed = bool(missing or mismatched or missing_profiles)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current encoded audio acceptance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
        }

    def _release_format_decision_export_gate(self, export_manifest: dict[str, Any], format_decision_gate: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_decision = export_manifest.get("format_decision") if isinstance(export_manifest.get("format_decision"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_decision or manifest_decision.get("status") in {"", "missing"}:
            missing.append("format_decision")
        release_id = str(export_manifest.get("release_id") or "")
        export_dir = self.release_store.export_dir(release_id)
        report_path = str(manifest_decision.get("report_path") or "format-decision/decision-report.json")
        report: dict[str, _interfaces_api_runtime.Any] = {}
        try:
            candidate = _interfaces_api_runtime.read_json(export_dir / report_path)
            report = candidate if isinstance(candidate, dict) else {}
        except Exception:
            missing.append(report_path)
        expected_report_hash = str(format_decision_gate.get("report_hash") or "")
        manifest_report_hash = str(manifest_decision.get("report_hash") or "")
        if expected_report_hash and manifest_report_hash != expected_report_hash:
            mismatched.append("report_hash")
        if report and str(report.get("integrity_hash") or "") != expected_report_hash:
            mismatched.append("report_payload")
        selected = set(manifest_decision.get("selected_profiles", []) if isinstance(manifest_decision.get("selected_profiles"), list) else [])
        gate_required = set(format_decision_gate.get("required_profiles", []) if isinstance(format_decision_gate.get("required_profiles"), list) else [])
        missing_profiles = sorted(gate_required - selected)
        failed = bool(missing or mismatched or missing_profiles)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current format decision evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
        }

    def _release_rights_clearance_export_gate(self, export_manifest: dict[str, Any], rights_gate: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_rights = export_manifest.get("rights_clearance") if isinstance(export_manifest.get("rights_clearance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_rights:
            missing.append("rights_clearance")
        for field in ("report_hash", "source_hash"):
            manifest_value = str(manifest_rights.get(field) or "")
            gate_value = str(rights_gate.get(field) or "")
            if not manifest_value or manifest_value != gate_value:
                mismatched.append(field)
        if str(manifest_rights.get("status") or "") != "passed":
            mismatched.append("status")
        failed = bool(missing or mismatched)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current rights clearance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "manifest_status": manifest_rights.get("status") or "missing",
        }

    def _distribution_encoded_audio_acceptance_export_gate(self, export_manifest: dict[str, Any], acceptance_gate: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_acceptance = export_manifest.get("encoded_audio_acceptance") if isinstance(export_manifest.get("encoded_audio_acceptance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_acceptance:
            missing.append("encoded_audio_acceptance")
        for field in ("source_hash", "summary_hash", "status"):
            manifest_value = str(manifest_acceptance.get(field) or "")
            gate_value = str(acceptance_gate.get(field) or "")
            if not manifest_value or manifest_value != gate_value:
                mismatched.append(field)
        manifest_profiles = {str(item) for item in manifest_acceptance.get("required_profiles", []) if str(item).strip()} if isinstance(manifest_acceptance.get("required_profiles"), list) else set()
        gate_profiles = {str(item) for item in acceptance_gate.get("required_profiles", []) if str(item).strip()} if isinstance(acceptance_gate.get("required_profiles"), list) else set()
        missing_profiles = sorted(gate_profiles - manifest_profiles)
        failed = bool(missing or mismatched or missing_profiles)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Distribution Export is stale. Rebuild export before signoff." if failed else "Distribution Export contains current encoded audio acceptance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
        }

    def _distribution_format_decision_export_gate(self, export_manifest: dict[str, Any], format_decision_gate: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_decision = export_manifest.get("format_decision") if isinstance(export_manifest.get("format_decision"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_decision or manifest_decision.get("status") in {"", "missing"}:
            missing.append("format_decision")
        if str(manifest_decision.get("report_hash") or "") != str(format_decision_gate.get("report_hash") or ""):
            mismatched.append("report_hash")
        gate_required = set(format_decision_gate.get("required_profiles", []) if isinstance(format_decision_gate.get("required_profiles"), list) else [])
        covered = set(manifest_decision.get("covered_profiles", []) if isinstance(manifest_decision.get("covered_profiles"), list) else [])
        missing_profiles = sorted(gate_required - covered)
        if isinstance(manifest_decision.get("missing_profiles"), list):
            missing_profiles = sorted(set(missing_profiles) | {str(item) for item in manifest_decision.get("missing_profiles", []) if str(item).strip()})
        role_incompatible = sorted({str(item) for item in manifest_decision.get("role_incompatible_profiles", []) if str(item).strip()}) if isinstance(manifest_decision.get("role_incompatible_profiles"), list) else []
        target = export_manifest.get("target") if isinstance(export_manifest.get("target"), dict) else {}
        coverage = _interfaces_api_runtime.distribution_target_format_decision_coverage(
            target,
            sorted(gate_required),
            {
                "selected_profiles": manifest_decision.get("selected_profiles", []),
                "archive_profiles": manifest_decision.get("archive_profiles", []),
            },
        )
        if sorted(covered) != list(coverage.get("covered_profiles", [])):
            mismatched.append("covered_profiles")
        role_incompatible = sorted(set(role_incompatible) | set(coverage.get("role_incompatible_profiles", [])))
        missing_profiles = sorted(set(missing_profiles) | set(coverage.get("missing_profiles", [])))
        failed = bool(missing or mismatched or missing_profiles or role_incompatible)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Distribution Export is stale. Rebuild export before signoff." if failed else "Distribution Export contains current format decision evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
            "role_incompatible_profiles": role_incompatible,
        }

    def _package_rights_clearance_export_gate(self, export_manifest: dict[str, Any], rights_gate: dict[str, Any], *, package_label: str) -> dict[str, _interfaces_api_runtime.Any]:
        manifest_rights = export_manifest.get("rights_clearance") if isinstance(export_manifest.get("rights_clearance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_rights:
            missing.append("rights_clearance")
        for field in ("report_hash", "source_hash"):
            manifest_value = str(manifest_rights.get(field) or "")
            gate_value = str(rights_gate.get(field) or "")
            if not manifest_value or manifest_value != gate_value:
                mismatched.append(field)
        if str(manifest_rights.get("status") or "") != "passed":
            mismatched.append("status")
        failed = bool(missing or mismatched)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": f"{package_label} Export is stale. Rebuild export before signoff." if failed else f"{package_label} Export contains current rights clearance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "manifest_status": manifest_rights.get("status") or "missing",
        }
