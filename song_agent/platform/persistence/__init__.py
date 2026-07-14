"""Transactional local persistence for mutable MusicForge workflows."""

from song_agent.platform.persistence.database import MusicForgeDatabase
from song_agent.platform.persistence.file_artifacts import FileArtifactStore, write_json_atomic
from song_agent.platform.persistence.locks import WorkspaceLock, WorkspaceLockError
from song_agent.platform.persistence.migrations import LegacyWorkspaceMigrator
from song_agent.platform.persistence.program import (
    PROGRAM_COMPONENTS,
    ProgramAggregate,
    ProgramDocumentRecord,
    ProgramPersistenceError,
    ProgramStateRepository,
    program_json_facade,
    read_program_json,
    write_program_json,
)
from song_agent.platform.persistence.recovery import PersistenceRecovery
from song_agent.platform.persistence.repository import WorkflowRecord, WorkflowRepository
from song_agent.platform.persistence.unit_of_work import FileUnitOfWork
from song_agent.platform.persistence.v13_migration import V13MigrationOrchestrator, migration_anchor_path, verify_v13_migration_evidence

__all__ = [
    "FileArtifactStore",
    "FileUnitOfWork",
    "LegacyWorkspaceMigrator",
    "MusicForgeDatabase",
    "PROGRAM_COMPONENTS",
    "ProgramAggregate",
    "ProgramDocumentRecord",
    "ProgramPersistenceError",
    "ProgramStateRepository",
    "program_json_facade",
    "PersistenceRecovery",
    "WorkflowRecord",
    "WorkflowRepository",
    "WorkspaceLock",
    "WorkspaceLockError",
    "V13MigrationOrchestrator",
    "migration_anchor_path",
    "verify_v13_migration_evidence",
    "read_program_json",
    "write_json_atomic",
    "write_program_json",
]
