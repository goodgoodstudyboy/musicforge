from __future__ import annotations

from pathlib import Path

from song_agent.application.maintenance import MaintenanceApplication
from song_agent.domains.creation.lts_maintenance import LTSMaintenanceStore
from song_agent.release_check.runner import run_release_check_matrix


def build_maintenance_application(repo_root: Path) -> MaintenanceApplication:
    """Compose maintenance workflows with the release-check adapter."""
    return MaintenanceApplication(
        repo_root,
        store=LTSMaintenanceStore(repo_root=repo_root.resolve()),
        release_check_executor=run_release_check_matrix,
    )


__all__ = ["build_maintenance_application"]
