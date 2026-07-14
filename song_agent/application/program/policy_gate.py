from __future__ import annotations

from pathlib import Path
from typing import Any

from song_agent.application.evidence_policy_gate import evaluate_evidence_policy_gate, resolve_workspace_evidence_manifest
from song_agent.application.policy_compatibility import evaluate_gate_rows


PROGRAM_POLICY_IDS = {"program.continuity", "program.receiver_acceptance"}


class ProgramPolicyGate:
    """Policy-owned Program gate with a legacy fact projection at the boundary."""

    def __init__(self, program_store: Any) -> None:
        self.program_store = program_store

    def evaluate(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        policy_id = str(payload.get("policy") or payload.get("gate_policy") or "").strip()
        manifest = payload.get("evidence_manifest") or payload.get("evidence_graph_manifest")
        manifest_id = payload.get("evidence_manifest_id")
        if policy_id or manifest or manifest_id:
            return self._evaluate_manifest(program_id, policy_id, manifest, manifest_id)
        return self._evaluate_legacy(program_id, payload)

    def _evaluate_manifest(
        self,
        program_id: str,
        policy_id: str,
        manifest: Path | str | None,
        manifest_id: str | None,
    ) -> dict[str, Any]:
        if policy_id not in PROGRAM_POLICY_IDS:
            return _failed(policy_id, "program_policy_id")
        workspace = Path(self.program_store.root).parent.resolve()
        try:
            manifest_path = resolve_workspace_evidence_manifest(
                workspace,
                manifest_id=manifest_id,
                manifest=manifest,
            )
            result = evaluate_evidence_policy_gate(policy_id, manifest_path, allowed_root=workspace)
        except Exception:
            return _failed(policy_id, "program_policy_runtime")
        nodes = result.get("graph", {}).get("nodes", [])
        scoped = bool(nodes) and all(
            str(row.get("ref", {}).get("component_id") or "") == program_id
            for row in nodes
            if isinstance(row, dict)
        )
        if not scoped:
            result["status"] = "failed"
            result["hard_block"] = True
            result["blockers"] = sorted(
                set(result.get("blockers", [])) | {"policy.program_scope"}
            )
        result["program_id"] = program_id
        return result

    def _evaluate_legacy(self, program_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        legacy = self.program_store.gate(
            required=True,
            program_zip_path=payload.get("program_zip"),
            verification_report_path=payload.get("program_verification_report"),
            external_evidence_manifest_path=payload.get("external_evidence_manifest"),
            program_signoff_binding_path=payload.get("program_signoff_binding"),
        )
        result = evaluate_gate_rows(
            "program.compatibility",
            program_id,
            (("program_runtime", legacy),),
        )
        result["legacy_gate_summary"] = {
            "status": legacy.get("status"),
            "authoritative": False,
        }
        return result


def _failed(policy_id: str, blocker: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "hard_block": True,
        "policy_id": policy_id,
        "blockers": [blocker],
        "warnings": [],
        "checks": [],
    }
