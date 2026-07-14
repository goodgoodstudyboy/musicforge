"""Composable lifecycle primitives for signed MusicForge evidence."""

from song_agent.platform.lifecycle.archive import ArchiveBuilder, ImmutableSnapshotGuard
from song_agent.platform.lifecycle.change_control import ChangeRequestService, ResetService
from song_agent.platform.lifecycle.event_ledger import HistoryChain, HistoryMigrationReport, HistoryValidation
from song_agent.platform.lifecycle.generation import GenerationService
from song_agent.platform.lifecycle.signoff import SignoffService
from song_agent.platform.lifecycle.registry import LifecycleCapability, LifecycleCapabilityRegistry, active_lifecycle_registry

__all__ = [
    "ArchiveBuilder",
    "ChangeRequestService",
    "GenerationService",
    "HistoryChain",
    "HistoryMigrationReport",
    "HistoryValidation",
    "ImmutableSnapshotGuard",
    "ResetService",
    "SignoffService",
    "LifecycleCapability",
    "LifecycleCapabilityRegistry",
    "active_lifecycle_registry",
]
