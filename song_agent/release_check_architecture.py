from __future__ import annotations

from pathlib import Path


def run_architecture_guardrails_smoke(root: Path) -> tuple[bool, str]:
    try:
        from song_agent.application.generation.service import generate_request as application_generate_request
        from song_agent.application.jobs.model import JobState as ApplicationJobState
        from song_agent.architecture_guardrails import evaluate_architecture, write_architecture_metrics
        from song_agent.cli import generate_request as cli_generate_request
        from song_agent.server import JobState as ServerJobState

        report = evaluate_architecture(root)
        write_architecture_metrics(report, root / "runs" / "architecture" / "metrics.json")
        metrics = dict(report.get("metrics") or {})
        blockers = list(report.get("blockers") or [])
        checks = {
            "boundaries": report.get("status"),
            "blocker_count": len(blockers),
            "job_state_compatibility": ServerJobState is ApplicationJobState,
            "generation_compatibility": cli_generate_request is application_generate_request,
            "module_count": metrics.get("module_count"),
            "cycle_count": metrics.get("cycle_count"),
            "mega_file_ratchet": "passed" if not any("mega_file_growth" in blocker for blocker in blockers) else "failed",
            "security_helper_ratchet": "passed" if not any("security_helper_growth" in blocker for blocker in blockers) else "failed",
        }
        ok = (
            report.get("status") == "passed"
            and checks["blocker_count"] == 0
            and checks["job_state_compatibility"] is True
            and checks["generation_compatibility"] is True
        )
        return ok, "v12.14 architecture guardrails: " + ", ".join(
            f"{key}={value}" for key, value in checks.items()
        )
    except Exception as exc:
        return False, f"v12.14 Architecture guardrails smoke failed: {exc}"


def run_architecture_ratchet_smoke(root: Path) -> tuple[bool, str]:
    try:
        from song_agent.architecture_guardrails import evaluate_architecture

        report = evaluate_architecture(root)
        ratchet = dict((report.get("metrics") or {}).get("ratchet") or {})
        delta = dict(ratchet.get("delta") or {})
        checks = {
            "status": ratchet.get("status"),
            "previous_release_tag": ratchet.get("previous_release_tag"),
            "active_import_delta": delta.get("active_to_compatibility_import_count"),
            "compatibility_debt_count": ratchet.get("compatibility_debt_count"),
            "interface_limits": (ratchet.get("interface_limits") or {}).get("status"),
            "blocker_count": len(ratchet.get("blockers") or []),
        }
        ok = (
            report.get("status") == "passed"
            and checks["status"] == "passed"
            and int(checks["active_import_delta"] or 0) < 0
            and int(checks["compatibility_debt_count"] or 0) > 0
            and checks["interface_limits"] == "passed"
            and checks["blocker_count"] == 0
        )
        return ok, "v13.1 architecture ratchet: " + ", ".join(f"{key}={value}" for key, value in checks.items())
    except Exception as exc:
        return False, f"v13.1 architecture ratchet smoke failed: {exc}"
