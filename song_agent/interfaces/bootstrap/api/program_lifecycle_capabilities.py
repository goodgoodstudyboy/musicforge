from __future__ import annotations
from inspect import getsourcefile
from pathlib import Path
from song_agent.domains.program.unified_release_program import UnifiedReleaseProgramStore
from song_agent.domains.program.unified_release_program_operations import UnifiedReleaseProgramOperationsStore
from song_agent.domains.program.unified_release_program_handoff import UnifiedReleaseProgramHandoffStore
from song_agent.domains.program.unified_release_program_vault import UnifiedReleaseProgramVaultStore
from song_agent.domains.program.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStore
from song_agent.domains.program.unified_release_program_continuity import UnifiedReleaseProgramContinuityStore
from song_agent.domains.program.unified_release_program_continuity_distribution import UnifiedReleaseProgramContinuityDistributionStore
from song_agent.domains.program.unified_release_program_continuity_acceptance import UnifiedReleaseProgramContinuityAcceptanceStore
from song_agent.domains.program.unified_release_program_continuity_acceptance_change import UnifiedReleaseProgramContinuityAcceptanceChangeStore
from song_agent.domains.program.unified_release_program_continuity_command_center import UnifiedReleaseProgramContinuityCommandCenterStore
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff import UnifiedReleaseProgramContinuityCommandCenterSignoffStore
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance import UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change import UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore
from song_agent.platform.lifecycle.registry import LifecycleCapability, LifecycleCapabilityRegistry

def _lifecycle_capability(component_type: str, store_type: type[object], *, signoff: str='', reset: str='', archive: str='', services: tuple[str, ...]) -> LifecycleCapability:
    return LifecycleCapability(component_type=component_type, module=store_type.__module__, store_class=store_type.__name__, store_type=store_type, source_path=Path(getsourcefile(store_type) or ''), signoff_method=signoff, reset_method=reset, archive_method=archive, required_services=services)
ACTIVE_LIFECYCLE_CAPABILITIES = (
    _lifecycle_capability('unified_release_program', UnifiedReleaseProgramStore, signoff='signoff', archive='build_zip', services=('HistoryChain', 'SignoffService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_operations', UnifiedReleaseProgramOperationsStore, reset='reset_program_signoff', archive='build_operations_archive_zip', services=('HistoryChain', 'ChangeRequestService', 'ResetService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_handoff', UnifiedReleaseProgramHandoffStore, signoff='signoff_handoff', archive='build_handoff_archive_zip', services=('HistoryChain', 'SignoffService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_vault', UnifiedReleaseProgramVaultStore, archive='build_vault_zip', services=('HistoryChain', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_vault_operations', UnifiedReleaseProgramVaultOperationsStore, signoff='signoff_operations', archive='build_archive_zip', services=('HistoryChain', 'SignoffService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_continuity', UnifiedReleaseProgramContinuityStore, signoff='signoff_continuity', archive='build_archive_zip', services=('HistoryChain', 'SignoffService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_continuity_kit', UnifiedReleaseProgramContinuityDistributionStore, archive='build_kit_zip', services=('ArchiveBuilder',)),
    _lifecycle_capability('unified_release_program_continuity_acceptance', UnifiedReleaseProgramContinuityAcceptanceStore, signoff='signoff_acceptance', archive='build_archive_zip', services=('HistoryChain', 'SignoffService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_continuity_acceptance_change', UnifiedReleaseProgramContinuityAcceptanceChangeStore, reset='reset_acceptance_signoff', archive='build_archive_zip', services=('HistoryChain', 'ChangeRequestService', 'ResetService', 'GenerationService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_continuity_command_center', UnifiedReleaseProgramContinuityCommandCenterStore, archive='build_zip', services=('ArchiveBuilder',)),
    _lifecycle_capability('unified_release_program_continuity_command_center_signoff', UnifiedReleaseProgramContinuityCommandCenterSignoffStore, signoff='signoff', reset='reset_signoff', archive='build_archive_zip', services=('HistoryChain', 'SignoffService', 'ChangeRequestService', 'ResetService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_receiver_acceptance', UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore, signoff='signoff', archive='build_archive_zip', services=('HistoryChain', 'SignoffService', 'ArchiveBuilder')),
    _lifecycle_capability('unified_release_program_receiver_acceptance_change', UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore, reset='reset_receiver_acceptance_signoff', archive='build_archive_zip', services=('HistoryChain', 'ChangeRequestService', 'ResetService', 'GenerationService', 'ArchiveBuilder')),
)
active_lifecycle_registry = LifecycleCapabilityRegistry(ACTIVE_LIFECYCLE_CAPABILITIES)
__all__ = ['ACTIVE_LIFECYCLE_CAPABILITIES', 'active_lifecycle_registry']
