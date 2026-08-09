from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from song_agent.application.evidence_policy_gate import (
    EvidencePolicyGateError,
    resolve_workspace_evidence_manifest,
)
from song_agent.domains.trust.ga_readiness import (
    REQUIRED_DOCS,
    build_ga_readiness_report,
    write_ga_readiness_report,
)
from song_agent.platform.contracts import JsonDocument
from song_agent.platform.contracts.documents import normalize_json_document
from song_agent.platform.persistence.file_artifacts import read_json_document
from song_agent.platform.version import VERSION

MAINTENANCE_CHECK_PROFILES = ("daily", "emergency", "release", "weekly")


class ReleaseCheckResultPort(Protocol):
    ok: bool


class ReleaseCheckReportPort(Protocol):
    ok: bool
    results: Sequence[ReleaseCheckResultPort]


class ReleaseCheckExecutor(Protocol):
    def __call__(
        self,
        *,
        repo_root: Path,
        profile: str,
        run_tests: bool,
    ) -> ReleaseCheckReportPort: ...


class MaintenanceBackupPort(Protocol):
    def list_backups(self) -> Sequence[Mapping[str, object]]: ...

    def create_backup(self, *, mode: str) -> Mapping[str, object]: ...

    def read_backup(self, backup_id: str) -> Mapping[str, object]: ...

    def verify_backup(self, backup_id: str) -> Mapping[str, object]: ...

    def backup_zip_path(self, backup_id: str) -> Path: ...

    def restore_plan(
        self,
        *,
        backup_id: str | None,
        zip_path: Path | None,
        target: Path,
    ) -> Mapping[str, object]: ...

    def restore(
        self,
        *,
        backup_id: str | None,
        zip_path: Path | None,
        target: Path,
        confirm: bool,
        overwrite: bool,
        allow_current_workspace: bool,
    ) -> Mapping[str, object]: ...


class MaintenanceStorePort(Protocol):
    @property
    def backups(self) -> MaintenanceBackupPort: ...

    @property
    def check_runs_dir(self) -> Path: ...

    def status(self) -> Mapping[str, object]: ...

    def run_upgrade_preflight(
        self,
        *,
        target_version: str,
        require_verified_backup: bool,
        allow_dirty: bool,
    ) -> Mapping[str, object]: ...

    def migration_status(self) -> Mapping[str, object]: ...

    def migration_plan(self) -> Mapping[str, object]: ...

    def run_migrations(self, *, require_backup: bool) -> Mapping[str, object]: ...

    def list_check_runs(self) -> Sequence[Mapping[str, object]]: ...

    def run_check(self, *, profile: str) -> Mapping[str, object]: ...


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


@dataclass(frozen=True)
class GaReadinessCommand:
    policy: str | None
    evidence_manifest_id: str | None
    evidence_manifest: str | None
    strict: bool
    allow_dirty: bool
    require_manual_acceptance: bool
    require_audio: bool
    require_audio_campaign: bool
    audio_campaign_id: str | None
    audio_campaign_archive_zip_path: str | None
    audio_campaign_archive_verification_report_path: str | None
    require_final_readiness: bool
    final_handoff_verification_report_path: str | None
    release_check_latest_report_path: str | None
    release_check_ga_report_path: str | None
    run_release_checks: bool
    skip_tests: bool

    @classmethod
    def from_document(cls, payload: JsonDocument) -> GaReadinessCommand:
        manifest = payload.get("evidence_manifest")
        return cls(
            policy=_optional_text(payload.get("policy")),
            evidence_manifest_id=_optional_text(payload.get("evidence_manifest_id")),
            evidence_manifest=manifest if isinstance(manifest, str) else None,
            strict=bool(payload.get("strict", False)),
            allow_dirty=bool(payload.get("allow_dirty", False)),
            require_manual_acceptance=bool(payload.get("require_manual_acceptance", False)),
            require_audio=bool(payload.get("require_audio", False)),
            require_audio_campaign=bool(payload.get("require_audio_campaign", False) or payload.get("audio_campaign_id")),
            audio_campaign_id=_optional_text(payload.get("audio_campaign_id")),
            audio_campaign_archive_zip_path=_optional_text(
                payload.get("audio_campaign_archive_zip_path") or payload.get("audio_campaign_archive")
            ),
            audio_campaign_archive_verification_report_path=_optional_text(
                payload.get("audio_campaign_archive_verification_report_path") or payload.get("audio_campaign_archive_verification_report")
            ),
            require_final_readiness=bool(payload.get("require_final_readiness", False)),
            final_handoff_verification_report_path=_optional_text(payload.get("final_handoff_verification_report_path")),
            release_check_latest_report_path=_optional_text(payload.get("release_check_latest_report_path")),
            release_check_ga_report_path=_optional_text(payload.get("release_check_ga_report_path")),
            run_release_checks=bool(payload.get("run_release_checks", False)),
            skip_tests=bool(payload.get("skip_tests", True)),
        )


class MaintenanceApplication:
    """Application boundary for GA readiness and LTS maintenance workflows."""

    def __init__(
        self,
        repo_root: Path,
        *,
        store: MaintenanceStorePort,
        release_check_executor: ReleaseCheckExecutor | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self._store = store
        self._release_check_executor = release_check_executor

    def ga_status(self) -> JsonDocument:
        return normalize_json_document(build_ga_readiness_report(repo_root=self.repo_root))

    def run_ga_check(self, command: GaReadinessCommand) -> JsonDocument:
        if command.run_release_checks and self._release_check_executor is None:
            raise RuntimeError("Release-check execution is not configured for maintenance.")
        manifest_path = None
        if command.policy:
            manifest_path = resolve_workspace_evidence_manifest(
                self.repo_root,
                manifest_id=command.evidence_manifest_id,
                manifest=command.evidence_manifest,
            )
        report = normalize_json_document(
            build_ga_readiness_report(
                repo_root=self.repo_root,
                policy=command.policy,
                evidence_manifest_path=manifest_path,
                strict=command.strict,
                allow_dirty=command.allow_dirty,
                require_manual_acceptance=command.require_manual_acceptance,
                require_audio=command.require_audio,
                require_audio_campaign=command.require_audio_campaign,
                audio_campaign_id=command.audio_campaign_id,
                audio_campaign_archive_zip_path=command.audio_campaign_archive_zip_path,
                audio_campaign_archive_verification_report_path=(command.audio_campaign_archive_verification_report_path),
                require_final_readiness=command.require_final_readiness,
                final_handoff_verification_report_path=(command.final_handoff_verification_report_path),
                release_check_latest_report_path=command.release_check_latest_report_path,
                release_check_ga_report_path=command.release_check_ga_report_path,
                run_release_checks=command.run_release_checks,
                skip_tests=command.skip_tests,
                release_check_executor=self._release_check_executor,
            )
        )
        write_ga_readiness_report(report)
        return report

    def docs_index(self) -> JsonDocument:
        docs = [
            {
                "path": rel,
                "exists": (self.repo_root / rel).exists(),
                "title": Path(rel).stem.replace("_", " ").replace("-", " ").title(),
            }
            for rel in REQUIRED_DOCS
        ]
        return normalize_json_document(
            {
                "docs": docs,
                "summary": {
                    "required_count": len(REQUIRED_DOCS),
                    "present_count": sum(1 for item in docs if item["exists"]),
                },
            }
        )

    def status(self) -> JsonDocument:
        return normalize_json_document(self._store.status())

    def list_backups(self) -> list[JsonDocument]:
        return [normalize_json_document(item) for item in self._store.backups.list_backups()]

    def create_backup(self, mode: str) -> JsonDocument:
        return normalize_json_document(self._store.backups.create_backup(mode=mode))

    def read_backup(self, backup_id: str) -> JsonDocument:
        return normalize_json_document(self._store.backups.read_backup(backup_id))

    def verify_backup(self, backup_id: str) -> JsonDocument:
        return normalize_json_document(self._store.backups.verify_backup(backup_id))

    def backup_zip_path(self, backup_id: str) -> Path:
        return self._store.backups.backup_zip_path(backup_id)

    def restore_plan(
        self,
        *,
        backup_id: str | None,
        zip_path: Path | None,
        target: Path,
    ) -> JsonDocument:
        return normalize_json_document(
            self._store.backups.restore_plan(
                backup_id=backup_id,
                zip_path=zip_path,
                target=target,
            )
        )

    def restore_backup(
        self,
        *,
        backup_id: str | None,
        zip_path: Path | None,
        target: Path,
        confirm: bool,
        overwrite: bool,
        allow_current_workspace: bool,
    ) -> JsonDocument:
        return normalize_json_document(
            self._store.backups.restore(
                backup_id=backup_id,
                zip_path=zip_path,
                target=target,
                confirm=confirm,
                overwrite=overwrite,
                allow_current_workspace=allow_current_workspace,
            )
        )

    def run_upgrade_preflight(
        self,
        *,
        target_version: str | None,
        require_verified_backup: bool,
        allow_dirty: bool,
    ) -> JsonDocument:
        return normalize_json_document(
            self._store.run_upgrade_preflight(
                target_version=target_version or VERSION,
                require_verified_backup=require_verified_backup,
                allow_dirty=allow_dirty,
            )
        )

    def migration_overview(self) -> JsonDocument:
        return {
            "migration": normalize_json_document(self._store.migration_status()),
            "plan": normalize_json_document(self._store.migration_plan()),
        }

    def migration_status(self) -> JsonDocument:
        return normalize_json_document(self._store.migration_status())

    def migration_plan(self) -> JsonDocument:
        return normalize_json_document(self._store.migration_plan())

    def run_migrations(self, *, require_backup: bool) -> JsonDocument:
        return normalize_json_document(self._store.run_migrations(require_backup=require_backup))

    def list_check_runs(self) -> list[JsonDocument]:
        return [normalize_json_document(item) for item in self._store.list_check_runs()]

    def run_check(self, profile: str) -> JsonDocument:
        return normalize_json_document(self._store.run_check(profile=profile))

    def read_check(self, run_id: str) -> JsonDocument:
        return read_json_document(self._store.check_runs_dir / run_id / "maintenance-check-report.json")


class MaintenanceServerPort(Protocol):
    maintenance_application: MaintenanceApplication


__all__ = [
    "EvidencePolicyGateError",
    "GaReadinessCommand",
    "MAINTENANCE_CHECK_PROFILES",
    "MaintenanceApplication",
    "MaintenanceBackupPort",
    "MaintenanceServerPort",
    "MaintenanceStorePort",
]
