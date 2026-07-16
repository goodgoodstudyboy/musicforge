from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from typing import Any


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class DeliveryRoutesGetOrRefreshDistributionQa:
    def _get_or_refresh_distribution_qa(self, release_id: str, target: Any, *, refresh: bool) -> ImplementationDocument:
        if not refresh:
            existing = self.distribution_store.read_qa(release_id, target.target_id, default={})
            if existing:
                release = self.release_store.get_release(release_id)
                current = _interfaces_api_runtime.stable_hash(_interfaces_api_runtime.distribution_source_state(store=self.distribution_store, release=release, target=target))
                if str(existing.get("source_hash") or "") != current:
                    return _interfaces_api_runtime.mark_distribution_qa_stale(existing, current_source_hash=current)
                return existing
        report = _interfaces_api_runtime.build_distribution_qa_report(store=self.distribution_store, release_id=release_id, target=target, now=_interfaces_api_runtime._utc_now())
        report = self.distribution_store.write_qa(release_id, target.target_id, report)
        self.distribution_store.update_qa_summary(release_id, target.target_id, _interfaces_api_runtime.distribution_qa_summary(report))
        return report
