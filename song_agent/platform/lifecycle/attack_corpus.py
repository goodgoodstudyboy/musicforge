from __future__ import annotations

from pathlib import Path

from song_agent.platform.contracts.lifecycle import ResetAuthorization, SignoffRef
from song_agent.platform.lifecycle.archive import ArchiveBuilder
from song_agent.platform.lifecycle.change_control import ChangeRequestService, ResetService
from song_agent.platform.lifecycle.event_ledger import HistoryChain
from song_agent.platform.lifecycle.registry import LifecycleCapabilityRegistry
from song_agent.platform.lifecycle.signoff import SignoffService
from song_agent.platform.verification.hashing import integrity_hash


def run_active_lifecycle_attack_corpus(
    root: Path,
    registry: LifecycleCapabilityRegistry,
) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    history = HistoryChain(root / "history.jsonl")
    signoff = SignoffService.seal(
        {"package_type": "test_signoff", "subject_id": "subject-001", "signed_by": "original", "source_hash": "a" * 64}
    )
    event = history.append(
        {"event_type": "signed", "signoff_hash": signoff["integrity_hash"], "signed_by": signoff["signed_by"]}
    )
    binding = SignoffService.seal(
        {"package_type": "test_binding", "signoff_hash": signoff["integrity_hash"], "history_event_hash": event["event_hash"]},
        payload_hash=False,
    )
    reference = SignoffRef(
        subject_id="subject-001",
        generation=1,
        signoff_hash=str(signoff["integrity_hash"]),
        binding_hash=str(binding["integrity_hash"]),
        history_event_hash=str(event["event_hash"]),
        source_hash="a" * 64,
    )
    valid_pair = SignoffService.validate_pair(signoff, binding)
    valid_history = SignoffService.validate_history_binding(history, reference)
    deleted_signoff_blocked = _delete_signoff_blocked(root, history)
    full_resign_blocked = _full_resign_blocked(root, reference)
    stale_snapshot_blocked = _stale_snapshot_blocked(root)
    cr_reuse_blocked = _cr_reuse_blocked()
    adoption = registry.adoption_report()
    results = {
        "signoff_pair": valid_pair,
        "history_binding": valid_history,
        "delete_signoff_file": deleted_signoff_blocked,
        "full_resign_signed_by": full_resign_blocked,
        "stale_source": stale_snapshot_blocked,
        "change_request_reuse": cr_reuse_blocked,
        "active_adoption": adoption["status"] == "passed",
    }
    return {
        "schema_version": 1,
        "status": "passed" if all(results.values()) else "failed",
        "results": results,
        "adoption": adoption,
    }


def _delete_signoff_blocked(root: Path, history: HistoryChain) -> bool:
    binding_path = root / "binding.json"
    binding_path.write_text("{}\n", encoding="utf-8")
    try:
        SignoffService.assert_transition_allowed(
            history,
            artifact_paths=(root / "signoff.json", binding_path),
            signed_event_types={"signed"},
            reset_event_types={"reset"},
        )
    except ValueError:
        return True
    return False


def _full_resign_blocked(root: Path, reference: SignoffRef) -> bool:
    forged = HistoryChain(root / "forged-history.jsonl")
    forged_signoff = SignoffService.seal(
        {"package_type": "test_signoff", "subject_id": "subject-001", "signed_by": "forged", "source_hash": "a" * 64}
    )
    forged.append(
        {"event_type": "signed", "signoff_hash": forged_signoff["integrity_hash"], "signed_by": "forged"}
    )
    return not SignoffService.validate_history_binding(forged, reference)


def _stale_snapshot_blocked(root: Path) -> bool:
    export = root / "export"
    expected = ArchiveBuilder.export_documents(export, {"report.json": {"status": "passed"}})
    (export / "report.json").write_text('{"status":"failed"}\n', encoding="utf-8")
    try:
        ArchiveBuilder.build_zip(export, root / "archive.zip", expected)
    except ValueError:
        return True
    return False


def _cr_reuse_blocked() -> bool:
    target = {"signoff_hash": "a" * 64}
    source = {"source_hash": "b" * 64}
    request = {
        "package_type": "test_change_request",
        "program_id": "subject-001",
        "change_request_id": "cr-001",
        "change_type": "reset_signoff",
        "allowed_actions": ["reset_signoff"],
        "target": target,
        "source": source,
        "status": "applied",
        "applied_at": "now",
        "submitted_request_hash": "c" * 64,
    }
    request["integrity_hash"] = integrity_hash(request)
    approval = {
        "package_type": "test_approval",
        "program_id": "subject-001",
        "change_request_id": "cr-001",
        "status": "approved",
        "approved_actions": ["reset_signoff"],
        "target": target,
        "source": source,
        "request_hash": request["submitted_request_hash"],
    }
    approval["integrity_hash"] = integrity_hash(approval)
    request["approval_hash"] = approval["integrity_hash"]
    request["integrity_hash"] = integrity_hash(request)
    try:
        ChangeRequestService.validate_reset_authorization(
            request,
            approval,
            ResetAuthorization("subject-001", "cr-001", "reset_signoff", "reset_signoff", target, source),
        )
    except ValueError:
        proof = ResetService.build_proof({"request_hash": request["integrity_hash"], "status": "applied"})
        return bool(proof.get("integrity_hash"))
    return False
