from __future__ import annotations

import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from song_agent.release_audio_baseline_governance import ReleaseAudioBaselineGovernanceStore
from song_agent.release_audio_command_center import ReleaseAudioCommandCenterStore
from song_agent.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStore
from song_agent.release_audio_quality_actions import ReleaseAudioQualityActionQueueStore
from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from song_agent.release_audio_regression import ReleaseAudioRegressionStore
from song_agent.release_audio_regression_response import ReleaseAudioRegressionResponseStore
from song_agent.release_checks import _v1010_signed_timeline_release


@dataclass
class CommandCenterFixture:
    release_id: str
    server: Any
    store: ReleaseAudioCommandCenterStore
    evidence: dict[str, Any]


@contextmanager
def command_center_fixture() -> Iterator[CommandCenterFixture]:
    servers: list[Any] = []
    try:
        baseline = _v1010_signed_timeline_release("Command Center Runtime Baseline")
        current = _v1010_signed_timeline_release("Command Center Runtime Track")
        servers.extend([baseline["server"], current["server"]])
        server = current["server"]

        baseline_store = ReleaseAudioBaselineGovernanceStore(release_store=baseline["server"].release_store)
        baseline_doc = baseline_store.create_from_release(
            baseline["release_id"],
            {
                "timeline": baseline["timeline_zip"],
                "timeline_verification_report": baseline["timeline_verification"],
                "certification": baseline["cert_zip"],
                "certification_verification_report": baseline["cert_verification"],
            },
        )
        baseline_store.approve(baseline_doc["baseline_id"], {"approved_by": "pytest", "reason": "Command Center baseline approved."})
        baseline_store.activate(baseline_doc["baseline_id"])
        baseline_zip = baseline_store.build_zip()
        baseline_store.verify_zip(strict=True, require_active=True)

        regression_store = ReleaseAudioRegressionStore(
            release_store=server.release_store,
            certification_store=current["timeline_store"].certification_store,
            timeline_store=current["timeline_store"],
        )
        regression_store.configure_baseline(
            current["release_id"],
            {
                "baseline_release_id": baseline["release_id"],
                "baseline_timeline": baseline["timeline_zip"],
                "baseline_timeline_verification_report": baseline["timeline_verification"],
                "baseline_certification": baseline["cert_zip"],
                "baseline_certification_verification_report": baseline["cert_verification"],
                "current_timeline": current["timeline_zip"],
                "current_timeline_verification_report": current["timeline_verification"],
                "current_certification": current["cert_zip"],
                "current_certification_verification_report": current["cert_verification"],
            },
        )
        regression_store.refresh_report(current["release_id"])
        regression_store.signoff(current["release_id"], {"signed_by": "pytest", "role": "audio_quality_lead"})
        regression_zip = regression_store.build_zip(current["release_id"])
        regression_store.verify_zip(current["release_id"], strict=True, require_passed=True, require_signed=True, require_current=True, require_baseline_current=True)

        response_store = ReleaseAudioRegressionResponseStore(release_store=server.release_store, regression_store=regression_store)
        response_store.create_plan(current["release_id"])
        response_store.run_safe_actions(current["release_id"])
        response_store.closeout(current["release_id"], {"closed_by": "pytest", "reason": "Command Center regression response closeout accepted."})
        response_store.signoff(current["release_id"], {"signed_by": "pytest", "role": "audio_quality_lead"})
        response_zip = response_store.build_zip(current["release_id"])
        response_store.verify_zip(current["release_id"], strict=True, require_closed=True, require_signed=True, require_regression_current=True, **response_store._response_verifier_kwargs(current["release_id"]))  # noqa: SLF001

        observatory_store = ReleaseAudioQualityObservatoryStore(release_store=server.release_store)
        observatory_id = observatory_store.create({"name": "Command Center Runtime Observatory", "release_ids": [current["release_id"]]})["observatory_id"]
        observatory_store.refresh(observatory_id)
        observatory_zip = observatory_store.build_zip(observatory_id)
        observatory_store.verify_zip(observatory_id, strict=True, require_current_evidence=True, require_no_critical_risk=True)

        queue_store = ReleaseAudioQualityActionQueueStore(release_store=server.release_store, observatory_store=observatory_store)
        queue_id = queue_store.create_from_observatory(observatory_id, name="Command Center Runtime Queue")["queue_id"]
        queue_store.run_safe(queue_id)
        queue_zip = queue_store.build_zip(queue_id)
        queue_store.verify_zip(queue_id, strict=True, require_current_observatory=True, require_no_blocking=False)

        signoff_store = ReleaseAudioQualityActionQueueSignoffStore(queue_store=queue_store, release_store=server.release_store)
        for item in signoff_store.list_manual_items(queue_id)["manual_items"]:
            signoff_store.resolve_manual_item(queue_id, item["item_id"], {"status": "completed", "resolved_by": "pytest", "reason": "Manual action handled."})
        signoff_store.refresh_closeout(queue_id)
        signoff_store.signoff(queue_id, {"signed_by": "pytest", "role": "audio_quality_lead", "reason": "Command Center queue signoff accepted."})
        signoff_archive = signoff_store.build_archive_zip(queue_id)
        signoff_store.verify_archive(queue_id, strict=True, require_current_queue=True, require_signed=True, require_no_unresolved_manual=True)

        evidence = {
            "certification": {"zip": current["cert_zip"], "verification_report": current["cert_verification"]},
            "timeline": {"zip": current["timeline_zip"], "verification_report": current["timeline_verification"]},
            "regression": {"zip": regression_zip["zip_path"], "verification_report": regression_store.verification_report_path(current["release_id"])},
            "baseline_governance": {"zip": baseline_zip["zip_path"], "verification_report": baseline_store.verification_report_path()},
            "regression_response": {"zip": response_zip["zip_path"], "verification_report": response_store.verification_report_path(current["release_id"])},
            "observatory": {"zip": observatory_zip["zip_path"], "verification_report": observatory_store.verification_report_path(observatory_id)},
            "action_queue": {"zip": queue_zip["zip_path"], "verification_report": queue_store.verification_report_path(queue_id)},
            "action_queue_signoff": {"zip": signoff_archive["zip_path"], "verification_report": signoff_store.archive_verification_report_path(queue_id)},
            "evidence_root": server.release_store.root,
        }
        store = ReleaseAudioCommandCenterStore(
            release_store=server.release_store,
            observatory_store=observatory_store,
            action_queue_store=queue_store,
            action_signoff_store=signoff_store,
        )
        yield CommandCenterFixture(release_id=current["release_id"], server=server, store=store, evidence=evidence)
    finally:
        for server in servers:
            close = getattr(server, "server_close", None)
            if callable(close):
                close()


def append_untrusted_entry(zip_path: Path | str) -> None:
    with zipfile.ZipFile(Path(zip_path), "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("unexpected-runtime.txt", b"unexpected runtime evidence\n")


def json_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    def convert(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {key: convert(child) for key, child in value.items()}
        if isinstance(value, list):
            return [convert(child) for child in value]
        return value

    return convert(evidence)
