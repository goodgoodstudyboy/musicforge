from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class DeliveryRoutesPart006:
    def _get_or_refresh_distribution_qa(self, release_id: str, target: Any, *, refresh: bool) -> dict[str, Any]:
        if not refresh:
            existing = self.distribution_store.read_qa(release_id, target.target_id, default={})
            if existing:
                release = self.release_store.get_release(release_id)
                current = stable_hash(distribution_source_state(store=self.distribution_store, release=release, target=target))
                if str(existing.get("source_hash") or "") != current:
                    return mark_distribution_qa_stale(existing, current_source_hash=current)
                return existing
        report = build_distribution_qa_report(store=self.distribution_store, release_id=release_id, target=target, now=_utc_now())
        report = self.distribution_store.write_qa(release_id, target.target_id, report)
        self.distribution_store.update_qa_summary(release_id, target.target_id, distribution_qa_summary(report))
        return report
