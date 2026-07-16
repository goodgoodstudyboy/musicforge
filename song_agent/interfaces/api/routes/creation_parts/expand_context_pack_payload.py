from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesExpandContextPackPayload:
    def _expand_context_pack_payload(self, payload: ImplementationDocument) -> dict[str, _interfaces_api_runtime.Any]:
        pack_id = str(payload.get("context_pack_id") or "").strip()
        if not pack_id:
            return payload
        pack = self.context_pack_store.read_pack(pack_id)
        applied = _interfaces_api_runtime.apply_context_pack(pack, asset_store=self.asset_store, reference_store=self.reference_store, captured_at=_interfaces_api_runtime._utc_now())
        asset_refs = _interfaces_api_runtime.merge_context_refs(payload.get("asset_refs"), applied["asset_refs"], "asset_id", 5)
        reference_refs = _interfaces_api_runtime.merge_context_refs(payload.get("reference_refs"), applied["reference_refs"], "reference_id", 5)
        return {
            **payload,
            "asset_refs": asset_refs,
            "reference_refs": reference_refs,
            "context_pack": _interfaces_api_runtime.context_pack_snapshot(pack, {"asset_refs": asset_refs, "reference_refs": reference_refs}, captured_at=_interfaces_api_runtime._utc_now()),
        }
