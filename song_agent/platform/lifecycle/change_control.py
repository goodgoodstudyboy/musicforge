from __future__ import annotations

from typing import Any

from song_agent.platform.contracts.lifecycle import ResetAuthorization
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok


class ChangeRequestService:
    @staticmethod
    def validate_reset_authorization(
        request: dict[str, Any],
        approval: dict[str, Any],
        expected: ResetAuthorization,
        *,
        approved_actions_field: str = "approved_actions",
    ) -> None:
        if not integrity_ok(request) or request.get("status") != "approved" or request.get("applied_at"):
            raise ValueError("Change Request must be approved, valid, and unused.")
        if request.get("program_id") != expected.subject_id or request.get("change_request_id") != expected.request_id:
            raise ValueError("Change Request identity mismatch.")
        if request.get("change_type") != expected.change_type or expected.action not in set(request.get("allowed_actions") or []):
            raise ValueError("Change Request does not authorize the reset action.")
        if not integrity_ok(approval) or approval.get("status") != "approved":
            raise ValueError("Change Request approval proof is invalid.")
        if approval.get("program_id") != expected.subject_id or approval.get("change_request_id") != expected.request_id:
            raise ValueError("Approval identity mismatch.")
        if approval.get("target") != request.get("target") or request.get("target") != expected.target:
            raise ValueError("Approval target binding mismatch.")
        if expected.source is not None and (approval.get("source") != request.get("source") or request.get("source") != expected.source):
            raise ValueError("Approval source binding mismatch.")
        approved_actions = set(approval.get(approved_actions_field) or [])
        if approved_actions and expected.action not in approved_actions:
            raise ValueError("Approval does not authorize the reset action.")
        submitted_hash = request.get("submitted_request_hash") or request.get("request_hash")
        if approval.get("request_hash") and submitted_hash and approval.get("request_hash") != submitted_hash:
            raise ValueError("Approval request hash mismatch.")
        if request.get("approval_hash") and request.get("approval_hash") != approval.get("integrity_hash"):
            raise ValueError("Change Request approval hash mismatch.")


class ResetService:
    @staticmethod
    def build_proof(payload: dict[str, Any]) -> dict[str, Any]:
        proof = dict(payload)
        proof["integrity_hash"] = integrity_hash(proof)
        return proof

    @staticmethod
    def mark_applied(request: dict[str, Any], *, applied_at: str, proof_hash: str, event_hash: str) -> dict[str, Any]:
        result = dict(request)
        result.update({"status": "applied", "applied_at": applied_at, "reset_proof_hash": proof_hash, "reset_event_hash": event_hash})
        result["integrity_hash"] = integrity_hash(result)
        return result
