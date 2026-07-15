from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class DeliveryRoutesGetOrRefreshSubmissionQa:
    def _get_or_refresh_submission_qa(self, release_id: str, batch: Any, *, refresh: bool) -> dict[str, _interfaces_api_runtime.Any]:
        if not refresh:
            existing = self.submission_store.read_qa(release_id, batch.submission_id, default={})
            if existing:
                current = _interfaces_api_runtime.stable_hash(_interfaces_api_runtime.submission_source_state(store=self.submission_store, release_id=release_id, submission=batch))
                if str(existing.get("source_hash") or "") != current:
                    return _interfaces_api_runtime.mark_submission_qa_stale(existing, current_source_hash=current)
                return existing
        report = _interfaces_api_runtime.build_submission_qa_report(store=self.submission_store, release_id=release_id, submission=batch, now=_interfaces_api_runtime._utc_now())
        report = self.submission_store.write_qa(release_id, batch.submission_id, report)
        self.submission_store.update_qa_summary(release_id, batch.submission_id, _interfaces_api_runtime.submission_qa_summary(report))
        return report

    def _submission_payload_with_evidence_summary(self, release_id: str, batch: Any) -> dict[str, _interfaces_api_runtime.Any]:
        payload = batch.to_dict()
        try:
            overview = self.submission_evidence_store.overview(release_id, batch.submission_id)
            summary = overview.get("summary") if isinstance(overview.get("summary"), dict) else {}
            report_summary = overview.get("report_summary") if isinstance(overview.get("report_summary"), dict) else {}
            signoff_summary = overview.get("signoff_summary") if isinstance(overview.get("signoff_summary"), dict) else {}
            payload["latest_evidence_summary"] = {
                **summary,
                "status": report_summary.get("status") or summary.get("status") or "not_started",
                "signoff_status": signoff_summary.get("status") or summary.get("signoff_status") or "not_signed",
                "report_hash": report_summary.get("integrity_hash"),
            }
        except Exception:
            payload["latest_evidence_summary"] = {"status": "not_started", "signoff_status": "not_signed"}
        return payload

    def _build_distribution_layout(self, release_id: str, target: Any) -> dict[str, _interfaces_api_runtime.Any]:
        release = self.release_store.get_release(release_id)
        try:
            release_manifest = _interfaces_api_runtime.read_release_export_manifest(self.release_store, release_id)
        except FileNotFoundError:
            release_manifest = {}
        metadata = _interfaces_api_runtime.read_release_metadata(self.release_store, release_id, default={})
        template = self.distribution_store.resolve_target_template(target)
        artwork_id = str((target.options or {}).get("artwork_id") or "").strip()
        artwork = _interfaces_api_runtime.read_distribution_artwork(self.distribution_store, release_id, artwork_id) if artwork_id else latest_distribution_artwork(self.distribution_store, release_id)
        return _interfaces_api_runtime.build_distribution_layout_plan(
            release_id=release_id,
            target=target,
            release=release,
            release_manifest=release_manifest,
            release_metadata=metadata,
            template=template,
            artwork=artwork if isinstance(artwork, dict) else {},
            release_export_dir=self.release_store.export_dir(release_id),
        )
