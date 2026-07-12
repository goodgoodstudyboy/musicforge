from __future__ import annotations

import json
import tempfile
from pathlib import Path

from song_agent.platform.contracts.lifecycle import ResetAuthorization, SignoffRef
from song_agent.platform.lifecycle import ArchiveBuilder, ChangeRequestService, HistoryChain, SignoffService
from song_agent.platform.verification.hashing import integrity_hash


ACTIVE_V12_LIFECYCLE_STORES = (
    "unified_release_program.py",
    "unified_release_program_operations.py",
    "unified_release_program_handoff.py",
    "unified_release_program_vault.py",
    "unified_release_program_vault_operations.py",
    "unified_release_program_continuity.py",
    "unified_release_program_continuity_acceptance.py",
    "unified_release_program_continuity_acceptance_change.py",
    "unified_release_program_continuity_command_center_signoff.py",
    "unified_release_program_continuity_command_center_acceptance.py",
    "unified_release_program_continuity_command_center_acceptance_change.py",
)


def run_lifecycle_kernel_smoke(root: Path) -> tuple[bool, str]:
    del root
    try:
        with tempfile.TemporaryDirectory(prefix="mf-v1216-lifecycle-kernel-") as temp:
            base = Path(temp)
            history = HistoryChain(base / "history.jsonl")
            signed = history.append({"event_type": "signed", "signoff_hash": "signoff-1"})
            reference = SignoffRef("subject-1", 1, "signoff-1", "binding-1", signed["event_hash"])
            history_happy = history.validate().valid and SignoffService.validate_history_binding(history, reference)

            forged = HistoryChain.build_event(
                {"event_type": "signed", "signoff_hash": "forged-signoff"},
                previous_event_hash="",
            )
            history.path.write_text(json.dumps(forged, sort_keys=True) + "\n", encoding="utf-8")
            history_full_resign = history.validate().valid and not SignoffService.validate_history_binding(history, reference)

            migrated = base / "migrated.jsonl"
            migration = history.migrate_copy(
                migrated,
                source_schema_version=1,
                target_schema_version=2,
                adapter=lambda rows: [{**row, "schema_version": 2} for row in rows],
            )
            migration_explicit = migration.source_hash != migration.target_hash and Path(migration.rollback_path).is_file()

            target = {"signoff_hash": "signoff-1", "generation": 1}
            source = {"source_hash": "source-1"}
            request = {
                "program_id": "subject-1",
                "change_request_id": "cr-1",
                "change_type": "reset_signoff",
                "allowed_actions": ["reset_signoff"],
                "status": "approved",
                "target": target,
                "source": source,
            }
            approval = _integrity({"program_id": "subject-1", "change_request_id": "cr-1", "status": "approved", "target": target, "source": source, "approved_actions": ["reset_signoff"]})
            request["approval_hash"] = approval["integrity_hash"]
            request = _integrity(request)
            expected = ResetAuthorization("subject-1", "cr-1", "reset_signoff", "reset_signoff", target, source)
            ChangeRequestService.validate_reset_authorization(request, approval, expected)
            wrong_action = _rejected({**request, "allowed_actions": ["refresh"]}, approval, expected)
            wrong_target = _rejected({**request, "target": {"signoff_hash": "wrong"}}, approval, expected)
            wrong_source = _rejected({**request, "source": {"source_hash": "wrong"}}, approval, expected)
            reused = _rejected({**request, "applied_at": "2026-07-13T00:00:00Z"}, approval, expected)
            resigned_approval = _rejected(request, {**approval, "target": {"signoff_hash": "wrong"}}, expected, resign_approval=True)

            export_dir = base / "export"
            zip_path = base / "archive.zip"
            documents = {"manifest.json": {"status": "passed"}, "README.txt": "lifecycle\n"}
            payloads = ArchiveBuilder.export_documents(export_dir, documents)
            ArchiveBuilder.build_zip(export_dir, zip_path, payloads)
            zip_path.write_bytes(zip_path.read_bytes() + b"tamper")
            archive_tamper = False
            try:
                ArchiveBuilder.build_zip(export_dir, zip_path, payloads)
            except ValueError:
                archive_tamper = True

        source_root = Path(__file__).resolve().parent
        forbidden = ('event["payload_hash"] = stable_hash', 'event["event_hash"] = stable_hash')
        stores_migrated = all(
            "HistoryChain" in (source_root / filename).read_text(encoding="utf-8")
            and not any(token in (source_root / filename).read_text(encoding="utf-8") for token in forbidden)
            for filename in ACTIVE_V12_LIFECYCLE_STORES
        )
        signals = {
            "history_happy": history_happy,
            "history_full_resign": history_full_resign,
            "migration_explicit": migration_explicit,
            "wrong_action": wrong_action,
            "wrong_target": wrong_target,
            "wrong_source": wrong_source,
            "cr_reuse": reused,
            "resigned_approval": resigned_approval,
            "archive_tamper": archive_tamper,
            "active_stores_migrated": stores_migrated,
        }
        return all(signals.values()), "v12.16 lifecycle kernel: " + ", ".join(f"{key}={value}" for key, value in signals.items())
    except Exception as exc:
        return False, f"v12.16 Lifecycle Kernel smoke failed: {exc}"


def _integrity(document: dict[str, object]) -> dict[str, object]:
    result = dict(document)
    result["integrity_hash"] = integrity_hash(result)
    return result


def _rejected(
    request: dict[str, object],
    approval: dict[str, object],
    expected: ResetAuthorization,
    *,
    resign_approval: bool = False,
) -> bool:
    candidate_request = _integrity({**request, "integrity_hash": ""})
    candidate_approval = _integrity({**approval, "integrity_hash": ""}) if resign_approval else approval
    try:
        ChangeRequestService.validate_reset_authorization(candidate_request, candidate_approval, expected)
    except ValueError:
        return True
    return False
